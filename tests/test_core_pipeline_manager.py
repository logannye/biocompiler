"""Typed adapter mechanics; native semantic parity is a separate installed gate."""
from copy import deepcopy
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
import unittest
from unittest.mock import patch

from biocompiler.artifacts.provenance import SourceLink
from biocompiler.compiler.passes import PassResult
from biocompiler.compiler.pipeline import (
    ArtifactStatus, CheckDecision, CheckSpec, CompletionProfile, ComponentInputContract, NoCandidateFound, PassContext,
    PassContract, PassManager, PipelineError, PipelineResult, ScopedObligation, StageRecord,
)
from biocompiler.core_client import CoreClient, CoreProtocolError
from biocompiler.core_pipeline_callback_session import CallbackRejected
from biocompiler.core_pipeline_manager import CorePassManager, ComponentPreparation, ManagerInspection, _ordered, capability_profile
from biocompiler.core_pipeline_session import decode_document, encode_document
from biocompiler.ir.intent import freeze_json
from biocompiler.ir.behavior import BehaviorProgram
from biocompiler.ir.stages import Stage
from biocompiler.verification.evidence import CheckOutcome
from tests import test_pipeline as pipeline_fixtures


def provider_result(kind, value, role):
    return {'kind': kind, 'value': value, 'view': {'role': role, 'tree': _ordered(value), 'bindings': {}, 'aliases': []}}


class FixtureSession:
    """Returns test-authored views; deliberately implements no manager semantics."""
    instances = []

    def __init__(self, core, *, application, objects, invocation_handler, **options):
        self.core, self.application, self.objects, self.handler = core, application, objects, invocation_handler
        self.requests, self.results = [], {}
        self.closed = self.invalidated = False
        self.last_response = None
        self.instances.append(self)

    def call(self, operation, arguments):
        self.requests.append((operation, arguments))
        if operation.startswith('initialize-'):
            value = {'kind': operation.removeprefix('initialize-'), 'manager': True, 'artifacts': [],
                'target': {'value': arguments.get('target', arguments.get('request', {}).get('build_request', {}).get('target')),
                           'binding': {'kind': 'host', 'object': arguments['target_object']}}}
        else:
            value = self.results.get(operation)
            if isinstance(value, BaseException):
                raise value
            if callable(value):
                value = value(arguments)
        self.last_response = SimpleNamespace(result=value, sequence=len(self.requests))
        return self.last_response

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
            'message': 'Earlier native precondition failed.', 'attributes': {}, 'attributes_tree': ['object', []]}))
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
            'message': "Stale artifact 'input'; changed dependencies: request.", 'attributes': {}, 'attributes_tree': ['object', []]}))
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
        first = self.manager._objects.resolve(self.manager._invoke('native-provider', {'provider_id': 'provider/native', 'role': 'intent_to_behavior.validator'}).value)
        second = self.manager._objects.resolve(self.manager._invoke('native-provider', {'provider_id': 'provider/native', 'role': 'intent_to_behavior.validator'}).value)
        self.assertIs(first, second)
        reference = self.manager._invoke('provider-reference', {'object': self.manager._objects.retain(first)})
        self.assertEqual(reference.value, {'kind': 'native', 'provider_id': 'provider/native'})
        self.session.results['call-native-provider'] = provider_result('decision', {'outcome': 'pass', 'detail': 'Native fixture', 'evidence': {}}, 'intent_to_behavior.validator')
        decision = first(context)
        self.assertIs(type(decision), CheckDecision)
        self.assertIs(decision.outcome, CheckOutcome.PASS)
        self.assertEqual(self.session.requests[-1], ('call-native-provider', {'provider_id': 'provider/native', 'context_id': 'context/test'}))
        with self.assertRaises(CoreProtocolError):
            first(PassContext({}, None, self.fixture.target, {}, {}, ()))

    def test_native_proxy_role_cannot_be_rebound_or_inferred_from_reply(self):
        self.manager._invoke('native-provider', {'provider_id': 'provider/native', 'role': 'intent_to_behavior.producer'})
        with self.assertRaisesRegex(CoreProtocolError, 'role was rebound'):
            self.manager._invoke('native-provider', {'provider_id': 'provider/native', 'role': 'behavior_to_synthetic.producer'})
        with self.assertRaisesRegex(CoreProtocolError, 'closure role'):
            self.manager._invoke('native-provider', {'provider_id': 'provider/other', 'role': 'caller_selected.constructor'})
        value = provider_result('decision', {'outcome': 'pass', 'detail': 'valid fields', 'evidence': {}}, 'intent_to_behavior.validator')
        with self.assertRaises(CoreProtocolError):
            self.manager._native_return(value, role='intent_to_behavior.producer')
        self.assertTrue(self.session.invalidated)

    def test_fixed_initializer_retains_actual_request_and_config_once(self):
        from tools.capture_pipeline_fixed_provider_semantics import authority
        request, history, until, config = authority('static:requested')
        original = config.to_dict
        original_request = request.to_dict
        with patch.object(type(config), 'to_dict', autospec=True, side_effect=lambda value: original()) as serialize, \
                patch.object(type(request), 'to_dict', autospec=True, side_effect=lambda value: original_request()) as serialize_request:
            manager = CorePassManager.from_components(self.core, request, history, until=until, config=config)
        self.addCleanup(manager.close)
        self.assertEqual(serialize.call_count, 1)
        self.assertEqual(serialize_request.call_count, 1)
        operation, arguments = manager.session.requests[0]
        self.assertEqual(operation, 'initialize-components')
        self.assertIs(manager._objects.resolve(arguments['config_object']), config)
        self.assertIs(manager._objects.resolve(arguments['request_object']), request)
        self.assertEqual(arguments['request_tree'], _ordered(arguments['request']))
        self.assertIs(manager.target, request.target)
        completion = manager._invoke('origin-reference', {'root': 'request', 'path': ['domain', 'inputs', 0, 'observable']})
        self.assertIs(manager._objects.resolve(completion.value), request.domain.inputs[0].observable)
        self.assertEqual(manager._provider_target_document, request.target.to_dict())

    def test_default_fixed_configuration_is_structural_and_fresh(self):
        from tools.capture_pipeline_fixed_provider_semantics import authority
        from biocompiler.synthesis.synthetic import SyntheticGeneratorConfig
        request, history, until, _ = authority('static:requested')
        expected = SyntheticGeneratorConfig().to_dict()
        with patch.object(SyntheticGeneratorConfig, '__init__', side_effect=AssertionError('Legacy config constructor')), \
                patch('biocompiler.synthesis.synthetic.catalog_for_profile', side_effect=AssertionError('Legacy catalog resolution')):
            first = CorePassManager.from_components(self.core, request, history, until=until)
            second = CorePassManager.from_synthetic(self.core, request, history, until=until)
        self.addCleanup(first.close)
        self.addCleanup(second.close)
        for manager in (first, second):
            self.assertEqual(manager.session.requests[0][1]['config'], expected)
            self.assertEqual(manager._provider_config.to_dict(), expected)
            self.assertIs(type(manager._provider_config), SyntheticGeneratorConfig)
        self.assertIsNot(first._provider_config, second._provider_config)

    def test_expected_native_exceptions_use_closed_classes_and_complete_attributes(self):
        value = {'module': 'biocompiler.compiler.pipeline', 'type': 'NoCandidateFound', 'message': 'Native complete message',
            'attributes': {'pass_id': 'pass', 'configuration': {'zeta': 1}, 'dependencies': {'request': 'a' * 64}}}
        value['attributes_tree'] = _ordered(value['attributes'])
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

    def test_no_candidate_snapshots_keep_order_kinds_and_independent_identity(self):
        configuration = freeze_json({'zeta': [{'integer': 1, 'float': 1.0, 'boolean': True,
            'nothing': None, 'text': 'a'}], 'alpha': {'last': 2, 'first': 3}})
        dependencies = freeze_json({'request': 'a' * 64, 'registry': 'b' * 64, 'target': 'c' * 64})
        context_configuration = self.manager._binding(self.native(configuration, 'snapshot/configuration'))
        context_dependencies = self.manager._binding(self.native(dependencies, 'snapshot/dependencies'))
        attributes = {'pass_id': 'pass', 'configuration': {'zeta': [{'integer': 1, 'float': 1.0,
            'boolean': True, 'nothing': None, 'text': 'a'}], 'alpha': {'last': 2, 'first': 3}},
            'dependencies': dict(dependencies)}
        descriptor = {'module': 'biocompiler.compiler.pipeline', 'type': 'NoCandidateFound',
            'message': 'Native complete message', 'attributes': decode_document(encode_document(attributes)),
            'attributes_tree': _ordered(attributes)}
        cache = dict(self.manager._bindings)
        errors = []
        for _ in range(2):
            self.session.results['run'] = CallbackRejected(SimpleNamespace(result=descriptor))
            with self.assertRaises(NoCandidateFound) as caught:
                self.manager.run('pass', 'input', 'output')
            errors.append(caught.exception)
        first, second = errors
        self.assertEqual(tuple(vars(first)), ('pass_id', 'configuration', 'dependencies'))
        self.assertEqual(tuple(first.configuration), ('zeta', 'alpha'))
        self.assertEqual(tuple(first.configuration['zeta'][0]), ('integer', 'float', 'boolean', 'nothing', 'text'))
        self.assertEqual(tuple(first.configuration['alpha']), ('last', 'first'))
        self.assertEqual(tuple(first.dependencies), ('request', 'registry', 'target'))
        for name, kind in (('integer', int), ('float', float), ('boolean', bool), ('text', str)):
            self.assertIs(type(first.configuration['zeta'][0][name]), kind)
        self.assertIsNone(first.configuration['zeta'][0]['nothing'])
        self.assertIsNot(first.configuration, context_configuration)
        self.assertIsNot(first.dependencies, context_dependencies)
        self.assertIsNot(first.configuration, second.configuration)
        self.assertIsNot(first.dependencies, second.dependencies)
        self.assertIsNot(first.configuration['zeta'], second.configuration['zeta'])
        self.assertIsNot(first.configuration['zeta'][0], second.configuration['zeta'][0])
        self.assertIsNot(first.configuration['alpha'], context_configuration['alpha'])
        self.assertEqual(self.manager._bindings, cache)
        with self.assertRaises(TypeError):
            first.configuration['alpha']['last'] = 5
        self.assertFalse(self.session.invalidated)

    def test_native_exception_tree_rejects_shape_value_and_scalar_kind_disagreement(self):
        attributes = {'pass_id': 'pass', 'configuration': {'value': 1}, 'dependencies': {'request': 'a' * 64}}
        descriptor = {'module': 'biocompiler.compiler.pipeline', 'type': 'NoCandidateFound', 'message': 'Native message',
            'attributes': attributes, 'attributes_tree': _ordered(attributes)}
        def replace_attribute(value, key, item):
            value['attributes'][key] = item
            value['attributes_tree'] = _ordered(value['attributes'])
        changes = [lambda value: value.pop('attributes_tree'), lambda value: value.update(extra=None),
            lambda value: value['attributes'].update(extra=None),
            lambda value: value.update(attributes_tree=['array', []]),
            lambda value: value['attributes_tree'][1].reverse(),
            lambda value: value['attributes_tree'][1].append(value['attributes_tree'][1][0]),
            lambda value: replace_attribute(value, 'pass_id', 1),
            lambda value: replace_attribute(value, 'configuration', []),
            lambda value: replace_attribute(value, 'dependencies', {'request': 1}),
            lambda value: value['attributes_tree'][1][1][1][1][0].__setitem__(1, ['scalar', True]),
            lambda value: value['attributes_tree'][1][1][1][1][0].__setitem__(1, ['scalar', 1.0]),
            lambda value: value['attributes_tree'][1][1][1][1][0].__setitem__(1, ['scalar', float('nan')]),
            lambda value: value['attributes_tree'][1][1][1][1][0].__setitem__(1, ['scalar', {}])]
        for change in changes:
            with self.subTest(change=change):
                value = deepcopy(descriptor)
                change(value)
                with self.assertRaises(CoreProtocolError):
                    self.manager._exception(value)
        changed = deepcopy(descriptor)
        changed['attributes_tree'][1][1][1][1][0][1] = ['scalar', True]
        self.session.results['run'] = CallbackRejected(SimpleNamespace(result=changed))
        with self.assertRaisesRegex(CoreProtocolError, 'differ from their ordered tree'):
            self.manager.run('pass', 'input', 'output')
        self.assertTrue(self.session.invalidated)

    def test_other_native_exceptions_require_empty_ordered_attributes(self):
        value = {'module': 'biocompiler.compiler.pipeline', 'type': 'PipelineError',
            'message': 'Native rejection', 'attributes': {}, 'attributes_tree': ['object', []]}
        error = self.manager._exception(value)
        self.assertIs(type(error), PipelineError)
        self.assertEqual(vars(error), {})
        for tree in (['array', []], ['object', [['extra', ['scalar', None]]]]):
            with self.subTest(tree=tree), self.assertRaises(CoreProtocolError):
                self.manager._exception({**value, 'attributes_tree': tree})

    def test_historical_view_does_not_reconstruct_acceptance_locally(self):
        envelope = self.record()
        envelope['value']['accepted'] = False
        self.session.results['inspect'] = {'records': {'input': envelope}}
        historical = self.manager.historical('input')
        self.assertFalse(historical.accepted)
        self.assertEqual(self.session.requests[-1], ('inspect', {}))
        self.session.results['get'] = CallbackRejected(SimpleNamespace(result={
            'module': 'biocompiler.compiler.pipeline', 'type': 'PipelineError',
            'message': 'Record was rejected.', 'attributes': {}, 'attributes_tree': ['object', []]}))
        with self.assertRaisesRegex(PipelineError, 'Record was rejected'):
            self.manager.get('input')

    def test_typed_inspection_state_preserves_shapes_order_and_actual_identities(self):
        class ActualProvider:
            def __call__(self, context):
                raise AssertionError('Inspection called provider')
            def __eq__(self, other):
                raise AssertionError('Inspection compared provider')
            def __hash__(self):
                raise AssertionError('Inspection hashed provider')
        producer, validator = ActualProvider(), ActualProvider()
        raw = self.inspection(producer, validator)
        admission = ComponentInputContract('admission', '1', 'components.v1', self.fixture.first.checks,
            ('r',), (self.fixture.exact,), ('request',))
        for name in ('component_inputs', 'component_input_history'):
            for row in raw['snapshot'][name].values():
                row['contract'] = admission.to_dict()
        profile = CompletionProfile('synthetic', Stage.BEHAVIOR, 'behavior.v1', ('exact',))
        raw['snapshot']['profiles']['synthetic'] = self.manager._profile_document(profile)
        raw['order']['profiles'] = ['synthetic']
        raw['snapshot']['records']['input']['value']['accepted'] = False
        self.session.results['inspect-ordered'] = raw
        before = len(self.session.requests)
        with patch.object(PassManager, 'get', side_effect=AssertionError('Python freshness used')), \
                patch.object(PassManager, '__init__', side_effect=AssertionError('Python manager used')), \
                patch.object(PassContract, '__post_init__', side_effect=AssertionError('Python contract check used')), \
                patch.object(ComponentInputContract, '__post_init__', side_effect=AssertionError('Python admission check used')), \
                patch.object(CheckSpec, '__post_init__', side_effect=AssertionError('Python check validation used')), \
                patch.object(ScopedObligation, '__post_init__', side_effect=AssertionError('Python obligation validation used')), \
                patch.object(CompletionProfile, '__post_init__', side_effect=AssertionError('Python profile check used')):
            state = self.manager.inspection_state()
        self.assertEqual(self.session.requests[before:], [('inspect-ordered', {})])
        self.assertEqual(tuple(state), ('_target', '_dependencies', '_passes', '_component_inputs',
            '_provider_history', '_records', '_profiles'))
        self.assertIs(state['_target'], self.fixture.target)
        self.assertTrue(all(type(state[name]) is dict for name in tuple(state)[1:]))
        self.assertEqual(tuple(state['_dependencies']), ('zeta', 'alpha'))
        self.assertEqual(tuple(state['_passes']), ('z', 'a'))
        self.assertEqual(tuple(state['_provider_history']), ('z-history', ('component_input', 'admission-history'), 'a-history'))
        contract, actual_producer, checks = state['_passes']['z']
        self.assertIs(type(state['_passes']['z']), tuple)
        self.assertIs(type(contract), PassContract)
        self.assertEqual(contract.to_dict(), self.fixture.first.to_dict())
        self.assertIs(contract.input_stage, self.fixture.first.input_stage)
        self.assertIs(type(contract.checks), tuple)
        self.assertIs(type(contract.checks[0]), CheckSpec)
        self.assertIs(type(contract.introduces), tuple)
        self.assertIs(actual_producer, producer)
        self.assertIs(type(checks), dict)
        self.assertEqual(tuple(checks), ('zeta', 'alpha'))
        self.assertIs(checks['zeta'], validator)
        self.assertIs(state['_provider_history']['z-history'][1], producer)
        self.assertIs(type(state['_component_inputs']['policy'][0]), ComponentInputContract)
        self.assertIs(type(state['_component_inputs']['policy'][0].obligations[0]), ScopedObligation)
        self.assertEqual(state['_component_inputs']['policy'][0].to_dict(), admission.to_dict())
        self.assertIs(state['_records']['input'], self.manager._records['input'])
        self.assertFalse(state['_records']['input'].accepted)
        self.assertIs(type(state['_profiles']['synthetic']), CompletionProfile)
        self.assertEqual(state['_profiles']['synthetic'], profile)
        state['_dependencies']['new'] = 'value'
        checks.clear()
        second = self.manager.inspection_state()
        self.assertEqual(tuple(second['_dependencies']), ('zeta', 'alpha'))
        self.assertEqual(tuple(second['_passes']['z'][2]), ('zeta', 'alpha'))
        self.assertIs(second['_records']['input'], state['_records']['input'])

    def test_typed_inspection_fails_closed_for_malformed_native_contract_views(self):
        raw = self.inspection(lambda context: context, lambda context: context)
        self.session.results['inspect-ordered'] = raw
        with self.assertRaisesRegex(CoreProtocolError, 'typed historical manager state'):
            self.manager.inspection_state()
        self.assertTrue(self.session.invalidated)

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
        value = provider_result('proposal', {'output': {'schema_version': 'biocompiler.behavior.v0.1', 'name': 'native',
            'nodes': [], 'roots': [], 'source_fingerprint': 'a' * 64, 'requirements': [], 'source_links': {}, 'policies': {}, 'parameter_bindings': {}},
            'obligations': [], 'source_links': [{'requirement_id': 'r', 'source_node_id': 's',
                'target_node_id': 't', 'pass_name': 'p'}], 'observation_map': {}, 'search_status': 'candidate'}, 'intent_to_behavior.producer')
        result = self.manager._native_return(value, role='intent_to_behavior.producer',
            input_payload=freeze_json({'intent': {'nodes': [], 'roots': []}}))
        self.assertIs(type(result), PassResult)
        self.assertIs(type(result.output), BehaviorProgram)
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
            self.manager._native_return(provider_result('decision', {'outcome': 'undeclared-outcome', 'detail': 'x', 'evidence': {}}, 'intent_to_behavior.validator'), role='intent_to_behavior.validator')
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

    def referenced_inspection(self, full, *, definitions=True):
        result = deepcopy(full)
        records = result['snapshot']['records']
        result['record_definitions'] = [records[name] for name in result['order']['records']] if definitions else []
        result['snapshot']['records'] = {name: {'record_id': value['bindings']['record_id']}
            for name, value in records.items()}
        return result

    def test_referenced_inspection_preserves_complete_state_without_extra_native_queries(self):
        full = self.inspection(lambda context: context, lambda context: context)
        self.session.results['inspect-ordered'] = full
        ordinary = self.manager.inspect_ordered()
        record = self.manager._records['input']
        first = self.referenced_inspection(full)
        self.session.results['inspect-ordered-references'] = first
        before = len(self.session.requests)
        compact = self.manager.inspect_ordered_references()
        self.assertEqual(compact.snapshot, ordinary.snapshot)
        self.assertEqual(compact.order, ordinary.order)
        self.assertIs(self.manager._records['input'], record)
        self.assertIs(compact.providers['provider/producer'], ordinary.providers['provider/producer'])
        # Mutating a detached transport fixture cannot alter the stored envelope.
        first['record_definitions'][0]['value']['accepted'] = False
        self.session.results['inspect-ordered-references'] = self.referenced_inspection(full, definitions=False)
        repeated = self.manager.inspect_ordered_references()
        self.assertEqual(repeated.snapshot, ordinary.snapshot)
        self.assertIs(self.manager._records['input'], record)
        self.assertEqual(self.session.requests[before:], [('inspect-ordered-references', {}),
            ('inspect-ordered-references', {})])

    def test_referenced_inspection_rejects_unknown_incarnations_even_if_full_view_was_seen(self):
        full = self.inspection(lambda context: context, lambda context: context)
        self.session.results['inspect-ordered'] = full
        self.manager.inspect_ordered()
        self.session.results['inspect-ordered-references'] = self.referenced_inspection(full, definitions=False)
        with self.assertRaises(CoreProtocolError) as rejected:
            self.manager.inspect_ordered_references()
        self.assertIn('record definitions', str(rejected.exception.__cause__))
        self.assertTrue(self.session.invalidated)

    def test_referenced_inspection_rejects_redefinition_and_foreign_record_names(self):
        full = self.inspection(lambda context: context, lambda context: context)
        initial = self.referenced_inspection(full)
        self.session.results['inspect-ordered-references'] = initial
        self.manager.inspect_ordered_references()
        variants = []
        variants.append(deepcopy(initial))  # Even identical definitions cannot be introduced twice.
        changed = self.referenced_inspection(full, definitions=False)
        changed['snapshot']['records']['input']['record_id'] = 'record/foreign'
        variants.append(changed)
        renamed = self.referenced_inspection(full, definitions=False)
        renamed['snapshot']['records']['other'] = renamed['snapshot']['records'].pop('input')
        renamed['order']['records'] = ['other']
        variants.append(renamed)
        duplicated = self.referenced_inspection(full, definitions=False)
        duplicated['snapshot']['records']['other'] = deepcopy(duplicated['snapshot']['records']['input'])
        duplicated['order']['records'].append('other')
        variants.append(duplicated)
        for index, raw in enumerate(variants):
            with self.subTest(index=index):
                # This fabricated session allows repeated malformed views solely
                # to exercise decoder rejection; real invalidation is terminal.
                self.session.invalidated = False
                self.session.results['inspect-ordered-references'] = raw
                with self.assertRaises(CoreProtocolError):
                    self.manager.inspect_ordered_references()
                self.assertTrue(self.session.invalidated)

    def test_referenced_inspection_binds_definition_order_before_hydration(self):
        full = self.inspection(lambda context: context, lambda context: context)
        full['snapshot']['records']['second'] = self.record(identity='second')
        full['order']['records'].append('second')
        raw = self.referenced_inspection(full)
        raw['record_definitions'].reverse()
        self.session.results['inspect-ordered-references'] = raw
        with self.assertRaises(CoreProtocolError) as rejected:
            self.manager.inspect_ordered_references()
        self.assertIn('first-reference order', str(rejected.exception.__cause__))
        self.assertEqual(self.manager._inspection_record_ids, {})
        self.assertTrue(self.session.invalidated)

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
        completion = self.manager._invoke('native-provider', {'provider_id': 'provider/producer', 'role': 'intent_to_behavior.producer'})
        proxy = self.manager._objects.resolve(completion.value)
        self.session.results['inspect-ordered'] = self.inspection(proxy, lambda context: context)
        self.assertIs(self.manager.inspect_ordered().providers['provider/producer'], proxy)

    def test_owned_component_preparation_preserves_order_and_native_registration_objects(self):
        # The fixture contract is original authoring data; every operation below
        # is an adapter request against inert scripted responses.
        self.session.results['prepare-components'] = {'preparation_id': 'prep/1',
            'dependencies': [['zeta', 'a' * 64], ['alpha', 'b' * 64]]}
        prepared = self.manager.prepare_components()
        self.assertEqual(prepared.dependencies, (('zeta', 'a' * 64), ('alpha', 'b' * 64)))
        self.session.results['component-profile'] = {'scope': 'component_realization', 'stage': Stage.COMPONENTS.value,
            'schema': 'assembly.v1', 'obligations': ['model']}
        profile = self.manager.component_profile(prepared)
        self.assertIs(type(profile), CompletionProfile)
        count = len(self.session.requests)
        with self.assertRaisesRegex(CoreProtocolError, 'does not belong'):
            self.manager.component_profile(ComponentPreparation('prep/1', prepared.dependencies))
        self.assertEqual(len(self.session.requests), count)
        contract = self.fixture.first
        producer = self.manager._invoke('native-provider', {'provider_id': 'provider/staged-producer',
            'role': 'synthetic_to_components.producer'}).value
        validator = self.manager._invoke('native-provider', {'provider_id': 'provider/staged-validator',
            'role': 'synthetic_to_components.validator'}).value
        self.session.results['component-registration'] = {'contract': contract.to_dict(), 'producer': producer,
            'validators': [[check.id, validator] for check in contract.checks],
            'obligation_objects': [self.native(item.to_dict()) for item in contract.introduces]}
        registration = self.manager.component_registration(prepared)
        self.assertEqual(registration.contract.to_dict(), contract.to_dict())
        self.assertIs(registration.producer, self.manager._objects.resolve(producer))
        self.assertEqual(tuple(registration.validators), tuple(check.id for check in contract.checks))
        self.manager.register_completion_profile(profile)
        self.manager.register(registration.contract, registration.producer, registration.validators)
        args = self.session.requests[-1][1]
        for reference, item in zip(args['obligation_objects'], registration.contract.introduces):
            self.assertIs(self.manager._objects.resolve(reference), item)

    def test_finish_requires_exact_owned_public_result_and_no_extra_result_lookup(self):
        self.session.results['prepare-components'] = {'preparation_id': 'prep/1', 'dependencies': []}
        prepared = self.manager.prepare_components()
        envelope = self.record(identity='components')
        record = self.manager._record(envelope)
        result_raw = {'value': {'status': 'complete', 'artifact': envelope['value'],
            'scope': 'component_realization', 'unresolved': []}, 'artifact': envelope}
        self.session.results['result'] = result_raw
        result = self.manager.result('components', scope='component_realization')
        sequence = self.session.last_response.sequence
        clone = PipelineResult(result.status, result.artifact, result.scope, result.unresolved)
        count = len(self.session.requests)
        with self.assertRaisesRegex(CoreProtocolError, 'actual public result wrapper'):
            self.manager.finish_components(prepared, clone)
        self.assertEqual(len(self.session.requests), count)
        # Decode hook here observes exact arguments and result resolver; the
        # independent full6authority store suite checks actual build hydration.
        from biocompiler.compiler.components import ComponentBuild
        built = object.__new__(ComponentBuild)
        object.__setattr__(built, 'result', result)
        self.session.results['finish-components'] = {'fixture': 'complete'}
        def decode(raw, **options):
            self.assertIs(options['result'](result_raw), result)
            return built
        with patch.object(self.manager._build_views, 'decode', side_effect=decode):
            self.assertIs(self.manager.finish_components(prepared, result), built)
        self.assertEqual(self.session.requests[-1], ('finish-components', {'preparation_id': 'prep/1',
            'record_id': 'record/components', 'result_sequence': sequence}))
        self.assertEqual(len(self.session.requests), count + 1)
        def altered(raw, **options):
            changed = deepcopy(result_raw)
            changed['value']['scope'] = 'other'
            return options['result'](changed)
        with patch.object(self.manager._build_views, 'decode', side_effect=altered):
            with self.assertRaises(CoreProtocolError):
                self.manager.finish_components(prepared, result)
        self.assertTrue(self.session.invalidated)

    def test_interrupted_build_hydration_invalidates_without_retry_or_semantic_fallback(self):
        error = KeyboardInterrupt()
        self.session.results['build-result'] = {'fixture': 'completed'}
        count = len(self.session.requests)
        with patch.object(self.manager._build_views, 'decode', side_effect=error):
            with self.assertRaises(KeyboardInterrupt) as caught:
                self.manager.build_result('synthetic')
        self.assertIs(caught.exception, error)
        self.assertTrue(self.session.invalidated)
        self.assertEqual(self.session.requests[count:], [('build-result', {'kind': 'synthetic'})])


if __name__ == '__main__':
    unittest.main()
