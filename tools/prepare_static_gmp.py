"""Prepare hosted Zarith configuration using a selected static GMP archive.

No compilation, archive rewriting or executable modification is performed here.
The subsequent final-binary audit must still prove portable dependency closure.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shlex
import stat
from pathlib import Path
import re
import subprocess


def require(condition, message):
    if not condition:
        raise ValueError(message)


def regular(path, maximum):
    require(path.is_absolute() and path.is_file() and not path.is_symlink(),
            'Static GMP input must be an absolute regular file')
    size = path.stat().st_size
    require(0 < size <= maximum, 'Static GMP input exceeds its size bound')
    raw = path.read_bytes()
    require(len(raw) == size, 'Static GMP input changed while reading')
    return raw


def pin(raw):
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}


def resolve_selected(path, maximum):
    """Retain the exact bounded symlink traversal used for package discovery."""
    require(path.is_absolute() and '..' not in path.parts, 'Invalid selected GMP path')
    requested = str(path)
    links = []
    while True:
        current = Path(path.anchor)
        for part in path.parts[1:]:
            current /= part
            mode = current.lstat().st_mode
            if stat.S_ISLNK(mode):
                require(len(links) < 40, 'GMP selected path has too many symlinks')
                target = os.readlink(current)
                require(target and len(target.encode()) <= 4096, 'Invalid GMP symlink target')
                links.append({'path': str(current), 'target': target})
                suffix = path.relative_to(current)
                replacement = Path(target) if Path(target).is_absolute() else current.parent / target
                path = Path(os.path.normpath(str(replacement / suffix)))
                break
        else:
            raw = regular(path, maximum)
            return path, {'requested': requested, 'resolved': str(path), 'links': links, **pin(raw)}


def validate_resolution(value, requested, expected):
    require(type(value) is dict and set(value) == {'requested','resolved','links','sha256','size'}
        and value['requested'] == requested and value['resolved'] == expected['path']
        and {key: value[key] for key in ('sha256','size')} == {key: expected[key] for key in ('sha256','size')}
        and type(value['links']) is list and len(value['links']) <= 40, 'GMP discovered input is detached')
    current = Path(requested)
    require(current.is_absolute() and '..' not in current.parts, 'Invalid retained GMP selected path')
    for link in value['links']:
        require(type(link) is dict and set(link) == {'path','target'} and type(link['path']) is str
            and type(link['target']) is str and 0 < len(link['target'].encode()) <= 4096,
            'Invalid retained GMP symlink step')
        path = Path(link['path'])
        require(path.is_absolute() and '..' not in path.parts and current.is_relative_to(path),
            'GMP symlink step is outside the selected path')
        target = Path(link['target'])
        target = target if target.is_absolute() else path.parent / target
        current = Path(os.path.normpath(str(target / current.relative_to(path))))
    require(str(current) == value['resolved'], 'GMP resolved input differs from exact traversal')


def pkgconfig(archive, header, version):
    """Pass the selected archive as a recorded C link dependency, not an ar member."""
    require(re.fullmatch(r'[0-9]+(?:\.[0-9]+){1,3}', version) is not None,
            'Invalid GMP version')
    for path in (archive, header):
        require(path.is_absolute() and re.fullmatch(r'/[A-Za-z0-9_./+@-]+', str(path)) is not None,
                'GMP paths must be absolute and require no shell/pkg-config escaping')
        require('..' not in path.parts, 'GMP path cannot contain parent traversal')
    require(archive.name == 'libgmp.a' and header.name == 'gmp.h', 'Unexpected static GMP file names')
    return (f'Name: gmp\nDescription: reviewed static GMP input for Biocompiler\n'
            f'Version: {version}\nLibs: -custom -cclib {archive}\nCflags: -I{header.parent}\n').encode()


def prepare(*, archive, header, version, output):
    require(not output.exists(), 'Static GMP configuration output already exists')
    library = regular(archive, 64 * 1024 * 1024)
    include = regular(header, 1024 * 1024)
    require(library.startswith(b'!<arch>\n') and len(library) >= 68,
            'GMP static library is not an archive')
    text = pkgconfig(archive, header, version)
    # A selected system library is recorded, not asserted to be portable. The
    # final ELF/Mach-O audit and fresh installs determine release acceptance.
    record = {'schema_version': 'biocompiler.static_gmp_input.v1', 'version': version,
              'archive': {'path': str(archive), **pin(library)},
              'header': {'path': str(header), **pin(include)},
              'pkg_config': pin(text),
              'final_binary_dependency_audit': 'required', 'native_execution': False}
    output.mkdir(parents=True)
    (output / 'gmp.pc').write_bytes(text)
    (output / 'input.json').write_text(json.dumps(record, sort_keys=True, indent=2) + '\n')
    return record


def probe(tool, arguments, *, environment=None):
    tool = tool.resolve(strict=True)
    tool_bytes = regular(tool, 64 * 1024 * 1024)
    require(type(arguments) is list and all(type(value) is str for value in arguments), 'Invalid metadata command')
    env = dict(os.environ) if environment is None else dict(environment)
    env['LC_ALL'] = 'C'
    command = [str(tool), *arguments, 'gmp']
    result = subprocess.run(command, check=False, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=10, env=env)
    require(result.returncode == 0 and not result.stderr and len(result.stdout) < 8192,
            'Unable to inspect the selected GMP installation')
    value = result.stdout.decode('utf-8').strip()
    require(bool(value) and '\n' not in value and '\r' not in value, 'Invalid GMP metadata')
    receipt = {'argv': command, 'tool': {'path': str(tool), **pin(tool_bytes)},
        'environment': {name: env.get(name) for name in ('LC_ALL', 'PKG_CONFIG_PATH', 'PKG_CONFIG_LIBDIR',
            'PKG_CONFIG_SYSROOT_DIR', 'PKG_CONFIG_ALLOW_SYSTEM_CFLAGS', 'PKG_CONFIG_ALLOW_SYSTEM_LIBS')},
        'stdout': result.stdout.decode('utf-8'), 'stderr': result.stderr.decode('utf-8'), 'returncode': result.returncode}
    return value, receipt


def validate_probe(receipt, arguments):
    require(type(receipt) is dict and set(receipt) == {'argv', 'tool', 'environment', 'stdout', 'stderr', 'returncode'},
            'Incomplete GMP metadata receipt')
    tool = receipt['tool']
    require(type(tool) is dict and set(tool) == {'path', 'sha256', 'size'} and Path(tool['path']).is_absolute()
        and re.fullmatch('[0-9a-f]{64}', tool['sha256']) and type(tool['size']) is int and 0 < tool['size'] <= 64 * 1024 * 1024,
        'Invalid GMP metadata tool identity')
    require(receipt['argv'] == [tool['path'], *arguments, 'gmp'] and receipt['returncode'] == 0
        and type(receipt['returncode']) is int and receipt['stderr'] == '' and type(receipt['stdout']) is str
        and 0 < len(receipt['stdout'].encode()) < 8192, 'GMP metadata command or outcome differs')
    env = receipt['environment']
    require(type(env) is dict and set(env) == {'LC_ALL', 'PKG_CONFIG_PATH', 'PKG_CONFIG_LIBDIR',
        'PKG_CONFIG_SYSROOT_DIR', 'PKG_CONFIG_ALLOW_SYSTEM_CFLAGS', 'PKG_CONFIG_ALLOW_SYSTEM_LIBS'}
        and env['LC_ALL'] == 'C' and all(value is None or type(value) is str for value in env.values()),
        'GMP metadata environment differs')
    value = receipt['stdout'].strip()
    require(bool(value) and '\n' not in value and '\r' not in value, 'Invalid retained GMP metadata')
    return value


def validate_receipt(record, pc_bytes):
    require(type(record) is dict and set(record) == {'schema_version', 'version', 'archive', 'header',
        'pkg_config', 'final_binary_dependency_audit', 'native_execution', 'selection', 'configured', 'resolution'},
        'Incomplete static GMP build-input receipt')
    require(record['schema_version'] == 'biocompiler.static_gmp_input.v1' and record['native_execution'] is False
        and record['final_binary_dependency_audit'] == 'required', 'Unknown static GMP receipt authority')
    for name in ('archive', 'header'):
        row = record[name]
        require(type(row) is dict and set(row) == {'path', 'sha256', 'size'} and Path(row['path']).is_absolute()
            and re.fullmatch('[0-9a-f]{64}', row['sha256']) and type(row['size']) is int
            and 0 < row['size'] <= (64 * 1024 * 1024 if name == 'archive' else 1024 * 1024),
            'Invalid selected GMP input identity')
    require(record['pkg_config'] == pin(pc_bytes) and pc_bytes == pkgconfig(Path(record['archive']['path']),
        Path(record['header']['path']), record['version']), 'Static GMP configuration differs from selected inputs')
    selection, configured = record['selection'], record['configured']
    require(type(selection) is dict and set(selection) == {'version', 'libdir', 'includedir'}
        and type(configured) is dict and set(configured) == {'directory', 'libs', 'cflags'}, 'Incomplete GMP probe census')
    version = validate_probe(selection['version'], ['--modversion'])
    libdir = validate_probe(selection['libdir'], ['--variable=libdir'])
    includedir = validate_probe(selection['includedir'], ['--variable=includedir'])
    require(version == record['version'] and Path(libdir).is_absolute() and Path(includedir).is_absolute(),
        'GMP selected metadata differs')
    require(selection['version']['environment'] == selection['libdir']['environment']
        == selection['includedir']['environment'], 'GMP discovery environment changed between probes')
    resolution = record['resolution']
    require(type(resolution) is dict and set(resolution) == {'archive','header'}, 'Incomplete GMP input traversal')
    validate_resolution(resolution['archive'], str(Path(libdir) / 'libgmp.a'), record['archive'])
    validate_resolution(resolution['header'], str(Path(includedir) / 'gmp.h'), record['header'])
    tools = [row['tool'] for row in selection.values()]
    libs = validate_probe(configured['libs'], ['--libs'])
    cflags = validate_probe(configured['cflags'], ['--cflags'])
    tools += [configured[name]['tool'] for name in ('libs', 'cflags')]
    require(all(tool == tools[0] for tool in tools), 'GMP metadata tools changed between probes')
    require(shlex.split(libs) == ['-custom', '-cclib', record['archive']['path']]
        and shlex.split(cflags) == ['-I' + str(Path(record['header']['path']).parent)],
        'GMP configured flags contain a dynamic fallback, foreign input or reordered tokens')
    directory = configured['directory']
    require(type(directory) is str and Path(directory).is_absolute(), 'Invalid private GMP configuration directory')
    for name in ('libs', 'cflags'):
        env = configured[name]['environment']
        require(env['PKG_CONFIG_LIBDIR'] == directory and env['PKG_CONFIG_PATH'] == directory
            and env['PKG_CONFIG_SYSROOT_DIR'] is None and env['PKG_CONFIG_ALLOW_SYSTEM_CFLAGS'] == '1'
            and env['PKG_CONFIG_ALLOW_SYSTEM_LIBS'] == '1', 'GMP configured lookup may select a foreign provider')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pkg-config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    # Resolve package-manager symlinks and retain both actual discovery commands
    # and the private configuration's observed output before any native build.
    version, version_probe = probe(args.pkg_config, ['--modversion'])
    libdir, libdir_probe = probe(args.pkg_config, ['--variable=libdir'])
    includedir, include_probe = probe(args.pkg_config, ['--variable=includedir'])
    archive, archive_resolution = resolve_selected(Path(libdir) / 'libgmp.a', 64 * 1024 * 1024)
    header, header_resolution = resolve_selected(Path(includedir) / 'gmp.h', 1024 * 1024)
    result = prepare(archive=archive, header=header, version=version, output=args.output)
    directory = str(args.output.resolve(strict=True))
    env = dict(os.environ, PKG_CONFIG_LIBDIR=directory, PKG_CONFIG_PATH=directory,
        PKG_CONFIG_ALLOW_SYSTEM_CFLAGS='1', PKG_CONFIG_ALLOW_SYSTEM_LIBS='1')
    env.pop('PKG_CONFIG_SYSROOT_DIR', None)
    _, libs = probe(args.pkg_config, ['--libs'], environment=env)
    _, cflags = probe(args.pkg_config, ['--cflags'], environment=env)
    result['resolution'] = {'archive': archive_resolution, 'header': header_resolution}
    result['selection'] = {'version': version_probe, 'libdir': libdir_probe, 'includedir': include_probe}
    result['configured'] = {'directory': directory, 'libs': libs, 'cflags': cflags}
    validate_receipt(result, (args.output / 'gmp.pc').read_bytes())
    (args.output / 'input.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
