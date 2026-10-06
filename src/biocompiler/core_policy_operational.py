"""Explicit transport for the bounded native operational policy profile.

Python checks transport identity, retained authority and claim boundaries. It
does not lower policies, interpret timelines or supply a semantic fallback.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
from typing import Callable, Literal, cast

from biocompiler.core_client import (
    CoreClient, CoreProtocolError, CoreResponse, JsonValue,
    _object, decode_json, encode_json,
)
from biocompiler import core_policy as source

VALIDATION_SCOPE = "bounded-policy-operational-v0.1"
IMPLEMENTATION = "biocompiler.ocaml.policy_operational.v0.1"
RESOURCE_PROFILE = "biocompiler.policy_operational.resources.v0.1"
RESULT_SCHEMA = "biocompiler.core.policy_operational.v1"
REPORT_SCHEMA = "biocompiler.policy_lowering_report.v0.1"
CANDIDATE_SCHEMA = "biocompiler.policy_behavior.v0.1"
OPERATIONAL_PROFILE = "biocompiler.policy_operational.v0.1"
EXECUTION_SCHEMA = "biocompiler.policy_execution.v0.1"
PROFILE: dict[str, JsonValue] = {
    "operations": ["check-policy-lowering", "execute-policy", "replay-policy-execution"],
    "document_profile": "biocompiler.policy.v0.1",
    "schema_version": RESULT_SCHEMA,
    "implementation": IMPLEMENTATION,
    "resource_profile": RESOURCE_PROFILE,
    "validation_scope": VALIDATION_SCOPE,
    "artifact": "withheld",
    "target_status": "unassessed",
}
PRODUCER_PROFILE: dict[str, JsonValue] = {
    "operations": ["compile-policy"],
    "implementation": IMPLEMENTATION,
    "validation_scope": VALIDATION_SCOPE,
}
_RESULT_FIELDS = {
    "schema_version", "implementation", "resource_profile", "validation_scope",
    "request_fingerprint", "candidate_fingerprint", "report_fingerprint", "candidate", "report",
}
_REPORT_FIELDS = {
    "schema_version", "source_assessment", "correspondence", "artifact", "target_status", "realization",
}
_CANDIDATE_FIELDS = {
    "schema_version", "profile", "source_document", "descriptor_bundle", "source_artifact_digest",
    "descriptors_digest", "source_ledger", "requirements_ledger", "assumptions", "unresolved_obligations", "nodes",
}
_CORRESPONDENCE_FIELDS = {
    "schema_version", "status", "profile", "document_artifact_digest", "descriptors_digest",
    "candidate_fingerprint", "source_assessment", "admission", "requirements", "assumptions",
    "unresolved_obligations", "target_status", "artifact",
}
_ADMISSION_FIELDS = {
    "schema_version", "status", "profile", "document_artifact_digest", "descriptors_digest",
    "source_assessment", "target_status", "artifact",
}
_EXECUTION_FIELDS = {
    "schema_version", "profile", "behavior_digest", "timeline_digest", "horizon", "executor", "status",
    "frames", "attempts", "requirements", "usage", "claim",
}


def _fingerprint(value: JsonValue) -> str:
    return hashlib.sha256(encode_json(value)).hexdigest()


def _same(left: JsonValue, right: JsonValue) -> bool:
    return encode_json(left) == encode_json(right)


def _pin(actual: JsonValue, expected: JsonValue, label: str) -> str:
    digest = _fingerprint(expected)
    if actual != digest:
        raise CoreProtocolError(label + " fingerprint does not match complete supplied authority")
    return digest


def _source_assessment(response: CoreResponse, report: JsonValue, document: JsonValue) -> source.PolicyAssessment:
    """Reuse the source profile's representation checks, without semantic work."""
    wrapper: JsonValue = {
        "schema_version": source.RESULT_SCHEMA,
        "implementation": source.IMPLEMENTATION,
        "resource_profile": source.RESOURCE_PROFILE,
        "validation_scope": source.VALIDATION_SCOPE,
        "supplied_document_fingerprint": _fingerprint(document),
        "assessment_fingerprint": _fingerprint(report),
        "assessment": report,
    }
    assessment = source._result(replace(response, result=wrapper), document)
    _, program = source._documents(document)
    declarations = cast(list[JsonValue], program["declarations"])
    sources = cast(list[dict[str, JsonValue]], program["source_map"])
    retained = assessment.assessment
    for key, originals in (
        ("declarations", declarations),
        ("requirements", [value for value in declarations if cast(dict[str, JsonValue], value)["$type"] == "Requirement"]),
    ):
        for value, original in zip(cast(list[JsonValue], retained[key]), originals):
            row = cast(dict[str, JsonValue], value)
            matches: JsonValue = [span for span in sources if span["declaration_id"] == row["id"]]
            if not _same(row["value"], original) or not _same(row["sources"], matches):
                raise CoreProtocolError("Operational source assessment changed an exact source occurrence")
    return assessment


def _candidate(value: JsonValue, payload: dict[str, JsonValue], assessment: dict[str, JsonValue]) -> dict[str, JsonValue]:
    candidate = _object(value, _CANDIDATE_FIELDS, "Operational policy candidate")
    if candidate["schema_version"] != CANDIDATE_SCHEMA or candidate["profile"] != OPERATIONAL_PROFILE:
        raise CoreProtocolError("Operational candidate changed its negotiated schema or profile")
    if (not _same(candidate["source_document"], payload["document"])
            or not _same(candidate["descriptor_bundle"], payload["definitions"])):
        raise CoreProtocolError("Operational candidate changed complete source or definition authority")
    if "candidate" in payload and not _same(value, payload["candidate"]):
        raise CoreProtocolError("Native checker replaced the supplied operational candidate")
    _pin(candidate["source_artifact_digest"], payload["document"], "Candidate source")
    _pin(candidate["descriptors_digest"], payload["definitions"], "Candidate definitions")
    for candidate_key, assessment_key in (
        ("source_ledger", "declarations"), ("requirements_ledger", "requirements"),
        ("assumptions", "assumptions"), ("unresolved_obligations", "unresolved_obligations"),
    ):
        if not _same(candidate[candidate_key], assessment[assessment_key]):
            raise CoreProtocolError("Operational candidate lost complete source " + assessment_key)
    if type(candidate["nodes"]) is not list:
        raise CoreProtocolError("Operational candidate nodes must be a list")
    for value in candidate["nodes"]:
        node = _object(value, {"id", "kind", "source_path", "data"}, "Operational node")
        if any(type(node[field]) is not str or not node[field] for field in ("id", "kind", "source_path")):
            raise CoreProtocolError("Operational node identity, kind and source path must be nonempty text")
        if type(node["data"]) is not dict:
            raise CoreProtocolError("Operational node data must be a record")
    return candidate


def _correspondence(value: JsonValue, payload: dict[str, JsonValue], candidate: JsonValue,
                    assessment: dict[str, JsonValue]) -> None:
    correspondence = _object(value, _CORRESPONDENCE_FIELDS, "Operational correspondence")
    admission = _object(correspondence["admission"], _ADMISSION_FIELDS, "Operational admission")
    for checked, schema, status in (
        (correspondence, "biocompiler.policy_correspondence.v0.1", "valid"),
        (admission, "biocompiler.policy_operational_admission.v0.1", "admitted"),
    ):
        if (checked["schema_version"] != schema or checked["status"] != status
                or checked["profile"] != OPERATIONAL_PROFILE or checked["target_status"] != "unassessed"
                or checked["artifact"] != "withheld"):
            raise CoreProtocolError("Operational correspondence changed its admitted scope")
        _pin(checked["document_artifact_digest"], payload["document"], "Correspondence source")
        _pin(checked["descriptors_digest"], payload["definitions"], "Correspondence definitions")
        if not _same(checked["source_assessment"], assessment):
            raise CoreProtocolError("Operational correspondence changed its complete source assessment")
    _pin(correspondence["candidate_fingerprint"], candidate, "Correspondence candidate")
    for key in ("requirements", "assumptions", "unresolved_obligations"):
        if not _same(correspondence[key], assessment[key]):
            raise CoreProtocolError("Operational correspondence omitted or altered source " + key)


def _execution(value: JsonValue, payload: dict[str, JsonValue], candidate: JsonValue) -> None:
    execution = _object(value, _EXECUTION_FIELDS, "Operational execution")
    if (execution["schema_version"] != EXECUTION_SCHEMA or execution["profile"] != OPERATIONAL_PROFILE
            or execution["status"] != "complete" or execution["claim"] != "bounded_supplied_timeline_only"):
        raise CoreProtocolError("Operational execution changed its bounded claim")
    _pin(execution["behavior_digest"], candidate, "Execution candidate")
    _pin(execution["timeline_digest"], payload["timeline"], "Execution timeline and bounds")
    timeline = source._record(payload["timeline"], "Supplied timeline")
    for field in ("horizon", "executor"):
        if not _same(execution[field], timeline.get(field)):
            raise CoreProtocolError("Operational execution changed supplied timeline " + field)
    for field in ("frames", "attempts", "requirements"):
        if type(execution[field]) is not list or any(type(row) is not dict for row in execution[field]):
            raise CoreProtocolError("Operational execution " + field + " must be a list of records")
    usage = _object(execution["usage"], {"ticks", "work", "trace_items", "attempts"}, "Execution resource usage")
    bounds = source._record(timeline.get("bounds"), "Supplied execution bounds")
    for field, bound in (("ticks", "max_ticks"), ("work", "max_work"), ("trace_items", "max_trace_items"), ("attempts", "max_attempts")):
        count, maximum = usage[field], bounds.get(bound)
        if type(count) is not int or count < 0 or type(maximum) is not int or maximum < count:
            raise CoreProtocolError("Execution resource usage exceeds or changes its supplied bounds")
    for field, count in (("frames", "ticks"), ("attempts", "attempts")):
        if len(cast(list[JsonValue], execution[field])) != usage[count]:
            raise CoreProtocolError("Execution retained an incomplete " + field + " ledger")
    lowered = cast(dict[str, JsonValue], candidate)
    originals = cast(list[dict[str, JsonValue]], lowered["requirements_ledger"])
    requirements = cast(list[JsonValue], execution["requirements"])
    if len(requirements) != len(originals):
        raise CoreProtocolError("Execution omitted or added an original source requirement")
    for value, original in zip(requirements, originals):
        requirement = _object(value, {"id", "kind", "status", "source", "assumptions", "conditional", "coverage", "obligations"},
                              "Executed requirement")
        declaration = cast(dict[str, JsonValue], original["value"])
        if (requirement["id"] != original["id"] or requirement["kind"] != declaration["kind"]
                or not _same(requirement["source"], declaration)
                or not _same(requirement["assumptions"], declaration["assumptions"])):
            raise CoreProtocolError("Execution changed an original requirement identity, source or assumptions")
        if (requirement["status"] not in ("pass", "fail", "unknown", "unsupported")
                or type(requirement["conditional"]) is not bool
                or requirement["conditional"] != bool(declaration["assumptions"] or lowered["assumptions"])):
            raise CoreProtocolError("Execution changed a requirement's conditional claim boundary")
        coverage = _object(requirement["coverage"],
                           {"samples", "true", "false", "unknown", "triggers", "active", "inactive", "horizon_complete"},
                           "Requirement coverage")
        if type(coverage["horizon_complete"]) is not bool or any(
            type(count) is not int or count < 0 for key, count in coverage.items() if key != "horizon_complete"
        ):
            raise CoreProtocolError("Execution requirement coverage must retain nonnegative counts and horizon status")
        obligations = requirement["obligations"]
        if type(obligations) is not list:
            raise CoreProtocolError("Execution requirement obligations must be a complete list")
        for obligation in obligations:
            row = _object(obligation, {"trigger", "binding", "attempt", "opened_at", "deadline", "status", "closed_at", "response_unknown"},
                          "Requirement obligation")
            if row["status"] not in ("pass", "fail", "unknown") or type(row["response_unknown"]) is not bool:
                raise CoreProtocolError("Execution obligation changed its bounded status")
            binding = _object(row["binding"], {"encounter", "generation"}, "Obligation binding")
            if (binding["encounter"] is not None and type(binding["encounter"]) is not str
                    or type(binding["generation"]) is not int or binding["generation"] < 0):
                raise CoreProtocolError("Execution obligation lost its encounter generation binding")
            for field in ("trigger", "opened_at", "deadline"):
                source._text(row[field], "Obligation " + field)
            for field in ("attempt", "closed_at"):
                if row[field] is not None:
                    source._text(row[field], "Obligation " + field)


@dataclass(frozen=True)
class OperationalPolicyResult:
    """Immutable native transport result; every JSON read returns a new snapshot."""

    request_id: str
    operation: str
    executable: Literal["core", "verify"]
    request_fingerprint: str
    candidate_fingerprint: str
    report_fingerprint: str
    _result_json: bytes

    @property
    def result(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], decode_json(self._result_json))

    @property
    def candidate(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], self.result["candidate"])

    @property
    def report(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], self.result["report"])


def _result(response: CoreResponse, payload: dict[str, JsonValue]) -> OperationalPolicyResult:
    result = _object(response.result, _RESULT_FIELDS, "Operational policy result")
    if (result["schema_version"] != RESULT_SCHEMA or result["implementation"] != IMPLEMENTATION
            or result["resource_profile"] != RESOURCE_PROFILE or result["validation_scope"] != VALIDATION_SCOPE):
        raise CoreProtocolError("Native operational policy result changed its negotiated profile")
    request = {key: value for key, value in payload.items() if key != "report"}
    request_fingerprint = _pin(result["request_fingerprint"], request, "Operational request")
    candidate_fingerprint = _pin(result["candidate_fingerprint"], result["candidate"], "Operational candidate")
    report_fingerprint = _pin(result["report_fingerprint"], result["report"], "Operational report")
    executing = response.operation in ("execute-policy", "replay-policy-execution")
    report = _object(result["report"], _REPORT_FIELDS | ({"execution"} if executing else set()), "Operational policy report")
    if (report["schema_version"] != REPORT_SCHEMA or report["artifact"] != "withheld"
            or report["target_status"] != "unassessed" or report["realization"] != "unassessed"):
        raise CoreProtocolError("Native operational report upgraded an unsupported claim")
    assessment = _source_assessment(response, report["source_assessment"], payload["document"])
    if assessment.status != "valid":
        raise CoreProtocolError("Native operational success requires a valid source assessment")
    _candidate(result["candidate"], payload, assessment.assessment)
    _correspondence(report["correspondence"], payload, result["candidate"], assessment.assessment)
    if executing:
        _execution(report["execution"], payload, result["candidate"])
    if response.operation == "replay-policy-execution" and not _same(report, payload["report"]):
        raise CoreProtocolError("Fresh policy execution replay differs from the complete retained report")
    return OperationalPolicyResult(response.request_id, response.operation, response.executable,
                                   request_fingerprint, candidate_fingerprint, report_fingerprint,
                                   encode_json(result))


@dataclass(frozen=True)
class OperationalPolicyClient:
    transport: CoreClient

    def _call(self, operation: str, payload: dict[str, JsonValue], *,
              cancelled: Callable[[], bool] | None) -> OperationalPolicyResult:
        snapshot = cast(dict[str, JsonValue], decode_json(encode_json(payload)))
        if operation == "compile-policy" and self.transport.role != "core":
            raise CoreProtocolError("Policy compilation requires an explicitly selected core producer")
        capabilities = self.transport.negotiate(operation, cancelled=cancelled)
        if (capabilities.profiles.get("policy_operational") != PROFILE
                or VALIDATION_SCOPE not in capabilities.validation_scopes):
            raise CoreProtocolError("Selected executable lacks the exact native operational policy profile")
        if operation == "compile-policy" and capabilities.profiles.get("policy_operational_producer") != PRODUCER_PROFILE:
            raise CoreProtocolError("Selected executable lacks the exact native operational policy producer profile")
        return _result(self.transport.call(operation, snapshot, cancelled=cancelled), snapshot)

    def compile(self, document: JsonValue, definitions: JsonValue, *,
                cancelled: Callable[[], bool] | None = None) -> OperationalPolicyResult:
        return self._call("compile-policy", {"document": document, "definitions": definitions}, cancelled=cancelled)

    def check_lowering(self, document: JsonValue, definitions: JsonValue, candidate: JsonValue, *,
                       cancelled: Callable[[], bool] | None = None) -> OperationalPolicyResult:
        return self._call("check-policy-lowering", {"document": document, "definitions": definitions,
                                                   "candidate": candidate}, cancelled=cancelled)

    def execute(self, document: JsonValue, definitions: JsonValue, candidate: JsonValue, timeline: JsonValue, *,
                cancelled: Callable[[], bool] | None = None) -> OperationalPolicyResult:
        return self._call("execute-policy", {"document": document, "definitions": definitions,
                                            "candidate": candidate, "timeline": timeline}, cancelled=cancelled)

    def replay(self, document: JsonValue, definitions: JsonValue, candidate: JsonValue, timeline: JsonValue,
               report: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> OperationalPolicyResult:
        return self._call("replay-policy-execution", {"document": document, "definitions": definitions,
                                                     "candidate": candidate, "timeline": timeline,
                                                     "report": report}, cancelled=cancelled)
