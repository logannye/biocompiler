"""Hosted-only binary wheel assembly from final, audited native bytes.

This command does not compile, repair, sign, upload or publish. Its two audit
programs are explicit absolute hosted paths; binaries are never executed here.
Local tests exercise pure parsers/manifests only, never the wheel writer.
"""
from __future__ import annotations
import argparse
import ast
import base64
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import subprocess
import tomllib
import zipfile

TARGETS = {'linux-x86_64': ('Linux', 'x86_64', 'py3-none-manylinux_2_39_x86_64'),
    'macos-arm64': ('Darwin', 'arm64', 'py3-none-macosx_14_0_arm64')}
ROLES = ('biocompiler-core', 'biocompiler-verify')
EVIDENCE = ('dependencies.opam.locked', 'switch.export', 'packages.txt')
VERSION = '0.1.0.dev29'
CORE_VERSION, PROTOCOL = '0.1.0', 'biocompiler.core.v1'
SCHEMA = 'biocompiler.core_distribution.v1'
MATERIAL_FILES = {'materials.json', 'notices.json', 'materials-companion.json', 'static-gmp.json', 'gmp.pc', 'linkage-receipt.json'}
FILES = {'__init__.py', 'bin/biocompiler-core', 'bin/biocompiler-verify', 'binaries.json', *EVIDENCE, 'linkage.json', *MATERIAL_FILES}


def require(condition, message):
    if not condition: raise ValueError(message)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)+'\n').encode()


def sha(raw): return hashlib.sha256(raw).hexdigest()


def regular(path, maximum):
    require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= maximum,
        'Missing, nonregular, symlinked or oversized release input: '+str(path))
    return path.read_bytes()


def source_versions(root):
    """Read source constants without importing or executing product code."""
    metadata = tomllib.loads(regular(root/'pyproject.toml', 64*1024).decode())
    source = ast.parse(regular(root/'src/biocompiler/core_client.py', 1024*1024))
    values = {node.targets[0].id: ast.literal_eval(node.value) for node in source.body
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in ('CORE_VERSION', 'PROTOCOL')}
    require(metadata['project']['version'] == VERSION and values == {'CORE_VERSION': CORE_VERSION, 'PROTOCOL': PROTOCOL},
        'Release constants differ from source SDK or executable protocol version')


def distribution(raw):
    require(type(raw) is bytes and len(raw) <= 64*1024, 'Invalid distribution manifest bytes')
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'Duplicate distribution manifest key')
            result[key] = value
        return result
    def constant(_): raise ValueError('Nonfinite distribution manifest')
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    fields = {'schema_version', 'distribution', 'distribution_version', 'sdk_version', 'core_version', 'protocol',
        'source_revision', 'tested_revision', 'run_id', 'native_platform', 'wheel_tag', 'files'}
    require(type(value) is dict and set(value) == fields and raw == canonical(value), 'Incomplete or noncanonical distribution manifest')
    require(value['native_platform'] in TARGETS and value['wheel_tag'] == TARGETS[value['native_platform']][2],
        'Distribution wheel platform or tag differs')
    require(all(type(value[key]) is str and re.fullmatch(r'[0-9a-f]{40}', value[key]) for key in ('source_revision', 'tested_revision'))
        and type(value['run_id']) is str and re.fullmatch(r'[0-9]+', value['run_id']), 'Invalid release source or run identity')
    require(type(value['files']) is dict and set(value['files']) == FILES, 'Distribution file census differs')
    for name, pin in value['files'].items():
        require(type(pin) is dict and set(pin) == {'sha256', 'size'} and type(pin['sha256']) is str
            and re.fullmatch(r'[0-9a-f]{64}', pin['sha256']) and type(pin['size']) is int and pin['size'] >= 0
            and pin['size'] <= (256*1024*1024 if name.startswith('bin/') else 1024*1024), 'Invalid distribution file pin')
    return value


def elf_policy(text):
    require(type(text) is str and len(text) <= 1024*1024, 'Invalid ELF audit output')
    require(not re.search(r'\((?:RPATH|RUNPATH|FILTER|AUXILIARY|AUDIT|DEPAUDIT)\)', text), 'ELF runtime search path is not portable')
    isa = re.findall(r'x86 ISA needed: ([^\n]+)', text)
    require(not isa or isa == ['x86-64-baseline'], 'ELF requires an unreviewed CPU ISA level')
    needed = re.findall(r'\(NEEDED\).*?Shared library: \[([^\]]+)\]', text)
    allowed = {'libc.so.6', 'libm.so.6', 'libpthread.so.0', 'libdl.so.2', 'librt.so.1', 'ld-linux-x86-64.so.2'}
    require(needed and len(needed) == len(set(needed)) and set(needed) <= allowed,
        'ELF depends on an unbundled or unreviewed library')
    require(re.findall(r'Requesting program interpreter: ([^\]]+)', text) == ['/lib64/ld-linux-x86-64.so.2'],
        'ELF interpreter differs from the reviewed Linux target')
    tokens = set(re.findall(r'\bGLIBC_[A-Za-z0-9_.]+', text))
    require(tokens and all(re.fullmatch(r'GLIBC_[0-9]+\.[0-9]+(?:\.[0-9]+)?', value) for value in tokens),
        'Unreviewed GLIBC version requirement')
    versions = [tuple(map(int, value.removeprefix('GLIBC_').split('.'))) for value in tokens]
    require(all(value <= (2, 39, 0) for value in versions), 'ELF requires GLIBC newer than its wheel tag')
    require(not re.search(r'\b(?:GLIBCXX_|CXXABI_|GCC_)[A-Za-z0-9_.]+', text),
        'ELF requires an unreviewed compiler runtime ABI')
    return {'needed': needed, 'maximum_glibc': '.'.join(map(str, max(versions)))}


def macho_policy(text):
    require(type(text) is str and len(text) <= 1024*1024, 'Invalid Mach-O audit output')
    commands = re.split(r'\nLoad command [0-9]+\n', '\n'+text)
    libraries, minima = [], []
    for block in commands:
        match = re.search(r'^\s+cmd (LC_[A-Z0-9_]+)\s*$', block, re.M)
        if match is None: continue
        command = match[1]
        require(command not in ('LC_RPATH', 'LC_DYLD_ENVIRONMENT'), 'Mach-O runtime search path is not portable')
        if command.endswith('_DYLIB'):
            require(command == 'LC_LOAD_DYLIB', 'Mach-O uses an unreviewed dynamic loader command')
            names = re.findall(r'^\s+name (.+?) \(offset [0-9]+\)\s*$', block, re.M)
            require(len(names) == 1 and names[0] in ('/usr/lib/libSystem.B.dylib',),
                'Mach-O depends on an unbundled or unreviewed library')
            libraries.extend(names)
        if command == 'LC_BUILD_VERSION':
            require(re.findall(r'^\s+platform (\S+)', block, re.M) in (['1'], ['macos']),
                'Mach-O targets another Apple platform')
            minima.extend(re.findall(r'^\s+minos ([0-9.]+)', block, re.M))
        if command.startswith('LC_VERSION_MIN_'):
            require(command == 'LC_VERSION_MIN_MACOSX', 'Mach-O targets another Apple platform')
            minima.extend(re.findall(r'^\s+version ([0-9.]+)', block, re.M))
    require(libraries and len(libraries) == len(set(libraries)), 'Mach-O dependency census is empty or repeated')
    require(len(minima) == 1 and re.fullmatch(r'[0-9]+(?:\.[0-9]+){1,2}', minima[0])
        and tuple(map(int, minima[0].split('.'))) <= (14, 0, 0), 'Mach-O deployment target exceeds its wheel tag')
    return {'needed': libraries, 'minimum_macos': minima[0]}


def image(raw, target):
    if target == 'linux-x86_64':
        valid = len(raw) >= 64 and raw[:6] == b'\x7fELF\x02\x01' and int.from_bytes(raw[16:18], 'little') in (2, 3) and int.from_bytes(raw[18:20], 'little') == 62
    else:
        valid = len(raw) >= 32 and raw[:4] == b'\xcf\xfa\xed\xfe' and int.from_bytes(raw[4:8], 'little') == 0x0100000c and int.from_bytes(raw[12:16], 'little') == 2
    require(valid, 'Binary image does not match release target')


def audit(tool, path, target):
    require(tool.is_absolute() and tool.is_file(), 'Audit tool must have an explicit hosted absolute path')
    options = ['--dynamic', '--program-headers', '--version-info', '--notes', '--wide'] if target == 'linux-x86_64' else ['-l']
    command = [str(tool), *options, str(path)]
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)
    require(completed.returncode == 0 and not completed.stderr and len(completed.stdout) <= 1024*1024,
        'Hosted linkage audit failed or exceeded its bound')
    text = completed.stdout.decode('utf-8', errors='strict')
    policy = elf_policy(text) if target == 'linux-x86_64' else macho_policy(text)
    return {'argv': command, 'tool_sha256': sha(regular(tool, 256*1024*1024)),
        'stdout': text, 'returncode': completed.returncode, 'policy': policy}


def plan(root, *, target, source_revision, tested_revision, run_id, audit_tool,
         material_root, material_document, material_authority, material_sha256, companion):
    require(target in TARGETS and all(re.fullmatch(r'[0-9a-f]{40}', item) for item in (source_revision, tested_revision))
        and re.fullmatch(r'[0-9]+', run_id), 'Invalid exact hosted release authority')
    if __package__:
        from .check_realization_binaries import verify
    else:
        from check_realization_binaries import verify
    verify(root, tested_revision, target)
    manifest_raw = regular(root/'binaries.json', 64*1024)
    manifest = json.loads(manifest_raw)
    require(set(manifest) == {'revision', 'system', 'machine', 'sha256'} and manifest['revision'] == tested_revision
        and (manifest['system'], manifest['machine']) == TARGETS[target][:2] and set(manifest['sha256']) == set(ROLES),
        'Native manifest differs from exact tested release authority')
    files, audits = {'__init__.py': b'', 'binaries.json': manifest_raw}, {}
    for name in ROLES:
        path = root/name; raw = regular(path, 256*1024*1024)
        require(sha(raw) == manifest['sha256'][name], 'Audited binary differs from tested byte identity')
        image(raw, target)
        audits[name] = audit(audit_tool, path, target)
        require(sha(regular(path, 256*1024*1024)) == sha(raw), 'Binary changed during static audit')
        files['bin/'+name] = raw
    files.update({name: regular(root/name, 1024*1024) for name in EVIDENCE})
    if __package__:
        from . import prebuilt_core_materials as materials
    else:
        import prebuilt_core_materials as materials
    material_receipt = materials.verify(material_root, material_document, material_authority,
        dependency_lock=materials.digest(files['dependencies.opam.locked']), manifest_sha256=material_sha256)
    require(all(material_authority[key] == value for key, value in {
        'source_revision': source_revision, 'tested_revision': tested_revision, 'run_id': run_id,
        'native_platform': target, 'binaries': {name: materials.digest(files['bin/'+name]) for name in ROLES}}.items()),
        'Release materials do not bind final audited binaries')
    require(companion['materials_sha256'] == material_sha256 and companion['entries'] == len(material_document['files']),
        'Companion does not bind the complete materials index')
    selected = material_document['static_gmp']
    files['materials.json'] = canonical(material_document)
    files['notices.json'] = canonical(materials.retained_notices(material_document, lambda name: (material_root/name).read_bytes()))
    files['materials-companion.json'] = canonical(companion)
    files['static-gmp.json'] = regular(material_root/selected['receipt'], 1024*1024)
    files['gmp.pc'] = regular(material_root/selected['pkg_config'], 64*1024)
    files['linkage-receipt.json'] = canonical({'schema_version': 'biocompiler.core_linkage_receipt.v1',
        'native_platform': target, 'binaries': manifest['sha256'], 'audits': audits,
        'static_gmp_sha256': sha(files['static-gmp.json'])})
    files['linkage.json'] = canonical({'schema_version': 'biocompiler.core_linkage.v1',
        'native_platform': target, 'policy': 'system-libraries-only.v1', 'sha256': manifest['sha256']})
    distribution = {'schema_version': SCHEMA, 'distribution': 'biocompiler-core',
        'distribution_version': VERSION, 'sdk_version': VERSION, 'core_version': CORE_VERSION, 'protocol': PROTOCOL,
        'source_revision': source_revision, 'tested_revision': tested_revision, 'run_id': run_id,
        'native_platform': target, 'wheel_tag': TARGETS[target][2],
        'files': {name: {'sha256': sha(raw), 'size': len(raw)} for name, raw in files.items()}}
    files['distribution.json'] = canonical(distribution)
    return files, {'distribution': distribution, 'audits': audits,
        'distribution_sha256': sha(files['distribution.json']), 'materials': material_receipt, 'companion': companion}


def wheel_entries(files, target):
    """Pure wheel contents planning; no archive or native execution."""
    require(target in TARGETS and set(files) == FILES | {'distribution.json'}, 'Unexpected binary wheel file layout')
    info = 'biocompiler_core-'+VERSION+'.dist-info'
    entries = {'biocompiler_core/'+name: (raw, 0o755 if name.startswith('bin/') else 0o644) for name, raw in files.items()}
    entries[info+'/METADATA'] = (('Metadata-Version: 2.1\nName: biocompiler-core\nVersion: '+VERSION+
        '\nSummary: Internal prebuilt Biocompiler Core and independent Verify\nRequires-Python: >=3.11\n\n').encode(), 0o644)
    entries[info+'/WHEEL'] = (('Wheel-Version: 1.0\nGenerator: biocompiler-release-v1\nRoot-Is-Purelib: false\nTag: '+TARGETS[target][2]+'\n').encode(), 0o644)
    buffer = io.StringIO(newline=''); writer = csv.writer(buffer, lineterminator='\n')
    for path, (raw, _) in sorted(entries.items()):
        digest = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b'=').decode()
        writer.writerow([path, 'sha256='+digest, len(raw)])
    writer.writerow([info+'/RECORD', '', ''])
    entries[info+'/RECORD'] = buffer.getvalue().encode(), 0o644
    return entries


def write_wheel(path, entries):
    """Hosted packaging step; not exercised by local source tests."""
    require(not path.exists(), 'Refusing to replace an existing reviewed wheel')
    with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, (raw, mode) in sorted(entries.items(), key=lambda pair: ('.dist-info/' in pair[0], pair[0])):
            entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0)); entry.create_system = 3
            entry.external_attr = (stat.S_IFREG | mode) << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, raw)


def release(manifests):
    require(len(manifests) == 2, 'SDK release requires both reviewed platform manifests')
    documents = [distribution(raw) for raw in manifests]
    require({value['native_platform'] for value in documents} == set(TARGETS), 'SDK release platform census differs')
    first = documents[0]
    for value in documents:
        require(value['schema_version'] == SCHEMA and all(value[key] == first[key] for key in
            ('sdk_version', 'distribution', 'distribution_version', 'source_revision', 'tested_revision', 'run_id', 'core_version', 'protocol')),
            'SDK release mixes source, tested revision, run or protocol identities')
        require(value['sdk_version'] == VERSION and value['core_version'] == CORE_VERSION and value['protocol'] == PROTOCOL
            and value['distribution'] == 'biocompiler-core' and value['distribution_version'] == VERSION,
            'SDK release mixes package and executable versions')
    return {'schema_version': 'biocompiler.core_release.v1', **{key: first[key] for key in
        ('sdk_version', 'distribution', 'distribution_version', 'source_revision', 'tested_revision', 'run_id')},
        'platforms': {value['native_platform']: sha(raw) for value, raw in zip(documents, manifests)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    binary = commands.add_parser('wheel')
    binary.add_argument('--source-root', type=Path, required=True)
    binary.add_argument('--native-root', type=Path, required=True)
    binary.add_argument('--platform', choices=tuple(TARGETS), required=True)
    binary.add_argument('--source-revision', required=True); binary.add_argument('--tested-revision', required=True)
    binary.add_argument('--run-id', required=True); binary.add_argument('--audit-tool', type=Path, required=True)
    binary.add_argument('--output', type=Path, required=True)
    binary.add_argument('--materials-root', type=Path, required=True)
    binary.add_argument('--materials', type=Path, required=True)
    binary.add_argument('--materials-authority', type=Path, required=True)
    binary.add_argument('--materials-sha256', required=True)
    sdk = commands.add_parser('release')
    sdk.add_argument('--source-root', type=Path, required=True)
    sdk.add_argument('--manifests', type=Path, nargs=2, required=True)
    sdk.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source_versions(args.source_root)
    if args.command == 'release':
        require(not args.output.exists(), 'Refusing to replace an existing SDK release authority')
        result = release([regular(path, 64*1024) for path in args.manifests])
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(canonical(result))
        return
    if __package__:
        from . import prebuilt_core_materials as materials
    else:
        import prebuilt_core_materials as materials
    require(not args.output.exists(), 'Release output must be fresh')
    args.output.mkdir(parents=True)
    document = json.loads(regular(args.materials, 1024*1024))
    authority = json.loads(regular(args.materials_authority, 64*1024))
    materials.verify(args.materials_root, document, authority,
        dependency_lock=materials.digest(regular(args.native_root/'dependencies.opam.locked', 1024*1024)),
        manifest_sha256=args.materials_sha256)
    companion = materials.write_companion(args.materials_root, document,
        args.output/('biocompiler-core-materials-'+args.platform+'.zip'))
    files, receipt = plan(args.native_root, target=args.platform, source_revision=args.source_revision,
        tested_revision=args.tested_revision, run_id=args.run_id, audit_tool=args.audit_tool,
        material_root=args.materials_root, material_document=document, material_authority=authority,
        material_sha256=args.materials_sha256, companion=companion)
    args.output.mkdir(parents=True, exist_ok=True)
    path = args.output/('biocompiler_core-'+VERSION+'-'+TARGETS[args.platform][2]+'.whl')
    write_wheel(path, wheel_entries(files, args.platform))
    (args.output/'distribution.json').write_bytes(files['distribution.json'])
    receipt['wheel'] = {'name': path.name, 'sha256': sha(path.read_bytes()), 'size': path.stat().st_size}
    (args.output/'packaging-receipt.json').write_bytes(canonical(receipt))


if __name__ == '__main__': main()
