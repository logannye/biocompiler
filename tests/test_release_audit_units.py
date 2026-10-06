"""Independent literal unit-record checks promoted from the exercised audit."""
from pathlib import Path
import ast
import copy
import hashlib
import json
import unittest
from tools import release_audit_units as audit
ROOT = Path(__file__).resolve().parents[1]


def run_controls():
    if not __debug__:
        raise RuntimeError('Literal audit controls require enabled assertions')
    def digest(v):
        return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()).hexdigest()
    def encoded(v):
        return json.dumps(v,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()

    protocol = (ROOT/'tools/test_shards.py').read_bytes()
    weights = (ROOT/'tools/test_shard_weights.json').read_bytes()
    source = {'tools/test_shards.py':hashlib.sha256(protocol).hexdigest(),
              'tools/test_shard_weights.json':hashlib.sha256(weights).hexdigest(),
              'tests/test_synthetic_only.py':'4'*64}
    authority = {'head_revision':'1'*40,'revision':'2'*40,'head_tree':'3'*40,'tree':'3'*40,'run_id':123,'run_attempt':1}
    classes = {f'synthetic.C{i}':[f'synthetic.C{i}.test_only'] for i in range(5)}
    ids = [f'synthetic.C{i}.test_only' for i in range(5)]
    # Independently literal equal-weight scheduling: five equal classes occupy the
    # five index-ordered buckets exactly once. No checker scheduling output reused.
    assignments = [{'index':i,'class_ids':[f'synthetic.C{i}'],'test_ids':[ids[i]],'estimated_seconds':2.0} for i in range(5)]
    statuses = ['success','skipped','expected_failure','success','success']


    def fixture():
        artifacts = {}; number=0
        def put(name, member, value):
            nonlocal number
            number += 1
            artifacts[name] = {'files':{member:encoded(value)},'provenance':{
                **{k:authority[k] for k in ('head_revision','revision','run_id','run_attempt')},
                'artifact_id':number,'zip_sha256':f'{number:064x}'}}
        for minor,version in [('3.11','3.11.15'),('3.14','3.14.6')]:
            env = {'revision':authority['revision'],'python':version,'implementation':'CPython'}
            discovery={'start_directory':'tests','pattern':'test*.py','test_ids':ids,'classes':classes,'source_files':source}
            discovery['digest']=digest(discovery)
            plan={'schema':'biocompiler.unittest_shard_plan.v1','environment':env,'discovery':discovery,'shard_count':5,'weights_digest':digest(json.loads(weights)),'shards':assignments}
            plan['fingerprint']=digest(plan)
            put(f'unit-plan-py{minor}','plan.json',plan)
            results=[]
            for i,status in enumerate(statuses):
                class_id=f'synthetic.C{i}'
                record={'id':ids[i],'class_id':class_id,'status':status,'seconds':.25,'subtests':[{'id':f'{ids[i]} (literal=1)','status':status}]}
                summary={'tests':1,'seconds':.375,'test_seconds':.25,'fixture_seconds':.125,'statuses':{status:1}}
                result={'schema':'biocompiler.unittest_shard_result.v1','plan_fingerprint':plan['fingerprint'],'environment':env,'discovery_digest':discovery['digest'],'shard_index':i,'status':'success','selected_ids':[ids[i]],'tests':[record],'classes':{class_id:summary},'class_fixture_seconds':{class_id:.125},'fixture_errors':[],'errors':[],'elapsed_seconds':1.0}
                results.append(result);put(f'unit-result-py{minor}-shard-{i}',f'shard-{i}.json',result)
            account={'schema':'biocompiler.unittest_shard_accounting.v1','status':'pass','environment':env,'revision':env['revision'],'python_version':version,'total_tests':5,'shard_count':5,'shard_seconds':{str(i):1.0 for i in range(5)},'plan_fingerprint':plan['fingerprint'],'discovery_digest':discovery['digest'],'expected_shards':5,'verified_shards':[0,1,2,3,4],'discovered_count':5,'executed_count':5,'executed_ids':ids,'result_digests':sorted(digest(r) for r in results)}
            put(f'unit-accounting-py{minor}',f'accounting-py{minor}.json',account)
        return artifacts


    def verify(artifacts, **overrides):
        kwargs={'authority':authority,'expected_source_inventory':source,'shard_protocol_source':protocol,'weights_source':weights}
        kwargs.update(overrides)
        return audit.audit_unit_evidence(artifacts,**kwargs)

    def change(artifacts,name,fn):
        member=next(iter(artifacts[name]['files'])); value=json.loads(artifacts[name]['files'][member]);fn(value)
        artifacts[name]['files'][member]=encoded(value)
    def result_change(a,fn): change(a,'unit-result-py3.11-shard-0',fn)
    def plan_change(a,fn):
        def edit(p):
            fn(p);p['discovery']['digest']=digest({k:v for k,v in p['discovery'].items() if k!='digest'})
            p['fingerprint']=digest({k:v for k,v in p.items() if k!='fingerprint'})
        change(a,'unit-plan-py3.11',edit)

    base=fixture(); positive=verify(base)
    assert len(positive['versions'])==2
    assert all(v['statuses']=={'expected_failure':1,'skipped':1,'success':3} and v['subtest_statuses']==v['statuses'] for v in positive['versions'])
    rejections=[]
    def negative(name,mutation=None,**kwargs):
        a=copy.deepcopy(base)
        if mutation:mutation(a)
        try:verify(a,**kwargs)
        except (AssertionError,ValueError,UnicodeError,TypeError,KeyError) as exc:rejections.append({'name':name,'rejection':str(exc)})
        else:raise AssertionError('Mutation accepted: '+name)
    negative('missing_artifact',lambda a:a.pop('unit-plan-py3.11'))
    negative('extra_artifact',lambda a:a.update(extra=copy.deepcopy(a['unit-plan-py3.11'])))
    negative('extra_member',lambda a:a['unit-plan-py3.11']['files'].update(extra=b'{}'))
    for key,value in [('run_id',124),('run_attempt',2),('head_revision','5'*40),('revision','6'*40)]:
        negative('foreign_'+key,lambda a,k=key,v=value:a['unit-plan-py3.11']['provenance'].__setitem__(k,v))
    negative('duplicate_artifact_id',lambda a:a['unit-plan-py3.14']['provenance'].__setitem__('artifact_id',a['unit-plan-py3.11']['provenance']['artifact_id']))
    for version in ['3.11.15\n','3.11.*','3.011.15','3.11.15rc1','3.14.6']:
        negative('invalid_version_'+repr(version),lambda a,v=version:plan_change(a,lambda p:p['environment'].__setitem__('python',v)))
    negative('wrong_implementation',lambda a:plan_change(a,lambda p:p['environment'].__setitem__('implementation','PyPy')))
    negative('patch_drift_result',lambda a:result_change(a,lambda r:r['environment'].__setitem__('python','3.11.16')))
    negative('rehash_changed_source',lambda a:plan_change(a,lambda p:p['discovery']['source_files'].__setitem__('tests/test_synthetic_only.py','5'*64)))
    negative('duplicate_class_membership',lambda a:plan_change(a,lambda p:p['discovery']['classes']['synthetic.C1'].append(ids[0])))
    negative('class_membership_omission',lambda a:plan_change(a,lambda p:p['discovery']['classes'].pop('synthetic.C4')))
    negative('rehashed_assignment_reorder',lambda a:plan_change(a,lambda p:p['shards'].reverse()))
    negative('rehashed_weight_change',lambda a:plan_change(a,lambda p:p['shards'][0].__setitem__('estimated_seconds',3.0)))
    negative('missing_test',lambda a:result_change(a,lambda r:r['tests'].clear()))
    negative('duplicate_test',lambda a:result_change(a,lambda r:r['tests'].append(copy.deepcopy(r['tests'][0]))))
    negative('extra_test',lambda a:result_change(a,lambda r:r['tests'][0].__setitem__('id','foreign.C.test_x')))
    negative('wrong_class',lambda a:result_change(a,lambda r:r['tests'][0].__setitem__('class_id','synthetic.C1')))
    negative('failed_test',lambda a:result_change(a,lambda r:r['tests'][0].__setitem__('status','failure')))
    negative('failed_subtest',lambda a:result_change(a,lambda r:r['tests'][0]['subtests'][0].__setitem__('status','failure')))
    negative('boolean_time',lambda a:result_change(a,lambda r:r['tests'][0].__setitem__('seconds',True)))
    negative('fixture_error',lambda a:result_change(a,lambda r:r['fixture_errors'].append('setUpClass')))
    negative('class_summary_tamper',lambda a:result_change(a,lambda r:r['classes']['synthetic.C0'].__setitem__('seconds',.5)))
    negative('result_digest_tamper',lambda a:change(a,'unit-accounting-py3.11',lambda p:p['result_digests'].__setitem__(0,'f'*64)))
    negative('account_count_drift',lambda a:change(a,'unit-accounting-py3.11',lambda p:p.__setitem__('total_tests',4)))
    negative('tree_mismatch',authority={**authority,'tree':'4'*40})
    negative('protocol_source_changed',shard_protocol_source=protocol+b'\n')
    negative('weights_source_changed',weights_source=weights+b'\n')
    negative('duplicate_json_key',lambda a:a['unit-plan-py3.11']['files'].__setitem__('plan.json',b'{"schema":1,"schema":2}'))
    negative('nonfinite_json',lambda a:a['unit-plan-py3.11']['files'].__setitem__('plan.json',b'{"x":NaN}'))
    # Verify copied exact body and all documentary anchors without importing tools.
    def bodies(raw):
        text=raw.decode(); tree=ast.parse(text)
        return {n.name:ast.get_source_segment(text,n) for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
    original=bodies(protocol); helper_source=(ROOT/'tools/release_audit_units.py').read_bytes(); copied=bodies(helper_source)
    for name,pin in audit.COPIED_FUNCTIONS.items():
        assert copied[name]==original[name] and hashlib.sha256(original[name].encode()).hexdigest()==pin
    for name,pin in audit.REVIEWED_FUNCTIONS.items():
        assert hashlib.sha256(original[name].encode()).hexdigest()==pin
    report={'schema':'pr85.unit_audit_synthetic_selfcheck.v1','status':'pass','scope':'Only independently literal synthetic retained records. No hosted final audit, project discovery, native execution or network.', 'helper_sha256':hashlib.sha256(helper_source).hexdigest(),'selfcheck_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'positive_cases':1,'negative_cases':len(rejections),'allowed_status_counts':positive['versions'][0]['statuses'],'copied_body_checks':'exact','rejections':rejections}
    return report


class ReleaseAuditUnitTests(unittest.TestCase):
    def test_complete_literal_evidence_and_36_rejection_controls(self):
        report = run_controls()
        self.assertEqual(report["positive_cases"], 1)
        self.assertEqual(report["negative_cases"], 36)
        self.assertEqual(report["status"], "pass")
