"""Pure Python integrity/authority checks for native lowering conformance."""

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest


PATH = Path(__file__).resolve().parents[1] / "tools/freeze_lowering.py"
SPEC = importlib.util.spec_from_file_location("lowering_corpus_under_test", PATH)
campaign = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(campaign)


class LoweringCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = campaign.CORPUS.read_bytes()
        cls.corpus = json.loads(cls.content)

    def test_exact_reproducible_current_python_oracle(self):
        rebuilt = campaign.build_corpus()
        campaign.check_corpus(rebuilt)
        self.assertEqual(campaign.encoded(rebuilt), self.content)

    def test_complete_profiles_and_declared_census(self):
        coverage = self.corpus["coverage"]
        self.assertEqual(len(self.corpus["cases"]), 31)
        self.assertEqual(len(self.corpus["rejections"]), 32)
        self.assertEqual(len(self.corpus["literal_expectations"]), 6)
        self.assertEqual(coverage["covered_kinds"], sorted(campaign.SUPPORTED_KINDS | campaign.EXTENSION_KINDS))
        self.assertEqual(coverage["uncovered_kinds"], [])
        self.assertEqual(len(coverage["by_profile"][campaign.V1]), 38)
        self.assertEqual(len(coverage["by_profile"][campaign.BEHAVIOR_V2]), 42)

    def test_whole_fixture_is_bounded_without_native_build(self):
        count, depth, size = 0, 0, 0
        pending = [(self.corpus, 0)]
        while pending:
            value, level = pending.pop()
            count += 1
            depth = max(depth, level)
            if isinstance(value, dict):
                pending.extend((item, level + 1) for item in value.values())
                size = max([size] + [len(key.encode()) for key in value])
            elif isinstance(value, list):
                pending.extend((item, level + 1) for item in value)
            elif isinstance(value, str):
                size = max(size, len(value.encode()))
        self.assertLess(len(self.content), 16 * 1024 * 1024)
        self.assertLess(count, 250_000)
        self.assertLessEqual(depth, 128)
        self.assertLessEqual(size, 4 * 1024 * 1024)
        self.assertNotIn(b"/Users/", self.content)

    def test_checker_numeric_equivalence_is_not_mislabeled_exact_production(self):
        prior = [item for item in self.corpus["cases"] if "prior_checker_candidate" in item]
        self.assertEqual(len(prior), 14)
        exact = [item for item in prior if item["prior_checker_candidate"]["exact_producer_bytes"]]
        different = [item for item in prior if not item["prior_checker_candidate"]["exact_producer_bytes"]]
        self.assertEqual(len(exact), 13)
        self.assertEqual([item["id"] for item in different], ["retained/numeric_policy_equality"])
        item = different[0]
        self.assertNotEqual(item["behavior_artifact_fingerprint"], item["prior_checker_candidate"]["artifact_fingerprint"])
        self.assertIs(type(item["expected_behavior"]["policies"]["integral_step"]["value"]), int)

    def test_all_dynamic_duration_families_retain_source_diagnostic(self):
        dynamic = [item for item in self.corpus["rejections"] if item["id"].startswith("duration/dynamic_")]
        self.assertEqual(len(dynamic), 6)
        for item in dynamic:
            self.assertEqual(item["expected_stage"], "lowering")
            self.assertEqual(item["expected_code"], "unsupported_lowering_dynamic_duration")
            self.assertEqual(item["python_error_category"], "UnsupportedBehaviorError")
            self.assertIsNotNone(item["source_node_id"])
            self.assertEqual(item["source_location"], campaign.LOCATION.to_dict())

    def test_literals_preserve_primitive_kinds_and_optional_type_fields(self):
        values = {item["case_id"]: item["expected_behavior"] for item in self.corpus["literal_expectations"]}
        self.assertIs(type(values["literal/integer"]["parameter_bindings"]["amount"]["value"]), int)
        self.assertIs(type(values["literal/float"]["parameter_bindings"]["amount"]["value"]), float)
        self.assertEqual(campaign.encoded(values["literal/signed_zero"]["parameter_bindings"]["amount"]["value"]), b"-0.0\n")
        self.assertEqual(values["literal/optional_type_fields"]["nodes"][0]["data_type"], {"kind": "scalar", "name": "Level"})
        for name in ("integer", "float", "signed_zero", "optional_type_fields"):
            value = values["literal/" + name]
            self.assertEqual(value["source_links"], {"parameter": ["parameter"]})
            self.assertEqual(value["nodes"][0]["source"], campaign.LOCATION.to_dict())

    def test_existing_python_entry_point_late_override_contract_remains_explicit(self):
        item = next(item for item in self.corpus["cases"] if item["id"] == "parameters/default_duration")
        request = campaign.BuildRequest.from_dict(item["request"])
        with self.assertRaisesRegex(campaign.bc.TypeMismatchError, "cannot accept later"):
            campaign.lower_to_behavior(request, parameters={})
        with self.assertRaisesRegex(campaign.bc.TypeMismatchError, "cannot accept later"):
            campaign.lower_to_behavior(request, parameters={"wait": campaign.bc.Duration(3)})
        output = campaign.lower_to_behavior(request.intent, parameters={"wait": campaign.bc.Duration(3)})
        expected = next(item for item in self.corpus["cases"] if item["id"] == "parameters/explicit_override")
        self.assertEqual(campaign.encoded(output.to_dict()), campaign.encoded(expected["expected_behavior"]))

    def test_corrupted_expected_artifact_and_duplicate_ids_fail(self):
        changed = deepcopy(self.corpus)
        changed["cases"][0]["behavior_fingerprint"] = "0" * 64
        with self.assertRaisesRegex(AssertionError, "Wrong lowering identity"):
            campaign.check_corpus(changed)
        changed = deepcopy(self.corpus)
        changed["cases"][0]["expected_behavior"]["name"] = "corrupted_producer_claim"
        with self.assertRaisesRegex(AssertionError, "Wrong exact producer output"):
            campaign.check_corpus(changed)
        changed = deepcopy(self.corpus)
        changed["cases"][1]["id"] = changed["cases"][0]["id"]
        with self.assertRaisesRegex(AssertionError, "Duplicate lowering"):
            campaign.check_corpus(changed)


if __name__ == "__main__":
    unittest.main()
