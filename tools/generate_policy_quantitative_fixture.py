"""Artificial independent sampled-reservoir originals; no native computation."""
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
PATH = ROOT / "core/test/data/policy_quantitative_v01.json"
PROFILE = "biocompiler.policy_sampled_reservoir_component_mrna.v0.1"
STATES = ["q0", "q1", "q2", "q3"]
LEVELS = ["0", "0.5", "1", "1.5"]
SPEC = {"id": "sampled_reservoir", "states": STATES, "terminal": [], "effects": ["response"],
    "transitions": [(identity, source, destination, "updated", guard, effect)
        for identity, source, destination, guard, effect in (
            ("up0", "q0", "q1", "positive", None), ("down0", "q0", "q0", "negative", None),
            ("up1", "q1", "q2", "positive", "response"), ("down1", "q1", "q0", "negative", None),
            ("up2", "q2", "q3", "positive", None), ("down2", "q2", "q1", "negative", None),
            ("up3", "q3", "q3", "positive", None), ("down3", "q3", "q2", "negative", None))]}


def law():
    return {"schema_version": "biocompiler.policy_sampled_reservoir.v0.1",
        "profile": "biocompiler.policy_sampled_saturating_reservoir.v0.1",
        "substance": "fixture.reservoir.amount", "compartment": "fixture.executor.reservoir", "unit": p.to_data(p.COUNT),
        **{key: p.to_data(p.quantity(amount, p.COUNT)) for key, amount in (
            ("quantum", "0.5"), ("capacity", "1.5"), ("threshold", "1"), ("initial", "0"))},
        "sample_period": p.to_data(p.quantity(1, p.SECOND))}


def build():
    seed_bytes = (shared.DATA / "policy_staged_material_seed_v01.json").read_bytes()
    assert hashlib.sha256(seed_bytes).hexdigest() == shared.SEED_SHA256
    seed = json.loads(seed_bytes)
    library, fragments, links = finite.declared_fragments(SPEC)
    for model in library["models"]:
        if model["body"]["primitive"] == "evidence_bank": model["body"]["configuration"]["freshness_ticks"] = 1
        if model["body"]["primitive"] == "machine_bank": model["body"]["configuration"]["initial"] = "q0"
        model["identity"]["content_fingerprint"] = shared.digest(model["body"])
        model["configuration_digest"] = shared.digest(model["body"]["configuration"])
    models = {row["identity"]["id"]: row for row in library["models"]}
    for fragment in fragments.values():
        for node in fragment["nodes"]: node["model"] = deepcopy(models[node["model"]["identity"]["id"]])
    original = finite.implementation_request(SPEC, library)
    document = p.from_data(original["document"], p.BuildRequest)
    declarations = tuple(replace(row, initial="q0") if isinstance(row, p.Machine) else
        replace(row, freshness=p.quantity(1, p.SECOND)) if isinstance(row, p.Observation) else
        replace(row, horizon=p.quantity(15, p.SECOND)) if isinstance(row, p.Requirement) else row
        for row in document.program.declarations)
    document = replace(document, program=replace(document.program, declarations=declarations),
                       assurance=replace(document.assurance, horizon=p.quantity(15, p.SECOND)))
    original["document"] = p.to_data(document)
    domain = original["operating_domain"]
    domain.update(horizon_ticks=15, observation_factors=[], feedback_factors=[], foreign_feedback_factors=[])
    domain["lifecycle_factors"] = [{"slots": ["e1", "e2"], "ticks": [13], "actions": ["keep", "reset"]}]
    domain["fixed_observations"] = [{"available_tick": tick, "observed_tick": tick, "observation": "condition", "slot": slot,
        "status": "missing" if value is None else "valid", "value": value}
        for tick, value in ((0, False), (1, True), (2, True), (3, None), (4, True), (5, True),
                            (7, False), (8, False), (9, False), (10, False), (11, True), (12, True), (14, True))
        for slot in ("e1", "e2")]
    components, rule, union, molecule = finite.composition(SPEC, fragments, links, seed)
    component = components["control"]
    local = {node["id"]: node["model"]["identity"] for node in fragments["control"]["nodes"]}
    component.update(schema_version="biocompiler.policy_component_material.v0.2", profile="biocompiler.policy_quantitative_local_material.v0.1")
    component["body"]["quantitative_contracts"] = [{"id": "reservoir", "mechanism": law(),
        "state": {"node": "machine", "model": local["machine"], "values": [
            {"state": state, "quantity": p.to_data(p.quantity(amount, p.COUNT))} for state, amount in zip(STATES, LEVELS)]},
        "input": {"node": "evidence", "model": local["evidence"], "value_port": "value", "updated_port": "updated"},
        "output": {"boundary": "response.request", "model": local["commit2"]}}]
    component["identity"]["content_fingerprint"] = shared.digest(component["body"])
    rule["body"]["components"][0]["component"] = deepcopy(component["identity"])
    rule["identity"]["content_fingerprint"] = shared.digest(rule["body"])
    context, inputs, resources = finite.context(SPEC, original, components, rule, union)
    context["record_layout"].update(horizon_ticks=15, maximum_tick=17)
    layout_digest = shared.digest(context["record_layout"])
    def extend_availability(value):
        if isinstance(value, dict):
            if "duration_min" in value and "duration_max" in value:
                value.update(duration_min="15", duration_max="15")
            for child in value.values(): extend_availability(child)
        elif isinstance(value, list):
            for child in value: extend_availability(child)
    for provider in context["providers"]:
        extend_availability(provider["body"])
        for capacity in provider["body"]["capacities"]:
            capacity["record_layout_digest"] = layout_digest
            if capacity["unit"] == "evidence_records": capacity["quantity"] = 16
        provider["identity"]["content_fingerprint"] = shared.digest(provider["body"])
    bridge = original["catalog_bindings"][0]
    request = {"schema_version": "biocompiler.policy_component_material_request.v0.8", "profile": PROFILE,
        "implementation_request": original,
        "component_library": {"schema_version": "biocompiler.policy_component_library.v0.1",
            "profile": "biocompiler.policy_exact_component_library.v0.1", "components": list(components.values())},
        "composition_rule": rule, "catalog_binding": {**{key: bridge[key] for key in ("entry_id", "entry_version", "entry_digest", "operation", "realization")},
            "components": rule["body"]["components"], "rule": rule["identity"]},
        "input_bindings": inputs, "resource_bindings": resources, "context": context,
        "budgets": {"profile": "biocompiler.policy_component_material_resources.v0.1", "max_work": 500000000,
            "max_report_bytes": 8323072, "max_report_nodes": 249968},
        "quantitative": {"mechanism": law(), "selection": {"instance": "control", "component": deepcopy(component["identity"]), "contract": "reservoir"},
            "source": {"machine": "machine", "observation": "condition", "effect": "response"}}}
    table = [{"source": state, "input": truth, "destination": destination, "request": requested}
        for state, positive, negative, requested in (("q0", "q1", "q0", False), ("q1", "q2", "q0", True),
                                                    ("q2", "q3", "q1", False), ("q3", "q3", "q2", False))
        for truth, destination, requested in (("true", positive, requested), ("false", negative, False), ("unknown", state, False))]
    limits = shared.original()["limits"]
    # Sixteen complete ticks publish at least two inventories of 63 live
    # output rows; their fixed charges alone exceed the old one-million cap.
    limits["candidate"]["max_work"] = 10_000_000
    return {"schema_version": "biocompiler.policy_quantitative_literals.v0.1",
        "notice": "Artificial supplied quantitative component-to-RNA contract. No native acceptance or biological evidence is asserted.",
        "seed_sha256": shared.SEED_SHA256, "request": request, "limits": limits,
        "expected": {"molecule": molecule, "sequence": "CCAUGGCUUAAGGAAAA", "ordered_union": union, "table": table,
            "states": STATES, "levels": LEVELS, "crossing_transition": "up1", "crossing_commit": "commit2"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    encoded = json.dumps(build(), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n"
    assert len(encoded.encode()) < 1_000_000, "Keep quantitative originals bounded"
    if args.check:
        assert PATH.read_text() == encoded, "Quantitative fixture changed; review supplied originals"
    else:
        PATH.write_text(encoded)


if __name__ == "__main__":
    main()
