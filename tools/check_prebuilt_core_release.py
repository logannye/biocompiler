"""Independently verify complete staged wheels and retained material companions.

No imports from either wheel, native execution, extraction or publication occur.
CI supplies source/tested/run identity and material pins independently of artifacts.
"""
from __future__ import annotations
import argparse
import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import struct
import zipfile

if __package__:
    from . import build_prebuilt_core as build, prebuilt_core_materials as materials
else:
    import build_prebuilt_core as build
    import prebuilt_core_materials as materials

require, canonical, sha = build.require, build.canonical, build.sha
MAX_ARCHIVE = 1536 * 1024 * 1024


def document(raw, maximum=1024*1024, *, require_canonical=True):
    require(type(raw) is bytes and len(raw) <= maximum, 'Oversized release control document')
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result, 'Duplicate release control field')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('Nonfinite release control constant: '+value)
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    require(not require_canonical or canonical(value) == raw, 'Noncanonical release control document')
    return value


def archive_members(archive, *, maximum_files, maximum_total, maximum_file, stored=False, _sdk_backend_record=False):
    require(not archive.comment, 'Archive has an unbound comment')
    rows, size = {}, 0
    for entry in archive.infolist():
        name = materials.logical(entry.filename)
        mode = entry.external_attr >> 16
        require(name not in rows and not entry.is_dir() and stat.S_ISREG(mode), 'Repeated or nonregular archive member')
        require(entry.create_system == 3 and not entry.extra and not entry.comment and entry.flag_bits & ~0x800 == 0
            and entry.compress_type in ((zipfile.ZIP_STORED,) if stored else (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED))
            and entry.date_time == (1980,1,1,0,0,0), 'Unreviewed archive metadata')
        # The pinned SDK backend writes only RECORD as regular0664. This private
        # staging allowance is never used by the final wheel/companion readers.
        modes = (0o644,0o755,0o664) if _sdk_backend_record and name == 'biocompiler-'+build.VERSION+'.dist-info/RECORD' else (0o644,0o755)
        require(0 <= entry.file_size <= maximum_file and stat.S_IMODE(mode) in modes, 'Invalid archive mode or member size')
        size += entry.file_size
        require(size <= maximum_total and len(rows) < maximum_files, 'Archive complete expansion exceeds limit')
        rows[name] = entry
    stream = archive.fp
    cursor = 0
    for name, entry in rows.items():
        require(entry.header_offset == cursor, 'Archive has an unclaimed prefix, gap or reordered local header')
        stream.seek(cursor); header = stream.read(30)
        require(len(header) == 30, 'Truncated archive local header')
        signature, version, flags, method, time, date, crc, compressed, size, namesize, extra = struct.unpack('<I5H3I2H',header)
        require(signature == 0x04034b50 and version <= 20 and flags == entry.flag_bits
            and time == 0 and date == 33 and method == entry.compress_type and crc == entry.CRC and compressed == entry.compress_size
            and size == entry.file_size and extra == 0, 'Local and central archive authority differ')
        require(stream.read(namesize) == name.encode('utf-8'), 'Local archive name differs')
        cursor += 30 + namesize + compressed
    require(cursor == archive.start_dir, 'Archive local content does not close at central directory')
    stream.seek(0,2); length = stream.tell()
    require(length >= 22, 'Truncated archive end record')
    stream.seek(length-22); end = struct.unpack('<I4H2IH',stream.read(22))
    require(end == (0x06054b50,0,0,len(rows),len(rows),
        sum(46+len(name.encode('utf-8')) for name in rows),cursor,0)
        and cursor+end[5]+22 == length, 'Archive has an unclaimed central record or trailing bytes')
    return rows


def read_wheel(path):
    require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= MAX_ARCHIVE, 'Invalid wheel file')
    with zipfile.ZipFile(path) as archive:
        rows = archive_members(archive, maximum_files=10000, maximum_total=768*1024*1024, maximum_file=256*1024*1024)
        entries = {name: (archive.read(entry), stat.S_IMODE(entry.external_attr >> 16)) for name, entry in rows.items()}
    validate_record(entries)
    return entries


def validate_record(entries):
    records = [name for name in entries if name.endswith('.dist-info/RECORD')]
    require(len(records) == 1, 'Wheel must have one RECORD')
    record = records[0]
    require(len(entries[record][0]) <= 2*1024*1024, 'Wheel RECORD too large')
    rows = list(csv.reader(io.StringIO(entries[record][0].decode('utf-8'))))
    require(all(len(row) == 3 for row in rows) and len(rows) == len(entries)
        and len({row[0] for row in rows}) == len(rows) and {row[0] for row in rows} == set(entries), 'Wheel RECORD census differs')
    for name, digest, size in rows:
        if name == record:
            require(digest == size == '', 'RECORD must not hash itself')
        else:
            raw = entries[name][0]
            expected = 'sha256='+base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b'=').decode()
            require(digest == expected and size == str(len(raw)), 'Wheel RECORD byte identity differs')


def validate_native(entries, *, expected, material_authority, material_sha256, packaging):
    """Pure counterpart over full actual entry bytes; no semantic or native code."""
    validate_record(entries)
    prefix = 'biocompiler_core/'
    files = {name[len(prefix):]: raw for name, (raw, _) in entries.items() if name.startswith(prefix)}
    require(set(files) == build.FILES | {'distribution.json'}, 'Native package census differs')
    manifest = build.distribution(files['distribution.json'])
    require(all(manifest[key] == value for key, value in expected.items()), 'Native release differs from external CI identity')
    target = manifest['native_platform']
    require(entries == build.wheel_entries(files, target), 'Native wheel metadata, modes, paths or RECORD differ')
    for name, row in manifest['files'].items():
        require(row == materials.digest(files[name]), 'Native distribution member differs')
    require(files['__init__.py'] == b'', 'Native package imports executable Python code')
    binaries = document(files['binaries.json'],64*1024,require_canonical=False)
    require(binaries == {'revision': expected['tested_revision'], 'system': build.TARGETS[target][0],
        'machine': build.TARGETS[target][1], 'sha256': {name: sha(files['bin/'+name]) for name in build.ROLES}}, 'Native manifest differs')
    for name in build.ROLES:
        build.image(files['bin/'+name], target)
    require(document(files['linkage.json']) == {'schema_version':'biocompiler.core_linkage.v1',
        'native_platform':target,'policy':'system-libraries-only.v1','sha256':binaries['sha256']}, 'Linkage identity differs')
    index = document(files['materials.json'])
    materials.schema(index, material_authority)
    require(sha(files['materials.json']) == material_sha256 and all(material_authority[key] == expected[key]
        for key in ('source_revision','tested_revision','run_id','native_platform')), 'Materials authority differs')
    require(material_authority['binaries'] == {name: materials.digest(files['bin/'+name]) for name in build.ROLES},
        'Materials do not bind exact final binaries')
    receipt = document(files['linkage-receipt.json'])
    require(type(receipt) is dict and set(receipt) == {'schema_version','native_platform','binaries','audits','static_gmp_sha256'}
        and receipt['schema_version'] == 'biocompiler.core_linkage_receipt.v1' and receipt['native_platform'] == target
        and receipt['binaries'] == binaries['sha256'] and set(receipt['audits']) == set(build.ROLES), 'Linkage audit census differs')
    for name, audit in receipt['audits'].items():
        options = ['--dynamic','--program-headers','--version-info','--notes','--wide'] if target == 'linux-x86_64' else ['-l']
        require(set(audit) == {'argv','tool_sha256','stdout','returncode','policy'}
            and len(audit['argv']) == len(options)+2 and Path(audit['argv'][0]).is_absolute()
            and audit['argv'][1:-1] == options and Path(audit['argv'][-1]).name == name
            and type(audit['tool_sha256']) is str and re.fullmatch('[0-9a-f]{64}',audit['tool_sha256'])
            and type(audit['returncode']) is int and audit['returncode'] == 0, 'Invalid retained linkage command')
        policy = build.elf_policy(audit['stdout']) if target == 'linux-x86_64' else build.macho_policy(audit['stdout'])
        require(policy == audit['policy'], 'Retained linkage policy differs from full raw audit')
    static = document(files['static-gmp.json'])
    materials.gmp.validate_receipt(static, files['gmp.pc'])
    require(materials.digest(files['static-gmp.json']) == material_authority['static_gmp_receipt']
        and receipt['static_gmp_sha256'] == sha(files['static-gmp.json']), 'Static input receipt differs')
    expected_material_receipt = {'schema_version':materials.SCHEMA,'manifest':materials.digest(files['materials.json']),
        'files':materials.companion_entries(index),'authority':material_authority,
        'dependency_lock':materials.digest(files['dependencies.opam.locked']),
        'scope':'retained byte closure only; hosted build, license review and release acceptance remain required'}
    require(packaging['materials'] == expected_material_receipt, 'Packaging material closure receipt differs')
    require(packaging['distribution'] == manifest and packaging['distribution_sha256'] == sha(files['distribution.json'])
        and packaging['audits'] == receipt['audits'], 'Packaging receipt is detached from wheel bytes')
    companion = document(files['materials-companion.json'])
    require(companion == packaging['companion'] and set(companion) == {'schema_version','filename','sha256','size','materials_sha256','format','entries'}
        and companion['schema_version'] == 'biocompiler.core_material_companion.v1'
        and companion['format'] == 'zip-stored-1980-regular0644-v1' and companion['materials_sha256'] == material_sha256
        and companion['entries'] == len(index['files']) and re.fullmatch('[0-9a-f]{64}',companion['sha256'])
        and type(companion['size']) is int and 0 < companion['size'] <= MAX_ARCHIVE
        and companion['filename'] == 'biocompiler-core-materials-'+target+'.zip', 'Companion binding differs')
    return {'distribution': manifest, 'materials': index, 'companion': companion,
        'notices': document(files['notices.json']), 'static': static, 'gmp_pc': files['gmp.pc'],
        'lock': materials.digest(files['dependencies.opam.locked'])}


def verify_companion(path, checked):
    require(path.name == checked['companion']['filename'] and path.is_file() and not path.is_symlink()
        and path.stat().st_size == checked['companion']['size'], 'Material companion path or size differs')
    with path.open('rb') as source:
        require(hashlib.file_digest(source,'sha256').hexdigest() == checked['companion']['sha256'], 'Material companion hash differs')
    index = checked['materials']; observed, retained = {}, {}
    special = {index['static_gmp'][name] for name in ('receipt','pkg_config')} | {index['dependency_lock']}
    with zipfile.ZipFile(path) as archive:
        rows = archive_members(archive, maximum_files=materials.MAX_FILES, maximum_total=materials.MAX_TOTAL,
            maximum_file=materials.MAX_FILE, stored=True)
        require(set(rows) == set(index['files']) and list(rows) == sorted(rows), 'Companion complete ordered census differs')
        for name, entry in rows.items():
            require(stat.S_IMODE(entry.external_attr >> 16) == 0o644, 'Companion member is executable')
            digest, size, kept = hashlib.sha256(), 0, []
            keep = name in special or index['files'][name]['role'] in ('license','notice')
            with archive.open(entry) as source:
                while chunk := source.read(1024*1024):
                    size += len(chunk); digest.update(chunk)
                    if keep:
                        require(size <= 1024*1024, 'Retained companion control too large')
                        kept.append(chunk)
            observed[name] = {'sha256':digest.hexdigest(),'size':size}
            require(observed[name] == {key:index['files'][name][key] for key in ('sha256','size')}, 'Companion member differs')
            if keep: retained[name] = b''.join(kept)
    require(observed[index['dependency_lock']] == checked['lock'], 'Companion lock differs from final native lock')
    selected = index['static_gmp']
    require(retained[selected['receipt']] == canonical(checked['static']) and retained[selected['pkg_config']] == checked['gmp_pc'],
        'Companion static configuration differs')
    for name in ('archive','header'):
        require(observed[selected[name]] == {key:checked['static'][name][key] for key in ('sha256','size')}, 'Companion selected static bytes differ')
    require(materials.retained_notices(index,retained.__getitem__) == checked['notices'], 'Installed notices differ from complete source companion')
    return observed


def validate_sdk(entries, *, source_files, release):
    validate_record(entries)
    info = 'biocompiler-'+build.VERSION+'.dist-info/'
    packages = {name:raw for name,(raw,_) in entries.items() if not name.startswith(info)}
    require(set(packages) == set(source_files) | {'biocompiler/_core_release.json'} and all(packages[name] == raw for name,raw in source_files.items()),
        'SDK package source/resource inventory differs')
    require(document(packages['biocompiler/_core_release.json'],64*1024) == release, 'SDK release pins differ')
    from email.parser import BytesParser
    metadata = BytesParser().parsebytes(entries[info+'METADATA'][0])
    require(metadata['Name'] == 'biocompiler' and metadata['Version'] == build.VERSION and metadata['Requires-Python'] == '>=3.11'
        and metadata.get_all('Provides-Extra') == ['core'], 'SDK metadata differs')
    requirements = metadata.get_all('Requires-Dist') or []
    require(len(requirements) == 1 and re.fullmatch(r'biocompiler-core\s*==\s*'+re.escape(build.VERSION)+r'\s*;\s*extra\s*==\s*[\"\']core[\"\']',requirements[0]),
        'SDK does not pin the exact optional native release')
    require(entries[info+'entry_points.txt'][0] == b'[console_scripts]\nbiocompiler = biocompiler.entrypoint:main\n', 'SDK CLI entry point differs')
    wheel = entries[info+'WHEEL'][0].decode()
    require('Root-Is-Purelib: true' in wheel.splitlines() and [line for line in wheel.splitlines() if line.startswith('Tag:')] == ['Tag: py3-none-any'], 'SDK wheel is not pure')
    require(all(mode == 0o644 for _,mode in entries.values()), 'SDK contains executable members')
    require(set(entries) - set(packages) <= {info+name for name in ('METADATA','WHEEL','RECORD','entry_points.txt','top_level.txt','licenses/LICENSE')},
        'SDK has unreviewed distribution metadata')


def source_package(root):
    result = {}
    for path in sorted((root/'src/biocompiler').rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
            require(not path.is_symlink(), 'SDK source package contains a symlink')
            name = path.relative_to(root/'src').as_posix()
            require(name != 'biocompiler/_core_release.json', 'Source checkout contains a fabricated release pin')
            require(path.stat().st_size <= 16*1024*1024, 'SDK source file too large')
            result[name] = path.read_bytes()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform-root',type=Path,nargs=2,required=True)
    parser.add_argument('--material-authorities',type=Path,required=True)
    parser.add_argument('--source-revision',required=True); parser.add_argument('--tested-revision',required=True)
    parser.add_argument('--run-id',required=True); parser.add_argument('--sdk',type=Path)
    parser.add_argument('--source-root',type=Path,required=True); parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(); authorities = document(args.material_authorities.read_bytes())
    require(set(authorities) == set(build.TARGETS), 'Independent material authority platform census differs')
    manifests, wheels, distributions, companions = [], {}, {}, {}
    for root in args.platform_root:
        receipt = document(build.regular(root/'packaging-receipt.json',4*1024*1024),4*1024*1024)
        target = receipt['distribution']['native_platform']
        require(target not in wheels and target in build.TARGETS, 'Repeated native platform')
        filename = 'biocompiler_core-'+build.VERSION+'-'+build.TARGETS[target][2]+'.whl'
        path = root/filename
        require(receipt['wheel'] == {'name':filename, 'sha256':hashlib.file_digest(path.open('rb'),'sha256').hexdigest(), 'size':path.stat().st_size}, 'Packaging wheel identity differs')
        checked = validate_native(read_wheel(path), expected={'source_revision':args.source_revision,
            'tested_revision':args.tested_revision,'run_id':args.run_id,'native_platform':target},
            material_authority=authorities[target]['authority'],material_sha256=authorities[target]['manifest_sha256'],packaging=receipt)
        verify_companion(root/checked['companion']['filename'],checked)
        manifests.append(canonical(checked['distribution'])); wheels[target]=receipt['wheel']
        distributions[target]=checked['distribution'];companions[target]=checked['companion']
    release = build.release(manifests)
    if args.sdk:
        validate_sdk(read_wheel(args.sdk),source_files=source_package(args.source_root),release=release)
    result = {'schema_version':'biocompiler.prebuilt_candidate_validation.v1','status':'pass',
        'source_revision':args.source_revision,'tested_revision':args.tested_revision,'run_id':args.run_id,
        'platforms':wheels,'distributions':distributions,'material_companions':companions,'release':release,
        'sdk_sources':{name:materials.digest(raw) for name,raw in source_package(args.source_root).items()},'sdk':None if args.sdk is None else materials.digest(args.sdk.read_bytes()),
        'native_execution':False,'acceptance':'staged bytes verified; installed four-runtime gates required'}
    require(not args.output.exists(),'Refusing to replace candidate validation')
    args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_bytes(canonical(result))


if __name__ == '__main__': main()
