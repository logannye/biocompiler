"""Persistent transport adversarial tests use real Python subprocesses only."""
from dataclasses import FrozenInstanceError
import hashlib
import gc
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from biocompiler.core_client import (
    CoreCancelled, CoreClient, CoreProtocolError, CoreTimeout, CoreTransportError,
    CoreUnavailable,
)
from biocompiler import core_pipeline_session as transport
from biocompiler.core_pipeline_session import (
    CorePipelineSession, SessionRejected, SessionUnsupported, capability_profile,
    decode_document, encode_document,
)


# This peer implements only transport observations, never compiler acceptance.
# A complete read is deliberately assembled from small chunks. The optional
# hooks corrupt individual protocol obligations independently of the client.
PEER = r'''
import hashlib, json, os, subprocess, sys, time
PROFILE = DECLARATION['profile']
limits = DECLARATION['limits'].copy()
manager_limits = DECLARATION['manager_limits'].copy()
inputs = outputs = commands = 0
dependencies = {}
def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
def read_exact(size):
    data = bytearray()
    while len(data) < size:
        chunk = os.read(0, min(257, size - len(data)))
        if not chunk:
            sys.exit(0)
        data.extend(chunk)
    return bytes(data)
assert sys.argv[1:] == ['--pipeline-session-v1']
while True:
    header = read_exact(9)
    body = read_exact(int(header[:8], 16))
    request = json.loads(body)
    inputs += len(body) + 9
    commands += 1
    operation, payload = request['operation'], request['payload']
    if operation == 'hello':
        if payload['limits'] is not None:
            limits = payload['limits']
        if payload['manager_limits'] is not None:
            manager_limits = payload['manager_limits']
        result = {'profile': DECLARATION, 'limits': limits, 'manager_limits': manager_limits}
    elif operation.startswith('initialize-'):
        kind = operation[len('initialize-'):]
        result = {'kind': kind, 'manager': True, 'artifacts': DECLARATION['artifacts'].get(kind, [])}
    elif operation == 'target':
        result = {'schema_version': 'biocompiler.target.v0.1', 'observed_payload': payload, 'pid': os.getpid()}
    elif operation == 'set-dependency':
        dependencies[payload['key']] = payload['identity']
        result = None
    elif operation == 'inspect':
        result = dict.fromkeys(['target', 'dependencies', 'passes', 'component_inputs',
            'provider_history', 'component_input_history', 'records', 'profiles'], {})
        result['dependencies'] = dependencies.copy()
    else:
        result = None
    charged = DECLARATION['fixed_limits']['terminal_reserve_work'] + commands * 1000
    response = {
        'protocol': DECLARATION['protocol'], 'profile': PROFILE,
        'session_id': request['session_id'], 'sequence': request['sequence'],
        'operation': operation, 'request_sha256': hashlib.sha256(body).hexdigest(),
        'status': 'ok', 'closed': operation == 'close', 'result': result,
        'diagnostics': [], 'exception': None,
        'usage': {'work_charged': charged, 'work_remaining': limits['max_work'] - charged,
            'input_bytes': inputs, 'output_bytes': 0, 'commands': commands,
            'retained_bytes': commands * 10},
        'core': {'implementation': 'ocaml', 'version': '0.1.0',
            'protocol': 'biocompiler.core.v1', 'executable': 'core'}}
    # BEFORE_RESPONSE
    while True:
        raw = encode(response)
        census = outputs + len(raw) + 9
        if response['usage']['output_bytes'] == census:
            break
        response['usage']['output_bytes'] = census
    # AFTER_RESPONSE
    packet = f'{len(raw):08x}\n'.encode() + raw
    # BEFORE_WRITE
    while packet:
        count = os.write(1, packet[:31])
        packet = packet[count:]
    outputs += len(raw) + 9
    # AFTER_WRITE
    if response['closed']:
        sys.exit(0)
'''


class SessionCodecTests(unittest.TestCase):
    def test_profile_matches_frozen_protocol_and_is_not_caller_mutable(self):
        declaration = Path(__file__).parents[1] / 'protocol/pipeline-session-v1.json'
        self.assertEqual(encode_document(capability_profile()) + b'\n', declaration.read_bytes())
        profile = capability_profile()
        profile['limits']['max_json_nodes'] = 1
        self.assertEqual(capability_profile()['limits']['max_json_nodes'], 1_000_000)

    def test_numeric_unicode_and_key_count_roundtrip(self):
        value = {'é': [-0.0, True, 2**200, 1e-7], '😀': 'é'}
        encoded = encode_document(value)
        self.assertEqual(encoded, json.dumps(value, sort_keys=True, separators=(',', ':'),
                                            ensure_ascii=False).encode())
        self.assertEqual(encode_document(decode_document(encoded)), encoded)
        # Root + key + value: object keys are nodes too.
        self.assertEqual(decode_document(b'{"x":1}', max_nodes=3), {'x': 1})
        for action in (lambda: encode_document({'x': 1}, max_nodes=2),
                       lambda: decode_document(b'{"x":1}', max_nodes=2)):
            with self.assertRaises(CoreProtocolError):
                action()

    def test_session_supports_more_than_stateless_node_limit(self):
        value = [None] * 250_001
        self.assertEqual(decode_document(encode_document(value)), value)
        with self.assertRaises(CoreProtocolError):
            decode_document(b'[' + b'0,' * 499_999 + b'0]', max_nodes=500_000)

    def test_malformed_ambiguous_and_non_scalar_json(self):
        for raw in (b'{"x":1,"x":2}', b'NaN', b'Infinity', b'1e999', b'"\xff"',
                    b'"\\ud800"', b'{} {}', b'\xef\xbb\xbf{}', b'01', b'', b'[{]}',
                    b'"\\"', b'null garbage', b'10000'):
            with self.subTest(raw=raw), patch.dict(transport._FIXED, max_number_chars=4), self.assertRaises(CoreProtocolError):
                decode_document(raw)
        for value in ({1: 'key'}, (1, 2), object(), float('inf'), float('nan'), '\ud800'):
            with self.subTest(kind=type(value)), self.assertRaises(CoreProtocolError):
                encode_document(value)

    def test_exact_depth_string_number_bytes_and_cycles(self):
        with patch.dict(transport._FIXED, max_depth=2, max_string_bytes=4, max_number_chars=4):
            for value in ([[[0]]], 'ééé', 10000, {'ééé': 1}):
                with self.subTest(value=value), self.assertRaises(CoreProtocolError):
                    encode_document(value)
                with self.subTest(raw=value), self.assertRaises(CoreProtocolError):
                    decode_document(json.dumps(value).encode())
            self.assertEqual(decode_document(encode_document([['éé']])), [['éé']])
        cycle = []
        cycle.append(cycle)
        with self.assertRaises(CoreProtocolError):
            encode_document(cycle)
        for value in (['x' * 1000] * 1000, ['\x00' * 100]):
            with self.assertRaises(CoreProtocolError):
                encode_document(value, max_bytes=500)
        with self.assertRaises(CoreProtocolError):
            decode_document(b'{}', max_bytes=1)
        previous = sys.get_int_max_str_digits()
        try:
            sys.set_int_max_str_digits(0)
            with self.assertRaises(CoreProtocolError):
                encode_document(1 << 1_000_000)
        finally:
            sys.set_int_max_str_digits(previous)


@unittest.skipUnless(os.name == 'posix', 'Persistent native transport targets POSIX')
class SessionProcessTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'peer'

    def client(self, *, before='', after='', before_write='', after_write='', **options):
        script = 'DECLARATION = ' + repr(capability_profile()) + '\n' + PEER
        for name, code in (('BEFORE_RESPONSE', before), ('AFTER_RESPONSE', after),
                           ('BEFORE_WRITE', before_write), ('AFTER_WRITE', after_write)):
            script = script.replace('    # ' + name, '\n'.join('    ' + line for line in code.splitlines()))
        self.path.write_text(f'#!{sys.executable}\n' + script)
        self.path.chmod(0o700)
        return CoreClient(self.path, **options)

    def session(self, **options):
        session = CorePipelineSession(self.client(**options))
        self.addCleanup(session.close)
        return session

    def assert_dead(self, session):
        self.assertTrue(session.closed)
        self.assertTrue(session.invalidated)
        self.assertIsNotNone(session.returncode)
        with self.assertRaises(CoreProtocolError):
            session.call('target', {})

    def test_live_process_identity_exact_frames_and_immutable_receipts(self):
        self.client()
        pin = hashlib.sha256(self.path.read_bytes()).hexdigest()
        with CorePipelineSession(CoreClient(self.path, expected_sha256=pin)) as session:
            self.assertEqual(session.executable_sha256, pin)
            hello = session.hello_response
            initial = session.call('initialize-empty', {'target': {}, 'dependencies': [], 'completion_profiles': []})
            mutation = session.call('set-dependency', {'key': 'reference', 'identity': 'v2'})
            state = session.call('inspect', {})
            target = session.call('target', {'unicode': 'é', 'large': 'x' * 200_000})
            self.assertEqual(target.result['pid'], session.pid)
            self.assertIsNone(session.returncode)
            self.assertEqual(state.result['dependencies'], {'reference': 'v2'})
            self.assertEqual([reply.sequence for reply in (hello, initial, mutation, state, target)], list(range(5)))
            self.assertEqual(target.usage['input_bytes'], sum(len(reply.request_frame) for reply in (hello, initial, mutation, state, target)))
            self.assertEqual(target.usage['output_bytes'], sum(len(reply.response_frame) for reply in (hello, initial, mutation, state, target)))
            self.assertEqual(target.receipt['request_sha256'], hashlib.sha256(target.request_document).hexdigest())
            self.assertEqual(int(target.response_frame[:8], 16), len(target.response_document))
            state.result['dependencies']['reference'] = 'forged'
            self.assertEqual(state.result['dependencies'], {'reference': 'v2'})
            target.usage['commands'] = -1
            self.assertEqual(target.usage['commands'], 5)
            with self.assertRaises(FrozenInstanceError):
                target.sequence = 99
            self.assertEqual(session.last_response, target)
        self.assertTrue(session.closed)
        self.assertFalse(session.invalidated)
        self.assertEqual(session.returncode, 0)
        self.assertIsNone(session.close())

    def test_human_target_schema_is_preserved(self):
        with self.session(before="if operation == 'target':\n    response['result']['schema_version'] = 'biocompiler.human_target_context.v0.1'\n    response['result']['human_target'] = {'declaration': 'preserved'}") as session:
            target = session.call('target', {}).result
            self.assertEqual(target['schema_version'], 'biocompiler.human_target_context.v0.1')
            self.assertEqual(target['human_target'], {'declaration': 'preserved'})

    def test_expected_errors_preserve_mutations_and_advance_sequence(self):
        hook = """if operation == 'set-dependency':
    response.update(status='error', result=None,
        diagnostics=[{'code':'pipeline_error','message':'after mutation','path':None}],
        exception={'module':'biocompiler.compiler.pipeline','type':'PipelineError','message':'after mutation','attributes':{}})
elif operation == 'unknown':
    response.update(status='unsupported', result=None,
        diagnostics=[{'code':'unsupported','message':'unsupported operation','path':None}])"""
        with self.session(before=hook) as session:
            with self.assertRaises(SessionRejected) as rejected:
                session.call('set-dependency', {'key': 'changed', 'identity': 'retained'})
            self.assertFalse(rejected.exception.response.closed)
            self.assertEqual(rejected.exception.response.exception['type'], 'PipelineError')
            self.assertEqual(session.call('inspect', {}).result['dependencies'], {'changed': 'retained'})
            with self.assertRaises(SessionUnsupported) as unsupported:
                session.call('unknown', {})
            self.assertEqual(unsupported.exception.response.sequence, 3)
            self.assertEqual(session.call('target', {}).sequence, 4)

    def test_valid_terminal_rejection_closes_and_reaps(self):
        hook = """if operation == 'target':
    response.update(status='error', closed=True, result=None,
        diagnostics=[{'code':'pipeline_session_fatal','message':'Resource exhausted','path':None}])"""
        session = self.session(before=hook)
        with self.assertRaises(SessionRejected) as caught:
            session.call('target', {})
        self.assertTrue(caught.exception.response.closed)
        self.assert_dead(session)

    def test_reserved_terminal_frame_can_exceed_reduced_normal_ceiling(self):
        limits = capability_profile()['limits']
        limits['max_frame_bytes'] = 6000
        hook = """if operation == 'target':
    response.update(status='error', closed=True, result=None,
        diagnostics=[{'code':'pipeline_session_fatal','message':'x' * 6100,'path':None}])"""
        session = CorePipelineSession(self.client(before=hook), limits=limits)
        self.addCleanup(session.close)
        with self.assertRaises(SessionRejected) as caught:
            session.call('target', {})
        self.assertGreater(len(caught.exception.response.response_document), 6000)
        self.assertLessEqual(len(caught.exception.response.response_frame), 8192)
        self.assert_dead(session)

    def test_terminal_reserve_includes_its_frame_header(self):
        before = """if operation == 'target':
    response.update(status='error', closed=True, result=None,
        diagnostics=[{'code':'pipeline_session_fatal','message':'x','path':None}])"""
        after = """if operation == 'target':
    # Craft exactly 8192 body bytes, exceeding the total reservation by 9.
    response['diagnostics'][0]['message'] += 'x' * (8192 - len(raw))
    raw = encode(response)
    assert len(raw) == 8192"""
        session = self.session(before=before, after=after)
        with self.assertRaisesRegex(CoreProtocolError, 'reserved capacity'):
            session.call('target', {})
        self.assert_dead(session)

    def test_partial_writes_are_completed_without_restarting_process(self):
        with self.session() as session:
            real_write = os.write
            written = []
            def partial_write(fd, data):
                count = real_write(fd, data[:127])
                written.append(count)
                return count
            with patch.object(transport.os, 'write', side_effect=partial_write):
                response = session.call('target', {'message': 'x' * 20_000})
            self.assertGreater(len(written), 100)
            self.assertEqual(sum(written), len(response.request_frame))
            self.assertEqual(response.result['pid'], session.pid)

    def test_output_byte_census_is_exact(self):
        session = self.session(after="if operation == 'target':\n    response['usage']['output_bytes'] -= 1\n    raw = encode(response)")
        with self.assertRaisesRegex(CoreProtocolError, 'wire census'):
            session.call('target', {})
        self.assert_dead(session)

    def test_response_binding_and_shapes_reject_and_reap(self):
        mutations = (
            "response['session_id'] = 'another-session'", "response['sequence'] = True",
            "response['sequence'] += 1", "response['operation'] = 'inspect'",
            "response['request_sha256'] = '0' * 64", "response['protocol'] = 'old'",
            "response['profile'] = 'old'", "response['core']['implementation'] = 'python'",
            "response['core']['executable'] = 'verify'", "response['core']['version'] = 'other'",
            "response['status'] = []", "response['closed'] = 1", "response['extra'] = None",
            "response['diagnostics'] = {}", "response['exception'] = {}",
            "response['diagnostics'] = [{'code':'bad','message':'bad','path':None}]",
            "response['status'] = 'error'", "response['closed'] = True",
            "response['result'] = None", "response['usage']['commands'] = True",
            "response['usage']['commands'] -= 1", "response['usage']['input_bytes'] -= 1",
            "response['usage']['work_remaining'] += 1", "response['usage']['retained_bytes'] = 0",
        )
        for change in mutations:
            with self.subTest(change=change):
                session = self.session(before="if operation == 'target':\n    " + change)
                with self.assertRaises(CoreProtocolError):
                    session.call('target', {})
                self.assert_dead(session)

    def test_profile_and_reduction_negotiation_are_exact(self):
        limits = capability_profile()['limits']
        limits['max_work'] //= 2
        manager_limits = capability_profile()['manager_limits']
        manager_limits['max_records'] = 2
        with CorePipelineSession(self.client(), limits=limits, manager_limits=manager_limits) as session:
            self.assertEqual(session.hello_response.result['limits'], limits)
            self.assertEqual(session.hello_response.result['manager_limits'], manager_limits)
            limits['max_work'] = 1
            self.assertNotEqual(session.hello_response.result['limits'], limits)
        for hook in ("response['result']['profile'] = PROFILE",
                     "response['result']['profile']['limits']['max_json_nodes'] -= 1",
                     "response['result']['limits']['max_frame_bytes'] = True",
                     "response['result']['manager_limits']['max_records'] -= 1"):
            with self.subTest(hook=hook), self.assertRaises(CoreProtocolError):
                CorePipelineSession(self.client(before="if operation == 'hello':\n    " + hook))
        for reduction in ({}, {'max_work': 5}, dict(capability_profile()['limits'], max_work=True),
                          dict(capability_profile()['limits'], max_work=0),
                          dict(capability_profile()['limits'], max_work=10**15)):
            with self.subTest(reduction=reduction), patch.object(transport.subprocess, 'Popen') as start:
                with self.assertRaises(CoreProtocolError):
                    CorePipelineSession(self.client(), limits=reduction)
                start.assert_not_called()

    def test_bad_frames_partial_exit_and_output_floods(self):
        cases = (
            ("packet = b'0000000A\\n' + b'{}'", CoreProtocolError),
            ("packet = b'00000000\\n'", CoreProtocolError),
            ("packet = b'ffffffff\\n'", CoreProtocolError),
            ("packet = b'00000002!' + b'{}'", CoreProtocolError),
            ("packet = b'00000003\\n' + b'{x}'", CoreProtocolError),
            ("packet += packet", CoreProtocolError),
            ("os.write(1, b'00000020\\n{}'); sys.exit(9)", CoreTransportError),
            ("os.write(2, b'x' * 1_100_000)", CoreTransportError),
        )
        for action, error in cases:
            with self.subTest(action=action):
                session = self.session(before_write="if operation == 'target':\n    " + action)
                with self.assertRaises(error):
                    session.call('target', {})
                self.assert_dead(session)

    def test_lifetime_usage_cannot_reset(self):
        mutations = (
            "response['usage']['work_charged'] -= 2000; response['usage']['work_remaining'] += 2000",
            "response['usage']['retained_bytes'] = 0",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                session = self.session(before="if operation == 'target':\n    " + mutation)
                session.call('inspect', {})
                with self.assertRaises(CoreProtocolError):
                    session.call('target', {})
                self.assert_dead(session)

    def test_cumulative_stderr_and_aggregate_wire_limits(self):
        session = self.session(before="if operation == 'target':\n    os.write(2, b'x' * 600_000)")
        session.call('target', {})
        with self.assertRaises(CoreTransportError):
            session.call('target', {})
        self.assert_dead(session)
        limits = capability_profile()['limits']
        limits['max_total_bytes'] = 20_000
        session = CorePipelineSession(self.client(), limits=limits)
        self.addCleanup(session.close)
        with self.assertRaises(CoreTransportError):
            session.call('target', {'large': 'x' * 20_000})
        self.assert_dead(session)

    def test_normal_response_must_obey_reduced_frame_ceiling(self):
        limits = capability_profile()['limits']
        limits['max_frame_bytes'] = 6000
        session = CorePipelineSession(self.client(before="if operation == 'target':\n    response['result']['large'] = 'x' * 6100"), limits=limits)
        self.addCleanup(session.close)
        with self.assertRaises(CoreProtocolError):
            session.call('target', {})
        self.assert_dead(session)

    def test_unsolicited_output_and_unannounced_process_loss(self):
        session = self.session(after_write="if operation == 'target':\n    os.write(1, b'x')")
        with self.assertRaises(CoreProtocolError):
            session.call('target', {})
            time.sleep(0.02)
            session.call('target', {})
        self.assert_dead(session)
        session = self.session()
        os.kill(session.pid, signal.SIGKILL)
        session._process.wait()
        with self.assertRaises(CoreTransportError):
            session.call('target', {})
        self.assert_dead(session)

    def test_timeout_cancellation_and_keyboard_interrupt_invalidate(self):
        session = self.session(before="if operation == 'target':\n    time.sleep(30)", timeout_seconds=0.5)
        with self.assertRaises(CoreTimeout):
            session.call('target', {})
        self.assert_dead(session)
        for interrupt in (lambda: True, lambda: (_ for _ in ()).throw(KeyboardInterrupt())):
            session = self.session()
            with self.assertRaises((CoreCancelled, KeyboardInterrupt)):
                session.call('target', {}, cancelled=interrupt)
            self.assert_dead(session)
        with patch.object(transport.subprocess, 'Popen') as start, self.assertRaises(CoreCancelled):
            CorePipelineSession(self.client(), cancelled=lambda: True)
        start.assert_not_called()

    def test_timeout_kills_process_group_with_inherited_pipes(self):
        descendant = Path(self.directory.name) / 'descendant.pid'
        alive = Path(self.directory.name) / 'descendant-survived'
        child_code = f'import time; time.sleep(1); open({str(alive)!r}, "w").write("alive"); time.sleep(30)'
        hook = f"""if operation == 'target':
    child = subprocess.Popen([sys.executable, '-c', {child_code!r}])
    open({str(descendant)!r}, 'w').write(str(child.pid))
    time.sleep(30)"""
        session = self.session(before=hook, timeout_seconds=0.5)
        started = time.monotonic()
        with self.assertRaises(CoreTimeout):
            session.call('target', {})
        self.assertLess(time.monotonic() - started, 2)
        self.assert_dead(session)
        self.assertGreater(int(descendant.read_text()), 0)
        # A still-running descendant would write this marker. Unlike ps/kill(0),
        # the assertion works under process-inspection sandboxing and does not
        # confuse a killed process awaiting its system reaper with live code.
        time.sleep(1)
        self.assertFalse(alive.exists())

    def test_close_requires_clean_exit_and_context_preserves_original_error(self):
        for hook in ("if operation == 'close':\n    sys.exit(8)",
                     "if operation == 'close':\n    os.write(1, b'trailing')"):
            session = self.session(after_write=hook)
            with self.assertRaises((CoreProtocolError, CoreTransportError)):
                session.close()
            self.assert_dead(session)
        session = self.session(before="if operation == 'close':\n    time.sleep(30)", timeout_seconds=0.5)
        with self.assertRaisesRegex(ValueError, 'original'):
            with session:
                raise ValueError('original')
        self.assert_dead(session)

    def test_local_errors_owner_and_reentrant_guards_do_not_send(self):
        with self.session() as session:
            for operation, payload in (('hello', {}), ('close', {}), ('', {}), ('target', object())):
                with self.subTest(operation=operation), self.assertRaises(CoreProtocolError):
                    session.call(operation, payload)
            errors = []
            def wrong_thread():
                try:
                    session.call('target', {})
                except CoreProtocolError as error:
                    errors.append(error)
            thread = threading.Thread(target=wrong_thread)
            thread.start()
            thread.join()
            self.assertEqual(len(errors), 1)
            session._active = True
            try:
                with self.assertRaises(CoreProtocolError):
                    session.call('target', {})
            finally:
                session._active = False
            self.assertEqual(session.call('target', {}).sequence, 1)

    def test_forked_finalizer_cannot_terminate_parent_session(self):
        session = self.session()
        child = os.fork()
        if child == 0:
            try:
                try:
                    session.call('target', {})
                except CoreProtocolError:
                    pass
                else:
                    os._exit(1)
                # Simulate the inherited finalizer running during child exit.
                session._finalizer()
                os._exit(0)
            except BaseException:
                os._exit(2)
        _, status = os.waitpid(child, 0)
        self.assertEqual(os.waitstatus_to_exitcode(status), 0)
        self.assertEqual(session.call('target', {}).result['pid'], session.pid)

    def test_collection_and_failed_handshake_reap_actual_children(self):
        session = CorePipelineSession(self.client())
        process = session._process
        del session
        gc.collect()
        self.assertIsNotNone(process.poll())
        original_start = transport.subprocess.Popen
        children = []
        def observe_start(*args, **kwargs):
            process = original_start(*args, **kwargs)
            children.append(process)
            return process
        client = self.client(before="if operation == 'hello':\n    response['profile'] = 'wrong'")
        with patch.object(transport.subprocess, 'Popen', side_effect=observe_start):
            with self.assertRaises(CoreProtocolError):
                CorePipelineSession(client)
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].poll())

    def test_explicit_core_binary_pin_is_checked_before_start(self):
        with patch.object(transport.subprocess, 'Popen') as start:
            for client, error in ((CoreClient(self.path.parent / 'missing'), CoreUnavailable),
                                  (self.client(role='verify'), CoreProtocolError),
                                  (self.client(expected_sha256='0'*64), CoreUnavailable)):
                with self.subTest(error=error), self.assertRaises(error):
                    CorePipelineSession(client)
            start.assert_not_called()


if __name__ == '__main__':
    unittest.main()
