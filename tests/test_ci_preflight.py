"""Original-source proof failures must stop expensive hosted validation early."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import check_ci_preflight as preflight
from tools import reference_original_counterpart as reference


AUTHORITIES = ('reference-contracts', 'realization-workflow', 'workflow-cli')


class OriginalSourcePreflightTests(unittest.TestCase):
    def test_current_original_sources_restore_all_frozen_authorities(self):
        for name in AUTHORITIES:
            with self.subTest(name=name):
                row = preflight.check_original_sources(name)
                self.assertGreater(row['source_count'], 0)

    def test_missing_or_changed_callback_witness_fails_all_three_authorities(self):
        read = Path.read_bytes
        witness = reference.ROOT / reference.CALLBACK_DRAIN_WITNESS
        for missing in (False, True):
            def altered(path):
                if path == witness:
                    if missing:
                        raise FileNotFoundError(str(path))
                    return read(path) + b'\n'
                return read(path)
            for name in AUTHORITIES:
                with self.subTest(name=name, missing=missing), patch.object(Path, 'read_bytes', altered):
                    with self.assertRaises((AssertionError, FileNotFoundError)):
                        preflight.check_original_sources(name)

    def test_any_failed_authority_fails_preflight_after_retaining_complete_results(self):
        for failed in AUTHORITIES:
            def inspect(name):
                if name == failed:
                    raise AssertionError('Missing exact source restoration')
                return {'source_count': 1}
            with self.subTest(failed=failed), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / 'preflight.json'
                with patch.object(preflight.sys, 'argv', ['preflight', '--output', str(output)]), \
                        patch.object(preflight.sys, 'addaudithook'), \
                        patch.object(preflight, 'test_plan', return_value=['native']), \
                        patch.object(preflight, 'load_plan', return_value=['direct']), \
                        patch.object(preflight, 'campaign_names'), \
                        patch.object(preflight, 'CAMPAIGNS', [('fixture', 'fixture')]), \
                        patch.object(preflight, 'check', return_value={'source_count': 1}), \
                        patch.object(preflight, 'check_original_sources', side_effect=inspect):
                    self.assertEqual(preflight.main(), 1)
                receipt = json.loads(output.read_text())
                self.assertEqual(receipt['status'], 'fail')
                self.assertEqual([row['name'] for row in receipt['original_source_authorities']], list(AUTHORITIES))
                self.assertEqual([row['name'] for row in receipt['original_source_authorities']
                                  if row['status'] == 'fail'], [failed])
                self.assertEqual(receipt['campaigns'][0]['status'], 'pass')
