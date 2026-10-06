"""Exact historical source identities for the immutable manager corpora.

Only the separately reviewed manager registration, two reference entry prefixes
and two policy package entrypoints have counterparts. Every other captured file
retains its exact historical bytes. Content-pinned witnesses reject any additional
change.
"""
from __future__ import annotations
from pathlib import Path

from tools import manager_registration_source_lineage as lineage


def verify_source_identity(root: Path, path: str, historical_sha256: str):
    root = Path(root)
    if path == lineage.PATH:
        return lineage.verify_source(root, path, historical_sha256)
    if path in ('src/biocompiler/compiler/construct.py', 'src/biocompiler/compiler/molecular.py'):
        from tools import reference_original_counterpart as reference
        original, proof = reference.route_source_witness(path)
        if historical_sha256 != lineage.sha(original):
            raise AssertionError('Original reference source identity changed: ' + path)
        current = (root / path).read_bytes()
        if current != original:
            restored, proof = reference.route_source_witness(path, current)
            if restored != original:
                raise AssertionError('Original reference source restoration changed: ' + path)
        return {'path': path, 'historical_sha256': historical_sha256,
                'current_sha256': lineage.sha(current),
                'kind': 'identical_bytes' if current == original else 'reference_entry_prefix',
                'witness_sha256': proof['witness_sha256']}
    if path in ('src/biocompiler/__init__.py', 'src/biocompiler/__main__.py'):
        from tools import policy_entrypoint_source_lineage as policy
        original = policy.witness(root)['sources'][path]['before_source'].encode()
        if historical_sha256 != lineage.sha(original):
            raise AssertionError('Original policy entrypoint source identity changed: ' + path)
        current = (root / path).read_bytes()
        if current == original:
            return {'path': path, 'historical_sha256': historical_sha256,
                    'current_sha256': historical_sha256, 'kind': 'identical_bytes',
                    'witness_sha256': policy.WITNESS_SHA256}
        return policy.verify_source(root, path, historical_sha256)
    actual = lineage.sha((root / path).read_bytes())
    if actual != historical_sha256:
        raise AssertionError('Original captured source bytes changed: ' + path)
    return {'path': path, 'historical_sha256': historical_sha256,
            'current_sha256': actual, 'kind': 'identical_bytes'}
