"""Freeze a bounded staged-regimen source and hand-authored timeline expectations.

These are artificial software fixtures: two abstract effect identities request
one supplied operation. No implementation model, RNA or biological mechanism is
inferred. Expected state and attempt traces are literals, never native output.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

from biocompiler import policy as p
from biocompiler.policy import patterns

PATH = "core/test/data/policy_staged_regimen_source_v01.json"
CASE_IDS = ("both_complete", "first_failure_and_timeout", "second_timeouts",
            "false_handoff_no_retry", "unknown_handoff_no_retry", "wrong_feedback",
            "reset_generation", "end_scope", "terminal_no_reentry")


def build_program() -> p.PolicyProgram:
    interface = p.SemanticDefinition("staged.interface", "1", "interface", "Supplied abstract executor interface.")
    encounter_contract = p.SemanticDefinition("staged.encounter", "1", "encounter", "Explicit encounter identity and reset generation.")
    observation_contract = p.SemanticDefinition("staged.observation", "1", "observation", "Timestamped supplied truth evidence.", result=p.TRUTH)
    operation = p.SemanticDefinition("staged.operation", "1", "operation", "Request the same abstract product in two distinctly identified stages.")
    lifecycle_contract = p.SemanticDefinition("staged.lifecycle", "1", "lifecycle", "Attempt/executor/subject-correlated completion or failure; explicit timeout.")
    builder = p.ProgramBuilder("bounded_staged_regimen", semantics=p.SemanticBundle("staged.semantics", "1",
        (interface, encounter_contract, observation_contract, operation, lifecycle_contract)))
    executor = builder.executor("executor", requires=(interface.ref,))
    encounter = builder.encounter("encounter", executor=executor, contract=encounter_contract.ref, termination="explicit_event")
    clock = builder.clock("clock", basis="logical", resolution=p.quantity(1, p.SECOND))
    condition = builder.observe("condition", observer=executor, subject=encounter.target, value_type=p.TRUTH,
        contract=observation_contract.ref, clock=clock, access="cell", coverage="event", coherence="frame",
        freshness=p.quantity(10, p.SECOND))
    lifecycle = p.EffectLifecycle("continuous", "continue", "defer", "unsupported", "feedback", "feedback",
        lifecycle_contract.ref, p.quantity(2, p.SECOND))
    first = builder.effect("stage_one", contract=operation.ref, executor=executor, subject=encounter.target, lifecycle=lifecycle)
    second = builder.effect("stage_two", contract=operation.ref, executor=executor, subject=encounter.target, lifecycle=lifecycle)
    patterns.ordered_effects(builder, "regimen", executor=p.ref(executor), scope=p.Scope("encounter", p.ref(encounter)),
        on=p.rising(condition.expression), permitted=condition.expression, first=first, second=second,
        arbitration=p.Arbitration("exclusive", "reject", "reject", "forbidden", "none"), lifetime="encounter")
    for name, effect in (("first_initiation", first), ("second_initiation", second)):
        builder.require(p.Requirement(name, "progress", "Each requested attempt initiates under the supplied abstract lifecycle.",
            p.Scope("encounter", p.ref(encounter)), trigger=effect.event("requested"), response=effect.event("initiated"),
            deadline=p.quantity(1, p.SECOND), horizon=p.quantity(6, p.SECOND), clock=p.ref(clock)))
    program = builder.freeze()
    # Fixed logical source locations are part of this reviewed original packet;
    # host checkout paths do not replace or parameterize source authority.
    return replace(program, source_map=tuple(p.SourceSpan(row.id, "staged_regimen_literal.py", i + 1,
        pattern="regimen" if row.id.startswith("regimen/") else None) for i, row in enumerate(program.declarations)))


def observation(identity: str, tick: int, value: bool | None, *, status: str = "valid", suffix: str = "") -> dict:
    return {"id": f"{identity}-observation-{tick}{suffix}", "available_at": str(tick), "observed_at": str(tick),
        "observer": "cell-1", "subject": "target-" + identity[-1], "encounter": identity,
        "observation": "condition", "status": status, "value": value}


def feedback(identity: str, tick: int, attempt: int, stage: str, outcome: str, *, name: str | None = None) -> dict:
    return {"id": name or f"{identity}-{stage}-{tick}-{outcome}", "available_at": str(tick), "executor": "cell-1",
        "subject": "target-" + identity[-1], "encounter": identity, "effect": stage,
        "attempt": f"attempt/{attempt}", "outcome": outcome}


def timeline() -> dict:
    return {"profile": "biocompiler.policy_timeline.v0.1", "executor": "cell-1", "horizon": "6",
        "encounters": [{"id": identity, "declaration": "encounter", "target": "target-" + identity[-1],
            "start": "0", "end": None, "resets": []} for identity in ("e1", "e2")],
        "observations": [observation(identity, tick, value) for tick, value in ((0, False), (1, True)) for identity in ("e1", "e2")],
        "feedback": [], "bounds": {"max_ticks": 100, "max_inputs": 100, "max_encounters": 2,
            "max_attempts": 16, "max_work": 4000000, "max_trace_items": 20000, "max_microsteps": 100}}


def machine(encounter: str, state: str, attempt: int | None = None, generation: int = 0) -> dict:
    return {"machine": "regimen/stages", "binding": {"encounter": encounter, "generation": generation},
        "state": state, "attempts": [] if attempt is None else [f"attempt/{attempt}"]}


def frame(tick: int, left: tuple | None, right: tuple | None, active: tuple[int, ...]) -> dict:
    return {"time": str(tick), "machines": [machine(identity, *values) for identity, values in (("e1", left), ("e2", right)) if values is not None],
        "active_attempts": [f"attempt/{value}" for value in active]}


def attempt(number: int, encounter: str, stage: str, started: int, ended: int, status: str, generation: int = 0) -> dict:
    return {"id": f"attempt/{number}", "effect": stage, "executor": "cell-1", "subject": "target-" + encounter[-1],
        "binding": {"encounter": encounter, "generation": generation}, "machine": "regimen/stages",
        "initiator": "regimen/start" if stage == "stage_one" else "regimen/handoff", "parameters": {},
        "started_at": str(started), "deadline": str(started + 2), "ended_at": str(ended), "status": status,
        "authorization": "true"}


def fixture() -> dict:
    program = build_program()
    interpretations = ("capability.deferred.v1", "encounter.explicit.v1", "observation.external_evidence.v1",
                       "effect.abstract_attempt.v1", "lifecycle.correlated_feedback.v1")
    definitions = {"schema_version": "biocompiler.policy_operational_definitions.v0.1", "profile": "biocompiler.policy_operational.v0.1",
        "definitions": [{"definition": p.to_data(definition.ref), "semantics": semantics}
            for definition, semantics in zip(program.semantics.definitions, interpretations)]}
    cases = []
    def retain(identity, original, frames, attempts, rejected=()):
        assert len(frames) == 7 and [row["time"] for row in frames] == [str(i) for i in range(7)]
        cases.append({"id": identity, "timeline": original, "expected": {"frames": frames, "attempts": attempts,
            "feedback_rejected": [{"id": name, "reason": reason} for name, reason in rejected]}})
    r, f, s, c, x = ("ready",), ("first", 1), ("second", 3), ("completed",), ("failed",)
    initial = [frame(0, r, r, ()), frame(1, f, ("first", 2), (1, 2))]
    both = timeline()
    both["feedback"] = [feedback("e1", 2, 1, "stage_one", "completed"), feedback("e2", 3, 2, "stage_one", "completed"),
        feedback("e1", 4, 3, "stage_two", "completed"), feedback("e2", 5, 4, "stage_two", "completed")]
    retain("both_complete", both, initial + [frame(2, s, ("first", 2), (2, 3)), frame(3, s, ("second", 4), (3, 4)),
        frame(4, c, ("second", 4), (4,)), frame(5, c, c, ()), frame(6, c, c, ())],
        [attempt(1, "e1", "stage_one", 1, 2, "completed"), attempt(2, "e2", "stage_one", 1, 3, "completed"),
         attempt(3, "e1", "stage_two", 2, 4, "completed"), attempt(4, "e2", "stage_two", 3, 5, "completed")])
    failed = timeline(); failed["feedback"] = [feedback("e1", 2, 1, "stage_one", "failed")]
    retain("first_failure_and_timeout", failed, initial + [frame(2, x, ("first", 2), (2,))] + [frame(i, x, x, ()) for i in (3, 4, 5, 6)],
        [attempt(1, "e1", "stage_one", 1, 2, "failed"), attempt(2, "e2", "stage_one", 1, 3, "timed_out")])
    second_timeout = deepcopy(both); second_timeout["feedback"] = second_timeout["feedback"][:2]
    retain("second_timeouts", second_timeout, initial + [frame(2, s, ("first", 2), (2, 3)), frame(3, s, ("second", 4), (3, 4)),
        frame(4, x, ("second", 4), (4,)), frame(5, x, x, ()), frame(6, x, x, ())],
        [attempt(1, "e1", "stage_one", 1, 2, "completed"), attempt(2, "e2", "stage_one", 1, 3, "completed"),
         attempt(3, "e1", "stage_two", 2, 4, "timed_out"), attempt(4, "e2", "stage_two", 3, 5, "timed_out")])
    for identity, value, status in (("false_handoff_no_retry", False, "valid"), ("unknown_handoff_no_retry", None, "missing")):
        blocked = timeline(); blocked["observations"] += [observation("e1", 2, value, status=status), observation("e1", 3, True)]
        blocked["feedback"] = [feedback("e1", 2, 1, "stage_one", "completed"), feedback("e1", 4, 1, "stage_one", "completed", name="stale-completion")]
        retain(identity, blocked, initial + [frame(2, f, ("first", 2), (2,))] + [frame(i, f, x, ()) for i in (3, 4, 5, 6)],
            [attempt(1, "e1", "stage_one", 1, 2, "completed"), attempt(2, "e2", "stage_one", 1, 3, "timed_out")], [("stale-completion", "stale_attempt")])
    wrong = timeline()
    wrong["feedback"] = [feedback("e1", 2, 1, "stage_two", "completed", name="wrong-stage"),
        feedback("e2", 2, 1, "stage_one", "completed", name="wrong-encounter"),
        {**feedback("e1", 2, 1, "stage_one", "completed", name="wrong-executor"), "executor": "cell-other"},
        {**feedback("e1", 2, 1, "stage_one", "completed", name="wrong-subject"), "subject": "target-other"}]
    retain("wrong_feedback", wrong, initial + [frame(2, f, ("first", 2), (1, 2))] + [frame(i, x, x, ()) for i in (3, 4, 5, 6)],
        [attempt(1, "e1", "stage_one", 1, 3, "timed_out"), attempt(2, "e2", "stage_one", 1, 3, "timed_out")],
        [(name, "identity_mismatch") for name in ("wrong-stage", "wrong-encounter", "wrong-executor", "wrong-subject")])
    reset = timeline(); reset["encounters"][0]["resets"] = ["2"]
    reset["observations"] += [observation("e1", 2, False), observation("e1", 3, True)]
    reset["feedback"] = [feedback("e1", 2, 1, "stage_one", "completed", name="pre-reset-completion"),
        feedback("e1", 4, 1, "stage_one", "completed", name="old-generation-completion"),
        feedback("e1", 4, 3, "stage_one", "completed"), feedback("e1", 5, 4, "stage_two", "completed")]
    retain("reset_generation", reset, initial + [frame(2, ("ready", None, 1), ("first", 2), (2,)),
        frame(3, ("first", 3, 1), x, (3,)), frame(4, ("second", 4, 1), x, (4,)), frame(5, ("completed", None, 1), x, ()), frame(6, ("completed", None, 1), x, ())],
        [attempt(1, "e1", "stage_one", 1, 2, "encounter_reset"), attempt(2, "e2", "stage_one", 1, 3, "timed_out"),
         attempt(3, "e1", "stage_one", 3, 4, "completed", 1), attempt(4, "e1", "stage_two", 4, 5, "completed", 1)],
        [("pre-reset-completion", "stale_attempt"), ("old-generation-completion", "stale_attempt")])
    ended = timeline(); ended["encounters"][0]["end"] = "2"
    ended["feedback"] = [feedback("e1", 2, 1, "stage_one", "completed", name="ended-completion")]
    retain("end_scope", ended, initial + [frame(2, None, ("first", 2), (2,))] + [frame(i, None, x, ()) for i in (3, 4, 5, 6)],
        [attempt(1, "e1", "stage_one", 1, 2, "encounter_ended"), attempt(2, "e2", "stage_one", 1, 3, "timed_out")], [("ended-completion", "stale_attempt")])
    terminal = deepcopy(both); terminal["observations"] += [observation("e1", 5, False), observation("e1", 6, True)]
    retain("terminal_no_reentry", terminal, deepcopy(cases[0]["expected"]["frames"]), deepcopy(cases[0]["expected"]["attempts"]))
    assert tuple(case["id"] for case in cases) == CASE_IDS
    return {"fixture_version": "biocompiler.policy_staged_regimen_source_literals.v0.1", "claim_scope": "bounded_abstract_source_execution_only",
        "document": p.to_data(program), "definitions": definitions, "cases": cases}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--check", action="store_true"); args = parser.parse_args()
    path = Path(__file__).resolve().parents[1] / PATH
    content = json.dumps(fixture(), sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"
    if args.check:
        if path.read_text(encoding="utf-8") != content: raise SystemExit("Staged source fixture differs; review source and literal expectations")
    else: path.write_text(content, encoding="utf-8")


if __name__ == "__main__": main()
