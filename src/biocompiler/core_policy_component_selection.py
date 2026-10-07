"""Immutable native complete-catalog selection transport; no Python admission.

All original alternatives and complete candidates cross the native boundary on
every call. Representation checks bind returned evidence and exact paired bytes;
only fresh native checking supplies semantic acceptance.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Callable, cast

from biocompiler import core_policy_component_material as component
from biocompiler import core_policy_material as material
from biocompiler.core_client import (
    CORE_VERSION, PROTOCOL, CoreClient, CoreProtocolError, CoreResponse, JsonValue,
    _object, decode_json, encode_json,
)

VALIDATION_SCOPE = "policy-component-selection-mrna-v0.1"
IMPLEMENTATION = "biocompiler.ocaml.policy_component_selection.v0.1"
RESULT_SCHEMA = "biocompiler.core.policy_component_selection.v1"
REQUEST_SCHEMA = "biocompiler.policy_component_selection_request.v0.1"
REQUEST_PROFILE = "biocompiler.policy_component_material_selection.v0.1"
CANDIDATE_SCHEMA = "biocompiler.policy_component_selection_candidate.v0.1"
REPORT_SCHEMA = "biocompiler.policy_component_selection_assessment.v0.1"
EXPORT_SCHEMA = "biocompiler.policy_component_selection_mrna_export.v0.1"
MANIFEST_SCHEMA = "biocompiler.policy_component_selection_mrna_manifest.v0.1"
RESOURCE_PROFILE = "biocompiler.policy_component_selection_resources.v0.1"
RESOURCE_PROFILE_V2 = "biocompiler.policy_component_selection_resources.v0.2"
OPERATIONS = ("check-policy-component-selection", "replay-policy-component-selection", "export-policy-component-selection")
PUBLICATION_PROFILE = "biocompiler.policy_component_selection_publication.v0.1"
ACCEPTED_STATUS = "checked_selection"
CLAIM_SCOPE = "bounded_complete_supplied_catalog_selection_to_exact_mrna"
PREMISE = component.PREMISE
MAX_INPUT_BYTES = 8388608
MAX_RESULT_BYTES = material.MAX_RESULT_BYTES
MAX_RESULT_NODES = material.MAX_RESULT_NODES
PUBLICATION_LIMITS: list[JsonValue] = [
    {"profile": RESOURCE_PROFILE, "max_report_bytes": MAX_RESULT_BYTES, "max_report_nodes": MAX_RESULT_NODES},
    {"profile": RESOURCE_PROFILE_V2, "max_report_bytes": MAX_RESULT_BYTES, "max_report_nodes": 1000000},
]
PROFILE: dict[str, JsonValue] = {
    "operations": list(OPERATIONS),
    "request_schema": REQUEST_SCHEMA, "candidate_schema": CANDIDATE_SCHEMA,
    "schema_version": RESULT_SCHEMA, "implementation": IMPLEMENTATION,
    "resource_profiles": [RESOURCE_PROFILE, RESOURCE_PROFILE_V2], "publication_limits": PUBLICATION_LIMITS,
    "publication_profile": PUBLICATION_PROFILE, "validation_scope": VALIDATION_SCOPE,
    "max_input_bytes": MAX_INPUT_BYTES, "max_result_bytes": MAX_RESULT_BYTES, "max_result_nodes": MAX_RESULT_NODES,
    "artifact": "on_fresh_export_only", "empirical": "unassessed",
}
_REPORT_FIELDS = {"schema_version", "profile", "implementation", "resource_profile", "common_authority_profile",
    "request_fingerprint", "candidate_fingerprint", "invocation_fingerprint", "status", "claim_scope", "premise",
    "census_complete", "all_inner_accepted", "alternatives", "predicate", "proposed_selected_id", "selected_id",
    "winner_matches", "limits", "budgets", "empirical", "artifact", "export", "usage"}
_same, _pin, _record, _rows, _count = material._same, material._pin, material._record, material._rows, material._count


def _integer(value: JsonValue, minimum: int, maximum: int, label: str) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise CoreProtocolError(label + " exceeds its closed integer bound")
    return value


def _id(value: JsonValue) -> str:
    if (type(value) is not str or not 1 <= len(value) <= 128 or not value.isascii()
            or not value[0].isalnum() or any(not (c.isalnum() or c in "._-") for c in value)):
        raise CoreProtocolError("Selection ID must match its bounded ASCII grammar")
    return value


def _measure(raw: JsonValue) -> tuple[int, int]:
    pending = [(raw, 0)]
    nodes = 0
    while pending:
        value, depth = pending.pop()
        nodes += 1
        if depth > 128:
            raise CoreProtocolError("Selection publication exceeds its depth bound")
        if type(value) is dict:
            nodes += len(value)
            for key in value:
                if len(key.encode("utf-8")) > 1000000:
                    raise CoreProtocolError("Selection key exceeds its bounded string profile")
            pending.extend((item, depth + 1) for item in value.values())
        elif type(value) is list:
            pending.extend((item, depth + 1) for item in value)
        elif type(value) is int and value.bit_length() > 4096:
            raise CoreProtocolError("Selection integer exceeds its bounded bit profile")
        elif type(value) is str and len(value.encode("utf-8")) > 1000000:
            raise CoreProtocolError("Selection value exceeds its bounded string profile")
        if nodes + len(pending) > 250000:
            raise CoreProtocolError("Selection publication exceeds its individual node bound")
    return len(encode_json(raw, limit=MAX_INPUT_BYTES)), nodes


def _original(value: JsonValue) -> dict[str, JsonValue]:
    _measure(value)
    request = _object(value, {"schema_version", "profile", "alternatives", "predicate", "budgets"}, "Complete selection original")
    component._expect(request, {"schema_version": REQUEST_SCHEMA, "profile": REQUEST_PROFILE}, "Original selection")
    rows = _rows(request["alternatives"], "Original alternative census")
    if not 1 <= len(rows) <= 16:
        raise CoreProtocolError("Selection requires one to sixteen complete originals")
    seen = set()
    for value in rows:
        row = _object(value, {"id", "rank", "request"}, "Original alternative")
        identity = _id(row["id"])
        if identity in seen:
            raise CoreProtocolError("Selection original repeats an alternative ID")
        seen.add(identity)
        _integer(row["rank"], 0, 2147483647, "Alternative rank")
        component._original(row["request"])
    predicate = _object(request["predicate"], {"max_total_nt"}, "Original length predicate")
    _integer(predicate["max_total_nt"], 0, 1000000, "Original length predicate")
    budgets = _object(request["budgets"], {"profile", "max_work", "max_report_bytes", "max_report_nodes"}, "Original selection budgets")
    if budgets["profile"] not in (RESOURCE_PROFILE, RESOURCE_PROFILE_V2):
        raise CoreProtocolError("Unknown original selection resource profile")
    _integer(budgets["max_work"], 1, 17000000000, "Original aggregate work")
    _integer(budgets["max_report_bytes"], 1, MAX_RESULT_BYTES, "Original cumulative bytes")
    _integer(budgets["max_report_nodes"], 1, MAX_RESULT_NODES if budgets["profile"] == RESOURCE_PROFILE else 1000000,
             "Original cumulative nodes")
    return request


def _candidates(value: JsonValue, originals: list[dict[str, JsonValue]]) -> dict[str, dict[str, JsonValue]]:
    candidate = _object(value, {"schema_version", "alternatives", "selected_id"}, "Complete selection candidate")
    if candidate["schema_version"] != CANDIDATE_SCHEMA:
        raise CoreProtocolError("Selection candidate changed its schema")
    ids = {_id(row["id"]) for row in originals}
    rows = _rows(candidate["alternatives"], "Complete candidate census")
    by_id: dict[str, dict[str, JsonValue]] = {}
    for value in rows:
        row = _object(value, {"id", "candidate"}, "Candidate alternative")
        identity = _id(row["id"])
        if identity not in ids or identity in by_id:
            raise CoreProtocolError("Candidate changed the unique original alternative census")
        by_id[identity] = component._candidate(row["candidate"])
    if set(by_id) != ids or candidate["selected_id"] is not None and _id(candidate["selected_id"]) not in ids:
        raise CoreProtocolError("Candidate omitted an original or proposed an unknown winner")
    return by_id


def _sequence(candidate: dict[str, JsonValue]) -> str:
    construction = _record(candidate["construction"], "Checked child construction")
    molecules = _rows(_record(construction.get("inventory"), "Checked child inventory").get("molecules"), "Checked child molecules")
    if len(molecules) != 1 or not _same(construction.get("member_order"), [molecules[0].get("id")]):
        raise CoreProtocolError("Selection requires the exact checked single RNA inventory")
    sequence = molecules[0].get("sequence")
    if type(sequence) is not str or not sequence or len(sequence) > 1000000 or any(c not in "ACGU" for c in sequence):
        raise CoreProtocolError("Checked selection lacks exact bounded RNA spelling")
    return sequence


def _assessment(response: CoreResponse, request: dict[str, JsonValue], candidate: dict[str, JsonValue],
                report: dict[str, JsonValue], limits: JsonValue) -> dict[str, dict[str, JsonValue]]:
    budgets = _record(request["budgets"], "Original budgets")
    component._expect(report, {"schema_version": REPORT_SCHEMA, "profile": REQUEST_PROFILE,
        "implementation": "biocompiler.ocaml.policy_component_selection_check.v0.1",
        "resource_profile": budgets["profile"], "common_authority_profile": "biocompiler.policy_decision_leader_variant.v0.1",
        "claim_scope": "bounded_complete_supplied_catalog_selection", "premise": PREMISE,
        "census_complete": True, "empirical": "unassessed", "artifact": "withheld", "export": "withheld",
        "limits": limits, "budgets": budgets, "predicate": request["predicate"], "proposed_selected_id": candidate["selected_id"]}, "Complete selection assessment")
    invocation: JsonValue = {"request": request, "candidate": candidate, "limits": limits}
    for key, raw in (("request_fingerprint", request), ("candidate_fingerprint", candidate), ("invocation_fingerprint", invocation)):
        _pin(report[key], raw, key)
    originals = sorted(_rows(request["alternatives"], "Originals"), key=lambda row: _id(row["id"]))
    candidates = _candidates(candidate, originals)
    rows = _rows(report["alternatives"], "Complete assessment census")
    if len(rows) != len(originals):
        raise CoreProtocolError("Assessment omitted or added a complete original alternative")
    eligible: list[tuple[int, str]] = []
    all_passed = True
    inner_by_id = {}
    reserved = 0
    maximum = _record(request["predicate"], "Predicate")["max_total_nt"]
    for raw, original in zip(rows, originals):
        row = _object(raw, {"id", "rank", "request_fingerprint", "candidate_fingerprint", "inner", "total_nt", "sequence_sha256", "eligible"}, "Alternative assessment")
        identity = _id(original["id"])
        component._expect(row, {"id": identity, "rank": original["rank"]}, "Canonical evaluation census")
        child_request = component._original(original["request"])
        child_candidate = candidates[identity]
        _pin(row["request_fingerprint"], child_request, "Complete child original")
        _pin(row["candidate_fingerprint"], child_candidate, "Complete child candidate")
        inner = component._report(row["inner"])
        component._assessment(response, child_request, child_candidate, inner, limits)
        inner_by_id[identity] = inner
        child_budgets = _record(child_request["budgets"], "Original child budgets")
        material._publication(inner, _count(child_budgets.get("max_report_bytes"), "Child bytes"),
                              _count(child_budgets.get("max_report_nodes"), "Child nodes"))
        reserved += _count(child_budgets.get("max_work"), "Unchanged child allowance")
        if inner["status"] != component.ACCEPTED_STATUS:
            all_passed = False
            component._expect(row, {"total_nt": None, "sequence_sha256": None, "eligible": None}, "Unaccepted child")
        else:
            sequence = _sequence(child_candidate)
            passes = len(sequence) <= cast(int, maximum)
            component._expect(row, {"total_nt": len(sequence), "sequence_sha256": hashlib.sha256(sequence.encode()).hexdigest(),
                                    "eligible": passes}, "Fresh checked child material")
            if passes:
                eligible.append((cast(int, original["rank"]), identity))
    winner = min(eligible)[1] if all_passed and eligible else None
    matches = all_passed and candidate["selected_id"] == winner
    status = ("inner_not_accepted" if not all_passed else "proposed_winner_mismatch" if not matches
              else "no_eligible_alternative" if winner is None else ACCEPTED_STATUS)
    component._expect(report, {"all_inner_accepted": all_passed, "selected_id": winner, "winner_matches": matches if all_passed else None,
                              "status": status}, "Complete native selection outcome")
    usage = _object(report["usage"], {"unit", "charged_work", "reserved_child_work", "original_decoding_work", "candidate_decoding_work"}, "Selection work accounting")
    charged = _count(usage["charged_work"], "Charged selection work")
    if (usage["unit"] != "logical_data_visits_and_reserved_child_allowances" or usage["reserved_child_work"] != reserved
            or type(usage["reserved_child_work"]) is not int or charged > _count(budgets["max_work"], "Original total allowance")
            or charged < reserved + _count(usage["original_decoding_work"], "Original decoding") + _count(usage["candidate_decoding_work"], "Candidate decoding")):
        raise CoreProtocolError("Selection accounting changed its original work obligations")
    return inner_by_id


def _artifact(value: JsonValue, *, response: CoreResponse, request: dict[str, JsonValue], candidate: dict[str, JsonValue],
              report: dict[str, JsonValue], limits: JsonValue, inners: dict[str, dict[str, JsonValue]]) -> None:
    if response.operation != "export-policy-component-selection":
        if value is not None:
            raise CoreProtocolError("Only fresh selection export may return an artifact")
        return
    if report["status"] != ACCEPTED_STATUS:
        raise CoreProtocolError("Selection export lacks complete fresh acceptance")
    artifact = _object(value, {"schema_version", "fasta", "fasta_sha256", "manifest", "manifest_sha256"}, "Selection paired export")
    if artifact["schema_version"] != EXPORT_SCHEMA or type(artifact["fasta"]) is not str:
        raise CoreProtocolError("Selection export changed its exact artifact profile")
    if artifact["fasta_sha256"] != hashlib.sha256(artifact["fasta"].encode()).hexdigest():
        raise CoreProtocolError("Selection FASTA differs from its exact digest")
    _pin(artifact["manifest_sha256"], artifact["manifest"], "Complete outer manifest")
    manifest = _object(artifact["manifest"], {"schema_version", "profile", "claim_scope", "premise", "request", "candidate", "limits",
        "assessment", "bindings", "selected", "members", "fasta_sha256", "empirical", "original_authority"}, "Complete selection manifest")
    component._expect(manifest, {"schema_version": MANIFEST_SCHEMA, "profile": REQUEST_PROFILE, "claim_scope": CLAIM_SCOPE,
        "premise": PREMISE, "request": request, "candidate": candidate, "limits": limits, "assessment": report,
        "empirical": "unassessed", "original_authority": "retain_original_inputs_separately"}, "Outer manifest authority")
    bindings = _object(manifest["bindings"], {"request_fingerprint", "candidate_fingerprint", "invocation_fingerprint", "assessment_fingerprint"}, "Outer manifest bindings")
    for key, raw in (("request_fingerprint", request), ("candidate_fingerprint", candidate),
                     ("invocation_fingerprint", {"request": request, "candidate": candidate, "limits": limits}), ("assessment_fingerprint", report)):
        _pin(bindings[key], raw, key)
    identity = cast(str, report["selected_id"])
    original = component._unique(_rows(request["alternatives"], "Originals"), "id", identity, "Selected original")
    proposed = component._unique(_rows(candidate["alternatives"], "Candidates"), "id", identity, "Selected candidate")
    selected = _object(manifest["selected"], {"id", "request_fingerprint", "candidate_fingerprint", "assessment_fingerprint"}, "Selected child bindings")
    component._expect(selected, {"id": identity}, "Selected manifest identity")
    for key, child_raw in (("request_fingerprint", original["request"]), ("candidate_fingerprint", proposed["candidate"]),
                     ("assessment_fingerprint", inners[identity])):
        _pin(selected[key], child_raw, key)
    child = _record(proposed["candidate"], "Selected candidate")
    _sequence(child)
    material._artifact_members(construction=child["construction"], members=manifest["members"], fasta=artifact["fasta"],
                              fasta_sha256=artifact["fasta_sha256"], manifest_fasta_sha256=manifest["fasta_sha256"])


def _publication(response: CoreResponse, result: dict[str, JsonValue], request: dict[str, JsonValue],
                 report: dict[str, JsonValue], inners: dict[str, dict[str, JsonValue]]) -> None:
    budgets = _record(request["budgets"], "Original publication budgets")
    # Native reserves maximal usage digits before recording the checking-phase snapshot.
    assessed = {**report, "usage": {**_record(report["usage"], "Usage"), "charged_work": budgets["max_work"]}}
    events: list[JsonValue] = [*inners.values(), assessed]
    if result["artifact"] is not None:
        events.append(_record(result["artifact"], "Artifact")["manifest"])
    # These fields are already authenticated by CoreClient's exact wire decoder.
    events.append({"protocol": PROTOCOL, "request_id": response.request_id, "operation": response.operation,
        "status": response.status, "result": result, "diagnostics": [],
        "core": {"implementation": "ocaml", "version": response.version, "protocol": PROTOCOL, "executable": response.executable}})
    total_bytes = total_nodes = 0
    for event in events:
        size, nodes = _measure(event)
        total_bytes += size
        total_nodes += nodes
        if total_bytes > cast(int, budgets["max_report_bytes"]) or total_nodes > cast(int, budgets["max_report_nodes"]):
            raise CoreProtocolError("Selection exceeds its original cumulative publication allowance")
    material._publication({"result": result}, MAX_RESULT_BYTES, MAX_RESULT_NODES)


@dataclass(frozen=True)
class PolicyComponentSelectionResult(material.PolicyMaterialResult):
    """Immutable whole-catalog evidence; a selected child never replaces its originals."""


def _result(response: CoreResponse, payload: dict[str, JsonValue]) -> PolicyComponentSelectionResult:
    _measure(response.result)
    if response.status != "ok" or response.diagnostics or response.operation not in OPERATIONS or response.version != CORE_VERSION:
        raise CoreProtocolError("Selection result lacks its actual successful negotiated operation")
    result = _object(response.result, material._RESULT_FIELDS, "Complete selection result")
    request = _original(payload["request"])
    budgets = _record(request["budgets"], "Original budgets")
    component._expect(result, {"schema_version": RESULT_SCHEMA, "implementation": IMPLEMENTATION,
        "resource_profile": budgets["profile"], "validation_scope": VALIDATION_SCOPE}, "Negotiated selection result")
    candidate = _object(result["candidate"], {"schema_version", "alternatives", "selected_id"}, "Selection candidate")
    if not _same(candidate, payload["candidate"]):
        raise CoreProtocolError("Selection checker changed the complete supplied candidate")
    report = _object(result["report"], _REPORT_FIELDS, "Complete selection assessment")
    pins = [_pin(result[key], raw, label) for key, raw, label in (
        ("request_fingerprint", request, "Complete selection original"), ("candidate_fingerprint", candidate, "Complete selection candidate"),
        ("invocation_fingerprint", {"request": request, "candidate": candidate, "limits": payload["limits"]}, "Complete selection invocation"),
        ("report_fingerprint", report, "Complete selection report"))]
    inners = _assessment(response, request, candidate, report, payload["limits"])
    _artifact(result["artifact"], response=response, request=request, candidate=candidate, report=report, limits=payload["limits"], inners=inners)
    if response.operation == "replay-policy-component-selection" and not _same(result, payload["report"]):
        raise CoreProtocolError("Fresh replay differs from the complete retained selection wrapper")
    _publication(response, result, request, report, inners)
    request_hash, candidate_hash, invocation_hash, report_hash = pins
    return PolicyComponentSelectionResult(response.request_id, response.operation, response.executable,
        request_hash, candidate_hash, invocation_hash, report_hash, encode_json(result))


@dataclass(frozen=True)
class PolicyComponentSelectionClient:
    transport: CoreClient

    def _call(self, operation: str, payload: dict[str, JsonValue], *, cancelled: Callable[[], bool] | None) -> PolicyComponentSelectionResult:
        snapshot = cast(dict[str, JsonValue], decode_json(encode_json(payload)))
        _measure(snapshot)
        original = _original(snapshot["request"])
        _candidates(snapshot["candidate"], _rows(original["alternatives"], "Originals"))
        capabilities = self.transport.negotiate(operation, cancelled=cancelled)
        if not _same(capabilities.profiles.get("policy_component_selection"), PROFILE) or VALIDATION_SCOPE not in capabilities.validation_scopes:
            raise CoreProtocolError("Selected executable lacks the exact bounded selection profile")
        return _result(self.transport.call(operation, snapshot, cancelled=cancelled), snapshot)

    def check(self, request: JsonValue, candidate: JsonValue, limits: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyComponentSelectionResult:
        return self._call("check-policy-component-selection", {"request": request, "candidate": candidate, "limits": limits}, cancelled=cancelled)

    def replay(self, request: JsonValue, candidate: JsonValue, limits: JsonValue, report: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyComponentSelectionResult:
        return self._call("replay-policy-component-selection", {"request": request, "candidate": candidate, "limits": limits, "report": report}, cancelled=cancelled)

    def export(self, request: JsonValue, candidate: JsonValue, limits: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyComponentSelectionResult:
        return self._call("export-policy-component-selection", {"request": request, "candidate": candidate, "limits": limits}, cancelled=cancelled)
