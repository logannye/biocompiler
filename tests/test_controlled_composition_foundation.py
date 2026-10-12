"""Adversarial tests of representation checks, never a receptor simulator."""
from __future__ import annotations

from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest

from tools import check_controlled_composition_foundation as foundation


class ControlledCompositionFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = foundation.read(foundation.ROOT / foundation.PROFILE)
        cls.corpus = foundation.read(foundation.ROOT / foundation.CORPUS)

    def reject(self, mutate):
        corpus = deepcopy(self.corpus)
        mutate(corpus)
        with self.assertRaises(foundation.FoundationError):
            foundation.validate(self.profile, corpus)

    def test_oversized_integer_rejects_before_conversion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'integer.json'
            path.write_text('{"count":' + '1' * 5000 + '}')
            with self.assertRaisesRegex(foundation.FoundationError, 'integer exceeds'):
                foundation.read(path)
        with self.assertRaisesRegex(foundation.FoundationError, 'integer exceeds'):
            foundation.bounded({'count': 10 ** 5000})

    def test_closed_corpus_does_not_claim_semantic_execution(self):
        result = foundation.validate(self.profile, self.corpus)
        self.assertEqual(result["case_count"], 41)
        self.assertIs(result["acceptance"], False)
        self.assertEqual(result["semantic_execution"], "not_performed")
        self.assertEqual(result["native_status"], "not_run")
        self.assertGreater(result["expected_verdict_counts"]["violates"], 0)

    def test_semantically_wrong_candidate_is_still_a_valid_negative_specification(self):
        case = next(row for row in self.corpus["cases"] if row["id"] == "constant_on")
        self.assertEqual(case["expected_verdict"], "violates")
        foundation.validate_case(case)

    def test_saved_pass_labels_cannot_upgrade_declarative_inventory(self):
        for key, value in (("acceptance", True), ("acceptance", 0), ("native_status", "passed"),
                           ("status", "verified"), ("fixture_kind", "empirically_qualified")):
            with self.subTest(key=key, value=value):
                self.reject(lambda corpus: corpus.__setitem__(key, value))

    def test_expected_result_is_not_allowed_to_be_executed_result(self):
        self.reject(lambda corpus: corpus["cases"][0].__setitem__("observed_verdict", "satisfies"))

    def test_complete_named_inventory_cannot_silently_shrink(self):
        def mutation(corpus):
            corpus["cases"].pop()
            corpus["case_inventory"].pop()
        self.reject(mutation)

    def test_duplicate_and_reordered_cases_reject(self):
        self.reject(lambda corpus: corpus["cases"].append(deepcopy(corpus["cases"][0])))
        self.reject(lambda corpus: corpus["cases"].reverse())

    def test_unknown_is_evidence_not_a_physical_band(self):
        self.reject(lambda corpus: corpus["cases"][0]["candidate_activity"][0].__setitem__("band", "unknown"))
        corpus = deepcopy(self.corpus)
        corpus["cases"][0]["candidate_activity"][0]["evidence"] = "missing"
        self.assertIs(foundation.validate(self.profile, corpus)["acceptance"], False)

    def test_physical_inputs_do_not_accept_evidence_literals(self):
        self.reject(lambda corpus: corpus["cases"][0]["input_history"][0].__setitem__("controller", "missing"))
        self.reject(lambda corpus: corpus["cases"][0]["input_history"][0]["availability"].__setitem__("protein_a", "unknown"))

    def test_tick_booleans_and_gaps_reject(self):
        self.reject(lambda corpus: corpus["cases"][0]["input_history"][0].__setitem__("tick", False))
        self.reject(lambda corpus: corpus["cases"][0]["candidate_activity"].pop())
        self.reject(lambda corpus: corpus["cases"][0]["domain"].__setitem__("horizon_tick", 9))

    def test_duplicate_json_fields_and_floats_reject(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            for raw in ('{"a":1,"a":2}', '{"a":1.5}', '{"a":NaN}', '{"a":Infinity}'):
                with self.subTest(raw=raw):
                    path.write_text(raw)
                    with self.assertRaises(foundation.FoundationError):
                        foundation.read(path)

    def test_unknown_fields_and_perturbations_reject(self):
        self.reject(lambda corpus: corpus.__setitem__("extra", None))
        self.reject(lambda corpus: corpus["cases"][0]["perturbation"].update(target="native", operation="execute", value="command"))

    def test_known_perturbation_operations_cannot_cross_target_boundaries(self):
        for target, operation, value in (
            ("candidate", "replace", "fixture.foreign_controlled_pair"),
            ("saved_report", "substitute_and_repin_complete_local_authority", "fixture.foreign_controlled_pair"),
            ("candidate_activity", "clear_executor_controller_on_encounter_reset", True),
            ("verification_budget.max_work", "substitute", 1),
        ):
            with self.subTest(target=target, operation=operation):
                self.reject(lambda corpus: corpus["cases"][0]["perturbation"].update(
                    target=target, operation=operation, value=value))

    def test_perturbation_value_shapes_are_closed(self):
        for target, operation, invalid_values in (
            ("candidate_activity", "replace", ("unknown", None, {"band": "active"})),
            ("candidate_state", "clear_executor_controller_on_encounter_reset", (1, False, "true")),
            ("candidate_material_members", "replace", ("rna_a", ["rna_c"], ["rna_a"] * 4, [True])),
            ("candidate", "substitute", ({"identity": "foreign"}, "", 1)),
            ("saved_report", "substitute", ([], None)),
            ("bundle", "substitute", (False, {})),
            ("original_controller", "replace", ({"controller": "foreign"}, "")),
            ("deployment.same_recipient", "replace", (0, "false", None)),
            ("source.activity_endpoint", "replace", ({"endpoint": "killing"}, "")),
            ("source.initial_activity", "replace", ("unknown", True)),
            ("verification_domain.suffix_ticks", "replace", (True, -1, foundation.MAX_TICK + 1)),
            ("verification_budget.max_work", "replace", (True, 0, {}, foundation.MAX_TICK + 1)),
        ):
            for value in invalid_values:
                with self.subTest(target=target, value=value):
                    self.reject(lambda corpus: corpus["cases"][0]["perturbation"].update(
                        target=target, operation=operation, value=value))

    def test_invalid_original_requests_remain_declarative_perturbations(self):
        for case_id in ("different_recipient", "unsupported_initial_active", "incomplete_suffix",
                        "missing_material_member", "extra_material_member"):
            with self.subTest(case_id=case_id):
                case = next(row for row in self.corpus["cases"] if row["id"] == case_id)
                self.assertNotEqual(case["expected_verdict"], "satisfies")
                foundation.validate_case(case)

    def test_file_reader_rejects_nonregular_inputs_without_following_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            regular = root / "regular.json"
            regular.write_text('{"status":"declarative"}')
            self.assertEqual(foundation.read(regular), {"status": "declarative"})
            link = root / "linked.json"
            link.symlink_to(regular)
            broken_link = root / "broken.json"
            broken_link.symlink_to(root / "missing.json")
            for path in (root, link, broken_link):
                with self.subTest(path=path.name), self.assertRaises(foundation.FoundationError):
                    foundation.read(path)
            if hasattr(os, "mkfifo"):
                fifo = root / "input.fifo"
                os.mkfifo(fifo)
                with self.assertRaises(foundation.FoundationError):
                    foundation.read(fifo)

    def test_source_and_mechanism_delays_remain_distinct_inputs(self):
        case = next(row for row in self.corpus["cases"] if row["id"] == "response_before_deadline")
        self.assertNotEqual(case["original_conditions"]["source_deadlines"], case["original_conditions"]["model_delays"])
        foundation.validate_case(case)

    def test_missing_evidence_inventory_and_exhaustive_claim_reject(self):
        self.reject(lambda corpus: corpus["cases"][0]["input_history"][0]["evidence"].pop("controller"))
        self.reject(lambda corpus: corpus["coverage"].__setitem__("exhaustive_domain_execution", "passed"))

    def test_resource_bounds_apply_before_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "oversize.json"
            for raw in (b"", b" " * (foundation.MAX_BYTES + 1)):
                path.write_bytes(raw)
                with self.assertRaises(foundation.FoundationError):
                    foundation.read(path)
        corpus = deepcopy(self.corpus)
        corpus["cases"][0]["purpose"] = "x" * 4097
        with self.assertRaises(foundation.FoundationError):
            foundation.validate(self.profile, corpus)


if __name__ == "__main__":
    unittest.main()
