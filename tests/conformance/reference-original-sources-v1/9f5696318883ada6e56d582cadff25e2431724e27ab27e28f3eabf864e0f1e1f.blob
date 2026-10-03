#!/usr/bin/env python3
"""Freeze complete original exact-reference contracts; never execute native code.

Original test bodies and assertions run unchanged. A code-identity trace observes
the actual Python domain/checker/producer calls, including calls through imported
aliases. Complete inputs and outputs are content addressed; no expected output
is supplied to a producer or checker. Filesystem-loader behavior is exercised by
the original tests but is not advertised as native domain acceptance.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from collections.abc import Mapping
from contextlib import contextmanager
import hashlib
import importlib
import inspect
import json
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / 'tests/conformance/reference-contracts-v1.json'
DOCUMENTS = CORPUS.with_suffix('')
SCHEMA = 'biocompiler.reference_contract_conformance.v1'
FILES = (
    'test_references', 'test_component_adapters', 'test_construct_ir',
    'test_construct_assembly', 'test_construct_audit', 'test_construct_checker',
    'test_molecular_ir', 'test_molecular_checker',
)
MAX_DOCUMENT_BYTES = 1_000_000
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_OBSERVATIONS = 150_000


def require(value, message):
    if not value:
        raise AssertionError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def encoded(value):
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                      allow_nan=False).encode('utf-8') + b'\n'


def sha(value):
    return hashlib.sha256(value).hexdigest()


def inventory(value):
    return sha(canonical({k: v for k, v in value.items() if k != 'inventory_fingerprint'}))


@contextmanager
def source_paths():
    old = sys.path[:]
    sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests'), str(ROOT)]
    try:
        yield
    finally:
        sys.path[:] = old


def definitions():
    """Closed class and function inventory; no wire-selected imports/reflection."""
    from biocompiler.registry import references as r
    from biocompiler.registry import reference_components as a
    from biocompiler.ir import construct as c, molecular as m
    from biocompiler.semantics.coordinates import SequenceRange
    from biocompiler.verification import construct as cc, molecular as mc
    from biocompiler.synthesis import construct as p
    from biocompiler.backends.reference import emit_reference_sequence
    kinds = {
        'reference-record': r.ReferenceRecord, 'reference-manifest': r.ReferenceManifest,
        'reference-selection': a.ReferenceSelection, 'sequence-range': SequenceRange,
        'construct-reference': c.ConstructReference, 'construct-molecule': c.ConstructMolecule,
        'component-placement': c.ComponentPlacement, 'construct-feature': c.ConstructFeature,
        'construct-junction': c.ConstructJunction, 'regulatory-relationship': c.RegulatoryRelationship,
        'construct-dependency': c.ConstructDependency, 'layout-evidence-policy': c.LayoutEvidencePolicy,
        'construct-request': c.ConstructRequest, 'construct-candidate': c.ConstructCandidate,
        'feature-status': m.FeatureStatus, 'translation-policy': m.TranslationPolicy,
        'encoding-policy': m.EncodingPolicy, 'encoding-evidence-policy': m.EncodingEvidencePolicy,
        'encoding-change': m.EncodingChange, 'molecular-record': m.MolecularRecord,
        'molecular-artifact': m.MolecularArtifact,
        'construct-result': cc.ConstructResult, 'molecular-result': mc.MolecularResult,
    }
    functions = {
        'normalize-sequence': r.normalize_sequence, 'translate-cds': r.translate_cds,
        'adapt-reference-component': a.adapt_reference_component,
        'reference-feature-statuses': m.reference_feature_statuses,
        'prepare-reference-construct': p.prepare_reference_construct,
        'generate-construct': p.generate_construct,
        'emit-reference-sequence': emit_reference_sequence,
        'check-construct-request': cc.check_construct_request,
        'check-construct': cc.check_construct, 'check-molecular': mc.check_molecular,
    }
    return kinds, functions


def verify_functions(kinds, functions):
    """Bind observations to live original code and its real canonical namespace."""
    cache = {}
    pending = list(functions.values())
    for cls in kinds.values():
        pending.extend(getattr(cls, mode).__func__ for mode in ('from_dict', 'from_json')
                       if hasattr(cls, mode))
    for fn in pending:
        require(type(fn) is types.FunctionType, 'Original reference callable was replaced')
        module = sys.modules.get(fn.__module__)
        require(module is not None and fn.__globals__ is vars(module), 'Original reference function namespace differs')
        path = Path(fn.__code__.co_filename).resolve()
        require(path.is_relative_to(ROOT / 'src/biocompiler') and
            Path(module.__file__).resolve() == path, 'Original reference function source differs')
        if path not in cache:
            root = compile(path.read_bytes(), str(path), 'exec', dont_inherit=True)
            codes, stack = {}, [root]
            while stack:
                code = stack.pop()
                codes[code.co_qualname] = code
                stack.extend(x for x in code.co_consts if type(x) is types.CodeType)
            cache[path] = codes
        require(fn.__code__ == cache[path].get(fn.__code__.co_qualname),
                'Original reference executable code differs from source')


def original_test_ids():
    with source_paths():
        return [test.id() for name in FILES for test in leaves(
            unittest.defaultTestLoader.loadTestsFromModule(importlib.import_module(name)))]


def plain(value):
    if value is None or type(value) in (str, bool, int, float):
        return value
    if isinstance(value, Mapping):
        require(all(type(k) is str for k in value), 'Non-string reference input key')
        return {k: plain(v) for k, v in value.items()}
    if type(value) in (tuple, list):
        return [plain(v) for v in value]
    if type(value).__module__.startswith('biocompiler.') and hasattr(value, 'to_dict'):
        return plain(value.to_dict())
    raise AssertionError('Uncaptured reference value type: ' + type(value).__module__ + '.' + type(value).__qualname__)


class Store:
    def __init__(self):
        self.documents = {}
        self.total = 0

    def add(self, value):
        raw = plain(value)
        data = canonical(raw)
        require(len(data) <= MAX_DOCUMENT_BYTES, 'Reference document exceeds byte bound')
        key = sha(data)
        if key not in self.documents:
            self.total += len(data) + 1
            require(self.total <= MAX_TOTAL_BYTES, 'Reference corpus exceeds total byte bound')
            self.documents[key] = raw
        return key


class Observer:
    def __init__(self, store, kinds, functions):
        self.store, self.kinds = store, kinds
        self.context = 'setup'
        self.rows, self.active, self.counts = [], {}, Counter()
        self.busy = False
        self.classes = {cls: kind for kind, cls in kinds.items()}
        self.codes = {}
        for operation, fn in functions.items():
            self.codes[fn.__code__] = (operation, tuple(inspect.signature(fn).parameters))
        self.decoders = {}
        for cls in kinds.values():
            for mode in ('from_dict', 'from_json'):
                if hasattr(cls, mode):
                    fn = getattr(cls, mode)
                    self.decoders.setdefault(fn.__func__.__code__, {})[(cls, mode)] = fn
        self.seen_objects = {}

    def describe(self, frame):
        if frame.f_code in self.codes:
            return self.codes[frame.f_code]
        if frame.f_code in self.decoders:
            cls = frame.f_locals.get('cls')
            for (wanted, mode) in self.decoders[frame.f_code]:
                if cls is wanted:
                    return 'decode-' + self.classes[cls] + ('-json' if mode == 'from_json' else ''), ('text' if mode == 'from_json' else 'data',)
        return None

    def retain_objects(self, value):
        if type(value) in self.classes:
            self.seen_objects[(self.classes[type(value)], self.store.add(value))] = value
        if isinstance(value, Mapping):
            for item in value.values():
                self.retain_objects(item)
        elif type(value) in (tuple, list):
            for item in value:
                self.retain_objects(item)

    def trace(self, frame, event, arg):
        if self.busy:
            return None
        if event == 'call':
            spec = self.describe(frame)
            if spec is None:
                return None
            operation, names = spec
            self.busy = True
            try:
                key = (self.context, operation)
                ordinal = self.counts[key]
                self.counts[key] += 1
                inputs = {name: self.store.add(frame.f_locals[name]) for name in names}
                for name in names:
                    self.retain_objects(frame.f_locals[name])
                row = dict(id=self.context + '/' + operation + '/' + str(ordinal),
                           context=self.context, operation=operation, inputs=inputs)
                self.rows.append(row)
                require(len(self.rows) <= MAX_OBSERVATIONS, 'Reference observation bound')
                self.active[id(frame)] = [row, None]
            finally:
                self.busy = False
            return self.trace
        tracked = self.active.get(id(frame))
        if tracked is None:
            return None
        if event == 'exception':
            tracked[1] = arg[1]
        elif event == 'return':
            row, error = self.active.pop(id(frame))
            self.busy = True
            try:
                if arg is None and error is not None:
                    row['outcome'] = dict(status='raise', module=type(error).__module__,
                        type=type(error).__qualname__, message=str(error))
                else:
                    self.retain_objects(arg)
                    outcome = dict(status='return', value=self.store.add(arg))
                    if type(arg) in self.classes:
                        outcome['fingerprint'] = arg.fingerprint
                        if hasattr(arg, 'layout_fingerprint'):
                            outcome['layout_fingerprint'] = arg.layout_fingerprint
                        if hasattr(arg, 'to_json'):
                            outcome['json'] = self.store.add(arg.to_json())
                    row['outcome'] = outcome
            finally:
                self.busy = False
        return self.trace


class Results(unittest.TestResult):
    def __init__(self, observer):
        super().__init__()
        self.observer = observer
        self.outcomes = []

    def startTest(self, test):
        super().startTest(test)
        self.observer.context = test.id()

    def addSuccess(self, test):
        super().addSuccess(test)
        self.outcomes.append({'id': test.id(), 'status': 'pass'})


def leaves(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from leaves(item)
        else:
            yield item


def source_inventory():
    paths = {Path('tests') / (name + '.py') for name in FILES}
    pending = list(paths)
    while pending:
        path = pending.pop()
        for node in ast.walk(ast.parse((ROOT / path).read_text())):
            names = ([node.module] if isinstance(node, ast.ImportFrom) else
                     [x.name for x in node.names] if isinstance(node, ast.Import) else [])
            for name in names:
                if name and name.startswith('test_'):
                    child = Path('tests') / (name.replace('.', '/') + '.py')
                    if child not in paths and (ROOT / child).is_file():
                        paths.add(child)
                        pending.append(child)
    # The complete current product source inventory is independent of ambient
    # sys.modules and includes transitive serializers/checkers, not just roots.
    paths.update(p.relative_to(ROOT) for p in (ROOT / 'src/biocompiler').rglob('*.py'))
    # Retained offline source/evidence bytes remain supplied authority, never fetched.
    data = ROOT / 'data/references/fap_car'
    paths.update(p.relative_to(ROOT) for p in data.rglob('*') if p.is_file())
    return {p.as_posix(): sha((ROOT / p).read_bytes()) for p in sorted(paths)}


def capture():
    with source_paths():
        kinds, functions = definitions()
        verify_functions(kinds, functions)
        modules = [importlib.import_module(name) for name in FILES]
        suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in modules)
        test_ids = [test.id() for test in leaves(suite)]
        require(len(test_ids) == len(set(test_ids)), 'Duplicate original reference test id')
        store = Store()
        observer = Observer(store, kinds, functions)
        result = Results(observer)
        old = sys.gettrace()
        require(old is None, 'Original reference capture requires an uninstrumented thread')
        sys.settrace(observer.trace)
        try:
            suite.run(result)
            require(result.wasSuccessful() and result.testsRun == len(test_ids),
                'Original reference assertions failed: ' + repr(result.errors + result.failures))
            require([row['id'] for row in result.outcomes] == test_ids,
                'Original reference test outcome census differs')
            # Additive producer controls use fresh original fixtures; expected
            # checker reports/candidates are never passed as accepted authority.
            fixture = importlib.import_module('test_construct_checker').fixture
            for alphabet in ('DNA', 'RNA'):
                observer.context = 'foundation-producers/' + alphabet
                request, candidate, registry, manifests = fixture(alphabet)
                generated = functions['generate-construct'](request)
                functions['emit-reference-sequence'](request, generated, registry, manifests)
            # Replay the exact complete authority from each original construct
            # mutation through the original emitter. Saved check outcomes are
            # deliberately not read or passed to it.
            from biocompiler.registry.components import ComponentRegistry
            requests = [row.copy() for row in observer.rows if row['operation'] == 'check-construct']
            seen = set()
            for row in requests:
                signature = tuple(sorted(row['inputs'].items()))
                if signature in seen:
                    continue
                seen.add(signature)
                raw = {k: store.documents[v] for k, v in row['inputs'].items()}
                observer.context = 'foundation-emitter-replay/' + row['id']
                request = kinds['construct-request'].from_dict(raw['request'])
                construct = kinds['construct-candidate'].from_dict(raw['candidate'])
                registry = ComponentRegistry.from_dict(raw['registry'])
                manifests = {key: kinds['reference-manifest'].from_dict(value)
                             for key, value in raw['manifests'].items()}
                try:
                    functions['emit-reference-sequence'](request, construct, registry, manifests)
                except Exception as error:
                    from biocompiler.errors import SerializationError
                    require(type(error) is SerializationError, 'Unexpected original emitter rejection')
            # Every observed typed object receives its own strict complete domain
            # roundtrip, including rich unsupported layouts used by old tests.
            values = sorted(observer.seen_objects.items())
            for (kind, identity), value in values:
                observer.context = 'foundation-roundtrip/' + kind + '/' + identity
                require(store.add(value) == identity, 'Observed typed authority changed before roundtrip')
                kinds[kind].from_dict(value.to_dict())
        finally:
            sys.settrace(old)
        require(not observer.active, 'Unfinished original reference observation')
        counts = Counter(row['operation'] for row in observer.rows)
        index = {
            'schema_version': SCHEMA,
            'authority': 'unchanged_original_python_functions_and_test_bodies;native_outputs_never_expected',
            'scope': 'reference_domain_and_pure_producer_checker_foundation;no_retained_manager_or_archive_acceptance',
            'source_files': source_inventory(), 'test_modules': list(FILES),
            'test_ids': test_ids, 'test_outcomes': result.outcomes,
            'operations': sorted(counts), 'operation_counts': dict(sorted(counts.items())),
            'observations': observer.rows,
            'documents': {key: {'path': 'tests/conformance/reference-contracts-v1/' + key + '.json',
                'bytes': len(canonical(value)) + 1} for key, value in sorted(store.documents.items())},
        }
        index['inventory_fingerprint'] = inventory(index)
        return index, store.documents


def validate(index, documents, *, sources=True):
    require(index['schema_version'] == SCHEMA, 'Reference corpus schema differs')
    require(index['inventory_fingerprint'] == inventory(index), 'Reference inventory differs')
    require(index['test_modules'] == list(FILES), 'Original module census differs')
    require(index['test_ids'] == original_test_ids(), 'Original per-test census differs')
    require(len(index['test_ids']) == len(set(index['test_ids'])), 'Duplicate original test id')
    require(index['test_outcomes'] == [{'id': name, 'status': 'pass'} for name in index['test_ids']],
            'Original test accounting differs')
    if sources:
        require(set(index['source_files']) == set(source_inventory()), 'Original reference source census differs')
        for name, identity in index['source_files'].items():
            require(sha((ROOT / name).read_bytes()) == identity, 'Original reference source differs: ' + name)
    require(set(documents) == set(index['documents']), 'Reference document inventory differs')
    total = 0
    for key, raw in documents.items():
        data = canonical(raw)
        require(sha(data) == key, 'Reference document identity differs')
        require(index['documents'][key] == {'path': 'tests/conformance/reference-contracts-v1/' + key + '.json',
            'bytes': len(data) + 1}, 'Reference document descriptor differs')
        require(len(data) <= MAX_DOCUMENT_BYTES, 'Reference document size differs')
        total += len(data) + 1
    require(total <= MAX_TOTAL_BYTES, 'Reference inventory byte bound')
    with source_paths():
        kinds, functions = definitions()
    operations = {op: set(inspect.signature(fn).parameters) for op, fn in functions.items()}
    for kind, cls in kinds.items():
        operations['decode-' + kind] = {'data'}
        if hasattr(cls, 'from_json'):
            operations['decode-' + kind + '-json'] = {'text'}
    ids = set()
    used = set()
    counts = Counter()
    ordinals = Counter()
    for row in index['observations']:
        require(set(row) == {'id', 'context', 'operation', 'inputs', 'outcome'}, 'Reference observation fields differ')
        require(row['id'] not in ids, 'Duplicate reference observation')
        ids.add(row['id'])
        operation = row['operation']
        require(operation in operations and set(row['inputs']) == operations[operation],
                'Unknown operation or incomplete original authority slots')
        key = (row['context'], operation)
        require(row['id'] == row['context'] + '/' + operation + '/' + str(ordinals[key]),
                'Reference observation sequence differs')
        ordinals[key] += 1
        counts[row['operation']] += 1
        used.update(row['inputs'].values())
        outcome = row['outcome']
        if outcome['status'] == 'return':
            require(set(outcome) <= {'status', 'value', 'fingerprint', 'layout_fingerprint', 'json'}
                and {'status', 'value'} <= set(outcome), 'Reference return fields differ')
            used.add(outcome['value'])
            if 'json' in outcome:
                used.add(outcome['json'])
                require(canonical(json.loads(documents[outcome['json']])) == canonical(documents[outcome['value']]),
                        'Reference complete JSON return differs')
            if 'fingerprint' in outcome:
                raw = documents[outcome['value']]
                reference = operation.startswith(('decode-reference-manifest', 'decode-reference-record'))
                expected = json.dumps(raw, sort_keys=True, separators=(',', ':'), ensure_ascii=reference,
                                      allow_nan=False).encode('utf-8')
                require(sha(expected) == outcome['fingerprint'], 'Reference public fingerprint differs')
            if 'layout_fingerprint' in outcome:
                raw = documents[outcome['value']]
                names = ('molecules', 'placements', 'features', 'junctions', 'regulatory_relations',
                         'dependencies', 'assumptions', 'evidence_policy')
                expected = raw['layout_fingerprint'] if 'layout_fingerprint' in raw else sha(canonical({k: raw[k] for k in names}))
                require(expected == outcome['layout_fingerprint'],
                        'Reference layout fingerprint differs')
        else:
            require(set(outcome) == {'status', 'module', 'type', 'message'} and outcome['status'] == 'raise',
                    'Reference exception fields differ')
    require(len(ids) <= MAX_OBSERVATIONS, 'Reference observation count bound')
    require(used <= set(documents), 'Missing reference observation document')
    # Typed objects retained for roundtrip can introduce complete documents before
    # their own observations; all are ultimately consumed by a roundtrip input.
    require(used == set(documents), 'Unclaimed reference document')
    require(index['operations'] == sorted(counts) and index['operation_counts'] == dict(sorted(counts.items())),
            'Reference operation census differs')


def load():
    raw = CORPUS.read_bytes()
    require(len(raw) <= 16 * 1024 * 1024, 'Reference index exceeds native byte bound')
    index = json.loads(raw)
    require(raw == canonical(index) + b'\n', 'Reference index physical bytes differ')
    documents = {}
    for key, row in index['documents'].items():
        require(row['path'] == 'tests/conformance/reference-contracts-v1/' + key + '.json',
                'Reference document path differs')
        data = (ROOT / row['path']).read_bytes()
        require(len(data) <= MAX_DOCUMENT_BYTES + 1, 'Reference document physical byte bound')
        value = json.loads(data)
        require(data == canonical(value) + b'\n' and len(data) == row['bytes'],
                'Reference document physical bytes differ')
        documents[key] = value
    validate(index, documents)
    return index, documents


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    index, documents = capture()
    validate(index, documents)
    if args.write:
        require(not CORPUS.exists(), 'Frozen reference corpus already exists; never overwrite')
        DOCUMENTS.mkdir(parents=True, exist_ok=True)
        for key, raw in documents.items():
            (DOCUMENTS / (key + '.json')).write_bytes(canonical(raw) + b'\n')
        CORPUS.write_bytes(canonical(index) + b'\n')
    else:
        frozen, old = load()
        require(index == frozen and documents == old, 'Fresh original reference capture differs')
    print(json.dumps({'tests': len(index['test_ids']), 'observations': len(index['observations']),
        'documents': len(documents), 'bytes': sum(row['bytes'] for row in index['documents'].values()),
        'inventory_fingerprint': index['inventory_fingerprint']}, sort_keys=True))


if __name__ == '__main__':
    main()
