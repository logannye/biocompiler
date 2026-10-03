"""Fresh original execution in an isolated canonical package, never in native state.

Only Python sources are copied. Reviewed manager and reference entry prefixes
are restored to their whole originals within each task's captured source scope;
all other bytes remain bound to the installed package. No compiled extensions,
build outputs or accepted state are imported.
"""
from __future__ import annotations
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from tools import manager_registration_source_lineage as lineage

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'biocompiler.original_manager_counterpart.v1'
FILES = (
    'tools/capture_pipeline_deferred_semantics.py',
    'tools/capture_pipeline_callback_semantics.py',
    'tools/capture_pipeline_identity_semantics.py',
    'tests/test_pipeline_callback_semantics.py',
    'tests/test_pipeline_identity_semantics.py',
    'tools/check_pipeline_deferred_runtime.py',
    'tools/check_pipeline_deferred_runtime_receipt.py',
    'tools/pipeline_original_counterpart.py',
    'tools/manager_registration_source_lineage.py',
    'tests/test_pipeline.py', 'tests/test_component_admission.py',
    'tests/test_pipeline_deferred_semantics.py',
    'tests/test_pipeline_deferred_runtime.py',
    'tests/test_pipeline_deferred_runtime_receipt.py',
)
DATA = ('tests/conformance/pipeline-callback-semantics-v1.json',
    'tests/conformance/pipeline-identity-semantics-v1.json',
    'tests/conformance/pipeline-deferred-semantics-v1.json',
    'tests/conformance/manager-registration-source-lineage-v1.json')
TEST_MODULES = ('test_pipeline_callback_semantics', 'test_pipeline_identity_semantics', 'test_pipeline_deferred_semantics', 'test_pipeline_deferred_runtime',
    'test_pipeline_deferred_runtime_receipt', 'test_pipeline_fixed_provider_semantics', 'test_pipeline_fixed_build_semantics', 'test_pipeline_contract_literals')
MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_OUTPUT_BYTES = 32 * 1024 * 1024
TASKS = ('deferred', 'callbacks', 'identity', 'tests', 'fixed-registration-original', 'fixed-provider-original', 'fixed-build-original')

def build_indexes():
    from tools.check_pipeline_session_install import INDEXES
    values=[]
    for name,pin in INDEXES.values():
        path='tests/conformance/'+name
        raw=(ROOT/path).read_bytes();value=json.loads(raw)
        require(value['inventory_fingerprint']==pin==lineage.sha(canonical({key:item for key,item in value.items()
            if key!='inventory_fingerprint'})), 'Original build source index differs')
        values.append((path,value))
    return values


def closure_task(task, test_module):
    if task == 'tests':
        name = test_module.removeprefix('tests.')
        if name == 'test_pipeline_fixed_provider_semantics': return 'fixed-provider-original'
        if name == 'test_pipeline_fixed_build_semantics': return 'fixed-build-original'
    return task


def reference_routes(task, test_module=None):
    if closure_task(task, test_module) != 'fixed-build-original':
        return {}
    from tools import reference_original_counterpart as reference
    return {path: reference.route_source_witness(path) for path in reference.ROUTE_SOURCES}


def task_files(task, test_module=None):
    original_task = task
    task = closure_task(task, test_module)
    files=list(FILES)
    if original_task == 'tests': files.append('tests/' + test_module.removeprefix('tests.') + '.py')
    if original_task == 'tests' and test_module.removeprefix('tests.') == 'test_pipeline_contract_literals':
        files.append('tools/capture_pipeline_contract_literals.py')
    if task.startswith('fixed-'):
        from tools.check_pipeline_fixed_registration_install import overlay_files
        files.extend(overlay_files())
    if task=='fixed-build-original':
        files.append('tools/realization_source_lineage.py')
        files.append('tools/reference_original_counterpart.py')
        for _,index in build_indexes(): files.extend(path for path in index['source_files'] if not path.startswith('src/'))
    return tuple(dict.fromkeys(files))


def task_data(task, test_module=None):
    task = closure_task(task, test_module)
    files=list(DATA)
    if task == 'tests' and test_module.removeprefix('tests.') == 'test_pipeline_contract_literals':
        files.append('tests/conformance/pipeline-contract-literals-v1.json')
    if task.startswith('fixed-'):
        files.extend((lineage.TOOL_WITNESS, 'tests/conformance/pipeline-fixed-build-semantics-v1.json'))
    if task == 'fixed-provider-original': files.append('tests/conformance/pipeline-fixed-provider-semantics-v1.json')
    if task == 'fixed-build-original': files.append('tests/conformance/pipeline-fixed-build-semantics-v1.json')
    if task=='fixed-build-original':
        from tools import reference_original_counterpart as reference
        files.append(reference.ROUTE_WITNESS)
        for path,index in build_indexes():
            files.extend((path,'tests/conformance/'+index['full_corpus']['path']))
            files.extend('tests/conformance/'+index['provider_directory']+'/'+entry['id']+'.json'
                for entry in index['provider_documents'])
    return tuple(dict.fromkeys(files))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def run(task='deferred', *, test_module=None, test_ids=None):
    require(task in TASKS, 'Unknown original counterpart task')
    require((task == 'tests' and test_module.removeprefix('tests.') in TEST_MODULES and type(test_ids) is list and test_ids and len(set(test_ids)) == len(test_ids)) or (task != 'tests' and test_module is None),
        'Unknown original counterpart test module')
    package = importlib.import_module('biocompiler')
    package_root = Path(package.__file__).resolve().parent
    original = lineage.original_source()
    route = lineage.verify_source(ROOT, lineage.PATH, lineage.HISTORICAL[lineage.PATH])
    package_route = (package_root / 'compiler/pipeline.py').read_bytes()
    require(package_route == (ROOT / lineage.PATH).read_bytes(), 'Installed original counterpart source differs')
    sources = {}
    for path in sorted(package_root.rglob('*.py')):
        require(not path.is_symlink() and path.resolve().is_relative_to(package_root),
            'Original counterpart package source escapes installed root')
        logical = 'src/biocompiler/' + path.relative_to(package_root).as_posix()
        sources[logical] = (path, path.read_bytes())
    for logical in task_files(task, test_module):
        path = ROOT / logical
        sources[logical] = (path, path.read_bytes())
    tool_route = lineage.verify_tool_source(sources[lineage.TOOL_PATH][1]) if lineage.TOOL_PATH in sources else None
    routes = reference_routes(task, test_module)
    for logical, (_, proof) in routes.items():
        require(lineage.sha(sources[logical][1]) == proof['correspondence']['current_sha256'],
            'Installed reference entry source differs from its reviewed counterpart')
    require(sum(len(raw) for _, raw in sources.values()) <= MAX_SOURCE_BYTES,
        'Original counterpart source copy exceeds closed bound')
    with tempfile.TemporaryDirectory(prefix='biocompiler-original-counterpart-') as directory:
        overlay = Path(directory).resolve()
        rows = []
        for logical, (path, raw) in sorted(sources.items()):
            copied = original if logical == lineage.PATH else lineage.original_tool_source() if logical == lineage.TOOL_PATH else routes[logical][0] if logical in routes else raw
            target = overlay / logical
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(copied)
            rows.append({'logical': logical, 'origin': str(path), 'origin_sha256': lineage.sha(raw),
                'path': str(target), 'sha256': lineage.sha(copied), 'substituted': copied != raw})
        data=[]
        for logical in task_data(task, test_module):
            target = overlay / logical
            target.parent.mkdir(parents=True, exist_ok=True)
            os.link(ROOT / logical, target)
            data.append({'logical':logical,'sha256':lineage.sha((ROOT/logical).read_bytes())})
        manifest = {'schema': SCHEMA, 'task': task, 'test_module': test_module, 'test_ids': test_ids,
            'root': str(overlay), 'package_root': str(package_root), 'route': route, 'tool_route':tool_route,
            'reference_routes': {path: proof for path, (_, proof) in routes.items()}, 'sources': rows, 'data':data}
        (overlay / 'manifest.json').write_bytes(canonical(manifest))
        result = overlay / 'result.json'
        script = ('import sys;sys.path[:0]=[sys.argv[1],sys.argv[1]+"/src",sys.argv[1]+"/tests"];'
            'from tools.pipeline_original_counterpart import child;child(sys.argv[1])')
        environment = dict(os.environ)
        environment.pop('PYTHONPATH', None)
        environment['PYTHONDONTWRITEBYTECODE'] = '1'
        completed = subprocess.run([sys.executable, '-I', '-c', script, str(overlay)],
            cwd=directory, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
        require(completed.returncode == 0, 'Original counterpart child failed: ' +
            completed.stderr.decode(errors='replace')[-12000:])
        require(result.is_file() and result.stat().st_size <= MAX_OUTPUT_BYTES,
            'Original counterpart output missing or too large')
        value = json.loads(result.read_bytes())
        validate(value)
        return value


def validate(value):
    require(type(value) is dict and set(value) == {'manifest', 'modules', 'value'},
        'Malformed original counterpart result')
    manifest = value['manifest']
    require(set(manifest) == {'schema', 'task', 'test_module', 'test_ids', 'root', 'package_root', 'route', 'tool_route', 'reference_routes', 'sources', 'data'}
        and manifest['schema'] == SCHEMA and manifest['task'] in TASKS,
        'Malformed original counterpart manifest')
    root = Path(manifest['root'])
    require(root.is_absolute() and type(manifest['sources']) is list, 'Original counterpart root differs')
    require(manifest['data']==[{'logical':path,'sha256':lineage.sha((ROOT/path).read_bytes())} for path in task_data(manifest['task'], manifest['test_module'])],
        'Original counterpart data closure differs')
    routes = reference_routes(manifest['task'], manifest['test_module'])
    require(manifest['reference_routes'] == {path: proof for path, (_, proof) in routes.items()},
        'Original counterpart reference entry correspondence differs')
    rows = {}
    for row in manifest['sources']:
        require(set(row) == {'logical', 'origin', 'origin_sha256', 'path', 'sha256', 'substituted'}
            and row['logical'] not in rows, 'Original counterpart source census differs')
        logical = row['logical']
        require(logical in task_files(manifest['task'], manifest['test_module']) or logical.startswith('src/biocompiler/') and logical.endswith('.py'),
            'Unreviewed original counterpart file')
        require('..' not in Path(logical).parts and row['path'] == str(root / logical),
            'Original counterpart source path differs')
        raw = (ROOT / logical).read_bytes()
        require(row['origin_sha256'] == lineage.sha(raw), 'Original counterpart origin bytes differ')
        wanted = lineage.original_source() if logical == lineage.PATH else lineage.original_tool_source() if logical == lineage.TOOL_PATH else routes[logical][0] if logical in routes else raw
        require(row['sha256'] == lineage.sha(wanted) and row['substituted'] is (wanted != raw),
            'Original counterpart substitution differs')
        if logical.startswith('src/'):
            require(row['origin'] == str(Path(manifest['package_root']) / logical.removeprefix('src/biocompiler/')),
                'Original counterpart installed source origin differs')
        else:
            require(Path(row['origin']).name == Path(logical).name, 'Original counterpart tool origin differs')
        rows[logical] = row
    expected = set(task_files(manifest['task'], manifest['test_module'])) | {'src/biocompiler/' + path.relative_to(ROOT / 'src/biocompiler').as_posix()
        for path in (ROOT / 'src/biocompiler').rglob('*.py')}
    require(set(rows) == expected, 'Original counterpart complete source census differs')
    require(manifest['tool_route'] == (lineage.verify_tool_source((ROOT/lineage.TOOL_PATH).read_bytes())
        if lineage.TOOL_PATH in expected else None), 'Original counterpart helper source lineage differs')
    require(manifest['route'] == lineage.verify_source(ROOT, lineage.PATH, lineage.HISTORICAL[lineage.PATH]),
        'Original counterpart routed source lineage differs')
    modules = value['modules']
    require(type(modules) is dict and 'biocompiler.compiler.pipeline' in modules, 'Original canonical module absent')
    for name, module in modules.items():
        logical = module['logical']
        require(set(module) == {'logical', 'path', 'sha256', 'namespace'} and logical in rows
            and module['path'] == rows[logical]['path'] and module['sha256'] == rows[logical]['sha256']
            and module['namespace'] == name, 'Original product module provenance differs')
        derived = logical.removeprefix('src/').removesuffix('.py').replace('/', '.')
        require(name == derived.removesuffix('.__init__'), 'Original module is not in its canonical namespace')
    return value['value']


def child(directory):
    overlay = Path(directory).resolve()
    manifest = json.loads((overlay / 'manifest.json').read_bytes())
    rows = {row['logical']: row for row in manifest['sources']}
    require(str(ROOT) == str(overlay), 'Original counterpart runner escaped overlay')
    for logical, row in rows.items():
        require(row['path'] == str(overlay / logical) and lineage.sha((overlay / logical).read_bytes()) == row['sha256'],
            'Original counterpart copied bytes differ')
    for row in manifest['data']:
        require(lineage.sha((overlay/row['logical']).read_bytes())==row['sha256'], 'Original counterpart data bytes differ')
    require((overlay / lineage.PATH).read_bytes() == lineage.original_source(), 'Original manager substitution missing')
    if lineage.TOOL_PATH in rows:
        require((overlay/lineage.TOOL_PATH).read_bytes()==lineage.original_tool_source(), 'Original helper substitution missing')
    for logical, proof in manifest['reference_routes'].items():
        require(lineage.sha((overlay / logical).read_bytes()) == proof['correspondence']['original_sha256'],
            'Original reference entry substitution missing')
    if manifest['task'] == 'deferred':
        from tools import capture_pipeline_deferred_semantics as oracle
        from tools import check_pipeline_deferred_runtime as runtime
        from tools import check_pipeline_deferred_runtime_receipt as receipt
        frozen = json.loads(oracle.OUTPUT.read_bytes())
        current = oracle.capture()
        proof = runtime.compare_current(frozen, current, oracle=oracle)
        proof['capture_authority'] = receipt.capture_authority(oracle=oracle)
        receipt.validate_retained(frozen, current, proof, python_version=proof['capture_authority']['python_version'])
        value = {'capture': current, 'proof': proof}
    elif manifest['task'].startswith('fixed-'):
        if manifest['task']=='fixed-registration-original':
            from tools.check_pipeline_fixed_registration_install import capture_original
            value=capture_original()
        else:
            suffix='provider' if manifest['task']=='fixed-provider-original' else 'build'
            oracle=importlib.import_module('tools.capture_pipeline_fixed_'+suffix+'_semantics')
            value=oracle.capture()
    elif manifest['task'] in ('callbacks', 'identity'):
        name = 'callback' if manifest['task'] == 'callbacks' else 'identity'
        oracle = importlib.import_module('tools.capture_pipeline_' + name + '_semantics')
        value = oracle.capture()
        require(value == json.loads(oracle.OUTPUT.read_bytes()), 'Complete original counterpart differs')
    else:
        import unittest
        require(manifest['test_module'].removeprefix('tests.') in TEST_MODULES, 'Unknown original test module')
        suite = unittest.defaultTestLoader.loadTestsFromName(manifest['test_module'])
        def flatten(items):
            for item in items:
                if isinstance(item, unittest.TestSuite): yield from flatten(item)
                else: yield item
        discovered = list(flatten(suite))
        wanted = manifest['test_ids']
        selected = [case for case in discovered if case.id() in wanted]
        require([case.id() for case in selected] == wanted and
            len({type(case) for case in selected}) == 1, 'Original selected test class census differs')
        class RetainedResult(unittest.TextTestResult):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs); self.outcomes=[]
            def retain(self, test, status, detail=None):
                self.outcomes.append({'id':test.id(), 'class':type(test).__module__+'.'+type(test).__qualname__,
                    'status':status, 'detail':detail})
            def addSuccess(self, test):
                super().addSuccess(test);self.retain(test,'success')
            def addError(self, test, error):
                super().addError(test,error);self.retain(test,'error',self._exc_info_to_string(error,test))
            def addFailure(self, test, error):
                super().addFailure(test,error);self.retain(test,'failure',self._exc_info_to_string(error,test))
            def addSkip(self, test, reason):
                super().addSkip(test,reason);self.retain(test,'skipped',reason)
            def addExpectedFailure(self, test, error):
                super().addExpectedFailure(test,error);self.retain(test,'expected-failure',self._exc_info_to_string(error,test))
            def addUnexpectedSuccess(self, test):
                super().addUnexpectedSuccess(test);self.retain(test,'unexpected-success')
        result = unittest.TextTestRunner(stream=sys.stderr,resultclass=RetainedResult).run(unittest.TestSuite(selected))
        value = {'test_ids':wanted, 'tests':result.testsRun, 'outcomes':result.outcomes}
    modules = {}
    for name, module in tuple(sys.modules.items()):
        if name == 'biocompiler' or name.startswith('biocompiler.'):
            path = Path(module.__file__).resolve()
            require(path.is_relative_to(overlay / 'src/biocompiler') and vars(module).get('__name__') == name,
                'Original product import escaped its canonical overlay namespace')
            logical = path.relative_to(overlay).as_posix()
            require(logical in rows and lineage.sha(path.read_bytes()) == rows[logical]['sha256'],
                'Original product import has unreviewed bytes')
            modules[name] = {'logical': logical, 'path': str(path), 'sha256': rows[logical]['sha256'], 'namespace': name}
    (overlay / 'result.json').write_bytes(canonical({'manifest': manifest, 'modules': modules, 'value': value}))


def validate_test_outcomes(value, ids, classname):
    require(type(value) is dict and set(value) == {'test_ids','tests','outcomes'}
        and value['test_ids'] == ids and value['tests'] == len(ids) and type(value['outcomes']) is list,
        'Original per-test execution census differs')
    require([row['id'] for row in value['outcomes']] == ids and len(set(ids)) == len(ids),
        'Original per-test outcomes are missing, duplicated or reordered')
    for row in value['outcomes']:
        require(set(row) == {'id','class','status','detail'} and row['class'] == classname
            and row['status'] in ('success','failure','error','skipped','expected-failure','unexpected-success')
            and (row['detail'] is None or type(row['detail']) is str), 'Malformed original test outcome')
    return {row['id']:row for row in value['outcomes']}


def original_test_suite(loader, tests, pattern, module):
    """Keep actual discovered classes/instances and forward fresh child results."""
    if not lineage.routed():
        return tests
    import unittest
    from types import MethodType
    require(module.removeprefix('tests.') in TEST_MODULES, 'Unreviewed original test bridge module')
    def flatten(items):
        for item in items:
            if isinstance(item, unittest.TestSuite): yield from flatten(item)
            else: yield item
    classes={}
    for case in flatten(tests): classes.setdefault(type(case),[]).append(case)
    result=[]
    for original, cases in classes.items():
        require(original.__module__.removeprefix('tests.') == module.removeprefix('tests.') and 'tearDownClass' not in vars(original),
            'Original class fixture scope changed')
        ids=[case.id() for case in cases]
        classname=original.__module__+'.'+original.__qualname__
        def setup(cls, ids=ids, classname=classname, module=original.__module__):
            receipt=run('tests',test_module=module,test_ids=ids)
            cls._original_receipt=receipt
            cls._original_outcomes=validate_test_outcomes(receipt['value'],ids,classname)
        # Only the parent execution bridge changes. The child imports untouched
        # class bodies, runs their real fixtures and returns each exact outcome.
        original.setUpClass=classmethod(setup)
        def execute(self, result=None):
            own=result is None
            if own:
                result=self.defaultTestResult()
                result.startTestRun()
            result.startTest(self)
            try:
                row=type(self)._original_outcomes[self.id()]
                require(row['id']==self.id(), 'Original child result belongs to another test')
                status,detail=row['status'],row['detail']
                if status=='success': result.addSuccess(self)
                elif status=='skipped': result.addSkip(self,detail)
                elif status=='unexpected-success': result.addUnexpectedSuccess(self)
                else:
                    error=RuntimeError(detail) if status=='error' else AssertionError(detail)
                    info=(type(error),error,None)
                    if status=='error': result.addError(self,info)
                    elif status=='failure': result.addFailure(self,info)
                    else: result.addExpectedFailure(self,info)
            finally:
                result.stopTest(self)
                if own: result.stopTestRun()
            return result
        for case in cases:
            case.run=MethodType(execute,case)
            result.append(case)
    return unittest.TestSuite(result)


def metadata_correspondence(current, counterpart):
    """Two full executions, one exact source-metadata difference, no state import."""
    old=validate(counterpart)
    require(counterpart['manifest']['task'] in ('fixed-provider-original','fixed-build-original','callbacks'),
        'Source metadata correspondence has no closed original task')
    require(type(current) is dict and set(current)==set(old) and
        type(current.get('source_files')) is dict and type(old.get('source_files')) is dict,
        'Original/current complete capture shapes differ')
    for document in (current,old):
        require(document.get('inventory_fingerprint')==lineage.sha(canonical({key:value for key,value in document.items()
            if key!='inventory_fingerprint'})), 'Complete original/current capture inventory differs')
    require(set(current['source_files'])==set(old['source_files']), 'Original/current source census differs')
    for path,pin in old['source_files'].items():
        observed=current['source_files'][path]
        require(observed==lineage.sha((ROOT/path).read_bytes()), 'Current capture source differs from actual bytes')
        if path==lineage.PATH:
            lineage.verify_source(ROOT,path,pin)
        elif path==lineage.TOOL_PATH:
            lineage.verify_tool_source((ROOT/path).read_bytes(),pin)
        else:
            require(observed==pin, 'Unreviewed current capture metadata difference')
    historical={key:value for key,value in old.items() if key not in ('source_files','inventory_fingerprint')}
    actual={key:value for key,value in current.items() if key not in ('source_files','inventory_fingerprint')}
    require(canonical(actual)==canonical(historical), 'Complete original/current execution differs outside exact source metadata')
    return {'schema':'biocompiler.manager_registration_capture_counterpart.v1',
        'lineage':lineage.verify_source(ROOT,lineage.PATH,old['source_files'][lineage.PATH]),
        'tool_lineage':lineage.verify_tool_source((ROOT/lineage.TOOL_PATH).read_bytes(),old['source_files'][lineage.TOOL_PATH])
            if lineage.TOOL_PATH in old['source_files'] else None,
        'original_inventory':old['inventory_fingerprint'],'current_inventory':current['inventory_fingerprint'],
        'complete_body_sha256':lineage.sha(canonical(historical))}
