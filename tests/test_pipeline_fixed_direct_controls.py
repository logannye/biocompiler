"""Fabricated complete peers exercise direct controls; no native acceptance."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from tools import pipeline_fixed_direct_controls as direct
from tools import check_pipeline_fixed_continuation_install as continuation
from tools import capture_pipeline_fixed_build_semantics as oracle
from tests.test_pipeline_fixed_provider_campaign import Script
from tests.test_core_pipeline_build_views import BuildEnvelopeFixture
from tests.test_pipeline_manager_campaign import reframe, guard_with_routes

manager = direct.manager


class DirectRecordObservationTests(unittest.TestCase):
    """Record observation order is independent of lazy SDK cache insertion."""
    def setUp(self):
        from tests import test_core_pipeline_manager as views
        self.views = views.CorePipelineManagerTests()
        self.views.setUp()
        self.addCleanup(self.views.doCleanups)
        self.names = ('request', 'behavior', 'mechanism', 'components')
        self.envelopes = {name: self.views.record(identity=name) for name in self.names}
        from biocompiler.core_pipeline_manager import _ordered
        self.configuration = {'actual': 'inspected mechanism configuration'}
        provenance = {'configuration': self.configuration}
        self.envelopes['mechanism']['value']['provenance'] = provenance
        self.envelopes['mechanism']['bindings']['provenance']['tree'] = _ordered(provenance)

    def inspected_records(self):
        live = self.views.manager
        # The actual build reader decodes its historical candidate before its
        # result record: synthetic -> mechanism, components -> mechanism/components.
        for name in ('mechanism', 'mechanism', 'mechanism', 'components'):
            live._record(self.envelopes[name])
        snapshot = {name: {} for name in ('passes', 'component_inputs', 'provider_history',
            'component_input_history', 'dependencies', 'profiles')}
        snapshot.update(target=live._target.to_dict(), records=self.envelopes)
        order = {name: list(value) for name, value in snapshot.items() if name != 'target'}
        order.update(combined_provider_history=[], validators={name: {} for name in
            ('passes', 'component_inputs', 'provider_history', 'component_input_history')})
        inspected = live._ordered_inspection({'snapshot': snapshot, 'order': order, 'providers': []})
        return live._inspection_state(inspected)['_records']

    def test_actual_sdk_inspection_order_retains_lazy_cached_record_objects(self):
        records = self.inspected_records()
        self.assertEqual(tuple(self.views.manager._records), ('mechanism', 'components', 'request', 'behavior'))
        self.assertEqual(tuple(records), self.names)
        self.assertIsNot(records, self.views.manager._records)
        for name in self.names:
            self.assertIs(records[name], self.views.manager._records[name])

    def run_direct(self, *, wrong_inspection_order=False):
        records = self.inspected_records()
        configuration = self.configuration
        expected = [{'id': 'direct/'+str(index), 'original_cases': []} for index in range(6)]
        authority = {'request': object(), 'history': (), 'until': 1, 'config': object()}
        originals = [{'authority_objects': authority} for _ in expected]
        selected = object()
        created, observed, witnesses, closed = [], [], [], []
        test = self
        class Peer:
            def __init__(self):
                self.session = SimpleNamespace(last_response=SimpleNamespace(sequence=0), traffic=[])
                self._records = dict(test.views.manager._records)
                order = tuple(reversed(test.names)) if wrong_inspection_order else test.names
                self.observed_records = {name: records[name] for name in order}
                self._provider_config = authority['config']
                self._inspection_providers = {}
                self.passes, self.registered, self.calls = {}, {}, []
                for index, role in enumerate(direct.ROLES):
                    def producer(context):
                        return SimpleNamespace(output=SimpleNamespace(generator_config=selected))
                    self.passes[role] = (SimpleNamespace(version='fixture.v1'), producer, {})
                    self._inspection_providers['provider/'+str(index)] = producer
                self.inspections = 0
            def build_result(self, kind):
                self.session.last_response.sequence += 1
                return kind
            def inspection_state(self):
                self.inspections += 1
                self.session.last_response.sequence += 1
                return {'_passes': self.passes, '_records': self.observed_records}
            def register(self, contract, wrapper, validators):
                self.registered[len(self.registered)] = wrapper
            def run(self, role, source, output, *, configuration):
                self.calls.append((role, source, output, configuration))
                return self.registered[len(self.calls)-1](object())
        class Witness(direct.Witness):
            def __init__(self):
                super().__init__()
                witnesses.append(self)
            def evidence(self, oracle):
                return {}
        def factory(*args, **kwargs):
            peer = Peer(); created.append(peer); return peer
        def observe(identity, value, **kwargs):
            self.assertEqual(tuple(name for name, _ in value['component_records']), self.names)
            self.assertEqual(tuple(name for name, _ in value['synthetic_records']), self.names[:3])
            for name, actual in value['component_records']:
                self.assertIs(actual, records[name])
            self.assertIs(value['selected_config'], selected)
            observed.append(identity)
            return {'id': identity}
        from biocompiler.core_pipeline_manager import CorePassManager
        receipt = {}
        with patch.object(CorePassManager, 'from_components', side_effect=factory), \
                patch.object(direct, 'Witness', Witness), \
                patch.object(direct.providers, 'installed_modules'), \
                patch.object(manager, 'artifact', side_effect=lambda receipt, raw: manager.sha(raw)), \
                patch.object(continuation, 'close_receipt', side_effect=lambda peer, *_: closed.append(peer)):
            direct.run(object(), SimpleNamespace(build={'cases': expected}),
                SimpleNamespace(observe_case=observe), receipt, originals)
        self.assertEqual(observed, [row['id'] for row in expected])
        self.assertEqual(len(receipt['direct_checks']), 6)
        self.assertEqual(closed, created)
        for peer, witness in zip(created, witnesses):
            self.assertEqual(peer.inspections, 1)
            self.assertIs(witness.records, peer.observed_records)
            self.assertEqual(tuple(peer._records), ('mechanism', 'components', 'request', 'behavior'))
            self.assertEqual(peer.calls, [(role, source, output, configuration if index == 1 else None)
                for index, (role, source, output) in enumerate(zip(direct.ROLES,
                    ('request', *direct.OUTPUTS[:2]), direct.OUTPUTS))])

    def test_direct_controls_use_one_inspected_order_and_the_same_record_objects(self):
        self.run_direct()

    def test_direct_controls_still_reject_wrong_native_inspection_order(self):
        with self.assertRaisesRegex(AssertionError, 'Direct initial record census differs'):
            self.run_direct(wrong_inspection_order=True)


def fixture(receipt, expected, original, *, late_origin=False):
    from biocompiler.core_pipeline_manager import _ordered
    from biocompiler.core_pipeline_provider_views import allocate, origin_reference
    from biocompiler.compiler.pipeline import PassContract
    from biocompiler.ir.intent import thaw_json
    helper = BuildEnvelopeFixture(original)
    objects = helper.callbacks
    request, config = original['authority_objects']['request'], original['requested_config']
    refs = {name: objects.retain(value) for name, value in (('request', request), ('target', request.target), ('config', config))}
    actual_manager = original['component'].manager
    saved = {name: dict(getattr(actual_manager, name)) for name in ('_dependencies', '_passes', '_component_inputs', '_provider_history', '_records', '_profiles')}
    records = dict(saved['_records'])
    calls, new_records, wrappers = [], {}, {}
    try:
        source = 'request'
        for pass_id, name, output_id in zip(direct.ROLES, direct.NAMES, direct.OUTPUTS):
            contract, producer, validators = actual_manager._passes[pass_id]
            contract = allocate(PassContract, {**vars(contract), 'version': contract.version+direct.VERSION_SUFFIX})
            def wrapper(context, producer=producer, name=name):
                proposal = producer(context)
                calls.append((name, context, proposal))
                return proposal
            wrappers[pass_id] = wrapper
            actual_manager.register(contract, wrapper, validators)
            configuration = dict(records['mechanism'].provenance['configuration']) if name == 'generate' else None
            new_records[output_id] = actual_manager.run(pass_id, source, output_id, configuration=configuration)
            source = output_id
    finally:
        for name, value in saved.items():
            setattr(actual_manager, name, value)
    observed = {**original, 'producer_returns': [(name, proposal) for name, _, proposal in calls],
        'selected_config': calls[1][2].output.generator_config}
    graph = oracle.observe_case(expected['id'], observed)
    graph['original_cases'] = expected['original_cases']
    assert graph == expected, 'Actual original wrapper chain changed the complete graph'
    values, envelopes = [], {}
    def binding(value, document, flavor='json'):
        index = next((index for index, (previous, kind) in enumerate(values) if previous is value and kind == flavor), None)
        if index is None:
            index = len(values); values.append((value, flavor))
        return {'kind': 'native', 'identity': 'view/'+str(index), 'tree': _ordered(document)}
    for index, (key, record) in enumerate({**records, **new_records}.items()):
        raw = record.to_dict()
        envelopes[key] = {'value': raw, 'bindings': {'record_id': 'record/'+str(index),
            **{name: binding(getattr(record, name), raw[name]) for name in ('payload', 'dependencies', 'requirements', 'checks', 'provenance')},
            'obligations': binding(record.obligations, raw['obligations'], 'obligations'),
            'obligation_objects': [binding(value, raw_item, 'obligation') for value, raw_item in zip(record.obligations, raw['obligations'])]}}
    builds = []
    for kind, source in (('synthetic', original['synthetic']), ('components', original['component'])):
        value = helper.envelope(kind)
        value['result'] = {'value': continuation.ordinary_value(source.result), 'artifact': envelopes[source.result.artifact.id]}
        value['sources']['candidate'] = envelopes['mechanism']
        builds.append(value)
    proposals = [helper.provider(name, proposal)[1] for name, _, proposal in calls]
    evidence = {'inspection': None, 'calls': [], 'objects': {}, 'providers': {}, 'arguments': {}, 'build_sequences': []}
    roots = {'request': request, 'target': request.target, 'config': config,
        **dict(oracle.providers.source_origins(request)),
        'constant:synthetic_capabilities': origin_reference(request, 'syntheticCapabilities', [])}
    for handle, value in objects._objects.items():
        names = [name for name, root in roots.items() if value is root]
        if names: evidence['objects'][handle] = {'kind': 'source', 'names': names}
    slots, roles = {}, {}
    for pass_id in direct.ROLES:
        contract, producer, validators = saved['_passes'][pass_id]
        for slot in ('producer', *validators):
            token = 'provider/'+str(len(slots)); reference = objects.retain(object())
            slots[pass_id, slot] = (token, reference)
            roles[token] = pass_id+('.producer' if slot == 'producer' else '.validator')
            evidence['providers'][token] = {'object': reference['handle'], 'pass_id': pass_id, 'slot': slot}
        reference = objects.retain(wrappers[pass_id])
        evidence['objects'][reference['handle']] = {'kind': 'wrapper', 'pass_id': pass_id}
    snapshot = {name: {} for name in manager.STATE_MAPS}
    snapshot.update(target=request.target.to_dict(), dependencies=dict(saved['_dependencies']), records={key: envelopes[key] for key in records},
        profiles={key: {**vars(value), 'stage': value.stage.value, 'obligations': list(value.obligations)} for key, value in saved['_profiles'].items()})
    for name in ('passes', 'provider_history'):
        for key, (contract, producer, validators) in saved['_'+name].items():
            snapshot[name][key] = {'contract': contract.to_dict(), 'producer': slots[contract.id, 'producer'][0],
                'validators': {slot: slots[contract.id, slot][0] for slot in validators}}
    order = {name: list(snapshot[name]) for name in manager.STATE_MAPS}
    order.update(combined_provider_history=list(saved['_provider_history']), validators={name: {
        key: list(value['validators']) for key, value in snapshot[name].items()} for name in manager.REGISTRATION_MAPS})
    inspection = {'snapshot': snapshot, 'order': order,
        'providers': [{'provider_id': token, 'object': reference} for token, reference in slots.values()]}
    script = Script(receipt)
    sequence = script.command('initialize-components', {**expected['authority'], 'config': config.to_dict(),
        'request_tree': _ordered(request.to_dict()), 'manager_limits': None, **{key+'_object': value for key, value in refs.items()}})
    from tests.pipeline_fixed_initializer_fixture import emit, records as initializer_records
    hooks = emit(script, sequence,
        {'value': request.target.to_dict(), 'binding': {'kind': 'host', 'object': refs['target']}},
        {key: entry['contract'] for key, entry in inspection['snapshot']['passes'].items()},
        [(token, roles[token], reference) for token, reference in slots.values()], count=3)
    evidence['arguments'].update(hooks['arguments'])
    initializer_records(hooks, (envelopes[key] for key in records))
    introduced = {item['id']: handle for handle, item in hooks['host_documents'].items()}
    script.reply(sequence, {'kind': 'components', 'manager': True,
        'artifacts': ['candidate', 'pipeline_result', 'selection_result', 'assembly', 'link_result', 'behavior_result'],
        'target': {'value': request.target.to_dict(), 'binding': {'kind': 'host', 'object': refs['target']}}})
    origin_specs = [(root, []) for root in ('BOOLEAN', 'LEVEL', 'DURATION', 'defaultLifecycle', 'syntheticCapabilities')]
    for collection, key, items in (('domain', 'inputs', request.domain.inputs), ('contract', 'requirements', request.contract.requirements)):
        for index in range(len(items)):
            path = [collection, key, index, 'observable']
            origin_specs.extend([('request', path), ('request', path+['dtype'])])
    origin_specs.extend(('request', ['behavior', 'nodes', index, 'source']) for index, value in enumerate(request.behavior.nodes) if value.source is not None)
    anchored = set()
    delayed = objects.retain(origin_reference(request, 'BOOLEAN', []))['handle'] if late_origin else None
    for kind, envelope in zip(('synthetic', 'components'), builds):
        sequence = script.command('build-result', {'kind': kind}); evidence['build_sequences'].append(sequence)
        for root, path in origin_specs:
            reference = objects.retain(origin_reference(request, root, path))
            if reference['handle'] in evidence['objects'] and reference['handle'] not in anchored and reference['handle'] != delayed:
                script.invoke(sequence, 'origin-reference', {'root': root, 'path': path}, reference); anchored.add(reference['handle'])
        script.reply(sequence, envelope)
    sequence = script.command('inspect-ordered', {}); evidence['inspection'] = sequence
    script.reply(sequence, inspection)
    source_id = 'request'
    for index, (pass_id, output_id) in enumerate(zip(direct.ROLES, direct.OUTPUTS)):
        contract, producer, validators = saved['_passes'][pass_id]
        raw_contract = {**contract.to_dict(), 'version': contract.version+direct.VERSION_SUFFIX}
        wrapper = objects.retain(wrappers[pass_id]); mapping = objects.retain(validators)
        evidence['arguments'][mapping['handle']] = {'kind': 'validators', 'items': [[key, slots[pass_id, key][0]] for key in validators]}
        obligations = []
        for offset, value in enumerate(contract.introduces):
            # Actual inspection_state yields fresh typed contract objects, so
            # these wrappers must not reuse initialization's equal obligations.
            from biocompiler.core_pipeline_manager import _obligation
            reference = objects.retain(_obligation(value.to_dict()))
            obligations.append(reference)
            introduced[value.id] = reference['handle']
            evidence['arguments'][reference['handle']] = {'kind': 'contract_obligation', 'pass_id': pass_id,
                'index': offset, 'value': value.to_dict()}
        sequence = script.command('register', {'contract': raw_contract, 'producer': wrapper, 'validators': mapping, 'obligation_objects': obligations})
        for slot in validators:
            token, reference = slots[pass_id, slot]
            script.invoke(sequence, 'provider-reference', {'object': reference}, {'kind': 'native', 'provider_id': token})
        wrapper_token = 'provider/'+str(6+index)
        script.invoke(sequence, 'bind-provider', {'provider_id': wrapper_token, 'object': wrapper}, None)
        script.reply(sequence, None)
        configuration = dict(records['mechanism'].provenance['configuration']) if index == 1 else None
        config_ref = None if configuration is None else objects.retain(configuration)
        if config_ref is not None:
            evidence['arguments'][config_ref['handle']] = {'kind': 'configuration', 'value': oracle.providers.plain(configuration)}
        sequence = script.command('run', {'pass_id': pass_id, 'input_id': source_id, 'output_id': output_id, 'configuration': config_ref})
        context = calls[index][1]; document = {key: thaw_json(getattr(context, key)) for key in ('input', 'output', 'configuration', 'dependencies', 'observation_map')}; document.update(target=context.target.to_dict(), requirements=list(context.requirements), source_links=[]); context_ref = objects.retain(context)
        context_id = 'context/'+str(index)
        context_bindings = {name: binding(getattr(context, name), document[name], 'default-observation' if name == 'observation_map' else 'json')
            for name in ('configuration', 'dependencies', 'requirements', 'observation_map')}
        context_bindings.update(input=envelopes[source_id]['bindings']['payload'], target={'kind': 'host', 'object': refs['target']}, output=None, source_links=None)
        script.invoke(sequence, 'hydrate-context', {'context_id': context_id, 'document': document, 'bindings': context_bindings}, context_ref)
        callback = script.begin(sequence, 'call-provider', {'provider_id': wrapper_token, 'context': context_ref})
        start = len(script.rows)
        nested = script.command('call-native-provider', {'provider_id': slots[pass_id, 'producer'][0], 'context_id': context_id})
        if late_origin and index == 2:
            script.invoke(nested, 'origin-reference', {'root': 'BOOLEAN', 'path': []}, {'handle': delayed})
        script.reply(nested, proposals[index])
        proposal_ref = objects.retain(calls[index][2])
        evidence['calls'].append({'pass_id': pass_id, 'ordinal': 0, 'before_frames': start, 'after_frames': len(script.rows),
            'sequence': nested, 'returned_object': proposal_ref['handle']})
        script.end(callback, proposal_ref)
        output = envelopes[output_id]
        for offset, obligation in enumerate(output['value']['obligations']):
            if obligation['id'] in introduced:
                output['bindings']['obligation_objects'][offset] = {
                    'kind': 'host', 'object': {'handle': introduced[obligation['id']]}}
        script.reply(sequence, envelopes[output_id])
        source_id = output_id
    script.close()
    return script.rows, graph, evidence


class DirectControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.originals = []
        cls.corpus = oracle.capture(retain=cls.originals)
        cls.temporary = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temporary.name)
        cls.receipt = {'_artifact_directory': str(cls.directory), 'artifacts': {}}
        cls.expected = cls.corpus['cases'][0]
        cls.frames, cls.actual, cls.evidence = fixture(cls.receipt, cls.expected, cls.originals[0])

    @classmethod
    def tearDownClass(cls): cls.temporary.cleanup()

    def check(self, frames=None, evidence=None, *, receipt=None, expected=None, actual=None, original=None):
        receipt = receipt or self.receipt
        channel, application = manager.declarations(); details = {}
        manager.validate_frames(frames or self.frames, manager.Artifacts(Path(receipt['_artifact_directory']), receipt['artifacts']),
            channel, application, details=details, provider_calls=True, initializer='initialize-components')
        return direct.validate_case(expected or self.expected, actual or self.actual, evidence or self.evidence,
            details, oracle, original or self.originals[0], application)

    def test_complete_valid_frame_bound_direct_control(self):
        self.assertEqual(self.check()['returns'], 3)

    def test_all_six_complete_original_graphs_and_actual_original_wrapper_chains(self):
        for expected, original in zip(self.corpus['cases'], self.originals):
            with self.subTest(case=expected['id']), tempfile.TemporaryDirectory() as directory:
                receipt = {'_artifact_directory': directory, 'artifacts': {}}
                frames, actual, evidence = fixture(receipt, expected, original)
                self.assertEqual(self.check(frames, evidence, receipt=receipt, expected=expected, actual=actual, original=original)['returns'], 3)


    def test_repaired_frames_cannot_detach_source_role_context_or_return(self):
        from biocompiler.core_client import CoreProtocolError
        changes = {
            'provider-role': 'provider role or physical handle',
            'build-kind': 'synthetic build request',
            'chained-input': 'chained source argument',
            'wrapper-result': 'another proposal object',
            'context-token': 'fixed provider or live context',
            'context-source': 'source payload capability',
            'source-record': 'historical parser source',
            'candidate-alias': 'Candidate parsed type origin census',
            'candidate-alias-collision': 'Candidate parsed types reused a node origin',
            'stale-obligation-origin': 'actual registration object origin',
            'inherited-obligation-origin': 'actual registration object origin',
            **{key: 'Complete accepted direct record' for key in ('pass-identity', 'stage', 'discharged', 'provenance', 'check')},
        }
        for change, diagnostic in changes.items():
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                receipt = {'_artifact_directory': directory, 'artifacts': {}}
                frames, actual, evidence = fixture(receipt, self.expected, self.originals[0])
                row = {'frames': frames}; receipt['checks'] = [row]
                def mutate(values):
                    commands = [value for value in values if value['kind'] == 'command']
                    replies = {value['sequence']: value for value in values if value['kind'] == 'reply'}
                    invokes = [value for value in values if value['kind'] == 'invoke']
                    first_build = next(value for value in commands if value['operation'] == 'build-result')
                    build = replies[first_build['sequence']]['outcome']['value']
                    first_run = next(value for value in commands if value['operation'] == 'run')
                    first_direct = next(value for value in commands if value['operation'] == 'call-native-provider')
                    if change == 'provider-role':
                        value = next(value for value in invokes if value['action'] == 'native-provider')
                        value['arguments']['role'] = value['arguments']['role'].replace('.producer', '.validator')
                    elif change == 'build-kind': first_build['arguments']['kind'] = 'components'
                    elif change == 'chained-input': first_run['arguments']['input_id'] = 'mechanism'
                    elif change == 'context-token': first_direct['arguments']['context_id'] = 'context/998'
                    elif change == 'context-source':
                        value = next(value for value in invokes if value['action'] == 'hydrate-context')
                        value['arguments']['bindings']['input']['identity'] = 'view/9998'
                    elif change == 'source-record':
                        inspection = next(value for value in commands if value['operation'] == 'inspect-ordered')
                        build['sources']['candidate'] = deepcopy(replies[inspection['sequence']]['outcome']['value']['snapshot']['records']['behavior'])
                    elif change == 'candidate-alias': build['view']['aliases'].pop()
                    elif change == 'candidate-alias-collision':
                        aliases = [value for value in build['view']['aliases'] if value['paths'][0][0] == 'candidate']
                        aliases[1]['binding']['identity'] = aliases[0]['binding']['identity']
                    elif change in ('stale-obligation-origin', 'inherited-obligation-origin'):
                        initial = next(value for value in commands if value['operation'] == 'register'
                            and value['parent_invocation'] is not None and value['arguments']['obligation_objects'])
                        declaration = initial['arguments']['contract']['introduces'][0]
                        runs = [value for value in commands if value['operation'] == 'run']
                        owner = runs[1 if change == 'stale-obligation-origin' else 2]
                        record = replies[owner['sequence']]['outcome']['value']
                        offset = next(index for index, item in enumerate(record['value']['obligations'])
                            if item['id'] == declaration['id'])
                        record['bindings']['obligation_objects'][offset] = {
                            'kind': 'host', 'object': deepcopy(initial['arguments']['obligation_objects'][0])}
                    elif change in ('pass-identity', 'stage', 'discharged', 'provenance', 'check'):
                        accepted = replies[first_run['sequence']]['outcome']['value']
                        if change == 'pass-identity': accepted['value']['pass_identity'] = '0'*64
                        elif change == 'stage': accepted['value']['stage'] = 'components'
                        elif change == 'discharged': accepted['value']['discharged'] = []
                        elif change == 'provenance':
                            accepted['value']['provenance']['search'] = 'forged'
                            from biocompiler.core_pipeline_manager import _ordered
                            accepted['bindings']['provenance']['tree'] = _ordered(accepted['value']['provenance'])
                        else:
                            check = next(iter(accepted['value']['checks'].values()))
                            check['subject'] = '0'*64
                            from biocompiler.core_pipeline_manager import _ordered
                            accepted['bindings']['checks']['tree'] = _ordered(accepted['value']['checks'])
                # Keep the callback mutation explicit: its local witness retains
                # the actual returned object, while only the valid frame changes.
                if change == 'wrapper-result':
                    def mutate(values):
                        invocation = next(value for value in values if value['kind'] == 'invoke' and value['action'] == 'call-provider')
                        reply = next(value for value in values if value['kind'] == 'continue' and value['invocation_id'] == invocation['invocation_id'])
                        reply['outcome']['value'] = {'handle': 'object/9998'}
                reframe(receipt, row, mutate)
                # Transport integrity is independently valid after every edit.
                details = {}; channel, application = manager.declarations()
                manager.validate_frames(row['frames'], manager.Artifacts(Path(directory), receipt['artifacts']),
                    channel, application, details=details, provider_calls=True, initializer='initialize-components')
                with self.assertRaises((AssertionError, CoreProtocolError)) as failure:
                    direct.validate_case(self.expected, actual, evidence, details, oracle, self.originals[0], application)
                chain, error = [], failure.exception
                while error is not None:
                    chain.append(str(error)); error = error.__cause__
                self.assertRegex(' | '.join(chain), diagnostic)

    def test_source_capability_cannot_be_used_before_actual_origin_return(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = {'_artifact_directory': directory, 'artifacts': {}}
            frames, actual, evidence = fixture(receipt, self.expected, self.originals[0], late_origin=True)
            with self.assertRaisesRegex(AssertionError, 'before its actual native origin return'):
                self.check(frames, evidence, receipt=receipt, actual=actual)

    def test_complete_six_process_front_gate_and_cross_campaign_identity_census(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            receipt = {'_artifact_directory': directory, 'artifacts': {}, 'direct_checks': [],
                'native_inputs': {'sha256': {'biocompiler-core': 'a'*64}}}
            put = lambda value: manager.artifact(receipt, manager.canonical(value))
            guard = sorted([['biocompiler.core_pipeline_manager', 'CorePassManager.'+name] for name in
                ('_fixed', 'from_components', 'build_result', 'inspection_state', '_native_return')] + [
                ['biocompiler.core_pipeline_callback_session', 'CorePipelineCallbackSession.__init__'],
                ['biocompiler.core_pipeline_callback_session', 'CorePipelineCallbackSession.call'],
                ['biocompiler.pipeline_callback_objects', 'CallbackObjects.execute']])
            for index, (expected, original) in enumerate(zip(self.corpus['cases'], self.originals)):
                frames, actual, evidence = fixture(receipt, expected, original)
                receipt['direct_checks'].append({'id': expected['id'], 'frames': frames,
                    'actual': put(actual), 'evidence': put(evidence), 'pid': 500+index, 'returncode': 0,
                    'closed': True, 'invalidated': False, 'executable_sha256': 'a'*64,
                    'stderr': put({'hex': ''}), 'guard': put(guard_with_routes(receipt, guard, frames)), 'after_close': put({
                        'type': 'CoreProtocolError', 'message': 'Callback session is closed; it cannot reconnect',
                        'traffic_unchanged': True, 'pid_unchanged': True})})
            artifacts = manager.Artifacts(Path(directory), receipt['artifacts'])
            sessions, pids = set(), set()
            result = direct.validate(receipt, SimpleNamespace(build=self.corpus), oracle, artifacts, sessions, pids, originals=self.originals)
            self.assertEqual(len(result), 6)
            self.assertEqual((len(sessions), len(pids)), (6, 6))
            for field, value in (('pid', 42), ('executable_sha256', 'b'*64), ('returncode', 1), ('invalidated', True)):
                previous = receipt['direct_checks'][0][field]
                receipt['direct_checks'][0][field] = value
                with self.subTest(field=field), self.assertRaisesRegex(AssertionError, 'process authority or lifecycle'):
                    direct.validate(receipt, SimpleNamespace(build=self.corpus), oracle, artifacts, set(), {42}, originals=self.originals)
                receipt['direct_checks'][0][field] = previous
            receipt['direct_checks'].pop()
            with self.assertRaisesRegex(AssertionError, 'Incomplete six'):
                direct.validate(receipt, SimpleNamespace(build=self.corpus), oracle, artifacts, set(), set(), originals=self.originals)

    def test_actual_graph_and_call_observations_are_required_whole(self):
        for field in ('build_sequences', 'calls', 'providers', 'arguments'):
            evidence = deepcopy(self.evidence)
            evidence[field] = [] if type(evidence[field]) is list else {}
            with self.subTest(field=field), self.assertRaises((AssertionError, KeyError)):
                self.check(evidence=evidence)
        actual = deepcopy(self.actual)
        actual['nodes'][0]['class'] = 'invented.Class'
        with self.assertRaisesRegex(AssertionError, 'Complete actual direct graph'):
            self.check(actual=actual)


if __name__ == '__main__': unittest.main()
