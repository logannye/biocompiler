"""Additive exact fixed-registration authority controls; no native execution."""
from contextlib import contextmanager
from copy import deepcopy
import dis
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import check_pipeline_fixed_registration_install as campaign
from tools import capture_pipeline_fixed_build_semantics as build
from tools import pipeline_fixed_initializer_receipts as initializers
from tests.pipeline_fixed_initializer_fixture import emit
from tests.test_pipeline_fixed_provider_campaign import Script
from tests.test_pipeline_manager_campaign import reframe


class OriginalCadence:
    """A tracer observes real bodies without replacing the patched base slot."""
    def __init__(self):
        self.context, self.rows, self.boundaries = None, [], []
        self.managers, self.upstreams, self.errors = {}, {}, {}
        self.active = set()
        self.codes = {getattr(build.pipeline.PassManager, name).__code__: name for name in
            ('set_dependency', 'register_completion_profile', 'register', 'run')}
        self.fixed_codes = {build.synthetic.run_synthetic_pipeline.__code__: 'run_synthetic_pipeline',
            build.components.run_component_pipeline.__code__: 'run_component_pipeline'}

    @contextmanager
    def in_context(self, name):
        previous, self.context = self.context, name
        try:
            yield
        finally:
            self.context = previous

    def trace(self, frame, event, value):
        if event != 'call' or self.context is None:
            return None
        name = self.fixed_codes.get(frame.f_code)
        fixed = name is not None
        owner = frame.f_locals.get('self')
        if not fixed:
            name = self.codes.get(frame.f_code)
            if name is None or owner is not self.managers.get(self.context) or id(owner) in self.active:
                return None
            self.active.add(id(owner))
        row = {'context': self.context, 'api': name if fixed else 'PassManager.'+name}
        if fixed:
            self.boundaries.append(row)
        else:
            self.rows.append(row)
        last_error = None
        def local(current, kind, argument):
            nonlocal last_error
            if kind == 'exception':
                last_error = argument[1]
            elif kind == 'return':
                normal = next(item.opname for item in dis.get_instructions(current.f_code, show_caches=True)
                    if item.offset == current.f_lasti).startswith('RETURN_')
                row['outcome'] = 'returned' if normal else 'raised'
                if not normal:
                    assert last_error is not None
                    row['error'] = {'module': type(last_error).__module__, 'type': type(last_error).__name__,
                        'message': str(last_error)}
                    self.errors.setdefault(self.context, []).append(last_error)
                elif name == 'run_synthetic_pipeline':
                    self.managers[self.context] = argument.manager
                    self.upstreams[self.context] = argument
                if not fixed:
                    self.active.remove(id(owner))
                if name == 'run_component_pipeline':
                    row['manager_same'] = current.f_locals['manager'] is self.managers[self.context]
            return local
        return local

    @contextmanager
    def installed(self):
        previous = sys.gettrace()
        assert previous is None
        sys.settrace(self.trace)
        try:
            yield
        finally:
            intact = sys.gettrace() == self.trace
            sys.settrace(previous)
            assert intact


class PipelineFixedRegistrationCampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = campaign.Corpus()

    def test_exact_cohort_keeps_all_prior_exclusions_and_remaining_boundaries(self):
        self.assertEqual((len(self.corpus.boundaries), len(self.corpus.cases)), (6, 3))
        self.assertEqual((len(self.corpus.prefix), len(self.corpus.suffix)), (24, 9))
        self.assertEqual(len(self.corpus.fixed.excluded), 10)
        self.assertEqual(len(self.corpus.remaining), 4)
        self.assertEqual(len(self.corpus.metadata()['original_continuations']), 6)
        for case in self.corpus.cases:
            run = self.corpus.fixed.continuations[case['id']]['events'][-1]
            self.assertEqual(run['state_before'], run['state_after'])

    def test_unchanged_three_methods_observe_six_boundaries_same_three_managers_and_33_calls(self):
        observer = OriginalCadence()
        with build.portable_sources(), observer.installed():
            result = campaign.run_original_bodies(context=observer.in_context)
        self.assertEqual(result['methods'], 3)
        self.assertEqual(len(observer.managers), 3)
        self.assertEqual(len({id(value) for value in observer.managers.values()}), 3)
        self.assertEqual([{key: row[key] for key in ('context', 'api', 'outcome')} for row in observer.boundaries],
            [{key: row[key] for key in ('context', 'api', 'outcome')} for row in self.corpus.boundaries])
        self.assertEqual(observer.rows, [{key: event[key] for key in ('api', 'context', 'outcome', 'error') if key in event}
            for event in self.corpus.events])
        for context in campaign.CONTEXTS:
            self.assertIs(observer.errors[context][0], observer.errors[context][1])
            self.assertTrue(next(row for row in observer.boundaries
                if row['context'] == context and row['api'] == 'run_component_pipeline')['manager_same'])
            actual = observer.managers[context]
            self.assertNotIn('components', actual._records)
            self.assertIn('synthetic_to_components', actual._passes)
            self.assertIs(observer.upstreams[context].manager, actual)

    def test_authoring_only_fixture_uses_unchanged_request_recipe(self):
        module = campaign.load_body_module()
        with build.portable_sources():
            result = campaign.run_original_bodies(module=module,
                prepare=lambda cls: campaign.authored_fixture(cls, module))
        self.assertEqual(result['contexts'], list(campaign.CONTEXTS))
        cls = getattr(module, campaign.CLASS)
        for case in self.corpus.cases:
            authority = self.corpus.fixed.document('fixed', case['authority'])
            self.assertEqual({'request': cls.request.to_dict(), 'history': [value.to_dict() for value in cls.history],
                'until': 7, 'config': None}, authority)

    def test_import_preserves_resolution_and_exact_original_method_source(self):
        paths = list(sys.path)
        module = campaign.load_body_module()
        self.assertEqual(paths, sys.path)
        for name in campaign.METHODS:
            method = getattr(getattr(module, campaign.CLASS), name)
            self.assertEqual(method.__code__.co_filename, str(campaign.ROOT/campaign.SOURCE))
            self.assertEqual(method.__code__.co_qualname, campaign.CLASS+'.'+name)

    def test_fresh_original_preserves_complete_failed_state_and_callback_graphs(self):
        retained=[]
        actual=campaign.capture_original(retain=retained)
        self.assertIs(campaign.validate_original(self.corpus,actual),actual)
        self.assertEqual([len(item['graph']['nodes']) for item in actual['cases']],[339,339,346])
        self.assertEqual(len(retained),3)
        for row,case in zip(retained,actual['cases']):
            self.assertIs(row['upstream'].manager,row['manager'])
            self.assertIsNot(row['source'],row['changed'])
            self.assertIs(row['source'].output,row['changed'].output)
            self.assertEqual(campaign.mutation_graph(build,row['request'],row['context_object'],
                row['source'],row['changed']),case['graph'])
        mutant=deepcopy(actual)
        state=campaign.fixed.mapping(mutant['cases'][0]['final']['fields']['_dependencies'])
        self.assertTrue(state)
        # A complete raw document mutation cannot be hidden behind the summary.
        mutant['cases'][0]['final']['fields']['_dependencies']['items'][0][1]={'kind':'str','value':'forged'}
        with self.assertRaises(AssertionError):campaign.validate_original(self.corpus,mutant)

    def test_loaded_body_and_globals_substitution_rejected_before_execution(self):
        from types import FunctionType
        module=campaign.load_body_module();cls=getattr(module,campaign.CLASS)
        name=campaign.METHODS[0];original=getattr(cls,name)
        foreign=FunctionType(original.__code__,dict(original.__globals__),original.__name__)
        foreign.__qualname__=original.__qualname__;foreign.__module__=original.__module__
        with patch.object(cls,name,foreign),self.assertRaisesRegex(AssertionError,'foreign globals'):
            campaign.body_authority(module)
        def replacement(self):return None
        replacement.__qualname__=original.__qualname__;replacement.__module__=original.__module__
        replacement=FunctionType(replacement.__code__,vars(module),original.__name__)
        replacement.__qualname__=original.__qualname__;replacement.__module__=original.__module__
        with patch.object(cls,name,replacement),self.assertRaisesRegex(AssertionError,'complete source'):
            campaign.body_authority(module)

    def test_exact_source_callback_reconstruction_preserves_all_original_mutations(self):
        module=campaign.load_body_module();retained=[]
        campaign.capture_original(module=module,retain=retained)
        for context,row in zip(campaign.CONTEXTS,retained):
            callback=campaign.mutation_recipe(module,context)
            changed=callback(row['source'],row['context_object'])
            self.assertEqual(campaign.mutation_graph(build,row['request'],row['context_object'],row['source'],changed),
                campaign.mutation_graph(build,row['request'],row['context_object'],row['source'],row['changed']))

    def test_live_evidence_keeps_initial_hook_and_inspected_obligation_origins_distinct(self):
        from types import SimpleNamespace
        from biocompiler.core_pipeline_manager import _Binding, _contract_view, _ordered
        from biocompiler.pipeline_callback_objects import CallbackObjects
        from tools import capture_pipeline_fixed_provider_semantics as original
        case = self.corpus.cases[0]
        snapshot = campaign.fixed.snapshot(self.corpus.fixed.document('continuation',
            self.corpus.fixed.continuations[case['id']]['events'][-1]['state_after']))
        raw = snapshot['passes']['behavior_to_synthetic']['contract']
        initial, inspected = (_contract_view(raw, admission=False) for _ in range(2))
        self.assertEqual(len(initial.introduces), 1)
        self.assertIsNot(initial.introduces[0], inspected.introduces[0])
        broker = CallbackObjects()
        def validator(*_args):
            raise AssertionError('Evidence extraction never executes a validator')
        broker.retain(validator)
        validators = broker.retain({raw['checks'][0]['id']: validator})
        initial_ref, inspected_ref = [broker.retain(value.introduces[0]) for value in (initial, inspected)]
        binding = {'kind': 'native', 'identity': 'value/0', 'tree': _ordered(raw['introduces'][0])}
        bodies = [
            {'kind': 'invoke', 'action': 'register-fixed', 'invocation_id': 7,
             'arguments': {'contract': raw, 'obligation_objects': [binding]}},
            {'kind': 'command', 'operation': 'register', 'parent_invocation': 7,
             'arguments': {'contract': raw, 'validators': validators, 'obligation_objects': [initial_ref]}},
            {'kind': 'command', 'operation': 'register', 'parent_invocation': None,
             'arguments': {'contract': raw, 'validators': validators, 'obligation_objects': [inspected_ref]}},
        ]
        live = SimpleNamespace(_objects=broker,
            _bindings={'value/0': _Binding(campaign.canonical(binding['tree']), 'obligation', initial.introduces[0])},
            session=SimpleNamespace(traffic=[]))
        witness = campaign.providers.Witness()
        witness.request, _, _, witness.config = original.authority('static:requested')
        witness.manager = live
        witness.contracts = {raw['id']: inspected}
        witness.providers = {'provider/0': {'pass_id': raw['id'], 'slot': raw['checks'][0]['id'], 'object': validator}}
        def evidence():
            live.session.traffic = [SimpleNamespace(frame=campaign.manager.frame(value)) for value in bodies]
            return witness.evidence(original)
        actual = evidence()
        self.assertIn(initial_ref['handle'], actual['arguments'])
        self.assertIn(inspected_ref['handle'], actual['arguments'])
        bodies[1]['arguments']['obligation_objects'] = [inspected_ref]
        with self.assertRaisesRegex(AssertionError, 'native-root object identity'):
            evidence()
        bodies[1]['arguments']['obligation_objects'] = [initial_ref]
        bodies[2]['arguments']['obligation_objects'] = [initial_ref]
        with self.assertRaisesRegex(AssertionError, 'inspected contract object identity'):
            evidence()


class FixedInitializerReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = campaign.Corpus()

    def fixture(self, directory, count=2):
        receipt = {'artifacts': {}, '_artifact_directory': str(directory)}
        case = self.corpus.cases[0]
        authority = self.corpus.fixed.document('fixed', case['authority'])
        state = campaign.fixed.snapshot(self.corpus.fixed.document('continuation',
            self.corpus.fixed.continuations[case['id']]['events'][-1]['state_after']))
        contracts = {key: value['contract'] for key, value in state['passes'].items()}
        channel, application = campaign.manager.declarations()
        script = Script(receipt)
        from biocompiler.core_pipeline_manager import _ordered
        arguments = {**authority, 'request_tree': _ordered(authority['request']), 'manager_limits': None,
            'request_object': {'handle': 'object/0'}, 'target_object': {'handle': 'object/1'},
            'config_object': {'handle': 'object/2'}}
        arguments['config'] = application['default_generator_config']
        kind = 'synthetic' if count == 2 else 'components'
        seq = script.command('initialize-'+kind, arguments)
        target = {'value': authority['request']['build_request']['target'], 'binding': {'kind': 'host', 'object': arguments['target_object']}}
        capabilities = [('provider/'+str(index*2+j), role+suffix, {'handle': 'object/'+str(10+index*2+j)})
            for index, role in enumerate(initializers.ROLES[:count]) for j, suffix in enumerate(('.producer', '.validator'))]
        expected = emit(script, seq, target, contracts, capabilities, count=count)
        script.reply(seq, {'kind': kind, 'manager': True, 'artifacts': [], 'target': target})
        script.close()
        return receipt, script.rows, contracts, channel, application, expected

    def details(self, receipt, frames, directory, channel, application, count=2):
        details = {}
        campaign.manager.validate_frames(frames, campaign.manager.Artifacts(Path(directory), receipt['artifacts']),
            channel, application, details=details, provider_calls=False,
            initializer='initialize-synthetic' if count == 2 else 'initialize-components')
        return details

    def validate(self, details, contracts):
        initialization = next(item for item in details['commands'] if item['operation'].startswith('initialize-'))
        return initializers.validate(details, initialization, contracts=contracts)

    def test_exact_publication_two_or_three_registrations_and_all_real_broker_traversals(self):
        for count in (2, 3):
            with self.subTest(count=count), tempfile.TemporaryDirectory() as directory:
                receipt, frames, contracts, channel, application, expected = self.fixture(directory, count)
                details = self.details(receipt, frames, directory, channel, application, count)
                actual = self.validate(details, contracts)
                self.assertEqual(actual['commands'], expected['commands'])
                self.assertEqual(list(actual['minted']), expected['minted'])
                self.assertEqual({key: value[1] for key, value in actual['host_documents'].items()}, expected['host_documents'])

    def test_rehashed_publication_role_contract_owner_and_primitive_mutations_fail_semantically(self):
        mutations = (
            ('publication', lambda bodies: next(item for item in bodies if item.get('action') == 'manager-created')['arguments']['target']['value'].__setitem__('id', 'wrong'), 'target authority'),
            ('role', lambda bodies: next(item for item in bodies if item.get('action') == 'native-provider')['arguments'].__setitem__('role', 'behavior_to_synthetic.producer'), 'closure role'),
            ('contract', lambda bodies: next(item for item in bodies if item.get('action') == 'register-fixed')['arguments']['contract'].__setitem__('version', 'wrong'), 'contract differs'),
            ('callback-return', lambda bodies: self.change_hook_return(bodies), 'registration return value'),
            ('callable-result', lambda bodies: self.change_primitive_return(bodies), 'different value'),
            ('primitive-argument', lambda bodies: next(item for item in bodies if item.get('action') == 'is-instance')['arguments'].__setitem__('type', 'tuple'), 'arguments differ'),
        )
        for name, mutate, diagnostic in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                receipt, frames, contracts, channel, application, _ = self.fixture(directory)
                self.validate(self.details(receipt, frames, directory, channel, application), contracts)
                row = {'frames': frames}
                receipt['checks'] = [row]
                reframe(receipt, row, mutate)
                details = self.details(receipt, row['frames'], directory, channel, application)
                with self.assertRaisesRegex(AssertionError, diagnostic):
                    self.validate(details, contracts)

    @staticmethod
    def change_hook_return(bodies):
        identity = next(item['invocation_id'] for item in bodies if item.get('action') == 'register-fixed')
        next(item for item in bodies if item.get('kind') == 'continue' and item['invocation_id'] == identity)['outcome']['value'] = 'leaked'

    @staticmethod
    def change_primitive_return(bodies):
        identity = next(item['invocation_id'] for item in bodies if item.get('action') == 'callable')
        next(item for item in bodies if item.get('kind') == 'continue' and item['invocation_id'] == identity)['outcome']['value'] = False


if __name__ == '__main__':
    unittest.main()
