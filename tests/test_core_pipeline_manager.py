"""Typed adapter mechanics; native semantic parity is a separate installed gate."""
from copy import deepcopy
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
import unittest
from unittest.mock import patch

from biocompiler.artifacts.provenance import SourceLink
from biocompiler.compiler.passes import PassResult
from biocompiler.compiler.pipeline import (
    ArtifactStatus, CheckDecision, CompletionProfile, ComponentInputContract, NoCandidateFound, PassContext,
    PassManager, PipelineError, PipelineResult, StageRecord,
)
from biocompiler.core_client import CoreClient, CoreProtocolError
from biocompiler.core_pipeline_callback_session import CallbackRejected
from biocompiler.core_pipeline_manager import CorePassManager, ManagerInspection, _ordered, capability_profile
from biocompiler.core_pipeline_session import encode_document
from biocompiler.ir.intent import freeze_json
from biocompiler.ir.stages import Stage
from biocompiler.verification.evidence import CheckOutcome
from tests import test_pipeline as pipeline_fixtures


class FixtureSession:
    """Returns test-authored views; deliberately implements no manager semantics."""
    instances = []

    def __init__(self, core, *, application, objects, invocation_handler, **options):
        self.core, self.application, self.objects, self.handler = core, application, objects, invocation_handler
        self.requests, self.results = [], {}
        self.closed = self.invalidated = False
        self.instances.append(self)

    def call(self, operation, arguments):
        self.requests.append((operation, arguments))
        if operation.startswith('initialize-'):
            value = {'kind': operation.removeprefix('initialize-'), 'manager': True, 'artifacts': [],
                'target': {'value': arguments.get('target'),
                           'binding': {'kind': 'host', 'object': arguments['target_object']}}}
        else:
            value = self.results.get(operation)
            if isinstance(value, BaseException):
                raise value
            if callable(value):
                value = value(arguments)
        return SimpleNamespace(result=value)

    def close(self):
        self.closed = True

    def _invalidate(self):
        self.closed = self.invalidated = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class CorePipelineManagerTests(unittest.TestCase):
    def setUp(self):
        FixtureSession.instances.clear()
        self.patch = patch('biocompiler.core_pipeline_manager.CorePipelineCallbackSession', FixtureSession)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.fixture = pipeline_fixtures.PipelineTests()
        self.fixture.setUp()
        self.core = CoreClient(Path('/fixture/core'))
        self.manager = CorePassManager(self.core, target=self.fixture.target,
            dependencies={'zeta': 'a' * 64, 'request': 'b' * 64, 'alpha': 'c' * 64})
        self.addCleanup(self.manager.close)
        self.session = self.manager.session
        self.counter = 0

    def host(self, value):
        return {'kind': 'host', 'object': self.manager._objects.retain(value)}

    def native(self, value, identity=None):
        self.counter += 1
        return {'kind': 'native', 'identity': identity or 'view/' + str(self.counter), 'tree': _ordered(value)}

    def record(self, *, identity='input', payload=None, obligations=None, requirements=None, dependencies=None):
        payload = freeze_json({'schema_version': 'intent.v1', 'zeta': 1, 'alpha': 2}) if payload is None else payload
        obligations = (self.fixture.exact, self.fixture.biological) if obligations is None else obligations
        requirements = ('zeta', 'alpha') if requirements is None else requirements
        dependencies = freeze_json({'zeta': 'a' * 64, 'request': 'b' * 64}) if dependencies is None else dependencies
        checks, provenance = {'z_check': {'outcome': 'pass'}, 'a_check': {'outcome': 'pass'}}, {'authority': 'test fixture', 'zeta': 1, 'alpha': 2}
        record = StageRecord(identity, Stage.INTENT, payload, requirements, obligations, (), dependencies,
            None, None, None, freeze_json(checks), freeze_json(provenance), True)
        return {'value': record.to_dict(), 'bindings': {
            'record_id': 'record/' + identity, 'payload': self.host(payload), 'requirements': self.host(requirements),
            'dependencies': self.host(dependencies), 'obligations': self.host(obligations),
            'obligation_objects': [self.host(item) for item in obligations],
            'checks': self.native(checks), 'provenance': self.native(provenance)}}

    def context(self, *, identity, payload, requirements, dependencies, configuration, output=None, links=None, observation=None):
        bindings = {'input': self.host(payload), 'output': None if output is None else self.host(output),
            'target': self.host(self.fixture.target), 'requirements': self.host(requirements),
            'dependencies': self.host(dependencies), 'configuration': self.host(configuration),
            'source_links': None if links is None else self.host(links),
            'observation_map': self.native({}) if observation is None else self.host(observation)}
        document = {'input': {}, 'output': None, 'target': self.fixture.target.to_dict(), 'requirements': [],
            'dependencies': {}, 'configuration': {}, 'source_links': [], 'observation_map': {}}
        return {'context_id': identity, 'document': document, 'bindings': bindings}

    def hydrate(self, arguments):
        completion = self.manager._invoke('hydrate-context', arguments)
        self.assertEqual(completion.status, 'ok')
        return self.manager._objects.resolve(completion.value)

    def inspection(self, producer, validator, *, producer_id='provider/producer', validator_id='provider/validator'):
        registration = {'contract': self.fixture.first.to_dict(), 'producer': producer_id,
            'validators': {'alpha': validator_id, 'zeta': validator_id}}
        admission = {'contract': {'id': 'admission'}, 'validators': {'alpha': validator_id, 'zeta': validator_id}}
        snapshot = {'target': self.fixture.target.to_dict(), 'dependencies': {'alpha': 'a' * 64, 'zeta': 'b' * 64},
            'passes': {'a': registration, 'z': registration}, 'component_inputs': {'policy': admission},
            'provider_history': {'a-history': registration, 'z-history': registration},
            'component_input_history': {'admission-history': admission}, 'records': {'input': self.record()},
            'profiles': {}}
        order = {key: list(value) for key, value in snapshot.items() if key != 'target'}
        order.update(dependencies=['zeta', 'alpha'], passes=['z', 'a'], provider_history=['z-history', 'a-history'],
            combined_provider_history=['z-history', ['component_input', 'admission-history'], 'a-history'],
            validators={field: {key: ['zeta', 'alpha'] for key in snapshot[field]}
                for field in ('passes', 'component_inputs', 'provider_history', 'component_input_history')})
        return {'snapshot': snapshot, 'order': order, 'providers': [
            {'provider_id': producer_id, 'object': self.manager._objects.retain(producer)},
            {'provider_id': validator_id, 'object': self.manager._objects.retain(validator)}]}

    def test_exact_application_and_constructor_do_not_initialize_python_manager(self):
        path = Path(__file__).parents[1] / 'protocol/pipeline-callback-manager-v1.json'
        self.assertEqual(encode_document(capability_profile()) + b'\n', path.read_bytes())
        self.assertIsInstance(self.manager, PassManager)
        self.assertIs(self.manager.target, self.fixture.target)
        self.assertEqual(self.session.application, capability_profile())
        operation, arguments = self.session.requests[0]
        self.assertEqual(operation, 'initialize-empty')
        self.assertEqual([item[0] for item in arguments['dependencies']], ['zeta', 'request', 'alpha'])
        self.assertIs(self.manager._objects.resolve(arguments['target_object']), self.fixture.target)
        with patch.object(PassManager, '__init__', side_effect=AssertionError('Python manager used')):
            manager = CorePassManager(self.core, target=self.fixture.target, dependencies={'request': 'b' * 64})
            manager.close()

    def test_registration_retains_actual_providers_and_mapping_without_reading_them(self):
        class Deferred(dict):
            def __iter__(self):
                raise AssertionError('eager iteration')

            def values(self):
                raise AssertionError('eager provider validation')

            def __getitem__(self, key):
                raise AssertionError('eager mapping lookup')

        producer, validators = object(), Deferred()
        self.manager.register(self.fixture.first, producer, validators)
        operation, arguments = self.session.requests[-1]
        self.assertEqual(operation, 'register')
        self.assertIs(self.manager._objects.resolve(arguments['producer']), producer)
        self.assertIs(self.manager._objects.resolve(arguments['validators']), validators)
        self.assertEqual(set(arguments), set(capability_profile()['operations']['register']['fields']))

    def test_payload_and_configuration_are_not_materialized_before_native_prefix(self):
        class Deferred:
            def to_dict(self):
                raise AssertionError('premature to_dict')

            def __iter__(self):
                raise AssertionError('premature iteration')

        error = CallbackRejected(SimpleNamespace(result={'module': 'biocompiler.compiler.pipeline', 'type': 'PipelineError',
            'message': 'Earlier native precondition failed.', 'attributes': {}}))
        self.session.results.update({'add-input': error, 'run': error})
        payload, configuration = Deferred(), Deferred()
        with self.assertRaisesRegex(PipelineError, 'Earlier native precondition'):
            self.manager.add_input('input', payload)
        self.assertIs(self.manager._objects.resolve(self.session.requests[-1][1]['payload']), payload)
        with self.assertRaisesRegex(PipelineError, 'Earlier native precondition'):
            self.manager.run('missing', 'missing', 'output', configuration=configuration)
        self.assertIs(self.manager._objects.resolve(self.session.requests[-1][1]['configuration']), configuration)
        self.assertFalse(self.session.invalidated)

    def test_record_cache_preserves_identity_but_every_get_rechecks_native_freshness(self):
        envelope = self.record()
        self.session.results['get'] = envelope
        first, second = self.manager.get('input'), self.manager.get('input')
        self.assertIs(first, second)
        self.assertIs(first.payload, self.manager._objects.resolve(envelope['bindings']['payload']['object']))
        self.assertEqual(list(first.payload), ['schema_version', 'zeta', 'alpha'])
        self.assertEqual(list(first.checks), ['z_check', 'a_check'])
        self.assertEqual(list(first.provenance), ['authority', 'zeta', 'alpha'])
        self.assertEqual([operation for operation, _ in self.session.requests].count('get'), 2)
        self.session.results['get'] = CallbackRejected(SimpleNamespace(result={
            'module': 'biocompiler.compiler.pipeline', 'type': 'PipelineError',
            'message': "Stale artifact 'input'; changed dependencies: request.", 'attributes': {}}))
        with self.assertRaisesRegex(PipelineError, 'Stale artifact'):
            self.manager.get('input')
        self.assertIs(self.manager._records['input'], first)

    def test_native_record_identity_rebinding_invalidates_channel(self):
        envelope = self.record()
        self.session.results['get'] = envelope
        self.manager.get('input')
        changed = deepcopy(envelope)
        changed['bindings']['record_id'] = 'replacement'
        self.session.results['get'] = changed
        with self.assertRaises(CoreProtocolError):
            self.manager.get('input')
        self.assertTrue(self.session.invalidated)

    def test_contexts_share_fields_and_source_tuple_but_not_producer_identity(self):
        payload, output = freeze_json({'schema_version': 'intent.v1'}), freeze_json({'schema_version': 'behavior.v1'})
        requirements, dependencies = ('zeta', 'alpha'), freeze_json({'zeta': 'a' * 64, 'alpha': 'b' * 64})
        configuration, observation = freeze_json({'zeta': 1, 'alpha': 2}), freeze_json({'zeta': 'node', 'alpha': 'node'})
        links = (SourceLink('zeta', 'node', 'node', 'pass'), SourceLink('alpha', 'node', 'node', 'pass'))
        producer_args = self.context(identity='context/producer', payload=payload, requirements=requirements,
            dependencies=dependencies, configuration=configuration)
        validator_args = self.context(identity='context/validator', payload=payload, requirements=requirements,
            dependencies=dependencies, configuration=configuration, output=output, links=links, observation=observation)
        producer, validator, repeat = self.hydrate(producer_args), self.hydrate(validator_args), self.hydrate(validator_args)
        self.assertIs(type(producer), PassContext)
        self.assertIsNot(producer, validator)
        self.assertIs(validator, repeat)
        for name in ('input', 'target', 'requirements', 'dependencies', 'configuration'):
            self.assertIs(getattr(producer, name), getattr(validator, name))
        self.assertIs(validator.target, self.fixture.target)
        self.assertIs(validator.source_links, links)
        self.assertIs(validator.output, output)
        self.assertIs(validator.observation_map, observation)
        self.assertIs(type(producer.observation_map), dict)
        producer.observation_map['local mutation'] = True
        self.assertIs(self.hydrate(producer_args).observation_map, producer.observation_map)
        self.assertEqual(producer.observation_map, {'local mutation': True})

    def test_equal_native_values_with_different_identity_do_not_coalesce(self):
        first = self.native({'zeta': [1], 'alpha': 2}, 'view/first')
        second = self.native({'zeta': [1], 'alpha': 2}, 'view/second')
        left, right = self.manager._binding(first), self.manager._binding(second)
        self.assertEqual(left, right)
        self.assertIsNot(left, right)
        self.assertIs(left, self.manager._binding(first))
        self.assertEqual(list(left), ['zeta', 'alpha'])
        changed = deepcopy(first)
        changed['tree'][1].reverse()
        with self.assertRaisesRegex(CoreProtocolError, 'rebound'):
            self.manager._binding(changed)

    def test_whole_obligation_tuple_and_original_elements_survive_result(self):
        obligations = (self.fixture.exact, self.fixture.biological)
        envelope = self.record(obligations=obligations)
        self.session.results['get'] = envelope
        record = self.manager.get('input')
        self.assertIs(record.obligations, obligations)
        value = {'status': 'partial', 'artifact': envelope['value'], 'scope': 'therapeutic',
                 'unresolved': [item.to_dict() for item in obligations]}
        self.session.results['result'] = {'value': value, 'artifact': envelope}
        first, second = self.manager.result('input', scope='therapeutic'), self.manager.result('input', scope='therapeutic')
        self.assertIs(type(first), PipelineResult)
        self.assertIs(first.status, ArtifactStatus.PARTIAL)
        self.assertIsNot(first, second)
        self.assertIs(first.artifact, record)
        self.assertTrue(all(left is right for left, right in zip(first.unresolved, obligations)))

    def test_application_actions_preserve_set_effects_and_actual_exception(self):
        events = []
        error = ValueError('iterator failed')

        class Values:
            def __iter__(self):
                events.append('iter')
                yield 'first'
                raise error

        completion = self.manager._invoke('set-equal', {'object': self.manager._objects.retain(Values()), 'values': ['first']})
        self.assertEqual(events, ['iter'])
        self.assertEqual(completion.status, 'exception')
        caught = None
        try:
            self.manager._objects.rethrow(completion.value['exception_token'])
        except ValueError as current:
            caught = current
        self.assertIs(caught, error)
        links = [SourceLink('r', 's', 't', 'p')]
        completion = self.manager._invoke('source-link-set-equal', {
            'objects': [self.manager._objects.retain(item) for item in links], 'expected': [vars(item) for item in links]})
        self.assertEqual(completion.value, True)

    def test_ordered_json_retains_every_mapping_order_and_scalar_kind(self):
        value = freeze_json({'zeta': {'omega': 1, 'alpha': 1.0}, 'alpha': [True, None]})
        completion = self.manager._invoke('ordered-json', {'object': self.manager._objects.retain(value)})
        self.assertEqual(completion.status, 'ok')
        tree = completion.value
        self.assertEqual([item[0] for item in tree[1]], ['zeta', 'alpha'])
        self.assertEqual([item[0] for item in tree[1][0][1][1]], ['omega', 'alpha'])
        self.assertIs(type(tree[1][0][1][1][0][1][1]), int)
        self.assertIs(type(tree[1][0][1][1][1][1][1]), float)

    def test_native_proxy_tokens_are_stable_and_accept_only_original_context(self):
        args = self.context(identity='context/test', payload=freeze_json({}), requirements=(),
            dependencies=freeze_json({}), configuration=freeze_json({}))
        context = self.hydrate(args)
        first = self.manager._objects.resolve(self.manager._invoke('native-provider', {'provider_id': 'provider/native'}).value)
        second = self.manager._objects.resolve(self.manager._invoke('native-provider', {'provider_id': 'provider/native'}).value)
        self.assertIs(first, second)
        reference = self.manager._invoke('provider-reference', {'object': self.manager._objects.retain(first)})
        self.assertEqual(reference.value, {'kind': 'native', 'provider_id': 'provider/native'})
        self.session.results['call-native-provider'] = {'kind': 'decision', 'value': {'outcome': 'pass', 'detail': 'Native fixture', 'evidence': {}}}
        decision = first(context)
        self.assertIs(type(decision), CheckDecision)
        self.assertIs(decision.outcome, CheckOutcome.PASS)
        self.assertEqual(self.session.requests[-1], ('call-native-provider', {'provider_id': 'provider/native', 'context_id': 'context/test'}))
        with self.assertRaises(CoreProtocolError):
            first(PassContext({}, None, self.fixture.target, {}, {}, ()))

    def test_expected_native_exceptions_use_closed_classes_and_complete_attributes(self):
        value = {'module': 'biocompiler.compiler.pipeline', 'type': 'NoCandidateFound', 'message': 'Native complete message',
            'attributes': {'pass_id': 'pass', 'configuration': {'zeta': 1}, 'dependencies': {'request': 'a' * 64}}}
        self.session.results['run'] = CallbackRejected(SimpleNamespace(result=value))
        with self.assertRaises(NoCandidateFound) as caught:
            self.manager.run('pass', 'input', 'output')
        self.assertEqual(str(caught.exception), 'Native complete message')
        self.assertEqual(caught.exception.pass_id, 'pass')
        self.assertIs(type(caught.exception.configuration), MappingProxyType)
        self.assertIsNone(caught.exception.__context__)
        self.assertFalse(self.session.invalidated)
        value['module'], value['type'] = 'subprocess', 'Popen'
        self.session.results['run'] = CallbackRejected(SimpleNamespace(result=value))
        with self.assertRaises(CoreProtocolError):
            self.manager.run('pass', 'input', 'output')
        self.assertTrue(self.session.invalidated)

    def test_historical_view_does_not_reconstruct_acceptance_locally(self):
        envelope = self.record()
        envelope['value']['accepted'] = False
        self.session.results['inspect'] = {'records': {'input': envelope}}
        historical = self.manager.historical('input')
        self.assertFalse(historical.accepted)
        self.assertEqual(self.session.requests[-1], ('inspect', {}))
        self.session.results['get'] = CallbackRejected(SimpleNamespace(result={
            'module': 'biocompiler.compiler.pipeline', 'type': 'PipelineError',
            'message': 'Record was rejected.', 'attributes': {}}))
        with self.assertRaisesRegex(PipelineError, 'Record was rejected'):
            self.manager.get('input')

    def test_admission_keeps_original_contract_collection_handles(self):
        original = self.fixture.first
        contract = ComponentInputContract('admission', '1', 'components.v1', original.checks,
            ('requirement',), (self.fixture.exact,), ('request',))
        validators = {'check': object()}
        self.manager.register_component_input(contract, validators)
        operation, arguments = self.session.requests[-1]
        self.assertEqual(operation, 'register-component-input')
        self.assertEqual(set(arguments), set(capability_profile()['operations'][operation]['fields']))
        self.assertIs(self.manager._objects.resolve(arguments['requirements_object']), contract.requirements)
        self.assertIs(self.manager._objects.resolve(arguments['obligations_object']), contract.obligations)
        self.assertIs(self.manager._objects.resolve(arguments['validators']), validators)

    def test_fixed_initializers_preserve_different_history_materialization_order(self):
        events = []
        def deferred_history():
            events.append('iterated')
            yield object()

        events.clear()
        with self.assertRaisesRegex(TypeError, 'RealizationRequest'):
            CorePassManager.from_synthetic(self.core, object(), deferred_history())
        self.assertEqual(events, [])
        with self.assertRaisesRegex(TypeError, 'RealizationRequest'):
            CorePassManager.from_components(self.core, object(), deferred_history())
        self.assertEqual(events, ['iterated'])

    def test_custom_contract_subclass_is_explicitly_unsupported_before_conversion(self):
        class Custom(type(self.fixture.first)):
            def to_dict(self):
                raise AssertionError('Custom authoring semantics must not be silently canonicalized')

        instance = object.__new__(Custom)
        for key, value in vars(self.fixture.first).items():
            object.__setattr__(instance, key, value)
        with self.assertRaisesRegex(CoreProtocolError, 'Custom pass contract'):
            self.manager.register(instance, object(), {})
        self.assertFalse(self.session.invalidated)

    def test_native_proposal_view_has_typed_wrapper_without_python_acceptance(self):
        value = {'kind': 'proposal', 'value': {'output': {'schema_version': 'behavior.v1', 'nodes': []},
            'obligations': [], 'source_links': [{'requirement_id': 'r', 'source_node_id': 's',
                'target_node_id': 't', 'pass_name': 'p'}], 'observation_map': {}, 'search_status': 'candidate'}}
        result = self.manager._native_return(value)
        self.assertIs(type(result), PassResult)
        self.assertIs(type(result.output), MappingProxyType)
        self.assertIs(type(result.source_links[0]), SourceLink)
        self.assertEqual(result.search_status, 'candidate')

    def test_native_obligation_elements_are_typed_without_legacy_post_init(self):
        value = self.fixture.exact.to_dict()
        binding = self.native(value, 'obligation/exact')
        with patch.object(type(self.fixture.exact), '__post_init__', side_effect=AssertionError('Python semantic constructor')):
            observed = self.manager._binding(binding, flavor='obligation')
        self.assertIs(type(observed), type(self.fixture.exact))
        self.assertEqual(observed.to_dict(), value)
        self.assertIs(observed, self.manager._binding(binding, flavor='obligation'))

    def test_regular_list_obligations_make_tuple_view_without_changing_elements(self):
        obligations = [self.fixture.exact, self.fixture.biological]
        envelope = self.record(obligations=obligations)
        self.session.results['get'] = envelope
        first = self.manager.get('input')
        self.assertIs(type(first.obligations), tuple)
        self.assertTrue(all(left is right for left, right in zip(first.obligations, obligations)))
        self.assertIs(self.manager.get('input').obligations, first.obligations)

    def test_malformed_result_binding_closes_authority_without_observing_host_fields(self):
        envelope = self.record()
        original = {'status': 'partial', 'artifact': envelope['value'], 'scope': 'therapeutic',
            'unresolved': [item.to_dict() for item in (self.fixture.exact, self.fixture.biological)]}
        mutations = []
        changed = deepcopy(original)
        changed['unresolved'][0]['description'] = 'Different meaning under the same identifier'
        mutations.append(changed)
        changed = deepcopy(original)
        changed['unresolved'].append(changed['unresolved'][0])
        mutations.append(changed)
        changed = deepcopy(original)
        changed['unresolved'][0]['id'] = 'unknown'
        mutations.append(changed)
        changed = deepcopy(original)
        changed['status'] = 'unrecognized'
        mutations.append(changed)
        for value in mutations:
            with self.subTest(value=value):
                self.session.invalidated = False
                self.session.results['result'] = {'value': value, 'artifact': envelope}
                with self.assertRaises(CoreProtocolError):
                    self.manager.result('input', scope='therapeutic')
                self.assertTrue(self.session.invalidated)

    def test_malformed_unit_provider_and_inspection_views_close_authority(self):
        self.session.results['set-dependency'] = {'unexpected': True}
        with self.assertRaises(CoreProtocolError):
            self.manager.set_dependency('request', 'a' * 64)
        self.assertTrue(self.session.invalidated)
        self.session.invalidated = False
        with self.assertRaises(CoreProtocolError):
            self.manager._native_return({'kind': 'decision', 'value': {'outcome': 'undeclared-outcome', 'detail': 'x', 'evidence': {}}})
        self.assertTrue(self.session.invalidated)
        self.session.invalidated = False
        self.session.results['inspect'] = {'records': None}
        with self.assertRaises(CoreProtocolError):
            self.manager.historical('input')
        self.assertTrue(self.session.invalidated)

    def test_ordered_inspection_preserves_actual_provider_identity_and_declared_orders(self):
        class Provider:
            def __call__(self, context):
                raise AssertionError('Inspection called the provider')

            def __eq__(self, other):
                raise AssertionError('Inspection compared provider values')

            def __hash__(self):
                raise AssertionError('Inspection hashed a provider')

        producer, validator = Provider(), Provider()
        raw = self.inspection(producer, validator)
        self.session.results['inspect-ordered'] = raw
        observed = self.manager.inspect_ordered()
        self.assertIs(type(observed), ManagerInspection)
        self.assertEqual(self.session.requests[-1], ('inspect-ordered', {}))
        self.assertIs(observed.providers['provider/producer'], producer)
        self.assertIs(observed.providers['provider/validator'], validator)
        self.assertEqual(tuple(observed.snapshot['dependencies']), ('zeta', 'alpha'))
        self.assertEqual(tuple(observed.snapshot['passes']), ('z', 'a'))
        self.assertEqual(tuple(observed.snapshot['passes']['a']['validators']), ('zeta', 'alpha'))
        self.assertEqual(observed.order['combined_provider_history'],
            ('z-history', ('component_input', 'admission-history'), 'a-history'))
        self.assertEqual(set(observed.snapshot['records']['input']), {'value', 'bindings'})
        with self.assertRaises(TypeError):
            observed.providers['provider/producer'] = validator
        with self.assertRaises(TypeError):
            observed.snapshot['dependencies']['zeta'] = 'changed'
        self.assertIs(self.manager.inspect_ordered().providers['provider/producer'], producer)

    def test_distinct_equal_bound_methods_keep_distinct_native_tokens(self):
        class Owner:
            def provider(self, context):
                return context

        owner = Owner()
        left, right = owner.provider, owner.provider
        self.assertIsNot(left, right)
        self.assertEqual(left, right)
        self.session.results['inspect-ordered'] = self.inspection(left, right)
        observed = self.manager.inspect_ordered()
        self.assertIs(observed.providers['provider/producer'], left)
        self.assertIs(observed.providers['provider/validator'], right)

    def test_ordered_inspection_rejects_incomplete_orders_and_provider_census(self):
        producer, validator = lambda context: context, lambda context: context
        original = self.inspection(producer, validator)
        mutations = []
        raw = deepcopy(original); raw['order']['dependencies'] = ['zeta', 'zeta']; mutations.append(raw)
        raw = deepcopy(original); raw['order']['validators']['passes']['a'] = ['zeta']; mutations.append(raw)
        raw = deepcopy(original); raw['order']['combined_provider_history'].reverse(); mutations.append(raw)
        raw = deepcopy(original); raw['order']['combined_provider_history'][1][0] = 'component-input'; mutations.append(raw)
        raw = deepcopy(original); raw['providers'].pop(); mutations.append(raw)
        raw = deepcopy(original); raw['providers'].append(raw['providers'][0]); mutations.append(raw)
        raw = deepcopy(original); raw['providers'][0]['provider_id'] = 'provider/extra'; mutations.append(raw)
        raw = deepcopy(original); raw['providers'][1]['object'] = raw['providers'][0]['object']; mutations.append(raw)
        raw = deepcopy(original); raw['snapshot']['records'] = {'wrong': raw['snapshot']['records']['input']}
        raw['order']['records'] = ['wrong']; mutations.append(raw)
        for raw in mutations:
            with self.subTest(raw=raw):
                self.session.invalidated = False
                self.session.results['inspect-ordered'] = raw
                with self.assertRaises(CoreProtocolError):
                    self.manager.inspect_ordered()
                self.assertTrue(self.session.invalidated)

    def test_provider_bijection_survives_absence_and_rejects_rebinding(self):
        producer, validator = lambda context: context, lambda context: context
        original = self.inspection(producer, validator)
        self.session.results['inspect-ordered'] = original
        self.manager.inspect_ordered()
        empty = deepcopy(original)
        for name in ('passes', 'component_inputs', 'provider_history', 'component_input_history'):
            empty['snapshot'][name] = {}
            empty['order'][name] = []
            empty['order']['validators'][name] = {}
        empty['order']['combined_provider_history'] = []
        empty['providers'] = []
        self.session.results['inspect-ordered'] = empty
        self.manager.inspect_ordered()
        changed = deepcopy(original)
        changed['providers'][0]['object'] = self.manager._objects.retain(lambda context: context)
        self.session.results['inspect-ordered'] = changed
        with self.assertRaises(CoreProtocolError):
            self.manager.inspect_ordered()
        self.assertTrue(self.session.invalidated)

    def test_inspection_resolves_existing_native_proxy_without_copying_it(self):
        completion = self.manager._invoke('native-provider', {'provider_id': 'provider/producer'})
        proxy = self.manager._objects.resolve(completion.value)
        self.session.results['inspect-ordered'] = self.inspection(proxy, lambda context: context)
        self.assertIs(self.manager.inspect_ordered().providers['provider/producer'], proxy)


if __name__ == '__main__':
    unittest.main()
