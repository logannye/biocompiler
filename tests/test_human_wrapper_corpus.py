"""Retained complete human authority; structural import never grants admission."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

_PATH = Path(__file__).resolve().parents[1] / "tools/freeze_human_wrappers.py"
_SPEC = importlib.util.spec_from_file_location("human_wrapper_corpus_under_test", _PATH)
campaign = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(campaign)


class HumanWrapperCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.retained = campaign.CORPUS.read_bytes()
        cls.corpus = json.loads(cls.retained)

    def test_complete_corpus_reproduces_with_all_python_invariants(self):
        rebuilt = campaign.build_corpus()
        campaign.check_corpus(rebuilt)
        self.assertEqual(campaign.encoded(rebuilt), self.retained)
        self.assertEqual(rebuilt["coverage"]["positive_count"], 40)
        self.assertEqual(rebuilt["coverage"]["rejection_count"], 244)
        self.assertEqual(rebuilt["coverage"]["kinds"], sorted(campaign.PARSERS))

    def test_every_wrapper_preserves_full_circuit_authority(self):
        for kind in campaign.WRAPPERS:
            row = next(row for row in self.corpus["records"] if row["id"] == "circuit/" + kind)
            circuit = campaign.CircuitRequest.from_dict(row["input"])
            source = circuit.profile.source_request
            self.assertEqual(campaign.source_kind(source), kind)
            self.assertEqual(source.to_dict(), row["normalized"]["profile"]["source_request"])
            if kind != "build":
                self.assertTrue(campaign.evidence_paths(source))

    def test_semantic_and_full_identity_remain_distinct(self):
        by_id = {row["id"]: row for row in self.corpus["records"]}
        original, moved = by_id["base/behavior_request"], by_id["behavior/source_only_relocation"]
        self.assertEqual(original["fingerprint"], moved["fingerprint"])
        self.assertNotEqual(original["artifact_fingerprint"], moved["artifact_fingerprint"])
        self.assertNotEqual(original["fingerprint"], by_id["behavior/float_duration"]["fingerprint"])
        self.assertNotEqual(original["fingerprint"], by_id["behavior/alpha_renamed"]["fingerprint"])

    def test_intended_wrapper_failures_have_valid_nested_authority(self):
        for row in self.corpus["rejections"]:
            if row["expected_stage"] != "wrapper":
                continue
            data, kind = row["input"], row["kind"]
            with self.subTest(case=row["id"]):
                if kind == "behavior_request":
                    campaign.bc.BuildRequest.from_dict(data["build_request"])
                    campaign.bc.ConditionalSecretionContract.from_dict(data["contract"])
                elif kind == "deployment_request":
                    campaign.bc.HumanBehaviorRequest.from_dict(data["behavior_request"])
                    campaign.bc.DeploymentContract.from_dict(data["deployment"])
                else:
                    self.assertEqual(kind, "acceptance_request")
                    campaign.bc.HumanDeploymentRequest.from_dict(data["deployment_request"])
                    campaign.bc.HumanAcceptanceContract.from_dict(data["acceptance"])

    def test_unknown_and_unimplemented_declarations_remain_importable(self):
        ids = {row["id"] for row in self.corpus["records"]}
        self.assertTrue({"deployment/unknown_timing", "deployment/required_co_payload_unimplemented",
                         "deployment/structurally_valid_late_onset"} <= ids)
        row = next(row for row in self.corpus["records"] if row["id"] == "base/acceptance_request")
        self.assertEqual(row["normalized"]["acceptance"]["shutdown"]["actuator_support"], "unimplemented")
        self.assertFalse(row["normalized"]["acceptance"]["shutdown"]["overrides_source_guard"])
        self.assertIn("human admission remain unimplemented", self.corpus["claim_scope"])

    def test_hash_normalization_literals_and_census_cannot_be_forged(self):
        for field, value, message in (("fingerprint", "0" * 64, "Authority identity drift"),
                                      ("normalized", {}, "Normalized authority drift")):
            changed = deepcopy(self.corpus)
            changed["records"][0][field] = value
            with self.assertRaisesRegex(AssertionError, message): campaign.check_corpus(changed)
        changed = deepcopy(self.corpus); changed["literal_expectations"].pop()
        with self.assertRaisesRegex(AssertionError, "Missing independent literal"): campaign.check_corpus(changed)
        changed = deepcopy(self.corpus); changed["coverage"]["positive_count"] -= 1
        with self.assertRaisesRegex(AssertionError, "Positive census drift"): campaign.check_corpus(changed)

    def test_full_document_obeys_native_budget_and_has_no_checkout_paths(self):
        usage = campaign.check_corpus(self.corpus)
        self.assertLess(usage["bytes"], 5_000_000)
        self.assertLess(usage["values"], 100_000)
        self.assertLess(usage["depth"], 20)
        self.assertNotIn(str(campaign.ROOT).encode(), self.retained)
        self.assertEqual(self.corpus["coverage"]["independent_literal_count"], 4)

    def test_check_mode_cannot_create_missing_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "missing.json"
            with self.assertRaises(FileNotFoundError): campaign.main(["--output", str(output), "--check"])
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
