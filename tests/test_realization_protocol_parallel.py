"""Pure role-worker controls. No executable campaign or native process runs."""
import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import realization_protocol_parallel as p
from tools import check_realization_protocol as campaign
from tools import check_realization_reproducibility as checker
from tests import test_realization_reproducibility as fixtures


# Exact original function bytes at 1a8f775; these are preserved, not regenerated.
PROTOCOL_BODY_PINS = {'transport_only': '022ca8782eb7d8a38503febb30da43892f90c12973afc995a7328d1bcaff49bc', 'check_result': 'a02f15d9c97f854d36b987ca508624b3847a6549c8fae0ffeb97003a79a27769', 'invoke': 'c4bef49af25a4e41a093524509a3260d47b3af6e661e93688328888706bfc2f6', 'rejected': '914d3e003cbc08974a07fcdd8a54f36d2acaf28ebcb9cd97bb728551e21e9221', 'artifact': '96eb7b61cfe9ed9664d13cc6a1c1a748abb49bfb7240ce1a082ec8681b2a84cc', 'campaign': '537c83d778f4003a002837996d3bb9e4517919449942a16dcbba8713b7a9c04b', 'boundary_campaign': 'ad67e40302b85669d465353eff808e28855df716b7aeecd076efd7260ad2b983'}
ROUTING_BODY_PINS = {'_named': '6753c49d1a6b3a08e747d444fd062e1a72988e77d3507f9011f8ebb8e9e453a2', 'allowed_frame': 'af1adf1555a61aeae8f4472ec66a4d0494cdcec1a0560482a2080577828d1a13', 'routed_execution': 'c3e3c121bb269adc84247dc7b4231fa2c35bc9920d348d72f954f1d78e1a7edd', 'hydrate': '320ebea2718a1bdaf483aeaade5dc55727f431a78a137a257b84f030d573878e', 'sdk_function': 'd7fcce60cd98b82d8187ed6560600e70cc83da475195da9651f6442e8689dde3', 'campaign': '0b4e7e7da24d84b4e7558418487bfafda1d2fd6a533a5dc9c8c7dbb589c94429'}


class ProtocolRoleTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.golden = fixtures.RealizationReproducibilityTests().golden_small()
        self.parts = {role:self.root/'protocol-workers'/role for role in p.ROLES}
        self.receipt = {'schema_version':'biocompiler.realization_protocol_conformance.v1','status':'running',
                        'revision':'a'*40,'source_revision':'b'*40,'run_id':'77',
                        'platform':'fixture-linux','system':'Linux','machine':'x86_64','python_version':'3.11.9',
                        'package_path':'/installed/biocompiler/__init__.py','corpus_pin':checker.CORPUS_PIN,
                        'baseline_pin':checker.BASE_PIN,'scope':'direct_operations_only_no_workflow_archive_or_export_migration',
                        'executables':{role:{'path':'/installed/bin/'+role,'sha256':('c' if role=='core' else 'd')*64} for role in p.ROLES},
                        'checks':[]}
        self.receipt['campaign_sources']=checker.scheduler_sources()
        self.output = self.root/'protocol-reports'; self.output.mkdir()
        self.make_parts(self.golden)

    def envelope(self,case,error,operation,replay,golden):
        if error:
            return {'status':'error','result':None,'diagnostics':[{'code':error['code'],
                    'message':error.get('message','Explicit fixture rejection.'),'path':None}]}
        report = golden.document(case['result']); profile = golden.profiles[checker.APIS[case['api']][0]]
        dependency = operation == 'realization-dependencies'; label = 'dependencies' if dependency else 'assessment'
        encoding = profile['dependency_encoding' if dependency else 'assessment_encoding']
        _,payload = golden.payload(case,replay)
        value = {key:profile['dependency_'+key if dependency and key in ('validation_scope','claim_scope') else key]
                 for key in ('profile','implementation','service_implementation','validation_scope','claim_scope')}
        value.update(schema_version=profile['result_schemas'][operation],resource_profile=profile['resources']['protocol']['profile'],
                     resources=profile['resources'],supplied_authority_fingerprint=checker.digest({k:v for k,v in payload.items() if k!='assessment'}),
                     authority_identities=case['authority_identities'])
        value.update({label:report,label+'_fingerprint':checker.digest(report,ascii=encoding=='python-json-ascii-v1')})
        return value

    def make_parts(self,golden):
        kind=p.mode(self.receipt)
        by_role = {role:deepcopy(self.receipt) for role in p.ROLES}
        for role,receipt in by_role.items():
            directory=self.parts[role]; directory.mkdir(parents=True,exist_ok=True)
            reports=directory/'receipt-reports';reports.mkdir(exist_ok=True)
            (directory/'worker.log').write_text(role+' complete diagnostic\n')
            receipt.update(schema_version=f'biocompiler.realization_{kind}_role.v1',status='success',role=role,artifact_directory='receipt-reports',artifacts={})
        for (role,identity,operation),(case,error,replay) in golden.expected(kind).items():
            value=self.envelope(case,error,operation,replay,golden)
            if kind=='routing' and not error:value=golden.document(case['result'])
            pin=checker.digest(value)
            receipt=by_role[role];raw=checker.canonical(value)+b'\n'
            (self.parts[role]/'receipt-reports'/(pin+'.json')).write_bytes(raw)
            receipt['artifacts'][pin]={'path':pin+'.json','bytes':len(raw),'canonical_sha256':pin}
            row={'role':role,'id':identity,'operation':operation,'artifact':pin}
            if error:row['error']=error['code']
            elif kind=='routing':
                profile=golden.profiles[checker.APIS[case['api']][0]];dependency=operation=='realization-dependencies'
                encoding=profile['dependency_encoding' if dependency else 'assessment_encoding']
                row.update(report=checker.digest(value,ascii=encoding=='python-json-ascii-v1'),outcome=None if dependency else value['outcome'])
            else:
                label='dependencies' if operation=='realization-dependencies' else 'assessment'
                row.update(authority=value['supplied_authority_fingerprint'],outcome=None if label=='dependencies' else value[label]['outcome'])
                row[label]=value[label+'_fingerprint']
            receipt['checks'].append(row)
        for role,receipt in by_role.items():
            if kind=='routing':receipt['guard']={'status':'passed','allowed_executed_functions':sorted(checker.REQUIRED_ROUTES),
                'input_hydration':'outside_guard_before_native_call','snapshot_request_rehydration':'forbidden_during_native_call'}
            receipt['completed_checks']=len(receipt['checks']);self.write(self.parts[role]/'receipt.json',receipt)
        return by_role

    @staticmethod
    def write(path,value):path.write_bytes(checker.canonical(value)+b'\n')

    def merge(self):
        value=deepcopy(self.receipt)
        with patch.object(checker,'Golden',return_value=self.golden):p.merge(self.parts,self.output,value)
        value.update(completed_checks=len(value['checks']),status='success')
        return value

    def test_exact_full_13438_order_and_original_independent_checker(self):
        # Corpus-only reads and literal envelope fixtures. No native transport.
        self.golden=checker.Golden()
        for root in self.parts.values():
            for path in (root/'receipt-reports').iterdir():path.unlink()
        self.make_parts(self.golden)
        receipt=self.merge();ordered=list(self.golden.expected('protocol'))
        self.assertEqual(len(ordered),13438)
        self.assertEqual([(r['role'],r['id'],r['operation']) for r in receipt['checks']],ordered)
        self.assertEqual(sum(key[0]=='core' for key in ordered),6719)
        self.assertEqual(sum(key[0]=='verify' for key in ordered),6719)
        original_artifacts=json.loads((self.parts['core']/'receipt.json').read_bytes())['artifacts']
        self.assertEqual(receipt['artifacts'],original_artifacts)
        self.assertGreater(len(receipt['artifacts']),1000)
        checker.validate_checks({**receipt,'completed_checks':len(ordered)},'protocol',self.golden,
                                checker.artifacts(self.output,receipt['artifacts']))

    def test_original_case_and_boundary_bodies_are_byte_for_byte_unchanged(self):
        new=Path(campaign.__file__).read_text()
        def bodies(text):
            lines=text.splitlines(keepends=True)
            return {node.name:''.join(lines[node.lineno-1:node.end_lineno]) for node in ast.parse(text).body if isinstance(node,ast.FunctionDef)}
        for name in ('campaign','boundary_campaign','check_result','transport_only','artifact','invoke','rejected'):
            self.assertEqual(hashlib.sha256(bodies(new)[name].encode()).hexdigest(),PROTOCOL_BODY_PINS[name],name)

    def test_identical_role_artifacts_deduplicate_with_original_receipt_shape(self):
        core=json.loads((self.parts['core']/'receipt.json').read_bytes())
        merged=self.merge()
        self.assertEqual(merged['schema_version'],self.receipt['schema_version'])
        self.assertEqual(merged['artifacts'],core['artifacts'])
        self.assertEqual(len(merged['checks']),2*len(core['checks']))
        self.assertEqual({p.name for p in self.output.iterdir()},set(row['path'] for row in core['artifacts'].values()))

    def test_wrong_missing_reordered_duplicated_or_failed_role_cannot_publish(self):
        path=self.parts['core']/'receipt.json';original=json.loads(path.read_bytes())
        mutations=(lambda r:r.update(role='verify'),lambda r:r.update(status='failure'),lambda r:r.update(completed_checks=0),
                   lambda r:r['checks'].pop(),lambda r:r['checks'].append(deepcopy(r['checks'][0])),
                   lambda r:r['checks'].reverse(),lambda r:r['checks'][0].update(role='verify'),
                   lambda r:r.update(artifact_directory='../foreign'),lambda r:r.update(schema_version=self.receipt['schema_version']))
        for change in mutations:
            value=deepcopy(original);change(value);self.write(path,value)
            with self.assertRaises(AssertionError):self.merge()
            self.assertFalse(any(self.output.iterdir()))
        self.write(path,original);self.parts.pop('verify')
        with self.assertRaises(AssertionError):self.merge()

    def test_source_run_runtime_package_corpus_executable_ownership_is_exact(self):
        path=self.parts['verify']/'receipt.json';original=json.loads(path.read_bytes())
        for key in p.AUTHORITY:
            value=deepcopy(original);value[key]={} if key=='executables' else 'foreign'
            self.write(path,value)
            with self.subTest(key=key),self.assertRaisesRegex(AssertionError,'authority'):self.merge()
            self.assertFalse(any(self.output.iterdir()))
        value=deepcopy(original);value['executables']['core']['sha256']='f'*64;self.write(path,value)
        with self.assertRaisesRegex(AssertionError,'authority'):self.merge()

    def test_changed_extra_symlinked_and_colliding_artifacts_reject_before_publication(self):
        role=self.parts['verify'];path=next((role/'receipt-reports').iterdir());original=path.read_bytes()
        for raw in (original+b' ',b'{"forged":true}\n'):
            path.write_bytes(raw)
            with self.assertRaises(AssertionError):self.merge()
            self.assertFalse(any(self.output.iterdir()))
        path.write_bytes(original)
        extra=role/'receipt-reports'/'unowned.json';extra.write_text('{}')
        with self.assertRaises(AssertionError):self.merge()
        extra.unlink();path.unlink();path.symlink_to(self.parts['core']/'receipt-reports'/path.name)
        with self.assertRaises(AssertionError):self.merge()
        path.unlink();path.write_bytes(original)
        # Force the cross-role collision branch independently of digest checks;
        # real mismatched bytes above are rejected by the unchanged reader first.
        real=checker.artifacts
        def values(directory,declared):
            result=real(directory,declared)
            if directory.parent.name=='verify':result[next(iter(result))]={'conflicting':'canonical bytes'}
            return result
        with patch.object(checker,'artifacts',side_effect=values),self.assertRaisesRegex(AssertionError,'Conflicting'):
            self.merge()

    def test_forged_self_consistent_report_fails_unchanged_semantic_checker(self):
        path=self.parts['core']/'receipt.json';receipt=json.loads(path.read_bytes())
        row=next(row for row in receipt['checks'] if 'authority' in row);pin=row['artifact'];file=path.parent/'receipt-reports'/(pin+'.json')
        value=json.loads(file.read_bytes());value['claim_scope']='forged'
        new_pin=checker.digest(value);raw=checker.canonical(value)+b'\n';file.unlink();(file.parent/(new_pin+'.json')).write_bytes(raw)
        receipt['artifacts'][new_pin]={'bytes':len(raw),'path':new_pin+'.json','canonical_sha256':new_pin};del receipt['artifacts'][pin]
        for item in receipt['checks']:
            if item['artifact']==pin:item['artifact']=new_pin
        self.write(path,receipt)
        with self.assertRaises(AssertionError):self.merge()
        self.assertFalse(any(self.output.iterdir()))

    def test_two_isolated_workers_keep_exact_commands_environment_and_wait_on_failure(self):
        args=SimpleNamespace(output=self.root/'dispatch/protocol.json',core=Path('/installed/bin/core'),verify=Path('/installed/bin/verify'))
        barrier=threading.Barrier(2);seen=[];done=[];parent=dict(os.environ)
        def fake_run(command,**kw):
            role=command[command.index('--role')+1];seen.append((role,command,kw));barrier.wait(timeout=5)
            kw['stdout'].write((role+' complete diagnostic\n').encode());done.append(role)
            return SimpleNamespace(returncode=1 if role=='core' else 0)
        with patch.object(subprocess,'run',side_effect=fake_run),patch.object(p,'merge',side_effect=AssertionError('No merge after failed worker')):
            with self.assertRaisesRegex(AssertionError,'process failed'):p.execute(args,self.output,self.receipt)
        self.assertEqual(set(done),set(p.ROLES));self.assertEqual(len(seen),2);self.assertEqual(dict(os.environ),parent)
        for role,command,kw in seen:
            self.assertEqual(command[0],__import__('sys').executable)
            self.assertEqual(command[1],str(Path(p.__file__).with_name('check_realization_protocol.py').resolve()))
            self.assertEqual(command[command.index('--workers')+1],'1')
            self.assertEqual(command[command.index('--core')+1],str(args.core));self.assertEqual(command[command.index('--verify')+1],str(args.verify))
            self.assertEqual(kw['env']['GITHUB_SHA'],self.receipt['revision']);self.assertEqual(kw['env']['GITHUB_HEAD_SHA'],self.receipt['source_revision'])
            self.assertEqual(kw['env']['GITHUB_RUN_ID'],self.receipt['run_id']);self.assertNotIn('cwd',kw)
            log=self.root/'dispatch/protocol-workers'/role/'worker.log';self.assertIn(b'complete diagnostic',log.read_bytes())

    def test_worker_completion_order_does_not_change_merge_order(self):
        args=SimpleNamespace(output=self.root/'dispatch/protocol.json',core=Path('/installed/bin/core'),verify=Path('/installed/bin/verify'))
        verify_done=threading.Event();finished=[]
        def fake_run(command,**kw):
            role=command[command.index('--role')+1]
            if role=='verify':finished.append(role);verify_done.set()
            else:self.assertTrue(verify_done.wait(5));finished.append(role)
            return SimpleNamespace(returncode=0)
        with patch.object(subprocess,'run',side_effect=fake_run),patch.object(p,'merge') as merge:
            p.execute(args,self.output,self.receipt)
        self.assertEqual(finished,['verify','core']);self.assertEqual(list(merge.call_args.args[0]),['core','verify'])

    def test_relative_custom_output_keeps_owned_mode_worker_root(self):
        previous=Path.cwd()
        try:
            os.chdir(self.root)
            args=SimpleNamespace(output=Path('dispatch/custom.json'),core=Path('/installed/bin/core'),verify=Path('/installed/bin/verify'))
            directory=Path('dispatch/custom-reports');directory.mkdir(parents=True)
            receipt=deepcopy(self.receipt)
            def fake_run(command,**kw):
                role=command[command.index('--role')+1]
                output=Path(command[command.index('--output')+1])
                self.assertEqual(output,self.root/'dispatch/protocol-workers'/role/'receipt.json')
                shutil.copyfile(self.parts[role]/'receipt.json',output)
                shutil.copytree(self.parts[role]/'receipt-reports',output.parent/'receipt-reports')
                kw['stdout'].write(b'complete isolated role diagnostic\n')
                return SimpleNamespace(returncode=0)
            with patch.object(subprocess,'run',side_effect=fake_run),patch.object(checker,'Golden',return_value=self.golden):
                p.execute(args,directory,receipt)
            self.assertEqual(receipt['checks'],[row for role in p.ROLES for row in json.loads((self.parts[role]/'receipt.json').read_bytes())['checks']])
            self.assertEqual(receipt['role_workers']['roles']['core']['receipt']['path'],'protocol-workers/core/receipt.json')
        finally:
            os.chdir(previous)

    def test_shared_runner_dispatches_serial_coordinator_and_both_selected_roles(self):
        core=self.root/'core';verify=self.root/'verify'
        for path in (core,verify):path.write_bytes(b'nonexecuted fixture');path.chmod(0o755)
        args=SimpleNamespace(core=core,verify=verify,output=self.root/'routing.json')
        corpus=SimpleNamespace(index={'coverage':{'sdk_checks_per_role':2,'protocol_checks_per_role':2}})
        def execute(clients,_corpus,receipt):receipt['checks']=[{'role':client.role} for client in clients for _ in range(2)]
        environment={'GITHUB_SHA':'a'*40,'GITHUB_HEAD_SHA':'b'*40,'GITHUB_RUN_ID':'77'}
        observed=[]
        def coordinated(_args,_directory,receipt):
            observed.append(receipt['schema_version'])
            self.assertNotIn('role',receipt)
            execute([SimpleNamespace(role=r) for r in p.ROLES],corpus,receipt)
        with patch.object(campaign.platform,'platform',return_value='fixture-linux'),patch.object(campaign,'require_installed'),patch.object(campaign,'Corpus',return_value=corpus), \
             patch.object(subprocess,'check_output',return_value='a'*40+'\n'),patch.dict(os.environ,environment),patch.object(p,'execute',side_effect=coordinated):
            for kind in ('protocol','routing'):
                for workers,role in ((1,None),(2,None),(1,'core'),(1,'verify')):
                    args.workers=workers;args.role=role;args.output=self.root/f'{kind}-{workers}-{role}.json'
                    schema=f'biocompiler.realization_{kind}_conformance.v1'
                    self.assertEqual(campaign.run_main(args,execute,schema),0)
                    receipt=json.loads(args.output.read_bytes());self.assertEqual(receipt['completed_checks'],2 if role else 4)
                    self.assertEqual({row['role'] for row in receipt['checks']},{role} if role else set(p.ROLES))
                    self.assertEqual(receipt['schema_version'],f'biocompiler.realization_{kind}_role.v1' if role else schema)
            self.assertEqual(observed,['biocompiler.realization_protocol_conformance.v1','biocompiler.realization_routing_conformance.v1'])
            args.workers=2;args.role='core';args.output=self.root/'invalid.json'
            self.assertEqual(campaign.run_main(args,execute,'biocompiler.realization_protocol_conformance.v1'),1)
            self.assertEqual(json.loads(args.output.read_bytes())['status'],'failure')
            args.workers=1;args.role='foreign';args.output=self.root/'unknown-role.json'
            self.assertEqual(campaign.run_main(args,execute,'biocompiler.realization_protocol_conformance.v1'),1)
            self.assertEqual(json.loads(args.output.read_bytes())['status'],'failure')

    def routing_fixture(self,full=False):
        self.parts={role:self.root/'routing-workers'/role for role in p.ROLES}
        self.output=self.root/'routing-reports';self.output.mkdir()
        self.receipt['schema_version']='biocompiler.realization_routing_conformance.v1'
        if full:self.golden=checker.Golden()
        return self.make_parts(self.golden)

    def test_full_8314_routing_order_guards_and_original_body(self):
        self.routing_fixture(full=True)
        receipt=self.merge();ordered=list(self.golden.expected('routing'))
        self.assertEqual(len(ordered),8314)
        self.assertEqual([(row['role'],row['id'],row['operation']) for row in receipt['checks']],ordered)
        self.assertEqual(set(receipt['guard']['allowed_executed_functions']),checker.REQUIRED_ROUTES)
        from tools import check_realization_routing as routing
        def bodies(path):
            text=path.read_text();lines=text.splitlines(keepends=True)
            return {node.name:''.join(lines[node.lineno-1:node.end_lineno]) for node in ast.parse(text).body if isinstance(node,ast.FunctionDef)}
        new=bodies(Path(routing.__file__))
        self.assertEqual({name:hashlib.sha256(value.encode()).hexdigest() for name,value in new.items() if name!='main'},ROUTING_BODY_PINS)

    def test_each_routing_role_must_preserve_complete_guard(self):
        self.routing_fixture();path=self.parts['verify']/'receipt.json';original=json.loads(path.read_bytes())
        for change in (lambda r:r.pop('guard'),lambda r:r['guard'].update(status='failure'),
                       lambda r:r['guard']['allowed_executed_functions'].pop(),
                       lambda r:r['guard']['allowed_executed_functions'].append('biocompiler.compiler.request.RealizationRequest.__post_init__'),
                       lambda r:r['guard'].update(input_hydration='inside'),
                       lambda r:r['guard'].update(snapshot_request_rehydration='allowed')):
            receipt=deepcopy(original);change(receipt);self.write(path,receipt)
            with self.assertRaises(AssertionError):self.merge()
            self.assertFalse(any(self.output.iterdir()))

    def test_mode_does_not_accept_arbitrary_campaign_callable_or_schema(self):
        receipt=deepcopy(self.receipt);receipt['schema_version']='biocompiler.unreviewed.v1'
        with self.assertRaisesRegex(AssertionError,'Unknown'):p.mode(receipt)

    def test_raw_workers_are_rechecked_independently_after_aggregation(self):
        receipt=self.merge()
        checker.validate_worker_evidence(self.root,receipt,'protocol',self.golden)
        for role in p.ROLES:
            path=self.parts[role]/'receipt.json';original=path.read_bytes()
            for change in (lambda r:r.update(source_revision='f'*40),lambda r:r['checks'].reverse(),
                           lambda r:r.update(status='failure'),lambda r:r['executables']['core'].update(sha256='e'*64)):
                worker=json.loads(original);change(worker);self.write(path,worker)
                changed=deepcopy(receipt);entry=changed['role_workers']['roles'][role]['receipt']
                entry.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size)
                with self.assertRaises(AssertionError):checker.validate_worker_evidence(self.root,changed,'protocol',self.golden)
            path.write_bytes(original)
            log=self.parts[role]/'worker.log';raw=log.read_bytes();log.write_bytes(raw+b'changed')
            with self.assertRaises(AssertionError):checker.validate_worker_evidence(self.root,receipt,'protocol',self.golden)
            log.write_bytes(raw)
        legacy=deepcopy(receipt);legacy.pop('role_workers');legacy.pop('campaign_sources')
        with self.assertRaisesRegex(AssertionError,'required aggregate binding'):
            checker.validate_worker_evidence(self.root,legacy,'protocol',self.golden)
        (self.root/'protocol-workers').rename(self.root/'legacy-workers')
        checker.validate_worker_evidence(self.root,legacy,'protocol',self.golden)

    def test_postrun_metadata_source_closure_and_safe_paths_fail_closed(self):
        receipt=self.merge()
        mutations=(lambda r:r['role_workers'].update(workers=1),lambda r:r['role_workers'].update(campaign='routing'),
                   lambda r:r['role_workers']['roles'].pop('verify'),lambda r:r['role_workers'].update(source_pins={}),
                   lambda r:r.update(campaign_sources={}),
                   lambda r:r['role_workers']['roles']['core']['log'].update(path='../foreign'),
                   lambda r:r['role_workers']['roles']['core']['receipt'].update(sha256='0'*64))
        for change in mutations:
            value=deepcopy(receipt);change(value)
            with self.assertRaises(AssertionError):checker.validate_worker_evidence(self.root,value,'protocol',self.golden)
        path=self.parts['core']/'worker.log';raw=path.read_bytes();path.unlink();path.symlink_to(self.parts['verify']/'worker.log')
        with self.assertRaises(AssertionError):checker.validate_worker_evidence(self.root,receipt,'protocol',self.golden)
        path.unlink();path.write_bytes(raw)
        extra=self.parts['core']/'extra.txt';extra.write_text('unowned')
        with self.assertRaises(AssertionError):checker.validate_worker_evidence(self.root,receipt,'protocol',self.golden)

    def test_postrun_each_routing_guard_and_raw_report_bytes_are_required(self):
        self.routing_fixture();receipt=self.merge();checker.validate_worker_evidence(self.root,receipt,'routing',self.golden)
        role='verify';path=self.parts[role]/'receipt.json';original=path.read_bytes();worker=json.loads(original)
        worker['guard']['allowed_executed_functions'].pop();self.write(path,worker)
        changed=deepcopy(receipt);entry=changed['role_workers']['roles'][role]['receipt']
        entry.update(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size)
        with self.assertRaises(AssertionError):checker.validate_worker_evidence(self.root,changed,'routing',self.golden)
        path.write_bytes(original)
        report=next((self.parts[role]/'receipt-reports').iterdir());report.write_bytes(report.read_bytes()+b' ')
        with self.assertRaises(AssertionError):checker.validate_worker_evidence(self.root,receipt,'routing',self.golden)

    def test_campaign_recipe_only_enables_protocol_and_routing_parallelism(self):
        from tools import prebuilt_release_pipeline as pipeline
        owned={'package_root':'/installed','source_revision':'a'*40,'tested_revision':'b'*40,'native_platform':'linux-x86_64',
               'files':{f'bin/biocompiler-{role}':{'path':f'/installed/bin/biocompiler-{role}','sha256':role} for role in p.ROLES}}
        commands=pipeline.campaign_plan(Path('/checkout'),Path('/installed/bin/python'),owned,Path('/output'))
        self.assertEqual(len(commands),17)
        for name,command in commands:
            if name in ('protocol','routing'):self.assertEqual(command[command.index('--workers')+1],'2')
            else:self.assertNotIn('--workers',command)


    def test_independent_installed_recipe_rejects_serial_missing_or_extra_workers(self):
        from tests import test_prebuilt_sdk_matrix as matrix_fixtures
        fixture=matrix_fixtures.MatrixTests();fixture.setUp();fixture.verify()
        original=deepcopy(fixture.receipt)
        for campaign_name in ('protocol','routing'):
            for replacement in ([],['--workers','1'],['--workers','3']):
                fixture.receipt=deepcopy(original)
                command=next(row['argv'] for row in fixture.receipt['commands'] if row['log']['path']==campaign_name+'.log')
                index=command.index('--workers');command[index:index+2]=replacement
                with self.subTest(campaign=campaign_name,replacement=replacement),self.assertRaisesRegex(ValueError,'owned-path recipe'):
                    fixture.verify()


if __name__=='__main__':unittest.main()
