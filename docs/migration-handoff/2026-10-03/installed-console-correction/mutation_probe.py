"""In-memory regression mutants only; production/test files remain unchanged."""
import hashlib,inspect,json,sys,types,unittest
from pathlib import Path
from unittest.mock import patch
from tests import test_prebuilt_release_chain as tests
pipeline=tests.pipeline
source=inspect.getsource(pipeline.installed)
prepend="    env['PATH'] = str(python.parent) + os.pathsep + env.get('PATH', os.defpath)\n"
assert source.count(prepend)==1
start="        require(shutil.which('biocompiler',path=env['PATH']) == str(console),\n                'Fresh installed console script missing')\n"
assert source.count(start)==1
rows=[]
for name,old,test in [
    ('missing_path_prepend',prepend,'test_installed_dispatch_selects_fresh_console_for_complete_lifecycle_and_campaigns'),
    ('missing_exact_console_guard',start,'test_missing_or_nonexecutable_fresh_console_rejects_host_fallback_before_campaigns')]:
    changed=source.replace(old,'',1);namespace={}
    exec(compile(changed,'<in-memory installed '+name+'>','exec'),namespace)
    mutant=types.FunctionType(namespace['installed'].__code__,vars(pipeline),'installed')
    result=unittest.TestResult()
    with patch.object(pipeline,'installed',mutant):tests.HostedPlanTests(test).run(result)
    expected=(1,1) if name=='missing_path_prepend' else (2,0)
    assert result.testsRun==1 and (len(result.failures),len(result.errors))==expected,(name,result.testsRun,result.failures,result.errors)
    if result.errors:assert len(result.errors)==1 and "KeyError: 'PATH'" in result.errors[0][1]
    rows.append({'mutation':name,'test':test,'tests_run':result.testsRun,'rejected_subtests':len(result.failures)+len(result.errors),
        'assertion_failures':len(result.failures),'missing_path_errors':len(result.errors),
        'diagnostics':[failure for _,failure in result.failures+result.errors]})
print(json.dumps({'schema':'biocompiler.installed_console_mutation_controls.v1','python_version':sys.version.split()[0],
    'status':'pass','production_installed_source_sha256':hashlib.sha256(source.encode()).hexdigest(),
    'scope':'Only the selected installed() function is replaced in memory; all process/install calls are mocked by tests. No source overwrite/native/build execution.',
    'controls':rows},indent=2,sort_keys=True))
