"""Exact closure-snapshot predecessor; all older witnesses stay immutable.

This source proof restores the complete reviewed runner and the driver's
SOURCES-only extension. It does not cache validation or accept semantic output.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATHS = frozenset(('tools/pipeline_original_counterpart.py',
                   'tools/check_pipeline_fixed_continuation_install.py'))
WITNESS = ROOT / 'tests/conformance/pipeline-counterpart-closure-source-delta-v1.json'
WITNESS_SHA256 = '36618228e3d21056806c8bfdd641234b2acedef683f2c46c33b2fe670778190a'
MAX_WITNESS_BYTES = 1024 * 1024


def restore(path, current, proof_bytes=None):
    if path not in PATHS:
        return current

    def require(value, message):
        if not value:
            raise AssertionError(message)

    def pin(raw):
        return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}

    if proof_bytes is None:
        require(WITNESS.is_file() and not WITNESS.is_symlink()
                and WITNESS.stat().st_size <= MAX_WITNESS_BYTES,
                'Counterpart closure witness missing, redirected or oversized')
        raw = WITNESS.read_bytes()
    else:
        raw = proof_bytes
    require(type(raw) is bytes and len(raw) <= MAX_WITNESS_BYTES
            and hashlib.sha256(raw).hexdigest() == WITNESS_SHA256,
            'Unreviewed counterpart closure source witness')
    proof = json.loads(raw)
    require(set(proof) == {'schema', 'base_revision', 'files'}
            and proof['schema'] == 'biocompiler.pipeline_counterpart_closure_source_delta.v1'
            and proof['base_revision'] == '77d6be591921482735c48b1940ccbfdfd1b2362e'
            and set(proof['files']) == PATHS,
            'Counterpart closure witness scope differs')
    for row in proof['files'].values():
        require(set(row) == {'historical', 'current', 'historical_source', 'current_source'},
                'Counterpart closure source scope differs')
        require(pin(row['historical_source'].encode()) == row['historical']
                and pin(row['current_source'].encode()) == row['current'],
                'Counterpart closure complete source identity differs')
    row = proof['files'][path]
    require(type(current) is bytes and current == row['current_source'].encode(),
            'Current source differs from reviewed counterpart closure snapshot')
    return row['historical_source'].encode()
