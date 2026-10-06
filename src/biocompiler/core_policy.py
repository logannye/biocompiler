"""Explicit transport to the independent OCaml policy source checker.

Only transport identity, representation and claim boundaries are checked here.
No Python evaluator, lowerer or realization implementation is imported or used.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Callable, Literal, cast

from biocompiler.core_client import (
    CoreClient, CoreProtocolError, CoreResponse, JsonValue,
    _names, _object, decode_json, encode_json,
)

VALIDATION_SCOPE = "policy-source-contracts-v0.1"
IMPLEMENTATION = "biocompiler.ocaml.policy_check.v0.1"
RESOURCE_PROFILE = "biocompiler.policy_frontend.resources.v0.1"
ASSESSMENT_SCHEMA = "biocompiler.policy_assessment.v0.1"
RESULT_SCHEMA = "biocompiler.core.policy_assessment.v1"
PROFILE: dict[str, JsonValue] = {
    "operations": ["assess-policy", "replay-policy-assessment"],
    "document_profile": "biocompiler.policy.v0.1",
    "assessment_schema": ASSESSMENT_SCHEMA,
    "implementation": IMPLEMENTATION,
    "resource_profile": RESOURCE_PROFILE,
    "validation_scope": VALIDATION_SCOPE,
    "max_document_bytes": 2 * 1024 * 1024,
    "max_depth": 64,
    "max_nodes": 100_000,
    "stages": {"representation": "implemented", "source_contracts": "implemented",
               "execution": "unsupported", "lowering": "unsupported", "realization": "unsupported"},
}
_ASSESSMENT_FIELDS = {
    "schema_version", "status", "document_digest", "program_digest", "artifact_digest",
    "declarations", "requirements", "required_features", "dependencies", "assumptions",
    "unresolved_obligations", "diagnostics", "semantic_status", "target_status", "lowering", "artifact",
}


def _fingerprint(value: JsonValue) -> str:
    return hashlib.sha256(encode_json(value)).hexdigest()


def _semantic(value: JsonValue) -> JsonValue:
    if isinstance(value, dict):
        return {key: _semantic(item) for key, item in value.items() if key not in ("source_map", "provenance")}
    if isinstance(value, list):
        return [_semantic(item) for item in value]
    return value


def _hash(value: JsonValue) -> str:
    if type(value) is not str or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise CoreProtocolError("Policy identity must be a lowercase SHA-256 fingerprint")
    return value


def _record(value: JsonValue, label: str) -> dict[str, JsonValue]:
    if type(value) is not dict:
        raise CoreProtocolError(label + " must be a record")
    return value


def _text(value: JsonValue, label: str) -> str:
    if type(value) is not str or not value.strip():
        raise CoreProtocolError(label + " must be nonempty text")
    return value


def _documents(raw: JsonValue) -> tuple[dict[str, JsonValue], dict[str, JsonValue]]:
    document = _record(raw, "Policy document")
    if document.get("$type") == "CompilationSubmission":
        document = _record(document.get("request"), "Submitted request")
    if document.get("$type") == "BuildRequest":
        program = _record(document.get("program"), "Policy program")
    elif document.get("$type") == "PolicyProgram":
        program = document
    else:
        raise CoreProtocolError("Native assessment requires a frozen program, request or submission")
    if program.get("$type") != "PolicyProgram":
        raise CoreProtocolError("Native assessment changed the frozen program type")
    return document, program


def _ledger(value: JsonValue, program: dict[str, JsonValue], *, requirements: bool, program_path: str) -> None:
    declarations, sources = program.get("declarations"), program.get("source_map")
    if type(declarations) is not list or type(sources) is not list or type(value) is not list:
        raise CoreProtocolError("Policy assessment must retain complete ordered declaration and source ledgers")
    expected = [(index, _record(row, "Declaration")) for index, row in enumerate(declarations)]
    if requirements:
        expected = [(index, row) for index, row in expected if row.get("$type") == "Requirement"]
    if len(value) != len(expected):
        raise CoreProtocolError("Native policy ledger omitted or added an occurrence")
    for actual, (index, original) in zip(value, expected):
        row = _object(actual, {"id", "kind", "path", "value", "sources"}, "Policy ledger entry")
        if row["id"] != original.get("id") or row["kind"] != original.get("$type") or row["value"] != original:
            raise CoreProtocolError("Native policy ledger changed source identity, ordering or meaning")
        matching = [source for source in sources if _record(source, "Source correspondence").get("declaration_id") == row["id"]]
        if row["sources"] != matching:
            raise CoreProtocolError("Native policy ledger lost source correspondence")
        if row["path"] != f"{program_path}/declarations/{index}":
            raise CoreProtocolError("Native policy ledger changed its exact source path")


@dataclass(frozen=True)
class PolicyAssessment:
    """A retained native source assessment; replay requires the original document.

    This record grants no execution, molecular artifact or therapeutic acceptance.
    Every assessment read returns a new container rather than mutable authority.
    """
    request_id: str
    operation: str
    executable: Literal["core", "verify"]
    status: Literal["valid", "invalid"]
    document_digest: str
    program_digest: str
    artifact_digest: str
    assessment_fingerprint: str
    _assessment_json: bytes

    @property
    def assessment(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], decode_json(self._assessment_json))


def _result(response: CoreResponse, raw: JsonValue) -> PolicyAssessment:
    result = _object(response.result, {"schema_version", "implementation", "resource_profile", "validation_scope",
                                      "supplied_document_fingerprint", "assessment_fingerprint", "assessment"}, "Policy result")
    if (result["schema_version"] != RESULT_SCHEMA or result["implementation"] != IMPLEMENTATION
            or result["resource_profile"] != RESOURCE_PROFILE or result["validation_scope"] != VALIDATION_SCOPE):
        raise CoreProtocolError("Native policy result changed its negotiated profile")
    artifact_digest = _fingerprint(raw)
    if _hash(result["supplied_document_fingerprint"]) != artifact_digest:
        raise CoreProtocolError("Native policy result belongs to different supplied authority")
    assessment = _object(result["assessment"], _ASSESSMENT_FIELDS, "Policy assessment")
    if (assessment["schema_version"] != ASSESSMENT_SCHEMA or assessment["semantic_status"] != "unresolved"
            or assessment["target_status"] != "unassessed" or assessment["lowering"] != "unsupported"
            or assessment["artifact"] != "withheld"):
        raise CoreProtocolError("Native policy assessment upgraded an unsupported claim")
    document, program = _documents(raw)
    document_digest, program_digest = _fingerprint(_semantic(document)), _fingerprint(_semantic(program))
    if (assessment["artifact_digest"] != artifact_digest or assessment["document_digest"] != document_digest
            or assessment["program_digest"] != program_digest):
        raise CoreProtocolError("Native policy assessment changed source or deployment identities")
    root = _record(raw, "Policy document")
    program_path = "/document" + ("/request" if root["$type"] == "CompilationSubmission" else "")
    if document["$type"] == "BuildRequest":
        program_path += "/program"
    _ledger(assessment["declarations"], program, requirements=False, program_path=program_path)
    _ledger(assessment["requirements"], program, requirements=True, program_path=program_path)
    for key in ("required_features", "assumptions", "unresolved_obligations"):
        _names(assessment[key], "Policy " + key)
    diagnostics = assessment["diagnostics"]
    if type(diagnostics) is not list:
        raise CoreProtocolError("Policy diagnostics must be a list")
    for item in diagnostics:
        diagnostic = _object(item, {"code", "message", "path"}, "Policy diagnostic")
        _text(diagnostic["code"], "Diagnostic code")
        _text(diagnostic["message"], "Diagnostic message")
        if type(diagnostic["path"]) is not str or not diagnostic["path"].startswith("/document"):
            raise CoreProtocolError("Policy diagnostic is missing its source path")
    status = assessment["status"]
    if status not in ("valid", "invalid") or (status == "valid") != (len(diagnostics) == 0):
        raise CoreProtocolError("Contradictory native policy source status")
    dependencies = assessment["dependencies"]
    if type(dependencies) is not list:
        raise CoreProtocolError("Policy dependencies must be a list")
    seen: set[tuple[str, str, str]] = set()
    for dependency in dependencies:
        pin = _object(dependency, {"$type", "id", "version", "digest"}, "Policy dependency")
        if pin["$type"] != "DefinitionRef":
            raise CoreProtocolError("Policy dependency changed its type")
        identity = (_text(pin["id"], "Definition identity"), _text(pin["version"], "Definition version"), _hash(pin["digest"]))
        if identity in seen:
            raise CoreProtocolError("Duplicate native policy dependency")
        seen.add(identity)
    fingerprint = _hash(result["assessment_fingerprint"])
    if fingerprint != _fingerprint(assessment):
        raise CoreProtocolError("Native policy assessment fingerprint mismatch")
    return PolicyAssessment(response.request_id, response.operation, response.executable,
                            cast(Literal["valid", "invalid"], status), document_digest, program_digest,
                            artifact_digest, fingerprint, encode_json(assessment))


@dataclass(frozen=True)
class PolicyClient:
    transport: CoreClient

    def _call(self, operation: str, payload: dict[str, JsonValue], *,
              cancelled: Callable[[], bool] | None) -> PolicyAssessment:
        snapshot = cast(dict[str, JsonValue], decode_json(encode_json(payload)))
        raw = snapshot["document" if operation == "assess-policy" else "expected_document"]
        capabilities = self.transport.negotiate(operation, cancelled=cancelled)
        if capabilities.profiles.get("policy_frontend") != PROFILE or VALIDATION_SCOPE not in capabilities.validation_scopes:
            raise CoreProtocolError("Selected executable lacks the exact native policy front-end profile")
        result = _result(self.transport.call(operation, snapshot, cancelled=cancelled), raw)
        if operation == "replay-policy-assessment" and result.assessment != snapshot["assessment"]:
            raise CoreProtocolError("Fresh policy replay differs from the retained assessment")
        return result

    def assess(self, document: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyAssessment:
        return self._call("assess-policy", {"document": document}, cancelled=cancelled)

    def replay(self, *, expected_document: JsonValue, assessment: JsonValue,
               cancelled: Callable[[], bool] | None = None) -> PolicyAssessment:
        return self._call("replay-policy-assessment", {"expected_document": expected_document,
                                                     "assessment": assessment}, cancelled=cancelled)
