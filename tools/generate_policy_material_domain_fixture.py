"""Author complete original domain-extension requests without executing policy.

The first two authorities retain the existing independently authored context
fixtures. The third retains a keep/reset grammar whose complete search exceeds
the frozen work budget; it must remain incomplete with no export. The fourth
separately declares a smaller grammar with feedback at tick5 only. It cannot
discharge the third case's larger domain. Counts and trace witnesses are literal
expectations, never obtained from a producer or checked report. This is source
authoring only; hosted native checks establish acceptance.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "core/test/data"
OUTPUT = DATA / "policy_material_domain_v01.json"
SEED_REQUEST = "754a3a30752855c3e9458c0b657a2e7ac850d6aebb27e260009e331296341e36"
SEED_CONTEXT = "d25a17db6e84c10c44fe1df44efe89352fb53a69f4178ee68a9f0b5b6b5720f2"


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def pin(value: dict) -> None:
    value["identity"]["content_fingerprint"] = digest(value["body"])


def feedback(tick: int, rows: list[tuple[int, str]]) -> dict:
    return {"tick": tick, "rows": [{"creation_ordinal": ordinal, "outcome": outcome}
        for ordinal, outcome in rows]}


def attempt(ordinal: int, slot: str, generation: int, start: int, end: int, status: str) -> dict:
    return {"creation_ordinal": ordinal, "slot": slot, "target": "target-1" if slot == "e1" else "target-2",
        "generation": generation, "started_tick": start, "deadline_tick": start + 2,
        "ended_tick": end, "status": status}


def lift(seed: dict, private: dict, identity: str, widths: list[int], claim: str) -> dict:
    request = deepcopy(seed["request"])
    request.update(implementation_request=deepcopy(private["source_case"]["request"]),
        material_contract=deepcopy(private["contract"]), context=deepcopy(private["context"]))
    request["catalog_binding"]["material_contract"] = deepcopy(request["material_contract"]["identity"])
    expected = deepcopy(seed["expected"])
    # These counts are independent Cartesian products, not a decoded report.
    expected.update(histories=widths[-1], transitions=sum(widths), prefixes_started=1 + sum(widths),
        prefixes_after_tick=widths, domain_claim=claim, trace_witnesses=[])
    expected.pop("request_decoding_work")
    return {"id": identity, "request": request, "expected": expected}


def refresh_expectations(case: dict, seed: dict) -> None:
    request, expected = case["request"], case["expected"]
    original = request["implementation_request"]
    base = seed["request"]
    # Changing the environment does not reauthor the source, requirements,
    # primitive contract, configuration/wires, carrier sites, or molecular body.
    for key in ("document", "definitions", "implementation_library", "catalog_bindings"):
        if original[key] != base["implementation_request"][key]:
            raise ValueError(f"Domain sibling changed original {key}")
    for key in ("kernel", "carriers", "products", "material_key", "structure_authority", "input_witnesses", "allocations"):
        if request["material_contract"]["body"][key] != base["material_contract"]["body"][key]:
            raise ValueError(f"Domain sibling changed material {key}")
    requirements = [row for row in original["document"]["program"]["declarations"]
        if row["$type"] == "Requirement"]
    if [row["id"] for row in requirements] != ["request_progress", "initiation_progress", "exclusive_selection"]:
        raise ValueError("The independently fixed three hard requirements changed")
    contract, context = request["material_contract"], request["context"]
    layout = context["record_layout"]
    if layout["domain_digest"] != digest(original["operating_domain"]):
        raise ValueError("Supplied complete-record layout lost its original domain")
    if layout["kernel_digest"] != digest(contract["body"]["kernel"]):
        raise ValueError("Supplied complete-record layout lost its unchanged kernel")
    for provider in context["providers"]:
        if provider["identity"]["content_fingerprint"] != digest(provider["body"]):
            raise ValueError("Supplied provider body has a stale identity")
        for capacity in provider["body"]["capacities"]:
            if capacity["record_layout_digest"] != digest(layout):
                raise ValueError("Capacity omitted the complete original record layout")
        if provider["body"]["kind"] == "environment" and provider["body"]["grammar"] != original["operating_domain"]:
            raise ValueError("Environment provider does not retain the complete original grammar")
    if contract["identity"]["content_fingerprint"] != digest(contract["body"]):
        raise ValueError("Supplied composite material case has a stale identity")
    expected.update(request_fingerprint=digest(request), source_request_digest=digest(original),
        context_digest=digest(context), material_contract_digest=digest(contract),
        source_artifact_digest=digest(original["document"]), definitions_digest=digest(original["definitions"]),
        library_digest=digest(original["implementation_library"]), kernel_digest=digest(contract["body"]["kernel"]),
        carrier_digest=digest(contract["body"]["carriers"]), requirements=deepcopy(requirements),
        domain_digest=digest(original["operating_domain"]), resource_demands=deepcopy(contract["body"]["resources"]),
        queue_records=next(row["quantity"] for row in contract["body"]["resources"] if row["unit"] == "control_event_records"),
        ordered_cause_slots=layout["ordered_cause_slots"], maximum_tick=layout["maximum_tick"])


def recreate(seed: dict, extended: dict) -> dict:
    case = lift(seed, extended, "reset_recreate", [1, 1, 1, 2, 18, 486, 486],
        "Every keep/reset choice at tick3 combines with all silence/completed/failed feedback "
        "for both old attempts at tick4, then all three attempts at tick5. Fixed false3/true4 "
        "samples produce a new e1 attempt in the retained or reset generation. "
        "No active-only selector, requirement filter, or wrong-address route is admitted.")
    request = case["request"]
    original = request["implementation_request"]
    domain = original["operating_domain"]
    domain["observation_factors"] = []
    domain["lifecycle_factors"] = [{"slots": ["e1"], "ticks": [3], "actions": ["keep", "reset"]}]
    domain["feedback_factors"][0]["ticks"] = [4, 5]
    domain["fixed_observations"].extend([
        {"slot": "e1", "observation": "condition", "available_tick": tick, "observed_tick": tick,
         "status": "valid", "value": value} for tick, value in ((3, False), (4, True))])
    # The unchanged graph needs one persistent evidence record per possible
    # e1 input row (5), three retained correlations, and three feedback rows.
    # Queue = 2*(2+1+2+2+5)+4*3+3 = 39; causes = 39*(6+1) = 273.
    # The third attempt starts4/deadline6; both original attempts end3 before
    # feedback4/5. Same-tick new creation cannot enter feedback4's alphabet.
    contract = request["material_contract"]
    contract["identity"]["id"] = "artificial.context.reset_recreate_component"
    for resource in contract["body"]["resources"]:
        if resource["unit"] == "evidence_records":
            resource["quantity"] = 5
    pin(contract)
    request["catalog_binding"]["material_contract"] = deepcopy(contract["identity"])
    context = request["context"]
    context["record_layout"]["domain_digest"] = digest(domain)
    for provider in context["providers"]:
        body = provider["body"]
        if body["kind"] == "environment":
            body["grammar"] = deepcopy(domain)
        for capacity in body["capacities"]:
            capacity["record_layout_digest"] = digest(context["record_layout"])
            if capacity["unit"] == "evidence_records":
                capacity["quantity"] = 5
        pin(provider)
    witnesses = []
    for lifecycle, generation, old_status in (("keep", 0, "timed_out"), ("reset", 1, "encounter_reset")):
        for outcome in ("completed", "failed", "silence"):
            final_rows = [(1, "completed"), (2, "failed")]
            if outcome != "silence":
                final_rows.append((3, outcome))
            witnesses.append({"id": f"{lifecycle}_{outcome}", "lifecycle": [{"tick": 3, "slot": "e1", "action": lifecycle}],
                "observations": [], "feedback": [feedback(4, [(1, "completed"), (2, "failed")]), feedback(5, final_rows)],
                "creations_by_tick": [0, 2, 0, 0, 1, 0, 0],
                "final_attempts": [attempt(1, "e1", 0, 1, 3, old_status), attempt(2, "e2", 0, 1, 3, "timed_out"),
                    attempt(3, "e1", generation, 4, 6 if outcome == "silence" else 5,
                        "timed_out" if outcome == "silence" else outcome)],
                "feedback_rejections": [{"tick": tick, "creation_ordinal": ordinal, "reason": "stale_attempt"}
                    for tick in (4, 5) for ordinal in (1, 2)],
                "feedback_acceptances": [] if outcome == "silence" else [{"tick": 5, "creation_ordinal": 3}],
                "observation_occurrence_ids": [f"domain/observation/{tick}/{index}"
                    for tick, count in enumerate((2, 2, 2, 1, 1, 0, 0)) for index in range(count)],
                "feedback_occurrence_ids": [f"domain/feedback/{tick}/{index}"
                    for tick, count in ((4, 2), (5, len(final_rows))) for index in range(count)]})
    case["expected"]["trace_witnesses"] = witnesses
    return case


def recreate_feedback(original_case: dict) -> dict:
    """Author a distinct complete domain, without filtering the larger search."""
    case = deepcopy(original_case)
    case["id"] = "reset_recreate_feedback"
    request = case["request"]
    domain = request["implementation_request"]["operating_domain"]
    domain["feedback_factors"][0]["ticks"] = [5]
    # Both old attempts and the new attempt enter tick5's alphabet. Each has
    # silence/completed/failed, for 2 lifecycle choices * 3**3 = 54 histories.
    # Five e1 evidence records, three correlations/feedback rows, queue39 and
    # cause273 stay unchanged. Every choice is retained, including stale ones.
    contract = request["material_contract"]
    contract["identity"]["id"] = "artificial.context.reset_recreate_feedback_component"
    pin(contract)
    request["catalog_binding"]["material_contract"] = deepcopy(contract["identity"])
    context = request["context"]
    context["record_layout"]["domain_digest"] = digest(domain)
    for provider in context["providers"]:
        body = provider["body"]
        if body["kind"] == "environment":
            body["grammar"] = deepcopy(domain)
        for capacity in body["capacities"]:
            capacity["record_layout_digest"] = digest(context["record_layout"])
        pin(provider)
    widths = [1, 1, 1, 2, 2, 54, 54]
    expected = case["expected"]
    expected.update(histories=widths[-1], transitions=sum(widths), prefixes_started=1 + sum(widths),
        prefixes_after_tick=widths,
        domain_claim="A separately declared complete domain: every keep/reset choice at tick3 combines "
            "with silence/completed/failed feedback for all three prior attempts at tick5 only. "
            "Fixed false3/true4 samples recreate an e1 attempt in the retained or reset generation. "
            "This 54-history domain does not discharge the separate 486-history reset_recreate request. "
            "No active-only selector, requirement filter, or wrong-address route is admitted.")
    for witness in expected["trace_witnesses"]:
        witness["feedback"] = [row for row in witness["feedback"] if row["tick"] == 5]
        witness["feedback_rejections"] = [row for row in witness["feedback_rejections"] if row["tick"] == 5]
        witness["feedback_occurrence_ids"] = [identity for identity in witness["feedback_occurrence_ids"]
            if identity.startswith("domain/feedback/5/")]
    return case


def build() -> dict:
    seed = json.loads((DATA / "policy_material_request_v01.json").read_text())
    contexts = json.loads((DATA / "policy_material_context_v01.json").read_text())
    if digest(seed["request"]) != SEED_REQUEST or digest(contexts) != SEED_CONTEXT:
        raise ValueError("Original authority changed; independently review before regeneration")
    extended = lift(seed, contexts["extended_evidence_case"], "extended_evidence", [1, 1, 9, 54, 54, 54, 54],
        "All nine initial correlated-feedback histories combine with silence, false, true, missing, invalid "
        "and conflicting e1 evidence at tick3. All choices remain in the original finite grammar.")
    extended["expected"]["trace_witnesses"] = [{"id": "known_true_repeated_attempt", "lifecycle": [],
        "observations": [{"tick": 3, "slot": "e1", "status": "valid", "value": True}], "feedback": [],
        "creations_by_tick": [0, 2, 0, 1, 0, 0, 0],
        "final_attempts": [attempt(1, "e1", 0, 1, 3, "timed_out"), attempt(2, "e2", 0, 1, 3, "timed_out"),
            attempt(3, "e1", 0, 3, 5, "timed_out")], "feedback_rejections": [], "feedback_acceptances": []}]
    resetting = lift(seed, contexts["reset_feedback_case"], "reset_feedback", [1, 1, 1, 3, 27, 27, 27],
        "Every keep/reset/end choice at tick3 combines with all silence/completed/failed feedback "
        "for both old attempts at tick4. This case does not recreate an attempt after reset.")
    resetting["expected"]["trace_witnesses"] = [{"id": f"{action}_old_feedback", "lifecycle": [{"tick": 3, "slot": "e1", "action": action}],
        "observations": [], "feedback": [feedback(4, [(1, "completed"), (2, "failed")])],
        "creations_by_tick": [0, 2, 0, 0, 0, 0, 0],
        "final_attempts": [attempt(1, "e1", 0, 1, 3, status), attempt(2, "e2", 0, 1, 3, "timed_out")],
        "feedback_rejections": [{"tick": 4, "creation_ordinal": ordinal, "reason": "stale_attempt"} for ordinal in (1, 2)],
        "feedback_acceptances": []}
        for action, status in (("keep", "timed_out"), ("reset", "encounter_reset"), ("end", "encounter_ended"))]
    large_recreation = recreate(seed, contexts["extended_evidence_case"])
    cases = [extended, resetting, large_recreation, recreate_feedback(large_recreation)]
    for case in cases:
        refresh_expectations(case, seed)
        case["expected"]["check_expectation"] = "accepted"
    # Keep the original 486-history request and every literal trace unchanged.
    # No increase in its frozen 100m work limit and no retrospective narrowing
    # may convert an incomplete search into an accepted material artifact.
    large_recreation["expected"].update(check_expectation="incomplete", status="not_accepted",
        material_status="unassessed", context_status="unassessed",
        incomplete_code="policy_preservation_work_limit")
    return {"schema_version": "biocompiler.policy_material_domain_literals.v0.1",
        "notice": "Artificial supplied contracts and complete original domains. Source-only literal witnesses; hosted native acceptance pending. "
            "No biological viability claim. No saved candidate/report is production authority.",
        "limits": deepcopy(seed["limits"]), "cases": cases}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    encoded = json.dumps(build(), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.check:
        if OUTPUT.read_text() != encoded:
            raise SystemExit("Material domain literals differ from inert authoring source")
    else:
        OUTPUT.write_text(encoded)


if __name__ == "__main__":
    main()
