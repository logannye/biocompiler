"""Outer run/source/matrix bindings; semantic receipts have separate controls."""
from contextlib import ExitStack
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import pipeline_fixed_registration_runtime as runtime


class FixedRegistrationRuntimeTests(unittest.TestCase):
    revision = 'a' * 40
    source_revision = 'b' * 40
    run_id = '12345'

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'realization'
        self.native_root = Path(self.temporary.name) / 'native'
        self.root.mkdir()
        self.native_root.mkdir()
        self.rows = {}
        self.inputs = {}
        self.binaries = {}
        self.sources = {'src/biocompiler/example.py': 'c' * 64}
        self.tools = {'tools/example.py': 'd' * 64}
        self.metadata = {'coverage': {'methods': 3}, 'declarations': {'protocol/example.json': 'e' * 64}}
        for target, (system, machine) in runtime.r.PLATFORMS.items():
            native = {'revision': self.revision, 'system': system, 'machine': machine,
                'sha256': {'biocompiler-core': '1' * 64, 'biocompiler-verify': '2' * 64}}
            self.binaries[target] = native
            (self.native_root / target).mkdir()
            for python in runtime.r.PYTHONS:
                name = 'realization-'+target+'-py'+python
                slot = self.root / name
                (slot / runtime.gate.ARTIFACT_DIRECTORY).mkdir(parents=True)
                inputs = {**native, 'run_id': self.run_id, 'source_revision': self.source_revision,
                    'python_version': python+'.99'}
                self.inputs[name] = inputs
                self.rows[name] = {'schema_version': runtime.gate.SCHEMA, 'status': 'success',
                    'scope': runtime.gate.SCOPE, 'revision': self.revision,
                    'source_revision': self.source_revision, 'run_id': self.run_id,
                    'python_version': inputs['python_version'], 'system': system, 'machine': machine,
                    'native_platform': target, 'artifact_directory': runtime.gate.ARTIFACT_DIRECTORY,
                    'native_inputs': native, 'python_sources': self.sources, 'campaign_sources': self.tools,
                    **self.metadata, 'package_path': '/installed/site-packages/biocompiler/__init__.py',
                    'executables': {'core': '/installed/native/biocompiler-core',
                        'verify': '/installed/native/biocompiler-verify'}, 'artifacts': {}}
        self.save()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(runtime.gate, 'Corpus', return_value=object()))
        self.stack.enter_context(patch.object(runtime, 'product_sources', return_value=self.sources))
        self.stack.enter_context(patch.object(runtime, 'campaign_sources', return_value=self.tools))
        self.stack.enter_context(patch.object(runtime, 'metadata', return_value=self.metadata))
        self.verify_binaries = self.stack.enter_context(patch.object(runtime.r, 'verify_binaries',
            side_effect=lambda path, revision, target: copy.deepcopy(self.binaries[target])))
        self.validate = self.stack.enter_context(patch.object(runtime.gate, 'validate_checks',
            create=True, return_value=[{'id': str(index), 'events': 11} for index in range(3)]))

    def save(self):
        for name, row in self.rows.items():
            (self.root / name / runtime.gate.RECEIPT_FILE).write_bytes(runtime.canonical(row)+b'\n')
            (self.root / name / 'native-inputs.json').write_bytes(runtime.canonical(self.inputs[name])+b'\n')

    def compare(self, **changes):
        return runtime.compare(self.root, self.native_root, **{
            'revision': self.revision, 'source_revision': self.source_revision,
            'run_id': self.run_id, **changes})

    def test_complete_four_slot_matrix_invokes_every_semantic_reconstruction(self):
        result = self.compare()
        self.assertEqual(result['status'], 'success')
        self.assertEqual(set(result['receipts']), set(self.rows))
        self.assertEqual(self.validate.call_count, 4)
        self.assertEqual(self.verify_binaries.call_count, 2)
        for call in self.validate.call_args_list:
            self.assertEqual(call.args[0]['source_revision'], self.source_revision)
            self.assertIsInstance(call.args[2], runtime.manager.Artifacts)

    def test_missing_extra_or_symlinked_runtime_slot_cannot_be_a_matrix(self):
        name = next(iter(self.rows))
        slot = self.root / name
        holding = self.root / 'held-slot'
        slot.rename(holding)
        with self.assertRaisesRegex(AssertionError, 'Incomplete four-runtime'):
            self.compare()
        slot.symlink_to(holding, target_is_directory=True)
        with self.assertRaisesRegex(AssertionError, 'Unsafe registration runtime slot'):
            self.compare()
        slot.unlink()
        holding.rename(slot)
        (self.root / 'realization-extra').mkdir()
        with self.assertRaisesRegex(AssertionError, 'Incomplete four-runtime'):
            self.compare()

    def test_rewritten_receipt_cannot_change_current_source_run_or_native_authority(self):
        name = next(iter(self.rows))
        baseline = copy.deepcopy(self.rows[name])
        changes = {'status': 'running', 'revision': 'f' * 40, 'source_revision': 'f' * 40,
            'run_id': 'old', 'python_version': '3.10.99', 'native_platform': 'other',
            'python_sources': {}, 'campaign_sources': {}, 'declarations': {},
            'coverage': {}, 'native_inputs': {}, 'artifact_directory': 'other'}
        for key, value in changes.items():
            with self.subTest(field=key):
                self.rows[name] = {**copy.deepcopy(baseline), key: value}
                self.save()
                with self.assertRaisesRegex(AssertionError, 'Stale or mixed registration receipt'):
                    self.compare()
        self.rows[name] = baseline

    def test_rewritten_input_manifest_cannot_mix_run_source_runtime_or_binaries(self):
        name = next(iter(self.inputs))
        baseline = copy.deepcopy(self.inputs[name])
        for key, value in {'run_id': 'other', 'source_revision': 'f' * 40,
                'python_version': '3.10.99', 'sha256': {}}.items():
            with self.subTest(field=key):
                self.inputs[name] = {**copy.deepcopy(baseline), key: value}
                self.save()
                with self.assertRaisesRegex(AssertionError, 'Stale registration native inputs'):
                    self.compare()
        self.inputs[name] = baseline

    def test_unbound_package_and_role_paths_reject(self):
        name = next(iter(self.rows))
        baseline = copy.deepcopy(self.rows[name])
        for change, message in (
            ({'package_path': str(runtime.ROOT / 'src/biocompiler/__init__.py')}, 'not installed'),
            ({'package_path': 'relative/package.py'}, 'not installed'),
            ({'executables': {'core': '/installed/biocompiler-verify',
                'verify': '/installed/biocompiler-core'}}, 'binary selection absent'),
            ({'executables': {'core': '/installed/biocompiler-core',
                'verify': '/elsewhere/biocompiler-verify'}}, 'binary selection absent')):
            with self.subTest(change=change):
                self.rows[name] = {**copy.deepcopy(baseline), **change}
                self.save()
                with self.assertRaisesRegex(AssertionError, message):
                    self.compare()

    def test_inner_semantic_failure_or_cross_runtime_difference_is_not_hidden(self):
        self.validate.side_effect = AssertionError('semantic evidence changed')
        with self.assertRaisesRegex(AssertionError, 'semantic evidence changed'):
            self.compare()
        self.validate.side_effect = [[{'case': 1}], [{'case': 2}]]
        with self.assertRaisesRegex(AssertionError, 'observations differ across four runtimes'):
            self.compare()

    def test_current_authority_is_required_before_loading_artifacts(self):
        for changes in ({'revision': None}, {'source_revision': 'abc'}, {'run_id': ''}):
            with self.subTest(changes=changes), self.assertRaisesRegex(AssertionError, 'Missing current'):
                self.compare(**changes)
        self.validate.assert_not_called()


if __name__ == '__main__':
    unittest.main()
