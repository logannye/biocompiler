"""Real Python subprocess peers test transport only, never native acceptance."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
from biocompiler import core_package_files as files
from biocompiler import core_pipeline_callback_session as transport
from biocompiler.core_client import CoreClient, CoreError, CoreProtocolError
from biocompiler.pipeline_callback_objects import CallbackObjects
from tests.test_core_pipeline_callback_session import PEER, APPLICATION


class PackageCallbackTransportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.objects = CallbackObjects()
        self.addCleanup(self.objects.close)

    def client(self, extra='', before_reply='', declaration=None):
        declaration = declaration or transport.package_capability_profile()
        script = PEER.replace("assert sys.argv[1:] == ['--pipeline-callback-session-v1']", '''assert len(sys.argv) == 4 and sys.argv[1] == '--reference-package-fds-v1'
input_fd = None if sys.argv[2] == '-' else int(sys.argv[2])
output_fd = int(sys.argv[3])
assert os.fstat(output_fd).st_size == 0''')
        script = script.replace("if operation == 'call-host':", '''if operation == 'write-output':
        data = bytes.fromhex(value['arguments'])
        os.write(output_fd, data)
        outcome = {'status': 'ok', 'value': {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}}
    elif operation == 'read-input':
        assert input_fd is not None
        size = os.fstat(input_fd).st_size
        data = os.read(input_fd, size + 1)
        assert len(data) == size
        outcome = {'status': 'ok', 'value': data.hex()}
    elif operation == 'call-host':''')
        script = script.replace('# BEFORE_REPLY', before_reply)
        path = Path(self.directory.name) / 'python-protocol-peer'
        path.write_text('#!' + sys.executable + '\nDECLARATION = ' + repr(declaration)
            + '\nAPPLICATION = ' + repr(APPLICATION) + '\n' + extra + '\n' + script)
        path.chmod(0o700)
        return CoreClient(path, timeout_seconds=3,
            expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest())

    def test_complete_fd_bytes_with_exact_profile_and_reaped_process(self):
        data = b'PK\x00\xff\r\n' * 100
        with files.PackageFiles(data) as owned:
            session = transport.CorePipelineCallbackSession(self.client(), application=APPLICATION,
                objects=self.objects, _package_files=owned)
            self.addCleanup(session.close)
            self.assertEqual(session.hello_response.result['declaration']['profile'],
                             'biocompiler.core.reference_package_channel.v1')
            self.assertEqual(session.hello_response.result['limits']['max_retained_bytes'], 536870912)
            self.assertEqual(bytes.fromhex(session.call('read-input', None).result), data)
            descriptor = session.call('write-output', data.hex()).result
            session.close()
            self.assertEqual(session.returncode, 0)
            self.assertEqual(owned.read_output(descriptor), data)
            self.assertEqual(transport.capability_profile()['limits']['max_retained_bytes'], 134217728)

    def test_host_invocation_keeps_original_object_identity(self):
        marker = object()
        handle = self.objects.retain(lambda: marker)
        with files.PackageFiles(None) as owned:
            with transport.CorePipelineCallbackSession(self.client(), application=APPLICATION,
                    objects=self.objects, _package_files=owned) as session:
                reply = session.call('call-host', {'action': 'call', 'arguments': {
                    'callable': handle, 'args': [], 'kwargs': {}}})
                self.assertIs(self.objects.resolve(reply.result), marker)

    def test_old_profile_cannot_authorize_package_owner(self):
        with files.PackageFiles(None) as owned:
            with self.assertRaises(CoreError):
                transport.CorePipelineCallbackSession(self.client(declaration=transport.capability_profile()),
                    application=APPLICATION, objects=self.objects, _package_files=owned)
            with self.assertRaisesRegex(CoreProtocolError, 'invalidated'):
                owned.monitor()

    def test_output_overflow_invalidates_and_reaps(self):
        with files.PackageFiles(None, max_archive_bytes=3) as owned:
            session = transport.CorePipelineCallbackSession(self.client(), application=APPLICATION,
                objects=self.objects, _package_files=owned)
            with self.assertRaisesRegex(CoreProtocolError, 'byte bounds'):
                session.call('write-output', b'oversized'.hex())
            self.assertTrue(session.invalidated)
            self.assertIsNotNone(session.returncode)
            with self.assertRaisesRegex(CoreProtocolError, 'invalidated'):
                owned.read_output({'bytes': 9, 'sha256': '0'*64})

    def test_rehashed_control_reply_cannot_substitute_output_digest(self):
        mutation = "if operation == 'write-output': outcome['value']['sha256'] = '0' * 64"
        with files.PackageFiles(None) as owned:
            with transport.CorePipelineCallbackSession(self.client(before_reply=mutation), application=APPLICATION,
                    objects=self.objects, _package_files=owned) as session:
                descriptor = session.call('write-output', b'actual'.hex()).result
            with self.assertRaisesRegex(CoreProtocolError, 'bytes differ'):
                owned.read_output(descriptor)

    def test_complete_protocol_declaration_matches_native_literal(self):
        declared = json.loads((ROOT / 'protocol/reference-package-channel-v1.json').read_bytes())
        self.assertEqual(transport.package_capability_profile(), declared)
        source = (ROOT / 'core/lib/pipeline_service/callback_channel.ml').read_text()
        literal = source.split('{package|', 1)[1].split('|package}', 1)[0]
        self.assertEqual(json.loads(literal), declared)


if __name__ == '__main__':
    unittest.main()
