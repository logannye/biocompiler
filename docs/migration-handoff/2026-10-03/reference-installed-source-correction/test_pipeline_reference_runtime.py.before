"""Outer authority/orchestration controls, never a native semantic substitute."""
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import pipeline_reference_runtime as runtime


class ReferenceRuntimeAuthorityTests(unittest.TestCase):
    revision='a'*40
    source_revision='b'*40
    run_id='12345'

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'receipts';self.root.mkdir()
        self.native=Path(self.temp.name)/'native';self.native.mkdir()
        self.sources={'src/biocompiler/example.py':'c'*64}
        self.tools={'tools/example.py':'d'*64}
        self.metadata={'corpus':{'path':'frozen','sha256':'e'*64},'declarations':{'profile':'f'*64}}
        self.rows={};self.inputs={};self.binaries={}
        for target,(system,machine) in runtime.r.PLATFORMS.items():
            native={'revision':self.revision,'system':system,'machine':machine,
                'sha256':{'biocompiler-core':'1'*64,'biocompiler-verify':'2'*64}}
            self.binaries[target]=native;(self.native/target).mkdir()
            for python in runtime.r.PYTHONS:
                name='realization-'+target+'-py'+python
                directory=self.root/name;(directory/runtime.gate.ARTIFACT_DIRECTORY).mkdir(parents=True)
                self.inputs[name]={**native,'source_revision':self.source_revision,'run_id':self.run_id,'python_version':python+'.99'}
                self.rows[name]={'schema_version':runtime.gate.SCHEMA,'execution_kind':'installed-native','scope':runtime.SCOPE,
                    'status':'success','revision':self.revision,'source_revision':self.source_revision,'run_id':self.run_id,
                    'native_platform':target,'system':system,'machine':machine,'python_version':python+'.99',
                    'python_sources':self.sources,'campaign_sources':self.tools,'native_inputs':native,
                    'artifact_directory':runtime.gate.ARTIFACT_DIRECTORY,**self.metadata,
                    'package_path':'/installed/site-packages/biocompiler/__init__.py',
                    'executables':{'core':'/native/biocompiler-core','verify':'/native/biocompiler-verify'},'artifacts':{}}
        self.interpreters={}
        for python in runtime.r.PYTHONS:
            path=Path(self.temp.name)/('python'+python);path.write_bytes(('test interpreter '+python).encode());path.chmod(0o700)
            self.interpreters[python]=path
        self.save()
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        for owner,name,value in ((runtime.gate,'Corpus',object()),(runtime,'product_sources',self.sources),
                (runtime,'campaign_sources',self.tools),(runtime,'metadata',self.metadata)):
            self.stack.enter_context(patch.object(owner,name,return_value=value))
        self.binary=self.stack.enter_context(patch.object(runtime.r,'verify_binaries',
            side_effect=lambda path,revision,target:deepcopy(self.binaries[target])))
        self.run=self.stack.enter_context(patch.object(runtime.subprocess,'run',side_effect=self.worker))

    def save(self):
        for name,row in self.rows.items():
            (self.root/name/runtime.gate.RECEIPT_FILE).write_bytes(runtime.canonical(row)+b'\n')
            (self.root/name/'native-inputs.json').write_bytes(runtime.canonical(self.inputs[name])+b'\n')

    def worker(self,command,**kwargs):
        from types import SimpleNamespace
        def arg(name):return command[command.index('--'+name)+1]
        receipt,pin=runtime.r.read(Path(arg('receipt')))
        report={'schema_version':'biocompiler.reference_independent_reconstruction.v1','status':'success',
            'receipt_sha256':pin,'revision':self.revision,'source_revision':self.source_revision,'run_id':self.run_id,
            'native_platform':arg('platform'),'campaign_sources':self.tools,'python_sources':self.sources,
            'interpreter':command[0],'interpreter_sha256':runtime.sha(Path(command[0]).read_bytes()),
            'python_version':arg('python')+'.99','complete_artifacts':{},
            'projection':{'original_behavior':{'unit_fixture':'outer orchestration only'}},'reconstruction':{}}
        Path(arg('output')).write_bytes(runtime.canonical(report)+b'\n')
        return SimpleNamespace(returncode=0,stdout=b'',stderr=b'')

    def compare(self,**changes):
        return runtime.compare(self.root,self.native,**{'revision':self.revision,'source_revision':self.source_revision,
            'run_id':self.run_id,'python311':self.interpreters['3.11'],'python314':self.interpreters['3.14'],**changes})

    def test_all_four_slots_require_separate_matching_runtime_reconstruction(self):
        result=self.compare()
        self.assertEqual(set(result['receipts']),set(self.rows));self.assertEqual(self.run.call_count,4)
        self.assertEqual(self.binary.call_count,2)
        for call in self.run.call_args_list:
            command=call.args[0];minor=command[command.index('--python')+1]
            self.assertEqual(command[0],str(self.interpreters[minor].resolve()))
            self.assertIn('--reconstruct',command)
            self.assertFalse(Path(call.kwargs['cwd']).is_relative_to(runtime.ROOT))

    def test_source_run_binary_execution_kind_and_runtime_cannot_be_relabelled(self):
        name=next(iter(self.rows));original=deepcopy(self.rows[name])
        for field,value in {'execution_kind':'transcript-reconstruction','status':'running','revision':'f'*40,
                'source_revision':'f'*40,'run_id':'old','python_sources':{},'campaign_sources':{},
                'native_inputs':{},'native_platform':'other','python_version':'3.10.99','declarations':{}}.items():
            with self.subTest(field=field):
                self.rows[name]={**deepcopy(original),field:value};self.save()
                with self.assertRaises(AssertionError):self.compare()
        self.rows[name]=original

    def test_complete_matrix_and_independent_worker_success_are_mandatory(self):
        name=next(iter(self.rows));slot=self.root/name;held=self.root/'held';slot.rename(held)
        with self.assertRaisesRegex(AssertionError,'Incomplete four-runtime'):self.compare()
        slot.symlink_to(held,target_is_directory=True)
        with self.assertRaisesRegex(AssertionError,'Unsafe reference runtime'):self.compare()
        slot.unlink();held.rename(slot)
        from types import SimpleNamespace
        self.run.side_effect=lambda *args,**kwargs:SimpleNamespace(returncode=1,stdout=b'',stderr=b'actual replay failed')
        with self.assertRaisesRegex(AssertionError,'independent reconstruction failed'):self.compare()

    def test_worker_report_and_full_artifact_inventory_are_independently_bound(self):
        original=self.worker
        def changed(command,**kwargs):
            result=original(command,**kwargs);path=Path(command[command.index('--output')+1]);report,_=runtime.r.read(path)
            report['receipt_sha256']='0'*64;path.write_bytes(runtime.canonical(report)+b'\n');return result
        self.run.side_effect=changed
        with self.assertRaisesRegex(AssertionError,'Unbound reference reconstruction worker'):self.compare()
        self.run.side_effect=original
        name=next(iter(self.rows));(self.root/name/runtime.gate.ARTIFACT_DIRECTORY/'unclaimed.bin').write_bytes(b'unclaimed')
        with self.assertRaisesRegex(AssertionError,'Missing or extra complete workflow artifact'):self.compare()

    def test_actual_two_runtimes_and_current_authority_are_required(self):
        with self.assertRaisesRegex(AssertionError,'two actual Python runtimes'):
            self.compare(python314=self.interpreters['3.11'])
        with self.assertRaisesRegex(AssertionError,'Missing current reference run authority'):
            self.compare(run_id=None)
