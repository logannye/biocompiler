"""Cheap exact transport source restoration; no original or native execution."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import reference_original_counterpart as original
from tools import check_realization_workflow_corpus as workflow


class CallbackSourceLineageTests(unittest.TestCase):
    def setUp(self):
        self.current = (original.ROOT / original.CALLBACK_SOURCE).read_bytes()
        self.encoded = (original.ROOT / original.CALLBACK_DRAIN_WITNESS).read_bytes()

    def test_complete_new_then_unchanged_old_restoration_matches_original_bytes(self):
        previous, update = original.callback_drain_source_witness(self.current)
        self.assertEqual((len(previous), original.sha(previous)), (32588, original.CALLBACK_PREVIOUS_SHA))
        old = json.loads((original.ROOT / original.CALLBACK_WITNESS).read_bytes())
        self.assertEqual(old['current_sha256'], original.sha(previous))
        self.assertEqual(update['correspondence']['predecessor'],
                         {'path': original.CALLBACK_WITNESS, 'sha256': original.CALLBACK_WITNESS_SHA})
        restored, proof = original.callback_source_witness(self.current)
        self.assertEqual(restored, (original.ROOT / original.CALLBACK_BLOB).read_bytes())
        self.assertEqual((len(restored), original.sha(restored)), (32312, original.CALLBACK_ORIGINAL_SHA))
        self.assertEqual(proof['correspondence'], old)
        self.assertEqual(proof['buffered_close_update'], update)
        self.assertEqual(proof['current_sha256'], original.sha(self.current))

    def test_source_mutations_and_stale_revisions_cannot_enter_the_chain(self):
        previous, _ = original.callback_drain_source_witness(self.current)
        for raw in (previous, (original.ROOT / original.CALLBACK_BLOB).read_bytes(), self.current+b'\n',
                    self.current.replace(b"if 'stdout' in self._eof:", b"if False:", 1),
                    self.current.replace(b"    def close(self)", b"    def unreviewed_close(self)", 1)):
            with self.subTest(sha=original.sha(raw)), self.assertRaisesRegex(AssertionError, 'exact counterpart'):
                original.callback_source_witness(raw)

    def test_rehashed_update_cannot_change_spans_predecessor_or_whole_source(self):
        witness = json.loads(self.encoded)
        for kind in ('offset', 'missing', 'duplicate', 'before', 'after', 'path', 'base',
                     'previous', 'current', 'bytes', 'predecessor', 'scope', 'extra'):
            changed = deepcopy(witness)
            if kind == 'offset': changed['changes'][0]['new_start_line'] += 1
            elif kind == 'missing': changed['changes'].clear()
            elif kind == 'duplicate': changed['changes'].append(deepcopy(changed['changes'][0]))
            elif kind in ('before', 'after'): changed['changes'][0][kind] += '# unreviewed\n'
            elif kind == 'path': changed['path'] = original.CORE_SOURCE
            elif kind == 'base': changed['base_revision'] = '0' * 40
            elif kind == 'previous': changed['original_sha256'] = original.CALLBACK_ORIGINAL_SHA
            elif kind == 'current': changed['current_sha256'] = original.CALLBACK_PREVIOUS_SHA
            elif kind == 'bytes': changed['original_bytes'] += 1
            elif kind == 'predecessor': changed['predecessor']['sha256'] = '0' * 64
            elif kind == 'scope': changed['scope'] = 'current acceptance'
            else: changed['unreviewed'] = True
            encoded = original.canonical(changed) + b'\n'
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(AssertionError, 'drain source witness changed'):
                    original.callback_drain_source_witness(self.current, encoded)
                with patch.object(original, 'CALLBACK_DRAIN_WITNESS_SHA', original.sha(encoded)), self.assertRaises(AssertionError):
                    original.callback_drain_source_witness(self.current, encoded)

    def test_workflow_addition_requires_current_bytes_and_complete_witness(self):
        additions = {original.CALLBACK_SOURCE: original.CALLBACK_CURRENT_SHA}
        with patch.object(original, 'callback_source_witness', wraps=original.callback_source_witness) as checked:
            self.assertEqual(workflow.addition_counterparts(additions), [])
            checked.assert_called_once_with(self.current)
        with patch.object(original, 'CALLBACK_DRAIN_WITNESS_SHA', '0' * 64), self.assertRaisesRegex(AssertionError, 'drain source witness changed'):
            workflow.addition_counterparts(additions)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / original.CALLBACK_SOURCE
            path.parent.mkdir(parents=True)
            changed = self.current + b'# unreviewed\n'
            path.write_bytes(changed)
            with patch.object(workflow, 'ROOT', root), patch.dict(workflow.REVIEWED_ADDITIONS,
                    {original.CALLBACK_SOURCE: original.sha(changed)}), self.assertRaisesRegex(AssertionError, 'callback addition identity'):
                workflow.addition_counterparts({original.CALLBACK_SOURCE: original.sha(changed)})

    def test_native_source_gate_retains_old_body_and_same_new_finite_authority(self):
        source = (original.ROOT / 'core/test/test_reference_contracts_corpus.ml').read_text()
        before = source[source.index('let reference_callback_original '):source.index('let reference_session_original ')]
        added = '  let current=reference_callback_drain_original root name current in\n'
        self.assertEqual(before.count(added), 1)
        self.assertEqual(hashlib.sha256(before.replace(added, '').encode()).hexdigest(),
                         'ab4d849e447a6bbeed945f75a0d7c65129923f3dd9f57ee4530a764320fa40c1')
        update = source[source.index('let reference_callback_drain_original '):source.index('let reference_callback_original ')]
        for value in (original.CALLBACK_CURRENT_SHA, original.CALLBACK_PREVIOUS_SHA,
                      original.CALLBACK_DRAIN_WITNESS, original.CALLBACK_DRAIN_WITNESS_SHA,
                      original.CALLBACK_WITNESS, original.CALLBACK_WITNESS_SHA,
                      'spans=[355,355,355,358]', 'String.length restored=32588', 'Canonical.sha256 restored=previous_pin'):
            self.assertIn(value, update)
        # This is literal source consistency only; OCaml execution remains hosted.
        self.assertEqual(original.sha((original.ROOT / original.CALLBACK_WITNESS).read_bytes()),
                         'e3be989e0a76913f64ec959d4354bb4a352c70e0bf661ca58df68db15e544b5c')
