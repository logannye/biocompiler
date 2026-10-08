"""Execute original reference-manager tests against an exact archived package.

Historical source execution does not validate the current native adapter.
Current installed package origins are retained as separate evidence. Neither
Git nor a native executable is used at runtime, and no expectation is refreshed.
"""
from __future__ import annotations

import ast
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import MethodType

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'biocompiler.reference_pipeline_original_counterpart.v1'
CORPUS = 'tests/conformance/reference-pipeline-semantics-v1.json'
CORPUS_SHA = '516135a64458bc985294f7b2761138d5613209e3b225028492fe86f22c5092d3'
INVENTORY = 'e5ce05abcd7645854f4ca2daf46632cc5871f9ed301c283220b018709991d417'
FREEZER = 'tools/capture_reference_pipeline_semantics.py'
FREEZER_SHA = 'f2d2676d960ae49e44b2cca407c427b6eecee9a70cb11d5daf0abdb181c69cd3'
TEST = 'tests/test_reference_pipeline_semantics.py'
TEST_SHA = 'fc571817d0bef6095c5161e519e9047293aaaee670083d8681c59e06d1c65487'
RUNNER = 'tools/reference_pipeline_original_counterpart.py'
ARCHIVE = 'tests/conformance/reference-original-sources-v1.json'
ARCHIVE_SHA = 'df3323eceb20d967ea9ae8909da94f38660a1995d0e0314531bc5989516b014a'
REVISION = 'a8cf5266963abfb5beae408c296a6f626e8f51fe'
PROFILE = 'reference-pipeline-semantics-v1'
TEST_MODULE = 'test_reference_pipeline_semantics'
CLASS = 'ReferencePipelineSemanticsTests'
HOOK = '''\n\ndef load_tests(loader, tests, pattern):
    from tools.reference_pipeline_original_counterpart import original_test_suite
    return original_test_suite(loader, tests, pattern, __name__)
'''
MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_DATA_BYTES = 64 * 1024 * 1024
MAX_RESULT_BYTES = 8 * 1024 * 1024


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
    require(len(index['source_files']) == 200 and len(index['documents']) == 10867,
            'Frozen reference closure census differs')
    return index


def source_archive():
    raw = local_file(ROOT, ARCHIVE).read_bytes()
    require(sha(raw) == ARCHIVE_SHA, 'Original source archive index differs')
    index = json.loads(raw)
    require(index['schema'] == 'biocompiler.reference_original_sources.v1'
            and index['revision'] == REVISION and len(index['files']) == len(index['blobs']) == 215,
            'Original source archive census differs')
    directory = ROOT / 'tests/conformance/reference-original-sources-v1'
    expected = {row['path'] for row in index['blobs'].values()}
    require({path.relative_to(ROOT).as_posix() for path in directory.iterdir()} == expected,
            'Original source archive contains missing or unclaimed blobs')
    values = {}
    for pin, row in index['blobs'].items():
        require(row['path'] == 'tests/conformance/reference-original-sources-v1/' + pin + '.blob',
                'Original source archive blob path differs')
        value = local_file(ROOT, row['path']).read_bytes()
        require(len(value) == row['bytes'] and sha(value) == pin, 'Original source archive blob differs')
        values[pin] = value
    require(sum(map(len, values.values())) <= MAX_SOURCE_BYTES, 'Original source archive exceeds bound')
    for row in index['files'].values():
        require(row['sha256'] in values and len(values[row['sha256']]) == row['bytes'],
                'Original source archive file binding differs')
    return index, values


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
    require(len(result) == 9, 'Original reference test method census differs')
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
    documents = (ROOT / CORPUS).with_suffix('')
    require({path.name for path in documents.iterdir()} == {pin + '.json' for pin in index['documents']},
            'Original reference contains missing or unclaimed documents')
    for identity, size in sorted(index['documents'].items()):
        logical = 'tests/conformance/reference-pipeline-semantics-v1/' + identity + '.json'
        raw = local_file(ROOT, logical).read_bytes()
        require(len(raw) == size and raw.endswith(b'\n') and sha(raw[:-1]) == identity,
                'Frozen complete reference document bytes differ')
        result.append({'logical': logical, 'sha256': sha(raw), 'bytes': len(raw)})
    archive, _ = source_archive()
    result.append({'logical': ARCHIVE, 'sha256': ARCHIVE_SHA, 'bytes': len(local_file(ROOT, ARCHIVE).read_bytes())})
    result.extend({'logical': row['path'], 'sha256': pin, 'bytes': row['bytes']}
                  for pin, row in sorted(archive['blobs'].items()))
    require(sum(row['bytes'] for row in result) <= MAX_DATA_BYTES, 'Reference counterpart data copy exceeds bound')
    return result


def source_closure(index):
    archive, blobs = source_archive()
    profile = archive['profiles'][PROFILE]
    require(profile['corpus_sha256'] == CORPUS_SHA and profile['source_files'] == index['source_files'],
            'Archived original capture authority differs')
    values = {}
    for logical, identity in sorted(profile['snapshot_files'].items()):
        require(archive['files'][logical]['sha256'] == identity, 'Archived snapshot source binding differs')
        path = local_file(ROOT, archive['blobs'][identity]['path'])
        raw = blobs[identity]
        values[logical] = (path, raw, raw)
    witness = test_witness()
    require(archive['files'][TEST]['sha256'] == TEST_SHA and
            blobs[TEST_SHA] == witness['original_source'].encode(), 'Archived original TestCase bytes differ')
    values[TEST] = (local_file(ROOT, TEST), witness['current_source'].encode(), witness['original_source'].encode())
    path = local_file(ROOT, RUNNER)
    values[RUNNER] = (path, path.read_bytes(), path.read_bytes())
    require(sum(len(raw) for _, raw, _ in values.values()) <= MAX_SOURCE_BYTES, 'Reference counterpart source copy exceeds bound')
    require(len(values) == 202, 'Reference counterpart complete source census differs')
    return values, witness


def installed_authority():
    package = importlib.import_module('biocompiler')
    core = importlib.import_module('biocompiler.core_pipeline_manager')
    root = Path(package.__file__).resolve().parent
    modules = {}
    for name, module in (('biocompiler', package), ('biocompiler.core_pipeline_manager', core)):
        relative = '__init__.py' if name == 'biocompiler' else 'core_pipeline_manager.py'
        path = local_file(root, relative)
        require(vars(module).get('__name__') == name and Path(module.__file__).resolve() == path,
                'Current installed reference module origin differs')
        modules[name] = {'path': str(path), 'sha256': sha(path.read_bytes()), 'namespace': name}
    sources = {path.relative_to(root).as_posix(): sha(local_file(root, path.relative_to(root).as_posix()).read_bytes())
               for path in sorted(root.rglob('*.py'))}
    require(len(sources) <= 512, 'Current installed source census exceeds bound')
    return {'package_root': str(root), 'modules': modules, 'sources': sources,
            'scope': 'origin_only_not_current_bridge_semantic_validation'}


def run(*, test_module=TEST_MODULE, test_ids=None):
    ids = selection(test_module, test_ids)
    index = authority()
    installed = installed_authority()
    sources, witness = source_closure(index)
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
        manifest = {'schema': SCHEMA, 'root': str(overlay), 'installed': installed,
                    'test_module': test_module, 'test_ids': ids, 'sources': rows, 'data': data,
                    'test_witness': witness, 'source_inventory': index['source_files'],
                    'archive': {'path': ARCHIVE, 'sha256': ARCHIVE_SHA, 'revision': REVISION, 'profile': PROFILE}}
        (overlay / 'manifest.json').write_bytes(canonical(manifest))
        script = ('import sys;sys.path[:0]=[sys.argv[1],sys.argv[1]+"/src",sys.argv[1]+"/tests"];'
                  'from tools.reference_pipeline_original_counterpart import child;child(sys.argv[1])')
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
    require(type(receipt) is dict and set(receipt) == {'manifest', 'modules', 'source_inventory', 'value', 'fresh_capture'},
            'Malformed original reference receipt')
    manifest = receipt['manifest']
    require(type(manifest) is dict and set(manifest) == {'schema', 'root', 'installed', 'test_module', 'test_ids',
            'sources', 'data', 'test_witness', 'source_inventory', 'archive'} and manifest['schema'] == SCHEMA,
            'Malformed original reference manifest')
    root = Path(manifest['root'])
    require(root.is_absolute(), 'Original reference root differs')
    require(manifest['installed'] == installed_authority(), 'Current installed reference package origin differs')
    require(manifest['archive'] == {'path': ARCHIVE, 'sha256': ARCHIVE_SHA, 'revision': REVISION, 'profile': PROFILE},
            'Original reference archive authority differs')
    ids = selection(manifest['test_module'], manifest['test_ids'])
    index = authority()
    sources, witness = source_closure(index)
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
    wanted = index['loaded_modules'] | {manifest['test_module']: TEST}
    require(type(modules) is dict and set(modules) == set(wanted), 'Original reference canonical module census differs')
    for name, module in modules.items():
        require(type(module) is dict and set(module) == {'logical', 'path', 'sha256', 'namespace'},
                'Malformed original reference module authority')
        logical = module['logical']
        require(logical in rows and module['path'] == rows[logical]['path'] and
                module['sha256'] == rows[logical]['sha256'] and module['namespace'] == name,
                'Original reference loaded module source differs')
        require(logical == wanted[name], 'Original reference module logical origin differs')
        if name == 'biocompiler' or name.startswith('biocompiler.'):
            require(logical.startswith('src/biocompiler/') and name == logical.removeprefix('src/').removesuffix('.py')
                    .replace('/', '.').removesuffix('.__init__'), 'Original reference product namespace differs')
    outcomes(receipt['value'], ids, manifest['test_module'] + '.' + CLASS)
    fresh = receipt['fresh_capture']
    require(type(fresh) is dict and set(fresh) == {'index', 'documents', 'runtime'}, 'Original fresh capture is incomplete')
    require(fresh['index'] == index and fresh['documents'] == index['documents'],
            'Original fresh complete capture differs')
    runtime = fresh['runtime']
    require(type(runtime) is dict and runtime['python'] == sys.version
            and runtime['source_files'] == index['source_files']
            and runtime['events_sha256'] == sha(canonical(index['events']))
            and len(runtime['original_tracebacks']) == 116,
            'Original fresh runtime authority differs')
    # Execute the pinned original raw-frame verifier, retaining every frame and
    # physical tail alias. It uses only these complete hash-bound graph roots.
    capture_path = local_file(ROOT, FREEZER)
    require(sha(capture_path.read_bytes()) == FREEZER_SHA, 'Frozen reference capture tool changed')
    spec = importlib.util.spec_from_file_location('_reference_original_runtime_validator', capture_path)
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    graphs = {row['after']: json.loads(local_file(ROOT,
        'tests/conformance/reference-pipeline-semantics-v1/' + row['after'] + '.json').read_bytes())
        for row in index['events'] if row['outcome'] == 'raise'}
    oracle.validate_runtime(runtime, index, graphs)
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
    archive, _ = source_archive()
    snapshot = archive['profiles'][PROFILE]['snapshot_files']
    require({row['logical']: row['sha256'] for row in manifest['sources'] if row['logical'] in snapshot} == snapshot,
            'Child source files differ from the exact archived snapshot')
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
    execution = {'test_ids': manifest['test_ids'], 'tests': result.testsRun, 'outcomes': result.outcomes}
    index = authority()
    original_class = getattr(module, CLASS)
    fresh_index, fresh_docs = original_class.fresh_index, original_class.fresh_docs
    inventory = fresh_index['source_files']
    require(inventory == index['source_files'], 'Original reference fresh source inventory differs')
    require(fresh_index == index and set(fresh_docs) == set(index['documents']), 'Original fresh complete capture differs')
    fresh_documents = {}
    for identity, value in fresh_docs.items():
        raw = canonical(value)
        require(sha(raw) == identity and len(raw) + 1 == index['documents'][identity],
                'Original fresh complete document differs')
        fresh_documents[identity] = len(raw) + 1
    runtime_path = overlay / ('generated/migration-next/reference-pipeline-runtime-' + str(sys.version_info.major)
                              + '.' + str(sys.version_info.minor) + '.json')
    runtime = json.loads(runtime_path.read_bytes())
    module.oracle.validate_runtime(runtime, index, fresh_docs)
    # Import precisely the original capture's modules to complete a deterministic
    # namespace census; none executes a producer, manager operation or checker.
    for name in index['loaded_modules']:
        importlib.import_module(name)
    rows = {row['logical']: row for row in manifest['sources']}
    modules = {}
    for name, loaded in tuple(sys.modules.items()):
        if name == 'biocompiler' or name.startswith('biocompiler.') or name in index['loaded_modules'] or name == manifest['test_module']:
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
        'source_inventory': inventory, 'value': execution,
        'fresh_capture': {'index': fresh_index, 'documents': fresh_documents, 'runtime': runtime}}))


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
    require(original is vars(importlib.import_module(module)).get(CLASS),
            'Original reference class is not the actual module class')
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
