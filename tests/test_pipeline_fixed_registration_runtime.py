"""Outer run/source/matrix bindings; semantic receipts have separate controls."""
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import pipeline_fixed_registration_runtime as runtime


_RUNTIME_IMPORT = '''if __package__:
    from .check_realization_binaries import executable_path as native_executable
else:
    from check_realization_binaries import executable_path as native_executable
'''
_RUNTIME_OLD_PATH = "(args.native_root / ('biocompiler-'+role)).resolve()"
_RUNTIME_NEW_PATH = 'native_executable(args.native_root, role).resolve()'
_RUNTIME_ORIGINAL_SHA256 = '8d2e16b1db25dd295e7ce204096bade148b94215cece9087a2dcb20a6b2980e6'


def restore_runtime_source(current):
    """The complete 0dd0fe54 runtime permits exactly the two layout edits."""
    addition = _RUNTIME_IMPORT.encode()
    anchor = b'from __future__ import annotations\n'
    before, after = _RUNTIME_OLD_PATH.encode(), _RUNTIME_NEW_PATH.encode()
    if (current.count(anchor) != 1 or current.count(anchor + addition) != 1
            or current.count(addition) != 1 or current.count(after) != 1 or before in current):
        raise AssertionError('Registration runtime layout edit census differs')
    original = current.replace(addition, b'', 1).replace(after, before, 1)
    if hashlib.sha256(original).hexdigest() != _RUNTIME_ORIGINAL_SHA256:
        raise AssertionError('Complete original registration runtime differs')
    return original


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


class FixedRegistrationInstalledPathTests(unittest.TestCase):
    def preflight(self, layout, mutation=None):
        """Exercise campaign_main up to the first native boundary, never enter it."""
        from biocompiler.core_distribution import InstalledCoreDistribution
        with tempfile.TemporaryDirectory() as temporary, ExitStack() as stack:
            root = Path(temporary).resolve()
            package = root / 'owned'
            binaries = package / 'bin' if layout == 'installed' else package
            binaries.mkdir(parents=True)
            paths, pins = {}, {}
            for role in ('core', 'verify'):
                path = binaries / ('biocompiler-' + role)
                raw = ('unexecuted ' + role + ' fixture').encode()
                path.write_bytes(raw)
                path.chmod(0o755)
                paths[role], pins[role] = path, hashlib.sha256(raw).hexdigest()
            native = {'sha256': {path.name: pins[role] for role, path in paths.items()}}
            selected = InstalledCoreDistribution(package, root / 'sdk', b'', b'', b'', b'',
                tuple(('bin/biocompiler-' + role, path, pins[role], path.stat().st_size)
                    for role, path in paths.items()), ())
            supplied, supplied_pins, native_root = dict(paths), dict(pins), package
            if mutation == 'swapped_roles':
                supplied = {'core': paths['verify'], 'verify': paths['core']}
            elif mutation == 'unowned_same_name':
                other = root / 'other' / paths['core'].name
                other.parent.mkdir()
                other.write_bytes(paths['core'].read_bytes())
                other.chmod(0o755)
                supplied['core'] = other
            elif mutation == 'symlink':
                link = root / paths['core'].name
                link.symlink_to(paths['core'])
                supplied['core'] = link
            elif mutation == 'not_executable':
                paths['core'].chmod(0o644)
            elif mutation == 'wrong_hash':
                supplied_pins['core'] = 'f' * 64
            elif mutation == 'relative_path':
                supplied['core'] = Path(paths['core'].name)
            elif mutation == 'wrong_root':
                native_root = root / 'foreign'
            elif mutation == 'unknown_layout':
                layout = 'unreviewed'
            elif mutation is not None:
                self.fail('Unknown fixture mutation')
            output = root / 'receipt.json'
            stack.enter_context(patch.dict(runtime.os.environ, {
                'BIOCOMPILER_NATIVE_INPUT_LAYOUT': layout,
                'GITHUB_SHA': 'a' * 40, 'GITHUB_HEAD_SHA': 'b' * 40, 'GITHUB_RUN_ID': '123'}))
            stack.enter_context(patch.object(runtime.gate, 'Corpus', return_value=object()))
            stack.enter_context(patch.object(runtime, 'product_sources', return_value={}))
            stack.enter_context(patch.object(runtime, 'campaign_sources', return_value={}))
            stack.enter_context(patch.object(runtime, 'metadata', return_value={}))
            stack.enter_context(patch.object(runtime.providers, 'installed_modules'))
            stack.enter_context(patch.object(runtime.r, 'verify_binaries', return_value=native))
            stack.enter_context(patch.object(runtime.platform, 'system', return_value='Linux'))
            stack.enter_context(patch.object(runtime.platform, 'machine', return_value='x86_64'))
            stack.enter_context(patch.object(runtime.Path, 'cwd', return_value=root))
            owner = stack.enter_context(patch('biocompiler.core_distribution.installed_distribution',
                return_value=selected))
            client = stack.enter_context(patch('biocompiler.core_client.CoreClient'))
            boundary = stack.enter_context(patch.object(runtime.manager, 'verify_rejection',
                side_effect=RuntimeError('pure fixture stopped before native execution')))
            campaign = stack.enter_context(patch.object(runtime.gate, 'campaign'))
            stack.enter_context(patch('subprocess.Popen', side_effect=AssertionError('Native execution forbidden')))
            arguments = ['--native-root', str(native_root), '--platform', 'linux-x86_64', '--output', str(output)]
            for role in ('core', 'verify'):
                arguments.extend(('--' + role, str(supplied[role]), '--' + role + '-sha256', supplied_pins[role]))
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(runtime.campaign_main(arguments), 1)
            receipt = json.loads(output.read_bytes())
            campaign.assert_not_called()
            if mutation is None:
                client.assert_called_once()
                boundary.assert_called_once_with(paths['verify'], pins['verify'], unittest.mock.ANY)
                self.assertEqual(receipt['executables'], {role: str(path) for role, path in paths.items()})
                self.assertEqual(receipt['error'], 'RuntimeError: pure fixture stopped before native execution')
                self.assertEqual(owner.call_count, 2 if layout == 'installed' else 0)
            else:
                client.assert_not_called()
                boundary.assert_not_called()
                expected = ('Installed role root differs' if mutation == 'wrong_root' and layout == 'installed'
                    else 'Unknown explicit native input layout' if mutation == 'unknown_layout'
                    else 'Unbound registration binary')
                self.assertIn(expected, receipt['error'])

    def test_real_campaign_preflight_accepts_both_owned_layouts(self):
        for layout in ('artifact', 'installed'):
            with self.subTest(layout=layout):
                self.preflight(layout)

    def test_real_campaign_preflight_rejects_unbound_roles_and_paths(self):
        for layout in ('artifact', 'installed'):
            for mutation in ('swapped_roles', 'unowned_same_name', 'symlink', 'not_executable',
                    'wrong_hash', 'relative_path', 'wrong_root', 'unknown_layout'):
                with self.subTest(layout=layout, mutation=mutation):
                    self.preflight(layout, mutation)

    def test_runtime_restores_whole_original_source_with_only_two_layout_edits(self):
        current = Path(runtime.__file__).read_bytes()
        original = restore_runtime_source(current)
        self.assertIn(_RUNTIME_OLD_PATH.encode(), original)
        self.assertNotIn(_RUNTIME_IMPORT.encode(), original)

    def test_runtime_restoration_rejects_additional_or_different_edits(self):
        current = Path(runtime.__file__).read_bytes()
        for changed in (current + b'\n', current.replace(b'path.is_absolute()', b'True'),
                current.replace(_RUNTIME_NEW_PATH.encode(), b'path.resolve()'),
                current + _RUNTIME_IMPORT.encode(),
                current.replace(_RUNTIME_IMPORT.encode(), b'', 1) + _RUNTIME_IMPORT.encode()):
            with self.subTest(sha256=hashlib.sha256(changed).hexdigest()), self.assertRaises(AssertionError):
                restore_runtime_source(changed)


if __name__ == '__main__':
    unittest.main()
