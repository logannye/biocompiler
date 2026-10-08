"""Closed deferred context binding proofs over inert, fully framed transcripts.

These fixtures validate receipt logic only; they execute no native process.
"""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

from tools import check_pipeline_manager_install as gate
from tests.test_pipeline_manager_campaign import reframe


def fixture(root, *, foreign_source=False):
    channel, application = gate.declarations()
    directory = root/'frames'; directory.mkdir()
    receipt = {'_artifact_directory': str(directory), 'artifacts': {}, 'check': {'frames': []}}
    frames, sequence, event = [], 0, 0
    session = str(uuid4())
    def client(kind, **fields):
        nonlocal sequence
        value = {'protocol':channel['protocol'], 'profile':channel['profile'], 'session_id':session,
            'kind':kind, 'sequence':sequence, **fields}
        frames.append(value); sequence += 1
        return value['sequence']
    def server(kind, **fields):
        nonlocal event
        value = {'protocol':channel['protocol'], 'profile':channel['profile'], 'session_id':session,
            'kind':kind, 'event_id':event, 'usage':{key:0 for key in channel['usage_fields']}, **fields}
        frames.append(value); event += 1
        return value['event_id']
    def command(operation, arguments):
        return client('command', parent_invocation=None, operation=operation, arguments=arguments)
    def reply(seq, value=None, closed=False):
        server('reply', sequence=seq, request_sha256='0'*64, outcome={'status':'ok','value':value}, closed=closed)
    def invoke(seq, action, arguments, value):
        identity = server('invoke', invocation_id=event, parent_invocation=None, command_sequence=seq,
            command_sha256='0'*64, action=action, arguments=arguments)
        client('continue', invocation_id=identity, invocation_sha256='0'*64, outcome={'status':'return','value':value})
        return identity
    ref = lambda index: {'handle':'object/'+str(index)}
    seq = client('hello', declaration=channel, application=application, limits=None)
    reply(seq, {'declaration':channel,'application':application,'limits':channel['limits']})
    seq = command('initialize-empty', {'target':{},'dependencies':[], 'completion_profiles':[],
        'manager_limits':None,'target_object':ref(0)})
    reply(seq, {'kind':'empty','manager':True,'artifacts':[],'target':{'value':{},'binding':{}}})
    seq = command('register', {'contract':{'id':'lower'},'producer':ref(1),'validators':ref(2),'obligation_objects':[]})
    invoke(seq, 'bind-provider', {'provider_id':'provider/0','object':ref(1)}, None); reply(seq)
    seq = command('inspect-ordered', {})
    reply(seq, {'snapshot':{'passes':{'lower':{'producer':'provider/0'}}},'order':{},'providers':[]})
    run_args = {'pass_id':'lower','input_id':'input','output_id':'out','configuration':None}
    seq = command('run', run_args)
    document = {'input':{'schema_version':'intent.v1','nodes':[{'id':'n'}]},'output':None,'target':{},
        'configuration':{},'dependencies':{},'requirements':['r'],'source_links':[],'observation_map':{}}
    invoke(seq, 'hydrate-context', {'context_id':'context/0','document':deepcopy(document),'bindings':{'source_links':None}}, ref(3))
    invoke(seq, 'call-provider', {'provider_id':'provider/0','context':ref(3)}, ref(4))
    invoke(seq, 'attr', {'object':ref(4),'name':'source_links'}, ref(5))
    invoke(seq, 'tuple', {'object':ref(5)}, ref(5))
    invoke(seq, 'iter', {'object':ref(5)}, ref(6))
    for element in (20,21): invoke(seq, 'next', {'object':ref(6)}, {'exhausted':False,'object':ref(element)})
    invoke(seq, 'next', {'object':ref(6)}, {'exhausted':True,'object':None})
    for element in (20,21):
        invoke(seq, 'is-instance', {'object':ref(element),'type':'SourceLink'}, True)
        invoke(seq, 'attr', {'object':ref(element),'name':'pass_name'}, ref(30))
        invoke(seq, 'literal', {'kind':'json','value':'lower'}, ref(31))
        invoke(seq, 'compare', {'left':ref(30),'operator':'eq','right':ref(31)}, True)
    for element in (20,21):
        for field, value, number in (('requirement_id','r',40),('target_node_id','n',42),('source_node_id','n',44)):
            invoke(seq, 'attr', {'object':ref(element),'name':field}, ref(number))
            invoke(seq, 'literal', {'kind':'set','value':[value]}, ref(number+1))
            invoke(seq, 'contains', {'container':ref(number+1),'item':ref(number)}, True)
    if foreign_source:
        reply(seq)
        seq = command('run', {**run_args,'output_id':'later'})
    document['output'] = {'schema_version':'behavior.v1','nodes':[{'id':'n'}]}
    invoke(seq, 'hydrate-context', {'context_id':'context/1','document':deepcopy(document),
        'bindings':{'source_links':{'kind':'host','object':ref(5)}}}, ref(7))
    reply(seq); seq = client('close', parent_invocation=None); reply(seq, closed=True)
    row = receipt['check']
    row['frames'] = [{'direction':'client' if item['kind'] in channel['client_fields'] else 'server',
        'index':item.get('sequence',item.get('event_id')),'frame':gate.artifact(receipt,gate.frame(item))} for item in frames]
    reframe(receipt,row,lambda values:None)
    expected = deepcopy(document)
    expected['source_links'] = [{'requirement_id':'r','source_node_id':'n','target_node_id':'n','pass_name':'lower'} for _ in (20,21)]
    return receipt,row,expected


def checked(receipt,row,expected):
    details = {}; channel,application = gate.declarations()
    # Every mutant repairs SHA bindings, resource counters and frame inventory;
    # this mandatory framing pass precedes the semantic correspondence check.
    gate.validate_frames(row['frames'],gate.Artifacts(Path(receipt['_artifact_directory']),receipt['artifacts']),
        channel,application,details=details,provider_calls=False)
    hydration = next(item for item in details['invocations'].values()
        if item['action']=='hydrate-context' and item['arguments']['context_id']=='context/1')
    actual = gate.deferred_context_document(hydration,details)
    gate.equal(actual,expected,'Deferred callback read a context different from native authority')
    return details


class DeferredContextBindingsTests(unittest.TestCase):
    def test_complete_tuple_projection_preserves_duplicates_and_full_context(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt,row,expected = fixture(Path(directory))
            checked(receipt,row,expected)

    def test_no_binding_context_is_not_projected_or_mutated(self):
        for bindings in ({}, {'source_links':None}):
            document={'source_links':[],'input':{'unchanged':['value']}}
            hydration={'arguments':{'document':document,'bindings':bindings}}
            self.assertEqual(gate.deferred_context_document(hydration,{}),document)
            self.assertEqual(document,{'source_links':[],'input':{'unchanged':['value']}})

    def test_foreign_command_tuple_cannot_supply_current_hydration(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt,row,expected = fixture(Path(directory),foreign_source=True)
            with self.assertRaisesRegex(AssertionError,'attribute is missing'):
                checked(receipt,row,expected)

    def test_rehashed_producer_tuple_element_and_ambiguity_mutants_fail(self):
        def invokes(values,action):return [v for v in values if v['kind']=='invoke' and v['action']==action]
        def outcome(values,invocation):return next(v['outcome'] for v in values if v['kind']=='continue' and v['invocation_id']==invocation['invocation_id'])
        def wrong_provider(values):invokes(values,'call-provider')[0]['arguments']['provider_id']='provider/9'
        def wrong_result(values):invokes(values,'attr')[0]['arguments']['object']={'handle':'object/999'}
        def wrong_tuple(values):invokes(values,'hydrate-context')[-1]['arguments']['bindings']['source_links']['object']={'handle':'object/999'}
        def wrong_iterator(values):invokes(values,'next')[0]['arguments']['object']={'handle':'object/999'}
        def duplicate(values):outcome(values,invokes(values,'next')[1])['value']['object']={'handle':'object/20'}
        def reorder(values):
            first,second=invokes(values,'next')[:2]
            a,b=outcome(values,first)['value'],outcome(values,second)['value'];a['object'],b['object']=b['object'],a['object']
        def missing_exhaustion(values):outcome(values,invokes(values,'next')[2])['value']={'exhausted':False,'object':{'handle':'object/20'}}
        def altered_field(values):
            for v in invokes(values,'literal'):
                if v['arguments']=={'kind':'set','value':['r']}:v['arguments']['value']=['changed']
        def ambiguous(values):
            for v in invokes(values,'literal'):
                if v['arguments']=={'kind':'set','value':['r']}:v['arguments']['value']=['r','other']
        def false_type(values):outcome(values,invokes(values,'is-instance')[0])['value']=False
        def other_context(values):invokes(values,'hydrate-context')[-1]['arguments']['document']['observation_map']={'changed':'value'}
        for mutate,message in ((wrong_provider,'registered producer result'),(wrong_result,'registered producer result'),
            (wrong_tuple,'another source-link tuple'),(wrong_iterator,'materialization changed'),(duplicate,'type checks changed'),
            (reorder,'type checks changed'),(missing_exhaustion,'materialization changed'),(altered_field,'context different'),
            (ambiguous,'missing or ambiguous'),(false_type,'type checks changed'),(other_context,'context different')):
            with self.subTest(mutation=mutate.__name__),tempfile.TemporaryDirectory() as directory:
                receipt,row,expected=fixture(Path(directory));reframe(receipt,row,mutate)
                with self.assertRaisesRegex(AssertionError,message):checked(receipt,row,expected)

    def test_rehashed_numeric_boolean_results_are_not_native_success(self):
        for action in ('is-instance','compare','contains'):
            for invalid in (1,1.0):
                with self.subTest(action=action,value=invalid),tempfile.TemporaryDirectory() as directory:
                    receipt,row,expected=fixture(Path(directory))
                    def mutate(values):
                        invocation=next(v for v in values if v['kind']=='invoke' and v['action']==action)
                        continuation=next(v for v in values if v['kind']=='continue'
                            and v['invocation_id']==invocation['invocation_id'])
                        continuation['outcome']['value']=invalid
                    reframe(receipt,row,mutate)
                    message='type checks changed' if action=='is-instance' else 'scalar check did not return true'
                    with self.assertRaisesRegex(AssertionError,message):checked(receipt,row,expected)

    def test_rehashed_malformed_capability_references_are_not_native_handles(self):
        invalids=({'handle':1},{'handle':'foreign/5'},{'handle':'object/5','extra':1},
            {'handle':'object/05'},{'handle':'object/'},{'handle':'object/'+'1'*26})
        # These distinct roles cover each retained capability in the proof;
        # all occurrences are repaired together so equality alone cannot help.
        for identity in (3,4,5,6,20,30,31,40,41):
            for invalid in invalids:
                with self.subTest(identity=identity,value=invalid),tempfile.TemporaryDirectory() as directory:
                    receipt,row,expected=fixture(Path(directory))
                    def replace(value):
                        if value=={'handle':'object/'+str(identity)}:return deepcopy(invalid)
                        if type(value) is dict:return {key:replace(child) for key,child in value.items()}
                        if type(value) is list:return [replace(child) for child in value]
                        return value
                    reframe(receipt,row,lambda values:values.__setitem__(slice(None),replace(values)))
                    with self.assertRaisesRegex(AssertionError,'capability reference'):checked(receipt,row,expected)
