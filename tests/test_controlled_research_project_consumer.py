"""Closed, inert public consumer closure controls; no child or native execution."""
import ast
from pathlib import Path
import unittest
from unittest.mock import patch
from tools import check_controlled_research_project_consumer as consumer
from tools import check_controlled_research_project as campaign

class ControlledConsumerTests(unittest.TestCase):
    def test_closed_original_codec_census_excludes_actual_producers(self):
        self.assertEqual(len(consumer.MODULE_FILES),99);self.assertEqual(len(set(consumer.MODULE_FILES)),99)
        self.assertEqual(len({consumer.module_name(name) for name in consumer.MODULE_FILES}),99)
        for name in consumer.MODULE_FILES:
            self.assertTrue((campaign.ROOT/'src'/name).is_file());ast.parse((campaign.ROOT/'src'/name).read_bytes())
        for forbidden in ('biocompiler/compiler/circuit_construction.py','biocompiler/pipeline.py','biocompiler/reference_producer.py'):
            self.assertNotIn(forbidden,consumer.MODULE_FILES)
        self.assertIn('biocompiler/compiler/request.py',consumer.MODULE_FILES)
        self.assertIn('biocompiler/policy/research_project.py',consumer.MODULE_FILES)
    def test_empty_diagnostic_log_is_pinned_without_allowing_empty_inputs(self):
        import hashlib,tempfile
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp).resolve()/'empty.log';path.write_bytes(b'')
            self.assertEqual(consumer.log_pin(path),{'sha256':hashlib.sha256(b'').hexdigest(),'bytes':0})
            with self.assertRaisesRegex(AssertionError,'Oversized consumer input'):consumer.pin(path)

    def test_worker_and_parent_reject_local_native_execution(self):
        with patch.dict('os.environ',{},clear=True),patch('subprocess.Popen',side_effect=AssertionError('No execution')):
            with self.assertRaisesRegex(AssertionError,'hosted Linux'):consumer.worker(Path('/does-not-exist'))
            with self.assertRaisesRegex(AssertionError,'hosted Linux'):consumer.run_stage(package=None,verify=None,project=None,bundle=None,stage=None,output=None,expected_verify_sha256=None)
    def test_existing_public_zip_metadata_is_preserved_for_mutations(self):
        import json,tempfile,zipfile
        from biocompiler.core_client import encode_json
        from biocompiler.policy.material import _verify_staged
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'source.zip';target=Path(temp)/'changed.zip';fasta=b'>rna_0001 alphabet=RNA\nCCA\n>rna_0002 alphabet=RNA\nCCA\n';manifest={'report':{'human_use':'unassessed'}}
            with zipfile.ZipFile(source,'x') as archive:
                for name,raw in (('program.fasta',fasta),('manifest.json',encode_json(manifest))):
                    info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.external_attr=0o100644<<16;archive.writestr(info,raw)
            campaign.changed_bundle(source,target,'changed-fasta-b')
            changed=fasta.replace(b'CCA\n',b'CCA\n',1).split(b'\n');changed[3]=b'GCA'
            _verify_staged(target,(('program.fasta',b'\n'.join(changed)),('manifest.json',encode_json(manifest))))

if __name__=='__main__':unittest.main()
