"""Exact ordinal partitions and retained worker proofs using inert Python peers."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import synthetic_inspection_workers as w
from tests import test_synthetic_inspection_boundaries as fixture

p = w.p
BARRIER = '''import pathlib,sys,time
root=pathlib.Path(sys.argv[1]);index=sys.argv[2]
(root/(index+".ready")).write_text("ready")
deadline=time.monotonic()+5
while not all((root/(str(i)+".ready")).is_file() for i in (0,1)):
 if time.monotonic()>deadline:raise SystemExit(9)
 time.sleep(.01)
print("both isolated workers overlapped",flush=True)
'''


class SyntheticInspectionWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.SyntheticInspectionBoundaryTests.setUpClass()
        cls.addClassCleanup(fixture.SyntheticInspectionBoundaryTests.doClassCleanups)
        cls.fixture = fixture.SyntheticInspectionBoundaryTests
        cls.corpus = cls.fixture.small
        cls.parent = deepcopy(cls.fixture.receipt)
        cls.parent.update(schema_version=p.SCHEMA, status='success', revision='a'*40, source_revision='b'*40,
            execution=p.PARALLEL_EXECUTION,
            run_id='inspection-worker-fixture', python_version='3.11.15', system='Linux', machine='x86_64',
            native_platform='linux-x86_64', package_path='/installed/biocompiler/__init__.py', scope=p.SCOPE,
            native_inputs={'revision':'a'*40}, transport_sources={'fixture':'c'*64},
            campaign_sources=p.source_pins(p.SOURCES), artifact_directory=p.ARTIFACT_DIRECTORY, **p.metadata(cls.corpus))

    def part(self, folder, index):
        folder.mkdir(parents=True, exist_ok=True)
        (folder/'worker.log').write_text('complete inert worker diagnostics\n')
        artifacts = folder/p.ARTIFACT_DIRECTORY; artifacts.mkdir()
        result = deepcopy(self.parent)
        result.pop('_artifact_directory', None)
        result.update(schema_version=w.SCHEMA, worker_index=index, worker_count=2)
        result['execution']={'mode':'occurrence_worker','workers':2,'index':index}
        result['checks'] = [result['checks'][i] for i in w.ordinals(self.corpus,index)]
        result['completed_checks'] = len(result['checks'])
        if index:
            for field in ('verify_capabilities','verify_capability_guard'): result.pop(field)
        used = p.canonical(result['checks']) + p.canonical({key:result[key] for key in
            ('verify_capabilities','verify_capability_guard') if key in result})
        result['artifacts'] = {pin:row for pin,row in result['artifacts'].items() if pin.encode() in used}
        for row in result['artifacts'].values():
            shutil.copyfile(self.fixture.artifacts/row['path'],artifacts/row['path'])
        (folder/'receipt.json').write_bytes(p.canonical(result)+b'\n')
        return result

    def parts(self, directory):
        root=Path(directory)/w.ROOT_NAME
        for index in (0,1): self.part(root/str(index),index)
        return root

    def test_exact_complete_ordinal_partition_and_full_semantic_reconstruction(self):
        full = self.fixture.full
        left,right=w.ordinals(full,0),w.ordinals(full,1)
        self.assertEqual(sorted(left+right),list(range(9668)))
        self.assertFalse(set(left)&set(right)); self.assertEqual((len(left),len(right)),(4834,4834))
        with tempfile.TemporaryDirectory() as directory:
            root=self.parts(directory)
            combined,artifacts,metadata=w.collect(root,self.parent,self.corpus)
            for field in ('checks','artifacts','verify_capabilities','verify_capability_guard'):
                self.assertEqual(combined[field],self.parent[field])
            self.assertEqual(len(p.validate_checks(combined,self.corpus,artifacts)['checks']),18)
            combined['occurrence_workers']=metadata
            w.validate_evidence(directory,combined,self.corpus)

    def test_worker_authority_order_census_and_claim_corruptions_fail(self):
        for mutation in ('source','index','count','typed_metadata','missing_field','missing','duplicate','order','status','unassigned_capability'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as directory:
                root=self.parts(directory);file=root/'1/receipt.json';value=p.decode(file.read_bytes())
                if mutation=='source':value['source_revision']='d'*40
                elif mutation=='index':value['worker_index']=0
                elif mutation=='count':value['worker_count']=2.0
                elif mutation=='typed_metadata':value['original_occurrences']=float(value['original_occurrences'])
                elif mutation=='missing_field':del value['campaign_sources']
                elif mutation=='missing':value['checks'].pop();value['completed_checks']-=1
                elif mutation=='duplicate':value['checks'][1]=deepcopy(value['checks'][0])
                elif mutation=='order':value['checks'].reverse()
                elif mutation=='status':value['status']='failure'
                else:value['verify_capabilities']=self.parent['verify_capabilities']
                file.write_bytes(p.canonical(value)+b'\n')
                with self.assertRaises(AssertionError):w.collect(root,self.parent,self.corpus)

    def test_raw_worker_semantics_cannot_be_hidden_by_rehashing_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root=self.parts(directory);file=root/'0/receipt.json';value=p.decode(file.read_bytes())
            row=value['checks'][0];old=row['exchanges'][1]['request'];raw=(root/'0'/p.ARTIFACT_DIRECTORY/(old+'.bin')).read_bytes()+b' '
            new=p.sha(raw);row['exchanges'][1]['request']=new
            value['artifacts'][new]={'path':new+'.bin','bytes':len(raw),'sha256':new}
            (root/'0'/p.ARTIFACT_DIRECTORY/(new+'.bin')).write_bytes(raw)
            if old.encode() not in p.canonical(value['checks'])+p.canonical(value['verify_capabilities']):
                del value['artifacts'][old];(root/'0'/p.ARTIFACT_DIRECTORY/(old+'.bin')).unlink()
            file.write_bytes(p.canonical(value)+b'\n')
            with self.assertRaisesRegex(AssertionError,'wire-boundary evidence'):
                w.collect(root,self.parent,self.corpus)

    def test_postrun_rejects_removed_metadata_changed_logs_and_changed_aggregate(self):
        with tempfile.TemporaryDirectory() as directory:
            root=self.parts(directory);combined,_,metadata=w.collect(root,self.parent,self.corpus)
            with self.assertRaisesRegex(AssertionError,'evidence metadata'):w.validate_evidence(directory,combined,self.corpus)
            combined['occurrence_workers']=metadata
            for field in ('log','metadata','aggregate'):
                changed=deepcopy(combined)
                if field=='log':(root/'1/worker.log').write_text('changed diagnostics\n')
                elif field=='metadata':changed['occurrence_workers']['source_pins']={}
                else:changed['checks'].reverse()
                with self.subTest(field=field),self.assertRaises(AssertionError):w.validate_evidence(directory,changed,self.corpus)
                (root/'1/worker.log').write_text('complete inert worker diagnostics\n')
            shutil.rmtree(root)
            combined.pop('occurrence_workers')
            with self.assertRaisesRegex(AssertionError,'evidence metadata'):w.validate_evidence(directory,combined,self.corpus)
            combined['execution']={'mode':'serial_diagnostic','workers':1}
            with self.assertRaisesRegex(AssertionError,'evidence metadata'):w.validate_evidence(directory,combined,self.corpus)

    def test_missing_extra_symlinked_worker_evidence_fails(self):
        for mutation in ('missing','extra','symlink'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as directory:
                root=self.parts(directory)
                if mutation=='missing':shutil.rmtree(root/'1')
                elif mutation=='extra':(root/'unclaimed').mkdir()
                else:
                    (root/'1').rename(root/'other');(root/'1').symlink_to(root/'other',target_is_directory=True)
                with self.assertRaises(AssertionError):w.collect(root,self.parent,self.corpus)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);aggregate=root/p.ARTIFACT_DIRECTORY;aggregate.mkdir()
            outside=root/'missing-target';(root/w.ROOT_NAME).symlink_to(outside,target_is_directory=True)
            with patch.object(w.subprocess,'Popen') as start, self.assertRaisesRegex(AssertionError,'destination already exists'):
                w.execute(SimpleNamespace(output=root/'receipt.json'),aggregate,self.parent,self.corpus)
            start.assert_not_called();self.assertFalse(outside.exists())

    def execute_fixture(self,directory,*,failure=False,launch_failure=False):
        root=Path(directory);aggregate=root/p.ARTIFACT_DIRECTORY;aggregate.mkdir()
        output=root/'receipt.json';calls=[];waited=[];children=[]
        args=SimpleNamespace(output=output,core=Path(self.parent['executables']['core']),
            verify=Path(self.parent['executables']['verify']),core_sha256='c'*64,verify_sha256='d'*64,
            native_root=root/'native',platform='linux-x86_64')
        actual_popen=subprocess.Popen
        def start(command,**options):
            index=int(command[command.index('--worker-index')+1]);calls.append(index)
            self.assertEqual(command[:2],[sys.executable,str(Path(w.__file__).with_name('check_native_synthetic_inspection.py').resolve())])
            self.assertEqual(command[command.index('--workers')+1],'1')
            self.assertEqual(options['env']['GITHUB_SHA'],self.parent['revision'])
            self.assertEqual(options['env']['GITHUB_HEAD_SHA'],self.parent['source_revision'])
            self.assertEqual(options['env']['GITHUB_RUN_ID'],self.parent['run_id'])
            if launch_failure and index==1:raise OSError('inert second worker launch failure')
            folder=Path(command[command.index('--output')+1]).parent
            self.part(folder,index)
            if failure or launch_failure:
                class Failed:
                    def wait(self):waited.append(index);return 1 if failure and index==0 else 0
                return Failed()
            child=actual_popen([sys.executable,'-c',BARRIER,str(root),str(index)],stdout=options['stdout'],stderr=options['stderr'])
            children.append(child)
            class Running:
                def wait(self):
                    self_outer.assertEqual(calls,[0,1]);waited.append(index);return child.wait(timeout=10)
            self_outer=self
            return Running()
        receipt=deepcopy(self.parent);receipt.update(checks=[],artifacts={},_artifact_directory=str(aggregate))
        receipt.pop('verify_capabilities');receipt.pop('verify_capability_guard')
        try:
            with patch.object(w.subprocess,'Popen',side_effect=start):
                if failure or launch_failure:
                    with self.assertRaises((AssertionError,OSError)):w.execute(args,aggregate,receipt,self.corpus)
                else:w.execute(args,aggregate,receipt,self.corpus)
        finally:
            for child in children:
                if child.poll() is None:child.kill();child.wait()
        self.assertEqual(waited,[0] if launch_failure else [0,1])
        if failure or launch_failure:self.assertFalse(list(aggregate.iterdir()))
        else:
            self.assertEqual(receipt['checks'],self.parent['checks'])
            w.validate_evidence(root,receipt,self.corpus)
            self.assertEqual(len(p.validate_checks(receipt,self.corpus,p.Artifacts(aggregate,receipt['artifacts']))['checks']),18)

    def test_two_real_inert_processes_overlap_and_publish_original_order(self):
        with tempfile.TemporaryDirectory() as directory:self.execute_fixture(directory)

    def test_nonzero_and_launch_failure_drain_every_started_worker(self):
        for launch in (False,True):
            with self.subTest(launch=launch),tempfile.TemporaryDirectory() as directory:
                self.execute_fixture(directory,failure=not launch,launch_failure=launch)
