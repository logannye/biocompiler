"""Author a complete state-reading material authority without executing policy.

The original three hard requirements and complete nine-history environment are
unchanged. The supplied kernel is edited by explicit wire literals, never from
producer output. Expected state, phase and attempt values below are hand-authored
semantic witnesses; only hosted native execution can establish acceptance.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "core/test/data"
OUTPUT = DATA / "policy_material_state_v01.json"
SEED_REQUEST = "754a3a30752855c3e9458c0b657a2e7ac850d6aebb27e260009e331296341e36"


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def pin(value: dict) -> None:
    value["identity"]["content_fingerprint"] = digest(value["body"])


def endpoint(node: str, port: str = "out") -> dict:
    return {"node": "local." + node, "port": port}


def expression(prototype: dict, operator: str, arguments: list[dict]) -> dict:
    result = deepcopy(prototype)
    result.update(op=operator, args=deepcopy(arguments), value=None, ref=None, scope=None)
    return result


def build() -> dict:
    seed = json.loads((DATA / "policy_material_request_v01.json").read_text())
    if digest(seed["request"]) != SEED_REQUEST:
        raise ValueError("Original authority changed; independently review before regeneration")
    request = deepcopy(seed["request"])
    original = request["implementation_request"]
    document = original["document"]
    declarations = {row["id"]: row for row in document["program"]["declarations"]}
    selected = deepcopy(declarations["exclusive_selection"]["condition"]["args"][0]["args"][0])
    assert selected["op"] == "state" and selected["ref"]["id"] == "selected"
    select = declarations["select"]
    select["assignments"][1]["value"] = deepcopy(selected)
    select["when"] = expression(select["when"], "all", [select["when"],
        expression(select["when"], "not", [selected])])
    document["program"]["id"] = "state.prestate_and_guard"
    for span in document["program"]["source_map"]:
        span["file"] = "policy_state_prestate_and_guard.py"

    library = original["implementation_library"]
    library["id"] = "state.complete.library"
    prototype = deepcopy(next(model for model in library["models"] if model["body"]["primitive"] == "truth_not"))
    all_model = deepcopy(prototype)
    all_model["identity"]["id"] = "state.primitive.all2"
    all_model["body"].update(primitive="truth_all", configuration={"arity": 2})
    all_model["configuration_digest"] = digest(all_model["body"]["configuration"])
    pin(all_model)
    library["models"].append(all_model)
    original["catalog_bindings"][0]["models"] = [deepcopy(model["identity"]) for model in library["models"]]
    contract = request["material_contract"]
    contract["identity"]["id"] = "artificial.state.prestate_and_guard"
    body = contract["body"]
    kernel = body["kernel"]
    kernel["library_digest"] = digest(library)
    kernel["nodes"].extend([
        {"local_id": "local.selected_not", "model": prototype},
        {"local_id": "local.select_guard", "model": deepcopy(all_model)}])
    replacements = {
        ("local.select_commit", "value1"): endpoint("selected", "value"),
        ("local.select_gate", "guard"): endpoint("select_guard"),
        ("local.attempt", "authorization"): endpoint("select_guard"),
    }
    for wire in kernel["wires"]:
        key = (wire["to"]["node"], wire["to"]["port"])
        if key in replacements:
            wire["from"] = deepcopy(replacements[key])
    kernel["wires"].extend([
        {"from": endpoint("selected", "value"), "to": endpoint("selected_not", "in")},
        {"from": endpoint("evidence", "value"), "to": endpoint("select_guard", "in0")},
        {"from": endpoint("selected_not"), "to": endpoint("select_guard", "in1")}])
    kernel["semantic_exports"].extend([endpoint("selected_not"), endpoint("select_guard")])
    targets = [{"kind": kind, "id": row["local_id"]} for row in kernel["nodes"]
        for kind in ("primitive", "configuration", "replication")]
    targets += [{"kind": "wire", "index": index} for index in range(len(kernel["wires"]))]
    targets += [{"kind": "external_input", "id": row["id"]} for row in kernel["inputs"]]
    targets += [{"kind": "atomic_group", "id": row["id"]} for row in kernel["atomic_groups"]]
    targets += [{"kind": "semantic_export", "index": index} for index in range(len(kernel["semantic_exports"]))]
    targets += [{"kind": "slot_layout"}]
    sites = deepcopy(body["carriers"][0]["sites"])
    body["carriers"] = [{"target": target, "sites": deepcopy(sites)} for target in targets]
    pin(contract)
    request["catalog_binding"]["material_contract"] = deepcopy(contract["identity"])
    # Pure truth nodes add no persistent/control category. The complete queue
    # remains 2*(2+1+2+2+5)+4*2+2=34; causes=34*7=238; reason width=1+0=1.
    context = request["context"]
    context["record_layout"]["kernel_digest"] = digest(kernel)
    for provider in context["providers"]:
        for capacity in provider["body"]["capacities"]:
            capacity["record_layout_digest"] = digest(context["record_layout"])
        pin(provider)
    requirements = [row for row in document["program"]["declarations"] if row["$type"] == "Requirement"]
    base = seed["request"]["implementation_request"]
    assert requirements == [row for row in base["document"]["program"]["declarations"] if row["$type"] == "Requirement"]
    assert original["definitions"] == base["definitions"]
    assert original["operating_domain"] == base["operating_domain"]
    assert original["budgets"] == base["budgets"]
    assert body["resources"] == seed["request"]["material_contract"]["body"]["resources"]
    assert len(kernel["nodes"]) == 17 and len(kernel["wires"]) == 25 and len(targets) == 103
    expected = deepcopy(seed["expected"])
    expected.pop("request_decoding_work")
    expected.update(request_fingerprint=digest(request), source_request_digest=digest(original),
        source_artifact_digest=digest(document), definitions_digest=digest(original["definitions"]),
        domain_digest=digest(original["operating_domain"]), library_digest=digest(library),
        material_contract_digest=digest(contract), context_digest=digest(context), kernel_digest=digest(kernel),
        carrier_digest=digest(body["carriers"]), node_count=17, wire_count=25, carrier_count=103,
        requirements=deepcopy(requirements), histories=9, transitions=47, prefixes_started=48,
        prefixes_after_tick=[1, 1, 9, 9, 9, 9, 9], resource_demands=deepcopy(body["resources"]),
        queue_records=34, ordered_cause_slots=238, ordered_reason_slots=1, maximum_tick=8, identifier_bytes=384,
        state_occurrences=[
            {"source_path": "/document/program/declarations/9/assignments/1/value", "role": "state_write"},
            {"source_path": "/document/program/declarations/9/when/args/1/args/0", "role": "predicate"}],
        # Tick1 reads selected=false for both the guard and second write;
        # the settled selected=true then deauthorizes each continuing attempt.
        settled_states=[{"tick": tick, "slot": slot, "selected": selected_value, "excluded": excluded}
            for tick, selected_value, excluded in [(0, "false", "false"), (1, "true", "false")]
                + [(tick, "false", "true") for tick in range(2, 7)] for slot in ("e1", "e2")],
        guard_by_tick=["false", "false", "false", "false", "unknown", "unknown", "unknown"],
        trace_witnesses=[{"id": identity, "feedback": feedback,
            "final_attempts": [{"creation_ordinal": index + 1, "slot": slot, "target": "target-1" if slot == "e1" else "target-2",
                "generation": 0, "started_tick": 1, "deadline_tick": 3, "ended_tick": end, "status": status,
                "authorization": "false"} for index, (slot, end, status) in enumerate(endings)]}
            for identity, feedback, endings in [
                ("quiet_timeout", [], [("e1", 3, "timed_out"), ("e2", 3, "timed_out")]),
                ("mixed_feedback", [{"creation_ordinal": 1, "outcome": "completed"},
                    {"creation_ordinal": 2, "outcome": "failed"}], [("e1", 2, "completed"), ("e2", 2, "failed")])]])
    return {"schema_version": "biocompiler.policy_material_state_literals.v0.1",
        "notice": "Artificial separately supplied authority and literal prestate/guard expectations; hosted acceptance pending. No empirical claim.",
        "limits": deepcopy(seed["limits"]), "request": request, "expected": expected}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    encoded = json.dumps(build(), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.check:
        if OUTPUT.read_text() != encoded:
            raise SystemExit("State fixture differs from inert authoring source")
    else:
        OUTPUT.write_text(encoded)


if __name__ == "__main__":
    main()
