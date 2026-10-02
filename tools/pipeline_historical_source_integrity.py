"""Exact historical source identities for the immutable manager corpora.

Only the separately reviewed manager registration prefix has a counterpart.
Every other captured file must retain its exact historical bytes. The complete
old/current sources and their sole permitted difference stay in the existing
content-pinned witness; a caller cannot bless another edit by rehashing it.
"""
from __future__ import annotations
from pathlib import Path

from tools import manager_registration_source_lineage as lineage


def verify_source_identity(root: Path, path: str, historical_sha256: str):
    root = Path(root)
    if path == lineage.PATH:
        return lineage.verify_source(root, path, historical_sha256)
    actual = lineage.sha((root / path).read_bytes())
    if actual != historical_sha256:
        raise AssertionError('Original captured source bytes changed: ' + path)
    return {'path': path, 'historical_sha256': historical_sha256,
            'current_sha256': actual, 'kind': 'identical_bytes'}
