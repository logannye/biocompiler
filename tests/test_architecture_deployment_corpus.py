"""Exact declaration bytes and decimal deployment bounds for native migration."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("freeze_deployment", ROOT / "tools/freeze_architecture_deployment.py")
campaign = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(campaign)


class ArchitectureDeploymentCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = campaign.CORPUS.read_bytes()
        cls.corpus = json.loads(cls.raw)

    def test_complete_corpus_reproduces_with_original_authority(self):
        self.assertEqual(campaign.encoded(campaign.build_corpus()), self.raw)
        self.assertEqual([len(self.corpus[key]) for key in ("records", "rejections", "decimals", "sums")], [15, 78, 18, 6])
        self.assertLess(len(self.raw), 100_000)
        self.assertNotIn(str(ROOT).encode(), self.raw)

    def test_removed_cases_cannot_hide_in_recomputed_manifest(self):
        changed = deepcopy(self.corpus)
        changed["decimals"].pop()
        changed["case_ids_sha256"] = campaign.fingerprint([item["id"] for key in ("records", "rejections", "decimals", "sums") for item in changed[key]])
        with self.assertRaises(AssertionError): campaign.check_corpus(changed)

    def test_binary_rational_cannot_replace_decimal_meaning(self):
        changed = deepcopy(self.corpus)
        case = next(item for item in changed["decimals"] if item["input"] == 0.1)
        case["numerator"], case["denominator"] = (0.1).as_integer_ratio()
        with self.assertRaises(AssertionError): campaign.check_corpus(changed)

    def test_forged_normalized_authority_and_fingerprint_fail(self):
        changed = deepcopy(self.corpus)
        case = changed["records"][0]
        case["normalized"]["placement_id"] = "forged"
        case["fingerprint"] = campaign.fingerprint(case["normalized"])
        with self.assertRaises(AssertionError): campaign.check_corpus(changed)

    def test_structural_declarations_retain_later_contextual_failures(self):
        by_id = {item["id"]: item for item in self.corpus["records"]}
        self.assertIn("availability/empty_common_window", by_id)
        self.assertEqual(by_id["requirement/abstract_compartment"]["normalized"]["compartment"], "abstract")
        self.assertFalse(by_id["requirement/same_recipient_false"]["normalized"]["require_same_recipient"])

    def test_relabelled_decimal_boundary_is_rejected(self):
        changed = deepcopy(self.corpus)
        changed["sums"][0]["expected"] = 1
        with self.assertRaises(AssertionError): campaign.check_corpus(changed)

    def test_missing_corpus_is_not_created_by_check(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "missing.json"
            with self.assertRaises(FileNotFoundError): campaign.main(["--output", str(target)])
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
