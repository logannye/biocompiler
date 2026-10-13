"""Strict transport for fresh native joined material/behavior checking.

Retained child reports are checked as evidence documents, never converted into
native acceptance tokens. This module contains no RNA constructor or evaluator.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Callable, cast

from . import core_policy_controlled_composition as admission
from . import core_policy_controlled_material as material
from . import core_policy_controlled_behavior as behavior
from .core_client import CoreClient, CoreProtocolError, CoreResponse, JsonValue, _object, decode_json, encode_json
from .core_policy_material import PolicyMaterialResult, _artifact_members, _publication
from .core_policy_operational import _fingerprint, _pin, _same

COMPILE = "compile-policy-controlled-workflow"
CHECK = "check-policy-controlled-workflow"
REPLAY = "replay-policy-controlled-workflow"
EXPORT = "export-policy-controlled-workflow"
REQUEST_SCHEMA = "biocompiler.policy_controlled_workflow_request.v0.1"
LIMITS_SCHEMA = "biocompiler.policy_controlled_workflow_limits.v0.1"
CANDIDATE_SCHEMA = "biocompiler.policy_controlled_workflow_candidate.v0.1"
REPORT_SCHEMA = "biocompiler.policy_controlled_workflow_assessment.v0.1"
MANIFEST_SCHEMA = "biocompiler.policy_controlled_workflow_manifest.v0.1"
RESULT_SCHEMA = "biocompiler.core.policy_controlled_workflow.v1"
IMPLEMENTATION = "biocompiler.ocaml.policy_controlled_workflow.v0.1"
VALIDATION_SCOPE = "policy-controlled-workflow-v0.1"
ACCEPTED_STATUS = "controlled_workflow_accepted"
PROFILE: dict[str, JsonValue] = {**admission.PROFILE, "operations": [CHECK, REPLAY, EXPORT],
    "request_schema": REQUEST_SCHEMA, "candidate_schema": CANDIDATE_SCHEMA,
    "limits_schema": LIMITS_SCHEMA, "schema_version": RESULT_SCHEMA,
    "implementation": IMPLEMENTATION, "validation_scope": VALIDATION_SCOPE,
    "stage": "joined", "artifact": "checked_pair"}
PRODUCER_PROFILE: dict[str, JsonValue] = {**PROFILE, "operations": [CHECK, REPLAY, EXPORT, COMPILE]}
_REPORT_FIELDS = set("schema_version profile implementation stage status outcome claim_scope request_fingerprint candidate_fingerprint invocation_fingerprint material behavior project_context context limits resources budgets empirical_status human_use therapeutic_export".split())
_MANIFEST_FIELDS = set("schema_version stage request limits candidate report request_fingerprint candidate_fingerprint invocation_fingerprint report_fingerprint members empirical_status human_use therapeutic_export".split())
_record = admission._record


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CoreProtocolError(message)


def _limits(behavior_request: JsonValue) -> dict[str, JsonValue]:
    """An exact projection of supplied authority, never additional authority."""
    original = _record(_record(behavior_request)["original"])
    domain = _record(original["operating_domain"])
    projection: JsonValue = {"schema_version": LIMITS_SCHEMA, "budgets": original["budgets"],
        "domain_limits": domain["limits"], "horizon_tick": domain["horizon_tick"],
        "intervention_cutoff_tick": domain["intervention_cutoff_tick"], "resources": original["resources"]}
    return cast(dict[str, JsonValue], decode_json(encode_json(projection)))


def _original(value: JsonValue) -> dict[str, JsonValue]:
    request = _object(value, {"schema_version", "behavior_request", "limits"}, "Complete joined authority")
    _require(request["schema_version"] == REQUEST_SCHEMA, "Unknown joined request schema")
    behavior._original(request["behavior_request"])
    _require(_same(request["limits"], _limits(request["behavior_request"])),
             "Joined limits must exactly equal the complete original authority")
    _publication(request, 4_000_000, 100_000)
    return request


def _candidate(value: JsonValue) -> dict[str, JsonValue]:
    candidate = _object(value, {"schema_version", "request_fingerprint", "material_candidate", "behavior_candidate"}, "Joined candidate")
    _require(candidate["schema_version"] == CANDIDATE_SCHEMA, "Unknown joined candidate schema")
    digest = candidate["request_fingerprint"]
    _require(type(digest) is str and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest),
             "Malformed joined authority fingerprint")
    material._candidate(candidate["material_candidate"])
    behavior._candidate(candidate["behavior_candidate"])
    _publication(candidate, 4_000_000, 100_000)
    return candidate


@dataclass(frozen=True)
class PolicyControlledWorkflowResult(PolicyMaterialResult):
    """Fresh exact RNA and conditional behavior evidence; human use unassessed."""


def _result(response: CoreResponse, payload: dict[str, JsonValue]) -> PolicyControlledWorkflowResult:
    _require(response.operation in (COMPILE, CHECK, REPLAY, EXPORT) and response.status == "ok" and not response.diagnostics,
             "Joined workflow requires an unambiguous native response")
    value = _object(response.result, material._RESULT_FIELDS, "Complete joined result")
    material._flags(value, {"schema_version": RESULT_SCHEMA, "implementation": IMPLEMENTATION,
        "resource_profile": admission.RESOURCE_PROFILE, "validation_scope": VALIDATION_SCOPE}, "Joined profile changed")
    request = _original(payload["request"])
    behavior_request = _record(request["behavior_request"])
    original = _record(behavior_request["original"])
    candidate = _candidate(value["candidate"])
    _pin(candidate["request_fingerprint"], request, "Joined candidate authority")
    if "candidate" in payload:
        _require(_same(candidate, payload["candidate"]), "Native checker substituted supplied joined candidate")
    material_candidate = _record(candidate["material_candidate"])
    behavior_candidate = _record(candidate["behavior_candidate"])
    _pin(material_candidate["request_fingerprint"], original, "Material candidate authority")
    _pin(behavior_candidate["request_fingerprint"], behavior_request, "Behavior candidate authority")
    request_hash = _pin(value["request_fingerprint"], request, "Complete joined original")
    candidate_hash = _pin(value["candidate_fingerprint"], candidate, "Complete joined candidate")
    invocation_hash = _pin(value["invocation_fingerprint"], {"request_fingerprint": request_hash,
        "candidate_fingerprint": candidate_hash}, "Joined invocation")
    report = _object(value["report"], _REPORT_FIELDS, "Complete joined assessment")
    report_hash = _pin(value["report_fingerprint"], report, "Complete joined assessment")
    flags: dict[str, JsonValue] = {"empirical_status": "unassessed", "human_use": "unassessed", "therapeutic_export": "withheld"}
    material._flags(report, {**flags, "schema_version": REPORT_SCHEMA, "profile": admission.REQUEST_PROFILE,
        "implementation": "biocompiler.ocaml.policy_controlled_workflow_check.v0.1", "stage": "joined",
        "claim_scope": "exact_supplied_two_member_rna_and_conditional_behavior_in_complete_finite_domain",
        "request_fingerprint": request_hash, "candidate_fingerprint": candidate_hash,
        "invocation_fingerprint": invocation_hash}, "Joined assessment changed scope or authority")
    for key in ("context", "resources", "budgets"):
        _require(_same(report[key], original[key]), "Joined assessment changed original " + key)
    _require(_same(report["limits"], request["limits"]), "Joined assessment changed complete limits")
    _require(_same(report["project_context"], _record(original["source_authority"])["project_context"]),
             "Joined assessment changed complete project context")
    budgets = _record(original["budgets"])
    usage = _object(value["usage"], {"unit", "preparation_charged_work", "request_decoding_work", "publication"}, "Cumulative joined work")
    material._flags(usage, {"unit": "logical_data_visits_and_child_semantic_work",
        "publication": "requires_original_one_shot_frame_guard"}, "Joined work accounting changed")
    total = admission._count(usage["preparation_charged_work"], cast(int, budgets["max_work"]), 1)
    decoding = admission._count(usage["request_decoding_work"], total, 1)
    material_report = _object(report["material"], material._REPORT_FIELDS, "Retained fresh material assessment")
    behavior_report = _object(report["behavior"], behavior._REPORT_FIELDS, "Retained fresh behavior assessment")
    material._validate_report(material_report, original, material_candidate, total=total, decoding=decoding)
    behavior._validate_report(behavior_report, behavior_request, behavior_candidate, total=total, decoding=decoding)
    # Each of these three native enumerations debits the shared owner separately.
    # Their sum is a necessary lower bound, not an estimate of all native work.
    enumeration_work = sum(cast(int, _record(row)["work"]) for row in (
        _record(material_report["admission"])["domain_counters"],
        _record(behavior_report["admission"])["domain_counters"],
        _record(behavior_report["domain"])["counters"]))
    _require(enumeration_work <= total - decoding, "Joined cumulative work cannot cover all three native enumerations")
    outcomes = (material_report["outcome"], behavior_report["outcome"])
    outcome = ("fail" if "fail" in outcomes else "unknown" if "unknown" in outcomes
               else "unsupported" if "unsupported" in outcomes else "pass")
    _require(report["outcome"] == outcome and report["status"] == (ACCEPTED_STATUS if outcome == "pass" else "not_accepted"),
             "Joined verdict contradicts fresh child evidence")
    if response.operation == REPLAY:
        _require(_same(report, payload["report"]), "Replay changed supplied complete joined report")
    artifact = value["artifact"]
    if response.operation != EXPORT or outcome != "pass":
        _require(artifact is None, "Unchecked joined workflow published a pair")
    else:
        pair = _object(artifact, {"fasta", "fasta_sha256", "manifest", "manifest_sha256"}, "Joined pair")
        _require(type(pair["fasta"]) is str and pair["fasta_sha256"] == hashlib.sha256(pair["fasta"].encode()).hexdigest(),
                 "Joined FASTA digest changed")
        manifest = _object(pair["manifest"], _MANIFEST_FIELDS, "Complete joined manifest")
        material._flags(manifest, {**flags, "schema_version": MANIFEST_SCHEMA, "stage": "joined",
            "request_fingerprint": request_hash, "candidate_fingerprint": candidate_hash,
            "invocation_fingerprint": invocation_hash, "report_fingerprint": report_hash}, "Joined manifest changed scope or pins")
        for key, authority in (("request", request), ("limits", request["limits"]), ("candidate", candidate), ("report", report)):
            _require(_same(manifest[key], authority), "Joined manifest changed complete " + key)
        _pin(pair["manifest_sha256"], manifest, "Complete joined manifest")
        _publication(manifest, cast(int, budgets["max_report_bytes"]), cast(int, budgets["max_report_nodes"]))
        _artifact_members(construction=_record(material_candidate["construction"]), members=manifest["members"],
            fasta=pair["fasta"], fasta_sha256=pair["fasta_sha256"], manifest_fasta_sha256=pair["fasta_sha256"])
    _publication(report, cast(int, budgets["max_report_bytes"]), cast(int, budgets["max_report_nodes"]))
    _publication({"result": value}, admission.MAX_RESULT_BYTES, admission.MAX_RESULT_NODES)
    return PolicyControlledWorkflowResult(response.request_id, response.operation, response.executable,
        request_hash, candidate_hash, invocation_hash, report_hash, encode_json(value))


@dataclass(frozen=True)
class PolicyControlledWorkflowClient:
    transport: CoreClient

    def _call(self, operation: str, payload: dict[str, JsonValue], *, cancelled: Callable[[], bool] | None) -> PolicyControlledWorkflowResult:
        snapshot = cast(dict[str, JsonValue], decode_json(encode_json(payload)))
        _original(snapshot["request"])
        if "candidate" in snapshot:
            _candidate(snapshot["candidate"])
        if "report" in snapshot:
            _object(snapshot["report"], _REPORT_FIELDS, "Original joined replay report")
        _require(operation != COMPILE or self.transport.role == "core", "Joined compilation requires explicit Core producer")
        capabilities = self.transport.negotiate(operation, cancelled=cancelled)
        profile = PRODUCER_PROFILE if self.transport.role == "core" else PROFILE
        _require(_same(capabilities.profiles.get("policy_controlled_workflow"), profile)
            and VALIDATION_SCOPE in capabilities.validation_scopes, "Selected executable lacks exact joined workflow capability")
        response = self.transport.call(operation, snapshot, cancelled=cancelled)
        _require(response.operation == operation and response.executable == self.transport.role, "Joined response changed operation or executable")
        return _result(response, snapshot)

    def compile(self, request: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyControlledWorkflowResult:
        return self._call("compile-policy-controlled-workflow", {"request": request}, cancelled=cancelled)

    def check(self, request: JsonValue, candidate: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyControlledWorkflowResult:
        return self._call("check-policy-controlled-workflow", {"request": request, "candidate": candidate}, cancelled=cancelled)

    def replay(self, request: JsonValue, candidate: JsonValue, report: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyControlledWorkflowResult:
        return self._call("replay-policy-controlled-workflow", {"request": request, "candidate": candidate, "report": report}, cancelled=cancelled)

    def export(self, request: JsonValue, candidate: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyControlledWorkflowResult:
        return self._call("export-policy-controlled-workflow", {"request": request, "candidate": candidate}, cancelled=cancelled)
