"""Real Python subprocess reconstruction controls; no native execution."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from biocompiler.core_client import CoreClient, CoreProtocolError, CoreTransportError
from biocompiler.core_pipeline_callback_session import CorePipelineCallbackSession
from biocompiler.pipeline_callback_objects import CallbackObjects
from tests.test_pipeline_fixed_provider_campaign import Script
from tools import check_pipeline_manager_install as manager
from tools import reference_pipeline_transcript as transcript


class ReferenceTranscriptTests(unittest.TestCase):
    def frames(self, *, command=False):
        with tempfile.TemporaryDirectory() as directory:
            receipt = {'_artifact_directory': directory, 'artifacts': {}}
            script = Script(receipt)
            if command:
                script.reply(script.command('target', {}), {'value': 'retained native value'})
            script.close()
            return [(row['direction'], (Path(directory) / (row['frame'] + '.bin')).read_bytes())
                    for row in script.rows]

    def run_peer(self, frames, *, call=None):
        with transcript.TranscriptPeer([frames]) as peer:
            client = CoreClient(peer.executable, expected_sha256=peer.executable_sha256)
            with peer.recorded_nonces():
                session = CorePipelineCallbackSession(client, application=manager.declarations()[1], objects=CallbackObjects())
                try:
                    result = call(session) if call is not None else None
                    session.close()
                    self.assertEqual(session.returncode, 0)
                    self.assertEqual(session.stderr_bytes, b'')
                    self.assertEqual([(item.direction, item.frame) for item in session.traffic], frames)
                    return result, peer.evidence([session])
                finally:
                    if not session.closed:
                        session._invalidate()

    def test_current_transport_consumes_every_exact_frame_and_is_explicitly_nonnative(self):
        result, proof = self.run_peer(self.frames(command=True), call=lambda session: session.call('target', {}).result)
        self.assertEqual(result, {'value': 'retained native value'})
        self.assertIs(proof['native_execution'], False)
        self.assertEqual(len(proof['processes']), 1)
        self.assertEqual(proof['processes'][0]['frames'], 6)

    def test_changed_client_request_is_not_served_a_recorded_result(self):
        with self.assertRaises((CoreProtocolError, CoreTransportError)):
            self.run_peer(self.frames(command=True), call=lambda session: session.call('target', {'extra': True}))

    def test_reordered_missing_or_extra_response_bytes_fail_closed(self):
        frames = self.frames(command=True)
        changed = deepcopy(frames)
        changed[3], changed[5] = changed[5], changed[3]
        for mutant in (changed, frames[:-1], frames + [frames[-1]]):
            with self.subTest(frames=len(mutant)):
                with self.assertRaises((CoreProtocolError, CoreTransportError)):
                    self.run_peer(mutant, call=lambda session: session.call('target', {}))

    def test_nonce_lifetime_and_frame_membership_are_closed(self):
        frames = self.frames()
        with self.assertRaisesRegex(AssertionError, 'nonce'):
            transcript.TranscriptPeer([frames, frames])
        with transcript.TranscriptPeer([frames]) as peer:
            with self.assertRaisesRegex(AssertionError, 'omitted a process'):
                with peer.recorded_nonces():
                    pass
        with transcript.TranscriptPeer([frames]) as peer:
            with peer.recorded_nonces():
                peer._nonce()
                with self.assertRaisesRegex(AssertionError, 'extra process'):
                    peer._nonce()
            with self.assertRaisesRegex(AssertionError, 'completed process census'):
                peer.evidence([])
            with self.assertRaisesRegex(AssertionError, 'reconstructed process'):
                peer.evidence([object()])
            with self.assertRaisesRegex(AssertionError, 'twice'):
                with peer.recorded_nonces():
                    pass
        invalid = deepcopy(frames)
        invalid[0] = ('client', invalid[0][1] + b' ')
        with self.assertRaisesRegex(AssertionError, 'length differs'):
            transcript.TranscriptPeer([invalid])

    def test_tape_and_index_tampering_are_independently_rejected(self):
        frames = self.frames()
        for which in ('tape', 'index'):
            with transcript.TranscriptPeer([frames]) as peer:
                path = peer.directory / ('0.frames' if which == 'tape' else 'index.json')
                path.write_bytes(path.read_bytes() + b' ')
                client = CoreClient(peer.executable, expected_sha256=peer.executable_sha256)
                with peer.recorded_nonces():
                    with self.assertRaises((CoreProtocolError, CoreTransportError)):
                        CorePipelineCallbackSession(client, application=manager.declarations()[1], objects=CallbackObjects())

    def test_peer_executable_is_exactly_bound_to_tool_and_complete_tape_index(self):
        with transcript.TranscriptPeer([self.frames()]) as peer:
            expected = transcript.executable_source(**peer.origin)
            self.assertEqual(peer.executable.read_bytes(), expected)
            self.assertEqual(transcript.sha(expected), peer.executable_sha256)
            self.assertEqual(peer.origin['source_sha256'], transcript.sha(Path(transcript.__file__).read_bytes()))
            self.assertEqual(peer.origin['index_sha256'], transcript.sha((peer.directory / 'index.json').read_bytes()))
            authority = {'source_path': peer.origin['source'], 'source_sha256': peer.origin['source_sha256'],
                'index_sha256': peer.origin['index_sha256']}
            transcript.validate_executable(expected, peer.origin, **authority)
            for key in ('source_sha256', 'index_sha256'):
                changed = {**peer.origin, key: '0' * 64}
                self.assertNotEqual(transcript.executable_source(**changed), expected)
                with self.assertRaisesRegex(AssertionError, 'origin differs'):
                    transcript.validate_executable(transcript.executable_source(**changed), changed, **authority)
            for key in ('interpreter', 'source', 'directory'):
                with self.subTest(key=key), self.assertRaisesRegex(AssertionError, 'origin path'):
                    transcript.executable_source(**{**peer.origin, key: 'relative/path'})
            with self.assertRaisesRegex(AssertionError, 'exact current source-bound wrapper'):
                transcript.validate_executable(expected + b'print("forged acceptance")\n', peer.origin, **authority)
