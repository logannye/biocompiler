"""Original continuation driver controls; no native execution or fake acceptance."""
from contextlib import ExitStack, contextmanager
import sys
import unittest
from unittest.mock import patch

from tools import check_pipeline_fixed_continuation_install as campaign
from tools import capture_pipeline_fixed_build_semantics as build


class OriginalCadence:
    """Observe real original operations after each real upstream return."""
    def __init__(self, corpus):
        self.corpus, self.context = corpus, None
        self.managers, self.rows, self.case_rows = [], [], {}
        self.depth = {}
        self.offsets = {}
        self.authorities = []
        self.original_synthetic = build.synthetic.run_synthetic_pipeline

    @contextmanager
    def in_context(self, name):
        previous, self.context = self.context, name
        try:
            yield
        finally:
            self.context = previous

    def profile(self, frame, event, value):
        if event != 'return' or frame.f_code is not self.original_synthetic.__code__:
            return
        index = self.offsets.get(self.context, 0)
        expected = self.corpus.by_context[self.context][index]
        self.offsets[self.context] = index+1
        self.managers.append((value.manager, expected['id']))
        self.case_rows[expected['id']] = []
        source = frame.f_locals
        authority = {'request': source['request'].to_dict(), 'history': [item.to_dict() for item in source['frames']],
            'until': source['until'], 'config': source['requested_config'].to_dict()}
        # The boundary's original None argument is distinct from its defaulted
        # local configuration; take that authored argument from its caller.
        authority['config'] = frame.f_back.f_locals['config']
        if authority['config'] is not None:
            authority['config'] = authority['config'].to_dict()
        self.authorities.append((expected['id'], authority))

    @contextmanager
    def installed(self):
        previous = sys.getprofile()
        def combined(frame, event, value):
            self.profile(frame, event, value)
            if previous is not None:
                previous(frame, event, value)
        with ExitStack() as stack:
            for name in ('set_dependency', 'register_completion_profile', 'register', 'run', 'result', 'get'):
                original = getattr(build.pipeline.PassManager, name)
                def wrapper(instance, *args, _original=original, _name=name, **kwargs):
                    matches = [identity for value, identity in self.managers if value is instance]
                    if not matches or self.depth.get(id(instance), 0):
                        return _original(instance, *args, **kwargs)
                    assert len(matches) == 1
                    self.depth[id(instance)] = 1
                    row = {'api': 'PassManager.'+_name, 'context': self.context}
                    try:
                        result = _original(instance, *args, **kwargs)
                    except Exception as error:
                        row.update(outcome='raised', error={'module': type(error).__module__, 'type': type(error).__name__, 'message': str(error)})
                        raise
                    else:
                        row['outcome'] = 'returned'
                        return result
                    finally:
                        self.depth[id(instance)] = 0
                        self.rows.append(row)
                        self.case_rows[matches[0]].append(row)
                stack.enter_context(patch.object(build.pipeline.PassManager, name, wrapper))
            sys.setprofile(combined)
            try:
                yield
            finally:
                intact = sys.getprofile() is combined
                sys.setprofile(previous)
                assert intact


class PipelineFixedContinuationCampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = campaign.Corpus()

    def test_complete_unchanged_census_includes_fixture_manager_consumers(self):
        self.assertEqual(len(self.corpus.contexts), 17)
        self.assertEqual(len(self.corpus.cases), 39)
        self.assertEqual((len(self.corpus.prefix), len(self.corpus.suffix)), (312, 254))
        self.assertEqual(len(self.corpus.pending['excluded']), 10)
        self.assertEqual(len(self.corpus.pending['other_fixed_boundaries']), 97)
        for method in ('test_checked_component_scope_preserves_upstream_evidence_and_sources',
                'test_component_scope_cannot_complete_molecular_payload'):
            self.assertIn('tests/test_component_pipeline.py::ComponentPipelineTests.'+method, self.corpus.contexts)

    def test_unchanged_original_bodies_produce_every_566_operation_in_original_order(self):
        observer = OriginalCadence(self.corpus)
        with build.portable_sources(), observer.installed():
            result = campaign.run_original_bodies(context=observer.in_context)
        self.assertEqual(result['methods'], 13)
        self.assertEqual(len(observer.managers), 39)
        self.assertEqual(len(observer.rows), 566)
        self.assertEqual(list(observer.case_rows), [case['id'] for case in self.corpus.cases])
        for case in self.corpus.cases:
            expected = self.corpus.fixed.continuations[case['id']]['events']
            observed = observer.case_rows[case['id']]
            self.assertEqual(observed, [{key: event[key] for key in ('api', 'context', 'outcome', 'error') if key in event}
                for event in expected], case['id'])
        for identity, actual in observer.authorities:
            case = self.corpus.fixed.by_id[identity]
            self.assertEqual(actual, self.corpus.fixed.document('fixed', case['authority']), identity)

    def test_body_loader_restores_import_path_and_uses_original_source_files(self):
        previous = list(sys.path)
        modules = campaign.load_body_modules()
        self.assertEqual(sys.path, previous)
        for path, (name, methods) in campaign.METHODS.items():
            cls = getattr(modules[path], name)
            for method in methods:
                function = getattr(cls, method)
                self.assertEqual(function.__code__.co_filename, str(campaign.ROOT/path))
                self.assertEqual(function.__code__.co_qualname, name+'.'+method)


def framed_fixture(receipt, corpus, expected, objects):
    """Deliberately fabricated test peer; never supplied as native acceptance."""
    from copy import deepcopy
    from tests.test_pipeline_fixed_provider_campaign import Script
    from tests.test_core_pipeline_build_views import BuildEnvelopeFixture
    from biocompiler.core_pipeline_manager import _ordered
    from biocompiler.core_pipeline_provider_views import origin_reference
    helper = BuildEnvelopeFixture(objects)
    script = Script(receipt)
    source, config = objects['authority_objects']['request'], objects['requested_config']
    refs = {key: helper.callbacks.retain(value) for key, value in (
        ('request', source), ('target', source.target), ('config', config))}
    records = dict(objects['component_records'])
    values, record_envelopes = [], {}
    def binding(value, document, flavor='json'):
        index = next((index for index, (prior, kind) in enumerate(values) if prior is value and kind == flavor), None)
        if index is None:
            index = len(values); values.append((value, flavor))
        return {'kind': 'native', 'identity': 'view/'+str(index), 'tree': _ordered(document)}
    for index, (key, record) in enumerate(records.items()):
        raw = record.to_dict()
        record_envelopes[key] = {'value': raw, 'bindings': {'record_id': 'record/'+str(index),
            **{name: binding(getattr(record, name), raw[name]) for name in ('payload', 'dependencies', 'requirements', 'checks', 'provenance')},
            'obligations': binding(record.obligations, raw['obligations'], 'obligations'),
            'obligation_objects': [binding(value, document, 'obligation') for value, document in zip(record.obligations, raw['obligations'])]}}
    providers, roles = {}, {}
    for index, (pass_id, slot) in enumerate(campaign.fixed.SLOTS):
        token = 'provider/'+str(index)
        roles[token] = pass_id+('.producer' if slot == 'producer' else '.validator')
        providers[pass_id, slot] = (token, helper.callbacks.retain(object()))
    minted = set()
    evidence = {'events': [], 'inspections': [], 'providers': {token: ref['handle'] for token, ref in providers.values()},
        'record_identities': {item['bindings']['record_id']: key for key, item in record_envelopes.items()}}
    original_events = corpus.fixed.continuations[expected['id']]['events']
    last_inspection = None
    published = set()
    def inspect(raw, family):
        nonlocal last_inspection
        sequence = script.command('inspect-ordered-references', {}); evidence['inspections'].append(sequence)
        state = campaign.fixed.snapshot(raw)
        tokens = set()
        for name in ('passes', 'provider_history'):
            for entry in state[name].values():
                key = entry['contract']['id']
                token, ref = providers[key, 'producer'];entry['producer']=token;tokens.add(token)
                for slot in entry['validators']:
                    token, ref=providers[key, slot];entry['validators'][slot]=token;tokens.add(token)
        for token in sorted(tokens):
            if token not in minted:
                ref=next(ref for value, ref in providers.values() if value==token)
                script.invoke(sequence,'native-provider',{'provider_id':token,'role':roles[token]},ref);minted.add(token)
        for key, value in state['records'].items():
            campaign.equal(value, record_envelopes[key]['value'], 'Fixture original historical record differs')
            state['records'][key]=record_envelopes[key]
        definitions = []
        for key in campaign.original_order(raw)['records']:
            envelope=state['records'][key];token=envelope['bindings']['record_id']
            if token not in published:
                definitions.append(envelope);published.add(token)
            state['records'][key]={'record_id':token}
        script.reply(sequence, {'snapshot':state,'order':campaign.original_order(raw),'record_definitions':definitions,
            'providers':[{'provider_id':token,'object':next(ref for value,ref in providers.values() if value==token)} for token in sorted(tokens)]})
        last_inspection = (sequence, len(script.rows))
        return sequence
    authority = corpus.fixed.document('fixed',expected['authority'])
    sequence=script.command('initialize-synthetic',{**authority,'config':config.to_dict(),'request_tree':_ordered(source.to_dict()),
        'manager_limits':None,**{key+'_object':value for key,value in refs.items()}})
    script.reply(sequence,{'kind':'synthetic','manager':True,'artifacts':['candidate','pipeline_result','selection_result'],
        'target':{'value':source.target.to_dict(),'binding':{'kind':'host','object':refs['target']}}})
    def result_envelope(value):
        return {'value':campaign.ordinary_value(value),'artifact':record_envelopes[value.artifact.id]}
    upstream=helper.envelope('synthetic');upstream['result']=result_envelope(objects['synthetic'].result)
    upstream['sources']['candidate']=record_envelopes['mechanism']
    component=helper.envelope('components');component['result']=result_envelope(objects['component'].result)
    component['sources']['candidate']=record_envelopes['mechanism']
    sequence=script.command('build-result',{'kind':'synthetic'});evidence['upstream_sequence']=sequence
    roots=campaign.source_roots(build,source,config)
    origin_specs=[(name,[]) for name in ('BOOLEAN','LEVEL','DURATION','defaultLifecycle','syntheticCapabilities')]
    for collection,name,items in (('domain','inputs',source.domain.inputs),('contract','requirements',source.contract.requirements)):
        for index in range(len(items)):
            path=[collection,name,index,'observable'];origin_specs.extend([('request',path),('request',path+['dtype'])])
    for index,node in enumerate(source.behavior.nodes):
        if node.source is not None:origin_specs.append(('request',['behavior','nodes',index,'source']))
    # Supply only source references actually retained by the two build views.
    existing=set(helper.callbacks._objects)
    for root,path in origin_specs:
        value=origin_reference(source,root,path)
        handles=[handle for handle,item in helper.callbacks._objects.items() if item is value]
        if handles and handles[0] in existing:
            script.invoke(sequence,'origin-reference',{'root':root,'path':path},{'handle':handles[0]})
    script.reply(sequence,upstream)
    evidence['sources']={handle:[name for name,value in roots.items() if value is item] for handle,item in helper.callbacks._objects.items()
        if any(value is item for value in roots.values())}
    evidence['initial']=inspect(corpus.fixed.document('fixed',expected['manager_state']),'fixed')
    preparation={'preparation_id':'preparation/0','dependencies':[[campaign.fixed.unpack(corpus.fixed.document('continuation',event['arguments']))['bound'][key]
        for key in ('key','identity')] for event in original_events[:8]]}
    sequence=script.command('prepare-components',{});evidence['prepare_sequence']=sequence;script.reply(sequence,preparation)
    prep={'preparation_id':'preparation/0'}
    registration=None
    for index,event in enumerate(original_events):
        wanted=campaign.fixed.unpack(corpus.fixed.document('continuation',event['arguments']))['bound']
        if index==8:
            sequence=script.command('component-profile',prep);evidence['profile_sequence']=sequence;script.reply(sequence,wanted['profile'])
        if index==9:
            sequence=script.command('component-registration',prep);evidence['registration_sequence']=sequence
            token,producer=providers['synthetic_to_components','producer'];validator_token,validator=providers['synthetic_to_components','composition']
            for native,ref in ((token,producer),(validator_token,validator)):
                script.invoke(sequence,'native-provider',{'provider_id':native,'role':roles[native]},ref);minted.add(native)
            contract=objects['component'].manager._passes['synthetic_to_components'][0]
            registration={'contract':wanted['contract'],'producer':producer,'validators':[['composition',validator]],
                'obligation_objects':[binding(value,value.to_dict(),'obligation') for value in contract.introduces]}
            script.reply(sequence,registration)
        reused = last_inspection is not None and last_inspection[1] == len(script.rows)
        before = last_inspection[0] if reused else inspect(corpus.fixed.document('continuation',event['state_before']),'continuation')
        row={key:event[key] for key in ('api','context','outcome','error') if key in event}
        row.update(before=before,before_reused=reused,start_frame=len(script.rows))
        operation=event['api'].split('.')[-1].replace('_','-');arguments=deepcopy(wanted)
        if operation=='register':
            arguments={'contract':wanted['contract'],'producer':registration['producer'],
                'validators':helper.callbacks.retain({'composition':helper.callbacks.resolve(registration['validators'][0][1])}),
                'obligation_objects':[helper.callbacks.retain(item) for item in contract.introduces]}
        sequence=script.command(operation,arguments);row['sequence']=sequence
        if operation=='register':
            for token,reference in (providers['synthetic_to_components','producer'],providers['synthetic_to_components','composition']):
                script.invoke(sequence,'provider-reference',{'object':reference},{'kind':'native','provider_id':token})
        if event['outcome']=='raised':
            script.server('reply',{'sequence':sequence,'request_sha256':campaign.sha(script.bodies[sequence]),
                'outcome':{'status':'rejected','value':{**event['error'],'attributes':{},'attributes_tree':['object',[]]}},'closed':False})
        else:
            value=campaign.fixed.unpack(corpus.fixed.document('continuation',event['result']));row['value']=value
            if operation in ('get','run'):
                result=record_envelopes[value['id']];row['record_identity']=result['bindings']['record_id']
            elif operation=='result':
                result={'value':value,'artifact':record_envelopes[value['artifact']['id']]};row['record_identity']=result['artifact']['bindings']['record_id']
            else:result=None
            script.reply(sequence,result)
        row['end_frame']=len(script.rows);row['after']=inspect(corpus.fixed.document('continuation',event['state_after']),'continuation')
        evidence['events'].append(row)
        if index==11:
            sequence=script.command('finish-components',{**prep,'result_sequence':row['sequence'],'record_id':record_envelopes['components']['bindings']['record_id']})
            evidence['finish_sequence']=sequence;script.reply(sequence,component)
            evidence['completed']=inspect(corpus.fixed.document('fixed',corpus.fixed.by_id[expected['parent']]['manager_state']),'fixed')
    script.close()
    return script.rows,campaign.public_graph(corpus.authorities[expected['authority']]),evidence


class ContinuationReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pathlib import Path
        import tempfile
        cls.temporary=tempfile.TemporaryDirectory();cls.directory=Path(cls.temporary.name)
        cls.corpus=campaign.Corpus();cls.objects=[];build.capture(retain=cls.objects)
        cls.receipt={'_artifact_directory':str(cls.directory),'artifacts':{}}
        cls.expected=cls.corpus.cases[0]
        cls.frames,cls.actual,cls.evidence=framed_fixture(cls.receipt,cls.corpus,cls.expected,cls.objects[0])

    @classmethod
    def tearDownClass(cls):cls.temporary.cleanup()

    def check(self,frames=None,evidence=None):
        details={};channel,application=campaign.manager.declarations()
        artifacts=campaign.manager.Artifacts(self.directory,self.receipt['artifacts'])
        campaign.manager.validate_frames(frames or self.frames,artifacts,channel,application,details=details,
            provider_calls=False,initializer='initialize-synthetic')
        return campaign.validate_case(self.corpus,self.expected,self.actual,evidence or self.evidence,
            details,build,self.objects[0]['authority_objects'])

    def test_complete_frame_bound_original_chain_and_public_graph(self):
        result=self.check();self.assertEqual(result['events'],len(self.evidence['events']))

    def test_all_six_original_authorities_rebuild_complete_public_graphs(self):
        from pathlib import Path
        import tempfile
        for source_case, objects in zip(self.corpus.build['cases'], self.objects):
            expected=next(case for case in self.corpus.cases if case['authority']==source_case['authority_sha256'])
            with self.subTest(authority=source_case['id']),tempfile.TemporaryDirectory() as directory:
                receipt={'_artifact_directory':directory,'artifacts':{}}
                frames,actual,evidence=framed_fixture(receipt,self.corpus,expected,objects)
                details={};channel,application=campaign.manager.declarations()
                campaign.manager.validate_frames(frames,campaign.manager.Artifacts(Path(directory),receipt['artifacts']),
                    channel,application,details=details,provider_calls=False,initializer='initialize-synthetic')
                result=campaign.validate_case(self.corpus,expected,actual,evidence,details,build,objects['authority_objects'])
                self.assertEqual(result['events'],len(evidence['events']))

    def test_repaired_semantic_receipts_reject_values_roles_order_and_result_substitution(self):
        from copy import deepcopy
        from pathlib import Path
        import tempfile
        from tests.test_pipeline_manager_campaign import reframe
        changes = ('record-binding', 'role', 'order', 'arguments', 'error', 'finish-sequence', 'finish-result', 'candidate-identity')
        for change in changes:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                receipt={'_artifact_directory':directory,'artifacts':{}}
                frames,actual,evidence=framed_fixture(receipt,self.corpus,self.expected,self.objects[0])
                row={'frames':frames};receipt['checks']=[row]
                def mutate(values):
                    commands={value['sequence']:value for value in values if value['kind']=='command'}
                    replies={value['sequence']:value for value in values if value['kind']=='reply'}
                    if change=='record-binding':
                        token=next(value['outcome']['value']['bindings']['payload']['identity'] for value in replies.values()
                            if commands.get(value['sequence'],{}).get('operation')=='run')
                        def visit(value):
                            if type(value) is dict:
                                if value.get('kind')=='native' and value.get('identity')==token:value['tree']=['scalar',False]
                                for item in value.values():visit(item)
                            elif type(value) is list:
                                for item in value:visit(item)
                        visit(values)
                    elif change=='role':
                        entries=[value for value in values if value['kind']=='invoke' and value['action']=='native-provider']
                        entries[0]['arguments']['role'],entries[1]['arguments']['role']=entries[1]['arguments']['role'],entries[0]['arguments']['role']
                    elif change=='order':
                        reply=replies[evidence['initial']];reply['outcome']['value']['order']['dependencies'].reverse()
                    elif change=='arguments':
                        commands[evidence['events'][0]['sequence']]['arguments']['identity']='0'*64
                    elif change=='error':
                        event=next(item for item in evidence['events'] if item['outcome']=='raised')
                        replies[event['sequence']]['outcome']['value']['message']+=' changed'
                    elif change=='finish-sequence':
                        commands[evidence['finish_sequence']]['arguments']['result_sequence']=evidence['events'][10]['sequence']
                    elif change=='finish-result':
                        replies[evidence['finish_sequence']]['outcome']['value']['result']['value']['status']='partial'
                    else:
                        replies[evidence['finish_sequence']]['outcome']['value']['artifacts']['candidate']['binding']['identity']='artifact/999999'
                reframe(receipt,row,mutate)
                details={};channel,application=campaign.manager.declarations()
                campaign.manager.validate_frames(row['frames'],campaign.manager.Artifacts(Path(directory),receipt['artifacts']),
                    channel,application,details=details,provider_calls=False,initializer='initialize-synthetic')
                messages={'record-binding':'Native view binding projection', 'role':'proxy role', 'order':'insertion order',
                    'arguments':'command arguments', 'error':'actual native rejection', 'finish-sequence':'phase authority',
                    'finish-result':'retained result', 'candidate-identity':'complete public identity graph'}
                with self.assertRaisesRegex(AssertionError,messages[change]):
                    campaign.validate_case(self.corpus,self.expected,actual,evidence,details,build,self.objects[0]['authority_objects'])

    def test_event_outcome_cannot_be_reassigned_to_another_original_interval(self):
        from copy import deepcopy
        evidence=deepcopy(self.evidence)
        pair=next((left,right) for left in range(len(evidence['events'])) for right in range(left+1,len(evidence['events']))
            if all(evidence['events'][left].get(key)==evidence['events'][right].get(key) for key in ('api','context','outcome','value')))
        left,right=(evidence['events'][index] for index in pair)
        for key in ('sequence','start_frame','end_frame'):left[key],right[key]=right[key],left[key]
        with self.assertRaisesRegex(AssertionError,'own inspection interval'):self.check(evidence=evidence)

    def test_installed_loader_restores_search_path_and_rejects_source_package(self):
        import biocompiler
        previous=list(sys.path)
        loaded=campaign.load_oracle(installed=False)
        self.assertEqual(sys.path,previous)
        self.assertEqual(loaded.Graph.__module__,'fixed_build_original')
        with patch.object(biocompiler,'__file__',str(campaign.ROOT/'src/biocompiler/__init__.py')):
            with self.assertRaisesRegex(AssertionError,'Source-tree product'):
                campaign.load_oracle(installed=True)
        self.assertEqual(sys.path,previous)

    def test_repaired_compact_definitions_cannot_be_invented_rebound_or_published_late(self):
        from copy import deepcopy
        from pathlib import Path
        import tempfile
        from tests.test_pipeline_manager_campaign import reframe
        for change in ('missing','late','duplicate','wrong-name','unknown','alias'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as directory:
                receipt={'_artifact_directory':directory,'artifacts':{}}
                frames,actual,evidence=framed_fixture(receipt,self.corpus,self.expected,self.objects[0])
                row={'frames':frames};receipt['checks']=[row]
                def mutate(values):
                    replies={value['sequence']:value for value in values if value['kind']=='reply'}
                    initial=replies[evidence['initial']]['outcome']['value']
                    later=replies[evidence['events'][0]['after']]['outcome']['value']
                    if change in ('missing','late'):
                        definition=initial['record_definitions'].pop(0)
                        if change=='late':later['record_definitions'].append(definition)
                    elif change=='duplicate':later['record_definitions'].append(deepcopy(initial['record_definitions'][0]))
                    elif change=='wrong-name':initial['record_definitions'][0]['value']['id']='other'
                    elif change=='unknown':initial['snapshot']['records']['request']={'record_id':'record/999999'}
                    else:initial['snapshot']['records']['request']=deepcopy(initial['snapshot']['records']['behavior'])
                reframe(receipt,row,mutate)
                details={};channel,application=campaign.manager.declarations()
                campaign.manager.validate_frames(row['frames'],campaign.manager.Artifacts(Path(directory),receipt['artifacts']),
                    channel,application,details=details,provider_calls=False,initializer='initialize-synthetic')
                with self.assertRaisesRegex(AssertionError,'[Cc]ompact'):
                    campaign.validate_case(self.corpus,self.expected,actual,evidence,details,build,self.objects[0]['authority_objects'])

    def test_before_reuse_requires_exact_last_inspection_and_after_still_fresh(self):
        from copy import deepcopy
        for change in ('claimed-fresh','claimed-reuse','no-after'):
            evidence=deepcopy(self.evidence)
            if change=='claimed-fresh':
                row=next(item for item in evidence['events'] if item['before_reused']);row['before_reused']=False
            elif change=='claimed-reuse':
                row=evidence['events'][0];row['before_reused']=True
            else:
                row=evidence['events'][0];row['after']=row['before']
            with self.subTest(change=change),self.assertRaises(AssertionError):self.check(evidence=evidence)

    def test_four_runtime_comparison_rejects_missing_slots_before_claiming_success(self):
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'receipts';native=Path(directory)/'native'
            root.mkdir();native.mkdir()
            with self.assertRaisesRegex(AssertionError,'four-runtime'):
                campaign.compare(root,native,revision='a'*40,source_revision='b'*40,run_id='1')
        self.assertEqual(campaign.COVERAGE['fixed_boundaries'],136)
        self.assertEqual(campaign.COVERAGE['original_manager_contexts'],476)
        self.assertEqual(campaign.metadata(self.corpus)['pending']['excluded'],self.corpus.pending['excluded'])

    def test_repaired_intervening_native_command_invalidates_before_snapshot_reuse(self):
        from copy import deepcopy
        from pathlib import Path
        import tempfile
        from tests.test_pipeline_manager_campaign import reframe
        with tempfile.TemporaryDirectory() as directory:
            receipt={'_artifact_directory':directory,'artifacts':{}}
            frames,actual,evidence=framed_fixture(receipt,self.corpus,self.expected,self.objects[0])
            row={'frames':frames};receipt['checks']=[row]
            channel,application=campaign.manager.declarations()
            def mutate(values):
                old_positions={id(value):index for index,value in enumerate(values)}
                event=next(item for item in evidence['events'] if item['before_reused']);index=event['start_frame']
                command=deepcopy(values[index]);command.update(sequence=999999,operation='target',arguments={})
                target=next(value['outcome']['value']['target'] for value in values if value['kind']=='reply'
                    and type(value.get('outcome',{}).get('value')) is dict
                    and value['outcome']['value'].get('kind')=='synthetic' and 'manager' in value['outcome']['value'])
                reply=deepcopy(next(value for value in values if value['kind']=='reply' and value['sequence']==0))
                reply.update(event_id=999999,sequence=999999,outcome={'status':'ok','value':target})
                values[index:index]=[command,reply]
                sequences={value['sequence']:index for index,value in enumerate(value for value in values if value['kind'] in channel['client_fields'])}
                events={value['event_id']:index for index,value in enumerate(value for value in values if value['kind'] in channel['server_fields'])}
                positions={old_positions[id(value)]:index for index,value in enumerate(values) if id(value) in old_positions}
                for value in values:
                    if value['kind'] in channel['client_fields']:value['sequence']=sequences[value['sequence']]
                    else:
                        value['event_id']=events[value['event_id']]
                        if value['kind']=='reply':value['sequence']=sequences[value['sequence']]
                    if value['kind']=='invoke':value['command_sequence']=sequences[value['command_sequence']]
                    if value['kind'] in ('invoke','continue'):value['invocation_id']=events[value['invocation_id']]
                    if value['kind']=='command' and value['operation']=='finish-components':
                        value['arguments']['result_sequence']=sequences[value['arguments']['result_sequence']]
                for key in ('initial','completed','upstream_sequence','prepare_sequence','profile_sequence','registration_sequence','finish_sequence'):
                    evidence[key]=sequences[evidence[key]]
                evidence['inspections']=[sequences[sequence] for sequence in evidence['inspections']]
                for event in evidence['events']:
                    for key in ('before','after','sequence'):event[key]=sequences[event[key]]
                    for key in ('start_frame','end_frame'):event[key]=positions[event[key]]
            reframe(receipt,row,mutate)
            details={}
            campaign.manager.validate_frames(row['frames'],campaign.manager.Artifacts(Path(directory),receipt['artifacts']),
                channel,application,details=details,provider_calls=False,initializer='initialize-synthetic')
            with self.assertRaisesRegex(AssertionError,'intervening native traffic'):
                campaign.validate_case(self.corpus,self.expected,actual,evidence,details,build,self.objects[0]['authority_objects'])


if __name__ == '__main__':
    unittest.main()
