"""Deterministic inert-peer ordering controls; no native acceptance."""
import ast
import hashlib
import os
from pathlib import Path
import select
from types import SimpleNamespace
import unittest

from biocompiler.core_client import CoreProtocolError
from tests import test_core_pipeline_callback_session as fixtures


ORIGINAL_TEST_SHA256 = '8c8fc56b844d436ceb6a5d93565f3cbbefa951c2486890053c7234ae970db8fd'
# Exact additive fixture span; removing it restores the complete prior test source.
FIXTURE_ADDITION = b'        # This one malformed-output fixture requires the complete reply and its\n        # suffix to be available together. Separate writes permit the parent to\n        # finish the reply before the peer is scheduled to publish the suffix.\n        # Keep the existing method, bytes and assertion; delayed output has a\n        # separate FIFO-synchronized boundary test.\n        if after_write == "if next_event == 2: os.write(1, b\'unsolicited\')":\n            before_write += "\\nif next_event == 1:\\n    while len(packet) > 37:\\n        sent = os.write(1, packet[:37])\\n        packet = packet[sent:]\\n    packet += b\'unsolicited\'\\n    assert len(packet) <= os.fpathconf(1, \'PC_PIPE_BUF\')\\n    assert os.write(1, packet) == len(packet)\\n    packet = b\'\'"\n            after_write = \'\'\n'


def delayed_suffix_hook(ready: Path, release: Path) -> str:
    """Acknowledge reply completion, wait for the caller, then publish the suffix."""
    return f"""if next_event == 2:
    with open({str(ready)!r}, 'wb', buffering=0) as signal:
        assert signal.write(b'R') == 1
    with open({str(release)!r}, 'rb', buffering=0) as gate:
        assert gate.read(1) == b'!'
    assert os.write(1, b'unsolicited') == len(b'unsolicited')
    with open({str(ready)!r}, 'wb', buffering=0) as signal:
        assert signal.write(b'U') == 1"""


def fifo(directory: Path, name: str) -> tuple[Path, int]:
    path = directory / name
    os.mkfifo(path, 0o600)
    return path, os.open(path, os.O_RDWR | os.O_NONBLOCK)


def receive(fd: int, expected: bytes) -> None:
    if select.select([fd], [], [], 2)[0] != [fd] or os.read(fd, 1) != expected:
        raise AssertionError('Inert peer did not reach its exact FIFO barrier')


@unittest.skipUnless(os.name == 'posix', 'Callback transport targets POSIX')
class CallbackUnsolicitedOrderingTests(unittest.TestCase):
    def fixture(self):
        value = fixtures.CallbackSessionTests()
        value.setUp()
        self.addCleanup(value.doCleanups)
        return value

    def test_only_additive_fixture_span_restores_complete_original_source(self):
        raw = Path(fixtures.__file__).read_bytes()
        self.assertEqual(raw.count(FIXTURE_ADDITION), 1)
        restored = raw.replace(FIXTURE_ADDITION, b'', 1)
        self.assertEqual(hashlib.sha256(restored).hexdigest(), ORIGINAL_TEST_SHA256)
        old = ast.parse(restored)
        new = ast.parse(raw)
        def methods(tree):
            return {(group.name, method.name): ast.dump(method, include_attributes=False)
                    for group in tree.body if isinstance(group, ast.ClassDef)
                    for method in group.body if isinstance(method, ast.FunctionDef)}
        original, current = methods(old), methods(new)
        self.assertEqual(set(original), set(current))
        for name in original:
            if name != ('CallbackSessionTests', 'core'):
                self.assertEqual(current[name], original[name], name)
        self.assertEqual(fixtures.PEER, next(node.value.value for node in old.body
                         if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
                         and target.id == 'PEER' for target in node.targets)))

    def test_atomic_tail_preserves_every_frame_byte_and_fragmented_prefix(self):
        fixture = self.fixture()
        fixture.core(after_write="if next_event == 2: os.write(1, b'unsolicited')")
        tree = ast.parse(fixture.path.read_text())
        emit = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'emit')
        hooks = [node for node in emit.body if isinstance(node, ast.If) and ast.unparse(node.test) == 'next_event == 1']
        self.assertEqual(len(hooks), 1)
        code = compile(ast.Module(body=hooks, type_ignores=[]), '<atomic-fixture-tail>', 'exec')
        for size in (1, 37, 38, 74, 75, 1024):
            with self.subTest(size=size):
                packet = b'p' * size
                writes = []
                def write(fd, body):
                    self.assertEqual(fd, 1)
                    writes.append(body)
                    return len(body)
                environment = {'next_event': 1, 'packet': packet,
                    'os': SimpleNamespace(write=write, fpathconf=lambda fd, key: 512)}
                exec(code, environment)
                self.assertEqual(b''.join(writes), packet + b'unsolicited')
                self.assertTrue(all(len(body) == 37 for body in writes[:-1]))
                self.assertTrue(writes[-1].endswith(b'unsolicited'))
                self.assertLessEqual(len(writes[-1]), 48)
                self.assertEqual(environment['packet'], b'')
        environment = {'next_event': 0, 'packet': b'original', 'os': None}
        exec(code, environment)
        self.assertEqual(environment['packet'], b'original')
        environment = {'next_event': 1, 'packet': b'p',
            'os': SimpleNamespace(write=lambda fd, body: len(body) - 1, fpathconf=lambda fd, key: 512)}
        with self.assertRaises(AssertionError):
            exec(code, environment)

    def test_later_suffix_is_terminal_before_next_call_or_close(self):
        for operation in ('call', 'close'):
            with self.subTest(operation=operation):
                fixture = self.fixture()
                ready_path, ready = fifo(Path(fixture.directory.name), 'ready')
                release_path, release = fifo(Path(fixture.directory.name), 'release')
                self.addCleanup(os.close, ready)
                self.addCleanup(os.close, release)
                session = fixture.session(fixture.core(after_write=delayed_suffix_hook(ready_path, release_path)))
                self.addCleanup(session._invalidate)
                # The peer cannot publish the suffix until this complete call
                # has returned and the caller explicitly releases the FIFO.
                self.assertEqual(session.call('echo', {}).result, {})
                receive(ready, b'R')
                self.assertFalse(session.invalidated)
                before = session.traffic
                self.assertEqual(os.write(release, b'!'), 1)
                receive(ready, b'U')
                with self.assertRaisesRegex(CoreProtocolError, 'Unsolicited or trailing'):
                    if operation == 'call':
                        session.call('echo', {})
                    else:
                        session.close()
                self.assertTrue(session.invalidated)
                self.assertTrue(session.closed)
                self.assertIsNotNone(session.returncode)
                self.assertEqual(session.traffic, before)
