"""Independent source catalogs and literal census controls; no Git or native run."""
from contextlib import ExitStack
from copy import deepcopy
import ast
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import sys
import inspect
from io import BytesIO
import stat
import zipfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import release_audit_plan as plan
from tools import release_audit_native as native

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = Path(os.environ.get('BIOCOMPILER_AUDIT_SOURCE_ROOT', ROOT))
IDENTITY = {'head_revision': 'a' * 40, 'revision': 'b' * 40, 'run_id': '37', 'run_attempt': '1'}
SOURCE_FILES = {
    'core/test/dune': b'(literal inert test plan)\n',
    'src/inert.py': b'VALUE = 7\n',
    'tools/comparison.py': b'def compare(value):\n    return value\n',
    'protocol/fixture.json': b'{"value":7}\n',
    '.github/workflows/ci.yml': b'name: inert test workflow\n',
    'pyproject.toml': b'[project]\nname="inert"\n',
}


def catalog_row(name, raw, mode='100644'):
    blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    return mode + ' blob ' + blob + '\t' + name


class ReleaseAuditPlanTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(sys.modules))
        self.stack.enter_context(patch.object(sys, 'path', [str(SOURCE_ROOT / 'tools'), str(SOURCE_ROOT / 'src'), str(ROOT / 'tools'), *sys.path]))
        sys.modules.pop('check_policy_development', None)
        for name in ('subprocess.Popen', 'socket.socket', 'socket.create_connection', 'ctypes.CDLL', 'os.system'):
            self.stack.enter_context(patch(name, side_effect=AssertionError('Pure plan tests forbid process/network/native loading')))
        for name, raw in SOURCE_FILES.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            path.chmod(0o755 if name == 'tools/comparison.py' else 0o644)
        self.tracked = sorted(SOURCE_FILES)
        self.rows = [catalog_row(name, SOURCE_FILES[name], '100755' if name == 'tools/comparison.py' else '100644') for name in self.tracked]
        self.original_profile = json.loads((ROOT / 'protocol/release-audit-v1.json').read_text())

    def profile(self, component=False):
        path = ROOT / ('protocol/release-audit-component-v1.json' if component else 'protocol/release-audit-v1.json')
        profile = json.loads(path.read_text())
        profile['workflow_sha256'] = hashlib.sha256(SOURCE_FILES['.github/workflows/ci.yml']).hexdigest()
        profile['dune_sha256'] = hashlib.sha256(SOURCE_FILES['core/test/dune']).hexdigest()
        # Only this literal function participates in synthetic plan pin testing.
        profile['policy_comparison_function_pins'] = {'tools/comparison.py:compare': hashlib.sha256(SOURCE_FILES['tools/comparison.py'].rstrip(b'\n')).hexdigest()}
        profile['legacy_comparison_schemas'] = {}
        return profile

    def modules(self, profile, census):
        suites, executables, fixtures = census
        native_plan = [{'name': 'literal_suite_' + str(i), 'environment': [], 'dependencies': []} for i in range(suites)]
        fixture_map = {'test/fixture-' + str(i): 'protocol/fixture.json' for i in range(fixtures)}
        native_members = [*fixture_map, *['bin/inert-' + str(i) for i in range(executables)]]
        return {
            'ci_native_bundle': SimpleNamespace(test_plan=lambda text: deepcopy(native_plan), expected_members=lambda root: list(native_members), dependency_members=lambda root: dict(fixture_map)),
            'ci_core_groups': SimpleNamespace(PLAN_SHA256=profile['direct_group_plan_sha256'], load_plan=lambda root: [{'id': str(i)} for i in range(67)]),
            'ci_validation': SimpleNamespace(REQUIRED_NEEDS=set(profile['required_needs']), EXPECTED_RECEIPTS={(r['job'], r['variant']) for r in profile['ordinary_receipts']}, CORE_PLATFORMS={name: tuple(value) for name, value in profile['platforms'].items()}),
        }

    def build(self, component=False, *, profile=None, census=None, rows=None):
        profile = self.profile(component) if profile is None else profile
        census = ((156, 158, 23) if component else (149, 151, 23)) if census is None else census
        source_rows = [row for row in self.rows if not row.split('\t')[1].startswith('.github/')]
        kwargs = {'component_source_rows': self.rows if rows is None else rows} if component else {}
        with patch.dict(sys.modules, self.modules(profile, census)):
            return plan.build_plan(self.root, identity=IDENTITY, tree='c' * 40, base='d' * 40,
                profile=profile, profile_sha256='e' * 64, tracked=self.tracked, source_rows=source_rows, **kwargs)

    def test_independent_catalog_binds_github_git_blob_and_executable_mode(self):
        actual = plan.derive_component_sources(self.root, self.rows, self.tracked)
        self.assertEqual(set(actual), set(SOURCE_FILES))
        workflow = SOURCE_FILES['.github/workflows/ci.yml']
        expected_blob = hashlib.sha1(b'blob 26\0' + workflow).hexdigest()
        self.assertEqual(len(workflow), 26)
        self.assertEqual(actual['.github/workflows/ci.yml'], {'sha256': hashlib.sha256(workflow).hexdigest(), 'size': 26, 'git_blob': expected_blob, 'mode': '100644'})
        self.assertEqual(actual['tools/comparison.py']['mode'], '100755')
        self.assertEqual(actual['tools/comparison.py']['size'], 37)

    def test_catalog_rejects_omitted_extra_duplicate_and_malformed_git_rows(self):
        original = self.rows[0]
        header, name = original.split('\t')
        mode, kind, blob = header.split()
        mutations = (
            self.rows[1:], self.rows + [original],
            [*self.rows, '100644 blob ' + 'a' * 40 + '\ttests/foreign.py'],
            [original.replace(blob, 'a' * 39), *self.rows[1:]],
            [original.replace(blob, 'A' * 40), *self.rows[1:]],
            [original.replace(' blob ', ' tree '), *self.rows[1:]],
            [original.replace('100644', '120000'), *self.rows[1:]],
            ['malformed', *self.rows[1:]],
            [header + '\t../outside', *self.rows[1:]],
            [header + '\t/absolute', *self.rows[1:]],
            [header + '\t.github//workflows/ci.yml', *self.rows[1:]],
        )
        for index, rows in enumerate(mutations):
            with self.subTest(index=index), self.assertRaises((AssertionError, ValueError)):
                plan.derive_component_sources(self.root, rows, self.tracked)

    def test_catalog_missing_tracked_or_changed_content_mode_and_extra_file_fail(self):
        with self.assertRaises((AssertionError, ValueError)):
            plan.derive_component_sources(self.root, self.rows, self.tracked[1:])
        path = self.root / '.github/workflows/ci.yml'
        path.write_bytes(b'name: altered and rehashed\n')
        with self.assertRaises((AssertionError, ValueError)):
            plan.derive_component_sources(self.root, self.rows, self.tracked)
        path.write_bytes(SOURCE_FILES['.github/workflows/ci.yml'])
        executable = self.root / 'tools/comparison.py'
        executable.chmod(0o644)
        with self.assertRaises((AssertionError, ValueError)):
            plan.derive_component_sources(self.root, self.rows, self.tracked)
        executable.chmod(0o755)
        extra = self.root / '.github/workflows/untracked.yml'
        extra.write_bytes(b'name: unknown\n')
        with self.assertRaises((AssertionError, ValueError)):
            plan.derive_component_sources(self.root, self.rows, self.tracked)

    def test_old_and_component_plans_bind_distinct_full_native_censuses(self):
        old, component = self.build(), self.build(True)
        self.assertEqual(old['profile'], 'complete-release-v1')
        self.assertEqual(component['profile'], 'complete-component-release-v1')
        self.assertEqual((len(old['native_plan']), len(old['native_members']), len(old['fixture_pins'])), (149, 174, 23))
        self.assertEqual((len(component['native_plan']), len(component['native_members']), len(component['fixture_pins'])), (156, 181, 23))
        self.assertEqual(component['counts']['native_executables'], 158)
        self.assertEqual(old['counts']['native_executables'], 151)
        self.assertEqual(component['component_sources'], plan.derive_component_sources(self.root, self.rows, self.tracked))
        self.assertNotIn('component_sources', old)
        self.assertIn('.github/workflows/ci.yml', component['component_sources'])
        self.assertNotIn('.github/workflows/ci.yml', component['source_archive_files'])
        for key in ('physical_jobs', 'ordinary_receipts', 'unit_artifacts', 'download_artifact_names', 'required_metadata_names'):
            self.assertEqual(len(old[key]), len(component[key]))

    def test_wrong_census_or_rehashed_source_cannot_downgrade_component_plan(self):
        for census in ((149, 151, 23), (155, 158, 23), (156, 157, 23), (156, 158, 22)):
            with self.subTest(census=census), self.assertRaises(AssertionError):
                self.build(True, census=census)
        profile = self.profile(True)
        profile['counts']['native_suites'] = 149
        profile['counts']['native_executables'] = 151
        with self.assertRaises(AssertionError):
            self.build(True, profile=profile, census=(149, 151, 23))
        with self.assertRaises((AssertionError, ValueError)):
            self.build(True, rows=self.rows[1:])
        source = self.root / 'tools/comparison.py'
        source.write_bytes(b'def compare(value):\n    return None\n')
        changed_rows = [catalog_row(name, (self.root / name).read_bytes(), '100755' if name == 'tools/comparison.py' else '100644') for name in self.tracked]
        with self.assertRaisesRegex(AssertionError, 'comparison body changed'):
            self.build(True, rows=changed_rows)

    def test_original_profile_bytes_and_component_scope_are_independently_fixed(self):
        original = (ROOT / 'protocol/release-audit-v1.json').read_bytes()
        self.assertEqual(hashlib.sha256(original).hexdigest(), '87aa3b5209a0f4f6e4bac675fa18593922cfeaf46e4a051cb0dfde72c935e08d')
        profile = json.loads((ROOT / 'protocol/release-audit-component-v1.json').read_text())
        self.assertEqual(profile['id'], 'complete-component-release-v1')
        self.assertEqual({name: profile['counts'][name] for name in ('physical_jobs', 'ordinary_receipts', 'native_suites', 'native_executables', 'native_fixtures')},
            {'physical_jobs': 74, 'ordinary_receipts': 59, 'native_suites': 156, 'native_executables': 158, 'native_fixtures': 23})
        self.assertEqual(profile['workflow_sha256'], hashlib.sha256((SOURCE_ROOT / '.github/workflows/ci.yml').read_bytes()).hexdigest())
        self.assertEqual(profile['dune_sha256'], hashlib.sha256((SOURCE_ROOT / 'core/test/dune').read_bytes()).hexdigest())

    def test_native_default_and_component_bundle_censuses_are_closed(self):
        self.assertEqual(inspect.signature(native.audit_bundle).parameters['expected_executables'].default, 151)
        self.assertEqual(inspect.signature(native.audit_bundle).parameters['expected_fixtures'].default, 23)
        identity = {'revision': 'b' * 40, 'run_id': '37', 'run_attempt': '1'}
        def bundle(executables):
            values = {**{'test/fixture-' + str(i): b'literal data' for i in range(23)},
                      **{'bin/program-' + str(i): b'inert executable bytes' for i in range(executables)}}
            pins = {name: {'size': len(value), 'sha256': hashlib.sha256(value).hexdigest()} for name, value in values.items()}
            document = {'schema': 'biocompiler.ci_native_bundle.v1', **identity, 'system': 'Linux', 'machine': 'x86_64', 'dune_sha256': 'e' * 64, 'files': pins}
            data = BytesIO()
            with zipfile.ZipFile(data, 'w') as archive:
                for name, value in {**values, 'manifest.json': json.dumps(document).encode()}.items():
                    member = zipfile.ZipInfo(name)
                    member.external_attr = (stat.S_IFREG | 0o644) << 16
                    archive.writestr(member, value)
            return zipfile.ZipFile(BytesIO(data.getvalue())), document, {name: pin for name, pin in pins.items() if name.startswith('test/')}
        for executables in (151, 158):
            archive, document, fixtures = bundle(executables)
            with archive:
                kwargs = {'identity': identity, 'runtime': ('Linux', 'x86_64'), 'expected_members': list(document['files']), 'fixture_pins': fixtures, 'dune_sha256': 'e' * 64}
                self.assertEqual(native.audit_bundle(archive, **kwargs, **({'expected_executables': 158} if executables == 158 else {})), document)
                if executables == 158:
                    with self.assertRaises(AssertionError):
                        native.audit_bundle(archive, **kwargs)
                for wrong in (150, 157, 159, True, 158.0):
                    with self.subTest(executables=executables, wrong=wrong), self.assertRaises(AssertionError):
                        native.audit_bundle(archive, **kwargs, expected_executables=wrong)

    def test_native_suite_default_and_component_argument_and_log_censuses(self):
        self.assertEqual(inspect.signature(native.audit_suites).parameters['expected_count'].default, 149)
        identity = {'revision': 'b' * 40, 'run_id': '37', 'run_attempt': '1'}
        for count in (149, 156):
            rows = [{'name': 'literal_' + str(i), 'environment': []} for i in range(count)]
            values = {'native-suites/' + row['name'] + '.log': b'literal hosted output' for row in rows}
            tests = [{'name': row['name'], 'argv': ['/hosted/source/core/_build/default/test/' + row['name'] + '.exe'], 'returncode': 0, 'duration_seconds': 0,
                      'log': {'sha256': hashlib.sha256(b'literal hosted output').hexdigest(), 'size': 21}} for row in rows]
            receipt = {'revision': 'b' * 40, 'run_id': '37', 'run_attempt': '1', 'expected': [row['name'] for row in rows], 'tests': tests}
            values['native-suites/receipt.json'] = json.dumps(receipt).encode()
            kwargs = {'identity': identity, 'plan': rows, 'environment_paths': {}}
            result = native.audit_suites(values.__getitem__, set(values), **kwargs, **({'expected_count': 156} if count == 156 else {}))
            self.assertEqual(result['tests'], count)
            if count == 156:
                with self.assertRaises(AssertionError):
                    native.audit_suites(values.__getitem__, set(values), **kwargs)
            for wrong in (148, 155, 157, True, 156.0):
                with self.subTest(count=count, wrong=wrong), self.assertRaises(AssertionError):
                    native.audit_suites(values.__getitem__, set(values), **kwargs, expected_count=wrong)
            with self.assertRaises(AssertionError):
                native.audit_suites(values.__getitem__, set(values) - {'native-suites/literal_0.log'}, **kwargs, expected_count=count)

    def test_component_profile_pins_all_thirteen_original_functions_and_actual_dune_census(self):
        profile = json.loads((ROOT / 'protocol/release-audit-component-v1.json').read_text())
        expected = {
            'tools/check_policy_core.py:compare_receipts', 'tools/check_policy_operational.py:compare',
            'tools/check_policy_implementation.py:compare', 'tools/check_policy_material.py:compare',
            'tools/check_policy_material_consumer.py:compare', 'tools/check_policy_development.py:source_snapshot',
            'tools/check_policy_component_fixture.py:validate', 'tools/check_policy_component_material.py:validate_installed',
            'tools/check_policy_component_material.py:compare_installed', 'tools/check_policy_material_consumer.py:validate_component_producer',
            'tools/check_policy_material_prebuilt.py:component_authorities', 'tools/check_policy_material_prebuilt.py:component_inputs',
            'tools/check_policy_material_prebuilt.py:verify_slot',
        }
        self.assertEqual(set(profile['policy_comparison_function_pins']), expected)
        for location in sorted(expected):
            path, name = location.split(':')
            source = (SOURCE_ROOT / path).read_text()
            selected = [node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == name]
            self.assertEqual(len(selected), 1)
            self.assertEqual(hashlib.sha256(ast.get_source_segment(source, selected[0]).encode()).hexdigest(),
                             profile['policy_comparison_function_pins'][location])
        spec = importlib.util.spec_from_file_location('literal_current_native_plan', SOURCE_ROOT / 'tools/ci_native_bundle.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        suites = module.test_plan((SOURCE_ROOT / 'core/test/dune').read_text())
        fixtures = module.dependency_members(SOURCE_ROOT)
        members = module.expected_members(SOURCE_ROOT)
        self.assertEqual((len(suites), len(members), len(fixtures)), (156, 181, 23))
        self.assertEqual(len(members - set(fixtures)), 158)
