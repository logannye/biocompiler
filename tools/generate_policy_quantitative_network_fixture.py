"""Independent artificial reserved transfer network and exact RNA premises; no native execution."""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from biocompiler import policy as p
try:
    import generate_policy_finite_machine_fixture as finite
except ModuleNotFoundError:
    from tools import generate_policy_finite_machine_fixture as finite

shared = finite.shared
ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "core/test/data/policy_quantitative_network_v01.json"
PROFILE = "biocompiler.policy_sampled_transfer_network_component_mrna.v0.1"
PRIMITIVE = "biocompiler.policy_multi_site_implementation.v0.1"
OBSERVABLE = "biocompiler.policy_multi_site_observables.v0.1"
PHASE = "biocompiler.policy_multi_site_primitive_execution.v0.1"
STATES = ["q000", "q001", "q010", "q011", "q100", "q101", "q110", "q111"]
VECTORS = [(0, 0, 0), (0, 0, 1), (0, 1, 0), (0, 1, 1), (1, 0, 0), (1, 0, 1), (1, 1, 0), (1, 1, 1)]
EDGE_IDS = ["a_to_b", "b_to_c", "a_to_c", "b_to_a", "c_to_a"]
# Independent literal destinations and per-edge reservations; no authoring-law evaluation.
ROWS = (("q000", "q000", (0,0,0,0,0), False, "q000", (0,0,0,0,0)),
        ("q001", "q001", (0,0,0,0,0), False, "q100", (0,0,0,0,1)),
        ("q010", "q001", (0,1,0,0,0), False, "q100", (0,0,0,1,0)),
        ("q011", "q011", (0,0,0,0,0), False, "q101", (0,0,0,1,0)),
        ("q100", "q010", (1,0,0,0,0), True, "q100", (0,0,0,0,0)),
        ("q101", "q011", (1,0,0,0,0), True, "q101", (0,0,0,0,0)),
        ("q110", "q101", (0,1,0,0,0), False, "q110", (0,0,0,0,0)),
        ("q111", "q111", (0,0,0,0,0), False, "q111", (0,0,0,0,0)))
SPEC = {"id": "sampled_transfer_network", "states": STATES, "terminal": [], "effects": ["response"],
    "transitions": [(identity, source, destination, "updated", guard, effect)
        for identity, source, destination, guard, effect in (
            ("reverse1", "q001", "q100", "negative", None), ("forward2", "q010", "q001", "positive", None),
            ("reverse2", "q010", "q100", "negative", None), ("reverse3", "q011", "q101", "negative", None),
            ("forward4", "q100", "q010", "positive", "response"), ("forward5", "q101", "q011", "positive", "response"),
            ("forward6", "q110", "q101", "positive", None))]}


def law():
    quantity = lambda amount: p.to_data(p.quantity(amount, p.COUNT))
    return {"schema_version": "biocompiler.policy_sampled_transfer_network.v0.1",
        "profile": "biocompiler.policy_sampled_reserved_transfer_network.v0.1",
        "substance": "fixture.reservoir.amount", "unit": p.to_data(p.COUNT), "quantum": quantity(1),
        "reservoirs": [{"compartment": name, "capacity": quantity(1), "initial": quantity(initial)}
                       for name, initial in (("a", 1), ("b", 1), ("c", 0))],
        "transfers": [{"id": identity, "source": source, "destination": destination, "amount": quantity(1), "when": truth}
                      for identity, source, destination, truth in (("a_to_b", "a", "b", True), ("b_to_c", "b", "c", True),
                          ("a_to_c", "a", "c", True), ("b_to_a", "b", "a", False), ("c_to_a", "c", "a", False))],
        "threshold": {"compartment": "b", "amount": quantity(1)},
        "sample_period": p.to_data(p.quantity(1, p.SECOND)),
        "arbitration": "declared_order_prestate_reservation", "ownership": "single_atomic_state_owner"}


def declared_fragments():
    """Supply two distinct commit ports feeding one attempt store, with per-site guards."""
    library, fragments, links = finite.declared_fragments(SPEC)
    library["profile"] = PRIMITIVE
    for model in library["models"]:
        body = model["body"]
        if body["primitive"] == "evidence_bank": body["configuration"]["freshness_ticks"] = 1
        if body["primitive"] == "machine_bank": body["configuration"]["initial"] = "q110"
        if body["primitive"] == "attempt_bank":
            body.update(primitive="attempt_bank_sites", profile=PRIMITIVE)
            body["configuration"].update(sites=2, capacity=6)
        model["identity"]["content_fingerprint"] = shared.digest(body)
        model["configuration_digest"] = shared.digest(body["configuration"])
    models = {row["identity"]["id"]: row for row in library["models"]}
    for fragment in fragments.values():
        fragment.update(profile="biocompiler.policy_multi_site_fragment.v0.1", primitive_profile=PRIMITIVE,
                        observable_profile=OBSERVABLE, phase_profile=PHASE)
        for node in fragment["nodes"]: node["model"] = deepcopy(models[node["model"]["identity"]["id"]])
        seen = {}
        for boundary in fragment["boundary_ports"]:
            identity = boundary["id"]
            index = seen.get(identity, 0)
            seen[identity] = index + 1
            boundary["id"] = identity + str(index)
            if fragment is fragments["actuator"] and identity != "response.product":
                boundary["endpoint"]["port"] += str(index)
    seen = {}
    for link in links:
        identity = link["id"]
        index = seen.get(identity, 0)
        seen[identity] = index + 1
        link["id"] = identity + str(index)
        for end in ("producer", "consumer"): link[end]["boundary"] += str(index)
    return library, fragments, links


def build():
    seed_bytes = (shared.DATA / "policy_staged_material_seed_v01.json").read_bytes()
    assert hashlib.sha256(seed_bytes).hexdigest() == shared.SEED_SHA256
    seed = json.loads(seed_bytes)
    library, fragments, links = declared_fragments()
    original = finite.implementation_request(SPEC, library)
    original.update(schema_version="biocompiler.policy_realization_request.v0.7", profile="biocompiler.policy_multi_site_inputs.v0.1")
    document = p.from_data(original["document"], p.BuildRequest)
    declarations = tuple(replace(row, initial="q110") if isinstance(row, p.Machine) else
        replace(row, freshness=p.quantity(1, p.SECOND)) if isinstance(row, p.Observation) else
        replace(row, horizon=p.quantity(12, p.SECOND)) if isinstance(row, p.Requirement) else row
        for row in document.program.declarations)
    document = replace(document, program=replace(document.program, declarations=declarations),
                       assurance=replace(document.assurance, horizon=p.quantity(12, p.SECOND)))
    original["document"] = p.to_data(document)
    domain = original["operating_domain"]
    domain.update(horizon_ticks=12, observation_factors=[], feedback_factors=[], foreign_feedback_factors=[])
    domain["logical_limits"]["max_source_attempts"] = 6
    domain["lifecycle_factors"] = [{"slots": ["e1", "e2"], "ticks": [7], "actions": ["keep", "reset"]}]
    domain["fixed_observations"] = [{"available_tick": tick, "observed_tick": tick, "observation": "condition", "slot": slot,
        "status": "missing" if value is None else "valid", "value": value}
        for tick, value in ((0, True), (1, True), (2, None), (3, False), (4, True), (5, True),
                            (7, False), (8, True), (9, True), (10, None), (11, False), (12, False)) for slot in ("e1", "e2")]
    components, rule, union, molecule = finite.composition(SPEC, fragments, links, seed)
    for component in components.values():
        # Same bounded active-attempt storage, explicit new primitive identity.
        requirements = deepcopy(component["body"]["fragment"])
        for node in requirements["nodes"]:
            if node["model"]["body"]["primitive"] == "attempt_bank_sites":
                node["model"]["body"]["primitive"] = "attempt_bank"
        component["body"]["provider_requirements"] = shared.prerequisites(requirements)
        for requirement in component["body"]["provider_requirements"]:
            if requirement.get("unit") == "machine_state_bits": requirement["minimum"] = 3
            if requirement.get("unit") in ("active_attempt_records", "timer_cells") and requirement["owner"]["id"] == "response":
                requirement["minimum"] = 6
    component = components["control"]
    local = {node["id"]: node["model"]["identity"] for node in fragments["control"]["nodes"]}
    component.update(schema_version="biocompiler.policy_component_material.v0.5", profile="biocompiler.policy_transfer_network_local_material.v0.1")
    component["body"]["quantitative_contracts"] = [{"id": "network", "mechanism": law(),
        "state": {"node": "machine", "model": local["machine"], "values": [
            {"state": state, "amounts": [p.to_data(p.quantity(amount, p.COUNT)) for amount in vector]}
            for state, vector in zip(STATES, VECTORS)]},
        "input": {"node": "evidence", "model": local["evidence"], "value_port": "value", "updated_port": "updated"},
        "outputs": [{"source_state": state, "input": True, "boundary": "response.request" + str(site), "model": local[commit]}
                    for site, (state, commit) in enumerate((("q100", "commit4"), ("q101", "commit5")))]}]

    for component in components.values(): component["identity"]["content_fingerprint"] = shared.digest(component["body"])
    rule.update(schema_version="biocompiler.policy_component_assembly_rule.v0.5",
                profile="biocompiler.policy_multi_site_component_assembly.v0.1")
    rule["body"].update(primitive_profile=PRIMITIVE, observable_profile=OBSERVABLE, phase_profile=PHASE)
    rule["body"]["components"] = [{"slot": slot, "component": component["identity"]} for slot, component in components.items()]
    rule["identity"]["content_fingerprint"] = shared.digest(rule["body"])
    union.update(primitive_profile=PRIMITIVE, observable_profile=OBSERVABLE, phase_profile=PHASE)
    context, inputs, resources = finite.context(SPEC, original, components, rule, union)
    context["record_layout"].update(horizon_ticks=12, maximum_tick=14, attempts=6)
    layout_digest = shared.digest(context["record_layout"])
    def extend_availability(value):
        if isinstance(value, dict):
            if "duration_min" in value and "duration_max" in value: value.update(duration_min="12", duration_max="12")
            for child in value.values(): extend_availability(child)
        elif isinstance(value, list):
            for child in value: extend_availability(child)
    for provider in context["providers"]:
        extend_availability(provider["body"])
        for capacity in provider["body"]["capacities"]:
            capacity["record_layout_digest"] = layout_digest
            if capacity["unit"] == "evidence_records": capacity["quantity"] = 13
        provider["identity"]["content_fingerprint"] = shared.digest(provider["body"])
    bridge = original["catalog_bindings"][0]
    request = {"schema_version": "biocompiler.policy_component_material_request.v0.12", "profile": PROFILE,
        "implementation_request": original,
        "component_library": {"schema_version": "biocompiler.policy_component_library.v0.1",
            "profile": "biocompiler.policy_exact_component_library.v0.1", "components": list(components.values())},
        "composition_rule": rule, "catalog_binding": {**{key: bridge[key] for key in ("entry_id", "entry_version", "entry_digest", "operation", "realization")},
            "components": rule["body"]["components"], "rule": rule["identity"]},
        "input_bindings": inputs, "resource_bindings": resources, "context": context,
        "budgets": {"profile": "biocompiler.policy_component_material_resources.v0.1", "max_work": 500000000,
            "max_report_bytes": 8323072, "max_report_nodes": 249968},
        "quantitative": {"mechanism": law(), "selection": {"instance": "control", "component": deepcopy(components["control"]["identity"]), "contract": "network"},
            "source": {"machine": "machine", "observation": "condition", "effect": "response"}}}
    coordinates = dict(zip(STATES, VECTORS))
    table = [{"source": state, "input": truth, "destination": destination, "request": requested,
              "before": list(coordinates[state]), "after": list(coordinates[destination]),
              "flows": [{"transfer": identity, "quanta": amount} for identity, amount in zip(EDGE_IDS, flows)]}
        for state, positive, forward, requested, negative, reverse in ROWS
        for truth, destination, requested, flows in (
            ("true", positive, requested, forward), ("false", negative, False, reverse), ("unknown", state, False, (0,0,0,0,0)))]

    limits = shared.original()["limits"]
    limits["source"]["max_ticks"] = 13
    limits["candidate"]["max_work"] = 10_000_000
    return {"schema_version": "biocompiler.policy_quantitative_network_literals.v0.1",
        "notice": "Artificial supplied prestate-reserved transfer-network quantitative component-to-RNA premises. No native acceptance or biological evidence is asserted.",
        "seed_sha256": shared.SEED_SHA256, "request": request, "limits": limits,
        "expected": {"molecule": molecule, "sequence": "CCAUGGCUUAAGGAAAA", "ordered_union": union, "table": table,
            "states": STATES, "vectors": [list(vector) for vector in VECTORS], "edge_ids": EDGE_IDS,
            "crossing_transitions": ["forward4", "forward5"], "crossing_commits": ["commit4", "commit5"],
            "keep_trajectory": ["q101", "q011", "q011", "q101", "q011", "q011", "q011", "q101", "q011", "q011", "q011", "q101", "q101"],
            "reset_trajectory": ["q101", "q011", "q011", "q101", "q011", "q011", "q011", "q110", "q101", "q011", "q011", "q101", "q101"]}}



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    encoded = json.dumps(build(), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n"
    assert len(encoded.encode()) < 1_000_000, "Keep supplied originals bounded"
    if args.check: assert PATH.read_text() == encoded, "Transfer-network quantitative fixture changed; review original premises"
    else: PATH.write_text(encoded)


if __name__ == "__main__": main()
