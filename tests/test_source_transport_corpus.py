"""Independent integrity checks for the retained source-only transport campaign."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from biocompiler.ir.architecture_build import PayloadArchitectureBuild,PayloadArchitectureRequest
from biocompiler.ir.serialization import fingerprint
from biocompiler.semantics.architecture_execution import evaluate_payload_architecture
from biocompiler.semantics.evaluator import InputFrame,SignalSample
from biocompiler.semantics.types import decode_binding

ROOT=Path(__file__).resolve().parents[1]
CORPUS=ROOT/'tests/conformance/source-transport-v1.json'
EXPECTED_PIN='4da417dc6840da4d4ccdd60341996b72d4524a222e0c8763460d1e65dfaff3f5'

def strict_patch(base,changes):
    result=deepcopy(base)
    for change in changes:
        if set(change)!=({'op','path','value'} if change.get('op')=='set' else {'op','path'}):raise ValueError('fields')
        if change['op'] not in ('set','remove'):raise ValueError('operation')
        path=change['path']
        if not isinstance(path,list) or not 0<len(path)<=96:raise ValueError('path')
        current=result
        for key in path[:-1]:
            if isinstance(current,dict) and type(key) is str and key in current:current=current[key]
            elif isinstance(current,list) and type(key) is int and 0<=key<len(current):current=current[key]
            else:raise ValueError('descent')
        key=path[-1]
        if isinstance(current,dict) and type(key) is str:
            if change['op']=='remove':
                if key not in current:raise ValueError('absent deletion')
                del current[key]
            else:current[key]=deepcopy(change['value'])
        elif isinstance(current,list) and type(key) is int and 0<=key<len(current) and change['op']=='set':current[key]=deepcopy(change['value'])
        else:raise ValueError('terminal')
    return result

def pretty(raw):return (json.dumps(raw,sort_keys=True,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
def canonical(raw):return json.dumps(raw,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def bounded(raw,*,maximum=4_000_000,max_nodes=100000,max_depth=96):
    pending=[(raw,0)];count=0
    while pending:
        value,depth=pending.pop();count+=1
        if depth>max_depth or count>max_nodes:raise ValueError('tree bound')
        if isinstance(value,dict):pending.extend((item,depth+1) for pair in value.items() for item in pair)
        elif isinstance(value,list):pending.extend((item,depth+1) for item in value)
    if len(pretty(raw))>maximum:raise ValueError('byte bound')

def load():
    index=json.loads(CORPUS.read_text());metadata={d['id']:d for d in index['documents']}
    raw={key:json.loads((CORPUS.with_suffix('')/(key+'.json')).read_text()) for key in metadata}
    def resolve(identity):
        descriptor=metadata[identity];value=raw[identity]
        if descriptor['format']=='delta':
            base=descriptor['base'];parent=metadata[base]
            if parent['format']!='full' or parent['base'] is not None or parent['kind']!=descriptor['kind'] or value['base']!=base or base==identity:raise ValueError('baseline')
            value=strict_patch(raw[base],value['edits'])
        elif descriptor['format']!='full' or descriptor['base'] is not None:raise ValueError('format')
        if fingerprint(value)!=identity:raise ValueError('resolved identity')
        bounded(value)
        if len(pretty(value))!=descriptor['resolved_bytes']:raise ValueError('resolved bytes')
        return value
    return index,metadata,raw,resolve

class SourceTransportCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index,cls.metadata,cls.documents,resolver=load()
        cls.resolve=staticmethod(resolver)
    def test_complete_inventory_and_storage_are_pinned(self):
        index=self.index
        self.assertEqual(index['inventory_fingerprint'],EXPECTED_PIN)
        self.assertEqual(fingerprint({k:v for k,v in index.items() if k!='inventory_fingerprint'}),EXPECTED_PIN)
        self.assertEqual(index['schema_version'],'biocompiler.source_transport_conformance.v1')
        self.assertEqual(len(self.metadata),len(index['documents']))
        self.assertEqual({p.name for p in CORPUS.with_suffix('').iterdir()},{key+'.json' for key in self.metadata})
        total=CORPUS.stat().st_size
        for identity,descriptor in self.metadata.items():
            self.assertRegex(identity,r'^[0-9a-f]{64}$')
            raw=self.documents[identity];self.assertEqual(fingerprint(raw),descriptor['stored_fingerprint'])
            bounded(raw);size=(CORPUS.with_suffix('')/(identity+'.json')).stat().st_size
            self.assertEqual(size,descriptor['bytes']);total+=size
            self.resolve(identity)
        self.assertLessEqual(total,16*1024*1024)
        bounded(index,maximum=16*1024*1024,max_nodes=250000,max_depth=128)
    def test_all_nine_original_assertion_methods_and_every_call_are_retained(self):
        from test_architecture_execution import CoupledArchitectureExecutionTests
        prefix='test_architecture_execution.CoupledArchitectureExecutionTests.'
        expected=[prefix+name for name in sorted(dir(CoupledArchitectureExecutionTests)) if name.startswith('test_')]
        ledger=self.index['coverage']['methods']
        self.assertEqual([x['method'] for x in ledger],expected);self.assertEqual(len(expected),9)
        for method in ledger:
            self.assertEqual(method['status'],'source_assertions_executed')
            self.assertEqual(method['retained_calls'],sum(c['id'].startswith(method['method']+'/') for c in self.index['cases']))
        self.assertEqual(sum(x['retained_calls'] for x in ledger),self.index['coverage']['original_calls'])
    def test_complete_authorities_and_every_document_are_reachable(self):
        used=set();identities=set()
        for case in self.index['cases']:
            self.assertNotIn(case['id'],identities);identities.add(case['id'])
            for key in ('request','build','input','expected'):
                identity=case[key]
                if identity is None:continue
                used.add(identity);descriptor=self.metadata[identity]
                self.assertEqual(descriptor['kind'],'result' if key=='expected' else key)
                if descriptor['base'] is not None:used.add(descriptor['base'])
            request=PayloadArchitectureRequest.from_dict(self.resolve(case['request']))
            build=PayloadArchitectureBuild.from_dict(self.resolve(case['build']))
            self.assertEqual(request.fingerprint,case['request']);self.assertEqual(build.fingerprint,case['build'])
        self.assertEqual(used,set(self.metadata))
    def test_independently_authored_transport_timelines(self):
        cases={x['id']:x for x in self.index['cases']}
        self.assertGreaterEqual(len(self.index['literal_assertions']),6)
        for item in self.index['literal_assertions']:
            trace=self.resolve(cases[item['case_id']]['expected'])
            if item['projection']=='receiver_values':actual=[f['receiver_values'][item['receiver']] for f in trace['channel_frames']]
            elif item['projection']=='delivery_times':actual=[f['sent'].get(item['channel'],{}).get('delivery_time') for f in trace['channel_frames']]
            else:self.fail('Unknown independent projection')
            self.assertEqual(canonical(actual),canonical(item['expected']),item['case_id'])
        self.assertEqual(self.index['claim_scope'],'source_prefix_execution_under_declared_contracts_only')
    def test_fresh_python_replay_preserves_full_trace_and_authority(self):
        cases={c['id']:c for c in self.index['cases']}
        for identity in ('literal/baseline','literal/custom_sum','literal/custom_pulse'):
            case=cases[identity];raw=self.resolve(case['input'])
            history={key:tuple(InputFrame(frame['time'],{name:SignalSample(**sample) for name,sample in frame['signals'].items()},
                {contact:{name:SignalSample(**sample) for name,sample in samples.items()} for contact,samples in frame['contacts'].items()}) for frame in frames) for key,frames in raw['histories'].items()}
            def option(value):return decode_binding(value) if isinstance(value,dict) else value
            actual=evaluate_payload_architecture(PayloadArchitectureBuild.from_dict(self.resolve(case['build'])),
                PayloadArchitectureRequest.from_dict(self.resolve(case['request'])),history,
                until=option(raw['until']),step=option(raw['step']),max_samples=raw['max_samples'],failed_channels=raw['failed_channels'])
            self.assertEqual(canonical(actual.to_dict()),canonical(self.resolve(case['expected'])))
    def test_delta_mutations_do_not_normalize_missing_or_boolean_paths(self):
        base={'a':[1,2],'b':False}
        self.assertEqual(strict_patch(base,[{'op':'set','path':['a',1],'value':3}]),{'a':[1,3],'b':False})
        self.assertEqual(base,{'a':[1,2],'b':False})
        for patch in ({'op':'set','path':[],'value':0},{'op':'set','path':['missing','x'],'value':0},
                      {'op':'set','path':['a',True],'value':0},{'op':'remove','path':['absent']},
                      {'op':'remove','path':['a',0]}):
            with self.assertRaises(ValueError):strict_patch(base,[patch])
    def test_native_resource_difference_is_explicit_and_does_not_claim_candidate_execution(self):
        profile=self.index['compatibility']
        self.assertEqual(profile['native_resources'],'biocompiler.source_transport.resources.v1')
        self.assertEqual(profile['max_work'],50000000);self.assertEqual(profile['max_output_nodes'],250000)
        self.assertEqual(profile['max_output_bytes'],33*1024*1024)
        for case in self.index['cases']:
            if case['expected']:
                result=self.resolve(case['expected'])
                self.assertEqual(result['policies']['claim_scope'],'sampled_abstract_execution_under_declared_contracts_no_physiological_prediction')
                self.assertEqual(result['request_fingerprint'],case['request']);self.assertEqual(result['build_fingerprint'],case['build'])
