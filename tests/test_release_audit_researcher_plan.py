"""Additive exact researcher release scope; inert source and retained-data tests."""
from contextlib import ExitStack
from copy import deepcopy
import ast
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from tools import release_audit_plan as plan
from tools import release_audit_native as native
from tools import release_audit as audit

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('BIOCOMPILER_RESEARCHER_SOURCE_ROOT', ROOT.parent / 'researcher-alpha')).resolve()
PROFILE = json.loads((ROOT / 'protocol/release-audit-researcher-alpha-v1.json').read_text())


def git_row(name, raw):
    return '100644 blob ' + hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() + '\t' + name


class ResearcherAuditPlanTests(unittest.TestCase):
    def setUp(self):
        stack = ExitStack(); self.addCleanup(stack.close)
        for name in ('subprocess.Popen', 'socket.socket', 'socket.create_connection', 'ctypes.CDLL', 'os.system'):
            stack.enter_context(patch(name, side_effect=AssertionError('Inert audit tests forbid native/process/network')))

    def test_historical_profiles_and_current_artifact_classifications_are_unchanged(self):
        self.assertEqual(hashlib.sha256((ROOT / 'protocol/release-audit-v1.json').read_bytes()).hexdigest(),
                         '87aa3b5209a0f4f6e4bac675fa18593922cfeaf46e4a051cb0dfde72c935e08d')
        component = json.loads((ROOT / 'protocol/release-audit-component-v1.json').read_text())
        from release_audit_researcher import SOURCE_FUNCTION_PINS
        self.assertEqual(set(PROFILE['policy_comparison_function_pins']),
                         set(component['policy_comparison_function_pins']) | set(SOURCE_FUNCTION_PINS))
        self.assertEqual(len(PROFILE['policy_comparison_function_pins']), 30)
        self.assertEqual(component['counts']['native_suites'], 156)
        self.assertEqual(PROFILE['counts'], {**plan.BASE_COUNTS, 'native_suites': 171,
            'native_executables': 174, 'native_fixtures': 26})
        for field in ('required_needs', 'ordinary_receipts', 'unit_artifacts', 'permitted_artifact_names',
                      'required_metadata_names', 'download_artifact_names', 'legacy_comparison_schemas',
                      'native_environment_paths', 'platforms'):
            self.assertEqual(PROFILE[field], component[field], field)
        self.assertEqual([row['name'] for row in PROFILE['physical_jobs']],
                         [row['name'] for row in component['physical_jobs']])
        self.assertEqual(len(PROFILE['physical_jobs']), 74)
        self.assertEqual(len(PROFILE['permitted_artifact_names']), 173)
        self.assertFalse(any('${{' in step['name'] for job in PROFILE['physical_jobs']
                             for step in job['steps'] if step['name']))

    def test_current_source_workflow_native_and_function_authority(self):
        self.assertEqual(PROFILE['workflow_sha256'], hashlib.sha256((SOURCE / '.github/workflows/ci.yml').read_bytes()).hexdigest())
        self.assertEqual(PROFILE['dune_sha256'], hashlib.sha256((SOURCE / 'core/test/dune').read_bytes()).hexdigest())
        for location, expected in PROFILE['policy_comparison_function_pins'].items():
            path, name = location.rsplit(':', 1); raw = (SOURCE / path).read_text()
            function = next(row for row in ast.parse(raw).body if isinstance(row, ast.FunctionDef) and row.name == name)
            self.assertEqual(hashlib.sha256(ast.get_source_segment(raw, function).encode()).hexdigest(), expected, location)
        with patch.object(sys, 'path', [str(SOURCE / 'tools'), str(SOURCE / 'src'), *sys.path]), patch.dict(sys.modules):
            for name in ('ci_native_bundle', 'ci_validation', 'ci_core_groups'): sys.modules.pop(name, None)
            import ci_native_bundle, ci_core_groups, ci_validation
            suites = ci_native_bundle.test_plan((SOURCE / 'core/test/dune').read_text())
            fixtures = ci_native_bundle.dependency_members(SOURCE)
            self.assertEqual((len(suites), len(ci_native_bundle.expected_members(SOURCE)) - len(fixtures), len(fixtures)), (171, 174, 26))
            self.assertIn('core/_build/default/test/component_fixture_export/main.exe', ci_native_bundle.expected_members(SOURCE))
            self.assertEqual(len(ci_core_groups.load_plan(SOURCE)), 67)
            self.assertEqual(ci_core_groups.PLAN_SHA256, PROFILE['direct_group_plan_sha256'])
            self.assertEqual(len(ci_validation.EXPECTED_RECEIPTS), 59)
            self.assertEqual(set(ci_validation.REQUIRED_NEEDS), set(PROFILE['required_needs']))

    def test_exact_current_steps_and_skip_allowances(self):
        jobs = []
        for index, spec in enumerate(PROFILE['physical_jobs']):
            applies = spec['matrix'].get('platform') == 'macos-arm64' and spec['matrix'].get('python-version', '3.11') == '3.11'
            steps = [{'name': 'Set up job', 'number': 1, 'status': 'completed', 'conclusion': 'success'}]
            for step in spec['steps']:
                skip = step['if'] == 'failure()' or step['name'] == audit.BOOTSTRAP_STEP_NAME and not applies
                steps.append({'name': step['name'] or 'Run ' + str(step['uses']), 'number': step['yaml_ordinal'] + 1,
                              'status': 'completed', 'conclusion': 'skipped' if skip else 'success'})
            jobs.append({'id': index + 1, 'name': spec['name'], 'run_id': 37, 'run_attempt': 1, 'head_sha': 'a' * 40,
                         'status': 'completed', 'conclusion': 'success', 'labels': [spec['runner']], 'steps': steps})
        document = {'total_count': len(jobs), 'jobs': jobs}
        run = {'id': 37, 'head_sha': 'a' * 40}
        self.assertEqual(len(audit.validate_jobs(document, run, PROFILE)), 29)
        for mutation in ('omit', 'skip-new-comparison', 'wrong-attempt'):
            changed = deepcopy(document)
            if mutation == 'omit': changed['jobs'].pop()
            elif mutation == 'wrong-attempt': changed['jobs'][0]['run_attempt'] = 2
            else:
                row = next(row for row in changed['jobs'] if row['name'] == 'policy-prebuilt-reproducibility')
                row['steps'][-1]['conclusion'] = 'skipped'
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                audit.validate_jobs(changed, run, PROFILE)

    def test_starter_catalog_requires_exact_current_git_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve(); rows = []
            for name in plan.STARTER_SOURCE_FILES:
                path = root / name; path.parent.mkdir(parents=True, exist_ok=True)
                raw = ('independent ' + name).encode(); path.write_bytes(raw); path.chmod(0o644)
                rows.append(git_row(name, raw))
            def checked(supplied):
                return plan.derive_component_sources(root, supplied, list(plan.STARTER_SOURCE_FILES),
                    source_roots=plan.STARTER_SOURCE_FILES, check_census=False)
            self.assertEqual(set(checked(rows)), set(plan.STARTER_SOURCE_FILES))
            for supplied in (rows[:-1], rows + rows[:1], [rows[0].replace('blob ', 'tree '), *rows[1:]]):
                with self.assertRaises(AssertionError): checked(supplied)
            (root / plan.STARTER_SOURCE_FILES[0]).write_text('changed without Git authority')
            with self.assertRaises(AssertionError): checked(rows)

    def test_researcher_build_plan_requires_both_new_catalogs_and_exact_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            names = set(plan.STARTER_SOURCE_FILES) | {'core/test/dune', 'src/sample.py', 'tools/compare.py',
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
            source_rows = [row for name, row in rows.items() if any(name == base or name.startswith(base + '/') for base in plan.RESEARCHER_SOURCE_ROOTS)]
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
                starter_source_rows=[rows[name] for name in plan.STARTER_SOURCE_FILES])
            with patch.dict(sys.modules, modules), patch('tools.release_audit_component.audit_sources', side_effect=lambda root, audited_sources: audited_sources):
                built = plan.build_plan(root, **options)
                self.assertEqual(set(built['starter_sources']), set(plan.STARTER_SOURCE_FILES))
                self.assertIn('data/researcher_alpha/expected.json', built['component_sources'])
                for field in ('component_source_rows', 'starter_source_rows'):
                    changed = {**options, field: None}
                    with self.assertRaises(AssertionError): plan.build_plan(root, **changed)
                changed = deepcopy(profile); changed['counts']['native_suites'] = 156
                with self.assertRaises(AssertionError): plan.build_plan(root, **{**options, 'profile': changed})

    def test_new_native_bundle_scope_does_not_become_historical_default(self):
        values = {**{'fixture/' + str(i): b'original' for i in range(26)},
                  **{'bin/' + str(i): b'inert executable bytes' for i in range(174)}}
        pins = {name: native.digest(raw) for name, raw in values.items()}
        identity = {'revision': 'b' * 40, 'run_id': '37', 'run_attempt': '1'}
        document = {'schema': 'biocompiler.ci_native_bundle.v1', **identity, 'system': 'Linux', 'machine': 'x86_64',
                    'dune_sha256': 'e' * 64, 'files': pins}
        stream = BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            for name, raw in {**values, 'manifest.json': json.dumps(document).encode()}.items():
                member = zipfile.ZipInfo(name); member.external_attr = (stat.S_IFREG | 0o644) << 16; archive.writestr(member, raw)
        with zipfile.ZipFile(BytesIO(stream.getvalue())) as archive:
            options = dict(identity=identity, runtime=('Linux', 'x86_64'), expected_members=list(values),
                fixture_pins={name: value for name, value in pins.items() if name.startswith('fixture/')}, dune_sha256='e' * 64)
            self.assertEqual(native.audit_bundle(archive, **options, expected_executables=174, expected_fixtures=26), document)
            with self.assertRaises(AssertionError): native.audit_bundle(archive, **options)
            with self.assertRaises(AssertionError): native.audit_bundle(archive, **options, expected_executables=174, expected_fixtures=23)


if __name__ == '__main__':
    unittest.main()
