"""Source gap inspection cannot turn declared metadata into an admissible case."""

from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_sources import COVERAGE_FIELDS, CircuitSourceInventory
from biocompiler.verification import circuit_sources as checker
from biocompiler.verification.circuit_sources import inspect_circuit_source_readiness
from test_circuit_source_checking import inventory, review


class CircuitSourceReadinessTests(unittest.TestCase):
    def test_empty_inventory_reports_missing_case_without_inventing_one(self):
        value = CircuitSourceInventory("empty-inventory", "1", (), (), ())
        report = inspect_circuit_source_readiness(value)
        self.assertEqual(report["metadata_consistency"], "pass")
        self.assertEqual(report["case_inventory_status"], "missing")
        self.assertEqual(report["cases"], [])
        self.assertEqual(report["sources"], [])
        self.assertEqual(report["readiness"], "not_established")
        self.assertTrue(report["unresolved_acceptance_gates"])

    def test_every_field_remains_visible_with_its_actual_gap_reason(self):
        value = inventory()
        report = inspect_circuit_source_readiness(value)
        selected = report["cases"][0]
        self.assertEqual(selected["missing_field_count"], len(COVERAGE_FIELDS))
        self.assertEqual(selected["declared_provided_field_count"], 0)
        self.assertEqual(selected["context_status"], "unknown")
        self.assertEqual(
            {field["field"] for field in selected["fields"]}, COVERAGE_FIELDS
        )
        self.assertTrue(
            all(field["availability"] == "not_reviewed" for field in selected["fields"])
        )
        self.assertEqual(report["inventory_fingerprint"], value.fingerprint)

    def test_all_provided_metadata_and_human_reviews_cannot_establish_readiness(self):
        value = inventory(provided=True, with_context=True)
        value = replace(
            value,
            reviews=tuple(
                replace(item, reviewer_kind="human") for item in value.reviews
            ),
        )
        report = inspect_circuit_source_readiness(value)
        selected = report["cases"][0]
        self.assertEqual(report["metadata_consistency"], "pass")
        self.assertEqual(selected["missing_field_count"], 0)
        self.assertEqual(
            selected["declared_provided_field_count"], len(COVERAGE_FIELDS)
        )
        self.assertEqual(selected["readiness"], "not_established")
        self.assertEqual(
            selected["metadata_review_status"], "declared_current_metadata_only"
        )
        self.assertTrue(
            all(field["verification"] == "not_checked" for field in selected["fields"])
        )
        self.assertEqual(report["sources"][0]["byte_receipt"], "declared_unverified")
        self.assertEqual(report["source_bytes"], "not_checked")
        self.assertEqual(report["empirical_validation"], "unknown")
        self.assertEqual(report["human_admission"], "not_admitted")
        self.assertTrue(report["unresolved_acceptance_gates"])

    def test_case_edit_invalidates_metadata_review_and_inventory_identity(self):
        value = inventory()
        changed = replace(value, cases=(replace(value.cases[0], label="Edited label"),))
        original = inspect_circuit_source_readiness(value)
        report = inspect_circuit_source_readiness(changed)
        self.assertNotEqual(
            original["inventory_fingerprint"], report["inventory_fingerprint"]
        )
        self.assertEqual(report["metadata_consistency"], "fail")
        self.assertEqual(report["cases"][0]["metadata_review_status"], "missing")
        self.assertTrue(
            any("stale_or_unknown_case" in item for item in report["diagnostics"])
        )

    def test_duplicate_source_records_and_missing_sources_are_not_hidden(self):
        value = inventory(with_reviews=False)
        changed = replace(
            value,
            sources=(*value.sources, value.sources[0]),
            cases=(
                replace(value.cases[0], source_ids=(value.sources[0].id, "missing")),
            ),
        )
        report = inspect_circuit_source_readiness(changed)
        self.assertEqual(len(report["sources"]), 2)
        self.assertTrue(
            all(item["identity_status"] == "ambiguous" for item in report["sources"])
        )
        self.assertEqual(report["cases"][0]["missing_source_ids"], ["missing"])
        self.assertEqual(
            report["cases"][0]["ambiguous_source_ids"], [value.sources[0].id]
        )
        self.assertEqual(report["metadata_consistency"], "fail")

    def test_selected_case_requires_exact_unique_identity(self):
        value = inventory()
        report = inspect_circuit_source_readiness(value, case_id=value.cases[0].id)
        self.assertEqual(report["selected_case_id"], value.cases[0].id)
        for selected in ("missing", "", True, 1, []):
            with self.subTest(case_id=selected), self.assertRaises(SerializationError):
                inspect_circuit_source_readiness(value, case_id=selected)
        duplicate = replace(value, cases=(*value.cases, value.cases[0]))
        with self.assertRaisesRegex(SerializationError, "exactly one"):
            inspect_circuit_source_readiness(duplicate, case_id=value.cases[0].id)
        report = inspect_circuit_source_readiness(duplicate)
        self.assertEqual(len(report["cases"]), 2)
        self.assertEqual(report["metadata_consistency"], "fail")

    def test_selected_case_does_not_hide_invalid_global_inventory_metadata(self):
        value = inventory()
        unrelated_stale_review = replace(
            review(value.cases[0], "case"), id="stale", subject_fingerprint="b" * 64
        )
        value = replace(value, reviews=(*value.reviews, unrelated_stale_review))
        report = inspect_circuit_source_readiness(value, case_id=value.cases[0].id)
        self.assertEqual(report["metadata_consistency"], "fail")
        self.assertTrue(any("review:stale:" in item for item in report["diagnostics"]))

    def test_unretrieved_restricted_or_retracted_source_statuses_remain_visible(self):
        value = inventory(with_reviews=False)
        source = value.sources[0]
        changed = replace(
            source,
            access_status="restricted",
            byte_sha256=None,
            byte_size=None,
            retrieved_at=None,
            reuse_status="restricted",
            reuse_locator="Restricted fixture reuse statement",
            correction_status="retracted",
        )
        report = inspect_circuit_source_readiness(replace(value, sources=(changed,)))
        supplied = report["sources"][0]
        self.assertEqual(supplied["access_status"], "restricted")
        self.assertEqual(supplied["byte_receipt"], "missing")
        self.assertEqual(supplied["reuse_status"], "restricted")
        self.assertEqual(supplied["correction_status"], "retracted")
        self.assertEqual(report["readiness"], "not_established")

    def test_deterministic_detached_report_preserves_inert_text(self):
        value = inventory()
        selected = replace(value.cases[0], id="literal-$(not-a-command)")
        value = replace(value, cases=(selected,), reviews=())
        first = inspect_circuit_source_readiness(value)
        second = inspect_circuit_source_readiness(
            CircuitSourceInventory.from_json(value.to_json())
        )
        self.assertEqual(
            json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True)
        )
        self.assertEqual(first["cases"][0]["case_id"], selected.id)
        first["cases"][0]["fields"][0]["note"] = "Changed local inspection view"
        self.assertNotEqual(first, inspect_circuit_source_readiness(value))
        self.assertEqual(second, inspect_circuit_source_readiness(value))

    def test_raw_dict_and_saved_assessment_do_not_replace_typed_inventory(self):
        value = inventory()
        for supplied in (value.to_dict(), checker.check_circuit_sources(value), None):
            with self.assertRaises(SerializationError):
                inspect_circuit_source_readiness(supplied)

    def test_report_budget_fails_closed(self):
        value = inventory()
        assessment = checker.check_circuit_sources(value)
        with (
            patch.object(checker, "check_circuit_sources", return_value=assessment),
            patch.object(checker, "MAX_ASSESSMENT_JSON_BYTES", 100),
        ):
            with self.assertRaisesRegex(SerializationError, "byte limit"):
                inspect_circuit_source_readiness(value)


if __name__ == "__main__":
    unittest.main()
