"""Complete fixed workflow gates, pinned inputs and original-body promotion."""
from copy import deepcopy
from contextlib import redirect_stderr
from io import StringIO
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import release_audit as audit

ROOT = Path(__file__).resolve().parents[1]
PROFILE = json.loads((ROOT / 'protocol/release-audit-v1.json').read_text())
BOOTSTRAP_NAME = 'Seed the exact hosted macOS ARM64 Python runtime'
BOOTSTRAP_FIXED = "${{ runner.environment == 'github-hosted' && runner.os == 'macOS' && runner.arch == 'ARM64' && fromJSON(env.BIOCOMPILER_SUPPORTED_PYTHON)['3.11'] == '3.11.15' }}"
BOOTSTRAP_MATRIX = "${{ runner.environment == 'github-hosted' && runner.os == 'macOS' && runner.arch == 'ARM64' && fromJSON(env.BIOCOMPILER_SUPPORTED_PYTHON)[matrix.python-version] == '3.11.15' }}"
BOOTSTRAP_JOBS = {'ocaml-build': 2, 'ocaml-native-tests': 2, 'ocaml-core': 2,
                  'architecture-sdk': 4, 'installed-campaigns': 20,
                  'realization-conformance': 4, 'policy-prebuilt-installed': 4}


def required_bootstrap(spec):
    # Independent expected policy over the literal reviewed platform/minor labels.
    return spec['matrix'].get('platform') == 'macos-arm64' and spec['matrix'].get('python-version', '3.11') == '3.11'


class ReleaseAuditOrchestrationTests(unittest.TestCase):
    def setUp(self):
        for target in ('subprocess.Popen', 'socket.socket', 'socket.create_connection', 'ctypes.CDLL', 'os.system'):
            guard = patch(target, side_effect=AssertionError('Inert release audit tests forbid process/network/native loading'))
            guard.start()
            self.addCleanup(guard.stop)

    def jobs(self, profile=None):
        rows = []
        profile = PROFILE if profile is None else profile
        for index, spec in enumerate(profile['physical_jobs']):
            steps = [{'name': 'Set up job', 'number': 1, 'status': 'completed', 'conclusion': 'success'}]
            for declared in spec['steps']:
                steps.append({'name': declared['name'] or 'Run ' + str(declared['uses']),
                              'number': declared['yaml_ordinal'] + 1, 'status': 'completed',
                              'conclusion': 'skipped' if declared['if'] == 'failure()' or (declared['name'] == BOOTSTRAP_NAME and not required_bootstrap(spec)) else 'success'})
            rows.append({'id': index + 1000, 'name': spec['name'], 'run_id': 37, 'run_attempt': 1,
                         'head_sha': 'a' * 40, 'status': 'completed', 'conclusion': 'success',
                         'labels': [spec['runner']], 'steps': steps})
        return {'total_count': 74, 'jobs': rows}

    def check_jobs(self, jobs, profile=None):
        return audit.validate_jobs(jobs, {'id': 37, 'head_sha': 'a' * 40}, PROFILE if profile is None else profile)

    def test_complete_job_gate_and_only_two_failure_upload_skips(self):
        jobs = self.jobs()
        skips = self.check_jobs(jobs)
        self.assertEqual([row for row in skips if row['condition'] == 'failure()'], [
            {'job': 'integration-examples (3.11)', 'step': 'Retain reference build failure evidence',
             'number': 33, 'condition': 'failure()', 'value': False},
            {'job': 'integration-examples (3.14)', 'step': 'Retain reference build failure evidence',
             'number': 33, 'condition': 'failure()', 'value': False}])
        self.assertEqual(len(skips), 29)
        for field, value in [('run_id', 38), ('run_attempt', 2), ('head_sha', 'b' * 40),
                             ('status', 'in_progress'), ('conclusion', 'failure'),
                             ('labels', ['self-hosted']), ('name', 'unreviewed')]:
            changed = deepcopy(jobs); changed['jobs'][0][field] = value
            with self.subTest(field=field), self.assertRaises(AssertionError):
                self.check_jobs(changed)
        for change in ('omit-job', 'duplicate-id', 'omit-step', 'repeat-step', 'rename-step',
                       'skip-check', 'incomplete-step', 'run-failure-upload', 'add-skipped-post'):
            changed = deepcopy(jobs); job = changed['jobs'][0]
            if change == 'omit-job': changed['jobs'].pop()
            elif change == 'duplicate-id': job['id'] = changed['jobs'][1]['id']
            elif change == 'omit-step': job['steps'].pop()
            elif change == 'repeat-step': job['steps'].append(deepcopy(job['steps'][0]))
            elif change == 'rename-step':
                step = next(i for i, spec in enumerate(PROFILE['physical_jobs'][0]['steps'], 1) if spec['name'])
                job['steps'][step]['name'] = 'other check'
            elif change == 'skip-check': job['steps'][1]['conclusion'] = 'skipped'
            elif change == 'incomplete-step': job['steps'][1]['status'] = 'in_progress'
            elif change == 'add-skipped-post': job['steps'].append({'name': 'Post unknown cache', 'number': 100,
                'status': 'completed', 'conclusion': 'skipped'})
            else:
                target = next(r for r in changed['jobs'] if r['name'] == 'integration-examples (3.11)')
                next(s for s in target['steps'] if s['number'] == 33)['conclusion'] = 'success'
            with self.subTest(change=change), self.assertRaises(AssertionError):
                self.check_jobs(changed)

    def test_all_sixteen_legacy_schemas_and_identity_fields_are_bound(self):
        self.assertEqual(len(PROFILE['legacy_comparison_schemas']), 16)
        identity = {'revision': 'c' * 40, 'head_revision': 'a' * 40, 'run_id': '37'}
        for name, schema in PROFILE['legacy_comparison_schemas'].items():
            original = {'schema_version': schema['schema_version'], 'status': 'success',
                        'revision': 'c' * 40, 'source_revision': 'a' * 40, 'run_id': '37'}
            audit.validate_legacy_comparison(original, name=name, plan=PROFILE, identity=identity)
            for field in original:
                changed = dict(original); changed[field] = 'unreviewed'
                with self.subTest(name=name, field=field), self.assertRaises(AssertionError):
                    audit.validate_legacy_comparison(changed, name=name, plan=PROFILE, identity=identity)

    def test_pinned_runtime_comparator_steps_remain_required_before_comparison(self):
        self.assertEqual(PROFILE['workflow_sha256'],
                         'f3cae89b566811835c2273988150a6f4ab8bf088399c9cba66c2bb57485a314c')
        comparisons = {
            'executable-rna-reproducibility':
                'Compare exact RNA and contract artifacts across Python versions',
            'payload-architecture-reproducibility':
                'Compare complete source, model, RNA, matching, control and manifest artifacts across Python versions',
            'circuit-reproducibility':
                'Compare complete deterministic infrastructure artifacts across Python versions',
        }
        for name, comparison in comparisons.items():
            spec = next(row for row in PROFILE['physical_jobs'] if row['name'] == name)
            self.assertEqual((spec['job'], spec['matrix'], spec['runner']),
                             (name, {}, 'ubuntu-latest'))
            self.assertEqual([(step['yaml_ordinal'], step['name'], step['uses'], step['if'])
                              for step in spec['steps']], [
                (1, None, 'actions/checkout@v4', None),
                (2, None, 'actions/setup-python@v5', None),
                (3, 'Record job authority and start time', None, None),
                (4, None, 'actions/download-artifact@v4', None),
                (5, None, 'actions/download-artifact@v4', None),
                (6, comparison, None, None),
                (7, 'Record successful validation and runtime', None, None),
                (8, 'Retain required job receipt', 'actions/upload-artifact@v4', 'always()'),
            ])
            for mutation in ('omit-setup', 'skip-setup', 'incomplete-setup',
                             'old-seven-steps', 'setup-after-authority'):
                jobs = self.jobs()
                target = next(row for row in jobs['jobs'] if row['name'] == name)
                setup = next(step for step in target['steps'] if step['number'] == 3)
                if mutation in {'omit-setup', 'old-seven-steps'}:
                    target['steps'].remove(setup)
                    if mutation == 'old-seven-steps':
                        for step in target['steps']:
                            if step['number'] > 3:
                                step['number'] -= 1
                elif mutation == 'skip-setup':
                    setup['conclusion'] = 'skipped'
                elif mutation == 'incomplete-setup':
                    setup['status'] = 'in_progress'; setup['conclusion'] = None
                else:
                    authority = next(step for step in target['steps'] if step['number'] == 4)
                    setup['number'], authority['number'] = 4, 3
                with self.subTest(job=name, mutation=mutation), self.assertRaises(AssertionError):
                    self.check_jobs(jobs)

    def test_independent_input_digest_and_closed_packet_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); raw = root / 'run.json'; raw.write_text('{"id":37}')
            packet = root / 'packet.json'
            original = {'schema': 'biocompiler.release_api_packet.v1',
                        'files': {'run': {'path': 'run.json', 'sha256': audit.sha(raw)}}}
            packet.write_text(json.dumps(original)); seal = audit.sha(packet)
            data, pins = audit.read_packet(packet, seal)
            self.assertEqual(data, {'run': {'id': 37}})
            self.assertEqual(pins['run']['sha256'], hashlib.sha256(b'{"id":37}').hexdigest())
            raw.write_text('{"id":38}')
            with self.assertRaises(AssertionError): audit.read_packet(packet, seal)
            changed = deepcopy(original); changed['files']['run']['sha256'] = audit.sha(raw)
            packet.write_text(json.dumps(changed))
            with self.assertRaises(AssertionError): audit.read_packet(packet, seal)
            for path in ('../run.json', '/absolute.json', None):
                changed = deepcopy(original); changed['files']['run']['path'] = path
                packet.write_text(json.dumps(changed))
                with self.subTest(path=path), self.assertRaises(AssertionError):
                    audit.read_packet(packet, audit.sha(packet))
            raw.write_text('{"id":37,"id":38}')
            with self.assertRaises(AssertionError): audit.read_pinned(raw, audit.sha(raw))
            raw.write_text('{"id":NaN}')
            with self.assertRaises(AssertionError): audit.read_pinned(raw, audit.sha(raw))

    def test_complete_fixed_scope_and_tool_dependencies_are_loaded_before_source(self):
        self.assertEqual(PROFILE['counts'], {
            'architecture_policy_comparisons': 6, 'direct_core_groups': 67, 'download_artifacts': 102,
            'installed_campaigns': 17, 'installed_group_receipts': 20, 'installed_runtime_slots': 4,
            'native_executables': 151, 'native_fixtures': 23, 'native_suites': 149,
            'ordinary_receipts': 59, 'physical_jobs': 74, 'required_metadata': 128, 'unit_artifacts': 14})
        self.assertEqual(len(PROFILE['physical_jobs']), 74)
        self.assertEqual(len(PROFILE['ordinary_receipts']), 59)
        self.assertEqual(len(PROFILE['unit_artifacts']), 14)
        self.assertEqual(len(PROFILE['download_artifact_names']), 102)
        self.assertEqual(len(set(PROFILE['required_metadata_names'])), 128)
        for name in ('identity', 'native', 'plan', 'policy', 'units'):
            module = getattr(audit, 'release_audit_' + name)
            self.assertEqual(Path(module.__file__).resolve(), ROOT / ('tools/release_audit_' + name + '.py'))

    def test_exact_bootstrap_profile_has_eleven_required_runs_and_twenty_seven_skips(self):
        affected = [row for row in PROFILE['physical_jobs'] if row['job'] in BOOTSTRAP_JOBS]
        self.assertEqual(len(affected), 38)
        self.assertEqual({name: sum(row['job'] == name for row in affected) for name in BOOTSTRAP_JOBS}, BOOTSTRAP_JOBS)
        self.assertEqual(sum(required_bootstrap(row) for row in affected), 11)
        observed = []
        for row in PROFILE['physical_jobs']:
            declared = [step for step in row['steps'] if step['name'] == BOOTSTRAP_NAME]
            if row['job'] not in BOOTSTRAP_JOBS:
                self.assertEqual(declared, [])
                continue
            condition = BOOTSTRAP_FIXED if row['job'] in {'ocaml-build', 'ocaml-native-tests', 'ocaml-core'} else BOOTSTRAP_MATRIX
            self.assertEqual(declared, [{'yaml_ordinal': 2, 'name': BOOTSTRAP_NAME, 'uses': None, 'if': condition}])
            self.assertEqual(row['steps'][0], {'yaml_ordinal': 1, 'name': None, 'uses': 'actions/checkout@v4', 'if': None})
            self.assertEqual(row['steps'][2], {'yaml_ordinal': 3, 'name': None, 'uses': 'actions/setup-python@v5', 'if': None})
            if not required_bootstrap(row):
                observed.append({'job': row['name'], 'step': BOOTSTRAP_NAME, 'number': 3, 'condition': condition, 'value': False})
        self.assertEqual(len(observed), 27)
        self.assertEqual([row for row in self.check_jobs(self.jobs()) if row['step'] == BOOTSTRAP_NAME], observed)

    def test_bootstrap_execution_condition_cannot_be_skipped_or_run_in_another_slot(self):
        for spec in PROFILE['physical_jobs']:
            if spec['job'] not in BOOTSTRAP_JOBS:
                continue
            jobs = self.jobs()
            job = next(row for row in jobs['jobs'] if row['name'] == spec['name'])
            seed = next(step for step in job['steps'] if step['name'] == BOOTSTRAP_NAME)
            seed['conclusion'] = 'skipped' if required_bootstrap(spec) else 'success'
            with self.subTest(slot=spec['name']), self.assertRaises(AssertionError):
                self.check_jobs(jobs)
        for conclusion, status in (('failure', 'completed'), ('cancelled', 'completed'), (None, 'in_progress')):
            jobs = self.jobs()
            job = next(row for row in jobs['jobs'] if row['name'] == 'ocaml-build (macos-14, macos-arm64)')
            seed = next(step for step in job['steps'] if step['name'] == BOOTSTRAP_NAME)
            seed.update(conclusion=conclusion, status=status)
            with self.subTest(conclusion=conclusion, status=status), self.assertRaises(AssertionError):
                self.check_jobs(jobs)

    def test_bootstrap_missing_extra_renamed_or_reordered_observed_step_is_rejected(self):
        for mutation in ('missing', 'extra', 'renamed', 'reordered'):
            jobs = self.jobs()
            job = next(row for row in jobs['jobs'] if row['name'] == 'ocaml-build (macos-14, macos-arm64)')
            seed = next(step for step in job['steps'] if step['name'] == BOOTSTRAP_NAME)
            if mutation == 'missing':
                job['steps'].remove(seed)
            elif mutation == 'extra':
                job['steps'].append(dict(seed, number=900))
            elif mutation == 'renamed':
                seed['name'] = 'Unreviewed runtime acquisition'
            else:
                setup = next(step for step in job['steps'] if step['number'] == 4)
                seed['number'], setup['number'] = setup['number'], seed['number']
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                self.check_jobs(jobs)

    def test_bootstrap_profile_missing_extra_position_or_condition_cannot_expand_skip_allowance(self):
        for mutation in ('missing', 'extra', 'position', 'condition', 'unconditional', 'uses', 'foreign-job'):
            profile = deepcopy(PROFILE)
            spec = next(row for row in profile['physical_jobs'] if row['name'] == 'ocaml-build (macos-14, macos-arm64)')
            seed = next(step for step in spec['steps'] if step['name'] == BOOTSTRAP_NAME)
            if mutation == 'missing':
                spec['steps'].remove(seed)
            elif mutation == 'extra':
                spec['steps'].append(dict(seed, yaml_ordinal=900))
            elif mutation == 'position':
                seed['yaml_ordinal'] = 1
            elif mutation == 'condition':
                seed['if'] = "${{ runner.os == 'macOS' }}"
            elif mutation == 'unconditional':
                seed['if'] = None
            elif mutation == 'uses':
                seed['uses'] = 'unreviewed/provider@v1'
            else:
                target = next(row for row in profile['physical_jobs'] if row['job'] == 'ci-preflight')
                target['steps'].append(dict(seed, yaml_ordinal=900))
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                self.check_jobs(self.jobs(), profile)

    def test_profile_slot_mutations_cannot_turn_required_bootstrap_into_permitted_skip(self):
        for mutation in ('python-minor', 'platform', 'runner', 'physical-name', 'installed-group'):
            profile = deepcopy(PROFILE)
            spec = next(row for row in profile['physical_jobs'] if row['name'] == 'installed-campaigns (macos-14, macos-arm64, 3.11, fixed)')
            if mutation == 'python-minor':
                spec['matrix']['python-version'] = '3.14'
            elif mutation == 'platform':
                spec['matrix']['platform'] = 'linux-x86_64'
            elif mutation == 'runner':
                spec['runner'] = 'ubuntu-24.04'
            elif mutation == 'physical-name':
                spec['name'] = 'unreviewed physical slot'
            else:
                spec['matrix']['group'] = 'unreviewed'
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                self.check_jobs(self.jobs(), profile)

    def test_profile_cli_defaults_to_original_and_requires_closed_explicit_component_choice(self):
        arguments = ['prepare', '--source-root', '/literal/source', '--authority', '/literal/authority.json',
                     '--packet', '/literal/packet.json', '--output', '/literal/plan.json',
                     '--authority-sha256', 'a' * 64, '--packet-sha256', 'b' * 64, '--tool-revision', 'c' * 40]
        self.assertEqual(audit.parse_args(arguments).profile, 'complete-release-v1')
        self.assertEqual(audit.parse_args(arguments + ['--profile', 'complete-component-release-v1']).profile,
                         'complete-component-release-v1')
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            audit.parse_args(arguments + ['--profile', 'automatic-or-partial'])
        self.assertEqual(Path(audit.release_audit_component.__file__).resolve(), ROOT / 'tools/release_audit_component.py')

    def test_component_profile_requires_full_existing_jobs_and_hosted_original_emission(self):
        profile = json.loads((ROOT / 'protocol/release-audit-component-v1.json').read_text())
        self.assertEqual(profile['id'], 'complete-component-release-v1')
        self.assertEqual(profile['counts'], {**PROFILE['counts'], 'native_suites': 156, 'native_executables': 158})
        jobs = self.jobs(profile)
        self.assertEqual(len(jobs['jobs']), 74)
        skips = self.check_jobs(jobs, profile)
        self.assertEqual(len(skips), 29)
        emitter = 'Emit independent component originals from the current domain-only build'
        builds = [row for row in profile['physical_jobs'] if row['job'] == 'ocaml-build']
        self.assertEqual(len(builds), 2)
        for spec in builds:
            steps = [step for step in spec['steps'] if step['name'] == emitter]
            self.assertEqual(len(steps), 1)
            self.assertIsNone(steps[0]['if'])
            actual = next(row for row in jobs['jobs'] if row['name'] == spec['name'])
            number = steps[0]['yaml_ordinal'] + 1
            for mutation in ('missing', 'skipped', 'failure', 'wrong-name'):
                changed = deepcopy(jobs)
                target = next(row for row in changed['jobs'] if row['name'] == actual['name'])
                step = next(row for row in target['steps'] if row['number'] == number)
                if mutation == 'missing':
                    target['steps'].remove(step)
                elif mutation == 'wrong-name':
                    step['name'] = 'Different fixture producer'
                else:
                    step['conclusion'] = mutation
                with self.subTest(slot=spec['name'], mutation=mutation), self.assertRaises(AssertionError):
                    self.check_jobs(changed, profile)
        for field in ('ordinary_receipts', 'unit_artifacts', 'required_needs', 'download_artifact_names', 'required_metadata_names'):
            self.assertEqual(profile[field], PROFILE[field])
