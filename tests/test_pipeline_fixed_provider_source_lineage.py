"""Complete fixed-provider Corpus startup with the one reviewed source route."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import check_pipeline_fixed_provider_install as providers
from tools import manager_registration_source_lineage as lineage


class FixedProviderSourceLineageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.checkout = providers.ROOT
        cls.oracle_bytes = (cls.checkout / providers.ORACLE_PATH).read_bytes()
        cls.oracle = json.loads(cls.oracle_bytes)
        cls.sources = {
            path: (cls.checkout / path).read_bytes()
            for path in cls.oracle['source_files']
        }
        cls.directory = tempfile.TemporaryDirectory(prefix='fixed-provider-lineage-')
        cls.addClassCleanup(cls.directory.cleanup)
        cls.root = Path(cls.directory.name)
        for path, raw in {providers.ORACLE_PATH: cls.oracle_bytes, **cls.sources}.items():
            target = cls.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)

    def corpus(self):
        # Only relocate the provider's complete, byte-identical input census.
        # Its prior manager Corpus still performs all real original checks.
        with patch.object(providers, 'ROOT', self.root):
            return providers.Corpus()

    def replace_source(self, path, raw):
        target = self.root / path
        target.write_bytes(raw)
        self.addCleanup(target.write_bytes, self.sources[path])

    def assert_original_authority(self, corpus):
        self.assertEqual(corpus.pin, providers.ORACLE_SHA256)
        self.assertEqual(corpus.value, self.oracle)
        self.assertEqual(tuple(case['id'] for case in corpus.cases), providers.CASES)
        self.assertEqual(len(corpus.value['source_files']), 29)
        self.assertEqual(corpus.value['source_files'][lineage.PATH], lineage.HISTORICAL[lineage.PATH])
        self.assertEqual(corpus.metadata()['original_sources'], self.oracle['source_files'])
        self.assertEqual((self.checkout / providers.ORACLE_PATH).read_bytes(), self.oracle_bytes)

    def test_real_corpus_accepts_exact_reviewed_prefix_without_changing_original(self):
        entry = lineage.load_witness()
        self.assertEqual(self.sources[lineage.PATH], entry['routed_source'].encode())
        self.assertNotEqual(providers.sha(self.sources[lineage.PATH]), lineage.HISTORICAL[lineage.PATH])
        self.assert_original_authority(self.corpus())

    def test_real_corpus_still_accepts_exact_historical_source(self):
        self.replace_source(lineage.PATH, lineage.original_source())
        self.assert_original_authority(self.corpus())

    def test_reviewed_prefix_does_not_authorize_any_other_manager_edit(self):
        current = self.sources[lineage.PATH]
        changes = {
            'route': current.replace(b'issubclass(type(self), native_type)', b'type(self) is native_type', 1),
            'old-body': current.replace(b'    def register(', b'    def register_changed(', 1),
            'extra': current + b'\n# unrelated source edit\n',
            'newlines': current.replace(b'\n', b'\r\n'),
        }
        for label, raw in changes.items():
            with self.subTest(label=label):
                self.assertNotEqual(raw, current)
                self.replace_source(lineage.PATH, raw)
                with self.assertRaisesRegex(ValueError, 'Routed manager registration bytes differ'):
                    self.corpus()

    def test_other_source_files_remain_exact_raw_hashes(self):
        for path in ('src/biocompiler/compiler/behavior.py', providers.ORACLE_TOOL):
            with self.subTest(path=path):
                self.assertIn(path, self.sources)
                self.replace_source(path, self.sources[path] + b'\n# unrelated source edit\n')
                with self.assertRaisesRegex(AssertionError, 'Original fixed-provider source changed: ' + path):
                    self.corpus()
                (self.root / path).write_bytes(self.sources[path])

    def test_rehashed_oracle_cannot_replace_historical_source_authority(self):
        changed = deepcopy(self.oracle)
        changed['source_files'][lineage.PATH] = providers.sha(self.sources[lineage.PATH])
        changed['inventory_fingerprint'] = providers.sha(providers.canonical({
            key: value for key, value in changed.items() if key != 'inventory_fingerprint'
        }))
        target = self.root / providers.ORACLE_PATH
        self.addCleanup(target.write_bytes, self.oracle_bytes)
        target.write_bytes(providers.canonical(changed))
        with self.assertRaisesRegex(AssertionError, 'Frozen original fixed-provider file changed'):
            self.corpus()


if __name__ == '__main__':
    unittest.main()
