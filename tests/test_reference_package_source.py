"""The installed source proof admits only the reviewed finite entry prefixes."""
import hashlib
import json
from pathlib import Path
import unittest

from biocompiler import core_reference_package_source as source
from biocompiler.core_package_owner import PackageBoundaryError


class ReferencePackageSourceTests(unittest.TestCase):
    def test_complete_current_sources_restore_original_base_bytes(self):
        for relative, (before, after, _) in source._SOURCES.items():
            path = source._PACKAGE / relative
            raw = path.read_bytes()
            with self.subTest(path=relative):
                self.assertEqual(hashlib.sha256(raw).hexdigest(), after)
                restored = source.check_source(path, raw)
                self.assertEqual(hashlib.sha256(restored).hexdigest(), before)

    def test_installed_literal_matches_reviewed_prefix_witness(self):
        root = Path(__file__).resolve().parents[1]
        witness = json.loads((root / 'protocol/reference-package-public-prefixes-v1.json').read_bytes())
        self.assertEqual(witness['base_revision'], source.BASE_REVISION)
        for relative, row in witness['files'].items():
            self.assertEqual(source._SOURCES[relative], (row['before_sha256'], row['after_sha256'],
                tuple((item['function'], item['text']) for item in row['prefixes'])))

    def test_extra_missing_duplicated_or_replaced_bytes_reject(self):
        relative = 'compiler/reference.py'
        path = source._PACKAGE / relative
        raw = path.read_bytes()
        prefix = source._SOURCES[relative][2][0][1].encode()
        for changed in (raw + b'\n', raw.replace(prefix, b'', 1), raw + prefix,
                raw.replace(b'REFERENCE_BUILD_VERSION', b'CHANGED_BUILD_VERSION', 1)):
            with self.assertRaisesRegex(PackageBoundaryError, 'current source bytes'):
                source.check_source(path, changed)

    def test_original_bytes_are_not_an_alternate_current_authority(self):
        path = source._PACKAGE / 'compiler/reference.py'
        original = source.check_source(path, path.read_bytes())
        with self.assertRaisesRegex(PackageBoundaryError, 'current source bytes'):
            source.check_source(path, original)

    def test_unreviewed_and_external_paths_reject(self):
        with self.assertRaises(PackageBoundaryError):
            source.check_source(Path('/unreviewed/reference.py'), b'')
        with self.assertRaises(PackageBoundaryError):
            source.check_source(source._PACKAGE / 'unknown.py', b'')
