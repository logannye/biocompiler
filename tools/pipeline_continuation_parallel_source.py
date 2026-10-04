"""Exact additive source restoration before the existing occurrence witness."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PATH='tools/check_pipeline_fixed_continuation_install.py'
WITNESS=ROOT/'tests/conformance/pipeline-continuation-parallel-source-delta-v1.json'
WITNESS_SHA256='bca7480ba6e6a44736c5004b7f5b4bda1294a60b6b32aa9f3bbc43250ed0d4ad'

def restore(path,current,proof_bytes=None):
    if path!=PATH:return current
    def require(value,message):
        if not value:raise AssertionError(message)
    raw=WITNESS.read_bytes()if proof_bytes is None else proof_bytes
    require(hashlib.sha256(raw).hexdigest()==WITNESS_SHA256,'Unreviewed continuation parallel source witness')
    proof=json.loads(raw)
    require(set(proof)=={'schema','base_revision','files'}
        and proof['schema']=='biocompiler.fixed_continuation_parallel_source_delta.v1'
        and proof['base_revision']=='1a8f775429c6b8d23e5a4bc66240f28fdb2a95a2'
        and set(proof['files'])=={PATH},'Parallel source witness scope differs')
    row=proof['files'][PATH]
    def pin(value):return {'bytes':len(value),'sha256':hashlib.sha256(value).hexdigest()}
    require(set(row)=={'historical','current','spans'}and row['current']==pin(current),
        'Current source differs from reviewed continuation parallel delta')
    require(type(row['spans'])is list and row['spans'],'Missing parallel source spans')
    end=0
    for span in row['spans']:
        require(set(span)=={'offset','before','after'}and type(span['offset'])is int and span['offset']>=end
            and type(span['before'])is str and type(span['after'])is str,'Malformed parallel source span')
        end=span['offset']+len(span['before'].encode())
    restored=current
    for index,span in reversed(list(enumerate(row['spans']))):
        offset=span['offset']+sum(len(item['after'].encode())-len(item['before'].encode())for item in row['spans'][:index])
        before,after=span['before'].encode(),span['after'].encode()
        require(restored[offset:offset+len(after)]==after,'Parallel source span differs')
        restored=restored[:offset]+before+restored[offset+len(after):]
    require(pin(restored)==row['historical'],'Complete prior source differs after parallel restoration')
    return restored
