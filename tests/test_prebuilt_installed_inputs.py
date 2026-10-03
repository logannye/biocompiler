"""Owned installed layouts with nonexecuted synthetic images; actual Python cancellation child."""
import importlib.util
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


fixtures = load('distribution_fixture', ROOT / 'tests/test_core_distribution.py')
verifier = load('draft_binary_verifier', ROOT / 'tools/check_realization_binaries.py')
with patch.dict(sys.modules, {'check_realization_binaries': verifier}):
    campaign = load('draft_campaign_inputs', ROOT / 'tools/prebuilt_campaign_inputs.py')
probe = load('draft_process_probe', ROOT / 'tools/prebuilt_process_probe.py')


class InstalledInputsTests(unittest.TestCase):
    setUp = fixtures.CoreDistributionTests.setUp
    sync = fixtures.CoreDistributionTests.sync
    publish_manifest = fixtures.CoreDistributionTests.publish_manifest

    def arguments(self):
        return dict(directory=self.native.root / 'biocompiler_core', revision=self.tested_revision,
            target=self.target, source_revision=self.revision, run_id=self.run_id,
            core=self.native.root / 'biocompiler_core/bin/biocompiler-core',
            verify_binary=self.native.root / 'biocompiler_core/bin/biocompiler-verify')

    def installed(self, **updates):
        with patch.dict(sys.modules, {'biocompiler.core_distribution': fixtures.distribution}):
            return verifier.verify_installed(**(self.arguments() | updates))

    def test_exact_owned_paths_and_immutable_descriptor_without_binary_execution(self):
        selected = fixtures.distribution.installed_distribution()
        self.assertEqual(selected.executable('core'), self.arguments()['core'])
        with self.assertRaises(AttributeError):
            selected.package_root = Path('/other')
        proof = self.installed()
        self.assertEqual(proof['native']['revision'], self.tested_revision)
        self.assertEqual(proof['ownership']['source_revision'], self.revision)
        self.assertEqual(proof['ownership']['run_id'], self.run_id)
        self.assertEqual(set(proof['documents']), {'release.json', 'distribution.json', 'binaries.json', 'linkage.json'})
        self.assertEqual(set(proof['ownership']['sdk_files']),
            {'__init__.py', 'core_distribution.py', 'core_client.py', '_core_release.json'})
        self.negotiate.assert_not_called()

    def test_same_byte_artifact_mirror_symlink_and_wrong_owner_are_rejected(self):
        root = self.native.root / 'biocompiler_core'
        mirror = self.root / 'mirror'
        shutil.copytree(root, mirror)
        with self.assertRaisesRegex(ValueError, 'actual owned package'):
            self.installed(directory=mirror, core=mirror/'bin/biocompiler-core',
                verify_binary=mirror/'bin/biocompiler-verify')
        link = self.root / 'link'; link.symlink_to(self.arguments()['core'])
        with self.assertRaisesRegex(ValueError, 'exact owned path'):
            self.installed(core=link)
        with self.assertRaisesRegex(ValueError, 'exact owned path'):
            self.installed(core=mirror/'bin/biocompiler-core')
        for key, value in (('revision', '1'*40), ('source_revision', '2'*40), ('run_id', '999'), ('target', 'macos-arm64')):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'authority differs'):
                self.installed(**{key: value})

    def wrapper(self):
        args = self.arguments()
        with patch.dict(sys.modules, {'biocompiler.core_distribution': fixtures.distribution}):
            return campaign.InstalledCampaignInputs(native_root=args.pop('directory'),
                verify=args.pop('verify_binary'), **args)

    def test_campaign_keeps_old_native_projection_and_checks_all_owned_inputs_again(self):
        value = self.wrapper()
        before = value.native
        before['sha256']['biocompiler-core'] = 'changed'
        self.assertNotEqual(before, value.native)
        with patch.dict(sys.modules, {'biocompiler.core_distribution': fixtures.distribution}):
            proof = value.finish()
        self.assertEqual(proof['input_layout'], 'installed')
        self.assertEqual(proof['before'], proof['after'])
        self.assertEqual(proof['core'], str(self.arguments()['core']))
        with self.assertRaisesRegex(ValueError, 'already finalized'):
            value.finish()
        self.negotiate.assert_not_called()

    def test_campaign_rejects_changed_binary_even_if_record_and_release_are_repaired(self):
        value = self.wrapper()
        self.files['bin/biocompiler-core'] += b'changed image'
        self.sync()
        with patch.dict(sys.modules, {'biocompiler.core_distribution': fixtures.distribution}):
            with self.assertRaisesRegex(ValueError, 'changed during execution'):
                value.finish()
        self.assertFalse(value.completed)

    def test_flat_verifier_semantics_remain_exact_after_closed_layout_prefix(self):
        import ast
        current = ast.parse((ROOT / 'tools/check_realization_binaries.py').read_text())
        original = ast.parse((ROOT / 'tests/conformance/prebuilt-source-v1/tools/check_realization_binaries.py.source').read_text())
        current_functions = {node.name: node for node in current.body if isinstance(node, ast.FunctionDef)}
        for node in original.body:
            if isinstance(node, ast.FunctionDef) and node.name != 'main':
                observed = current_functions[node.name]
                if node.name == 'verify':
                    self.assertEqual(len(observed.body), len(node.body) + 3)
                    observed.body = observed.body[3:]
                self.assertEqual(ast.dump(observed), ast.dump(node))
        self.assertIn('verify_installed', current_functions)
        self.assertIn('executable_path', current_functions)


class StartedCancellationTests(unittest.TestCase):
    def test_actual_started_python_child_is_killed_and_reaped_by_installed_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            proof = probe.started_cancellation(Path(directory).resolve() / 'actual-child')
            self.assertIs(proof['native_execution'], False)
            self.assertIs(proof['reaped'], True)
            self.assertEqual(proof['parent'], os.getpid())
            self.assertEqual(proof['group'], proof['pid'])
            self.assertEqual(proof['attempts'], 1)
            self.assertGreaterEqual(proof['predicate_calls'], 2)
            with self.assertRaises(ChildProcessError):
                os.waitpid(proof['pid'], os.WNOHANG)
            with self.assertRaisesRegex(AssertionError, 'fresh absolute'):
                probe.started_cancellation(Path(directory).resolve() / 'actual-child')


if __name__ == '__main__':
    unittest.main()
