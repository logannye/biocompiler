"""Build, replay and retrieve complete supplied constructions with explicit scope."""

from biocompiler.artifacts.circuit_construction_build import CircuitConstructionBuild
from biocompiler.artifacts.circuit_molecules import CircuitMoleculeRecord
from biocompiler.backends.circuit_construction import construct_circuit_candidate
from biocompiler.ir.circuit_construction import CircuitConstructionRequest
from biocompiler.ir.serialization import require
from biocompiler.verification.circuit_construction import (
    check_circuit_construction,
    verify_circuit_construction_assessment,
)


def build_circuit_construction(
    request: CircuitConstructionRequest,
) -> CircuitConstructionBuild:
    """Propose, then independently check the complete supplied construction."""
    require(
        isinstance(request, CircuitConstructionRequest),
        "Expected a typed construction request.",
    )
    request = CircuitConstructionRequest.from_dict(request.to_dict())
    candidate = construct_circuit_candidate(request)
    assessment = check_circuit_construction(candidate, expected_request=request)
    return CircuitConstructionBuild(request, candidate, assessment)


def verify_circuit_construction(build, *, expected_request):
    """Replay every operation against separately retained full authority."""
    require(
        isinstance(build, CircuitConstructionBuild),
        "Expected a historical construction build.",
    )
    require(
        isinstance(expected_request, CircuitConstructionRequest),
        "Expected independent complete construction authority.",
    )
    build = CircuitConstructionBuild.from_dict(build.to_dict())
    expected_request = CircuitConstructionRequest.from_dict(expected_request.to_dict())
    require(
        build.request.to_dict() == expected_request.to_dict(),
        "Construction build differs from independent complete authority.",
    )
    return verify_circuit_construction_assessment(
        build.assessment, build.candidate, expected_request=expected_request
    )


def verified_circuit_molecules(build, *, expected_request):
    """Retrieve the complete nominal set after fresh strict structural checks.

    This is not a human-use admission or physical synthesis authorization.
    Complete source/operation authority remains available in the build record.
    """
    assessment = verify_circuit_construction(build, expected_request=expected_request)
    require(
        expected_request.mode == "strict",
        "Diagnostic construction cannot produce a complete-set handoff.",
    )
    require(
        assessment.passed and assessment.complete,
        "Complete-set handoff requires fresh successful construction and payload checks.",
    )
    require(
        build.candidate.bundle is not None and not build.candidate.missing_members,
        "Complete-set handoff cannot omit a required member.",
    )
    return CircuitMoleculeRecord(
        build.candidate.bundle, build.candidate.experimental_amounts, {}
    )
