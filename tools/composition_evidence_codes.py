"""Exact error projections for retained historical composition report records.

This fixture helper classifies only observed failures. ``value`` is the full
literal record independently reconstructed from captured arguments/defaults or
import text. Unknown messages and changed rejection predicates fail closed.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_OPERATIONS = {"LinkDiagnostic", "ResolvedDependency", "ResourceUsage", "CompositionResult"}
_IDENTITY_FIELDS = {"schema_version", "kind", "id", "version", "content_fingerprint"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def expected_code(call: Mapping[str, Any], operation: str, value: Any) -> str | None:
    """Return the exact native diagnostic or ``None`` for a returned record."""
    _require(operation in _OPERATIONS, f"Unclassified composition evidence operation: {operation}")
    _require(call["api"] in {f"{operation}.__init__", f"{operation}.from_dict", f"{operation}.from_json"},
             f"Unclassified composition evidence API: {call['api']}")
    if call["outcome"] == "returned":
        return None
    _require(call["outcome"] == "raised", f"Unknown composition evidence outcome: {call['outcome']}")
    error = call["error"]
    _require(error["module"] == "biocompiler.errors" and error["type"] == "SerializationError",
             f"Unclassified composition evidence exception: {error}")
    _require(isinstance(value, dict), "Captured composition evidence rejection lost its complete record")
    message = error["message"]
    if message == "Invalid link diagnostic status.":
        _require(operation == "LinkDiagnostic" and
                 (not isinstance(value["status"], str) or value["status"] not in {"fail", "unknown", "unsupported"}),
                 "Diagnostic rejection has no invalid status")
        return "composition_evidence"
    _require(operation == "CompositionResult", f"Unclassified leaf rejection: {operation}: {message}")
    if message == "Invalid fields in PinnedIdentity.":
        identities = value["dependencies"]["identities"]
        _require(isinstance(identities, list), "Pinned-identity field rejection lost its array")
        for identity in identities:
            if not isinstance(identity, dict):
                return "invalid_type"
            # Pinned_identity.of_json checks unknown keys before required keys.
            if set(identity) - _IDENTITY_FIELDS:
                return "unknown_field"
            if _IDENTITY_FIELDS - set(identity):
                return "missing_field"
        raise AssertionError("Rejected pinned identities have no field-shape defect")
    if message == "Passing compositions cannot contain unresolved resource accounting.":
        _require(value["outcome"] == "pass" and isinstance(value["resource_usage"], list)
                 and any(item["status"] != "pass" for item in value["resource_usage"]),
                 "Passing-resource rejection lost its contradictory declaration")
        return "composition_evidence"
    if message == "Unsupported checker version.":
        deps = value["dependencies"]
        _require(deps["checker"] != "biocompiler.component_linker.v0.3"
                 or deps["admission_policy"] != "biocompiler.human_admission_policy.v0.1",
                 "Unsupported-version rejection has current versions")
        return "composition_evidence"
    raise AssertionError(f"Unclassified composition evidence rejection: {operation}: {message}")
