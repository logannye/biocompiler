"""Frozen, bounded abstract execution evidence for native migration parity."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


_PATH = Path(__file__).resolve().parents[1] / "tools/freeze_reference_execution.py"
_SPEC = importlib.util.spec_from_file_location("reference_execution_corpus_under_test", _PATH)
campaign = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(campaign)


class ReferenceExecutionCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.retained = campaign.CORPUS.read_bytes()
        cls.corpus = json.loads(cls.retained)

    def test_frozen_complete_traces_and_source_test_assertions_reproduce(self):
        rebuilt = campaign.build_corpus()
        campaign.check_corpus(rebuilt)
        self.assertEqual(campaign.encoded(rebuilt), self.retained)
        self.assertEqual(rebuilt["coverage"]["source_test_count"], 61)

    def test_all_operations_profiles_and_case_b_variants_are_mandatory(self):
        coverage = self.corpus["coverage"]
        self.assertEqual(len(coverage["supported_kinds"]), 38)
        self.assertEqual(len(coverage["extension_kinds"]), 4)
        self.assertEqual(len(coverage["reachable_kinds"]), 42)
        self.assertEqual(coverage["uncovered_kinds"], [])
        self.assertEqual(coverage["case_b_count"], 24)
        self.assertEqual(len(coverage["by_profile"]["biocompiler.behavior.v0.1"]), 38)
        self.assertEqual(len(coverage["by_profile"]["biocompiler.behavior.v0.2"]), 42)
        self.assertTrue(all(coverage["operation_witnesses"].values()))
        self.assertIn("no coupled transport", self.corpus["claim_scope"])
        self.assertEqual(len(self.corpus["literal_expectations"]), 3)
        self.assertEqual(len(self.corpus["literal_assertions"]), 3)

    def test_whole_document_is_within_native_wire_read_bounds(self):
        usage = campaign.resource_usage(self.corpus)
        self.assertLess(usage["bytes"], 2_000_000)
        self.assertLess(usage["nodes"], 50_000)
        self.assertLess(usage["depth"], 20)
        self.assertLess(usage["max_string_bytes"], 1024)
        self.assertNotIn(str(campaign.ROOT).encode(), self.retained)

    def test_stale_program_and_trace_identities_are_rejected(self):
        changed = deepcopy(self.corpus)
        changed["programs"][0]["id"] = "0" * 64
        with self.assertRaisesRegex(AssertionError, "Wrong full program identity"):
            campaign.check_corpus(changed)
        changed = deepcopy(self.corpus)
        changed["cases"][0]["trace_fingerprint"] = "0" * 64
        with self.assertRaisesRegex(AssertionError, "Wrong trace fingerprint"):
            campaign.check_corpus(changed)

    def test_complete_trace_numeric_kinds_cannot_be_forged(self):
        changed = deepcopy(self.corpus)
        case = next(case for case in changed["cases"] if case["id"] == "literal/atomic_state_bool_to_int")
        case["expected_trace"]["frames"][0]["states"]["n000004"] = False
        case["trace_fingerprint"] = campaign.fingerprint(case["expected_trace"])
        with self.assertRaisesRegex(AssertionError, "Complete trace mismatch"):
            campaign.check_corpus(changed)

    def test_evaluator_and_parser_failure_categories_are_checked(self):
        changed = deepcopy(self.corpus)
        changed["rejections"][0]["expected_code"] = "evaluation_observation"
        with self.assertRaisesRegex(AssertionError, "Wrong evaluator failure"):
            campaign.check_corpus(changed)
        changed = deepcopy(self.corpus)
        changed["parser_rejections"][0]["expected_stage"] = "evaluation"
        with self.assertRaisesRegex(AssertionError, "Wrong data parser failure"):
            campaign.check_corpus(changed)

    def test_missing_case_b_timeline_cannot_hide_in_recomputed_manifest(self):
        changed = deepcopy(self.corpus)
        removed = next(case for case in changed["cases"] if case["id"].startswith("case_b/base/"))
        changed["cases"].remove(removed)
        changed["case_b_assertions"] = [item for item in changed["case_b_assertions"] if item["case_id"] != removed["id"]]
        changed["coverage"] = campaign.coverage(changed)
        with self.assertRaisesRegex(AssertionError, "Missing original case-B"):
            campaign.check_corpus(changed)

    def test_literal_expectations_and_source_exclusions_are_retained(self):
        changed = deepcopy(self.corpus)
        changed["literal_expectations"] = changed["literal_expectations"][1:]
        changed["coverage"] = campaign.coverage(changed)
        with self.assertRaisesRegex(AssertionError, "Missing independent complete-trace"):
            campaign.check_corpus(changed)
        changed = deepcopy(self.corpus)
        changed["exclusions"] = []
        with self.assertRaisesRegex(AssertionError, "Missing source test exclusion ledger"):
            campaign.check_corpus(changed)

    def test_check_mode_cannot_create_a_missing_corpus(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "missing.json"
            with self.assertRaises(FileNotFoundError):
                campaign.main(["--output", str(output)])
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
