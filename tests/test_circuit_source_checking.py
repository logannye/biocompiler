"""Metadata-only relationship and authority checks using invented declarations."""

import ast
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import unittest
from unittest.mock import patch

from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_profile import HumanExperimentContext
from biocompiler.ir.circuit_sources import (
    COVERAGE_FIELDS,
    CircuitSourceCase,
    CircuitSourceInventory,
    SourceDocument,
    SourceGap,
    SourceReview,
)
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.verification import circuit_sources as checker
from biocompiler.verification.circuit_sources import (
    CircuitSourcesAssessment,
    check_circuit_sources,
    verify_circuit_sources,
)
from biocompiler.verification.evidence import CheckOutcome


def document(*, id="fixture.paper", retrieved=True):
    return SourceDocument(
        id,
        "fixture-version-1",
        "Invented metadata fixture; no scientific source was retrieved",
        "https://example.invalid/fixture",
        "article",
        "retrieved" if retrieved else "not_retrieved",
        "unreviewed",
        None,
        "not_checked",
        "a" * 64 if retrieved else None,
        123 if retrieved else None,
        "2026-09-30T00:00:00Z" if retrieved else None,
    )


def byte_pin(source):
    return PinnedIdentity("source", source.id, source.version, source.byte_sha256)


def context(source):
    return HumanExperimentContext(
        "human_cell_line",
        "nonimmune",
        "Invented human cell context declaration",
        "Not established in fixture",
        "cytoplasm",
        "not_reported",
        (byte_pin(source),),
        "Invented context locator",
        ("No real assay conditions inspected",),
    )


def case(source, *, provided=False, with_context=False):
    return CircuitSourceCase(
        "fixture.case",
        "adar_human",
        "Metadata-only test case",
        (source.id,),
        tuple(
            SourceGap(
                field,
                "provided" if provided else "not_reviewed",
                "Availability is only a declaration; no source content checked.",
                (source.id,) if provided else (),
                "Invented record locator" if provided else None,
                (byte_pin(source),) if provided else (),
            )
            for field in sorted(COVERAGE_FIELDS)
        ),
        context(source) if with_context else None,
    )


def review(subject, kind):
    return SourceReview(
        "fixture.review." + kind,
        kind,
        subject.fingerprint,
        "software_agent",
        "invented-reviewer",
        "Fixture metadata consistency inspection only",
        ("No source-byte, molecular or empirical validation performed",),
    )


def inventory(*, provided=False, with_context=False, with_reviews=True):
    source = document()
    selected_case = case(source, provided=provided, with_context=with_context)
    return CircuitSourceInventory(
        "fixture.inventory",
        "1",
        (source,),
        (selected_case,),
        (review(source, "source"), review(selected_case, "case"))
        if with_reviews
        else (),
    )


def change_gap(selected_case, field, **changes):
    return replace(
        selected_case,
        coverage=tuple(
            replace(gap, **changes) if gap.field == field else gap
            for gap in selected_case.coverage
        ),
    )


class CircuitSourceCheckingTests(unittest.TestCase):
    def setUp(self):
        self.inventory = inventory()
        self.assessment = check_circuit_sources(self.inventory)

    def test_assessment_indentation_is_bounded_before_encoding(self):
        for indent in (True, False, -1, 9, 10**100, 1.0, " ", " " * 10000, []):
            with (
                self.subTest(indent_type=type(indent).__name__),
                patch.object(
                    CircuitSourcesAssessment,
                    "to_dict",
                    side_effect=AssertionError(
                        "Allocated before indentation validation"
                    ),
                ),
                self.assertRaisesRegex(SerializationError, "indentation"),
            ):
                self.assessment.to_json(indent=indent)
        for indent in (None, 0, 1, 8):
            self.assertEqual(
                CircuitSourcesAssessment.from_json(
                    self.assessment.to_json(indent=indent)
                ),
                self.assessment,
            )

    def test_assessment_character_preflight_precedes_utf8_allocation(self):
        class EncodingTrap(str):
            def encode(self, *args, **kwargs):
                raise AssertionError("Oversized assessment encoded before preflight")

        with patch.object(checker, "MAX_ASSESSMENT_JSON_BYTES", 32):
            with self.assertRaisesRegex(SerializationError, "byte limit"):
                CircuitSourcesAssessment.from_json(EncodingTrap(" " * 33))

    def test_assessment_streaming_budget_stops_before_remaining_chunks(self):
        def chunks(*args, **kwargs):
            yield " " * 10000
            raise AssertionError("Encoder continued after assessment budget")

        with (
            patch.object(checker, "MAX_ASSESSMENT_JSON_BYTES", 10000),
            patch.object(checker.json.JSONEncoder, "iterencode", side_effect=chunks),
            self.assertRaisesRegex(SerializationError, "publication newline"),
        ):
            self.assessment.to_json()

    def assert_failed_with(self, value, code):
        result = check_circuit_sources(value)
        self.assertIs(result.outcome, CheckOutcome.FAIL, result.diagnostics)
        self.assertTrue(
            any(code in item for item in result.diagnostics), result.diagnostics
        )
        self.assertEqual(result.inventory, value)
        return result

    def test_honest_gaps_are_consistent_without_readiness_or_retrieval_claims(self):
        result = self.assessment
        self.assertIs(result.outcome, CheckOutcome.PASS)
        self.assertEqual(result.claim_scope, "metadata_consistency_only")
        self.assertEqual(result.molecular_readiness, "unassessed")
        self.assertEqual(result.empirical_validation, "unknown")
        self.assertEqual(result.human_admission, "not_admitted")
        self.assertEqual(result.source_bytes, "not_checked")
        summary = result.case_summaries[0]
        self.assertEqual(summary["context_status"], "unknown")
        self.assertEqual(len(summary["gaps"]), 9)
        self.assertFalse(summary["declared_provided_fields"])
        self.assertEqual({item["status"] for item in summary["gaps"]}, {"not_reviewed"})

    def test_empty_inventory_is_only_consistent_metadata(self):
        empty = CircuitSourceInventory("empty.fixture", "1", (), (), ())
        result = check_circuit_sources(empty)
        self.assertIs(result.outcome, CheckOutcome.PASS)
        self.assertEqual(result.case_summaries, ())
        self.assertEqual(result.molecular_readiness, "unassessed")

    def test_all_provided_fields_and_context_do_not_establish_completeness(self):
        value = inventory(provided=True, with_context=True)
        result = check_circuit_sources(value)
        self.assertIs(result.outcome, CheckOutcome.PASS)
        summary = result.case_summaries[0]
        self.assertEqual(set(summary["declared_provided_fields"]), COVERAGE_FIELDS)
        self.assertEqual(summary["gaps"], ())
        self.assertEqual(summary["context_status"], "declared_unverified")
        self.assertEqual(result.source_bytes, "not_checked")
        self.assertEqual(result.molecular_readiness, "unassessed")
        self.assertEqual(result.empirical_validation, "unknown")
        self.assertEqual(result.human_admission, "not_admitted")

    def test_source_gap_states_are_retained_without_collapsing_unknowns(self):
        selected_case = self.inventory.cases[0]
        for status in (
            "not_reviewed",
            "not_reported",
            "unavailable",
            "ambiguous",
            "conflicting",
        ):
            value = replace(
                self.inventory,
                cases=(change_gap(selected_case, "chemistry", status=status),),
                reviews=(),
            )
            result = check_circuit_sources(value)
            self.assertIs(result.outcome, CheckOutcome.PASS)
            chemistry = next(
                item
                for item in result.case_summaries[0]["gaps"]
                if item["field"] == "chemistry"
            )
            self.assertEqual(chemistry["status"], status)
            self.assertEqual(result.molecular_readiness, "unassessed")

    def test_url_and_metadata_fingerprint_do_not_supply_source_byte_receipt(self):
        source = document(retrieved=False)
        selected_case = case(source)
        value = CircuitSourceInventory(
            "unretrieved.fixture", "1", (source,), (selected_case,), ()
        )
        self.assertIs(check_circuit_sources(value).outcome, CheckOutcome.PASS)
        pretend_pin = PinnedIdentity(
            "source", source.id, source.version, source.fingerprint
        )
        changed = change_gap(
            selected_case,
            "component_authority",
            status="provided",
            source_ids=(source.id,),
            locator="Metadata is not source content",
            record_pins=(pretend_pin,),
        )
        self.assert_failed_with(
            replace(value, cases=(changed,)), "source_byte_receipt_missing"
        )

    def test_unknown_case_source_is_a_retained_failure(self):
        selected_case = replace(self.inventory.cases[0], source_ids=("missing.source",))
        self.assert_failed_with(
            replace(self.inventory, cases=(selected_case,), reviews=()),
            "unknown_source:missing.source",
        )

    def test_coverage_source_must_belong_to_case_and_inventory(self):
        other = document(id="other.source")
        selected_case = self.inventory.cases[0]
        for source_id, sources, expected in (
            (other.id, (*self.inventory.sources, other), "source_not_in_case"),
            ("missing.source", self.inventory.sources, "unknown_source"),
        ):
            changed = change_gap(selected_case, "chemistry", source_ids=(source_id,))
            self.assert_failed_with(
                replace(self.inventory, sources=sources, cases=(changed,), reviews=()),
                expected,
            )

    def test_provided_coverage_requires_a_pin_for_every_declared_source(self):
        value = inventory(provided=True, with_reviews=False)
        other = document(id="other.source")
        selected_case = replace(
            value.cases[0], source_ids=(value.sources[0].id, other.id)
        )
        selected_case = change_gap(
            selected_case, "chemistry", source_ids=selected_case.source_ids
        )
        self.assert_failed_with(
            replace(value, sources=(*value.sources, other), cases=(selected_case,)),
            "provided_sources_require_byte_receipt_pins",
        )

    def test_pins_require_source_ids_version_and_declared_byte_hash(self):
        value = inventory(provided=True, with_reviews=False)
        original_pin = byte_pin(value.sources[0])
        for pin, diagnostic in (
            (replace(original_pin, id="missing.source"), "unknown_pin_source"),
            (
                replace(original_pin, version="different-version"),
                "pin_version_mismatch",
            ),
            (
                replace(original_pin, content_fingerprint="b" * 64),
                "pin_byte_receipt_mismatch",
            ),
            (
                replace(original_pin, content_fingerprint=value.sources[0].fingerprint),
                "pin_byte_receipt_mismatch",
            ),
        ):
            changed = change_gap(value.cases[0], "observations", record_pins=(pin,))
            self.assert_failed_with(replace(value, cases=(changed,)), diagnostic)

    def test_unknown_gap_with_pin_still_requires_a_real_binding(self):
        selected_case = change_gap(
            self.inventory.cases[0],
            "observations",
            record_pins=(byte_pin(self.inventory.sources[0]),),
        )
        self.assert_failed_with(
            replace(self.inventory, cases=(selected_case,), reviews=()),
            "pin_source_not_in_declared_sources",
        )

    def test_context_pin_cannot_use_document_metadata_hash(self):
        value = inventory(with_context=True, with_reviews=False)
        source, selected_case = value.sources[0], value.cases[0]
        bad_pin = replace(byte_pin(source), content_fingerprint=source.fingerprint)
        changed = replace(
            selected_case, context=replace(selected_case.context, sources=(bad_pin,))
        )
        self.assert_failed_with(
            replace(value, cases=(changed,)), "context:pin_byte_receipt_mismatch"
        )

    def test_context_source_must_belong_to_case(self):
        value = inventory(with_context=True, with_reviews=False)
        other = document(id="other.source")
        changed = replace(value.cases[0], context=context(other))
        self.assert_failed_with(
            replace(value, sources=(*value.sources, other), cases=(changed,)),
            "context:pin_source_not_in_declared_sources",
        )

    def test_duplicate_source_case_and_review_ids_fail_without_dropping_records(self):
        for collection in ("sources", "cases", "reviews"):
            records = getattr(self.inventory, collection)
            value = replace(self.inventory, **{collection: (*records, records[0])})
            result = self.assert_failed_with(
                value, "duplicate_" + collection[:-1] + "_id"
            )
            restored = CircuitSourcesAssessment.from_json(result.to_json())
            self.assertEqual(
                len(getattr(restored.inventory, collection)), len(records) + 1
            )
            self.assertIs(
                verify_circuit_sources(restored, expected_inventory=value).outcome,
                CheckOutcome.FAIL,
            )

    def test_source_or_case_edit_invalidates_existing_review(self):
        changed_source = replace(
            self.inventory.sources[0], title="Edited source metadata"
        )
        changed_case = change_gap(
            self.inventory.cases[0], "controls", note="Edited coverage note"
        )
        self.assert_failed_with(
            replace(self.inventory, sources=(changed_source,)),
            "stale_or_unknown_source_fingerprint",
        )
        self.assert_failed_with(
            replace(self.inventory, cases=(changed_case,)),
            "stale_or_unknown_case_fingerprint",
        )

    def test_review_subject_kind_and_metadata_hash_are_both_authoritative(self):
        original = next(
            item for item in self.inventory.reviews if item.subject_kind == "source"
        )
        for changed in (
            replace(original, subject_kind="case"),
            replace(
                original, subject_fingerprint=self.inventory.sources[0].byte_sha256
            ),
        ):
            self.assert_failed_with(
                replace(self.inventory, reviews=(changed,)), "stale_or_unknown_"
            )

    def test_retrieval_and_review_declarations_do_not_change_evidence_dimensions(self):
        for correction in ("not_checked", "none_known", "corrected", "retracted"):
            source = replace(self.inventory.sources[0], correction_status=correction)
            value = replace(
                self.inventory, sources=(source,), reviews=(review(source, "source"),)
            )
            result = check_circuit_sources(value)
            self.assertIs(result.outcome, CheckOutcome.PASS)
            self.assertEqual(result.source_bytes, "not_checked")
            self.assertEqual(result.empirical_validation, "unknown")
            self.assertEqual(result.molecular_readiness, "unassessed")

    def test_assessment_roundtrip_is_deterministic_and_deeply_immutable(self):
        restored = CircuitSourcesAssessment.from_json(self.assessment.to_json())
        self.assertEqual(restored, self.assessment)
        self.assertEqual(restored.fingerprint, self.assessment.fingerprint)
        with self.assertRaises(FrozenInstanceError):
            restored.outcome = CheckOutcome.FAIL
        with self.assertRaises(TypeError):
            restored.dependencies["inventory"] = "b" * 64
        with self.assertRaises(TypeError):
            restored.case_summaries[0]["context_status"] = "verified"
        with self.assertRaises(TypeError):
            restored.case_summaries[0]["gaps"][0]["note"] = "Changed note"

    def test_assessment_has_strict_fields_and_rejects_forged_claims(self):
        for key in self.assessment.to_dict():
            data = self.assessment.to_dict()
            del data[key]
            with self.subTest(missing=key), self.assertRaises(SerializationError):
                CircuitSourcesAssessment.from_dict(data)
        for key, value in (
            ("schema_version", "future"),
            ("sequence", "unsupported field"),
            ("claim_scope", "complete_reconstruction"),
            ("molecular_readiness", "complete"),
            ("empirical_validation", "pass"),
            ("human_admission", "admitted"),
            ("source_bytes", "verified"),
        ):
            with self.subTest(field=key), self.assertRaises(SerializationError):
                CircuitSourcesAssessment.from_dict(
                    self.assessment.to_dict() | {key: value}
                )
        with self.assertRaises(SerializationError):
            CircuitSourcesAssessment.from_json(
                self.assessment.to_json()[:-1] + ', "outcome": "pass"}'
            )

    def test_external_complete_authority_is_required_for_fresh_replay(self):
        with self.assertRaises(TypeError):
            verify_circuit_sources(self.assessment)
        for expected in (
            None,
            self.inventory.fingerprint,
            self.inventory.to_dict(),
            self.assessment,
        ):
            with self.assertRaises(SerializationError):
                verify_circuit_sources(self.assessment, expected_inventory=expected)
        independent = CircuitSourceInventory.from_json(self.inventory.to_json())
        self.assertEqual(
            verify_circuit_sources(self.assessment, expected_inventory=independent),
            self.assessment,
        )

    def test_consistently_rehashed_inventory_cannot_replace_external_authority(self):
        source = self.inventory.sources[0]
        for changes in (
            {"title": "Changed source title"},
            {"version": "different-version"},
            {"byte_sha256": "b" * 64},
            {"byte_size": 456},
            {"retrieved_at": "2026-09-30T01:00:00Z"},
            {"correction_status": "corrected"},
        ):
            changed = replace(source, **changes)
            value = replace(
                self.inventory, sources=(changed,), reviews=(review(changed, "source"),)
            )
            report = check_circuit_sources(value)
            with (
                self.subTest(changes=changes),
                self.assertRaisesRegex(
                    SerializationError, "independent expected inventory"
                ),
            ):
                verify_circuit_sources(report, expected_inventory=self.inventory)

    def test_inventory_history_metadata_is_retained_and_authoritative(self):
        changed = replace(
            self.inventory,
            version="2",
            previous_inventory_fingerprint=self.inventory.fingerprint,
            change_reason="Metadata correction; no new source content",
        )
        result = check_circuit_sources(changed)
        self.assertEqual(
            result.inventory.previous_inventory_fingerprint, self.inventory.fingerprint
        )
        with self.assertRaises(SerializationError):
            verify_circuit_sources(result, expected_inventory=self.inventory)

    def test_forged_pass_and_gap_summary_fail_fresh_reconstruction(self):
        invalid = replace(
            self.inventory,
            reviews=(replace(self.inventory.reviews[0], subject_fingerprint="b" * 64),),
        )
        failed = check_circuit_sources(invalid)
        forged = replace(failed, outcome=CheckOutcome.PASS, diagnostics=())
        with self.assertRaisesRegex(SerializationError, "current independent metadata"):
            verify_circuit_sources(forged, expected_inventory=invalid)
        data = self.assessment.to_dict()
        data["case_summaries"][0]["declared_provided_fields"] = sorted(COVERAGE_FIELDS)
        data["case_summaries"][0]["gaps"] = []
        forged_gaps = CircuitSourcesAssessment.from_dict(data)
        with self.assertRaisesRegex(SerializationError, "current independent metadata"):
            verify_circuit_sources(forged_gaps, expected_inventory=self.inventory)

    def test_current_checker_and_policy_versions_are_reconstructed(self):
        for owner, attribute in (
            (checker, "CHECKER_VERSION"),
            (checker.circuit_sources, "SOURCE_PROFILE_VERSION"),
            (checker.circuit_sources, "INVENTORY_POLICY_VERSION"),
            (checker.circuit_profile, "PROFILE_VERSION"),
            (checker.admission, "ADMISSION_POLICY_VERSION"),
        ):
            with patch.object(owner, attribute, "future-policy"):
                with self.assertRaisesRegex(
                    SerializationError, "current independent metadata"
                ):
                    verify_circuit_sources(
                        self.assessment, expected_inventory=self.inventory
                    )

    def test_published_assessment_size_includes_default_indentation_and_newline(self):
        pretty = self.assessment.to_json()
        compact = self.assessment.to_json(indent=None)
        size = len(pretty.encode("utf-8"))
        self.assertLess(len(compact.encode("utf-8")) + 1, size)
        with patch.object(checker, "MAX_ASSESSMENT_JSON_BYTES", size):
            with self.assertRaisesRegex(SerializationError, "publication newline"):
                CircuitSourcesAssessment.from_json(compact)
        with patch.object(checker, "MAX_ASSESSMENT_JSON_BYTES", size + 1):
            published = self.assessment.to_json() + "\n"
            self.assertEqual(
                CircuitSourcesAssessment.from_json(published), self.assessment
            )
            with self.assertRaises(SerializationError):
                CircuitSourcesAssessment.from_json(published + "\n")
            with self.assertRaisesRegex(SerializationError, "publication newline"):
                self.assessment.to_json(indent=4)

    def test_large_identifiers_stay_in_inventory_with_bounded_diagnostics(self):
        large_case_id = "case-" + "x" * 4000
        large_missing_id = "missing-" + "y" * 4000
        changed_case = replace(
            self.inventory.cases[0], id=large_case_id, source_ids=(large_missing_id,)
        )
        value = replace(self.inventory, cases=(changed_case,), reviews=())
        result = self.assert_failed_with(value, "unknown_source:sha256-")
        self.assertEqual(result.inventory.cases[0].id, large_case_id)
        self.assertEqual(result.inventory.cases[0].source_ids, (large_missing_id,))
        self.assertTrue(
            all(
                len(item.encode("utf-8")) <= checker.MAX_DIAGNOSTIC_TEXT_BYTES
                for item in result.diagnostics
            )
        )
        self.assertNotIn(large_case_id, " ".join(result.diagnostics))

    def test_diagnostic_budget_truncation_explicitly_remains_failure(self):
        missing = tuple(f"missing-source-{index}" for index in range(10))
        changed_case = change_gap(
            self.inventory.cases[0], "chemistry", source_ids=missing
        )
        value = replace(self.inventory, cases=(changed_case,), reviews=())
        with patch.object(checker, "MAX_DIAGNOSTICS", 3):
            result = check_circuit_sources(value)
            self.assertIs(result.outcome, CheckOutcome.FAIL)
            self.assertEqual(len(result.diagnostics), 3)
            self.assertTrue(
                any(
                    item.startswith("additional_metadata_failure_occurrences_omitted:")
                    for item in result.diagnostics
                )
            )
            self.assertEqual(result.inventory, value)
            self.assertEqual(
                verify_circuit_sources(result, expected_inventory=value), result
            )

    def test_assessment_output_budget_fails_closed_without_losing_source_authority(
        self,
    ):
        # Metadata and summary repetition are bounded separately from the source
        # inventory. A valid inventory is never converted to a PASS by dropping
        # content when the result budget cannot accommodate its complete report.
        input_size = len((self.inventory.to_json() + "\n").encode("utf-8"))
        result_size = len((self.assessment.to_json() + "\n").encode("utf-8"))
        self.assertGreater(result_size, input_size)
        with patch.object(checker, "MAX_ASSESSMENT_JSON_BYTES", input_size + 1):
            with self.assertRaisesRegex(SerializationError, "byte limit exceeded"):
                check_circuit_sources(self.inventory)
        self.assertEqual(
            check_circuit_sources(self.inventory).inventory, self.inventory
        )

    def test_aggregate_import_budget_rejects_before_decoding_shared_gap_values(self):
        data = self.assessment.to_dict()
        shared_note = "x" * 4096
        for gap in data["case_summaries"][0]["gaps"]:
            gap["note"] = shared_note
        # Every individual note fits the source schema. Reusing the same Python
        # string object must still consume bytes once per serialized occurrence.
        self.assertLess(len(shared_note), checker.MAX_ASSESSMENT_TEXT_BYTES)
        with (
            patch.object(checker, "MAX_ASSESSMENT_JSON_BYTES", 20_000),
            patch.object(
                CircuitSourceInventory,
                "from_dict",
                side_effect=AssertionError("Nested decoding ran before preflight"),
            ) as decode,
        ):
            with self.assertRaisesRegex(
                SerializationError, "aggregate text byte limit"
            ):
                CircuitSourcesAssessment.from_dict(data)
            decode.assert_not_called()
            # Direct construction receives the same aggregate preflight before
            # reparsing its inventory or interpreting supplied case summaries.
            with self.assertRaisesRegex(
                SerializationError, "aggregate text byte limit"
            ):
                replace(self.assessment, case_summaries=data["case_summaries"])
            decode.assert_not_called()

    def test_import_item_and_depth_limits_precede_nested_decoding(self):
        wide = self.assessment.to_dict()
        wide["case_summaries"] = [None] * 1025
        deep = self.assessment.to_dict()
        nested = []
        for _ in range(checker.MAX_ASSESSMENT_DEPTH + 1):
            nested = [nested]
        deep["case_summaries"] = nested
        with patch.object(
            CircuitSourceInventory,
            "from_dict",
            side_effect=AssertionError("Nested decoding ran before preflight"),
        ) as decode:
            with patch.object(checker, "MAX_ASSESSMENT_ITEMS", 1024):
                with self.assertRaisesRegex(SerializationError, "item limit"):
                    CircuitSourcesAssessment.from_dict(wide)
            with self.assertRaisesRegex(SerializationError, "nesting limit"):
                CircuitSourcesAssessment.from_dict(deep)
            decode.assert_not_called()

    def test_checker_imports_no_fetcher_generator_or_model_execution(self):
        tree = ast.parse(Path(checker.__file__).read_text())
        dependencies = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                dependencies.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                dependencies.append(node.module or "")
        for dependency in dependencies:
            self.assertFalse(
                dependency.startswith(
                    (
                        "requests",
                        "urllib",
                        "http",
                        "biocompiler.synthesis",
                        "biocompiler.backends",
                        "biocompiler.models",
                        "biocompiler.compiler",
                    )
                ),
                dependency,
            )


if __name__ == "__main__":
    unittest.main()
