"""Evidence bookkeeping over artificial fixtures is never experimental support."""

import ast
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import unittest
from unittest.mock import patch

from biocompiler.compiler.circuit_construction import build_circuit_construction
from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_construction import AmountDeclaration
from biocompiler.ir.circuit_evidence import (
    CircuitEvidenceObservationBinding,
    CircuitEvidenceReceipt,
    CircuitEvidenceRequest,
    CircuitEvidenceSource,
    CircuitEvidenceSourceReceipt,
    MAX_EVIDENCE_OBSERVATIONS,
    MAX_EVIDENCE_SOURCES,
)
from biocompiler.verification import circuit_evidence as checker
from biocompiler.verification.circuit_evidence import (
    CircuitEvidenceAssessment,
    capture_circuit_evidence,
    check_circuit_evidence,
    verify_circuit_evidence_assessment,
)
from examples.circuit_construction import make_construction_request
from examples.circuit_molecules import fixture_provenance
from examples.circuit_profile import make_profile_requests


def evidence_source(construction, **changes):
    requirement = construction.circuit.requirements[0]
    source = CircuitEvidenceSource(
        "artificial-observation",
        "observation",
        "1",
        "a" * 64,
        "unassigned",
        make_profile_requests()["reference"].source_experiment,
        (
            CircuitEvidenceObservationBinding(
                requirement.id, requirement.behavior.output.observation.id
            ),
        ),
        fixture_provenance("artificial-evidence-metadata"),
    )
    return replace(source, **changes)


class CircuitEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.construction = make_construction_request()
        cls.build = build_circuit_construction(cls.construction)
        cls.source = evidence_source(cls.construction)
        cls.request = CircuitEvidenceRequest(cls.construction, (cls.source,))
        cls.receipt = capture_circuit_evidence(cls.build, expected_request=cls.request)

    def check(self, receipt=None, *, request=None, build=None):
        return check_circuit_evidence(
            self.receipt if receipt is None else receipt,
            self.build if build is None else build,
            expected_request=self.request if request is None else request,
        )

    def test_current_identity_never_grants_evidence_or_model_claims(self):
        assessment = self.check()
        self.assertEqual(assessment.freshness, "current")
        self.assertEqual(assessment.construction_status, "checked_complete")
        self.assertEqual(assessment.prediction, "unsupported")
        self.assertEqual(assessment.empirical_validation, "unknown")
        self.assertEqual(assessment.evidence_applicability, "unassessed")
        self.assertEqual(assessment.human_therapeutic_admission, "not_admitted")
        self.assertFalse(hasattr(assessment, "passed"))
        self.assertEqual(
            {row.id for row in assessment.dependencies},
            {
                "circuit",
                "construction",
                "material",
                "context",
                "source:" + self.source.id,
            },
        )

    def test_public_records_round_trip_without_import_granting_authority(self):
        for value in (
            self.source.observations[0],
            self.source,
            self.request,
            self.receipt.sources[0],
            self.receipt,
            self.check(),
        ):
            with self.subTest(record=type(value).__name__):
                imported = type(value).from_json(value.to_json() + "\n")
                self.assertEqual(imported.to_dict(), value.to_dict())
                self.assertEqual(imported.fingerprint, value.fingerprint)
        historical = CircuitEvidenceAssessment.from_json(self.check().to_json())
        self.assertEqual(
            verify_circuit_evidence_assessment(
                historical, self.receipt, self.build, expected_request=self.request
            ),
            historical,
        )

    def test_records_are_frozen_and_source_order_is_canonical(self):
        with self.assertRaises(FrozenInstanceError):
            self.source.use = "held_out"
        another = replace(self.source, id="another-source")
        left = CircuitEvidenceRequest(self.construction, [self.source, another])
        right = CircuitEvidenceRequest(self.construction, [another, self.source])
        self.assertEqual(left.fingerprint, right.fingerprint)

    def test_external_correction_and_use_edits_invalidate_identity(self):
        for changes in (
            {"record_fingerprint": "b" * 64},
            {"version": "2"},
            {"use": "calibration"},
            {"population_scope": "mean_population"},
            {"source_context": None},
            {
                "source_context": replace(
                    self.source.source_context, cell_state="changed-declared-state"
                )
            },
            {"provenance": fixture_provenance("corrected-provenance")},
        ):
            with self.subTest(changes=changes):
                request = replace(
                    self.request, sources=(replace(self.source, **changes),)
                )
                result = self.check(request=request)
                self.assertEqual(result.freshness, "stale")
                self.assertEqual(
                    [row.id for row in result.dependencies if row.status == "stale"],
                    ["source:" + self.source.id],
                )

    def test_observations_models_and_references_have_distinct_declared_uses(self):
        model = replace(self.source, id="model", kind="model", use="prediction")
        reference = replace(
            self.source,
            id="reference",
            kind="reference",
            use="reference_only",
            observations=(),
        )
        request = replace(self.request, sources=(self.source, model, reference))
        receipt = capture_circuit_evidence(self.build, expected_request=request)
        result = self.check(receipt, request=request)
        self.assertEqual(result.freshness, "current")
        self.assertEqual(result.prediction, "unsupported")
        self.assertEqual(
            {item.kind for item in request.sources},
            {"model", "observation", "reference"},
        )
        for source, use in (
            (model, "held_out"),
            (self.source, "prediction"),
            (reference, "calibration"),
        ):
            with self.subTest(kind=source.kind), self.assertRaises(SerializationError):
                replace(source, use=use)

    def test_new_removed_and_empty_sources_report_missing_separately(self):
        removed = self.check(request=replace(self.request, sources=()))
        self.assertEqual(removed.freshness, "missing")
        self.assertTrue(removed.missing_evidence)
        self.assertEqual(removed.dependencies[-1].status, "missing_current")
        added_request = replace(
            self.request, sources=(self.source, replace(self.source, id="new-source"))
        )
        added = self.check(request=added_request)
        self.assertEqual(added.freshness, "missing")
        self.assertEqual(
            next(
                row.status
                for row in added.dependencies
                if row.id == "source:new-source"
            ),
            "missing_receipt",
        )
        empty_request = replace(self.request, sources=())
        empty = capture_circuit_evidence(self.build, expected_request=empty_request)
        self.assertEqual(self.check(empty, request=empty_request).freshness, "missing")

    def test_missing_and_stale_details_are_both_preserved(self):
        changed = replace(self.source, record_fingerprint="c" * 64)
        request = replace(
            self.request, sources=(changed, replace(self.source, id="additional"))
        )
        result = self.check(request=request)
        self.assertEqual(result.freshness, "missing")
        self.assertEqual(
            {row.status for row in result.dependencies},
            {"current", "stale", "missing_receipt"},
        )

    def test_material_and_construction_edits_invalidate_existing_receipt(self):
        source = self.construction.sources[0]
        changed_source = replace(
            source, molecule=replace(source.molecule, sequence="ACGTTC")
        )
        construction = replace(self.construction, sources=(changed_source,))
        build = build_circuit_construction(construction)
        result = self.check(
            request=replace(self.request, construction=construction), build=build
        )
        self.assertEqual(result.freshness, "stale")
        statuses = {row.id: row.status for row in result.dependencies}
        self.assertEqual(statuses["construction"], "stale")
        self.assertEqual(statuses["material"], "stale")
        self.assertEqual(statuses["circuit"], "current")

    def test_amount_changes_invalidate_material_even_without_sequence_changes(self):
        amount = AmountDeclaration(
            "amount",
            self.construction.output_members[0].id,
            "fixture-preparation",
            (),
            1,
            "declared_fixture_unit",
            fixture_provenance("fixture-amount"),
        )
        construction = replace(self.construction, amounts=(amount,))
        build = build_circuit_construction(construction)
        result = self.check(
            request=replace(self.request, construction=construction), build=build
        )
        statuses = {row.id: row.status for row in result.dependencies}
        self.assertEqual(statuses["material"], "stale")
        self.assertEqual(
            [item.sequence for item in build.candidate.bundle.molecules],
            [item.sequence for item in self.build.candidate.bundle.molecules],
        )

    def test_source_context_edit_invalidates_context_and_circuit(self):
        circuit = replace(
            self.construction.circuit,
            profile=replace(
                self.construction.circuit.profile,
                source_experiment=self.source.source_context,
            ),
        )
        construction = replace(self.construction, circuit=circuit)
        build = build_circuit_construction(construction)
        result = self.check(
            request=replace(self.request, construction=construction), build=build
        )
        statuses = {row.id: row.status for row in result.dependencies}
        self.assertEqual(statuses["context"], "stale")
        self.assertEqual(statuses["circuit"], "stale")

    def test_unrelated_current_build_cannot_be_authority(self):
        request = replace(
            self.request, construction=replace(self.construction, id="unrelated")
        )
        with self.assertRaisesRegex(SerializationError, "differs from independent"):
            self.check(request=request)

    def test_diagnostic_and_incomplete_builds_are_explicitly_unsupported(self):
        for construction in (
            replace(self.construction, mode="diagnostic"),
            replace(self.construction, payload_structures=()),
        ):
            with self.subTest(mode=construction.mode):
                build = build_circuit_construction(construction)
                request = replace(self.request, construction=construction)
                result = self.check(request=request, build=build)
                self.assertEqual(result.freshness, "unsupported")
                self.assertEqual(result.dependencies, ())
                with self.assertRaisesRegex(SerializationError, "complete strict"):
                    capture_circuit_evidence(build, expected_request=request)

    def test_checker_replays_construction_without_assembler_or_capture(self):
        with (
            patch(
                "biocompiler.backends.circuit_construction.construct_circuit_candidate",
                side_effect=AssertionError("producer called"),
            ),
            patch.object(
                checker,
                "capture_circuit_evidence",
                side_effect=AssertionError("capture called"),
            ),
        ):
            self.assertEqual(self.check().freshness, "current")
        with patch.object(
            checker,
            "verify_circuit_construction_assessment",
            side_effect=SerializationError("fresh structural replay failed"),
        ) as replay:
            with self.assertRaisesRegex(
                SerializationError, "fresh structural replay failed"
            ):
                self.check()
            replay.assert_called_once()

    def test_checker_has_no_compiler_backend_or_model_runner_import(self):
        tree = ast.parse(Path(checker.__file__).read_text())
        imports = [
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        ]
        self.assertFalse(
            any(
                name.startswith(
                    (
                        "biocompiler.compiler",
                        "biocompiler.backends",
                        "biocompiler.models",
                    )
                )
                for name in imports
            )
        )

    def test_self_consistent_forged_pass_cannot_replace_structural_replay(self):
        value = self.build.candidate.values[0]
        changed = replace(value, sequence=value.sequence[::-1])
        self.assertNotEqual(changed.sequence, value.sequence)
        candidate = replace(
            self.build.candidate,
            values=tuple(
                changed if item.id == value.id else item
                for item in self.build.candidate.values
            ),
        )
        historical = replace(
            self.build.assessment,
            candidate_fingerprint=candidate.fingerprint,
            reconstructed_fingerprint=candidate.fingerprint,
        )
        build = replace(self.build, candidate=candidate, assessment=historical)
        self.assertTrue(build.assessment.passed)
        with self.assertRaises(SerializationError):
            self.check(build=build)

    def test_checked_assessment_cannot_omit_core_or_source_inventory(self):
        assessment = self.check()
        for dependencies in (
            (),
            tuple(row for row in assessment.dependencies if row.id != "material"),
            tuple(
                row
                for row in assessment.dependencies
                if not row.id.startswith("source:")
            ),
        ):
            with (
                self.subTest(count=len(dependencies)),
                self.assertRaises(SerializationError),
            ):
                replace(assessment, dependencies=dependencies)

    def test_mutated_receipt_hash_is_stale_and_never_authoritative(self):
        for key in ("circuit", "construction", "material", "context"):
            with self.subTest(key=key):
                result = self.check(
                    replace(self.receipt, **{key + "_fingerprint": "0" * 64})
                )
                self.assertEqual(result.freshness, "stale")
                self.assertEqual(
                    next(row.status for row in result.dependencies if row.id == key),
                    "stale",
                )

    def test_historical_assessment_needs_fresh_complete_replay(self):
        result = self.check()
        request = replace(self.request, sources=(replace(self.source, version="new"),))
        with self.assertRaisesRegex(SerializationError, "stale or differs"):
            verify_circuit_evidence_assessment(
                result, self.receipt, self.build, expected_request=request
            )
        forged = replace(
            result,
            dependencies=tuple(
                replace(row, current_fingerprint="b" * 64)
                if row.id.startswith("source:")
                else row
                for row in result.dependencies
            ),
        )
        with self.assertRaisesRegex(SerializationError, "stale or differs"):
            verify_circuit_evidence_assessment(
                forged, self.receipt, self.build, expected_request=self.request
            )

    def test_cannot_import_pass_or_admitted_claims(self):
        result = self.check()
        for key, value in (
            ("prediction", "pass"),
            ("empirical_validation", "verified"),
            ("evidence_applicability", "applicable"),
            ("human_therapeutic_admission", "admitted"),
            ("claim_scope", "Published evidence verified"),
            ("checker_version", "other-checker"),
        ):
            with self.subTest(key=key), self.assertRaises(SerializationError):
                replace(result, **{key: value})

    def test_absent_observation_binding_is_rejected(self):
        binding = replace(self.source.observations[0], observation_id="unreported")
        source = replace(self.source, observations=(binding,))
        with self.assertRaisesRegex(
            SerializationError, "absent requirement or nominal observation"
        ):
            replace(self.request, sources=(source,))
        with self.assertRaisesRegex(SerializationError, "require nominal observation"):
            replace(self.source, observations=())

    def test_unknown_extra_duplicate_and_cyclic_fields_are_rejected(self):
        document = self.receipt.to_dict()
        document["passed"] = True
        with self.assertRaises(SerializationError):
            CircuitEvidenceReceipt.from_dict(document)
        with self.assertRaises(SerializationError):
            CircuitEvidenceReceipt.from_json(
                '{"schema_version":"one","schema_version":"two"}'
            )
        cyclic = {}
        cyclic["self"] = cyclic
        with self.assertRaises(SerializationError):
            CircuitEvidenceRequest.from_dict(cyclic)
        with self.assertRaises(SerializationError):
            replace(self.source, kind="experimental_validation")

    def test_bounded_and_duplicate_inventories_reject_before_use(self):
        for sources in (
            (self.source, self.source),
            tuple(
                replace(self.source, id=f"source-{index}")
                for index in range(MAX_EVIDENCE_SOURCES + 1)
            ),
        ):
            with (
                self.subTest(count=len(sources)),
                self.assertRaises(SerializationError),
            ):
                replace(self.request, sources=sources)
        with self.assertRaises(SerializationError):
            replace(
                self.source,
                observations=self.source.observations * (MAX_EVIDENCE_OBSERVATIONS + 1),
            )
        with self.assertRaises(SerializationError):
            replace(
                self.receipt, sources=(self.receipt.sources[0], self.receipt.sources[0])
            )

    def test_bad_hash_text_and_nonfinite_input_are_rejected(self):
        for changes in (
            {"record_fingerprint": "A" * 64},
            {"id": " bad "},
            {"version": "bad\x00"},
            {"population_scope": "all_cells"},
        ):
            with self.subTest(changes=changes), self.assertRaises(SerializationError):
                replace(self.source, **changes)
        with self.assertRaises(SerializationError):
            CircuitEvidenceSource.from_json(
                self.source.to_json().replace('"unknown"', "NaN", 1)
            )
        with self.assertRaises(SerializationError):
            CircuitEvidenceSourceReceipt("source", "not-a-hash")


if __name__ == "__main__":
    unittest.main()
