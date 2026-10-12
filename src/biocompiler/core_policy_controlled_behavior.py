"""Immutable native controlled behavior transport; no Python activity evaluator."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, cast

from . import core_policy_controlled_composition as admission
from .core_client import CoreClient, CoreProtocolError, CoreResponse, JsonValue, _object, decode_json, encode_json
from .core_policy_controlled_material import _admission, _flags
from .core_policy_material import PolicyMaterialResult, _publication
from .core_policy_operational import _fingerprint, _pin, _same

CONSTRUCT = "construct-policy-controlled-behavior"
CHECK = "check-policy-controlled-behavior"
REPLAY = "replay-policy-controlled-behavior"
REQUEST_SCHEMA = "biocompiler.policy_controlled_behavior_request.v0.1"
CANDIDATE_SCHEMA = "biocompiler.policy_controlled_behavior_candidate.v0.1"
REPORT_SCHEMA = "biocompiler.policy_controlled_behavior_assessment.v0.1"
RESULT_SCHEMA = "biocompiler.core.policy_controlled_behavior.v1"
IMPLEMENTATION = "biocompiler.ocaml.policy_controlled_behavior.v0.1"
VALIDATION_SCOPE = "policy-controlled-composition-behavior-v0.1"
ACCEPTED_STATUS = "checked_controlled_behavior"
PROFILE: dict[str, JsonValue] = {**admission.PROFILE, "operations": [CHECK, REPLAY],
    "request_schema": REQUEST_SCHEMA, "candidate_schema": CANDIDATE_SCHEMA,
    "schema_version": RESULT_SCHEMA, "implementation": IMPLEMENTATION,
    "validation_scope": VALIDATION_SCOPE, "stage": "behavior", "artifact": "none", "material": "not_joined"}
PRODUCER_PROFILE: dict[str, JsonValue] = {**PROFILE, "operations": [CHECK, REPLAY, CONSTRUCT]}
_RESULT_FIELDS = set("schema_version implementation resource_profile validation_scope request_fingerprint candidate_fingerprint invocation_fingerprint candidate report_fingerprint report artifact usage".split())
_REPORT_FIELDS = set("schema_version profile implementation stage status outcome claim_scope request_fingerprint candidate_fingerprint invocation_fingerprint admission source_correspondence composition domain requirements coverage model_correspondence evidence_status availability counterexample context assumptions resources budgets material_status empirical_status human_use therapeutic_export".split())
_COVERAGE = set("active background antigen_absent_controller_enabled controller_disabled_antigen_present reversible_cycle".split())
_record = admission._record
_rows = admission._rows
_count = admission._count


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CoreProtocolError(message)


def _original(value: JsonValue) -> dict[str, JsonValue]:
    request = _object(value, {"schema_version", "original", "readout_evidence"}, "Complete behavioral authority")
    _require(request["schema_version"] == REQUEST_SCHEMA, "Unknown behavior request schema")
    original = admission._original(request["original"])
    horizon = _count(_record(original["operating_domain"])["horizon_tick"], 64, 1)
    readout = _object(request["readout_evidence"], {"freshness_ticks", "samples"}, "Original executor readout evidence")
    _count(readout["freshness_ticks"], 64, 1)
    samples = _rows(readout["samples"])
    _require(len(samples) == horizon + 1, "Readout authority must explicitly cover every tick")
    for tick, raw in enumerate(samples):
        row = _object(raw, {"tick", "status", "observed_tick"}, "Readout sample")
        _require(_count(row["tick"], horizon) == tick, "Readout samples must be ordered and unique")
        _require(row["status"] in ("valid", "missing", "invalid", "conflicting"), "Unknown readout evidence status")
        if row["status"] == "missing":
            _require(row["observed_tick"] is None, "Missing readout cannot claim a timestamp")
        else:
            _count(row["observed_tick"], tick)
    _publication(request, 4_000_000, 100_000)
    return request


def _candidate(value: JsonValue) -> dict[str, JsonValue]:
    candidate = _object(value, {"schema_version", "request_fingerprint", "implementation"}, "Complete behavior candidate")
    _require(candidate["schema_version"] == CANDIDATE_SCHEMA, "Unknown behavior candidate schema")
    digest = candidate["request_fingerprint"]
    _require(type(digest) is str and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), "Malformed candidate authority pin")
    implementation = _object(candidate["implementation"], set("schema_version mechanism_model control_contract semantics catalog_binding assembly context resources primitives wires".split()), "Complete activity primitive graph")
    _require(implementation["schema_version"] == "biocompiler.policy_controlled_activity_implementation.v0.1", "Unknown activity implementation")
    for key in ("mechanism_model", "control_contract", "semantics", "catalog_binding", "assembly", "context", "resources"):
        _record(implementation[key])
    primitives = _rows(implementation["primitives"])
    _require(len(primitives) == 8, "Primitive census changed")
    expected: list[JsonValue] = [{"id": "encounter", "op": "encounter_live"}]
    for name, key in (("antigen", "antigen"), ("controller", "controller"), ("protein-a", "protein_a"), ("protein-b", "protein_b")):
        expected.append({"id": name, "op": "physical_input", "key": key})
    expected.append({"id": "gate", "op": "all"})
    _require(_same(primitives[:6], expected), "Closed gate/input primitives changed")
    activity = _object(primitives[6], set("id op onset_ticks cessation_ticks reactivation_ticks initial_band timer_scope activation_scope".split()), "Delayed activity primitive")
    _flags(activity, {"id": "activity", "op": "delayed_reversible", "initial_band": "background",
        "timer_scope": "executor", "activation_scope": "encounter_generation"}, "Activity ownership changed")
    for key in ("onset_ticks", "cessation_ticks", "reactivation_ticks"):
        _count(activity[key], 10_000, 1)
    _require(_same(primitives[7], {"id": "readout", "op": "activity_band"}), "Activity readout changed")
    wires: JsonValue = [{"from": source, "to": target, "input": key} for source, target, key in (
        ("encounter", "gate", "live"), ("antigen", "gate", "antigen"), ("controller", "gate", "controller"),
        ("protein-a", "gate", "protein_a"), ("protein-b", "gate", "protein_b"),
        ("gate", "activity", "enabled"), ("activity", "readout", "band"))]
    _require(_same(implementation["wires"], wires), "Closed candidate wiring changed")
    _publication(candidate, 4_000_000, 100_000)
    return candidate


@dataclass(frozen=True)
class PolicyControlledBehaviorResult(PolicyMaterialResult):
    """Finite conditional behavior evidence; material joining remains unperformed."""


def _result(response: CoreResponse, payload: dict[str, JsonValue]) -> PolicyControlledBehaviorResult:
    value = _object(response.result, _RESULT_FIELDS, "Controlled behavior result")
    _flags(value, {"schema_version": RESULT_SCHEMA, "implementation": IMPLEMENTATION,
        "resource_profile": admission.RESOURCE_PROFILE, "validation_scope": VALIDATION_SCOPE}, "Behavior result changed negotiated profile")
    request = _original(payload["request"])
    original = _record(request["original"])
    candidate = _candidate(value["candidate"])
    _pin(candidate["request_fingerprint"], request, "Candidate complete behavior authority")
    if "candidate" in payload:
        _require(_same(candidate, payload["candidate"]), "Native checker substituted supplied candidate")
    request_hash = _pin(value["request_fingerprint"], request, "Complete behavior request")
    candidate_hash = _pin(value["candidate_fingerprint"], candidate, "Complete behavior candidate")
    invocation_hash = _pin(value["invocation_fingerprint"], {"request_fingerprint": request_hash,
        "candidate_fingerprint": candidate_hash}, "Behavior invocation")
    report = _object(value["report"], _REPORT_FIELDS, "Complete behavioral assessment")
    report_hash = _pin(value["report_fingerprint"], report, "Complete behavioral assessment")
    _flags(report, {"schema_version": REPORT_SCHEMA, "profile": admission.REQUEST_PROFILE,
        "implementation": "biocompiler.ocaml.policy_controlled_behavior_check.v0.1", "stage": "behavior",
        "claim_scope": "conditional_supplied_model_and_source_requirements_in_complete_finite_domain",
        "request_fingerprint": request_hash, "candidate_fingerprint": candidate_hash, "invocation_fingerprint": invocation_hash,
        "material_status": "not_joined", "empirical_status": "unassessed", "human_use": "unassessed",
        "therapeutic_export": "withheld"}, "Behavior assessment upgraded its conditional scope")
    _require(value["artifact"] is None, "Behavior-only operation cannot publish a material artifact")
    for key in ("context", "resources", "budgets"):
        _require(_same(report[key], original[key]), "Behavior report changed complete original " + key)
    source = _record(original["source_authority"])
    implementation = _record(candidate["implementation"])
    originals = {key: original[key] for key in ("mechanism_model", "catalog_binding", "assembly", "context", "resources")}
    originals.update(control_contract=source["control_contract"], semantics=_record(_record(source["document"])["program"])["semantics"])
    for key, authority in originals.items():
        _require(_same(implementation[key], authority), "Candidate copied authority differs from complete original " + key)
    activity = _record(_rows(implementation["primitives"])[6])
    delays = _record(_record(original["mechanism_model"])["body"])["delays"]
    _require(_same({key: activity[key] for key in ("onset_ticks", "cessation_ticks", "reactivation_ticks")}, delays), "Candidate primitive delays differ from supplied actual model")
    _require(_same(report["assumptions"], _record(source["project_context"])["assumptions"]), "Behavior report changed supplied assumptions")
    budgets = _record(original["budgets"])
    usage = _object(value["usage"], {"unit", "preparation_charged_work", "request_decoding_work", "publication"}, "Behavior work accounting")
    _flags(usage, {"unit": "logical_data_visits_and_child_semantic_work", "publication": "requires_original_one_shot_frame_guard"}, "Behavior work accounting changed")
    total = _count(usage["preparation_charged_work"], cast(int, budgets["max_work"]), 1)
    decoding = _count(usage["request_decoding_work"], total, 1)
    _admission(report["admission"], original, total, decoding)
    admitted = _record(_record(report["admission"])["source_admission"])
    _require(_count(admitted["horizon_ticks"], 64, 1) == _record(original["operating_domain"])["horizon_tick"],
             "Source admission changed its exact integral horizon")
    _require(_same(report["source_correspondence"], admitted["correspondence"]), "Behavior report lost exact source correspondence")
    coverage = _object(report["coverage"], _COVERAGE, "Complete non-vacuous behavior coverage")
    _require(all(type(item) is bool for item in coverage.values()), "Coverage flags must be exact booleans")
    _require(report["model_correspondence"] in ("pass", "fail", "incomplete"), "Unknown model correspondence status")
    _require(report["evidence_status"] in ("resolved", "unknown"), "Unknown evidence status")
    domain = _object(report["domain"], {"completion", "counters", "assessed_histories", "pending_at_horizon"}, "Complete domain assessment")
    _require(domain["completion"] in ("complete", "exhausted", "cancelled") and type(domain["pending_at_horizon"]) is bool,
             "Unknown completion or pending flag")
    _require((report["model_correspondence"] == "incomplete") == (domain["completion"] != "complete"),
             "Model correspondence completeness differs from domain completion")
    counters = _object(domain["counters"], {"prefixes", "transitions", "histories", "work"}, "Behavior domain census")
    limits = _record(_record(original["operating_domain"])["limits"])
    counts = {key: _count(raw, _count(limits["max_" + key], 16_000_000, 1)) for key, raw in counters.items()}
    histories = _count(domain["assessed_histories"], counts["histories"])
    _require(histories == counts["histories"] and counts["prefixes"] == counts["transitions"] + 1
             and counts["work"] <= total - decoding, "Behavior exploration counters contradict retained work")
    if domain["completion"] == "complete":
        _require(histories > 0 and _same(counters, _record(report["admission"])["domain_counters"]),
                 "Complete behavioral exploration differs from admitted complete domain census")
    composition = _object(report["composition"], set("rule modules wires controller_records observation_records timer_cells state_bits dependency_reconstruction whole_program_crosscheck executable_authority component_definition_role".split()), "Explicit module composition")
    _flags(composition, {"rule": "two_executor_owned_availability_projections_into_one_reversible_activity",
        "controller_records": 1, "observation_records": 2, "timer_cells": 3, "state_bits": 4,
        "dependency_reconstruction": "pass", "executable_authority": "complete_supplied_deterministic_delay_model",
        "component_definition_role": "declared_realization_dependencies_not_independent_executors"}, "Composition changed its explicit conditional premise")
    for key in ("controller_records", "observation_records", "timer_cells", "state_bits"):
        _count(composition[key], 4, 1)
    _require(composition["whole_program_crosscheck"] == ("pass" if domain["completion"] == "complete" and report["model_correspondence"] == "pass" else "not_accepted"), "Composition crosscheck contradicts domain/model evidence")
    implementation = _record(candidate["implementation"])
    _require(_same(composition["wires"], implementation["wires"]), "Composition omitted candidate wiring")
    bindings = [_record(row) for row in _rows(_record(original["assembly"])["product_bindings"])]
    modules = _rows(composition["modules"])
    _require(len(modules) == len(bindings) == 2, "Composition omitted a member")
    for index, (raw, binding) in enumerate(zip(modules, bindings)):
        module = _object(raw, set("member_id product_parameter assumptions input guarantee biological_realization".split()), "Conditional component module")
        _flags(module, {"member_id": binding["member_id"], "product_parameter": binding["product_parameter"],
            "input": "protein_a" if index == 0 else "protein_b", "guarantee": "identity_projection_of_supplied_functional_availability",
            "biological_realization": "unassessed"}, "Component module changed supplied bindings or claimed independent biological execution")
        _require(_same(module["assumptions"], original["context"]), "Component premise changed original context")
    requirements = [_record(row) for row in _rows(report["requirements"])]
    source_requirements = [_record(row) for row in _rows(admitted["requirements"])]
    _require(len(requirements) == len(source_requirements) == 6, "Behavior assessment omitted a source requirement")
    requirement_fail = False
    requirement_unknown = False
    declarations = [_record(row) for row in _rows(_record(report["source_correspondence"])["declarations"])]
    definitions = [_record(row) for row in _rows(_record(report["source_correspondence"])["definitions"])]
    for row, authority in zip(requirements, source_requirements):
        _object(row, set("id kind source_path original contract pass fail unknown not_exercised".split()), "Aggregated source requirement")
        for key in ("id", "kind", "source_path"):
            _require(row[key] == authority[key], "Behavior requirement correspondence changed")
        declaration = next((item for item in declarations if item["id"] == row["id"]), None)
        _require(declaration is not None and _same(row["original"], declaration["original"]), "Requirement lost its complete source body")
        contract = _record(_record(row["original"])["contract"])
        definition = next((item for item in definitions if _record(item["reference"])["id"] == contract["id"]), None)
        _require(definition is not None and _same(row["contract"], definition["original"]), "Requirement lost its complete contract body")
        outcomes = {key: _count(row[key], histories) for key in ("pass", "fail", "unknown", "not_exercised")}
        _require(sum(outcomes.values()) == histories, "Requirement did not assess every completed history exactly once")
        requirement_fail |= outcomes["fail"] > 0
        requirement_unknown |= outcomes["unknown"] > 0
    availability = _rows(report["availability"])
    _require(len(availability) == 2, "Availability omitted a member")
    frames = histories * (_count(_record(original["operating_domain"])["horizon_tick"], 64, 1) + 1)
    rna_unknown = False
    for raw, binding in zip(availability, bindings):
        row = _object(raw, set("member_id scope rna_absent_frames protein_absent_frames rna_unknown_evidence_frames protein_unknown_evidence_frames deployment_assumptions physical_loss evidence_status".split()), "Separate molecular availability")
        _flags(row, {"member_id": binding["member_id"], "scope": "executor", "deployment_assumptions": "admitted_conditional_premises"}, "Availability changed member or scope")
        amounts = {key: _count(row[key], frames) for key in ("rna_absent_frames", "protein_absent_frames", "rna_unknown_evidence_frames", "protein_unknown_evidence_frames")}
        _require(row["physical_loss"] == ("observed_in_domain" if amounts["rna_absent_frames"] + amounts["protein_absent_frames"] else "not_observed"), "Physical loss confused with evidence")
        _require(row["evidence_status"] == ("unknown" if amounts["rna_unknown_evidence_frames"] + amounts["protein_unknown_evidence_frames"] else "resolved"), "Availability evidence status contradicts counts")
        rna_unknown |= amounts["rna_unknown_evidence_frames"] > 0
    _require(not (requirement_unknown or rna_unknown) or report["evidence_status"] == "unknown", "Behavior assessment suppressed relevant unknown evidence")
    if domain["completion"] == "complete" and (requirement_fail or requirement_unknown or rna_unknown
            or domain["pending_at_horizon"] is True or report["model_correspondence"] == "fail"):
        _require(report["counterexample"] is not None, "Complete nonacceptance lost its required retained counterexample")
    if report["counterexample"] is not None:
        counterexample = _object(report["counterexample"], set("history_index reduction model_correspondence pending_at_horizon deployment_evidence_unknown source_monitor trace".split()), "Complete retained counterexample")
        _count(counterexample["history_index"], histories, 1)
        _require(counterexample["reduction"] == "none_complete_original_history", "Unvalidated counterexample reduction")
        for key in ("model_correspondence", "pending_at_horizon", "deployment_evidence_unknown"):
            _require(type(counterexample[key]) is bool, "Counterexample flags must be booleans")
        _require(not counterexample["pending_at_horizon"] or domain["pending_at_horizon"] is True,
                 "Retained pending transition disappeared from the aggregate")
        _require(not counterexample["deployment_evidence_unknown"] or (rna_unknown and report["evidence_status"] == "unknown"),
                 "Retained deployment gap disappeared from the aggregate")
        monitored = _object(counterexample["source_monitor"], set("schema_version profile complete outcome horizon_ticks last_tick pending evidence_policy requirements coverage evidence_gaps history".split()), "Original source monitor")
        horizon = _count(_record(original["operating_domain"])["horizon_tick"], 64, 1)
        _flags(monitored, {"schema_version": "biocompiler.policy_controlled_source_monitor.v0.1",
            "profile": admission.REQUEST_PROFILE, "evidence_policy": "biocompiler.controlled_evidence.conservative.v0.1"}, "Source monitor changed closed scope")
        _require(monitored["complete"] is True and type(monitored["pending"]) is bool
            and monitored["outcome"] in ("pass", "fail", "unknown")
            and _count(monitored["horizon_ticks"], 64, 1) == horizon
            and _count(monitored["last_tick"], 64) == horizon, "Retained source monitor truncated original horizon")
        _require(not monitored["pending"] or counterexample["pending_at_horizon"] is True,
                 "Retained source obligation disappeared from pending accounting")
        monitored_coverage = _object(monitored["coverage"], _COVERAGE, "Counterexample coverage")
        _require(all(type(value) is bool for value in monitored_coverage.values())
                 and all(not value or coverage[key] for key, value in monitored_coverage.items()), "Counterexample coverage contradicts complete aggregate")
        monitored_rows = _rows(monitored["requirements"])
        _require(len(monitored_rows) == 6, "Source monitor omitted an obligation")
        monitored_statuses: list[str] = []
        for raw, aggregate, authority in zip(monitored_rows, requirements, source_requirements):
            row = _object(raw, set("id source_path kind status deadline_ticks source_declaration contract events".split()), "Counterexample source obligation")
            for key in ("id", "kind", "source_path", "deadline_ticks"):
                _require(_same(row[key], authority[key]), "Counterexample source correspondence changed")
            _require(row["status"] in ("pass", "fail", "unknown", "not_exercised") and aggregate[cast(str, row["status"])] != 0,
                     "Counterexample source status contradicts aggregate")
            monitored_statuses.append(cast(str, row["status"]))
            _require(_same(row["source_declaration"], aggregate["original"]), "Counterexample source body changed")
            contract = _object(row["contract"], {"identity", "path", "reference", "body"}, "Original requirement contract")
            reference = _record(_record(aggregate["original"])["contract"])
            definition = next(item for item in definitions if _record(item["reference"])["id"] == reference["id"])
            _require(contract["identity"] == reference["id"] and contract["path"] == definition["source_path"]
                and _same(contract["reference"], reference) and _same(contract["body"], aggregate["contract"]), "Counterexample lost full contract authority")
            for raw_event in _rows(row["events"]):
                event = _record(raw_event)
                if event.get("action") == "violation":
                    _object(event, {"tick", "action", "reason"}, "Source violation event")
                    _count(event["tick"], horizon)
                    _require(event["reason"] in ("activation_without_uninterrupted_qualified_response",
                        "active_episode_changed_generation_without_background"), "Unknown source violation reason")
                else:
                    _object(event, {"tick", "action", "trigger_tick", "deadline_tick", "generation"}, "Source deadline event")
                    event_tick = _count(event["tick"], horizon)
                    _require(event["action"] in ("triggered", "cancelled", "discharged", "deadline_missed"), "Unknown source deadline action")
                    trigger = _count(event["trigger_tick"], event_tick)
                    deadline = _count(event["deadline_tick"], 128, trigger + 1)
                    _require(deadline == trigger + _count(row["deadline_ticks"], 64, 1),
                             "Source event changed its original deadline bound")
                    _count(event["generation"], 16, 1)
        monitor_uncertain = "unknown" in monitored_statuses or monitored["pending"] is True or bool(_rows(monitored["evidence_gaps"]))
        monitor_outcome = "fail" if "fail" in monitored_statuses else "unknown" if monitor_uncertain else "pass"
        _require(monitored["outcome"] == monitor_outcome, "Retained source outcome contradicts its six obligations")
        _require(not monitor_uncertain or report["evidence_status"] == "unknown",
                 "Retained source uncertainty disappeared from the aggregate")
        for raw_gap in _rows(monitored["evidence_gaps"]):
            gap = _object(raw_gap, {"tick", "channel", "status"}, "Required evidence gap")
            _count(gap["tick"], horizon)
            _require(gap["channel"] in ("activity", "antigen", "controller", "protein_a", "protein_b")
                and gap["status"] in ("stale", "missing", "invalid", "conflicting"), "Unknown evidence gap kind")
        trace = _rows(counterexample["trace"])
        _require(len(trace) == _count(_record(original["operating_domain"])["horizon_tick"], 64, 1) + 1, "Counterexample dropped original history suffix")
        monitor_history = _rows(monitored["history"])
        _require(len(monitor_history) == len(trace), "Source monitor dropped original frames")
        trace_corresponds = True
        for tick, (raw, raw_history) in enumerate(zip(trace, monitor_history)):
            frame = _object(raw, {"input", "candidate", "model_reference", "corresponds"}, "Counterexample frame")
            inputs = _object(frame["input"], set("tick event live generation generation_started_tick physical evidence".split()), "Original input batch")
            _require(type(frame["corresponds"]) is bool and _count(inputs["tick"], 64) == tick, "Counterexample changed tick order")
            _require(inputs["event"] in ("none", "start", "end", "reset") and type(inputs["live"]) is bool, "Input lifecycle changed shape")
            generation = _count(inputs["generation"], 16)
            _count(inputs["generation_started_tick"], tick)
            input_keys = {"antigen", "controller", "rna_a", "rna_b", "protein_a", "protein_b"}
            physical = _object(inputs["physical"], input_keys, "Original physical frame")
            for key, band in physical.items():
                alphabet = ("enabled", "disabled") if key == "controller" else ("present", "absent")
                _require(type(band) is str and band in alphabet, "Physical input changed its native categorical alphabet")
            evidence = _object(inputs["evidence"], input_keys, "Original evidence frame")
            for key, raw_evidence in evidence.items():
                observation = _object(raw_evidence, {"status", "observed_tick", "generation"}, "Original channel evidence")
                _require(observation["status"] in ("valid", "missing", "invalid", "conflicting"), "Evidence quality changed")
                if observation["status"] == "missing":
                    _require(observation["observed_tick"] is None and observation["generation"] is None,
                             "Missing channel evidence cannot claim a timestamp or generation")
                else:
                    _count(observation["observed_tick"], tick)
                    if key == "antigen":
                        _count(observation["generation"], generation)
                    else:
                        _require(observation["generation"] is None, "Executor evidence cannot claim encounter ownership")
            history = _object(raw_history, {"input", "activity", "readout_evidence", "qualified_gate", "inputs_required"}, "Original monitored frame")
            _require(_same(history["input"], inputs) and _same(history["activity"], frame["candidate"]), "Source monitoring used different physical history")
            _require(history["readout_evidence"] in ("valid", "stale", "missing", "invalid", "conflicting")
                and type(history["qualified_gate"]) is bool and type(history["inputs_required"]) is bool, "Source monitoring mixed physical and evidence states")
            readout_authority = _record(request["readout_evidence"])
            readout_sample = _record(_rows(readout_authority["samples"])[tick])
            expected_readout = readout_sample["status"]
            observed = readout_sample["observed_tick"]
            if observed is not None and tick - cast(int, observed) > cast(int, readout_authority["freshness_ticks"]):
                expected_readout = "stale"
            _require(history["readout_evidence"] == expected_readout, "Counterexample changed original executor readout evidence")
            for key in ("candidate", "model_reference"):
                sample = _object(frame[key], {"tick", "band", "activation_generation"}, "Activity sample")
                _require(_count(sample["tick"], 64) == tick and sample["band"] in ("background", "active"), "Activity sample changed physical bands")
                sample_generation = sample["activation_generation"]
                if sample_generation is not None:
                    _count(sample_generation, generation, 1)
                _require((sample_generation is None) == (sample["band"] == "background"), "Activity generation contradicts physical band")
            _require(frame["corresponds"] == _same(frame["candidate"], frame["model_reference"]), "Counterexample correspondence contradicts retained exact samples")
            trace_corresponds = trace_corresponds and frame["corresponds"] is True
        _require(counterexample["model_correspondence"] == trace_corresponds, "Retained model summary contradicts its complete trace")
        _require(trace_corresponds or report["model_correspondence"] != "pass",
                 "Retained model mismatch disappeared from the aggregate")
    _require(report["outcome"] in ("pass", "fail", "unknown"), "Unknown behavioral outcome")
    failed = requirement_fail or report["model_correspondence"] == "fail" or domain["pending_at_horizon"] is True or (domain["completion"] == "complete" and not all(coverage.values()))
    expected_outcome = "fail" if failed else "pass" if domain["completion"] == "complete" and report["evidence_status"] == "resolved" else "unknown"
    _require(report["outcome"] == expected_outcome, "Behavior outcome contradicts retained requirement/domain/evidence assessments")
    passed = report["outcome"] == "pass"
    _require(report["status"] == (ACCEPTED_STATUS if passed else "not_accepted"), "Behavior status contradicts its outcome")
    if passed:
        _require(all(coverage.values()) and report["model_correspondence"] == "pass"
            and report["evidence_status"] == "resolved" and report["counterexample"] is None,
            "Behavior acceptance lacks complete resolved evidence and non-vacuous coverage")
    if response.operation == REPLAY:
        _require(_same(report, payload["report"]), "Replay substituted supplied report instead of exact fresh comparison")
    _publication(report, cast(int, budgets["max_report_bytes"]), cast(int, budgets["max_report_nodes"]))
    _publication({"result": value}, admission.MAX_RESULT_BYTES, admission.MAX_RESULT_NODES)
    return PolicyControlledBehaviorResult(response.request_id, response.operation, response.executable,
        request_hash, candidate_hash, invocation_hash, report_hash, encode_json(value))


@dataclass(frozen=True)
class PolicyControlledBehaviorClient:
    transport: CoreClient

    def _call(self, operation: str, payload: dict[str, JsonValue], *, cancelled: Callable[[], bool] | None) -> PolicyControlledBehaviorResult:
        snapshot = cast(dict[str, JsonValue], decode_json(encode_json(payload)))
        _original(snapshot["request"])
        if "candidate" in snapshot:
            _candidate(snapshot["candidate"])
        if "report" in snapshot:
            _object(snapshot["report"], _REPORT_FIELDS, "Original replay report")
        _require(operation != CONSTRUCT or self.transport.role == "core", "Behavior construction requires explicit Core producer")
        capabilities = self.transport.negotiate(operation, cancelled=cancelled)
        profile = PRODUCER_PROFILE if self.transport.role == "core" else PROFILE
        _require(_same(capabilities.profiles.get("policy_controlled_composition_behavior"), profile)
            and VALIDATION_SCOPE in capabilities.validation_scopes, "Selected executable lacks exact behavior-only capability")
        response = self.transport.call(operation, snapshot, cancelled=cancelled)
        _require(response.operation == operation and response.executable == self.transport.role, "Behavior response changed operation or executable")
        return _result(response, snapshot)

    def construct_behavior(self, request: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyControlledBehaviorResult:
        return self._call("construct-policy-controlled-behavior", {"request": request}, cancelled=cancelled)

    def check_behavior(self, request: JsonValue, candidate: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyControlledBehaviorResult:
        return self._call("check-policy-controlled-behavior", {"request": request, "candidate": candidate}, cancelled=cancelled)

    def replay_behavior(self, request: JsonValue, candidate: JsonValue, report: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> PolicyControlledBehaviorResult:
        return self._call("replay-policy-controlled-behavior", {"request": request, "candidate": candidate, "report": report}, cancelled=cancelled)
