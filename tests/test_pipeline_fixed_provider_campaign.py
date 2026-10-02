"""Integrity controls for fixed native-provider replay; no native execution."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from tests.test_pipeline_manager_campaign import fake_frames, reframe, guard_with_routes
from tools import check_pipeline_manager_install as manager
from tools import check_pipeline_fixed_provider_install as fixed
from tools import capture_pipeline_fixed_provider_semantics as original
from tests import test_core_pipeline_provider_views as view_tests


class Script:
    """Fabricated framing for comparator controls; never native acceptance."""
    def __init__(self, receipt):
        from uuid import uuid4
        self.receipt, self.rows, self.bodies, self.live = receipt, [], {}, []
        self.sequence = self.event = self.input_bytes = self.output_bytes = self.nodes = self.commands = 0
        self.channel, self.application = manager.declarations()
        self.nonce = str(uuid4())
        sequence = self.client('hello', {'declaration': self.channel, 'application': self.application, 'limits': None})
        self.reply(sequence, {'declaration': self.channel, 'application': self.application, 'limits': self.channel['limits']})

    def client(self, kind, fields):
        value = {'protocol': self.channel['protocol'], 'profile': self.channel['profile'], 'session_id': self.nonce,
            'kind': kind, 'sequence': self.sequence, **fields}
        raw = manager.frame(value)
        self.bodies[self.sequence] = raw[9:]
        self.rows.append({'direction': 'client', 'index': self.sequence, 'frame': manager.artifact(self.receipt, raw)})
        self.input_bytes += len(raw); self.nodes += manager.json_nodes(value)
        if kind != 'continue': self.commands += 1
        self.sequence += 1
        return self.sequence-1

    def command(self, name, arguments):
        return self.client('command', {'operation': name, 'arguments': arguments,
            'parent_invocation': self.live[-1] if self.live else None})

    def server(self, kind, fields):
        value = {'protocol': self.channel['protocol'], 'profile': self.channel['profile'], 'session_id': self.nonce,
            'kind': kind, 'event_id': self.event, **fields, 'usage': {key: 0 for key in self.channel['usage_fields']}}
        self.nodes += manager.json_nodes(value)
        count = len(self.rows)+1
        value['usage'].update(input_bytes=self.input_bytes, output_bytes=self.output_bytes, frames=count,
            commands=self.commands, json_nodes=self.nodes, pending_invocations=len(self.live)+(kind=='invoke'),
            retained_bytes=10000+count, work_charged=1000000+count*100, work_remaining=10**12-1000000-count*100)
        while True:
            raw = manager.frame(value)
            expected = self.output_bytes+len(raw)
            if value['usage']['output_bytes'] == expected: break
            value['usage']['output_bytes'] = expected
        self.rows.append({'direction': 'server', 'index': self.event, 'frame': manager.artifact(self.receipt, raw)})
        self.output_bytes += len(raw); self.event += 1
        return value['event_id'], raw[9:]

    def reply(self, sequence, value, closed=False):
        return self.server('reply', {'sequence': sequence, 'request_sha256': manager.sha(self.bodies[sequence]),
            'outcome': {'status': 'ok', 'value': value}, 'closed': closed})

    def begin(self, sequence, action, arguments):
        identity, raw = self.server('invoke', {'invocation_id': self.event, 'command_sequence': sequence,
            'command_sha256': manager.sha(self.bodies[sequence]), 'parent_invocation': self.live[-1] if self.live else None,
            'action': action, 'arguments': arguments})
        self.live.append(identity)
        return identity, raw

    def end(self, invocation, value):
        identity, raw = invocation
        assert self.live.pop() == identity
        self.client('continue', {'invocation_id': identity, 'invocation_sha256': manager.sha(raw),
            'outcome': {'status': 'return', 'value': value}})

    def invoke(self, sequence, action, arguments, value):
        self.end(self.begin(sequence, action, arguments), value)

    def close(self):
        self.reply(self.client('close', {'parent_invocation': None}), None, True)


def fixture(receipt, expected, retained, helper):
    """Translate actual original objects to a fabricated, explicitly test-only peer."""
    from biocompiler.pipeline_callback_objects import CallbackObjects
    from biocompiler.core_pipeline_manager import _ordered
    from biocompiler.core_pipeline_provider_views import origin_reference
    objects = CallbackObjects()
    source = retained['request']; config = retained['config']
    refs = {name: objects.retain(value) for name, value in (('target', source.target), ('config', config), ('request', source))}
    envelopes = list(helper.envelopes(retained, objects))
    roots = {'target': source.target, 'config': config, 'request': source, **dict(original.source_origins(source)),
        'constant:synthetic_capabilities': origin_reference(source, 'syntheticCapabilities', [])}
    evidence = {'calls': [], 'inspection': None, 'objects': {}, 'providers': {}, 'arguments': {}}
    for handle, value in objects._objects.items():
        names = [name for name, root in roots.items() if value is root]
        if names: evidence['objects'][handle] = {'kind': 'source', 'names': names}
    roles = {}
    passes = {}
    wrappers = {}
    for i, event in enumerate(expected['events']):
        pid = event['pass_id']; producer, validator = 'provider/'+str(i*2), 'provider/'+str(i*2+1)
        check = event['contract']['checks'][0]['id']
        for token, slot in ((producer, 'producer'), (validator, check)):
            ref = objects.retain(object())
            evidence['providers'][token] = {'object': ref['handle'], 'pass_id': pid, 'slot': slot}
            roles[token] = pid+('.producer' if slot == 'producer' else '.validator')
        contract = deepcopy(event['contract']); contract['version'] = contract['version'].removesuffix('.fixed_view_witness')
        passes[pid] = {'contract': contract, 'producer': producer, 'validators': {check: validator}}
        wrappers[pid] = objects.retain(object())
        evidence['objects'][wrappers[pid]['handle']] = {'kind': 'wrapper', 'pass_id': pid}
    snapshot = {name: {} for name in manager.STATE_MAPS}
    snapshot.update(target=source.target.to_dict(), passes=passes)
    order = {name: list(snapshot[name]) for name in manager.STATE_MAPS}
    order.update(combined_provider_history=[], validators={name: {key: list(entry['validators']) for key, entry in snapshot[name].items()}
        for name in manager.REGISTRATION_MAPS})
    inspection = {'snapshot': snapshot, 'order': order,
        'providers': [{'provider_id': token, 'object': {'handle': item['object']}} for token, item in evidence['providers'].items()]}
    script = Script(receipt)
    sequence = script.command('initialize-components', {**expected['authority'], 'request_tree': _ordered(source.to_dict()), 'manager_limits': None,
        **{name+'_object': value for name, value in refs.items()}})
    from tests.pipeline_fixed_initializer_fixture import emit
    hooks = emit(script, sequence,
        {'value': source.target.to_dict(), 'binding': {'kind': 'host', 'object': refs['target']}},
        {key: entry['contract'] for key, entry in passes.items()},
        [(token, roles[token], {'handle': item['object']}) for token, item in evidence['providers'].items()], count=3)
    evidence['arguments'].update(hooks['arguments'])
    script.reply(sequence, {'kind': 'components', 'manager': True,
        'artifacts': ['candidate', 'pipeline_result', 'selection_result', 'assembly', 'link_result', 'behavior_result'],
        'target': {'value': source.target.to_dict(), 'binding': {'kind': 'host', 'object': refs['target']}}})
    sequence = script.command('inspect-ordered', {}); evidence['inspection'] = sequence
    script.reply(sequence, inspection)
    anchored = set()
    next_binding = 0
    def binding(value):
        nonlocal next_binding
        token='value/'+str(next_binding);next_binding+=1
        return {'kind':'native','identity':token,'tree':_ordered(value)}
    introduced = {item['id']: handle for handle, item in hooks['host_documents'].items()}
    def record_bindings(value, index):
        return {'record_id':'record/'+str(index), **{name:binding(value[name]) for name in
            ('payload','dependencies','requirements','checks','provenance','obligations')},
            'obligation_objects':[{'kind': 'host', 'object': {'handle': introduced[item['id']]}}
                if item['id'] in introduced else binding(item) for item in value['obligations']]}
    # Resolve each source-root object through a legitimate origin action, with
    # physical identity (including repeated BOOLEAN paths) rather than equality.
    origin_specs = [(root, []) for root in ('BOOLEAN', 'LEVEL', 'DURATION', 'defaultLifecycle', 'syntheticCapabilities')]
    for collection, name, values in (('domain', 'inputs', source.domain.inputs), ('contract', 'requirements', source.contract.requirements)):
        for i in range(len(values)):
            path = [collection, name, i, 'observable']
            origin_specs.extend([('request', path), ('request', path+['dtype'])])
    origin_specs.extend(('request', ['behavior', 'nodes', i, 'source']) for i, node in enumerate(source.behavior.nodes) if node.source is not None)
    previous_payload = None
    for index, event in enumerate(expected['events']):
        pid = event['pass_id']; registration = passes[pid]
        mapping = objects.retain(object())
        evidence['arguments'][mapping['handle']] = {'kind': 'validators', 'items': list(map(list, registration['validators'].items()))}
        obligations = []
        for offset, value in enumerate(event['contract']['introduces']):
            # inspection_state creates fresh typed contract/obligation views.
            # Their equal declarations do not reuse initializer host objects.
            from biocompiler.core_pipeline_manager import _obligation
            ref = objects.retain(_obligation(value))
            obligations.append(ref)
            introduced[value['id']] = ref['handle']
            evidence['arguments'][ref['handle']] = {'kind': 'contract_obligation', 'pass_id': pid, 'index': offset, 'value': value}
        sequence = script.command('register', {'contract': event['contract'], 'producer': wrappers[pid],
            'validators': mapping, 'obligation_objects': obligations})
        for token in registration['validators'].values():
            script.invoke(sequence, 'provider-reference', {'object': {'handle': evidence['providers'][token]['object']}},
                {'kind': 'native', 'provider_id': token})
        wrapper_token = 'provider/'+str(6+index)
        script.invoke(sequence, 'bind-provider', {'provider_id': wrapper_token, 'object': wrappers[pid]}, None)
        script.reply(sequence, None)
        configuration = config.to_dict() if pid == 'behavior_to_synthetic' else None
        config_ref = objects.retain(configuration) if configuration is not None else None
        if config_ref is not None:
            evidence['arguments'][config_ref['handle']] = {'kind': 'configuration', 'value': original.plain(configuration)}
        sequence = script.command('run', {key: event[key] for key in ('pass_id', 'input_id', 'output_id')} | {'configuration': config_ref})
        context_ref = objects.retain(object()); context_id = 'context/'+str(index)
        document={'input':expected['authority']['request']['build_request'] if index==0 else expected['events'][index-1]['record']['payload'],
            'output':None,'target':source.target.to_dict(),'configuration':{} if configuration is None else configuration,
            'dependencies':snapshot['dependencies'],'requirements':event['record']['requirements'],'source_links':[],'observation_map':{}}
        context_bindings={name:binding(document[name]) for name in ('input','configuration','dependencies','requirements','observation_map')}
        if previous_payload is not None: context_bindings['input'] = previous_payload
        context_bindings.update(target={'kind':'host','object':refs['target']},output=None,source_links=None)
        script.invoke(sequence,'hydrate-context',{'context_id':context_id,'document':document,'bindings':context_bindings},context_ref)
        wrapper_call = script.begin(sequence, 'call-provider', {'provider_id': wrapper_token, 'context': context_ref})
        first_ref = None
        for ordinal in range(2):
            pass_id, proposal, envelope = envelopes[index*2+ordinal]
            assert pass_id == pid
            start = len(script.rows)
            direct = script.command('call-native-provider', {'provider_id': registration['producer'], 'context_id': context_id})
            # All host origins are linked to complete real producer replies.
            for root, path in origin_specs:
                value = origin_reference(source, root, path)
                ref = objects.retain(value)
                if ref['handle'] in evidence['objects'] and ref['handle'] not in anchored:
                    script.invoke(direct, 'origin-reference', {'root': root, 'path': path}, ref)
                    anchored.add(ref['handle'])
            script.reply(direct, envelope)
            if ordinal == 0: first_ref = objects.retain(proposal)
            evidence['calls'].append({'pass_id': pid, 'ordinal': ordinal, 'before_frames': start,
                'after_frames': len(script.rows), 'sequence': direct, 'returned_object': first_ref['handle'] if ordinal == 0 else None})
        script.end(wrapper_call, first_ref)
        payload_reference=objects.retain(envelopes[index*2][1].output.to_dict())
        script.invoke(sequence,'ordered-json',{'object':payload_reference},_ordered(event['record']['payload']))
        previous_payload={'kind':'host','object':payload_reference}
        stored_bindings=record_bindings(event['record'],index);stored_bindings['payload']=previous_payload
        script.reply(sequence, {'value':event['record'],'bindings':stored_bindings})
    script.close()
    return {'frames': script.rows, 'evidence_value': evidence, 'actual_value': expected}


def complete_receipt(directory, corpus, helper):
    from uuid import uuid4
    directory = Path(directory); path = directory/fixed.ARTIFACT_DIRECTORY; path.mkdir(parents=True)
    receipt = {'_artifact_directory':str(path),'artifacts':{},'checks':[], 'completed_checks':3,
        'native_inputs':{'sha256':{'biocompiler-core':'a'*64,'biocompiler-verify':'b'*64}},
        'executables':{'core':'/native/biocompiler-core','verify':'/native/biocompiler-verify'}}
    put=lambda value: manager.artifact(receipt, manager.canonical(value))
    fixed.capture_counterpart(receipt, original.capture(), 'fixed-provider-original', corpus.value)
    channel,application=manager.declarations()
    stdout={'protocol':'biocompiler.core.v1','request_id':None,'operation':None,'status':'error','result':None,
        'diagnostics':[{'code':'unexpected_arguments','message':'Expected standard JSON input or the exact inherited artifact descriptor arguments.','path':None}],
        'core':{**manager.fixed.CORE,'executable':'verify'}}
    receipt['verify_rejection']={'argv':[receipt['executables']['verify'],manager.ARGUMENT], 'executable_sha256':'b'*64,'returncode':2,
        'request':manager.artifact(receipt,manager.frame(manager.verify_request(channel,application,str(uuid4())))),
        'stdout':manager.artifact(receipt,manager.canonical(stdout)+b'\n'),'stderr':put({'hex':''})}
    guard=sorted([['biocompiler.core_pipeline_manager','CorePassManager.'+name] for name in
        ('_fixed','from_components','inspection_state','_call_native','_native_return')]+[
        ['biocompiler.core_pipeline_callback_session','CorePipelineCallbackSession.__init__'],
        ['biocompiler.core_pipeline_callback_session','CorePipelineCallbackSession.call'],
        ['biocompiler.pipeline_callback_objects','CallbackObjects.execute']])
    for index,expected in enumerate(corpus.cases):
        row=fixture(receipt,expected,helper.proposals[expected['id']],helper)
        row.update(id=expected['id'],actual=put(row.pop('actual_value')),evidence=put(row.pop('evidence_value')),
            pid=500+index,returncode=0,closed=True,invalidated=False,executable_sha256='a'*64,
            stderr=put({'hex':''}),guard=put(guard_with_routes(receipt,guard,row['frames'])),after_close=put({'type':'CoreProtocolError',
            'message':'Callback session is closed; it cannot reconnect','traffic_unchanged':True,'pid_unchanged':True}))
        receipt['checks'].append(row)
    return receipt


def matrix_fixture(directory,corpus,helper):
    root=Path(directory);native_root=root/'native';runtime_root=root/'realization';native_root.mkdir();runtime_root.mkdir()
    revision,source_revision,run_id='a'*40,'b'*40,'fixed-provider-unit-fixture'
    for target,(system,machine) in manager.r.PLATFORMS.items():
        native_path=native_root/target;native_path.mkdir();pins={}
        for role in ('core','verify'):
            path=native_path/('biocompiler-'+role);path.write_bytes(('NONEXECUTABLE UNIT FIXTURE '+target+' '+role).encode())
            pins[path.name]=manager.sha(path.read_bytes())
        (native_path/'binaries.json').write_bytes(manager.canonical({'revision':revision,'system':system,'machine':machine,'sha256':pins})+b'\n')
        native=manager.r.verify_binaries(native_path,revision,target)
        for python in manager.r.PYTHONS:
            slot=runtime_root/('realization-'+target+'-py'+python)
            receipt=complete_receipt(slot,corpus,helper)
            receipt.update(schema_version=fixed.SCHEMA,status='success',scope=fixed.SCOPE,revision=revision,source_revision=source_revision,
                run_id=run_id,python_version=python+'.9',system=system,machine=machine,native_platform=target,
                artifact_directory=fixed.ARTIFACT_DIRECTORY,native_inputs=native,python_sources=fixed.product_sources(corpus),
                campaign_sources=manager.r.source_pins(fixed.SOURCES),package_path='/installed/site-packages/biocompiler/__init__.py',**corpus.metadata())
            receipt['executables']={role:str(native_path/('biocompiler-'+role)) for role in ('core','verify')}
            receipt['verify_rejection'].update(argv=[receipt['executables']['verify'],manager.ARGUMENT],executable_sha256=pins['biocompiler-verify'])
            for row in receipt['checks']:row['executable_sha256']=pins['biocompiler-core']
            del receipt['_artifact_directory']
            (slot/fixed.RECEIPT_FILE).write_bytes(manager.canonical(receipt)+b'\n')
            (slot/'native-inputs.json').write_bytes(manager.canonical({**native,'run_id':run_id,'source_revision':source_revision,'python_version':python+'.9'})+b'\n')
    return runtime_root,native_root,dict(revision=revision,source_revision=source_revision,run_id=run_id)


class PipelineFixedProviderCampaignTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import json
        cls.frozen = json.loads(original.OUTPUT.read_bytes())
        view_tests.StructuralProviderViewsTests.setUpClass()
        cls.helper = view_tests.StructuralProviderViewsTests()
        from types import SimpleNamespace
        cls.corpus = SimpleNamespace(value=cls.frozen,cases=cls.frozen['cases'],metadata=lambda:{'coverage':fixed.COVERAGE,'pending':cls.frozen['pending']})

    def prepared(self, directory, index=0):
        receipt = {'_artifact_directory': directory, 'artifacts': {}}
        expected = self.frozen['cases'][index]
        row = fixture(receipt, expected, self.helper.proposals[expected['id']], self.helper)
        receipt['checks'] = [row]
        return receipt, row, expected

    def details(self, receipt, row, directory):
        details = {}
        channel, application = manager.declarations()
        manager.validate_frames(row['frames'], manager.Artifacts(Path(directory), receipt['artifacts']), channel, application,
            details=details, initializer='initialize-components')
        return details

    def validate(self, receipt, row, expected, directory):
        return fixed.validate_case(expected, row['actual_value'], row['evidence_value'], self.details(receipt,row,directory), original)

    @staticmethod
    def outer_registration_arguments(receipt, row, *, obligations=False):
        artifacts=manager.Artifacts(Path(receipt['_artifact_directory']),receipt['artifacts'])
        for frame in row['frames']:
            value=manager.frame_body(artifacts.raw(frame['frame']))
            if (value.get('operation')=='register' and value['parent_invocation'] is None
                    and (not obligations or value['arguments']['obligation_objects'])):
                return value['arguments']
        raise AssertionError('Missing actual wrapper registration in test fixture')

    def test_all_original_return_graphs_reconstruct_from_complete_native_reply_shapes(self):
        for index in range(3):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as directory:
                receipt,row,expected = self.prepared(directory,index)
                self.assertEqual(self.validate(receipt,row,expected,directory)['returns'], 6)


    def test_repaired_reply_value_and_order_changes_fail_semantic_observation(self):
        from biocompiler.core_pipeline_manager import _ordered
        for change in ('value', 'order', 'selected-origin'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                receipt,row,expected = self.prepared(directory,1 if change=='selected-origin' else 0)
                def mutate(frames):
                    replies = [value for value in frames if value['kind']=='reply'
                        and value['outcome'].get('value',{}).__class__ is dict
                        and value['outcome']['value'].get('kind')=='proposal']
                    envelope = replies[2 if change in ('selected-origin','order') else 0]['outcome']['value']
                    if change=='value':
                        envelope['value']['observation_map']['mutation'] = True
                        envelope['view']['tree'] = _ordered(envelope['value'])
                    elif change=='order':
                        tree = envelope['view']['tree']
                        observation = next(item[1] for item in tree[1] if item[0]=='observation_map')
                        # Lower observation contains multiple keys; preserve values.
                        self.assertGreater(len(observation[1]),1)
                        observation[1].reverse()
                    else:
                        init = next(value for value in frames if value['kind']=='command' and value['operation']=='initialize-components')
                        envelope['view']['bindings']['generator_config'] = {'kind':'host','object':init['arguments']['config_object']}
                reframe(receipt,row,mutate)
                self.details(receipt,row,directory)  # repaired framing must pass first
                with self.assertRaisesRegex(AssertionError,'typed fields or physical aliases'):
                    self.validate(receipt,row,expected,directory)

    def test_repaired_native_record_and_authority_changes_fail(self):
        from biocompiler.core_pipeline_manager import _ordered
        for change,message in (('record','accepted record'),('request-order','request insertion order'),
                ('provider','closure or live context'),('context','closure or live context')):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                receipt,row,expected = self.prepared(directory)
                def mutate(frames):
                    if change=='record':
                        seq = next(value['sequence'] for value in frames if value['kind']=='command' and value['operation']=='run')
                        reply = next(value for value in frames if value['kind']=='reply' and value['sequence']==seq)
                        reply['outcome']['value']['value']['id'] = 'forged'
                    elif change=='request-order':
                        init = next(value for value in frames if value['kind']=='command' and value['operation']=='initialize-components')
                        init['arguments']['request_tree'][1].reverse()
                    else:
                        call = next(value for value in frames if value['kind']=='command' and value['operation']=='call-native-provider')
                        call['arguments']['provider_id' if change=='provider' else 'context_id'] = 'provider/2' if change=='provider' else 'context/1'
                reframe(receipt,row,mutate)
                self.details(receipt,row,directory)
                with self.assertRaisesRegex(AssertionError,message):
                    self.validate(receipt,row,expected,directory)

    def test_repaired_origin_action_and_wrapper_result_cannot_detach(self):
        for change,message in (('origin','actual source object'),('wrapper','first actual native proposal')):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                receipt,row,expected = self.prepared(directory)
                def mutate(frames):
                    invocation = next(value for value in frames if value['kind']=='invoke' and value['action']==
                        ('origin-reference' if change=='origin' else 'call-provider'))
                    if change=='origin':
                        invocation['arguments'] = {'root':'DURATION','path':[]}
                    else:
                        continuation = next(value for value in frames if value['kind']=='continue' and value['invocation_id']==invocation['invocation_id'])
                        continuation['outcome']['value'] = {'handle':'object/999999'}
                reframe(receipt,row,mutate)
                self.details(receipt,row,directory)
                with self.assertRaisesRegex(AssertionError,message):
                    self.validate(receipt,row,expected,directory)

    def test_observation_intervals_provider_bijection_and_obligation_slots_are_exact(self):
        for change,message in (('interval','exact reply interval'),('providers','physically distinct'),
                ('obligation','inspected obligation slot'),('validator','retained validator objects'),('extra','Unclaimed')):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                receipt,row,expected = self.prepared(directory)
                evidence = row['evidence_value']
                if change=='interval':
                    left,right=evidence['calls'][:2]
                    for key in ('sequence','before_frames','after_frames'):
                        left[key],right[key] = right[key],left[key]
                elif change=='providers':
                    keys=list(evidence['providers']); evidence['providers'][keys[1]]['object']=evidence['providers'][keys[0]]['object']
                elif change=='obligation':
                    args = self.outer_registration_arguments(receipt, row, obligations=True)
                    evidence['arguments'][args['obligation_objects'][0]['handle']]['index']=1
                elif change=='validator':
                    args = self.outer_registration_arguments(receipt, row)
                    evidence['arguments'][args['validators']['handle']]['items'][0][1]='provider/999'
                else:
                    evidence['arguments']['object/999999']={'kind':'configuration','value':None}
                with self.assertRaisesRegex(AssertionError,message):
                    self.validate(receipt,row,expected,directory)



    def test_repaired_complete_view_binding_and_lifetime_mutants_reject(self):
        for change,message in (('context-input','binding projection'),('record-payload','binding projection'),
                ('context-id','contexts reused'),('context-object','contexts reused'),('record-id','records reused'),
                ('record-fields','record binding fields'),('context-fields','context binding fields'),('shared-view','lifetime identity'),
                ('host-payload','Host view binding projection'),('future-host','preceding actual source')):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as directory:
                receipt,row,expected=self.prepared(directory)
                def mutate(frames):
                    contexts=[value for value in frames if value['kind']=='invoke' and value['action']=='hydrate-context']
                    if change=='context-input':
                        contexts[0]['arguments']['bindings']['input']['tree']=['scalar',False]
                    elif change=='context-fields':
                        del contexts[0]['arguments']['bindings']['input']
                    elif change=='context-id':
                        for value in contexts:value['arguments']['context_id']='context/999'
                        for value in frames:
                            if value['kind']=='command' and value['operation']=='call-native-provider':value['arguments']['context_id']='context/999'
                    elif change=='context-object':
                        first=next(value['outcome']['value'] for value in frames if value['kind']=='continue' and value['invocation_id']==contexts[0]['invocation_id'])
                        for context in contexts[1:]:
                            owner=context['command_sequence']
                            next(value for value in frames if value['kind']=='continue' and value['invocation_id']==context['invocation_id'])['outcome']['value']=first
                            next(value for value in frames if value['kind']=='invoke' and value['command_sequence']==owner and value['action']=='call-provider')['arguments']['context']=first
                    elif change=='host-payload':
                        owners={value['sequence'] for value in frames if value.get('operation')=='run'}
                        invocation=next(value for value in frames if value['kind']=='invoke' and value['action']=='ordered-json'
                            and value['command_sequence'] in owners)
                        next(value for value in frames if value['kind']=='continue' and value['invocation_id']==invocation['invocation_id'])['outcome']['value']=['scalar',False]
                    elif change=='future-host':
                        owners={value['sequence'] for value in frames if value.get('operation')=='run'}
                        invocations=[value for value in frames if value['kind']=='invoke' and value['action']=='ordered-json'
                            and value['command_sequence'] in owners]
                        contexts[1]['arguments']['bindings']['input']={'kind':'host','object':invocations[1]['arguments']['object']}
                    elif change=='shared-view':
                        contexts[0]['arguments']['bindings']['configuration']['identity']=contexts[0]['arguments']['bindings']['input']['identity']
                    else:
                        sequences={value['sequence'] for value in frames if value['kind']=='command' and value['operation']=='run'}
                        records=[value['outcome']['value'] for value in frames if value['kind']=='reply' and value['sequence'] in sequences]
                        if change=='record-payload':records[0]['bindings']['payload']={'kind':'native','identity':'value/999999','tree':['scalar',False]}
                        elif change=='record-fields':del records[0]['bindings']['payload']
                        else:records[1]['bindings']['record_id']=records[0]['bindings']['record_id']
                reframe(receipt,row,mutate)
                self.details(receipt,row,directory)
                with self.assertRaisesRegex(AssertionError,message):self.validate(receipt,row,expected,directory)

    def test_complete_artifact_census_verify_role_and_lifetime_are_mandatory(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt=complete_receipt(directory,self.corpus,self.helper)
            def validate():
                return fixed.validate_checks(receipt,self.corpus,manager.Artifacts(Path(receipt['_artifact_directory']),receipt['artifacts']))
            self.assertEqual(len(validate()),3)
            receipt['checks'][0]['closed']=False
            with self.assertRaisesRegex(AssertionError,'lifecycle'):validate()
            receipt['checks'][0]['closed']=True
            receipt['verify_rejection']['argv'][-1]='--pipeline-session-v1'
            with self.assertRaisesRegex(AssertionError,'Actual Verify'):validate()
            receipt['verify_rejection']['argv'][-1]=manager.ARGUMENT
            receipt['checks'][1],receipt['checks'][0]=receipt['checks'][0],receipt['checks'][1]
            with self.assertRaisesRegex(AssertionError,'reordered'):validate()
            receipt['checks'][1],receipt['checks'][0]=receipt['checks'][0],receipt['checks'][1]
            identity=manager.artifact(receipt,b'unused complete bytes')
            with self.assertRaisesRegex(AssertionError,'Unreferenced'):validate()
            del receipt['artifacts'][identity]
            (Path(receipt['_artifact_directory'])/(identity+'.bin')).unlink()
            identity=receipt['checks'][0]['frames'][0]['frame']
            path=Path(receipt['_artifact_directory'])/(identity+'.bin')
            path.write_bytes(path.read_bytes()+b' ')
            with self.assertRaisesRegex(AssertionError,'declared identity'):validate()

    def test_four_runtime_comparison_rehashes_full_evidence_and_source_authority(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory,patch.object(fixed,'Corpus',return_value=self.corpus):
            root,native,authority=matrix_fixture(directory,self.corpus,self.helper)
            result=fixed.compare(root,native,**authority)
            self.assertEqual(len(result['receipts']),4)
            slot=next(root.iterdir());path=slot/fixed.RECEIPT_FILE
            baseline=path.read_bytes();receipt=manager.r.decode(baseline)
            for key,value in (('run_id','old'),('source_revision','c'*40),('scope','full migration'),
                    ('python_sources',{}),('campaign_sources',{}),('pending',[]),('package_path',str(manager.ROOT/'src/biocompiler/__init__.py'))):
                changed=deepcopy(receipt);changed[key]=value;path.write_bytes(manager.canonical(changed)+b'\n')
                with self.subTest(key=key),self.assertRaises(AssertionError):fixed.compare(root,native,**authority)
            path.write_bytes(baseline)
            binary=next(native.glob('*/biocompiler-core'));binary.write_bytes(binary.read_bytes()+b'changed')
            with self.assertRaises((AssertionError,ValueError)):fixed.compare(root,native,**authority)

    def test_original_loading_restores_import_path_and_rejects_source_tree_runtime(self):
        import sys
        from unittest.mock import patch
        before=list(sys.path);loaded=fixed.load_oracle(installed=False)
        self.assertEqual(sys.path,before)
        self.assertEqual(loaded.CASES,original.CASES)
        import biocompiler.core_pipeline_provider_views as views
        with patch.object(views,'__file__',str(manager.ROOT/'src/biocompiler/core_pipeline_provider_views.py')):
            with self.assertRaisesRegex(AssertionError,'Source-tree'):fixed.load_oracle()
        self.assertEqual(sys.path,before)

    def test_guard_requires_the_exact_closed_initializer_and_transport(self):
        directory=self.enterContext(tempfile.TemporaryDirectory())
        artifacts=manager.Artifacts(Path(directory),{})
        base = [['biocompiler.core_pipeline_callback_session','CorePipelineCallbackSession.__init__'],
            ['biocompiler.core_pipeline_callback_session','CorePipelineCallbackSession.call'],
            ['biocompiler.pipeline_callback_objects','CallbackObjects.execute']]
        for initializer in ('initialize-empty','initialize-synthetic','initialize-components'):
            names = ['CorePassManager.__init__'] if initializer=='initialize-empty' else ['CorePassManager._fixed',
                'CorePassManager.from_'+initializer.removeprefix('initialize-')]
            entries = sorted(base+[['biocompiler.core_pipeline_manager',name] for name in names])
            manager.check_guard(entries,initializer=initializer,frames=[],artifacts=artifacts)
            for missing in entries:
                with self.assertRaisesRegex(AssertionError,'Missing actual native'):
                    manager.check_guard([item for item in entries if item is not missing],initializer=initializer,
                        frames=[],artifacts=artifacts)
        with self.assertRaisesRegex(AssertionError,'Unknown closed manager guard initializer'):
            manager.check_guard([],initializer='other')

    def test_frame_validator_accepts_only_one_explicit_closed_initializer(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = {'_artifact_directory': directory, 'artifacts': {}}
            row = {'frames': fake_frames(receipt)}
            receipt['checks'] = [row]
            channel, application = manager.declarations()
            def verify(initializer):
                return manager.validate_frames(row['frames'], manager.Artifacts(Path(directory), receipt['artifacts']),
                    channel, application, initializer=initializer)
            verify('initialize-empty')
            for operation in ('initialize-synthetic', 'initialize-components'):
                def mutate(values):
                    command = next(value for value in values if value['kind']=='command' and value['operation'].startswith('initialize-'))
                    command['operation'] = operation
                    command['arguments'] = {key: None for key in application['operations'][operation]['fields']}
                reframe(receipt, row, mutate)
                verify(operation)
                with self.assertRaisesRegex(AssertionError, 'declared initializer'):
                    verify('initialize-empty')
            for invalid in ('initialize-arbitrary', '', None, 1):
                with self.assertRaisesRegex(AssertionError, 'Unknown closed manager initializer'):
                    verify(invalid)


if __name__ == '__main__':
    unittest.main()
