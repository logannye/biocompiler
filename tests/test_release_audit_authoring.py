"""Typed release audit: pure correspondence, closed census and hostile handoffs.

Use BIOCOMPILER_AUTHORING_SOURCE_ROOT for the frozen typed source checkout.
Synthetic files are inert copy-plan controls, never native acceptance evidence.
"""
from __future__ import annotations

import ast
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import release_audit as cli
from tools import release_audit_plan as plan
import release_audit_authoring as audit
from tests import test_release_audit_researcher as historical

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('BIOCOMPILER_AUTHORING_SOURCE_ROOT', ROOT.parent / 'researcher-authoring')).resolve()
PROFILE = json.loads((ROOT / 'protocol/release-audit-researcher-authoring-v1.json').read_text())


def git_row(name, raw):
    return '100644 blob ' + hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() + '\t' + name


def pin(raw, *, child=False):
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes' if child else 'size': len(raw)}


class AuthoringAuditTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(sys, 'path', [str(SOURCE / 'tools'), str(SOURCE / 'src'), str(SOURCE), *sys.path]))
        self.stack.enter_context(patch.dict(sys.modules))
        for name, module in list(sys.modules.items()):
            origin = getattr(module, '__file__', None)
            if not origin:
                continue
            expected = SOURCE / 'tools' / (name + '.py')
            if '.' not in name and expected.is_file() and Path(origin).resolve() != expected:
                sys.modules.pop(name, None)
            elif name == 'biocompiler' or name.startswith('biocompiler.'):
                if not Path(origin).resolve().is_relative_to(SOURCE / 'src'):
                    sys.modules.pop(name, None)
        for target in ('subprocess.run', 'subprocess.Popen', 'subprocess.check_output', 'os.system',
                       'os.posix_spawn', 'socket.socket', 'socket.create_connection', 'ctypes.CDLL'):
            self.stack.enter_context(patch(target, side_effect=AssertionError('Inert audit forbids execution/network')))
        self.starter = importlib.import_module('researcher_alpha_starter')
        self.installed = importlib.import_module('check_researcher_alpha_installed')
        for target in ('source_authority', 'create_starter'):
            self.stack.enter_context(patch.object(self.starter, target, side_effect=AssertionError('No Git or assembler')))
        self.folder = Path(self.stack.enter_context(tempfile.TemporaryDirectory())).resolve()

    def test_historical_profile_bytes_and_all_other_classifications_are_preserved(self):
        expected = {
            'release-audit-v1.json': '87aa3b5209a0f4f6e4bac675fa18593922cfeaf46e4a051cb0dfde72c935e08d',
            'release-audit-component-v1.json': '3d6872560ca6a419c855e5e610dad1b10597187ce838aac1cd1900202606f83c',
            'release-audit-researcher-alpha-v1.json': '04b2f755204ce00610da793d88a9a12d127f3b90f70f2338e8d367d66a285f63',
        }
        for name, digest in expected.items():
            self.assertEqual(hashlib.sha256((ROOT / 'protocol' / name).read_bytes()).hexdigest(), digest)
        old = json.loads((ROOT / 'protocol/release-audit-researcher-alpha-v1.json').read_text())
        changes = {'id', 'scope', 'workflow_sha256', 'policy_comparison_function_pins', 'limitations', 'researcher_authoring'}
        self.assertEqual({key: value for key, value in PROFILE.items() if key not in changes},
                         {key: value for key, value in old.items() if key not in changes})
        self.assertEqual(PROFILE['researcher_authoring'], plan.AUTHORING_SCOPE)
        self.assertEqual(len(PROFILE['physical_jobs']), 74)
        self.assertEqual((PROFILE['counts']['native_suites'], PROFILE['counts']['native_executables'],
                          PROFILE['counts']['native_fixtures']), (171, 174, 26))
        self.assertEqual(cli.PROFILES[plan.AUTHORING_PROFILE], 'release-audit-researcher-authoring-v1.json')
        self.assertNotIn('researcher_authoring', old)
        self.assertNotIn('examples/author_staged_research_project.py', plan.RESEARCHER_SOURCE_ROOTS)
        self.assertEqual(set(plan.AUTHORING_SOURCE_ROOTS) - set(plan.RESEARCHER_SOURCE_ROOTS),
                         {'examples/author_staged_research_project.py'})

    def test_current_workflow_and_every_source_function_have_exact_authority(self):
        self.assertEqual(PROFILE['workflow_sha256'], hashlib.sha256((SOURCE / '.github/workflows/ci.yml').read_bytes()).hexdigest())
        self.assertEqual(PROFILE['policy_comparison_function_pins'], audit.SOURCE_FUNCTION_PINS)
        self.assertEqual(len(audit.SOURCE_FUNCTION_PINS), 40)
        for location, digest in audit.SOURCE_FUNCTION_PINS.items():
            path, name = location.rsplit(':', 1); raw = (SOURCE / path).read_text()
            node = next(row for row in ast.parse(raw).body if isinstance(row, ast.FunctionDef) and row.name == name)
            self.assertEqual(hashlib.sha256(ast.get_source_segment(raw, node).encode()).hexdigest(), digest, location)
        workflow = (SOURCE / '.github/workflows/ci.yml').read_text()
        for name in ('test_policy_component_inputs', 'test_author_staged_research_project', 'test_researcher_alpha_witness'):
            self.assertIn('tests.' + name, workflow)

    def test_original_prebuilt_adapter_retains_all_current_checks(self):
        with patch.object(historical, 'SOURCE', SOURCE):
            historical.check_correspondence(Path(cli.release_audit_researcher.__file__).read_text())

    def test_closed_typed_census_rejects_old_or_broadened_source(self):
        audit.check_profile_sources()
        source = self.installed.researcher
        for module, name, value in ((self.installed, 'SCHEMA', 'biocompiler.researcher_alpha_installed_campaign.v0.1'),
                                   (source, 'OBSERVATIONS', source.OBSERVATIONS[:-1]),
                                   (source, 'INPUTS', source.INPUTS[:-1]),
                                   (source, 'PROJECT_IDS', ('staged', 'comparison')),
                                   (self.starter, 'SOURCE_FILES', self.starter.SOURCE_FILES[:-1])):
            with self.subTest(name=name), patch.object(module, name, value), self.assertRaises(AssertionError):
                audit.check_profile_sources()
        with patch.object(self.starter, 'researcher_evidence_files', return_value=audit.EVIDENCE_FILES[:-1]), self.assertRaises(AssertionError):
            audit.check_profile_sources()

    def test_typed_plan_requires_new_source_catalogs_and_exact_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            names = set(plan.AUTHORING_STARTER_SOURCE_FILES) | {'core/test/dune', 'src/sample.py', 'tools/compare.py',
                'protocol/fixture.json', '.github/workflows/ci.yml', 'pyproject.toml'}
            content = {name: b'Inert source\n' for name in names}
            content['tools/compare.py'] = b'def compare():\n    return None\n'
            for name, raw in content.items():
                path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw); path.chmod(0o644)
            profile = deepcopy(PROFILE)
            profile.update(workflow_sha256=hashlib.sha256(content['.github/workflows/ci.yml']).hexdigest(),
                dune_sha256=hashlib.sha256(content['core/test/dune']).hexdigest(), legacy_comparison_schemas={},
                policy_comparison_function_pins={'tools/compare.py:compare': hashlib.sha256(content['tools/compare.py'].rstrip()).hexdigest()})
            rows = {name: git_row(name, raw) for name, raw in content.items()}
            source_rows = [row for name, row in rows.items() if any(name == base or name.startswith(base + '/') for base in plan.AUTHORING_SOURCE_ROOTS)]
            native_plan = [{'name': 'test_' + str(i), 'environment': []} for i in range(171)]
            fixtures = {'fixture/' + str(i): 'protocol/fixture.json' for i in range(26)}
            modules = {'ci_native_bundle': SimpleNamespace(test_plan=lambda _: native_plan,
                dependency_members=lambda _: fixtures, expected_members=lambda _: [*fixtures, *('bin/' + str(i) for i in range(174))]),
                'ci_core_groups': SimpleNamespace(PLAN_SHA256=profile['direct_group_plan_sha256'], load_plan=lambda _: list(range(67))),
                'ci_validation': SimpleNamespace(REQUIRED_NEEDS=set(profile['required_needs']),
                    EXPECTED_RECEIPTS={(row['job'], row['variant']) for row in profile['ordinary_receipts']},
                    CORE_PLATFORMS={name: tuple(value) for name, value in profile['platforms'].items()})}
            options = dict(identity={'head_revision': 'a' * 40, 'revision': 'b' * 40, 'run_id': '37', 'run_attempt': '1'},
                tree='c' * 40, base='d' * 40, profile=profile, profile_sha256='e' * 64, tracked=sorted(names),
                source_rows=[], component_source_rows=source_rows,
                starter_source_rows=[rows[name] for name in plan.AUTHORING_STARTER_SOURCE_FILES])
            with patch.dict(sys.modules, modules), patch('tools.release_audit_component.audit_sources', side_effect=lambda root, audited_sources: audited_sources):
                built = plan.build_plan(root, **options)
                self.assertEqual(set(built['starter_sources']), set(plan.AUTHORING_STARTER_SOURCE_FILES))
                self.assertIn('data/researcher_alpha/expected.json', built['component_sources'])
                self.assertIn('examples/author_staged_research_project.py', built['component_sources'])
                self.assertEqual(built['researcher_authoring'], plan.AUTHORING_SCOPE)
                for key in plan.AUTHORING_SCOPE:
                    changed = deepcopy(profile); changed['researcher_authoring'][key] -= 1
                    with self.subTest(scope=key), self.assertRaisesRegex(AssertionError, 'Typed authoring scope'):
                        plan.build_plan(root, **{**options, 'profile': changed})
                omitted = [row for row in source_rows if not row.endswith('\texamples/author_staged_research_project.py')]
                with self.assertRaises(AssertionError):
                    plan.build_plan(root, **{**options, 'component_source_rows': omitted})
                for field in ('component_source_rows', 'starter_source_rows'):
                    changed = {**options, field: None}
                    with self.assertRaises(AssertionError): plan.build_plan(root, **changed)
                changed = deepcopy(profile); changed['counts']['native_suites'] = 156
                with self.assertRaises(AssertionError): plan.build_plan(root, **{**options, 'profile': changed})

    def test_installed_wrapper_keeps_original_comparison_and_checks_typed_result(self):
        result = {'staged_material': {'untouched': 'staged result'},
                  'staged_originals': {'untouched': 'staged originals'},
                  'researcher_originals': {name: 'inert pin' for name in audit.INPUTS},
                  'researcher_project': {'schema_version': audit.INSTALLED_SCHEMA,
                                         'inputs': {name: 'inert pin' for name in audit.INPUTS}}}
        with patch.object(audit, '_audit_installed_profiles', return_value=result) as delegate:
            self.assertIs(audit.audit_installed_profiles('retained', audited_sources='independent'), result)
            delegate.assert_called_once_with('retained', audited_sources='independent')
            result['researcher_project']['schema_version'] = 'biocompiler.researcher_alpha_installed_campaign.v0.1'
            with self.assertRaisesRegex(AssertionError, 'comparison scope'):
                audit.audit_installed_profiles('retained', audited_sources='independent')
        with patch.object(self.installed.researcher, 'OBSERVATIONS', audit.OBSERVATIONS[:-1]), \
             patch.object(audit, '_audit_installed_profiles') as delegate, self.assertRaises(AssertionError):
            audit.audit_installed_profiles('retained', audited_sources='independent')
        delegate.assert_not_called()

    def fixture(self):
        source = self.folder / 'source'; source.mkdir()
        catalog, contents = {}, {}
        for name in plan.AUTHORING_STARTER_SOURCE_FILES:
            raw = ('INDEPENDENT INERT SOURCE: ' + name).encode()
            path = source / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw); path.chmod(0o644)
            catalog[name] = {**pin(raw), 'git_blob': hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest(), 'mode': '100644'}
            contents[name] = raw
        slots = [self.folder / ('slot-' + str(index)) for index in range(4)]
        evidence = slots[0] / 'evidence'; (evidence / 'researcher-alpha').mkdir(parents=True)
        identity = {'revision': '1' * 40, 'head_revision': '2' * 40, 'run_id': '123', 'run_attempt': '1'}
        child = {**identity, 'schema_version': audit.INSTALLED_SCHEMA, 'status': 'pass',
                 'system': 'Linux', 'machine': 'x86_64', 'python_version': '3.11.15', 'files': {}}
        for name in audit.EVIDENCE_FILES:
            raw = ('INERT RETAINED EVIDENCE: ' + name).encode()
            (evidence / name).write_bytes(raw); child['files'][name] = pin(raw, child=True)
            contents['evidence/' + name] = raw
        raw = json.dumps(child).encode(); (evidence / 'researcher-alpha.json').write_bytes(raw)
        contents['evidence/researcher-alpha.json'] = raw
        slot_names = sorted((system, machine, minor) for system, machine in (('Linux', 'x86_64'), ('Darwin', 'arm64')) for minor in ('3.11', '3.14'))
        comparison = {**identity, 'schema_version': 'biocompiler.policy_material_prebuilt_campaign.v0.4', 'status': 'pass',
                      'slots': [{'slot': list(slot)} for slot in slot_names], 'researcher_project': {'status': 'pass',
                      'attempts': [{'slot': ['Linux', 'x86_64', '3.11'], 'run_attempt': '1', 'receipt': pin(raw, child=True)}]}}
        sdk = self.folder / 'sdk.whl'; sdk.write_bytes(b'INERT SDK')
        contents['wheels/sdk.whl'] = sdk.read_bytes()
        candidate = {'source_revision': identity['head_revision'], 'tested_revision': identity['revision'],
                     'run_id': identity['run_id'], 'sdk': pin(sdk.read_bytes()), 'platforms': {}}
        natives = {}
        for name in ('linux-x86_64', 'macos-arm64'):
            path = self.folder / (name + '.whl'); path.write_bytes(('INERT NATIVE ' + name).encode())
            natives[name] = {'native': path}; candidate['platforms'][name] = {'name': path.name, **pin(path.read_bytes())}
            contents['wheels/' + path.name] = path.read_bytes()
        output = self.folder / 'output'; output.mkdir()
        candidate_path = self.folder / 'candidate.json'; candidate_path.write_text(json.dumps(candidate))
        contents['evidence/candidate.json'] = candidate_path.read_bytes()
        (output / 'prebuilt-comparison.json').write_text(json.dumps(comparison))
        contents['evidence/prebuilt-comparison.json'] = (output / 'prebuilt-comparison.json').read_bytes()
        manifest = {'schema_version': 'biocompiler.researcher_alpha_starter.v0.2', 'status': 'installed_candidate',
                    'release_acceptance': 'pending_overall_and_actual_main_gates', 'empirical': 'unassessed',
                    'real_researcher_project': 'unqualified', 'source_revision': identity['head_revision'],
                    'tested_revision': identity['revision'], 'run_id': identity['run_id'], 'run_attempt': identity['run_attempt'],
                    'slots': [list(slot) for slot in slot_names], 'files': {name: pin(raw) for name, raw in sorted(contents.items())},
                    'entrypoint': 'docs/researcher-alpha-quickstart.md', 'review': 'docs/researcher-alpha-review.md'}
        directory = output / 'researcher-starter'; directory.mkdir()
        for name, raw in contents.items():
            path = directory / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
        (directory / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
        args = SimpleNamespace(sdk=sdk, release_candidate=candidate_path, output_dir=output, compare=slots)
        return directory, args, comparison, natives, source, catalog, manifest

    def checked(self, values):
        directory, args, comparison, natives, source, catalog, _ = values
        return audit.audit_starter(directory, args, comparison, natives, source_root=source, audited_sources=catalog)

    def test_full_handoff_preserves_all_40_receipt_relative_files(self):
        values = self.fixture(); result = self.checked(values)
        self.assertEqual(result, values[-1]); self.assertEqual(len(result['files']), 58)
        self.assertEqual(sum(name.endswith('.zip') for name in result['files']), 7)
        self.assertFalse(any(name.startswith('verified-examples/') for name in result['files']))
        self.assertEqual(result['release_acceptance'], 'pending_overall_and_actual_main_gates')

    def test_missing_tampered_redirected_diagnostic_or_mutant_fails(self):
        values = self.fixture(); directory = values[0]
        for name in ('authored-catalog-authorization.json', 'authored-completion-no-publication.json',
                     'staged-changed-candidate.zip', 'comparison-changed-fasta.zip'):
            path = directory / 'evidence/researcher-alpha' / name; raw = path.read_bytes(); path.unlink()
            with self.subTest(name=name, kind='missing'), self.assertRaisesRegex(AssertionError, 'census'): self.checked(values)
            path.write_bytes(b'changed diagnostic')
            with self.subTest(name=name, kind='changed'), self.assertRaisesRegex(AssertionError, 'copy differs'): self.checked(values)
            path.unlink(); path.symlink_to(values[1].compare[0] / 'evidence/researcher-alpha' / name)
            with self.subTest(name=name, kind='redirect'), self.assertRaisesRegex(AssertionError, 'Redirected'): self.checked(values)
            path.unlink(); path.write_bytes(raw)
        (directory / 'verified-examples').mkdir()
        with self.assertRaisesRegex(AssertionError, 'Unexpected'): self.checked(values)

    def test_child_self_rehash_cannot_replace_independent_comparison(self):
        values = self.fixture(); evidence = values[1].compare[0] / 'evidence'
        child_path = evidence / 'researcher-alpha.json'; child = json.loads(child_path.read_bytes())
        name = 'researcher-alpha/authored-catalog-authorization.json'; path = evidence / name
        path.write_bytes(b'self-rehashed diagnostic'); child['files'][name] = pin(path.read_bytes(), child=True)
        child_path.write_text(json.dumps(child))
        with self.assertRaisesRegex(ValueError, 'independent installed comparison'): self.checked(values)

    def test_rehashed_copy_manifest_cannot_change_original_evidence_or_scope(self):
        values = self.fixture(); directory = values[0]; original = values[-1]
        name = 'evidence/researcher-alpha/authored-catalog-authorization.json'
        path = directory / name; raw = path.read_bytes(); path.write_bytes(b'new diagnostic')
        manifest = deepcopy(original); manifest['files'][name] = pin(path.read_bytes())
        (directory / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
        with self.assertRaisesRegex(AssertionError, 'manifest'): self.checked(values)
        path.write_bytes(raw)
        for field, value in (('release_acceptance', 'complete'), ('empirical', 'established'), ('real_researcher_project', 'qualified')):
            changed = deepcopy(original); changed[field] = value
            (directory / 'manifest.json').write_text(json.dumps(changed, sort_keys=True, indent=2) + '\n')
            with self.subTest(field=field), self.assertRaisesRegex(AssertionError, 'manifest'): self.checked(values)


if __name__ == '__main__':
    unittest.main()
