"""Bounded artificial finite-machine originals, authored without native execution.

Graph fragments, timelines and RNA assertions are supplied fixture premises.
No compiler output, evaluator or native acceptance is used to construct them.
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
    import generate_policy_staged_material_fixture as shared
except ModuleNotFoundError:
    from tools import generate_policy_staged_material_fixture as shared

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "core/test/data/policy_finite_machine_v01.json"
MATERIAL_PROFILE = "biocompiler.policy_finite_machine_component_mrna.v0.1"
SPECS = (
    {"id": "retry_cycle", "states": ["ready", "active", "done"], "terminal": ["done"], "effects": ["response"],
     "transitions": [("launch", "ready", "active", "rising", "positive", "response"),
        ("complete", "active", "done", "response.completed", "true", None),
        ("retry_failure", "active", "ready", "response.failed", "true", None),
        ("retry_timeout", "active", "ready", "response.timed_out", "true", None)]},
    {"id": "guarded_branch", "states": ["ready", "deciding", "accepted", "rejected", "done"],
     "terminal": ["rejected", "done"], "effects": ["probe", "response"],
     "transitions": [("launch", "ready", "deciding", "rising", "positive", "probe"),
        ("accept", "deciding", "accepted", "probe.completed", "positive", "response"),
        ("reject", "deciding", "rejected", "probe.completed", "negative", None),
        ("complete", "accepted", "done", "response.completed", "true", None),
        ("probe_fail", "deciding", "rejected", "probe.failed", "true", None),
        ("probe_timeout", "deciding", "rejected", "probe.timed_out", "true", None),
        ("response_fail", "accepted", "rejected", "response.failed", "true", None),
        ("response_timeout", "accepted", "rejected", "response.timed_out", "true", None)]},
    {"id": "updated_fork", "states": ["ready", "active", "success", "failure"],
     "terminal": ["success", "failure"], "effects": ["response"],
     "transitions": [("launch", "ready", "active", "updated", "positive", "response"),
        ("complete", "active", "success", "response.completed", "true", None),
        ("fail", "active", "failure", "response.failed", "true", None),
        ("timeout", "active", "failure", "response.timed_out", "true", None)]},
)


def source_request(spec, *, horizon_ticks=5):
    base = shared.build_request()
    retained = [row for row in base.program.declarations if not isinstance(row, (p.Machine, p.Transition, p.Effect, p.Requirement))]
    observation = next(row for row in retained if isinstance(row, p.Observation))
    prototype = next(row for row in base.program.declarations if isinstance(row, p.Effect))
    effects = {identity: replace(prototype, id=identity) for identity in spec["effects"]}
    machine = p.Machine("machine", p.Ref("executor", "Role"), p.Scope("encounter", p.Ref("encounter", "Encounter")),
        tuple(spec["states"]), "ready", tuple(spec["terminal"]), "encounter",
        p.Arbitration("exclusive", "reject", "reject", "forbidden", "none"))
    transitions = []
    for identity, source, destination, event, guard, effect in spec["transitions"]:
        on = (p.rising(observation.expression) if event == "rising" else observation.updated if event == "updated"
              else effects[event.split(".")[0]].event(event.split(".")[1]))
        when = {"positive": observation.expression, "negative": p.not_(observation.expression), "true": p.TRUE}[guard]
        transitions.append(p.Transition(identity, p.ref(machine), source, destination, on, when, "defer",
                                       () if effect is None else (p.ref(effects[effect]),)))
    requirements = [p.Requirement(identity + "_initiation", "progress", "Each requested abstract attempt initiates.",
        p.Scope("encounter", p.Ref("encounter", "Encounter")), trigger=effect.event("requested"), response=effect.event("initiated"),
        deadline=p.quantity(1, p.SECOND), horizon=p.quantity(horizon_ticks, p.SECOND), clock=p.Ref("clock", "Clock"))
        for identity, effect in effects.items()]
    declarations = tuple(retained + list(effects.values()) + [machine] + transitions + requirements)
    program = replace(base.program, id="finite_" + spec["id"], declarations=declarations,
        source_map=tuple(p.SourceSpan(row.id, "finite_" + spec["id"] + ".py", i + 1) for i, row in enumerate(declarations)))
    interface = next(value.ref for value in program.semantics.definitions if value.category == "interface")
    entry = replace(base.implementations.implementations[0], dependencies=(interface,))
    return replace(base, program=program, assurance=replace(base.assurance, requirements=tuple(row.id for row in requirements),
                   horizon=p.quantity(horizon_ticks, p.SECOND)),
                   implementations=replace(base.implementations, implementations=(entry,)))


def implementation_request(spec, library, *, horizon_ticks=5):
    request = shared.realization()
    request.update(schema_version="biocompiler.policy_realization_request.v0.5",
                   profile="biocompiler.policy_finite_machine_inputs.v0.1",
                   document=p.to_data(source_request(spec, horizon_ticks=horizon_ticks)), implementation_library=library)
    entry = request["document"]["implementations"]["implementations"][0]
    request["catalog_bindings"][0].update(entry_digest=shared.digest(entry), models=[row["identity"] for row in library["models"]])
    domain = request["operating_domain"]
    domain["horizon_ticks"] = horizon_ticks
    domain["feedback_factors"] = []
    def sample(tick, value, status="valid", slots=("e1", "e2")):
        return [{"available_tick": tick, "observed_tick": tick, "observation": "condition", "slot": slot,
                 "status": status, "value": value} for slot in slots]
    if spec["id"] == "retry_cycle":
        domain["fixed_observations"] = sum((sample(tick, value) for tick, value in ((0, False), (1, True), (2, False), (3, True))), [])
        factors = [("response", [2], ["failed"]), ("response", [4], ["completed"])]
    elif spec["id"] == "guarded_branch":
        domain["observation_factors"] = [{"age_ticks": [0], "alphabet": "known_truth_and_evidence_status.v1",
            "max_rows_per_slot_tick": 1, "observation": "condition", "slots": ["e1"], "ticks": [2]}]
        factors = [("probe", [2], ["completed", "failed"]), ("response", [3], ["completed", "failed"])]
    else:
        domain["fixed_observations"] = sample(0, False) + sample(1, None, "missing") + sample(2, True)
        factors = [("response", [3], ["completed", "failed"])]
    for effect, ticks, outcomes in factors:
        domain["feedback_factors"].append({"attempt_selector": "all_previously_created", "effect": effect,
            "max_rows_per_attempt_tick": 1, "outcomes": outcomes, "routes": ["correlated"], "ticks": ticks})
    return request


def coalesce_output_boundaries(fragments, links):
    """Keep one boundary per producer endpoint; retain every distinct link sink."""
    renamed = {}
    for slot, fragment in fragments.items():
        endpoints = {}
        boundaries = []
        for boundary in fragment["boundary_ports"]:
            endpoint = (boundary["endpoint"]["node"], boundary["endpoint"]["port"])
            if endpoint in endpoints:
                original = endpoints[endpoint]
                assert boundary["direction"] == original["direction"] == "output"
                assert boundary["signal_type"] == original["signal_type"]
                assert {key: value for key, value in boundary.items() if key != "id"} == {
                    key: value for key, value in original.items() if key != "id"}
                renamed[slot, boundary["id"]] = original["id"]
            else:
                endpoints[endpoint] = boundary
                boundaries.append(boundary)
        fragment["boundary_ports"] = boundaries
    for link in links:
        producer = link["producer"]
        producer["boundary"] = renamed.get((producer["slot"], producer["boundary"]), producer["boundary"])


def declared_fragments(spec):
    models = {}
    def model(primitive, config, *, executor=False):
        key = shared.digest([primitive, config, executor])
        if key not in models:
            item = shared.model(spec["id"] + "." + str(len(models)), primitive, config, executor=executor)
            item["identity"]["id"] = "finite." + spec["id"] + ".model." + str(len(models))
            models[key] = item
        return deepcopy(models[key])
    def node(identity, primitive, config, *, executor=False):
        return {"id": identity, "model": model(primitive, config, executor=executor)}
    count = len(spec["transitions"])
    control = [node("evidence", "evidence_bank", {"freshness_ticks": 10}),
        node("machine", "machine_bank", {"states": spec["states"], "initial": "ready", "terminal": spec["terminal"],
            "writers": count, "retained_capacity": 1})]
    # A literal primitive is a source occurrence, not an implicit helper. The
    # quantitative shapes use only the observation and its negation as guards.
    if any(row[4] == "true" for row in spec["transitions"]):
        control.append(node("true", "truth_constant", {"value": "true"}))
    control.append(node("arbiter", "exclusive_arbiter", {"lanes": count}))
    cwires = []
    if any(row[3] == "rising" for row in spec["transitions"]):
        control.append(node("edge", "observed_rising", {})); cwires.append(shared.wire("evidence", "value", "edge", "in"))
    if any(row[4] == "negative" for row in spec["transitions"]):
        control.append(node("not", "truth_not", {})); cwires.append(shared.wire("evidence", "value", "not", "in"))
    actuator = [node("product", "product_constant", {"product": "fixture.product.alpha"}, executor=True)]
    awires, cboundaries, aboundaries, links = [], [], [], []
    def cross(identity, producer, pnode, pport, consumer, cnode, cport, signal):
        table = {"control": cboundaries, "actuator": aboundaries}
        table[producer].append(shared.boundary(identity, "output", signal, pnode, pport))
        table[consumer].append(shared.boundary(identity, "input", signal, cnode, cport))
        links.append({"id": identity, "producer": {"slot": producer, "boundary": identity},
            "consumer": {"slot": consumer, "boundary": identity}, "signal_type": signal,
            "scope": "immutable_executor_broadcast" if signal == "product_symbol" else "same_encounter_slot"})
    for effect in spec["effects"]:
        actuator.append(node(effect, "attempt_bank", {"capacity": 4, "timeout_ticks": 2,
            "authorization": "continuous", "on_loss": "continue", "on_unknown": "defer"}))
    selectors = set()
    for index, (_, source, destination, event, guard, effect) in enumerate(spec["transitions"]):
        gate, commit = f"gate{index}", f"commit{index}"
        control += [node(gate, "transition_gate", {"source": source, "correlation": "retained_attempt" if "." in event else "unbound"}),
            node(commit, "transition_commit", {"destination": destination, "writes": 0, "requests": int(effect is not None)})]
        gnode, gport = {"positive": ("evidence", "value"), "negative": ("not", "out"), "true": ("true", "out")}[guard]
        cwires += [shared.wire("machine", "snapshot", gate, "machine"), shared.wire(gnode, gport, gate, "guard"),
            shared.wire(gate, "candidate", "arbiter", f"in{index}"), shared.wire("arbiter", f"out{index}", commit, "grant"),
            shared.wire(commit, "machine_write", "machine", f"write{index}")]
        if event in ("rising", "updated"):
            cwires.append(shared.wire("edge" if event == "rising" else "evidence", "events" if event == "rising" else "updated", gate, "on"))
        else:
            owner, phase = event.split(".")
            selector = owner + "_" + phase
            if selector not in selectors:
                selectors.add(selector); actuator.append(node(selector, "event_select", {"event_kind": phase}))
                awires.append(shared.wire(owner, "events", selector, "events"))
            cross(f"event{index}", "actuator", selector, "selected", "control", gate, "on", "event_batch")
        if effect:
            cross(effect + ".product", "actuator", "product", "out", "control", commit, "product0", "product_symbol")
            cross(effect + ".request", "control", commit, "request0", "actuator", effect, "request", "effect_request")
            cross(effect + ".authorization", "control", gnode, gport, "actuator", effect, "authorization", "truth_value")
    def fragment(slot, nodes, wires, boundaries, inputs, groups):
        # shared.fragment uses an explicit output census; truth_not is the only
        # additional scalar node in these three declared topologies.
        exports = [shared.endpoint(row["id"], port) for row in nodes
            for port in (["out"] if row["model"]["body"]["primitive"] == "truth_not" else shared.output_ports(row["model"]))]
        value = {"schema_version": "biocompiler.policy_component_fragment.v0.1", "profile": "biocompiler.policy_staged_fragment.v0.1",
            "primitive_profile": shared.PROFILE, "observable_profile": shared.OBSERVABLE, "phase_profile": shared.PHASE,
            "id": "finite." + spec["id"] + "." + slot, "version": "1", "slot_layout": {"id": "encounters", "slots": 2},
            "nodes": nodes, "wires": wires, "boundary_ports": boundaries, "external_slots": inputs, "atomic_groups": groups,
            "semantic_exports": exports}
        return value
    fragments = {"control": fragment("control", control, cwires, cboundaries,
        [{"id": "condition", "kind": "evidence", "consumer": shared.endpoint("evidence", "samples")}],
        [{"id": "selection", "arbiter": "arbiter", "commits": [f"commit{i}" for i in range(count)]}]),
        "actuator": fragment("actuator", actuator, awires, aboundaries,
            [{"id": effect + "_feedback", "kind": "feedback", "consumer": shared.endpoint(effect, "feedback")} for effect in spec["effects"]], [])}
    assert sum(len(value["nodes"]) for value in fragments.values()) <= 64
    library = {"schema_version": "biocompiler.policy_implementation_library.v0.1", "profile": shared.PROFILE,
        "id": "finite." + spec["id"] + ".library", "version": "1", "models": list(models.values())}
    return library, fragments, links


def material_authority(spec, seed):
    authority = deepcopy(seed["material_authority"])
    qualify = lambda local: json.dumps(["control" if local == "utr5" else "actuator", local], separators=(",", ":"))
    authority["template"]["id"] = "finite." + spec["id"] + ".payload"
    for member in authority["members"]:
        member["regions"] = {key: qualify(value) for key, value in member["regions"].items()}
    for structure in authority["template"]["payload_structures"]:
        for region in structure["regions"]: region["feature_id"] = qualify(region["feature_id"])
    for step in authority["template"]["steps"]:
        for port in step["ports"]:
            for row in port["feature_transition"]["dispositions"]:
                for output in row["outputs"]: output["id"] = qualify(output["id"])
    molecule = deepcopy(seed["expected_molecules"][0])
    for feature in molecule["features"]: feature["id"] = qualify(feature["id"])
    molecule["features"].sort(key=lambda row: row["id"])
    return authority, molecule


def composition(spec, fragments, links, seed):
    components = {}
    for slot, fragment in fragments.items():
        value = shared.component("decision" if slot == "control" else "driver", fragment, seed)
        # ceil(log2(states)) is the supplied minimum local state encoding.
        for requirement in value["body"]["provider_requirements"]:
            if requirement.get("unit") == "machine_state_bits": requirement["minimum"] = (len(spec["states"]) - 1).bit_length()
        value["identity"] = shared.pin("model", "finite." + spec["id"] + "." + slot, value["body"])
        components[slot] = value
    authority, molecule = material_authority(spec, seed)
    body = {"primitive_profile": shared.PROFILE, "observable_profile": shared.OBSERVABLE, "phase_profile": shared.PHASE,
        "transport_profile": "biocompiler.policy_identity_transport.v0.1", "slot_layout": {"id": "encounters", "slots": 2},
        "components": [{"slot": slot, "component": value["identity"]} for slot, value in components.items()], "links": links,
        "node_order": [{"slot": slot, "node": row["id"]} for slot, value in fragments.items() for row in value["nodes"]],
        "wire_order": [{"kind": "local", "slot": slot, "index": i} for slot, value in fragments.items() for i in range(len(value["wires"]))]
            + [{"kind": "link", "id": row["id"]} for row in links],
        "input_order": [{"slot": slot, "external_slot": row["id"], "id": row["id"]} for slot, value in fragments.items() for row in value["external_slots"]],
        "group_order": [{"slot": "control", "group": "selection"}],
        "export_order": [{"slot": slot, **row} for slot, value in fragments.items() for row in value["semantic_exports"]],
        "root_bindings": [{"slot": slot, "source": value["body"]["root"]["id"]} for slot, value in components.items()],
        "joins": [{"id": "leader_to_body", "step": "join", "port": "joined", "left": "control", "right": "actuator", "offset": 2}],
        "link_carriers": [{"link": row["id"], "producer_site": 0, "consumer_site": 0, "joins": ["leader_to_body"]} for row in links],
        "material_authority": authority}
    rule = {"schema_version": "biocompiler.policy_component_assembly_rule.v0.2", "profile": "biocompiler.policy_instance_component_assembly.v0.1",
        "identity": shared.pin("model", "finite." + spec["id"] + ".assembly", body), "body": body}
    def resolve(value):
        endpoint = next(row["endpoint"] for row in fragments[value["slot"]]["boundary_ports"] if row["id"] == value["boundary"])
        return {"slot": value["slot"], **endpoint}
    union = {"schema_version": "biocompiler.policy_instance_ordered_union.v0.1",
        **{key: deepcopy(body[key]) for key in ("primitive_profile", "observable_profile", "phase_profile", "transport_profile", "slot_layout", "links")},
        "nodes": [{"slot": slot, "node": row["id"], "model": row["model"]} for slot, value in fragments.items() for row in value["nodes"]],
        "wires": [{"producer": {"slot": slot, **row["producer"]}, "consumer": {"slot": slot, **row["consumer"]}}
            for slot, value in fragments.items() for row in value["wires"]] + [{key: resolve(row[key]) for key in ("producer", "consumer")} for row in links],
        "inputs": [{"id": row["id"], "kind": row["kind"], "consumer": {"slot": slot, **row["consumer"]}}
            for slot, value in fragments.items() for row in value["external_slots"]],
        "atomic_groups": [{"slot": "control", "id": "selection", "arbiter": {"slot": "control", "node": "arbiter"},
            "commits": [{"slot": "control", "node": f"commit{i}"} for i in range(len(spec["transitions"]))]}],
        "semantic_exports": body["export_order"]}
    return components, rule, union, molecule


def context(spec, request, components, rule, union, *, horizon_ticks=5):
    base = shared.build()["request"]["context"]
    base["profile"] = MATERIAL_PROFILE
    base["placement"]["template_id"] = rule["body"]["material_authority"]["template"]["id"]
    layout = base["record_layout"]
    layout.update(rule=rule["identity"], union_digest=shared.digest(union), domain_digest=shared.digest(request["operating_domain"]),
                  ordered_cause_slots=2048, horizon_ticks=horizon_ticks)
    providers = {row["body"]["kind"]: row for row in base["providers"]}
    providers["environment"]["body"]["grammar"] = deepcopy(request["operating_domain"])
    interface = providers["interface"]["body"]
    availability = deepcopy(interface["availability"])
    interface["channels"] = [{"id": identity, "kind": kind, "observer": "executor", "source": source,
        "subject": "encounter/target", "availability": deepcopy(availability)}
        for identity, kind, source in [("condition", "observation", "condition")]
          + [(effect + "_feedback", "feedback", effect) for effect in spec["effects"]]]
    chassis = providers["chassis"]["body"]
    chassis["capacities"] = []
    bindings = []
    def capacity(owner, unit, scope, quantity, identity):
        chassis["capacities"].append({"id": identity, "pool_id": "finite." + spec["id"] + "." + identity,
            "unit": unit, "scope": scope, "quantity": quantity, "slots": ["e1", "e2"] if scope == "per_encounter_slot" else [],
            "availability": deepcopy(availability), "record_layout_digest": shared.digest(layout)})
        bindings.append({"owner": owner, "unit": unit, "scope": scope, "provider": chassis["definition"], "capacity": identity})
    for slot, value in components.items():
        for row in value["body"]["provider_requirements"]:
            if row["kind"] != "capacity": continue
            owner = {"kind": "input", "id": row["owner"]["id"]} if row["owner"]["kind"] == "external_slot" else {
                "kind": "node", "slot": slot, "node": row["owner"]["id"]}
            quantity = row["minimum"]
            if row["unit"] in ("evidence_records", "input_rows_per_tick", "retained_correlation_records"): quantity = 8
            capacity(owner, row["unit"], row["scope"], quantity, slot + "." + row["id"])
    for unit, scope, quantity in (("generation_counters", "per_encounter_slot", 1), ("timer_cells", "per_executor", 1),
                                 ("control_event_records", "per_executor", 256)):
        capacity({"kind": "layout"}, unit, scope, quantity, "layout." + unit + "." + scope)
    for provider in base["providers"]: provider["identity"]["content_fingerprint"] = shared.digest(provider["body"])
    inputs = [{"input": row["id"], "source": row["source"], "provider": interface["definition"], "channel": row["id"]} for row in interface["channels"]]
    return base, inputs, bindings


def build():
    seed_bytes = (shared.DATA / "policy_staged_material_seed_v01.json").read_bytes()
    assert hashlib.sha256(seed_bytes).hexdigest() == shared.SEED_SHA256
    seed = json.loads(seed_bytes)
    cases = []
    # The guarded domain has no inputs after tick 3 and its final timeout is at
    # tick 4. Keep every branch and deadline in the positive case; retain the
    # previous complete tick-5 original separately as a work-limit control.
    for spec, horizon_ticks in [(spec, 4 if spec["id"] == "guarded_branch" else 5) for spec in SPECS] + [(SPECS[1], 5)]:
        library, fragments, links = declared_fragments(spec)
        coalesce_output_boundaries(fragments, links)
        original = implementation_request(spec, library, horizon_ticks=horizon_ticks)
        components, rule, union, molecule = composition(spec, fragments, links, seed)
        context_value, inputs, resources = context(spec, original, components, rule, union, horizon_ticks=horizon_ticks)
        bridge = original["catalog_bindings"][0]
        request = {"schema_version": "biocompiler.policy_component_material_request.v0.7", "profile": MATERIAL_PROFILE,
            "implementation_request": original,
            "component_library": {"schema_version": "biocompiler.policy_component_library.v0.1", "profile": "biocompiler.policy_exact_component_library.v0.1", "components": list(components.values())},
            "composition_rule": rule, "catalog_binding": {**{key: bridge[key] for key in ("entry_id", "entry_version", "entry_digest", "operation", "realization")},
                "components": rule["body"]["components"], "rule": rule["identity"]},
            "input_bindings": inputs, "resource_bindings": resources, "context": context_value,
            "budgets": {"profile": "biocompiler.policy_component_material_resources.v0.1", "max_work": 500000000,
                "max_report_bytes": 8323072, "max_report_nodes": 249968}}
        cases.append({"id": spec["id"], "request": request, "expected": {"molecule": molecule,
            "sequence": "CCAUGGCUUAAGGAAAA", "ordered_union": union,
            "state_count": len(spec["states"]), "transition_count": len(spec["transitions"]), "effect_count": len(spec["effects"]),
            "node_count": len(union["nodes"]), "wire_count": len(union["wires"]), "link_count": len(links)}})
    limits = shared.original()["limits"]
    # The guarded two-effect history needs 14 complete port inventories and
    # at least 60 retained attempt publications. Their mandatory output charges,
    # other signal payloads and final inventories exceed one million work units
    # before evaluator/retention work. Fund it within the existing finite ceiling.
    limits["candidate"]["max_work"] = 10_000_000
    previous = cases.pop()
    # Pin the exact independent authority used by hosted run 37984363402. A
    # bounded incomplete result never transfers acceptance to this old domain.
    previous_invocation = {"request": previous["request"], "limits": deepcopy(limits)}
    assert shared.digest(previous_invocation) == "d6aedac658830616d3d58aac29bb13be0eff00f23a705d91117b4942abb3f341"
    cases[1]["expected"].update(histories=110, transitions=276)
    incomplete = {"id": "guarded_branch_horizon_5_work_limit", **previous_invocation,
        "expected": {"histories": 110, "transitions": 386, "status": "incomplete",
            "diagnostic": "policy_preservation_work_limit", "accepted_material": False,
            "export_diagnostic": "policy_component_material_export_not_accepted"}}
    return {"schema_version": "biocompiler.policy_finite_machine_literals.v0.1",
        "notice": "Artificial supplied component-to-RNA premises. No native acceptance or biological evidence is asserted.",
        "seed_sha256": shared.SEED_SHA256, "limits": limits, "cases": cases, "incomplete_cases": [incomplete]}


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--check", action="store_true"); args = parser.parse_args()
    encoded = json.dumps(build(), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n"
    assert len(encoded.encode()) < 2_000_000, "Keep finite original packets bounded"
    if args.check:
        assert PATH.read_text() == encoded, "Finite fixture changed; review supplied originals"
    else:
        PATH.write_text(encoded)


if __name__ == "__main__": main()
