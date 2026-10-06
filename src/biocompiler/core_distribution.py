"""Explicit discovery of the exact prebuilt distribution owned by this SDK.

No native package is imported, and no binary is searched for, downloaded, built,
repaired, or made executable here. Package installation is the trust boundary;
RECORD and release pins provide consistency, not publisher authentication.
"""
from __future__ import annotations

import base64
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import stat
import sys
from typing import Any, Literal, NamedTuple, cast

from . import __version__
from .core_client import CORE_VERSION, PROTOCOL, CoreClient, CoreUnavailable

NATIVE_DISTRIBUTION = 'biocompiler-core'
RELEASE_SCHEMA = 'biocompiler.core_release.v1'
DISTRIBUTION_SCHEMA = 'biocompiler.core_distribution.v1'
PLATFORMS = {
    'linux-x86_64': ('Linux', 'x86_64', 'py3-none-manylinux_2_39_x86_64'),
    'macos-arm64': ('Darwin', 'arm64', 'py3-none-macosx_14_0_arm64'),
}
FILES = ('__init__.py', 'bin/biocompiler-core', 'bin/biocompiler-verify',
    'binaries.json', 'dependencies.opam.locked', 'switch.export', 'packages.txt', 'linkage.json',
    'materials.json', 'notices.json', 'materials-companion.json', 'static-gmp.json', 'gmp.pc', 'linkage-receipt.json')
MAXIMUM_BINARY = 256 * 1024 * 1024
SDK_DIRECTORY = Path(__file__).resolve().parent


def _require(condition: object, message: str) -> None:
    if not condition:
        raise CoreUnavailable(message)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == keys, 'Invalid '+label+' fields')
    return cast(dict[str, Any], value)


def _json(raw: bytes) -> Any:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in values:
            _require(key not in result, 'Duplicate prebuilt manifest key')
            result[key] = value
        return result
    def constant(_: str) -> None:
        raise CoreUnavailable('Nonfinite prebuilt manifest value')
    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise CoreUnavailable('Malformed prebuilt manifest') from error


def _distribution(name: str) -> metadata.Distribution:
    def normalize(value: str) -> str:
        return re.sub(r'[-_.]+', '-', value).lower()
    found = [value for value in metadata.distributions()
        if normalize(value.metadata['Name'] or '') == name]
    _require(len(found) == 1, 'Install exactly one owned '+name+' distribution')
    _require(found[0].version == __version__, 'Prebuilt distribution and SDK release differ')
    return found[0]


def _owned(distribution: metadata.Distribution, relative: str, maximum: int) -> tuple[Path, bytes]:
    candidates = [item for item in distribution.files or () if str(item) == relative]
    _require(len(candidates) == 1, 'Missing or duplicate owned package file: '+relative)
    entry = candidates[0]
    root = Path(str(distribution.locate_file('.'))).absolute()
    path = Path(str(distribution.locate_file(entry))).absolute()
    _require(path.is_relative_to(root), 'Owned native path escaped the distribution')
    for ancestor in (path, *path.parents):
        if ancestor == root:
            break
        _require(not ancestor.is_symlink(), 'Symlinked owned native path: '+relative)
    _require(path.resolve().is_relative_to(root.resolve()), 'Resolved native path escaped its distribution')
    try:
        before = path.lstat()
        _require(stat.S_ISREG(before.st_mode), 'Nonregular owned package file: '+relative)
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, 'rb') as source:
            info = os.fstat(source.fileno())
            _require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
                (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns), 'Owned file changed before reading')
            _require(stat.S_ISREG(info.st_mode) and 0 <= info.st_size <= maximum,
                'Missing, nonregular or oversized owned package file: '+relative)
            raw = source.read(maximum+1)
    except OSError as error:
        raise CoreUnavailable('Unavailable owned package file: '+relative) from error
    _require(len(raw) == info.st_size and len(raw) <= maximum, 'Owned file changed while reading')
    digest = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b'=').decode('ascii')
    _require(entry.hash is not None and entry.hash.mode == 'sha256' and entry.hash.value == digest
        and entry.size == len(raw), 'Owned file differs from wheel RECORD: '+relative)
    return path, raw


def _platform() -> str:
    current = (platform.system(), platform.machine())
    matches = [name for name, value in PLATFORMS.items() if current == value[:2]]
    _require(len(matches) == 1, 'No prebuilt Core for this operating system and architecture')
    target = matches[0]
    if target == 'linux-x86_64':
        libc, version = platform.libc_ver()
        _require(libc == 'glibc' and re.fullmatch(r'[0-9]+\.[0-9]+', version)
            and tuple(map(int, version.split('.'))) >= (2, 39), 'Prebuilt Core requires glibc 2.39 or newer')
    else:
        version = platform.mac_ver()[0]
        _require(re.fullmatch(r'[0-9]+(?:\.[0-9]+){1,2}', version)
            and tuple(map(int, version.split('.'))) >= (14, 0), 'Prebuilt Core requires macOS 14 or newer')
    return target


def _image(raw: bytes, target: str) -> None:
    if target == 'linux-x86_64':
        valid = (len(raw) >= 64 and raw[:6] == b'\x7fELF\x02\x01'
            and int.from_bytes(raw[16:18], 'little') in (2, 3) and int.from_bytes(raw[18:20], 'little') == 62)
    else:
        valid = (len(raw) >= 32 and raw[:4] == b'\xcf\xfa\xed\xfe'
            and int.from_bytes(raw[4:8], 'little') == 0x0100000c and int.from_bytes(raw[12:16], 'little') == 2)
    _require(valid, 'Owned executable image does not match the selected native platform')


class InstalledCoreDistribution(NamedTuple):
    """Immutable owned-path evidence; no semantic result or process is cached."""
    package_root: Path
    sdk_root: Path
    release_bytes: bytes
    distribution_bytes: bytes
    binaries_bytes: bytes
    linkage_bytes: bytes
    file_pins: tuple[tuple[str, Path, str, int], ...]
    sdk_file_pins: tuple[tuple[str, Path, str, int], ...]

    def executable(self, role: Literal['core', 'verify']) -> Path:
        _require(role in ('core', 'verify'), 'Unknown prebuilt executable role')
        name = 'bin/biocompiler-' + role
        return next(path for member, path, _, _ in self.file_pins if member == name)

    def ownership(self) -> dict[str, Any]:
        release = _json(self.release_bytes)
        manifest = _json(self.distribution_bytes)
        return {'schema_version': 'biocompiler.installed_core_ownership.v1',
            'package_root': str(self.package_root), 'sdk_root': str(self.sdk_root),
            'source_revision': release['source_revision'], 'tested_revision': release['tested_revision'],
            'run_id': release['run_id'], 'native_platform': manifest['native_platform'],
            'release_sha256': _sha(self.release_bytes), 'distribution_sha256': _sha(self.distribution_bytes),
            'manifest_sha256': _sha(self.binaries_bytes),
            'files': {name: {'path': str(path), 'sha256': digest, 'size': size}
                for name, path, digest, size in self.file_pins},
            'sdk_files': {name: {'path': str(path), 'sha256': digest, 'size': size}
                for name, path, digest, size in self.sdk_file_pins}}


def installed_distribution() -> InstalledCoreDistribution:
    """Revalidate complete owned SDK/native files without starting any process."""
    target = _platform()
    sdk = _distribution('biocompiler')
    sdk_files = []
    for name in ('__init__.py', 'core_distribution.py', 'core_client.py'):
        owned_path, sdk_raw = _owned(sdk, 'biocompiler/'+name, 1024*1024)
        _require(owned_path.resolve() == SDK_DIRECTORY/name, 'SDK discovery does not belong to the loaded package')
        sdk_files.append((name, owned_path, _sha(sdk_raw), len(sdk_raw)))
    release_path, release_bytes = _owned(sdk, 'biocompiler/_core_release.json', 64*1024)
    sdk_files.append(('_core_release.json', release_path, _sha(release_bytes), len(release_bytes)))
    release = _object(_json(release_bytes), {'schema_version', 'sdk_version', 'distribution',
        'distribution_version', 'source_revision', 'tested_revision', 'run_id', 'platforms'}, 'SDK core release')
    _require(release['schema_version'] == RELEASE_SCHEMA and release['sdk_version'] == __version__
        and release['distribution'] == NATIVE_DISTRIBUTION and release['distribution_version'] == __version__
        and type(release['source_revision']) is str and re.fullmatch(r'[0-9a-f]{40}', release['source_revision']),
        'Incompatible SDK core release authority')
    _require(type(release['tested_revision']) is str and re.fullmatch(r'[0-9a-f]{40}', release['tested_revision'])
        and type(release['run_id']) is str and re.fullmatch(r'[0-9]+', release['run_id']),
        'Invalid tested revision or hosted run identity')
    pins = _object(release['platforms'], set(PLATFORMS), 'supported platform release pins')
    for pin in pins.values():
        _require(type(pin) is str and re.fullmatch(r'[0-9a-f]{64}', pin), 'Invalid platform release pin')
    native = _distribution(NATIVE_DISTRIBUTION)
    # pip may add installer-generated bytecode to RECORD. This module never
    # imports biocompiler_core; only exact caches for its empty __init__ source
    # are non-authoritative installation byproducts, not executable authority.
    cache = re.compile(r'biocompiler_core/__pycache__/__init__\.'+re.escape(sys.implementation.cache_tag or '')+r'(?:\.opt-[12])?\.pyc')
    owned = [str(item) for item in native.files or () if str(item).startswith('biocompiler_core/')
        and not cache.fullmatch(str(item))]
    _require(sorted(owned) == sorted('biocompiler_core/'+name for name in (*FILES, 'distribution.json')),
        'Native package file inventory differs from the closed release layout')
    _, manifest_bytes = _owned(native, 'biocompiler_core/distribution.json', 64*1024)
    _require(_sha(manifest_bytes) == pins[target], 'Native manifest differs from the SDK release pin')
    manifest = _object(_json(manifest_bytes), {'schema_version', 'distribution', 'distribution_version',
        'sdk_version', 'core_version', 'protocol', 'source_revision', 'tested_revision', 'run_id', 'native_platform', 'wheel_tag', 'files'},
        'native distribution manifest')
    expected = {'schema_version': DISTRIBUTION_SCHEMA, 'distribution': NATIVE_DISTRIBUTION,
        'distribution_version': __version__, 'sdk_version': __version__, 'core_version': CORE_VERSION,
        'protocol': PROTOCOL, 'source_revision': release['source_revision'],
        'tested_revision': release['tested_revision'], 'run_id': release['run_id'], 'native_platform': target,
        'wheel_tag': PLATFORMS[target][2]}
    _require(all(manifest.get(key) == value for key, value in expected.items()),
        'Stale or incompatible native distribution manifest')
    wheel = native.read_text('WHEEL') or ''
    _require([line for line in wheel.splitlines() if line.startswith('Tag: ')] == ['Tag: '+expected['wheel_tag']]
        and 'Root-Is-Purelib: false' in wheel.splitlines(), 'Installed native wheel tag differs from release policy')
    files = _object(manifest['files'], set(FILES), 'complete native file inventory')
    checked = {}
    for name in FILES:
        maximum = MAXIMUM_BINARY if name.startswith('bin/') else 1024*1024
        pin = _object(files[name], {'sha256', 'size'}, 'native file pin')
        path, raw = _owned(native, 'biocompiler_core/'+name, maximum)
        _require(type(pin['size']) is int and pin['size'] == len(raw) and pin['sha256'] == _sha(raw),
            'Owned native file differs from its release manifest: '+name)
        checked[name] = path, raw
    binaries = _object(_json(checked['binaries.json'][1]), {'revision', 'system', 'machine', 'sha256'},
        'original native binary manifest')
    _require(binaries['revision'] == release['tested_revision']
        and (binaries['system'], binaries['machine']) == PLATFORMS[target][:2],
        'Binary manifest has stale revision or wrong platform')
    hashes = _object(binaries['sha256'], {'biocompiler-core', 'biocompiler-verify'}, 'both executable identities')
    for name, digest in hashes.items():
        path, raw = checked['bin/'+name]
        _require(raw and _sha(raw) == digest and os.access(path, os.X_OK),
            'Owned executable is missing, altered or not executable')
        _image(raw, target)
    linkage = _object(_json(checked['linkage.json'][1]), {'schema_version', 'native_platform', 'policy', 'sha256'},
        'native linkage audit')
    _require(linkage == {'schema_version': 'biocompiler.core_linkage.v1', 'native_platform': target,
        'policy': 'system-libraries-only.v1', 'sha256': hashes}, 'Native linkage audit does not bind both final binaries')
    package_root = checked['binaries.json'][0].parent
    _require(all(path == package_root / name for name, (path, _) in checked.items()),
             'Owned native members do not share the exact package layout')
    return InstalledCoreDistribution(package_root, SDK_DIRECTORY, release_bytes, manifest_bytes,
        checked['binaries.json'][1], checked['linkage.json'][1],
        tuple((name, path, _sha(raw), len(raw)) for name, (path, raw) in checked.items()), tuple(sdk_files))


def installed_core(*, role: Literal['core', 'verify'] = 'core', operation: str = 'capabilities',
                   timeout_seconds: float = 30.0) -> CoreClient:
    """Check complete owned release bytes and freshly negotiate one actual role."""
    _require(role in ('core', 'verify'), 'Unknown prebuilt executable role')
    selected = installed_distribution()
    hashes = _json(selected.binaries_bytes)['sha256']
    client = CoreClient(selected.executable(role), role=role, timeout_seconds=timeout_seconds,
        expected_sha256=hashes['biocompiler-' + role])
    client.negotiate(operation)
    return client
