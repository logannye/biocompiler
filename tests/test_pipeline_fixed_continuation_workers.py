"""Bounded process scheduling and whole-class grouping without native execution."""
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from tools import pipeline_fixed_continuation_workers as workers


def require(value, message):
    if not value: raise AssertionError(message)


def equal(actual, expected, message):
    if actual != expected: raise AssertionError(message)


class ContinuationWorkerControls(unittest.TestCase):
    def scheduler(self, *, fail=None, hang=None, startup=None, limit=2):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        active=set();peak=[0];calls=[];now=[0.0]
        class Process:
            def __init__(self, name):self.name=name;self.polls=0;self.stopped=False
            def poll(self):
                self.polls+=1
                if self.name==hang and not self.stopped:return None
                if not self.stopped and self.polls<({'a':4,'b':2,'c':1}.get(self.name,1)):return None
                active.discard(self.name);return -15 if self.stopped else 1 if self.name==fail else 0
            def terminate(self):self.stopped=True;calls.append(('terminate',self.name))
            def kill(self):self.stopped=True;calls.append(('kill',self.name))
            def wait(self,timeout):active.discard(self.name);return -15
        def launch(command,**kwargs):
            name=command[0];calls.append(('start',name))
            if name==startup:raise OSError('synthetic launch failure')
            active.add(name);peak[0]=max(peak[0],len(active));return Process(name)
        def sleep(seconds):now[0]+=seconds
        jobs=[{'id':name,'command':[name],'cwd':folder.name,'env':{},'log':Path(folder.name)/(name+'.log'),
            'timeout':0.1 if name==hang else 10}for name in('a','b','c')]
        return jobs,launch,lambda:now[0],sleep,active,peak,calls

    def test_two_process_bound_and_source_order_survive_out_of_order_finishes(self):
        jobs,popen,clock,sleep,active,peak,calls=self.scheduler()
        result=workers.bounded_processes(jobs,popen=popen,clock=clock,sleep=sleep,stop=lambda process:process.terminate() or process.wait(timeout=1))
        self.assertEqual(list(result),['a','b','c']);self.assertEqual(peak[0],2);self.assertFalse(active)
        self.assertTrue(all(row['returncode']==0 for row in result.values()))
        self.assertEqual([name for action,name in calls if action=='start'],['a','b','c'])

    def test_one_worker_is_a_true_serial_limit(self):
        jobs,popen,clock,sleep,active,peak,calls=self.scheduler()
        workers.bounded_processes(jobs,limit=1,popen=popen,clock=clock,sleep=sleep,stop=lambda process:process.terminate() or process.wait(timeout=1))
        self.assertEqual(peak[0],1);self.assertFalse(active)

    def test_failed_worker_is_retained_and_cannot_become_success(self):
        jobs,popen,clock,sleep,active,peak,calls=self.scheduler(fail='b')
        result=workers.bounded_processes(jobs,popen=popen,clock=clock,sleep=sleep,stop=lambda process:process.terminate() or process.wait(timeout=1))
        self.assertEqual(result['b']['returncode'],1);self.assertEqual(len(result),3)
        self.assertTrue(all(Path(job['log']).is_file()for job in jobs))

    def test_timeout_terminates_worker_and_retains_failure(self):
        jobs,popen,clock,sleep,active,peak,calls=self.scheduler(hang='a')
        result=workers.bounded_processes(jobs,popen=popen,clock=clock,sleep=sleep,stop=lambda process:process.terminate() or process.wait(timeout=1))
        self.assertTrue(result['a']['timed_out']);self.assertNotEqual(result['a']['returncode'],0)
        self.assertIn(('terminate','a'),calls);self.assertFalse(active)

    def test_launch_failure_drains_previously_started_workers(self):
        jobs,popen,clock,sleep,active,peak,calls=self.scheduler(startup='b')
        result=workers.bounded_processes(jobs,popen=popen,clock=clock,sleep=sleep,stop=lambda process:process.terminate() or process.wait(timeout=1))
        self.assertIn('synthetic',result['b']['spawn_error']);self.assertIsNone(result['b']['returncode'])
        self.assertIn(('start','c'),calls);self.assertFalse(active)

    def test_invalid_bound_and_duplicate_jobs_cannot_launch(self):
        for limit in(0,3,True):
            with self.subTest(limit=limit),self.assertRaisesRegex(AssertionError,'allowance'):
                workers.bounded_processes([{'id':'a'}],limit=limit)
        with self.assertRaisesRegex(AssertionError,'duplicate'):
            workers.bounded_processes([{'id':'a'},{'id':'a'}])

    def fixture(self):
        events=[]
        class State(unittest.TestCase):
            @classmethod
            def setUpClass(cls):events.append('fixture');cls.value=[]
            def first(self):self.value.append('first');events.append('first')
            def second(self):self.assertEqual(self.value,['first']);events.append('second')
        module=SimpleNamespace(State=State)
        driver=SimpleNamespace(METHODS={'fixture.py':('State',('first','second'))},require=require,equal=equal)
        return driver,module,State,events

    def test_class_fixture_and_ordered_methods_keep_shared_identity(self):
        driver,module,cls,events=self.fixture();contexts=[]
        @contextmanager
        def context(name):contexts.append(name);yield
        before=(cls.setUpClass.__func__.__code__,cls.first.__code__,cls.second.__code__)
        result=workers.run_original_group(driver,'fixture.py',modules={'fixture.py':module},context=context)
        self.assertEqual(events,['fixture','first','second']);self.assertEqual(result['contexts'],contexts)
        self.assertEqual(before,(cls.setUpClass.__func__.__code__,cls.first.__code__,cls.second.__code__))
        self.assertEqual(result['methods'],2)

    def test_equal_but_distinct_method_code_is_rejected(self):
        driver,module,cls,events=self.fixture();original=cls.first
        def mutate(self):
            original(self)
            cls.first.__code__=cls.first.__code__.replace()
        cls.first=mutate
        with self.assertRaisesRegex(AssertionError,'bodies changed'):
            workers.run_original_group(driver,'fixture.py',modules={'fixture.py':module})

    def test_class_assertion_failure_is_not_partial_success(self):
        driver,module,cls,events=self.fixture()
        driver.METHODS['fixture.py']=('State',('second','first'))
        with self.assertRaisesRegex(AssertionError,'Original class assertions failed'):
            workers.run_original_group(driver,'fixture.py',modules={'fixture.py':module})

    def test_group_case_selection_keeps_each_context_and_all_calls(self):
        driver,module,cls,events=self.fixture()
        corpus=SimpleNamespace(cases=[{'id':index,'context':context}for index,context in enumerate(
            ('fixture.py::fixture.setUpClass','other.py::fixture.setUpClass','fixture.py::State.first',
             'fixture.py::State.first','fixture.py::State.second'))])
        self.assertEqual([row['id']for row in workers.cases(driver,corpus,'fixture.py')],[0,2,3,4])
        with self.assertRaisesRegex(AssertionError,'Unknown'):
            workers.contexts(driver,'other.py')

    def test_direct_controls_finish_before_native_chains_in_both_schedules(self):
        self.check_direct_first(fail=False)

    def test_direct_control_failure_prevents_expensive_native_chain_launch(self):
        self.check_direct_first(fail=True)

    def check_direct_first(self, *, fail):
        from tools import check_pipeline_fixed_continuation_install as driver
        from tools import pipeline_fixed_direct_controls as direct
        for limit in (1, 2):
            with self.subTest(workers=limit):
                events = []
                receipt = {'_artifact_directory': 'unused', 'artifacts': {}}
                oracle = SimpleNamespace(capture=lambda **kwargs: {})
                def controls(*args):
                    self.assertIs(args[3], receipt)
                    events.append('direct')
                    if fail:
                        raise AssertionError('original direct failure')
                with patch.object(driver, 'load_oracle', return_value=oracle), \
                        patch.object(driver.providers, 'capture_counterpart'), \
                        patch.object(driver.providers, 'installed_modules'), \
                        patch.object(driver.occurrences, 'read_frozen', return_value={}), \
                        patch.object(driver.occurrences, 'capture', return_value={}), \
                        patch.object(driver.occurrences, 'validate', return_value={}), \
                        patch.object(direct, 'run', side_effect=controls), \
                        patch.object(workers, 'run_workers', side_effect=lambda *args, **kwargs: events.append('workers')), \
                        patch.object(driver, 'run_native_bodies', side_effect=lambda *args, **kwargs: events.append('serial')):
                    if fail:
                        with self.assertRaisesRegex(AssertionError, '^original direct failure$'):
                            driver.campaign(object(), SimpleNamespace(build={}), receipt, workers=limit, native_root=Path('/unused'))
                        self.assertEqual(events, ['direct'])
                    else:
                        driver.campaign(object(), SimpleNamespace(build={}), receipt, workers=limit, native_root=Path('/unused'))
                        self.assertEqual(events, ['direct', 'workers' if limit == 2 else 'serial'])

    def test_group_comparison_rejects_equal_authority_with_changed_physical_graph(self):
        driver,module,cls,events=self.fixture();driver.occurrences=SimpleNamespace(validate=lambda *args:None)
        baseline={'source_files':{'source':'pin'},'driver_body_sha256':'body',
            'occurrences':[{'id':'call','context':'fixture.py::fixture.setUpClass','call_index':0,'authority':'same','graph':'g'}],
            'graphs':{'g':{'nodes':[{'identity':'original'}]}}}
        value={'schema_version':workers.SCHEMA,'group':'fixture.py','source_files':baseline['source_files'],
            'driver_body_sha256':'body','execution':{'contexts':workers.contexts(driver,'fixture.py'),'methods':2,
            'assertions':'passed','log':'\nOK\n'},'occurrences':baseline['occurrences'],'graphs':{'g':{'nodes':[{'identity':'different'}]}}}
        with self.assertRaisesRegex(AssertionError,'Complete grouped original graph'):
            workers.validate_original_group(driver,None,value,baseline,'fixture.py')


class ContinuationReceiptControls(unittest.TestCase):
    def setUp(self):
        import hashlib,json
        from tools import check_pipeline_session_install as receipts
        from tools import check_workflow_reproducibility as r
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup);root=Path(self.folder.name)
        canonical=lambda value:json.dumps(value,sort_keys=True,separators=(',',':')).encode()
        self.driver=SimpleNamespace(METHODS={'a.py':('A',('one',)),'b.py':('B',('two',))},require=require,equal=equal,
            canonical=canonical,sha=lambda raw:hashlib.sha256(raw).hexdigest(),r=r,manager=SimpleNamespace(artifact=receipts.artifact,Artifacts=r.Artifacts),
            metadata=lambda corpus:{'fixed_metadata':'fixed'},occurrences=SimpleNamespace(validate=lambda *args:None,MAX_BYTES=32*1024*1024))
        self.corpus=SimpleNamespace(cases=[{'id':'first','context':'a.py::fixture.setUpClass'},
            {'id':'second','context':'b.py::B.two'}])
        self.baseline={'source_files':{'source':'pin'},'driver_body_sha256':'body',
            'occurrences':[{'id':case['id'],'context':case['context'],'call_index':0,'authority':'same','graph':case['id']}
                for case in self.corpus.cases],'graphs':{case['id']:{'nodes':[case['id']]}for case in self.corpus.cases}}
        common={key:key for key in('schema_version','scope','revision','source_revision','run_id','python_version','system','machine',
            'native_platform','package_path','native_inputs','executables','python_sources','campaign_sources','fixed_metadata')}
        common['fixed_metadata']='fixed'
        destination=root/'parent';destination.mkdir()
        self.receipt={**common,'_artifact_directory':str(destination),'artifacts':{},'checks':[],'direct_checks':[],
            'worker_outcomes':{group:{'returncode':0,'spawn_error':None,'timed_out':False,'duration_seconds':1.0}for group in self.driver.METHODS}}
        self.children={}
        for index,group in enumerate(self.driver.METHODS):
            directory=root/str(index);directory.mkdir()
            child={**common,'_artifact_directory':str(directory),'artifacts':{},'status':'success','direct_checks':[]}
            execution={'contexts':workers.contexts(self.driver,group),'methods':1,'assertions':'passed','log':'actual '+group+'\nOK\n'}
            occurrence=[row for row in self.baseline['occurrences']if row['context']in execution['contexts']]
            observation={'schema_version':workers.SCHEMA,'group':group,'source_files':self.baseline['source_files'],
                'driver_body_sha256':'body','execution':execution,'occurrences':occurrence,
                'graphs':{row['graph']:self.baseline['graphs'][row['graph']]for row in occurrence}}
            child['partition']={'group':group,'serial_original_sha256':self.driver.sha(canonical(self.baseline)),
                'original_group':receipts.artifact(child,canonical(observation))}
            child['original_execution']=receipts.artifact(child,canonical({**execution,
                'entries':[['biocompiler.compiler.components','run_component_pipeline']]}))
            child['checks']=[{'id':row['id'],'actual':'test-only'}for row in occurrence];child['completed_checks']=len(occurrence)
            del child['_artifact_directory']
            self.children[group]=(child,directory,canonical(child)+b'\n',b'actual worker log\n')

    def merge(self):
        workers.merge_workers(self.driver,self.corpus,self.receipt,self.baseline,self.children)
    def validate(self):
        artifacts=self.driver.manager.Artifacts(self.receipt['_artifact_directory'],self.receipt['artifacts'])
        workers.validate_partitions(self.driver,self.receipt,self.corpus,artifacts,self.baseline)
    def replace_child(self,group,change):
        child,directory,raw,log=self.children[group];change(child)
        self.children[group]=(child,directory,self.driver.canonical(child)+b'\n',log)

    def test_complete_worker_merge_preserves_source_order_and_raw_evidence(self):
        self.merge();self.validate()
        self.assertEqual([row['id']for row in self.receipt['checks']],['first','second'])
        self.assertEqual([row['group']for row in self.receipt['partitions']],['a.py','b.py'])
        self.assertTrue(all('worker_receipt'in row and'worker_log'in row for row in self.receipt['partitions']))

    def test_missing_and_reordered_workers_cannot_merge(self):
        del self.children['b.py']
        with self.assertRaisesRegex(AssertionError,'Missing, repeated or reordered'):self.merge()

    def test_failed_or_mixed_revision_worker_cannot_merge(self):
        self.replace_child('a.py',lambda child:child.update(source_revision='other'))
        with self.assertRaisesRegex(AssertionError,'Mixed class worker metadata'):self.merge()

    def test_changed_raw_receipt_cannot_be_hidden_by_parsed_claim(self):
        child,directory,raw,log=self.children['a.py'];self.children['a.py']=(child,directory,b'{}\n',log)
        with self.assertRaisesRegex(AssertionError,'raw receipt differs'):self.merge()

    def test_repaired_aggregate_execution_cannot_invent_test_success(self):
        self.merge()
        self.receipt['original_execution']=self.driver.manager.artifact(self.receipt,self.driver.canonical({'contexts':[],
            'methods':13,'assertions':'passed','log':'\nOK\n','entries':[]}))
        with self.assertRaisesRegex(AssertionError,'Aggregate original execution'):self.validate()

    def test_repaired_raw_worker_receipt_must_match_aggregate_checks(self):
        self.merge();row=self.receipt['partitions'][0]
        original=self.children['a.py'][0];changed=dict(original,checks=[{'id':'first','actual':'forged'}])
        row['worker_receipt']=self.driver.manager.artifact(self.receipt,self.driver.canonical(changed)+b'\n')
        with self.assertRaisesRegex(AssertionError,'Raw worker checks differ'):self.validate()

    def test_nonzero_worker_exit_cannot_be_hidden_by_success_receipt(self):
        self.merge();self.receipt['worker_outcomes']['a.py']['returncode']=1
        with self.assertRaisesRegex(AssertionError,'did not finish successfully'):self.validate()

    def test_worker_outcomes_cannot_drop_partition_proof(self):
        self.merge();del self.receipt['partitions']
        with self.assertRaisesRegex(AssertionError,'lack partition evidence'):self.validate()

    def test_actual_artifact_collision_rejects_merge(self):
        child=self.children['a.py'][0];identity=next(iter(child['artifacts']))
        (Path(self.receipt['_artifact_directory'])/(identity+'.bin')).write_bytes(b'wrong actual bytes')
        with self.assertRaisesRegex(AssertionError,'collision'):self.merge()

class ContinuationSourceDeltaControls(unittest.TestCase):
    def test_exact_additive_delta_precedes_unchanged_occurrence_witness(self):
        import hashlib,json
        from tools import pipeline_continuation_parallel_source as source
        from tools import pipeline_occurrence_source as occurrence
        current=(source.ROOT/source.PATH).read_bytes()
        proof=json.loads(source.WITNESS.read_bytes());prior=source.restore(source.PATH,current)
        self.assertEqual({'bytes':len(prior),'sha256':hashlib.sha256(prior).hexdigest()},proof['files'][source.PATH]['historical'])
        oldest=occurrence.restore(source.PATH,current)
        frozen=json.loads(occurrence.WITNESS.read_bytes())['files'][source.PATH]['historical']
        self.assertEqual({'bytes':len(oldest),'sha256':hashlib.sha256(oldest).hexdigest()},frozen)

    def test_extra_delta_and_rehashed_witness_are_rejected(self):
        import json
        from tools import pipeline_continuation_parallel_source as source
        current=(source.ROOT/source.PATH).read_bytes()
        with self.assertRaisesRegex(AssertionError,'Current source differs'):source.restore(source.PATH,current+b'\n# other\n')
        forged=json.loads(source.WITNESS.read_bytes());forged['files'][source.PATH]['current']['bytes']+=1
        with self.assertRaisesRegex(AssertionError,'Unreviewed'):source.restore(source.PATH,current,json.dumps(forged).encode())

    def test_frozen_original_driver_functions_remain_exact(self):
        import ast
        from tools import pipeline_continuation_parallel_source as source
        current=(source.ROOT/source.PATH).read_bytes();prior=source.restore(source.PATH,current)
        for name in('load_body_modules','run_original_bodies','public_graph','observed_public_graph'):
            def extract(raw):
                text=raw.decode();node=next(node for node in ast.parse(text).body if isinstance(node,ast.FunctionDef)and node.name==name)
                return ast.get_source_segment(text,node)
            self.assertEqual(extract(current),extract(prior))

if __name__=='__main__':unittest.main()
