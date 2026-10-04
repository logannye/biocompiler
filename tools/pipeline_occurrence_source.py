"""Restore the exact predecessor of the per-occurrence graph correction."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WITNESS = ROOT / 'tests/conformance/pipeline-occurrence-source-delta-v1.json'
WITNESS_SHA256 = '8b8c455783299cfe6cda7f38f94b17a2459a2a0b2b61b6f2a2ece00797d89d9e'


def restore(path, current, proof_bytes=None):
    """Finite reviewed source changes; never a semantic acceptance shortcut."""
    raw = WITNESS.read_bytes() if proof_bytes is None else proof_bytes
    def require(condition, message):
        if not condition:
            raise AssertionError(message)
    require(hashlib.sha256(raw).hexdigest() == WITNESS_SHA256,
        'Unreviewed per-occurrence source witness')
    proof = json.loads(raw)
    require(set(proof) == {'schema', 'revision', 'files'}
        and proof['schema'] == 'biocompiler.pipeline_occurrence_source_delta.v1'
        and proof['revision'] == '1bd9c2e88573e01b3c46d5134dd30d21c76fa0df'
        and set(proof['files']) == {'tools/check_pipeline_fixed_continuation_install.py',
            'tools/pipeline_original_counterpart.py'} and path in proof['files'],
        'Per-occurrence source witness scope differs')
    row = proof['files'][path]
    require(set(row) == {'historical', 'current', 'spans'}
        and row['current'] == {'bytes': len(current), 'sha256': hashlib.sha256(current).hexdigest()},
        'Current source differs from the reviewed per-occurrence correction')
    spans = row['spans']
    require(type(spans) is list and spans, 'Missing per-occurrence source changes')
    end = 0
    for span in spans:
        require(set(span) == {'offset', 'before', 'after'} and type(span['offset']) is int
            and span['offset'] >= end and type(span['before']) is str and type(span['after']) is str,
            'Malformed per-occurrence source change')
        end = span['offset'] + len(span['before'].encode())
    restored = current
    for index, span in reversed(list(enumerate(spans))):
        offset = span['offset'] + sum(len(prior['after'].encode()) - len(prior['before'].encode())
            for prior in spans[:index])
        before, after = span['before'].encode(), span['after'].encode()
        require(restored[offset:offset+len(after)] == after, 'Per-occurrence source span differs')
        restored = restored[:offset] + before + restored[offset+len(after):]
    require(row['historical'] == {'bytes': len(restored), 'sha256': hashlib.sha256(restored).hexdigest()},
        'Complete predecessor source differs after per-occurrence restoration')
    return restored
