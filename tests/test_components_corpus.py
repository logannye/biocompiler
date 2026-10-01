"""Complete retained component import and contextual declaration evidence."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("components_corpus_under_test", ROOT / "tools/freeze_components.py")
campaign = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(campaign)

class ComponentsCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = campaign.CORPUS.read_bytes()
        cls.document = json.loads(cls.content)
        cls.by_id = {x["id"]: x for x in cls.document["cases"]}

    def test_complete_corpus_is_reproducible_with_eight_types_and_thirteen_operators(self):
        rebuilt = campaign.build_corpus()
        campaign.check_corpus(rebuilt)
        self.assertEqual(campaign.encoded(rebuilt), self.content)
        self.assertEqual((len(rebuilt["cases"]), len(rebuilt["rejections"]), rebuilt["coverage"]["domain_check_count"]), (60, 112, 42))
        self.assertEqual(rebuilt["coverage"]["record_kinds"], sorted(campaign.KINDS))
        self.assertEqual(rebuilt["coverage"]["executable_operations"], sorted(campaign.OPERATIONS))
        self.assertLess(len(self.content), 700_000)
        self.assertNotIn(str(ROOT).encode(), self.content)

    def test_normalization_preserves_names_and_orders_each_typed_inventory(self):
        record = self.by_id["all_component_arrays_sort_by_id_only"]
        for key in ("ports", "identities", "evidence", "parameters", "dependencies", "capabilities", "resources"):
            self.assertEqual([x["id"] for x in record["input"][key]], ["z", "a"])
            self.assertEqual([x["id"] for x in record["normalized"][key]], ["a", "z"])
        self.assertEqual(record["normalized"]["assumptions"], ["second", "first"])
        ordered = self.by_id["input_port_order_is_authority"]["normalized"]
        self.assertEqual(ordered["synthetic_model"]["input_ports"], ["in0", "in2", "in1"])
        self.assertEqual(self.by_id["component_names_preserve_whitespace_order"]["normalized"]["id"], " component ")

    def test_none_model_unknown_resource_and_reference_scope_remain_valid_declarations(self):
        self.assertIsNone(self.by_id["historical_synthetic_no_executable_model"]["normalized"]["synthetic_model"])
        self.assertIsNone(self.by_id["resource_unknown"]["normalized"]["amount"])
        reference = self.by_id["sequence_reference_retains_parameters_evidence_domain"]["normalized"]
        self.assertTrue(reference["parameters"] and reference["evidence"] and reference["supported_domain"]["constraints"])
        self.assertEqual(reference["ports"], [])
        self.assertEqual(self.by_id["reference_arbitrary_precision_length"]["normalized"]["sequence_length"], 10**40)

    def test_contextual_checks_retain_unknown_and_scalar_numeric_spelling(self):
        unknown = self.by_id["executable_unknown_is_not_failure"]["domain_checks"]
        self.assertEqual([x["status"] for x in unknown], ["unknown", "unknown"])
        numeric = self.by_id["constant_numeric_equivalent_attribute_spelling"]["normalized"]
        self.assertIs(type(numeric["synthetic_model"]["attributes"]["value"]["canonical_value"]), float)
        deferred = self.by_id["declaration_context_validation_deferred"]
        self.assertEqual(deferred["normalized"]["attributes"]["value"], "not a typed literal")
        self.assertEqual(deferred["domain_checks"], [])
        self.assertEqual(self.by_id["executable_input"]["domain_checks"], [])

    def test_retained_case_b_pin_and_complete_component_are_not_reauthored(self):
        request = json.loads((ROOT / "tests/conformance/case-b/base/request.json").read_bytes())
        component = request["library"]["refinements"][0]["components"][0]
        self.assertEqual(campaign.canonical(component), campaign.canonical(self.by_id["retained_case_b_modeled_component"]["input"]))
        self.assertEqual(component["classification"], "modeled_component")
        self.assertIsNone(component["synthetic_model"])

    def test_truncated_or_renamed_case_cannot_hide_in_recomputed_manifest(self):
        changed = deepcopy(self.document); changed["cases"].pop(); changed["coverage"] = campaign.coverage(changed)
        with self.assertRaisesRegex(AssertionError, "Truncated"):
            campaign.check_corpus(changed)
        changed = deepcopy(self.document); changed["cases"][-1]["id"] = "hidden_case_loss"
        with self.assertRaisesRegex(AssertionError, "retained case inventory"):
            campaign.check_corpus(changed)

    def test_forged_normalization_fingerprint_and_unknown_assessment_fail(self):
        changed = deepcopy(self.document); changed["cases"][0]["normalized"]["content_fingerprint"] = "b" * 64
        changed["cases"][0]["fingerprint"] = campaign.fingerprint(changed["cases"][0]["normalized"])
        with self.assertRaisesRegex(AssertionError, "complete component record"):
            campaign.check_corpus(changed)
        changed = deepcopy(self.document); changed["cases"][0]["fingerprint"] = "0" * 64
        with self.assertRaisesRegex(AssertionError, "fingerprint"):
            campaign.check_corpus(changed)
        changed = deepcopy(self.document)
        item = next(x for x in changed["cases"] if x["id"] == "executable_unknown_is_not_failure")
        item["domain_checks"][0]["status"] = "pass"
        with self.assertRaisesRegex(AssertionError, "local assessment"):
            campaign.check_corpus(changed)

    def test_rejections_require_the_intended_category_and_actual_invalid_input(self):
        changed = deepcopy(self.document); changed["rejections"][0]["expected_code"] = "unsupported_schema"
        with self.assertRaisesRegex(AssertionError, "rejection categories"):
            campaign.check_corpus(changed)
        changed = deepcopy(self.document)
        item = next(x for x in changed["rejections"] if x["id"] == "component_unknown_field")
        item["input"].pop("extra")
        with self.assertRaisesRegex(AssertionError, "Accepted negative"):
            campaign.check_corpus(changed)

    def test_check_only_never_creates_missing_corpus(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.json"
            with self.assertRaises(FileNotFoundError):
                campaign.main(["--check", "--output", str(path)])
            self.assertFalse(path.exists())

if __name__ == "__main__":
    unittest.main()
