"""Routing cannot turn incomplete compiler validation into documentation success."""
from copy import deepcopy
import re
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import ci_validation as ci
from tests import test_ci_validation as fixtures
from tests import test_ci_change_scope as scope_fixtures

ROOT = Path(__file__).resolve().parents[1]


class RoutedGateTests(unittest.TestCase):
    def fixture(self, scope='full'):
        needs, receipts, accounting, expected = fixtures.ValidationGateTests().fixture()
        authority = {**expected, 'source_revision': 'b' * 40, 'repository': 'logannye/biocompiler',
                     'event': 'pull_request', 'workflow': '.github/workflows/ci.yml'}
        plan = {'scope': scope, 'identity': authority}
        docs = None
        needs.update({'change-scope': {'result': 'success', 'outputs': {'scope': scope}},
                      'docs-validation': {'result': 'skipped' if scope == 'full' else 'success'}})
        if scope == 'docs_only':
            docs = {'identity': deepcopy(authority)}
            receipts, accounting = [], []
            for name in ci.REQUIRED_NEEDS:
                needs[name] = {'result': 'skipped'}
        successes = (ci.full_job_names() - {'Validation complete'} if scope == 'full'
                     else {'docs-validation'}) | {'change-scope'}
        skips = {'docs-validation'} if scope == 'full' else ci.REQUIRED_NEEDS
        rows = [{'id': index + 1, 'name': name, 'run_id': 123, 'run_attempt': 2,
                 'head_sha': 'b' * 40, 'status': 'completed',
                 'conclusion': 'success' if name in successes else 'skipped'}
                for index, name in enumerate(sorted(successes | skips))]
        rows.append({'id': 999, 'name': 'Validation complete', 'run_id': 123, 'run_attempt': 2,
                     'head_sha': 'b' * 40, 'status': 'in_progress', 'conclusion': None})
        run = {'id': 123, 'run_attempt': 2, 'head_sha': 'b' * 40, 'status': 'in_progress',
               'conclusion': None, 'repository': {'full_name': 'logannye/biocompiler'},
               'event': 'pull_request', 'path': '.github/workflows/ci.yml'}
        return [ROOT, needs, receipts, accounting, expected, plan, docs, run,
                [{'total_count': len(rows), 'jobs': rows}]]

    def evaluate(self, args):
        # Source/event rederivation has separate real Git mutation tests. These
        # fixtures isolate route, complete legacy validation and live-job binding.
        with patch.object(ci.ci_change_scope, 'validate_plan', return_value=args[5]), \
             patch.object(ci.ci_change_scope, 'validate_docs', return_value=args[6]):
            return ci.validate_routed(*args)

    def assert_rejected(self, args):
        try:
            self.assertEqual(self.evaluate(args)['status'], 'fail')
        except (ValueError, KeyError):
            pass

    def test_full_route_preserves_every_legacy_slot(self):
        result = self.evaluate(self.fixture())
        self.assertEqual(result['schema_version'], 'biocompiler.ci_validation.v0.1')
        self.assertEqual(result['status'], 'pass')
        self.assertEqual(len(result['jobs']), 59)
        self.assertEqual(len(ci.full_job_names()), 74)
        for slot in ci.EXPECTED_RECEIPTS:
            with self.subTest(slot=slot):
                args = self.fixture()
                args[2] = [row for row in args[2] if (row['job'], row['variant']) != slot]
                self.assert_rejected(args)

    def test_documentation_has_distinct_non_release_schema(self):
        result = self.evaluate(self.fixture('docs_only'))
        self.assertEqual(result['schema_version'], 'biocompiler.ci_documentation_validation.v0.1')
        self.assertEqual(result['status'], 'pass')
        self.assertIs(result['acceptance'], False)
        self.assertIs(result['package_release_qualified'], False)
        self.assertEqual(result['native_validation'], 'not_run')
        self.assertNotIn('jobs', result)

    def test_docs_cannot_hide_executed_missing_or_failed_full_work(self):
        for job in ci.REQUIRED_NEEDS:
            for state in ('success', 'failure', 'cancelled', 'in_progress'):
                with self.subTest(job=job, state=state):
                    args = self.fixture('docs_only')
                    args[1][job]['result'] = state
                    self.assert_rejected(args)
        for kind in ('receipts', 'accounting', 'missing_scope', 'extra_needs', 'bad_scope_output'):
            args = self.fixture('docs_only')
            if kind == 'receipts': args[2].append({})
            elif kind == 'accounting': args[3].append({})
            elif kind == 'missing_scope': args[1].pop('change-scope')
            elif kind == 'extra_needs': args[1]['extra'] = {'result': 'success'}
            else: args[1]['change-scope']['outputs']['scope'] = 'full'
            self.assert_rejected(args)

    def test_receipt_must_match_actual_selected_producer_attempt(self):
        for scope, target in (('full', 'ci-preflight (3.11)'), ('full', 'change-scope'),
                              ('docs_only', 'docs-validation')):
            args = self.fixture(scope)
            row = next(row for row in args[8][0]['jobs'] if row['name'] == target)
            row['run_attempt'] = 1
            self.assert_rejected(args)
            if target == 'change-scope': args[5]['identity']['run_attempt'] = '1'
            elif target == 'docs-validation': args[6]['identity']['run_attempt'] = '1'
            else:
                next(receipt for receipt in args[2] if ci.concrete_job(receipt['job'], receipt['variant']) == target)['run_attempt'] = '1'
            self.assertEqual(self.evaluate(args)['status'], 'pass')

    def test_later_failed_job_cannot_be_hidden_by_earlier_receipt(self):
        args = self.fixture()
        row = args[8][0]['jobs'][0]
        earlier = {**row, 'id': 1001, 'run_attempt': 1}
        row['conclusion'] = 'failure'
        args[8][0]['jobs'].append(earlier)
        args[8][0]['total_count'] += 1
        self.assert_rejected(args)

    def test_route_failure_and_unexpected_docs_receipt_fail_full(self):
        for job in ci.ROUTING_NEEDS:
            args = self.fixture()
            args[1][job]['result'] = 'failure'
            self.assert_rejected(args)
        args = self.fixture()
        args[6] = {}
        self.assert_rejected(args)


class RealClassifierGateTests(unittest.TestCase):
    """Real classifier/seal/gate composition over inert Git objects and REST."""

    def setUp(self):
        # Import the fixture module, not its TestCase into this namespace:
        # unittest discovery must not duplicate the classifier controls.
        self.peer = scope_fixtures.ChangeScopeTests()
        self.peer.setUp()
        self.addCleanup(self.peer.doCleanups)

    def fixture(self, plan, docs):
        args = RoutedGateTests().fixture(plan['scope'])
        expected = {key: self.peer.env['GITHUB_' + field] for key, field in
                    (('revision', 'SHA'), ('run_id', 'RUN_ID'), ('run_attempt', 'RUN_ATTEMPT'))}
        args[0], args[4], args[5], args[6] = self.peer.root, expected, plan, docs
        for receipt in args[2]:
            receipt.update(expected)
        for account in args[3]:
            account['revision'] = expected['revision']
        args[7].update(id=int(expected['run_id']), run_attempt=int(expected['run_attempt']),
                       head_sha=self.peer.source)
        for row in args[8][0]['jobs']:
            row.update(run_id=int(expected['run_id']), run_attempt=int(expected['run_attempt']),
                       head_sha=self.peer.source)
            if row['name'] == 'change-scope':
                row['run_attempt'] = int(plan['identity']['run_attempt'])
            if row['name'] == 'docs-validation' and docs:
                row['run_attempt'] = int(docs['identity']['run_attempt'])
        return args

    def evaluate(self, args):
        return ci.validate_routed(*args, env=self.peer.env, event=self.peer.event)

    def test_real_readme_seal_reaches_only_distinct_documentation_gate(self):
        plan = self.peer.plan(); docs = self.peer.docs(plan)
        args = self.fixture(plan, docs)
        result = self.evaluate(args)
        self.assertEqual(result['status'], 'pass')
        self.assertEqual(result['schema_version'], 'biocompiler.ci_documentation_validation.v0.1')
        self.assertEqual(result['documentation'], docs)
        self.assertNotIn('jobs', result)
        self.assertIs(result['package_release_qualified'], False)
        (self.peer.root / 'README.md').write_bytes(b'changed after docs job\n')
        with self.assertRaisesRegex(ValueError, 'working bytes'):
            self.evaluate(args)

    def test_real_shared_change_falls_back_and_requires_every_full_receipt(self):
        for revision in (self.peer.source, self.peer.tested):
            self.peer.files[revision]['core/shared.ml'] = ('100644', b'changed shared source\n')
        plan = self.peer.plan()
        self.assertEqual(plan['scope'], 'full')
        args = self.fixture(plan, None)
        result = self.evaluate(args)
        self.assertEqual(result['schema_version'], 'biocompiler.ci_validation.v0.1')
        self.assertEqual(result['status'], 'pass')
        self.assertEqual(len(result['jobs']), 59)
        args[2].pop()
        self.assertEqual(self.evaluate(args)['status'], 'fail')

    def test_real_earlier_plan_and_docs_attempts_require_exact_actual_producers(self):
        plan = self.peer.plan(); docs = self.peer.docs(plan)
        self.peer.env['GITHUB_RUN_ATTEMPT'] = '2'
        args = self.fixture(plan, docs)
        result = self.evaluate(args)
        self.assertEqual(result['status'], 'pass')
        self.assertEqual(result['routing']['plan']['identity']['run_attempt'], '1')
        self.assertEqual(result['documentation']['identity']['run_attempt'], '1')
        actual = next(row for row in args[8][0]['jobs'] if row['name'] == 'docs-validation')
        actual['run_attempt'] = 2
        with self.assertRaisesRegex(ValueError, 'actual producing attempt'):
            self.evaluate(args)


class RoutingWorkflowTests(unittest.TestCase):
    def test_all_full_jobs_depend_on_gated_entry_or_explicit_scope(self):
        text = (ROOT / '.github/workflows/ci.yml').read_text()
        blocks = {match[1]: match[2] for match in re.finditer(
            r'^  ([a-z][a-z0-9-]*):\n(.*?)(?=^  [a-z][a-z0-9-]*:\n|\Z)',
            text.split('\njobs:\n', 1)[1], re.M | re.S)}
        self.assertEqual(set(blocks), ci.WORKFLOW_NEEDS | {'validation'})
        for job in ('ci-preflight', 'unit-accounting', 'prebuilt-core-validation'):
            self.assertIn("needs.change-scope.result == 'success'", blocks[job])
            self.assertIn("needs.change-scope.outputs.scope == 'full'", blocks[job])
        for job in ('unit-accounting', 'prebuilt-core-validation'):
            self.assertIn('always() &&', blocks[job])
            self.assertIn('needs: [change-scope, ', blocks[job])
        def ancestors(job, seen=frozenset()):
            self.assertNotIn(job, seen)
            needs = re.search(r'^    needs: (.*)$', blocks[job], re.M)
            direct = set(needs[1].strip('[]').split(', ')) if needs else set()
            return direct | set().union(*(ancestors(parent, seen | {job}) for parent in direct))
        for job in ci.REQUIRED_NEEDS:
            self.assertIn('change-scope', ancestors(job))
        final = blocks['validation']
        self.assertIn('name: Validation complete\n    if: always()', final)
        self.assertIn('filter=all&per_page=100', final)
        self.assertIn('gh api --paginate --slurp', final)
        self.assertIn('--scope-plan ', final)
        self.assertIn('--job-pages ', final)
        self.assertIn('name: validation-receipt', final)
        self.assertIn('del needs["change-scope"]', blocks['prebuilt-core-validation'])
        self.assertNotIn('paths-ignore:', text)
