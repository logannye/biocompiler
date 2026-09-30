"""Independent scope, authority and claim-promotion attacks on the R0 checker."""

import ast
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import unittest
from unittest.mock import patch

from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_profile import (
    BOUNDARIES,
    CircuitProfileRequest,
    HumanExperimentContext,
    ImmuneLineage,
    ImmuneRecipientIdentity,
)
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.semantics.context import PayloadFormat
from biocompiler.verification import circuit_profile as checker
from biocompiler.verification.circuit_profile import (
    CircuitProfileAssessment,
    check_circuit_profile,
    verify_circuit_profile,
)
from biocompiler.verification.evidence import CheckOutcome
from examples.human_acceptance import make_human_acceptance
from examples.human_target import make_human_target


def experiment(**changes):
    """Invented source declarations, never a fetched or reviewed paper."""
    return HumanExperimentContext(
        **(
            {
                "system": "human_cell_line",
                "immune_classification": "nonimmune",
                "cell_identity": "HEK293 fixture declaration",
                "cell_state": "Not reported in this software fixture",
                "compartment": "cytoplasm",
                "delivery_mode": "dna_delivery",
                "sources": (
                    PinnedIdentity("source", "fixture.article", "1", "a" * 64),
                ),
                "locator": "Artificial source-context fixture; no empirical claim",
                "assay_conditions": ("Assay conditions unestablished",),
            }
            | changes
        )
    )


def product_request(
    *, boundary="planning", molecular_form=PayloadFormat.RNA, source=None
):
    target = (
        source.target
        if source is not None
        else replace(make_human_target(), payload_format=molecular_form)
    )
    recipient = ImmuneRecipientIdentity(
        ImmuneLineage.T_CELL,
        target.fingerprint,
        target.human_target.cell_subtype.fingerprint,
    )
    return CircuitProfileRequest(
        "human_immune_payload",
        "candidate_design",
        target.payload_format,
        boundary,
        target,
        recipient,
        experiment(),
        source,
    )


def reference_request(*, boundary="planning", molecular_form=PayloadFormat.RNA):
    return CircuitProfileRequest(
        "human_reference",
        "exact_reproduction",
        molecular_form,
        boundary,
        source_experiment=experiment(),
    )


class CircuitProfileCheckingTests(unittest.TestCase):
    def setUp(self):
        self.request = product_request()
        self.assessment = check_circuit_profile(self.request)

    def test_every_boundary_preserves_separate_unresolved_dimensions(self):
        for factory in (product_request, reference_request):
            for boundary in BOUNDARIES:
                for form in PayloadFormat:
                    with self.subTest(
                        purpose=factory.__name__, boundary=boundary, form=form
                    ):
                        request = factory(boundary=boundary, molecular_form=form)
                        result = check_circuit_profile(request)
                        self.assertEqual(result.boundary, boundary)
                        self.assertIs(result.outcome, CheckOutcome.UNSUPPORTED)
                        self.assertEqual(result.molecular_generation, "unimplemented")
                        self.assertEqual(result.behavior_compilation, "unimplemented")
                        self.assertEqual(
                            result.human_therapeutic_admission, "not_admitted"
                        )
                        self.assertEqual(
                            result.dimensions["empirical_validation"], "unknown"
                        )
                        self.assertEqual(
                            result.dimensions["human_admission"], "not_admitted"
                        )
                        for dimension in (
                            "base_identity",
                            "source_nominal_specification",
                            "complete_molecule_identity",
                            "mechanism_correspondence",
                            "model_validation",
                        ):
                            self.assertEqual(
                                result.dimensions[dimension], "unsupported"
                            )
                        self.assertIn(
                            f"{boundary}:r0_molecular_generation_unimplemented",
                            result.diagnostics,
                        )
                        self.assertIn(
                            f"{boundary}:human_therapeutic_use_not_admitted",
                            result.diagnostics,
                        )
                        self.assertEqual(
                            verify_circuit_profile(result, expected_request=request),
                            result,
                        )

    def test_eligibility_is_declarative_and_reference_has_no_product_target(self):
        product = self.assessment
        reference = check_circuit_profile(reference_request())
        self.assertEqual(product.eligibility, "declared_human_immune_target")
        self.assertEqual(reference.eligibility, "human_reference_only")
        for result in (product, reference):
            self.assertEqual(
                result.eligibility_basis,
                "declaration_or_ontology_contract_not_empirical",
            )
            self.assertNotIn("pass", result.dimensions.values())
        self.assertIsNone(reference.request.target)
        self.assertIsNone(reference.request.recipient)

    def test_nonimmune_in_vitro_source_cannot_replace_human_immune_target(self):
        result = self.assessment
        self.assertEqual(result.request.target, self.request.target)
        self.assertEqual(result.request.source_experiment.system, "human_cell_line")
        self.assertIn(
            "source_experiment_does_not_replace_deployment_target", result.diagnostics
        )
        self.assertIn(
            "nonimmune_source_does_not_establish_immune_applicability",
            result.diagnostics,
        )
        self.assertIn(
            "in_vitro_source_does_not_establish_in_vivo_applicability",
            result.diagnostics,
        )
        self.assertNotEqual(
            result.dependencies["target"], result.dependencies["source_experiment"]
        )

    def test_in_vivo_immune_source_and_citations_do_not_promote_claims(self):
        source = experiment(
            system="human_in_vivo",
            immune_classification="immune",
            immune_lineage=ImmuneLineage.T_CELL,
        )
        result = check_circuit_profile(replace(self.request, source_experiment=source))
        self.assertEqual(result.dimensions, self.assessment.dimensions)
        self.assertIn(
            "source_context_and_citations_do_not_establish_function", result.diagnostics
        )

    def test_component_origin_is_not_recipient_species(self):
        source = experiment(
            sources=(
                PinnedIdentity(
                    "source", "archaeal_l7ae_in_human_cells.fixture", "1", "b" * 64
                ),
            )
        )
        request = replace(reference_request(), source_experiment=source)
        result = check_circuit_profile(request)
        self.assertEqual(result.eligibility, "human_reference_only")
        self.assertEqual(result.request.source_experiment.sources, source.sources)
        self.assertEqual(result.request.source_experiment.recipient_taxon_id, 9606)

    def test_not_reported_delivery_is_retained_without_inference(self):
        request = replace(
            self.request, source_experiment=experiment(delivery_mode="not_reported")
        )
        result = check_circuit_profile(request)
        self.assertEqual(result.request.source_experiment.delivery_mode, "not_reported")
        self.assertEqual(result.dimensions["empirical_validation"], "unknown")

    def test_exact_reproduction_mode_does_not_establish_identity(self):
        result = check_circuit_profile(replace(self.request, mode="exact_reproduction"))
        self.assertEqual(result.dimensions["base_identity"], "unsupported")
        self.assertEqual(result.dimensions["complete_molecule_identity"], "unsupported")

    def test_roundtrip_and_deep_immutability(self):
        result = CircuitProfileAssessment.from_json(self.assessment.to_json())
        self.assertEqual(result, self.assessment)
        self.assertEqual(result.fingerprint, self.assessment.fingerprint)
        with self.assertRaises(FrozenInstanceError):
            result.eligibility = "human_reference_only"
        with self.assertRaises(TypeError):
            result.dimensions["base_identity"] = "pass"
        with self.assertRaises(TypeError):
            result.dependencies["checker"] = "invented"

    def test_strict_fields_schema_and_duplicate_json_keys(self):
        for key in self.assessment.to_dict():
            data = self.assessment.to_dict()
            del data[key]
            with self.subTest(missing=key), self.assertRaises(SerializationError):
                CircuitProfileAssessment.from_dict(data)
        for changes in ({"passed": True}, {"schema_version": "future"}):
            with self.assertRaises(SerializationError):
                CircuitProfileAssessment.from_dict(self.assessment.to_dict() | changes)
        with self.assertRaises(SerializationError):
            CircuitProfileAssessment.from_json(
                self.assessment.to_json()[:-1]
                + ', "eligibility": "human_reference_only"}'
            )

    def test_imported_success_labels_are_rejected_in_every_dimension(self):
        for dimension in self.assessment.dimensions:
            data = self.assessment.to_dict()
            data["dimensions"][dimension] = "pass"
            with (
                self.subTest(dimension=dimension),
                self.assertRaises(SerializationError),
            ):
                CircuitProfileAssessment.from_dict(data)
        for key, value in (
            ("outcome", "pass"),
            ("human_therapeutic_admission", "admitted"),
            ("molecular_generation", "implemented"),
            ("behavior_compilation", "implemented"),
            ("claim_scope", "therapeutic_function_verified"),
            ("eligibility_basis", "empirically_validated"),
        ):
            with self.subTest(field=key), self.assertRaises(SerializationError):
                CircuitProfileAssessment.from_dict(
                    self.assessment.to_dict() | {key: value}
                )

    def test_fresh_verification_requires_complete_external_request(self):
        with self.assertRaises(TypeError):
            verify_circuit_profile(self.assessment)
        for authority in (
            None,
            self.request.fingerprint,
            self.request.to_dict(),
            self.assessment,
        ):
            with (
                self.subTest(authority=type(authority)),
                self.assertRaises(SerializationError),
            ):
                verify_circuit_profile(self.assessment, expected_request=authority)
        independent = CircuitProfileRequest.from_json(self.request.to_json())
        self.assertIsNot(independent, self.assessment.request)
        self.assertEqual(
            verify_circuit_profile(self.assessment, expected_request=independent),
            self.assessment,
        )

    def test_forged_success_diagnostics_do_not_survive_fresh_reconstruction(self):
        for forged in (
            replace(self.assessment, diagnostics=("all_checks_passed",)),
            replace(self.assessment, eligibility="human_reference_only"),
        ):
            restored = CircuitProfileAssessment.from_json(forged.to_json())
            with self.assertRaisesRegex(
                SerializationError, "current independent policy"
            ):
                verify_circuit_profile(restored, expected_request=self.request)

    def test_policy_versions_are_reconstructed_not_trusted(self):
        for owner, name in (
            (checker, "CHECKER_VERSION"),
            (checker.circuit_ir, "PROFILE_VERSION"),
            (checker.admission, "ADMISSION_POLICY_VERSION"),
        ):
            with self.subTest(version=name), patch.object(owner, name, "future.policy"):
                with self.assertRaisesRegex(
                    SerializationError, "current independent policy"
                ):
                    verify_circuit_profile(
                        self.assessment, expected_request=self.request
                    )
                current = check_circuit_profile(self.request)
                self.assertEqual(current.human_therapeutic_admission, "not_admitted")

    def test_boundary_changes_require_a_new_assessment(self):
        for boundary in BOUNDARIES - {self.request.boundary}:
            changed = replace(self.request, boundary=boundary)
            with self.subTest(boundary=boundary), self.assertRaises(SerializationError):
                verify_circuit_profile(self.assessment, expected_request=changed)
            fresh = check_circuit_profile(changed)
            self.assertNotEqual(fresh.fingerprint, self.assessment.fingerprint)
            self.assertEqual(fresh.boundary, boundary)

    def test_consistently_rehashed_source_changes_do_not_supply_authority(self):
        original = self.request.source_experiment
        for changes in (
            {"system": "primary_human_cells"},
            {"cell_identity": "A different declared cell"},
            {"cell_state": "A different declared state"},
            {"compartment": "nucleus"},
            {"delivery_mode": "rna_delivery"},
            {"locator": "Different supplementary figure"},
            {"assay_conditions": ("Different reported conditions",)},
            {"sources": (replace(original.sources[0], content_fingerprint="c" * 64),)},
        ):
            changed = replace(
                self.request, source_experiment=replace(original, **changes)
            )
            forged = check_circuit_profile(changed)
            with (
                self.subTest(changes=changes),
                self.assertRaisesRegex(
                    SerializationError, "independent expected request"
                ),
            ):
                verify_circuit_profile(forged, expected_request=self.request)

    def test_rebinding_target_and_recipient_does_not_replace_original_authority(self):
        target = replace(
            self.request.target,
            human_target=replace(
                self.request.target.human_target,
                cell_state=replace(
                    self.request.target.human_target.cell_state,
                    description="An altered required recipient state",
                ),
            ),
        )
        request = replace(
            self.request,
            target=target,
            recipient=replace(
                self.request.recipient, target_fingerprint=target.fingerprint
            ),
        )
        consistent = check_circuit_profile(request)
        with self.assertRaisesRegex(SerializationError, "independent expected request"):
            verify_circuit_profile(consistent, expected_request=self.request)

    def test_complete_source_wrappers_and_unknown_obligations_remain_authoritative(
        self,
    ):
        source = make_human_acceptance()
        request = product_request(source=source)
        result = check_circuit_profile(request)
        self.assertEqual(result.request.source_request.to_dict(), source.to_dict())
        restored = CircuitProfileAssessment.from_json(result.to_json())
        self.assertEqual(
            restored.request.source_request.acceptance.shutdown.controllability,
            source.acceptance.shutdown.controllability,
        )
        changed_source = replace(
            source,
            acceptance=replace(
                source.acceptance,
                shutdown=replace(
                    source.acceptance.shutdown,
                    controllability=replace(
                        source.acceptance.shutdown.controllability,
                        limitations="An altered, still unresolved shutdown obligation",
                    ),
                ),
            ),
        )
        changed_request = replace(request, source_request=changed_source)
        self.assertNotEqual(changed_request.fingerprint, request.fingerprint)
        with self.assertRaises(SerializationError):
            verify_circuit_profile(
                check_circuit_profile(changed_request), expected_request=request
            )

    def test_poisoned_in_memory_request_is_reparsed_at_checker_boundary(self):
        for field, value in (("boundary", "manufacturing"), ("target", None)):
            poisoned = CircuitProfileRequest.from_json(self.request.to_json())
            object.__setattr__(poisoned, field, value)
            with self.subTest(field=field), self.assertRaises(SerializationError):
                check_circuit_profile(poisoned)

    def test_assessment_resources_are_bounded(self):
        for changes in (
            {"diagnostics": tuple(f"diagnostic-{number}" for number in range(33))},
            {"diagnostics": ("x" * 1025,)},
            {
                "dependencies": dict(self.assessment.dependencies)
                | {"checker": "x" * 257}
            },
        ):
            with (
                self.subTest(changes=tuple(changes)),
                self.assertRaises(SerializationError),
            ):
                replace(self.assessment, **changes)
        with self.assertRaises(SerializationError):
            CircuitProfileAssessment.from_json(
                " " * (checker.MAX_ASSESSMENT_JSON_BYTES + 1)
            )

    def test_default_publication_budget_reserves_newline(self):
        data = self.assessment.to_dict()
        pretty = self.assessment.to_json()
        compact = self.assessment.to_json(indent=None)
        pretty_bytes = len(pretty.encode("utf-8"))
        self.assertLess(len(compact.encode("utf-8")) + 1, pretty_bytes)
        # A compact representation that fits cannot admit an assessment whose
        # default publication, with its final newline, cannot be read back.
        with patch.object(checker, "MAX_ASSESSMENT_JSON_BYTES", pretty_bytes):
            for load in (
                lambda: CircuitProfileAssessment.from_dict(data),
                lambda: CircuitProfileAssessment.from_json(compact),
                lambda: self.assessment.to_json(),
            ):
                with self.assertRaisesRegex(SerializationError, "publication newline"):
                    load()
        with patch.object(checker, "MAX_ASSESSMENT_JSON_BYTES", pretty_bytes + 1):
            restored = CircuitProfileAssessment.from_dict(data)
            published = restored.to_json() + "\n"
            self.assertEqual(
                len(published.encode("utf-8")), checker.MAX_ASSESSMENT_JSON_BYTES
            )
            self.assertEqual(CircuitProfileAssessment.from_json(published), restored)
            with self.assertRaises(SerializationError):
                CircuitProfileAssessment.from_json(published + "\n")

    def test_custom_indentation_cannot_exceed_publication_budget(self):
        standard_bytes = len((self.assessment.to_json() + "\n").encode("utf-8"))
        with patch.object(checker, "MAX_ASSESSMENT_JSON_BYTES", standard_bytes):
            compact = self.assessment.to_json(indent=None)
            self.assertEqual(
                CircuitProfileAssessment.from_json(compact), self.assessment
            )
            with self.assertRaisesRegex(SerializationError, "publication newline"):
                self.assessment.to_json(indent=4)

    def test_checker_has_no_generation_or_execution_dependencies(self):
        tree = ast.parse(Path(checker.__file__).read_text())
        dependencies = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                dependencies.extend(item.name for item in node.names)
            elif isinstance(node, ast.ImportFrom):
                dependencies.append(node.module or "")
        for dependency in dependencies:
            self.assertFalse(
                dependency.startswith(
                    (
                        "biocompiler.synthesis",
                        "biocompiler.backends",
                        "biocompiler.compiler",
                    )
                ),
                dependency,
            )


if __name__ == "__main__":
    unittest.main()
