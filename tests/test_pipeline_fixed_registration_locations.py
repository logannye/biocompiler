"""Real pure-Python original/current equality from external package placement."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import check_pipeline_fixed_registration_install as gate


class RegistrationLocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='biocompiler-registration-placement-')
        cls.addClassCleanup(cls.directory.cleanup)
        root = Path(cls.directory.name)
        # Copy only Python source. No wheel build, native library, binary, saved
        # accepted records or captured expectation is executable input.
        for source in (gate.ROOT / 'src/biocompiler').rglob('*.py'):
            target = root / 'biocompiler' / source.relative_to(gate.ROOT / 'src/biocompiler')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        script = '''import importlib,json,pathlib,sys
sys.path[:0]=[sys.argv[1],sys.argv[2]]
import biocompiler
from tools import check_pipeline_fixed_registration_install as gate
from tools import pipeline_original_counterpart as counterpart
for name in sorted(gate.manager.TRANSPORT_MODULES):importlib.import_module(name)
oracle=gate.continuation.load_oracle()
module=gate.load_body_module(installed=True)
original=counterpart.run('fixed-registration-original')
locations=gate.provider_locations()
current=gate.capture_original(module=module,oracle=oracle)
assert gate.provider_locations()==locations
gate.providers.installed_modules()
pathlib.Path(sys.argv[3]).write_bytes(gate.canonical(dict(original=original,current=current,locations=locations)))
'''
        result = subprocess.run([sys.executable, '-I', '-B', '-c', script,
            str(gate.ROOT), str(root), str(root / 'capture.json')], cwd=root,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
        if result.returncode:
            raise AssertionError(result.stderr.decode(errors='replace'))
        cls.fresh = json.loads((root / 'capture.json').read_bytes())
        cls.projected = gate.compare_original(**cls.fresh)

    def test_real_installed_placement_changes_only_eighteen_authenticated_paths(self):
        original, current = self.fresh['original']['value'], self.fresh['current']
        self.assertNotEqual(original, current)
        differences = []
        for identity, item in current['providers'].items():
            before = original['providers'][identity]
            if before != item:
                self.assertEqual(set(before), set(item))
                self.assertEqual([key for key in item if item[key] != before[key]], ['file'])
                differences.append(identity)
        self.assertEqual(len(differences), 18)
        self.assertEqual(gate.compare_original(**self.fresh), original)
        self.assertEqual(gate.provider_projection(current, self.fresh['locations']), original)
        self.assertIs(gate.validate_original(gate.Corpus(), current), current)
        # Exact raw evidence is retained; neither comparison mutates it.
        self.assertTrue(all(current['providers'][key]['file'] in ('synthetic.py', 'components.py')
            for key in differences))
        local_locations = gate.provider_locations()
        local = gate.capture_original()
        self.assertEqual(gate.provider_projection(local, local_locations), original)

    def test_forged_locations_and_source_pins_are_rejected(self):
        for field, value in (('path', '/another/synthetic.py'), ('sha256', '0' * 64),
                ('bytes', 1), ('logical', 'src/biocompiler/synthesis/synthetic.py'),
                ('module', 'biocompiler.synthesis.synthetic')):
            with self.subTest(field=field):
                fresh = deepcopy(self.fresh)
                fresh['locations']['sources'][0][field] = value
                with self.assertRaises((AssertionError, KeyError)):
                    gate.compare_original(**fresh)
        for field, value in (('package_path', '/other/biocompiler/__init__.py'),
                ('source_root', '/other/checkout')):
            with self.subTest(field=field):
                fresh = deepcopy(self.fresh); fresh['locations'][field] = value
                with self.assertRaises(AssertionError): gate.compare_original(**fresh)

    def test_paths_other_provider_fields_and_slot_census_are_not_normalized(self):
        identity = next(key for key, item in self.fresh['current']['providers'].items()
            if item.get('module') == 'biocompiler.compiler.synthetic')
        for field, value in (('file', '/forged/synthetic.py'), ('file', 'src/biocompiler/compiler/synthetic.py'),
                ('module', 'biocompiler.synthesis.synthetic'), ('line', 1), ('source', 'forged'),
                ('defaults', ['forged']), ('closure', {}), ('qualname', 'run_synthetic_pipeline.<locals>.forged')):
            with self.subTest(field=field, value=value):
                fresh = deepcopy(self.fresh); fresh['current']['providers'][identity][field] = value
                with self.assertRaises(AssertionError): gate.compare_original(**fresh)
        for extra in (False, True):
            fresh = deepcopy(self.fresh)
            item = fresh['current']['providers'][identity]
            if extra: fresh['current']['providers']['forged/extra'] = deepcopy(item)
            else: del fresh['current']['providers'][identity]
            with self.subTest(extra=extra), self.assertRaises(AssertionError): gate.compare_original(**fresh)

    def test_complete_state_and_callback_graphs_remain_authoritative(self):
        for field in ('initial', 'final', 'graph'):
            fresh = deepcopy(self.fresh); fresh['current']['cases'][0][field]['forged'] = True
            with self.subTest(field=field), self.assertRaises(AssertionError): gate.compare_original(**fresh)

    def test_live_source_bytes_and_entry_identity_are_checked(self):
        module = gate.importlib.import_module('biocompiler.compiler.synthetic')
        with patch.object(module, 'run_synthetic_pipeline', lambda: None), self.assertRaisesRegex(
                AssertionError, 'live provider entry'):
            gate.provider_locations()
        original = gate.r.raw_file
        target = Path(module.__file__).resolve()
        reads = []
        def altered(path):
            if Path(path) == target:
                reads.append(path)
                if len(reads) == 1:
                    return b'forged'
            return original(path)
        with patch.object(gate.r, 'raw_file', side_effect=altered), self.assertRaisesRegex(
                AssertionError, 'installed provider source'):
            gate.provider_locations()

    def test_failed_comparison_preserves_both_raw_captures_before_native(self):
        counterpart = gate.providers.tool('pipeline_original_counterpart')
        locations = self.fresh['locations']
        current = deepcopy(self.fresh['current']); current['cases'][0]['graph']['forged'] = True
        with tempfile.TemporaryDirectory() as directory:
            receipt = {'_artifact_directory': directory, 'artifacts': {}}
            with patch.object(gate.continuation, 'load_oracle'), patch.object(gate, 'load_body_module'), \
                    patch.object(counterpart, 'run', return_value=self.fresh['original']), \
                    patch.object(gate, 'provider_locations', return_value=locations), \
                    patch.object(gate, 'capture_original', return_value=current), \
                    patch.object(gate, 'NativeWitness') as native:
                with self.assertRaisesRegex(AssertionError, 'Current ordinary behavior differs'):
                    gate.campaign(None, None, receipt)
                native.assert_not_called()
            artifacts = gate.manager.Artifacts(Path(directory), receipt['artifacts'])
            retained = artifacts.json(receipt['fresh_original'], gate.r.MAX_ARTIFACT_BYTES)
            self.assertEqual(retained, dict(original=self.fresh['original'], current=current, locations=locations))


if __name__ == '__main__':
    unittest.main()
