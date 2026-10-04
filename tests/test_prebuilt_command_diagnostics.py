"""Bounded hosted-command diagnostics using only harmless Python children."""
from contextlib import redirect_stdout
import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import prebuilt_release_pipeline as pipeline


class HostedCommandDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.log = self.root / 'campaign.log'
        self.environment = pipeline.clean_environment(os.environ)
        self.environment['DIAGNOSTIC_ENV_NOT_FOR_OUTPUT'] = 'private-environment-sentinel'

    def run_python(self, script):
        return pipeline.run([sys.executable, '-I', '-c', script], cwd=self.root,
                            environment=self.environment, log=self.log, timeout=30)

    def test_failed_child_prints_bounded_cause_and_keeps_complete_combined_log(self):
        prefix = b'old-output-not-in-preview\n' + b'x' * (pipeline.FAILURE_TAIL_BYTES + 128) + b'\n'
        rows = b''.join(f'line-{index:03d}\n'.encode() for index in range(100))
        stdout = prefix + rows + b'long-line:' + b'y' * 2000 + b'\nstdout-cause\n'
        stderr = b'::error::not-a-workflow-command\n::add-mask::not-a-mask\n##[error]not-legacy\n'
        stderr += b':::error:::overlapping-colons\n'
        stderr += b'bad-utf8:\xff\x00\x1b[2J\rstderr-cause\n'
        script = ('import os\n'
                  "os.write(1, b'old-output-not-in-preview\\n' + b'x' * "
                  + str(pipeline.FAILURE_TAIL_BYTES + 128) + " + b'\\n')\n"
                  + 'os.write(1, ' + repr(rows + b'long-line:' + b'y' * 2000 + b'\nstdout-cause\n') + ')\n'
                  + 'os.write(2, ' + repr(stderr) + ')\nraise SystemExit(7)\n')
        output = io.StringIO()
        with patch.object(pipeline.time, 'monotonic', side_effect=[10.0, 11.25]), \
                redirect_stdout(output), self.assertRaisesRegex(ValueError, 'Hosted command failed; complete log retained'):
            self.run_python(script)
        envelope = output.getvalue().splitlines()
        self.assertEqual(envelope[:2], ['::group::Installed campaign: campaign', 'campaign: exit 7, 1.25s'])
        self.assertEqual(envelope[-1], '::endgroup::')
        self.assertEqual(envelope.count('::group::Installed campaign: campaign'), 1)
        self.assertEqual(envelope.count('::endgroup::'), 1)
        self.assertLessEqual(len(envelope), pipeline.FAILURE_TAIL_LINES + 4)
        # Only the approved three-line progress envelope is excluded. Every
        # original bound and escaping assertion below still checks the tail.
        shown = '\n'.join(envelope[2:-1]) + '\n'
        self.assertIn('(exit 7)', shown)
        self.assertIn('stdout-cause', shown)
        self.assertIn('stderr-cause', shown)
        self.assertNotIn('old-output-not-in-preview', shown)
        self.assertNotIn('line-000', shown)
        self.assertNotIn('private-environment-sentinel', shown)
        self.assertNotIn('::', shown)
        self.assertNotIn('##[', shown)
        self.assertIn(': :error: :not-a-workflow-command', shown)
        self.assertIn('[line truncated]', shown)
        self.assertTrue(shown.isascii())
        self.assertNotIn('\x00', shown)
        self.assertNotIn('\x1b', shown)
        self.assertNotIn('\r', shown)
        lines = shown.splitlines()
        self.assertLessEqual(len(lines), pipeline.FAILURE_TAIL_LINES + 1)
        self.assertTrue(all(line.startswith('  | ') for line in lines[1:]))
        self.assertTrue(all(len(line) <= pipeline.FAILURE_LINE_CHARS + 4 for line in lines[1:]))
        self.assertLessEqual(len(shown.encode('ascii')),
                             pipeline.FAILURE_TAIL_LINES * (pipeline.FAILURE_LINE_CHARS + 5) + 2048)
        self.assertEqual(self.log.read_bytes(), stdout + stderr)

    def test_success_retains_hashed_log_without_replaying_child_output(self):
        raw = b'success-stdout\nsuccess-stderr\n'
        output = io.StringIO()
        with patch.object(pipeline.time, 'monotonic', side_effect=[10.0, 11.25]), redirect_stdout(output):
            receipt = self.run_python("import os; os.write(1,b'success-stdout\\n'); os.write(2,b'success-stderr\\n')")
        self.assertEqual(output.getvalue().splitlines(), [
            '::group::Installed campaign: campaign', 'campaign: exit 0, 1.25s', '::endgroup::'])
        self.assertNotIn('success-stdout', output.getvalue())
        self.assertNotIn('success-stderr', output.getvalue())
        self.assertNotIn('log tail:', output.getvalue())
        self.assertEqual(receipt['duration_seconds'], 1.25)
        self.assertEqual(receipt['returncode'], 0)
        self.assertEqual(receipt['cwd'], str(self.root))
        self.assertEqual(receipt['log'], {'path': self.log.name, 'size': len(raw),
                                          'sha256': hashlib.sha256(raw).hexdigest()})
        self.assertEqual(self.log.read_bytes(), raw)

    def test_timeout_closes_log_before_preview_and_reraises_same_exception(self):
        timeout = subprocess.TimeoutExpired(['inert-timeout-control'], 30)
        handles = []
        def timed_out(*args, **kwargs):
            handles.append(kwargs['stdout'])
            kwargs['stdout'].write(b'partial-timeout-cause\n')
            raise timeout
        actual_tail = pipeline.failure_log_tail
        def closed_tail(log, **kwargs):
            self.assertTrue(handles[0].closed)
            return actual_tail(log, **kwargs)
        output = io.StringIO()
        with patch.object(pipeline.subprocess, 'run', side_effect=timed_out), \
                patch.object(pipeline, 'failure_log_tail', side_effect=closed_tail), redirect_stdout(output):
            with self.assertRaises(subprocess.TimeoutExpired) as caught:
                self.run_python('raise AssertionError("must be mocked")')
        self.assertIs(caught.exception, timeout)
        self.assertIn('(timeout)', output.getvalue())
        self.assertIn('partial-timeout-cause', output.getvalue())
        self.assertEqual(self.log.read_bytes(), b'partial-timeout-cause\n')
        envelope = output.getvalue().splitlines()
        self.assertEqual(envelope[0], '::group::Installed campaign: campaign')
        self.assertEqual(envelope[-1], '::endgroup::')
        self.assertEqual(envelope.count('::group::Installed campaign: campaign'), 1)
        self.assertEqual(envelope.count('::endgroup::'), 1)
        self.assertNotIn('campaign: exit', output.getvalue())

        # Opening the retained log can fail before a subprocess starts; the
        # begun group must still close without replacing that exact error.
        unavailable = self.root / 'unavailable.log'
        failure = OSError('inert log-open failure')
        output = io.StringIO()
        with patch.object(Path, 'open', side_effect=failure), \
                patch.object(pipeline.subprocess, 'run') as child, redirect_stdout(output):
            with self.assertRaises(OSError) as caught:
                pipeline.run([sys.executable, '-I', '-c', 'pass'], cwd=self.root,
                             environment=self.environment, log=unavailable)
        self.assertIs(caught.exception, failure)
        child.assert_not_called()
        self.assertEqual(output.getvalue().splitlines(), [
            '::group::Installed campaign: unavailable', '::endgroup::'])

    def test_preview_reads_only_the_bounded_suffix(self):
        self.log.write_bytes(b'x' * (pipeline.FAILURE_TAIL_BYTES * 2) + b'\nlast-cause\n')
        with self.log.open('rb') as source:
            wrapper = unittest.mock.MagicMock(wraps=source)
            wrapper.__enter__.return_value = wrapper
            wrapper.__exit__.return_value = False
            with patch.object(Path, 'open', return_value=wrapper), redirect_stdout(io.StringIO()) as output:
                pipeline.failure_log_tail(self.log, reason='exit 1')
            wrapper.read.assert_called_once_with(pipeline.FAILURE_TAIL_BYTES)
            self.assertEqual(wrapper.seek.call_args_list,
                             [unittest.mock.call(0, os.SEEK_END),
                              unittest.mock.call(self.log.stat().st_size - pipeline.FAILURE_TAIL_BYTES)])
        self.assertIn('last-cause', output.getvalue())

    def test_unavailable_preview_does_not_replace_child_failure(self):
        actual_open = Path.open
        def open_except_preview(path, mode='r', *args, **kwargs):
            if path == self.log and mode == 'rb' and not getattr(open_except_preview, 'failed', False):
                open_except_preview.failed = True
                raise OSError('inert preview read failure')
            return actual_open(path, mode, *args, **kwargs)
        with patch.object(Path, 'open', new=open_except_preview), redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, 'Hosted command failed; complete log retained'):
                self.run_python('raise SystemExit(9)')
        self.assertTrue(open_except_preview.failed)
        self.assertEqual(self.log.read_bytes(), b'')

    def test_unavailable_stdout_does_not_replace_timeout(self):
        timeout = subprocess.TimeoutExpired(['inert-timeout-control'], 30)
        def timed_out(*args, **kwargs):
            kwargs['stdout'].write(b'timeout-cause\n')
            raise timeout
        closed = io.StringIO()
        closed.close()
        with patch.object(pipeline.subprocess, 'run', side_effect=timed_out), redirect_stdout(closed):
            with self.assertRaises(subprocess.TimeoutExpired) as caught:
                self.run_python('raise AssertionError("must be mocked")')
        self.assertIs(caught.exception, timeout)
        self.assertEqual(self.log.read_bytes(), b'timeout-cause\n')


if __name__ == '__main__':
    unittest.main()
