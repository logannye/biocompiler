"""Author explicit artificial staged material premises without native execution.

Only immutable RNA, chemistry and template declarations are borrowed from the
reviewed synthetic seed. Staged models, component carriers, graph connectivity,
source/domain and provider resources are new supplied conditional premises.
Nothing here infers biological behavior from an RNA sequence.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from biocompiler import policy as p
try:
    from generate_policy_staged_regimen_fixture import build_program
except ModuleNotFoundError:
    from tools.generate_policy_staged_regimen_fixture import build_program

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "core/test/data"
SEED_SHA256 = "d03cdf56a0a5cbbfab5ce5bdd9585ef85bf493e88464005b9147aa7dd3ecfe4a"
ORIGINAL_REQUEST_DIGEST = "754a3a30752855c3e9458c0b657a2e7ac850d6aebb27e260009e331296341e36"
REALIZATION = DATA / "policy_staged_realization_request_v01.json"
OUTPUT = DATA / "policy_staged_material_v01.json"
PROFILE = "biocompiler.policy_staged_primitives.v0.1"
OBSERVABLE = "biocompiler.policy_staged_observables.v0.1"
PHASE = "biocompiler.policy_staged_primitive_execution.v0.1"
STATES = ["ready", "first", "second", "completed", "failed"]
TRANSITIONS = [
    ("start", "ready", "first", "unbound", 1),
    ("handoff", "first", "second", "retained_attempt", 1),
    ("completed", "second", "completed", "retained_attempt", 0),
    ("first_failed", "first", "failed", "retained_attempt", 0),
    ("second_failed", "second", "failed", "retained_attempt", 0),
    ("first_timed_out", "first", "failed", "retained_attempt", 0),
    ("second_timed_out", "second", "failed", "retained_attempt", 0),
]


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def pin(kind: str, identity: str, body: object) -> dict:
    return {"schema_version": "biocompiler.component_identity.v0.1", "kind": kind,
            "id": identity, "version": "1", "content_fingerprint": digest(body)}


def original() -> dict:
    value = json.loads((DATA / "policy_material_request_v01.json").read_text())
    assert digest(value["request"]) == ORIGINAL_REQUEST_DIGEST, "Review changed original authority before reuse"
    return value


def model(name: str, primitive: str, configuration: dict, *, executor: bool = False) -> dict:
    body = {"schema_version": "biocompiler.policy_primitive_model.v0.1",
        "profile": PROFILE if primitive in ("machine_bank", "transition_gate", "transition_commit") else "biocompiler.policy_truth_primitives.v0.1",
        "primitive": primitive, "configuration": configuration,
        "replication": {"kind": "executor"} if executor else {"kind": "encounter_slots", "layout_id": "encounters", "slots": 2}}
    return {"identity": pin("model", "staged.primitive." + name, body),
            "configuration_digest": digest(configuration), "body": body}


def models() -> dict:
    values = [
        model("evidence", "evidence_bank", {"freshness_ticks": 10}),
        model("machine", "machine_bank", {"states": STATES, "initial": "ready", "terminal": ["completed", "failed"], "writers": 7, "retained_capacity": 1}),
        model("edge", "observed_rising", {}), model("true", "truth_constant", {"value": "true"}),
        model("product", "product_constant", {"product": "fixture.product.alpha"}, executor=True),
        model("arbiter", "exclusive_arbiter", {"lanes": 7}),
        model("attempt", "attempt_bank", {"capacity": 4, "timeout_ticks": 2, "authorization": "continuous", "on_loss": "continue", "on_unknown": "defer"}),
    ]
    for source, correlation in (("ready", "unbound"), ("first", "retained_attempt"), ("second", "retained_attempt")):
        values.append(model("gate." + source, "transition_gate", {"source": source, "correlation": correlation}))
    for destination, requests in (("first", 1), ("second", 1), ("completed", 0), ("failed", 0)):
        values.append(model("commit." + destination, "transition_commit", {"destination": destination, "writes": 0, "requests": requests}))
    for event in ("completed", "failed", "timed_out"):
        values.append(model("event." + event, "event_select", {"event_kind": event}))
    return {"schema_version": "biocompiler.policy_implementation_library.v0.1", "profile": PROFILE,
            "id": "staged.supplied.library", "version": "1", "models": values}


def build_request() -> p.BuildRequest:
    base = p.from_data(original()["request"]["implementation_request"]["document"], p.BuildRequest)
    program = build_program()
    definition = replace(next(value for value in program.semantics.definitions if value.category == "operation"),
                         parameters=(p.Parameter("product", p.TEXT),))
    parameter = p.Parameter("product", p.TEXT, value="fixture.product.alpha")
    argument = p.Argument("product", p.Expr("parameter", p.TEXT, ref=p.ref(parameter)))
    declarations = []
    for declaration in program.declarations:
        if isinstance(declaration, p.Effect):
            declaration = replace(declaration, contract=definition.ref, parameters=(argument,))
        elif isinstance(declaration, p.Transition) and declaration.id == "regimen/handoff":
            declaration = replace(declaration, when=p.TRUE)
        elif isinstance(declaration, p.Requirement):
            declaration = replace(declaration, horizon=p.quantity(5, p.SECOND))
        declarations.append(declaration)
    declarations.insert(5, parameter)
    definitions = tuple(definition if value.category == "operation" else value for value in program.semantics.definitions)
    definitions += tuple(value for value in base.program.semantics.definitions if value.id in
                         ("exclusion.chassis", "exclusion.environment", "exclusion.delivery", "fixture.realization.primitives"))
    program = replace(program, id="bounded_staged_material", declarations=tuple(declarations),
        semantics=replace(program.semantics, definitions=definitions), source_map=tuple(
            p.SourceSpan(value.id, "staged_material_original.py", index + 1, pattern="regimen" if value.id.startswith("regimen/") else None)
            for index, value in enumerate(declarations)))
    interface = next(value.ref for value in definitions if value.category == "interface")
    chassis = replace(base.deployment.bindings[0].chassis, capabilities=(interface,), interfaces=(interface,))
    deployment = replace(base.deployment, bindings=(replace(base.deployment.bindings[0], chassis=chassis),))
    entry = replace(base.implementations.implementations[0], id="staged.same_product.primitives", operation=definition.ref)
    return replace(base, program=program, deployment=deployment,
        implementations=replace(base.implementations, id="staged.supplied.catalog", implementations=(entry,)),
        assurance=replace(base.assurance, requirements=("first_initiation", "second_initiation"), horizon=p.quantity(5, p.SECOND)))


def realization() -> dict:
    base = original()["request"]["implementation_request"]
    request = deepcopy(base)
    document = p.to_data(build_request())
    request["document"] = document
    request["definitions"]["definitions"] = [{"definition": p.to_data(value.ref), "semantics": tag} for value, tag in
        zip(build_request().program.semantics.definitions[:5], ("capability.deferred.v1", "encounter.explicit.v1",
            "observation.external_evidence.v1", "effect.abstract_attempt.v1", "lifecycle.correlated_feedback.v1"))]
    request["implementation_library"] = models()
    entry = document["implementations"]["implementations"][0]
    request["catalog_bindings"] = [{"entry_id": entry["id"], "entry_version": entry["version"], "entry_digest": digest(entry),
        "operation": entry["operation"], "realization": entry["realization"],
        "models": [value["identity"] for value in request["implementation_library"]["models"]]}]
    domain = request["operating_domain"]
    domain["horizon_ticks"] = 5
    domain["logical_limits"]["max_source_attempts"] = 4
    domain["fixed_observations"] = [row for row in domain["fixed_observations"] if row["available_tick"] < 2]
    prototype = domain["feedback_factors"][0]
    domain["feedback_factors"] = [{**deepcopy(prototype), "effect": effect, "ticks": [tick]}
                                 for effect, tick in (("stage_one", 2), ("stage_two", 3))]
    return request


def endpoint(node: str, port: str) -> dict:
    return {"node": node, "port": port}


def wire(source: str, output: str, target: str, input_port: str) -> dict:
    return {"producer": endpoint(source, output), "consumer": endpoint(target, input_port)}


def output_ports(value: dict) -> list[str]:
    primitive, config = value["body"]["primitive"], value["body"]["configuration"]
    fixed = {"evidence_bank": ["value", "updated"], "machine_bank": ["snapshot"], "observed_rising": ["events"],
             "truth_constant": ["out"], "product_constant": ["out"], "attempt_bank": ["events", "snapshot"],
             "transition_gate": ["candidate"], "event_select": ["selected"]}
    if primitive == "exclusive_arbiter":
        return ["out" + str(index) for index in range(config["lanes"])]
    if primitive == "transition_commit":
        return ["request" + str(index) for index in range(config["requests"])] + ["machine_write"]
    return fixed[primitive]


def fragment(identity: str, nodes: list, wires: list, boundaries: list, inputs: list, groups: list) -> dict:
    return {"schema_version": "biocompiler.policy_component_fragment.v0.1", "profile": "biocompiler.policy_staged_fragment.v0.1",
        "primitive_profile": PROFILE, "observable_profile": OBSERVABLE, "phase_profile": PHASE,
        "id": identity, "version": "1", "slot_layout": {"id": "encounters", "slots": 2},
        "nodes": nodes, "wires": wires, "boundary_ports": boundaries, "external_slots": inputs, "atomic_groups": groups,
        "semantic_exports": [endpoint(node["id"], port) for node in nodes for port in output_ports(node["model"])]}


def boundary(identity: str, direction: str, signal: str, node: str, port: str) -> dict:
    return {"id": identity, "direction": direction, "signal_type": signal, "endpoint": endpoint(node, port)}


def fragments(library: dict) -> tuple[dict, dict]:
    by_model = {value["identity"]["id"].removeprefix("staged.primitive."): value for value in library["models"]}
    def node(identity, name):
        return {"id": identity, "model": deepcopy(by_model[name])}
    decision_nodes = [node(name, name) for name in ("evidence", "machine", "edge", "true", "arbiter")]
    decision_wires = [wire("evidence", "value", "edge", "in")]
    for index, (_, source, destination, _, _) in enumerate(TRANSITIONS):
        gate, commit = f"t{index}_gate", f"t{index}_commit"
        decision_nodes += [node(gate, "gate." + source), node(commit, "commit." + destination)]
        decision_wires += [wire("machine", "snapshot", gate, "machine"),
            wire("evidence" if index == 0 else "true", "value" if index == 0 else "out", gate, "guard"),
            wire(gate, "candidate", "arbiter", f"in{index}"), wire("arbiter", f"out{index}", commit, "grant"),
            wire(commit, "machine_write", "machine", f"write{index}")]
        if index == 0:
            decision_wires.append(wire("edge", "events", gate, "on"))
    driver_nodes = [node("product", "product"), node("first", "attempt"), node("second", "attempt")]
    driver_wires = []
    decision_boundaries, driver_boundaries = [], [boundary("product", "output", "product_symbol", "product", "out")]
    events = (("completed", 1, 2), ("failed", 3, 4), ("timed_out", 5, 6))
    for stage, bank in enumerate(("first", "second")):
        prefix = f"stage{stage}."
        decision_boundaries += [boundary(prefix + "product", "input", "product_symbol", f"t{stage}_commit", "product0"),
            boundary(prefix + "request", "output", "effect_request", f"t{stage}_commit", "request0"),
            boundary(prefix + "authorization", "output", "truth_value", "evidence" if stage == 0 else "true", "value" if stage == 0 else "out")]
        driver_boundaries += [boundary(prefix + "request", "input", "effect_request", bank, "request"),
            boundary(prefix + "authorization", "input", "truth_value", bank, "authorization")]
        for event, first_lane, second_lane in events:
            selector = bank + "_" + event
            driver_nodes.append(node(selector, "event." + event))
            driver_wires.append(wire(bank, "events", selector, "events"))
            driver_boundaries.append(boundary(prefix + event, "output", "event_batch", selector, "selected"))
            decision_boundaries.append(boundary(prefix + event, "input", "event_batch", f"t{first_lane if stage == 0 else second_lane}_gate", "on"))
    decision = fragment("staged.decision", decision_nodes, decision_wires, decision_boundaries,
        [{"id": "condition", "kind": "evidence", "consumer": endpoint("evidence", "samples")}],
        [{"id": "staged_selection", "arbiter": "arbiter", "commits": [f"t{i}_commit" for i in range(7)]}])
    driver = fragment("staged.driver", driver_nodes, driver_wires, driver_boundaries,
        [{"id": bank + "_feedback", "kind": "feedback", "consumer": endpoint(bank, "feedback")} for bank in ("first", "second")], [])
    assert len(decision["nodes"]) == 19 and len(driver["nodes"]) == 9
    assert len(decision["wires"]) == 37 and len(driver["wires"]) == 6
    return decision, driver


def prerequisites(value: dict) -> list:
    result = [{"kind": "input", "id": row["id"] + ".input", "external_slot": row["id"]} for row in value["external_slots"]]
    def capacity(kind, identity, unit, scope, minimum):
        return {"kind": "capacity", "id": identity + "." + unit + "." + scope,
            "owner": {"kind": kind, "id": identity}, "unit": unit, "scope": scope, "minimum": minimum}
    result += [capacity("external_slot", row["id"], "input_rows_per_tick",
        "per_encounter_slot" if row["kind"] == "evidence" else "per_executor", 1) for row in value["external_slots"]]
    # This is the independently supplied resource premise, in literal node order.
    specifications = {"evidence_bank": [("evidence_records", "per_encounter_slot", 1), ("timer_cells", "per_encounter_slot", 1)],
        "machine_bank": [("machine_state_bits", "per_encounter_slot", 3), ("machine_correlation_records", "per_encounter_slot", 1)],
        "observed_rising": [("edge_history_cells", "per_encounter_slot", 1)],
        "attempt_bank": [("active_attempt_records", "per_encounter_slot", 4), ("retained_correlation_records", "per_executor", 1),
                         ("timer_cells", "per_encounter_slot", 4)]}
    for node in value["nodes"]:
        result += [capacity("node", node["id"], unit, scope, count) for unit, scope, count in specifications.get(node["model"]["body"]["primitive"], [])]
    return result


def component(slot: str, value: dict, seed: dict) -> dict:
    root = deepcopy(seed["roots"][slot])
    feature = "utr5" if slot == "decision" else "cds"
    material_path = deepcopy(next(row["path"] for row in root["molecule"]["features"] if row["id"] == feature))
    site = {"root": root["id"], "feature": feature, "path": material_path}
    targets = [{"kind": kind, "id": row["id"]} for row in value["nodes"] for kind in ("primitive", "configuration", "replication")]
    targets += [{"kind": "local_wire", "index": index} for index in range(len(value["wires"]))]
    targets += [{"kind": "external_slot", "id": row["id"]} for row in value["external_slots"]]
    targets += [{"kind": "boundary_port", "id": row["id"]} for row in value["boundary_ports"]]
    targets += [{"kind": "atomic_group", "id": row["id"]} for row in value["atomic_groups"]]
    targets += [{"kind": "semantic_export", "index": index} for index in range(len(value["semantic_exports"]))] + [{"kind": "slot_layout"}]
    body = {"fragment": value, "root": root, "carriers": [{"target": target, "sites": [deepcopy(site)]} for target in targets],
            "products": deepcopy(seed["products"]) if slot == "driver" else [], "provider_requirements": prerequisites(value)}
    return {"schema_version": "biocompiler.policy_component_material.v0.1", "profile": "biocompiler.policy_exact_local_material.v0.1",
            "identity": pin("model", "staged." + slot + ".supplied_material", body), "body": body}


def rule(components: dict, seed: dict) -> dict:
    links = []
    for stage in range(2):
        for kind, source, target, signal, scope in (
            ("product", "driver", "decision", "product_symbol", "immutable_executor_broadcast"),
            ("request", "decision", "driver", "effect_request", "same_encounter_slot"),
            ("authorization", "decision", "driver", "truth_value", "same_encounter_slot"),
            ("completed", "driver", "decision", "event_batch", "same_encounter_slot"),
            ("failed", "driver", "decision", "event_batch", "same_encounter_slot"),
            ("timed_out", "driver", "decision", "event_batch", "same_encounter_slot")):
            identity = f"stage{stage}." + kind
            links.append({"id": identity, "producer": {"slot": source, "boundary": "product" if kind == "product" else identity},
                "consumer": {"slot": target, "boundary": identity}, "signal_type": signal, "scope": scope})
    local = {slot: value["body"]["fragment"] for slot, value in components.items()}
    body = {"primitive_profile": PROFILE, "observable_profile": OBSERVABLE, "phase_profile": PHASE,
        "transport_profile": "biocompiler.policy_identity_transport.v0.1", "slot_layout": {"id": "encounters", "slots": 2},
        "components": [{"slot": slot, "component": value["identity"]} for slot, value in components.items()], "links": links,
        "node_order": [{"slot": slot, "node": row["id"]} for slot, value in local.items() for row in value["nodes"]],
        "wire_order": [{"kind": "local", "slot": slot, "index": index} for slot, value in local.items() for index in range(len(value["wires"]))]
            + [{"kind": "link", "id": row["id"]} for row in links],
        "input_order": [{"slot": slot, "external_slot": row["id"], "id": row["id"]} for slot, value in local.items() for row in value["external_slots"]],
        "group_order": [{"slot": "decision", "group": "staged_selection"}],
        "export_order": [{"slot": slot, **row} for slot, value in local.items() for row in value["semantic_exports"]],
        "root_bindings": [{"slot": slot, "source": seed["roots"][slot]["id"]} for slot in components],
        "join": {"id": "leader_to_driver", "step": "join", "port": "joined", "left": "decision", "right": "driver", "offset": 2},
        "link_carriers": [{"link": row["id"], "producer_site": 0, "consumer_site": 0, "join": "leader_to_driver"} for row in links],
        "material_authority": deepcopy(seed["material_authority"])}
    return {"schema_version": "biocompiler.policy_component_assembly_rule.v0.1", "profile": "biocompiler.policy_staged_component_assembly.v0.1",
            "identity": pin("model", "staged.supplied_assembly", body), "body": body}


def ordered_union(components: dict, assembly: dict) -> dict:
    local = {slot: value["body"]["fragment"] for slot, value in components.items()}
    def resolve(reference):
        row = next(row for row in local[reference["slot"]]["boundary_ports"] if row["id"] == reference["boundary"])
        return {"slot": reference["slot"], **row["endpoint"]}
    wires = [{"producer": {"slot": slot, **row["producer"]}, "consumer": {"slot": slot, **row["consumer"]}}
             for slot, value in local.items() for row in value["wires"]]
    wires += [{"producer": resolve(row["producer"]), "consumer": resolve(row["consumer"])} for row in assembly["body"]["links"]]
    return {"schema_version": "biocompiler.policy_component_ordered_union.v0.1", "primitive_profile": PROFILE,
        "observable_profile": OBSERVABLE, "phase_profile": PHASE, "transport_profile": "biocompiler.policy_identity_transport.v0.1",
        "slot_layout": {"id": "encounters", "slots": 2},
        "nodes": [{"slot": slot, "node": row["id"], "model": row["model"]} for slot, value in local.items() for row in value["nodes"]],
        "wires": wires, "inputs": [{"id": row["id"], "kind": row["kind"], "consumer": {"slot": slot, **row["consumer"]}}
            for slot, value in local.items() for row in value["external_slots"]],
        "atomic_groups": [{"slot": "decision", "id": "staged_selection", "arbiter": {"slot": "decision", "node": "arbiter"},
            "commits": [{"slot": "decision", "node": f"t{i}_commit"} for i in range(7)]}],
        "semantic_exports": assembly["body"]["export_order"], "links": assembly["body"]["links"]}


def context_and_bindings(original_request: dict, components: dict, assembly: dict, union: dict) -> tuple[dict, list, list]:
    context = deepcopy(original()["request"]["context"])
    document, domain = original_request["document"], original_request["operating_domain"]
    interface = next(row["definition"] for row in original_request["definitions"]["definitions"] if row["semantics"] == "capability.deferred.v1")
    context.update(schema_version="biocompiler.policy_component_context.v0.1", profile="biocompiler.policy_staged_component_mrna.v0.1")
    context["clock"]["original_clock"] = next(row for row in document["program"]["declarations"] if row["$type"] == "Clock")
    context["placement"]["template_id"] = assembly["body"]["material_authority"]["template"]["id"]
    shapes = context["record_layout"]["record_shapes"]
    for key in ("active_attempt_records", "retained_correlation_records"):
        shapes[key].append("machine_bank")
    shapes["control_event_records"] += ["machine_bank", "source_state_index", "destination_state_index", "ordered_retained_attempt_ids"]
    shapes["machine_state_bits"] = ["machine_bank", "scope_slot_generation", "state_index"]
    shapes["machine_correlation_records"] = ["machine_bank", "scope_slot_generation", "attempt_id"]
    context["record_layout"] = {"profile": "biocompiler.policy_staged_component_complete_records.v0.1", "record_shapes": shapes,
        "rule": assembly["identity"], "union_digest": digest(union), "domain_digest": digest(domain), "slots": 2, "generations": 2,
        "attempts": 4, "horizon_ticks": 5, "maximum_tick": 15, "ordered_reason_slots": 1, "ordered_cause_slots": 384, "identifier_bytes": 512}
    availability = {"duration_min": "5", "duration_max": "5", "onset_min": "0", "onset_max": "0"}
    providers = {row["body"]["kind"]: row for row in context["providers"]}
    chassis = providers["chassis"]["body"]
    chassis["chassis"] = deepcopy(document["deployment"]["bindings"][0]["chassis"])
    chassis["capacities"] = []
    providers["environment"]["body"]["grammar"] = deepcopy(domain)
    providers["interface"]["body"]["definition"] = deepcopy(interface)
    providers["interface"]["body"]["channels"] = [
        {"id": "condition", "kind": "observation", "observer": "executor", "source": "condition", "subject": "encounter/target", "availability": availability},
        *[{"id": bank + "_feedback", "kind": "feedback", "observer": "executor", "source": effect, "subject": "encounter/target", "availability": availability}
          for bank, effect in (("first", "stage_one"), ("second", "stage_two"))]]
    bindings = []
    def capacity(owner, unit, scope, quantity, identity):
        chassis["capacities"].append({"id": identity, "pool_id": "staged.pool." + identity, "unit": unit, "scope": scope,
            "quantity": quantity, "slots": ["e1", "e2"] if scope == "per_encounter_slot" else [],
            "availability": availability, "record_layout_digest": digest(context["record_layout"])})
        bindings.append({"owner": owner, "unit": unit, "scope": scope, "provider": chassis["definition"], "capacity": identity})
    for slot, component_value in components.items():
        for row in component_value["body"]["provider_requirements"]:
            if row["kind"] != "capacity":
                continue
            local_owner = row["owner"]
            owner = {"kind": "input", "id": local_owner["id"]} if local_owner["kind"] == "external_slot" else {"kind": "node", "slot": slot, "node": local_owner["id"]}
            quantity = row["minimum"]
            if row["unit"] == "evidence_records": quantity = 2
            if row["unit"] == "retained_correlation_records" or (row["unit"] == "input_rows_per_tick" and slot == "driver"): quantity = 4
            capacity(owner, row["unit"], row["scope"], quantity, slot + "." + row["id"])
    for unit, scope, count in (("generation_counters", "per_encounter_slot", 1), ("timer_cells", "per_executor", 1),
                               ("control_event_records", "per_executor", 64)):
        capacity({"kind": "layout"}, unit, scope, count, "layout." + unit + "." + scope)
    for provider in context["providers"]:
        provider["body"]["availability"] = deepcopy(availability)
        provider["identity"]["content_fingerprint"] = digest(provider["body"])
    inputs = [{"input": identity, "source": source, "provider": interface, "channel": identity}
              for identity, source in (("condition", "condition"), ("first_feedback", "stage_one"), ("second_feedback", "stage_two"))]
    assert len(bindings) == 17
    return context, inputs, bindings


def build() -> dict:
    seed_path = DATA / "policy_staged_material_seed_v01.json"
    assert hashlib.sha256(seed_path.read_bytes()).hexdigest() == SEED_SHA256, "Review changed synthetic material declarations"
    seed = json.loads(seed_path.read_text())
    original_request = realization()
    values = fragments(original_request["implementation_library"])
    components = {slot: component(slot, value, seed) for slot, value in zip(("decision", "driver"), values)}
    assembly = rule(components, seed)
    union = ordered_union(components, assembly)
    context, inputs, resources = context_and_bindings(original_request, components, assembly, union)
    bridge = original_request["catalog_bindings"][0]
    request = {"schema_version": "biocompiler.policy_component_material_request.v0.1", "profile": "biocompiler.policy_component_mrna.v0.1",
        "implementation_request": original_request,
        "component_library": {"schema_version": "biocompiler.policy_component_library.v0.1", "profile": "biocompiler.policy_exact_component_library.v0.1", "components": list(components.values())},
        "composition_rule": assembly, "catalog_binding": {**{key: bridge[key] for key in ("entry_id", "entry_version", "entry_digest", "operation", "realization")},
            "components": assembly["body"]["components"], "rule": assembly["identity"]},
        "input_bindings": inputs, "resource_bindings": resources, "context": context,
        "budgets": {"profile": "biocompiler.policy_component_material_resources.v0.1", "max_work": 500000000,
                    "max_report_bytes": 8323072, "max_report_nodes": 249968}}
    sequence = "CCAUGGCUUAAGGAAAA"
    assert seed["expected_molecules"][0]["sequence"] == sequence
    return {"schema_version": "biocompiler.policy_staged_material_literals.v0.1",
        "notice": "Separately supplied artificial staged source, domain, component-to-RNA carriers and resource premises; native acceptance pending, empirical realization unassessed.",
        "seed_sha256": SEED_SHA256, "request": request, "limits": deepcopy(original()["limits"]),
        "expected": {"sequence": sequence, "fasta": ">rna_0001 alphabet=RNA\n" + sequence + "\n", "molecule": seed["expected_molecules"][0],
            "histories": 25, "transitions": 86, "prefixes_started": 87, "prefixes_after_tick": [1, 1, 9, 25, 25, 25],
            "census_derivation": "Each slot has five branches: first-stage silence, first-stage failure, or first completion followed by second-stage silence/completion/failure. Two slots give 5*5=25; ticks0..5 give1+1+9+25+25+25=86 transitions and87 started prefixes.",
            "requirements": ["first_initiation", "second_initiation"], "node_count": 28, "wire_count": 55, "link_count": 12,
            "resource_bindings": 17, "queue_records": 64, "ordered_cause_slots": 384, "ordered_union": union}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for path, value in ((REALIZATION, realization()), (OUTPUT, build())):
        encoded = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        if args.check:
            assert path.read_text() == encoded, "Changed staged fixture original: " + path.name
        else:
            path.write_text(encoded)


if __name__ == "__main__":
    main()
