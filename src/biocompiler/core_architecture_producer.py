"""Typed, immutable transport for native architecture production and export.

The native producer and independent checker own all semantic decisions. This
adapter checks the complete transport contract, artifact bytes and scoped
assessment without importing Python production or checking implementations.
Stored results do not grant authority to a later export or replay.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
from typing import Callable, Literal, cast

from biocompiler.core_architecture import (
    ASSESSMENT_SCHEMA, IMPLEMENTATION as CHECKER_IMPLEMENTATION,
    RESOURCE_PROFILE as CHECKER_RESOURCE_PROFILE, ArchitectureResult,
    _hash, _result as _assessment_result,
)
from biocompiler.core_client import (
    LIMITS, CoreCapabilities, CoreClient, CoreProtocolError, CoreResponse,
    JsonValue, _names, _object, decode_json, encode_json,
)


VALIDATION_SCOPE = "supplied-architecture-production-v1"
IMPLEMENTATION = "biocompiler.ocaml.architecture_producer.v0.1"
RESOURCE_PROFILE = "biocompiler.architecture_producer.resources.v1"
BUILD_RESULT_SCHEMA = "biocompiler.core.architecture_build.v1"
EXPORT_RESULT_SCHEMA = "biocompiler.core.architecture_export.v1"
BUILD_SCHEMA = "biocompiler.payload_architecture_build.v0.2"
EXPORT_SCHEMA = "biocompiler.payload_architecture_export.v0.1"
PROFILE: dict[str, JsonValue] = {
    "operations": ["compile-architecture", "export-architecture"],
    "request_schema": "biocompiler.payload_architecture_request.v0.1",
    "build_schema": BUILD_SCHEMA,
    "export_schema": EXPORT_SCHEMA,
    "assessment_schema": ASSESSMENT_SCHEMA,
    "implementation": IMPLEMENTATION,
    "resource_profile": RESOURCE_PROFILE,
    "checker_implementation": CHECKER_IMPLEMENTATION,
    "checker_resource_profile": CHECKER_RESOURCE_PROFILE,
    "validation_scope": VALIDATION_SCOPE,
}
BuildStatus = Literal["compiled", "partial", "unsupported", "no_solution", "search_exhausted"]
_BUILD_KEYS = {"schema_version", "request_fingerprint", "execution", "plan", "construction",
               "alternatives", "diagnostics", "status", "match_instances"}
_IDENTITY_KEYS = {"schema_version", "implementation", "resource_profile", "validation_scope",
                  "supplied_request_fingerprint", "request_fingerprint", "build_fingerprint", "verification"}


def _encoded(value: JsonValue) -> bytes:
    return encode_json(value, limit=LIMITS["max_response_bytes"])


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fingerprint(value: JsonValue) -> str:
    return _digest(_encoded(value))


def _text(value: JsonValue, label: str) -> str:
    if type(value) is not str:
        raise CoreProtocolError(f"{label} must be UTF-8 text")
    return value


def _document(value: JsonValue, label: str) -> tuple[bytes, dict[str, JsonValue]]:
    text = _text(value, label)
    data = text.encode("utf-8")
    document = decode_json(data)
    if type(document) is not dict or _encoded(document) != data:
        raise CoreProtocolError(f"{label} must be an exact canonical JSON object without a newline")
    return data, document


def _negotiate(capabilities: CoreCapabilities) -> None:
    if (capabilities.profiles.get("architecture_producer") != PROFILE
            or VALIDATION_SCOPE not in capabilities.validation_scopes):
        raise CoreProtocolError("Incompatible architecture producer schemas, implementations, resource profiles or scope")


def _identity(result: dict[str, JsonValue], schema: str, supplied_request: JsonValue) -> tuple[str, str, str]:
    if (result["schema_version"] != schema or result["implementation"] != IMPLEMENTATION
            or result["resource_profile"] != RESOURCE_PROFILE or result["validation_scope"] != VALIDATION_SCOPE):
        raise CoreProtocolError("Architecture producer result changed its negotiated profile")
    supplied = _hash(result["supplied_request_fingerprint"], "Supplied request")
    if supplied != _fingerprint(supplied_request):
        raise CoreProtocolError("Architecture producer result is bound to a different supplied request")
    return supplied, _hash(result["request_fingerprint"], "Request"), _hash(result["build_fingerprint"], "Build")


def _build(value: JsonValue, request_fingerprint: str, build_fingerprint: str) -> tuple[dict[str, JsonValue], BuildStatus]:
    build = _object(value, _BUILD_KEYS, "Architecture build")
    status = build["status"]
    if (build["schema_version"] != BUILD_SCHEMA or build["request_fingerprint"] != request_fingerprint
            or _fingerprint(build) != build_fingerprint):
        raise CoreProtocolError("Architecture build schema or complete identity mismatch")
    if type(status) is not str or status not in {"compiled", "partial", "unsupported", "no_solution", "search_exhausted"}:
        raise CoreProtocolError("Invalid architecture build status")
    return build, cast(BuildStatus, status)


def _verification(response: CoreResponse, result: dict[str, JsonValue], *, request: JsonValue,
                  build: JsonValue, request_fingerprint: str, build_fingerprint: str) -> ArchitectureResult:
    verification = _assessment_result(replace(response, result=result["verification"]),
                                      {"expected_request": request, "build": build})
    if (verification.request_fingerprint != request_fingerprint
            or verification.build_fingerprint != build_fingerprint):
        raise CoreProtocolError("Producer artifact and independent verification identities disagree")
    return verification


@dataclass(frozen=True)
class ArchitectureCompileResult:
    """Complete build bytes plus the separately scoped fresh native assessment."""

    request_id: str
    supplied_request_fingerprint: str
    request_fingerprint: str
    build_fingerprint: str
    status: BuildStatus
    build_json: bytes
    verification: ArchitectureResult

    @property
    def build(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], decode_json(self.build_json))


@dataclass(frozen=True)
class ArchitectureExportResult:
    """Inseparable RNA FASTA and full manifest bytes, each pinned independently."""

    request_id: str
    supplied_request_fingerprint: str
    supplied_build_fingerprint: str
    request_fingerprint: str
    build_fingerprint: str
    export_fingerprint: str
    fasta_sha256: str
    manifest_sha256: str
    fasta_bytes: bytes
    manifest_json: bytes
    verification: ArchitectureResult

    @property
    def fasta(self) -> str:
        return self.fasta_bytes.decode("utf-8")

    @property
    def manifest(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], decode_json(self.manifest_json))

    @property
    def export(self) -> dict[str, JsonValue]:
        return {"schema_version": EXPORT_SCHEMA, "fasta": self.fasta, "manifest": self.manifest}


def _compile_result(response: CoreResponse, payload: dict[str, JsonValue]) -> ArchitectureCompileResult:
    result = _object(response.result, _IDENTITY_KEYS | {"build_json"}, "Architecture compile result")
    supplied, request_fingerprint, build_fingerprint = _identity(result, BUILD_RESULT_SCHEMA, payload["request"])
    data, document = _document(result["build_json"], "Build JSON")
    build, status = _build(document, request_fingerprint, build_fingerprint)
    verification = _verification(response, result, request=payload["request"], build=build,
                                 request_fingerprint=request_fingerprint, build_fingerprint=build_fingerprint)
    return ArchitectureCompileResult(response.request_id, supplied, request_fingerprint,
                                     build_fingerprint, status, data, verification)


def _export_result(response: CoreResponse, payload: dict[str, JsonValue]) -> ArchitectureExportResult:
    result = _object(response.result, _IDENTITY_KEYS | {
        "supplied_build_fingerprint", "export_fingerprint", "fasta", "fasta_sha256", "manifest_json", "manifest_sha256",
    }, "Architecture export result")
    supplied, request_fingerprint, build_fingerprint = _identity(result, EXPORT_RESULT_SCHEMA, payload["expected_request"])
    supplied_build = _hash(result["supplied_build_fingerprint"], "Supplied build")
    if supplied_build != _fingerprint(payload["build"]):
        raise CoreProtocolError("Architecture export is bound to a different supplied build")
    verification = _verification(response, result, request=payload["expected_request"], build=payload["build"],
                                 request_fingerprint=request_fingerprint, build_fingerprint=build_fingerprint)
    if verification.outcome != "pass" or not verification.construction_complete:
        raise CoreProtocolError("Architecture export lacks fresh passing construction verification")
    fasta = _text(result["fasta"], "FASTA")
    fasta_bytes = fasta.encode("utf-8")
    fasta_sha256 = _hash(result["fasta_sha256"], "FASTA")
    if not fasta.startswith(">") or _digest(fasta_bytes) != fasta_sha256:
        raise CoreProtocolError("Architecture FASTA bytes or fingerprint mismatch")
    manifest_json, document = _document(result["manifest_json"], "Manifest JSON")
    manifest_sha256 = _hash(result["manifest_sha256"], "Manifest")
    manifest = _object(document, {"request_fingerprint", "build", "verification", "delivered_member_ids", "source_authority"},
                       "Architecture export manifest")
    if (_digest(manifest_json) != manifest_sha256 or manifest["request_fingerprint"] != request_fingerprint
            or manifest["source_authority"] != "Retain the independently supplied request separately."):
        raise CoreProtocolError("Architecture manifest bytes, request or authority mismatch")
    _build(manifest["build"], request_fingerprint, build_fingerprint)
    if _encoded(manifest["verification"]) != verification._assessment_json:
        raise CoreProtocolError("Architecture manifest omitted or changed its complete independent assessment")
    if not _names(manifest["delivered_member_ids"], "Delivered member identities"):
        raise CoreProtocolError("Architecture export has no delivered members")
    artifact: JsonValue = {"schema_version": EXPORT_SCHEMA, "fasta": fasta, "manifest": manifest}
    export_fingerprint = _hash(result["export_fingerprint"], "Export")
    if _fingerprint(artifact) != export_fingerprint:
        raise CoreProtocolError("Complete architecture export fingerprint mismatch")
    return ArchitectureExportResult(response.request_id, supplied, supplied_build, request_fingerprint,
                                    build_fingerprint, export_fingerprint, fasta_sha256, manifest_sha256,
                                    fasta_bytes, manifest_json, verification)


@dataclass(frozen=True)
class ArchitectureProducerClient:
    transport: CoreClient

    def _call(self, operation: str, payload: dict[str, JsonValue], *,
              cancelled: Callable[[], bool] | None) -> tuple[CoreResponse, dict[str, JsonValue]]:
        if self.transport.role != "core":
            raise CoreProtocolError("Architecture production requires the core executable role")
        # Freeze caller-owned authority before negotiation or any subprocess I/O.
        snapshot = cast(dict[str, JsonValue], decode_json(encode_json(payload)))
        _negotiate(self.transport.negotiate(operation, cancelled=cancelled))
        return self.transport.call(operation, snapshot, cancelled=cancelled), snapshot

    def compile(self, *, request: JsonValue, cancelled: Callable[[], bool] | None = None) -> ArchitectureCompileResult:
        response, payload = self._call("compile-architecture", {"request": request}, cancelled=cancelled)
        return _compile_result(response, payload)

    def export(self, *, expected_request: JsonValue, build: JsonValue,
               cancelled: Callable[[], bool] | None = None) -> ArchitectureExportResult:
        response, payload = self._call("export-architecture", {"expected_request": expected_request, "build": build},
                                       cancelled=cancelled)
        return _export_result(response, payload)
