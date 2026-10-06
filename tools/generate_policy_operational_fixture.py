"""Freeze abstract operational inputs; never execute or infer expected traces.

The literal timeline deliberately completes one correlated attempt and lets the
other expire with no new observations. All values are software test fixtures.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from biocompiler import policy as p


def fixture() -> dict:
    interface = p.SemanticDefinition("fixture.interface", "1", "interface", "Abstract executor input.")
    encounter_definition = p.SemanticDefinition("fixture.encounter", "1", "encounter", "Explicit encounter identity.")
    observation_definition = p.SemanticDefinition("fixture.observation", "1", "observation", "Exact timestamped evidence.", result=p.TRUTH)
    operation = p.SemanticDefinition("fixture.effect", "1", "operation", "Abstract effect request only.")
    lifecycle = p.SemanticDefinition("fixture.lifecycle", "1", "lifecycle", "Correlated bounded feedback.")
    definitions = (interface, encounter_definition, observation_definition, operation, lifecycle)
    executor = p.Role("executor", (interface.ref,))
    target = p.Subject("target", "cell", "encounter", p.ref(executor), p.Ref("encounter", "Encounter"))
    encounter = p.Encounter("encounter", p.ref(executor), p.ref(target), encounter_definition.ref, "explicit_event")
    clock = p.Clock("clock", "availability", p.quantity(1, p.SECOND))
    observation = p.Observation("condition", p.ref(executor), p.ref(target), p.TRUTH,
                                observation_definition.ref, p.ref(clock), "cell", "event", "frame",
                                p.quantity(2, p.SECOND))
    state = p.StateStore("seen", p.TRUTH, p.Scope("encounter", p.ref(encounter)), False, 16,
                         "reject", "encounter", None, "not_applicable")
    effect = p.Effect("response", operation.ref, p.ref(executor), p.ref(target),
                      p.EffectLifecycle("continuous", "continue", "defer", "unsupported", "feedback", "feedback",
                                        lifecycle.ref, p.quantity(2, p.SECOND)))
    rule = p.Rule("respond", p.ref(executor), p.rising(observation.expression), observation.expression,
                  "defer", (p.ref(effect),), (p.Assignment(p.ref(state), p.TRUE),),
                  p.Arbitration("exclusive", "reject", "reject", "forbidden", "none"))
    requirement = p.Requirement("completion", "progress", "Each request completes within two ticks.",
                                p.Scope("encounter", p.ref(encounter)), condition=p.TRUE,
                                response=effect.completed, deadline=p.quantity(2, p.SECOND),
                                horizon=p.quantity(4, p.SECOND),
                                assumptions=("Only supplied feedback is modeled.",),
                                trigger=effect.event("requested"), clock=p.ref(clock))
    safety = p.Requirement("scoped_memory", "safety", "Known true evidence implies this encounter recorded its response.",
                           p.Scope("encounter", p.ref(encounter)),
                           condition=p.any_of(p.not_(observation.expression), state.expression),
                           horizon=p.quantity(4, p.SECOND))
    declarations = (executor, target, encounter, clock, observation, state, effect, rule, requirement, safety)
    document = p.PolicyProgram("operational_literal", p.SemanticBundle("fixture.semantics", "1", definitions),
                               declarations, tuple(p.SourceSpan(item.id, "operational_literal.py", i + 1)
                                                   for i, item in enumerate(declarations)))
    semantics = ["capability.deferred.v1", "encounter.explicit.v1", "observation.external_evidence.v1", "effect.abstract_attempt.v1", "lifecycle.correlated_feedback.v1"]
    bundle = {"schema_version": "biocompiler.policy_operational_definitions.v0.1",
              "profile": "biocompiler.policy_operational.v0.1",
              "definitions": [{"definition": p.to_data(item.ref), "semantics": tag}
                              for item, tag in zip(definitions, semantics)]}
    observations = [{"id": f"{encounter_id}-{time}", "available_at": str(time), "observed_at": str(time),
                     "observer": "cell-1", "subject": subject, "encounter": encounter_id,
                     "observation": "condition", "status": "valid", "value": value}
                    for time, value in ((0, False), (1, True))
                    for encounter_id, subject in (("e1", "target-1"), ("e2", "target-2"))]
    timeline = {"profile": "biocompiler.policy_timeline.v0.1", "executor": "cell-1", "horizon": "4",
                "encounters": [{"id": identity, "declaration": "encounter", "target": target_id,
                                "start": "0", "end": None, "resets": []}
                               for identity, target_id in (("e1", "target-1"), ("e2", "target-2"))],
                "observations": observations,
                "feedback": [{"id": "feedback-1", "available_at": "2", "executor": "cell-1", "subject": "target-1",
                              "encounter": "e1", "effect": "response", "attempt": "attempt/1", "outcome": "completed"}],
                "bounds": {"max_ticks": 100, "max_inputs": 100, "max_encounters": 16, "max_attempts": 100,
                           "max_work": 1000000, "max_trace_items": 10000, "max_microsteps": 100}}
    return {"fixture_version": "biocompiler.policy_operational_literals.v0.1", "document": p.to_data(document),
            "definitions": bundle, "timeline": timeline,
            "expected_attempts": [{"id": "attempt/1", "encounter": "e1", "subject": "target-1", "status": "completed"},
                                  {"id": "attempt/2", "encounter": "e2", "subject": "target-2", "status": "timed_out"}]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = Path(__file__).resolve().parents[1] / "core/test/data/policy_operational_v01.json"
    content = json.dumps(fixture(), sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"
    if args.check:
        if path.read_text(encoding="utf-8") != content:
            raise SystemExit("Frozen operational policy inputs differ; review before changing literals")
    else:
        path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
