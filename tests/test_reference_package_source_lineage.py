"""Exact public and transport predecessor proofs retain frozen authority."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import reference_package_source_lineage as lineage


class ReferencePackageSourceLineageTests(unittest.TestCase):
    def test_complete_current_sources_restore_base573(self):
        for logical, (before, after, _) in (lineage.PUBLIC | lineage.TRANSPORT).items():
            with self.subTest(path=logical):
                current = (lineage.ROOT / logical).read_bytes()
                restored, proof = lineage.restore(logical, current)
                self.assertEqual(lineage.sha(current), after)
                self.assertEqual(lineage.sha(restored), before)
                self.assertEqual(proof['current_sha256'], after)
                self.assertEqual(lineage.source_identity(lineage.ROOT, logical), before)

    def test_changed_source_and_original_only_reject(self):
        for logical in lineage.PUBLIC | lineage.TRANSPORT:
            current = (lineage.ROOT / logical).read_bytes()
            previous, _ = lineage.restore(logical, current)
            for changed in (current + b'\n', previous):
                with self.subTest(path=logical), self.assertRaisesRegex(AssertionError, 'exact counterpart'):
                    lineage.restore(logical, changed)

    def test_foreign_original_authority_and_paths_reject(self):
        for logical in lineage.PUBLIC | lineage.TRANSPORT:
            with self.assertRaisesRegex(AssertionError, 'original source authority'):
                lineage.verify_source(lineage.ROOT, logical, '0' * 64)
        with self.assertRaisesRegex(AssertionError, 'Unreviewed'):
            lineage.restore('src/biocompiler/unknown.py', b'')

    def test_changed_witness_is_not_authority(self):
        for logical, name in ((next(iter(lineage.PUBLIC)), 'PUBLIC_PIN'),
                              (next(iter(lineage.TRANSPORT)), 'TRANSPORT_PIN')):
            with patch.object(lineage, name, '0' * 64):
                with self.assertRaisesRegex(AssertionError, 'witness changed'):
                    lineage.restore(logical)

    def test_unchanged_file_identity_is_exact_actual_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'unchanged.py'
            path.write_bytes(b'actual source\n')
            self.assertEqual(lineage.source_identity(root, path.name), lineage.sha(path.read_bytes()))
