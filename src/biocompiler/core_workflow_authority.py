"""Native source-authority validation, without workflow execution or acceptance.

The separate artifact capability returns the complete normalized request. This
adapter checks its transport, schema and identities only. It never imports a
Python request constructor, invokes a checker or substitutes a stored result.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Callable, Literal, cast

from biocompiler.core_artifacts import (
    AUTHORITY_OPERATION, MAX_ARTIFACT_BYTES, MAX_CONTROL_BYTES, _canonical,
    _preflight_bytes, call_artifact, decode_artifact,
)
from biocompiler.core_client import (
    CoreCapabilities, CoreClient, CoreProtocolError, JsonValue, _object,
    decode_json, encode_json,
)
from biocompiler.core_workflow import (
    _limits, _same, capability_profile as _workflow_profile, effective_resources,
)

OPERATION = AUTHORITY_OPERATION
OPERATIONS = (OPERATION,)
_RECEIPT_FIELDS = {
    "schema_version", "profile", "operation", "executable", "request_id",
    "validation_scope", "implementation_version", "workflow_version",
    "workflow_operation", "mode", "authority_fingerprint", "request_fingerprint", "resources",
}
_REQUEST_FIELDS = {
    "schema_version", "realization", "candidate", "operation", "mode", "history",
    "until", "bounds", "signature", "max_evaluations",
}


def capability_profile() -> dict[str, Any]:
    """Return the exact authority-only capability as a defensive copy."""
    profile = _workflow_profile()
    del profile["record_schema"]
    profile.update(profile="biocompiler.core.verification_workflow_authority.v1",
                   implementation_version="biocompiler.ocaml.verification_workflow_authority.v0.1",
                   operations=list(OPERATIONS), validation_scope="fresh_source_authority_only")
    return profile


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


class _AuthorityCore(CoreClient):
    def negotiate(self, operation: str, *, cancelled: Callable[[], bool] | None = None) -> CoreCapabilities:
        capabilities = super().negotiate(operation, cancelled=cancelled)
        profile = capability_profile()
        if (not _same(capabilities.profiles.get("verification_workflow_authority"), profile)
                or AUTHORITY_OPERATION not in capabilities.operations
                or profile["validation_scope"] not in capabilities.validation_scopes):
            raise CoreProtocolError("Incompatible workflow authority profile, resources or validation scope")
        return capabilities


@dataclass(frozen=True)
class AuthorityResult:
    """Complete native request bytes; this object confers no workflow acceptance."""
    request_id: str
    operation: str
    executable: Literal["core", "verify"]
    workflow_operation: str
    mode: str
    authority_fingerprint: str
    request_fingerprint: str
    request_json: bytes
    _receipt_json: bytes
    _envelope_json: bytes

    @property
    def request(self) -> dict[str, Any]:
        return cast(dict[str, Any], decode_artifact(self.request_json))

    @property
    def receipt(self) -> dict[str, Any]:
        return cast(dict[str, Any], decode_json(self._receipt_json, limit=MAX_CONTROL_BYTES))

    @property
    def envelope(self) -> dict[str, Any]:
        return cast(dict[str, Any], decode_json(self._envelope_json, limit=MAX_CONTROL_BYTES))


@dataclass(frozen=True)
class AuthorityClient:
    core: CoreClient

    def validate(self, request: bytes, *, limits: JsonValue = None, request_id: str | None = None,
                 cancelled: Callable[[], bool] | None = None) -> AuthorityResult:
        # Freeze mutable controls before negotiation. The input's structural
        # decoder performs no Python source or biological semantic validation.
        reduced = _limits(limits)
        frozen_limits: JsonValue = None if limits is None else cast(JsonValue, dict(reduced))
        authority = decode_artifact(request, authority=True)
        canonical_authority = _canonical(authority, MAX_ARTIFACT_BYTES)
        profile = capability_profile()
        core = _AuthorityCore(self.core.executable, self.core.role,
                              self.core.timeout_seconds, self.core.expected_sha256)
        response = call_artifact(core, AUTHORITY_OPERATION,
            {"profile": profile["profile"], "limits": frozen_limits}, authority=request,
            output_limit=reduced["max_report_bytes"], request_id=request_id, cancelled=cancelled)
        envelope = _object(response.response.result,
            {"schema_version", "transport", "authority", "retained_record", "artifact", "result"},
            "Authority artifact envelope")
        receipt = _object(envelope["result"], _RECEIPT_FIELDS, "Workflow authority receipt")
        _preflight_bytes(response.artifact, limit=reduced["max_report_bytes"], nodes=reduced["max_report_nodes"])
        document = _object(decode_artifact(response.artifact), _REQUEST_FIELDS, "Normalized workflow request")
        if type(authority) is not dict:
            raise CoreProtocolError("Successful source authority must be a complete request object")
        action, mode = authority.get("operation"), authority.get("mode")
        if (type(action) is not str or action not in ("check", "explore", "reduce")
                or type(mode) is not str or mode not in ("candidate", "model")
                or document["schema_version"] != profile["request_schema"]
                or document["operation"] != action or document["mode"] != mode):
            raise CoreProtocolError("Normalized workflow authority schema, operation or mode differs")
        canonical_request = _canonical(document, reduced["max_report_bytes"])
        if canonical_request != response.artifact:
            raise CoreProtocolError("Normalized workflow authority is not canonical JSON")
        supplied_identity = _sha(canonical_authority)
        normalized_identity = _sha(response.artifact)
        expected: dict[str, JsonValue] = {
            "schema_version": "biocompiler.core.verification_workflow_authority_result.v1",
            "profile": profile["profile"], "operation": AUTHORITY_OPERATION,
            "executable": self.core.role, "request_id": response.response.request_id,
            "validation_scope": profile["validation_scope"],
            "implementation_version": profile["implementation_version"],
            "workflow_version": profile["workflow_version"], "workflow_operation": action, "mode": mode,
            "authority_fingerprint": supplied_identity, "request_fingerprint": normalized_identity,
            "resources": effective_resources(frozen_limits),
        }
        if not _same(receipt, expected):
            raise CoreProtocolError("Authority receipt differs from the complete request identities or effective resources")
        return AuthorityResult(response.response.request_id, AUTHORITY_OPERATION, self.core.role,
            action, mode, supplied_identity, normalized_identity, response.artifact,
            encode_json(receipt, limit=MAX_CONTROL_BYTES), encode_json(envelope, limit=MAX_CONTROL_BYTES))
