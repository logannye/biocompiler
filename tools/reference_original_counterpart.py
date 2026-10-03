"""Run the frozen reference tests in their exact, finite original source closure.

New product files are not original authority. Every captured file retains its
pinned bytes in the child. The single reviewed Core transport counterpart is
restored from an exact archived source; this never validates the current bridge
or refreshes an expectation. Native code is neither loaded nor run.
"""
from __future__ import annotations

import ast
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import MethodType

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'biocompiler.reference_original_counterpart.v1'
CORPUS = 'tests/conformance/reference-contracts-v1.json'
CORPUS_SHA = 'f0d3acadad15fbc29f195fc1a7dae875e8fb027565ec20fdbe1934fec7f3cf1b'
INVENTORY = '69c26f9329ec1d3a40e17a0a5f70d311611121d57b9b9f9962163678b1dc952c'
FREEZER = 'tools/freeze_reference_contracts.py'
FREEZER_SHA = '9f5696318883ada6e56d582cadff25e2431724e27ab27e28f3eabf864e0f1e1f'
TEST = 'tests/test_reference_contracts_corpus.py'
TEST_SHA = '84df82fd9a57d18ad022d68a318aeb3495ff0a724b1205a73cb8092d20c2133b'
RUNNER = 'tools/reference_original_counterpart.py'
CORE_SOURCE = 'src/biocompiler/core_pipeline_manager.py'
CORE_ORIGINAL_SHA = '40a08477c97a97159372d9723267df3cacf8335a59d6b00ada34bb56470e31f3'
CORE_CURRENT_SHA = '0c0cfac138484cf71f1bb1303e66873b8b148ca236e07930fdbadd0b477a11be'
CORE_BLOB = 'tests/conformance/reference-original-sources-v1/' + CORE_ORIGINAL_SHA + '.blob'
CORE_WITNESS = 'tests/conformance/reference-manager-source-counterpart-v1.json'
CORE_WITNESS_SHA = '9f4406d46a7d18db944094ea6875a1daceb3d327b2da8e8029250e312ea833f8'
# Imported by the frozen test_synthetic_generation fixture, but not included
# in its original source_inventory traversal. Entire bytes match c58aa504.
SUPPORT = {'examples/realization_check.py': '0d1012d2c3cd074540afce586658ee2ee3cba08a4e3d2e2586f8aaec1fa75fc2'}
TEST_MODULE = 'test_reference_contracts_corpus'
CLASS = 'ReferenceContractsCorpusTests'
HOOK = '''\n\ndef load_tests(loader, tests, pattern):
    from tools.reference_original_counterpart import original_test_suite
    return original_test_suite(loader, tests, pattern, __name__)
'''
MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_DATA_BYTES = 64 * 1024 * 1024
MAX_RESULT_BYTES = 4 * 1024 * 1024


def require(value, message):
    if not value:
        raise AssertionError(message)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def local_file(root, logical):
    require(type(logical) is str and not Path(logical).is_absolute() and '..' not in Path(logical).parts,
            'Reference counterpart logical path escapes its source root')
    path = root / logical
    require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root.resolve()),
            'Reference counterpart source path is missing or redirected: ' + logical)
    return path


def authority():
    raw = local_file(ROOT, CORPUS).read_bytes()
    require(sha(raw) == CORPUS_SHA, 'Frozen reference corpus bytes differ')
    index = json.loads(raw)
    require(index['inventory_fingerprint'] == INVENTORY == sha(canonical(
        {key: value for key, value in index.items() if key != 'inventory_fingerprint'})),
        'Frozen reference inventory differs')
    require(len(index['source_files']) == 203 and len(index['documents']) == 4000,
            'Frozen reference closure census differs')
    return index


def core_source_witness(raw=None):
    """One exact reviewed transport revision, never a changed-file whitelist."""
    encoded = local_file(ROOT, CORE_WITNESS).read_bytes()
    require(sha(encoded) == CORE_WITNESS_SHA, 'Reference Core source witness changed')
    witness = json.loads(encoded)
    require(set(witness) == {'schema_version', 'base_revision', 'path', 'original_sha256',
        'current_sha256', 'changes', 'restoration'} and
        witness['schema_version'] == 'biocompiler.reference_manager_source_counterpart.v1' and
        witness['base_revision'] == 'a8cf5266963abfb5beae408c296a6f626e8f51fe' and
        witness['path'] == CORE_SOURCE and witness['original_sha256'] == CORE_ORIGINAL_SHA and
        witness['current_sha256'] == CORE_CURRENT_SHA and len(witness['changes']) == 6,
        'Reference Core source correspondence is not the closed reviewed revision')
    current = local_file(ROOT, CORE_SOURCE).read_bytes() if raw is None else raw
    require(type(current) is bytes and sha(current) == CORE_CURRENT_SHA,
            'Captured reference Core source is outside its exact counterpart')
    archived = local_file(ROOT, CORE_BLOB).read_bytes()
    require(sha(archived) == CORE_ORIGINAL_SHA, 'Original reference Core archive changed')
    lines = current.decode().splitlines(keepends=True)
    original_lines = archived.decode().splitlines(keepends=True)
    previous = 0
    for change in witness['changes']:
        require(set(change) == {'old_start_line', 'old_end_line', 'new_start_line', 'new_end_line', 'before', 'after'}
            and all(type(change[key]) is int for key in ('old_start_line', 'old_end_line', 'new_start_line', 'new_end_line'))
            and type(change['before']) is str and type(change['after']) is str
            and previous < change['new_start_line'] <= change['new_end_line'],
            'Reference Core exact source spans overlap or changed')
        previous = change['new_end_line']
        require(''.join(lines[change['new_start_line'] - 1:change['new_end_line']]) == change['after']
            and ''.join(original_lines[change['old_start_line'] - 1:change['old_end_line']]) == change['before'],
            'Reference Core complete source span differs')
    for change in reversed(witness['changes']):
        lines[change['new_start_line'] - 1:change['new_end_line']] = change['before'].splitlines(keepends=True)
    require(''.join(lines).encode() == archived, 'Reference Core restoration differs from entire archived source')
    return archived, {'path': CORE_SOURCE, 'archive': CORE_BLOB, 'archive_sha256': CORE_ORIGINAL_SHA,
        'current_sha256': CORE_CURRENT_SHA, 'witness': CORE_WITNESS, 'witness_sha256': CORE_WITNESS_SHA,
        'correspondence': witness, 'scope': 'original source execution only; current native bridge validation is separate'}


def test_witness(raw=None):
    current = local_file(ROOT, TEST).read_bytes() if raw is None else raw
    require(type(current) is bytes, 'Original reference test source must be bytes')
    if sha(current) == TEST_SHA:
        original, hooked = current, False
    else:
        hook = HOOK.encode()
        require(current.count(hook) == 1 and current.endswith(hook),
                'Reference test has an unreviewed bridge extension')
        original, hooked = current[:-len(hook)], True
        require(sha(original) == TEST_SHA, 'Reference test bodies differ from their whole original source')
    return {'original_sha256': TEST_SHA, 'current_sha256': sha(current),
            'original_source': original.decode(), 'current_source': current.decode(),
            'hook': HOOK if hooked else None}


def method_names():
    tree = ast.parse(test_witness()['original_source'])
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == CLASS)
    result = sorted(node.name for node in cls.body if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'))
    require(len(result) == 8, 'Original reference test method census differs')
    return result


def selection(module, ids):
    require(module in (TEST_MODULE, 'tests.' + TEST_MODULE), 'Unknown reference counterpart test module')
    available = [module + '.' + CLASS + '.' + method for method in method_names()]
    ids = available if ids is None else ids
    require(type(ids) is list and ids == available,
            'Original reference test selection is missing, duplicated or reordered')
    return ids


def data_closure(index):
    result = [{'logical': CORPUS, 'sha256': CORPUS_SHA, 'bytes': len(local_file(ROOT, CORPUS).read_bytes())}]
    for identity, row in sorted(index['documents'].items()):
        logical = 'tests/conformance/reference-contracts-v1/' + identity + '.json'
        require(row['path'] == logical, 'Frozen reference document path differs')
        raw = local_file(ROOT, logical).read_bytes()
        require(len(raw) == row['bytes'] and raw.endswith(b'\n') and sha(raw[:-1]) == identity,
                'Frozen complete reference document bytes differ')
        result.append({'logical': logical, 'sha256': sha(raw), 'bytes': len(raw)})
    for logical, identity in ((CORE_BLOB, CORE_ORIGINAL_SHA), (CORE_WITNESS, CORE_WITNESS_SHA)):
        raw = local_file(ROOT, logical).read_bytes()
        require(sha(raw) == identity, 'Reference exact Core counterpart data changed')
        result.append({'logical': logical, 'sha256': identity, 'bytes': len(raw)})
    require(sum(row['bytes'] for row in result) <= MAX_DATA_BYTES, 'Reference counterpart data copy exceeds bound')
    return result


def source_closure(index, package_root):
    values = {}
    pins = index['source_files'] | {FREEZER: FREEZER_SHA} | SUPPORT
    for logical, identity in sorted(pins.items()):
        path = local_file(ROOT, logical)
        raw = path.read_bytes()
        if logical == CORE_SOURCE:
            require(identity == CORE_ORIGINAL_SHA, 'Frozen reference Core authority changed')
            copied, _ = core_source_witness(raw)
        else:
            require(sha(raw) == identity, 'Captured reference source bytes changed: ' + logical)
            copied = raw
        if logical.startswith('src/biocompiler/'):
            path = local_file(package_root, logical.removeprefix('src/biocompiler/'))
            require(path.read_bytes() == raw, 'Installed captured reference source bytes differ: ' + logical)
        values[logical] = (path, raw, copied)
    witness = test_witness()
    values[TEST] = (local_file(ROOT, TEST), witness['current_source'].encode(), witness['original_source'].encode())
    path = local_file(ROOT, RUNNER)
    values[RUNNER] = (path, path.read_bytes(), path.read_bytes())
    require(sum(len(raw) for _, raw, _ in values.values()) <= MAX_SOURCE_BYTES, 'Reference counterpart source copy exceeds bound')
    require(len(values) == 207, 'Reference counterpart complete source census differs')
    return values, witness


def run(*, test_module=TEST_MODULE, test_ids=None):
    ids = selection(test_module, test_ids)
    index = authority()
    package = importlib.import_module('biocompiler')
    package_root = Path(package.__file__).resolve().parent
    sources, witness = source_closure(index, package_root)
    data = data_closure(index)
    with tempfile.TemporaryDirectory(prefix='biocompiler-reference-original-') as directory:
        overlay = Path(directory).resolve()
        rows = []
        for logical, (origin, current, copied) in sorted(sources.items()):
            target = overlay / logical
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(copied)
            rows.append({'logical': logical, 'origin': str(origin), 'origin_sha256': sha(current),
                         'path': str(target), 'sha256': sha(copied), 'substituted': current != copied})
        for row in data:
            target = overlay / row['logical']
            target.parent.mkdir(parents=True, exist_ok=True)
            os.link(local_file(ROOT, row['logical']), target)
        manifest = {'schema': SCHEMA, 'root': str(overlay), 'package_root': str(package_root),
                    'test_module': test_module, 'test_ids': ids, 'sources': rows, 'data': data,
                    'test_witness': witness, 'source_inventory': index['source_files'],
                    'core_source_witness': core_source_witness()[1]}
        (overlay / 'manifest.json').write_bytes(canonical(manifest))
        script = ('import sys;sys.path[:0]=[sys.argv[1],sys.argv[1]+"/src",sys.argv[1]+"/tests"];'
                  'from tools.reference_original_counterpart import child;child(sys.argv[1])')
        environment = dict(os.environ)
        environment.pop('PYTHONPATH', None)
        completed = subprocess.run([sys.executable, '-I', '-B', '-c', script, str(overlay)],
            cwd=overlay, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        require(completed.returncode == 0, 'Original reference child failed: ' + completed.stderr.decode(errors='replace')[-12000:])
        output = overlay / 'result.json'
        require(output.is_file() and output.stat().st_size <= MAX_RESULT_BYTES, 'Original reference child result is missing or too large')
        receipt = json.loads(output.read_bytes())
        try:
            validate(receipt)
        except AssertionError as error:
            raise AssertionError(str(error) + '\n' + completed.stderr.decode(errors='replace')[-12000:]) from error
        return receipt


def outcomes(value, ids, classname):
    require(type(value) is dict and set(value) == {'test_ids', 'tests', 'outcomes'} and
            value['test_ids'] == ids and value['tests'] == len(ids), 'Original reference execution census differs')
    rows = value['outcomes']
    require(type(rows) is list and [row['id'] for row in rows] == ids,
            'Original reference outcomes are missing, duplicated or reordered')
    for row in rows:
        require(set(row) == {'id', 'class', 'status', 'detail'} and row['class'] == classname and
                row['status'] in ('success', 'failure', 'error', 'skipped', 'expected-failure', 'unexpected-success') and
                (row['detail'] is None or type(row['detail']) is str), 'Original reference outcome identity or status differs')
    return {row['id']: row for row in rows}


def validate(receipt):
    require(type(receipt) is dict and set(receipt) == {'manifest', 'modules', 'source_inventory', 'value'},
            'Malformed original reference receipt')
    manifest = receipt['manifest']
    require(type(manifest) is dict and set(manifest) == {'schema', 'root', 'package_root', 'test_module', 'test_ids',
            'sources', 'data', 'test_witness', 'source_inventory', 'core_source_witness'} and manifest['schema'] == SCHEMA,
            'Malformed original reference manifest')
    root, package_root = Path(manifest['root']), Path(manifest['package_root'])
    require(root.is_absolute() and package_root.is_absolute(), 'Original reference roots differ')
    current_package = Path(importlib.import_module('biocompiler').__file__).resolve().parent
    require(package_root == current_package, 'Original reference installed package origin differs')
    ids = selection(manifest['test_module'], manifest['test_ids'])
    index = authority()
    sources, witness = source_closure(index, package_root)
    require(manifest['core_source_witness'] == core_source_witness()[1],
            'Original reference Core source correspondence differs')
    require(manifest['test_witness'] == witness, 'Original reference whole-test correspondence differs')
    expected = []
    for logical, (origin, current, copied) in sorted(sources.items()):
        expected.append({'logical': logical, 'origin': str(origin), 'origin_sha256': sha(current),
                         'path': str(root / logical), 'sha256': sha(copied), 'substituted': current != copied})
    require(manifest['sources'] == expected, 'Original reference source/copy census differs')
    require(manifest['data'] == data_closure(index), 'Original reference complete document census differs')
    require(receipt['source_inventory'] == manifest['source_inventory'] == index['source_files'],
            'Original reference executed source closure differs')
    rows = {row['logical']: row for row in expected}
    modules = receipt['modules']
    mandatory = {'biocompiler', 'biocompiler.compiler.pipeline', 'biocompiler.registry.references',
        'biocompiler.ir.construct', 'biocompiler.ir.molecular', 'biocompiler.verification.construct',
        'biocompiler.verification.molecular', 'examples.realization_check', manifest['test_module']}
    require(type(modules) is dict and mandatory <= set(modules), 'Original reference canonical module census differs')
    for name, module in modules.items():
        require(type(module) is dict and set(module) == {'logical', 'path', 'sha256', 'namespace'},
                'Malformed original reference module authority')
        logical = module['logical']
        require(logical in rows and module['path'] == rows[logical]['path'] and
                module['sha256'] == rows[logical]['sha256'] and module['namespace'] == name,
                'Original reference loaded module source differs')
        if name == manifest['test_module']:
            require(logical == TEST, 'Original reference test module differs')
        elif name == 'examples.realization_check':
            require(logical == 'examples/realization_check.py', 'Original reference supporting fixture module differs')
        else:
            require(logical.startswith('src/biocompiler/') and name == logical.removeprefix('src/').removesuffix('.py')
                    .replace('/', '.').removesuffix('.__init__'), 'Original reference product namespace differs')
    outcomes(receipt['value'], ids, manifest['test_module'] + '.' + CLASS)
    return receipt['value']


def leaves(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from leaves(item)
        else:
            yield item


def child(directory):
    overlay = Path(directory).resolve()
    require(overlay == ROOT, 'Original reference runner escaped its snapshot')
    manifest = json.loads((overlay / 'manifest.json').read_bytes())
    for row in manifest['sources'] + manifest['data']:
        require(sha(local_file(overlay, row['logical']).read_bytes()) == row['sha256'],
                'Original reference copied bytes differ')
    require(sha(local_file(overlay, TEST).read_bytes()) == TEST_SHA, 'Original reference test body was not restored')
    require(sha(local_file(overlay, FREEZER).read_bytes()) == FREEZER_SHA, 'Original reference freezer changed')
    module = importlib.import_module(manifest['test_module'])
    discovered = list(leaves(unittest.defaultTestLoader.loadTestsFromModule(module)))
    selected = [case for case in discovered if case.id() in manifest['test_ids']]
    require([case.id() for case in selected] == manifest['test_ids'] and
            all(type(case) is getattr(module, CLASS) for case in selected), 'Original reference selected TestCases differ')

    class RetainedResult(unittest.TextTestResult):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.outcomes = []

        def retain(self, test, status, detail=None):
            self.outcomes.append({'id': test.id(), 'class': type(test).__module__ + '.' + type(test).__qualname__,
                                  'status': status, 'detail': detail})

        def addSuccess(self, test):
            super().addSuccess(test); self.retain(test, 'success')

        def addError(self, test, error):
            super().addError(test, error); self.retain(test, 'error', self._exc_info_to_string(error, test))

        def addFailure(self, test, error):
            super().addFailure(test, error); self.retain(test, 'failure', self._exc_info_to_string(error, test))

        def addSkip(self, test, reason):
            super().addSkip(test, reason); self.retain(test, 'skipped', reason)

        def addExpectedFailure(self, test, error):
            super().addExpectedFailure(test, error); self.retain(test, 'expected-failure', self._exc_info_to_string(error, test))

        def addUnexpectedSuccess(self, test):
            super().addUnexpectedSuccess(test); self.retain(test, 'unexpected-success')

    result = unittest.TextTestRunner(stream=sys.stderr, resultclass=RetainedResult).run(unittest.TestSuite(selected))
    value = {'test_ids': manifest['test_ids'], 'tests': result.testsRun, 'outcomes': result.outcomes}
    inventory = module.oracle.source_inventory()
    require(inventory == authority()['source_files'], 'Original reference fresh source inventory differs')
    rows = {row['logical']: row for row in manifest['sources']}
    modules = {}
    for name, loaded in tuple(sys.modules.items()):
        if name == 'biocompiler' or name.startswith('biocompiler.') or name in (manifest['test_module'], 'examples.realization_check'):
            path = Path(loaded.__file__).resolve()
            require(path.is_relative_to(overlay) and vars(loaded).get('__name__') == name,
                    'Original reference loaded module escaped canonical snapshot')
            logical = path.relative_to(overlay).as_posix()
            require(logical in rows and sha(path.read_bytes()) == rows[logical]['sha256'],
                    'Original reference loaded source bytes changed')
            modules[name] = {'logical': logical, 'path': str(path), 'sha256': rows[logical]['sha256'], 'namespace': name}
    for row in manifest['sources'] + manifest['data']:
        require(sha(local_file(overlay, row['logical']).read_bytes()) == row['sha256'],
                'Original reference source or expected documents changed during execution')
    (overlay / 'result.json').write_bytes(canonical({'manifest': manifest, 'modules': modules,
                                                   'source_inventory': inventory, 'value': value}))


def original_test_suite(loader, tests, pattern, module):
    """Retain actual discovered instances/classes; forward each real child outcome."""
    require(module in (TEST_MODULE, 'tests.' + TEST_MODULE), 'Unknown reference test bridge module')
    witness = test_witness()
    if witness['hook'] is None:
        return tests
    cases = list(leaves(tests))
    require(cases and len({type(case) for case in cases}) == 1, 'Original reference test class census differs')
    original = type(cases[0])
    require(original.__module__ == module and original.__qualname__ == CLASS and 'tearDownClass' not in vars(original),
            'Original reference class identity or fixtures changed')
    ids = selection(module, [case.id() for case in cases])
    classname = module + '.' + CLASS

    def setup(cls):
        receipt = run(test_module=module, test_ids=ids)
        cls._reference_original_receipt = receipt
        cls._reference_original_outcomes = outcomes(receipt['value'], ids, classname)

    original.setUpClass = classmethod(setup)

    def execute(self, result=None):
        own = result is None
        if own:
            result = self.defaultTestResult()
            result.startTestRun()
        result.startTest(self)
        try:
            row = type(self)._reference_original_outcomes[self.id()]
            status, detail = row['status'], row['detail']
            if status == 'success': result.addSuccess(self)
            elif status == 'skipped': result.addSkip(self, detail)
            elif status == 'unexpected-success': result.addUnexpectedSuccess(self)
            else:
                error = RuntimeError(detail) if status == 'error' else AssertionError(detail)
                info = (type(error), error, None)
                if status == 'error': result.addError(self, info)
                elif status == 'failure': result.addFailure(self, info)
                else: result.addExpectedFailure(self, info)
        finally:
            result.stopTest(self)
            if own: result.stopTestRun()
        return result

    for case in cases:
        case.run = MethodType(execute, case)
    return unittest.TestSuite(cases)
