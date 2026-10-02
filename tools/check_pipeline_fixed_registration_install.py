"""Exact original registration-interception cohort and installed replay authority.

The three unchanged adversarial method bodies are the only mutation recipes.
All original boundary/state documents remain expected-only and retain their
original exclusion classification in the preceding campaign.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager, nullcontext
from copy import deepcopy
import importlib
from pathlib import Path
import sys
from types import FunctionType
from unittest.mock import patch

if __package__:
    from . import check_pipeline_fixed_continuation_install as continuation
else:
    import check_pipeline_fixed_continuation_install as continuation

providers, manager, fixed, r = (continuation.providers, continuation.manager,
    continuation.fixed, continuation.r)
ROOT = manager.ROOT
require, equal, canonical, sha = manager.require, manager.equal, manager.canonical, manager.sha
SCHEMA = 'biocompiler.installed_fixed_registration_interception.v1'
SCOPE = 'three_original_registration_mutations_six_boundaries_three_managers_24_prefix_9_suffix'
RECEIPT_FILE = 'pipeline-fixed-registration.json'
ARTIFACT_DIRECTORY = 'pipeline-fixed-registration-artifacts'
SOURCE = 'tests/test_component_pipeline_audit.py'
CLASS = 'ComponentPipelineAuditTests'
METHODS = (
    'test_duplicate_source_links_cannot_hide_a_provenance_error',
    'test_nonempty_forged_observation_map_cannot_pass',
    'test_valid_but_wrong_source_links_cannot_pass',
)
CONTEXTS = tuple(SOURCE+'::'+CLASS+'.'+method for method in METHODS)
ERROR = {'module': 'biocompiler.compiler.pipeline', 'type': 'PipelineError',
    'message': 'Component pass provenance changed authoritative source links or observations.'}
COVERAGE = {'fixed_boundaries': 136, 'original_manager_contexts': 476,
    'methods': 3, 'boundaries': 6, 'retained_managers': 3,
    'prefix_operations': 24, 'suffix_operations': 9,
    'returned_boundaries': 3, 'raised_boundaries': 3,
    'returned_operations': 30, 'raised_operations': 3,
    'prior_excluded_boundaries': 10, 'remaining_excluded_boundaries': 4}
SOURCES = ('tools/check_pipeline_fixed_registration_install.py',
    'tests/test_pipeline_fixed_registration_campaign.py',
    'tests/test_pipeline_fixed_initializer_receipts.py', 'tools/pipeline_fixed_registration_runtime.py',
    'tests/test_pipeline_fixed_registration_runtime.py', 'tests/pipeline_fixed_registration_fixture.py',
    'tests/test_pipeline_fixed_registration_receipts.py', *continuation.SOURCES)


def overlay_files():
    """Finite import closure for the unchanged original child capture."""
    return (
        'tools/check_realization_binaries.py', 'tools/check_workflow_reproducibility.py',
        'tools/check_pipeline_session_install.py', 'tools/check_pipeline_manager_trace.py',
        'tools/check_pipeline_manager_install.py', 'tools/pipeline_fixed_initializer_receipts.py',
        'tools/check_pipeline_fixed_provider_install.py', 'tools/check_pipeline_fixed_continuation_install.py',
        'tools/check_pipeline_fixed_registration_install.py', 'examples/checked_pipeline.py',
        'examples/component_linking.py', 'tests/test_component_pipeline_audit.py',
        'tools/capture_pipeline_fixed_build_semantics.py', 'examples/temporal_pipeline.py',
        'tools/capture_pipeline_fixed_provider_semantics.py', 'tools/freeze_component_runtime.py',
        'tools/freeze_realization_acceptance.py', 'tests/test_component_pipeline.py',
        'tests/test_semantic_matrix.py', 'tests/test_temporal_generation.py',
        'tests/test_temporal_components.py', 'examples/synthetic_build.py',
        'examples/synthetic_verification.py', 'examples/synthetic_design.py',
        'tests/test_synthetic_design_workflows.py', 'tools/freeze_checked_pipeline.py',
    )


class Corpus:
    """Close the finite cohort without relabeling any preceding excluded call."""
    def __init__(self):
        self.fixed = fixed.Corpus()
        self.boundaries = [case for case in self.fixed.all_cases if case['context'] in CONTEXTS]
        equal([(case['context'], case['api'], case['outcome']) for case in self.boundaries],
            [(context, api, outcome) for context in CONTEXTS for api, outcome in
                (('run_component_pipeline', 'raised'), ('run_synthetic_pipeline', 'returned'))],
            'Original registration boundary cohort differs')
        self.cases = [case for case in self.boundaries if case['api'] == 'run_synthetic_pipeline']
        self.by_context = {case['context']: [case] for case in self.cases}
        self.prefix, self.suffix, self.events = [], [], []
        managers = set()
        for case in self.cases:
            parent = self.fixed.by_id[case['parent']]
            require(parent['parent'] is None and parent['manager'] == case['manager']
                and parent['authority'] == case['authority'] and case['manager'] is not None,
                'Original fixed boundary lost its same physical manager/authority')
            managers.add(case['manager'])
            equal(parent['error'], ERROR, 'Original outer interception failure differs')
            for boundary in (parent, case):
                require(boundary in self.fixed.excluded
                    and boundary['kind'] == 'actual_original_function'
                    and boundary['changed_bindings'] == ['PassManager.register']
                    and boundary['python_only_inputs'] == [],
                    'Original registration interception classification changed')
            require(not self.fixed.continuations[parent['id']]['events'],
                'Raised outer fixed boundary gained a returned-manager suffix')
            entry = self.fixed.continuations[case['id']]
            events = entry['events']
            equal([item['id'] for item in events],
                entry['supported_prefix_events']+entry['pending_callback_dependent_suffix'],
                'Original partial-state continuation order differs')
            equal([event['api'] for event in events],
                ['PassManager.set_dependency']*8 + ['PassManager.register_completion_profile',
                    'PassManager.register', 'PassManager.run'], 'Original interception operation census differs')
            equal([event['id'] for event in events], [case['context']+'/event/'+str(index)
                for index in (*range(132, 140), 142, 145, 154)],
                'Original interception event identities differ')
            require(all(event['outcome'] == 'returned' for event in events[:-1])
                and events[-1]['outcome'] == 'raised' and events[-1]['state_before'] == events[-1]['state_after'],
                'Original failed proposal changed its retained manager state')
            equal(events[-1]['error'], ERROR, 'Original failed run differs')
            initial = fixed.snapshot(self.fixed.document('fixed', case['manager_state']))
            final = fixed.snapshot(self.fixed.document('continuation', events[-1]['state_after']))
            require(list(initial['records']) == list(final['records']) == ['request', 'behavior', 'mechanism']
                and 'synthetic_to_components' not in initial['passes']
                and 'synthetic_to_components' in final['passes'],
                'Original partial state omitted its registration or stored a failed proposal')
            equal(initial['records'], final['records'], 'Failed interception replaced an earlier original record')
            self.prefix.extend(events[:8]); self.suffix.extend(events[8:]); self.events.extend(events)
        require(len(managers) == 3 and len(self.prefix) == 24 and len(self.suffix) == 9
            and Counter(event['outcome'] for event in self.events) == {'returned': 30, 'raised': 3},
            'Original registration cohort was narrowed')
        self.remaining = [case for case in self.fixed.excluded if case not in self.boundaries]
        require(len(self.remaining) == 4 and Counter(case['kind'] for case in self.remaining)
            == {'actual_original_function': 3, 'mocked_boundary': 1},
            'Remaining invalid-input/mocked boundary coverage was lost')

    def metadata(self):
        return {'coverage': COVERAGE, 'fixed_authority': fixed.metadata(self.fixed),
            'original_boundaries': self.boundaries,
            'original_continuations': [self.fixed.continuations[case['id']] for case in self.boundaries],
            'pending': {'remaining': [{'case': case, 'continuation': self.fixed.continuations[case['id']]}
                for case in self.remaining], 'prior_excluded_classification_unchanged': self.fixed.excluded,
                'full_manager_contexts': 476,
                'scope': 'Supplementary exact interception gate; every preceding compatibility gate remains mandatory'}}


def load_body_module(*, installed=False):
    if installed:
        providers.installed_modules()
    paths = list(sys.path)
    try:
        sys.path.extend((str(ROOT), str(ROOT/'tests')))
        module = importlib.import_module(Path(SOURCE).stem)
    finally:
        sys.path[:] = paths
    require(Path(module.__file__).resolve() == ROOT/SOURCE and sys.path == paths,
        'Original registration body import changed source authority')
    if installed:
        providers.installed_modules()
    return module


def body_authority(module):
    """Bind executed functions to full pinned source and their actual globals."""
    cls = getattr(module, CLASS)
    functions = [(module, getattr(cls, name)) for name in (*METHODS, 'run_with_metadata_mutation')]
    functions.append((sys.modules[module.build_request.__module__], module.build_request))
    evidence = []
    for owner, function in functions:
        path = Path(owner.__file__).resolve()
        require(type(function) is FunctionType and function.__globals__ is vars(owner)
            and path.is_relative_to(ROOT) and function.__module__ == owner.__name__,
            'Original registration function has foreign globals or source')
        raw = r.raw_file(path)
        codes = {code.co_qualname: code for code in manager._nested_codes(compile(raw, str(path), 'exec', dont_inherit=True))}
        require(function.__qualname__ in codes and function.__code__ == codes[function.__qualname__]
            and function.__closure__ is None,
            'Original registration loaded body differs from its complete source')
        evidence.append({'path': str(path.relative_to(ROOT)), 'sha256': sha(raw), 'qualname': function.__qualname__})
    return evidence


def run_original_bodies(*, module=None, context=None, prepare=None):
    """Run the unchanged method/helper bodies, retaining original assertions.

    Native callers supply only ``prepare`` for fixture authoring. The original
    fixture's unrelated successful ComponentBuild is not an input to any of
    these three methods and is never supplied as accepted native state.
    """
    module = load_body_module() if module is None else module
    authority = body_authority(module)
    context = context or (lambda name: nullcontext())
    cls = getattr(module, CLASS)
    prepare(cls) if prepare is not None else cls.setUpClass()
    previous = module.PassManager.register
    completed = []
    for name, identity in zip(METHODS, CONTEXTS):
        test = cls(name)
        with context(identity):
            test.setUp()
            try:
                getattr(test, name)()
            finally:
                test.tearDown()
                test.doCleanups()
        require(module.PassManager.register is previous, 'Original patch leaked beyond its method')
        completed.append(identity)
    return {'contexts': completed, 'methods': len(completed), 'status': 'passed',
        'body_source': {'path': SOURCE, 'sha256': sha(r.raw_file(ROOT/SOURCE))}, 'executed_functions': authority}


def authored_fixture(cls, module):
    """Only the unchanged source-defined authored request/history feed Core."""
    cls.request, cls.history = module.build_request()


class NativeWitness(continuation.NativeWitness):
    """Execute the same staged calls; the unchanged patched register owns wrapping."""
    def __init__(self, core, corpus, oracle, module):
        super().__init__(core, corpus, oracle)
        self.module = module
        self.body_codes = {code.co_qualname: code for code in manager._nested_codes(
            compile(r.raw_file(ROOT/SOURCE), str(ROOT/SOURCE), 'exec', dont_inherit=True))}

    def factory(self, request, history, *, until=None, config=None):
        from biocompiler.core_pipeline_manager import CorePassManager
        require(self.context in self.corpus.by_context and self.offsets.get(self.context, 0) == 0,
            'Registration fixed call was duplicated or left its original context')
        self.offsets[self.context] = 1
        expected = self.corpus.by_context[self.context][0]
        frames = tuple(history)
        authority = {'request': request.to_dict(), 'history': [frame.to_dict() for frame in frames],
            'until': until, 'config': None if config is None else config.to_dict()}
        equal(authority, self.corpus.fixed.document('fixed', expected['authority']),
            'Registration original authoring changed before native execution')
        case = {'id': expected['id'], 'guard': set(), 'events': [], 'inspections': [],
            'provider_objects': {}, 'record_objects': {}, 'request': request, 'config': config}
        self.cases.append(case)
        with manager.guarded_execution(case['guard']):
            actual = CorePassManager.from_synthetic(self.core, request, frames, until=until, config=config)
        case['manager'] = actual
        with manager.guarded_execution(case['guard']):
            upstream = actual.build_result('synthetic')
        case['upstream'], case['upstream_sequence'] = upstream, actual.session.last_response.sequence
        case['initial'] = self.inspect(case)
        case['before_records'] = tuple((key, actual._records[key]) for key in ('request', 'behavior', 'mechanism'))
        with manager.guarded_execution(case['guard']):
            preparation = actual.prepare_components()
        case['prepare_sequence'] = actual.session.last_response.sequence
        for key, identity in preparation.dependencies:
            actual.set_dependency(key, identity)
        with manager.guarded_execution(case['guard']):
            profile = actual.component_profile(preparation)
        case['profile_sequence'] = actual.session.last_response.sequence
        actual.register_completion_profile(profile)
        with manager.guarded_execution(case['guard']):
            registration = actual.component_registration(preparation)
        case['registration'], case['registration_sequence'] = registration, actual.session.last_response.sequence
        actual.register(registration.contract, registration.producer, registration.validators)
        # The last real inspection includes the installed host wrapper. Retain
        # its actual object and source-bound closure before any candidate call.
        candidates = [value for value in case['provider_objects'].values()
            if type(value) is FunctionType and value.__globals__ is vars(self.module)
            and value.__qualname__ == CLASS+'.run_with_metadata_mutation.<locals>.register.<locals>.producer']
        require(len(candidates) == 1, 'Original patched base register did not install its actual wrapper')
        wrapper = candidates[0]
        require(wrapper.__code__ == self.body_codes[wrapper.__qualname__]
            and wrapper.__code__.co_freevars == ('mutation', 'source_producer'),
            'Installed wrapper differs from the original source body')
        closure = dict(zip(wrapper.__code__.co_freevars, (cell.cell_contents for cell in wrapper.__closure__)))
        require(closure['source_producer'] is registration.producer, 'Original wrapper captured another native producer')
        mutation = closure['mutation']
        require(type(mutation) is FunctionType and mutation.__globals__ is vars(self.module)
            and mutation.__qualname__.startswith(CLASS+'.'+self.context.rsplit('.', 1)[1]+'.<locals>.')
            and mutation.__code__ == self.body_codes[mutation.__qualname__],
            'Installed wrapper captured another mutation recipe')
        case['wrapper'], case['mutation'] = wrapper, mutation
        try:
            actual.run(registration.contract.id, 'mechanism', 'components')
        except Exception as error:
            case['error_object'] = error
            case['outer_error'] = {'module': type(error).__module__, 'type': type(error).__name__, 'message': str(error)}
            equal(case['outer_error'], ERROR, 'Original native provenance rejection differs')
            require(not actual.session.closed and not actual.session.invalidated,
                'Logical rejection discarded the already-published actual manager')
            case['completed'] = case['events'][-1]['after']
            require(tuple(actual._records) == ('request', 'behavior', 'mechanism')
                and all(actual._records[key] is value for key, value in case['before_records']),
                'Failed native proposal stored or replaced an actual historical record')
            require('source_proposal' in case and 'mutated_proposal' in case and case.get('wrapper_context_same') is True,
                'Original mutation did not observe the actual native producer return')
            case['mutation_graph'] = mutation_graph(self.oracle, request, case['context_object'],
                case['source_proposal'], case['mutated_proposal'])
            raise
        raise AssertionError('Original metadata mutation unexpectedly passed native acceptance')

    @contextmanager
    def observed_callbacks(self):
        from biocompiler.core_pipeline_manager import _NativeProvider
        native_code = _NativeProvider.__call__.__code__
        previous = sys.getprofile()
        def observe(frame, event, value):
            if event == 'return' and frame.f_code is native_code:
                provider = frame.f_locals['self']
                case = self.found(provider._manager)
                if case is not None and case.get('registration') is not None and provider is case['registration'].producer:
                    require('source_proposal' not in case, 'Original wrapper invoked its native producer more than once')
                    case['source_proposal'] = value
                    response = provider._manager.session.last_response
                    require(response.operation == 'call-native-provider', 'Native producer return lost its exact command')
                    case['producer_sequence'] = response.sequence
            for case in self.cases:
                if not case['id'].startswith(str(self.context)+'/event/'):
                    continue
                wrapper = case.get('wrapper')
                if wrapper is not None and frame.f_code is wrapper.__code__:
                    if event == 'call':
                        require('context_object' not in case, 'Original wrapper was invoked twice')
                        case['context_object'] = frame.f_locals['context']
                    elif event == 'return':
                        case['mutated_proposal'] = value
                        case['wrapper_context_same'] = frame.f_locals['context'] is case['context_object']
            if previous is not None:
                previous(frame, event, value)
        sys.setprofile(observe)
        try:
            yield
        finally:
            intact = sys.getprofile() is observe
            sys.setprofile(previous)
            require(intact, 'Registration observation profiler was replaced')


def mutation_graph(oracle, request, context, source, changed):
    """Complete finite producer/mutation object graph, preserving every alias."""
    graph = oracle.Graph()
    roots = {'target': graph.encode(request.target)}
    origins = [[name, graph.encode(value)] for name, value in oracle.providers.source_origins(request)]
    roots['context'] = [[name, graph.encode(getattr(context, name))]
        for name in ('input', 'output', 'target', 'configuration', 'dependencies', 'requirements', 'source_links', 'observation_map')]
    roots['source_proposal'] = graph.encode(source)
    roots['mutated_proposal'] = graph.encode(changed)
    return {'roots': roots, 'source_origins': origins, 'nodes': graph.nodes}


def capture_original(*, module=None, oracle=None, retain=None):
    """Fresh independent original execution; callers retain the whole result."""
    module = load_body_module() if module is None else module
    oracle = continuation.load_oracle(installed=False) if oracle is None else oracle
    from biocompiler.compiler import synthetic, components
    paths = list(sys.path)
    try:
        Observer=providers.tool('freeze_checked_pipeline').Observer
    finally:
        sys.path[:] = paths
    encoder = Observer((SOURCE,))
    code = compile(r.raw_file(ROOT/SOURCE), str(ROOT/SOURCE), 'exec', dont_inherit=True)
    wrapper_code = next(item for item in manager._nested_codes(code)
        if item.co_qualname == CLASS+'.run_with_metadata_mutation.<locals>.register.<locals>.producer')
    rows, current = [], None
    previous = sys.getprofile()
    @contextmanager
    def context(name):
        nonlocal current
        current = {'context': name}
        rows.append(current)
        try:
            yield
        finally:
            current = None
    def state(value):
        return deepcopy(encoder.store.documents[encoder.state(value)])
    def observe(frame, event, value):
        if current is not None:
            if event == 'return' and frame.f_code is synthetic.run_synthetic_pipeline.__code__:
                require(value is not None and 'manager' not in current, 'Original synthetic boundary did not return once')
                current['manager'], current['initial'], current['upstream'] = value.manager, state(value.manager), value
                current['requested_config'] = frame.f_locals['requested_config']
            if frame.f_code == wrapper_code:
                if event == 'call':
                    require('context_object' not in current, 'Original mutation wrapper ran twice')
                    current['context_object'] = frame.f_locals['context']
                elif event == 'return':
                    current['changed'] = value
            if event == 'return' and frame.f_globals is vars(components) \
                    and frame.f_code.co_qualname == 'run_component_pipeline.<locals>.generate':
                require('source' not in current and value is not None, 'Original fixed producer did not return once')
                current['source'] = value
            if event == 'return' and frame.f_code is components.run_component_pipeline.__code__:
                require(value is None and frame.f_locals['manager'] is current['manager'],
                    'Original failed component call replaced its retained manager')
                current['final'] = state(current['manager'])
        if previous is not None:
            previous(frame, event, value)
    sys.setprofile(observe)
    try:
        with oracle.portable_sources():
            execution = run_original_bodies(module=module, context=context,
                prepare=lambda cls: authored_fixture(cls, module))
    finally:
        intact = sys.getprofile() is observe
        sys.setprofile(previous)
        require(intact, 'Original registration capture profiler was replaced')
    request = getattr(module, CLASS).request
    result = {'execution': execution, 'providers': encoder.providers, 'cases': []}
    for row in rows:
        require(set(row) == {'context', 'manager', 'initial', 'context_object', 'source', 'changed', 'final', 'upstream', 'requested_config'},
            'Original mutation capture lost a real callback/boundary')
        result['cases'].append({'context': row['context'], 'initial': row['initial'], 'final': row['final'],
            'graph': mutation_graph(oracle, request, row['context_object'], row['source'], row['changed'])})
        if retain is not None:
            retain.append({**row,'request':request,'history':getattr(module,CLASS).history,
                'wrapper':row['manager']._passes['synthetic_to_components'][1]})
    return result


class ProviderBijection:
    """Bridge only source-proven slots across the two original namespaces."""
    def __init__(self):
        self.forward, self.reverse, self.slots = {}, {}, {}

    def align(self, actual, expected, *, family, original_providers, actual_providers=None):
        result = deepcopy(actual)
        require(set(result) == set(expected), 'Registration manager fields were omitted')
        for field in ('passes', 'provider_history'):
            require(set(result[field]) == set(expected[field]), 'Registration manager provider inventory differs')
            for key, original in expected[field].items():
                got = result[field][key]
                equal(got['contract'], original['contract'], 'Registration manager contract differs')
                require(set(got['validators']) == set(original['validators']), 'Registration validator slot inventory differs')
                for slot in ('producer', *original['validators']):
                    old = original['producer'] if slot == 'producer' else original['validators'][slot]
                    token = got['producer'] if slot == 'producer' else got['validators'][slot]
                    require(type(token) is str and type(old) is str, 'Registration provider identity is missing')
                    source = original_providers[old]
                    wrapper = original['contract']['id'] == 'synthetic_to_components' and slot == 'producer'
                    if wrapper:
                        require(source['file'] == SOURCE and source['qualname'] ==
                            CLASS+'.run_with_metadata_mutation.<locals>.register.<locals>.producer'
                            and source['freevars'] == ['mutation', 'source_producer'],
                            'Original wrapped provider lacks its exact source recipe')
                    else:
                        module, function = fixed.SLOTS[original['contract']['id'], slot]
                        require(source['file'] == 'src/biocompiler/compiler/'+module+'.py'
                            and source['qualname'] == 'run_'+('component' if module == 'components' else module)
                                +'_pipeline.<locals>.'+function,
                            'Original provider lacks its exact fixed source slot')
                    if actual_providers is not None:
                        descriptor = actual_providers[token]
                        for name in ('class', 'qualname', 'freevars'):
                            equal(descriptor[name], source[name], 'Fresh original provider source changed: '+name)
                        require(descriptor['file'] in (source['file'], Path(source['file']).name),
                            'Fresh original provider came from another source file')
                    identity = original['contract']['id'], slot
                    require(self.forward.get((family, token), old) == old
                        and self.reverse.get((family, old), token) == token
                        and self.slots.get(identity, token) == token,
                        'Registration provider physical identity changed')
                    require(all(value != token or previous == identity for previous, value in self.slots.items()),
                        'Distinct registration provider slots physically aliased')
                    self.forward[family, token], self.reverse[family, old] = old, token
                    self.slots[identity] = token
                    if slot == 'producer':
                        got['producer'] = old
                    else:
                        got['validators'][slot] = old
        equal(result, expected, 'Complete original registration manager state differs')
        return result


def validate_original(corpus, value):
    require(type(value) is dict and set(value) == {'execution', 'providers', 'cases'}, 'Incomplete fresh registration original')
    equal(value['execution']['contexts'], list(CONTEXTS), 'Fresh original registration methods changed order')
    require(value['execution']['methods'] == 3 and value['execution']['status'] == 'passed',
        'Fresh original registration assertions did not all pass')
    require(len(value['cases']) == 3, 'Fresh original registration observation census differs')
    for case, observed in zip(corpus.cases, value['cases']):
        require(set(observed) == {'context', 'initial', 'final', 'graph'} and observed['context'] == case['context'],
            'Fresh original registration case differs')
        require(observed['initial']['manager'] == observed['final']['manager'], 'Fresh original replaced a failed manager')
        aliases = ProviderBijection()
        parent = corpus.fixed.by_id[case['parent']]
        for name, boundary in (('initial', case), ('final', parent)):
            aliases.align(fixed.snapshot(observed[name]), fixed.snapshot(corpus.fixed.document('fixed', boundary['manager_state'])),
                family='fixed', original_providers=corpus.fixed.indexes['fixed']['providers'],
                actual_providers=value['providers'])
        require(type(observed['graph']) is dict and set(observed['graph']) == {'roots', 'source_origins', 'nodes'}
            and len(observed['graph']['nodes']) > 300, 'Complete original mutation graph was narrowed')
    return value


def mutation_recipe(module, context):
    """Recover only the exact source-defined callback, never a manager decision."""
    authority = body_authority(module)
    require(context in CONTEXTS and authority, 'Unknown original mutation source')
    cls = getattr(module, CLASS)
    test = cls(context.rsplit('.', 1)[1])
    method = getattr(test, context.rsplit('.', 1)[1])
    codes = [code for code in manager._nested_codes(method.__func__.__code__)
        if code.co_qualname.startswith(method.__func__.__qualname__+'.<locals>.')
        and code.co_name in ('<lambda>', 'mutate')]
    require(len(codes) == 1 and codes[0].co_freevars in ((), ('self',)), 'Original mutation closure shape changed')
    def cell(value):
        return (lambda: value).__closure__[0]
    closure = tuple(cell(test) for _ in codes[0].co_freevars) or None
    return FunctionType(codes[0], vars(module), codes[0].co_name, closure=closure)


def witness_evidence(case, oracle):
    actual = case['manager']
    roots = continuation.source_roots(oracle, case['request'], actual._provider_config)
    retained = actual._objects._objects
    def handle(value):
        found = [name for name, item in retained.items() if item is value]
        require(len(found) == 1, 'Actual interception object has no unique retained handle')
        return found[0]
    commands = [r.decode(item.frame[9:]) for item in actual.session.traffic if item.direction == 'client']
    event = next(item for item in case['events'] if item['api'] == 'PassManager.register')
    registered = next(item for item in commands if item.get('sequence') == event['sequence'])['arguments']
    registration = case['registration']
    require(all(value is not case['source_proposal'] for value in retained.values()),
        'Original callback source proposal gained an unrequested host capability')
    require(actual._objects.resolve(registered['producer']) is case['wrapper']
        and actual._objects.resolve(registered['validators']) is registration.validators,
        'Original intercepted registration lost its actual wrapper or prepared validator mapping')
    require(len(registered['obligation_objects']) == len(registration.contract.introduces)
        and all(actual._objects.resolve(ref) is item for ref, item in
            zip(registered['obligation_objects'], registration.contract.introduces)),
        'Original intercepted registration lost prepared obligation instances')
    return {name: case[name] for name in ('events', 'inspections', 'initial', 'completed', 'upstream_sequence',
        'prepare_sequence', 'profile_sequence', 'registration_sequence', 'producer_sequence', 'outer_error')} | {
        'sources': {name: [key for key, root in roots.items() if value is root]
            for name, value in retained.items() if any(value is root for root in roots.values())},
        'providers': {token: handle(value) for token, value in
            {**actual._native_providers, **case['provider_objects']}.items()},
        'record_identities': {token: value.id for token, value in case['record_objects'].items()},
        'wrapper': {'object': handle(case['wrapper']), 'context': handle(case['context_object']),
            'source_proposal': None, 'mutated_proposal': handle(case['mutated_proposal']),
            'source_provider': handle(registration.producer),
            'wrapper_qualname': case['wrapper'].__qualname__, 'mutation_qualname': case['mutation'].__qualname__,
            'context_same': case['wrapper_context_same']}}


def replay_primitives(invocations, replay, *, native, host_provider=None, source_links=None):
    """Check every published host operation against its exact retained objects."""
    from biocompiler.core_pipeline_manager import _ordered
    from biocompiler.compiler.pipeline import SourceLink
    for item in invocations:
        action, args = item['action'], item['arguments']
        result = providers.returned(item)
        if action == 'provider-reference':
            handle = providers.reference(args['object'])
            require(handle in native or host_provider is not None and handle == host_provider[0],
                'Interception referred to an unrelated provider')
            wanted = {'kind': 'native', 'provider_id': native[handle]} if handle in native else {
                'kind': 'host', 'object': args['object']}
            equal(result, wanted, 'Interception changed exact provider origin')
        elif action == 'bind-provider':
            require(host_provider is not None and args == {'provider_id': host_provider[1],
                'object': {'handle': host_provider[0]}}, 'Interception bound another callback token')
            replay.execute(item)

        elif action == 'ordered-json':
            equal(result, _ordered(replay.host[providers.reference(args['object'])]),
                'Interception ordered observation differs from actual callback object')
        elif action == 'set-equal':
            equal(result, set(replay.host[providers.reference(args['object'])]) == set(args['values']),
                'Interception mapping key equality changed')
        elif action == 'source-link-set-equal':
            require(source_links is not None, 'Source-link equality escaped its actual candidate callback')
            equal(args['expected'], [vars(value) for value in source_links],
                'Native source-link authority differs from actual fixed producer')
            got = [replay.host[providers.reference(ref)] for ref in args['objects']]
            equal(result, set(got) == set(SourceLink(**value) for value in args['expected']),
                'Native source-link equality differs from actual original objects')
        else:
            require(action not in ('call-provider', 'hydrate-context', 'register-fixed', 'manager-created',
                'native-provider', 'origin-reference', 'release'), 'Unexpected interception callback action')
            replay.execute(item)


def proposal_actions(step, proposal, *, changed, context, contract, source_links):
    """Closed host-observation recipe of the three metadata-failure paths.

    The step callback either emits a test-only frame or checks the next real
    frame. This source-bound ordering checks observations, never acceptance.
    Native scope, freshness, correspondence and final rejection remain native.
    """
    def attr(value, name): return step('attr', {'object':value,'name':name})
    def literal(value, kind='json'): return step('literal',{'kind':kind,'value':value})
    def freeze(value):
        frozen=step('freeze-json',{'object':value})
        return step('ordered-json',{'object':frozen})
    def comparison(value, other):
        return step('compare',{'left':value,'right':literal(other),'operator':'eq'})
    def membership(value, collection):
        return step('contains',{'container':literal(collection,'set'),'item':value})
    require(changed.search_status=='candidate' and changed.output is not None and not changed.obligations,
        'Metadata-failure recipe escaped its source-defined proposal shape')
    step('is-instance',{'object':proposal,'type':'PassResult'})
    membership(attr(proposal,'search_status'),['candidate','no_candidate_found'])
    comparison(attr(proposal,'search_status'),'no_candidate_found')
    step('is-none',{'object':attr(proposal,'output')})
    output=attr(proposal,'output')
    document=step('document',{'object':output})
    step('is-instance',{'object':document,'type':'Mapping'})
    get=attr(document,'get')
    schema=step('call',{'callable':get,'args':[literal('schema_version')],'kwargs':{}})
    step('is-instance',{'object':schema,'type':'str'})
    stripped=step('call',{'callable':attr(schema,'strip'),'args':[],'kwargs':{}})
    step('truth',{'object':stripped});freeze(document)
    collection=step('tuple',{'object':attr(proposal,'source_links')})
    iterator=step('iter',{'object':collection})
    links=[]
    for _ in changed.source_links:
        item=step('next',{'object':iterator})
        require(item['exhausted'] is False,'Metadata-failure recipe omitted a source link')
        links.append(item['object'])
    equal(step('next',{'object':iterator}),{'exhausted':True,'object':None},'Metadata-failure source link inventory differs')
    for link in links:
        step('is-instance',{'object':link,'type':'SourceLink'})
        comparison(attr(link,'pass_name'),contract.id)
    raw=changed.output.to_dict()
    for key in contract.operation_path:raw=raw[key]
    input_ids=[node['id'] for node in context.input['mechanism']['nodes']]
    for link in links:
        membership(attr(link,'requirement_id'),list(context.requirements))
        membership(attr(link,'target_node_id'),[node['id'] for node in raw['nodes']])
        membership(attr(link,'source_node_id'),input_ids)
    require(contract.requires_source_map and contract.requires_observation_map,'Metadata-failure source contract changed')
    step('set-attribute-equal',{'objects':links,'name':'requirement_id','values':list(context.requirements)})
    step('is-instance',{'object':attr(proposal,'observation_map'),'type':'Mapping'})
    freeze(attr(proposal,'observation_map'))
    iterator=step('iter',{'object':attr(proposal,'obligations')})
    equal(step('next',{'object':iterator}),{'exhausted':True,'object':None},'Metadata failure invented producer obligations')
    if len(changed.source_links)==len(source_links):
        step('source-link-set-equal',{'objects':links,'expected':[dict(vars(link)) for link in source_links]})


def validate_case(corpus, expected, actual, evidence, details, oracle, source, original, *, module=None):
    """Bind the failed original workflow to one actual persistent native manager."""
    from biocompiler.core_pipeline_manager import _ordered
    from biocompiler.core_pipeline_provider_views import StructuralViews, origin_reference
    fields = {'events', 'inspections', 'initial', 'completed', 'upstream_sequence', 'prepare_sequence',
        'profile_sequence', 'registration_sequence', 'producer_sequence', 'sources', 'providers',
        'record_identities', 'wrapper', 'outer_error'}
    require(type(evidence) is dict and set(evidence) == fields, 'Incomplete interception evidence')
    equal(actual, original['graph'], 'Complete actual mutation graph differs from independent original')
    equal(evidence['outer_error'], ERROR, 'Original outer boundary exception differs')
    commands = {item['sequence']: item for item in details['commands']}
    require(len(commands) == len(details['commands']), 'Interception command sequence was reused')
    ordered = sorted(commands.values(), key=lambda item: item['start_frame'])
    init = ordered[0]
    require(init['operation'] == 'initialize-synthetic' and init['parent_invocation'] is None,
        'Interception changed its same-manager initialization')
    args, request, config_argument = init['arguments'], source['request'], source['config']
    _, application = manager.declarations()
    requested = config_argument if config_argument is not None else StructuralViews().config(application['default_generator_config'])
    authority = corpus.fixed.document('fixed', expected['authority'])
    equal({key: args[key] for key in ('request', 'history', 'until')},
        {key: authority[key] for key in ('request', 'history', 'until')}, 'Interception changed authored authority')
    equal(args['config'], requested.to_dict(), 'Interception changed requested configuration')
    equal(args['request_tree'], _ordered(request.to_dict()), 'Interception changed authored mapping order')
    require(args['manager_limits'] is None, 'Interception silently changed manager limits')
    views = continuation.ReceiptViews(request, requested, application)
    roots = continuation.source_roots(oracle, request, requested)
    names_seen = set()
    for handle, names in evidence['sources'].items():
        require(type(names) is list and names and all(name in roots and name not in names_seen for name in names),
            'Interception source-root census differs')
        require(all(roots[name] is roots[names[0]] for name in names), 'Interception merged distinct authoring objects')
        views.bind({'handle': handle}, roots[names[0]]); names_seen.update(names)
    for key, name in (('request_object', 'request'), ('config_object', 'requested_config'), ('target_object', 'target')):
        require(views.host.get(providers.reference(args[key])) is roots[name], 'Interception detached actual '+name)
    initial = providers.succeeded(init)
    equal(initial, {'kind': 'synthetic', 'manager': True, 'artifacts': ['candidate', 'pipeline_result', 'selection_result'],
        'target': {'value': request.target.to_dict(), 'binding': {'kind': 'host', 'object': args['target_object']}}},
        'Interception initialization lost its actual manager result')
    views.value._initialization(initial, 'synthetic')
    expanded = continuation.expand_inspections(ordered)
    hooks = providers.initializers.validate(details, init, contracts={key: item['contract']
        for key, item in expanded[evidence['initial']]['snapshot']['passes'].items()}, views=views)
    document_sources = {providers.reference(args['target_object']): (-1, request.target.to_dict()),
        providers.reference(args['config_object']): (-1, requested.to_dict()), **hooks['host_documents']}
    bindings = providers.BindingCensus(details, document_sources); bindings.initialization(hooks)
    minted = dict(hooks['minted'])
    source_positions = {providers.reference(args[key]): -1 for key in ('request_object', 'config_object', 'target_object')}
    invokes = sorted(details['invocations'].values(), key=lambda item: item['start_frame'])
    for invocation in invokes:
        action, arguments = invocation['action'], invocation['arguments']
        if action == 'native-provider':
            token, role = arguments['provider_id'], arguments['role']; reference = providers.returned(invocation)
            if invocation['command_sequence'] == init['sequence']:
                equal(minted.get(token), (reference, role, invocation['end_frame']), 'Initial proxy lost its registration hook')
                continue
            require(invocation['command_sequence'] == evidence['registration_sequence'] and token not in minted
                and role in ('synthetic_to_components.producer', 'synthetic_to_components.validator'),
                'Interception minted an unrelated native provider')
            views.provider(token, role, reference); minted[token] = reference, role, invocation['end_frame']
        elif action == 'origin-reference':
            require(set(arguments) == {'root', 'path'} and invocation['command_sequence']
                in (evidence['upstream_sequence'], evidence['producer_sequence']),
                'Interception used a late or unrelated source origin')
            value = origin_reference(request, arguments['root'], arguments['path'])
            handle = providers.reference(providers.returned(invocation))
            require(views.host.get(handle) is value, 'Interception origin detached its actual source object')
            source_positions.setdefault(handle, invocation['end_frame'])
    require(len(minted) == 6 and len({item[1] for item in minted.values()}) == 6,
        'Interception omitted a fixed native closure')
    require(set(evidence['sources']) == set(source_positions), 'Interception has unclaimed source handles')
    wrapper = evidence['wrapper']
    require(type(wrapper) is dict and set(wrapper) == {'object', 'context', 'source_proposal', 'mutated_proposal',
        'source_provider', 'wrapper_qualname', 'mutation_qualname', 'context_same'} and wrapper['context_same'] is True
        and wrapper['source_proposal'] is None, 'Incomplete original wrapper identity evidence')
    require(wrapper['wrapper_qualname'] == CLASS+'.run_with_metadata_mutation.<locals>.register.<locals>.producer',
        'Original wrapper code identity changed')
    host_tokens = [token for token, handle in evidence['providers'].items() if handle == wrapper['object']]
    require(len(host_tokens) == 1 and host_tokens[0] not in minted, 'Wrapped producer has no distinct actual provider token')
    wrapper_token = host_tokens[0]
    equal(evidence['providers'], {**{token: providers.reference(item[0]) for token, item in minted.items()},
        wrapper_token: wrapper['object']}, 'Interception provider physical census differs')
    bind_events = [item for item in invokes if item['action'] == 'bind-provider']
    require(len(bind_events) == 1 and bind_events[0]['arguments'] == {'provider_id': wrapper_token,
        'object': {'handle': wrapper['object']}} and providers.returned(bind_events[0]) is None,
        'Original host wrapper lacks its actual provider binding')
    bound = {token: item[0] for token, item in minted.items()}
    bound[wrapper_token] = {'handle': wrapper['object']}
    aliases, physical = ProviderBijection(), {}
    used, inspection_order = {init['sequence'], *hooks['commands']}, []
    def inspect(sequence, raw_original, family='continuation'):
        require(sequence in expanded, 'Interception lost a compact original observation')
        command = commands[sequence]
        require(command['operation'] == 'inspect-ordered-references' and command['arguments'] == {}
            and command['parent_invocation'] is None, 'Interception inspection authority changed')
        if sequence not in used: inspection_order.append(sequence)
        used.add(sequence); raw = expanded[sequence]
        available = {token: ref for token, ref in bound.items() if
            (bind_events[0]['end_frame'] if token == wrapper_token else minted[token][2]) < command['end_frame']}
        projected = manager.comparison_snapshot(raw, {item['provider_id']: item['provider_id'] for item in raw['providers']},
            previous=physical, bound=available)
        for group in ('passes', 'provider_history'):
            for item in projected['state'][group].values():
                producer = item['producer']; role = item['contract']['id']+'.producer'
                require((producer == wrapper_token and role == 'synthetic_to_components.producer')
                    or producer in minted and minted[producer][1] == role, 'Interception producer role changed')
                require(all(token in minted and minted[token][1] == item['contract']['id']+'.validator'
                    for token in item['validators'].values()), 'Interception validator role changed')
        aliases.align(projected['state'], fixed.snapshot(raw_original), family=family,
            original_providers=corpus.fixed.indexes[family]['providers'])
        equal(raw['order'], continuation.original_order(raw_original), 'Interception changed original manager order')
        for key, envelope in raw['snapshot']['records'].items():
            bindings.record(envelope, command['end_frame'])
            require(views.value._record(envelope).id == key, 'Interception record name/incarnation changed')
        return command
    inspect(evidence['initial'], corpus.fixed.document('fixed', expected['manager_state']), 'fixed')
    originals = corpus.fixed.continuations[expected['id']]['events']
    require(len(evidence['events']) == len(originals) == 11, 'Interception omitted an original manager operation')
    event_commands = []
    previous_after, previous_inspection = commands[evidence['initial']]['end_frame'], evidence['initial']
    for original_event, row in zip(originals, evidence['events']):
        equal({key: row.get(key) for key in ('api', 'context', 'outcome')},
            {key: original_event[key] for key in ('api', 'context', 'outcome')}, 'Interception original event order differs')
        before = inspect(row['before'], corpus.fixed.document('continuation', original_event['state_before']))
        after = inspect(row['after'], corpus.fixed.document('continuation', original_event['state_after']))
        require(type(row.get('before_reused')) is bool, 'Interception omitted explicit before-state reuse')
        if row['before_reused']:
            latest = max((item for item in commands.values() if item['end_frame'] < row['start_frame']), key=lambda item:item['end_frame'])
            require(latest['sequence'] == row['before'] == previous_inspection
                and latest['end_frame']+1 == row['start_frame'], 'Interception reused state across native traffic')
        else:
            require(previous_after < before['start_frame'], 'Interception reordered complete original event triples')
        require(row['after'] != row['before'] and after['start_frame'] > before['end_frame'], 'Missing fresh failed-workflow after-state')
        previous_after, previous_inspection = after['end_frame'], row['after']
        command = commands.get(row['sequence'])
        require(command is not None and row['sequence'] not in used, 'Interception reused another operation receipt')
        used.add(row['sequence']); event_commands.append(command)
        operation = original_event['api'].split('.')[-1].replace('_', '-')
        require(command['operation'] == operation and command['parent_invocation'] is None
            and row['start_frame'] == command['start_frame'] == before['end_frame']+1
            and row['end_frame'] == command['end_frame']+1 == after['start_frame'],
            'Interception event lost its exact before/action/after interval')
        wanted = fixed.unpack(corpus.fixed.document('continuation', original_event['arguments']))['bound']
        if operation == 'register':
            equal(command['arguments']['contract'], wanted['contract'], 'Interception changed original registration contract')
            equal(command['arguments']['producer'], {'handle': wrapper['object']}, 'Interception bypassed its original wrapper')
            require(bind_events[0]['command_sequence'] == command['sequence'], 'Wrapper binding belongs to another registration')
        else:
            equal(command['arguments'], wanted, 'Interception changed original command arguments')
        if original_event['outcome'] == 'raised':
            equal(row['error'], ERROR, 'Interception changed the actual original exception')
            equal(command['outcome'], {'status':'rejected','value':{**ERROR,'attributes':{},'attributes_tree':['object',[]]}},
                'Interception error detached from actual native rejection')
            require(set(row) == {'api','context','outcome','error','before','after','start_frame','end_frame','sequence','before_reused'},
                'Failed native operation invented a returned value')
        else:
            require(providers.succeeded(command) is None and row['value'] is None,
                'Original unit mutation returned an invented value')
    require(evidence['completed'] == evidence['events'][-1]['after'], 'Final partial state is not the failed run after-state')
    parent = corpus.fixed.by_id[expected['parent']]
    inspect(evidence['completed'], corpus.fixed.document('fixed', parent['manager_state']), 'fixed')
    def phase(name, operation, arguments):
        sequence = evidence[name]; command = commands.get(sequence)
        require(command is not None and sequence not in used and command['operation'] == operation
            and command['parent_invocation'] is None, 'Missing or repeated interception native phase')
        used.add(sequence); equal(command['arguments'], arguments, 'Interception phase authority changed')
        return command, providers.succeeded(command)
    upstream_command, upstream_raw = phase('upstream_sequence','build-result',{'kind':'synthetic'})
    prepare_command, prepared_raw = phase('prepare_sequence','prepare-components',{})
    require(init['end_frame'] < upstream_command['start_frame'] < upstream_command['end_frame']
        < commands[evidence['initial']]['start_frame'] < commands[evidence['initial']]['end_frame']
        < prepare_command['start_frame'] < prepare_command['end_frame'] < commands[evidence['events'][0]['before']]['start_frame'],
        'Interception preparation moved across original observations')
    prepared = views.value._component_preparation(prepared_raw)
    equal(list(map(list, prepared.dependencies)), [[item['arguments']['key'],item['arguments']['identity']]
        for item in event_commands[:8]], 'Interception dependency preparation changed original order/values')
    phase_args = {'preparation_id':prepared.identity}
    profile_command, profile = phase('profile_sequence','component-profile',phase_args)
    registration_command, native_registration = phase('registration_sequence','component-registration',phase_args)
    equal(profile,event_commands[8]['arguments']['profile'],'Interception changed prepared completion profile')
    equal(native_registration['contract'],event_commands[9]['arguments']['contract'],'Interception changed prepared contract')
    for phase_command,left,right in ((profile_command,7,8),(registration_command,8,9)):
        require(commands[evidence['events'][left]['after']]['end_frame'] < phase_command['start_frame']
            < phase_command['end_frame'] < commands[evidence['events'][right]['before']]['start_frame'],
            'Interception native phase moved across an original mutation')
    registration = views.value._component_registration(native_registration)
    require(providers.reference(native_registration['producer']) == wrapper['source_provider'],
        'Original wrapper captured another native producer')
    register, run = event_commands[9:]
    views.bind(register['arguments']['validators'],registration.validators)
    require(len(register['arguments']['obligation_objects']) == len(registration.contract.introduces),
        'Interception introduced obligation census differs')
    for ref,item in zip(register['arguments']['obligation_objects'],registration.contract.introduces):
        views.bind(ref,item); bindings.host[providers.reference(ref)]=[(register['start_frame']-1,item.to_dict())]
    bindings.registration(native_registration['contract'],register['arguments']['obligation_objects'],register['end_frame'])
    # Historical public build and source candidate are hydrated only from their
    # actual native receipts, sharing the production structural cache.
    for envelope in (upstream_raw['sources']['candidate'],upstream_raw['result']['artifact']):
        bindings.record(envelope,upstream_command['end_frame'])
    upstream = views.value._build_value(upstream_raw,kind='synthetic',result=views.value._result_value)
    require(upstream.manager is views.value and upstream.result.artifact is views.value._records['mechanism'],
        'Interception historical build lost its actual source record')
    run_invocations=[item for item in invokes if item['command_sequence']==run['sequence']]
    contexts=[item for item in run_invocations if item['action']=='hydrate-context']
    callbacks=[item for item in run_invocations if item['action']=='call-provider']
    require(len(contexts)==len(callbacks)==1,'Interception lost or duplicated its original wrapper call')
    context_invocation,callback=contexts[0],callbacks[0]
    bindings.context(context_invocation)
    context_ref=providers.returned(context_invocation)
    equal(context_ref,{'handle':wrapper['context']},'Interception context identity changed')
    equal(callback['arguments'],{'provider_id':wrapper_token,'context':context_ref},'Interception called another producer')
    require(context_invocation['end_frame'] < callback['start_frame'],'Interception used context before publication')
    context_args=context_invocation['arguments']
    from biocompiler.compiler.pipeline import PassContext
    raw_context=context_args['bindings']
    source_record=views.value._records['mechanism']
    document=context_args['document']
    equal(document,{'input':source_record.to_dict()['payload'],'output':None,'target':request.target.to_dict(),
        'configuration':{},'dependencies':fixed.snapshot(corpus.fixed.document('continuation',originals[-1]['state_before']))['dependencies'],
        'requirements':list(source_record.requirements),'source_links':[],'observation_map':{}},
        'Interception producer context differs from actual source record and current state')
    equal(raw_context['input'],expanded[evidence['initial']]['snapshot']['records']['mechanism']['bindings']['payload'],
        'Interception context lost original source payload capability')
    equal(raw_context['target'],{'kind':'host','object':args['target_object']},'Interception context changed actual target capability')
    context=PassContext(views.value._binding(raw_context['input']),None,views.value._binding(raw_context['target'],flavor='target'),
        views.value._binding(raw_context['configuration']),views.value._binding(raw_context['dependencies']),
        views.value._binding(raw_context['requirements']),(),views.value._binding(raw_context['observation_map'],flavor='default-observation'))
    views.bind(context_ref,context)
    direct=commands.get(evidence['producer_sequence'])
    callback_id=next(key for key,value in details['invocations'].items() if value is callback)
    require(direct is not None and direct['sequence'] not in used and direct['operation']=='call-native-provider'
        and direct['parent_invocation']==callback_id and callback['start_frame'] < direct['start_frame']
        < direct['end_frame'] < callback['end_frame'],'Original callback lost its nested native producer call')
    used.add(direct['sequence'])
    token=next(token for token,item in minted.items() if item[1]=='synthetic_to_components.producer')
    equal(direct['arguments'],{'provider_id':token,'context_id':context_args['context_id']},'Nested original producer authority differs')
    source_proposal=views.value._native_return(providers.succeeded(direct),
        role='synthetic_to_components.producer',input_payload=context.input)
    module=load_body_module() if module is None else module
    mutation=mutation_recipe(module,expected['context'])
    require(mutation.__qualname__==wrapper['mutation_qualname'],'Original mutation source closure changed')
    changed=mutation(source_proposal,context)
    equal(providers.returned(callback),{'handle':wrapper['mutated_proposal']},'Native manager consumed another callback result')
    equal(mutation_graph(oracle,request,context,source_proposal,changed),actual,
        'Actual producer/context receipts do not reproduce the full original mutation graph')
    replay=providers.initializers.PrimitiveReplay()
    for handle,value in views.host.items():replay.bind({'handle':handle},value)
    # This callable is a capability-only stand-in. The callback itself was
    # reconstructed above from exact original source and native proposal.
    replay.bind({'handle':wrapper['object']},providers.initializers._Capability())
    native={providers.reference(item[0]):token for token,item in minted.items()}
    registration_actions=[item for item in invokes if item['command_sequence']==register['sequence']]
    providers.initializers.registration_primitives(registration_actions,register,register['arguments']['producer'],
        register['arguments']['validators'],native,replay,host_provider=(wrapper['object'],wrapper_token))
    replay.bind({'handle':wrapper['mutated_proposal']},changed)
    consumption=[item for item in run_invocations if item not in (context_invocation,callback)]
    require(consumption and all(item['start_frame']>callback['end_frame'] and item['parent_invocation'] is None for item in consumption),
        'Original candidate observations moved outside native post-callback validation')
    position=0
    def step(action,arguments):
        nonlocal position
        require(position<len(consumption),'Native metadata observation trace ended early')
        item=consumption[position];position+=1
        equal((item['action'],item['arguments']),(action,arguments),'Native metadata observation action/order/object differs')
        replay_primitives([item],replay,native=native,source_links=source_proposal.source_links)
        return providers.returned(item)
    proposal_actions(step,{'handle':wrapper['mutated_proposal']},changed=changed,context=context,
        contract=registration.contract,source_links=source_proposal.source_links)
    require(position==len(consumption),'Native metadata failure contains an extra host observation')
    require(any(item['action']=='document' and replay.host[providers.reference(item['arguments']['object'])] is changed.output
        for item in consumption),'Native failed run did not observe the actual changed candidate document')
    equal(evidence['inspections'],sorted(inspection_order,key=lambda seq:commands[seq]['start_frame']),
        'Interception contains an unclaimed or reordered inspection')
    require(used==set(commands),'Interception contains an unclaimed native command')
    for item in invokes:
        owner=item['command_sequence']
        if owner in (init['sequence'],*hooks['commands'],register['sequence'],run['sequence']):
            continue
        permitted = ('native-provider',) if owner==registration_command['sequence'] else (
            ('origin-reference',) if owner in (upstream_command['sequence'],direct['sequence']) else ())
        require(item['action'] in permitted,'Interception contains an unclaimed host invocation')
    def source_available(value,frame):
        if type(value) is dict:
            if value.get('kind')=='host':
                handle=providers.reference(value['object'])
                require(handle in source_positions and source_positions[handle]<frame,
                    'Interception typed source was used before its actual origin publication')
            for child in value.values():source_available(child,frame)
        elif type(value) is list:
            for child in value:source_available(child,frame)
    source_available(upstream_raw['view'],upstream_command['end_frame'])
    source_available(providers.succeeded(direct)['view'],direct['end_frame'])
    equal(evidence['record_identities'],bindings.record_ids,'Interception lost actual historical record identities')
    return {'id':expected['id'],'events':11,'original_events':[item['id'] for item in originals],
        'complete_graph_sha256':sha(canonical(actual))}


def campaign(core, corpus, receipt):
    counterpart=providers.tool('pipeline_original_counterpart')
    oracle, module = continuation.load_oracle(), load_body_module(installed=True)
    original = counterpart.run('fixed-registration-original')
    current = capture_original(module=module, oracle=oracle)
    equal(current, counterpart.validate(original), 'Current ordinary behavior differs from exact original child')
    validate_original(corpus, current)
    receipt['fresh_original'] = manager.artifact(receipt, canonical({'original': original, 'current': current}))
    witness = NativeWitness(core, corpus, oracle, module)
    try:
        with oracle.portable_sources(), witness.observed_callbacks(), witness.entries({SOURCE: module}) as entries:
            execution = run_original_bodies(module=module, context=witness.in_context,
                prepare=lambda cls: authored_fixture(cls, module))
        receipt['original_execution'] = manager.artifact(receipt, canonical({**execution, 'entries': entries}))
        equal([case['id'] for case in witness.cases], [case['id'] for case in corpus.cases],
            'Original intercepted fixed calls were omitted or reordered')
        for case in witness.cases:
            receipt['checks'].append({'id': case['id'],
                'actual': manager.artifact(receipt, canonical(case['mutation_graph'])),
                'evidence': manager.artifact(receipt, canonical(witness_evidence(case, oracle)))})
    finally:
        for case in witness.cases:
            if 'manager' not in case: continue
            row = next((row for row in receipt['checks'] if row['id'] == case['id']), None)
            if row is None:
                row = {'id': case['id']}; receipt['checks'].append(row)
            continuation.close_receipt(case['manager'], row, case['guard'], receipt)
    providers.installed_modules()


def validate_checks(receipt, corpus, artifacts):
    counterpart=providers.tool('pipeline_original_counterpart')
    require(receipt.get('completed_checks') == 3 and type(receipt.get('checks')) is list
        and len(receipt['checks']) == 3, 'Incomplete installed interception campaign')
    fresh = artifacts.json(receipt['fresh_original'], r.MAX_ARTIFACT_BYTES)
    require(type(fresh) is dict and set(fresh) == {'original', 'current'}, 'Incomplete original counterpart evidence')
    require(fresh['original']['manifest']['task'] == 'fixed-registration-original', 'Wrong original counterpart task')
    equal(fresh['current'], counterpart.validate(fresh['original']), 'Original child and complete current capture differ')
    validate_original(corpus, fresh['current'])
    oracle, module = continuation.load_oracle(installed=False), load_body_module()
    equal(capture_original(module=module, oracle=oracle), fresh['current'], 'Complete original interception is not reproducible')
    execution = artifacts.json(receipt['original_execution'], r.MAX_ARTIFACT_BYTES)
    equal({key: value for key, value in execution.items() if key != 'entries'}, fresh['current']['execution'],
        'Unchanged original method assertions did not execute against the native adapter')
    require(type(execution['entries']) is list
        and ['biocompiler.compiler.components', 'run_component_pipeline'] in execution['entries']
        and ['biocompiler', 'run_component_pipeline'] in execution['entries'],
        'Original native entry routing omitted its actual public boundary')
    channel, application = manager.declarations()
    manager.validate_verify(receipt, artifacts, channel, application)
    sessions, pids, projection = set(), set(), []
    # The identical original authoring function constructs independent inputs;
    # no accepted record, proposal or expectation is supplied to Core.
    with oracle.portable_sources():
        request, history = module.build_request()
    source = {'request': request, 'history': history, 'until': 7, 'config': None}
    for expected, original, row in zip(corpus.cases, fresh['current']['cases'], receipt['checks']):
        require(type(row) is dict and set(row) == {'id', 'actual', 'evidence', 'pid', 'returncode', 'closed',
            'invalidated', 'executable_sha256', 'stderr', 'frames', 'after_close', 'guard'}
            and row['id'] == expected['id'], 'Missing or reordered installed interception workflow')
        continuation.validate_process(row, receipt, artifacts, pids, initializer='initialize-synthetic')
        details = {}
        traffic = manager.validate_frames(row['frames'], artifacts, channel, application, sessions=sessions,
            details=details, provider_calls=True, initializer='initialize-synthetic')
        result = validate_case(corpus, expected, artifacts.json(row['actual'], r.MAX_ARTIFACT_BYTES),
            artifacts.json(row['evidence'], r.MAX_ARTIFACT_BYTES), details, oracle, source, original, module=module)
        projection.append({**result, **traffic})
    require(artifacts.used == set(artifacts.declared), 'Unreferenced complete interception evidence')
    return projection


def compare(*args, **kwargs):
    return providers.tool('pipeline_fixed_registration_runtime').compare(*args, **kwargs)


def campaign_main(argv):
    return providers.tool('pipeline_fixed_registration_runtime').campaign_main(argv)


def main(argv=None):
    return providers.tool('pipeline_fixed_registration_runtime').main(argv)


if __name__ == '__main__':
    raise SystemExit(main())
