"""Immutable, explicitly negotiated bounded implementation transport.

Native checking alone interprets source, graphs and operating domains. Retained
JSON is reviewable evidence, never a transferable material/export capability.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, cast

from biocompiler import core_policy as source
from biocompiler import core_policy_operational as operational
from biocompiler.core_client import (
    LIMITS, CoreClient, CoreProtocolError, CoreResponse, JsonValue, _object, decode_json, encode_json,
)

VALIDATION_SCOPE = "bounded-policy-implementation-v0.1"
IMPLEMENTATION = "biocompiler.ocaml.policy_implementation.v0.1"
RESOURCE_PROFILE = "biocompiler.policy_preservation_resources.v0.1"
RESULT_SCHEMA = "biocompiler.core.policy_implementation.v1"
CANDIDATE_SCHEMA = "biocompiler.policy_implementation_candidate.v0.1"
REQUEST_SCHEMA = "biocompiler.policy_realization_request.v0.1"
REQUEST_PROFILE = "biocompiler.policy_realization_inputs.v0.1"
PRESERVATION_PROFILE = "biocompiler.policy_bounded_preservation.v0.1"
# Frozen negotiated publication profile; the protocol-budget regression test
# checks these literal values against the wire envelope reserves.
MAX_RESULT_BYTES = 8323072
MAX_RESULT_NODES = 249968
PROFILE: dict[str, JsonValue] = {
    "operations": ["check-policy-implementation", "replay-policy-implementation"],
    "request_schema": REQUEST_SCHEMA, "candidate_schema": CANDIDATE_SCHEMA,
    "schema_version": RESULT_SCHEMA, "implementation": IMPLEMENTATION,
    "resource_profile": RESOURCE_PROFILE, "validation_scope": VALIDATION_SCOPE,
    "max_result_bytes": MAX_RESULT_BYTES, "max_result_nodes": MAX_RESULT_NODES,
    "artifact": "withheld", "target_status": "unassessed", "material": "unassessed", "export": "withheld",
}
PRODUCER_PROFILE: dict[str, JsonValue] = {
    "operations": ["compile-policy-implementation"],
    "implementation": IMPLEMENTATION, "validation_scope": VALIDATION_SCOPE,
}
_RESULT_FIELDS = {
    "schema_version", "implementation", "resource_profile", "validation_scope", "request_fingerprint",
    "candidate_fingerprint", "invocation_fingerprint", "report_fingerprint", "candidate", "report",
}
_REPORT_FIELDS = {
    "schema_version", "profile", "request_fingerprint", "binding", "limits", "coverage", "program_coverage",
    "usage", "preservation", "requirements", "assurance", "status", "stopped", "target_status", "material", "artifact", "export",
}
_BINDING_FIELDS = {
    "schema_version", "profile", "observable_profile", "status", "request_fingerprint", "catalog_bindings_digest",
    "catalog_entry", "catalog_entry_digest", "source_artifact_digest", "descriptors_digest", "operating_domain_digest",
    "implementation_catalog_digest", "implementation_library_digest", "implementation_fingerprint",
    "proposed_binding_fingerprint", "source_admission", "source_occurrences", "interpreted_outputs", "execution",
    "preservation", "requirements", "material", "target_status", "artifact", "export",
}
_ADMISSION_FIELDS = {
    "schema_version", "profile", "resource_profile", "status", "request_fingerprint", "source_artifact_digest",
    "document_digest", "descriptors_digest", "operating_domain_digest", "implementation_catalog_digest",
    "implementation_library_digest", "catalog_bindings_digest", "source_assessment", "source_correspondence",
    "requested_requirements", "authorized_models", "assurance", "budgets", "exploration", "preservation", "requirements",
    "target_status", "material", "export", "artifact", "unresolved_obligations",
}
_REQUEST_FIELDS = {
    "schema_version", "profile", "document", "definitions", "operating_domain", "implementation_library",
    "catalog_bindings", "budgets",
}
_same = operational._same
_pin = operational._pin


def _record(value: JsonValue, label: str) -> dict[str, JsonValue]:
    if type(value) is not dict:
        raise CoreProtocolError(label + " must be a record")
    return value


def _rows(value: JsonValue, label: str) -> list[dict[str, JsonValue]]:
    if type(value) is not list or any(type(row) is not dict for row in value):
        raise CoreProtocolError(label + " must retain a list of records")
    return cast(list[dict[str, JsonValue]], value)


def _count(value: JsonValue, label: str) -> int:
    if type(value) is not int or value < 0:
        raise CoreProtocolError(label + " must be a nonnegative integer")
    return value


def _claim(value: dict[str, JsonValue]) -> None:
    if any(value[key] != expected for key, expected in (
        ("target_status", "unassessed"), ("material", "unassessed"), ("artifact", "withheld"), ("export", "withheld"),
    )):
        raise CoreProtocolError("Implementation evidence upgraded a material, target or export claim")


def _original(request: JsonValue) -> dict[str, JsonValue]:
    raw: dict[str, JsonValue] = _object(request, _REQUEST_FIELDS, "Original implementation request")
    if raw["schema_version"] != REQUEST_SCHEMA or raw["profile"] != REQUEST_PROFILE:
        raise CoreProtocolError("Implementation request changed its closed source profile")
    document = _record(raw["document"], "Original BuildRequest")
    if document.get("$type") != "BuildRequest":
        raise CoreProtocolError("Implementation checking requires a complete original BuildRequest")
    return raw


def _authority(response: CoreResponse, request: dict[str, JsonValue], candidate: dict[str, JsonValue],
               report: dict[str, JsonValue]) -> None:
    raw_binding = _record(report["binding"], "Source graph binding")
    staged = raw_binding.get("schema_version") == "biocompiler.policy_implementation_binding_report.v0.2"
    binding_profile = "biocompiler.policy_staged_source_graph.v0.1" if staged else "biocompiler.policy_exclusive_source_graph.v0.1"
    observable_profile = "biocompiler.policy_staged_observables.v0.1" if staged else "biocompiler.policy_truth_observables.v0.1"
    binding = _object(raw_binding, _BINDING_FIELDS | ({"state_encoding"} if staged else set()), "Source graph binding")
    admission = _object(binding["source_admission"], _ADMISSION_FIELDS, "Original input admission")
    _claim(binding)
    _claim(admission)
    if (binding["schema_version"] != ("biocompiler.policy_implementation_binding_report.v0.2" if staged else "biocompiler.policy_implementation_binding_report.v0.1")
            or binding["profile"] != binding_profile or binding["observable_profile"] != observable_profile
            or staged and binding["state_encoding"] != "exact_ordered_source_labels"
            or binding["status"] != "source_graph_bound" or binding["execution"] != "not_performed"
            or admission["schema_version"] != "biocompiler.policy_realization_admission.v0.1"
            or admission["profile"] != REQUEST_PROFILE
            or admission["resource_profile"] != "biocompiler.policy_realization_inputs.resources.v0.1"
            or admission["status"] != "admitted_inputs" or admission["exploration"] != "not_performed"
            or any(stage[key] != "unassessed" for stage in (binding, admission) for key in ("preservation", "requirements"))):
        raise CoreProtocolError("Implementation report changed a subordinate admission claim")
    document = _record(request["document"], "Original BuildRequest")
    original_program = _record(document["program"], "Original program")
    original_declarations = _rows(original_program["declarations"], "Original declarations")
    if not staged and any(row.get("$type") == "Machine" for row in original_declarations):
        raise CoreProtocolError("Original machines require the explicit staged binding profile")
    for stage in (binding, admission):
        for key, original in (
            ("request_fingerprint", request), ("source_artifact_digest", document),
            ("descriptors_digest", request["definitions"]), ("operating_domain_digest", request["operating_domain"]),
            ("implementation_catalog_digest", document["implementations"]),
            ("implementation_library_digest", request["implementation_library"]),
            ("catalog_bindings_digest", request["catalog_bindings"]),
        ):
            _pin(stage[key], original, key)
    _pin(binding["implementation_fingerprint"], candidate["implementation"], "Implementation graph")
    _pin(binding["proposed_binding_fingerprint"], candidate["binding"], "Proposed source mapping")
    graph = _object(candidate["implementation"], {
        "schema_version", "profile", "observable_profile", "authority", "slot_layout", "nodes", "wires",
        "inputs", "atomic_groups", "semantic_exports", "occurrences",
    }, "Implementation graph")
    if (graph["schema_version"] != "biocompiler.policy_implementation.v0.1"
            or graph["profile"] != ("biocompiler.policy_staged_primitives.v0.1" if staged else "biocompiler.policy_truth_primitives.v0.1")
            or graph["observable_profile"] != binding["observable_profile"]):
        raise CoreProtocolError("Actual graph changed its primitive or observable profile")
    if not _same(binding["source_occurrences"], graph.get("occurrences")):
        raise CoreProtocolError("Binding lost its complete graph occurrence inventory")
    authority = _object(graph.get("authority"), {
        "source_artifact_digest", "descriptors_digest", "domain_digest", "implementation_catalog_digest", "library_digest",
    }, "Implementation graph authority")
    for graph_key, binding_key in (
        ("source_artifact_digest", "source_artifact_digest"), ("descriptors_digest", "descriptors_digest"),
        ("domain_digest", "operating_domain_digest"), ("implementation_catalog_digest", "implementation_catalog_digest"),
        ("library_digest", "implementation_library_digest"),
    ):
        if not _same(authority[graph_key], binding[binding_key]):
            raise CoreProtocolError("Graph carries different external authority")
    bridges = _rows(request["catalog_bindings"], "Original catalog bridge")
    matches = [row for row in bridges if row.get("entry_id") == binding["catalog_entry"]]
    proposed = _object(candidate["binding"], {
        "schema_version", "profile", "catalog_entry", "observations", "states", "effects", "rules",
    } | ({"machines", "transitions"} if staged else set()), "Proposed binding")
    if (len(matches) != 1 or binding["catalog_entry_digest"] != matches[0].get("entry_digest")
            or proposed["catalog_entry"] != binding["catalog_entry"]
            or proposed["schema_version"] != ("biocompiler.policy_implementation_binding.v0.2" if staged else "biocompiler.policy_implementation_binding.v0.1")
            or proposed["profile"] != binding["profile"]):
        raise CoreProtocolError("Source binding changed its original catalog entry")
    if staged:
        for key, kind, fields, count in (
            ("machines", "Machine", {"source", "bank"}, 1),
            ("transitions", "Transition", {"source", "gate", "arbiter", "lane", "commit"}, 7),
        ):
            anchors = [_object(row, fields, "Staged source anchor") for row in _rows(proposed[key], "Staged anchors")]
            source_ids = [row["id"] for row in original_declarations if row.get("$type") == kind]
            if (len(anchors) != count or len(source_ids) != count
                    or any(type(value) is not str for value in source_ids)
                    or any(type(row["source"]) is not str for row in anchors)
                    or sorted(cast(str, row["source"]) for row in anchors) != sorted(cast(str, value) for value in source_ids)):
                raise CoreProtocolError("Staged binding changed its complete original machine or transition census")
            for anchor in anchors:
                if any(type(value) is not str or not value for name, value in anchor.items() if name != "lane"):
                    raise CoreProtocolError("Staged source anchor identity must be nonempty text")
                if key == "transitions" and (type(anchor["lane"]) is not int or not 0 <= anchor["lane"] <= 6):
                    raise CoreProtocolError("Staged transition lane must be a bounded integer")
        if proposed["states"] != [] or proposed["rules"] != []:
            raise CoreProtocolError("Staged source binding cannot invent separate state or rule anchors")
    pins: list[JsonValue] = []
    for bridge in bridges:
        for pin in _rows(bridge.get("models"), "Catalog model pins"):
            if not any(_same(pin, previous) for previous in pins):
                pins.append(pin)
    if not _same(admission["authorized_models"], pins):
        raise CoreProtocolError("Input admission lost the complete original model membership ledger")
    outputs = _rows(binding["interpreted_outputs"], "Interpreted node inventory")
    graph_nodes = _rows(graph["nodes"], "Actual graph nodes")
    if not _same([row.get("node") for row in outputs], [row.get("id") for row in graph_nodes]):
        raise CoreProtocolError("Binding omitted or reordered an actual graph node")
    assessment = operational._source_assessment(response, admission["source_assessment"], document)
    if assessment.status != "valid" or admission["document_digest"] != assessment.document_digest:
        raise CoreProtocolError("Implementation success lacks original valid source assessment")
    source_payload = {"document": request["document"], "definitions": request["definitions"]}
    operational._candidate(candidate["behavior"], source_payload, assessment.assessment)
    operational._correspondence(admission["source_correspondence"], source_payload, candidate["behavior"], assessment.assessment)
    assurance = _record(document["assurance"], "Original assurance")
    if (not _same(admission["assurance"], assurance) or not _same(admission["budgets"], request["budgets"])
            or not _same(admission["requested_requirements"], assurance["requirements"])):
        raise CoreProtocolError("Input admission changed original assurance or budgets")


def _evidence(request: dict[str, JsonValue], report: dict[str, JsonValue]) -> None:
    coverage = _object(report["coverage"], {
        "complete", "prefixes_started", "matched_prefixes", "transitions", "histories", "traversal", "digest",
    }, "Whole-domain coverage")
    if type(coverage["complete"]) is not bool or coverage["traversal"] != "exhaustive_depth_first_no_merging":
        raise CoreProtocolError("Whole-domain coverage changed its scope")
    complete = coverage["complete"]
    counts = {key: _count(coverage[key], key) for key in ("prefixes_started", "matched_prefixes", "transitions", "histories")}
    if (counts["prefixes_started"] != counts["transitions"] + 1
            or counts["matched_prefixes"] > counts["prefixes_started"]
            or complete and (counts["matched_prefixes"] != counts["prefixes_started"] or not counts["histories"])):
        raise CoreProtocolError("Coverage omitted or contradicted its traversal inventory")
    source._hash(coverage["digest"])
    activity = _object(report["program_coverage"], {
        "nonvacuous", "created_attempts", "active_prefixes", "inactive_prefixes", "witnesses",
    }, "Program exercise coverage")
    if type(activity["nonvacuous"]) is not bool:
        raise CoreProtocolError("Program nonvacuity must be an explicit Boolean")
    activity_counts = [_count(activity[key], key) for key in ("created_attempts", "active_prefixes", "inactive_prefixes")]
    if activity["nonvacuous"] != all(value > 0 for value in activity_counts):
        raise CoreProtocolError("Program activity contradicts its reported nonvacuity")
    _record(activity["witnesses"], "Program witnesses")
    budgets = _record(request["budgets"], "Original budgets")
    usage = _object(report["usage"], {
        "work", "source_work", "candidate_work", "monitor_work", "peak_retained_trace_items",
    }, "Preservation usage")
    for key in usage:
        _count(usage[key], key)
    for value, maximum in (
        (counts["prefixes_started"], budgets["max_prefixes"]), (counts["transitions"], budgets["max_transitions"]),
        (usage["work"], budgets["max_work"]), (usage["peak_retained_trace_items"], budgets["max_trace_items"]),
    ):
        if _count(value, "Consumed budget") > _count(maximum, "Original budget"):
            raise CoreProtocolError("Implementation report exceeds supplied original budgets")
    if sum(_count(usage[key], key) for key in ("source_work", "candidate_work", "monitor_work")) > _count(usage["work"], "Total work"):
        raise CoreProtocolError("Implementation accounting omitted executed work")
    document = _record(request["document"], "Original BuildRequest")
    program = _record(document["program"], "Original program")
    originals = [row for row in _rows(program["declarations"], "Original declarations") if row.get("$type") == "Requirement"]
    requirements = _rows(report["requirements"], "Complete requirement ledger")
    if len(requirements) != len(originals):
        raise CoreProtocolError("Preservation changed the original requirement inventory")
    for raw, original in zip(requirements, originals):
        row = _object(raw, {"id", "kind", "source", "status", "nonvacuous", "histories", "coverage", "witnesses"}, "Requirement result")
        if (row["id"] != original["id"] or row["kind"] != original["kind"] or not _same(row["source"], original)
                or row["status"] not in ("pass", "fail", "unknown", "unsupported") or type(row["nonvacuous"]) is not bool):
            raise CoreProtocolError("Preservation changed an original hard requirement or status")
        histories = _object(row["histories"], {"pass", "fail", "unknown", "not_exercised", "unsupported"}, "Requirement histories")
        history_count = sum(_count(value, "Requirement histories") for value in histories.values())
        if complete and history_count != counts["histories"]:
            raise CoreProtocolError("Completed report lost requirement outcomes for permitted histories")
        samples = _object(row["coverage"], {"samples", "active", "inactive", "enabled_triggers"}, "Requirement coverage")
        for value in samples.values():
            _count(value, "Requirement coverage")
        _record(row["witnesses"], "Requirement witnesses")
        if row["status"] == "pass" and (row["nonvacuous"] is not True or not _count(histories["pass"], "Passing histories")
                or any(_count(histories[key], key) for key in ("fail", "unknown", "unsupported"))):
            raise CoreProtocolError("Passing hard requirement contradicts retained evidence")
    checked = report["status"] == "checked_implementation"
    if report["status"] not in ("checked_implementation", "requirements_not_satisfied", "incomplete"):
        raise CoreProtocolError("Unknown implementation checking status")
    if (checked != (complete and activity["nonvacuous"] is True and all(row["status"] == "pass" for row in requirements))
            or report["assurance"] != ("bounded_requirements_satisfied" if checked else "not_established")
            or complete != (report["status"] != "incomplete")
            or complete and (report["preservation"] != "pass" or report["stopped"] is not None)):
        raise CoreProtocolError("Implementation acceptance contradicts complete original evidence")
    if not complete:
        stop = _object(report["stopped"], {"category", "diagnostic", "history", "source_execution", "candidate_frame"}, "Stopped traversal")
        if report["preservation"] not in ("fail", "unassessed") or type(stop["history"]) is not list:
            raise CoreProtocolError("Incomplete checking lost its exact stopped history")
        _object(stop["diagnostic"], {"code", "message", "path"}, "Stop diagnostic")


@dataclass(frozen=True)
class PolicyImplementationResult:
    """Native evidence snapshot; it grants no material/export authority."""

    request_id: str
    operation: str
    executable: Literal["core", "verify"]
    request_fingerprint: str
    candidate_fingerprint: str
    invocation_fingerprint: str
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

    @property
    def status(self) -> str:
        return cast(str, self.report["status"])


def _result(response: CoreResponse, payload: dict[str, JsonValue]) -> PolicyImplementationResult:
    result = _object(response.result, _RESULT_FIELDS, "Implementation result")
    if any(result[key] != expected for key, expected in (
        ("schema_version", RESULT_SCHEMA), ("implementation", IMPLEMENTATION),
        ("resource_profile", RESOURCE_PROFILE), ("validation_scope", VALIDATION_SCOPE),
    )):
        raise CoreProtocolError("Implementation result changed its negotiated profile")
    request = _original(payload["request"])
    candidate = _object(result["candidate"], {"schema_version", "behavior", "implementation", "binding"}, "Implementation candidate")
    if candidate["schema_version"] != CANDIDATE_SCHEMA or "candidate" in payload and not _same(candidate, payload["candidate"]):
        raise CoreProtocolError("Implementation checker changed the supplied candidate")
    report = _object(result["report"], _REPORT_FIELDS, "Preservation report")
    if report["schema_version"] != "biocompiler.policy_preservation_report.v0.1" or report["profile"] != PRESERVATION_PROFILE:
        raise CoreProtocolError("Preservation report changed its bounded profile")
    _claim(report)
    request_hash = _pin(result["request_fingerprint"], request, "Original request")
    candidate_hash = _pin(result["candidate_fingerprint"], candidate, "Complete candidate")
    invocation_hash = _pin(result["invocation_fingerprint"], {
        "request": request, "candidate": candidate, "limits": payload["limits"],
    }, "Complete invocation")
    report_hash = _pin(result["report_fingerprint"], report, "Complete report")
    if report["request_fingerprint"] != request_hash or not _same(report["limits"], payload["limits"]):
        raise CoreProtocolError("Preservation changed its original request or execution limits")
    _authority(response, request, candidate, report)
    _evidence(request, report)
    if response.operation == "replay-policy-implementation" and not _same(result, payload["report"]):
        raise CoreProtocolError("Fresh replay differs from the full saved implementation wrapper")
    # Count keys as well as values, matching the stricter native publication
    # contract. Core v1's generic value-node bound alone is insufficient here.
    pending: list[JsonValue] = [{"result": result}]
    nodes = 0
    while pending:
        value = pending.pop()
        nodes += 1
        if type(value) is dict:
            nodes += len(value)
            pending.extend(value.values())
        elif type(value) is list:
            pending.extend(value)
        if nodes + len(pending) > MAX_RESULT_NODES:
            raise CoreProtocolError("Complete implementation result exceeds its negotiated node bound")
    framed = encode_json({"result": result})
    if len(framed) > MAX_RESULT_BYTES:
        raise CoreProtocolError("Complete implementation result exceeds its negotiated publication bound")
    return PolicyImplementationResult(response.request_id, response.operation, response.executable,
                                      request_hash, candidate_hash, invocation_hash, report_hash, encode_json(result))


@dataclass(frozen=True)
class PolicyImplementationClient:
    transport: CoreClient

    def _call(self, operation: str, payload: dict[str, JsonValue], *,
              cancelled: Callable[[], bool] | None) -> PolicyImplementationResult:
        snapshot = cast(dict[str, JsonValue], decode_json(encode_json(payload)))
        _original(snapshot["request"])
        if operation == "compile-policy-implementation" and self.transport.role != "core":
            raise CoreProtocolError("Implementation production requires an explicitly selected Core producer")
        capabilities = self.transport.negotiate(operation, cancelled=cancelled)
        if (not _same(capabilities.profiles.get("policy_implementation"), PROFILE)
                or VALIDATION_SCOPE not in capabilities.validation_scopes):
            raise CoreProtocolError("Selected executable lacks the exact bounded implementation profile")
        if operation == "compile-policy-implementation" and not _same(
            capabilities.profiles.get("policy_implementation_producer"), PRODUCER_PROFILE
        ):
            raise CoreProtocolError("Selected executable lacks the exact implementation producer profile")
        return _result(self.transport.call(operation, snapshot, cancelled=cancelled), snapshot)

    def compile(self, request: JsonValue, limits: JsonValue, *,
                cancelled: Callable[[], bool] | None = None) -> PolicyImplementationResult:
        return self._call("compile-policy-implementation", {"request": request, "limits": limits}, cancelled=cancelled)

    def check(self, request: JsonValue, candidate: JsonValue, limits: JsonValue, *,
              cancelled: Callable[[], bool] | None = None) -> PolicyImplementationResult:
        return self._call("check-policy-implementation", {"request": request, "candidate": candidate, "limits": limits}, cancelled=cancelled)

    def replay(self, request: JsonValue, candidate: JsonValue, limits: JsonValue, report: JsonValue, *,
               cancelled: Callable[[], bool] | None = None) -> PolicyImplementationResult:
        """Recheck against the entire saved result wrapper, not its inner report."""
        return self._call("replay-policy-implementation", {
            "request": request, "candidate": candidate, "limits": limits, "report": report,
        }, cancelled=cancelled)
