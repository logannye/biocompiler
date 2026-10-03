"""The attempt facade extension cannot replace an older transport witness."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import reference_attempt_source as source


class ReferenceAttemptSourceTests(unittest.TestCase):
    def test_exact_whole_source_restoration_keeps_original_routing_witness(self):
        current=(source.ROOT/source.SOURCE).read_bytes()
        original, proof=source.restore(current)
        self.assertEqual(source.sha(current),source.CURRENT)
        self.assertEqual(source.sha(original),source.OLD)
        self.assertEqual(len(proof['correspondence']['changes']),31)
        self.assertEqual(proof['correspondence']['predecessor'],{
            'path':'tests/conformance/reference-public-routing-source-counterpart-v1.json',
            'sha256':'949bd00942bbaa8c6107c490692e38007e41309b0d8f22b0bccd4d8f8514f074'})

    def test_current_source_extra_or_old_code_cannot_be_relabelled(self):
        current=(source.ROOT/source.SOURCE).read_bytes()
        old,_=source.restore(current)
        for raw in (current+b'\n',old,current.replace(b'self._reference_scopes.pop()',b'self._reference_scopes.clear()',1)):
            self.assertNotEqual(raw,current)
            with self.assertRaisesRegex(AssertionError,'Unreviewed current'):source.restore(raw)
        with patch.object(source,'CURRENT',source.sha(current+b'\n')):
            with self.assertRaisesRegex(AssertionError,'lineage identity'):source.restore(current+b'\n')

    def test_witness_changed_or_linked_source_rejects(self):
        current=(source.ROOT/source.SOURCE).read_bytes()
        raw=(source.ROOT/source.WITNESS).read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/source.WITNESS;path.parent.mkdir(parents=True)
            path.write_bytes(raw+b'\n')
            with patch.object(source,'ROOT',root):
                with self.assertRaisesRegex(AssertionError,'witness bytes'):source.restore(current)
                path.unlink();path.symlink_to(source.ROOT/source.SOURCE)
                with self.assertRaisesRegex(AssertionError,'Missing exact'):source.restore(current)


if __name__=='__main__':unittest.main()
