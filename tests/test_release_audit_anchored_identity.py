"""Literal anchored-release controls; no live API or release acceptance."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import release_audit as audit
from tools.release_audit_identity import IdentityError, check_anchored_main_identity, check_main_identity


def fixture():
    expected = {
        'schema': 'biocompiler.anchored_main_identity.v1', 'repository': 'example/project',
        'repository_id': 17, 'main_branch': 'main', 'pr_number': 85,
        'pr_head_branch': 'codex/integration', 'accepted_pr_head': 'a' * 40,
        'premerge_main': 'b' * 40, 'merge_revision': 'c' * 40, 'accepted_tree': 'd' * 40,
        'run_id': 37, 'run_attempt': 1, 'workflow_id': 42, 'workflow_path': '.github/workflows/ci.yml',
        'check_suite_id': 53, 'actions_app_id': 64, 'actions_app_slug': 'github-actions',
        'main_anchor_sha256': '1' * 64, 'main_anchor_captured_at': '2026-10-08T01:01:00Z',
        'observed_main_revision': 'e' * 40, 'observed_main_ref_sha256': '2' * 64,
        'observed_main_captured_at': '2026-10-08T02:01:00+00:00', 'ancestry_sha256': '3' * 64,
    }
    # Independently literal API shapes, not synthesized from expected or output.
    packet = {
        'run': {'event': 'push', 'head_branch': 'main', 'head_sha': 'c' * 40,
                'head_commit': {'id': 'c' * 40, 'tree_id': 'd' * 40}, 'id': 37, 'run_attempt': 1,
                'workflow_id': 42, 'path': '.github/workflows/ci.yml', 'check_suite_id': 53,
                'repository': {'full_name': 'example/project', 'id': 17},
                'head_repository': {'full_name': 'example/project', 'id': 17},
                'status': 'completed', 'conclusion': 'success', 'updated_at': '2026-10-08T02:00:00Z'},
        'commit': {'sha': 'c' * 40, 'tree': {'sha': 'd' * 40},
                   'parents': [{'sha': 'b' * 40}, {'sha': 'a' * 40}]},
        'main_anchor': {'ref': 'refs/heads/main', 'object': {'type': 'commit', 'sha': 'c' * 40}},
        'main_ref': {'ref': 'refs/heads/main', 'object': {'type': 'commit', 'sha': 'e' * 40},
                     'url': 'https://api.github.com/repos/example/project/git/refs/heads/main'},
        'pr': {'number': 85, 'state': 'closed', 'merged': True, 'merge_commit_sha': 'c' * 40,
               'merged_at': '2026-10-08T01:00:00Z',
               'head': {'sha': 'a' * 40, 'ref': 'codex/integration',
                        'repo': {'full_name': 'example/project', 'id': 17}},
               'base': {'ref': 'main', 'repo': {'full_name': 'example/project', 'id': 17}}},
        'suite': {'id': 53, 'head_sha': 'c' * 40, 'head_branch': 'main',
                  'before': 'b' * 40, 'after': 'c' * 40,
                  'head_commit': {'id': 'c' * 40, 'tree_id': 'd' * 40},
                  'repository': {'full_name': 'example/project', 'id': 17},
                  'app': {'id': 64, 'slug': 'github-actions'},
                  'status': 'completed', 'conclusion': 'success'},
        'ancestry': {'url': 'https://api.github.com/repos/example/project/compare/' + 'c' * 40 + '...' + 'e' * 40,
                     'base_commit': {'sha': 'c' * 40}, 'merge_base_commit': {'sha': 'c' * 40},
                     'status': 'ahead', 'ahead_by': 1, 'behind_by': 0, 'total_commits': 1,
                     'commits': [{'sha': 'e' * 40, 'parents': [{'sha': 'c' * 40}]}]},
    }
    pins = {name: {'sha256': 'f' * 64, 'bytes': 100} for name in packet}
    pins['main_anchor']['sha256'] = '1' * 64
    pins['main_ref']['sha256'] = '2' * 64
    pins['ancestry']['sha256'] = '3' * 64
    return expected, packet, pins


def replace(value, path, changed):
    for name in path[:-1]: value = value[name]
    value[path[-1]] = changed


class AnchoredIdentityTests(unittest.TestCase):
    def setUp(self):
        for target in ('subprocess.Popen', 'socket.socket', 'socket.create_connection', 'ctypes.CDLL', 'os.system'):
            guard = patch(target, side_effect=AssertionError('Inert audit tests forbid execution/network'))
            guard.start(); self.addCleanup(guard.stop)

    def check(self, expected=None, packet=None, pins=None, success=True):
        e, p, a = fixture()
        return check_anchored_main_identity(expected=e if expected is None else expected,
            api_pins=a if pins is None else pins, require_success=success, **(p if packet is None else packet))

    def test_positive_keeps_release_m_and_distinguishes_observed_tip(self):
        result = self.check()
        self.assertEqual(result['schema'], 'biocompiler.anchored_main_identity_result.v1')
        self.assertEqual(result['source_revision'], 'c' * 40)
        self.assertEqual(result['tested_revision'], 'c' * 40)
        self.assertEqual(result['main_anchor']['revision'], 'c' * 40)
        self.assertEqual(result['observed_main']['revision'], 'e' * 40)
        self.assertIs(result['observed_main']['release_acceptance'], False)
        self.assertEqual(result['ancestry']['commits'], 1)
        self.assertIn('not_tip_release_acceptance', result['scope'])

    def test_original_current_main_rule_is_not_changed(self):
        expected, packet, _ = fixture()
        original = {k: v for k, v in expected.items() if k not in {
            'main_anchor_sha256', 'main_anchor_captured_at', 'observed_main_revision',
            'observed_main_ref_sha256', 'observed_main_captured_at', 'ancestry_sha256'}}
        original['schema'] = 'biocompiler.actual_main_identity.v1'
        original_packet = {k: v for k, v in packet.items() if k not in ('main_anchor', 'ancestry')}
        with self.assertRaisesRegex(IdentityError, 'current main revision'):
            check_main_identity(expected=original, **original_packet)
        original_packet['main_ref'] = packet['main_anchor']
        self.assertEqual(check_main_identity(expected=original, **original_packet)['schema'],
                         'biocompiler.actual_main_identity_result.v1')

    def test_unmodified_original_checker_bodies(self):
        path = Path(__file__).resolve().parents[1] / 'tools/release_audit_identity.py'
        source = path.read_text()
        wanted = {
            'check_main_identity': 'e2bb07988996a34d4aa6bedbb48ca8cf783dc3e7374786998a4c921824898fc0',
            'check_pr_identity': '313f8ce86fb3be5e19eb624a75db9ba714ca90d85b40aebabe7143cd46d9c941',
        }
        observed = {node.name: hashlib.sha256(ast.get_source_segment(source, node).encode()).hexdigest()
                    for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name in wanted}
        self.assertEqual(observed, wanted)

    def test_authority_is_closed_and_raw_pins_are_required(self):
        for key, value in [('main_anchor_sha256', '0' * 64), ('ancestry_sha256', 'x' * 64),
                           ('observed_main_ref_sha256', '0' * 64), ('observed_main_revision', 'c' * 40),
                           ('run_attempt', True), ('unknown', True)]:
            expected, _, _ = fixture(); expected[key] = value
            with self.subTest(key=key), self.assertRaises(IdentityError): self.check(expected=expected)
        for name in ('main_anchor', 'main_ref', 'ancestry'):
            _, _, pins = fixture(); pins[name]['sha256'] = '0' * 64
            with self.subTest(name=name), self.assertRaises(IdentityError): self.check(pins=pins)
        for missing in ('main_anchor_captured_at', 'observed_main_captured_at', 'observed_main_ref_sha256'):
            expected, _, _ = fixture(); del expected[missing]
            with self.subTest(missing=missing), self.assertRaises(IdentityError): self.check(expected=expected)
        with self.assertRaises(IdentityError): self.check(pins={})

    def test_capture_times_are_typed_ordered_caller_authority(self):
        for key, value in [('main_anchor_captured_at', '2026-10-08T00:59:00Z'),
                           ('main_anchor_captured_at', '2026-10-08T03:00:00Z'),
                           ('observed_main_captured_at', '2026-10-08T01:59:00Z'),
                           ('observed_main_captured_at', '2026-10-08'),
                           ('observed_main_captured_at', '2026-13-08T02:01:00Z'),
                           ('observed_main_captured_at', '2026-10-08T02:01:00-01:00'),
                           ('observed_main_captured_at', True)]:
            expected, _, _ = fixture(); expected[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(IdentityError): self.check(expected=expected)

    def test_old_release_checks_remain_required_in_anchored_route(self):
        for path, value in [(('run', 'event'), 'workflow_dispatch'), (('run', 'head_sha'), 'a' * 40),
                             (('run', 'run_attempt'), 2), (('run', 'status'), 'in_progress'),
                             (('run', 'conclusion'), 'failure'), (('suite', 'head_sha'), 'e' * 40),
                             (('suite', 'conclusion'), 'failure'), (('commit', 'tree', 'sha'), 'e' * 40),
                             (('commit', 'parents'), [{'sha': 'a' * 40}, {'sha': 'b' * 40}]),
                             (('main_anchor', 'object', 'sha'), 'e' * 40), (('pr', 'merged'), False)]:
            _, packet, _ = fixture(); replace(packet, path, value)
            with self.subTest(path=path), self.assertRaises(IdentityError): self.check(packet=packet)

    def test_fresh_tip_and_comparison_endpoint_cannot_be_substituted(self):
        for path, value in [(('main_ref', 'object', 'sha'), 'f' * 40), (('main_ref', 'object', 'type'), 'tag'),
                             (('main_ref', 'url'), 'https://api.github.com/repos/other/project/git/refs/heads/main'),
                             (('ancestry', 'url'), 'https://api.github.com/repos/example/project/compare/main...main'),
                             (('ancestry', 'base_commit', 'sha'), 'b' * 40),
                             (('ancestry', 'merge_base_commit', 'sha'), 'b' * 40),
                             (('ancestry', 'status'), 'diverged'), (('ancestry', 'behind_by'), 1),
                             (('ancestry', 'behind_by'), False), (('ancestry', 'ahead_by'), True),
                             (('ancestry', 'total_commits'), 1.0), (('ancestry', 'total_commits'), 101)]:
            _, packet, _ = fixture(); replace(packet, path, value)
            with self.subTest(path=path), self.assertRaises(IdentityError): self.check(packet=packet)

    def test_truncated_duplicate_detached_and_malformed_parent_graph_rejected(self):
        for commits in ([], [{'sha': 'f' * 40, 'parents': [{'sha': 'c' * 40}]}],
                        [{'sha': 'e' * 40, 'parents': [{'sha': 'b' * 40}]}],
                        [{'sha': 'e' * 40, 'parents': [{'sha': 'e' * 40}]}],
                        [{'sha': 'e' * 40, 'parents': [{'sha': 'c' * 40}] * 2}],
                        [{'sha': 'e' * 40, 'parents': []}],
                        [{'sha': 'e' * 40, 'parents': [{'sha': None}]}]):
            _, packet, _ = fixture(); packet['ancestry']['commits'] = commits
            with self.subTest(commits=commits), self.assertRaises(IdentityError): self.check(packet=packet)
        _, packet, _ = fixture()
        packet['ancestry'].update(total_commits=2, ahead_by=2)
        packet['ancestry']['commits'] *= 2
        with self.assertRaises(IdentityError): self.check(packet=packet)

    def test_complete_two_commit_graph_and_pending_prepare_have_bounded_scope(self):
        _, packet, _ = fixture()
        packet['ancestry'].update(total_commits=2, ahead_by=2, commits=[
            {'sha': 'f' * 40, 'parents': [{'sha': 'c' * 40}]},
            {'sha': 'e' * 40, 'parents': [{'sha': 'f' * 40}]}])
        self.assertEqual(self.check(packet=packet)['ancestry']['commits'], 2)
        for name in ('run', 'suite'): packet[name].update(status='in_progress', conclusion=None)
        self.assertIs(self.check(packet=packet, success=False)['requires_success'], False)
        with self.assertRaises(IdentityError): self.check(packet=packet)

    def test_dispatch_keeps_original_plan_identity_and_requires_seven_inputs_and_pins(self):
        expected, packet, pins = fixture()
        identity, tree, base, proof = audit.identity_from_authority(expected, packet, True, pins)
        self.assertEqual(identity, {'head_revision': 'c' * 40, 'revision': 'c' * 40, 'run_id': '37', 'run_attempt': '1'})
        self.assertEqual((tree, base), ('d' * 40, 'b' * 40))
        self.assertEqual(proof['observed_main']['revision'], 'e' * 40)
        with self.assertRaises(ValueError): audit.identity_from_authority(expected, packet, True)
        for name in ('main_anchor', 'ancestry'):
            changed = copy.deepcopy(packet); del changed[name]
            with self.assertRaises(AssertionError): audit.identity_from_authority(expected, changed, True, pins)

    def test_packet_reader_recomputes_exact_raw_pins_before_identity_dispatch(self):
        expected, packet, _ = fixture()
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw); files = {}
            for name, value in packet.items():
                path = directory / (name + '.json'); path.write_text(json.dumps(value))
                files[name] = {'path': path.name, 'sha256': audit.sha(path)}
            for name, key in [('main_anchor', 'main_anchor_sha256'), ('main_ref', 'observed_main_ref_sha256'),
                              ('ancestry', 'ancestry_sha256')]: expected[key] = files[name]['sha256']
            path = directory / 'packet.json'
            path.write_text(json.dumps({'schema': 'biocompiler.release_api_packet.v1', 'files': files}))
            decoded, pins = audit.read_packet(path, audit.sha(path))
            self.assertEqual(audit.identity_from_authority(expected, decoded, True, pins)[0]['revision'], 'c' * 40)
            (directory / 'main_anchor.json').write_text('{}')
            with self.assertRaises(AssertionError): audit.read_packet(path, audit.sha(path))


if __name__ == '__main__':
    unittest.main()
