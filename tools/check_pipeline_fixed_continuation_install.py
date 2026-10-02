"""Replay authority and original-body driver for retained fixed-workflow managers.

The complete frozen observations are comparison data. The driver executes the
unchanged original fixture and test functions. A native factory may replace only
the public fixed compiler entry points; authoring and assertions remain original.
"""
from __future__ import annotations

from collections import Counter
from contextlib import ExitStack, contextmanager, nullcontext
from copy import deepcopy
import importlib
import importlib.util
import argparse
import os
import platform
import re
import time
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

if __package__:
    from . import check_pipeline_fixed_provider_install as providers
else:
    import check_pipeline_fixed_provider_install as providers

manager, fixed, r = providers.manager, providers.manager.fixed, providers.r
ROOT = manager.ROOT
require, equal, canonical, sha = manager.require, manager.equal, manager.canonical, manager.sha
SCHEMA = 'biocompiler.installed_fixed_workflow_continuations.v1'
SCOPE = '39_original_live_fixed_workflow_chains_312_prefix_254_suffix_operations_not_all_fixed_interception'
RECEIPT_FILE, ARTIFACT_DIRECTORY = 'pipeline-fixed-continuations.json', 'pipeline-fixed-continuations-artifacts'
BUILD_ORACLE = 'tests/conformance/pipeline-fixed-build-semantics-v1.json'
BUILD_ORACLE_SHA256 = 'b423e1d60fbe688090bd44787ccb372a10847681cd8a011fd897cface9b9e28e'
METHODS = {
    'tests/test_component_pipeline.py': ('ComponentPipelineTests', (
        'test_checked_component_scope_preserves_upstream_evidence_and_sources',
        'test_component_scope_cannot_complete_molecular_payload',
        'test_every_dependency_invalidates_components_transitively',
        'test_import_roundtrip_preserves_locked_artifact')),
    'tests/test_component_pipeline_audit.py': ('ComponentPipelineAuditTests', (
        'test_documented_example_uses_full_target_selection',
        'test_remaining_upstream_roots_invalidate_component_acceptance')),
    'tests/test_temporal_components.py': ('TemporalComponentTests', (
        'test_new_dependencies_invalidate_component_acceptance',
        'test_reset_set_and_expiry_precedence_survive_component_reconstruction',
        'test_startup_memory_contact_loss_and_reset_have_literal_output_timeline')),
    'tests/test_synthetic_design_workflows.py': ('SyntheticDesignWorkflowTests', (
        'test_component_package_and_selection_cli_report_actual_scope',
        'test_rehashed_component_and_selection_documents_do_not_establish_acceptance',
        'test_selected_pipeline_receipts_expire_when_selection_policy_changes',
        'test_selected_temporal_components_package_reconstructs_every_stage')),
}
COVERAGE = {'fixed_boundaries': 136, 'original_manager_contexts': 476, 'eligible_chains': 39,
    'prefix_operations': 312, 'suffix_operations': 254, 'original_methods': 13, 'original_fixtures': 4,
    'original_contexts': 17, 'returned_suffix': 233, 'raised_suffix': 21,
    'excluded_boundaries': 10, 'excluded_prefix': 24, 'excluded_suffix': 9}


class Corpus:
    def __init__(self):
        self.fixed = fixed.Corpus()
        self.cases = [case for case in self.fixed.cases
            if self.fixed.continuations[case['id']].get('pending_callback_dependent_suffix')]
        self.by_context = {}
        for case in self.cases:
            self.by_context.setdefault(case['context'], []).append(case)
        self.build, self.build_pin = r.read(ROOT / BUILD_ORACLE)
        require(self.build_pin == BUILD_ORACLE_SHA256, 'Original public build graph bytes changed')
        require(self.build['schema_version'] == 'biocompiler.pipeline_fixed_build_semantics.v1', 'Unknown original build graph')
        equal(self.build['inventory_fingerprint'], sha(canonical({key: value for key, value in self.build.items()
            if key != 'inventory_fingerprint'})), 'Original public build inventory differs')
        for path, identity in self.build['source_files'].items():
            require(not Path(path).is_absolute() and '..' not in Path(path).parts and r.pin(identity),
                'Invalid original public build source: '+path)
            if path == 'src/biocompiler/compiler/pipeline.py':
                fixed.source_tool('manager_registration_source_lineage').verify_source(ROOT, path, identity)
            elif path == 'tools/check_pipeline_session_install.py':
                fixed.source_tool('manager_registration_source_lineage').verify_tool_source(r.raw_file(ROOT / path), identity)
            else:
                require(sha(r.raw_file(ROOT / path)) == identity, 'Original public build source changed: '+path)
        self.authorities = {case['authority_sha256']: case for case in self.build['cases']}
        require(len(self.cases) == 39 and len(self.authorities) == 6, 'Original continuation cohort was narrowed')
        require({case['authority'] for case in self.cases} == set(self.authorities), 'Original continuation authority coverage differs')
        self.contexts = set()
        self.prefix, self.suffix = [], []
        for case in self.cases:
            require(case['api'] == 'run_synthetic_pipeline' and case['outcome'] == 'returned'
                and case['parent'] in self.fixed.by_id, 'Continuation lost its original nested fixed boundary')
            parent = self.fixed.by_id[case['parent']]
            require(parent['api'] == 'run_component_pipeline' and parent['outcome'] == 'returned'
                and self.fixed.eligible(parent), 'Continuation parent is outside the eligible original component body')
            entry = self.fixed.continuations[case['id']]
            prefix, suffix = entry['supported_prefix_events'], entry['pending_callback_dependent_suffix']
            equal([event['id'] for event in entry['events']], prefix+suffix, 'Complete original continuation order differs')
            require(len(prefix) == 8 and all(event['api'] == 'PassManager.set_dependency'
                for event in entry['events'][:8]), 'Original component preparation mutations changed')
            require([event['api'] for event in entry['events'][8:12]] == [
                'PassManager.register_completion_profile', 'PassManager.register', 'PassManager.run', 'PassManager.result'],
                'Original component continuation sequence changed')
            self.prefix.extend(entry['events'][:8]); self.suffix.extend(entry['events'][8:])
            self.contexts.add(case['context'])
            self.contexts.update(event['context'] for event in entry['events'])
        expected_contexts = {path+'::fixture.setUpClass' for path in METHODS} | {
            path+'::'+cls+'.'+method for path, (cls, methods) in METHODS.items() for method in methods}
        equal(sorted(self.contexts), sorted(expected_contexts), 'Original continuation context closure differs')
        equal(dict(Counter(event['api'] for event in self.suffix)), {
            'PassManager.register_completion_profile': 39, 'PassManager.register': 39,
            'PassManager.run': 39, 'PassManager.result': 72, 'PassManager.get': 45, 'PassManager.set_dependency': 20},
            'Complete original suffix API census differs')
        require(len(self.prefix) == 312 and len(self.suffix) == 254
            and Counter(event['outcome'] for event in self.suffix) == {'returned': 233, 'raised': 21},
            'Complete original continuation outcome census differs')
        self.pending = {'excluded': [{'case': case, 'continuation': self.fixed.continuations[case['id']]}
            for case in self.fixed.excluded], 'other_fixed_boundaries': [case['id'] for case in self.fixed.all_cases
                if case not in self.cases], 'full_manager_contexts': 476,
            'scope': 'This additive cohort does not replace any original fixed/session/manager acceptance gate'}


def load_body_modules():
    """Import source-pinned tests while preserving installed product resolution."""
    previous = list(sys.path)
    try:
        sys.path.extend((str(ROOT), str(ROOT/'tests')))
        result = {path: importlib.import_module(Path(path).stem) for path in METHODS}
    finally:
        sys.path[:] = previous
    require(sys.path == previous, 'Original continuation loader changed import authority')
    for path, module in result.items():
        require(Path(module.__file__).resolve() == ROOT/path, 'Original continuation body came from another file')
    return result


def run_original_bodies(*, context=None, modules=None):
    """Execute all 13 original methods and four fixtures without rewriting them."""
    context = context or (lambda name: nullcontext())
    modules = load_body_modules() if modules is None else modules
    contexts, body_codes = [], []
    stack = ExitStack()
    current = None
    class Result(unittest.TextTestResult):
        def startTest(self, test):
            nonlocal current
            path = next(path for path, module in modules.items() if module.__name__ == type(test).__module__)
            name = path+'::'+type(test).__name__+'.'+test._testMethodName
            contexts.append(name)
            current = context(name)
            current.__enter__()
            super().startTest(test)
        def stopTest(self, test):
            nonlocal current
            try:
                super().stopTest(test)
            finally:
                current.__exit__(None, None, None)
                current = None
    suite = unittest.TestSuite()
    for path, (class_name, methods) in METHODS.items():
        cls = getattr(modules[path], class_name)
        original = cls.setUpClass
        body_codes.append(original.__func__.__code__)
        def setup(_cls, original=original, path=path):
            name = path+'::fixture.setUpClass'
            contexts.append(name)
            with context(name):
                original()
        stack.enter_context(patch.object(cls, 'setUpClass', classmethod(setup)))
        for method in methods:
            body_codes.append(getattr(cls, method).__code__)
            suite.addTest(cls(method))
    log = io.StringIO()
    with stack:
        result = unittest.TextTestRunner(stream=log, verbosity=2, resultclass=Result).run(suite)
    require(result.wasSuccessful() and result.testsRun == 13 and not result.skipped,
        'Original continuation assertions failed:\n'+log.getvalue())
    wanted = [item for path, (name, methods) in METHODS.items()
        for item in (path+'::fixture.setUpClass', *(path+'::'+name+'.'+method for method in methods))]
    equal(contexts, wanted, 'Original continuation execution order differs')
    require(len(body_codes) == 17, 'Original continuation body code census differs')
    return {'contexts': contexts, 'methods': result.testsRun, 'assertions': 'passed', 'log': log.getvalue()}


def public_graph(case):
    """Reindex the complete publicly reachable subgraph; keep private raw data.

    Profiler-only original producer returns and implementation-local config
    variables stay in the immutable original corpus. They are not invented as
    Python objects during native fixed execution. Public roots include every
    historical record and named source origin, not just selected alias claims.
    """
    seen, nodes = {}, []
    def copy(reference):
        if 'ref' not in reference:
            return deepcopy(reference)
        old = reference['ref']
        if old in seen:
            return {'ref': seen[old]}
        index = len(nodes)
        seen[old] = 'object/'+str(index)
        nodes.append(None)
        value = deepcopy(case['nodes'][int(old.split('/')[1])])
        if value['kind'] == 'dataclass':
            value['fields'] = [[name, copy(item)] for name, item in value['fields']]
        elif value['kind'] == 'mapping':
            value['items'] = [[copy(key), copy(item)] for key, item in value['items']]
        elif value['kind'] == 'sequence':
            value['items'] = [copy(item) for item in value['items']]
        nodes[index] = value
        return {'ref': seen[old]}
    roots = {name: copy(case['roots'][name]) for name in ('target', 'config_argument')}
    origins = [[name, copy(value)] for name, value in case['source_origins']]
    for stage in ('synthetic', 'component'):
        roots[stage] = copy(case['roots'][stage])
        roots[stage+'_records'] = [[name, copy(value)] for name, value in case['roots'][stage+'_records']]
    return {'roots': roots, 'source_origins': origins, 'nodes': nodes}


def observed_public_graph(oracle, request, config, upstream, built, before_records, after_records):
    graph = oracle.Graph(manager_type=type(built.manager))
    roots = {'target': graph.encode(request.target), 'config_argument': graph.encode(config)}
    origins = [[name, graph.encode(value)] for name, value in oracle.providers.source_origins(request)]
    for stage, value, records in (('synthetic', upstream, before_records), ('component', built, after_records)):
        roots[stage] = graph.encode(value)
        roots[stage+'_records'] = [[name, graph.encode(record)] for name, record in records]
    return {'roots': roots, 'source_origins': origins, 'nodes': graph.nodes}


def ordinary_value(value):
    """The closed returned manager vocabulary; no acceptance or user conversion."""
    from biocompiler.compiler.pipeline import PipelineResult, StageRecord
    if value is None:
        return None
    if type(value) is StageRecord:
        return value.to_dict()
    require(type(value) is PipelineResult, 'Unexpected fixed continuation result type')
    return {'status': value.status.value, 'artifact': value.artifact.to_dict(), 'scope': value.scope,
        'unresolved': [{'id': item.id, 'scope': item.scope, 'evidence_kind': item.evidence_kind.value,
            'description': item.description} for item in value.unresolved]}


class NativeWitness:
    """Observe actual public operations on one retained native manager per call."""
    def __init__(self, core, corpus, oracle):
        self.core, self.corpus, self.oracle = core, corpus, oracle
        self.context = None
        self.offsets, self.cases = {}, []
        self.depth = set()

    @contextmanager
    def in_context(self, name):
        previous, self.context = self.context, name
        try:
            yield
        finally:
            self.context = previous

    def found(self, instance):
        entries = [case for case in self.cases if case.get('manager') is instance]
        require(len(entries) <= 1, 'One native manager was reused across fixed calls')
        return entries[0] if entries else None

    def inspect(self, case):
        actual = case['manager']
        with manager.guarded_execution(case['guard']):
            inspected = actual.inspect_ordered_references()
        response = actual.session.last_response
        require(response is not None and response.operation == 'inspect-ordered-references', 'Missing actual fixed inspection receipt')
        raw = response.result
        for entry in raw['providers']:
            value = actual._objects.resolve(entry['object'])
            require(inspected.providers[entry['provider_id']] is value, 'Inspected provider lost actual physical identity')
            token = entry['provider_id']
            previous = case['provider_objects'].get(token)
            require(previous is None or previous is value, 'Native provider changed its actual host callable')
            require(all(other == token or retained is not value for other, retained in case['provider_objects'].items()),
                'Different native providers share one host callable')
            case['provider_objects'][token] = value
        for key, envelope in inspected.snapshot['records'].items():
            record = actual._records[key]
            token = envelope['bindings']['record_id']
            previous = case['record_objects'].get(token)
            require(previous is None or previous is record, 'Native record changed its actual host object')
            require(all(other == token or retained is not record for other, retained in case['record_objects'].items()),
                'Different native records share one host object')
            case['record_objects'][token] = record
        case['inspections'].append(response.sequence)
        case['_last_inspection'] = (response, len(actual.session.traffic))
        return response.sequence

    @contextmanager
    def manager_operations(self):
        from biocompiler.core_pipeline_manager import CorePassManager
        with ExitStack() as stack:
            for name in ('set_dependency', 'register_completion_profile', 'register', 'run', 'result', 'get'):
                original = getattr(CorePassManager, name)
                def wrapped(instance, *args, _original=original, _name=name, **kwargs):
                    case = self.found(instance)
                    if case is None or id(instance) in self.depth:
                        return _original(instance, *args, **kwargs)
                    previous = case.get('_last_inspection')
                    reused = previous is not None and instance.session.last_response is previous[0] \
                        and len(instance.session.traffic) == previous[1]
                    before = previous[0].sequence if reused else self.inspect(case)
                    self.depth.add(id(instance))
                    row = {'api': 'PassManager.'+_name, 'context': self.context, 'before': before, 'before_reused': reused,
                        'start_frame': len(instance.session.traffic)}
                    try:
                        with manager.guarded_execution(case['guard']):
                            value = _original(instance, *args, **kwargs)
                    except Exception as error:
                        row.update(outcome='raised', error={'module': type(error).__module__,
                            'type': type(error).__name__, 'message': str(error)})
                        raise
                    else:
                        row.update(outcome='returned', value=ordinary_value(value))
                        if value is not None:
                            artifact = value.artifact if _name == 'result' else value
                            require(instance._records[artifact.id] is artifact, 'Public operation returned another historical record')
                            row['record_identity'] = instance._record_bindings[artifact.id][0]
                        return value
                    finally:
                        self.depth.remove(id(instance))
                        response = instance.session.last_response
                        require(response is not None, 'Public operation lost its actual native reply')
                        row.update(sequence=response.sequence, end_frame=len(instance.session.traffic))
                        row['after'] = self.inspect(case)
                        case['events'].append(row)
                stack.enter_context(patch.object(CorePassManager, name, wrapped))
            yield

    def factory(self, request, history, *, until=None, config=None):
        from biocompiler.core_pipeline_manager import CorePassManager
        require(self.context in self.corpus.by_context, 'Fixed call occurred outside the original source context')
        index = self.offsets.get(self.context, 0)
        expected = self.corpus.by_context[self.context][index]
        self.offsets[self.context] = index+1
        frames = tuple(history)
        authority = {'request': request.to_dict(), 'history': [frame.to_dict() for frame in frames],
            'until': until, 'config': config.to_dict() if config is not None else None}
        equal(authority, self.corpus.fixed.document('fixed', expected['authority']), 'Original authoring changed before native initialization')
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
        case['before_records'] = tuple((name, actual._records[name]) for name in ('request', 'behavior', 'mechanism'))
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
        case['registration_sequence'] = actual.session.last_response.sequence
        case['registration'] = registration
        actual.register(registration.contract, registration.producer, registration.validators)
        record = actual.run(registration.contract.id, 'mechanism', 'components')
        result = actual.result('components', scope='synthetic_components')
        require(result.artifact is record, 'Component completion changed actual run-return record identity')
        with manager.guarded_execution(case['guard']):
            built = actual.finish_components(preparation, result)
        case['built'], case['finish_sequence'] = built, actual.session.last_response.sequence
        case['completed'] = self.inspect(case)
        case['after_records'] = tuple((name, actual._records[name]) for name in ('request', 'behavior', 'mechanism', 'components'))
        case['graph'] = observed_public_graph(self.oracle, request, config, upstream, built,
            case['before_records'], case['after_records'])
        equal(case['graph'], public_graph(self.corpus.authorities[expected['authority']]),
            'Complete public native build values or physical identities differ')
        return built

    @contextmanager
    def entries(self, modules):
        from biocompiler.compiler.components import run_component_pipeline
        allowed = {'biocompiler', *(module.__name__ for module in modules.values())}
        replaced = []
        with ExitStack() as stack:
            for name, module in tuple(sys.modules.items()):
                if module is None or not (name in allowed or name.startswith(('biocompiler.', 'examples.'))):
                    continue
                for attribute, value in tuple(vars(module).items()):
                    if value is run_component_pipeline:
                        stack.enter_context(patch.object(module, attribute, self.factory))
                        replaced.append((name, attribute))
            require(('biocompiler.compiler.components', 'run_component_pipeline') in replaced,
                'Native fixed entry routing omitted its authoritative module')
            with self.manager_operations():
                yield replaced


BUILD_TOOL = 'tools/capture_pipeline_fixed_build_semantics.py'
SOURCES = tuple(dict.fromkeys((BUILD_TOOL, 'tests/test_pipeline_fixed_build_semantics.py',
    'tools/check_pipeline_fixed_continuation_install.py', 'tests/test_pipeline_fixed_continuation_campaign.py',
    'src/biocompiler/core_pipeline_build_views.py', 'tests/test_core_pipeline_build_views.py',
    'tools/pipeline_fixed_direct_controls.py', 'tests/test_pipeline_fixed_direct_controls.py', *providers.SOURCES)))


def load_oracle(*, installed=True):
    if installed:
        providers.installed_modules()
    previous = list(sys.path)
    try:
        spec = importlib.util.spec_from_file_location('fixed_build_original', ROOT/BUILD_TOOL)
        oracle = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = oracle
        spec.loader.exec_module(oracle)
    finally:
        sys.path[:] = previous
    if installed:
        providers.installed_modules()
    return oracle


def metadata(corpus):
    return {'coverage': COVERAGE, 'pending': corpus.pending,
        'original_build': {'path': BUILD_ORACLE, 'sha256': corpus.build_pin,
            'inventory_fingerprint': corpus.build['inventory_fingerprint']},
        'fixed_authority': fixed.metadata(corpus.fixed),
        'declarations': r.source_pins((manager.CHANNEL_PATH, manager.APPLICATION_PATH)),
        'public_graph_projection': {'retained': ['target', 'config_argument', 'source_origins', 'synthetic',
            'synthetic_records', 'component', 'component_records'],
            'observation_only_roots': {'producer_returns': 'Profiler-only original fixed closure returns are not Python objects during internal native execution; six separate actual proxy controls retain their complete graph.',
                'requested_config': 'Implementation-local root is retained in the full original corpus and six proxy controls; every publicly reachable path remains included.',
                'selected_config': 'Implementation-local root is retained in the full original corpus and six proxy controls; selection and public build descendants remain included.'},
            'full_original_graph_retained': True, 'separate_direct_controls': 6}}


def product_sources(corpus):
    paths = {path for path in corpus.build['source_files'] if path.startswith('src/')}
    paths.update(manager.python_sources())
    paths.update(('src/biocompiler/core_pipeline_provider_views.py', 'src/biocompiler/core_pipeline_build_views.py'))
    return r.source_pins(paths)


def source_roots(oracle, request, requested_config):
    from biocompiler.core_pipeline_provider_views import origin_reference
    return {'request': request, 'target': request.target, 'requested_config': requested_config,
        **dict(oracle.providers.source_origins(request)),
        'constant:synthetic_capabilities': origin_reference(request, 'syntheticCapabilities', [])}


def witness_evidence(case, oracle):
    actual = case['manager']
    roots = source_roots(oracle, case['request'], actual._provider_config)
    sources = {handle: [name for name, root in roots.items() if value is root]
        for handle, value in actual._objects._objects.items()
        if any(value is root for root in roots.values())}
    events = case['events']
    register = next(entry for entry in events if entry['api'] == 'PassManager.register')
    requests = [r.decode(entry.frame[9:]) for entry in actual.session.traffic if entry.direction == 'client']
    request = next(entry for entry in requests if entry.get('sequence') == register['sequence'])
    arguments = request['arguments']
    registration = case['registration']
    require(actual._objects.resolve(arguments['producer']) is registration.producer,
        'Registration lost prepared actual producer')
    validators = actual._objects.resolve(arguments['validators'])
    require(validators is registration.validators and list(validators) == list(registration.validators)
        and all(validators[key] is value for key, value in registration.validators.items()),
        'Registration lost prepared actual validators')
    for reference, obligation in zip(arguments['obligation_objects'], registration.contract.introduces):
        require(actual._objects.resolve(reference) is obligation, 'Registration lost prepared obligation identity')
    return {name: case[name] for name in ('events', 'inspections', 'initial', 'completed', 'upstream_sequence',
        'prepare_sequence', 'profile_sequence', 'registration_sequence', 'finish_sequence')} | {
        'sources': sources, 'providers': {token: next(handle for handle, value in actual._objects._objects.items()
            if value is retained) for token, retained in case['provider_objects'].items()},
        'record_identities': {token: record.id for token, record in case['record_objects'].items()}}


def close_receipt(actual, row, seen, receipt):
    from biocompiler.core_client import CoreProtocolError
    with manager.guarded_execution(seen):
        actual.close()
    session = actual.session
    row.update(pid=session.pid, returncode=session.returncode, closed=session.closed, invalidated=session.invalidated,
        executable_sha256=session.executable_sha256, stderr=manager.artifact(receipt, canonical({'hex': session.stderr_bytes.hex()})),
        frames=[{'direction': entry.direction, 'index': entry.index, 'frame': manager.artifact(receipt, entry.frame)}
            for entry in session.traffic])
    before = len(session.traffic)
    try:
        with manager.guarded_execution(seen):
            actual.get('request')
    except CoreProtocolError as error:
        row['after_close'] = manager.artifact(receipt, canonical({'type': type(error).__name__, 'message': str(error),
            'traffic_unchanged': len(session.traffic) == before, 'pid_unchanged': session.pid == row['pid']}))
    else:
        raise AssertionError('Closed retained manager resumed')
    row['guard'] = manager.artifact(receipt, canonical([list(item) for item in sorted(seen)]))


def campaign(core, corpus, receipt):
    if __package__:
        from . import pipeline_fixed_direct_controls as direct
    else:
        import pipeline_fixed_direct_controls as direct
    oracle, originals = load_oracle(), []
    fresh = oracle.capture(retain=originals)
    providers.capture_counterpart(receipt, fresh, 'fixed-build-original', corpus.build)
    modules = load_body_modules()
    providers.installed_modules()
    witness = NativeWitness(core, corpus, oracle)
    try:
        with oracle.portable_sources(), witness.entries(modules) as entries:
            execution = run_original_bodies(context=witness.in_context, modules=modules)
        receipt['original_execution'] = manager.artifact(receipt, canonical({**execution, 'entries': entries}))
        equal([case['id'] for case in witness.cases], [case['id'] for case in corpus.cases],
            'Original fixed calls were omitted or reordered')
        for case in witness.cases:
            row = {'id': case['id'], 'actual': manager.artifact(receipt, canonical(case['graph'])),
                'evidence': manager.artifact(receipt, canonical(witness_evidence(case, oracle)))}
            receipt['checks'].append(row)
    finally:
        for case in witness.cases:
            if 'manager' not in case:
                continue
            row = next((item for item in receipt['checks'] if item['id'] == case['id']), None)
            if row is None:
                row = {'id': case['id']}; receipt['checks'].append(row)
            close_receipt(case['manager'], row, case['guard'], receipt)
    direct.run(core, corpus, oracle, receipt, originals)
    providers.installed_modules()


def original_order(raw):
    fields = raw['fields']
    maps = {'dependencies': '_dependencies', 'passes': '_passes', 'provider_history': '_provider_history',
        'records': '_records', 'profiles': '_profiles', 'component_inputs': '_component_inputs'}
    order = {key: list(fixed.mapping(fields[value])) for key, value in maps.items()}
    order['component_input_history'] = []
    order['combined_provider_history'] = list(order['provider_history'])
    order['validators'] = {key: {} for key in manager.REGISTRATION_MAPS}
    for key in ('passes', 'provider_history'):
        for identity, entry in fixed.mapping(fields[maps[key]]).items():
            order['validators'][key][identity] = list(fixed.mapping(entry['items'][2]))
    return order


class ReceiptViews:
    """Decode retained transport views only; no Core process or Python compiler.

    `_prepare` initializes bounded structural caches. Its transport constructor
    is replaced with an inert sink; every value consumed below is an already
    independently frame-checked native reply, never an original accepted record.
    """
    def __init__(self, request, config, application):
        from biocompiler import core_pipeline_manager as module
        from types import SimpleNamespace
        self.module = module
        self.value = module.CorePassManager.__new__(module.CorePassManager)
        with patch.object(module, 'CorePipelineCallbackSession', return_value=SimpleNamespace(_invalidate=lambda: None)):
            self.value._prepare(None, application=application)
        self.value._target = request.target
        self.value._provider_request, self.value._provider_config = request, config
        self.value._provider_target_document = request.target.to_dict()
        self.host = self.value._objects._objects

    def bind(self, reference, value):
        handle = providers.reference(reference)
        require(handle not in self.host or self.host[handle] is value, 'Actual retained host handle was rebound')
        require(all(key == handle or item is not value for key, item in self.host.items()),
            'One actual host object has multiple retained handles')
        self.host[handle] = value

    def provider(self, token, role, reference):
        require(token not in self.value._native_providers, 'Native provider was minted twice')
        value = self.module._NativeProvider(self.value, token)
        self.value._native_providers[token] = value
        self.value._native_provider_roles[token] = role
        self.bind(reference, value)



def expand_inspections(commands):
    """Expand only earlier, exact first-publication compact definitions.

    Full documents remain in raw frames. References are transport compression,
    never acceptance input, and cannot seed a definition from an expected file
    or a future response.
    """
    definitions, names, expanded = {}, {}, {}
    for command in sorted(commands, key=lambda item: item['start_frame']):
        if command['operation'] != 'inspect-ordered-references':
            continue
        raw = providers.succeeded(command)
        require(type(raw) is dict and set(raw) == {'snapshot', 'order', 'providers', 'record_definitions'},
            'Incomplete compact ordered inspection')
        require(type(raw['snapshot']) is dict and type(raw['snapshot'].get('records')) is dict
            and type(raw['order']) is dict and type(raw['order'].get('records')) is list
            and type(raw['record_definitions']) is list, 'Malformed compact record collection')
        records = raw['snapshot']['records']; order = raw['order']['records']
        require(all(type(key) is str for key in order) and len(order) == len(set(order)) and set(order) == set(records),
            'Compact record order is incomplete')
        tokens = []
        for key in order:
            reference = records[key]
            require(type(reference) is dict and set(reference) == {'record_id'}, 'Compact record has extra authority')
            token = providers.BindingCensus.identity(reference['record_id'], 'compact record')
            require(token not in tokens, 'Different record names reuse one compact incarnation')
            tokens.append(token)
        required = [token for token in tokens if token not in definitions]
        received = []
        for envelope in raw['record_definitions']:
            require(type(envelope) is dict and set(envelope) == {'value', 'bindings'}
                and type(envelope['bindings']) is dict and type(envelope['value']) is dict,
                'Malformed complete compact record definition')
            token = providers.BindingCensus.identity(envelope['bindings'].get('record_id'), 'compact definition')
            require(token not in definitions and token not in received, 'Compact record incarnation was redefined')
            require(token in required, 'Unrequested or late compact record definition')
            key = order[tokens.index(token)]
            require(envelope['value'].get('id') == key, 'Compact record definition has a different original name')
            definitions[token] = deepcopy(envelope); names[token] = key; received.append(token)
        equal(received, required, 'Compact first-publication definition census/order differs')
        actual = {}
        for key, token in zip(order, tokens):
            require(token in definitions and names[token] == key, 'Compact reference lacks its preceding named definition')
            actual[key] = deepcopy(definitions[token])
        expanded[command['sequence']] = {'snapshot': {**deepcopy(raw['snapshot']), 'records': actual},
            'order': deepcopy(raw['order']), 'providers': deepcopy(raw['providers'])}
    return expanded


def validate_case(corpus, expected, actual, evidence, details, oracle, authority_objects):
    from biocompiler.core_pipeline_manager import _ordered
    from biocompiler.core_pipeline_provider_views import StructuralViews, origin_reference
    fields = {'events', 'inspections', 'initial', 'completed', 'upstream_sequence', 'prepare_sequence',
        'profile_sequence', 'registration_sequence', 'finish_sequence', 'sources', 'providers', 'record_identities'}
    require(type(evidence) is dict and set(evidence) == fields, 'Incomplete retained-manager evidence')
    expected_graph = public_graph(corpus.authorities[expected['authority']])
    equal(actual, expected_graph, 'Complete public build graph differs from original')
    commands = {item['sequence']: item for item in details['commands']}
    require(len(commands) == len(details['commands']), 'Fixed continuation repeated a native command')
    ordered = sorted(commands.values(), key=lambda item: item['start_frame'])
    require(ordered[0]['operation'] == 'initialize-synthetic', 'Original retained chain has another initializer')
    init = ordered[0]; args = init['arguments']; source = authority_objects
    request, config_argument = source['request'], source['config']
    _, application = manager.declarations()
    requested = config_argument if config_argument is not None else StructuralViews().config(application['default_generator_config'])
    authority = corpus.fixed.document('fixed', expected['authority'])
    equal({key: args[key] for key in ('request', 'history', 'until')},
        {key: authority[key] for key in ('request', 'history', 'until')}, 'Initialization changed original authority')
    equal(args['config'], requested.to_dict(), 'Initialization changed original requested/default configuration')
    equal(args['request_tree'], _ordered(request.to_dict()), 'Initialization changed original authored mapping order')
    require(args['manager_limits'] is None, 'Continuation silently changed manager limits')
    views = ReceiptViews(request, requested, application)
    roots = source_roots(oracle, request, requested)
    seen_names = set()
    for handle, names in evidence['sources'].items():
        require(type(names) is list and names and all(name in roots and name not in seen_names for name in names),
            'Invalid original source-root identity census')
        require(all(roots[name] is roots[names[0]] for name in names), 'Source roots falsely merged by value')
        views.bind({'handle': handle}, roots[names[0]]); seen_names.update(names)
    for key, name in (('request_object', 'request'), ('config_object', 'requested_config'), ('target_object', 'target')):
        require(providers.reference(args[key]) in views.host and views.host[providers.reference(args[key])] is roots[name],
            'Initialization detached its actual authored source object')
    document_sources = {providers.reference(args['target_object']): (-1, request.target.to_dict()),
        providers.reference(args['config_object']): (-1, requested.to_dict())}
    bindings = providers.BindingCensus(details, document_sources)
    initial = providers.succeeded(init)
    equal(initial, {'kind': 'synthetic', 'manager': True, 'artifacts': ['candidate', 'pipeline_result', 'selection_result'],
        'target': {'value': request.target.to_dict(), 'binding': {'kind': 'host', 'object': args['target_object']}}},
        'Native initialization omitted its complete actual result')
    views.value._initialization(initial, 'synthetic')
    expanded = expand_inspections(ordered)
    hooks = providers.initializers.validate(details, init,
        contracts={key: value['contract'] for key, value in expanded[evidence['initial']]['snapshot']['passes'].items()}, views=views)
    require(all(item['parent_invocation'] is None or item['sequence'] in hooks['commands'] for item in commands.values()),
        'Fixed continuation unexpectedly dispatched an unclaimed nested command')
    document_sources.update(hooks['host_documents'])
    bindings = providers.BindingCensus(details, document_sources)
    bindings.initialization(hooks)
    minted = dict(hooks['minted'])
    for invocation in sorted(details['invocations'].values(), key=lambda item: item['start_frame']):
        action, arguments = invocation['action'], invocation['arguments']
        if action == 'native-provider':
            token, role = arguments['provider_id'], arguments['role']
            reference = providers.returned(invocation)
            if invocation['command_sequence'] == init['sequence']:
                equal(minted.get(token), (reference, role, invocation['end_frame']),
                    'Initializer proxy differs from its exact source-ordered hook')
                continue
            require(token not in minted and role in {key+suffix for key in ('intent_to_behavior', 'behavior_to_synthetic',
                'synthetic_to_components') for suffix in ('.producer', '.validator')}, 'Unknown or repeated original native provider')
            require(invocation['command_sequence'] == evidence['registration_sequence'],
                'Native fixed proxy was minted outside its actual initialization/registration')
            views.provider(token, role, reference)
            minted[token] = (reference, role, invocation['end_frame'])
        elif action == 'origin-reference':
            require(set(arguments) == {'root', 'path'}, 'Native origin fields differ from the closed source action')
            require(invocation['command_sequence'] == evidence['upstream_sequence'],
                'Historical build origin was supplied by a later or unrelated command')
            value = origin_reference(request, arguments['root'], arguments['path'])
            reference = providers.returned(invocation)
            require(providers.reference(reference) in views.host and views.host[providers.reference(reference)] is value,
                'Native origin lost its actual authored/global physical identity')
    equal(evidence['providers'], {key: providers.reference(value[0]) for key, value in minted.items()},
        'Complete provider evidence differs from actual proxy creation')
    require(len(minted) == 6 and len({entry[1] for entry in minted.values()}) == 6,
        'Original six fixed closure roles were not all retained')
    source_handles = {providers.reference(args[key]) for key in ('request_object', 'config_object', 'target_object')}
    source_handles.update(providers.reference(providers.returned(item)) for item in details['invocations'].values()
        if item['action'] == 'origin-reference')
    require(set(evidence['sources']) == source_handles, 'Unclaimed actual source handle evidence')
    aliases, physical = fixed.Providers(), {}
    used, inspection_order = {init['sequence'], *hooks['commands']}, []
    def inspect(sequence, original, family='continuation'):
        require(sequence in commands and commands[sequence]['operation'] == 'inspect-ordered-references', 'Missing actual inspection')
        command = commands[sequence]
        if sequence not in used:
            inspection_order.append(sequence)
        used.add(sequence)
        equal(command['arguments'], {}, 'Inspection gained authored authority')
        raw = expanded[sequence]
        tokens = {item['provider_id']: item['provider_id'] for item in raw['providers']}
        bound = {token: reference for token, (reference, role, end) in minted.items() if end < command['end_frame']}
        projected = manager.comparison_snapshot(raw, tokens, previous=physical, bound=bound)
        for group in ('passes', 'provider_history'):
            for entry in projected['state'][group].values():
                roles = [(entry['producer'], entry['contract']['id']+'.producer'),
                    *((token, entry['contract']['id']+'.validator') for token in entry['validators'].values())]
                require(all(minted[token][1] == role for token, role in roles),
                    'Actual native proxy role differs from its registered fixed closure slot')
        expected_state = fixed.snapshot(original)
        aliases.align(projected['state'], expected_state, corpus.fixed.indexes[family]['providers'], family)
        equal(raw['order'], original_order(original), 'Original manager insertion order differs')
        for key, envelope in raw['snapshot']['records'].items():
            bindings.record(envelope, command['end_frame'])
            require(views.value._record(envelope).id == key, 'Record incarnation differs from its snapshot key')
        return command
    inspect(evidence['initial'], corpus.fixed.document('fixed', expected['manager_state']), 'fixed')
    originals = corpus.fixed.continuations[expected['id']]['events']
    require(type(evidence['events']) is list and len(evidence['events']) == len(originals), 'Original event census was narrowed')
    event_commands = []
    registration_view = None
    previous_after = commands[evidence['initial']]['end_frame']
    previous_inspection = evidence['initial']
    for index, (original, row) in enumerate(zip(originals, evidence['events'])):
        equal({key: row.get(key) for key in ('api', 'context', 'outcome')},
            {key: original[key] for key in ('api', 'context', 'outcome')}, 'Original event order/context/outcome differs')
        before = inspect(row['before'], corpus.fixed.document('continuation', original['state_before']))
        after = inspect(row['after'], corpus.fixed.document('continuation', original['state_after']))
        require(type(row.get('before_reused')) is bool, 'Before-state inspection reuse lacks explicit evidence')
        if row['before_reused']:
            # The exact preceding completed inspection is the last native
            # frame. No command or callback can have changed native state.
            latest = max((item for item in commands.values() if item['end_frame'] < row['start_frame']),
                key=lambda item: item['end_frame'])
            require(latest['operation'] == 'inspect-ordered-references' and latest['sequence'] == row['before']
                and latest['end_frame']+1 == row['start_frame'], 'Reused before-state has intervening native traffic')
            require(row['before'] in (previous_inspection, evidence['completed']),
                'Reused before-state is not the immediately preceding original observation')
        else:
            require(previous_after < before['start_frame'], 'Original manager event chronology was reordered')
        require(row['after'] != row['before'] and after['start_frame'] > before['end_frame'],
            'Original operation did not receive its fresh after-state inspection')
        previous_after = after['end_frame']; previous_inspection = row['after']
        command = commands.get(row['sequence'])
        require(command is not None and row['sequence'] not in used, 'Original event reused another command receipt')
        used.add(row['sequence']); event_commands.append(command)
        operation = original['api'].split('.')[-1].replace('_', '-')
        require(command['operation'] == operation and row['start_frame'] == command['start_frame'] == before['end_frame']+1
            and row['end_frame'] == command['end_frame']+1 == after['start_frame'],
            'Original event is detached from its own inspection interval')
        wanted = fixed.unpack(corpus.fixed.document('continuation', original['arguments']))['bound']
        arguments = command['arguments']
        if operation == 'register':
            equal(arguments['contract'], wanted['contract'], 'Registration changed original contract authority')
            native = providers.succeeded(commands[evidence['registration_sequence']])
            equal(arguments['producer'], native['producer'], 'Registration substituted prepared producer')
            require(providers.reference(arguments['producer']) == evidence['providers'][aliases.reverse['continuation', wanted['producer']]],
                'Original producer physical capability changed')
            validator_items = [[key, minted[aliases.reverse['continuation', token]][0]] for key, token in wanted['validators'].items()]
            equal(native['validators'], validator_items, 'Prepared actual validator capabilities changed')
            # Hydrate exactly the native registration and bind its retained
            # obligations/map to the actual subsequent public arguments.
            registration_view = views.value._component_registration(native)
            views.bind(arguments['validators'], registration_view.validators)
            require(len(arguments['obligation_objects']) == len(registration_view.contract.introduces), 'Introduced object census differs')
            for reference, item in zip(arguments['obligation_objects'], registration_view.contract.introduces):
                views.bind(reference, item)
                document_sources[providers.reference(reference)] = (command['start_frame']-1, item.to_dict())
                bindings.host[providers.reference(reference)] = [document_sources[providers.reference(reference)]]
            refs = [invocation for invocation in details['invocations'].values()
                if invocation['command_sequence'] == command['sequence'] and invocation['action'] == 'provider-reference']
            for reference, token in [(arguments['producer'], aliases.reverse['continuation', wanted['producer']]),
                    *((reference, aliases.reverse['continuation', wanted['validators'][key]]) for key, reference in validator_items)]:
                matching = [invocation for invocation in refs if invocation['arguments'] == {'object': reference}]
                require(matching and all(providers.returned(item) == {'kind': 'native', 'provider_id': token} for item in matching),
                    'Registration failed to use its actual fixed capability')
        else:
            equal(arguments, wanted, 'Original manager command arguments differ')
        if original['outcome'] == 'raised':
            equal(row['error'], original['error'], 'Actual original error descriptor differs')
            equal(command['outcome'], {'status': 'rejected', 'value': {**original['error'], 'attributes': {},
                'attributes_tree': ['object', []]}}, 'Original error is detached from its actual native rejection')
            require(set(row) == {'api', 'context', 'outcome', 'error', 'before', 'after', 'start_frame', 'end_frame', 'sequence', 'before_reused'},
                'Raised event contains invented returned evidence')
        else:
            wanted_result = fixed.unpack(corpus.fixed.document('continuation', original['result']))
            equal(row['value'], wanted_result, 'Complete original returned value differs')
            result = providers.succeeded(command)
            if operation in ('get', 'run', 'result'):
                envelope = result['artifact'] if operation == 'result' else result
                bindings.record(envelope, command['end_frame'])
                value = views.value._result_value(result) if operation == 'result' else views.value._record(result)
                equal(ordinary_value(value), wanted_result, 'Actual native result is detached from original returned value')
                require(row['record_identity'] == envelope['bindings']['record_id'], 'Returned record lost physical incarnation')
            else:
                require(result is None and row['value'] is None, 'Original unit operation returned a value')
    def phase(name, operation, arguments):
        sequence = evidence[name]; command = commands.get(sequence)
        require(command is not None and sequence not in used and command['operation'] == operation, 'Missing or repeated native workflow phase')
        used.add(sequence); equal(command['arguments'], arguments, 'Native workflow phase authority changed')
        return command, providers.succeeded(command)
    upstream_command, upstream_raw = phase('upstream_sequence', 'build-result', {'kind': 'synthetic'})
    preparation_command, preparation = phase('prepare_sequence', 'prepare-components', {})
    require(init['end_frame'] < upstream_command['start_frame'] < upstream_command['end_frame']
        < commands[evidence['initial']]['start_frame'] < commands[evidence['initial']]['end_frame'] < preparation_command['start_frame']
        < preparation_command['end_frame'] < commands[evidence['events'][0]['before']]['start_frame'],
        'Native workflow moved preparation across original state observations')
    prepared = views.value._component_preparation(preparation)
    equal(list(map(list, prepared.dependencies)), [[command['arguments']['key'], command['arguments']['identity']]
        for command in event_commands[:8]], 'Prepared dependency values/order differ from original mutations')
    phase_args = {'preparation_id': prepared.identity}
    profile_command, profile = phase('profile_sequence', 'component-profile', phase_args)
    registration_command, registration = phase('registration_sequence', 'component-registration', phase_args)
    equal(profile, event_commands[8]['arguments']['profile'], 'Prepared profile differs from original registration')
    equal(registration['contract'], event_commands[9]['arguments']['contract'], 'Prepared contract differs from original registration')
    for phase_command, left, right in ((profile_command, 7, 8), (registration_command, 8, 9)):
        require(commands[evidence['events'][left]['after']]['end_frame'] < phase_command['start_frame']
            < phase_command['end_frame'] < commands[evidence['events'][right]['before']]['start_frame'],
            'Native phase moved across an original mutation')
    record = providers.succeeded(event_commands[10]); result_raw = providers.succeeded(event_commands[11])
    equal(result_raw['artifact'], record, 'Initial component result replaced actual run record')
    finish_command, finish_raw = phase('finish_sequence', 'finish-components', {**phase_args,
        'record_id': record['bindings']['record_id'], 'result_sequence': event_commands[11]['sequence']})
    require(commands[evidence['events'][11]['after']]['end_frame'] < finish_command['start_frame'],
        'Native final checking preceded original manager completion')
    equal(finish_raw['result'], result_raw, 'Native finish recomputed or substituted its retained result')
    parent = corpus.fixed.by_id[expected['parent']]
    completed = inspect(evidence['completed'], corpus.fixed.document('fixed', parent['manager_state']), 'fixed')
    require(finish_command['end_frame'] < completed['start_frame'], 'Completed build snapshot preceded native final checks')
    if len(event_commands) > 12:
        require(evidence['events'][12]['before'] == evidence['completed']
            or completed['end_frame'] < commands[evidence['events'][12]['before']]['start_frame'],
            'Historical build inspection was delayed until later original mutations')
    equal(evidence['inspections'],
        sorted(inspection_order, key=lambda sequence: commands[sequence]['start_frame']), 'Hidden or unclaimed manager inspection')
    require(len(set(evidence['inspections'])) == len(inspection_order) and used == set(commands),
        'Hidden or unclaimed native workflow operation')
    equal(evidence['record_identities'], bindings.record_ids, 'Actual historical record physical identity census differs')
    # Decode the two historical snapshots through the exact production view
    # reader, retaining one shared cache. Only native replies seed record data.
    upstream = views.value._build_value(upstream_raw, kind='synthetic', result=views.value._result_value)
    retained_result = views.value._result_value(result_raw)
    built = views.value._build_value(finish_raw, kind='components', result=lambda value: retained_result)
    before_records = tuple((key, views.value._records[key]) for key in ('request', 'behavior', 'mechanism'))
    after_records = (*before_records, ('components', views.value._records['components']))
    rebuilt = observed_public_graph(oracle, request, config_argument, upstream, built, before_records, after_records)
    equal(rebuilt, actual, 'Raw native build/record bindings do not reproduce the observed complete public identity graph')
    return {'id': expected['id'], 'events': len(originals), 'complete_graph_sha256': sha(canonical(actual)),
        'original_events': [event['id'] for event in originals]}


def validate_process(row, receipt, artifacts, pids, *, initializer):
    require(type(row['pid']) is int and row['pid'] > 0 and row['pid'] not in pids
        and type(row['returncode']) is int and row['returncode'] == 0 and row['closed'] is True
        and row['invalidated'] is False and row['executable_sha256'] == receipt['native_inputs']['sha256']['biocompiler-core'],
        'Retained manager process authority or lifetime differs')
    pids.add(row['pid'])
    equal(artifacts.json(row['stderr']), {'hex': ''}, 'Retained manager wrote unexpected stderr')
    equal(artifacts.json(row['after_close']), {'type': 'CoreProtocolError',
        'message': 'Callback session is closed; it cannot reconnect', 'traffic_unchanged': True, 'pid_unchanged': True},
        'Closed retained manager resumed')
    manager.check_guard(artifacts.json(row['guard'], r.MAX_ARTIFACT_BYTES), initializer=initializer,
        frames=row['frames'], artifacts=artifacts)


def validate_checks(receipt, corpus, artifacts):
    if __package__:
        from . import pipeline_fixed_direct_controls as direct
    else:
        import pipeline_fixed_direct_controls as direct
    require(type(receipt.get('completed_checks')) is int and receipt['completed_checks'] == 39
        and type(receipt.get('checks')) is list and len(receipt['checks']) == 39,
        'Incomplete installed retained-manager workflow campaign')
    current, counterpart = providers.validate_counterpart(receipt, artifacts, 'fixed-build-original', corpus.build)
    execution = artifacts.json(receipt['original_execution'])
    equal(execution['contexts'], [item for path, (name, methods) in METHODS.items()
        for item in (path+'::fixture.setUpClass', *(path+'::'+name+'.'+method for method in methods))],
        'Original source contexts were omitted or reordered')
    require(set(execution) == {'contexts', 'methods', 'assertions', 'log', 'entries'} and execution['methods'] == 13
        and execution['assertions'] == 'passed' and type(execution['log']) is str and execution['log'].endswith('\nOK\n')
        and ['biocompiler.compiler.components', 'run_component_pipeline'] in execution['entries'],
        'Original unchanged-body assertions did not complete')
    channel, application = manager.declarations()
    manager.validate_verify(receipt, artifacts, channel, application)
    oracle, originals = load_oracle(installed=False), []
    # Independently rebuild source-owned authoring roots. No accepted original
    # record is ever consumed by the native request or the receipt view reader.
    equal(oracle.capture(retain=originals), current, 'Independent original authority is not reproducible')
    authorities = {case['authority_sha256']: objects['authority_objects']
        for case, objects in zip(corpus.build['cases'], originals)}
    sessions, pids, projected = set(), set(), []
    for expected, row in zip(corpus.cases, receipt['checks']):
        require(type(row) is dict and set(row) == {'id', 'actual', 'evidence', 'pid', 'returncode', 'closed', 'invalidated',
            'executable_sha256', 'stderr', 'frames', 'after_close', 'guard'} and row['id'] == expected['id'],
            'Missing or reordered original retained workflow')
        validate_process(row, receipt, artifacts, pids, initializer='initialize-synthetic')
        details = {}
        traffic = manager.validate_frames(row['frames'], artifacts, channel, application, sessions=sessions,
            details=details, provider_calls=False, initializer='initialize-synthetic')
        result = validate_case(corpus, expected, artifacts.json(row['actual'], r.MAX_ARTIFACT_BYTES),
            artifacts.json(row['evidence'], r.MAX_ARTIFACT_BYTES), details, oracle, authorities[expected['authority']])
        projected.append({**result, **traffic})
    direct_projection = direct.validate(receipt, corpus, oracle, artifacts, sessions, pids, originals=originals)
    require(artifacts.used == set(artifacts.declared), 'Unreferenced complete retained-workflow evidence')
    return {'continuations': projected, 'direct_controls': direct_projection}


def compare(root, native_root, *, revision, source_revision, run_id):
    require(type(revision) is str and re.fullmatch(r'[0-9a-f]{40}', revision)
        and type(source_revision) is str and re.fullmatch(r'[0-9a-f]{40}', source_revision)
        and type(run_id) is str and run_id, 'Missing current retained-workflow validation authority')
    root, native_root = Path(root), Path(native_root)
    names = {'realization-'+target+'-py'+python for target in r.PLATFORMS for python in r.PYTHONS}
    require(root.is_dir() and not root.is_symlink() and native_root.is_dir() and not native_root.is_symlink()
        and {path.name for path in root.iterdir() if path.name.startswith('realization-')} == names,
        'Incomplete four-runtime retained-workflow matrix')
    corpus, receipts, binaries, reference_projection = Corpus(), {}, {}, None
    for target, (system, machine) in r.PLATFORMS.items():
        native = r.verify_binaries(native_root / target, revision, target)
        binaries[target] = native
        for python in r.PYTHONS:
            name = 'realization-'+target+'-py'+python
            directory = root / name
            require(directory.is_dir() and not directory.is_symlink(), 'Unsafe retained-workflow runtime slot')
            inputs, inputs_pin = r.read(directory / 'native-inputs.json', r.CONTROL_BYTES)
            require(all(inputs.get(key) == value for key, value in native.items()) and inputs.get('run_id') == run_id
                and inputs.get('source_revision') == source_revision and type(inputs.get('python_version')) is str
                and inputs['python_version'].startswith(python+'.'), 'Stale retained-workflow native inputs')
            receipt, receipt_pin = r.read(directory / RECEIPT_FILE)
            wanted = {'schema_version': SCHEMA, 'status': 'success', 'scope': SCOPE, 'revision': revision,
                'source_revision': source_revision, 'run_id': run_id, 'python_version': inputs['python_version'],
                'system': system, 'machine': machine, 'native_platform': target,
                'artifact_directory': ARTIFACT_DIRECTORY, 'native_inputs': native,
                'python_sources': product_sources(corpus), 'campaign_sources': r.source_pins(SOURCES), **metadata(corpus)}
            for key, value in wanted.items():
                equal(receipt.get(key), value, 'Stale or mixed retained-workflow receipt: '+key)
            require(type(receipt.get('package_path')) is str and Path(receipt['package_path']).is_absolute()
                and not Path(receipt['package_path']).is_relative_to(ROOT), 'Retained-workflow package was not installed')
            require(type(receipt.get('executables')) is dict and set(receipt['executables']) == {'core', 'verify'}
                and all(type(path) is str and Path(path).is_absolute() and Path(path).name == 'biocompiler-'+role
                    for role, path in receipt['executables'].items())
                and Path(receipt['executables']['core']).parent == Path(receipt['executables']['verify']).parent,
                'Exact retained-workflow binary selection absent')
            artifacts = manager.Artifacts(directory / ARTIFACT_DIRECTORY, receipt['artifacts'])
            projected = canonical(validate_checks(receipt, corpus, artifacts))
            require(reference_projection is None or projected == reference_projection,
                'Complete retained-workflow observations differ across four runtimes')
            reference_projection = projected
            receipts[name] = {'receipt_sha256': receipt_pin, 'native_inputs_sha256': inputs_pin, 'complete_artifacts': artifacts.verified}
    return {'schema_version': 'biocompiler.pipeline_fixed_continuation_reproducibility.v1', 'status': 'success', 'scope': SCOPE,
        'revision': revision, 'source_revision': source_revision, 'run_id': run_id, **metadata(corpus),
        'receipts': receipts, 'native_inputs': binaries, 'complete_results_sha256': sha(reference_projection),
        'projection': 'validated_unique_session_UUID4_and_process_PID_only;exact_command_invocation_hash_bindings_verified_before_projection;complete_frames_retained'}


def campaign_main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    for role in ('core', 'verify'):
        parser.add_argument('--'+role, required=True, type=Path)
        parser.add_argument('--'+role+'-sha256', required=True)
    parser.add_argument('--native-root', required=True, type=Path)
    parser.add_argument('--platform', required=True, choices=r.PLATFORMS)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    import biocompiler
    from biocompiler.core_client import CoreClient
    for name in sorted(manager.TRANSPORT_MODULES | manager.LITERAL_MODULES | {'biocompiler.core_pipeline_provider_views', 'biocompiler.core_pipeline_build_views'}):
        importlib.import_module(name)
    # Preload every source-owned class before loading authoring-only recipes.
    corpus, directory = Corpus(), args.output.with_name(ARTIFACT_DIRECTORY)
    for path in product_sources(corpus):
        importlib.import_module(path.removeprefix('src/').removesuffix('.py').replace('/', '.'))
    directory.mkdir(parents=True, exist_ok=True)
    require(not directory.is_symlink() and not any(directory.iterdir()), 'Unsafe or nonempty retained-workflow artifact directory')
    started = time.monotonic()
    receipt = {'schema_version': SCHEMA, 'status': 'running', 'scope': SCOPE, **metadata(corpus),
        'revision': os.environ.get('GITHUB_SHA'), 'source_revision': os.environ.get('GITHUB_HEAD_SHA', os.environ.get('GITHUB_SHA')),
        'run_id': os.environ.get('GITHUB_RUN_ID'), 'python_version': platform.python_version(), 'system': platform.system(),
        'machine': platform.machine(), 'native_platform': args.platform, 'package_path': str(Path(biocompiler.__file__).resolve()),
        'checks': [], 'direct_checks': [], 'artifacts': {}, 'artifact_directory': ARTIFACT_DIRECTORY, '_artifact_directory': str(directory)}
    code = 1
    try:
        require(not Path.cwd().resolve().is_relative_to(ROOT), 'Run installed retained-workflow campaign outside checkout')
        require(receipt['run_id'] and receipt['source_revision']
            and (platform.system(), platform.machine()) == r.PLATFORMS[args.platform], 'Missing or mismatched hosted retained-workflow authority')
        providers.installed_modules()
        native = r.verify_binaries(args.native_root, receipt['revision'], args.platform)
        receipt['native_inputs'], receipt['executables'] = native, {}
        for role in ('core', 'verify'):
            path, pin = getattr(args, role), getattr(args, role+'_sha256')
            require(path.is_absolute() and path.resolve() == (args.native_root / ('biocompiler-'+role)).resolve()
                and not path.is_symlink() and os.access(path, os.X_OK) and pin == native['sha256'][path.name], 'Unbound retained-workflow binary')
            receipt['executables'][role] = str(path)
        receipt['python_sources'] = product_sources(corpus)
        for relative, pin in receipt['python_sources'].items():
            name = relative.removeprefix('src/').removesuffix('.py').replace('/', '.')
            require(sha(r.raw_file(Path(sys.modules[name].__file__))) == pin, 'Installed retained-workflow source differs: '+name)
        receipt['campaign_sources'] = r.source_pins(SOURCES)
        client = CoreClient(args.core, role='core', expected_sha256=args.core_sha256, timeout_seconds=300)
        manager.verify_rejection(args.verify, args.verify_sha256, receipt)
        campaign(client, corpus, receipt)
        receipt['completed_checks'] = len(receipt['checks'])
        validate_checks(receipt, corpus, manager.Artifacts(directory, receipt['artifacts']))
        equal(r.verify_binaries(args.native_root, receipt['revision'], args.platform), native, 'Retained-workflow binaries changed during execution')
        receipt['status'], code = 'success', 0
    except Exception as error:
        receipt['status'], receipt['error'] = 'failure', type(error).__name__+': '+str(error)
        print(receipt['error'], file=sys.stderr)
    receipt['completed_checks'], receipt['duration_seconds'] = len(receipt['checks']), round(time.monotonic()-started, 6)
    del receipt['_artifact_directory']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(receipt)+b'\n')
    print('Installed retained-workflow views:', receipt['status'], receipt['completed_checks'], 'chains, 566 original operations, six direct controls')
    return code


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if '--compare' not in arguments:
        return campaign_main(arguments)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compare', required=True, action='store_true')
    for name in ('root', 'native-root', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args(arguments)
    result = compare(args.root, args.native_root, revision=os.environ.get('GITHUB_SHA'),
        source_revision=os.environ.get('GITHUB_HEAD_SHA', os.environ.get('GITHUB_SHA')), run_id=os.environ.get('GITHUB_RUN_ID'))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(result)+b'\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
