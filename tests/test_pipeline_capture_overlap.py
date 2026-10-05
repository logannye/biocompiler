"""Inert Python child/parent scheduling controls; no product or native campaigns."""
import ast
from contextlib import ExitStack
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

# The proposal runner supplies its overlay; an integrated test uses repo root.
ROOT = Path(os.environ.get('CAPTURE_OVERLAP_ROOT', Path(__file__).resolve().parents[1]))
BASE = Path(os.environ['CAPTURE_OVERLAP_BASE']) if 'CAPTURE_OVERLAP_BASE' in os.environ else None
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); sys.modules[name] = module
    spec.loader.exec_module(module); return module
counterpart = load('capture_overlap_counterpart_candidate', ROOT/'tools/pipeline_original_counterpart.py')


class CaptureProcessTests(unittest.TestCase):
    def command(self, body): return [sys.executable, '-I', '-B', '-c', body]
    def execute(self, body, capture, timeout=5, **kwargs):
        return counterpart._capture_process(self.command(body), cwd=str(Path.cwd()),
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'), timeout=timeout, capture=capture, **kwargs)

    def test_child_launches_and_drains_before_parent_finishes(self):
        with tempfile.TemporaryDirectory() as directory:
            ready, done = [Path(directory)/name for name in ('ready','done')]
            body = f'''import pathlib,sys,time
sys.stdout.write('x'*262144);sys.stdout.flush()
pathlib.Path({str(ready)!r}).write_text('ready')
deadline=time.monotonic()+4
while not pathlib.Path({str(done)!r}).exists():
 assert time.monotonic()<deadline
 time.sleep(.005)
sys.stderr.write('child drained')
'''
            current = object()
            def capture():
                deadline=time.monotonic()+4
                while not ready.exists():
                    self.assertLess(time.monotonic(), deadline)
                    time.sleep(.005)
                done.write_text('done');return current
            result, value = self.execute(body,capture)
            self.assertIs(value,current)
            self.assertEqual((result.returncode,len(result.stdout),result.stderr),(0,262144,b'child drained'))

    def test_launch_failure_does_not_run_capture(self):
        error = OSError('inert launch failed'); calls=[]
        def fail(*args,**kwargs): raise error
        with self.assertRaises(OSError) as raised:
            self.execute('',lambda:calls.append('capture'),popen=fail)
        self.assertIs(raised.exception,error);self.assertEqual(calls,[])

    def test_parent_exception_identity_survives_exact_child_kill_and_drain(self):
        processes=[];error=RuntimeError('original parent failure')
        def launch(*args,**kwargs):
            process=subprocess.Popen(*args,**kwargs);processes.append(process);return process
        def capture(): raise error
        with self.assertRaises(RuntimeError) as raised:
            self.execute('import time;time.sleep(30)',capture,popen=launch)
        self.assertIs(raised.exception,error)
        self.assertEqual(len(processes),1);self.assertIsNotNone(processes[0].poll())
        self.assertTrue(processes[0].stdout.closed and processes[0].stderr.closed)

    def test_timeout_stops_child_while_parent_original_finishes_then_refuses_pair(self):
        processes=[]; finished=[]
        def launch(*args,**kwargs):
            process=subprocess.Popen(*args,**kwargs);processes.append(process);return process
        def capture():
            deadline=time.monotonic()+3
            while processes[0].poll() is None:
                self.assertLess(time.monotonic(),deadline);time.sleep(.005)
            finished.append('original completed');return object()
        with self.assertRaises(subprocess.TimeoutExpired):
            self.execute('import time;time.sleep(30)',capture,timeout=.05,popen=launch)
        self.assertEqual(finished,['original completed'])
        self.assertTrue(processes[0].stdout.closed and processes[0].stderr.closed)

    def test_nonzero_child_keeps_outputs_and_current_for_existing_rejection(self):
        current=object();result,value=self.execute('import sys;print("child failure",file=sys.stderr);sys.exit(7)',lambda:current)
        self.assertEqual(result.returncode,7);self.assertEqual(result.stderr,b'child failure\n')
        self.assertIs(value,current)

    def test_closed_task_census_rejects_unreviewed_pair_before_run(self):
        with patch.object(counterpart,'run') as run:
            for task, callback in (('deferred',lambda:None),('fixed-build-original',None)):
                with self.subTest(task=task),self.assertRaisesRegex(AssertionError,'Unreviewed paired'):
                    counterpart.run_with_capture(task,callback)
            run.assert_not_called()

    def test_parent_exception_wins_over_cleanup_error_and_io_has_no_capture_thread(self):
        error=RuntimeError('exact original parent failure');released=threading.Event()
        parent_thread=threading.get_ident();io_threads=[]
        class Peer:
            stdout=io.BytesIO();stderr=io.BytesIO();returncode=None
            def communicate(self,timeout=None):
                io_threads.append(threading.get_ident())
                if not released.wait(2):raise AssertionError('fixture did not release child')
                self.returncode=-9;return b'',b''
            def poll(self):return self.returncode
            def kill(self):released.set();raise OSError('cleanup fixture failure')
            def wait(self):return self.returncode
        peer=Peer()
        def capture():
            self.assertEqual(threading.get_ident(),parent_thread);raise error
        with self.assertRaises(RuntimeError) as raised:
            self.execute('',capture,popen=lambda *a,**kw:peer)
        self.assertIs(raised.exception,error)
        self.assertEqual(len(io_threads),1);self.assertNotEqual(io_threads[0],parent_thread)
        self.assertTrue(peer.stdout.closed and peer.stderr.closed)


class PairPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Loading this tool imports only source, never starts its campaign.
        cls.driver=load('tools.capture_overlap_driver_candidate', ROOT/'tools/check_pipeline_fixed_continuation_install.py')

    def helper(self, original, current, expected, *, validation_error=False, correspondence_error=False):
        order=[];receipt={};artifact_calls=[]
        def paired(task,capture):
            order.append('child launched');value=capture();self.assertIs(value,current)
            order.append('child joined');return original,value
        def validate(value):
            self.assertIs(value,original);order.append('complete original validated')
            if validation_error: return {'forged':True}
            return expected
        def proof(actual,before):
            self.assertIs(actual,current);self.assertIs(before,original);order.append('complete correspondence')
            if correspondence_error: raise AssertionError('correspondence failure')
            return {'proof':True}
        peer=SimpleNamespace(run_with_capture=paired,validate=validate,metadata_correspondence=proof)
        def capture():order.append('current capture');return current
        def artifact(_receipt,raw):artifact_calls.append(raw);return hashlib.sha256(raw).hexdigest()
        with patch.object(self.driver.providers,'tool',return_value=peer),patch.object(self.driver.providers,'artifact',side_effect=artifact):
            if validation_error or correspondence_error:
                with self.assertRaises(AssertionError):
                    self.driver.capture_counterpart_pair(receipt,'fixed-build-original',expected,capture)
                self.assertEqual(receipt,{});self.assertEqual(artifact_calls,[])
            else:
                self.assertIs(self.driver.capture_counterpart_pair(receipt,'fixed-build-original',expected,capture),current)
                self.assertEqual(set(receipt),{'fresh_original','current_original','original_counterpart','original_correspondence'})
                self.assertEqual(artifact_calls,[self.driver.canonical(value) for value in (expected,current,original,{'proof':True})])
        return order

    def test_both_complete_captures_and_equalities_precede_any_publication(self):
        self.assertEqual(self.helper({'original':1},{'current':2},{'expected':3}),
            ['child launched','current capture','child joined','complete original validated','complete correspondence'])

    def test_original_or_correspondence_mismatch_never_publishes_partial_pair(self):
        for kind in ('validation_error','correspondence_error'):
            with self.subTest(kind=kind):self.helper({'o':1},{'c':2},{'e':3},**{kind:True})


class CampaignSequenceTests(unittest.TestCase):
    def test_two_complete_pairs_finish_before_direct_controls_and_workers(self):
        text=(ROOT/'tools/check_pipeline_fixed_continuation_install.py').read_text()
        node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='campaign')
        # Substitute only imports of the inert test double for direct controls.
        node.body=node.body[1:]
        for failure in (None,'fixed-build-original','fixed-continuation-original'):
            calls=[];receipt={'_artifact_directory':'unused','artifacts':{}};originals_seen=[]
            def capture(**kwargs):kwargs['retain'].append('actual parent object');calls.append('current build');return 'build'
            def pair(receipt,task,expected,capture):
                calls.append(task+' launched');value=capture()
                if task==failure:raise AssertionError('pair failed')
                calls.append(task+' validated');return value
            def direct_run(core,corpus,oracle,receipt,originals):
                originals_seen.extend(originals);calls.append('direct6')
            namespace={'__name__':__name__,'sys':sys,'direct':SimpleNamespace(run=direct_run),
                'load_oracle':lambda:SimpleNamespace(capture=capture),
                'capture_counterpart_pair':pair,'providers':SimpleNamespace(installed_modules=lambda:calls.append('source check')),
                'occurrences':SimpleNamespace(read_frozen=lambda *a:'frozen39',capture=lambda *a:calls.append('current39') or 'current39',validate=lambda *a:'graphs'),
                'continuation_workers':lambda:SimpleNamespace(run_workers=lambda *a,**kw:calls.append('workers'))}
            exec(compile(ast.Module(body=[node],type_ignores=[]),str(ROOT/'tools/check_pipeline_fixed_continuation_install.py'),'exec'),namespace)
            if failure:
                with self.assertRaisesRegex(AssertionError,'pair failed'):namespace['campaign'](None,SimpleNamespace(build='frozen6'),receipt,workers=2)
                self.assertNotIn('direct6',calls);self.assertNotIn('workers',calls)
            else:
                namespace['campaign'](None,SimpleNamespace(build='frozen6'),receipt,workers=2)
                self.assertEqual(calls,['fixed-build-original launched','current build','fixed-build-original validated',
                    'fixed-continuation-original launched','current39','fixed-continuation-original validated','direct6','workers','source check'])
                self.assertEqual(originals_seen,['actual parent object'])


class SourceRestorationTests(unittest.TestCase):
    def test_new_layer_restores_exact_frozen_predecessors_and_original_functions(self):
        layer=load('capture_overlap_source_candidate',ROOT/'tools/pipeline_capture_overlap_source.py')
        import json
        proof=json.loads(layer.WITNESS.read_bytes())
        for path in layer.PATHS:
            current=(ROOT/path).read_bytes();prior=layer.restore(path,current)
            self.assertEqual({'sha256':hashlib.sha256(prior).hexdigest(),'bytes':len(prior)},proof['files'][path]['historical'])
            if BASE is not None:self.assertEqual(prior,(BASE/path).read_bytes())
            with self.assertRaisesRegex(AssertionError,'Current source differs'):layer.restore(path,current+b'\n')
            with self.assertRaisesRegex(AssertionError,'Unreviewed'):layer.restore(path,current,b'{}')
        path='tools/check_pipeline_fixed_continuation_install.py'
        for name in ('load_body_modules','run_original_bodies','public_graph','observed_public_graph'):
            def function(text):
                node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name==name)
                return ast.get_source_segment(text,node)
            current=(ROOT/path).read_bytes()
            self.assertEqual(function(current.decode()),function(layer.restore(path,current).decode()))

    def test_new_layer_composes_with_unchanged_prior_witnesses(self):
        import tools
        from tools import pipeline_occurrence_source as original
        layer=load('capture_overlap_source_composition',ROOT/'tools/pipeline_capture_overlap_source.py')
        parallel=load('capture_overlap_parallel_composition',ROOT/'tools/pipeline_continuation_parallel_source.py')
        parallel.WITNESS=original.ROOT/'tests/conformance/pipeline-continuation-parallel-source-delta-v1.json'
        for path in layer.PATHS:
            current=(ROOT/path).read_bytes()
            with patch.object(tools,'pipeline_capture_overlap_source',layer,create=True), \
                    patch.object(tools,'pipeline_continuation_parallel_source',parallel,create=True):
                restored=original.restore(path,current)
            import json
            self.assertEqual({'sha256':hashlib.sha256(restored).hexdigest(),'bytes':len(restored)},
                json.loads(original.WITNESS.read_bytes())['files'][path]['historical'])

    def test_full_publication_checks_are_identical_to_the_existing_serial_helper(self):
        def body(path,name):
            node=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name==name)
            return node.body
        before=body(ROOT/'tools/check_pipeline_fixed_provider_install.py','capture_counterpart')[2:]
        after=body(ROOT/'tools/check_pipeline_fixed_continuation_install.py','capture_counterpart_pair')[3:-1]
        class StripProviderQualifier(ast.NodeTransformer):
            def visit_Attribute(self,node):
                return ast.Name(id=node.attr,ctx=node.ctx) if isinstance(node.value,ast.Name) and node.value.id=='providers' else self.generic_visit(node)
        self.assertEqual([ast.dump(node) for node in before],
            [ast.dump(StripProviderQualifier().visit(node)) for node in after])

if __name__=='__main__':unittest.main()
