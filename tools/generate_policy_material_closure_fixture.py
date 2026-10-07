"""Author three complete supplied authorities; never run policy semantics.

The nine-node kernel below is an explicit primitive/wire literal. The two
fifteen-node cases preserve the existing complete supplied kernel and RNA.
No producer output, candidate, or saved report supplies production authority.
Counts and selected traces are independently authored expectations, not
executed evidence. The original broad UNKNOWN source case remains unchanged.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "core/test/data"
OUTPUT = DATA / "policy_material_closure_v01.json"
SEED_REQUEST = "754a3a30752855c3e9458c0b657a2e7ac850d6aebb27e260009e331296341e36"
ONE_RULE_CASE = "c815af2809aafb8893ad706a814d427ad37facc5a76b6761206a8c4cabc5ab4a"


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def pin(value: dict) -> None:
    value["identity"]["content_fingerprint"] = digest(value["body"])


def endpoint(node: str, port: str) -> dict:
    return {"node": "local." + node, "port": port}


def fixed_observations() -> list[dict]:
    return [{"slot": slot, "observation": "condition", "available_tick": tick,
        "observed_tick": tick, "status": "valid", "value": value}
        for tick, value in ((0, False), (1, True), (2, False)) for slot in ("e1", "e2")]


def one_rule_kernel(seed: dict, library: dict) -> dict:
    kernel = deepcopy(seed["request"]["material_contract"]["body"]["kernel"])
    models = {model["identity"]["id"]: model for model in library["models"]}
    names = ["evidence", "edge", "true", "product", "gate", "arbiter", "commit", "seen", "attempt"]
    assert set(models) == {"fixture.primitive." + name for name in names}
    kernel["library_digest"] = digest(library)
    kernel["nodes"] = [{"local_id": "local." + name,
        "model": deepcopy(models["fixture.primitive." + name])} for name in names]
    wires = [("evidence", "value", "edge", "in"), ("edge", "events", "gate", "on"),
        ("evidence", "value", "gate", "guard"), ("gate", "candidate", "arbiter", "in0"),
        ("arbiter", "out0", "commit", "grant"), ("true", "out", "commit", "value0"),
        ("product", "out", "commit", "product0"), ("commit", "write0", "seen", "write0"),
        ("commit", "request0", "attempt", "request"), ("evidence", "value", "attempt", "authorization")]
    kernel["wires"] = [{"from": endpoint(a, b), "to": endpoint(c, d)} for a, b, c, d in wires]
    kernel["inputs"] = [{"id": "condition", "kind": "evidence", "to": endpoint("evidence", "samples")},
        {"id": "feedback", "kind": "feedback", "to": endpoint("attempt", "feedback")}]
    kernel["atomic_groups"] = [{"id": "response", "arbiter": "local.arbiter", "commits": ["local.commit"]}]
    kernel["semantic_exports"] = [endpoint(node, port) for node, port in [
        ("evidence", "value"), ("evidence", "updated"), ("edge", "events"), ("true", "out"),
        ("product", "out"), ("gate", "candidate"), ("arbiter", "out0"), ("commit", "write0"),
        ("commit", "request0"), ("seen", "value"), ("attempt", "events"), ("attempt", "snapshot")]]
    return kernel


def carriers(kernel: dict, sites: list[dict]) -> list[dict]:
    targets = [{"kind": kind, "id": row["local_id"]} for row in kernel["nodes"]
        for kind in ("primitive", "configuration", "replication")]
    targets += [{"kind": "wire", "index": index} for index in range(len(kernel["wires"]))]
    targets += [{"kind": "external_input", "id": row["id"]} for row in kernel["inputs"]]
    targets += [{"kind": "atomic_group", "id": row["id"]} for row in kernel["atomic_groups"]]
    targets += [{"kind": "semantic_export", "index": index} for index in range(len(kernel["semantic_exports"]))]
    targets += [{"kind": "slot_layout"}]
    return [{"target": target, "sites": deepcopy(sites)} for target in targets]


def one_rule_resources() -> list[dict]:
    # Two slots; one edge, one gate, one write + one request. Queue is
    # 2*(2+1+1+1+2)+4*2+2=24, including both feedback inputs at tick2.
    rows = [("node", "local.seen", "truth_cells", "per_encounter_slot", 1),
        ("node", "local.evidence", "evidence_records", "per_encounter_slot", 3),
        ("node", "local.edge", "edge_history_cells", "per_encounter_slot", 1),
        ("layout", "layout", "generation_counters", "per_encounter_slot", 1),
        ("node", "local.attempt", "active_attempt_records", "per_encounter_slot", 8),
        ("node", "local.attempt", "retained_correlation_records", "per_executor", 2),
        ("node", "local.attempt", "timer_cells", "per_encounter_slot", 8),
        ("node", "local.evidence", "timer_cells", "per_encounter_slot", 1),
        ("layout", "layout", "timer_cells", "per_executor", 1),
        ("layout", "layout", "control_event_records", "per_executor", 24),
        ("input", "condition", "input_rows_per_tick", "per_encounter_slot", 1),
        ("input", "feedback", "input_rows_per_tick", "per_executor", 2)]
    return [{"id": f"{owner}.{unit}.{scope}", "owner": {"kind": kind, **({} if kind == "layout" else {"id": owner})},
        "unit": unit, "scope": scope, "quantity": quantity} for kind, owner, unit, scope, quantity in rows]


def rebind_context(request: dict, *, one_rule: bool, queue: int) -> None:
    original = request["implementation_request"]
    domain, source = original["operating_domain"], original["document"]
    contract, context = request["material_contract"], request["context"]
    body, kernel = contract["body"], contract["body"]["kernel"]
    horizon = domain["horizon_ticks"]
    prefix = "fixture" if one_rule else "exclusion"
    definitions = source["program"]["semantics"]["definitions"]
    refs = {row["id"]: {"$type": "DefinitionRef", "id": row["id"], "version": row["version"], "digest": digest(row)}
        for row in definitions}
    chassis_ref = refs[prefix + ".chassis"]
    if one_rule:
        body["allocations"] = [{"demand_id": row["id"], "capacity_id": row["id"], "provider": deepcopy(chassis_ref)}
            for row in body["resources"]]
    for row in body["input_witnesses"]:
        row["provider"] = deepcopy(refs[prefix + ".interface"])
    context["clock"]["original_clock"] = deepcopy(next(row for row in source["program"]["declarations"] if row["$type"] == "Clock"))
    layout = context["record_layout"]
    layout.update(kernel_digest=digest(kernel), domain_digest=digest(domain), slots=2,
        generations=domain["logical_limits"]["max_generations_per_slot"],
        attempts=domain["logical_limits"]["max_source_attempts"], horizon_ticks=horizon,
        maximum_tick=horizon + 2, ordered_reason_slots=1, ordered_cause_slots=queue * (horizon + 1), identifier_bytes=384)
    availability = {"onset_min": "0", "onset_max": "0", "duration_min": str(horizon), "duration_max": str(horizon)}
    demands = {row["id"]: row for row in body["resources"]}
    capacity_rows: dict[str, dict] = {}
    for allocation in body["allocations"]:
        allocation["provider"] = deepcopy(chassis_ref)
        demand = demands[allocation["demand_id"]]
        identity = allocation["capacity_id"]
        row = capacity_rows.setdefault(identity, {"id": identity, "pool_id": "executor.pool." + identity,
            "unit": demand["unit"], "scope": demand["scope"], "quantity": 0,
            "slots": ["e1", "e2"] if demand["scope"] == "per_encounter_slot" else [],
            "availability": deepcopy(availability), "record_layout_digest": digest(layout)})
        assert row["unit"] == demand["unit"] and row["scope"] == demand["scope"]
        row["quantity"] += demand["quantity"]
    for provider in context["providers"]:
        supplied = provider["body"]
        kind = supplied["kind"]
        supplied.update(definition=deepcopy(refs[prefix + "." + kind]), availability=deepcopy(availability))
        supplied["capacities"] = list(capacity_rows.values()) if kind == "chassis" else []
        if kind == "chassis":
            supplied["chassis"] = deepcopy(source["deployment"]["bindings"][0]["chassis"])
        elif kind == "environment":
            supplied["grammar"] = deepcopy(domain)
        elif kind == "interface":
            supplied["environment"] = deepcopy(refs[prefix + ".environment"])
            for channel in supplied["channels"]:
                channel["availability"] = deepcopy(availability)
        pin(provider)
    pin(contract)
    bridge = original["catalog_bindings"][0]
    request["catalog_binding"] = {key: deepcopy(bridge[key]) for key in
        ("entry_id", "entry_version", "entry_digest", "operation", "realization")}
    request["catalog_binding"]["material_contract"] = deepcopy(contract["identity"])


def oid(tick: int, index: int) -> str:
    return f"domain/observation/{tick}/{index}"


def attempt(ordinal: int, slot: str, start: int, end: int, status: str) -> dict:
    return {"creation_ordinal": ordinal, "slot": slot, "target": "target-1" if slot == "e1" else "target-2",
        "generation": 0, "started_tick": start, "deadline_tick": start + 2, "ended_tick": end, "status": status}


def snapshot(tick: int, observed: int, available: int, ids: list[str], value: str | None, reasons: list[str]) -> dict:
    return {"tick": tick, "slot": "e1", "observed_tick": observed, "available_tick": available,
        "occurrence_ids": ids, "defined": value is not None, "value": value, "reasons": reasons}


def trace(identity: str, rows: list[dict], *, third: bool, observed: int, available: int,
          retained: list[str], status: str, samples: list[tuple[int, str | None, list[str]]]) -> dict:
    # Every argument describing behavior is a literal below; this function only
    # formats repeated schema, identity and unchanged per-slot expectations.
    result = {"id": identity, "lifecycle": [], "observations": rows, "feedback": [],
        "creations_by_tick": [0, 2, 0, 1 if third else 0, 0, 0, 0],
        "final_attempts": [attempt(1, "e1", 1, 3, "timed_out"), attempt(2, "e2", 1, 3, "timed_out")]
            + ([attempt(3, "e1", 3, 5, "timed_out")] if third else []),
        "feedback_acceptances": [], "feedback_rejections": [],
        "evidence_snapshots": [snapshot(tick, observed, available, retained, value, reasons) for tick, value, reasons in samples],
        "observation_batches": [] if not rows else [{"tick": 3, "slot": "e1", "input_ids": [oid(3, i) for i in range(len(rows))],
            "retained_ids": retained, "observed_tick": observed, "status": status}],
        "state_snapshots": [{"tick": tick, "slot": slot, "source": state, "value": value}
            for tick in (3, 6) for slot in ("e1", "e2")
            for state, value in (("selected", "true" if third and slot == "e1" else "false"),
                                 ("excluded", "false" if third and slot == "e1" else "true"))]}
    return result


def row(observed: int, value: bool | None, status: str = "valid") -> dict:
    return {"tick": 3, "slot": "e1", "observed_tick": observed, "status": status, "value": value}


def age_traces() -> list[dict]:
    return [
        trace("silence", [], third=False, observed=2, available=2, retained=[oid(2, 0)], status="valid",
            samples=[(3, "false", []), (4, None, ["stale"])]),
        trace("newer_true", [row(3, True)], third=True, observed=3, available=3, retained=[oid(3, 0)], status="valid",
            samples=[(3, "true", []), (4, "true", []), (5, None, ["stale"])]),
        trace("tied_false", [row(2, False)], third=False, observed=2, available=3, retained=[oid(2, 0), oid(3, 0)], status="valid",
            samples=[(3, "false", []), (4, None, ["stale"])]),
        trace("tied_true_conflicts", [row(2, True)], third=False, observed=2, available=3, retained=[oid(2, 0), oid(3, 0)], status="conflicting",
            samples=[(3, None, ["conflicting"]), (4, None, ["conflicting"])]),
        trace("older_true_ignored", [row(1, True)], third=False, observed=2, available=2, retained=[oid(2, 0)], status="valid",
            samples=[(3, "false", []), (4, None, ["stale"])])]


def multiplicity_traces() -> list[dict]:
    retained = [oid(3, 0), oid(3, 1)]
    return [age_traces()[0],
        trace("double_true", [row(3, True), row(3, True)], third=True, observed=3, available=3, retained=retained, status="valid",
            samples=[(3, "true", []), (4, "true", []), (5, None, ["stale"])]),
        trace("false_then_true", [row(3, False), row(3, True)], third=False, observed=3, available=3, retained=retained, status="conflicting",
            samples=[(3, None, ["conflicting"]), (5, None, ["conflicting"])]),
        trace("true_then_false", [row(3, True), row(3, False)], third=False, observed=3, available=3, retained=retained, status="conflicting",
            samples=[(3, None, ["conflicting"]), (5, None, ["conflicting"])]),
        trace("double_false", [row(3, False), row(3, False)], third=False, observed=3, available=3, retained=retained, status="valid",
            samples=[(3, "false", []), (5, None, ["stale"])]),
        trace("missing_then_invalid", [row(3, None, "missing"), row(3, None, "invalid")], third=False,
            observed=3, available=3, retained=retained, status="conflicting",
            samples=[(3, None, ["conflicting"]), (5, None, ["conflicting"])]),
        trace("double_missing", [row(3, None, "missing"), row(3, None, "missing")], third=False,
            observed=3, available=3, retained=retained, status="missing",
            samples=[(3, None, ["missing"]), (5, None, ["missing"])])]


def one_rule_traces() -> list[dict]:
    result = []
    for identity, endings in (("mixed_feedback", [(2, "completed"), (2, "failed")]),
                              ("quiet_timeouts", [(3, "timed_out"), (3, "timed_out")])):
        result.append({"id": identity, "lifecycle": [], "observations": [],
            "feedback": [] if identity == "quiet_timeouts" else [{"tick": 2, "rows": [
                {"creation_ordinal": 1, "outcome": "completed"}, {"creation_ordinal": 2, "outcome": "failed"}]}],
            "creations_by_tick": [0, 2, 0, 0, 0],
            "final_attempts": [attempt(index + 1, slot, 1, end, status)
                for index, (slot, (end, status)) in enumerate(zip(("e1", "e2"), endings, strict=True))],
            "feedback_acceptances": [] if identity == "quiet_timeouts" else [
                {"tick": 2, "creation_ordinal": 1}, {"tick": 2, "creation_ordinal": 2}],
            "feedback_rejections": [], "observation_batches": [],
            "evidence_snapshots": [snapshot(4, 2, 2, [oid(2, 0)], None, ["stale"])],
            "state_snapshots": [{"tick": tick, "slot": slot, "source": "seen", "value": value}
                for tick, value in ((0, "false"), (1, "true"), (2, "true"), (4, "true")) for slot in ("e1", "e2")]})
    return result


def expectations(seed: dict, identity: str, request: dict, widths: list[int], witnesses: list[dict]) -> dict:
    original, body = request["implementation_request"], request["material_contract"]["body"]
    expected = deepcopy(seed["expected"])
    expected.pop("request_decoding_work")
    requirements = [row for row in original["document"]["program"]["declarations"] if row["$type"] == "Requirement"]
    if identity == "one_rule":
        # Independent inventory: the same four base + three request + nine
        # definition + one catalog + three state/effect/arbitration obligations,
        # but four original hard requirements instead of the sibling's three.
        obligations = [value.replace("exclusion.", "fixture.").replace(
            "fixture.response.primitives.resolved_chassis", "fixture.response.primitives")
            for value in expected["obligations"] if not value.startswith("requirement_satisfaction:")]
        obligations += ["requirement_satisfaction:" + value for value in
            ["request_progress", "initiation_progress", "request_authorization", "scoped_memory"]]
        expected["obligations"] = sorted(obligations)
        expected["context_discharges"] = [value.replace("exclusion.", "fixture.") for value in expected["context_discharges"]]
        assert len(expected["obligations"]) == 24
    layout = request["context"]["record_layout"]
    expected.update(request_fingerprint=digest(request), source_request_digest=digest(original),
        source_artifact_digest=digest(original["document"]), definitions_digest=digest(original["definitions"]),
        domain_digest=digest(original["operating_domain"]), library_digest=digest(original["implementation_library"]),
        material_contract_digest=digest(request["material_contract"]), context_digest=digest(request["context"]),
        kernel_digest=digest(body["kernel"]), carrier_digest=digest(body["carriers"]),
        node_count=len(body["kernel"]["nodes"]), wire_count=len(body["kernel"]["wires"]), carrier_count=len(body["carriers"]),
        requirements=deepcopy(requirements), requirement_ids=[row["id"] for row in requirements],
        histories=widths[-1], transitions=sum(widths), prefixes_started=1 + sum(widths), prefixes_after_tick=widths,
        horizon_ticks=original["operating_domain"]["horizon_ticks"], trace_witnesses=witnesses,
        resource_demands=deepcopy(body["resources"]), queue_records=next(row["quantity"] for row in body["resources"]
            if row["unit"] == "control_event_records"), ordered_cause_slots=layout["ordered_cause_slots"],
        ordered_reason_slots=1, maximum_tick=layout["maximum_tick"], identifier_bytes=384)
    return expected


def author_one(seed: dict, first: dict) -> dict:
    request = deepcopy(seed["request"])
    request["implementation_request"] = deepcopy(first["request"])
    original = request["implementation_request"]
    domain = original["operating_domain"]
    domain.update(fixed_observations=fixed_observations(), observation_factors=[], lifecycle_factors=[])
    domain["feedback_factors"][0]["ticks"] = [2]
    contract = request["material_contract"]
    contract["identity"]["id"] = "artificial.closure.one_rule"
    body = contract["body"]
    body["kernel"] = one_rule_kernel(seed, original["implementation_library"])
    body["carriers"] = carriers(body["kernel"], body["carriers"][0]["sites"])
    body["resources"] = one_rule_resources()
    rebind_context(request, one_rule=True, queue=24)
    assert original["document"] == first["request"]["document"]
    assert original["definitions"] == first["request"]["definitions"]
    assert len(body["carriers"]) == 53
    expected = expectations(seed, "one_rule", request, [1, 1, 9, 9, 9], one_rule_traces())
    expected["domain_claim"] = "Fixed false0/true1/false2 in both slots, followed by silence; each of the two prior attempts independently permits silence/completed/failed only at tick2. All four original hard requirements remain unchanged."
    return {"id": "one_rule", "request": request, "expected": expected}


def author_evidence(seed: dict, *, multiplicity: bool) -> dict:
    identity = "ordered_multiplicity" if multiplicity else "aged_evidence"
    request = deepcopy(seed["request"])
    original = request["implementation_request"]
    domain = original["operating_domain"]
    domain["feedback_factors"] = []
    domain["logical_limits"]["max_source_attempts"] = 3
    domain["observation_factors"] = [{"slots": ["e1"], "observation": "condition", "ticks": [3],
        "alphabet": "known_truth_and_evidence_status.v1", "age_ticks": [0] if multiplicity else [0, 1, 2],
        "max_rows_per_slot_tick": 2 if multiplicity else 1}]
    contract = request["material_contract"]
    contract["identity"]["id"] = "artificial.closure." + identity
    # Repeated equal input values still consume distinct occurrence records.
    # The two source edges, two gates and five writes/requests are unchanged.
    # No feedback factor exists, but the actual feedback port still requires
    # one typed input row capacity. It contributes zero events to queue maxima.
    # Age: 2*(2+1+2+2+5)+4*3+0=36, causes=252, evidence=3+1.
    # Multiplicity: 2*(2+2+2+2+5)+4*3+0=38, causes=266, evidence=3+2.
    queue = 38 if multiplicity else 36
    for resource in contract["body"]["resources"]:
        if resource["unit"] == "evidence_records":
            resource["quantity"] = 5 if multiplicity else 4
        elif resource["unit"] == "retained_correlation_records":
            resource["quantity"] = 3
        elif resource["unit"] == "control_event_records":
            resource["quantity"] = queue
        elif resource["unit"] == "input_rows_per_tick":
            resource["quantity"] = 2 if multiplicity and resource["owner"]["id"] == "condition" else 1
    rebind_context(request, one_rule=False, queue=queue)
    count = 31 if multiplicity else 16  # 1+5+5^2 versus 1+3*5.
    expected = expectations(seed, identity, request, [1, 1, 1, count, count, count, count],
        multiplicity_traces() if multiplicity else age_traces())
    expected["domain_claim"] = ("Fixed false0/true1/false2 in both slots. At tick3 e1 independently permits silence or every ordered zero-to-two-row evidence batch at age0. Feedback is explicitly silent; no permitted history is filtered."
        if multiplicity else "Fixed false0/true1/false2 in both slots. At tick3 e1 independently permits silence or one row of every evidence class at each age0/1/2. Feedback is explicitly silent; no permitted history is filtered.")
    return {"id": identity, "request": request, "expected": expected}


def validate_authoring(case: dict, seed: dict) -> None:
    request = case["request"]
    original, contract, context = request["implementation_request"], request["material_contract"], request["context"]
    body = contract["body"]
    assert contract["identity"]["content_fingerprint"] == digest(body)
    assert request["catalog_binding"]["material_contract"] == contract["identity"]
    assert body["kernel"]["library_digest"] == digest(original["implementation_library"])
    assert context["record_layout"]["domain_digest"] == digest(original["operating_domain"])
    assert context["record_layout"]["kernel_digest"] == digest(body["kernel"])
    assert body["structure_authority"] == seed["request"]["material_contract"]["body"]["structure_authority"]
    assert body["material_key"] == seed["expected"]["molecules"]
    for model in original["implementation_library"]["models"]:
        assert model["identity"]["content_fingerprint"] == digest(model["body"])
        assert model["configuration_digest"] == digest(model["body"]["configuration"])
    for provider in context["providers"]:
        assert provider["identity"]["content_fingerprint"] == digest(provider["body"])
        if provider["body"]["kind"] == "environment":
            assert provider["body"]["grammar"] == original["operating_domain"]
        for capacity in provider["body"]["capacities"]:
            assert capacity["record_layout_digest"] == digest(context["record_layout"])
            assert capacity["quantity"] == sum(resource["quantity"] for allocation in body["allocations"]
                if allocation["capacity_id"] == capacity["id"] for resource in body["resources"]
                if resource["id"] == allocation["demand_id"])
    if case["id"] != "one_rule":
        for key in ("document", "definitions", "implementation_library", "catalog_bindings"):
            assert original[key] == seed["request"]["implementation_request"][key]
        for key in ("kernel", "carriers", "products", "input_witnesses", "allocations"):
            assert body[key] == seed["request"]["material_contract"]["body"][key]


def build() -> dict:
    seed = json.loads((DATA / "policy_material_request_v01.json").read_text())
    first = json.loads((DATA / "policy_implementation_binding_v01.json").read_text())["cases"][0]
    if digest(seed["request"]) != SEED_REQUEST or digest(first) != ONE_RULE_CASE:
        raise ValueError("Frozen source authority changed; independently review before regeneration")
    cases = [author_one(seed, first), author_evidence(seed, multiplicity=False), author_evidence(seed, multiplicity=True)]
    for case in cases:
        validate_authoring(case, seed)
    return {"schema_version": "biocompiler.policy_material_closure_literals.v0.1",
        "notice": "Artificial independently supplied original contracts and bounded domains; source-only expectations, hosted acceptance pending. "
            "The original broad UNKNOWN witness is unchanged. No empirical realization or broader language support is asserted.",
        "limits": deepcopy(seed["limits"]), "cases": cases}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    encoded = json.dumps(build(), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.check:
        if OUTPUT.read_text() != encoded:
            raise SystemExit("Closure fixture differs from inert authoring source")
    else:
        OUTPUT.write_text(encoded)


if __name__ == "__main__":
    main()
