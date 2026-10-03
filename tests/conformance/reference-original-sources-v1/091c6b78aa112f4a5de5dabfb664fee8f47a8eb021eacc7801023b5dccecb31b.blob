"""Experimental typed transport for independently checked OCaml architectures.

This module imports no Python compiler, semantic evaluator or domain checker.
It validates transport identity and claim shape; the selected core owns semantic
checking. Public production workflows remain on their explicitly selected engine.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Callable, Literal, cast

from biocompiler.core_client import (
    CoreCapabilities, CoreClient, CoreProtocolError, CoreResponse, JsonValue,
    _names, _object, decode_json, encode_json,
)


VALIDATION_SCOPE = "supplied-architecture-correspondence-v1"
IMPLEMENTATION = "biocompiler.ocaml.architecture_check.v0.1"
RESOURCE_PROFILE = "biocompiler.architecture_check.resources.v1"
RESULT_SCHEMA = "biocompiler.core.architecture_assessment.v1"
ASSESSMENT_SCHEMA = "biocompiler.payload_architecture_verification.v0.1"
CHECKER_POLICY = "biocompiler.payload_architecture_checker.v0.3"
CLAIM_SCOPE = ("Exact source and supplied composite execution-contract correspondence, explicit functional "
               "requirements under bounded control proof profiles, declared RNA availability intervals, physical "
               "composition and complete RNA construction only. No empirical component function or human "
               "therapeutic admission is established.")
PROFILE: dict[str, JsonValue] = {
    "operations": ["verify-architecture", "replay-architecture"],
    "request_schema": "biocompiler.payload_architecture_request.v0.1",
    "build_schema": "biocompiler.payload_architecture_build.v0.2",
    "assessment_schema": ASSESSMENT_SCHEMA,
    "implementation": IMPLEMENTATION,
    "resource_profile": RESOURCE_PROFILE,
    "validation_scope": VALIDATION_SCOPE,
}
Outcome = Literal["pass", "fail", "unknown", "unsupported"]


def _fingerprint(value: JsonValue) -> str:
    return hashlib.sha256(encode_json(value)).hexdigest()


def _hash(value: JsonValue, label: str) -> str:
    if type(value) is not str or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise CoreProtocolError(f"{label} must be a lowercase SHA-256 fingerprint")
    return value


def _negotiate(capabilities: CoreCapabilities) -> None:
    if capabilities.profiles.get("architecture") != PROFILE or VALIDATION_SCOPE not in capabilities.validation_scopes:
        raise CoreProtocolError("Incompatible architecture schemas, implementation, resource profile or scope")


@dataclass(frozen=True)
class ArchitectureResult:
    """Immutable complete assessment bytes and separately scoped result fields.

    A serialized or manually constructed instance supplies no fresh authority.
    Replaying it requires the complete original request and candidate again.
    """

    request_id: str
    operation: str
    executable: Literal["core", "verify"]
    assessment_fingerprint: str
    supplied_request_fingerprint: str
    supplied_build_fingerprint: str
    request_fingerprint: str
    build_fingerprint: str
    outcome: Outcome
    translation_complete: bool
    construction_complete: bool
    unresolved: tuple[str, ...]
    assumptions: tuple[str, ...]
    _assessment_json: bytes

    @property
    def assessment(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], decode_json(self._assessment_json))


def _result(response: CoreResponse, payload: dict[str, JsonValue]) -> ArchitectureResult:
    result = _object(response.result, {"schema_version", "implementation", "resource_profile", "validation_scope",
                                      "supplied_request_fingerprint", "supplied_build_fingerprint",
                                      "assessment_fingerprint", "assessment"}, "Architecture result")
    if (result["schema_version"] != RESULT_SCHEMA or result["implementation"] != IMPLEMENTATION
            or result["resource_profile"] != RESOURCE_PROFILE or result["validation_scope"] != VALIDATION_SCOPE):
        raise CoreProtocolError("Architecture result changed its negotiated profile")
    supplied_request = _hash(result["supplied_request_fingerprint"], "Supplied request")
    supplied_build = _hash(result["supplied_build_fingerprint"], "Supplied build")
    if supplied_request != _fingerprint(payload["expected_request"]) or supplied_build != _fingerprint(payload["build"]):
        raise CoreProtocolError("Architecture result is bound to different supplied authority")
    assessment = _object(result["assessment"], {
        "schema_version", "request_fingerprint", "build_fingerprint", "outcome", "translation_complete",
        "construction_complete", "diagnostics", "unresolved", "assumptions", "checker_version", "claim_scope",
        "search_verified", "empirical_validation", "human_therapeutic_admission",
    }, "Architecture assessment")
    if (assessment["schema_version"] != ASSESSMENT_SCHEMA or assessment["checker_version"] != CHECKER_POLICY
            or assessment["claim_scope"] != CLAIM_SCOPE or assessment["search_verified"] is not False
            or assessment["empirical_validation"] != "unknown" or assessment["human_therapeutic_admission"] != "not_admitted"):
        raise CoreProtocolError("Architecture assessment has incompatible claims")
    outcome, translation, construction = (assessment[key] for key in ("outcome", "translation_complete", "construction_complete"))
    if type(outcome) is not str or outcome not in {"pass", "fail", "unknown", "unsupported"}:
        raise CoreProtocolError("Invalid architecture outcome")
    if type(translation) is not bool or type(construction) is not bool:
        raise CoreProtocolError("Architecture completion flags must be booleans")
    unresolved = _names(assessment["unresolved"], "Unresolved obligations")
    assumptions = _names(assessment["assumptions"], "Assumptions")
    diagnostics = assessment["diagnostics"]
    if type(diagnostics) is not list or any(type(item) is not dict for item in diagnostics):
        raise CoreProtocolError("Architecture diagnostics must be records")
    for item in diagnostics:
        gap = _object(item, {"schema_version", "category", "code", "requirement_ids", "candidate_ids",
                             "message", "conflict_set"}, "Architecture diagnostic")
        if gap["schema_version"] != "biocompiler.architecture_gap.v0.1" or gap["category"] not in (
            "unsupported_semantics", "missing_implementation", "incompatible_composition", "contradictory_requirements",
            "missing_sequence_authority", "search_budget_exhausted", "independent_verification_failure",
        ):
            raise CoreProtocolError("Invalid architecture diagnostic schema or category")
        for key in ("code", "message"):
            if type(gap[key]) is not str or not cast(str, gap[key]).strip():
                raise CoreProtocolError("Invalid architecture diagnostic text")
        for key in ("requirement_ids", "candidate_ids", "conflict_set"):
            _names(gap[key], "Architecture diagnostic inventory")
    if outcome == "pass" and diagnostics or translation and (not construction or unresolved):
        raise CoreProtocolError("Contradictory architecture assessment claims")
    fingerprint = _hash(result["assessment_fingerprint"], "Assessment")
    if fingerprint != _fingerprint(assessment):
        raise CoreProtocolError("Architecture assessment fingerprint mismatch")
    return ArchitectureResult(response.request_id, response.operation, response.executable, fingerprint,
                              supplied_request, supplied_build,
                              _hash(assessment["request_fingerprint"], "Request"),
                              _hash(assessment["build_fingerprint"], "Build"), cast(Outcome, outcome),
                              translation, construction, unresolved, assumptions, encode_json(assessment))


@dataclass(frozen=True)
class ArchitectureClient:
    transport: CoreClient

    def _call(self, operation: str, payload: dict[str, JsonValue], *,
              cancelled: Callable[[], bool] | None) -> ArchitectureResult:
        # Freeze caller-owned containers before negotiation or subprocess I/O.
        snapshot = cast(dict[str, JsonValue], decode_json(encode_json(payload)))
        _negotiate(self.transport.negotiate(operation, cancelled=cancelled))
        return _result(self.transport.call(operation, snapshot, cancelled=cancelled), snapshot)

    def verify(self, *, expected_request: JsonValue, build: JsonValue,
               cancelled: Callable[[], bool] | None = None) -> ArchitectureResult:
        return self._call("verify-architecture", {"expected_request": expected_request, "build": build}, cancelled=cancelled)

    def replay(self, *, expected_request: JsonValue, build: JsonValue, assessment: JsonValue,
               cancelled: Callable[[], bool] | None = None) -> ArchitectureResult:
        return self._call("replay-architecture", {"expected_request": expected_request, "build": build,
                                                 "assessment": assessment}, cancelled=cancelled)
