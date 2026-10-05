"""Exact source counterpart for the finite reference-package entry prefixes.

The complete current bytes and the original bytes are separately pinned. Only
these reviewed insertions can be removed; no imported source supplies authority.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import MappingProxyType

import biocompiler
from biocompiler.core_package_owner import PackageBoundaryError

BASE_REVISION = "573cfdf6504572cfc0fdd045bbd018c9e4d85320"
_PACKAGE = Path(biocompiler.__file__).resolve().parent
_SOURCES = MappingProxyType({
    'compiler/reference.py': ('61a1ec4412112c1443bfc4f548d4de0b620b9384a0d9acab67a46639a7353527',
        '8e56175c7f2c82004baa2ddc4652ace854a6b9bc36f2602724635b688a741cf9',
        (('_tools', "    import sys as _package_sys\n    _package_backend = _package_sys.modules.get('biocompiler.reference_package_backend')\n    if _package_backend is not None:\n        _package_value = _package_backend.default('_tools')\n        if _package_value is not _package_backend.UNSELECTED:\n            return _package_value\n"), ('prepare_reference_build', "    import sys as _package_sys\n    _package_backend = _package_sys.modules.get('biocompiler.reference_package_backend')\n    _package_route = None if _package_backend is None else _package_backend.current()\n    if _package_route is not None:\n        return _package_route.prepare(alphabet, reference_directory, fasta_line_width=fasta_line_width)\n"), ('build_reference_package', "    import sys as _package_sys\n    _package_backend = _package_sys.modules.get('biocompiler.reference_package_backend')\n    _package_route = None if _package_backend is None else _package_backend.current()\n    if _package_route is not None:\n        return _package_route.build(request, reference_directory, run_metadata=run_metadata)\n"), ('verify_reference_package', "    import sys as _package_sys\n    _package_backend = _package_sys.modules.get('biocompiler.reference_package_backend')\n    _package_route = None if _package_backend is None else _package_backend.current()\n    if _package_route is not None:\n        return _package_route.reconstruct(data, expected_request=expected_request, expected_build_fingerprint=expected_build_fingerprint)\n"), ('publish_reference_package', "    import sys as _package_sys\n    _package_backend = _package_sys.modules.get('biocompiler.reference_package_backend')\n    _package_route = None if _package_backend is None else _package_backend.current()\n    if _package_route is not None:\n        return _package_route.publish(package, output)\n"))),
    'registry/reference_builds.py': ('5fe58bb430fb3d0870161815f9bca232910751fcd6698b4a83bb1cf8ee256c96',
        'bca8a9d704d656d215479271e80564997ea4cb12bf616378defa2e9657a1af43',
        (('load_reference_inputs', "    import sys as _package_sys\n    _package_backend = _package_sys.modules.get('biocompiler.reference_package_backend')\n    if _package_backend is not None:\n        _package_value = _package_backend.default('load_reference_inputs', alphabet, reference_directory)\n        if _package_value is not _package_backend.UNSELECTED:\n            return _package_value\n"), ('collect_reference_files', "    import sys as _package_sys\n    _package_backend = _package_sys.modules.get('biocompiler.reference_package_backend')\n    if _package_backend is not None:\n        _package_value = _package_backend.default('collect_reference_files', reference_directory, manifest)\n        if _package_value is not _package_backend.UNSELECTED:\n            return _package_value\n"))),
    'artifacts/sequences.py': ('e5240d52aa7a2d97453b1e57cf84af159ed880015d0892f80e8fb1dfc587ed03',
        'ba7264d7e9fb19c693ddeb54e570ac6bc09e17638b1dc6c50acb4e0ec71598c3',
        (('export_reference_sequence', "    import sys as _package_sys\n    _package_backend = _package_sys.modules.get('biocompiler.reference_package_backend')\n    _package_route = None if _package_backend is None else _package_backend.current()\n    if _package_route is not None:\n        return _package_route.export(request, construct, artifact, registry, manifests, line_width=line_width)\n"),)),
    'verification/components.py': ('1112dfd60791cb55eac6343c8e7a08d59f3b9f11a1618dc1fb1a82654da3af4a',
        '81320d87650a2d5f2aaffb16957c5388c5576218f0d68a4d8bf0ddcc4a76bda3',
        (('check_composition', "    import sys as _package_sys\n    _package_backend = _package_sys.modules.get('biocompiler.reference_package_backend')\n    if _package_backend is not None:\n        _package_value = _package_backend.default('check_composition', request, registry)\n        if _package_value is not _package_backend.UNSELECTED:\n            return _package_value\n"),)),
    'verification/construct.py': ('370686f2379158303e5b059882205350ebabd200499dffa105c58d56dde891cc',
        'd648609057ee528bb4d1a90179b6b3daa7938d915713966e44d120930fc0b793',
        (('check_construct', "    import sys as _package_sys\n    _package_backend = _package_sys.modules.get('biocompiler.reference_package_backend')\n    if _package_backend is not None:\n        _package_value = _package_backend.default('check_construct', request, candidate, registry, manifests)\n        if _package_value is not _package_backend.UNSELECTED:\n            return _package_value\n"),)),
    'verification/molecular.py': ('0a12ceba4dadcea95b90770ec640edd30df95b854829d1e5307e809b09fc056c',
        '34b06b55ab1cb2866ab34e53a6d0039c9f3f827eb97d0dd056dc68303c0213f2',
        (('check_molecular', "    import sys as _package_sys\n    _package_backend = _package_sys.modules.get('biocompiler.reference_package_backend')\n    if _package_backend is not None:\n        _package_value = _package_backend.default('check_molecular', request, construct, candidate, registry, manifests)\n        if _package_value is not _package_backend.UNSELECTED:\n            return _package_value\n"),)),
    'compiler/molecular.py': ('040d85262f0b96f00e20276237a42bba9f68de8bd61e06148621432417ce4166',
        '040d85262f0b96f00e20276237a42bba9f68de8bd61e06148621432417ce4166', ()),
})


def check_source(path: Path, raw: bytes) -> bytes:
    """Verify current installed bytes and return the exact original counterpart."""
    try:
        relative = path.relative_to(_PACKAGE).as_posix()
    except ValueError as error:
        raise PackageBoundaryError('Package source lies outside its installed package') from error
    authority = _SOURCES.get(relative)
    if authority is None or type(raw) is not bytes:
        raise PackageBoundaryError('Package source lacks an exact reviewed counterpart')
    before, after, prefixes = authority
    if hashlib.sha256(raw).hexdigest() != after:
        raise PackageBoundaryError('Package current source bytes differ')
    restored = raw
    for _, text in prefixes:
        prefix = text.encode('utf-8')
        if restored.count(prefix) != 1:
            raise PackageBoundaryError('Package source prefix is absent or repeated')
        restored = restored.replace(prefix, b'', 1)
    if hashlib.sha256(restored).hexdigest() != before:
        raise PackageBoundaryError('Package original source counterpart differs')
    return restored
