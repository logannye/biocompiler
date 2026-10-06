"""Exact capture-overlap predecessor layer; prior witnesses remain immutable."""
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
WITNESS = ROOT/'tests/conformance/pipeline-capture-overlap-source-delta-v1.json'
WITNESS_SHA256 = 'a6d817a7b8cbbca6a06608a0b495d2ad5520cb279e0793521d32310b26cb3c10'
PATHS = {'tools/pipeline_original_counterpart.py', 'tools/check_pipeline_fixed_continuation_install.py'}

def restore(path, current, proof_bytes=None):
    if path not in PATHS: return current
    from tools import pipeline_policy_counterpart_source
    current = pipeline_policy_counterpart_source.restore(path, current)
    def require(value, message):
        if not value: raise AssertionError(message)
    def pin(raw): return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    raw = WITNESS.read_bytes() if proof_bytes is None else proof_bytes
    require(hashlib.sha256(raw).hexdigest() == WITNESS_SHA256, 'Unreviewed capture overlap source witness')
    proof = json.loads(raw)
    require(set(proof) == {'schema','base_revision','files'}
        and proof['schema'] == 'biocompiler.pipeline_capture_overlap_source_delta.v1'
        and proof['base_revision'] == '54e73a5c10c7f86a5f389ea7b71932f68ed0c092'
        and set(proof['files']) == PATHS, 'Capture overlap source witness scope differs')
    row = proof['files'][path]
    require(set(row) == {'historical','current','spans'} and row['current'] == pin(current),
        'Current source differs from reviewed capture overlap delta')
    spans = row['spans']; end = 0
    require(type(spans) is list and spans, 'Missing capture overlap spans')
    for span in spans:
        require(set(span) == {'offset','before','after'} and type(span['offset']) is int
            and span['offset'] >= end and type(span['before']) is str and type(span['after']) is str,
            'Malformed capture overlap span')
        end = span['offset'] + len(span['before'].encode())
    restored = current
    for index, span in reversed(list(enumerate(spans))):
        offset = span['offset'] + sum(len(item['after'].encode())-len(item['before'].encode()) for item in spans[:index])
        before, after = span['before'].encode(), span['after'].encode()
        require(restored[offset:offset+len(after)] == after, 'Capture overlap source span differs')
        restored = restored[:offset] + before + restored[offset+len(after):]
    require(pin(restored) == row['historical'], 'Complete capture predecessor differs')
    return restored
