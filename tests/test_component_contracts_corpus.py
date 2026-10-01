"""Retained component contract identities, exact algebra and diagnostic profile."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

campaign = load("freeze_component_contracts")
unicode14 = load("freeze_unicode14_printability")

class ComponentContractCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = campaign.OUTPUT.read_bytes()
        cls.corpus = json.loads(cls.content)

    def test_retained_full_records_and_algebra_reproduce_exactly(self):
        rebuilt = campaign.build_corpus()
        campaign.validate(rebuilt)
        self.assertEqual(campaign.encode(rebuilt), self.content)
        self.assertEqual(len(rebuilt["records"]), 30)
        self.assertEqual(len(rebuilt["rejections"]), 35)
        self.assertEqual(len(rebuilt["algebra"]), 77)
        self.assertEqual(rebuilt["coverage"]["literal_algebra_count"], 71)
        self.assertEqual(rebuilt["coverage"]["synthetic_operations"], sorted(campaign.OPERATIONS))
        self.assertLess(len(self.content), 250_000)
        self.assertNotIn(str(ROOT), self.content.decode())

    def test_missing_case_cannot_hide_in_recomputed_coverage(self):
        changed = deepcopy(self.corpus)
        changed["algebra"].pop()
        changed["coverage"] = campaign.coverage(changed)
        with self.assertRaisesRegex(AssertionError, "Truncated"):
            campaign.validate(changed)
        changed = deepcopy(self.corpus)
        changed["algebra"][-1]["id"] = "replacement_unsupported_claim"
        changed["coverage"] = campaign.coverage(changed)
        with self.assertRaisesRegex(AssertionError, "case inventory"):
            campaign.validate(changed)

    def test_duplicate_identity_and_manifest_forgery_fail(self):
        changed = deepcopy(self.corpus)
        changed["algebra"][0]["id"] = changed["records"][0]["id"]
        with self.assertRaisesRegex(AssertionError, "Duplicate"):
            campaign.validate(changed)
        changed = deepcopy(self.corpus)
        changed["coverage"]["record_kinds"] = []
        with self.assertRaises(AssertionError):
            campaign.validate(changed)

    def test_forged_positive_and_fingerprint_are_rejected(self):
        changed = deepcopy(self.corpus)
        changed["records"][0]["normalized"]["values"] = [False]
        changed["records"][0]["fingerprint"] = campaign.fingerprint(changed["records"][0]["normalized"])
        with self.assertRaises(AssertionError):
            campaign.validate(changed)
        changed = deepcopy(self.corpus)
        changed["records"][0]["fingerprint"] = "0" * 64
        with self.assertRaises(AssertionError):
            campaign.validate(changed)

    def test_forged_unknown_pass_and_endpoint_kind_fail(self):
        changed = deepcopy(self.corpus)
        case = next(x for x in changed["algebra"] if x["id"] == "unknown_not_reflexive")
        case["expected"]["status"] = "pass"
        case["fingerprint"] = campaign.fingerprint(case["expected"])
        with self.assertRaisesRegex(AssertionError, "unknown_not_reflexive"):
            campaign.validate(changed)
        changed = deepcopy(self.corpus)
        item = next(x for x in changed["records"] if x["id"] == "interval_mixed")
        item["normalized"]["upper"] = 4
        item["fingerprint"] = campaign.fingerprint(item["normalized"])
        with self.assertRaises(AssertionError):
            campaign.validate(changed)

    def test_rejection_category_cannot_be_relabelled(self):
        changed = deepcopy(self.corpus)
        changed["rejections"][0]["expected_code"] = "component_contract"
        with self.assertRaisesRegex(AssertionError, "native rejection"):
            campaign.validate(changed)
        changed = deepcopy(self.corpus)
        changed["rejections"][0]["input"].pop("extra")
        with self.assertRaisesRegex(AssertionError, "Malformed fixture was accepted"):
            campaign.validate(changed)

    def test_unknown_runtime_initialization_and_units_are_distinct(self):
        cases = {item["id"]: item for item in self.corpus["algebra"]}
        self.assertEqual(cases["infer_held_initial_unknown"]["expected"]["values"], [False])
        self.assertEqual(cases["infer_held_runtime_unknown"]["expected"]["kind"], "unknown")
        self.assertEqual(cases["port_initial_is_separate"]["expected"]["status"], "fail")
        self.assertEqual(cases["units_not_converted"]["expected"]["status"], "fail")
        self.assertEqual(cases["mixed_large_integer_float"]["expected"]["status"], "fail")
        self.assertIsNone(cases["infer_input"]["expected"])

    def test_check_mode_never_creates_missing_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.json"
            with self.assertRaises(SystemExit):
                campaign.main(["--check", "--output", str(path)])
            self.assertFalse(path.exists())

    def test_unicode_table_and_native_implementation_are_pinned_offline(self):
        data = json.loads(unicode14.TABLE.read_bytes())
        unicode14.validate(data)
        self.assertEqual(data["range_count"], 700)
        self.assertEqual(unicode14.MODULE.read_bytes(), unicode14.native_module(data))
        self.assertTrue((ROOT / data["license_file"]).read_text().startswith("UNICODE LICENSE V3"))
        changed = deepcopy(data)
        changed["printable_ranges"][0][0] += 1
        with self.assertRaises(AssertionError):
            unicode14.validate(changed)
        with self.assertRaisesRegex(AssertionError, "source digest"):
            unicode14.ranges_from_source(b"fabricated Unicode data")

    def test_unicode_version_differences_are_explicit_not_host_generated(self):
        data = json.loads(unicode14.TABLE.read_bytes())
        printable = lambda point: any(low <= point <= high for low, high in data["printable_ranges"])
        for point in (0x20, ord("μ"), 0x1FAE7, 0xE0100):
            self.assertTrue(printable(point))
        for point in (0, 0x85, 0xA0, 0x200B, 0xE000, 0xF0000, 0x1FAE8, 0x1FA89, 0x10FFFF):
            self.assertFalse(printable(point))
        witnesses = self.corpus["diagnostic_witnesses"]
        self.assertEqual(len(witnesses), 3)
        self.assertEqual(witnesses[0]["expected_repr"], "'a\\U0001fae8'")
        self.assertEqual(witnesses[0]["newer_python_repr"], "'a\U0001fae8'")
        self.assertEqual(witnesses[1]["expected_repr"], "'a\\U0001fa89'")
        self.assertEqual(self.corpus["diagnostic_profile"], unicode14.PROFILE)

if __name__ == "__main__":
    unittest.main()
