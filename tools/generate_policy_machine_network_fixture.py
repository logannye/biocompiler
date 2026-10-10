"""Independent two-controller supplied models and exact artificial RNA premises.

The hand-authored fragments and literal relocated program are independent of
native lowering, linking, execution and acceptance. No biological claim follows.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from biocompiler import policy as p
from biocompiler.policy import modules as mod, module_linking as ml
try:
    import generate_policy_finite_machine_fixture as finite
except ModuleNotFoundError:
    from tools import generate_policy_finite_machine_fixture as finite

shared = finite.shared
ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "core/test/data/policy_machine_network_v01.json"
PROFILE = "biocompiler.policy_network_component_mrna.v0.1"
HORIZON = 10
SPEC = {"id": "communicating_network", "states": ["ready", "active"], "terminal": [],
    "effects": ["response_a", "response_b"], "transitions": list(range(8))}
CONTEXT = ("executor", "encounter/target", "encounter", "clock", "product")
A_IDS = ("permit", "response_a", "machine_a", "launch_a", "complete_a", "fail_a", "timeout_a", "initiation_a")
B_IDS = ("response_b", "machine_b", "launch_b", "complete_b", "fail_b", "timeout_b", "initiation_b")
RELOCATIONS = {**{key: "sense/" + key for key in ("condition_a", "condition_b")},
               **{key: "alpha/" + key for key in A_IDS}, **{key: "beta/" + key for key in B_IDS}}


def source_request():
    base = shared.build_request()
    old = {row.id: row for row in base.program.declarations}
    context = [old[key] for key in CONTEXT]
    prototype = next(row for row in old.values() if isinstance(row, p.Observation))
    observations = [replace(prototype, id="condition_" + name, freshness=p.quantity(age, p.SECOND), coherence="stream_" + name)
                    for name, age in (("a", 2), ("b", 3))]
    effect = next(row for row in old.values() if isinstance(row, p.Effect))
    scope = p.Scope("encounter", p.Ref("encounter", "Encounter"))
    permit = p.StateStore("permit", p.TRUTH, scope, False, 2, "reject", "encounter", None, "not_applicable")
    controllers = []
    for i, name in enumerate(("a", "b")):
        response = replace(effect, id="response_" + name, lifecycle=replace(effect.lifecycle, timeout=p.quantity(4, p.SECOND)))
        ids = tuple(prefix + "_" + name for prefix in ("launch", "complete", "fail", "timeout"))
        arbitration = p.Arbitration("priority", "declared_order", "reject", "forbidden", "none", ids)
        machine = p.Machine("machine_" + name, p.Ref("executor", "Role"), scope, ("ready", "active"), "ready", (), "encounter", arbitration)
        condition = observations[i].expression if i == 0 else p.all_of(observations[i].expression, permit.expression)
        transitions = [p.Transition(ids[0], p.ref(machine), "ready", "active", observations[i].updated, condition, "defer", (p.ref(response),),
            (p.Assignment(p.ref(permit), p.TRUE),) if i == 0 else ())]
        for identity, phase in zip(ids[1:], ("completed", "failed", "timed_out")):
            transitions.append(p.Transition(identity, p.ref(machine), "active", "ready", response.event(phase), p.TRUE, "defer", (),
                (p.Assignment(p.ref(permit), p.FALSE),) if i == 0 else ()))
        requirement = p.Requirement("initiation_" + name, "progress", "Every requested attempt initiates under its original correlation.", scope,
            trigger=response.event("requested"), response=response.event("initiated"), deadline=p.quantity(1, p.SECOND),
            horizon=p.quantity(HORIZON, p.SECOND), clock=p.Ref("clock", "Clock"))
        controllers.extend(([permit] if i == 0 else []) + [response, machine] + transitions + [requirement])
    rows = tuple(context + observations + controllers)
    program = replace(base.program, id="module_network", declarations=rows,
        source_map=tuple(p.SourceSpan(row.id, "network_original.py", index + 1) for index, row in enumerate(rows)))
    interface = next(value.ref for value in program.semantics.definitions if value.category == "interface")
    entry = replace(base.implementations.implementations[0], dependencies=(interface,))
    return replace(base, program=program, implementations=replace(base.implementations, implementations=(entry,)),
        assurance=replace(base.assurance, requirements=("initiation_a", "initiation_b"), horizon=p.quantity(HORIZON, p.SECOND)))


def module_originals(program):
    rows = {row.id: row for row in program.declarations}
    spans = {row.declaration_id: row for row in program.source_map}
    context = replace(program, declarations=tuple(rows[key] for key in CONTEXT), source_map=tuple(spans[key] for key in CONTEXT))
    ports = tuple(mod.InputPort("subject" if key == "encounter/target" else key, rows[key], "read" if key == "product" else "context") for key in CONTEXT)
    bindings = tuple(mod.ModuleBinding(port.name, p.ref(port.declaration)) for port in ports)
    sense_ids = ("condition_a", "condition_b")
    sensor = mod.ModuleTemplate("network_sensor", "1", program.semantics, ports,
        tuple(mod.OutputPort(key, rows[key], "read") for key in sense_ids), tuple(rows[key] for key in sense_ids),
        source_map=tuple(spans[key] for key in sense_ids))
    instances = [mod.instantiate(sensor, "sense", bindings=bindings)]
    for name, ids, instance in (("a", A_IDS, "alpha"), ("b", B_IDS, "beta")):
        inputs = ports + (mod.InputPort("condition", rows["condition_" + name], "read"),)
        extra = (mod.ModuleBinding("condition", mod.ModuleOutput("sense", "condition_" + name)),)
        if name == "b":
            inputs += (mod.InputPort("permit", rows["permit"], "read"),)
            extra += (mod.ModuleBinding("permit", mod.ModuleOutput("alpha", "permit")),)
        body = tuple(rows[key] for key in ids if not key.startswith("initiation_"))
        outputs = (mod.OutputPort("permit", rows["permit"], "read"),) if name == "a" else ()
        template = mod.ModuleTemplate("network_controller_" + name, "1", program.semantics, inputs, outputs, body,
            private=(p.ref(rows["machine_" + name]), p.ref(rows["response_" + name])),
            guarantees=(rows["initiation_" + name],), source_map=tuple(spans[key] for key in ids))
        instances.append(mod.instantiate(template, instance, bindings=bindings + extra))
    return ml.ModuleBundle(context, tuple(instances)).to_data()


def literal_program(program):
    """Literal relocation oracle, not the module composer under test."""
    def relocate(value):
        if type(value) is list: return [relocate(item) for item in value]
        if type(value) is not dict: return value
        result = {key: relocate(item) for key, item in value.items()}
        if result.get("$type") == "Ref": result["id"] = RELOCATIONS.get(result["id"], result["id"])
        if result.get("$type") == "SourceSpan": result["declaration_id"] = RELOCATIONS.get(result["declaration_id"], result["declaration_id"])
        if result.get("$type") == "Arbitration": result["order"] = [RELOCATIONS[key] for key in result["order"]]
        return result
    result = relocate(p.to_data(program))
    for row in result["declarations"]: row["id"] = RELOCATIONS.get(row["id"], row["id"])
    return result


def declared_fragments():
    models = {}
    def node(identity, primitive, config, executor=False):
        key = shared.digest([primitive, config, executor])
        if key not in models:
            model = shared.model("network." + str(len(models)), primitive, config, executor=executor)
            models[key] = model
        return {"id": identity, "model": deepcopy(models[key])}
    control = [node("evidence_a", "evidence_bank", {"freshness_ticks": 2}), node("evidence_b", "evidence_bank", {"freshness_ticks": 3}),
        node("permit", "truth_register", {"initial": "false", "writers": 4}),
        *[node("machine_" + name, "machine_bank", {"states": ["ready", "active"], "initial": "ready", "terminal": [], "writers": 4, "retained_capacity": 1}) for name in ("a", "b")],
        node("true", "truth_constant", {"value": "true"}), node("false", "truth_constant", {"value": "false"}),
        node("guard_b", "truth_all", {"arity": 2}),
        *[node("arbiter_" + name, "priority_arbiter", {"order": [0, 1, 2, 3]}) for name in ("a", "b")]]
    cwires = [shared.wire("evidence_b", "value", "guard_b", "in0"), shared.wire("permit", "value", "guard_b", "in1")]
    actuator = [node("product", "product_constant", {"product": "fixture.product.alpha"}, executor=True)]
    awires, cboundaries, aboundaries, links = [], [], [], []
    def cross(identity, producer, pnode, pport, consumer, cnode, cport, signal):
        table = {"control": cboundaries, "actuator": aboundaries}
        table[producer].append(shared.boundary(identity, "output", signal, pnode, pport))
        table[consumer].append(shared.boundary(identity, "input", signal, cnode, cport))
        links.append({"id": identity, "producer": {"slot": producer, "boundary": identity}, "consumer": {"slot": consumer, "boundary": identity},
            "signal_type": signal, "scope": "immutable_executor_broadcast" if signal == "product_symbol" else "same_encounter_slot"})
    for i, name in enumerate(("a", "b")):
        bank = "response_" + name
        actuator.append(node(bank, "attempt_bank", {"capacity": 12, "timeout_ticks": 4, "authorization": "continuous", "on_loss": "continue", "on_unknown": "defer"}))
        for j, phase in enumerate((None, "completed", "failed", "timed_out")):
            index, gate, commit = i * 4 + j, f"gate{i * 4 + j}", f"commit{i * 4 + j}"
            control += [node(gate, "transition_gate", {"source": "ready" if j == 0 else "active", "correlation": "unbound" if j == 0 else "retained_attempt"}),
                node(commit, "transition_commit", {"destination": "active" if j == 0 else "ready", "writes": int(i == 0), "requests": int(j == 0)})]
            guard = "evidence_a" if i == 0 and j == 0 else "guard_b" if j == 0 else "true"
            port = "value" if guard == "evidence_a" else "out"
            cwires += [shared.wire("machine_" + name, "snapshot", gate, "machine"), shared.wire(guard, port, gate, "guard"),
                shared.wire(gate, "candidate", "arbiter_" + name, f"in{j}"), shared.wire("arbiter_" + name, f"out{j}", commit, "grant"),
                shared.wire(commit, "machine_write", "machine_" + name, f"write{j}")]
            if i == 0:
                cwires += [shared.wire("true" if j == 0 else "false", "out", commit, "value0"), shared.wire(commit, "write0", "permit", f"write{j}")]
            if j == 0:
                cwires.append(shared.wire("evidence_" + name, "updated", gate, "on"))
                cross(bank + ".product", "actuator", "product", "out", "control", commit, "product0", "product_symbol")
                cross(bank + ".request", "control", commit, "request0", "actuator", bank, "request", "effect_request")
                cross(bank + ".authorization", "control", guard, port, "actuator", bank, "authorization", "truth_value")
            else:
                selector = bank + "_" + phase
                actuator.append(node(selector, "event_select", {"event_kind": phase}))
                awires.append(shared.wire(bank, "events", selector, "events"))
                cross("event" + str(index), "actuator", selector, "selected", "control", gate, "on", "event_batch")
    def outputs(row):
        primitive, config = row["model"]["body"]["primitive"], row["model"]["body"]["configuration"]
        if primitive == "truth_register": return ["value"]
        if primitive == "truth_all": return ["out"]
        if primitive == "priority_arbiter": return [f"out{i}" for i in range(len(config["order"]))]
        if primitive == "transition_commit": return [f"write{i}" for i in range(config["writes"])] + shared.output_ports(row["model"])
        return shared.output_ports(row["model"])
    def fragment(slot, nodes, wires, boundaries, inputs, groups):
        return {"schema_version": "biocompiler.policy_component_fragment.v0.1", "profile": "biocompiler.policy_staged_fragment.v0.1",
            "primitive_profile": shared.PROFILE, "observable_profile": shared.OBSERVABLE, "phase_profile": shared.PHASE,
            "id": "network." + slot, "version": "1", "slot_layout": {"id": "encounters", "slots": 2}, "nodes": nodes, "wires": wires,
            "boundary_ports": boundaries, "external_slots": inputs, "atomic_groups": groups,
            "semantic_exports": [shared.endpoint(row["id"], port) for row in nodes for port in outputs(row)]}
    fragments = {"control": fragment("control", control, cwires, cboundaries,
        [{"id": "condition_" + name, "kind": "evidence", "consumer": shared.endpoint("evidence_" + name, "samples")} for name in ("a", "b")],
        [{"id": "selection_" + name, "arbiter": "arbiter_" + name, "commits": [f"commit{i*4+j}" for j in range(4)]} for i, name in enumerate(("a", "b"))]),
        "actuator": fragment("actuator", actuator, awires, aboundaries,
            [{"id": "response_" + name + "_feedback", "kind": "feedback", "consumer": shared.endpoint("response_" + name, "feedback")} for name in ("a", "b")], [])}
    finite.coalesce_output_boundaries(fragments, links)
    return {"schema_version": "biocompiler.policy_implementation_library.v0.1", "profile": shared.PROFILE,
            "id": "network.library", "version": "1", "models": list(models.values())}, fragments, links


def shared_arbitration(original):
    """Raw-source whole-network policy: one logical resource winner per slot."""
    request = deepcopy(original)
    document = p.from_data(request["document"], p.BuildRequest)
    rows = list(document.program.declarations)
    old_permit = next(row for row in rows if isinstance(row, p.StateStore))
    busy_a, busy_b = replace(old_permit, id="alpha/busy"), replace(old_permit, id="beta/busy")
    free = p.not_(p.any_of(busy_a.expression, busy_b.expression))
    observations = [row for row in rows if isinstance(row, p.Observation)]
    order = tuple(row.id for row in rows if isinstance(row, p.Transition))
    updated = []
    for row in rows:
        if isinstance(row, p.StateStore):
            updated.extend((busy_a, busy_b)); continue
        if isinstance(row, p.Machine): row = replace(row, arbitration=replace(row.arbitration, order=order))
        if isinstance(row, p.Transition):
            alpha = row.machine.id == "alpha/machine_a"
            state = busy_a if alpha else busy_b
            launching = row.source == "ready"
            row = replace(row, when=p.all_of(observations[0 if alpha else 1].expression, free) if launching else p.TRUE,
                assignments=(p.Assignment(p.ref(state), p.TRUE if launching else p.FALSE),))
        if isinstance(row, p.Requirement): row = replace(row, horizon=p.quantity(4, p.SECOND))
        updated.append(row)
    safety = p.Requirement("shared_capacity_one", "safety", "At most one controller owns the logical resource per encounter.",
        old_permit.scope, condition=p.not_(p.all_of(busy_a.expression, busy_b.expression)), horizon=p.quantity(4, p.SECOND), clock=p.Ref("clock", "Clock"))
    updated.append(safety)
    document = replace(document, program=replace(document.program, id="shared_network", declarations=tuple(updated),
        source_map=tuple(p.SourceSpan(row.id, "shared_network_original.py", i + 1) for i, row in enumerate(updated))),
        assurance=replace(document.assurance, requirements=document.assurance.requirements + (safety.id,), horizon=p.quantity(4, p.SECOND)))
    request["document"] = p.to_data(document)
    domain = request["operating_domain"]
    domain.update(horizon_ticks=4, lifecycle_factors=[])
    domain["fixed_observations"] = [row for row in domain["fixed_observations"] if row["available_tick"] <= 2]
    domain["fixed_observations"] += [{"available_tick": 4, "observed_tick": 4, "observation": "sense/condition_b",
        "slot": slot, "status": "valid", "value": slot == "e1"} for slot in ("e1", "e2")]
    domain["feedback_factors"] = [row for row in domain["feedback_factors"] if row["ticks"] == [3]]
    additions = [("truth_any", {"arity": 2}), ("truth_not", {}), ("priority_arbiter", {"order": list(range(8))}),
        ("transition_commit", {"destination": "active", "writes": 1, "requests": 1}),
        ("transition_commit", {"destination": "ready", "writes": 1, "requests": 0})]
    library = request["implementation_library"]
    for i, (primitive, config) in enumerate(additions):
        if not any(row["body"]["primitive"] == primitive and row["body"]["configuration"] == config for row in library["models"]):
            library["models"].append(shared.model("network.shared." + str(i), primitive, config))
    request["catalog_bindings"][0]["models"] = [row["identity"] for row in library["models"]]
    return {"request": request, "expected": {"winner": "alpha/launch_a", "suppressed": "beta/launch_b",
        "safety_requirement": safety.id, "logical_capacity": 1, "machines": ["alpha/machine_a", "beta/machine_b"],
        "stores": ["alpha/busy", "beta/busy"], "priority_order": list(order)}}


def build():
    seed_bytes = (shared.DATA / "policy_staged_material_seed_v01.json").read_bytes()
    assert hashlib.sha256(seed_bytes).hexdigest() == shared.SEED_SHA256
    seed = json.loads(seed_bytes)
    document = source_request()
    modules, program = module_originals(document.program), literal_program(document.program)
    library, fragments, links = declared_fragments()
    original = shared.realization()
    original.update(schema_version="biocompiler.policy_realization_request.v0.6", profile="biocompiler.policy_network_inputs.v0.1",
        document=p.to_data(document), implementation_library=library)
    original["document"]["program"] = deepcopy(program)
    original["document"]["assurance"]["requirements"] = [RELOCATIONS[key] for key in document.assurance.requirements]
    entry = original["document"]["implementations"]["implementations"][0]
    original["catalog_bindings"][0].update(entry_digest=shared.digest(entry), models=[row["identity"] for row in library["models"]])
    original["budgets"]["max_work"] = 100_000_000
    domain = original["operating_domain"]
    domain.update(horizon_ticks=HORIZON, observation_factors=[], foreign_feedback_factors=[],
        lifecycle_factors=[{"slots": ["e1"], "ticks": [7], "actions": ["keep", "reset"]}])
    domain["logical_limits"]["max_source_attempts"] = 12
    samples = ((0, "a", False, 0), (0, "b", False, 0), (1, "a", True, 1), (1, "b", True, 1),
        (2, "a", None, 2), (2, "b", True, 1), (4, "a", True, 4), (4, "b", None, 4),
        (5, "b", True, 5), (8, "a", True, 8), (8, "b", True, 8), (9, "b", True, 9))
    domain["fixed_observations"] = [{"available_tick": tick, "observed_tick": observed, "observation": "sense/condition_" + name,
        "slot": slot, "status": "missing" if value is None and slot == "e1" else "valid", "value": value if slot == "e1" else False}
        for tick, name, value, observed in samples for slot in ("e1", "e2")]
    domain["feedback_factors"] = [{"attempt_selector": "all_previously_created", "effect": RELOCATIONS["response_" + name],
        "max_rows_per_attempt_tick": 1, "outcomes": [phase], "routes": ["correlated"], "ticks": [tick]}
        for name, tick, phase in (("a", 3, "completed"), ("b", 3, "failed"), ("a", 5, "completed"))]
    components, rule, union, molecule = finite.composition(SPEC, fragments, links, seed)
    for slot, component in components.items():
        for row in component["body"]["provider_requirements"]:
            if row.get("unit") in ("active_attempt_records", "timer_cells") and row["owner"]["id"].startswith("response_"):
                row["minimum"] = 12
        if slot == "control":
            requirements = component["body"]["provider_requirements"]
            # The supplied permit register precedes both machine banks. Its
            # capacity belongs at that same point in the local node inventory.
            first_machine = next(index for index, row in enumerate(requirements)
                if row.get("owner") == {"kind": "node", "id": "machine_a"})
            requirements.insert(first_machine, {"kind": "capacity", "id": "permit.truth_cells.per_encounter_slot",
                "owner": {"kind": "node", "id": "permit"}, "unit": "truth_cells", "scope": "per_encounter_slot", "minimum": 1})
        component["identity"]["content_fingerprint"] = shared.digest(component["body"])
    rule["body"]["components"] = [{"slot": slot, "component": value["identity"]} for slot, value in components.items()]
    rule["body"]["group_order"] = [{"slot": "control", "group": "selection_" + name} for name in ("a", "b")]
    rule["identity"]["content_fingerprint"] = shared.digest(rule["body"])
    union["atomic_groups"] = [{"slot": "control", "id": row["id"], "arbiter": {"slot": "control", "node": row["arbiter"]},
        "commits": [{"slot": "control", "node": name} for name in row["commits"]]} for row in fragments["control"]["atomic_groups"]]
    context, inputs, resources = finite.context(SPEC, original, components, rule, union)
    context["profile"] = PROFILE
    context["record_layout"].update(attempts=12, horizon_ticks=HORIZON, maximum_tick=14, ordered_reason_slots=2, ordered_cause_slots=4096)
    providers = {row["body"]["kind"]: row for row in context["providers"]}
    interface = providers["interface"]["body"]
    availability = {"duration_min": str(HORIZON), "duration_max": str(HORIZON), "onset_min": "0", "onset_max": "0"}
    interface["channels"] = [{"id": identity, "kind": kind, "observer": "executor", "source": source, "subject": "encounter/target",
        "availability": deepcopy(availability)} for identity, kind, source in
        [("condition_" + name, "observation", "sense/condition_" + name) for name in ("a", "b")]
        + [("response_" + name + "_feedback", "feedback", RELOCATIONS["response_" + name]) for name in ("a", "b")]]
    inputs = [{"input": row["id"], "source": row["source"], "provider": interface["definition"], "channel": row["id"]} for row in interface["channels"]]
    # One physical pool has one supplied capacity record. Both controllers
    # reserve their own twelve records from that same twenty-four-record pool.
    chassis = providers["chassis"]["body"]
    attempt_capacities = [row for row in chassis["capacities"] if row["unit"] == "active_attempt_records"]
    assert len(attempt_capacities) == 2
    shared_attempt_capacity = attempt_capacities[0]["id"]
    attempt_capacity_ids = {row["id"] for row in attempt_capacities}
    for allocation in resources:
        if allocation["unit"] == "active_attempt_records":
            assert allocation["provider"] == chassis["definition"] and allocation["capacity"] in attempt_capacity_ids
            allocation["capacity"] = shared_attempt_capacity
    chassis["capacities"] = [row for row in chassis["capacities"]
        if row["unit"] != "active_attempt_records" or row["id"] == shared_attempt_capacity]
    def extend(value):
        if type(value) is dict:
            if "duration_min" in value: value.update(availability)
            for child in value.values(): extend(child)
        elif type(value) is list:
            for child in value: extend(child)
    for provider in context["providers"]:
        extend(provider["body"])
        for capacity in provider["body"].get("capacities", []):
            capacity["record_layout_digest"] = shared.digest(context["record_layout"])
            if capacity["unit"] in ("evidence_records", "input_rows_per_tick", "retained_correlation_records"): capacity["quantity"] = 24
            if capacity["unit"] == "active_attempt_records":
                capacity.update(pool_id="network.shared_attempt_capacity", quantity=24)
        provider["identity"]["content_fingerprint"] = shared.digest(provider["body"])
    bridge = original["catalog_bindings"][0]
    request = {"schema_version": "biocompiler.policy_component_material_request.v0.9", "profile": PROFILE, "implementation_request": original,
        "component_library": {"schema_version": "biocompiler.policy_component_library.v0.1", "profile": "biocompiler.policy_exact_component_library.v0.1", "components": list(components.values())},
        "composition_rule": rule, "catalog_binding": {**{key: bridge[key] for key in ("entry_id", "entry_version", "entry_digest", "operation", "realization")},
            "components": rule["body"]["components"], "rule": rule["identity"]}, "input_bindings": inputs, "resource_bindings": resources,
        "context": context, "budgets": {"profile": "biocompiler.policy_component_material_resources.v0.1", "max_work": 500000000,
            "max_report_bytes": 8323072, "max_report_nodes": 249968}}
    limits = deepcopy(shared.original()["limits"])
    limits["source"]["max_attempts"] = 16
    limits["source"]["max_ticks"] = 16
    limits["candidate"]["max_work"] = 10_000_000
    limits["max_step_work"] = 10_000_000
    return {"schema_version": "biocompiler.policy_machine_network_literals.v0.1", "notice": __doc__, "seed_sha256": shared.SEED_SHA256,
        "modules": modules, "program": program, "request": request, "limits": limits, "shared": shared_arbitration(original),
        "expected": {"program": deepcopy(program), "molecule": molecule, "sequence": "CCAUGGCUUAAGGAAAA", "ordered_union": union,
            "machine_count": 2, "observation_count": 2, "state_count": 1, "transition_count": 8, "effect_count": 2,
            "node_count": len(union["nodes"]), "wire_count": len(union["wires"]), "link_count": len(links), "shared_attempt_capacity": 24}}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--check", action="store_true"); args = parser.parse_args()
    content = json.dumps(build(), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n"
    assert len(content.encode()) < 2_000_000
    if args.check:
        assert PATH.read_text() == content, "Network original fixture drift"
    else: PATH.write_text(content)

if __name__ == "__main__": main()
