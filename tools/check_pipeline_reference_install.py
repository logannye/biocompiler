"""Installed reference workflow observations from the unchanged original tests.

The original trace remains complete comparison evidence. Python implementation
frames are classified separately from public manager operations and actual host
callbacks; this tool never manufactures old Python frames for native execution.
"""
from __future__ import annotations

from collections import Counter
import ast
import contextlib
from contextlib import contextmanager
from dataclasses import fields, is_dataclass
from enum import Enum
import importlib
import importlib.util
import dis
import json
from pathlib import Path
import platform
import sys
import sysconfig
import tempfile
from types import FunctionType, MappingProxyType
import unittest
from unittest.mock import Mock, DEFAULT

if __package__:
    from . import check_pipeline_manager_install as manager
    from . import reference_pipeline_original_counterpart as original
else:
    import check_pipeline_manager_install as manager
    import reference_pipeline_original_counterpart as original

ROOT = manager.ROOT
require, equal, canonical, sha = manager.require, manager.equal, manager.canonical, manager.sha
SCHEMA = 'biocompiler.installed_reference_workflows.v1'
RECEIPT_FILE = 'pipeline-reference.json'
ARTIFACT_DIRECTORY = 'pipeline-reference-artifacts'
SOURCE = 'tools/check_pipeline_reference_install.py'
TEST_SOURCE = 'tests/test_pipeline_reference_campaign.py'
TEST_MODULES = ('test_construct_pipeline', 'test_molecular_pipeline')
CLASSES = ('ConstructPipelineTests', 'MolecularPipelineTests')
PUBLIC_METHODS = ('set_dependency', 'register_completion_profile', '_native_register',
                  'register_component_input', 'admit_component_input', 'get', 'run', 'result')
ROLE_SOURCES = {
    'reference_components.authority': ('biocompiler.compiler.construct', 'run_construct_pipeline.<locals>.verify_authority'),
    'reference_components.linkage': ('biocompiler.compiler.construct', 'run_construct_pipeline.<locals>.verify_linkage'),
    'components_to_construct.producer': ('biocompiler.compiler.construct', 'run_construct_pipeline.<locals>.assemble'),
    'components_to_construct.layout': ('biocompiler.compiler.construct', 'run_construct_pipeline.<locals>.verify_layout'),
    'construct_to_molecular.producer': ('biocompiler.compiler.molecular', 'run_molecular_pipeline.<locals>.emit'),
    'construct_to_molecular.sequence': ('biocompiler.compiler.molecular', 'run_molecular_pipeline.<locals>.check'),
    'construct_to_molecular.composition': ('biocompiler.compiler.molecular', 'run_molecular_pipeline.<locals>.check_linkage'),
}
SOURCES = (SOURCE, TEST_SOURCE, original.FREEZER, original.RUNNER,
    'tools/pipeline_reference_runtime.py', 'tests/test_pipeline_reference_runtime.py',
    'tools/reference_pipeline_transcript.py', 'tests/test_reference_pipeline_transcript.py',
    'tools/reference_execution_guard.py', 'tests/test_reference_execution_guard.py',
    'tools/reference_attempt_receipts.py', 'tests/test_reference_attempt_receipts.py',
    'tests/test_core_reference_attempts.py',
    'tools/reference_attempt_source.py', 'tests/test_reference_attempt_source.py',
    'tests/test_core_reference_manager.py', 'tests/test_reference_backend.py',
    'tests/conformance/reference-attempt-facade-counterpart-v1.json',
    'src/biocompiler/reference_backend.py',
    'tests/test_reference_pipeline_original_counterpart.py',
    'src/biocompiler/core_reference_manager.py', 'src/biocompiler/core_reference_host.py',
    'src/biocompiler/core_reference_views.py', 'src/biocompiler/core_reference_provider_views.py',
    *manager.SOURCES)


def tool(name):
    require(name in ('reference_execution_guard', 'reference_pipeline_transcript', 'pipeline_reference_runtime',
                    'reference_attempt_receipts'),
            'Unknown closed reference campaign helper')
    return importlib.import_module('.' + name, __package__) if __package__ else importlib.import_module(name)


def source_function(function, *, expected=None):
    """Bind a live callable to actual module globals and compiled source bytes."""
    require(type(function) is FunctionType, 'Reference source callable was replaced')
    module = sys.modules.get(function.__module__)
    require(module is not None and function.__globals__ is vars(module), 'Reference callable has foreign globals')
    path = Path(module.__file__).resolve()
    require(Path(function.__code__.co_filename).resolve() == path, 'Reference callable code came from another file')
    raw = path.read_bytes()
    codes = list(manager._nested_codes(compile(raw, str(path), 'exec', dont_inherit=True)))
    require(any(code == function.__code__ and code.co_qualname == function.__qualname__ for code in codes),
            'Reference loaded callable differs from its full source')
    if expected is not None:
        require(sha(raw) == expected, 'Original reference body source changed')
    import biocompiler
    package = Path(biocompiler.__file__).resolve().parent
    logical = ('src/biocompiler/' + path.relative_to(package).as_posix() if path.is_relative_to(package)
               else path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else None)
    return {'module': module.__name__, 'path': str(path), 'sha256': sha(raw),
            'file': logical, 'qualname': function.__qualname__, 'line': function.__code__.co_firstlineno,
            'freevars': list(function.__code__.co_freevars)}


def load_original():
    path = ROOT / original.FREEZER
    require(sha(path.read_bytes()) == original.FREEZER_SHA, 'Frozen reference capture source changed')
    spec = importlib.util.spec_from_file_location('reference_pipeline_original_observations', path)
    module = importlib.util.module_from_spec(spec)
    before = sys.path[:]
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = before
    return module


class Corpus:
    def __init__(self):
        self.oracle = load_original()
        self.index = original.authority()
        self.docs = {}
        directory = (ROOT / original.CORPUS).with_suffix('')
        require({p.name for p in directory.iterdir()} == {pin + '.json' for pin in self.index['documents']},
                'Reference document census differs')
        for pin, size in self.index['documents'].items():
            raw = (directory / (pin + '.json')).read_bytes()
            require(len(raw) == size and raw.endswith(b'\n') and sha(raw[:-1]) == pin,
                    'Reference complete document bytes differ')
            self.docs[pin] = json.loads(raw)
        # The separate archived counterpart validates historical Python source;
        # native replay must retain current installed bridge provenance instead.
        self.oracle.validate(self.index, self.docs, sources=False)
        self.events = self.index['events']
        self.taxonomy = classify(self.events)

    def metadata(self):
        return {'corpus': {'path': original.CORPUS, 'sha256': original.CORPUS_SHA,
                          'inventory_fingerprint': original.INVENTORY},
                'complete_original_coverage': self.index['coverage'], 'taxonomy': self.taxonomy,
                'scope': '18 existing reference methods; remaining full manager and export gates are separate'}


def classify(events):
    """Exhaustive, disjoint classification; no baseline event is discarded."""
    result = {name: [] for name in ('public_manager', 'initialization', 'workflow',
        'user_callback', 'host_override', 'authoring', 'native_internal')}
    for row in events:
        kind, parent = row['kind'], row['parent']
        if kind == 'manager.__init__': category = 'initialization'
        elif kind.startswith('manager.') and row['manager_parent'] is None: category = 'public_manager'
        elif kind.startswith('pipeline.'): category = 'workflow'
        elif kind in ('registration.wrapper', 'callback.forged', 'callback.producer'): category = 'user_callback'
        elif kind.startswith('override.'): category = 'host_override'
        elif kind.startswith('import.') and (parent is None or events[parent]['kind'].startswith('import.')):
            category = 'authoring'
        elif kind.startswith('producer.') and parent is None: category = 'authoring'
        else: category = 'native_internal'
        result[category].append(row['id'])
    equal(sorted(item for rows in result.values() for item in rows), list(range(len(events))),
          'Reference event taxonomy omitted or repeated an original observation')
    equal({name: len(rows) for name, rows in result.items()}, {'public_manager': 412, 'initialization': 27,
        'workflow': 41, 'user_callback': 8, 'host_override': 2, 'authoring': 12, 'native_internal': 1718},
        'Original reference behavior census changed')
    return result


def load_bodies(corpus, *, installed=True):
    import biocompiler
    package = Path(biocompiler.__file__).resolve().parent
    if installed:
        require(not package.is_relative_to(ROOT / 'src'), 'Reference campaign loaded source-tree product code')
    previous = sys.path[:]
    try:
        sys.path.extend((str(ROOT), str(ROOT / 'tests')))
        modules = [importlib.import_module(name) for name in TEST_MODULES]
    finally:
        sys.path[:] = previous
    cases, authority = [], []
    for name, cls_name, module in zip(TEST_MODULES, CLASSES, modules):
        path = 'tests/' + name + '.py'
        require(Path(module.__file__).resolve() == ROOT / path, 'Original reference test came from another module')
        require(sha((ROOT / path).read_bytes()) == corpus.index['source_files'][path], 'Original reference method source changed')
        cls = vars(module)[cls_name]
        selected = list(corpus.oracle.leaves(unittest.defaultTestLoader.loadTestsFromTestCase(cls)))
        require(len(selected) == 9 and all(type(test) is cls for test in selected), 'Original TestCase class or census differs')
        for test in selected:
            authority.append(source_function(getattr(cls, test._testMethodName), expected=corpus.index['source_files'][path]))
        cases.extend(selected)
    equal([test.id() for test in cases], corpus.index['test_ids'], 'Original reference TestCase identity/order changed')
    for name, module in tuple(sys.modules.items()):
        if name == 'biocompiler' or name.startswith('biocompiler.'):
            require(Path(module.__file__).resolve().is_relative_to(package), 'Mixed current product package origins')
    return modules, cases, authority


class FacadeSelection:
    """Replace only exact verified public aliases; leave real user hooks alone."""
    def __init__(self, corpus, construct, molecular):
        self.corpus, self.factories = corpus, {'construct': construct, 'molecular': molecular}
        self.aliases, self.calls, self.changes = [], [], []
        self.defaults = {}
        for kind in self.factories:
            module = importlib.import_module('biocompiler.compiler.' + kind)
            function = vars(module)['run_' + kind + '_pipeline']
            source_function(function, expected=corpus.index['source_files']['src/biocompiler/compiler/' + kind + '.py'])
            self.defaults[kind] = function

    def __enter__(self):
        for kind in self.factories:
            def invoke(request, registry, manifests, *, kind=kind):
                self.calls.append({'kind': kind, 'request': request, 'registry': registry, 'manifests': manifests})
                return self.factories[kind](request, registry, manifests)
            default = self.defaults[kind]
            for name, module in sorted(tuple(sys.modules.items())):
                if module is None or not (name == 'biocompiler' or name.startswith('biocompiler.')
                    or name in TEST_MODULES or name == 'examples.reference_construct'):
                    continue
                for slot, value in tuple(vars(module).items()):
                    if value is default:
                        self.aliases.append({'owner': name, 'slot': slot, 'kind': kind,
                            'source': source_function(default)})
                        self.changes.append((module, slot, default, invoke))
            require(any(module.__name__ == 'test_' + kind + '_pipeline' for module, _, _, fn in self.changes if fn is invoke),
                    'Original test public alias was not selected')
        for module, slot, previous, replacement in self.changes:
            require(vars(module)[slot] is previous, 'Public reference alias changed during selection')
            setattr(module, slot, replacement)
        return self

    def __exit__(self, *error):
        changed = []
        for module, slot, previous, replacement in reversed(self.changes):
            if vars(module).get(slot) is not replacement:
                changed.append(module.__name__ + '.' + slot)
            setattr(module, slot, previous)
        require(not changed, 'Selected reference alias changed during execution: ' + repr(changed))


def routed_source(kind, raw, *, archive=None):
    """Verify the only permitted change to each original public entry body.

    The callable itself remains original. Five source-bound statements dispatch
    before its old first statement; deleting them must recover every old byte.
    This is deliberately not an arbitrary line-offset or AST-only exemption.
    """
    require(kind in ('construct', 'molecular'), 'Unknown reference public route')
    if archive is None:
        index, blobs = original.source_archive()
        archive = blobs[index['files']['src/biocompiler/compiler/' + kind + '.py']['sha256']]
    name = 'run_' + kind + '_pipeline'
    module = ast.parse(archive)
    functions = [node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == name]
    require(len(functions) == 1 and len(functions[0].body) > 1 and
        isinstance(functions[0].body[0], ast.Expr) and isinstance(functions[0].body[0].value, ast.Constant)
        and type(functions[0].body[0].value.value) is str, 'Original reference route declaration differs')
    first = functions[0].body[1]
    offset = sum(len(line) for line in archive.splitlines(keepends=True)[:first.lineno - 1])
    prefix = ('    from sys import modules\n'
        '    _reference_backend = modules.get("biocompiler.reference_backend")\n'
        '    _reference_route = None if _reference_backend is None else _reference_backend.current()\n'
        '    if _reference_route is not None:\n'
        '        return _reference_route.' + kind + '(request, registry, manifests)\n').encode()
    require(raw == archive[:offset] + prefix + archive[offset:],
            'Reference public source differs beyond its exact five-line selection prefix')
    return {'path': 'src/biocompiler/compiler/' + kind + '.py',
        'original_sha256': sha(archive), 'current_sha256': sha(raw), 'offset': offset,
        'prefix': prefix.decode(), 'whole_original_restoration': True}


class ContextSelection:
    """Use the real explicit backend context; never replace a public alias."""
    def __init__(self, corpus, core, *, limits=None, manager_limits=None):
        self.corpus, self.core = corpus, core
        self.limits, self.manager_limits = limits, manager_limits
        self.aliases, self.sources, self.calls = [], [], []
        self.defaults = {}
        self.retained_aliases = []
        for kind in ('construct', 'molecular'):
            module = importlib.import_module('biocompiler.compiler.' + kind)
            function = vars(module)['run_' + kind + '_pipeline']
            source = source_function(function)
            proof = routed_source(kind, Path(source['path']).read_bytes())
            require(proof['original_sha256'] == corpus.index['source_files'][proof['path']],
                    'Reference route original source is outside the frozen cohort')
            self.sources.append(proof)
            self.defaults[kind] = function
        self.backend = importlib.import_module('biocompiler.reference_backend')
        context = self.backend.reference_core
        wrapped = getattr(context, '__wrapped__', None)
        require(type(context) is FunctionType and type(wrapped) is FunctionType and
            context.__globals__ is vars(contextlib) and
            context.__code__ is contextlib.contextmanager(lambda: None).__code__ and
            context.__closure__ is not None and len(context.__closure__) == 1 and
            context.__closure__[0].cell_contents is wrapped,
            'Reference selection context decorator differs')
        self.context_source = source_function(wrapped)
        require(wrapped.__module__ == 'biocompiler.reference_backend' and wrapped.__name__ == 'reference_core',
                'Reference selection context comes from another source function')
        self.scope = None
        self.selected = None

    def __enter__(self):
        require(self.backend.current() is None, 'Reference campaign inherited another native selection')
        for kind, default in self.defaults.items():
            for name, module in sorted(tuple(sys.modules.items())):
                if module is None or not (name == 'biocompiler' or name.startswith('biocompiler.')
                    or name in TEST_MODULES or name == 'examples.reference_construct'):
                    continue
                for slot, value in tuple(vars(module).items()):
                    if value is default:
                        self.aliases.append({'owner': name, 'slot': slot, 'kind': kind,
                            'source': source_function(default)})
                        self.retained_aliases.append((module, slot, default))
            require(any(row['owner'] == 'test_' + kind + '_pipeline' and row['kind'] == kind
                        for row in self.aliases), 'Original public TestCase alias is absent')
        self.scope = self.backend.reference_core(self.core, limits=self.limits, manager_limits=self.manager_limits)
        self.selected = self.scope.__enter__()
        require(self.backend.current() is self.selected and self.selected.core is self.core,
                'Reference context did not retain the supplied actual Core client')
        return self

    def __exit__(self, *error):
        require(self.scope is not None, 'Reference selection was not entered')
        try:
            require(self.backend.current() is self.selected, 'Reference selected backend changed during replay')
            for module, slot, original_function in self.retained_aliases:
                require(vars(module).get(slot) is original_function,
                        'Reference public alias was replaced during selected replay')
        finally:
            self.scope.__exit__(*error)
        require(self.backend.current() is None, 'Reference context did not restore its prior selection')


class ObservationGraph:
    """Stored fields and physical references only, with explicit native nodes."""
    def __init__(self, oracle, observer):
        self.original = oracle.Graph(oracle.Store(), object)
        self.store, self.observer = self.original.store, observer
        self.sources = {}

    def identity(self, value):
        return self.original.identity(value)

    @property
    def functions(self):
        return self.original.functions

    def source(self, function):
        previous = self.sources.get(id(function))
        if previous is None:
            value = source_function(function)
            self.sources[id(function)] = (function, function.__code__, function.__globals__, value)
            return value
        retained, code, namespace, value = previous
        require(retained is function and function.__code__ is code and function.__globals__ is namespace,
                'Observed callback source changed during graph capture')
        return value

    def snapshot(self, roots):
        from biocompiler.core_pipeline_manager import _NativeProvider
        from biocompiler.core_reference_manager import ReferenceCorePassManager
        nodes = {}
        def encode(value):
            if value is None or type(value) in (bool, int, str, float):
                return {'scalar': type(value).__name__, 'value': value}
            if isinstance(value, Enum): return {'enum': self.original_type(value), 'value': encode(value.value)}
            if isinstance(value, type): return {'class': self.original_type(value)}
            if value is DEFAULT: return {'sentinel': 'unittest.mock.DEFAULT'}
            identity = self.identity(value)
            if identity in nodes: return {'ref': identity}
            nodes[identity] = None
            if type(value) is ReferenceCorePassManager:
                node = {'kind': 'native-manager', 'class': self.original_type(value),
                        'process': self.observer.manager_number(value)}
            elif type(value) is _NativeProvider:
                owner, token = value._manager, value._identity
                require(owner._native_providers.get(token) is value, 'Unowned reference native provider')
                role = owner._native_provider_roles[token]
                require(role in ROLE_SOURCES, 'Unknown reference provider role')
                node = {'kind': 'native-provider', 'role': role, 'token': token, 'manager': encode(owner)}
            elif type(value) in (dict, MappingProxyType):
                node = {'kind': 'mapping', 'class': type(value).__name__,
                        'items': [[encode(key), encode(item)] for key, item in value.items()]}
            elif type(value) in (tuple, list):
                node = {'kind': 'sequence', 'class': type(value).__name__, 'items': [encode(item) for item in value]}
            elif type(value) in (set, frozenset):
                require(all(type(item) is str for item in value), 'Unreviewed observed set')
                node = {'kind': 'set', 'class': type(value).__name__, 'items': sorted(value)}
            elif type(value) is FunctionType:
                node = {'kind': 'provider', 'source': self.source(value), 'defaults': encode(value.__defaults__),
                    'kwdefaults': encode(value.__kwdefaults__), 'closure': [[key, encode(cell.cell_contents)]
                        for key, cell in zip(value.__code__.co_freevars, value.__closure__ or ())]}
            elif isinstance(value, Mock):
                state = vars(value)
                node = {'kind': 'mock', 'class': 'unittest.mock.MagicMock' if 'MagicMock' in self.original_type(value) else self.original_type(value),
                    'return_value': encode(state['_mock_return_value']), 'side_effect': encode(state['_mock_side_effect']),
                    'call_count': state['_mock_call_count'], 'calls': [[[encode(item) for item in call.args],
                        [[key, encode(item)] for key, item in call.kwargs.items()]] for call in state.get('_mock_call_args_list', ())]}
            elif isinstance(value, BaseException):
                node = {'kind': 'exception', 'class': self.original_type(value), 'args': encode(value.args),
                    'fields': [[key, encode(item)] for key, item in vars(value).items()],
                    'cause': encode(value.__cause__), 'context': encode(value.__context__), 'suppress_context': value.__suppress_context__}
            else:
                require(type(value) in self.original.safe, 'Unreviewed observed reference graph type: ' + self.original_type(value))
                node = {'kind': 'dataclass', 'class': self.original_type(value),
                    'fields': [[field.name, encode(object.__getattribute__(value, field.name))] for field in fields(value)],
                    'instance_fields': list(vars(value)), 'class_schema': vars(type(value)).get('schema_version')
                    if type(vars(type(value)).get('schema_version')) is str and 'schema_version' not in vars(value) else None}
            nodes[identity] = self.store.add(node)
            return {'ref': identity}
        value = [[name, encode(item)] for name, item in roots]
        return self.store.add({'kind': 'graph', 'roots': value, 'nodes': nodes})

    @staticmethod
    def original_type(value):
        cls = value if isinstance(value, type) else type(value)
        return cls.__module__ + '.' + cls.__qualname__


def observed_inspection(owner):
    inspection = owner.inspect_ordered_references()
    return owner._inspection_state(inspection)


class Observer:
    """Observe actual public calls and host objects without replacing methods."""
    def __init__(self, corpus):
        from biocompiler.core_pipeline_manager import CorePassManager, _NativeProvider
        from biocompiler.core_reference_manager import ReferenceCorePassManager
        from biocompiler.core_reference_host import ReferenceHost, HostValue, NativeDefault
        from biocompiler.compiler import construct, molecular
        from biocompiler.ir.construct import ConstructRequest, ConstructCandidate
        from biocompiler.ir.molecular import MolecularArtifact
        from biocompiler.synthesis.construct import generate_construct
        from biocompiler.backends.reference import emit_reference_sequence
        self.corpus, self.context = corpus, None
        self.graph = ObservationGraph(corpus.oracle, self)
        self.rows, self.stack, self.frames, self.managers = [], [], {}, []
        self.states, self.initializations, self.raw_traces = {}, [], []
        self.busy, self.error, self.clock = False, None, 0
        self.methods = {getattr(CorePassManager, name).__code__: name for name in PUBLIC_METHODS}
        self.initializer = ReferenceCorePassManager._initialize.__func__.__code__
        self.complete_construct = ReferenceCorePassManager._complete_construct.__code__
        self.complete_molecular = {ReferenceCorePassManager.complete_molecular.__code__,
            ReferenceCorePassManager.complete_molecular_public.__code__}
        self.process_prepare = ReferenceCorePassManager._reference_prepare.__code__
        self.process_frames = {}
        self.guarded_observation = None
        self.native_provider = _NativeProvider.__call__.__code__
        self.host_calls = {ReferenceHost.generate.__code__: 'host.generate', ReferenceHost.emit.__code__: 'host.emit',
                           ReferenceHost.proposal.__code__: 'host.proposal'}
        self.host_value, self.native_default = HostValue, NativeDefault
        self.trace_objects, self.trace_ids, self.instructions = [], {}, {}
        self.construct, self.molecular = construct, molecular
        self.pipeline_calls = {construct.run_construct_pipeline.__code__: ('pipeline.construct', construct.run_construct_pipeline),
            molecular.run_molecular_pipeline.__code__: ('pipeline.molecular', molecular.run_molecular_pipeline)}
        self.authoring_calls = {generate_construct.__code__: ('producer.generate_construct', generate_construct),
            emit_reference_sequence.__code__: ('producer.emit_reference_sequence', emit_reference_sequence)}
        self.imports = {}
        for cls in (ConstructRequest, ConstructCandidate, MolecularArtifact):
            for name in ('from_dict', 'from_json'):
                fn = getattr(cls, name).__func__
                self.imports.setdefault(fn.__code__, {})[cls] = name
        self.entry_functions = {}

    def manager_number(self, value):
        for index, item in enumerate(self.managers):
            if item is value: return index
        self.managers.append(value)
        return len(self.managers) - 1

    def state(self, value, *, force=False):
        number, session = self.manager_number(value), value.session
        previous = self.states.get(number)
        if not force and previous is not None and previous['end_frame'] == len(session.traffic):
            return {**previous, 'reused': True}
        start = len(session.traffic)
        # CPython suspends profiling while an observation trace executes.
        # call_tracing explicitly re-enters the real profiler for the complete
        # structural inspection lane; busy suppresses only this observer's
        # recursive snapshots, never the independent execution guard.
        state = (self.guarded_observation(observed_inspection, (value,))
            if self.guarded_observation is not None else sys.call_tracing(observed_inspection, (value,)))
        response = session.last_response
        require(response is not None and response.operation == 'inspect-ordered-references',
                'Observed state lacks its actual compact inspection')
        result = {'sequence': response.sequence, 'start_frame': start, 'end_frame': len(session.traffic),
                  'graph': self.graph.snapshot([('state', state)]), 'reused': False}
        self.states[number] = result
        return result

    def raw_identity(self, value):
        if value is None: return None
        if id(value) not in self.trace_ids:
            self.trace_ids[id(value)] = 'trace/' + str(len(self.trace_objects))
            self.trace_objects.append(value)
        return self.trace_ids[id(value)]

    def describe(self, frame):
        local, code = frame.f_locals, frame.f_code
        if code in self.pipeline_calls:
            kind, function = self.pipeline_calls[code]
            source_function(function)
            self.entry_functions[id(frame)] = function
            return kind, None
        if code in self.authoring_calls:
            require(not self.stack, 'Legacy reference producer executed inside the selected workflow')
            kind, function = self.authoring_calls[code]
            self.entry_functions[id(frame)] = function
            return kind, None
        if code in self.methods:
            name = self.methods[code]
            return 'manager.' + ('register' if name == '_native_register' else name), local['self']
        if code is self.initializer: return 'native.initialize', None
        if code is self.complete_construct: return 'native.construct-phase', local['self']
        if code in self.complete_molecular: return 'native.molecular-phase', local['self']
        if code in self.host_calls: return self.host_calls[code], None
        if code is self.native_provider: return 'native.provider', local['self']._manager
        if code in self.imports and local.get('cls') in self.imports[code]:
            require(not any(row['kind'].startswith(('manager.', 'native.', 'host.')) for row in self.stack),
                    'Legacy reference parser executed inside the native workflow')
            return 'import.' + local['cls'].__name__ + '.' + self.imports[code][local['cls']], None
        caller = frame.f_back
        if caller is not None and caller.f_code in self.host_calls and code.co_name == '__call__' and isinstance(local.get('self'), Mock):
            name = 'generate_construct' if caller.f_code is next(key for key, value in self.host_calls.items() if value == 'host.generate') else 'emit_reference_sequence'
            function = vars(self.construct if name == 'generate_construct' else self.molecular)[name]
            require(function is local['self'], 'Reference override invocation lost its actual module global')
            self.entry_functions[id(frame)] = function
            return 'override.' + name, None
        if Path(code.co_filename).resolve() in (ROOT / 'tests/test_construct_pipeline.py', ROOT / 'tests/test_molecular_pipeline.py'):
            if code.co_name == 'register':
                from biocompiler.compiler.pipeline import PassManager
                function = PassManager.register
                require(type(function) is FunctionType and function.__code__ is code,
                        'Public registration wrapper source identity changed')
                self.entry_functions[id(frame)] = function
                return 'registration.wrapper', local['manager']
            if code.co_name in ('forged', 'producer') and 'context' in local:
                function = self.corpus.oracle.Observer.callable(self, frame)
                require(function is not None, 'Reference proposal callback has no retained callable identity')
                self.entry_functions[id(frame)] = function
                return 'callback.' + code.co_name, None
        return None

    def roots(self, frame, kind):
        local = frame.f_locals
        if kind.startswith(('manager.', 'pipeline.', 'registration.', 'callback.', 'override.', 'import.', 'producer.')):
            roots = [('argument:' + key, value) for key, value in local.items() if key not in frame.f_code.co_freevars]
            function = self.entry_functions.get(id(frame))
            if function is not None:
                roots.append(('callable', function))
            if kind.startswith('pipeline.'):
                roots.extend((('global:generate_construct', self.construct.generate_construct),
                              ('global:emit_reference_sequence', self.molecular.emit_reference_sequence)))
            return roots
        if kind == 'native.initialize':
            return [(key, local[key]) for key in ('request', 'registry', 'manifests')]
        if kind in ('native.construct-phase', 'native.molecular-phase'):
            owner = local['self']
            if kind == 'native.molecular-phase' and 'snapshot' in local:
                # Actual public call arguments own this attempt; later attempts
                # must never change the observed authority of this invocation.
                return [(name, local[name]) for name in ('request', 'registry')] + [('manifests', local['snapshot'])]
            host = owner._reference_host
            return [('request', host.request), ('registry', host.registry),
                ('manifests', host.construct_manifests if kind == 'native.construct-phase' else host.molecular_manifests)]
        if kind.startswith('host.'):
            host = local['self']
            names = ('bound_request',) if kind == 'host.generate' else ('bound_construct',) if kind == 'host.emit' else ('source_links',)
            # These names are fixed by the reviewed host source, not inferred
            # from a result document or a saved expected argument.
            roots = [(key, local[key]) for key in names]
            if kind == 'host.proposal':
                roots.append(('output', local['value'].output))
            return roots + [('request', host.request), ('registry', host.registry),
                ('construct_manifests', host.construct_manifests), ('molecular_manifests', host.molecular_manifests)]
        if kind == 'native.provider': return [('provider', local['self']), ('context', local['context'])]
        return [('argument:' + key, value) for key, value in local.items() if key not in frame.f_code.co_freevars]

    def traceback(self, row, error, tb):
        frames = []
        while tb is not None:
            code = tb.tb_frame.f_code
            path = Path(code.co_filename)
            frames.append({'node': self.raw_identity(tb), 'frame': self.raw_identity(tb.tb_frame),
                'next': self.raw_identity(tb.tb_next), 'filename': code.co_filename, 'function': code.co_qualname,
                'first_line': code.co_firstlineno, 'line': tb.tb_lineno,
                'source_sha256': sha(path.read_bytes()) if path.is_file() else None})
            tb = tb.tb_next
        self.raw_traces.append({'event': row['id'], 'exception': self.graph.identity(error), 'frames': frames})

    def transport(self, frame):
        cursor = frame.f_back
        while cursor is not None:
            value = cursor.f_locals.get('self')
            owners = [(index, owner) for index, owner in enumerate(self.managers) if owner is value]
            if owners:
                index, owner = owners[0]
                session = owner.session
                if session._handlers and session._invocations:
                    return {'manager': index, 'sequence': session._handlers[-1].sequence,
                        'invocation': session._invocations[-1], 'start_frame': len(session.traffic)}
            cursor = cursor.f_back
        return None

    def trace(self, frame, event, arg):
        if self.busy or self.error is not None: return None
        self.busy = True
        try:
            if frame.f_code is self.process_prepare:
                if event == 'call':
                    self.process_frames[id(frame)] = frame
                elif event == 'return':
                    require(self.process_frames.pop(id(frame), None) is frame, 'Reference process creation frame changed')
                    owner = frame.f_locals['self']
                    if hasattr(owner, '_session'):
                        self.manager_number(owner)
                return self.trace
            if event == 'call':
                spec = self.describe(frame)
                if spec is None: return None
                kind, owner = spec
                roots = self.roots(frame, kind)
                row = {'id': len(self.rows), 'entry': self.clock, 'test': self.context, 'kind': kind,
                    'parent': self.stack[-1]['id'] if self.stack else None,
                    'manager_parent': next((item['id'] for item in reversed(self.stack)
                                            if item['kind'].startswith('manager.')), None),
                    'manager': None if owner is None else self.manager_number(owner),
                    'source': {'file': frame.f_code.co_filename, 'qualname': frame.f_code.co_qualname,
                               'line': frame.f_code.co_firstlineno}, 'before': self.graph.snapshot(roots)}
                transport = self.transport(frame)
                if transport is not None: row['transport'] = transport
                if owner is not None:
                    row['state_before'] = self.state(owner)
                    row['start_frame'] = len(owner.session.traffic)
                self.clock += 1
                self.rows.append(row); self.stack.append(row)
                self.frames[id(frame)] = (frame, row, roots, owner, None, None)
                return self.trace
            if id(frame) not in self.frames: return None
            retained, row, roots, owner, error, tb = self.frames[id(frame)]
            require(retained is frame, 'Reference observation frame identity collision')
            if event == 'exception':
                self.frames[id(frame)] = (frame, row, roots, owner, arg[1], arg[2])
            elif event == 'return':
                instructions = self.instructions.setdefault(frame.f_code,
                    {item.offset: item.opname for item in dis.get_instructions(frame.f_code)})
                returned = instructions.get(frame.f_lasti, '').startswith('RETURN_')
                require(returned or error is not None, 'Reference unwind lost actual exception')
                value = arg
                if returned and row['kind'] == 'native.initialize':
                    owner = value
                    row['manager'] = self.manager_number(owner)
                    self.initializations.append(row['id'])
                if returned and row['kind'].startswith('pipeline.'):
                    owner = value.manager
                    row['manager'] = self.manager_number(owner)
                if returned and isinstance(value, self.host_value):
                    row['route'] = 'host'; value = value.output
                elif returned and isinstance(value, self.native_default):
                    row['route'] = 'native'; value = value.value
                row['exit'] = self.clock; self.clock += 1
                row['outcome'] = 'return' if returned else 'raise'
                row['after'] = self.graph.snapshot([*roots, ('return', value) if returned else ('exception', error)])
                if 'transport' in row:
                    row['transport']['end_frame'] = len(self.managers[row['transport']['manager']].session.traffic)
                if owner is not None:
                    row['end_frame'] = len(owner.session.traffic)
                    response = owner.session.last_response
                    row['response_sequence'] = None if response is None else response.sequence
                    row['state_after'] = self.state(owner, force=True)
                if not returned: self.traceback(row, error, tb)
                require(self.stack.pop() is row, 'Reference native observation nesting changed')
                del self.frames[id(frame)]
                self.entry_functions.pop(id(frame), None)
            return self.trace
        except BaseException as error:
            self.error = error
            raise
        finally:
            self.busy = False


class GraphCorrespondence:
    """Compare complete public object graphs with an explicit provider seam.

Native callable closure environments are not Python function objects. Their
closed source-role correspondence is retained separately; actual proxy identity
must nevertheless remain bijective across every public graph and manager slot.
    """
    def __init__(self, expected_documents, actual_documents):
        self.expected, self.actual = expected_documents, actual_documents
        self.forward, self.reverse, self.provider_correspondence = {}, {}, {}

    def bind(self, left, right):
        require(left not in self.forward or self.forward[left] == right,
                'Original public object identity changed')
        require(right not in self.reverse or self.reverse[right] == left,
                'Distinct original public objects were coalesced')
        self.forward[left], self.reverse[right] = right, left

    def compare(self, left_graph, right_graph, *, roots=None):
        left, right = self.expected[left_graph], self.actual[right_graph]
        lroots, rroots = dict(left['roots']), dict(right['roots'])
        names = list(lroots) if roots is None else roots
        require(all(name in lroots and name in rroots for name in names), 'Public observation root omitted')
        visited = set()
        for name in names:
            self.value(lroots[name], rroots[name], left, right, visited, strict=True)

    def value(self, left, right, lg, rg, visited, *, strict):
        if type(left) is not dict or set(left) != {'ref'}:
            equal(right, left, 'Public scalar, enum or class changed')
            return
        require(type(right) is dict and set(right) == {'ref'}, 'Public object became a scalar')
        lid, rid = left['ref'], right['ref']
        require(lid in lg['nodes'] and rid in rg['nodes'], 'Public graph has dangling identity')
        ln, rn = self.expected[lg['nodes'][lid]], self.actual[rg['nodes'][rid]]
        # Stored records and actual callable/manager authority stay physical
        # even inside detached historical inspection views.
        physical = strict or ln['kind'] in ('manager', 'provider', 'mock') or (
            ln['kind'] == 'dataclass' and ln['class'] == 'biocompiler.compiler.pipeline.StageRecord')
        if physical: self.bind(lid, rid)
        key = (lid, rid, physical)
        if key in visited: return
        visited.add(key)
        if ln['kind'] == 'manager':
            require(rn['kind'] == 'native-manager', 'Public manager lost native ownership')
            return
        if rn['kind'] == 'native-provider':
            require(ln['kind'] == 'provider' and rn['role'] in ROLE_SOURCES,
                    'Native provider has no original callable correspondence')
            source = ln['source']
            equal((source['module'], source['qualname']), ROLE_SOURCES[rn['role']],
                  'Native provider role differs from its original callable slot')
            witness = {'original': lid, 'actual': rid, 'role': rn['role'], 'token': rn['token'],
                       'source': source, 'scope': 'native closure counterpart; original environment retained in baseline'}
            previous = self.provider_correspondence.get(lid)
            require(previous is None or previous == witness, 'Native callable origin changed')
            self.provider_correspondence[lid] = witness
            return
        require(ln['kind'] == rn['kind'], 'Public object kind changed')
        kind = ln['kind']
        def pair(a, b): self.value(a, b, lg, rg, visited, strict=physical)
        if kind in ('mapping', 'sequence', 'set'):
            equal(rn['class'], ln['class'], 'Public container type changed')
            require(len(ln['items']) == len(rn['items']), 'Public container length changed')
            if kind == 'set': equal(rn['items'], ln['items'], 'Public set changed')
            elif kind == 'sequence':
                for a, b in zip(ln['items'], rn['items']): pair(a, b)
            else:
                for (ka, va), (kb, vb) in zip(ln['items'], rn['items']): pair(ka, kb); pair(va, vb)
        elif kind == 'dataclass':
            for name in ('class', 'instance_fields', 'class_schema'):
                equal(rn[name], ln[name], 'Public raw dataclass structure changed')
            equal([name for name, _ in rn['fields']], [name for name, _ in ln['fields']], 'Public dataclass field order changed')
            for (_, a), (_, b) in zip(ln['fields'], rn['fields']): pair(a, b)
        elif kind == 'provider':
            for name in ('module', 'qualname', 'line', 'file', 'freevars'):
                equal(rn['source'][name], ln['source'][name], 'Actual host callback source changed')
            pair(ln['defaults'], rn['defaults']); pair(ln['kwdefaults'], rn['kwdefaults'])
            equal([name for name, _ in rn['closure']], [name for name, _ in ln['closure']], 'Actual callback capture order changed')
            for (_, a), (_, b) in zip(ln['closure'], rn['closure']): pair(a, b)
        elif kind == 'exception':
            equal(rn['class'], ln['class'], 'Actual exception type changed')
            equal(rn['suppress_context'], ln['suppress_context'], 'Actual exception chaining changed')
            for name in ('args', 'cause', 'context'): pair(ln[name], rn[name])
            equal([name for name, _ in rn['fields']], [name for name, _ in ln['fields']], 'Exception field order changed')
            for (_, a), (_, b) in zip(ln['fields'], rn['fields']): pair(a, b)
        elif kind == 'mock':
            for name in ('class', 'call_count'): equal(rn[name], ln[name], 'Actual replacement invocation count changed')
            pair(ln['return_value'], rn['return_value']); pair(ln['side_effect'], rn['side_effect'])
            require(len(ln['calls']) == len(rn['calls']), 'Actual replacement call census changed')
            for (la, lk), (ra, rk) in zip(ln['calls'], rn['calls']):
                require(len(la) == len(ra), 'Actual replacement positional argument count changed')
                for a, b in zip(la, ra): pair(a, b)
                equal([name for name, _ in rk], [name for name, _ in lk], 'Actual replacement keyword order changed')
                for (_, a), (_, b) in zip(lk, rk): pair(a, b)
        else: raise AssertionError('Unreviewed public graph correspondence: ' + kind)

    def state(self, original_graph, original_manager, current_graph):
        left, right = self.expected[original_graph], self.actual[current_graph]
        original_node = self.expected[left['nodes'][original_manager]]
        require(original_node['kind'] == 'manager', 'Expected before/after manager state missing')
        current_ref = dict(right['roots'])['state']
        current = self.actual[right['nodes'][current_ref['ref']]]
        require(current['kind'] == 'mapping' and current['class'] == 'dict', 'Actual inspection lacks its ordered structural state')
        actual_fields = [(key['value'], value) for key, value in current['items']]
        equal([name for name, _ in actual_fields], [name for name, _ in original_node['fields']],
              'Complete native historical field order differs')
        visited = set()
        for (name, old), (_, new) in zip(original_node['fields'], actual_fields):
            self.value(old, new, left, right, visited, strict=name == '_target')


def validate_source_callpoints(corpus, rows, graphs):
    """Bind actual host arguments at every original default/override callpoint.

    A native-default marker is not the original producer's return. Only the
    complete incoming arguments are compared here; returned native proposals
    and public results retain their independent observation/frame checks.
    """
    names = {'generate_construct': ('host.generate', ('bound_request',)),
        'emit_reference_sequence': ('host.emit', ('request', 'bound_construct', 'registry', 'molecular_manifests'))}
    originals = [row for row in corpus.events if row['parent'] is not None and
        row['kind'] in {prefix + name for name in names for prefix in ('producer.', 'override.')}]
    actual = [row for row in rows if row['kind'] in {value[0] for value in names.values()}]
    equal(Counter(row['kind'].split('.', 1)[1] for row in originals),
        {'generate_construct': 23, 'emit_reference_sequence': 13}, 'Original source callpoint census changed')
    equal([(row['test'], row['kind'], row['outcome'], row.get('route')) for row in actual],
        [(row['test'], names[row['kind'].split('.', 1)[1]][0], row['outcome'],
          'host' if row['kind'].startswith('override.') else 'native') for row in originals],
        'Actual source callpoint order, outcome or default/override route differs')
    checked = []
    for old, new in zip(originals, actual):
        name = old['kind'].split('.', 1)[1]
        target_names = names[name][1]
        source_names = ('argument:request',) if name == 'generate_construct' else (
            'argument:request', 'argument:construct', 'argument:registry', 'argument:manifests')
        for phase in ('before', 'after'):
            left, right = graphs.expected[old[phase]], graphs.actual[new[phase]]
            lroots, rroots = dict(left['roots']), dict(right['roots'])
            if old['kind'].startswith('override.'):
                args_ref = lroots['argument:args']
                require(type(args_ref) is dict and set(args_ref) == {'ref'}, 'Original override arguments lost tuple identity')
                args = graphs.expected[left['nodes'][args_ref['ref']]]
                require(args['kind'] == 'sequence' and args['class'] == 'tuple' and
                    len(args['items']) == len(target_names), 'Original override argument shape changed')
                values = args['items']
            else:
                values = [lroots[key] for key in source_names]
            require(all(key in rroots for key in target_names), 'Actual source callpoint argument omitted')
            visited = set()
            for value, key in zip(values, target_names):
                graphs.value(value, rroots[key], left, right, visited, strict=True)
        checked.append({'original': old['id'], 'actual': new['id'], 'route': new['route'],
            'scope': 'actual full input graph and physical origin at original callpoint; native return checked separately'})
    return checked


def validate_public_observations(corpus, rows, documents):
    expected = [corpus.events[index] for index in corpus.taxonomy['public_manager']]
    actual = [row for row in rows if row['kind'].startswith('manager.')]
    equal([(row['test'], row['kind'], row['outcome']) for row in actual],
          [(row['test'], row['kind'], row['outcome']) for row in expected],
          'Complete original public manager operation/outcome order differs')
    graphs = GraphCorrespondence(corpus.docs, documents)
    initialized = [row for row in rows if row['kind'] == 'native.initialize']
    originals = [corpus.events[index] for index in corpus.taxonomy['initialization']]
    equal([(row['test'], row['outcome']) for row in initialized],
        [(row['test'], row['outcome']) for row in originals], 'Original initialization ownership/outcome census differs')
    initialization_links = []
    for old, new in zip(originals, initialized):
        left, right = corpus.docs[old['after']], documents[new['after']]
        before = dict(left['roots'])['argument:self']
        returned = dict(right['roots'])['return']
        graphs.value(before, returned, left, right, set(), strict=True)
        graphs.state(old['after'], old['manager'], new['state_after']['graph'])
        initialization_links.append({'original': old['id'], 'actual': new['id'], 'manager': new['manager']})
    links = []
    for old, new in zip(expected, actual):
        before = corpus.docs[old['before']]
        roots = [name for name, _ in before['roots'] if name.startswith('argument:')]
        graphs.compare(old['before'], new['before'], roots=roots)
        graphs.compare(old['after'], new['after'], roots=roots + ['return' if old['outcome'] == 'return' else 'exception'])
        graphs.state(old['before'], old['manager'], new['state_before']['graph'])
        graphs.state(old['after'], old['manager'], new['state_after']['graph'])
        links.append({'original': old['id'], 'actual': new['id'], 'manager': new['manager']})
    boundaries = {}
    for category in ('workflow', 'user_callback', 'host_override', 'authoring'):
        originals = [corpus.events[index] for index in corpus.taxonomy[category]]
        names = {item['kind'] for item in originals}
        selected = [item for item in rows if item['kind'] in names]
        equal([(item['test'], item['kind'], item['outcome']) for item in selected],
            [(item['test'], item['kind'], item['outcome']) for item in originals],
            'Complete original ' + category + ' order/outcome census differs')
        checked = []
        for old, new in zip(originals, selected):
            before = corpus.docs[old['before']]
            roots = [name for name, _ in before['roots']]
            graphs.compare(old['before'], new['before'], roots=roots)
            graphs.compare(old['after'], new['after'], roots=roots + [
                'return' if old['outcome'] == 'return' else 'exception'])
            checked.append({'original': old['id'], 'actual': new['id']})
        boundaries[category] = checked
    source_callpoints = validate_source_callpoints(corpus, rows, graphs)
    return {'public_operations': links, 'initializations': initialization_links, 'boundaries': boundaries,
            'source_callpoints': source_callpoints,
            'provider_correspondence': list(graphs.provider_correspondence.values()),
            'physical_aliases': sorted(graphs.forward.items())}


def run_bodies(corpus, *, core=None, factories=None, observer=None, installed=True,
               limits=None, manager_limits=None):
    modules, cases, authority = load_bodies(corpus, installed=installed)
    # The original Results receives genuine original TestCase instances and
    # forwards every failure/error/skip/subtest, with all assertions unchanged.
    result = corpus.oracle.Results(observer)
    require((core is None) != (factories is None), 'Select exactly one explicit reference replay route')
    selected = (ContextSelection(corpus, core, limits=limits, manager_limits=manager_limits)
                if core is not None else FacadeSelection(corpus, *factories))
    old_trace = sys.gettrace()
    require(old_trace is None or observer is None, 'Reference runtime requires an unoccupied observation trace')
    with selected:
        try:
            if observer is not None: sys.settrace(observer.trace)
            unittest.TestSuite(cases).run(result)
            if observer is not None:
                require(sys.gettrace() == observer.trace and observer.error is None and not observer.stack,
                        'Reference live observation was replaced or incomplete')
        finally:
            sys.settrace(old_trace)
    require(result.rows == corpus.index['observed_results'],
            'Unchanged original reference test outcomes differ: ' + repr(result.errors + result.failures))
    require(result.wasSuccessful() and result.testsRun == 18 and not result.skipped,
            'Unchanged original reference assertions failed')
    return {'results': result.rows, 'body_authority': authority, 'aliases': selected.aliases,
            'mode': 'public_context' if core is not None else 'explicit_facade',
            'route_sources': selected.sources if isinstance(selected, ContextSelection) else [],
            'selected_calls': [row['kind'] for row in selected.calls]}


# Runtime observation deliberately precedes any oracle comparison. It retains
# actual selected processes even when an unchanged assertion or callback fails.
def run_observed(core, corpus, receipt, *, installed=True, guard=None):
    from biocompiler.core_client import CoreProtocolError
    observer = Observer(corpus)
    result = None
    failed = None
    execution = None
    receipt['processes'] = []
    try:
        with (contextlib.nullcontext() if guard is None else guard(observer)) as execution:
            result = run_bodies(corpus, core=core, observer=observer, installed=installed)
    except BaseException as error:
        failed = error
    finally:
        # Closing happens outside the observation trace: it is transport cleanup,
        # not an original user operation. Every close frame remains in receipts.
        for number, owner in enumerate(observer.managers):
            session = owner.session
            row = {'manager': number, 'pid': session.pid,
                'executable_sha256': session.executable_sha256, 'frames': []}
            receipt['processes'].append(row)
            try:
                owner.close()
                before = len(session.traffic)
                try:
                    owner.get('request')
                except CoreProtocolError as error:
                    row['after_close'] = {'type': type(error).__name__, 'message': str(error),
                        'traffic_unchanged': len(session.traffic) == before, 'pid_unchanged': session.pid == row['pid']}
                else:
                    raise AssertionError('Closed reference manager resumed')
            except BaseException as error:
                if failed is None: failed = error
            finally:
                row.update(returncode=session.returncode, closed=session.closed, invalidated=session.invalidated,
                    stderr=manager.artifact(receipt, canonical({'hex': session.stderr_bytes.hex()})),
                    frames=[{'direction': entry.direction, 'index': entry.index,
                             'frame': manager.artifact(receipt, entry.frame)} for entry in session.traffic])
        observation = {
            'events': observer.rows, 'initializations': observer.initializations,
            'raw_tracebacks': observer.raw_traces,
            'documents': sorted(manager.artifact(receipt, canonical(value)) for value in observer.graph.store.docs.values()),
            'physical_objects': len(observer.graph.original.values), 'result': result}
        receipt['observation'] = manager.artifact(receipt, canonical(observation))
        receipt['observation_sources'] = manager.artifact(receipt, canonical(capture_observation_sources(
            observation, observer.graph.store.docs, receipt)))
    if failed is not None: raise failed
    require(execution is not None, 'Reference native execution guard is mandatory')
    receipt['guard'] = manager.artifact(receipt, canonical(execution.evidence()))
    require(len(observer.managers) == 27 and len(observer.initializations) == 27,
            'Reference unchanged methods did not retain all27actual manager processes')
    return observer


def validate_processes(receipt, artifacts, *, executable_sha256):
    """Validate exact raw native process traffic before reconstructing objects."""
    rows = receipt.get('processes')
    require(type(rows) is list and len(rows) == 27, 'Reference process census differs')
    channel, application = manager.declarations()
    sessions, pids, details, tapes = set(), set(), [], []
    for number, row in enumerate(rows):
        require(type(row) is dict and set(row) == {'manager', 'pid', 'executable_sha256', 'frames', 'after_close',
            'returncode', 'closed', 'invalidated', 'stderr'} and row['manager'] == number,
            'Reference process receipt fields/order differ')
        require(type(row['pid']) is int and row['pid'] > 0 and row['pid'] not in pids,
                'Reference manager process is missing or repeated')
        pids.add(row['pid'])
        require(row['returncode'] == 0 and type(row['returncode']) is int and row['closed'] is True
            and row['invalidated'] is False and row['executable_sha256'] == executable_sha256,
            'Reference real native manager did not finish its selected executable')
        equal(artifacts.json(row['stderr']), {'hex': ''}, 'Reference native process wrote stderr')
        equal(row['after_close'], {'type': 'CoreProtocolError', 'message': 'Callback session is closed; it cannot reconnect',
            'traffic_unchanged': True, 'pid_unchanged': True}, 'Reference closed manager resumed or changed its error')
        decoded = {}
        manager.validate_frames(row['frames'], artifacts, channel, application,
            sessions=sessions, details=decoded, provider_calls=False, initializer='initialize-reference')
        details.append(decoded)
        tapes.append([(frame['direction'], artifacts.raw(frame['frame'])) for frame in row['frames']])
    return details, tapes


def checked_documents(value):
    require(type(value) is dict and value and len(value) <= 100_000, 'Reference observed document census differs')
    total = 0
    for identity, document in value.items():
        encoded = canonical(document)
        require(type(identity) is str and sha(encoded) == identity, 'Reference observed full document hash differs')
        total += len(encoded)
        require(total <= 256 * 1024 * 1024, 'Reference observed full documents exceed their bound')
    return value


def observed_data(receipt, artifacts):
    actual = artifacts.json(receipt['observation'], maximum=64 * 1024 * 1024)
    require(type(actual) is dict and set(actual) == {'events', 'initializations', 'raw_tracebacks', 'documents',
        'physical_objects', 'result'}, 'Reference complete observation fields differ')
    names = actual['documents']
    require(type(names) is list and names == sorted(set(names)) and len(names) <= 100_000,
            'Reference complete document index differs')
    actual['documents'] = checked_documents({name: artifacts.json(name, maximum=64 * 1024 * 1024) for name in names})
    require(type(actual['physical_objects']) is int and actual['physical_objects'] > 0,
            'Reference physical object census is absent')
    return actual


def observation_paths(observation, documents):
    paths = set()
    for document in documents.values():
        if document.get('kind') == 'provider':
            paths.add(document['source']['path'])
    for row in observation['events']:
        paths.add(row['source']['file'])
    for row in observation['raw_tracebacks']:
        paths.update(frame['filename'] for frame in row['frames'])
    result = observation['result']
    if result is not None:
        paths.update(row['path'] for row in result['body_authority'])
        paths.update(row['source']['path'] for row in result['aliases'])
    require(all(type(path) is str for path in paths), 'Reference source path is not a string')
    return paths


def capture_observation_sources(observation, documents, receipt):
    """Retain exact loaded source bytes; path correspondence is source-scoped.

    User data strings are never rewritten. Only enumerated callable/event/trace
    source fields may refer to these origin records during reconstruction.
    """
    import biocompiler
    package = Path(biocompiler.__file__).resolve().parent
    stdlib = Path(sysconfig.get_path('stdlib')).resolve()
    result = {'package_root': str(package), 'checkout_root': str(ROOT),
        'stdlib_root': str(stdlib), 'python_version': platform.python_version(), 'files': {}}
    for filename in sorted(observation_paths(observation, documents)):
        if filename == '<string>':
            result['files'][filename] = {'logical': '<generated-dataclass>', 'artifact': None}
            continue
        path = Path(filename)
        require(path.is_absolute() and path.resolve() == path and path.is_file() and not path.is_symlink(),
                'Reference observation has an unbound source filename')
        if path.is_relative_to(package):
            logical = 'src/biocompiler/' + path.relative_to(package).as_posix()
        elif path.is_relative_to(ROOT) and path.relative_to(ROOT).parts[0] in ('tests', 'tools', 'examples'):
            logical = path.relative_to(ROOT).as_posix()
        elif path.is_relative_to(stdlib) and 'site-packages' not in path.relative_to(stdlib).parts:
            logical = 'stdlib/' + path.relative_to(stdlib).as_posix()
        else:
            raise AssertionError('Reference observation source is outside its closed installed/authoring/runtime roots')
        raw = manager.r.raw_file(path, 4 * 1024 * 1024)
        result['files'][filename] = {'logical': logical, 'artifact': manager.artifact(receipt, raw)}
    return result


def validate_observation_sources(proof, observation, documents, artifacts, *, package_path, runtime):
    require(type(proof) is dict and set(proof) == {'package_root', 'checkout_root', 'stdlib_root', 'python_version', 'files'}
        and proof['python_version'] == runtime and type(proof['files']) is dict,
        'Reference observation source authority differs')
    require(proof['package_root'] == str(Path(package_path).parent),
            'Reference observed sources do not belong to the selected installed package')
    roots = {key: Path(proof[key]) for key in ('package_root', 'checkout_root', 'stdlib_root')}
    require(all(path.is_absolute() and '..' not in path.parts for path in roots.values())
        and roots['package_root'] != roots['checkout_root'], 'Reference source roots are malformed')
    equal(sorted(proof['files']), sorted(observation_paths(observation, documents)),
          'Reference observed source path census differs')
    logicals = set()
    projection = {}
    for filename, row in proof['files'].items():
        require(type(row) is dict and set(row) == {'logical', 'artifact'}, 'Reference source origin fields differ')
        logical = row['logical']
        require(type(logical) is str and logical not in logicals, 'Reference source aliases collide')
        logicals.add(logical)
        if filename == '<string>':
            equal(row, {'logical': '<generated-dataclass>', 'artifact': None}, 'Unbound generated source label')
        else:
            relative = Path(logical)
            require(not relative.is_absolute() and '..' not in relative.parts and relative.suffix == '.py',
                    'Reference logical source escaped its closed roots')
            if logical.startswith('src/biocompiler/'):
                expected = roots['package_root'] / logical.removeprefix('src/biocompiler/')
                current = ROOT / logical
            elif relative.parts[0] in ('tests', 'tools', 'examples'):
                expected, current = roots['checkout_root'] / logical, ROOT / logical
            elif relative.parts[0] == 'stdlib' and 'site-packages' not in relative.parts:
                expected = roots['stdlib_root'] / logical.removeprefix('stdlib/')
                current = Path(sysconfig.get_path('stdlib')) / logical.removeprefix('stdlib/')
            else:
                raise AssertionError('Unknown reference source-origin category')
            require(str(expected) == filename, 'Reference source origin path was relocated')
            raw = artifacts.raw(row['artifact'], 4 * 1024 * 1024)
            require(raw == manager.r.raw_file(current, 4 * 1024 * 1024),
                    'Reference source/runtime profile differs from the reconstruction interpreter: ' + logical)
        projection[filename] = logical
    for trace in observation['raw_tracebacks']:
        for frame in trace['frames']:
            row = proof['files'][frame['filename']]
            require(frame['source_sha256'] == row['artifact'], 'Reference traceback source bytes are detached')
    return projection


def normalized_observation(observation, path_projection):
    """Exact content rehash after ONLY proved source filename correspondence."""
    value = json.loads(canonical(observation))
    documents, remap, updated = value['documents'], {}, {}
    for identity, document in documents.items():
        if document.get('kind') == 'graph': continue
        if document.get('kind') == 'provider':
            document['source']['path'] = path_projection[document['source']['path']]
        new = sha(canonical(document)); remap[identity] = new; updated[new] = document
    for identity, document in documents.items():
        if document.get('kind') != 'graph': continue
        document['nodes'] = {name: remap[node] for name, node in document['nodes'].items()}
        new = sha(canonical(document)); remap[identity] = new; updated[new] = document
    for row in value['events']:
        row['source']['file'] = path_projection[row['source']['file']]
        for slot in ('before', 'after'):
            row[slot] = remap[row[slot]]
        for slot in ('state_before', 'state_after'):
            if slot in row: row[slot]['graph'] = remap[row[slot]['graph']]
    for trace in value['raw_tracebacks']:
        for frame in trace['frames']:
            frame['filename'] = path_projection[frame['filename']]
    result = value['result']
    if result is not None:
        for row in result['body_authority']:
            row['path'] = path_projection[row['path']]
        for row in result['aliases']:
            row['source']['path'] = path_projection[row['source']['path']]
    value['documents'] = updated
    return value


def validate_observation_links(observation, details, corpus):
    """Bind recorded event/inspection chronology to complete native traffic."""
    rows = observation['events']
    require(type(rows) is list and rows and len(rows) <= 10000, 'Reference event census is outside its bound')
    require([row['id'] for row in rows] == list(range(len(rows))), 'Reference event IDs were reordered')
    clock, snapshots = [], []
    commands = [{item['sequence']: item for item in process['commands']} for process in details]
    claimed = [set() for _ in details]
    for row in rows:
        require(row['test'] in corpus.index['test_ids'] and type(row['entry']) is int and type(row['exit']) is int
            and row['entry'] < row['exit'] and row['outcome'] in ('return', 'raise'), 'Reference event boundary differs')
        clock.extend(((row['entry'], True, row), (row['exit'], False, row)))
        owner = row['manager']
        require(owner is None or type(owner) is int and 0 <= owner < len(details), 'Reference event has another manager')
        for slot, tick in (('state_before', row['entry']), ('state_after', row['exit'])):
            if slot in row:
                require(owner is not None, 'Reference inspection has no actual manager')
                snapshots.append((tick, row, slot, row[slot]))
        if row['kind'].startswith('manager.'):
            sequence = row['response_sequence']
            command = commands[owner].get(sequence)
            operation = row['kind'].removeprefix('manager.').replace('_', '-')
            require(command is not None and command['operation'] == operation
                and command['start_frame'] == row['start_frame']
                and command['end_frame'] + 1 == row['end_frame'], 'Public operation is detached from its owning native command')
            require(sequence not in claimed[owner], 'Public manager command was claimed twice')
            claimed[owner].add(sequence)
            require((command['outcome']['status'] == 'ok') == (row['outcome'] == 'return'),
                    'Actual command and public exception outcomes disagree')
        if 'transport' in row:
            link = row['transport']
            require(type(link) is dict and set(link) == {'manager', 'sequence', 'invocation', 'start_frame', 'end_frame'}
                and type(link['manager']) is int and 0 <= link['manager'] < len(details), 'Malformed actual host invocation ownership')
            invocation = details[link['manager']]['invocations'].get(link['invocation'])
            require(invocation is not None and invocation['command_sequence'] == link['sequence']
                and invocation['start_frame'] < link['start_frame'] <= link['end_frame'] <= invocation['end_frame'],
                'Actual callback is detached from its enclosing native invocation')
            if row['kind'].startswith('host.'):
                action = invocation['action']
                wanted = {'host.generate': ('reference-generate',), 'host.emit': ('reference-emit',),
                    'host.proposal': ('reference-proposal', 'reference-molecular-proposal')}[row['kind']]
                require(action in wanted, 'Reference source callback uses another native action')
                # The attempt proof independently binds a Molecular proposal to
                # its same-command emit output and immutable provider origin.
                if action == 'reference-molecular-proposal':
                    require('preparation_id' in invocation['arguments'], 'Molecular proposal omitted its attempt')
        elif row['kind'].startswith(('host.', 'override.', 'callback.')):
            raise AssertionError('Actual host callback lacks its original native invocation')
    stack, observed_ticks = [], []
    for tick, entering, row in sorted(clock, key=lambda item: item[0]):
        observed_ticks.append(tick)
        if entering:
            require(row['parent'] == (stack[-1]['id'] if stack else None), 'Reference event parent/nesting differs')
            require(row['manager_parent'] == next((item['id'] for item in reversed(stack)
                if item['kind'].startswith('manager.')), None), 'Reference public manager parent differs')
            stack.append(row)
        else:
            require(stack and stack.pop() is row, 'Reference event exits are reordered')
    equal(observed_ticks, list(range(2 * len(rows))), 'Reference observation clock has gaps or duplicates')
    seen = {}
    for _, row, slot, state in sorted(snapshots, key=lambda item: item[0]):
        owner = row['manager']
        require(type(state) is dict and set(state) == {'sequence', 'start_frame', 'end_frame', 'graph', 'reused'}
            and type(state['reused']) is bool, 'Reference compact observation fields differ')
        command = commands[owner].get(state['sequence'])
        require(command is not None and command['operation'] == 'inspect-ordered-references'
            and command['start_frame'] == state['start_frame'] and command['end_frame'] + 1 == state['end_frame']
            and command['outcome']['status'] == 'ok', 'Reference state is detached from a complete successful inspection')
        key = owner, state['sequence']
        body = {field: value for field, value in state.items() if field != 'reused'}
        if state['reused']:
            require(slot == 'state_before' and key in seen and seen[key] == body
                and row['start_frame'] == state['end_frame'], 'Reused reference state has intervening native traffic')
        else:
            require(key not in seen, 'Reference compact inspection was published twice')
            seen[key] = body
        if slot == 'state_before':
            require(row['start_frame'] == state['end_frame'], 'Reference before-state is not adjacent to its operation')
        else:
            require(row['end_frame'] == state['start_frame'], 'Reference after-state is not adjacent to its operation')
    expected = {(index, row['sequence']) for index, group in enumerate(details) for row in group['commands']
        if row['operation'] == 'inspect-ordered-references'}
    require(set(seen) == expected, 'Missing or unclaimed complete native inspection')
    equal(observation['initializations'], [row['id'] for row in rows if row['kind'] == 'native.initialize'],
          'Reference initialization evidence differs')
    equal(observation['result']['results'], corpus.index['observed_results'], 'Original18TestCase outcomes differ')
    require(observation['result']['mode'] == 'public_context', 'Reference replay did not select actual public routing')
    return {'public_commands': sum(map(len, claimed)), 'compact_inspections': len(seen),
        'all_commands': sum(len(group['commands']) for group in details),
        'events': len(rows), 'processes': len(details)}


def internal_correspondence(corpus, projection):
    """Retain each old implementation event and its checked observable owner.

    This is deliberately not a claim that Python parser/manager frames execute
    in OCaml. Complete public state, typed results and callbacks are compared;
    independent native domain/checker conformance remains a required CI gate.
    """
    boundaries = {row['original']: row['actual'] for row in projection['public_operations'] + projection['initializations']}
    for rows in projection['boundaries'].values():
        boundaries.update((row['original'], row['actual']) for row in rows)
    boundaries.update((row['original'], row['actual']) for row in projection['source_callpoints'])
    result = []
    for identity in corpus.taxonomy['native_internal']:
        event = corpus.events[identity]
        parent = event['parent']
        while parent is not None and parent not in boundaries:
            parent = corpus.events[parent]['parent']
        require(parent is not None, 'Original native implementation event lacks an observable owner')
        result.append({'original': identity, 'kind': event['kind'], 'original_owner': parent,
            'actual_owner': boundaries[parent], 'before': event['before'], 'after': event['after'],
            'outcome': event['outcome'], 'scope': 'native implementation; full original observation retained, owning public behavior checked'})
    require(len(result) == 1718, 'Original internal implementation inventory changed')
    return result


def validate_native_evidence(receipt, corpus, artifacts):
    """Require real native authority externally, then check all retained bytes.

    The caller first verifies exact current source, run and binary manifests.
    This function does not accept transcript-peer receipts as native evidence.
    """
    guard = tool('reference_execution_guard')
    require(receipt.get('execution_kind') == 'installed-native', 'Reference evidence is not an actual native run')
    channel, application = manager.declarations()
    manager.validate_verify(receipt, artifacts, channel, application)
    details, tapes = validate_processes(receipt, artifacts,
        executable_sha256=receipt['native_inputs']['sha256']['biocompiler-core'])
    observation = observed_data(receipt, artifacts)
    sources = artifacts.json(receipt['observation_sources'], maximum=4 * 1024 * 1024)
    paths = validate_observation_sources(sources, observation, observation['documents'], artifacts,
        package_path=receipt['package_path'], runtime=receipt['python_version'])
    guarded = artifacts.json(receipt['guard'], maximum=32 * 1024 * 1024)
    guard.validate(guarded, [row['frames'] for row in receipt['processes']], artifacts)
    attempts = tool('reference_attempt_receipts').validate(details)
    links = validate_observation_links(observation, details, corpus)
    public = validate_public_observations(corpus, observation['events'], observation['documents'])
    internal = internal_correspondence(corpus, public)
    proof = {'links': links, 'public': public, 'internal': internal, 'attempt_lifecycle': attempts,
        'scope': 'complete original public behavior and actual callback identities; internal Python frames retain explicit native correspondence'}
    return observation, normalized_observation(observation, paths), guarded, proof, tapes


def guarded_projection(value, paths):
    """Only recorded runtime build-string/path differences leave the comparison."""
    result = json.loads(canonical(value))
    result.pop('python_version')
    for override in result['host_overrides']:
        for source in override['source']:
            require(source['file'] in paths, 'Reference guarded host source is absent from observation authority')
            source['file'] = paths[source['file']]
    return result


def reconstruct(receipt, corpus, artifacts, *, installed=True, retain=None):
    """Run the unchanged18/current bridge against exact validated native tapes.

    This returns separately labeled mechanical evidence. It never replaces the
    required real-Core run or executes an original Python semantic backend.
    """
    import biocompiler
    from biocompiler.core_client import CoreClient
    guard = tool('reference_execution_guard')
    TranscriptPeer = tool('reference_pipeline_transcript').TranscriptPeer
    require(receipt['python_version'].split('.')[:2] == list(map(str, sys.version_info[:2])),
            'Reference transcript reconstruction requires its actual Python minor')
    actual, normalized, guarded, proof, tapes = validate_native_evidence(receipt, corpus, artifacts)
    with tempfile.TemporaryDirectory(prefix='reference-reconstruction-evidence-') as directory:
        replay = {'_artifact_directory': directory, 'artifacts': {}, 'execution_kind': 'transcript-reconstruction',
            'package_path': str(Path(biocompiler.__file__).resolve()), 'python_version': platform.python_version()}
        with TranscriptPeer(tapes) as peer:
            client = CoreClient(peer.executable, role='core', expected_sha256=peer.executable_sha256, timeout_seconds=300)
            with peer.recorded_nonces():
                observer = run_observed(client, corpus, replay, installed=installed, guard=guard.execution)
            completion = peer.evidence([owner.session for owner in observer.managers])
            replay['peer_executable'] = manager.artifact(replay, peer.executable.read_bytes())
        replay_artifacts = manager.Artifacts(directory, replay['artifacts'])
        current = observed_data(replay, replay_artifacts)
        source_proof = replay_artifacts.json(replay['observation_sources'], maximum=4 * 1024 * 1024)
        current_paths = validate_observation_sources(source_proof, current, current['documents'], replay_artifacts,
            package_path=str(Path(biocompiler.__file__).resolve()), runtime=platform.python_version())
        equal(normalized_observation(current, current_paths), normalized,
              'Current unchanged workflow reconstruction differs from the complete actual native observation')
        current_guard = replay_artifacts.json(replay['guard'], maximum=32 * 1024 * 1024)
        guard.validate(current_guard, [row['frames'] for row in replay['processes']], replay_artifacts)
        old_sources = artifacts.json(receipt['observation_sources'], maximum=4 * 1024 * 1024)
        original_paths = {filename: row['logical'] for filename, row in old_sources['files'].items()}
        equal(guarded_projection(current_guard, current_paths), guarded_projection(guarded, original_paths),
              'Current reconstruction changed its complete guarded execution')
        for process in replay['processes']:
            replay_artifacts.json(process['stderr'])
            for frame in process['frames']: replay_artifacts.raw(frame['frame'])
        replay_artifacts.raw(replay['peer_executable'])
        require(replay_artifacts.used == set(replay_artifacts.declared), 'Unconsumed reconstruction artifact')
        if retain is not None:
            for identity in replay_artifacts.declared:
                require(retain(replay_artifacts.raw(identity)) == identity, 'Reconstructed raw artifact was not retained exactly')
        return {'schema_version': 'biocompiler.reference_workflow_reconstruction.v1',
            'native_execution': False, 'python_version': platform.python_version(),
            'source_platform': {'system': receipt['system'], 'machine': receipt['machine']},
            'reconstruction_platform': {'system': platform.system(), 'machine': platform.machine()},
            'scope': 'same-minor current client/host execution from byte-exact real native transcript; no native acceptance substituted',
            'complete_observation_sha256': sha(canonical(normalized)),
            'guarded_execution_sha256': sha(canonical(guarded_projection(current_guard, current_paths))),
            'comparison': proof, 'peer': completion,
            'reconstructed_receipt': {key: value for key, value in replay.items() if key != '_artifact_directory'},
            'reconstructed_artifacts': {identity: replay_artifacts.verified[identity] for identity in sorted(replay_artifacts.verified)}}


class SubsetArtifacts:
    """An exact subinventory of an already fully verified evidence directory."""
    def __init__(self, complete, declared):
        require(type(declared) is dict and declared and all(
            identity in complete.declared and entry == complete.declared[identity]
            for identity, entry in declared.items()), 'Reconstruction artifact inventory is detached')
        self.complete, self.declared, self.used = complete, declared, set()
        self.verified = {identity: complete.verified[identity] for identity in declared}

    def raw(self, identity, maximum=64 * 1024 * 1024):
        require(identity in self.declared, 'Reconstruction refers outside its complete artifact inventory')
        self.used.add(identity)
        return self.complete.raw(identity, maximum)

    def json(self, identity, maximum=65536):
        raw = self.raw(identity, maximum)
        value = manager.r.decode(raw)
        require(canonical(value) == raw, 'Noncanonical reconstruction evidence')
        return value


def validate_complete(receipt, corpus, artifacts):
    """Validate source-platform reconstruction as supplemental exact evidence.

    A comparison worker still re-executes the current client independently.
    Neither a stored reconstructed PASS nor an expected graph grants validity.
    """
    guard = tool('reference_execution_guard')
    actual, normalized, guarded, comparison, tapes = validate_native_evidence(receipt, corpus, artifacts)
    saved = artifacts.json(receipt['reconstruction'], maximum=64 * 1024 * 1024)
    require(saved['schema_version'] == 'biocompiler.reference_workflow_reconstruction.v1'
        and saved['native_execution'] is False and saved['python_version'] == receipt['python_version']
        and saved['source_platform'] == {'system': receipt['system'], 'machine': receipt['machine']}
        and saved['reconstruction_platform'] == saved['source_platform'], 'Missing source-platform reconstruction')
    equal(saved['comparison'], comparison, 'Saved reference reconstruction changed original correspondence')
    require(saved['complete_observation_sha256'] == sha(canonical(normalized)),
            'Saved reconstruction is detached from the complete actual observation')
    replay = saved['reconstructed_receipt']
    require(type(replay) is dict and set(replay) == {'artifacts', 'execution_kind', 'package_path', 'python_version',
        'processes', 'observation', 'observation_sources', 'guard', 'peer_executable'}
        and replay['execution_kind'] == 'transcript-reconstruction'
        and replay['python_version'] == receipt['python_version'] and replay['package_path'] == receipt['package_path'],
        'Saved reconstruction changed its actual installed runtime')
    subset = SubsetArtifacts(artifacts, replay['artifacts'])
    equal(saved['reconstructed_artifacts'], subset.verified, 'Reconstructed full-byte census differs')
    peer = saved['peer']
    require(peer['schema'] == tool('reference_pipeline_transcript').SCHEMA and peer['native_execution'] is False
        and peer['peer_sha256'] == replay['peer_executable'], 'Recorded peer was presented as native authority')
    source_origin = subset.json(replay['observation_sources'], maximum=4 * 1024 * 1024)
    require(peer['python'].startswith(replay['python_version']), 'Saved peer source/runtime origin differs')
    tool('reference_pipeline_transcript').validate_executable(subset.raw(replay['peer_executable']), peer['origin'],
        source_path=str(Path(source_origin['checkout_root']) / 'tools/reference_pipeline_transcript.py'),
        source_sha256=sha(manager.r.raw_file(ROOT / 'tools/reference_pipeline_transcript.py')),
        index_sha256=sha(canonical({'schema': peer['schema'], 'members': peer['processes']})))
    _, reproduced = validate_processes(replay, subset, executable_sha256=peer['peer_sha256'])
    require(reproduced == tapes, 'Saved reconstruction did not consume every exact native frame')
    require(len(peer['processes']) == len(peer['completed_processes']) == len(tapes), 'Saved peer process census differs')
    seen = set()
    for number, (tape, process, completed, member) in enumerate(zip(tapes, replay['processes'],
            peer['completed_processes'], peer['processes'])):
        raw = b''.join((b'C' if direction == 'client' else b'S') + body for direction, body in tape)
        equal(member, {'path': str(number) + '.frames', 'bytes': len(raw), 'sha256': sha(raw),
            'frames': len(tape), 'nonce': manager.frame_body(tape[0][1])['session_id']}, 'Saved peer tape is detached')
        equal(completed, {'tape': number, 'pid': process['pid'], 'returncode': 0, 'frames': len(tape),
            'executable_sha256': peer['peer_sha256']}, 'Saved peer completion is detached from its actual process')
        require(process['pid'] not in seen and process['pid'] not in {item['pid'] for item in receipt['processes']},
                'Reconstruction process was presented as a real native process')
        seen.add(process['pid'])
    current = observed_data(replay, subset)
    sources = subset.json(replay['observation_sources'], maximum=4 * 1024 * 1024)
    paths = validate_observation_sources(sources, current, current['documents'], subset,
        package_path=replay['package_path'], runtime=replay['python_version'])
    equal(normalized_observation(current, paths), normalized, 'Saved reconstructed full object/exception graph differs')
    current_guard = subset.json(replay['guard'], maximum=32 * 1024 * 1024)
    guard.validate(current_guard, [row['frames'] for row in replay['processes']], subset)
    old_sources = artifacts.json(receipt['observation_sources'], maximum=4 * 1024 * 1024)
    old_paths = {filename: row['logical'] for filename, row in old_sources['files'].items()}
    expected_guard = guarded_projection(guarded, old_paths)
    equal(guarded_projection(current_guard, paths), expected_guard, 'Saved reconstruction changed actual guarded calls')
    require(saved['guarded_execution_sha256'] == sha(canonical(expected_guard)), 'Saved guarded execution hash differs')
    require(subset.used == set(subset.declared) and artifacts.used == set(artifacts.declared),
            'Unconsumed complete reference evidence artifact')
    originals = sorted({row['original'] for row in comparison['public']['public_operations'] +
        comparison['public']['initializations'] + comparison['public']['source_callpoints']} | {row['original']
            for rows in comparison['public']['boundaries'].values() for row in rows})
    return {'complete_observation_sha256': saved['complete_observation_sha256'],
        'original_behavior': {'corpus': corpus.metadata()['corpus'], 'test_ids': corpus.index['test_ids'],
            'observed_results': corpus.index['observed_results'], 'taxonomy': corpus.taxonomy,
            'checked_public_observations': [{'id': identity, 'before': corpus.events[identity]['before'],
                'after': corpus.events[identity]['after'], 'outcome': corpus.events[identity]['outcome']} for identity in originals],
            'native_internal': [{key: value for key, value in row.items() if key != 'actual_owner'}
                for row in comparison['internal']]}, 'comparison': comparison}


def main(argv=None):
    return tool('pipeline_reference_runtime').main(argv)


if __name__ == '__main__':
    raise SystemExit(main())
