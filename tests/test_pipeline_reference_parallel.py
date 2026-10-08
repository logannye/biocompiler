"""Inert four-slot reconstruction scheduling and unchanged authority controls."""
from collections import Counter
from pathlib import Path
import subprocess
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests import test_pipeline_reference_runtime as original
from tools import pipeline_reference_runtime as runtime


class ReferenceParallelTests(unittest.TestCase):
    def setUp(self):
        self.fixture = original.ReferenceRuntimeAuthorityTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.names = list(self.fixture.rows)

    def slot(self, command):
        return Path(command[command.index('--receipt') + 1]).parent.name

    def test_complete_preparation_precedes_four_workers_and_canonical_validation(self):
        barrier = threading.Barrier(4, timeout=5)
        release = [threading.Event() for _ in range(4)]
        release[-1].set()
        lock = threading.Lock()
        prepared, active, peak = [], 0, 0
        finished, outputs, validated = [], [], []
        parent = threading.get_ident()
        artifacts, read = runtime.manager.Artifacts, runtime.r.read

        def prepare(*args, **kwargs):
            self.assertEqual(threading.get_ident(), parent)
            result = artifacts(*args, **kwargs)
            prepared.append(result)
            return result

        def worker(command, **kwargs):
            nonlocal active, peak
            name = self.slot(command)
            number = self.names.index(name)
            self.assertNotEqual(threading.get_ident(), parent)
            self.assertEqual(len(prepared), 4)
            self.assertEqual(kwargs, {'cwd': kwargs['cwd'], 'capture_output': True,
                'timeout': 10800, 'check': False})
            self.assertFalse(Path(kwargs['cwd']).is_relative_to(runtime.ROOT))
            with lock:
                active += 1
                peak = max(peak, active)
                outputs.append(command[command.index('--output') + 1])
            barrier.wait()
            self.assertTrue(release[number].wait(5))
            result = self.fixture.worker(command, **kwargs)
            with lock:
                active -= 1
                finished.append(name)
            if number:
                release[number - 1].set()
            return result

        def checked_read(path, *args, **kwargs):
            if Path(path).stem in self.names:
                self.assertEqual(threading.get_ident(), parent)
                self.assertEqual(len(finished), 4)
                validated.append(Path(path).stem)
            return read(path, *args, **kwargs)

        self.fixture.run.side_effect = worker
        with patch.object(runtime.manager, 'Artifacts', side_effect=prepare), \
                patch.object(runtime.r, 'read', side_effect=checked_read):
            result = self.fixture.compare()
        self.assertEqual(peak, 4)
        self.assertEqual(active, 0)
        self.assertEqual(finished, self.names[::-1])
        self.assertEqual(validated, self.names)
        self.assertEqual(list(result['receipts']), self.names)
        self.assertEqual(len(set(outputs)), 4)

    def test_last_slot_authority_failure_prevents_every_launch(self):
        self.fixture.inputs[self.names[-1]]['run_id'] = 'stale'
        self.fixture.save()
        with self.assertRaisesRegex(AssertionError, 'Stale reference native inputs'):
            self.fixture.compare()
        self.fixture.run.assert_not_called()

    def failed_cohort(self, failure):
        barrier = threading.Barrier(4, timeout=5)
        failed = threading.Event()
        lock = threading.Lock()
        finished = []

        def worker(command, **kwargs):
            name = self.slot(command)
            barrier.wait()
            try:
                if name == self.names[0]:
                    failed.set()
                    if isinstance(failure, BaseException):
                        raise failure
                    return failure
                self.assertTrue(failed.wait(5))
                return self.fixture.worker(command, **kwargs)
            finally:
                # Directory must survive every sibling's completion, even
                # when the canonical first slot fails immediately.
                self.assertTrue(Path(kwargs['cwd']).is_dir())
                with lock:
                    finished.append(name)

        self.fixture.run.side_effect = worker
        return finished

    def test_spawn_exception_and_timeout_drain_all_started_slots(self):
        for failure in (OSError('inert spawn failure'),
                        subprocess.TimeoutExpired(['inert-worker'], 10800)):
            with self.subTest(failure=type(failure).__name__):
                finished = self.failed_cohort(failure)
                with self.assertRaises(type(failure)) as caught:
                    self.fixture.compare()
                self.assertIs(caught.exception, failure)
                self.assertEqual(Counter(finished), Counter(self.names))

    def test_nonzero_and_excess_diagnostics_drain_without_acceptance(self):
        for failure, message in (
                (SimpleNamespace(returncode=1, stdout=b'', stderr=b'inert failure'),
                 'independent reconstruction failed'),
                (SimpleNamespace(returncode=0, stdout=b'x' * (1024 * 1024 + 1), stderr=b''),
                 'diagnostics exceeded bound')):
            with self.subTest(message=message):
                finished = self.failed_cohort(failure)
                with self.assertRaisesRegex(AssertionError, message):
                    self.fixture.compare()
                self.assertEqual(Counter(finished), Counter(self.names))

    def test_last_slot_report_authority_is_not_hidden_by_parallel_success(self):
        finished = []
        lock = threading.Lock()

        def worker(command, **kwargs):
            result = self.fixture.worker(command, **kwargs)
            name = self.slot(command)
            if name == self.names[-1]:
                output = Path(command[command.index('--output') + 1])
                report, _ = runtime.r.read(output)
                report['receipt_sha256'] = '0' * 64
                output.write_bytes(runtime.canonical(report) + b'\n')
            with lock:
                finished.append(name)
            return result

        self.fixture.run.side_effect = worker
        with self.assertRaisesRegex(AssertionError, 'Unbound reference reconstruction worker'):
            self.fixture.compare()
        self.assertEqual(Counter(finished), Counter(self.names))

    def test_cross_slot_complete_projection_equality_is_still_required(self):
        def worker(command, **kwargs):
            result = self.fixture.worker(command, **kwargs)
            if self.slot(command) == self.names[-1]:
                output = Path(command[command.index('--output') + 1])
                report, _ = runtime.r.read(output)
                report['projection']['original_behavior']['unaccepted_difference'] = True
                output.write_bytes(runtime.canonical(report) + b'\n')
            return result

        self.fixture.run.side_effect = worker
        with self.assertRaisesRegex(AssertionError, 'public behavior differs across runtimes'):
            self.fixture.compare()

    def test_missing_worker_output_cannot_be_replaced_by_sibling_success(self):
        def worker(command, **kwargs):
            result = self.fixture.worker(command, **kwargs)
            if self.slot(command) == self.names[-1]:
                Path(command[command.index('--output') + 1]).unlink()
            return result

        self.fixture.run.side_effect = worker
        with self.assertRaises((AssertionError, FileNotFoundError)):
            self.fixture.compare()


if __name__ == '__main__':
    unittest.main()
