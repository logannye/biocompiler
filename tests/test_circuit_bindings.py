"""Artificial identity-bookkeeping tests; no published or functional evidence."""

from dataclasses import replace
import unittest
from unittest.mock import patch

from biocompiler.backends.circuit_construction import construct_circuit_candidate
from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_bindings import CircuitBindingRequest, CircuitEntityBinding
from biocompiler.ir.circuit_construction import (
    ComplexMemberConstituent,
    ComplexMemberPlan,
    MemberRequirement,
    RoleDeclaration,
)
from biocompiler.ir.circuit_intent import CircuitLifecycle, CircuitProviderRequirement
from biocompiler.ir.circuit_molecules import MoleculeFeature
from biocompiler.ir.circuit_observations import ProductKind, QuantityKind
from biocompiler.semantics.molecule_coordinates import CoordinatePath, IndexSpan
from biocompiler.verification.circuit_bindings import (
    CircuitBindingAssessment,
    check_circuit_bindings,
    verify_circuit_binding_assessment,
)
from biocompiler.verification.evidence import CheckOutcome
from examples.circuit_construction import make_construction_request
from examples.circuit_molecules import fixture_provenance


def binding_fixture(*, provider=False):
    construction = make_construction_request()
    requirement = construction.circuit.requirements[0]
    output = replace(
        requirement.behavior.output,
        kind=ProductKind.RNA_PRODUCT,
        observation=replace(
            requirement.behavior.output.observation, quantity=QuantityKind.RNA_ABUNDANCE
        ),
    )
    dependency = CircuitProviderRequirement(
        "artificial_host",
        requirement.behavior.inputs[0].entity,
        "host",
        "cytoplasm",
        "declared_group",
    )
    behavior = replace(
        requirement.behavior,
        output=output,
        lifecycle=CircuitLifecycle("production_control"),
        dependencies=(dependency,) if provider else (),
    )
    construction = replace(
        construction,
        circuit=replace(
            construction.circuit,
            requirements=(replace(requirement, behavior=behavior),),
        ),
    )
    provenance = fixture_provenance("nominal-binding-software-fixture")
    bindings = tuple(
        CircuitEntityBinding(
            "binding-" + source_id,
            requirement.id,
            kind,
            source_id,
            "required-payload",
            "payload-role",
            "RNA",
            provenance,
        )
        for kind, source_id in (
            *(("input_observation", item.id) for item in behavior.inputs),
            ("output_product", output.id),
        )
    )
    if provider:
        construction = replace(
            construction,
            requirements=construction.requirements
            + (
                MemberRequirement(
                    "required-provider",
                    "host_provider",
                    None,
                    dependency.id,
                    dependency.fingerprint,
                    (
                        RoleDeclaration(
                            "provider-role",
                            "declared-host",
                            "host_provider",
                            "cytoplasm",
                        ),
                    ),
                ),
            ),
        )
        bindings += (
            CircuitEntityBinding(
                "binding-provider",
                requirement.id,
                "provider",
                dependency.id,
                "required-provider",
                "provider-role",
                "external",
                provenance,
            ),
        )
    return CircuitBindingRequest(
        "artificial-bindings",
        construction,
        bindings,
        ("Nominal associations are artificial software declarations.",),
    )


class CircuitBindingTests(unittest.TestCase):
    def check(self, request, candidate=None):
        return check_circuit_bindings(
            candidate or construct_circuit_candidate(request.construction),
            expected_request=request,
        )

    def test_complete_nominal_binding_preserves_all_claim_limits_and_source(self):
        request = binding_fixture(provider=True)
        assessment = self.check(request)
        self.assertTrue(assessment.passed, assessment.diagnostics)
        self.assertEqual(assessment.independent_entity_identity, "unestablished")
        self.assertEqual(assessment.molecular_implementation, "unimplemented")
        self.assertEqual(assessment.biological_function, "unestablished")
        self.assertEqual(assessment.empirical_validation, "unknown")
        self.assertEqual(assessment.human_therapeutic_admission, "not_admitted")
        self.assertEqual(assessment.provider_availability, "unestablished")
        self.assertEqual(assessment.provider_colocation, "unestablished")
        self.assertEqual(assessment.assumptions, request.assumptions)
        self.assertEqual(
            request.construction.circuit.profile.source_request,
            make_construction_request().circuit.profile.source_request,
        )
        self.assertEqual(CircuitBindingRequest.from_json(request.to_json()), request)
        self.assertEqual(
            CircuitBindingAssessment.from_json(assessment.to_json()), assessment
        )

    def test_every_input_product_and_provider_is_required(self):
        request = binding_fixture(provider=True)
        for missing in request.bindings:
            with self.subTest(source=missing.source_key):
                changed = replace(
                    request,
                    bindings=tuple(
                        item for item in request.bindings if item.id != missing.id
                    ),
                )
                assessment = self.check(changed)
                self.assertEqual(assessment.outcome, CheckOutcome.FAIL)
                self.assertIn(
                    f"fail:requirement:{missing.requirement_id}:missing_{missing.source_kind}:{missing.source_id}",
                    assessment.diagnostics,
                )

    def test_duplicate_and_unknown_source_keys_cannot_cover_missing_inputs(self):
        request = binding_fixture()
        first = request.bindings[0]
        duplicate = replace(first, id="duplicate")
        assessment = self.check(
            replace(request, bindings=(*request.bindings, duplicate))
        )
        self.assertIn(
            "fail:binding:duplicate:duplicate_source_binding", assessment.diagnostics
        )
        changed = replace(first, requirement_id="absent-requirement")
        assessment = self.check(
            replace(request, bindings=(changed, *request.bindings[1:]))
        )
        self.assertIn(f"fail:binding:{first.id}:unknown_source", assessment.diagnostics)
        self.assertTrue(
            any(
                ":missing_input_observation:" in item for item in assessment.diagnostics
            )
        )

    def test_missing_roles_members_and_declared_subject_kind_fail(self):
        request = binding_fixture()
        first = request.bindings[0]
        for changes, diagnostic in (
            (
                {"construction_requirement_id": "absent"},
                "missing_construction_requirement",
            ),
            ({"role_id": "absent"}, "missing_requirement_role"),
            ({"subject_kind": "protein"}, "subject_kind_mismatch"),
        ):
            with self.subTest(changes=changes):
                changed = replace(
                    request, bindings=(replace(first, **changes), *request.bindings[1:])
                )
                self.assertIn(
                    f"fail:binding:{first.id}:{diagnostic}",
                    self.check(changed).diagnostics,
                )

    def test_role_cannot_be_borrowed_from_another_requirement(self):
        request = binding_fixture(provider=True)
        first = request.bindings[0]
        changed = replace(
            request,
            bindings=(replace(first, role_id="provider-role"), *request.bindings[1:]),
        )
        self.assertIn(
            f"fail:binding:{first.id}:missing_requirement_role",
            self.check(changed).diagnostics,
        )

    def test_compartment_mismatch_is_rejected_without_assuming_transport(self):
        request = binding_fixture()
        requirement = request.construction.requirements[0]
        target = replace(
            request.construction.circuit.profile.target,
            compartments=("cytoplasm", "extracellular"),
        )
        circuit = replace(
            request.construction.circuit,
            profile=replace(request.construction.circuit.profile, target=target),
        )
        construction = replace(
            request.construction,
            circuit=circuit,
            requirements=(
                replace(
                    requirement,
                    roles=(replace(requirement.roles[0], compartment="extracellular"),),
                ),
            ),
        )
        changed = replace(request, construction=construction)
        assessment = self.check(changed)
        self.assertEqual(assessment.outcome, CheckOutcome.FAIL)
        self.assertEqual(
            sum(
                item.endswith(":compartment_mismatch")
                for item in assessment.diagnostics
            ),
            3,
        )

    def test_exact_feature_coordinates_and_final_frame_are_checked(self):
        request = binding_fixture()
        first = request.bindings[0]
        path = CoordinatePath("artificial-output.frame", (IndexSpan(0, 6),), "+")
        bound = replace(first, feature_id="nominal-region", path=path)
        request = replace(request, bindings=(bound, *request.bindings[1:]))
        self.assertTrue(self.check(request).passed)
        for changed_path in (
            replace(path, space_id="joined.frame"),
            replace(path, spans=(IndexSpan(0, 5),)),
            replace(path, strand="-"),
            None,
        ):
            with self.subTest(path=changed_path):
                changed = replace(
                    request,
                    bindings=(replace(bound, path=changed_path), *request.bindings[1:]),
                )
                self.assertIn(
                    f"fail:binding:{bound.id}:feature_coordinate_mismatch",
                    self.check(changed).diagnostics,
                )
        changed = replace(
            request,
            bindings=(replace(bound, feature_id="missing"), *request.bindings[1:]),
        )
        self.assertIn(
            f"fail:binding:{bound.id}:missing_final_feature",
            self.check(changed).diagnostics,
        )

    def test_provider_requires_matching_kind_and_full_original_authority(self):
        request = binding_fixture(provider=True)
        provider_binding = next(
            item for item in request.bindings if item.source_kind == "provider"
        )
        changed = replace(
            provider_binding,
            construction_requirement_id="required-payload",
            role_id="payload-role",
            subject_kind="RNA",
        )
        request = replace(
            request,
            bindings=tuple(
                changed if item.id == changed.id else item for item in request.bindings
            ),
        )
        self.assertIn(
            f"fail:binding:{changed.id}:provider_kind_mismatch",
            self.check(request).diagnostics,
        )

    def test_complex_binding_keeps_complex_kind_and_cannot_invent_coordinates(self):
        request = binding_fixture()
        provenance = fixture_provenance("artificial-complex-binding")
        construction = replace(
            request.construction,
            complex_members=(
                ComplexMemberPlan(
                    "complex",
                    "rna_complex",
                    (ComplexMemberConstituent("artificial-output", 2, provenance),),
                    provenance,
                ),
            ),
            requirements=request.construction.requirements
            + (
                MemberRequirement(
                    "required-complex",
                    "encoded_product",
                    "complex",
                    None,
                    None,
                    (
                        RoleDeclaration(
                            "complex-role", "artificial-complex", "helper", "cytoplasm"
                        ),
                    ),
                ),
            ),
        )
        first = request.bindings[0]
        bound = replace(
            first,
            construction_requirement_id="required-complex",
            role_id="complex-role",
            subject_kind="rna_complex",
        )
        changed = replace(
            request, construction=construction, bindings=(bound, *request.bindings[1:])
        )
        self.assertTrue(self.check(changed).passed)
        with self.assertRaises(SerializationError):
            replace(bound, feature_id="invented-feature")
        changed = replace(
            changed,
            bindings=(replace(bound, subject_kind="RNA"), *changed.bindings[1:]),
        )
        self.assertIn(
            f"fail:binding:{bound.id}:subject_kind_mismatch",
            self.check(changed).diagnostics,
        )

    def test_unreported_optional_feature_coordinates_cannot_grant_complete_binding(
        self,
    ):
        request = binding_fixture()
        step = request.construction.steps[-1]
        port = step.ports[0]
        feature = MoleculeFeature(
            "unreported-feature",
            "artificial-annotation",
            None,
            fixture_provenance("unknown-coordinate"),
        )
        port = replace(
            port,
            feature_transition=replace(
                port.feature_transition, added=(*port.feature_transition.added, feature)
            ),
        )
        construction = replace(
            request.construction,
            steps=(*request.construction.steps[:-1], replace(step, ports=(port,))),
        )
        first = replace(request.bindings[0], feature_id=feature.id)
        changed = replace(
            request, construction=construction, bindings=(first, *request.bindings[1:])
        )
        assessment = self.check(changed)
        self.assertEqual(assessment.outcome, CheckOutcome.UNSUPPORTED)
        self.assertFalse(assessment.complete)
        self.assertTrue(
            any(item.startswith("unsupported:") for item in assessment.diagnostics)
        )

    def test_external_entity_fields_are_exact_not_unknown_wildcards(self):
        request = binding_fixture(provider=True)
        first = next(item for item in request.bindings if item.source_id == "A")
        external = replace(
            first,
            construction_requirement_id="required-provider",
            role_id="provider-role",
            subject_kind="external",
        )
        request = replace(
            request,
            bindings=tuple(
                external if item.id == first.id else item for item in request.bindings
            ),
        )
        self.assertTrue(self.check(request).passed)
        other = next(item for item in request.bindings if item.source_id == "B")
        changed = replace(
            other,
            construction_requirement_id="required-provider",
            role_id="provider-role",
            subject_kind="external",
        )
        altered = replace(
            request,
            bindings=tuple(
                changed if item.id == other.id else item for item in request.bindings
            ),
        )
        self.assertIn(
            f"fail:binding:{changed.id}:external_entity_mismatch",
            self.check(altered).diagnostics,
        )

    def test_output_cannot_disappear_into_external_provider(self):
        request = binding_fixture(provider=True)
        output = next(
            item for item in request.bindings if item.source_kind == "output_product"
        )
        changed = replace(
            output,
            construction_requirement_id="required-provider",
            role_id="provider-role",
            subject_kind="external",
        )
        request = replace(
            request,
            bindings=tuple(
                changed if item.id == output.id else item for item in request.bindings
            ),
        )
        self.assertIn(
            f"fail:binding:{changed.id}:output_requires_materialized_member",
            self.check(request).diagnostics,
        )

    def test_tampered_constructed_bases_fail_before_binding_resolution(self):
        request = binding_fixture()
        candidate = construct_circuit_candidate(request.construction)
        value = candidate.values[0]
        candidate = replace(
            candidate, values=(replace(value, sequence="AAAAAA"), *candidate.values[1:])
        )
        with patch(
            "biocompiler.verification.circuit_bindings._binding_diagnostics",
            side_effect=AssertionError("Cannot resolve an unverified candidate"),
        ):
            assessment = self.check(request, candidate)
        self.assertEqual(assessment.outcome, CheckOutcome.FAIL)
        self.assertTrue(
            any(item.startswith("fail:value:") for item in assessment.diagnostics)
        )

    def test_saved_pass_cannot_be_reused_after_binding_or_source_edit(self):
        request = binding_fixture()
        candidate = construct_circuit_candidate(request.construction)
        assessment = self.check(request, candidate)
        self.assertEqual(
            verify_circuit_binding_assessment(
                assessment, candidate, expected_request=request
            ),
            assessment,
        )
        # A changed independent declaration remains structurally valid but must
        # invalidate its prior result even when emitted bases stay identical.
        first = request.bindings[0]
        changed = replace(
            request,
            bindings=(
                replace(first, provenance=fixture_provenance("different-declaration")),
                *request.bindings[1:],
            ),
        )
        with self.assertRaises(SerializationError):
            verify_circuit_binding_assessment(
                assessment, candidate, expected_request=changed
            )
        changed = replace(
            request, assumptions=("A different declared software assumption.",)
        )
        with self.assertRaises(SerializationError):
            verify_circuit_binding_assessment(
                assessment, candidate, expected_request=changed
            )
        root = request.construction.sources[0]
        construction = replace(
            request.construction,
            sources=(
                replace(root, molecule=replace(root.molecule, sequence="ACCTTA")),
            ),
        )
        changed = replace(request, construction=construction)
        with self.assertRaises(SerializationError):
            verify_circuit_binding_assessment(
                assessment,
                construct_circuit_candidate(construction),
                expected_request=changed,
            )

    def test_checker_does_not_call_producer(self):
        request = binding_fixture()
        candidate = construct_circuit_candidate(request.construction)
        with patch(
            "biocompiler.backends.circuit_construction.construct_circuit_candidate",
            side_effect=AssertionError("producer called"),
        ):
            self.assertTrue(self.check(request, candidate).passed)

    def test_changed_provider_context_invalidates_saved_result_without_promotion(self):
        request = binding_fixture(provider=True)
        assessment = self.check(request)
        requirement = request.construction.circuit.requirements[0]
        dependency = requirement.behavior.dependencies[0]
        changed_dependency = replace(
            dependency,
            availability="declared",
            colocation_group="different-declared-group",
        )
        circuit = replace(
            request.construction.circuit,
            requirements=(
                replace(
                    requirement,
                    behavior=replace(
                        requirement.behavior, dependencies=(changed_dependency,)
                    ),
                ),
            ),
        )
        construction = replace(
            request.construction,
            circuit=circuit,
            requirements=tuple(
                replace(item, external_fingerprint=changed_dependency.fingerprint)
                if item.external_id == dependency.id
                else item
                for item in request.construction.requirements
            ),
        )
        changed = replace(request, construction=construction)
        candidate = construct_circuit_candidate(construction)
        fresh = self.check(changed, candidate)
        self.assertTrue(fresh.passed)
        self.assertEqual(fresh.provider_availability, "unestablished")
        self.assertEqual(fresh.provider_colocation, "unestablished")
        with self.assertRaises(SerializationError):
            verify_circuit_binding_assessment(
                assessment, candidate, expected_request=changed
            )

    def test_imports_reject_unknown_keys_invalid_paths_and_claim_promotion(self):
        request = binding_fixture()
        data = request.to_dict()
        data["unknown"] = True
        with self.assertRaises(SerializationError):
            CircuitBindingRequest.from_dict(data)
        with self.assertRaises(SerializationError):
            replace(
                request.bindings[0],
                path=CoordinatePath("frame", (IndexSpan(0, 1),), "+"),
            )
        assessment = self.check(request)
        for changes in (
            {"independent_entity_identity": "verified"},
            {"molecular_implementation": "complete"},
            {"biological_function": "verified"},
            {"empirical_validation": "validated"},
            {"human_therapeutic_admission": "admitted"},
            {"provider_availability": "established"},
            {"provider_colocation": "established"},
            {"checker_version": "old"},
        ):
            with self.subTest(changes=changes), self.assertRaises(SerializationError):
                replace(assessment, **changes)

    def test_assumptions_are_bounded_unique_and_explicit(self):
        request = binding_fixture()
        self.assertEqual(replace(request, assumptions=()).assumptions, ())
        for assumptions in (
            ("duplicate", "duplicate"),
            ("",),
            tuple(str(i) for i in range(33)),
        ):
            with (
                self.subTest(assumptions=assumptions),
                self.assertRaises(SerializationError),
            ):
                replace(request, assumptions=assumptions)


if __name__ == "__main__":
    unittest.main()
