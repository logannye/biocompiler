"""Integrity and authority checks for the independent construction campaign."""
from collections import Counter
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "tools/freeze_construction_check.py"
SPEC = importlib.util.spec_from_file_location("construction_check_campaign", PATH)
campaign = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(campaign)
MANIFEST = "b551a905ddc80fb4a6272612381a8f9111c44df66f4048be0bcc8cc188f7e840"


class ConstructionCheckCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index, cls.documents = campaign.load()
        cls.cases = {case["id"]: case for case in cls.index["cases"]}

    def test_exact_manifest_and_complete_document_inventory(self):
        self.assertEqual(campaign.fingerprint(self.index), MANIFEST)
        self.assertEqual((len(self.cases), len(self.documents)), (83, 219))
        self.assertEqual(campaign.encoded(self.index), campaign.CORPUS.read_bytes())
        self.assertEqual({p.name for p in campaign.DOCUMENTS.glob("*.json")},
                         {identity + ".json" for identity in self.documents})
        total = len(campaign.CORPUS.read_bytes())
        for entry in self.index["documents"]:
            raw = self.documents[entry["id"]]
            data = (campaign.DOCUMENTS / (entry["id"] + ".json")).read_bytes()
            self.assertEqual(data, campaign.encoded(raw))
            self.assertEqual(len(data), entry["bytes"])
            self.assertEqual(campaign.fingerprint(raw), entry["id"])
            self.assertLessEqual(len(data), 4_000_000)
            campaign.bounds(raw, 4_000_000)
            total += len(data)
        self.assertEqual(total, 10_525_823)
        self.assertLess(total, 16 * 1024 * 1024)

    def test_complete_case_b_authority_and_candidates_are_preserved(self):
        self.assertEqual({entry["variant"] for entry in self.index["coverage"]["case_b"]},
                         {"base", "parameter-default", "parameter-override"})
        for entry in self.index["coverage"]["case_b"]:
            source = json.loads((campaign.ROOT / "tests/conformance/case-b" / entry["variant"] / "candidate.json").read_bytes())
            for key in entry["path"]:
                source = source[key]
            case = self.cases[entry["id"]]
            for key in ("request", "candidate"):
                self.assertEqual(campaign.encoded(source[key]), campaign.encoded(self.documents[case[key]]))
            self.assertEqual(case["origin"], "complete_retained_case_b")

    def test_actual_operations_outcomes_and_source_assertion_ledger(self):
        operations = {step["operation"]["schema_version"] for case in self.cases.values()
                      for step in self.documents[case["request"]]["steps"]}
        self.assertEqual(operations, {cls.schema_version for cls in campaign.OPERATION_TYPES})
        self.assertEqual(sorted(operations), self.index["coverage"]["operations"])
        outcomes = Counter(self.documents[case["assessment"]]["outcome"] for case in self.cases.values())
        self.assertEqual(outcomes, {"pass": 40, "fail": 34, "unsupported": 8, "unknown": 1})
        ledger = self.index["coverage"]["methods"]
        self.assertEqual(len(ledger), 51)
        self.assertEqual({entry["method"] for entry in ledger if entry["status"] == "separate_budget_literal"},
                         set(campaign.EXCLUDED))
        self.assertEqual(sum(entry["retained_calls"] for entry in ledger), 80)
        self.assertTrue(all(entry["status"] == "separate_budget_literal" or
                            entry["status"] == "source_assertions_executed" for entry in ledger))

    def test_every_assessment_binds_complete_external_authority(self):
        for case in self.cases.values():
            report = self.documents[case["assessment"]]
            self.assertEqual(report["request_fingerprint"], case["request"])
            self.assertEqual(report["candidate_fingerprint"], case["candidate"])
            self.assertEqual(report["reconstructed_fingerprint"], case["reconstructed"])
            self.assertEqual(report["complete"], report["outcome"] == "pass")
            self.assertEqual(report["biological_function"], "unestablished")
            self.assertEqual(report["human_therapeutic_admission"], "not_admitted")
            if report["outcome"] == "pass":
                self.assertEqual(case["candidate"], case["reconstructed"])
                self.assertEqual(report["diagnostics"], [])

    def test_fresh_source_checker_distinguishes_rehashed_candidate_from_expected(self):
        from biocompiler.verification.circuit_construction import verify_circuit_construction_assessment
        for outcome in ("pass", "fail", "unsupported", "unknown"):
            case = next(case for case in self.cases.values() if self.documents[case["assessment"]]["outcome"] == outcome)
            request = campaign.CircuitConstructionRequest.from_dict(self.documents[case["request"]])
            candidate = campaign.ConstructionCandidate.from_dict(self.documents[case["candidate"]])
            expected = campaign.reconstruct_for_check(request)
            self.assertEqual(expected.to_dict(), self.documents[case["reconstructed"]])
            fresh = campaign.check_circuit_construction(candidate, expected_request=request)
            self.assertEqual(fresh.to_dict(), self.documents[case["assessment"]])
            verify_circuit_construction_assessment(fresh, candidate, expected_request=request)

    def test_historical_imports_and_fresh_replay_reject_stale_authority(self):
        from biocompiler.verification.circuit_construction import verify_circuit_construction_assessment
        self.assertEqual(len(self.index["assessment_rejections"]), 28)
        for case in self.index["assessment_rejections"]:
            raw = campaign.apply_edits(self.documents[case["source"]], case["edits"])
            with self.assertRaises(campaign.SerializationError):
                campaign.CircuitConstructionAssessment.from_dict(raw)
        self.assertEqual(len(self.index["replay_rejections"]), 3)
        for case in self.index["replay_rejections"]:
            source = self.cases[case["source"]]
            request = campaign.CircuitConstructionRequest.from_dict(self.documents[source["request"]])
            candidate = campaign.ConstructionCandidate.from_dict(self.documents[source["candidate"]])
            historical = campaign.CircuitConstructionAssessment.from_dict(self.documents[case["assessment"]])
            with self.assertRaises(campaign.SerializationError):
                verify_circuit_construction_assessment(historical, candidate, expected_request=request)

    def test_fixture_corruption_fails_before_semantic_execution(self):
        bad = deepcopy(self.index)
        bad["cases"].pop()
        with self.assertRaisesRegex(AssertionError, "case census"):
            campaign.check_corpus(bad, self.documents)
        bad = deepcopy(self.index)
        bad["cases"][1]["id"] = bad["cases"][0]["id"]
        with self.assertRaisesRegex(AssertionError, "Duplicate"):
            campaign.check_corpus(bad, self.documents)
        documents = dict(self.documents)
        documents.pop(next(iter(documents)))
        with self.assertRaisesRegex(AssertionError, "Missing or extra"):
            campaign.check_corpus(self.index, documents)
        with self.assertRaises(KeyError):
            campaign.apply_edits({}, [{"op": "set", "path": ["absent", "nested"], "value": 0}])


if __name__ == "__main__":
    unittest.main()
