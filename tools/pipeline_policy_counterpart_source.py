"""Exact runner predecessor; existing capture witnesses remain unchanged."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATHS = {'tools/pipeline_original_counterpart.py', 'tools/check_pipeline_fixed_continuation_install.py'}
WITNESS = ROOT / 'tests/conformance/pipeline-policy-counterpart-source-delta-v1.json'
WITNESS_SHA256 = '96bd3db3678535fc57373a0d369c736c9c31ebfd5d331a2e91e373407fb82d54'


def restore(path, current, proof_bytes=None):
    if path not in PATHS:
        return current

    def require(value, message):
        if not value:
            raise AssertionError(message)

    def pin(raw):
        return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}

    raw = WITNESS.read_bytes() if proof_bytes is None else proof_bytes
    require(hashlib.sha256(raw).hexdigest() == WITNESS_SHA256,
            'Unreviewed policy counterpart runner witness')
    proof = json.loads(raw)
    require(set(proof) == {'schema', 'base_revision', 'files'} and
            proof['schema'] == 'biocompiler.pipeline_policy_counterpart_source_delta.v1' and
            proof['base_revision'] == '0dd041ff1964b7a95d25042513c1d55d17890aaa' and set(proof['files']) == PATHS,
            'Policy counterpart runner witness scope differs')
    row = proof['files'][path]
    require(set(row) == {'historical', 'current', 'historical_source', 'current_source'},
            'Policy counterpart runner source scope differs')
    historical, reviewed = row['historical_source'].encode(), row['current_source'].encode()
    require(pin(historical) == row['historical'] and pin(reviewed) == row['current'],
            'Policy counterpart complete runner identity differs')
    from tools import pipeline_counterpart_closure_source
    current = pipeline_counterpart_closure_source.restore(path, current)
    require(type(current) is bytes and current == reviewed,
            'Current source differs from reviewed policy counterpart runner')
    return historical
