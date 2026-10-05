"""Actual subprocess fixtures for framing/continuations, never native acceptance."""
from dataclasses import FrozenInstanceError
import hashlib
import os
from pathlib import Path
import selectors
import sys
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from biocompiler.core_client import CoreCancelled, CoreClient, CoreProtocolError, CoreTimeout, CoreTransportError, CoreUnavailable
from biocompiler.core_pipeline_session import encode_document
from biocompiler import core_pipeline_callback_session as transport
from biocompiler.core_pipeline_callback_session import CallbackFatal, CallbackRejected, CorePipelineCallbackSession, capability_profile
from biocompiler.pipeline_callback_objects import CallbackObjects


APPLICATION = {'schema_version': 'tests.host-callback.v1', 'authority': 'transport-fixture-only'}


@unittest.skipUnless(os.name == 'posix', 'Persistent callback transport targets POSIX')
class CallbackExitedPipeTests(unittest.TestCase):
    """Real pipe reads with one controlled readiness turn; no child execution."""

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
                    # Full command sent after select's readiness snapshot; the
                    # peer can exit with its reply still buffered for the next read.
                    process.returncode = exit_code
                return result

            def __getattr__(self, name):
                return getattr(delegate, name)

        session = CorePipelineCallbackSession.__new__(CorePipelineCallbackSession)
        session._package_files = None
        session._process, session._selector = process, DelayedStdout()
        session._eof, session._commands, session._traffic = set(), [], []
        session._stderr, session._sent = bytearray(), {}
        session._input_bytes = session._output_bytes = session._frame_count = session._node_count = 0
        session._next_event, session._limits = 0, capability_profile()['limits']
        session._closed = False
        session._finalizer = SimpleNamespace(detach=lambda: None)
        return session, stdin_read

    def test_exit_does_not_discard_buffered_frame_before_stdout_read(self):
        response = encode_document({'closed': True, 'outcome': {'status': 'ok', 'value': None}})
        request = encode_document({'kind': 'close', 'sequence': 1})
        for code in (0, 7):
            with self.subTest(exit_code=code):
                session, stdin = self.exchanged_pipe(transport._frame(response), exit_code=code)
                self.assertEqual(session._exchange(request, time.monotonic() + 1), response)
                self.assertEqual(os.read(stdin.fileno(), 4096), transport._frame(request))
                self.assertEqual([(item.direction, item.document) for item in session.traffic],
                                 [('client', request), ('server', response)])
                self.assertEqual(session.returncode, code)
                if code == 0:
                    session._finish(time.monotonic() + 1)
                    self.assertTrue(session.closed)
                else:
                    with self.assertRaisesRegex(CoreTransportError, 'exited unsuccessfully'):
                        session._finish(time.monotonic() + 1)

    def test_exited_peer_truncation_requires_actual_stdout_eof(self):
        for packet in (b'', b'0000', b'00000010\nshort'):
            with self.subTest(packet=packet):
                session, _ = self.exchanged_pipe(packet)
                with self.assertRaisesRegex(CoreTransportError, 'incomplete frame'):
                    session._exchange(encode_document({'sequence': 1}), time.monotonic() + 1)
                self.assertIn('stdout', session._eof)
                self.assertEqual([item.direction for item in session.traffic], ['client'])

    def test_exited_peer_still_enforces_frame_and_stderr_bounds(self):
        for packet, error, message, note in (
                (b'0000000G\n', CoreProtocolError, 'Invalid callback frame header', b''),
                (b'00000002\n{}x', CoreProtocolError, 'Trailing or multiple', b''),
                (b'02000001\n', CoreProtocolError, 'frame byte limit', b''),
                (b'', CoreTransportError, 'stderr limit', b'bounded-note')):
            with self.subTest(message=message):
                session, _ = self.exchanged_pipe(packet, stderr=note)
                with patch.object(transport, 'MAX_STDERR_BYTES', 4), self.assertRaisesRegex(error, message):
                    session._exchange(encode_document({'sequence': 1}), time.monotonic() + 1)

    def test_exited_process_with_inherited_open_pipe_keeps_deadline(self):
        session, _ = self.exchanged_pipe(b'', keep_stdout_open=True)
        with self.assertRaisesRegex(CoreTimeout, 'exceeded its deadline'):
            session._exchange(encode_document({'sequence': 1}), time.monotonic() + .05)
        self.assertNotIn('stdout', session._eof)


PEER = r'''
import hashlib, json, os, subprocess, sys, time
assert sys.argv[1:] == ['--pipeline-callback-session-v1']
limits = DECLARATION['limits'].copy()
input_bytes = output_bytes = frames = commands = json_nodes = 0
next_sequence = next_event = 0
pending = []
state = []
session_id = None
def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
def nodes(value):
    if isinstance(value, dict):
        return 1 + len(value) + sum(nodes(item) for item in value.values())
    if isinstance(value, list):
        return 1 + sum(nodes(item) for item in value)
    return 1
def read_exact(size):
    result = bytearray()
    while len(result) < size:
        chunk = os.read(0, min(193, size - len(result)))
        if not chunk:
            sys.exit(0)
        result.extend(chunk)
    return bytes(result)
def read():
    global next_sequence, input_bytes, frames, commands, json_nodes
    header = read_exact(9)
    assert header[8] == 10 and all(value in b'0123456789abcdef' for value in header[:8])
    raw = read_exact(int(header[:8], 16))
    value = json.loads(raw)
    assert value['protocol'] == DECLARATION['protocol'] and value['profile'] == DECLARATION['profile']
    assert value['sequence'] == next_sequence
    assert set(value) == set(DECLARATION['client_fields'][value['kind']])
    if session_id is not None:
        assert value['session_id'] == session_id
    next_sequence += 1
    input_bytes += len(raw) + 9
    frames += 1
    json_nodes += nodes(value)
    if value['kind'] != 'continue':
        commands += 1
    return value, raw
def emit(kind, fields):
    global next_event, output_bytes, frames, json_nodes
    charged = DECLARATION['fixed_limits']['terminal_work'] + (frames + 1) * 1000
    value = {'protocol': DECLARATION['protocol'], 'profile': DECLARATION['profile'],
        'session_id': session_id, 'kind': kind, 'event_id': next_event, **fields,
        'usage': {'work_charged': charged, 'work_remaining': limits['max_work'] - charged,
            'input_bytes': input_bytes, 'output_bytes': 0, 'frames': frames + 1,
            'commands': commands, 'json_nodes': 0, 'pending_invocations': len(pending),
            'retained_bytes': input_bytes}}
    # BEFORE_EVENT
    value['usage']['json_nodes'] = json_nodes + nodes(value)
    while True:
        raw = encode(value)
        final_bytes = output_bytes + len(raw) + 9
        if value['usage']['output_bytes'] == final_bytes:
            break
        value['usage']['output_bytes'] = final_bytes
    # AFTER_EVENT
    packet = f'{len(raw):08x}\n'.encode() + raw
    # BEFORE_WRITE
    while packet:
        sent = os.write(1, packet[:37])
        packet = packet[sent:]
    next_event += 1
    output_bytes += len(raw) + 9
    frames += 1
    json_nodes += nodes(value)
    # AFTER_WRITE
    return value, raw
def reply(command, raw, outcome, closed=False):
    return emit('reply', {'sequence': command['sequence'], 'request_sha256': hashlib.sha256(raw).hexdigest(),
                          'outcome': outcome, 'closed': closed})
def invoke(command, raw):
    parent = pending[-1] if pending else None
    identity = next_event
    pending.append(identity)
    event, event_raw = emit('invoke', {'invocation_id': identity, 'parent_invocation': parent,
        'command_sequence': command['sequence'], 'command_sha256': hashlib.sha256(raw).hexdigest(),
        'action': command['arguments']['action'], 'arguments': command['arguments']['arguments']})
    while True:
        value, body = read()
        if value['kind'] == 'continue':
            assert value['invocation_id'] == identity
            assert value['invocation_sha256'] == hashlib.sha256(event_raw).hexdigest()
            assert set(value['outcome']) == set(DECLARATION['continuation_outcomes'][value['outcome']['status']])
            pending.pop()
            outcome = value['outcome']
            return {'status': 'ok', 'value': outcome['value']} if outcome['status'] == 'return' else outcome
        assert value['kind'] == 'command'
        dispatch(value, body)
def dispatch(value, raw):
    assert value['kind'] == 'command'
    assert value['parent_invocation'] == (pending[-1] if pending else None)
    operation = value['operation']
    if operation == 'call-host':
        outcome = invoke(value, raw)
    elif operation == 'reject':
        state.append(value['arguments'])
        outcome = {'status': 'rejected', 'value': {'state': state.copy()}}
    elif operation == 'append':
        state.append(value['arguments'])
        outcome = {'status': 'ok', 'value': state.copy()}
    elif operation == 'inspect':
        outcome = {'status': 'ok', 'value': state.copy()}
    else:
        outcome = {'status': 'ok', 'value': value['arguments']}
    # BEFORE_REPLY
    reply(value, raw, outcome)
hello, hello_raw = read()
session_id = hello['session_id']
assert hello['kind'] == 'hello' and hello['declaration'] == DECLARATION and hello['application'] == APPLICATION
if hello['limits'] is not None:
    limits = hello['limits']
reply(hello, hello_raw, {'status': 'ok', 'value': {'declaration': DECLARATION, 'application': APPLICATION, 'limits': limits}})
while True:
    value, raw = read()
    if value['kind'] == 'close':
        assert value['parent_invocation'] is None and not pending
        reply(value, raw, {'status': 'ok', 'value': None}, closed=True)
        sys.exit(0)
    dispatch(value, raw)
'''


@unittest.skipUnless(os.name == 'posix', 'Persistent callback transport targets POSIX')
class CallbackSessionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'peer'
        self.objects = CallbackObjects()
        self.addCleanup(self.objects.close)

    def core(self, *, before='', after='', before_write='', after_write='', before_reply='', **options):
        # This one malformed-output fixture requires the complete reply and its
        # suffix to be available together. Separate writes permit the parent to
        # finish the reply before the peer is scheduled to publish the suffix.
        # Keep the existing method, bytes and assertion; delayed output has a
        # separate FIFO-synchronized boundary test.
        if after_write == "if next_event == 2: os.write(1, b'unsolicited')":
            before_write += "\nif next_event == 1:\n    while len(packet) > 37:\n        sent = os.write(1, packet[:37])\n        packet = packet[sent:]\n    packet += b'unsolicited'\n    assert len(packet) <= os.fpathconf(1, 'PC_PIPE_BUF')\n    assert os.write(1, packet) == len(packet)\n    packet = b''"
            after_write = ''
        script = PEER
        for key, value in [('BEFORE_EVENT', before), ('AFTER_EVENT', after), ('BEFORE_WRITE', before_write),
                           ('AFTER_WRITE', after_write), ('BEFORE_REPLY', before_reply)]:
            script = script.replace('    # ' + key, '\n'.join('    ' + line for line in value.splitlines()))
        self.path.write_text(f'#!{sys.executable}\nDECLARATION = {capability_profile()!r}\nAPPLICATION = {APPLICATION!r}\n' + script)
        self.path.chmod(0o700)
        return CoreClient(self.path, timeout_seconds=options.pop('timeout_seconds', 2), **options)

    def session(self, core=None, **options):
        result = CorePipelineCallbackSession(self.core() if core is None else core,
            application=APPLICATION, objects=self.objects, **options)
        self.addCleanup(result.close)
        return result

    def call_host(self, session, function, context=None):
        self.objects.bind_provider('provider/' + str(id(function)), self.objects.retain(function))
        return session.call('call-host', {'action': 'call-provider', 'arguments': {
            'provider_id': 'provider/' + str(id(function)), 'context': self.objects.retain(context)}})

    def test_profile_exact_handshake_receipts_and_process_identity(self):
        profile = Path(__file__).parents[1] / 'protocol/pipeline-callback-channel-v1.json'
        self.assertEqual(encode_document(capability_profile()) + b'\n', profile.read_bytes())
        session = self.session()
        self.assertEqual(session.executable_sha256, hashlib.sha256(self.path.read_bytes()).hexdigest())
        result = session.call('echo', {'nested': [1, 2]})
        self.assertEqual(result.result, {'nested': [1, 2]})
        self.assertEqual(result.receipt['request_sha256'], hashlib.sha256(result.request_document).hexdigest())
        copied = result.result
        copied['nested'].append(3)
        self.assertEqual(result.result, {'nested': [1, 2]})
        with self.assertRaises(FrozenInstanceError):
            result.sequence = 7
        pid = session.pid
        closed = session.close()
        self.assertIsNone(closed.result)
        self.assertEqual(session.pid, pid)
        self.assertEqual(session.returncode, 0)
        self.assertTrue(session.closed)
        self.assertFalse(session.invalidated)
        self.assertIsNone(session.close())
        self.assertEqual([item.direction for item in session.traffic], ['client', 'server'] * 3)
        self.assertEqual([item.index for item in session.traffic], [0, 0, 1, 1, 2, 2])
        for item in session.traffic:
            self.assertEqual(int(item.frame[:8], 16), len(item.document))
        self.assertEqual(closed.usage['input_bytes'], sum(len(item.frame) for item in session.traffic if item.direction == 'client'))
        self.assertEqual(closed.usage['output_bytes'], sum(len(item.frame) for item in session.traffic if item.direction == 'server'))

    def test_nested_commands_continue_same_process_and_bind_original_request(self):
        session = self.session()
        pid = session.pid
        observed = []

        def inner(context):
            observed.append(('inner', context))
            session.call('append', 'nested mutation')
            return context

        def outer(context):
            observed.append(('outer', context))
            nested = self.call_host(session, inner, context)
            self.assertIs(self.objects.resolve(nested.result), context)
            return context

        context = object()
        result = self.call_host(session, outer, context)
        self.assertIs(self.objects.resolve(result.result), context)
        self.assertEqual(observed, [('outer', context), ('inner', context)])
        self.assertEqual(session.call('inspect', {}).result, ['nested mutation'])
        self.assertEqual(session.pid, pid)
        requests = [item.value for item in session.traffic if item.direction == 'client']
        events = [item.value for item in session.traffic if item.direction == 'server']
        self.assertEqual([item['sequence'] for item in requests], list(range(len(requests))))
        self.assertEqual([item['event_id'] for item in events], list(range(len(events))))
        self.assertEqual([item['sequence'] for item in events if item['kind'] == 'reply'][:4], [0, 3, 2, 1])
        self.assertEqual([item['parent_invocation'] for item in requests if item['kind'] == 'command'][:3], [None, 1, 2])
        self.assertEqual([item['usage']['pending_invocations'] for item in events][:6], [0, 1, 2, 2, 1, 0])

    def test_original_callback_exception_and_rejection_keep_native_state_usable(self):
        session = self.session()
        cause = RuntimeError('original cause')
        error = ValueError('callback error')

        def raising(context):
            session.call('append', 'before exception')
            raise error from cause

        caught = None
        try:
            self.call_host(session, raising)
        except ValueError as current:
            caught = current
        self.assertIs(caught, error)
        self.assertIs(error.__cause__, cause)
        self.assertIsNone(error.__context__)
        self.assertTrue(error.__suppress_context__)
        self.assertFalse(session.closed)
        with self.assertRaises(CallbackRejected) as rejection:
            session.call('reject', 'before rejection')
        self.assertEqual(rejection.exception.response.result, {'state': ['before exception', 'before rejection']})
        self.assertEqual(session.call('inspect', {}).result, ['before exception', 'before rejection'])

    def test_nested_host_error_can_be_caught_and_outer_continues(self):
        session = self.session()
        error = KeyboardInterrupt('original keyboard interrupt')

        def inner(context):
            raise error

        def outer(context):
            caught = None
            try:
                self.call_host(session, inner)
            except KeyboardInterrupt as current:
                caught = current
            self.assertIs(caught, error)
            session.call('append', 'resumed')
            return context

        context = object()
        self.assertIs(self.objects.resolve(self.call_host(session, outer, context).result), context)
        self.assertEqual(session.call('inspect', {}).result, ['resumed'])

    def test_close_inside_callback_rejected_locally_without_closing_authority(self):
        session = self.session()

        def callback(context):
            with self.assertRaisesRegex(CoreProtocolError, 'Cannot close'):
                session.close()
            return context

        self.call_host(session, callback)
        self.assertFalse(session.closed)

    def test_cancel_predicate_cannot_reenter_nested_command_io(self):
        session = self.session()
        rejected = []

        def predicate():
            before = len(session.traffic)
            with self.assertRaisesRegex(CoreProtocolError, 'currently executing host handler'):
                session.call('append', 'must never reach native state')
            self.assertEqual(len(session.traffic), before)
            rejected.append(True)
            return False

        def callback(context):
            session.call('append', 'legitimate nested command', cancelled=predicate)
            return context

        self.call_host(session, callback)
        self.assertTrue(rejected)
        self.assertEqual(session.call('inspect', {}).result, ['legitimate nested command'])
        self.assertFalse(session.invalidated)

    def test_hello_rejects_wrong_declaration_application_and_core_role(self):
        for field in ('declaration', 'application', 'limits'):
            with self.subTest(field=field):
                core = self.core(before=f"if next_event == 0: value['outcome']['value']['{field}'] = {{}}")
                with self.assertRaises(CoreProtocolError):
                    self.session(core)
        with self.assertRaises(CoreProtocolError):
            self.session(CoreClient(self.path, role='verify'))

    def test_invocation_identity_parent_hash_allowlist_and_census_are_enforced(self):
        corruptions = [
            "value['invocation_id'] += 1", "value['parent_invocation'] = 0",
            "value['command_sequence'] += 1", "value['command_sha256'] = '0'*64",
            "value['event_id'] += 1", "value['action'] = 'eval'", "value['usage']['pending_invocations'] = 0",
            "value['session_id'] = 'other'", "value['profile'] = 'other'",
        ]
        for mutation in corruptions:
            with self.subTest(mutation=mutation):
                session = self.session(self.core(before="if kind == 'invoke': " + mutation))
                called = []
                with self.assertRaises(CoreProtocolError):
                    self.call_host(session, lambda context: called.append(context))
                self.assertEqual(called, [])
                self.assertTrue(session.invalidated)
                self.assertIsNotNone(session.returncode)

    def test_reply_cannot_claim_foreign_exception_or_wrong_original_request(self):
        for change in ["outcome = {'status':'raise','token':'exception/0'}",
                       "value['sequence'] += 1", "raw = b'{}'"]:
            with self.subTest(change=change):
                session = self.session(self.core(before_reply=change))
                with self.assertRaises(CoreProtocolError):
                    session.call('echo', {})
                self.assertTrue(session.invalidated)

    def test_budget_counter_resets_and_field_mismatches_close_channel(self):
        corruptions = [
            "value['usage']['input_bytes'] += 1", "value['usage']['frames'] += 1",
            "value['usage']['commands'] += 1", "value['usage']['work_remaining'] += 1",
            "value['usage']['retained_bytes'] = 0", "value['extra'] = None",
            "value['closed'] = True", "value['outcome']['extra'] = 1",
        ]
        for mutation in corruptions:
            with self.subTest(mutation=mutation):
                session = self.session(self.core(before="if next_event == 1: " + mutation))
                with self.assertRaises(CoreProtocolError):
                    session.call('echo', {})
                self.assertTrue(session.invalidated)

    def test_partial_writes_large_frames_and_bounded_stderr(self):
        session = self.session(self.core(before_write="os.write(2, b'bounded-note')"))
        value = {'large': 'x' * 500_000}
        self.assertEqual(session.call('echo', value).result, value)
        self.assertIn(b'bounded-note', session.stderr_bytes)
        session.close()
        session = self.session(self.core(before_write="if next_event == 1: os.write(2, b'x' * 4096)"))
        with patch.object(transport, 'MAX_STDERR_BYTES', 128), self.assertRaises(CoreTransportError):
            session.call('echo', {})
        self.assertTrue(session.invalidated)

    def test_truncated_malformed_multiple_and_unsolicited_frames_are_terminal(self):
        packets = ["b'00000010\\nshort'", "b'0000000G\\n'", "b'00000000\\n'", "packet + packet", "packet[:-1]"]
        for packet in packets:
            with self.subTest(packet=packet):
                session = self.session(self.core(before_write=f"if next_event == 1:\n    os.write(1, {packet})\n    sys.exit(0)"))
                with self.assertRaises((CoreProtocolError, CoreTransportError)):
                    session.call('echo', {})
                self.assertTrue(session.invalidated)
        session = self.session(self.core(after_write="if next_event == 2: os.write(1, b'unsolicited')"))
        with self.assertRaises((CoreProtocolError, CoreTransportError)):
            session.call('echo', {})

    def test_timeout_and_cancellation_reap_without_retry(self):
        session = self.session(self.core(before_write="if next_event == 1: time.sleep(30)"))
        session._core = CoreClient(self.path, timeout_seconds=0.15)
        with self.assertRaises(CoreTimeout):
            session.call('echo', {})
        self.assertIsNotNone(session.returncode)
        with self.assertRaises(CoreProtocolError):
            session.call('echo', {})
        session = self.session()
        count = 0

        def cancelled():
            nonlocal count
            count += 1
            return True

        with self.assertRaises(CoreCancelled):
            session.call('echo', {}, cancelled=cancelled)
        self.assertTrue(session.invalidated)
        self.assertEqual(count, 1)

    def test_outer_deadline_survives_nested_calls(self):
        session = self.session()
        session._core = CoreClient(self.path, timeout_seconds=0.2)

        def slow(context):
            time.sleep(0.25)
            session.call('echo', {})

        with self.assertRaises((CoreTimeout, CoreProtocolError)):
            self.call_host(session, slow)
        self.assertTrue(session.invalidated)
        self.assertIsNotNone(session.returncode)

    def test_native_fatal_keeps_exact_terminal_receipt_and_invalidates(self):
        hook = """if next_event == 1:
    value['kind'] = 'fatal'
    value['closed'] = True
    value['code'] = 'pipeline_callback_fatal'
    del value['outcome']"""
        session = self.session(self.core(before=hook))
        with self.assertRaises(CallbackFatal) as failure:
            session.call('echo', {})
        self.assertEqual(failure.exception.document, session.traffic[-1].document)
        self.assertEqual(session.traffic[-1].value['kind'], 'fatal')
        self.assertTrue(session.invalidated)
        self.assertIsNotNone(session.returncode)
        excessive = hook + "\n    value['usage']['commands'] = 2**13000\n    value['usage']['retained_bytes'] = 2**13000"
        session = self.session(self.core(before=excessive))
        with self.assertRaisesRegex(CoreProtocolError, 'Malformed callback fatal'):
            session.call('echo', {})
        self.assertTrue(session.invalidated)

    def test_node_census_and_duplicate_keys_are_checked_before_callbacks(self):
        for mutation in [
            "value['usage']['json_nodes'] += 1; raw = encode(value)",
            "raw = raw[:-1] + b',\"kind\":\"invoke\"}'",
        ]:
            with self.subTest(mutation=mutation):
                session = self.session(self.core(after="if kind == 'invoke': " + mutation))
                called = []
                with self.assertRaises(CoreProtocolError):
                    self.call_host(session, lambda context: called.append(context))
                self.assertEqual(called, [])
                self.assertTrue(session.invalidated)

    def test_same_exception_object_can_be_raised_again_with_growing_traceback(self):
        session = self.session()
        error = ValueError('reused')

        def callback(context):
            raise error

        old_tail = None
        for _ in range(2):
            try:
                self.call_host(session, callback)
            except ValueError as caught:
                self.assertIs(caught, error)
            else:
                self.fail('Original exception was not raised')
            traceback = error.__traceback__
            if old_tail is not None:
                cursor = traceback
                while cursor is not None and cursor is not old_tail:
                    cursor = cursor.tb_next
                self.assertIs(cursor, old_tail)
            old_tail = traceback
        self.assertFalse(session.closed)

    def test_timeout_kills_descendants_that_hold_inherited_pipes(self):
        marker = Path(self.directory.name) / 'descendant-survived'
        pid_file = Path(self.directory.name) / 'descendant.pid'
        child = f'import time; time.sleep(1); open({str(marker)!r}, "w").write("alive"); time.sleep(30)'
        hook = f"""if next_event == 1:
    child = subprocess.Popen([sys.executable, '-c', {child!r}])
    open({str(pid_file)!r}, 'w').write(str(child.pid))
    time.sleep(30)"""
        session = self.session(self.core(before_write=hook))
        session._core = CoreClient(self.path, timeout_seconds=0.5)
        with self.assertRaises(CoreTimeout):
            session.call('echo', {})
        self.assertIsNotNone(session.returncode)
        self.assertGreater(int(pid_file.read_text()), 0)
        time.sleep(1)
        self.assertFalse(marker.exists())

    def test_close_requires_clean_exit_and_preserves_original_with_exception(self):
        session = self.session(self.core(after_write="if value.get('closed'): sys.exit(7)"))
        with self.assertRaises(CoreTransportError):
            session.close()
        self.assertTrue(session.invalidated)
        error = ValueError('original body failure')
        session = self.session(self.core(after_write="if value.get('closed'): sys.exit(7)"))
        caught = None
        try:
            with session:
                raise error
        except ValueError as current:
            caught = current
        self.assertIs(caught, error)
        self.assertTrue(session.invalidated)

    def test_reduced_cumulative_frames_commands_nodes_and_bytes(self):
        for key, ceiling, value in [('max_commands', 2, {}), ('max_frames', 5, {}),
                                     ('max_json_nodes', 2500, list(range(2400))),
                                     ('max_total_bytes', 25_000, 'x' * 20_000)]:
            with self.subTest(key=key):
                limits = capability_profile()['limits']
                limits[key] = ceiling
                session = self.session(limits=limits)
                if key in ('max_commands', 'max_frames'):
                    session.call('echo', {})
                with self.assertRaises(CoreProtocolError):
                    session.call('echo', value)
                self.assertTrue(session.invalidated)

    def test_v2_lifetime_crosses_old_ceiling_and_reduced_lifetime_still_closes(self):
        self.assertEqual(capability_profile()['profile'], 'biocompiler.core.pipeline_callback_channel.v2')
        self.assertEqual(capability_profile()['limits']['max_json_nodes'], 2_000_000)
        self.assertEqual(capability_profile()['fixed_limits']['max_frame_json_nodes'], 1_000_000)
        payload = [None] * 180_000
        for ceiling in (2_000_000, 1_000_000):
            with self.subTest(ceiling=ceiling):
                limits = capability_profile()['limits']
                limits['max_json_nodes'] = ceiling
                session = self.session(self.core(timeout_seconds=30), limits=limits)
                pid = session.pid
                totals = []
                for _ in range(2):
                    response = session.call('echo', payload)
                    self.assertEqual(response.result, payload)
                    totals.append(response.usage['json_nodes'])
                if ceiling == 2_000_000:
                    response = session.call('echo', payload)
                    self.assertEqual(response.result, payload)
                    totals.append(response.usage['json_nodes'])
                    self.assertGreater(totals[-1], 1_000_000)
                    self.assertEqual(totals, sorted(set(totals)))
                    self.assertEqual(session.pid, pid)
                    session.close()
                    self.assertFalse(session.invalidated)
                else:
                    with self.assertRaisesRegex(CoreProtocolError, 'document limits'):
                        session.call('echo', payload)
                    self.assertTrue(session.invalidated)
                    self.assertIsNotNone(session.returncode)
                    before = len(session.traffic)
                    with self.assertRaisesRegex(CoreProtocolError, 'cannot reconnect'):
                        session.call('echo', None)
                    self.assertEqual(len(session.traffic), before)

    def test_exact_and_one_short_lifetime_boundary_include_close_frames(self):
        limits = capability_profile()['limits']
        limits['max_json_nodes'] = 10_000
        probe = self.session(limits=limits)
        probe.call('echo', [None] * 200)
        exact = probe.close().usage['json_nodes']
        for ceiling in (exact, exact - 1):
            with self.subTest(ceiling=ceiling):
                limits = capability_profile()['limits']
                limits['max_json_nodes'] = ceiling
                session = self.session(limits=limits)
                response = session.call('echo', [None] * 200)
                self.assertLess(response.usage['json_nodes'], ceiling)
                if ceiling == exact:
                    self.assertEqual(session.close().usage['json_nodes'], ceiling)
                    self.assertFalse(session.invalidated)
                    self.assertEqual(session.returncode, 0)
                else:
                    with self.assertRaisesRegex(CoreProtocolError, 'document limits'):
                        session.close()
                    self.assertTrue(session.invalidated)
                    self.assertIsNotNone(session.returncode)

    def test_one_million_node_frame_cap_remains_separate_from_lifetime(self):
        session = self.session(self.core(before_reply="outcome = {'status':'ok','value':None}", timeout_seconds=30))
        skeleton = {'protocol': transport.PROTOCOL, 'profile': transport.PROFILE,
            'session_id': session._nonce, 'kind': 'command', 'sequence': 1,
            'parent_invocation': None, 'operation': 'echo', 'arguments': []}
        count = 1_000_000 - transport._nodes(skeleton)
        response = session.call('echo', [None] * count)
        self.assertEqual(transport._nodes(session.traffic[-2].value), 1_000_000)
        self.assertGreater(response.usage['json_nodes'], 1_000_000)
        before = len(session.traffic)
        with self.assertRaisesRegex(CoreProtocolError, 'node limit'):
            session.call('echo', [None] * (count + 1))
        self.assertEqual(len(session.traffic), before)
        self.assertFalse(session.invalidated)  # Local encoding rejected before any I/O.
        session.close()
        session = self.session(self.core(before_reply="outcome = {'status':'ok','value':[None]*1_000_000}",
            timeout_seconds=30))
        with self.assertRaisesRegex(CoreProtocolError, 'node limit'):
            session.call('echo', None)
        self.assertTrue(session.invalidated)
        self.assertIsNotNone(session.returncode)

    def test_old_resource_profile_and_declaration_rejected_before_application(self):
        old = capability_profile()
        old['profile'] = 'biocompiler.core.pipeline_callback_channel.v1'
        old['limits']['max_json_nodes'] = 1_000_000
        del old['fixed_limits']['max_frame_json_nodes']
        marker = Path(self.directory.name) / 'application-was-used'
        mutations = ["value['profile'] = 'biocompiler.core.pipeline_callback_channel.v1'",
            f"value['outcome']['value']['declaration'] = {old!r}"]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                core = self.core(before='if next_event == 0: ' + mutation,
                    before_reply=f"open({str(marker)!r}, 'w').write('used')")
                with self.assertRaises(CoreProtocolError):
                    self.session(core)
                self.assertFalse(marker.exists())

    def test_thread_process_and_binary_pin_checks(self):
        session = self.session()
        errors = []

        def call():
            try:
                session.call('echo', {})
            except CoreProtocolError as error:
                errors.append(error)

        worker = threading.Thread(target=call)
        worker.start()
        worker.join()
        self.assertEqual(len(errors), 1)
        with patch.object(transport.os, 'getpid', return_value=-1), self.assertRaises(CoreProtocolError):
            session.call('echo', {})
        self.assertFalse(session.closed)
        session.close()
        with self.assertRaises(CoreUnavailable):
            self.session(self.core(expected_sha256='0' * 64))
        with self.assertRaises(CoreCancelled):
            self.session(cancelled=lambda: True)


if __name__ == '__main__':
    unittest.main()
