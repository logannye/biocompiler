"""Public editable example witnesses; no native process, install or network."""
from copy import deepcopy
from contextlib import ExitStack
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from biocompiler.core_client import CoreProtocolError
from tools import check_controlled_research_project as campaign

ROOT=Path(__file__).resolve().parents[1]

class ControlledCompositionExampleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name)
        self.example=campaign.load_example(ROOT/campaign.EXAMPLE);self.packet=campaign.checked_assets()
        self.guards=ExitStack();self.addCleanup(self.guards.close)
        for target in ('subprocess.Popen','socket.socket','os.system','os.posix_spawn'):
            self.guards.enter_context(patch(target,side_effect=AssertionError('Pure example cannot execute or use network')))

    def test_explicit_relative_cli_native_path_is_normalized_without_execution(self):
        from types import SimpleNamespace
        args=SimpleNamespace(core=Path('bin/biocompiler-core'),core_sha256='a'*64)
        with patch.object(self.example,'CoreClient',return_value='inert-client') as client:
            self.assertEqual(self.example._transport(args,'core'),'inert-client')
            client.assert_called_once_with(Path('bin/biocompiler-core').absolute(),role='core',expected_sha256='a'*64)

    def test_all_preparations_and_public_edits_equal_independent_originals(self):
        before=deepcopy(self.packet['inputs'])
        for case in self.packet['expected']['cases']:
            with self.subTest(case=case['id']):
                path,project=campaign.prepare_case(self.example,self.packet,case,self.folder)
                self.assertEqual(project.request,before[case['id']]);self.assertEqual(project.limits,before[case['id']]['limits'])
                self.assertEqual(project.schema if hasattr(project,'schema') else project.data['schema_version'],'biocompiler.research_project.v0.3')
                preflight=self.example.preflight(path);self.assertEqual(preflight['native_status'],'not_run')
                explanation=self.example.explain(path)
                self.assertEqual(explanation['products'],['MA','MG']);self.assertEqual(explanation['rna_members'],['rna-a','rna-b'])
                self.assertEqual(explanation['empirical_status'],'unassessed');self.assertIsNone(explanation['native_report'])
        self.assertEqual(self.packet['inputs'],before)

    def test_requested_deadline_edits_preserve_actual_model_and_material(self):
        case=self.packet['expected']['cases'][0];path,_=campaign.prepare_case(self.example,self.packet,case,self.folder)
        changed=self.example.edit(path,self.folder/'edited.json',deadlines={'onset_ticks':1,'controller_off_ticks':1})
        original=self.packet['inputs']['baseline']['behavior_request']['original'];edited=changed.request['behavior_request']['original']
        for key in ('mechanism_model','material_authority','assembly','catalog_binding','context'):
            self.assertEqual(edited[key],original[key])
        self.assertEqual(edited['source_authority']['control_contract']['actual_delays'],original['source_authority']['control_contract']['actual_delays'])
        for value in (0,True,1.5):
            with self.subTest(value=value),self.assertRaises((ValueError,CoreProtocolError)):
                self.example.edit(path,self.folder/'bad.json',deadlines={'onset_ticks':value})
        self.assertFalse((self.folder/'bad.json').exists())

    def test_preparation_preserves_original_and_existing_destinations(self):
        original=ROOT/campaign.ASSETS/'baseline-input.json';raw=original.read_bytes()
        with self.assertRaisesRegex(ValueError,'overwrite'):self.example.prepare(original,original)
        output=self.folder/'existing.json';output.write_bytes(b'existing')
        with self.assertRaises(FileExistsError):self.example.prepare(original,output)
        self.assertEqual(output.read_bytes(),b'existing');self.assertEqual(original.read_bytes(),raw)
        redirected=self.folder/'link.json';redirected.symlink_to(original)
        with self.assertRaises(ValueError):self.example.prepare(redirected,self.folder/'new.json')

    def test_readers_fail_closed_before_project_publication(self):
        for index,raw in enumerate((b'',b'{}',b'{"schema_version":1,"schema_version":2}',b'[]')):
            path=self.folder/str(index);path.write_bytes(raw)
            with self.subTest(index=index),self.assertRaises((ValueError,CoreProtocolError)):
                self.example.prepare(path,self.folder/'out.json')
        self.assertFalse((self.folder/'out.json').exists())
        original=ROOT/campaign.ASSETS/'baseline-input.json'
        with patch.object(self.example,'MAX_INPUT_BYTES',5),self.assertRaisesRegex(ValueError,'bound'):
            self.example.read_input(original)

if __name__=='__main__':unittest.main()
