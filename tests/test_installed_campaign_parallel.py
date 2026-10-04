"""Complete-campaign scheduling controls using inert subprocess stubs only."""
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import prebuilt_release_pipeline as pipeline
from tests import test_ci_scheduling as scheduling
from tests import test_prebuilt_release_chain as release


class InstalledCampaignParallelTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.receipt = {'status': 'running', 'commands': [], 'campaigns': []}
        self.environment = {'EXACT_ENVIRONMENT': 'preserved'}

    def plan(self, group='fixed'):
        return [(name, ['inert-python', name, '--output', str(self.root / (name + '.json'))])
                for name in pipeline.campaign_names(group)]

    def row(self, command, log, *, receipt=True):
        log.write_bytes(('complete inert log: ' + log.stem).encode())
        if receipt:
            (self.root / (log.stem + '.json')).write_text(json.dumps({'complete': log.stem}))
        return {'argv': command, 'cwd': str(self.root), 'returncode': 0, 'duration_seconds': 1.0,
                'log': {'path': log.name, 'size': log.stat().st_size, 'sha256': hashlib.sha256(log.read_bytes()).hexdigest()}}

    def execute(self, plan):
        return pipeline.execute_campaigns(plan, cwd=self.root, environment=self.environment,
                                          output=self.root, receipt=self.receipt)

    def test_actual_two_worker_overlap_all_five_and_original_receipt_order(self):
        plan = self.plan()
        lock, barrier = threading.Lock(), threading.Barrier(2)
        active = maximum = 0
        started, finished = [], []
        def run(command, *, cwd, environment, log, grouped):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
                started.append(log.stem)
            try:
                self.assertEqual(cwd, self.root)
                self.assertEqual(environment, self.environment)
                self.assertFalse(grouped)
                if log.stem != plan[-1][0]:
                    barrier.wait(5)
                return self.row(command, log)
            finally:
                with lock:
                    active -= 1
                    finished.append(log.stem)
        with patch.object(pipeline, 'run', side_effect=run):
            self.execute(plan)
        names = [name for name, _ in plan]
        self.assertEqual(maximum, 2)
        self.assertEqual(active, 0)
        self.assertCountEqual(started, names)
        self.assertCountEqual(finished, names)
        self.assertEqual([row['argv'] for row in self.receipt['commands']], [command for _, command in plan])
        self.assertEqual([row['name'] for row in self.receipt['campaigns']], names)
        self.assertEqual(self.receipt['campaign_execution'], pipeline.campaign_execution(names))

    def test_reversed_completion_keeps_manager_recipe_order(self):
        plan = self.plan('manager')
        second_done = threading.Event()
        completed = []
        def run(command, *, log, **kwargs):
            if log.stem == plan[0][0]:
                self.assertTrue(second_done.wait(5))
            row = self.row(command, log)
            completed.append(log.stem)
            if log.stem == plan[1][0]:
                second_done.set()
            return row
        with patch.object(pipeline, 'run', side_effect=run):
            self.execute(plan)
        self.assertEqual(completed, [plan[1][0], plan[0][0]])
        self.assertEqual([row['name'] for row in self.receipt['campaigns']], [name for name, _ in plan])

    def test_failure_and_missing_receipt_stop_dispatch_drain_started_and_fail_closed(self):
        for missing in (False, True):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory(dir=self.root) as folder:
                previous_root = self.root
                self.root = Path(folder)
                self.receipt = {'status': 'running', 'commands': [], 'campaigns': []}
                plan = self.plan()
                second_started, release_second, second_finished = (threading.Event() for _ in range(3))
                started = []
                failure = RuntimeError('Original failed child diagnostic')
                real_wait = pipeline.wait
                def wait(*args, **kwargs):
                    done, pending = real_wait(*args, **kwargs)
                    if any(future.result()[2] is not None for future in done):
                        release_second.set()
                    return done, pending
                def run(command, *, log, **kwargs):
                    started.append(log.stem)
                    if log.stem == plan[0][0]:
                        self.assertTrue(second_started.wait(5))
                        row = self.row(command, log, receipt=False)
                        if missing:
                            return row
                        raise failure
                    self.assertEqual(log.stem, plan[1][0], 'No new campaign after observed failure')
                    second_started.set()
                    self.assertTrue(release_second.wait(5))
                    row = self.row(command, log)
                    second_finished.set()
                    return row
                with patch.object(pipeline, 'run', side_effect=run), patch.object(pipeline, 'wait', side_effect=wait):
                    with self.assertRaises(ValueError if missing else RuntimeError) as caught:
                        self.execute(plan)
                if not missing:
                    self.assertIs(caught.exception, failure)
                else:
                    self.assertIn('Campaign omitted its complete receipt', str(caught.exception))
                self.assertTrue(second_finished.is_set())
                self.assertCountEqual(started, [name for name, _ in plan[:2]])
                self.assertEqual(self.receipt['status'], 'failure')
                self.assertEqual(self.receipt['campaign_execution']['started'], [name for name, _ in plan[:2]])
                self.assertEqual(self.receipt['campaign_failures'][0]['name'], plan[0][0])
                self.assertTrue(all((self.root / (name + '.log')).is_file() for name, _ in plan[:2]))
                self.assertEqual([row['name'] for row in self.receipt['campaigns']], [plan[1][0]])
                self.root = previous_root

    def test_duplicate_or_empty_plans_reject_before_dispatch(self):
        for plan in ([], [('same', ['inert']), ('same', ['inert'])]):
            with patch.object(pipeline, 'run') as run, self.assertRaisesRegex(ValueError, 'parallel campaign plan'):
                self.execute(plan)
            run.assert_not_called()

    def test_source_worker_and_started_census_are_independently_required(self):
        for mutation in ('missing', 'source', 'workers', 'order', 'started'):
            fixture = scheduling.PartitionedReceiptTests()
            fixture.setUp()
            self.addCleanup(fixture.doCleanups)
            receipt = fixture.parts['manager']
            if mutation == 'missing':
                del receipt['campaign_execution']
            elif mutation == 'source':
                receipt['campaign_execution']['driver_source']['sha256'] = '0' * 64
            elif mutation == 'workers':
                receipt['campaign_execution']['workers'] = 3
            elif mutation == 'order':
                receipt['campaign_execution']['campaign_order'].reverse()
            else:
                receipt['campaign_execution']['started'].pop()
            fixture.write_groups()
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'Parallel campaign execution'):
                pipeline.aggregate(fixture.args)

    def test_lifecycle_stays_serial_and_ownership_after_waits_for_every_campaign(self):
        self.assertEqual(pipeline.PARALLEL_CAMPAIGN_GROUPS, {'fixed', 'manager'})
        for group in ('fixed', 'manager'):
            fixture = release.HostedPlanTests()
            fixture.setUp()
            self.addCleanup(fixture.doCleanups)
            installed = pipeline.installed
            def grouped(args):
                args.group = group
                return installed(args)
            # Legacy fixtures import the driver by its script name; bind the
            # exact tested module explicitly without changing global aliases.
            with patch.object(release, 'pipeline', pipeline), patch.object(pipeline, 'installed', side_effect=grouped):
                args, python, console, foreign, calls, owners, receipt = fixture.installed_console_fixture(inherited_path=True, fresh_mode=0o755)
            expected = pipeline.campaign_names(group)
            self.assertEqual([row['name'] for row in calls[:6]], list(pipeline.LIFECYCLE_NAMES))
            self.assertCountEqual([row['name'] for row in calls[6:]], expected)
            self.assertEqual(owners, [2, 6, 6 + len(expected)])
            self.assertEqual([row['name'] for row in receipt['campaigns']], expected)
            self.assertEqual(receipt['ownership_before'], receipt['ownership_after'])
            self.assertEqual(receipt['status'], 'pass')

    def test_parallel_log_envelope_does_not_interleave_actions_group_markers(self):
        for outcome in ('success', 'nonzero', 'timeout'):
            with self.subTest(outcome=outcome):
                log = self.root / (outcome + '.log')
                raw = b'complete inert subprocess diagnostic'
                timeout = pipeline.subprocess.TimeoutExpired(['inert'], 1)
                def child(command, **kwargs):
                    kwargs['stdout'].write(raw)
                    if outcome == 'timeout':
                        raise timeout
                    return SimpleNamespace(returncode=0 if outcome == 'success' else 7)
                output = io.StringIO()
                with patch.object(pipeline.subprocess, 'run', side_effect=child), redirect_stdout(output):
                    if outcome == 'success':
                        receipt = pipeline.run(['inert'], cwd=self.root, environment={}, log=log, grouped=False)
                        self.assertEqual(receipt['log']['sha256'], hashlib.sha256(raw).hexdigest())
                    elif outcome == 'nonzero':
                        with self.assertRaisesRegex(ValueError, 'Hosted command failed'):
                            pipeline.run(['inert'], cwd=self.root, environment={}, log=log, grouped=False)
                    else:
                        with self.assertRaises(pipeline.subprocess.TimeoutExpired) as caught:
                            pipeline.run(['inert'], cwd=self.root, environment={}, log=log, grouped=False)
                        self.assertIs(caught.exception, timeout)
                self.assertNotIn('::group::', output.getvalue())
                self.assertNotIn('::endgroup::', output.getvalue())
                self.assertIn('Installed campaign: ' + outcome, output.getvalue())
                self.assertEqual(log.read_bytes(), raw)
                if outcome != 'success':
                    self.assertIn(raw.decode(), output.getvalue())


if __name__ == '__main__':
    unittest.main()
