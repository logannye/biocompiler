"""Author complete simultaneous-lifecycle/feedback/deadline material authority.

No policy evaluator, producer, native executable or saved report is consulted.
All 27 histories are retained: Keep/Reset/End for e1 at tick3 crossed with
silence/completed/failed for each of the two previously created attempts at
that same tick. Lifecycle precedes feedback, and feedback precedes timeout.
The literals below specify that ordering independently of a produced candidate.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "core/test/data"
OUTPUT = DATA / "policy_material_timing_v01.json"
SEED_REQUEST = "754a3a30752855c3e9458c0b657a2e7ac850d6aebb27e260009e331296341e36"
SEED_CONTEXT = "d25a17db6e84c10c44fe1df44efe89352fb53a69f4178ee68a9f0b5b6b5720f2"


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def pin(value: dict) -> None:
    value["identity"]["content_fingerprint"] = digest(value["body"])


def event(kind: str, slot: str, ordinal: int | None, generation: int = 0) -> dict:
    return {"kind": kind, "slot": slot, "generation": generation,
        "creation_ordinal": ordinal, "tick": 3, "microstep": 0}


def terminal(ordinal: int, status: str) -> dict:
    return {"creation_ordinal": ordinal, "slot": f"e{ordinal}", "target": f"target-{ordinal}",
        "generation": 0, "started_tick": 1, "deadline_tick": 3, "ended_tick": 3, "status": status}


def traces() -> list[dict]:
    result = []
    # The complete independent Cartesian alphabet is literal. Silence means
    # an absent feedback row, never an unrecorded successful completion.
    for lifecycle in ("keep", "reset", "end"):
        for first in ("silence", "completed", "failed"):
            for second in ("silence", "completed", "failed"):
                rows = [{"creation_ordinal": ordinal, "outcome": outcome}
                    for ordinal, outcome in ((1, first), (2, second)) if outcome != "silence"]
                actions = []
                for index, row in enumerate(rows):
                    rejected = lifecycle != "keep" and row["creation_ordinal"] == 1
                    actions.append({"kind": "feedback_rejected" if rejected else "feedback_accepted",
                        "id": f"domain/feedback/3/{index}", "creation_ordinal": row["creation_ordinal"],
                        "reason": "stale_attempt" if rejected else None, "microstep": 0})
                # Reset/end invalidate the original generation before feedback.
                # At Keep, supplied deadline feedback wins; only silence times out.
                if lifecycle == "keep":
                    events = []
                    statuses = ["timed_out" if outcome == "silence" else outcome for outcome in (first, second)]
                else:
                    statuses = ["encounter_reset" if lifecycle == "reset" else "encounter_ended",
                        "timed_out" if second == "silence" else second]
                    events = [event("attempt_reset" if lifecycle == "reset" else "attempt_ended", "e1", 1),
                        event("encounter_reset" if lifecycle == "reset" else "encounter_ended", "e1", None,
                            1 if lifecycle == "reset" else 0)]
                events += [event(row["outcome"], f"e{row['creation_ordinal']}", row["creation_ordinal"])
                    for row in rows if lifecycle == "keep" or row["creation_ordinal"] != 1]
                events += [event("timed_out", f"e{ordinal}", ordinal)
                    for ordinal, status in enumerate(statuses, 1) if status == "timed_out"]
                result.append({"id": f"{lifecycle}_{first}_{second}",
                    "lifecycle": [{"tick": 3, "slot": "e1", "action": lifecycle}], "observations": [],
                    "feedback": [{"tick": 3, "rows": rows}],
                    "creations_by_tick": [0, 2, 0, 0, 0, 0, 0],
                    "final_attempts": [terminal(ordinal, status) for ordinal, status in enumerate(statuses, 1)],
                    "deadline_actions": actions, "deadline_events": events,
                    "deadline_slots": [{"slot": "e1", "generation": 1 if lifecycle == "reset" else 0,
                        "active": lifecycle != "end"}, {"slot": "e2", "generation": 0, "active": True}],
                    "observation_occurrence_ids": [f"domain/observation/{tick}/{index}"
                        for tick in (0, 1, 2) for index in (0, 1)],
                    "feedback_occurrence_ids": [f"domain/feedback/3/{index}" for index in range(len(rows))]})
    return result


def build() -> dict:
    seed = json.loads((DATA / "policy_material_request_v01.json").read_text())
    contexts = json.loads((DATA / "policy_material_context_v01.json").read_text())
    if digest(seed["request"]) != SEED_REQUEST or digest(contexts) != SEED_CONTEXT:
        raise ValueError("Frozen original authority changed; independently review before regeneration")
    original_case = contexts["reset_feedback_case"]
    request = deepcopy(seed["request"])
    request.update(implementation_request=deepcopy(original_case["source_case"]["request"]),
        material_contract=deepcopy(original_case["contract"]), context=deepcopy(original_case["context"]))
    original, contract, context = request["implementation_request"], request["material_contract"], request["context"]
    domain = original["operating_domain"]
    domain["feedback_factors"][0]["ticks"] = [3]
    contract["identity"]["id"] = "artificial.context.simultaneous_deadline_component"
    pin(contract)
    request["catalog_binding"]["material_contract"] = deepcopy(contract["identity"])
    context["record_layout"]["domain_digest"] = digest(domain)
    for provider in context["providers"]:
        body = provider["body"]
        if body["kind"] == "environment":
            body["grammar"] = deepcopy(domain)
        for capacity in body["capacities"]:
            capacity["record_layout_digest"] = digest(context["record_layout"])
        pin(provider)
    # Same graph, horizons and maximum row/correlation counts. Simultaneity
    # preserves the existing conservative full-domain queue calculation:
    # 2*(2+1+2+2+5) + 4*2 + 2 = 34, and 34*(6+1) = 238 cause slots.
    assert contract["body"] == original_case["contract"]["body"]
    assert original["budgets"] == original_case["source_case"]["request"]["budgets"]
    for key in ("document", "definitions", "implementation_library", "catalog_bindings"):
        assert original[key] == seed["request"]["implementation_request"][key]
    for key in ("kernel", "carriers", "products", "material_key", "structure_authority", "input_witnesses", "allocations"):
        assert contract["body"][key] == seed["request"]["material_contract"]["body"][key]
    requirements = [row for row in original["document"]["program"]["declarations"] if row["$type"] == "Requirement"]
    assert [row["id"] for row in requirements] == ["request_progress", "initiation_progress", "exclusive_selection"]
    expected = deepcopy(seed["expected"])
    expected.pop("request_decoding_work")
    widths = [1, 1, 1, 27, 27, 27, 27]
    expected.update(request_fingerprint=digest(request), source_request_digest=digest(original),
        source_artifact_digest=digest(original["document"]), definitions_digest=digest(original["definitions"]),
        domain_digest=digest(domain), library_digest=digest(original["implementation_library"]),
        material_contract_digest=digest(contract), context_digest=digest(context),
        kernel_digest=digest(contract["body"]["kernel"]), carrier_digest=digest(contract["body"]["carriers"]),
        requirements=deepcopy(requirements), histories=27, transitions=111, prefixes_started=112,
        prefixes_after_tick=widths, trace_witnesses=traces(), resource_demands=deepcopy(contract["body"]["resources"]),
        queue_records=34, ordered_cause_slots=238, maximum_tick=8,
        domain_claim="Every Keep/Reset/End choice for e1 at tick3 combines with every silence/completed/failed "
            "choice for both prior attempts at their exact deadline3. Lifecycle is applied before feedback, "
            "and feedback before timeout. No choice is filtered and no requirement or budget is weakened.")
    assert sum(widths) == expected["transitions"] and len(expected["trace_witnesses"]) == expected["histories"]
    return {"schema_version": "biocompiler.policy_material_timing_literals.v0.1",
        "notice": "Artificial supplied contracts; independently authored complete grammar and timing literals. "
            "Hosted native acceptance pending. No produced report is authority and no empirical realization is claimed.",
        "limits": deepcopy(seed["limits"]), "cases": [{"id": "simultaneous_deadline_lifecycle", "request": request, "expected": expected}]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    encoded = json.dumps(build(), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.check:
        if OUTPUT.read_text() != encoded:
            raise SystemExit("Timing fixture differs from inert authoring source")
    else:
        OUTPUT.write_text(encoded)


if __name__ == "__main__":
    main()
