"""Exact package-prefix and owner-transport counterpart for frozen source checks.

This proves complete prior source bytes only. Historical corpus observations and
native package acceptance remain separate and are never refreshed here.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_REVISION = '573cfdf6504572cfc0fdd045bbd018c9e4d85320'
PUBLIC_WITNESS = 'protocol/reference-package-public-prefixes-v1.json'
PUBLIC_PIN = '2056c3a8f996646999bcbfc690e553c315a6c615a41484ed429b44b067ca7d96'
TRANSPORT_WITNESS = 'tests/conformance/reference-package-transport-source-counterpart-v1.json'
TRANSPORT_PIN = '80573b86ff3e5f08bedacbf631a35d8d7c4a5598e5b80175debc4a74175b67e9'
PUBLIC = {
    'src/biocompiler/compiler/reference.py': ('61a1ec4412112c1443bfc4f548d4de0b620b9384a0d9acab67a46639a7353527', '8e56175c7f2c82004baa2ddc4652ace854a6b9bc36f2602724635b688a741cf9', 5),
    'src/biocompiler/registry/reference_builds.py': ('5fe58bb430fb3d0870161815f9bca232910751fcd6698b4a83bb1cf8ee256c96', 'bca8a9d704d656d215479271e80564997ea4cb12bf616378defa2e9657a1af43', 2),
    'src/biocompiler/artifacts/sequences.py': ('e5240d52aa7a2d97453b1e57cf84af159ed880015d0892f80e8fb1dfc587ed03', 'ba7264d7e9fb19c693ddeb54e570ac6bc09e17638b1dc6c50acb4e0ec71598c3', 1),
    'src/biocompiler/verification/components.py': ('1112dfd60791cb55eac6343c8e7a08d59f3b9f11a1618dc1fb1a82654da3af4a', '81320d87650a2d5f2aaffb16957c5388c5576218f0d68a4d8bf0ddcc4a76bda3', 1),
    'src/biocompiler/verification/construct.py': ('370686f2379158303e5b059882205350ebabd200499dffa105c58d56dde891cc', 'd648609057ee528bb4d1a90179b6b3daa7938d915713966e44d120930fc0b793', 1),
    'src/biocompiler/verification/molecular.py': ('0a12ceba4dadcea95b90770ec640edd30df95b854829d1e5307e809b09fc056c', '34b06b55ab1cb2866ab34e53a6d0039c9f3f827eb97d0dd056dc68303c0213f2', 1),
}
TRANSPORT = {
    'src/biocompiler/core_pipeline_manager.py': ('44eeed2c22a9d07ff254dcd5b1e1edd26cf7e6bcfc29918ae20da39c2fbb544c', 'e70b302502bbae0cf274fb5dc420b276edf033189ea41cc3083575935f7119ba', 3),
    'src/biocompiler/core_pipeline_callback_session.py': ('d24cb3b78df7b7c85d0bbec5cd3c7634ca4756c5e8b0e113a8a3ba7258229a54', '963af95957f4a6c7843fca8f575ebe3817349b9ce0722c59da0cd64d21e9bc51', 17),
}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(value, message):
    if not value:
        raise AssertionError(message)


def restore(logical, raw=None, *, root=ROOT):
    """Accept one exact current source; restore its whole immutable base revision."""
    require(logical in PUBLIC or logical in TRANSPORT, 'Unreviewed package source counterpart')
    current = (root / logical).read_bytes() if raw is None else raw
    before, after, count = (PUBLIC if logical in PUBLIC else TRANSPORT)[logical]
    require(type(current) is bytes and sha(current) == after,
            'Package source is outside its exact counterpart: ' + logical)
    witness, pin = (PUBLIC_WITNESS, PUBLIC_PIN) if logical in PUBLIC else (TRANSPORT_WITNESS, TRANSPORT_PIN)
    encoded = (root / witness).read_bytes()
    require(sha(encoded) == pin, 'Package source counterpart witness changed')
    declaration = json.loads(encoded)
    require(declaration['base_revision'] == BASE_REVISION, 'Package source base revision differs')
    value = declaration['files'][logical.removeprefix('src/biocompiler/') if logical in PUBLIC else logical]
    require(value['before_sha256'] == before and value['after_sha256'] == after,
            'Package source counterpart identities differ')
    restored = current
    if logical in PUBLIC:
        require(declaration['schema_version'] == 'biocompiler.reference_package_public_prefixes.v1'
                and set(declaration['files']) == {name.removeprefix('src/biocompiler/') for name in PUBLIC}
                and len(value['prefixes']) == count, 'Package public source counterpart census differs')
        for row in value['prefixes']:
            prefix = row['text'].encode()
            require(restored.count(prefix) == 1, 'Package source prefix is absent or duplicated')
            restored = restored.replace(prefix, b'', 1)
    else:
        require(declaration['schema_version'] == 'biocompiler.reference_package_transport_counterpart.v1'
                and set(declaration['files']) == set(TRANSPORT) and len(value['changes']) == count
                and len(current) == value['after_bytes'], 'Package transport source counterpart census differs')
        previous = len(current) + 1
        for row in reversed(value['changes']):
            offset, new = row['byte_offset'], row['after'].encode()
            require(type(offset) is int and 0 <= offset < previous and offset + len(new) <= previous
                    and restored[offset:offset + len(new)] == new, 'Package exact source span differs')
            restored = restored[:offset] + row['before'].encode() + restored[offset + len(new):]
            previous = offset
        require(len(restored) == value['before_bytes'], 'Package preceding source size differs')
    require(sha(restored) == before, 'Package complete preceding source differs')
    return restored, {'path': logical, 'historical_sha256': before, 'current_sha256': after,
        'kind': 'reviewed_package_source_counterpart', 'witness': witness, 'witness_sha256': pin}


def source_identity(root, logical):
    raw = (root / logical).read_bytes()
    if logical in PUBLIC or logical in TRANSPORT:
        raw, _ = restore(logical, raw, root=root)
    return sha(raw)


def verify_source(root, logical, historical_sha256):
    original, proof = restore(logical, root=root)
    require(sha(original) == historical_sha256, 'Package original source authority differs')
    return proof


def native_reference_counterpart(raw):
    """Restore the exact outer native source proof before its frozen old gates."""
    if type(raw) is bytes and sha(raw) != 'e9db018e299f112c7e0c606edd6ea51ef1a98bf1bc28ffbb119589a173b1a853':
        from tools.policy_entrypoint_source_lineage import native_reference_counterpart as restore_authoring
        raw = restore_authoring(raw)
    require(type(raw) is bytes and sha(raw) == 'e9db018e299f112c7e0c606edd6ea51ef1a98bf1bc28ffbb119589a173b1a853',
            'Native package source proof differs')
    start = raw.index(b'(* Package integration is one additional finite source restoration layer.')
    end = raw.index(b'let reference_original root name expected current =', start)
    restored = raw[:start] + raw[end:]
    inserted = b'  let current=reference_package_original root name current in\n'
    require(restored.count(inserted) == 1, 'Native package source proof call differs')
    restored = restored.replace(inserted, b'', 1)
    current = b'  let restored=if Canonical.sha256 current=expected then current else if name="src/biocompiler/core_pipeline_manager.py" then'
    previous = b'  let restored=if name="src/biocompiler/core_pipeline_manager.py" then'
    require(restored.count(current) == 1, 'Native package source proof branch differs')
    restored = restored.replace(current, previous, 1)
    require(sha(restored) == '635e650c7370fb6606ee9f775c016f3256072d35b43266a06d0911de60bfb95e', 'Native preceding source proof differs')
    return restored
