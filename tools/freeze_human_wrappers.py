"""Retain bounded structural human authority, without assessment or admission.

Use the installed biocompiler selected by the caller. Repository imports supply
artificial examples only. Source coordinates are standardized before wrapper
reconstruction; diagnostic coordinates remain part of full artifact identity.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import sys

import biocompiler as bc
from biocompiler.ir.serialization import fingerprint

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from examples.human_behavior import make_human_behavior
from examples.human_deployment import make_human_deployment, with_fixture_bounds, co_payload_fixture, seconds
from examples.human_acceptance import make_human_acceptance
from biocompiler.ir.circuit_profile import CircuitProfileRequest, ImmuneRecipientIdentity
from biocompiler.ir.circuit_intent import CircuitRequest, CircuitRequirement

CORPUS = ROOT / "tests/conformance/human-wrappers-v1.json"
SCHEMA = "biocompiler.human_wrappers_conformance.v1"
PARSERS = dict(target_claim=bc.TargetClaim, observable=bc.Observable, response=bc.ResponseRequirement,
    measurement=bc.MeasurementSpec, predicate=bc.PredicateRefinement, conditional_secretion=bc.ConditionalSecretionContract,
    platform=bc.DeliveryPlatformSpec, exposure=bc.ExposureAssumption, timing=bc.ExpressionTiming,
    co_payload=bc.CoPayloadRequirement, deployment=bc.DeploymentContract,
    input_availability=bc.InputAvailabilitySpec, shutdown=bc.ExternalShutdownSpec, acceptance=bc.HumanAcceptanceContract,
    build=bc.BuildRequest, behavior_request=bc.HumanBehaviorRequest, deployment_request=bc.HumanDeploymentRequest,
    acceptance_request=bc.HumanAcceptanceRequest, profile=CircuitProfileRequest, circuit=CircuitRequest)
WRAPPERS = {"build", "behavior_request", "deployment_request", "acceptance_request"}


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def standardized(value):
    if isinstance(value, dict):
        if set(value) == {"file", "line", "function"}:
            return {"file": "fixtures/human_wrappers.py", "line": 11, "function": "artificial_human_source"}
        return {key: standardized(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [standardized(item) for item in value]
    return value


def portable(value):
    result = type(value).from_dict(standardized(value.to_dict()))
    require(result.fingerprint == value.fingerprint, "Source standardization changed semantic authority")
    return result


def source_kind(value):
    return {bc.BuildRequest: "build", bc.HumanBehaviorRequest: "behavior_request",
            bc.HumanDeploymentRequest: "deployment_request", bc.HumanAcceptanceRequest: "acceptance_request"}[type(value)]


def evidence_paths(value):
    if isinstance(value, bc.BuildRequest): return []
    behavior = value if isinstance(value, bc.HumanBehaviorRequest) else value.behavior_request
    result = ["behavior.contract." + path for path in behavior.contract.unresolved_evidence]
    if isinstance(value, (bc.HumanDeploymentRequest, bc.HumanAcceptanceRequest)):
        deployment = value if isinstance(value, bc.HumanDeploymentRequest) else value.deployment_request
        result += ["deployment." + path for path in deployment.deployment.unresolved_evidence]
    if isinstance(value, bc.HumanAcceptanceRequest):
        result += ["acceptance." + path for path in value.acceptance.unresolved_evidence]
    return result


def profile(source):
    target = source.target
    return CircuitProfileRequest("human_immune_payload", "candidate_design", target.payload_format, "planning", target,
        ImmuneRecipientIdentity(bc.ImmuneLineage.T_CELL, target.fingerprint, target.human_target.cell_subtype.fingerprint), None, source)


def circuit(source):
    build = source if isinstance(source, bc.BuildRequest) else source.build_request
    role = next(node.id for node in build.intent.nodes if node.kind == "role")
    incoming = bc.CircuitObservation("artificial_cue", bc.ObservationEntity("fixture", "cue", "1", "unknown"),
        bc.QuantityKind.MIRNA_ACTIVITY, "cytoplasm", bc.ObservationScope.CELL_ACCESSIBLE,
        bc.ObservationWindow("unknown", None, None, "unknown", "unknown"), bc.ObservationEncoding("qualitative", "qualitative"))
    outgoing = replace(incoming, id="artificial_report", quantity=bc.QuantityKind.FLUORESCENCE, scope=bc.ObservationScope.EVALUATOR)
    behavior = bc.CircuitBehavior((incoming,), bc.BooleanSpec((bc.CircuitSignal(incoming.id, incoming.fingerprint),), (False, True)),
        bc.CircuitProduct("report", bc.ProductKind.REPORTER_FLUORESCENCE, outgoing),
        bc.CircuitLifecycle("readout", None, None, None), ())
    requirement = CircuitRequirement("supplementary", behavior, role, (role,), None)
    deployment = source.deployment_request.deployment if isinstance(source, bc.HumanAcceptanceRequest) else source.deployment if isinstance(source, bc.HumanDeploymentRequest) else None
    return CircuitRequest(profile(source), (requirement,), "delivered_rna", "base_identity", "explicit_deployment" if deployment is None else deployment.id)


def changed(value, path, replacement):
    result = deepcopy(value)
    target = result
    for key in path[:-1]: target = target[key]
    target[path[-1]] = deepcopy(replacement)
    return result


def build_corpus():
    records, rejections, literals = [], [], []
    def add(identity, kind, value, *, expected=None):
        raw = value.to_dict() if hasattr(value, "to_dict") else deepcopy(value)
        parsed = PARSERS[kind].from_dict(raw)
        normalized = parsed.to_dict()
        if expected is not None:
            require(encoded(normalized) == encoded(expected), "Independent literal differs: " + identity)
            literals.append({"id": identity, "normalized": expected})
        item = dict(id=identity, kind=kind, input=raw, normalized=normalized,
                    fingerprint=parsed.fingerprint, artifact_fingerprint=fingerprint(normalized))
        if kind in WRAPPERS:
            item["unresolved_evidence"] = evidence_paths(parsed)
        records.append(item)
        return parsed
    def reject(identity, kind, value, path, replacement, code, stage="record"):
        raw = value.to_dict() if hasattr(value, "to_dict") else value
        raw = changed(raw, path, replacement)
        try: PARSERS[kind].from_dict(raw)
        except (ValueError, TypeError) as error:
            rejections.append(dict(id=identity, kind=kind, input=raw, expected_code=code, expected_stage=stage,
                                   python_exception=type(error).__name__, python_error=str(error)))
        else: raise AssertionError("Intended rejection accepted: " + identity)
    behavior = portable(make_human_behavior())
    deployment = portable(make_human_deployment())
    bounded = portable(with_fixture_bounds(make_human_deployment()))
    acceptance = portable(make_human_acceptance())
    c, d, a = behavior.contract, bounded.deployment, acceptance.acceptance
    values = dict(target_claim=c.goal_refinement, observable=c.input_measurement.observable, response=c.response,
        measurement=c.input_measurement, predicate=c.predicate, conditional_secretion=c, platform=d.platform,
        exposure=d.exposures[0], timing=d.timing, co_payload=co_payload_fixture(), deployment=d,
        input_availability=a.input_availability, shutdown=a.shutdown, acceptance=a, build=behavior.build_request,
        behavior_request=behavior, deployment_request=bounded, acceptance_request=acceptance)
    for kind, value in values.items(): add("base/" + kind, kind, value)
    add("deployment/unknown_timing", "deployment_request", deployment)
    copayload = replace(bounded, deployment=replace(d, co_payloads=(co_payload_fixture(),)))
    add("deployment/required_co_payload_unimplemented", "deployment_request", copayload)
    late = replace(bounded, deployment=replace(d, timing=replace(d.timing, onset=seconds(7, 8))))
    add("deployment/structurally_valid_late_onset", "deployment_request", late)
    add("predicate/strict_greater", "predicate", replace(c.predicate, operator=">"))
    for operator in ("<", "<="):
        data = behavior.to_dict()
        data["contract"]["predicate"]["operator"] = operator
        predicate_id = data["contract"]["predicate"]["predicate_id"]
        next(node for node in data["build_request"]["intent"]["nodes"] if node["id"] == predicate_id)["attributes"]["band"] = "low"
        add("behavior/" + operator, "behavior_request", data)
    unit = replace(behavior, contract=replace(c, horizon=bc.Duration(1, unit="min")))
    add("behavior/explicit_unit_conversion", "behavior_request", unit)
    data = behavior.to_dict()
    for node in data["build_request"]["intent"]["nodes"]: node["source"]["line"] += 1
    moved = add("behavior/source_only_relocation", "behavior_request", data)
    require(moved.fingerprint == behavior.fingerprint and moved.artifact_fingerprint != behavior.artifact_fingerprint,
            "Source-only identity distinction lost")
    mapping = {node.id: "renamed_" + node.id for node in behavior.build_request.intent.nodes}
    def rename(value):
        if isinstance(value, str): return mapping.get(value, value)
        if isinstance(value, list): return [rename(item) for item in value]
        if isinstance(value, dict): return {key: rename(item) for key, item in value.items()}
        return value
    add("behavior/alpha_renamed", "behavior_request", rename(behavior.to_dict()))
    # Integer/float spellings of durations remain distinct nominal authority.
    add("behavior/float_duration", "behavior_request", replace(behavior, contract=replace(c, horizon=bc.Duration(10.0))))
    for source in (behavior.build_request, behavior, bounded, acceptance):
        kind = source_kind(source)
        add("profile/" + kind, "profile", profile(source))
        add("circuit/" + kind, "circuit", circuit(source))
    claim_literal = {"schema_version": "biocompiler.target_claim.v0.1", "description": "Artificial claim.", "basis": "cited",
                     "evidence_ids": ["a", "z"], "limitations": "No empirical validation."}
    add("literal/cited_claim", "target_claim", changed(claim_literal, ("evidence_ids",), ["z", "a"]), expected=claim_literal)
    scalar_type = {"kind": "scalar", "name": "Level", "dimensions": {}, "arguments": []}
    observable_literal = {"schema_version": "biocompiler.observable.v0.1", "id": "readout", "dtype": scalar_type,
                          "role": "role", "scope": "cell", "compartment": "cytoplasm"}
    add("literal/observable", "observable", changed(observable_literal, ("dtype",), {"kind": "scalar", "name": "Level"}), expected=observable_literal)
    def scalar_literal(value, name, dimensions, unit):
        return {"kind": "scalar", "value": value, "canonical_value": value, "unit": unit,
                "type": {"kind": "scalar", "name": name, "dimensions": dimensions, "arguments": []}}
    def rate_interval(lower, upper):
        return {"kind": "interval", "lower": scalar_literal(lower, "ProductionRate", {"amount": 1, "time": -1}, "mol/s"),
                "upper": scalar_literal(upper, "ProductionRate", {"amount": 1, "time": -1}, "mol/s"),
                "type": {"kind": "interval", "name": "Interval[ProductionRate]", "dimensions": {},
                         "arguments": [{"kind": "scalar", "name": "ProductionRate", "dimensions": {"amount": 1, "time": -1}, "arguments": []}]}}
    response_literal = {"schema_version": "biocompiler.response_requirement.v0.1", "id": "response", "rule_id": "rule", "specification_id": "action",
        "observable": {**observable_literal, "dtype": {"kind": "scalar", "name": "ProductionRate", "dimensions": {"amount": 1, "time": -1}, "arguments": []}},
        "active_range": rate_interval(2, 3), "inactive_range": rate_interval(0, 1),
        "max_activation_delay": scalar_literal(0, "Duration", {"time": 1}, "s"),
        "max_deactivation_delay": scalar_literal(1.0, "Duration", {"time": 1}, "s")}
    add("literal/response", "response", response_literal, expected=response_literal)
    shutdown_literal = {"schema_version": "biocompiler.external_shutdown_spec.v0.1", "id": "stop", "request_definition": "Recorded request.",
        "observation_method": "Artificial log.", "response_delay": scalar_literal(0, "Duration", {"time": 1}, "s"),
        "observability": claim_literal, "controllability": claim_literal, "request_access": "external_evaluator",
        "persistence": "latched_for_remaining_horizon", "requirement": "background_after_deadline",
        "overrides_source_guard": False, "actuator_support": "unimplemented"}
    add("literal/shutdown", "shutdown", shutdown_literal, expected=shutdown_literal)
    # Strict schemas for every record and wrapper are retained, not only selected leaves.
    for kind, value in values.items():
        raw = value.to_dict()
        for key in raw:
            missing = deepcopy(raw); del missing[key]
            try: PARSERS[kind].from_dict(missing)
            except (ValueError, TypeError) as error:
                rejections.append(dict(id="missing/" + kind + "/" + key, kind=kind, input=missing, expected_code="missing_field",
                    expected_stage="record", python_exception=type(error).__name__, python_error=str(error)))
            else: raise AssertionError("Missing field accepted")
        reject("schema/" + kind, kind, value, ("schema_version",), "future", "unsupported_schema")
        reject("extra/" + kind, kind, value, ("validated",), True, "unknown_field")
    mutations = [
      ("measurement", ("access",), "external_evaluator", None),
      ("conditional_secretion", ("input_measurement", "access"), "external_evaluator", "invalid_human_contract"),
      ("conditional_secretion", ("output_measurement", "access"), "cell", "invalid_human_contract"),
      ("conditional_secretion", ("predicate", "operator"), "==", "invalid_human_contract"),
      ("conditional_secretion", ("predicate", "threshold"), bc.Concentration(20, unit="nM").to_dict(), "invalid_human_contract"),
      ("conditional_secretion", ("horizon",), bc.Duration(3).to_dict(), "invalid_human_contract"),
      ("conditional_secretion", ("initial_range",), bc.Interval(bc.ProductionRate(-1), bc.ProductionRate(0), type=bc.ProductionRate).to_dict(), "invalid_human_contract"),
      ("predicate", ("threshold", "canonical_value"), 99, "canonical_value_mismatch"),
      ("response", ("max_activation_delay",), bc.Duration(-1).to_dict(), "invalid_measurement_contract"),
      ("deployment", ("exposures",), [], "invalid_human_contract"),
      ("deployment", ("exposures",), [d.exposures[0].to_dict()] * 2, "invalid_human_contract"),
      ("deployment", ("exposure_window",), seconds(1, 2).to_dict(), "invalid_human_contract"),
      ("timing", ("duration",), seconds(0, 1).to_dict(), "invalid_human_contract"),
      ("timing", ("unknown_reason",), "invented", "invalid_human_contract"),
      ("co_payload", ("required",), 1, "invalid_human_contract"),
      ("co_payload", ("recipient_scope",), "same_patient", "invalid_human_contract"),
      ("co_payload", ("payload_identity", "kind"), "model", "invalid_human_contract"),
      ("deployment", ("delivery_targeting_is_disease_recognition",), 0, "invalid_human_contract"),
      ("acceptance", ("healthy_range",), a.context_domain.to_dict(), "invalid_human_contract"),
      ("acceptance", ("peak_ceiling",), a.background_ceiling.to_dict(), "invalid_human_contract"),
      ("acceptance", ("max_response_duration",), bc.Duration(0).to_dict(), "invalid_measurement_contract"),
      ("shutdown", ("overrides_source_guard",), True, "invalid_human_contract"),
      ("shutdown", ("overrides_source_guard",), 0, "invalid_human_contract"),
      ("shutdown", ("actuator_support",), "implemented", "invalid_human_contract"),
      ("input_availability", ("implementation",), "validated", "invalid_human_contract"),
    ]
    for index, (kind, path, replacement, code) in enumerate(mutations):
        if code is not None: reject("contract/" + str(index) + "/" + kind, kind, values[kind], path, replacement, code)
    request_mutations = [
      ("behavior_request", ("contract", "product"), "different"),
      ("behavior_request", ("contract", "input_signal_id"), "missing"),
      ("behavior_request", ("contract", "predicate", "operator"), "<="),
      ("behavior_request", ("contract", "input_measurement", "observable", "compartment"), "undeclared"),
      ("behavior_request", ("contract", "goal_refinement", "basis"), "cited"),
      ("deployment_request", ("deployment", "target_fingerprint"), "0" * 64),
      ("deployment_request", ("deployment", "recipient_role"), "different"),
      ("deployment_request", ("deployment", "platform", "payload_format"), "DNA"),
      ("deployment_request", ("deployment", "intended_population", "description"), "Different population."),
      ("deployment_request", ("deployment", "intracellular_destination"), "undeclared"),
      ("acceptance_request", ("acceptance", "behavior_fingerprint"), "0" * 64),
      ("acceptance_request", ("acceptance", "healthy_measurement", "observable", "id"), acceptance.behavior_request.contract.input_measurement.observable.id),
      ("acceptance_request", ("acceptance", "healthy_measurement", "observable", "role"), "other_role"),
      ("acceptance_request", ("acceptance", "input_availability", "response_delay"), bc.Duration(16).to_dict()),
      ("acceptance_request", ("acceptance", "shutdown", "response_delay"), bc.Duration(16).to_dict()),
    ]
    for index, (kind, path, replacement) in enumerate(request_mutations):
        code = "invalid_target_claim" if path[-1] == "basis" else "invalid_human_request"
        reject("request/" + str(index) + "/" + kind, kind, values[kind], path, replacement, code, "record" if code == "invalid_target_claim" else "wrapper")
    reject("request/empty_contract", "behavior_request", behavior, ("contract",), {}, "missing_field")
    # Mutants remain valid complete BuildRequests, isolating wrapper/source checks.
    source_mutations = [
        ("role_engineering", "role", ("attributes", "engineering"), "ex_vivo"),
        ("scope_kind", "scope", ("attributes", "scope"), "local"),
        ("signal_scope", "signal", ("attributes", "scope"), "local"),
        ("signal_type", "signal", ("data_type",), scalar_type),
        ("rule_trigger", "rule", ("attributes", "trigger"), "event"),
        ("rule_execution", "rule", ("attributes", "execution"), "sequential"),
        ("rule_priority", "rule", ("attributes", "priority"), 1),
        ("ongoing_boolean", "action.secrete", ("attributes", "ongoing"), 1),
        ("secretion_rate", "action.secrete", ("attributes", "rate"), "explicit"),
        ("secretion_product", "secretion", ("attributes", "product"), "different"),
    ]
    for identity, node_kind, path, replacement in source_mutations:
        data = behavior.to_dict()
        nodes = data["build_request"]["intent"]["nodes"]
        index = next(i for i, node in enumerate(nodes) if node["kind"] == node_kind)
        data = changed(data, ("build_request", "intent", "nodes", index, *path), replacement)
        bc.BuildRequest.from_dict(data["build_request"])
        reject("source/" + identity, "behavior_request", data, ("contract", "product"), data["contract"]["product"], "invalid_human_request", "wrapper")
    data = behavior.to_dict()
    extra = deepcopy(next(node for node in data["build_request"]["intent"]["nodes"] if node["kind"] == "goal"))
    extra["id"] = "unused_goal"
    data["build_request"]["intent"]["nodes"].append(extra)
    bc.BuildRequest.from_dict(data["build_request"])
    reject("source/unused_goal", "behavior_request", data, ("contract", "product"), data["contract"]["product"], "invalid_human_request", "wrapper")
    data = behavior.to_dict(); data["build_request"]["intent"]["roots"].append(c.input_signal_id)
    bc.BuildRequest.from_dict(data["build_request"])
    reject("source/extra_root", "behavior_request", data, ("contract", "product"), data["contract"]["product"], "invalid_human_request", "wrapper")
    for source in (bounded, acceptance):
        reject("circuit/stale_deployment/" + source_kind(source), "circuit", circuit(source), ("deployment_id",), "different", "invalid_circuit_record", "circuit")
    # Structurally valid nested claims with unknown evidence must fail source binding.
    data = behavior.to_dict(); data["contract"]["goal_refinement"].update(basis="cited", evidence_ids=["missing"])
    reject("request/unknown_evidence", "behavior_request", data, ("contract", "goal_refinement", "description"), "Cited fixture.", "invalid_human_request", "wrapper")
    document = dict(schema_version=SCHEMA, claim_scope="Typed structural human source import and declared correspondence only; assessment, actuators, empirical evidence and human admission remain unimplemented.",
        source_coordinate_policy={"file": "fixtures/human_wrappers.py", "line": 11, "function": "artificial_human_source", "applied": "before wrapper reconstruction; semantic identities unchanged"},
        records=records, rejections=rejections, literal_expectations=literals)
    document["coverage"] = dict(kinds=sorted({item["kind"] for item in records}), positive_count=len(records),
        rejection_count=len(rejections), independent_literal_count=len(literals), wrapper_kinds=sorted(WRAPPERS))
    return document


def check_corpus(document):
    require(document["schema_version"] == SCHEMA, "Wrong wrapper corpus schema")
    require(document["coverage"]["kinds"] == sorted(PARSERS), "Missing structural record family")
    require(document["coverage"]["positive_count"] == len(document["records"]), "Positive census drift")
    require(document["coverage"]["rejection_count"] == len(document["rejections"]), "Rejection census drift")
    ids = [item["id"] for item in document["records"] + document["rejections"]]
    require(len(ids) == len(set(ids)), "Duplicate fixture identity")
    for item in document["records"]:
        value = PARSERS[item["kind"]].from_dict(item["input"])
        require(encoded(value.to_dict()) == encoded(item["normalized"]), "Normalized authority drift: " + item["id"])
        require(value.fingerprint == item["fingerprint"] and fingerprint(value.to_dict()) == item["artifact_fingerprint"], "Authority identity drift: " + item["id"])
        if item["kind"] in WRAPPERS: require(evidence_paths(value) == item["unresolved_evidence"], "Evidence obligations drift")
    for item in document["rejections"]:
        try: PARSERS[item["kind"]].from_dict(item["input"])
        except (TypeError, ValueError) as error:
            require(type(error).__name__ == item["python_exception"] and str(error) == item["python_error"], "Rejection reason drift: " + item["id"])
        else: raise AssertionError("Intended rejection accepted: " + item["id"])
    by_id = {item["id"]: item for item in document["records"]}
    require({item["id"] for item in document["literal_expectations"]} == {"literal/cited_claim", "literal/observable", "literal/response", "literal/shutdown"}, "Missing independent literal")
    for literal in document["literal_expectations"]:
        require(encoded(literal["normalized"]) == encoded(by_id[literal["id"]]["normalized"]), "Independent literal drift")
    pending = [(document, 0)]; count = deepest = 0
    while pending:
        value, depth = pending.pop(); count += 1; deepest = max(deepest, depth)
        if isinstance(value, dict): pending.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, list): pending.extend((item, depth + 1) for item in value)
    require(count <= 250_000 and deepest <= 128 and len(encoded(document)) <= 16 * 1024 * 1024, "Corpus exceeds native read bound")
    return {"bytes": len(encoded(document)), "values": count, "depth": deepest}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=CORPUS)
    args = parser.parse_args(argv)
    corpus = build_corpus(); usage = check_corpus(corpus); data = encoded(corpus)
    if args.write:
        args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_bytes(data)
    else: require(args.output.read_bytes() == data, "Retained human-wrapper corpus drift")
    print(json.dumps({"status": "pass", **corpus["coverage"], **usage}, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
