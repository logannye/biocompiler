"""Reference facade mechanics; fixture replies do not prove native acceptance."""
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from biocompiler import core_pipeline_manager as base
from biocompiler import core_reference_manager as facade
from biocompiler.compiler.construct import run_construct_pipeline
from biocompiler.compiler.molecular import run_molecular_pipeline
from biocompiler.compiler.passes import PassResult
from biocompiler.compiler.pipeline import PassManager, PipelineError, PassContext
from biocompiler.core_client import CoreClient, CoreProtocolError
from biocompiler.core_pipeline_callback_session import CallbackRejected
from biocompiler.core_pipeline_manager import _ordered
from biocompiler.core_pipeline_session import encode_document
from biocompiler.core_reference_provider_views import REFERENCE_PROVIDER_ROLES
from biocompiler.ir.intent import freeze_json
from examples.reference_construct import reference_request


def native(value, identity):
    return {'kind': 'native', 'identity': identity, 'tree': _ordered(value)}


def rejected(message):
    return {'module': 'biocompiler.compiler.pipeline', 'type': 'PipelineError',
            'message': message, 'attributes': {}, 'attributes_tree': ['object', []]}


class ReferenceSession:
    """Complete typed wire fixtures and real local callbacks; no manager semantics."""
    source = None
    instances = []
    failure = None

    def __init__(self, core, *, application, objects, invocation_handler, **options):
        self.application, self.objects, self.handler = application, objects, invocation_handler
        self.requests, self.results, self.events = [], {}, []
        self.closed = self.invalidated = False
        self.last_response = None
        self._handlers = []
        self._limits = {'max_retained_bytes': 134_217_728}
        self.providers = {}
        self.native_provider_calls = 0
        self.admission_refs = None
        self.returned_construct = None
        self.checked_construct = None
        self.instances.append(self)

    def action(self, name, arguments):
        self.events.append(('action', name))
        value = self.handler(name, arguments)
        if value.status == 'exception':
            self.objects.rethrow(value.value['exception_token'])
        return value.value

    def provider(self, role):
        token = 'native/' + role
        value = self.action('native-provider', {'provider_id': token, 'role': role})
        self.providers[role] = value
        return value

    def obligation(self, item):
        return native(item.to_dict(), 'obligation/' + item.id)

    def record(self, name):
        record = self.source['molecular'].manager._records[name]
        document = record.to_dict()
        requirements = {'kind': 'host', 'object': self.admission_refs['requirements_object']}
        obligations = ({'kind': 'host', 'object': self.admission_refs['obligations_object']}
                       if name == 'components' else native(document['obligations'], 'obligations/' + name))
        return {'value': document, 'bindings': {
            'record_id': 'record/' + name, 'payload': native(document['payload'], 'payload/' + name),
            'requirements': requirements, 'dependencies': native(document['dependencies'], 'dependencies/' + name),
            'obligations': obligations, 'obligation_objects': [self.obligation(item) for item in record.obligations],
            'checks': native(document['checks'], 'checks/' + name),
            'provenance': native(document['provenance'], 'provenance/' + name)}}

    def result(self, name):
        result = self.source[name].result
        return {'value': {'status': result.status.value, 'artifact': result.artifact.to_dict(),
                'scope': result.scope, 'unresolved': [item.to_dict() for item in result.unresolved]},
                'artifact': self.record(name)}

    def build(self, name):
        build = self.source[name]
        def artifact(value, identity):
            document = value.to_dict()
            return {'value': document, 'binding': native(document, identity)}
        return {'build_id': 'build/' + name, 'kind': name,
                'candidate': artifact(build.candidate, 'candidate/' + name),
                'check_result': artifact(build.check_result, 'check/' + name),
                'result': self.result(name), 'construct': None if name == 'construct' else
                    ({'value': None, 'binding': {'kind': 'host', 'object': self.returned_construct}}
                     if self.returned_construct is not None else
                     artifact(self.source['construct'].candidate, 'candidate/construct'))}

    def registration(self, name):
        contract = self.source['contracts'][name]
        return {'contract': contract.to_dict(), 'producer': self.provider(name + '.producer'),
                'validators': [[slot, self.provider(role)] for slot, role in facade._SLOTS[name]],
                'obligation_objects': [self.obligation(item) for item in contract.introduces]}

    def call(self, operation, arguments):
        if self.closed:
            raise CoreProtocolError('Callback session is closed; it cannot reconnect')
        self.requests.append((operation, arguments))
        sequence = len(self.requests)
        self.events.append(('command', operation))
        self._handlers.append(SimpleNamespace(sequence=sequence))
        try:
            if operation == 'initialize-reference':
                target = {'value': arguments['request']['target'],
                          'binding': {'kind': 'host', 'object': arguments['target_object']}}
                self.action('manager-created', {'target': target})
                value = {'kind': 'reference', 'manager': True, 'artifacts': [], 'target': target}
            elif operation == 'reference-admission':
                contract = self.source['admission']
                value = {'contract': contract.to_dict(),
                    'validators': [[slot, self.provider(role)] for slot, role in facade._SLOTS[contract.id]],
                    'obligation_objects': [self.obligation(item) for item in contract.obligations]}
            elif operation == 'reference-registration':
                value = self.registration('components_to_construct')
            elif operation == 'register-component-input':
                self.admission_refs = arguments
                value = None
            elif operation in ('register', 'set-dependency', 'register-completion-profile'):
                value = None
            elif operation == 'admit-component-input':
                value = self.record('components')
            elif operation == 'get':
                value = self.record(arguments['identity'])
            elif operation == 'run':
                value = self.record(arguments['output_id'])
            elif operation == 'result':
                value = self.result(arguments['identity'])
            elif operation == 'finish-reference-construct':
                value = self.build('construct')
            elif operation in ('prepare-reference-molecular', 'prepare-reference-molecular-public'):
                value = {'preparation_id': 'preparation/molecular', 'dependencies': [
                    [key, self.source['molecular'].manager._dependencies[key]]
                    for key in self.source['contracts']['construct_to_molecular'].dependency_keys]}
            elif operation == 'reference-molecular-profile':
                profile = self.source['molecular'].manager._profiles['exact_cds']
                value = {'scope': profile.scope, 'stage': profile.stage.value,
                         'schema': profile.schema, 'obligations': list(profile.obligations)}
            elif operation == 'reference-molecular-registration':
                value = self.registration('construct_to_molecular')
            elif operation == 'finish-reference-molecular':
                if arguments['upstream'] is not None:
                    checked = self.action('reference-upstream-candidate',
                        {'upstream': arguments['upstream'], 'phase': 'check'})
                    self.checked_construct = checked
                    if checked['value'] is None:
                        value = {'module': 'biocompiler.errors', 'type': 'SerializationError',
                            'message': 'Invalid molecular checker artifacts.', 'attributes': {},
                            'attributes_tree': ['object', []]}
                        self.last_response = SimpleNamespace(result=value, sequence=sequence,
                            operation=operation, status='rejected')
                        raise CallbackRejected(self.last_response)
                    self.events.append(('fixture-check', checked['object']))
                    self.returned_construct = self.action('reference-upstream-candidate',
                        {'upstream': arguments['upstream'], 'phase': 'return'})['object']
                value = self.build('molecular')
            elif operation == 'reference-build-result':
                value = self.build(arguments['kind'])
            elif operation == 'call-native-provider':
                value = self.provider_result(arguments, sequence)
            else:
                raise AssertionError('Unknown fixture command ' + operation)
            if operation in self.results:
                value = self.results[operation](arguments, value)
            response = SimpleNamespace(result=value, sequence=sequence, operation=operation, status='ok')
            self.last_response = response
            if self.failure == operation:
                response.result = rejected('Source-bound fixture rejection')
                response.status = 'rejected'
                raise CallbackRejected(response)
            return response
        finally:
            self._handlers.pop()

    def provider_result(self, arguments, sequence):
        self.native_provider_calls += 1
        role = arguments['provider_id'].removeprefix('native/')
        manager = self.handler.__self__
        context = manager._contexts[arguments['context_id']][1]
        document = base._literal_json(context.input)
        action = 'reference-generate' if role == 'components_to_construct.producer' else 'reference-emit'
        route = self.action(action, {'input': document, 'argument': document, 'tree': _ordered(document)})
        links = [{'requirement_id': 'req', 'source_node_id': 'source', 'target_node_id': 'target', 'pass_name': role}]
        if route['kind'] == 'host':
            reference = self.action('reference-proposal', {'output': route['output'], 'source_links': links})
            return {'kind': 'host', 'object': reference}
        output = self.source['construct' if action == 'reference-generate' else 'molecular'].candidate.to_dict()
        proposal = {'output': output, 'source_links': links, 'obligations': [], 'observation_map': {}, 'search_status': 'candidate'}
        roots = {'parsed': route['argument']}
        if action == 'reference-emit':
            roots.update({name: self.objects.retain(manager._reference_molecular_host.origin(name)) for name in
                          ('request', 'translation_policy', 'encoding_policy', 'evidence_policy')})
        return {'kind': 'proposal', 'value': proposal,
                'view': {'role': role, 'tree': _ordered(proposal), 'origins': roots}}

    def close(self):
        self.closed = True

    def _invalidate(self):
        self.closed = self.invalidated = True


class ReferenceManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        request, manifest, registry = reference_request('RNA')
        saved = {'request': request, 'registry': registry, 'manifests': {manifest.reference_set_id: manifest}, 'contracts': {}}
        old_register, old_admission = PassManager.register, PassManager.register_component_input
        def register(manager, contract, producer, validators):
            saved['contracts'][contract.id] = contract
            return old_register(manager, contract, producer, validators)
        def admission(manager, contract, validators):
            saved['admission'] = contract
            return old_admission(manager, contract, validators)
        def construct(*args):
            saved['construct'] = run_construct_pipeline(*args)
            return saved['construct']
        with patch.object(PassManager, 'register', register), patch.object(PassManager, 'register_component_input', admission), \
             patch('biocompiler.compiler.molecular.run_construct_pipeline', construct):
            saved['molecular'] = run_molecular_pipeline(request, registry, saved['manifests'])
        cls.source = saved

    def setUp(self):
        ReferenceSession.source = self.source
        ReferenceSession.instances = []
        ReferenceSession.failure = None
        patched = patch('biocompiler.core_pipeline_manager.CorePipelineCallbackSession', ReferenceSession)
        patched.start(); self.addCleanup(patched.stop)
        self.core = CoreClient(Path('/fixture/core'))
        def cleanup():
            for session in ReferenceSession.instances:
                session.close()
        self.addCleanup(cleanup)

    def build(self, molecular=True):
        factory = (facade.ReferenceCorePassManager.from_molecular if molecular
                   else facade.ReferenceCorePassManager.from_construct)
        return factory(self.core, self.source['request'], self.source['registry'], self.source['manifests'])

    def context(self, manager, name):
        record = manager._records[name]
        value = PassContext(record.payload, None, manager.target, freeze_json({}), record.dependencies, record.requirements)
        token = 'context/' + str(len(manager._contexts))
        manager._contexts[token] = (b'fixture source-bound context', value)
        manager._context_ids[id(value)] = token
        return value

    def test_final_source_owner_phase_command_and_return_binding_mutants_fail_closed(self):
        original_action = ReferenceSession.action
        for mode in ('return-first', 'repeat-check', 'foreign-owner', 'wrong-command', 'changed-return-binding'):
            with self.subTest(mode=mode):
                def action(session, name, arguments):
                    if name == 'reference-upstream-candidate':
                        arguments = dict(arguments)
                        if mode == 'return-first' and arguments['phase'] == 'check':
                            arguments['phase'] = 'return'
                        elif mode == 'foreign-owner':
                            arguments['upstream'] = session.objects.retain(object())
                        elif mode == 'wrong-command':
                            session._handlers[-1].sequence += 100
                        value = original_action(session, name, arguments)
                        if mode == 'repeat-check' and arguments['phase'] == 'check':
                            original_action(session, name, arguments)
                        if mode == 'changed-return-binding' and arguments['phase'] == 'return':
                            value = {'object': session.objects.retain(object())}
                        return value
                    return original_action(session, name, arguments)
                with patch.object(ReferenceSession, 'action', action):
                    with self.assertRaises(CoreProtocolError):
                        self.build()
                session = ReferenceSession.instances[-1]
                self.assertTrue(session.invalidated)
                self.assertIsNone(session.handler.__self__._reference_final)

    def test_exact_public_method_order_one_session_build_and_record_identities(self):
        build = self.build()
        manager, session = build.manager, build.manager.session
        self.assertIs(type(manager), facade.ReferenceCorePassManager)
        self.assertIsInstance(manager, PassManager)
        self.assertEqual(len(ReferenceSession.instances), 1)
        operations = [name for name, _ in session.requests]
        self.assertEqual(operations, [
            'initialize-reference', 'reference-admission', 'register-component-input',
            'admit-component-input', 'get', 'reference-registration', 'register', 'run', 'result',
            'finish-reference-construct', 'prepare-reference-molecular', *(['set-dependency'] * 6),
            'reference-molecular-profile', 'register-completion-profile',
            'reference-molecular-registration', 'register', 'run', 'result', 'finish-reference-molecular'])
        upstream = manager._reference_builds['construct']
        self.assertIs(build.construct, upstream.candidate)
        self.assertIs(build.result.artifact, manager._records['molecular'])
        self.assertIs(upstream.result.artifact, manager._records['construct'])
        self.assertIs(build.result, manager._result_receipts[id(build.result)][0])
        self.assertIs(manager.target, self.source['request'].target)
        self.assertIs(manager.reference_build_result('molecular'), build)
        self.assertIs(manager.reference_build_result('construct'), upstream)
        self.assertEqual(len(ReferenceSession.instances), 1)
        self.assertEqual(session.requests[-1], ('reference-build-result', {'kind': 'construct'}))
        for operation, arguments in session.requests:
            if operation.startswith('finish-reference-'):
                name = 'construct' if operation.endswith('construct') else 'molecular'
                self.assertEqual(arguments['record_id'], 'record/' + name)
                self.assertEqual(session.requests[arguments['result_sequence'] - 1][0], 'result')

    def test_initializer_preserves_ordered_authority_and_actual_roots(self):
        build = self.build()
        manager = build.manager
        arguments = manager.session.requests[0][1]
        self.assertEqual(set(arguments), set(base.capability_profile()['operations']['initialize-reference']['fields']))
        self.assertEqual(arguments['request_tree'], _ordered(arguments['request']))
        self.assertEqual(arguments['registry_tree'], _ordered(arguments['registry']))
        self.assertEqual(arguments['manifests_tree'], _ordered(arguments['manifests']))
        resolve = manager._objects.resolve
        self.assertIs(resolve(arguments['request_object']), self.source['request'])
        self.assertIs(resolve(arguments['registry_object']), self.source['registry'])
        self.assertIsNot(resolve(arguments['construct_manifests_object']), resolve(arguments['molecular_manifests_object']))
        for key, original in self.source['manifests'].items():
            self.assertIs(resolve(arguments['construct_manifests_object'])[key], original)
            self.assertIs(resolve(arguments['molecular_manifests_object'])[key], original)
        for key, reference in arguments['policy_objects'].items():
            self.assertIs(resolve(reference), manager._reference_host.origin(key))

    def test_same_linkage_proxy_and_actual_public_register_wrapper_once(self):
        original = PassManager.register
        calls = []
        def wrapper(manager, contract, producer, validators):
            calls.append((manager, contract, producer, validators))
            return original(manager, contract, producer, validators)
        with patch.object(PassManager, 'register', wrapper):
            build = self.build()
        manager, session = build.manager, build.manager.session
        self.assertEqual([item[1].id for item in calls], ['components_to_construct', 'construct_to_molecular'])
        admission = manager._objects.resolve(session.admission_refs['validators'])
        self.assertIs(admission['component_linkage'], calls[0][3]['layout_composition'])
        for captured, (_, arguments) in zip(calls, [item for item in session.requests if item[0] == 'register']):
            self.assertIs(captured[0], manager)
            self.assertIs(manager._objects.resolve(arguments['producer']), captured[2])
            self.assertIs(manager._objects.resolve(arguments['validators']), captured[3])
        self.assertEqual(set(manager._native_provider_roles.values()), REFERENCE_PROVIDER_ROLES)

    def test_default_proxy_uses_native_route_fresh_input_and_audited_output_origins(self):
        build = self.build()
        manager = build.manager
        for role, source in (('components_to_construct.producer', 'components'),
                             ('construct_to_molecular.producer', 'construct')):
            provider = manager._objects.resolve(manager.session.providers[role])
            context = self.context(manager, source)
            first, second = provider(context), provider(context)
            self.assertIsNot(first, second); self.assertIsNot(first.output, second.output)
            self.assertIsNot(first.source_links[0], second.source_links[0])
            if source == 'components':
                self.assertIsNot(first.output.placements, second.output.placements)
            else:
                self.assertIs(first.output.records[0].reference_selection, self.source['request'].references[0].selection)
                self.assertIs(first.output.encoding_policy, second.output.encoding_policy)

    def test_actual_global_override_arguments_output_exception_and_lookup_each_call(self):
        build = self.build()
        manager = build.manager
        generator = manager._objects.resolve(manager.session.providers['components_to_construct.producer'])
        emitter = manager._objects.resolve(manager.session.providers['construct_to_molecular.producer'])
        class Opaque:
            def __getattribute__(self, name):
                raise AssertionError('Override output was inspected early')
        output = Opaque()
        seen = []
        def generate(parsed):
            seen.append(parsed)
            return output
        with patch('biocompiler.compiler.construct.generate_construct', generate):
            first = generator(self.context(manager, 'components'))
            second = generator(self.context(manager, 'components'))
        self.assertIs(first.output, output); self.assertIs(second.output, output)
        self.assertIsNot(seen[0], seen[1]); self.assertIsNot(seen[0], self.source['request'])
        captured = []
        def emit(*args):
            captured.append(args)
            return output
        with patch('biocompiler.compiler.molecular.emit_reference_sequence', emit):
            actual = emitter(self.context(manager, 'construct'))
        self.assertIs(actual.output, output)
        self.assertIs(captured[0][0], self.source['request'])
        self.assertIs(captured[0][2], self.source['registry'])
        self.assertIs(captured[0][3], manager._reference_host.molecular_manifests)
        error = KeyboardInterrupt('original')
        def failing(parsed):
            raise error
        with patch('biocompiler.compiler.construct.generate_construct', failing):
            with self.assertRaises(KeyboardInterrupt) as raised:
                generator(self.context(manager, 'components'))
        self.assertIs(raised.exception, error)
        self.assertFalse(manager.session.closed)
        restored = generator(self.context(manager, 'components'))
        self.assertIs(type(restored), PassResult)

    def test_replayed_prior_provider_origins_and_foreign_pair_are_rejected(self):
        build = self.build()
        manager = build.manager
        provider = manager._objects.resolve(manager.session.providers['components_to_construct.producer'])
        context = self.context(manager, 'components')
        saved = []
        manager.session.results['call-native-provider'] = lambda args, value: saved.append(deepcopy(value)) or value
        provider(context)
        manager.session.results['call-native-provider'] = lambda args, value: saved[0]
        with self.assertRaises(CoreProtocolError):
            provider(context)
        self.assertTrue(manager.session.invalidated)

    def test_sorted_links_keep_duplicate_multiplicity_and_actual_access_exceptions(self):
        build = self.build(False)
        manager = build.manager
        source = {'requirement_id': 'r', 'source_node_id': 's', 'target_node_id': 't', 'pass_name': 'p'}
        link = facade.ReferenceViews().source_link(source, ())
        result = manager._invoke('reference-source-links-equal', {
            'actual': [manager._objects.retain(link), manager._objects.retain(link)], 'expected': [source]})
        self.assertIs(result.value, False)
        error = ValueError('original descriptor')
        class Broken:
            @property
            def requirement_id(self):
                raise error
        completion = manager._invoke('reference-source-links-equal', {
            'actual': [manager._objects.retain(Broken())], 'expected': [source]})
        self.assertEqual(completion.status, 'exception')
        with self.assertRaises(ValueError) as raised:
            manager._objects.rethrow(completion.value['exception_token'])
        self.assertIs(raised.exception, error)

    def test_failed_admission_keeps_published_manager_and_never_requests_producer(self):
        ReferenceSession.failure = 'get'
        with self.assertRaisesRegex(PipelineError, 'Source-bound fixture rejection'):
            self.build(False)
        session = ReferenceSession.instances[0]
        self.assertFalse(session.closed)
        self.assertNotIn('reference-registration', [item[0] for item in session.requests])
        self.assertEqual(session.native_provider_calls, 0)
        manager = session.handler.__self__
        self.assertIn('components', manager._records)
        ReferenceSession.failure = None
        self.assertIs(manager.get('components'), manager._records['components'])

    def test_initializer_logical_failure_retains_owner_but_bad_publication_closes(self):
        ReferenceSession.failure = 'initialize-reference'
        with self.assertRaises(PipelineError):
            self.build(False)
        session = ReferenceSession.instances[-1]
        self.assertFalse(session.closed)
        self.assertIs(session.handler.__self__.target, self.source['request'].target)
        self.assertIsNone(session.handler.__self__._fixed_initialization)
        ReferenceSession.failure = None
        action = ReferenceSession.action
        def corrupted(owner, name, arguments):
            if name == 'manager-created':
                arguments = deepcopy(arguments)
                arguments['target']['value']['organism'] = 'foreign organism'
            return action(owner, name, arguments)
        with patch.object(ReferenceSession, 'action', corrupted):
            with self.assertRaises(CoreProtocolError):
                self.build(False)
        self.assertTrue(ReferenceSession.instances[-1].invalidated)

    def test_shared_retention_precedes_build_binding_source_and_result_allocation(self):
        manager = self.build(False).manager
        used = (manager._reference_origin_bytes + manager._reference_binding_bytes
            + manager._reference_build_views.retained_bytes + manager._result_retained_bytes)
        manager.session._limits['max_retained_bytes'] = used
        raw = deepcopy(manager.session.build('construct'))
        raw['build_id'] = 'fresh/build'
        raw['candidate']['binding']['identity'] = 'fresh/candidate'
        raw['check_result']['binding']['identity'] = 'fresh/check'
        store = manager._reference_build_views
        roots, builds, retained = len(store.roots), len(store.builds), store.retained_bytes
        with patch.object(facade.ReferenceViews, 'construct_candidate', side_effect=AssertionError('allocation')):
            with self.assertRaisesRegex(CoreProtocolError, 'shared retention'):
                store.decode(raw, manager=manager, result=manager._reference_builds['construct'].result,
                    result_envelope=raw['result'])
        self.assertEqual((len(store.roots), len(store.builds), store.retained_bytes), (roots, builds, retained))
        with patch.object(base, '_unordered', side_effect=AssertionError('allocation')):
            with self.assertRaisesRegex(CoreProtocolError, 'shared retention'):
                manager._binding(native({'data': ['new']}, 'fresh/binding'))
        self.assertNotIn('fresh/binding', manager._bindings)
        with patch.object(base.CorePassManager, '_result_value', side_effect=AssertionError('allocation')):
            with self.assertRaisesRegex(CoreProtocolError, 'Invalid native pipeline result') as raised:
                manager.result('construct', scope='reference_construct')
        self.assertIn('shared retention', str(raised.exception.__cause__))
        self.assertEqual(manager._reference_pending_bytes, 0)
        self.assertTrue(manager.session.invalidated)
        # A separate live session proves the source action fails before parsing.
        manager = self.build(False).manager
        manager.session._limits['max_retained_bytes'] = 1
        provider = manager._objects.resolve(manager.session.providers['components_to_construct.producer'])
        with patch.object(facade.ReferenceViews, 'construct_request', side_effect=AssertionError('allocation')):
            with self.assertRaises(CoreProtocolError):
                provider(self.context(manager, 'components'))
        self.assertEqual(manager._reference_origins, {})

    def test_reference_native_origins_cannot_rebind_as_record_containers(self):
        manager = self.build(False).manager
        for identity in ('candidate/construct', 'check/construct', 'build/construct'):
            with self.assertRaisesRegex(CoreProtocolError, 'collides'):
                manager._binding(native({}, identity))
            self.assertNotIn(identity, manager._bindings)

    def test_facade_default_path_never_enters_python_manager_or_producers(self):
        from biocompiler.compiler import construct, molecular
        forbidden_codes = {construct.generate_construct.__code__, molecular.emit_reference_sequence.__code__}
        observed = []
        previous = sys.getprofile()
        def observer(frame, event, arg):
            if event == 'call' and frame.f_code in forbidden_codes:
                observed.append(frame.f_code)
                raise AssertionError('Python semantic producer ran')
            if previous is not None:
                previous(frame, event, arg)
        def forbidden(*args, **kwargs):
            raise AssertionError('Python manager semantics ran')
        with ExitStack() as stack:
            for name in ('register_component_input', 'admit_component_input', 'get', 'run', 'result',
                         'set_dependency', 'register_completion_profile'):
                stack.enter_context(patch.object(PassManager, name, forbidden))
            sys.setprofile(observer)
            try:
                manager = self.build().manager
                for role, source in (('components_to_construct.producer', 'components'),
                                     ('construct_to_molecular.producer', 'construct')):
                    provider = manager._objects.resolve(manager.session.providers[role])
                    self.assertIs(type(provider(self.context(manager, source))), PassResult)
            finally:
                sys.setprofile(previous)
        self.assertEqual(observed, [])

    def test_finish_capabilities_foreign_result_and_preparation_fail_before_traffic(self):
        build = self.build()
        manager = build.manager
        count = len(manager.session.requests)
        with self.assertRaises(CoreProtocolError):
            manager.finish_reference_construct(manager._records['construct'], build.result)
        with self.assertRaises(CoreProtocolError):
            manager.reference_molecular_profile(base.ComponentPreparation('preparation/molecular', ()))
        self.assertEqual(len(manager.session.requests), count)
        manager.close()
        with self.assertRaisesRegex(CoreProtocolError, 'cannot reconnect'):
            manager.reference_build_result('construct')

    def test_canonical_class_seam_rejects_fakes_subclasses_and_uninitialized_instances(self):
        build = self.build(False)
        manager = build.manager
        contract = self.source['contracts']['components_to_construct']
        original = facade.ReferenceCorePassManager
        class Subclass(original):
            pass
        fake = type('ReferenceCorePassManager', (base.CorePassManager,), {'__module__': facade.__name__})
        for kind in (Subclass, fake, original):
            with self.assertRaises(CoreProtocolError):
                base.CorePassManager._native_register(kind.__new__(kind), contract, object(), {})
        counterfeit = ModuleType(facade.__name__)
        counterfeit.__dict__.update(vars(facade))
        with patch.dict(sys.modules, {facade.__name__: counterfeit}):
            with self.assertRaises(CoreProtocolError):
                manager.register(contract, object(), {})
        for path in (Path('/tmp/same-bytes/core_reference_manager.py'), Path(base.__file__)):
            counterfeit = ModuleType(facade.__name__)
            counterfeit.__dict__.update(vars(facade))
            counterfeit.__file__ = str(path)
            counterfeit.__spec__ = SimpleNamespace(origin=str(path))
            with patch.dict(sys.modules, {facade.__name__: counterfeit}):
                with self.assertRaises(CoreProtocolError):
                    base._register_reference_manager_type(original, counterfeit)


if __name__ == '__main__':
    unittest.main()
