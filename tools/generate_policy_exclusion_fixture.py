"""Freeze a separately authored mutual-exclusion policy, without executing it.

Selection flags describe finite policy state. Exclusion neither cancels an
existing product attempt nor asserts that any previously produced effect stops.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

from biocompiler import policy as p

VERSION = "biocompiler.policy_exclusion_source_literals.v0.1"
PRODUCT = "fixture.product.alpha"
HORIZON = 6


def build_request() -> p.BuildRequest:
    definitions = (
        p.SemanticDefinition("exclusion.interface", "1", "interface", "Abstract executor input."),
        p.SemanticDefinition("exclusion.encounter", "1", "encounter", "Explicit encounter identity."),
        p.SemanticDefinition("exclusion.observation", "1", "observation", "Exact timestamped evidence.", result=p.TRUTH),
        p.SemanticDefinition("exclusion.effect", "1", "operation", "Request an abstract named product; no molecular implementation.", parameters=(p.Parameter("product", p.TEXT),)),
        p.SemanticDefinition("exclusion.lifecycle", "1", "lifecycle", "Correlated bounded feedback; selection flags do not cancel attempts."),
        p.SemanticDefinition("exclusion.chassis", "1", "model", "Declared human immune context; executable binding pending."),
        p.SemanticDefinition("exclusion.environment", "1", "environment", "Declared in-vivo context; executable domain pending."),
        p.SemanticDefinition("exclusion.delivery", "1", "delivery", "Declared arrival, expression and activation interfaces; binding pending."),
    )
    refs = {definition.id.split(".")[-1]: definition.ref for definition in definitions}
    builder = p.ProgramBuilder("exclusion_source_literal", semantics=p.SemanticBundle("exclusion.semantics", "1", definitions))
    executor = builder.executor("executor", requires=(refs["interface"],))
    encounter = builder.encounter("encounter", executor=executor, contract=refs["encounter"], termination="explicit_event")
    clock = builder.clock("clock", basis="availability", resolution=p.quantity(1, p.SECOND))
    observation = builder.observe("condition", observer=executor, subject=encounter.target, value_type=p.TRUTH,
        contract=refs["observation"], clock=clock, access="cell", coverage="event", coherence="frame", freshness=p.quantity(2, p.SECOND))
    scope = p.Scope("encounter", p.ref(encounter))
    selected = builder.state(p.StateStore("selected", p.TRUTH, scope, False, 2, "reject", "encounter", None, "not_applicable"))
    excluded = builder.state(p.StateStore("excluded", p.TRUTH, scope, False, 2, "reject", "encounter", None, "not_applicable"))
    product = builder.add(p.Parameter("product", p.TEXT, PRODUCT))
    effect = builder.effect("response", executor=executor, subject=encounter.target, contract=refs["effect"],
        lifecycle=p.EffectLifecycle("continuous", "continue", "defer", "unsupported", "feedback", "feedback", refs["lifecycle"], p.quantity(2, p.SECOND)),
        parameters=(p.Argument("product", p.Expr("parameter", p.TEXT, ref=p.ref(product))),))
    arbitration = p.Arbitration("exclusive", "reject", "reject", "forbidden", "none")
    builder.rule("select", executor=executor, on=p.rising(observation.expression), when=observation.expression,
        unknown="defer", effects=(p.ref(effect),), assignments=(p.Assignment(p.ref(selected), p.TRUE), p.Assignment(p.ref(excluded), p.FALSE)), arbitration=arbitration)
    builder.rule("exclude", executor=executor, on=p.rising(p.not_(observation.expression)), when=p.not_(observation.expression),
        unknown="defer", effects=(), assignments=(p.Assignment(p.ref(selected), p.FALSE), p.Assignment(p.ref(excluded), p.TRUE)), arbitration=arbitration)
    builder.require(p.Requirement("request_progress", "progress", "An uncontested observed rising condition requests the product within one tick.", scope,
        condition=p.TRUE, response=effect.event("requested"), deadline=p.quantity(1, p.SECOND), horizon=p.quantity(HORIZON, p.SECOND),
        trigger=p.rising(observation.expression), clock=p.ref(clock)))
    builder.require(p.Requirement("initiation_progress", "progress", "Each request initiates its own correlated attempt within one tick.", scope,
        condition=p.TRUE, response=effect.event("initiated"), deadline=p.quantity(1, p.SECOND), horizon=p.quantity(HORIZON, p.SECOND),
        trigger=effect.event("requested"), clock=p.ref(clock)))
    builder.require(p.Requirement("exclusive_selection", "safety", "The encounter's selected and excluded flags are never both true at a settled tick.", scope,
        condition=p.not_(p.all_of(selected.expression, excluded.expression)), horizon=p.quantity(HORIZON, p.SECOND)))
    program = builder.freeze()
    program = replace(program, source_map=tuple(p.SourceSpan(item.id, "policy_exclusion_source_literal.py", index + 1)
                                               for index, item in enumerate(program.declarations)))
    chassis = p.ChassisProfile("exclusion.human_immune", "1", "abstract_immune", "supplied_profile", ("declared",), ("declared",),
        (refs["interface"],), refs["chassis"], (refs["environment"],), (refs["interface"],))
    delivery = p.DeliveryContract("delivery", (p.ref(executor),), refs["delivery"], refs["delivery"], refs["delivery"], "none_required", refs["delivery"])
    deployment = p.Deployment("deployment", (p.RoleBinding(p.ref(executor), chassis),), (refs["environment"],), delivery,
        p.RNAConstraints(design_count=1, member_count=1, helper_count=0, orf_count=1, product_count=1))
    return p.BuildRequest(program, deployment, p.ImplementationCatalogLock("exclusion.pending_implementations", "1"),
        p.AssuranceRequest(("request_progress", "initiation_progress", "exclusive_selection"), "bounded", p.quantity(HORIZON, p.SECOND)))


def observation(identity: str, time: str, encounter: str, value: bool | None, status: str = "valid") -> dict:
    return {"id": identity, "available_at": time, "observed_at": time, "observer": "cell-1", "subject": "target-" + encounter[-1],
            "encounter": encounter, "observation": "condition", "status": status, "value": value}


def timelines() -> list[dict]:
    base = {"profile": "biocompiler.policy_timeline.v0.1", "executor": "cell-1", "horizon": "6",
        "encounters": [{"id": name, "declaration": "encounter", "target": target, "start": "0", "end": None, "resets": []}
                       for name, target in (("e1", "target-1"), ("e2", "target-2"))],
        "observations": [observation(identity, time, encounter, value) for identity, time, encounter, value in (
            ("e1-low", "0", "e1", False), ("e2-low", "0", "e2", False), ("e1-select", "1", "e1", True),
            ("e1-exclude", "2", "e1", False), ("e2-select", "2", "e2", True),
            ("e1-reselect", "3", "e1", True), ("e2-exclude", "3", "e2", False))],
        "feedback": [{"id": "first-failed", "available_at": "2", "executor": "cell-1", "subject": "target-1", "encounter": "e1",
                      "effect": "response", "attempt": "attempt/1", "outcome": "failed"}],
        "bounds": {"max_ticks": 100, "max_inputs": 100, "max_encounters": 2, "max_attempts": 8,
                   "max_work": 1000000, "max_trace_items": 10000, "max_microsteps": 100}}
    requests = [{"encounter": encounter, "subject": subject, "time": time, "product": PRODUCT}
                for encounter, subject, time in (("e1", "target-1", "1"), ("e2", "target-2", "2"), ("e1", "target-1", "3"))]
    states = [
        {"time": "0", "e1": {"selected": False, "excluded": False}, "e2": {"selected": False, "excluded": False}},
        {"time": "1", "e1": {"selected": True, "excluded": False}, "e2": {"selected": False, "excluded": False}},
        {"time": "2", "e1": {"selected": False, "excluded": True}, "e2": {"selected": True, "excluded": False}},
        {"time": "3", "e1": {"selected": True, "excluded": False}, "e2": {"selected": False, "excluded": True}},
        {"time": "6", "e1": {"selected": True, "excluded": False}, "e2": {"selected": False, "excluded": True}},
    ]
    result = []
    for identity in ("failure_and_timeouts", "exclusion_preserves_live_attempt", "invalid_after_selection"):
        timeline = deepcopy(base)
        if identity == "exclusion_preserves_live_attempt":
            timeline["feedback"] = []
        if identity == "invalid_after_selection":
            timeline["observations"] += [observation("e1-invalid", "4", "e1", None, "invalid"),
                                         observation("e2-conflicting", "4", "e2", None, "conflicting")]
        result.append({"id": identity, "timeline": timeline, "literal_expectations": {
            "status": "unvalidated_source_semantics_expectation", "requests": deepcopy(requests), "state_frames": deepcopy(states),
            "terminal_outcomes": ["timed_out" if identity == "exclusion_preserves_live_attempt" else "failed", "timed_out", "timed_out"],
            "requirements": {"request_progress": "pass", "initiation_progress": "pass", "exclusive_selection": "pass"},
            "active_at_two": ["attempt/1", "attempt/2"] if identity == "exclusion_preserves_live_attempt" else ["attempt/2"],
            "quiet_final_evidence_unknown": True}})
    for identity in ("missing_without_selection", "invalid_without_selection"):
        timeline = deepcopy(base)
        timeline["feedback"] = []
        timeline["observations"] = ([] if identity == "missing_without_selection" else
            [observation("e1-invalid", "0", "e1", None, "invalid"), observation("e2-invalid", "0", "e2", None, "invalid")])
        result.append({"id": identity, "timeline": timeline, "literal_expectations": {
            "status": "unvalidated_source_semantics_expectation", "requests": [], "terminal_outcomes": [], "active_at_two": [],
            "state_frames": [deepcopy(states[0]), {**deepcopy(states[0]), "time": "6"}],
            "requirements": {"request_progress": "unknown", "initiation_progress": "unknown", "exclusive_selection": "pass"},
            "quiet_final_evidence_unknown": True}})
    return result


def source_edits(document: dict) -> list[dict]:
    declarations = document["program"]["declarations"]
    positions = {value["id"]: index for index, value in enumerate(declarations)}
    select = declarations[positions["select"]]
    overlapping = {**declarations[positions["exclude"]], "on": deepcopy(select["on"]), "when": deepcopy(select["when"])}
    cases = (
        ("select_sets_both", ["program", "declarations", positions["select"], "assignments", 1, "value"], p.to_data(p.TRUE),
         {"kind": "requirement_failure", "id": "exclusive_selection", "status": "fail"}),
        ("exclude_sets_both", ["program", "declarations", positions["exclude"], "assignments", 0, "value"], p.to_data(p.TRUE),
         {"kind": "requirement_failure", "id": "exclusive_selection", "status": "fail"}),
        ("opposite_select_guard", ["program", "declarations", positions["select"], "when"], deepcopy(declarations[positions["exclude"]]["when"]),
         {"kind": "requirement_failure", "id": "request_progress", "status": "fail"}),
        ("simultaneous_opposed_writes", ["program", "declarations", positions["exclude"]], overlapping,
         {"kind": "execution_rejection", "diagnostic": "policy_execution_exclusive"}),
    )
    result = []
    for identity, path, after, expected in cases:
        changed = deepcopy(document)
        current = changed
        for part in path[:-1]:
            current = current[part]
        before = deepcopy(current[path[-1]])
        current[path[-1]] = deepcopy(after)
        result.append({"id": identity, "path": path, "before": before, "after": after, "document": changed,
                       "expected_authoring_status": "complete", "expected_native_result": expected, "native_validation": "not_performed"})
    return result


def fixture() -> dict:
    request = build_request()
    document = p.to_data(request)
    tags = ("capability.deferred.v1", "encounter.explicit.v1", "observation.external_evidence.v1", "effect.abstract_attempt.v1", "lifecycle.correlated_feedback.v1")
    return {"fixture_version": VERSION, "stage": "source_authority_only", "artifact": "withheld", "native_validation": "not_performed",
        "relation_to_original": "Separately authored state-exclusion property; policy_realization_source_v01 and its unknown scoped-memory histories remain unchanged.",
        "document": document, "definitions": {"schema_version": "biocompiler.policy_operational_definitions.v0.1", "profile": "biocompiler.policy_operational.v0.1",
            "definitions": [{"definition": p.to_data(definition.ref), "semantics": tag}
                            for definition, tag in zip(request.program.semantics.definitions[:5], tags)]},
        "timelines": timelines(), "source_edits": source_edits(document),
        "coverage_limits": ["Literal histories do not prove a whole operating domain; no unknown histories are excluded.",
                            "No-trigger histories retain per-timeline unknown progress; whole-domain aggregation is not implemented here.",
                            "Selected/excluded describe source state only; exclusion does not stop active attempts or remove products."],
        "pending_authorities": ["closed_executable_operating_domain", "independent_implementation_models", "implementation_and_material_catalog_entries",
                                "complete_mrna_template_roots_and_chemistry", "configuration_and_connection_material_bindings",
                                "native_preservation_and_requirement_assessments", "fresh_material_and_export_acceptance"]}


def encoded_fixture() -> str:
    return json.dumps(fixture(), sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = Path(__file__).resolve().parents[1] / "core/test/data/policy_exclusion_source_v01.json"
    text = encoded_fixture()
    if args.check:
        if path.read_text(encoding="utf-8") != text:
            raise SystemExit("Exclusion source witness differs; review independent literals before updating")
    else:
        path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
