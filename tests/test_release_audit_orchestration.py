"""Complete fixed workflow gates, pinned inputs and original-body promotion."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools import release_audit as audit

ROOT = Path(__file__).resolve().parents[1]
PROFILE = json.loads((ROOT / 'protocol/release-audit-v1.json').read_text())


class ReleaseAuditOrchestrationTests(unittest.TestCase):
    def jobs(self):
        rows = []
        for index, spec in enumerate(PROFILE['physical_jobs']):
            steps = [{'name': 'Set up job', 'number': 1, 'status': 'completed', 'conclusion': 'success'}]
            for declared in spec['steps']:
                steps.append({'name': declared['name'] or 'Run ' + str(declared['uses']),
                              'number': declared['yaml_ordinal'] + 1, 'status': 'completed',
                              'conclusion': 'skipped' if declared['if'] == 'failure()' else 'success'})
            rows.append({'id': index + 1000, 'name': spec['name'], 'run_id': 37, 'run_attempt': 1,
                         'head_sha': 'a' * 40, 'status': 'completed', 'conclusion': 'success',
                         'labels': [spec['runner']], 'steps': steps})
        return {'total_count': 74, 'jobs': rows}

    def check_jobs(self, jobs):
        return audit.validate_jobs(jobs, {'id': 37, 'head_sha': 'a' * 40}, PROFILE)

    def test_complete_job_gate_and_only_two_failure_upload_skips(self):
        jobs = self.jobs()
        self.assertEqual(self.check_jobs(jobs), [
            {'job': 'integration-examples (3.11)', 'step': 'Retain reference build failure evidence',
             'number': 33, 'condition': 'failure()', 'value': False},
            {'job': 'integration-examples (3.14)', 'step': 'Retain reference build failure evidence',
             'number': 33, 'condition': 'failure()', 'value': False}])
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
