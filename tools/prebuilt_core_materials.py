"""Verify retained source, license and relinking inputs without executing them.

The approved dependency inventory and release identities are external inputs.
This proves an exact retained byte closure, not license sufficiency, successful
rebuilding, portable linking or permission to publish.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

if __package__:
    from . import prepare_static_gmp as gmp
else:
    import prepare_static_gmp as gmp

SCHEMA = 'biocompiler.core_release_materials.v1'
ROLES = {'source', 'license', 'notice', 'patch', 'build-recipe', 'relink-input',
         'link-input', 'header', 'dependency-lock', 'build-receipt', 'pkg-config'}
MINIMUM = {'biocompiler', 'ocaml', 'dune', 'zarith', 'digestif', 'gmp'}
MAX_FILES, MAX_FILE, MAX_TOTAL = 4096, 256 * 1024 * 1024, 1024 * 1024 * 1024
AUTHORITY = {'source_revision', 'tested_revision', 'run_id', 'native_platform', 'components', 'binaries',
             'static_gmp_receipt'}


def require(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False) + '\n').encode()


def digest(raw):
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def logical(value):
    require(type(value) is str and 0 < len(value.encode()) <= 1024
        and re.fullmatch(r'[A-Za-z0-9_./+@-]+', value) is not None,
        'Invalid release material path')
    path = PurePosixPath(value)
    require(not path.is_absolute() and str(path) == value and all(part not in ('.', '..') for part in path.parts),
        'Release material path escapes its closure')
    return value


def pin(value, *, empty=False):
    require(type(value) is dict and set(value) == {'sha256', 'size'}
        and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256'])
        and type(value['size']) is int and (0 if empty else 1) <= value['size'] <= MAX_FILE,
        'Invalid release material byte identity')


def schema(document, expected):
    require(type(expected) is dict and set(expected) == AUTHORITY,
        'Missing independently supplied material authority')
    for key in ('source_revision', 'tested_revision'):
        require(type(expected[key]) is str and re.fullmatch('[0-9a-f]{40}', expected[key]),
            'Invalid material source identity')
    require(type(expected['run_id']) is str and re.fullmatch('[0-9]+', expected['run_id'])
        and expected['native_platform'] in ('linux-x86_64', 'macos-arm64'),
        'Invalid material run or platform identity')
    components = expected['components']
    require(type(components) is dict and MINIMUM <= set(components) and len(components) <= 128,
        'Incomplete independently reviewed dependency inventory')
    for name, row in components.items():
        require(type(name) is str and re.fullmatch('[a-z][a-z0-9_-]*', name)
            and type(row) is dict and set(row) == {'version', 'linked'}
            and type(row['version']) is str and 0 < len(row['version']) <= 128
            and type(row['linked']) is bool, 'Invalid approved dependency metadata')
    binaries = expected['binaries']
    require(type(binaries) is dict and set(binaries) == {'biocompiler-core', 'biocompiler-verify'},
        'Incomplete final binary material identity')
    for value in binaries.values():
        pin(value)
    pin(expected['static_gmp_receipt'])
    require(type(document) is dict and set(document) == AUTHORITY | {
        'schema_version', 'files', 'static_gmp', 'dependency_lock', 'recipes'},
        'Incomplete release material manifest')
    require(document['schema_version'] == SCHEMA
        and all(canonical(document[key]) == canonical(value) for key, value in expected.items()),
        'Release materials differ from independently supplied authority')
    files = document['files']
    require(type(files) is dict and 1 <= len(files) <= MAX_FILES,
        'Release material file census exceeds its bound')
    roles = {name: set() for name in components}
    total = 0
    for path, row in files.items():
        logical(path)
        require(type(row) is dict and set(row) == {'component', 'role', 'sha256', 'size'}
            and row['component'] in components and row['role'] in ROLES,
            'Unreviewed release material member')
        pin({key: row[key] for key in ('sha256', 'size')})
        total += row['size']
        roles[row['component']].add(row['role'])
    require(total <= MAX_TOTAL, 'Complete release material size exceeds its bound')
    for component, found in roles.items():
        require({'source', 'build-recipe'} <= found and ('license' in found or (component == 'biocompiler' and 'notice' in found)),
            'Dependency lacks retained source, license or build recipe: ' + component)
        if components[component]['linked']:
            require('relink-input' in found, 'Linked dependency lacks retained relinking inputs: ' + component)
    def member(path, role, component=None):
        logical(path)
        require(path in files and files[path]['role'] == role
            and (component is None or files[path]['component'] == component),
            'Material binding has another role or dependency')
    member(document['dependency_lock'], 'dependency-lock', 'biocompiler')
    require(type(document['recipes']) is dict and set(document['recipes']) == {'build', 'relink'},
        'Missing exact complete build and relink recipes')
    for path in document['recipes'].values():
        member(path, 'build-recipe', 'biocompiler')
    selected = document['static_gmp']
    require(type(selected) is dict and set(selected) == {'receipt', 'pkg_config', 'archive', 'header'},
        'Incomplete static GMP material bindings')
    for name, role in (('receipt', 'build-receipt'), ('pkg_config', 'pkg-config'),
                       ('archive', 'link-input'), ('header', 'header')):
        member(selected[name], role, 'gmp')
    return files


def inventory(root):
    require(root.is_absolute() and root.is_dir() and not root.is_symlink()
        and root == root.resolve(strict=True), 'Materials require their physical retained root')
    found, folders = set(), set()
    for base, directories, files in os.walk(root, followlinks=False):
        for name in directories:
            path = Path(base) / name
            require(not path.is_symlink(), 'Release material directory is a symlink')
            folders.add(path.relative_to(root).as_posix())
            require(len(folders) <= MAX_FILES, 'Release material directory census exceeds its bound')
        for name in files:
            path = Path(base) / name
            require(stat.S_ISREG(path.lstat().st_mode), 'Release material is not a regular file')
            found.add(logical(path.relative_to(root).as_posix()))
            require(len(found) <= MAX_FILES, 'Release material file census exceeds its bound')
    parents = {str(parent) for name in found for parent in PurePosixPath(name).parents if str(parent) != '.'}
    require(folders == parents, 'Unclaimed empty release material directory')
    return found


def read_pin(path, expected):
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
    descriptor = os.open(path, flags)
    try:
        before = os.fstat(descriptor)
        require(stat.S_ISREG(before.st_mode) and before.st_size == expected['size'],
            'Release material size or file kind changed')
        hashed, size = hashlib.sha256(), 0
        while chunk := os.read(descriptor, min(1024 * 1024, expected['size'] + 1 - size)):
            size += len(chunk)
            require(size <= expected['size'], 'Release material grew while reading')
            hashed.update(chunk)
        after = os.fstat(descriptor)
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
            == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
            and size == expected['size'] and hashed.hexdigest() == expected['sha256'],
            'Release material bytes changed')
        return {'sha256': hashed.hexdigest(), 'size': size}
    finally:
        os.close(descriptor)


def verify(root, document, expected, *, dependency_lock, manifest_sha256):
    """Check exact closure and selected link inputs; no remote or native work."""
    root = Path(root)
    files = schema(document, expected)
    require(type(manifest_sha256) is str and re.fullmatch('[0-9a-f]{64}', manifest_sha256)
        and digest(canonical(document))['sha256'] == manifest_sha256,
        'Material manifest differs from independently retained identity')
    require(inventory(root) == set(files), 'Missing or unclaimed release materials')
    observed = {name: read_pin(root / name, row) for name, row in files.items()}
    pin(dependency_lock)
    require(observed[document['dependency_lock']] == dependency_lock,
        'Release materials changed the actual native dependency lock')
    selected = document['static_gmp']
    require(files[selected['receipt']]['size'] <= 1024 * 1024
        and files[selected['pkg_config']]['size'] <= 64 * 1024,
        'GMP retained control documents exceed their bound')
    raw = (root / selected['receipt']).read_bytes()
    require(digest(raw) == expected['static_gmp_receipt'],
        'Materials changed the independently retained static GMP input receipt')
    receipt = json.loads(raw)
    require(raw == canonical(receipt), 'Noncanonical GMP material receipt')
    gmp.validate_receipt(receipt, (root / selected['pkg_config']).read_bytes())
    require(receipt['version'] == expected['components']['gmp']['version'],
        'GMP material version differs from reviewed dependency')
    for name in ('archive', 'header'):
        require(observed[selected[name]] == {key: receipt[name][key] for key in ('sha256', 'size')},
            'Retained GMP bytes differ from actual selected link input')
    # Recheck exact control bytes as well as the complete names after parsing.
    for name in ('receipt', 'pkg_config'):
        read_pin(root / selected[name], files[selected[name]])
    require(inventory(root) == set(files), 'Release material census changed during verification')
    return {'schema_version': SCHEMA, 'manifest': digest(canonical(document)),
        'files': observed, 'authority': expected, 'dependency_lock': dependency_lock,
        'scope': 'retained byte closure only; hosted build, license review and release acceptance remain required'}


def retained_notices(document, read):
    """Exact license/notice bytes are installed; complete sources stay companion-bound."""
    import base64
    selected = {name: row for name, row in document['files'].items() if row['role'] in ('license', 'notice')}
    entries = {}
    size = 0
    for name, row in sorted(selected.items()):
        raw = read(name)
        require(digest(raw) == {key: row[key] for key in ('sha256', 'size')}, 'Notice bytes differ from materials')
        size += len(raw)
        require(size <= 512 * 1024, 'Installed notices exceed their complete bound')
        entries[name] = {'component': row['component'], 'role': row['role'],
                         'base64': base64.b64encode(raw).decode('ascii'), **digest(raw)}
    return {'schema_version': 'biocompiler.core_notices.v1', 'materials_sha256': digest(canonical(document))['sha256'],
            'entries': entries}


def companion_entries(document):
    """Pure exact companion inventory; this never assembles an archive."""
    return {name: {key: row[key] for key in ('sha256', 'size')}
            for name, row in sorted(document['files'].items())}


def write_companion(root, document, output):
    """Hosted-only streaming assembly; complete retained sources are never executed."""
    import zipfile
    require(not output.exists(), 'Refusing to replace a material companion')
    before = inventory(root)
    require(before == set(document['files']), 'Companion material census differs')
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
        for name, row in sorted(document['files'].items()):
            read_pin(root / name, row)
            entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = (stat.S_IFREG | 0o644) << 16
            entry.file_size = row['size']
            with archive.open(entry, 'w') as destination, (root / name).open('rb') as source:
                while block := source.read(1024 * 1024):
                    destination.write(block)
            read_pin(root / name, row)
    require(inventory(root) == before, 'Companion inputs changed during assembly')
    with output.open('rb') as source:
        archive_sha = hashlib.file_digest(source, 'sha256').hexdigest()
    return {'schema_version': 'biocompiler.core_material_companion.v1', 'filename': output.name,
            'sha256': archive_sha,
            'size': output.stat().st_size, 'materials_sha256': digest(canonical(document))['sha256'],
            'format': 'zip-stored-1980-regular0644-v1', 'entries': len(document['files'])}
