"""Source-bound proof of the native branch of the public registration method."""
import ast
import dis
import json
import sys
from pathlib import Path

from tools import manager_registration_source_lineage as lineage
from biocompiler.core_pipeline_manager import CorePassManager as _CANONICAL_CORE

TAG = 'native-registration-delegation'
BASE = ('biocompiler.compiler.pipeline', 'PassManager.register')
NATIVE = 'src/biocompiler/core_pipeline_manager.py'
RUNTIME_SITES='tests/conformance/manager-registration-runtime-sites-v2.json'
RUNTIME_PIN='0c880bbf1532268ecfd71cf3e79b75c5b4f8d13d8ddb03daa8919871e8330977'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def authority():
    entry = lineage.load_witness()
    return {'base_sha256': entry['routed_sha256'], 'native_sha256': lineage.sha((lineage.ROOT / NATIVE).read_bytes()),
        'witness_sha256': lineage.WITNESS_SHA256, 'base': 'PassManager.register',
        'entry': 'CorePassManager._native_register', 'receiver': 'biocompiler.core_pipeline_manager.CorePassManager',
        'arguments': ['self', 'contract', 'producer', 'validators'], 'immediate_entry_count': 1}


def runtime_authority(runtime):
    raw=(lineage.ROOT/RUNTIME_SITES).read_bytes()
    require(lineage.sha(raw)==RUNTIME_PIN,'Registration runtime-site witness changed')
    document=json.loads(raw)
    require(document['schema']=='biocompiler.registration_entry_runtime_sites.v1'
        and [item['runtime'] for item in document['runtimes']]==[[3,11],[3,14]], 'Registration runtime census differs')
    rows=[item for item in document['runtimes'] if item['runtime']==runtime]
    require(len(rows)==1 and rows[0]['source_sha256']==authority()['native_sha256'],
        'Registration runtime sites are detached from reviewed source')
    return rows[0]


def proof(request, reply):
    """Closed receipt construction; execution authority comes from Recorder only."""
    return {**authority(), 'kind':'command', 'session': request['session_id'], 'sequence': request['sequence'],
        'request_sha256': lineage.sha(canonical(request)), 'reply_sha256': lineage.sha(canonical(reply))}


class Recorder:
    def __init__(self, seen):
        from tools.check_pipeline_deferred_runtime import same_code
        self.same_code, self.seen, self.pending = same_code, seen, []
        self.module, self.core, self.base_code, self.native_code = lineage.installed_route()
        require(self.core.CorePassManager is _CANONICAL_CORE, 'Installed native manager class was replaced')
        runtime=runtime_authority(list(sys.version_info[:2]))
        require(lineage.sha(self.native_code.co_code)==runtime['bytecode_sha256']
            and lineage.sha(self.native_code.co_linetable)==runtime['line_table_sha256'],
            'Actual native registration code differs from pinned runtime sites')

    def is_base(self, frame):
        return frame.f_globals.get('__name__') == BASE[0] and frame.f_code.co_qualname == BASE[1]

    def enter(self, frame):
        require(frame.f_globals is vars(self.module) and self.same_code(frame.f_code, self.base_code),
            'Native delegation frame has foreign source or globals')
        manager = frame.f_locals.get('self')
        require(issubclass(type(manager), _CANONICAL_CORE),
            'Original Python manager semantic branch is forbidden')
        self.pending.append({'frame': frame, 'manager': manager, 'offset': len(manager.session.traffic),
            'entered': False, 'native_frame': None, 'call_entered': False, 'unwind': None})

    def observe(self, frame, event):
        if self.is_base(frame):
            if event == 'call':
                self.enter(frame)
                return True
            if event == 'return':
                found = [row for row in self.pending if row['frame'] is frame]
                require(len(found) == 1 and found[0]['entered'], 'Native delegation omitted its private entry')
                row = found[0]
                session = row['manager'].session
                incoming = [item for item in session.traffic[row['offset']:] if item.direction=='client' and item.value['kind']=='command']
                if not row['call_entered']:
                    require(not incoming and row['unwind'] is not None, 'Native pre-command rejection was not an actual exception unwind')
                    record={**authority(), 'kind':'pre-command-exception', 'session':session._nonce,
                        'frame_offset':row['offset'], 'frame_end':len(session.traffic), 'site':row['unwind'],
                        'runtime':list(sys.version_info[:2])}
                    self.seen.add((TAG,canonical(record).decode()))
                    self.pending.remove(row)
                    return False
                response = session.last_response
                require(response is not None and response.operation == 'register',
                    'Native delegation lost its owning registration reply')
                requests = [item for item in session.traffic[row['offset']:] if item.direction == 'client'
                    and item.value['kind'] == 'command' and item.value['sequence'] == response.sequence]
                replies = [item for item in session.traffic[row['offset']:] if item.direction == 'server'
                    and item.value['kind'] == 'reply' and item.value['sequence'] == response.sequence]
                require(len(requests) == len(replies) == 1 and requests[0].value['operation'] == 'register',
                    'Native delegation lacks its actual command pair')
                request, reply = requests[0], replies[0]
                record = proof(request.value, reply.value)
                # The protocol is canonical today, but bind exact raw bodies as
                # the transport does rather than assume re-encoding equivalence.
                record['request_sha256'] = lineage.sha(request.frame[9:])
                record['reply_sha256'] = lineage.sha(reply.frame[9:])
                record['kind']='command'
                self.seen.add((TAG, canonical(record).decode()))
                self.pending.remove(row)
        if event == 'call' and frame.f_code is self.native_code:
            parents = [row for row in self.pending if row['frame'] is frame.f_back]
            require(len(parents) == 1, 'Private native registration bypassed public delegation')
            row = parents[0]
            require(not row['entered'] and frame.f_globals is vars(self.core)
                and all(frame.f_locals.get(name) is row['frame'].f_locals.get(name)
                    for name in ('self', 'contract', 'producer', 'validators')),
                'Native delegation changed argument identities or repeated its private entry')
            row['entered'] = True
            row['native_frame'] = frame
        for row in self.pending:
            if event=='call' and frame.f_globals is vars(self.core) and frame.f_code.co_qualname=='CorePassManager._call' and frame.f_locals.get('operation')=='register':
                caller=frame.f_back
                if caller is not None and caller.f_back is row['native_frame']:
                    row['call_entered']=True
            if event=='return' and frame is row['native_frame']:
                instruction=next(item for item in dis.get_instructions(frame.f_code,show_caches=True) if item.offset==frame.f_lasti)
                if not instruction.opname.startswith('RETURN'):
                    row['unwind']={'line':frame.f_lineno,'offset':instruction.offset,'opcode':instruction.opname}
        return False

    def complete(self):
        require(not self.pending, 'Native delegation proof was interrupted')


def validate(entries, frames, artifacts):
    records = []
    for module, value in entries:
        if module == TAG:
            record = json.loads(value)
            require(type(record) is dict and record.get('kind') in ('command','pre-command-exception'), 'Malformed native delegation proof')
            fields={'sequence','request_sha256','reply_sha256'} if record['kind']=='command' else {'frame_offset','frame_end','site','runtime'}
            require(canonical(record).decode() == value and set(record) == set(authority()) |
                {'session','kind'} | fields, 'Malformed native delegation proof')
            require(all(record.get(key) == item for key, item in authority().items()),
                'Native delegation source or branch authority differs')
            records.append(record)
    require(frames is not None and artifacts is not None, 'Native delegation requires actual complete frame evidence')
    groups = frames if frames and type(frames[0]) is list else [frames]
    expected = []
    for group in groups:
        values = []
        for row in group:
            raw = artifacts.raw(row['frame'])
            values.append((row['direction'], json.loads(raw[9:]), raw[9:]))
        for direction, request, body in values:
            if direction != 'client' or request['kind'] != 'command' or request['operation'] != 'register':
                continue
            replies = [(reply, raw) for side, reply, raw in values if side == 'server' and reply['kind'] == 'reply'
                and reply['session_id'] == request['session_id'] and reply['sequence'] == request['sequence']]
            require(len(replies) == 1, 'Delegation command lacks exact owning reply')
            reply, reply_body = replies[0]
            require(reply['request_sha256'] == lineage.sha(body), 'Delegation reply lost raw request binding')
            expected.append({**authority(), 'kind':'command', 'session': request['session_id'], 'sequence': request['sequence'],
                'request_sha256': lineage.sha(body), 'reply_sha256': lineage.sha(reply_body)})
    for record in records:
        if record['kind']=='pre-command-exception':
            candidates=[group for group in groups if group and json.loads(artifacts.raw(group[0]['frame'])[9:])['session_id']==record['session']]
            require(len(candidates)==1 and type(record['frame_offset']) is int and record['frame_offset']==record['frame_end']
                and 0<=record['frame_offset']<=len(candidates[0]), 'Pre-command exception contains traffic or another session')
            site=record['site']
            tree=ast.parse((lineage.ROOT/NATIVE).read_bytes())
            method=next(node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name=='_native_register')
            permitted={node.lineno for node in ast.walk(method) if isinstance(node,(ast.Call,ast.Raise))}
            runtime=runtime_authority(record['runtime'])
            require(type(site) is dict and set(site)=={'line','offset','opcode'} and site in runtime['sites'] and site['line'] in permitted
                and site['opcode'] in ('CALL','CALL_KW','CALL_FUNCTION_EX','CACHE','RAISE_VARARGS','RERAISE'),
                'Pre-command exception lacks its closed native entry unwind site')
    require(sorted(canonical(item) for item in records if item['kind']=='command') == sorted(canonical(item) for item in expected),
        'Native delegation proofs differ from complete registration command census')
    require((list(BASE) in entries) == bool(records), 'Native delegation frame census differs from branch proofs')
    return [entry for entry in entries if entry[0] != TAG and tuple(entry) != BASE]
