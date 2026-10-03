"""Independent original-Python literal and source integrity checks."""
import hashlib
import json
from pathlib import Path
import unittest

from tools.capture_pipeline_contract_literals import ROOT, canonical, capture


class PipelineContractLiteralTests(unittest.TestCase):
    def test_complete_original_literals_reproduce_without_native_execution(self):
        saved = json.loads((ROOT / "tests/conformance/pipeline-contract-literals-v1.json").read_bytes())
        self.assertEqual(canonical(capture()), canonical(saved))
        self.assertEqual(len(saved["literals"]), 13)
        self.assertEqual(len(saved["rejections"]), 19)
        self.assertEqual(len({row["kind"] for row in saved["literals"]}), 12)
        for path, pin in saved["sources"].items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), pin)
        self.assertEqual(saved["inventory_fingerprint"], hashlib.sha256(canonical({
            key: value for key, value in saved.items() if key != "inventory_fingerprint"})).hexdigest())

    def test_complete_records_keep_numeric_identity_and_scope(self):
        saved = capture()
        row = next(row for row in saved["literals"] if row["id"] == "unicode-numeric-kinds")
        raw = canonical(row["document"])
        self.assertIn("é😀".encode(), raw)
        self.assertIn(b'[1,1.0,-0.0,', raw)
        baseline = saved["manager_baseline"]
        self.assertEqual(baseline["result"]["status"], "complete")
        self.assertEqual([row["id"] for row in baseline["result"]["unresolved"]], ["biology"])
        self.assertEqual(baseline["records"]["mechanism"], baseline["result"]["artifact"])
        self.assertEqual(list(baseline["records"]), ["input", "behavior", "mechanism"])


def load_tests(loader, tests, pattern):
    from tools.pipeline_original_counterpart import original_test_suite
    return original_test_suite(loader, tests, pattern, __name__)


if __name__ == "__main__":
    unittest.main()
