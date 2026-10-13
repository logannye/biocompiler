"""Inert editable-source copying and post-gate starter plans; no packaging/native work."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
from tools import controlled_composition_starter as starter
from tools import check_controlled_research_project as campaign

class ControlledStarterTests(unittest.TestCase):
    def test_editable_original_export_is_exact_and_claims_no_native_status(self):
        packet=campaign.checked_assets()
        with tempfile.TemporaryDirectory() as temp,patch('subprocess.Popen',side_effect=AssertionError('No native execution')):
            destination=Path(temp)/'editable';manifest=starter.stage_editable_inputs(packet,destination)
            self.assertEqual(manifest['native_status'],'not_run');self.assertEqual(manifest['files'],packet['pins'])
            self.assertEqual(campaign.checked_assets(destination)['inputs'],packet['inputs'])
            self.assertEqual(set(str(p.relative_to(destination)) for p in destination.rglob('*') if p.is_file()),set(campaign.INPUTS)|{'editable-inputs.json'})
            with self.assertRaisesRegex(AssertionError,'new editable'):starter.stage_editable_inputs(packet,destination)
    def test_editable_changed_original_rejected_before_copy(self):
        packet=campaign.checked_assets();packet['pins']=deepcopy(packet['pins']);packet['pins'][campaign.EXAMPLE]['sha256']='0'*64
        with tempfile.TemporaryDirectory() as temp,self.assertRaisesRegex(AssertionError,'before copy'):starter.stage_editable_inputs(packet,Path(temp)/'editable')
    def test_plan_preserves_scope_and_exact_sources_after_independent_receipt_check(self):
        # This test isolates the post-validator copy planner with explicit inert
        # bytes. Complete receipt validation has its own independent controls.
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);sdk=root/'sdk.inert';sdk.write_bytes(b'INERT SDK NEVER INSTALLED');receipt_path=root/'receipt.json';folder=root/'receipt';(folder/'rehearsal').mkdir(parents=True)
            sources={}
            for name in starter.SOURCE_FILES:
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'INERT SOURCE '+name.encode());pin=campaign.file_pin(path);sources[name]={'sha256':pin['sha256'],'size':pin['bytes']}
            binaries={}
            for role in ('core','verify'):
                path=root/(role+'.inert');path.write_bytes(b'INERT NEVER EXECUTED '+role.encode());binaries[role]=path
            for case in campaign.CASE_IDS:
                (folder/'rehearsal'/(case+'-project.json')).write_bytes(b'INERT PROJECT')
                if case in campaign.ACCEPTED:(folder/'rehearsal'/(case+'.zip')).write_bytes(b'INERT ARCHIVE')
            receipt={'sdk_wheel':{'name':sdk.name,**campaign.file_pin(sdk)},'binaries':{role:campaign.file_pin(path) for role,path in binaries.items()},'files':{},'empty_logs':[], 'native_authority':{'sources':sources},'identity':{'revision':'inert'}}
            receipt_path.write_bytes(campaign.canonical(receipt))
            def plan():return starter.plan(root=root,receipt_path=receipt_path,sdk_wheel=sdk,binaries=binaries)
            with patch.object(starter.installed,'validate_retained',return_value={}) as validate,patch('subprocess.Popen',side_effect=AssertionError('No native execution')):
                files,manifest=plan();validate.assert_called_once()
                self.assertEqual(set(files),set(manifest['files']));self.assertEqual(manifest['rc7_four_slot_acceptance'],'not_performed');self.assertEqual(manifest['human_use'],'unassessed')
                self.assertEqual(len([name for name in files if name.startswith('accepted/')]),6)
                with patch.object(starter,'MAX_TOTAL',1),self.assertRaisesRegex(AssertionError,'total byte'):plan()
                path=root/starter.SOURCE_FILES[0];path.write_bytes(b'ALTERED')
                with self.assertRaisesRegex(AssertionError,'source differs'):plan()
    def test_starter_native_assembly_is_hosted_only(self):
        with patch.dict('os.environ',{},clear=True),self.assertRaisesRegex(AssertionError,'hosted-only'):starter.create(SimpleNamespace())

if __name__=='__main__':unittest.main()
