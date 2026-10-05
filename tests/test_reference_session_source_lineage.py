"""Restore the exact raw-session close fix without changing frozen authority."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import reference_original_counterpart as original


class ReferenceSessionSourceLineageTests(unittest.TestCase):
    def setUp(self):
        self.current = (original.ROOT / original.SESSION_SOURCE).read_bytes()
        self.encoded = (original.ROOT / original.SESSION_WITNESS).read_bytes()

    def test_exact_exit_drain_span_restores_complete_original_archive(self):
        restored, proof = original.session_source_witness(self.current)
        self.assertEqual((len(restored), original.sha(restored)), (33907, original.SESSION_ORIGINAL_SHA))
        self.assertEqual(restored, (original.ROOT / original.SESSION_BLOB).read_bytes())
        self.assertEqual(original.authority()['source_files'][original.SESSION_SOURCE], original.sha(restored))
        self.assertEqual(proof['current_sha256'], original.sha(self.current))
        change, = proof['correspondence']['changes']
        self.assertEqual(change['before'], "            if 'stdout' in self._eof or self._process.poll() is not None:\n")
        self.assertEqual((change['old_start_line'], change['old_end_line'],
                          change['new_start_line'], change['new_end_line']), (418, 418, 418, 421))
        self.assertIn('current session transport validation is separate', proof['scope'])

    def test_stale_changed_or_unrelated_source_cannot_be_relabelled(self):
        restored, _ = original.session_source_witness(self.current)
        for raw in (restored, self.current + b'\n', b'# shifted\n' + self.current,
                self.current.replace(b"if 'stdout' in self._eof:", b"if 'stderr' in self._eof:", 1)):
            with self.subTest(pin=original.sha(raw)), self.assertRaisesRegex(AssertionError, 'exact counterpart'):
                original.session_source_witness(raw)

    def test_rehashed_witness_cannot_expand_closed_source_authority(self):
        witness = json.loads(self.encoded)
        for kind in ('offset', 'boolean-offset', 'missing', 'duplicate', 'before', 'after', 'path',
                     'base', 'old-pin', 'new-pin', 'old-bytes', 'new-bytes', 'scope', 'extra'):
            changed = deepcopy(witness)
            if kind == 'offset': changed['changes'][0]['new_start_line'] += 1
            elif kind == 'boolean-offset': changed['changes'][0]['old_start_line'] = True
            elif kind == 'missing': changed['changes'].clear()
            elif kind == 'duplicate': changed['changes'].append(deepcopy(changed['changes'][0]))
            elif kind in ('before', 'after'): changed['changes'][0][kind] += '# forged\n'
            elif kind == 'path': changed['path'] = original.CALLBACK_SOURCE
            elif kind == 'base': changed['base_revision'] = '0' * 40
            elif kind == 'old-pin': changed['original_sha256'] = original.CALLBACK_ORIGINAL_SHA
            elif kind == 'new-pin': changed['current_sha256'] = original.SESSION_ORIGINAL_SHA
            elif kind == 'old-bytes': changed['original_bytes'] += 1
            elif kind == 'new-bytes': changed['current_bytes'] += 1
            elif kind == 'scope': changed['scope'] = 'native acceptance'
            else: changed['unreviewed'] = True
            encoded = original.canonical(changed) + b'\n'
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(AssertionError, 'session source witness changed'):
                    original.session_source_witness(self.current, encoded)
                with patch.object(original, 'SESSION_WITNESS_SHA', original.sha(encoded)), self.assertRaises(AssertionError):
                    original.session_source_witness(self.current, encoded)

    def test_missing_changed_or_linked_archive_and_witness_are_rejected(self):
        for logical in (original.SESSION_BLOB, original.SESSION_WITNESS):
            for kind in ('missing', 'changed', 'linked'):
                with self.subTest(path=logical, kind=kind), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    for name in (original.SESSION_BLOB, original.SESSION_WITNESS):
                        path = root / name
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes((original.ROOT / name).read_bytes())
                    path = root / logical
                    if kind == 'changed': path.write_bytes(path.read_bytes() + b'\n')
                    else:
                        path.unlink()
                        if kind == 'linked': path.symlink_to(original.ROOT / logical)
                    with patch.object(original, 'ROOT', root), self.assertRaises(AssertionError):
                        original.session_source_witness(self.current)

    def test_complete_source_and_data_closures_retain_exact_session_proof(self):
        index = original.authority()
        sources, _ = original.source_closure(index, original.ROOT / 'src/biocompiler')
        self.assertEqual(len(sources), 207)
        _, current, copied = sources[original.SESSION_SOURCE]
        self.assertEqual(current, self.current)
        self.assertEqual(copied, (original.ROOT / original.SESSION_BLOB).read_bytes())
        data = original.data_closure(index)
        self.assertEqual(len(data), 4016)
        for logical, pin in ((original.SESSION_BLOB, original.SESSION_ORIGINAL_SHA),
                             (original.SESSION_WITNESS, original.SESSION_WITNESS_SHA)):
            self.assertEqual([row for row in data if row['logical'] == logical],
                [{'logical': logical, 'sha256': pin, 'bytes': len((original.ROOT / logical).read_bytes())}])
        from tools import check_pipeline_reference_install as campaign
        self.assertEqual(campaign.SOURCES.count('tests/test_reference_session_source_lineage.py'), 1)

    def test_native_gate_addition_preserves_entire_prior_source_and_archive_comparison(self):
        from tools.reference_package_source_lineage import native_reference_counterpart
        source = native_reference_counterpart((original.ROOT / 'core/test/test_reference_contracts_corpus.ml').read_bytes()).decode()
        start = source.index('let reference_session_original ')
        end = source.index('let reference_original root ')
        helper = source[start:end]
        branch = ('    else if name="src/biocompiler/core_pipeline_session.py" then\n'
                  '      reference_session_original root name expected current\n')
        self.assertEqual(source.count(branch), 1)
        restored = (source[:start] + source[end:]).replace(branch, '', 1)
        self.assertEqual(original.sha(restored.encode()),
                         'eec85717caffb22eacbbb1fb87f78bf04dd2dad79d5c4b918c60a75cea191b7c')
        for value in (original.SESSION_SOURCE, original.SESSION_ORIGINAL_SHA, original.SESSION_CURRENT_SHA,
                original.SESSION_WITNESS, original.SESSION_WITNESS_SHA, 'spans=[418,418,418,421]',
                'String.length restored=33907', 'Canonical.sha256 restored=original_pin'):
            self.assertIn(value, helper)
        self.assertIn('Canonical.sha256 archived=expected && restored=archived', source[end:])
        # Literal source review only; native compilation and execution stay hosted.


if __name__ == '__main__':
    unittest.main()
