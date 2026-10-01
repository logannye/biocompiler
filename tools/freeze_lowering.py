"""Retain exact Python lowerer outputs for the independent native producer.

The caller selects the Python installation. This tool neither imports nor runs
native compiler code. All new source examples are artificial language fixtures.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import biocompiler as bc
from biocompiler.compiler.behavior import lower_to_behavior, verify_lowering
from biocompiler.compiler.request import BuildRequest
from biocompiler.ir.behavior import BEHAVIOR_V2, SCHEMA_VERSION as V1, SUPPORTED_KINDS, EXTENSION_KINDS
from biocompiler.ir.intent import IntentProgram, SourceLocation
from biocompiler.ir.serialization import fingerprint


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/conformance/lowering-v1.json"
SCHEMA = "biocompiler.lowering_conformance.v1"
LOCATION = SourceLocation("fixtures/lowering.py", 7, "artificial_source")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def located(intent):
    return replace(intent, nodes=tuple(replace(node, source=LOCATION) for node in intent.nodes))


def frozen(therapy_or_intent, *, profile=V1, parameters=None, constraints=None):
    intent = (therapy_or_intent.freeze() if isinstance(therapy_or_intent, bc.Therapy) else therapy_or_intent)
    return BuildRequest.freeze(located(intent), parameters=parameters, behavior_profile=profile,
                               implementation_constraints=constraints or {})


def model(name):
    therapy = bc.Therapy("artificial_lowering_" + name)
    return therapy, therapy.engineer("observer", cell_type="human_T_cell")


def temporal(kind, *, parameter=False):
    therapy, cells = model(kind)
    observed = cells.environment.signal("context").present()
    wait = therapy.parameter("wait", type=bc.Duration, default=bc.Duration(2)) if parameter else bc.Duration(2)
    if kind == "held_for":
        cells.when(observed.held_for(wait)).do(cells.report("ready"))
    elif kind == "recently":
        cells.when(observed.recently(within=wait)).do(cells.report("ready"))
    elif kind == "followed_by":
        second = cells.external.signal("second").present().became_true()
        cells.on(observed.became_true().followed_by(second, within=wait)).do(cells.report("ready"))
    elif kind == "action.pulse":
        cells.on(observed.became_true()).do(cells.rest().for_(wait))
    elif kind == "memory":
        memory = cells.memory("seen", set_when=observed, duration=wait)
        cells.when(memory.is_set()).do(cells.report("ready"))
    elif kind == "integrated":
        signal = cells.environment.signal("amount")
        cells.when(signal.integrated(over=wait) > signal * wait).do(cells.rest())
    else:
        raise AssertionError(kind)
    options = dict(profile=BEHAVIOR_V2, constraints={"execution": {"integral_step": bc.Duration(1).to_dict()}}) if kind == "integrated" else {}
    return frozen(therapy, **options)


def changed_source(request, change):
    raw = request.intent.to_dict()
    change(raw)
    return BuildRequest.freeze(IntentProgram.from_dict(raw), behavior_profile=request.behavior_profile,
        implementation_constraints=request.implementation_constraints, preferences=request.preferences)


def first(raw, kind):
    return next(node for node in raw["nodes"] if node["kind"] == kind)


def parameter_literal(value, *, scalar_type=None):
    dtype = {"kind": "scalar", "name": "Level", "dimensions": {}, "arguments": []} if scalar_type is None else scalar_type
    binding = {"kind": "scalar", "value": value, "canonical_value": value, "unit": "1", "type": deepcopy(dtype)}
    node = {"id": "parameter", "kind": "parameter", "inputs": [],
            "attributes": {"name": "amount", "bound": True, "default": binding},
            "data_type": deepcopy(dtype), "role": None, "source": LOCATION.to_dict()}
    source = IntentProgram.from_dict({"schema_version": "biocompiler.intent.v0.1", "name": "literal_parameter",
                                     "nodes": [node], "roots": ["parameter"]})
    request = BuildRequest.freeze(source)
    return request, node


def rule_literal(*, event, policies):
    """Independent explicit graph/lineage/output for both policy rewrites."""
    level = {"kind": "scalar", "name": "Level", "dimensions": {}, "arguments": []}
    condition = {"kind": "condition", "name": "Condition", "dimensions": {}, "arguments": []}
    event_type = {"kind": "event", "name": "Event", "dimensions": {}, "arguments": []}

    def node(identity, kind, inputs, attrs, dtype=None, role="cell"):
        return dict(id=identity, kind=kind, inputs=inputs, attributes=attrs,
                    data_type=dtype, role=role, source=LOCATION.to_dict())

    nodes = [
        node("cell", "role", [], dict(name="cell", cell_type="human_T_cell", engineering="in_vivo"), role=None),
        node("environment", "scope", ["cell"], dict(name="environment", scope="environment")),
        node("signal", "signal", ["environment"], dict(name="context", scope="environment", observation="signal"), level),
        node("present", "qualitative", ["signal"], dict(band="present"), condition),
    ]
    lineages = dict(cell=["cell"], environment=["cell", "environment"],
                    signal=["cell", "environment", "signal"], present=["cell", "environment", "present", "signal"])
    if event:
        quantity = bc.Duration(2).to_dict()
        nodes += [
            node("edge", "became_true", ["present"], dict(initially_true_emits=True), event_type),
            node("rest", "action.rest", ["cell"], dict(ongoing=True)),
            node("duration", "literal", [], dict(value=quantity), quantity["type"], role=None),
            node("pulse", "action.pulse", ["rest", "duration"], dict(ongoing=True, retrigger="extend_from_latest_trigger")),
            node("rule", "rule", ["cell", "edge", "pulse"], dict(trigger="event", execution="concurrent",
                    priority="unspecified", ongoing_duration="explicit_or_design_choice")),
        ]
        lineages.update(edge=["cell", "edge", "environment", "present", "signal"], rest=["cell"],
                        duration=["duration"], pulse=["cell", "duration", "rest"])
        # Include each declaration itself explicitly, without consulting a
        # producer graph walker or the produced requirement declarations.
        lineages["rest"].append("rest")
        lineages["pulse"].append("pulse")
        lineages["pulse"].sort()
        lineages["rule"] = ["cell", "duration", "edge", "environment", "present", "pulse", "rest", "rule", "signal"]
        roots = ["cell", "rule"]
        required = [("rule", "rule")]
    else:
        nodes += [
            node("phase", "state", ["cell"], dict(name="phase", values=[False, 0], initial=False,
                  observation="prior_state", arbitration="unspecified")),
            node("assign", "action.state_set", ["phase"], dict(value=0, idempotent=True, ongoing=False)),
            node("rule", "rule", ["cell", "present", "assign"], dict(trigger="condition", execution="concurrent", priority="unspecified")),
        ]
        lineages.update(phase=["cell", "phase"], assign=["assign", "cell", "phase"],
                        rule=["assign", "cell", "environment", "phase", "present", "rule", "signal"])
        roots = ["cell", "phase", "rule"]
        required = [("phase", "state"), ("rule", "rule")]
    raw = dict(schema_version="biocompiler.intent.v0.1", name="literal_event" if event else "literal_state_rule",
               nodes=nodes, roots=roots)
    request = BuildRequest.freeze(IntentProgram.from_dict(raw))
    output_nodes = deepcopy(nodes)
    for item in output_nodes:
        item["contact_bound"] = False
        item["requirement_ids"] = ["requirement:" + identity for identity, _ in required if item["id"] in lineages[identity]]
        if item["id"] == "phase":
            item["attributes"].update(observation="shared_pre_update_state", arbitration="coalesce_identical_else_error")
        if item["id"] == "rule":
            item["attributes"] = (dict(trigger="event", execution="concurrent", priority="none", ongoing_duration="explicit",
                 ongoing_activation="explicit_duration", impulse_activation="event", state_assignment="event") if event else
                dict(trigger="condition", execution="concurrent", priority="none", ongoing_activation="level",
                     impulse_activation="onset", state_assignment="level"))
    expected = dict(schema_version=V1, name=raw["name"], nodes=output_nodes, roots=roots,
        source_fingerprint=request.intent.fingerprint, requirements=[
            dict(id="requirement:" + identity, kind=kind, source_node_id=identity,
                 lineage=lineages[identity], source=LOCATION.to_dict()) for identity, kind in required],
        source_links=lineages, policies=policies, parameter_bindings={})
    return request, expected


def build_corpus():
    cases, rejections, literals = [], [], []

    def add(identity, request, *, retained=None):
        request = BuildRequest.from_dict(request.to_dict())
        behavior = lower_to_behavior(request)
        require(verify_lowering(request, behavior).passed, "Generated candidate failed independent Python correspondence")
        raw = behavior.to_dict()
        item = dict(id=identity, request=request.to_dict(), expected_behavior=raw,
                    request_fingerprint=request.fingerprint, request_artifact_fingerprint=request.artifact_fingerprint,
                    behavior_fingerprint=behavior.fingerprint, behavior_artifact_fingerprint=fingerprint(raw))
        if retained is not None:
            exact = encoded(raw) == encoded(retained["behavior"])
            require(exact == (retained["id"] != "numeric_policy_equality"), "Unexpected retained producer-output variance")
            item["prior_checker_candidate"] = {
                "id": retained["id"], "artifact_fingerprint": retained["behavior_artifact_fingerprint"],
                "exact_producer_bytes": exact,
                "relation": "exact" if exact else "numeric_policy_mapping_equivalence_only",
            }
        cases.append(item)
        return behavior

    def reject(identity, request, code, *, stage="lowering"):
        raw = request.to_dict() if isinstance(request, BuildRequest) else request
        if stage == "lowering":
            authority = BuildRequest.from_dict(raw)
        try:
            if stage == "request":
                BuildRequest.from_dict(raw)
            else:
                lower_to_behavior(authority)
        except (bc.UnsupportedBehaviorError, bc.SerializationError, bc.TypeMismatchError) as error:
            detail = str(error)
            source = getattr(error, "source", None)
            node_id = getattr(error, "node_id", None)
            category = type(error).__name__
        else:
            raise AssertionError("Python accepted intended lowerer rejection " + identity)
        rejections.append(dict(id=identity, request=raw, expected_stage=stage, expected_code=code,
            expected_outcome="unsupported" if code.startswith("unsupported_") else "invalid",
            python_error=detail, python_error_category=category, source_node_id=node_id,
            source_location=source.to_dict() if source else None))

    previous = json.loads((ROOT / "tests/conformance/request-domains-v1.json").read_bytes())["lowering_cases"]
    originals = {}
    for item in previous:
        request = BuildRequest.from_dict(item["request"])
        originals[item["id"]] = request
        add("retained/" + item["id"], request, retained=item)
    basic = temporal("held_for", parameter=True)
    add("parameters/default_duration", basic)
    add("parameters/explicit_override", BuildRequest.freeze(basic.intent, parameters={"wait": bc.Duration(3)}))
    add("parameters/override_units", BuildRequest.freeze(basic.intent, parameters={"wait": bc.Duration(2000, unit="ms")}))
    shuffled = replace(basic.intent, nodes=tuple(reversed(basic.intent.nodes)), roots=tuple(reversed(basic.intent.roots)))
    add("ordering/non_topological_declarations", BuildRequest.freeze(shuffled))
    arithmetic = changed_source(basic, lambda raw: None)
    raw = arithmetic.intent.to_dict()
    parameter = first(raw, "parameter")
    extra = deepcopy(parameter)
    extra.update(id="duration_sum", kind="add", inputs=[parameter["id"], parameter["id"]], attributes={})
    first(raw, "held_for")["inputs"][1] = extra["id"]
    raw["nodes"].append(extra)
    add("parameters/arithmetic_constant_duration", BuildRequest.freeze(IntentProgram.from_dict(raw)))
    for name, value, dtype in (("integer", 1, None), ("float", 1.0, None), ("signed_zero", -0.0, None),
                              ("optional_type_fields", 2, {"kind": "scalar", "name": "Level"})):
        request, source_node = parameter_literal(value, scalar_type=dtype)
        behavior = add("literal/" + name, request)
        node = deepcopy(source_node)
        node.update(contact_bound=False, requirement_ids=[])
        # Closed policy literal is separate retained specification data, while
        # this complete graph/binding expectation is manually assembled.
        policy_literal = json.loads((ROOT / "tests/conformance/behavior-domains-v1.json").read_bytes())["cases"][0]["behavior"]["policies"]
        expected = dict(schema_version=V1, name="literal_parameter", nodes=[node], roots=["parameter"],
            source_fingerprint=request.intent.fingerprint, requirements=[],
            source_links={"parameter": ["parameter"]}, policies=policy_literal,
            parameter_bindings={"amount": deepcopy(source_node["attributes"]["default"])})
        require(encoded(expected) == encoded(behavior.to_dict()), "Independent parameter literal differs")
        literals.append(dict(case_id="literal/" + name, expected_behavior=expected))
    for event in (False, True):
        name = "literal/event_pulse" if event else "literal/typed_state_and_condition_rule"
        request, expected = rule_literal(event=event, policies=policy_literal)
        actual = add(name, request)
        require(encoded(expected) == encoded(actual.to_dict()), "Independent state/rule literal differs")
        literals.append(dict(case_id=name, expected_behavior=expected))

    for kind in ("held_for", "recently", "followed_by", "action.pulse", "memory", "integrated"):
        request = temporal(kind)
        add("temporal/" + kind, request)

        def dynamic(raw, kind=kind):
            node = first(raw, kind)
            index = node["attributes"]["input_names"].index("duration") if kind == "memory" else 2 if kind == "followed_by" else 1
            duration_id = node["inputs"][index]
            duration = next(item for item in raw["nodes"] if item["id"] == duration_id)
            scope = next(item for item in raw["nodes"] if item["kind"] == "scope" and item["attributes"]["scope"] == "environment")
            duration.update(kind="signal", inputs=[scope["id"]], role=scope["role"],
                            attributes={"name": "dynamic_duration", "scope": "environment", "observation": "signal"})
        reject("duration/dynamic_" + kind, changed_source(request, dynamic), "unsupported_lowering_dynamic_duration")

    for name, value in (("zero", 0), ("negative", -2)):
        reject("duration/" + name, BuildRequest.freeze(basic.intent, parameters={"wait": bc.Duration(value)}), "behavior_duration")
    for value_kind, value in (("interval", bc.Interval(1, 2)),
                              ("curve", bc.Curve(points=[(0, 1), (1, 2)], input=bc.Level, output=bc.Level))):
        therapy = bc.Therapy("artificial_lowering_" + value_kind)
        therapy.parameter("unsupported", type=value.dtype, default=value)
        reject("value/" + value_kind, frozen(therapy), "unsupported_lowering_value_kind")
    reject("operation/unknown_nonroot", changed_source(basic, lambda raw: raw["nodes"].append(
        dict(id="future", kind="future.operation", inputs=[], attributes={}, data_type=None, role=None, source=LOCATION.to_dict()))),
        "unsupported_lowering_operation")
    integrated = temporal("integrated")
    reject("profile/extensions_under_v1", BuildRequest.freeze(integrated.intent), "unsupported_lowering_operation")
    reject("integration/missing_step", BuildRequest.freeze(integrated.intent, behavior_profile=BEHAVIOR_V2),
           "unsupported_lowering_integral_step")
    reject("integration/unknown_execution_field", BuildRequest.freeze(integrated.intent, behavior_profile=BEHAVIOR_V2,
           implementation_constraints={"execution": {"future": True}}), "invalid_lowering_execution_policy")
    reject("integration/non_object_policy", BuildRequest.freeze(integrated.intent, behavior_profile=BEHAVIOR_V2,
           implementation_constraints={"execution": []}), "invalid_lowering_execution_policy")
    reject("integration/nonpositive_step", BuildRequest.freeze(integrated.intent, behavior_profile=BEHAVIOR_V2,
           implementation_constraints={"execution": {"integral_step": bc.Duration(0).to_dict()}}), "invalid_lowering_execution_policy")
    reject("integration/nondirect_observation", changed_source(integrated, lambda raw:
           first(raw, "integrated")["inputs"].__setitem__(0, first(raw, "multiply")["id"])), "unsupported_lowering_integration")

    def contact(raw):
        observation = next(node for node in raw["nodes"] if node["id"] == first(raw, "integrated")["inputs"][0])
        scope = next(node for node in raw["nodes"] if node["id"] == observation["inputs"][0])
        scope["attributes"].update(name="contact", scope="contact")
        observation["attributes"]["scope"] = "contact"
    reject("integration/contact", changed_source(integrated, contact), "unsupported_lowering_integration")
    stateful = originals["actions_state_signature_v1"]
    reject("state/unknown_read_policy", changed_source(stateful, lambda raw:
           first(raw, "state")["attributes"].update(observation="future")), "unsupported_lowering_state_policy")
    reject("state/unknown_arbitration", changed_source(stateful, lambda raw:
           first(raw, "state")["attributes"].update(arbitration="last_writer")), "unsupported_lowering_state_policy")
    for name, attrs in (("priority", {"priority": "first"}), ("execution", {"execution": "serial"}),
                        ("trigger", {"trigger": "future"}), ("extra", {"future": True})):
        reject("rule/" + name, changed_source(basic, lambda raw, attrs=attrs:
               first(raw, "rule")["attributes"].update(attrs)), "unsupported_lowering_rule_policy")
    pulse = temporal("action.pulse")
    reject("event/unknown_duration", changed_source(pulse, lambda raw:
           first(raw, "rule")["attributes"].update(ongoing_duration="future")), "unsupported_lowering_event_duration")
    reject("event/ongoing_without_pulse", changed_source(pulse, lambda raw:
           first(raw, "rule")["inputs"].__setitem__(2, first(raw, "action.pulse")["inputs"][0])),
           "unsupported_lowering_event_duration")

    def nested(raw):
        original = first(raw, "action.pulse")
        added = deepcopy(original)
        added.update(id="nested_pulse", inputs=[original["id"], original["inputs"][1]])
        raw["nodes"].append(added)
    reject("event/nested_pulse", changed_source(pulse, nested), "unsupported_lowering_nested_pulse")
    reject("invalid/qualitative_band", changed_source(basic, lambda raw:
           first(raw, "qualitative")["attributes"].update(band="invented")), "behavior_operation")
    reject("invalid/missing_roots", changed_source(basic, lambda raw: raw.update(roots=[])), "behavior_roots")
    bad = basic.to_dict()
    bad["resolved_bindings"]["wait"] = bc.Duration(7).to_dict()
    reject("request/forged_binding_manifest", bad, "resolved_bindings_mismatch", stage="request")
    bad = basic.to_dict()
    bad["explicit_overrides"]["undeclared"] = bc.Duration(7).to_dict()
    reject("request/unknown_parameter", bad, "unknown_parameter", stage="request")
    bad = basic.to_dict()
    parameter = first(bad["intent"], "parameter")
    parameter["attributes"].pop("default")
    parameter["attributes"]["bound"] = False
    reject("request/unbound_parameter", bad, "unbound_parameter", stage="request")

    by_profile = defaultdict(set)
    for case in cases:
        by_profile[case["expected_behavior"]["schema_version"]].update(node["kind"] for node in case["expected_behavior"]["nodes"])
    all_kinds = set().union(*by_profile.values())
    return dict(schema_version=SCHEMA, authority="current_python_producer_oracle",
        claim_scope="Exact frozen-request Behavior production only; no execution, molecular realization or empirical acceptance.",
        source_coordinate_policy="Retained authorities unchanged; new sources standardized before freezing and lowering.",
        cases=cases, rejections=rejections, literal_expectations=literals,
        coverage=dict(positive_count=len(cases), rejection_count=len(rejections), retained_request_count=len(previous),
            independent_literal_count=len(literals), supported_kinds=sorted(SUPPORTED_KINDS), extension_kinds=sorted(EXTENSION_KINDS),
            covered_kinds=sorted(all_kinds), uncovered_kinds=sorted((SUPPORTED_KINDS | EXTENSION_KINDS) - all_kinds),
            by_profile={key: sorted(value) for key, value in sorted(by_profile.items())},
            rejection_codes=dict(sorted(Counter(item["expected_code"] for item in rejections).items()))))


def check_corpus(document):
    require(document["schema_version"] == SCHEMA, "Wrong lowering corpus schema")
    ids = [item["id"] for item in document["cases"] + document["rejections"]]
    require(len(ids) == len(set(ids)), "Duplicate lowering case identity")
    require(len(document["cases"]) >= 31 and len(document["rejections"]) >= 32, "Incomplete lowering corpus")
    require(not document["coverage"]["uncovered_kinds"], "Missing supported lowering operations")
    profiles = defaultdict(set)
    for item in document["cases"]:
        profiles[item["expected_behavior"]["schema_version"]].update(node["kind"] for node in item["expected_behavior"]["nodes"])
    observed = set().union(*profiles.values())
    expected_coverage = dict(
        positive_count=len(document["cases"]), rejection_count=len(document["rejections"]),
        retained_request_count=sum("prior_checker_candidate" in item for item in document["cases"]),
        independent_literal_count=len(document["literal_expectations"]), supported_kinds=sorted(SUPPORTED_KINDS),
        extension_kinds=sorted(EXTENSION_KINDS), covered_kinds=sorted(observed),
        uncovered_kinds=sorted((SUPPORTED_KINDS | EXTENSION_KINDS) - observed),
        by_profile={key: sorted(value) for key, value in sorted(profiles.items())},
        rejection_codes=dict(sorted(Counter(item["expected_code"] for item in document["rejections"]).items())))
    require(document["coverage"] == expected_coverage, "Stale lowering coverage census")
    for item in document["cases"]:
        request = BuildRequest.from_dict(item["request"])
        result = lower_to_behavior(request)
        require(encoded(result.to_dict()) == encoded(item["expected_behavior"]), "Wrong exact producer output")
        for key, expected in (("request_fingerprint", request.fingerprint),
                              ("request_artifact_fingerprint", request.artifact_fingerprint),
                              ("behavior_fingerprint", result.fingerprint),
                              ("behavior_artifact_fingerprint", fingerprint(result.to_dict()))):
            require(item[key] == expected, "Wrong lowering identity " + key)
        require(verify_lowering(request, result).passed, "Independent correspondence failed")
    for item in document["rejections"]:
        if item["expected_stage"] == "lowering":
            request = BuildRequest.from_dict(item["request"])
        try:
            if item["expected_stage"] == "request":
                BuildRequest.from_dict(item["request"])
            else:
                lower_to_behavior(request)
        except (bc.UnsupportedBehaviorError, bc.SerializationError, bc.TypeMismatchError) as error:
            require(type(error).__name__ == item["python_error_category"] and str(error) == item["python_error"],
                    "Wrong intended Python producer rejection")
        else:
            raise AssertionError("Accepted negative lowering case")
    by_id = {item["id"]: item for item in document["cases"]}
    for literal in document["literal_expectations"]:
        require(encoded(literal["expected_behavior"]) == encoded(by_id[literal["case_id"]]["expected_behavior"]),
                "Independent lowerer literal disagrees")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Deliberately replace the retained Python oracle.")
    parser.add_argument("--check", action="store_true", help="Require exact deterministic retained bytes (default).")
    args = parser.parse_args(argv)
    document = build_corpus()
    check_corpus(document)
    content = encoded(document)
    if args.write:
        CORPUS.parent.mkdir(parents=True, exist_ok=True)
        CORPUS.write_bytes(content)
    else:
        require(CORPUS.read_bytes() == content, "Lowering corpus drifted; inspect before --write")
    print(json.dumps({"schema": SCHEMA, "positive": len(document["cases"]),
                      "rejected": len(document["rejections"]), "bytes": len(content)}, sort_keys=True))


if __name__ == "__main__":
    main()
