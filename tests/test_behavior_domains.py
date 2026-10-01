"""Retained Python authority for the hosted Behavior import conformance tests."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


_PATH = Path(__file__).resolve().parents[1] / "tools/freeze_behavior_domains.py"
_SPEC = importlib.util.spec_from_file_location("behavior_domains_under_test", _PATH)
campaign = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(campaign)


class BehaviorDomainCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.retained = campaign.CORPUS.read_bytes()
        cls.corpus = json.loads(cls.retained)

    def test_frozen_documents_are_reproducible_python_lowering_results(self):
        rebuilt = campaign.build_corpus()
        campaign.check_corpus(rebuilt)
        self.assertEqual(campaign.encoded(rebuilt), self.retained)
        self.assertEqual(len(rebuilt["cases"]), 7)
        self.assertLess(len(self.retained), 4_000_000)

    def test_profiles_cover_all_declared_operations_without_promoting_scope(self):
        coverage = self.corpus["coverage"]
        self.assertEqual(len(coverage["supported_kinds"]), 38)
        self.assertEqual(len(coverage["extension_kinds"]), 4)
        self.assertEqual(len(coverage["by_profile"][campaign.SCHEMA_VERSION]), 38)
        self.assertEqual(len(coverage["by_profile"][campaign.BEHAVIOR_V2]), 42)
        self.assertEqual(coverage["uncovered_kinds"], [])
        self.assertEqual(len({case["id"] for case in self.corpus["cases"]}), 7)
        self.assertIn("no reference-execution parity", self.corpus["claim_scope"])
        for case in self.corpus["cases"]:
            for item in case["behavior"]["nodes"] + case["behavior"]["requirements"]:
                self.assertIsNone(item["source"])

    def test_stale_expected_identity_and_counts_are_rejected(self):
        for field, value, message in (
            ("fingerprint", "0" * 64, "Wrong Behavior fingerprint"),
            ("source_fingerprint", "0" * 64, "Wrong source fingerprint"),
            ("operation_counts", {}, "Wrong operation counts"),
        ):
            with self.subTest(field=field):
                changed = deepcopy(self.corpus)
                changed["cases"][0][field] = value
                with self.assertRaisesRegex(AssertionError, message):
                    campaign.check_corpus(changed)

    def test_declared_coverage_cannot_hide_missing_cases(self):
        changed = deepcopy(self.corpus)
        changed["cases"] = changed["cases"][:-1]
        with self.assertRaisesRegex(AssertionError, "Coverage manifest disagrees"):
            campaign.check_corpus(changed)
        changed["coverage"] = campaign.coverage_for(changed["cases"])
        with self.assertRaisesRegex(AssertionError, "operation coverage is incomplete"):
            campaign.check_corpus(changed)

    def test_check_mode_does_not_create_a_missing_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "missing.json"
            with self.assertRaises(FileNotFoundError):
                campaign.main(["--output", str(output)])
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
