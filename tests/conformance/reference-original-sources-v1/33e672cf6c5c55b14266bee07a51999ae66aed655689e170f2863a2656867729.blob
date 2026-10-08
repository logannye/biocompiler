"""Fresh structural checking of supplied nominal circuit bindings.

No assembler/backend is imported. The construction checker freshly reconstructs
the supplied artifact before its final inventory can support any binding result.
Neither an alphabet match nor declared provenance proves molecular identity,
sensing, regulation, measurement, colocation or biological function.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from biocompiler.artifacts.circuit_construction import ConstructionCandidate
from biocompiler.artifacts.manifest import _hash
from biocompiler.ir.circuit_bindings import CircuitBindingRequest, _binding_assumptions
from biocompiler.ir.circuit_intent import same_authority
from biocompiler.ir.molecule_records import _MoleculeRecord, _text
from biocompiler.ir.serialization import require
from biocompiler.verification.circuit_construction import (
    MAX_ASSESSMENT_DIAGNOSTICS,
    MAX_DIAGNOSTIC_BYTES,
    _DiagnosticInventory,
    check_circuit_construction,
)
from biocompiler.verification.evidence import CheckOutcome


CHECKER_VERSION = "biocompiler.circuit_bindings_checker.v0.1"
CLAIM_SCOPE = "supplied_nominal_binding_correspondence"


@dataclass(frozen=True)
class CircuitBindingAssessment(_MoleculeRecord):
    request_fingerprint: str
    candidate_fingerprint: str
    construction_assessment_fingerprint: str
    outcome: CheckOutcome
    complete: bool
    diagnostics: tuple[str, ...]
    assumptions: tuple[str, ...] = ()
    checker_version: str = CHECKER_VERSION
    claim_scope: str = CLAIM_SCOPE
    independent_entity_identity: str = "unestablished"
    molecular_implementation: str = "unimplemented"
    biological_function: str = "unestablished"
    empirical_validation: str = "unknown"
    human_therapeutic_admission: str = "not_admitted"
    provider_availability: str = "unestablished"
    provider_colocation: str = "unestablished"
    schema_version: ClassVar[str] = "biocompiler.circuit_binding_assessment.v0.1"
    _decoders: ClassVar[dict] = {"outcome": CheckOutcome}

    def __post_init__(self):
        for key in (
            "request_fingerprint",
            "candidate_fingerprint",
            "construction_assessment_fingerprint",
        ):
            _hash(getattr(self, key), key)
        require(
            isinstance(self.outcome, CheckOutcome), "Expected typed binding outcome."
        )
        require(type(self.complete) is bool, "Binding completeness must be Boolean.")
        require(
            isinstance(self.diagnostics, (tuple, list))
            and len(self.diagnostics) <= MAX_ASSESSMENT_DIAGNOSTICS,
            "Invalid binding diagnostics.",
        )
        for diagnostic in self.diagnostics:
            _text(diagnostic, "Binding diagnostic", MAX_DIAGNOSTIC_BYTES)
        require(
            len(set(self.diagnostics)) == len(self.diagnostics),
            "Duplicate binding diagnostics.",
        )
        object.__setattr__(self, "diagnostics", tuple(sorted(self.diagnostics)))
        object.__setattr__(self, "assumptions", _binding_assumptions(self.assumptions))
        require(
            self.checker_version == CHECKER_VERSION, "Stale binding checker version."
        )
        require(
            self.claim_scope == CLAIM_SCOPE
            and self.independent_entity_identity == "unestablished"
            and self.molecular_implementation == "unimplemented"
            and self.biological_function == "unestablished"
            and self.empirical_validation == "unknown"
            and self.human_therapeutic_admission == "not_admitted",
            "Nominal bindings cannot promote identity, implementation or evidence claims.",
        )
        require(
            self.provider_availability == "unestablished"
            and self.provider_colocation == "unestablished",
            "Provider declarations and compartments do not establish availability or colocation.",
        )
        require(
            self.complete == (self.outcome is CheckOutcome.PASS)
            and (not self.complete or not self.diagnostics),
            "Binding completeness and diagnostics disagree with the outcome.",
        )
        self._check_resources()

    @property
    def passed(self):
        return self.outcome is CheckOutcome.PASS


def _source_inventory(circuit):
    sources = {}
    for requirement in circuit.requirements:
        behavior = requirement.behavior
        for source in behavior.inputs:
            sources[requirement.id, "input_observation", source.id] = source
        sources[requirement.id, "output_product", behavior.output.id] = (
            behavior.output.observation
        )
        for source in behavior.dependencies:
            sources[requirement.id, "provider", source.id] = source
    return sources


def _binding_diagnostics(binding, source, construction, bundle):
    """Resolve explicit references, without inventing biological correspondence."""
    prefix = f"fail:binding:{binding.id}:"
    requirements = {item.id: item for item in construction.requirements}
    requirement = requirements.get(binding.construction_requirement_id)
    if requirement is None:
        return (prefix + "missing_construction_requirement",)
    role = next(
        (item for item in requirement.roles if item.id == binding.role_id), None
    )
    if role is None:
        return (prefix + "missing_requirement_role",)
    errors = []
    if role.compartment != source.compartment:
        errors.append(prefix + "compartment_mismatch")

    if binding.source_kind == "provider":
        categories = {
            "host": {"host_provider"},
            "external_input": {"experimental_input"},
            "co_delivered": {"payload", "delivered_helper"},
        }
        if requirement.category not in categories[source.kind]:
            errors.append(prefix + "provider_kind_mismatch")
        if source.kind == "co_delivered" and requirement.member_id is None:
            errors.append(prefix + "co_delivered_member_missing")

    if requirement.member_id is None:
        if binding.subject_kind != "external":
            errors.append(prefix + "subject_kind_mismatch")
        if binding.source_kind == "output_product":
            errors.append(prefix + "output_requires_materialized_member")
        providers = tuple(
            provider
            for item in construction.circuit.requirements
            for provider in item.behavior.dependencies
            if provider.id == requirement.external_id
            and provider.fingerprint == requirement.external_fingerprint
        )
        # Construction validates this reference already; retain an explicit fail
        # here rather than allowing a missing source to act as a wildcard.
        if not providers:
            errors.append(prefix + "missing_external_provider")
        else:
            provider = providers[0]
            if not same_authority(provider.entity, source.entity):
                errors.append(prefix + "external_entity_mismatch")
            if binding.source_kind == "provider" and not same_authority(
                provider, source
            ):
                errors.append(prefix + "external_provider_authority_mismatch")
        return tuple(errors)

    members = {item.id: item for item in bundle.molecules}
    complexes = {item.id: item for item in bundle.complexes}
    member = members.get(requirement.member_id)
    complex_ = complexes.get(requirement.member_id)
    if member is None and complex_ is None:
        return (*errors, prefix + "missing_final_member")
    subject = member if member is not None else complex_
    subject_kind = member.space.alphabet if member is not None else complex_.kind
    if binding.subject_kind != subject_kind:
        errors.append(prefix + "subject_kind_mismatch")
    actual_role = next(
        (item for item in bundle.role_instances if item.id == role.id), None
    )
    if actual_role is None or (
        actual_role.subject_id != subject.id
        or actual_role.subject_fingerprint != subject.fingerprint
        or actual_role.compartment != role.compartment
        or actual_role.role != role.role
        or actual_role.purpose != role.purpose
    ):
        errors.append(prefix + "final_role_authority_mismatch")
    if binding.feature_id is not None:
        feature = (
            next(
                (item for item in member.features if item.id == binding.feature_id),
                None,
            )
            if member is not None
            else None
        )
        if feature is None:
            errors.append(prefix + "missing_final_feature")
        elif feature.path is None:
            errors.append(
                prefix + "feature_coordinate_mismatch"
                if binding.path is not None
                else f"unknown:binding:{binding.id}:feature_coordinates_unreported"
            )
        elif binding.path is None or not same_authority(feature.path, binding.path):
            errors.append(prefix + "feature_coordinate_mismatch")
    return tuple(errors)


def check_circuit_bindings(candidate, *, expected_request):
    """Check supplied nominal correspondence against fresh construction replay.

    PASS means all original observation/product/provider references resolve under
    the supplied authority. It never verifies that a named molecular entity is
    equivalent to a sequence, that a quantity is measurable from it, or that the
    construction implements the requested response or provider assumptions.
    """
    require(
        isinstance(expected_request, CircuitBindingRequest),
        "Expected independent binding authority.",
    )
    require(
        isinstance(candidate, ConstructionCandidate),
        "Expected a construction candidate.",
    )
    request = CircuitBindingRequest.from_dict(expected_request.to_dict())
    actual = ConstructionCandidate.from_dict(candidate.to_dict())
    construction = check_circuit_construction(
        actual, expected_request=request.construction
    )
    diagnostics = _DiagnosticInventory()
    diagnostics.extend(construction.diagnostics)
    sources = _source_inventory(request.construction.circuit)
    seen = set()
    for binding in request.bindings:
        if binding.source_key in seen:
            diagnostics.append(f"fail:binding:{binding.id}:duplicate_source_binding")
        seen.add(binding.source_key)
        source = sources.get(binding.source_key)
        if source is None:
            diagnostics.append(f"fail:binding:{binding.id}:unknown_source")
            continue
        # Candidate roles/features are authoritative only after a fresh complete
        # replay. Never resolve against a tampered or incomplete final bundle.
        if construction.passed:
            diagnostics.extend(
                _binding_diagnostics(
                    binding, source, request.construction, actual.bundle
                )
            )
    for requirement_id, kind, identity in sorted(sources.keys() - seen):
        diagnostics.append(
            f"fail:requirement:{requirement_id}:missing_{kind}:{identity}"
        )
    statuses = {item.split(":", 1)[0] for item in diagnostics}
    outcome = next(
        (
            value
            for value in (
                CheckOutcome.FAIL,
                CheckOutcome.UNSUPPORTED,
                CheckOutcome.UNKNOWN,
            )
            if value.value in statuses
        ),
        CheckOutcome.PASS,
    )
    return CircuitBindingAssessment(
        request.fingerprint,
        actual.fingerprint,
        construction.fingerprint,
        outcome,
        outcome is CheckOutcome.PASS,
        tuple(diagnostics),
        request.assumptions,
    )


def verify_circuit_binding_assessment(assessment, candidate, *, expected_request):
    """Reject stale or edited reports by comparing the complete fresh result."""
    require(
        isinstance(assessment, CircuitBindingAssessment),
        "Expected a saved binding assessment.",
    )
    saved = CircuitBindingAssessment.from_dict(assessment.to_dict())
    fresh = check_circuit_bindings(candidate, expected_request=expected_request)
    require(
        saved.fingerprint == fresh.fingerprint,
        "Binding assessment differs from fresh complete replay.",
    )
    return fresh
