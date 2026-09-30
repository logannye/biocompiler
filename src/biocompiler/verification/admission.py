"""One fail-closed use policy for planning, selection, verification and export.

No human therapeutic profile is admitted in this version. Source pins, biological
context labels, model classes and reported PASS results cannot change that fact.
The policy must be revised with independently supported profiles in later work.
"""

from biocompiler.ir.serialization import require
from biocompiler.semantics.admission import AdmissionAssessment, AdmissionRequest
from biocompiler.semantics.context import HumanTargetContext


def assess_admission(request):
    require(
        isinstance(request, AdmissionRequest), "Expected AdmissionRequest authority."
    )
    request = AdmissionRequest.from_dict(request.to_dict())
    human = isinstance(request.target, HumanTargetContext)
    evidence = request.target.human_target.evidence if human else ()
    reasons = []
    if request.intended_use == "software_test" and not human:
        decision = "software_only"
        reasons.append("software_testing_only_no_human_therapeutic_admission")
    else:
        decision = "not_admitted"
        reasons.append("human_profile_unavailable")
        if not human:
            reasons.append("human_target_contract_missing")
        elif request.intended_use == "software_test":
            reasons.append("human_target_cannot_be_downgraded_to_software")
        if human:
            reasons.append("human_applicability_not_independently_validated")
        categories = {item.system for item in evidence}
        if "human_in_vivo" not in categories:
            reasons.append("human_in_vivo_evidence_not_declared")
        for category in sorted(categories):
            reasons.append(
                {
                    "human_in_vivo": "human_in_vivo_evidence_requires_independent_review",
                    "primary_human_cells": "primary_human_cell_evidence_does_not_establish_in_vivo_applicability",
                    "human_cell_line": "human_cell_line_evidence_does_not_establish_primary_or_in_vivo_applicability",
                    "nonhuman_in_vivo": "nonhuman_in_vivo_evidence_does_not_establish_human_applicability",
                    "nonhuman_cells": "nonhuman_cell_evidence_does_not_establish_human_applicability",
                    "cell_free": "cell_free_evidence_does_not_establish_recipient_applicability",
                    "software_fixture": "software_fixture_is_not_biological_evidence",
                }[category]
            )
        for item in request.components:
            reasons.append(
                {
                    "synthetic_model": "synthetic_model_not_human_implementation",
                    "sequence_reference": "sequence_reference_not_human_implementation",
                    "modeled_component": "modeled_component_not_independently_admitted_for_human_use",
                }[item.classification]
            )
            if any(
                pin.id == "wo2022081694a1.murine-fapcar.cds" for pin in item.identities
            ):
                reasons.append("murine_fap_reference_not_human_implementation")
    return AdmissionAssessment(
        request.fingerprint,
        request.target.fingerprint,
        request.intended_use,
        request.boundary,
        decision,
        tuple(sorted(set(reasons))),
        tuple(item.fingerprint for item in request.components),
        evidence,
    )


def verify_admission(request, assessment):
    """Recompute from current independent authority; saved decisions are untrusted."""
    require(
        isinstance(assessment, AdmissionAssessment), "Expected AdmissionAssessment."
    )
    return assess_admission(request) == AdmissionAssessment.from_dict(
        assessment.to_dict()
    )


def admission_for_target(target, *, boundary, components=()):
    """Legacy target schemas can request software checks only, never human use."""
    # Derive use only from a freshly parsed schema, not context names/capabilities.
    from biocompiler.semantics.context import TargetContext

    require(isinstance(target, TargetContext), "Expected target authority.")
    target = TargetContext.from_dict(target.to_dict())
    return assess_admission(
        AdmissionRequest(
            target,
            "human_therapeutic"
            if isinstance(target, HumanTargetContext)
            else "software_test",
            boundary,
            tuple(components),
        )
    )


def require_software_use(target, *, boundary, components=()):
    assessment = admission_for_target(target, boundary=boundary, components=components)
    require(
        assessment.decision == "software_only",
        "Human therapeutic use is not admitted: " + "; ".join(assessment.diagnostics),
    )
    return assessment
