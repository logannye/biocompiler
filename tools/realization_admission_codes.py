"""Exact diagnostic projections for the retained admission capture.

This is fixture tooling, not policy execution or a production error adapter.
``value`` is the complete literal record rebuilt from retained constructor
arguments/defaults, raw import text, or the policy function's argument mapping.
A Python-only class distinction returns ``python_type_boundary``; its serialized
counterpart must be replayed separately and never counted as original-stage
native parity. Unknown observed errors fail classification.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_REQUEST_FIELDS = {"schema_version", "target", "intended_use", "boundary", "components"}
_ASSESSMENT_FIELDS = {
    "schema_version", "policy", "human_therapeutic_admission", "claim_scope", "evidence_status",
    "request_fingerprint", "target_fingerprint", "intended_use", "boundary", "decision",
    "diagnostics", "component_fingerprints", "evidence",
}
_POLICY_OPERATIONS = {"assess_admission", "verify_admission", "admission_for_target", "require_software_use"}
_GATE_ERROR = (
    "Human therapeutic use is not admitted: human_applicability_not_independently_validated; "
    "human_in_vivo_evidence_not_declared; human_profile_unavailable"
)
_FIXED_ERRORS = {f"Invalid {key}." for key in (
    "policy", "human_therapeutic_admission", "claim_scope", "evidence_status"
)}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _name_code(value: Any, string_code: str = "invalid_name") -> str:
    return string_code if isinstance(value, str) else "invalid_type"


def _valid_hash(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= set("0123456789abcdef")


def expected_code(call: Mapping[str, Any], operation: str, value: Any) -> str | None:
    """Return a precise current native code, explicit type boundary, or success.

    Operation names are ``AdmissionRequest``, ``AdmissionAssessment``, the four
    source policy names, and ``AdmissionAssessment.is_current``. The latter has
    only successful observations in this capture. This function deliberately
    does not catch or normalize unclassified nested failures.
    """
    allowed = {"AdmissionRequest", "AdmissionAssessment", "AdmissionAssessment.is_current"} | _POLICY_OPERATIONS
    _require(operation in allowed, f"Unclassified admission operation: {operation}")
    outcome = call["outcome"]
    if outcome == "returned":
        return None
    _require(outcome == "raised", f"Unknown admission outcome: {outcome}")
    error = call["error"]
    _require(error["module"] == "biocompiler.errors" and error["type"] == "SerializationError",
             f"Unclassified admission exception: {error}")
    message = error["message"]
    if operation in _POLICY_OPERATIONS:
        _require(operation == "require_software_use" and message == _GATE_ERROR,
                 f"Unclassified policy rejection: {operation}: {message}")
        return "admission_not_admitted"
    _require(operation in {"AdmissionRequest", "AdmissionAssessment"},
             f"Unclassified admission method rejection: {operation}: {message}")
    if message == "Duplicate JSON key: boundary.":
        _require(operation == "AdmissionRequest" and call["api"] == "AdmissionRequest.from_json"
                 and isinstance(value, str), "Duplicate-key observation lost its raw JSON text")
        return "duplicate_key"
    if message == "Full target authority required.":
        _require(operation == "AdmissionRequest" and call["api"] == "AdmissionRequest.__init__"
                 and isinstance(value, dict) and isinstance(value.get("target"), dict),
                 "Unknown target Python-type boundary")
        # The original call passes an ordinary mapping instead of a TargetContext.
        # Importing the exact full record is valid; never invent a wire error.
        from biocompiler.semantics.admission import AdmissionRequest
        AdmissionRequest.from_dict(value)
        return "python_type_boundary"
    if message == f"Invalid fields in {operation}.":
        if not isinstance(value, dict):
            return "invalid_type"
        required = _REQUEST_FIELDS if operation == "AdmissionRequest" else _ASSESSMENT_FIELDS
        if required - set(value):
            return "missing_field"
        if set(value) - required:
            return "unknown_field"
        raise AssertionError(f"No field difference at rejected {operation}")
    _require(isinstance(value, dict), f"Expected complete admission record for: {message}")
    if message == f"Unsupported {operation} schema.":
        return _name_code(value["schema_version"], "unsupported_schema")
    if message in _FIXED_ERRORS:
        _require(operation == "AdmissionAssessment", "Assessment fixed field on request")
        return "admission_record"
    if message == "Expected SHA-256 identity.":
        for key in ("request_fingerprint", "target_fingerprint"):
            if not _valid_hash(value[key]):
                return _name_code(value[key], "admission_record")
        hashes = value["component_fingerprints"]
        _require(isinstance(hashes, list) and any(not _valid_hash(item) for item in hashes),
                 "No invalid admission SHA-256 field")
        return "admission_record"
    choice_fields = {
        "Invalid intended use.": "intended_use",
        "Invalid admission boundary.": "boundary",
        "Unsupported admission decision.": "decision",
    }
    if message in choice_fields:
        return _name_code(value[choice_fields[message]], "admission_record")
    for key in ("diagnostics", "component_fingerprints"):
        if message == f"{key} must be an array.":
            _require(not isinstance(value[key], list), f"Array rejection has array {key}")
            return "invalid_type"
        if message == f"{key} must be a nonempty string.":
            _require(isinstance(value[key], list), f"Name rejection lost array {key}")
            invalid = [item for item in value[key] if not isinstance(item, str) or not item.strip()]
            _require(bool(invalid), f"Name rejection has no invalid member in {key}")
            return _name_code(invalid[0])
    if message == "Expected record array.":
        key = "components" if operation == "AdmissionRequest" else "evidence"
        _require(not isinstance(value[key], list), f"Record-array rejection has array {key}")
        return "invalid_type"
    if message == "Expected component records.":
        _require(operation == "AdmissionRequest" and call["api"] == "AdmissionRequest.__init__",
                 "Unknown component constructor rejection")
        components = value["components"]
        _require(not isinstance(components, list) or any(not isinstance(item, dict) for item in components),
                 "Component class-only rejection needs explicit Python boundary classification")
        return "invalid_type"
    contextual = {
        "Admission decisions need explicit scope/reasons.",
        "Software use cannot authorize a human therapeutic build.",
        "Ambiguous admission component identities.",
    }
    if message in contextual:
        return "admission_record"
    raise AssertionError(f"Unclassified admission diagnostic: {operation}: {message}")
