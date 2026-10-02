#!/usr/bin/env python3
"""Capture original fixed-pipeline boundaries across the complete 467-method cohort.

The preceding complete manager ledger supplies every internal and subsequent
manager transition. Actual original function bodies supply boundary observations;
patched callbacks, mocked boundaries and Python-only inputs remain explicit.
Captured acceptance is expected evidence, never an executable native action.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
import dis
import gzip
import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src'), str(ROOT / 'tests')]
from tools.freeze_checked_pipeline import (FILES, Observer, inventory, load, portable_sources, source_inventory)
from tools.package_checked_pipeline_corpus import canonical, sha, require
from biocompiler.compiler import components, synthetic, pipeline, synthetic_build
from biocompiler.synthesis import selection as selection_module
from biocompiler.compiler.request import RealizationRequest
from biocompiler.synthesis.synthetic import SyntheticGeneratorConfig

INDEX = ROOT / 'tests/conformance/fixed-pipeline-literals-v1.json'
DOCUMENTS = INDEX.with_suffix('')
OUT = ROOT / 'generated/migration-next/fixed-pipeline-capture'
PRIOR_MANIFEST = ROOT / 'tests/conformance/checked-pipeline-full-v1.json'
PRIOR_MANIFEST_SHA = '8c9702c131e19af9a9950402c06a554cb531d81789cd83f51a23f0e5ba0fac44'
PRIOR_INVENTORY = '1b8ce09b5bb39e9bec43dae64c00291716a5971349eafd14c1f9f7e2a6bb6117'
TARGETS = {synthetic.run_synthetic_pipeline.__code__: 'run_synthetic_pipeline',
           components.run_component_pipeline.__code__: 'run_component_pipeline'}
BINDINGS = ((synthetic, ('lower_to_behavior', 'verify_lowering', 'generate_synthetic', 'check_synthetic_candidate', 'catalog_for_profile')),
            (components, ('run_synthetic_pipeline', 'adapt_synthetic_components', 'check_component_assembly', 'check_component_behavior', 'check_composition')),
            (selection_module, ('select_synthetic',)), (pipeline.PassManager, ('register',)))
BASE_BINDINGS = {(owner.__name__ + '.' + key): getattr(owner, key) for owner, keys in BINDINGS for key in keys}


def prior_ledger():
    require(sha(PRIOR_MANIFEST.read_bytes()) == PRIOR_MANIFEST_SHA, 'Complete original manager manifest changed')
    manifest = json.loads(PRIOR_MANIFEST.read_bytes())
    archive = (PRIOR_MANIFEST.parent / manifest['archive']['path']).read_bytes()
    require(sha(archive) == manifest['archive']['sha256'], 'Complete original manager archive changed')
    raw = gzip.decompress(archive)
    require(sha(raw) == manifest['archive']['uncompressed_sha256'], 'Complete original manager index changed')
    value = json.loads(raw)
    require(value['inventory_fingerprint'] == PRIOR_INVENTORY, 'Original manager inventory differs')
    return value


class FixedObserver(Observer):
    def __init__(self, prior):
        super().__init__(FILES)
        self.prior = prior
        self.constructor_events = defaultdict(list)
        self.manager_events = defaultdict(list)
        for event in prior['events']:
            if event['api'] == 'PassManager.__init__':
                self.constructor_events[event['context']].append(event)
            if event['manager'] is not None:
                self.manager_events[event['manager']].append(event['id'])
        self.constructor_counts = Counter()
        self.manager_bindings = {}
        self.cases = []

    def provider(self, value):
        if not isinstance(value, Mock):
            return super().provider(value)
        identity = self.handle(value, 'provider')
        if identity not in self.providers:
            self.providers[identity] = {'id': identity, 'class': type(value).__module__ + '.' + type(value).__qualname__,
                'origin': 'original_test_mock', 'module': 'unittest.mock',
                'native_recipe': {'status': 'pending_review', 'reason': 'mocked_boundary_is_not_real_pipeline_execution'}}
            # Reading return_value creates a new child Mock when its default
            # sentinel is unset. Retain existing state without changing it.
            state = vars(value)
            self.providers[identity].update(return_value=self.encode(state.get('_mock_return_value')),
                side_effect=self.encode(state.get('_mock_side_effect')),
                existing_children=self.encode(state.get('_mock_children', {})))
        return {'$type': 'provider', 'id': identity}

    def active_context(self):
        if self.context is not None:
            return self.context['id']
        source = self.source()
        return source['file'] + '::fixture.' + source['function']

    def register_manager(self, frame):
        context = self.active_context()
        ordinal = self.constructor_counts[context]
        require(ordinal < len(self.constructor_events[context]), 'New original manager constructor occurrence')
        old = self.constructor_events[context][ordinal]
        manager = frame.f_locals['self']
        handle = self.handle(manager, 'manager')
        self.manager_bindings[handle] = {'manager': old['manager'], 'context': context,
            'constructor_event': old['id'], 'events': self.manager_events[old['manager']]}
        self.constructor_counts[context] += 1

    def bindings(self):
        values, changed = {}, []
        for owner, keys in BINDINGS:
            for key in keys:
                identity = owner.__name__ + '.' + key
                value = getattr(owner, key)
                values[identity] = self.provider(value)
                if value is not BASE_BINDINGS[identity]:
                    changed.append(identity)
        return values, changed

    def authority(self, arguments):
        request, history, config = arguments.get('request'), arguments.get('history'), arguments.get('config')
        result = {'until': arguments.get('until'), 'config': None, 'request': None, 'history': None}
        unsupported = []
        if isinstance(request, RealizationRequest):
            result['request'] = request.to_dict()
        else:
            unsupported.append('request_python_type')
        if config is not None:
            if isinstance(config, SyntheticGeneratorConfig):
                result['config'] = config.to_dict()
            else:
                unsupported.append('config_python_type')
        if isinstance(history, (tuple, list)) and all(hasattr(item, 'to_dict') for item in history):
            result['history'] = [item.to_dict() for item in history]
        else:
            unsupported.append('history_python_iteration')
        return self.store.retain(result), unsupported

    def returned(self, value):
        records = {}
        for key in ('candidate', 'assembly', 'link_result', 'behavior_result', 'selection_result'):
            if hasattr(value, key):
                item = getattr(value, key)
                records[key] = None if item is None else item.to_dict()
        records['stages'] = {key: item.to_dict() for key, item in value.manager._records.items()}
        return self.store.retain(records)

    def trace(self, frame, event, argument):
        if event != 'call' or self.serializing:
            return None
        if frame.f_code is pipeline.PassManager.__init__.__code__:
            with self.quiet():
                self.register_manager(frame)
            return None
        operation = TARGETS.get(frame.f_code)
        mocked = (frame.f_code is Mock.__call__.__code__ and frame.f_back is not None
            and frame.f_back.f_code is synthetic_build.build_synthetic_package.__code__
            and frame.f_back.f_locals.get('builder') is frame.f_locals.get('self'))
        if operation is None and not mocked:
            return None
        arguments = dict(frame.f_locals)
        if mocked:
            operation = 'run_synthetic_pipeline'
            arguments = {'request': arguments['args'][0], 'history': arguments['args'][1],
                         **arguments['kwargs'], 'mock': arguments['self']}
        observation = self.begin(operation, arguments)
        with self.quiet():
            bindings, changed = self.bindings()
            authority, invalid = self.authority(arguments)
            observation.update(kind='mocked_boundary' if mocked else 'actual_original_function',
                authority=authority, runtime_bindings=bindings, changed_bindings=changed,
                python_only_inputs=invalid, native_replay='pending_real_native_fixed_pipeline_execution')
            if mocked:
                observation['mock'] = self.provider(frame.f_locals['self'])
                observation['mock_calls_before'] = frame.f_locals['self'].call_count
            self.cases.append(observation)
        last_error = [None]
        def local(current, kind, value):
            if kind == 'exception':
                last_error[0] = value[1]
            elif kind == 'return':
                if current.f_code not in self.opcodes:
                    self.opcodes[current.f_code] = {item.offset: item.opname for item in dis.get_instructions(current.f_code)}
                normal = self.opcodes[current.f_code].get(current.f_lasti, '').startswith('RETURN_')
                require(normal or last_error[0] is not None, 'Original fixed pipeline exception was lost')
                with self.quiet():
                    observation['locals_at_exit'] = self.document(dict(current.f_locals))
                    manager = getattr(value, 'manager', None) if normal else current.f_locals.get('manager')
                    if manager is None and 'upstream' in current.f_locals:
                        manager = current.f_locals['upstream'].manager
                    if manager is not None:
                        handle = self.handle(manager, 'manager')
                        observation['manager'] = handle
                        observation['manager_ledger'] = self.manager_bindings[handle]
                        observation['manager_state'] = self.state(manager)
                    else:
                        observation['manager_ledger'] = None
                        observation['manager_state'] = None
                    if normal and not mocked:
                        observation['complete_records'] = self.returned(value)
                    if mocked:
                        observation['mock_calls_after'] = current.f_locals['self'].call_count
                self.finish(observation, value=value, error=None if normal else last_error[0])
            return local
        return local

    @contextmanager
    def installed(self):
        previous = sys.gettrace()
        sys.settrace(self.trace)
        try:
            yield
            require(sys.gettrace() == self.trace, 'Fixed pipeline observer was replaced')
        finally:
            sys.settrace(previous)


def child_main(script, output):
    calls = []
    def profile(frame, event, argument):
        if event == 'call' and frame.f_code in TARGETS:
            calls.append(TARGETS[frame.f_code])
    previous = sys.getprofile()
    sys.setprofile(profile)
    try:
        exec(compile(script, '<string>', 'exec'), {'__name__': '__main__'})
    finally:
        sys.setprofile(previous)
    Path(output).write_bytes(canonical({'actual_fixed_pipeline_calls': calls}) + b'\n')


def capture():
    require(os.environ.get('PYTHONHASHSEED') == '0', 'Capture requires PYTHONHASHSEED=0')
    require(not INDEX.exists() and not DOCUMENTS.exists(), 'Refusing to replace an immutable original corpus')
    pin = sha(Path(__file__).read_bytes())
    prior = prior_ledger()
    modules = [load(path) for path in FILES]
    methods = [path + '::' + test.id().split('.', 1)[1] for path, module in zip(FILES, modules) for test in inventory(module)]
    require(methods == prior['original_methods'], 'Complete original 467-method inventory changed')
    sources = source_inventory(FILES)
    require(sources == prior['source_files'], 'Original complete manager source differs before fixed pipeline capture')
    OUT.mkdir(parents=True, exist_ok=True)
    log = OUT / 'original-tests.log'
    original_subprocess = subprocess.run
    baseline_children, observed_children, child_calls = [], [], []
    def child_capture(destination, *, instrument=False):
        def observe(command, *args, **kwargs):
            if instrument:
                require(isinstance(command, list) and len(command) == 3 and command[:2] == [sys.executable, '-c'],
                        'New original subprocess shape requires complete capture')
                with tempfile.TemporaryDirectory(prefix='fixed-pipeline-child-') as directory:
                    output = Path(directory) / 'calls.json'
                    bootstrap = 'from tools.capture_fixed_pipeline_literals import child_main; child_main(' + repr(command[2]) + ',' + repr(str(output)) + ')'
                    result = original_subprocess([*command[:2], bootstrap], *args, **kwargs)
                    child_calls.append(json.loads(output.read_bytes()))
            else:
                result = original_subprocess(command, *args, **kwargs)
            destination.append({'command': command, 'returncode': result.returncode, 'stdout': result.stdout,
                                'stderr': result.stderr, 'hash_seed': kwargs.get('env', {}).get('PYTHONHASHSEED')})
            return result
        return observe
    with portable_sources(), patch.object(subprocess, 'run', child_capture(baseline_children)), log.open('w') as stream:
        baseline = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.TestSuite(
            test for module in modules for test in inventory(module)))
    require(baseline.wasSuccessful() and baseline.testsRun == 467 and not baseline.skipped,
            'Original fixed pipeline baseline assertions failed')
    observer = FixedObserver(prior)
    class Recorded(unittest.TextTestResult):
        def startTest(self, test):
            path = FILES[modules.index(sys.modules[type(test).__module__])]
            observer.context = {'id': path + '::' + test.id().split('.', 1)[1], 'kind': 'original_method',
                                'assertion_status': 'passed', 'events': []}
            super().startTest(test)
        def stopTest(self, test):
            observer.contexts.append(observer.context)
            observer.context = None
            require(not observer.stack, 'Unclosed original fixed pipeline observation')
            super().stopTest(test)
    with portable_sources(), observer.installed(), patch.object(subprocess, 'run', child_capture(observed_children, instrument=True)), log.open('a') as stream:
        observed = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=Recorded).run(unittest.TestSuite(
            test for module in modules for test in inventory(module)))
    require(observed.wasSuccessful() and observed.testsRun == 467 and not observed.skipped,
            'Observed original fixed pipeline assertions failed')
    require(baseline_children == observed_children == prior['baseline_subprocesses'], 'Original subprocess bytes changed')
    require(child_calls == [{'actual_fixed_pipeline_calls': []}, {'actual_fixed_pipeline_calls': []}],
            'Original child contains fixed pipeline calls requiring full boundary capture')
    require(all(not item['events'] for item in prior['contexts'] if item['kind'] == 'original_subprocess'),
            'Original child manager work requires additional fixed pipeline capture')
    require(dict(observer.constructor_counts) == {key: len(value) for key, value in observer.constructor_events.items()},
            'Original manager creation census changed')
    require(sources == source_inventory(FILES), 'Original fixed pipeline source changed during capture')
    require(sha(Path(__file__).read_bytes()) == pin, 'Fixed pipeline capture tool changed during execution')
    result = {'schema_version': 'biocompiler.fixed_pipeline_literals.v1',
        'scope': 'complete_original_function_observations_not_imported_acceptance_or_native_parity',
        'capture_tool': {'path': 'tools/capture_fixed_pipeline_literals.py', 'sha256': pin},
        'capture_support': {path: sha((ROOT / path).read_bytes()) for path in (
            'tools/freeze_checked_pipeline.py', 'tools/package_checked_pipeline_corpus.py')},
        'source_files': sources, 'original_methods': methods, 'contexts': observer.contexts,
        'prior_ledger': {'manifest': PRIOR_MANIFEST.relative_to(ROOT).as_posix(), 'manifest_sha256': PRIOR_MANIFEST_SHA,
            'inventory_fingerprint': PRIOR_INVENTORY, 'contexts': len(prior['contexts']), 'events': len(prior['events'])},
        'subprocesses': observed_children, 'subprocess_function_calls': child_calls, 'providers': observer.providers, 'cases': observer.cases,
        'manager_bindings': observer.manager_bindings, 'document_directory': DOCUMENTS.name,
        'documents': [{'id': key, 'bytes': len(canonical(value)) + 1} for key, value in sorted(observer.store.documents.items())],
        'coverage': {'original_methods': 467, 'contexts': len(observer.contexts), 'cases': len(observer.cases),
            'operations': dict(Counter(item['api'] for item in observer.cases)),
            'outcomes': dict(Counter(item['outcome'] for item in observer.cases)),
            'kinds': dict(Counter(item['kind'] for item in observer.cases)),
            'documents': len(observer.store.documents), 'document_bytes': observer.store.size,
            'providers': len(observer.providers), 'original_manager_constructors': sum(observer.constructor_counts.values())}}
    result['inventory_fingerprint'] = sha(canonical(result))
    raw = canonical(result) + b'\n'
    require(len(raw) < 64 * 1024 * 1024, 'Fixed pipeline index requires bounded packaging')
    DOCUMENTS.mkdir()
    for identity, value in observer.store.documents.items():
        require(sha(canonical(value)) == identity, 'Original boundary document changed')
        (DOCUMENTS / (identity + '.json')).write_bytes(canonical(value) + b'\n')
    INDEX.write_bytes(raw)
    receipt = {'inventory_fingerprint': result['inventory_fingerprint'], 'index_sha256': sha(raw),
               'index_bytes': len(raw), 'coverage': result['coverage']}
    (OUT / 'receipt.json').write_bytes(canonical(receipt) + b'\n')
    print(json.dumps(receipt, sort_keys=True), flush=True)


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    capture()
