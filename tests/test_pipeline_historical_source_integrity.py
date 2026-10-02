"""Closed source correspondence and genuine historical contract-test execution."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from tools import manager_registration_source_lineage as lineage
from tools import pipeline_original_counterpart as counterpart
from tools.pipeline_historical_source_integrity import verify_source_identity

ROOT = Path(__file__).resolve().parents[1]


class PipelineHistoricalSourceIntegrityTests(unittest.TestCase):
    def test_only_exact_manager_prefix_can_explain_a_changed_source(self):
        pin = lineage.HISTORICAL[lineage.PATH]
        current = (ROOT / lineage.PATH).read_bytes()
        proof = verify_source_identity(ROOT, lineage.PATH, pin)
        self.assertEqual(proof['historical_sha256'], pin)
        self.assertEqual(proof['current_sha256'], lineage.sha(current))
        self.assertEqual(proof['witness_sha256'], lineage.WITNESS_SHA256)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / lineage.PATH
            path.parent.mkdir(parents=True)
            path.write_bytes(lineage.original_source())
            self.assertEqual(verify_source_identity(root, lineage.PATH, pin)['kind'], 'identical_bytes')
            for changed in (current + b'\n# unrelated edit\n',
                            current.replace(b'return native_type._native_register', b'native_type._native_register', 1),
                            current.replace(b'issubclass(type(self), native_type)', b'True', 1)):
                path.write_bytes(changed)
                with self.subTest(pin=lineage.sha(changed)), self.assertRaises(ValueError):
                    verify_source_identity(root, lineage.PATH, pin)
                with self.assertRaises(ValueError):
                    verify_source_identity(root, lineage.PATH, lineage.sha(changed))
            other = root / 'ordinary.py'
            other.write_bytes(b'unchanged source\n')
            expected = lineage.sha(other.read_bytes())
            self.assertEqual(verify_source_identity(root, 'ordinary.py', expected)['kind'], 'identical_bytes')
            other.write_bytes(current)
            with self.assertRaisesRegex(AssertionError, 'Original captured source'):
                verify_source_identity(root, 'ordinary.py', expected)

    def test_contract_literal_bridge_runs_original_cases_and_keeps_canonical_origins(self):
        module = 'test_pipeline_contract_literals'
        classname = module + '.PipelineContractLiteralTests'
        ids = [classname + '.test_complete_original_literals_reproduce_without_native_execution',
               classname + '.test_complete_records_keep_numeric_identity_and_scope']
        receipt = counterpart.run('tests', test_module=module, test_ids=ids)
        actual = counterpart.validate(receipt)
        outcomes = counterpart.validate_test_outcomes(actual, ids, classname)
        self.assertEqual([outcomes[name]['status'] for name in ids], ['success', 'success'])
        observed = receipt['modules']['biocompiler.compiler.pipeline']
        self.assertEqual(observed['namespace'], 'biocompiler.compiler.pipeline')
        self.assertEqual(observed['sha256'], lineage.HISTORICAL[lineage.PATH])
        rows = {row['logical']: row for row in receipt['manifest']['sources']}
        self.assertEqual([name for name, row in rows.items() if row['substituted']], [lineage.PATH])
        capture = 'tools/capture_pipeline_contract_literals.py'
        self.assertEqual(rows[capture]['sha256'], lineage.sha((ROOT / capture).read_bytes()))
        self.assertIn('tests/conformance/pipeline-contract-literals-v1.json',
                      {row['logical'] for row in receipt['manifest']['data']})
        for mode in ('current-manager', 'foreign-namespace', 'missing-capture', 'changed-index'):
            changed = deepcopy(receipt)
            if mode == 'current-manager':
                changed['modules']['biocompiler.compiler.pipeline']['sha256'] = lineage.sha((ROOT / lineage.PATH).read_bytes())
            elif mode == 'foreign-namespace':
                changed['modules']['biocompiler.compiler.pipeline']['namespace'] = 'historical.pipeline'
            elif mode == 'missing-capture':
                changed['manifest']['sources'] = [row for row in changed['manifest']['sources'] if row['logical'] != capture]
            else:
                changed['manifest']['data'][-1]['sha256'] = '0' * 64
            with self.subTest(mode=mode), self.assertRaises(AssertionError):
                counterpart.validate(changed)
        for mode in ('missing', 'changed-class', 'changed-count'):
            changed = deepcopy(actual)
            if mode == 'missing': changed['outcomes'].pop()
            elif mode == 'changed-class': changed['outcomes'][0]['class'] = 'Another.Class'
            else: changed['tests'] -= 1
            with self.subTest(mode=mode), self.assertRaises(AssertionError):
                counterpart.validate_test_outcomes(changed, ids, classname)


if __name__ == '__main__':
    unittest.main()
