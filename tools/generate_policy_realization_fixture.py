"""Freeze complete source-authority witnesses without executing policy semantics.

These are artificial software inputs. Implementation models, executable domain
and exact material authority are deliberately absent pending their own profiles.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

from biocompiler import policy as p

FIXTURE_VERSION = "biocompiler.policy_realization_source_literals.v0.1"
SOURCE_FILE = "policy_realization_source_literal.py"
PRODUCT = "fixture.product.alpha"


def semantic_bundle() -> p.SemanticBundle:
    return p.SemanticBundle("realization_fixture.semantics", "1", (
        p.SemanticDefinition("fixture.interface", "1", "interface", "Abstract executor input."),
        p.SemanticDefinition("fixture.encounter", "1", "encounter", "Explicit encounter identity."),
        p.SemanticDefinition("fixture.observation", "1", "observation", "Exact timestamped evidence.", result=p.TRUTH),
        p.SemanticDefinition("fixture.effect", "1", "operation", "Request an abstract named product; no molecular implementation.",
                             parameters=(p.Parameter("product", p.TEXT),)),
        p.SemanticDefinition("fixture.lifecycle", "1", "lifecycle", "Correlated bounded feedback."),
        p.SemanticDefinition("fixture.chassis", "1", "model", "Declared human immune context; executable binding pending."),
        p.SemanticDefinition("fixture.environment", "1", "environment", "Declared in-vivo context; executable domain pending."),
        p.SemanticDefinition("fixture.delivery", "1", "delivery", "Declared arrival, expression and activation interfaces; binding pending."),
    ))


def build_request() -> p.BuildRequest:
    definitions = semantic_bundle()
    refs = {item.id: item.ref for item in definitions.definitions}
    builder = p.ProgramBuilder("realization_source_literal", semantics=definitions)
    executor = builder.executor("executor", requires=(refs["fixture.interface"],))
    encounter = builder.encounter("encounter", executor=executor, contract=refs["fixture.encounter"], termination="explicit_event")
    clock = builder.clock("clock", basis="availability", resolution=p.quantity(1, p.SECOND))
    observation = builder.observe("condition", observer=executor, subject=encounter.target, value_type=p.TRUTH,
                                  contract=refs["fixture.observation"], clock=clock, access="cell", coverage="event",
                                  coherence="frame", freshness=p.quantity(2, p.SECOND))
    scope = p.Scope("encounter", p.ref(encounter))
    seen = builder.state(p.StateStore("seen", p.TRUTH, scope, False, 2, "reject", "encounter", None, "not_applicable"))
    product = builder.add(p.Parameter("product", p.TEXT, PRODUCT))
    effect = builder.effect("response", contract=refs["fixture.effect"], executor=executor, subject=encounter.target,
                            lifecycle=p.EffectLifecycle("continuous", "continue", "defer", "unsupported", "feedback", "feedback",
                                                        refs["fixture.lifecycle"], p.quantity(2, p.SECOND)),
                            parameters=(p.Argument("product", p.Expr("parameter", p.TEXT, ref=p.ref(product))),))
    builder.rule("respond", executor=executor, on=p.rising(observation.expression), when=observation.expression,
                 unknown="defer", effects=(p.ref(effect),), assignments=(p.Assignment(p.ref(seen), p.TRUE),),
                 arbitration=p.Arbitration("exclusive", "reject", "reject", "forbidden", "none"))
    builder.require(p.Requirement("request_progress", "progress", "An uncontested known rising observation requests the product within one tick.",
                                  scope, condition=p.TRUE, response=effect.event("requested"), deadline=p.quantity(1, p.SECOND),
                                  horizon=p.quantity(4, p.SECOND), trigger=p.rising(observation.expression), clock=p.ref(clock)))
    builder.require(p.Requirement("initiation_progress", "progress", "Each request initiates its own correlated attempt within one tick.",
                                  scope, condition=p.TRUE, response=effect.event("initiated"), deadline=p.quantity(1, p.SECOND),
                                  horizon=p.quantity(4, p.SECOND), trigger=effect.event("requested"), clock=p.ref(clock)))
    builder.require(p.Requirement("request_authorization", "progress", "Each request has known-true evidence by its one-tick deadline; same-tick authorization is a separate preservation obligation.",
                                  scope, condition=p.TRUE, response=observation.expression, deadline=p.quantity(1, p.SECOND),
                                  horizon=p.quantity(4, p.SECOND), trigger=effect.event("requested"), clock=p.ref(clock)))
    builder.require(p.Requirement("scoped_memory", "safety", "Known true evidence implies this encounter recorded its response at the settled tick.",
                                  scope, condition=p.any_of(p.not_(observation.expression), seen.expression),
                                  horizon=p.quantity(4, p.SECOND)))
    program = builder.freeze()
    # Stable fixture provenance, independent of this generator's physical path.
    program = replace(program, source_map=tuple(p.SourceSpan(item.id, SOURCE_FILE, index + 1)
                                               for index, item in enumerate(program.declarations)))
    chassis = p.ChassisProfile("fixture.human_immune", "1", "abstract_immune", "supplied_profile",
                               ("declared",), ("declared",), (refs["fixture.interface"],), refs["fixture.chassis"],
                               (refs["fixture.environment"],), (refs["fixture.interface"],))
    delivery = p.DeliveryContract("delivery", (p.ref(executor),), refs["fixture.delivery"], refs["fixture.delivery"],
                                  refs["fixture.delivery"], "none_required", refs["fixture.delivery"])
    deployment = p.Deployment("deployment", (p.RoleBinding(p.ref(executor), chassis),), (refs["fixture.environment"],),
                              delivery, p.RNAConstraints(design_count=1, member_count=1, helper_count=0, orf_count=1, product_count=1))
    return p.BuildRequest(program, deployment, p.ImplementationCatalogLock("pending_supplied_implementations", "1"),
                          p.AssuranceRequest(("request_progress", "initiation_progress", "request_authorization", "scoped_memory"),
                                             "bounded", p.quantity(4, p.SECOND)))


def timelines() -> list[dict]:
    # Independent literal schedules. No evaluator or producer supplies these.
    base = {
        "profile": "biocompiler.policy_timeline.v0.1", "executor": "cell-1", "horizon": "4",
        "encounters": [{"id": encounter, "declaration": "encounter", "target": subject,
                        "start": "0", "end": None, "resets": []}
                       for encounter, subject in (("e1", "target-1"), ("e2", "target-2"))],
        "observations": [
            {"id": identity, "available_at": time, "observed_at": time, "observer": "cell-1",
             "subject": subject, "encounter": encounter, "observation": "condition", "status": "valid", "value": value}
            for identity, time, encounter, subject, value in (
                ("e1-low", "0", "e1", "target-1", False), ("e2-low", "0", "e2", "target-2", False),
                ("e1-rise", "1", "e1", "target-1", True), ("e2-rise", "2", "e2", "target-2", True))],
        "feedback": [],
        "bounds": {"max_ticks": 100, "max_inputs": 100, "max_encounters": 2, "max_attempts": 8,
                   "max_work": 1000000, "max_trace_items": 10000, "max_microsteps": 100},
    }
    result = []
    for name, outcome in (("completion_and_timeout", "completed"), ("failure_and_timeout", "failed"), ("both_timeout", None)):
        timeline = deepcopy(base)
        if outcome is not None:
            timeline["feedback"] = [{"id": "feedback-1", "available_at": "2", "executor": "cell-1", "subject": "target-1",
                                     "encounter": "e1", "effect": "response", "attempt": "attempt/1", "outcome": outcome}]
        result.append({"id": name, "timeline": timeline,
                       "literal_expectations": {"status": "unvalidated_source_semantics_expectation",
                           "requests": [{"encounter": "e1", "subject": "target-1", "time": "1", "product": PRODUCT},
                                        {"encounter": "e2", "subject": "target-2", "time": "2", "product": PRODUCT}],
                           "initiations": ["1", "2"], "terminal_outcomes": [outcome or "timed_out", "timed_out"],
                           "settled_memory_at_one": {"e1": True, "e2": False},
                           "authorization_closed_at": ["1", "2"],
                           "requirements": {"request_progress": "pass", "initiation_progress": "pass",
                                            "request_authorization": "pass", "scoped_memory": "pass"}}})
    for name, status in (("stale_before_response", "valid"), ("invalid_before_response", "invalid")):
        timeline = deepcopy(base)
        timeline["observations"] = [{**row, "status": status, "value": False if status == "valid" else None}
                                    for row in timeline["observations"][:2]]
        result.append({"id": name, "timeline": timeline,
                       "literal_expectations": {"status": "unvalidated_source_semantics_expectation", "requests": [], "initiations": [],
                           "terminal_outcomes": [], "requirements": {"request_progress": "unknown", "initiation_progress": "unknown",
                               "request_authorization": "unknown", "scoped_memory": "unknown"},
                           "coverage_obligation": "No rising trigger occurs; unknown evidence before any response leaves scoped safety unresolved."}})
    return result


def source_edits(document: dict) -> list[dict]:
    declarations = document["program"]["declarations"]
    indices = {item["id"]: index for index, item in enumerate(declarations)}
    cases = (
        ("opposite_guard", ["program", "declarations", indices["respond"], "when"],
         p.to_data(p.not_(p.Expr("observe", p.TRUTH, ref=p.Ref("condition", "Observation"), scope=p.Ref("encounter/target", "Subject")))),
         "complete", [], "Fresh execution must distinguish a suppressed required response and failed scoped-memory safety."),
        ("lost_memory_write", ["program", "declarations", indices["respond"], "assignments", 0, "value"],
         p.to_data(p.FALSE), "complete", [], "Fresh execution must distinguish the settled scoped-memory violation."),
        ("different_product", ["program", "declarations", indices["product"], "value"],
         "fixture.product.beta", "complete", [], "Prior implementation/material acceptance cannot authorize a changed product."),
        ("longer_assurance", ["assurance", "horizon", "amount"], "5", "complete", [],
         "The supplied four-tick histories cannot establish the requested longer assurance domain."),
        ("unknown_assurance_requirement", ["assurance", "requirements", 0], "missing_requirement", "invalid", ["assurance_requirements"],
         "Reject an assurance selector that does not resolve to an original requirement."),
        ("stale_effect_definition", ["program", "declarations", indices["response"], "contract", "digest"],
         "0" * 64, "invalid", ["definition_identity"], "Reject an effect bound to a changed definition pin."),
    )
    result = []
    for identity, path, replacement, status, codes, obligation in cases:
        changed = deepcopy(document)
        parent = changed
        for key in path[:-1]:
            parent = parent[key]
        before = deepcopy(parent[path[-1]])
        parent[path[-1]] = replacement
        result.append({"id": identity, "path": path, "before": before, "after": replacement, "document": changed,
                       "expected_authoring_status": status, "required_diagnostics": codes,
                       "required_future_check": obligation, "native_validation": "not_performed"})
    return result


def fixture() -> dict:
    request = build_request()
    document = p.to_data(request)
    refs = {item.id: item.ref for item in request.program.semantics.definitions}
    tags = (("fixture.interface", "capability.deferred.v1"), ("fixture.encounter", "encounter.explicit.v1"),
            ("fixture.observation", "observation.external_evidence.v1"), ("fixture.effect", "effect.abstract_attempt.v1"),
            ("fixture.lifecycle", "lifecycle.correlated_feedback.v1"))
    return {"fixture_version": FIXTURE_VERSION, "stage": "source_authority_only", "native_validation": "not_performed",
            "artifact": "withheld", "claim_scope": "Artificial source and literal test expectations only; no accepted implementation or material.",
            "document": document,
            "definitions": {"schema_version": "biocompiler.policy_operational_definitions.v0.1", "profile": "biocompiler.policy_operational.v0.1",
                            "definitions": [{"definition": p.to_data(refs[name]), "semantics": tag} for name, tag in tags]},
            "timelines": timelines(), "source_edits": source_edits(document),
            "coverage_limits": ["Supplied timelines are witnesses, not exhaustive finite-domain coverage or proof.",
                                "Scoped safety may be unknown under stale or invalid evidence before any response; do not exclude these histories to claim success.",
                                "One-tick authorization progress alone permits later evidence; exact same-tick no-unauthorized-attempt preservation remains to be checked."],
            "pending_authorities": ["closed_executable_operating_domain", "independent_implementation_models",
                                    "implementation_and_material_catalog_entries", "complete_mrna_template_roots_and_chemistry",
                                    "configuration_and_connection_material_bindings", "native_preservation_and_requirement_assessments",
                                    "fresh_material_and_export_acceptance"]}


def encoded_fixture() -> str:
    return json.dumps(fixture(), sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = Path(__file__).resolve().parents[1] / "core/test/data/policy_realization_source_v01.json"
    content = encoded_fixture()
    if args.check:
        if path.read_text(encoding="utf-8") != content:
            raise SystemExit("Realization source authority differs; review original literals before updating")
    else:
        path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
