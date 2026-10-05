"""Deterministic exit/readiness controls over real pipes; no native execution."""
import os
import selectors
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from biocompiler import core_pipeline_session as transport
from biocompiler.core_client import CoreCancelled, CoreProtocolError, CoreTimeout, CoreTransportError
from biocompiler.core_pipeline_session import CorePipelineSession, capability_profile, encode_document


@unittest.skipUnless(os.name == 'posix', 'Persistent pipeline transport targets POSIX')
class SessionExitedPipeTests(unittest.TestCase):
    def exchanged_pipe(self, packet, *, exit_code=0, stderr=b'', keep_stdout_open=False):
        pipes = []
        for _ in range(3):
            read, write = os.pipe()
            pipes.append((os.fdopen(read, 'rb', buffering=0), os.fdopen(write, 'wb', buffering=0)))
        for pair in pipes:
            for pipe in pair:
                self.addCleanup(pipe.close)
                os.set_blocking(pipe.fileno(), False)
        stdin_read, stdin_write = pipes[0]
        stdout_read, stdout_write = pipes[1]
        stderr_read, stderr_write = pipes[2]
        self.assertEqual(os.write(stdout_write.fileno(), packet), len(packet))
        self.assertEqual(os.write(stderr_write.fileno(), stderr), len(stderr))
        if not keep_stdout_open:
            stdout_write.close()
        stderr_write.close()
        process = SimpleNamespace(stdin=stdin_write, stdout=stdout_read, stderr=stderr_read, returncode=None)
        process.poll = lambda: process.returncode
        process.wait = lambda: process.returncode
        delegate = selectors.DefaultSelector()
        self.addCleanup(delegate.close)
        delegate.register(stdout_read, selectors.EVENT_READ, 'stdout')
        delegate.register(stderr_read, selectors.EVENT_READ, 'stderr')

        class DelayedStdout:
            first_wait = True

            def select(self, timeout=None):
                if self.first_wait:
                    if timeout == 0:
                        return []
                    self.first_wait = False
                    return [(delegate.get_key(stdin_write), selectors.EVENT_WRITE)]
                return delegate.select(timeout)

            def unregister(self, pipe):
                result = delegate.unregister(pipe)
                if pipe is stdin_write:
                    # The child exits after the request write, outside the
                    # readiness snapshot, with its complete reply still unread.
                    process.returncode = exit_code
                return result

            def __getattr__(self, name):
                return getattr(delegate, name)

        session = CorePipelineSession.__new__(CorePipelineSession)
        session._process, session._selector = process, DelayedStdout()
        session._eof, session._stderr = set(), bytearray()
        session._input_bytes = session._output_bytes = 0
        session._limits = capability_profile()['limits']
        session._closed = False
        session._finalizer = SimpleNamespace(detach=lambda: None)
        return session, stdin_read

    def test_exit_does_not_discard_buffered_frame_before_stdout_read(self):
        response = encode_document({'closed': True, 'status': 'ok', 'result': None})
        request = encode_document({'operation': 'close', 'sequence': 1})
        for code in (0, 7):
            with self.subTest(exit_code=code):
                session, stdin = self.exchanged_pipe(transport._frame(response), exit_code=code)
                self.assertEqual(session._exchange(request, time.monotonic() + 1, None), response)
                self.assertEqual(os.read(stdin.fileno(), 4096), transport._frame(request))
                self.assertEqual(session._input_bytes, len(transport._frame(request)))
                self.assertEqual(session._output_bytes, len(transport._frame(response)))
                self.assertEqual(session.returncode, code)
                if code == 0:
                    session._finish(time.monotonic() + 1, None)
                    self.assertTrue(session.closed)
                else:
                    with self.assertRaisesRegex(CoreTransportError, 'exited unsuccessfully'):
                        session._finish(time.monotonic() + 1, None)

    def test_exited_peer_truncation_requires_actual_stdout_eof(self):
        for packet in (b'', b'0000', b'00000010\nshort'):
            with self.subTest(packet=packet):
                session, _ = self.exchanged_pipe(packet)
                with self.assertRaisesRegex(CoreTransportError, 'incomplete response frame'):
                    session._exchange(b'{}', time.monotonic() + 1, None)
                self.assertIn('stdout', session._eof)
                self.assertEqual(session._output_bytes, 0)

    def test_exited_peer_preserves_frame_and_stderr_bounds(self):
        for packet, error, message, note in (
                (b'0000000G\n', CoreProtocolError, 'Invalid pipeline session frame header', b''),
                (b'00000002\n{}x', CoreProtocolError, 'Trailing or multiple', b''),
                (b'02000001\n', CoreProtocolError, 'frame byte limit', b''),
                (b'', CoreTransportError, 'stderr limit', b'bounded-note')):
            with self.subTest(message=message):
                session, _ = self.exchanged_pipe(packet, stderr=note)
                with patch.object(transport, 'MAX_STDERR_BYTES', 4), self.assertRaisesRegex(error, message):
                    session._exchange(b'{}', time.monotonic() + 1, None)

    def test_exited_peer_preserves_aggregate_wire_limit(self):
        session, _ = self.exchanged_pipe(transport._frame(b'{}'))
        session._limits['max_total_bytes'] = len(transport._frame(b'{}')) * 2 - 1
        with self.assertRaisesRegex(CoreTransportError, 'aggregate byte limit'):
            session._exchange(b'{}', time.monotonic() + 1, None)

    def test_exited_process_with_inherited_pipe_keeps_deadline(self):
        session, _ = self.exchanged_pipe(b'', keep_stdout_open=True)
        with self.assertRaisesRegex(CoreTimeout, 'exceeded its deadline'):
            session._exchange(b'{}', time.monotonic() + .05, None)
        self.assertNotIn('stdout', session._eof)

    def test_exited_process_with_inherited_pipe_keeps_cancellation(self):
        session, _ = self.exchanged_pipe(b'', keep_stdout_open=True)
        with self.assertRaisesRegex(CoreCancelled, 'command cancelled'):
            session._exchange(b'{}', time.monotonic() + 1, lambda: session.returncode is not None)
        self.assertNotIn('stdout', session._eof)


if __name__ == '__main__':
    unittest.main()
