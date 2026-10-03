#!/usr/bin/env python3
"""Complete original reference-manager traces in a canonical, isolated Python package.

No manager/provider methods are replaced. The two real unittest modules execute
unchanged, first without observation and then with a code-identity trace in a
separate process. Graphs retain physical identities and every stored field;
mutating containers acquire new content documents without changing identity.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter
from contextlib import contextmanager
from dataclasses import fields, is_dataclass
import dis
from enum import Enum
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import CodeType, FunctionType, MappingProxyType
import unittest
from unittest.mock import Mock, DEFAULT

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'biocompiler.reference_pipeline_semantics.v1'
CORPUS = ROOT / 'tests/conformance/reference-pipeline-semantics-v1.json'
DOCUMENTS = CORPUS.with_suffix('')
TESTS = ('test_construct_pipeline', 'test_molecular_pipeline')
FILES = ('tools/capture_reference_pipeline_semantics.py', 'tools/manager_registration_source_lineage.py',
         'tests/test_construct_pipeline.py', 'tests/test_molecular_pipeline.py', 'examples/reference_construct.py')
DATA = ('data/references/fap_car/manifest.json', 'data/references/fap_car/independent-audit.json', 'data/references/fap_car/source-excerpts.html', 'tests/conformance/manager-registration-source-lineage-v1.json')
METHODS = ('__init__', 'register_completion_profile', 'set_dependency', 'register',
           'register_component_input', 'admit_component_input', 'add_input', 'get', 'run', 'result', 'target')
TYPE_MODULES = ('compiler.pipeline', 'compiler.passes', 'compiler.construct', 'compiler.molecular',
    'artifacts.provenance', 'ir.components', 'ir.construct', 'ir.molecular', 'ir.composition', 'ir.intent',
    'registry.components', 'registry.references', 'registry.reference_components',
    'semantics.component_contracts', 'semantics.context', 'semantics.coordinates',
    'semantics.types', 'ir.component_contracts', 'verification.construct', 'verification.molecular', 'verification.components')
MAX_BYTES = 256 * 1024 * 1024
MAX_DOCUMENT = 16 * 1024 * 1024


def require(value, message):
    if not value:
        raise AssertionError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fingerprint(value):
    return sha(canonical({key: item for key, item in value.items() if key != 'inventory_fingerprint'}))


@contextmanager
def paths():
    previous = sys.path[:]
    sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests'), str(ROOT)]
    try:
        yield
    finally:
        sys.path[:] = previous


def relative(path):
    path = Path(path).resolve()
    require(path.is_relative_to(ROOT), 'Observed source escaped canonical package')
    return path.relative_to(ROOT).as_posix()


def class_name(value):
    cls = value if isinstance(value, type) else type(value)
    return cls.__module__ + '.' + cls.__qualname__


def leaves(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from leaves(item)
        else:
            yield item


def code_tree(code):
    yield code
    for item in code.co_consts:
        if type(item) is CodeType:
            yield from code_tree(item)


def verify_function(fn):
    require(type(fn) is FunctionType, 'Original function was replaced')
    module = sys.modules.get(fn.__module__)
    require(module is not None and fn.__globals__ is vars(module), 'Original function namespace differs')
    path = Path(fn.__code__.co_filename).resolve()
    require(Path(module.__file__).resolve() == path and path.is_relative_to(ROOT), 'Original function module origin differs')
    compiled = compile(path.read_bytes(), str(path), 'exec', dont_inherit=True)
    require(any(fn.__code__ == code for code in code_tree(compiled)), 'Original executable code differs from source')


class Store:
    def __init__(self):
        self.docs = {}
        self.bytes = 0

    def add(self, value):
        raw = canonical(value)
        require(len(raw) < MAX_DOCUMENT, 'Reference-manager document limit')
        key = sha(raw)
        if key not in self.docs:
            self.bytes += len(raw) + 1
            require(self.bytes <= MAX_BYTES, 'Reference-manager total document limit')
            self.docs[key] = value
        return key


class Graph:
    def __init__(self, store, manager):
        self.store, self.manager = store, manager
        self.values, self.identities, self.functions = [], {}, []
        self.safe = {value for suffix in TYPE_MODULES for value in vars(importlib.import_module('biocompiler.' + suffix)).values()
            if isinstance(value, type) and is_dataclass(value) and value.__module__ == 'biocompiler.' + suffix}
        self.sources = {}

    def identity(self, value):
        key = id(value)
        if key not in self.identities:
            self.identities[key] = len(self.values)
            self.values.append(value)
            if type(value) is FunctionType:
                self.functions.append(value)
        index = self.identities[key]
        require(self.values[index] is value, 'Physical graph identity collision')
        return 'object/' + str(index)

    def source(self, fn):
        if id(fn) in self.sources:
            return self.sources[id(fn)]
        verify_function(fn)
        code = fn.__code__
        value = {'file': relative(code.co_filename), 'qualname': code.co_qualname,
            'line': code.co_firstlineno, 'module': fn.__module__, 'freevars': list(code.co_freevars)}
        self.sources[id(fn)] = value
        return value

    def snapshot(self, roots):
        nodes = {}
        def encode(value):
            if value is None or type(value) in (bool, int, str, float):
                return {'scalar': type(value).__name__, 'value': value}
            if isinstance(value, Enum):
                return {'enum': class_name(value), 'value': encode(value.value)}
            if isinstance(value, type):
                return {'class': class_name(value)}
            if value is DEFAULT:
                return {'sentinel': 'unittest.mock.DEFAULT'}
            supported = (type(value) in self.safe or type(value) in (dict, MappingProxyType, tuple, list, set, frozenset,
                FunctionType, self.manager) or isinstance(value, (Mock, BaseException)))
            require(supported, 'Unreviewed reference graph type: ' + class_name(value))
            identity = self.identity(value)
            if identity in nodes:
                return {'ref': identity}
            nodes[identity] = None
            if type(value) is self.manager:
                node = {'kind': 'manager', 'class': class_name(value), 'fields': [[key, encode(item)] for key, item in vars(value).items()]}
            elif type(value) in (dict, MappingProxyType):
                node = {'kind': 'mapping', 'class': type(value).__name__, 'items': [[encode(key), encode(item)] for key, item in value.items()]}
            elif type(value) in (tuple, list):
                node = {'kind': 'sequence', 'class': type(value).__name__, 'items': [encode(item) for item in value]}
            elif type(value) in (set, frozenset):
                require(all(type(item) is str for item in value), 'Unreviewed graph set element')
                node = {'kind': 'set', 'class': type(value).__name__, 'items': sorted(value)}
            elif type(value) is FunctionType:
                node = {'kind': 'provider', 'source': self.source(value), 'defaults': encode(value.__defaults__),
                    'kwdefaults': encode(value.__kwdefaults__), 'closure': [[key, encode(cell.cell_contents)]
                    for key, cell in zip(value.__code__.co_freevars, value.__closure__ or ())]}
            elif isinstance(value, Mock):
                state = vars(value)
                calls = [[[encode(item) for item in call.args], [[key, encode(item)] for key, item in call.kwargs.items()]]
                         for call in state.get('_mock_call_args_list', ())]
                node = {'kind': 'mock', 'class': 'unittest.mock.MagicMock' if 'MagicMock' in class_name(value) else class_name(value),
                    'return_value': encode(state['_mock_return_value']), 'side_effect': encode(state['_mock_side_effect']),
                    'call_count': state['_mock_call_count'], 'calls': calls}
            elif isinstance(value, BaseException):
                node = {'kind': 'exception', 'class': class_name(value), 'args': encode(value.args),
                    'fields': [[key, encode(item)] for key, item in vars(value).items()],
                    'cause': encode(value.__cause__), 'context': encode(value.__context__), 'suppress_context': value.__suppress_context__}
            else:
                node = {'kind': 'dataclass', 'class': class_name(value),
                    'fields': [[field.name, encode(object.__getattribute__(value, field.name))] for field in fields(value)],
                    'instance_fields': list(vars(value)),
                    'class_schema': vars(type(value)).get('schema_version') if type(vars(type(value)).get('schema_version')) is str and 'schema_version' not in vars(value) else None}
            nodes[identity] = self.store.add(node)
            return {'ref': identity}
        result = [[name, encode(value)] for name, value in roots]
        return self.store.add({'kind': 'graph', 'roots': result, 'nodes': nodes})


class Observer:
    def __init__(self, store):
        from biocompiler.compiler import pipeline, construct, molecular
        from biocompiler.ir.construct import ConstructRequest, ConstructCandidate
        from biocompiler.ir.molecular import MolecularArtifact
        from biocompiler.synthesis.construct import generate_construct
        from biocompiler.backends.reference import emit_reference_sequence
        self.pipeline, self.construct, self.molecular = pipeline, construct, molecular
        self.graph = Graph(store, pipeline.PassManager)
        self.rows, self.stack, self.frames, self.context = [], [], {}, None
        self.instructions, self.busy, self.error = {}, False, None
        self.raw_tracebacks = []
        self.clock = 0
        self.raw_objects, self.raw_ids = [], {}
        self.methods = {}
        for name in METHODS:
            fn = vars(pipeline.PassManager)[name]
            fn = fn.fget if isinstance(fn, property) else fn
            verify_function(fn)
            self.methods[fn.__code__] = (name, fn)
        self.calls = {construct.run_construct_pipeline.__code__: ('pipeline.construct', construct.run_construct_pipeline),
            molecular.run_molecular_pipeline.__code__: ('pipeline.molecular', molecular.run_molecular_pipeline),
            generate_construct.__code__: ('producer.generate_construct', generate_construct),
            emit_reference_sequence.__code__: ('producer.emit_reference_sequence', emit_reference_sequence)}
        self.imports = {}
        for cls in (ConstructRequest, ConstructCandidate, MolecularArtifact):
            for name in ('from_dict', 'from_json'):
                fn = getattr(cls, name).__func__
                self.imports.setdefault(fn.__code__, {})[cls] = name

    def raw_identity(self, value):
        if value is None:
            return None
        if id(value) not in self.raw_ids:
            self.raw_ids[id(value)] = 'trace/' + str(len(self.raw_objects))
            self.raw_objects.append(value)
        return self.raw_ids[id(value)]

    def source(self, frame):
        return {'file': relative(frame.f_code.co_filename), 'function': frame.f_code.co_qualname, 'line': frame.f_lineno}

    def callable(self, frame):
        matches = []
        for value in self.graph.functions:
            if value.__code__ is frame.f_code and all(frame.f_locals.get(key) is cell.cell_contents
                for key, cell in zip(value.__code__.co_freevars, value.__closure__ or ())):
                matches.append(value)
        if len(matches) > 1:
            caller = frame.f_back
            while caller is not None:
                values = list(caller.f_locals.values())
                values += [item for value in values if type(value) in (dict, MappingProxyType) for item in value.values()]
                actual = [fn for fn in matches if any(fn is value for value in values)]
                if len(actual) == 1:
                    return actual[0]
                caller = caller.f_back
        require(len(matches) <= 1, 'Ambiguous actual retained callback identity: ' + frame.f_code.co_qualname)
        return matches[0] if matches else None

    def describe(self, frame):
        code, local = frame.f_code, frame.f_locals
        if code in self.methods:
            method, fn = self.methods[code]
            return 'manager.' + method, fn, local['self']
        if code in self.calls:
            kind, fn = self.calls[code]
            return kind, fn, None
        if code in self.imports and local.get('cls') in self.imports[code]:
            cls = local['cls']
            return 'import.' + cls.__name__ + '.' + self.imports[code][cls], None, None
        # The global call is observed at its actual Python entry, even for Mock.
        caller = frame.f_back
        if caller and caller.f_code.co_filename in (self.construct.__file__, self.molecular.__file__):
            slot = 'generate_construct' if caller.f_code.co_name == 'assemble' else 'emit_reference_sequence' if caller.f_code.co_name == 'emit' else None
            if slot and code.co_name == '__call__' and isinstance(local.get('self'), Mock):
                fn = vars(self.construct if slot == 'generate_construct' else self.molecular)[slot]
                require(fn is local['self'], 'Override invocation lost actual global callable')
                return 'override.' + slot, fn, None
        if code.co_name == 'register' and code.co_filename == str(ROOT / 'tests/test_construct_pipeline.py') or (
                code.co_name == 'register' and code.co_filename == str(ROOT / 'tests/test_molecular_pipeline.py')):
            fn = self.pipeline.PassManager.register
            require(type(fn) is FunctionType and fn.__code__ is code, 'Public registration override identity differs')
            return 'registration.wrapper', fn, local['manager']
        if 'context' in local and code.co_filename in (self.construct.__file__, self.molecular.__file__,
                str(ROOT / 'tests/test_construct_pipeline.py'), str(ROOT / 'tests/test_molecular_pipeline.py')):
            fn = self.callable(frame)
            if fn is not None:
                return 'callback.' + code.co_name, fn, None
        return None

    def trace(self, frame, event, arg):
        if self.busy or self.error is not None:
            return None
        self.busy = True
        try:
            if event == 'call':
                spec = self.describe(frame)
                if spec is None:
                    return None
                kind, fn, manager = spec
                roots = [('argument:' + key, value) for key, value in frame.f_locals.items() if key not in frame.f_code.co_freevars]
                if fn is not None:
                    roots.append(('callable', fn))
                if kind.startswith('pipeline.'):
                    roots.extend((('global:generate_construct', self.construct.generate_construct),
                                  ('global:emit_reference_sequence', self.molecular.emit_reference_sequence)))
                if manager is not None and not any(value is manager for _, value in roots):
                    roots.append(('manager', manager))
                row = {'id': len(self.rows), 'entry': self.clock, 'test': self.context, 'kind': kind, 'source': self.source(frame.f_back if kind.startswith('override.') else frame),
                    'parent': self.stack[-1]['id'] if self.stack else None,
                    'manager_parent': next((x['id'] for x in reversed(self.stack) if x['kind'].startswith('manager.')), None),
                    'manager': None if manager is None else self.graph.identity(manager),
                    'before': self.graph.snapshot(roots)}
                self.clock += 1
                self.rows.append(row)
                self.stack.append(row)
                self.frames[id(frame)] = (frame, row, roots, None, None)
                return self.trace
            if id(frame) not in self.frames:
                return None
            retained, row, roots, error, traceback = self.frames[id(frame)]
            require(retained is frame, 'Retained frame collision')
            if event == 'exception':
                self.frames[id(frame)] = (frame, row, roots, arg[1], arg[2])
            elif event == 'return':
                codes = self.instructions.setdefault(frame.f_code, {i.offset: i.opname for i in dis.get_instructions(frame.f_code)})
                returned = codes.get(frame.f_lasti, '').startswith('RETURN_')
                require(returned or error is not None, 'Observed unwind lost original exception')
                row['exit'] = self.clock
                self.clock += 1
                row['outcome'] = 'return' if returned else 'raise'
                extra = [('return', arg)] if returned else [('exception', error)]
                if not returned:
                    trace, raw_trace, tb = [], [], traceback
                    while tb is not None:
                        code = tb.tb_frame.f_code
                        filename = Path(code.co_filename)
                        original = filename.is_relative_to(ROOT)
                        raw_trace.append({'node': self.raw_identity(tb), 'frame': self.raw_identity(tb.tb_frame), 'next': self.raw_identity(tb.tb_next),
                            'filename': code.co_filename, 'function': code.co_qualname,
                            'first_line': code.co_firstlineno, 'line': tb.tb_lineno,
                            'projection': len(trace) if original else None,
                            'source_sha256': sha(filename.read_bytes()) if filename.is_file() else None})
                        if original:
                            trace.append({'source': self.source(tb.tb_frame), 'line': tb.tb_lineno})
                        tb = tb.tb_next
                    row['traceback'] = trace
                    self.raw_tracebacks.append({'event': row['id'], 'exception': self.graph.identity(error), 'frames': raw_trace})
                row['after'] = self.graph.snapshot([*roots, *extra])
                require(self.stack.pop() is row, 'Observed event nesting differs')
                del self.frames[id(frame)]
            return self.trace
        except BaseException as error:
            self.error = error
            raise
        finally:
            self.busy = False


class Results(unittest.TestResult):
    def __init__(self, observer=None):
        super().__init__()
        self.observer, self.rows = observer, []

    def startTest(self, test):
        super().startTest(test)
        self.rows.append({'id': test.id(), 'class': class_name(test), 'method': test._testMethodName, 'outcomes': []})
        if self.observer:
            self.observer.context = test.id()

    def status(self, test, name, error=None):
        require(self.rows[-1]['id'] == test.id(), 'Original result ownership differs')
        item = {'status': name}
        if error:
            item['exception'] = {'class': class_name(error[1]), 'args': list(error[1].args)}
        self.rows[-1]['outcomes'].append(item)

    def addSuccess(self, test):
        self.status(test, 'success'); super().addSuccess(test)
    def addError(self, test, error):
        self.status(test, 'error', error); super().addError(test, error)
    def addFailure(self, test, error):
        self.status(test, 'failure', error); super().addFailure(test, error)
    def addSkip(self, test, reason):
        self.status(test, 'skip'); super().addSkip(test, reason)
    def addExpectedFailure(self, test, error):
        self.status(test, 'expected_failure', error); super().addExpectedFailure(test, error)
    def addUnexpectedSuccess(self, test):
        self.status(test, 'unexpected_success'); super().addUnexpectedSuccess(test)
    def addSubTest(self, test, subtest, error):
        # Actual successful subtest IDs include stable authored dependency names.
        self.rows[-1].setdefault('subtests', []).append({'id': subtest.id(), 'status': 'success' if error is None else 'failure'})
        super().addSubTest(test, subtest, error)


def product_sources():
    return tuple('src/biocompiler/' + path.relative_to(ROOT / 'src/biocompiler').as_posix()
        for path in sorted((ROOT / 'src/biocompiler').rglob('*.py')))


def child(directory, mode):
    manifest = json.loads((Path(directory) / 'manifest.json').read_bytes())
    require(ROOT == Path(directory).resolve(), 'Child did not load canonical overlay')
    for path, pin in manifest['sources'].items():
        require(sha((ROOT / path).read_bytes()) == pin, 'Copied original source changed')
    with paths():
        from biocompiler.compiler import pipeline
        require(pipeline.PassManager.__module__ == 'biocompiler.compiler.pipeline' and
                pipeline.PassManager.register.__globals__ is vars(pipeline), 'Original manager is not canonical')
        modules = [importlib.import_module(name) for name in TESTS]
        cases = [test for module in modules for test in leaves(unittest.defaultTestLoader.loadTestsFromModule(module))]
        require([sum(type(test).__module__ == module.__name__ for test in cases) for module in modules] == [9, 9], 'Original method census differs')
        for test in cases:
            verify_function(getattr(type(test), test._testMethodName))
        store = Store()
        observer = Observer(store) if mode == 'observed' else None
        result = Results(observer)
        old = sys.gettrace()
        if observer:
            sys.settrace(observer.trace)
        try:
            unittest.TestSuite(cases).run(result)
            if observer and observer.error:
                raise observer.error
            if observer:
                require(sys.gettrace() == observer.trace, 'Original trace was replaced')
        finally:
            sys.settrace(old)
        if observer and observer.error:
            raise observer.error
        require(result.wasSuccessful() and result.testsRun == 18 and not result.skipped,
                'Original tests failed: ' + repr(result.errors + result.failures))
        require(not observer or not observer.stack, 'Unfinished original trace')
        loaded = {}
        for name, module in tuple(sys.modules.items()):
            filename = vars(module).get('__file__') if module is not None else None
            if not filename:
                continue
            path = Path(filename).resolve()
            if name == 'biocompiler' or name.startswith('biocompiler.') or name in TESTS or name == 'examples.reference_construct':
                logical = relative(path)
                require(logical in manifest['sources'] and sha(path.read_bytes()) == manifest['sources'][logical], 'Loaded original module differs')
                loaded[name] = logical
        value = {'results': result.rows, 'loaded_modules': dict(sorted(loaded.items()))}
        if observer:
            from examples.reference_construct import reference_request
            authorities = {}
            for alphabet in ('DNA', 'RNA'):
                request, manifest, registry = reference_request(alphabet)
                authorities[alphabet] = {'request': store.add(request.to_dict()), 'registry': store.add(registry.to_dict()),
                    'manifests': store.add({manifest.reference_set_id: manifest.to_dict()})}
            value.update(events=observer.rows, documents=store.docs, physical_objects=len(observer.graph.values),
                authorities=authorities, raw_tracebacks=observer.raw_tracebacks)
        (ROOT / 'result.json').write_bytes(canonical(value))


def capture():
    with paths():
        from tools import manager_registration_source_lineage as lineage
    old = lineage.original_source()
    lineage.verify_source(ROOT, lineage.PATH, lineage.HISTORICAL[lineage.PATH])
    files = (*product_sources(), *FILES, *DATA)
    require(len(set(files)) == len(files), 'Duplicate overlay file')
    original_sources = {name: sha(old if name == lineage.PATH else (ROOT / name).read_bytes()) for name in files}
    require(sum((ROOT / name).stat().st_size for name in files) < 32 * 1024 * 1024, 'Overlay source limit')
    captures = []
    for mode in ('baseline', 'observed'):
        with tempfile.TemporaryDirectory(prefix='biocompiler-reference-original-') as directory:
            root = Path(directory).resolve()
            for name in files:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(old if name == lineage.PATH else (ROOT / name).read_bytes())
            (root / 'manifest.json').write_bytes(canonical({'sources': original_sources}))
            script = 'import sys;sys.path.insert(0,sys.argv[1]);from tools.capture_reference_pipeline_semantics import child;child(sys.argv[1],sys.argv[2])'
            env = dict(os.environ, PYTHONHASHSEED='0', PYTHONDONTWRITEBYTECODE='1')
            env.pop('PYTHONPATH', None)
            process = subprocess.run([sys.executable, '-I', '-c', script, str(root), mode], cwd=root,
                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
            require(process.returncode == 0, 'Canonical original child failed: ' + process.stderr.decode(errors='replace')[-16000:])
            result = root / 'result.json'
            require(result.is_file() and result.stat().st_size < MAX_BYTES, 'Original output bound')
            captures.append(json.loads(result.read_bytes()))
    baseline, observed = captures
    require(baseline['results'] == observed['results'], 'Baseline and observed complete TestCase outcomes differ')
    rows = observed['events']
    runtime = {'python': sys.version, 'events_sha256': sha(canonical(rows)), 'source_files': original_sources,
        'original_tracebacks': observed['raw_tracebacks']}
    output = ROOT / ('generated/migration-next/reference-pipeline-runtime-' + str(sys.version_info.major) + '.' + str(sys.version_info.minor) + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical(runtime) + b'\n')
    managers = {r['manager'] for r in rows if r['kind'] == 'manager.__init__'}
    top = [r for r in rows if r['kind'].startswith('manager.') and r['manager_parent'] is None]
    index = {'schema': SCHEMA, 'scope': 'original_18_reference_methods_only_no_native_acceptance', 'source_files': original_sources,
        'source_substitutions': [{'path': lineage.PATH, 'sha256': lineage.HISTORICAL[lineage.PATH], 'witness_sha256': lineage.WITNESS_SHA256}],
        'test_ids': [r['id'] for r in baseline['results']], 'baseline': baseline, 'observed_results': observed['results'],
        'loaded_modules': observed['loaded_modules'], 'events': rows, 'authorities': observed['authorities'],
        'coverage': {'methods': 18, 'managers': len(managers), 'top_level_operations': len(top),
            'events': len(rows), 'physical_objects': observed['physical_objects'], 'kinds': dict(sorted(Counter(r['kind'] for r in rows).items()))},
        'documents': {key: len(canonical(value)) + 1 for key, value in sorted(observed['documents'].items())}}
    index['inventory_fingerprint'] = fingerprint(index)
    validate(index, observed['documents'])
    validate_runtime(runtime, index, observed['documents'])
    return index, observed['documents']


def validate(index, docs, *, sources=True):
    require(index['schema'] == SCHEMA and index['scope'] == 'original_18_reference_methods_only_no_native_acceptance' and index['inventory_fingerprint'] == fingerprint(index), 'Reference-manager inventory differs')
    require(index['baseline']['results'] == index['observed_results'] and index['test_ids'] == [r['id'] for r in index['observed_results']]
        and len(set(index['test_ids'])) == len(index['test_ids']) == 18, 'Complete original per-test census differs')
    require(all(row['outcomes'] == [{'status': 'success'}] and all(x['status'] == 'success' for x in row.get('subtests', []))
        for row in index['observed_results']), 'Original unittest outcome differs')
    require(set(docs) == set(index['documents']), 'Complete document inventory differs')
    physical_ids = set()
    for key, value in docs.items():
        require(sha(canonical(value)) == key and len(canonical(value)) + 1 == index['documents'][key], 'Original document hash or bytes differ')
        if type(value) is dict and value.get('kind') == 'graph':
            physical_ids.update(value['nodes'])
            require(set(value) == {'kind', 'roots', 'nodes'} and all(pin in docs for pin in value['nodes'].values()), 'Incomplete graph node census')
            pending = [value['roots'], *[docs[pin] for pin in value['nodes'].values()]]
            while pending:
                item = pending.pop()
                if type(item) is dict:
                    if set(item) == {'ref'}:
                        require(item['ref'] in value['nodes'], 'Dangling physical graph reference')
                    else:
                        pending.extend(item.values())
                elif type(item) is list:
                    pending.extend(item)
    require(physical_ids == {'object/' + str(i) for i in range(index['coverage']['physical_objects'])}, 'Complete physical identity census differs')
    for loaded in (index['loaded_modules'], index['baseline']['loaded_modules']):
        require(loaded.get('biocompiler.compiler.pipeline') == 'src/biocompiler/compiler/pipeline.py' and
            all(loaded.get(name) == 'tests/' + name + '.py' for name in TESTS), 'Canonical original module census differs')
        for name, path in loaded.items():
            require(path in index['source_files'], 'Original module source is unpinned')
            if name == 'biocompiler' or name.startswith('biocompiler.'):
                expected = 'src/' + name.replace('.', '/')
                require(path in (expected + '.py', expected + '/__init__.py'), 'Canonical product module origin differs')
    rows = index['events']
    wanted_ids = []
    for name in TESTS:
        tree = ast.parse((ROOT / ('tests/' + name + '.py')).read_bytes())
        for cls in sorted((n for n in tree.body if isinstance(n, ast.ClassDef)), key=lambda n:n.name):
            wanted_ids.extend(name + '.' + cls.name + '.' + method.name for method in
                sorted((n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name.startswith('test_')), key=lambda n:n.name))
    require(index['test_ids'] == wanted_ids, 'Actual original TestCase identities differ')
    timeline = sorted([(row['entry'], True, row) for row in rows] + [(row['exit'], False, row) for row in rows], key=lambda x:x[0])
    require([step for step, _, _ in timeline] == list(range(2 * len(rows))), 'Original complete call timeline differs')
    stack = []
    for _, entry, row in timeline:
        if entry:
            require(row['parent'] == (stack[-1]['id'] if stack else None), 'Original complete call nesting differs')
            require(row['manager_parent'] == next((r['id'] for r in reversed(stack) if r['kind'].startswith('manager.')), None),
                'Original manager ancestor differs')
            stack.append(row)
        else:
            require(stack and stack.pop() is row, 'Original complete return nesting differs')
    require(not stack, 'Original complete call stack differs')
    require([r['id'] for r in rows] == list(range(len(rows))) and all(r['test'] in index['test_ids'] for r in rows), 'Original event ownership or order differs')
    require(all(r['before'] in docs and r['after'] in docs and r['outcome'] in ('return', 'raise') for r in rows), 'Incomplete original event')
    require(all(r['parent'] is None or 0 <= r['parent'] < r['id'] and rows[r['parent']]['test'] == r['test'] for r in rows), 'Original event parent differs')
    managers = {r['manager'] for r in rows if r['kind'] == 'manager.__init__'}
    top = [r for r in rows if r['kind'].startswith('manager.') and r['manager_parent'] is None]
    require(len(managers) == 27 and len(top) == 439, 'Original 27-manager/439-operation census differs: ' + str((len(managers), len(top))))
    require(index['coverage'] == {'methods': 18, 'managers': 27, 'top_level_operations': 439,
        'events': len(rows), 'physical_objects': index['coverage']['physical_objects'], 'kinds': dict(sorted(Counter(r['kind'] for r in rows).items()))}, 'Original coverage differs')
    if sources:
        with paths():
            from tools import manager_registration_source_lineage as lineage
        files = (*product_sources(), *FILES, *DATA)
        require(set(index['source_files']) == set(files), 'Complete original source closure differs')
        for path, pin in index['source_files'].items():
            raw = lineage.original_source() if path == lineage.PATH else (ROOT / path).read_bytes()
            require(sha(raw) == pin, 'Original source changed: ' + path)
        lineage.verify_source(ROOT, lineage.PATH, lineage.HISTORICAL[lineage.PATH])
        require(index['source_substitutions'] == [{'path': lineage.PATH, 'sha256': lineage.HISTORICAL[lineage.PATH],
            'witness_sha256': lineage.WITNESS_SHA256}], 'Original substitution proof differs')



def validate_runtime(runtime, index, docs):
    require(set(runtime) == {'python', 'events_sha256', 'source_files', 'original_tracebacks'} and
        runtime['events_sha256'] == sha(canonical(index['events'])) and runtime['source_files'] == index['source_files'],
        'Raw original runtime proof differs')
    failures = [row for row in index['events'] if row['outcome'] == 'raise']
    require([row['event'] for row in runtime['original_tracebacks']] == [row['id'] for row in
        sorted(failures, key=lambda row:row['exit'])], 'Complete raw exception census differs')
    prefixes, nodes, frames_by_id = set(), {}, {}
    for observation in runtime['original_tracebacks']:
        row = index['events'][observation['event']]
        graph = docs[row['after']]
        require(dict(graph['roots'])['exception'] == {'ref': observation['exception']}, 'Raw exception identity differs')
        frames = observation['frames']
        # This finite original cohort has no runtime-library exception frames.
        # Retain every frame and require an exact source counterpart for all of it.
        require(len(frames) == len(row['traceback']) and [frame['projection'] for frame in frames] == list(range(len(frames))),
            'Complete raw original traceback differs')
        for raw, original in zip(frames, row['traceback']):
            site = original['source']
            suffix = '/' + site['file']
            require(raw['filename'].endswith(suffix) and raw['function'] == site['function'] and raw['line'] == original['line']
                and raw['source_sha256'] == index['source_files'][site['file']], 'Raw original source frame differs')
            prefixes.add(raw['filename'][:-len(suffix)])
            fixed = {key:raw[key] for key in ('frame', 'next', 'filename', 'function', 'first_line', 'line', 'source_sha256')}
            require(raw['node'] not in nodes or nodes[raw['node']] == fixed, 'Original traceback node identity changed')
            nodes[raw['node']] = fixed
            frame_fixed = {key:raw[key] for key in ('filename', 'function', 'first_line', 'source_sha256')}
            require(raw['frame'] not in frames_by_id or frames_by_id[raw['frame']] == frame_fixed, 'Original frame identity changed')
            frames_by_id[raw['frame']] = frame_fixed
        require(all(raw['next'] == (frames[i+1]['node'] if i+1<len(frames) else None) for i,raw in enumerate(frames)),
            'Original traceback tail differs')
    require(len(prefixes) == 1, 'Raw original frames came from different canonical packages')


def load():
    index = json.loads(CORPUS.read_bytes())
    docs = {key: json.loads((DOCUMENTS / (key + '.json')).read_bytes()) for key in index['documents']}
    require({p.name for p in DOCUMENTS.iterdir()} == {key + '.json' for key in docs}, 'Unclaimed reference graph documents')
    validate(index, docs)
    return index, docs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    index, docs = capture()
    if args.freeze:
        require(not CORPUS.exists() and not DOCUMENTS.exists(), 'Refusing to replace frozen reference pipeline corpus')
        DOCUMENTS.mkdir()
        for key, value in docs.items():
            (DOCUMENTS / (key + '.json')).write_bytes(canonical(value) + b'\n')
        CORPUS.write_bytes(canonical(index) + b'\n')
    elif args.check:
        require(load() == (index, docs), 'Complete fresh original capture differs')
    else:
        path = ROOT / 'generated/migration-next/reference-pipeline-capture.json'
        path.write_bytes(canonical({'index': index, 'documents': docs}) + b'\n')
    print(json.dumps(index['coverage'], sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
