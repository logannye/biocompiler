"""Author explicit artificial compound graphs; never evaluate source or graph.

Wiring and expression endpoints below are supplied fixture literals, not output
from the implementation producer. Every material case remains an independently
supplied conditional premise; identical RNA does not imply equal behavior.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

from biocompiler import policy as p
from generate_policy_material_lifecycle_fixture import SEED, SEED_REQUEST, author, digest, pin

OUTPUT = Path(__file__).resolve().parents[1] / "core/test/data/policy_material_compound_v01.json"


def endpoint(node: str, port: str = "out") -> dict:
    return {"node": node, "port": port}


def build_case(seed: dict, repeated: bool) -> dict:
    case = author(seed, "continuous", "defer")
    identity = "repeated_reasons" if repeated else "single_reason"
    case.update(id=identity, ordered_reason_width=2 if repeated else 1)
    request, parts = case["request"], case["candidate_parts"]
    original = request["implementation_request"]
    source = p.from_data(original["document"], p.BuildRequest)
    observation = next(d for d in source.program.declarations if isinstance(d, p.Observation)).expression
    select_guard = p.all_of(observation, p.any_of(observation if repeated else p.FALSE, p.TRUE))
    exclude_guard = p.any_of(p.not_(observation), p.all_of(
        p.not_(observation) if repeated else p.FALSE, p.FALSE if repeated else p.TRUE))
    write_true = p.all_of(p.TRUE, p.any_of(p.FALSE, p.TRUE))
    write_false = p.any_of(p.FALSE, p.all_of(p.FALSE, p.TRUE))
    declarations = []
    for item in source.program.declarations:
        if isinstance(item, p.StateStore) and item.id == "selected":
            item = replace(item, initial="unknown")
        if isinstance(item, p.Rule):
            values = (write_true, write_false) if item.id == "select" else (write_false, write_true)
            item = replace(item, when=select_guard if item.id == "select" else exclude_guard,
                assignments=tuple(replace(assignment, value=value) for assignment, value in zip(item.assignments, values, strict=True)))
        declarations.append(item)
    source = replace(source, program=replace(source.program, id=f"compound.{identity}", declarations=tuple(declarations),
        source_map=tuple(replace(span, file=f"policy_compound_{identity}.py") for span in source.program.source_map)))
    original["document"] = p.to_data(source)
    library = original["implementation_library"]
    library["id"] = "compound.complete.library"
    prototype = deepcopy(next(m for m in library["models"] if m["body"]["primitive"] == "truth_register"))
    specifications = [("compound.all2", "truth_all", {"arity": 2}),
        ("compound.any2", "truth_any", {"arity": 2}),
        ("compound.unknown_register", "truth_register", {"initial": "unknown", "writers": 2})]
    for identity_model, primitive, configuration in specifications:
        model = deepcopy(prototype)
        model["identity"]["id"] = identity_model
        model["body"].update(primitive=primitive, configuration=configuration)
        model["configuration_digest"] = digest(configuration)
        pin(model)
        library["models"].append(model)
    models = {model["identity"]["id"]: model for model in library["models"]}
    original["catalog_bindings"][0]["models"] = [deepcopy(model["identity"]) for model in library["models"]]
    graph = parts["implementation"]
    selected = next(node for node in graph["nodes"] if node["id"] == "selected")
    selected.update(model=deepcopy(models["compound.unknown_register"]["identity"]),
        configuration_digest=models["compound.unknown_register"]["configuration_digest"])
    added = [("guard_select_any", "compound.any2"), ("guard_select_all", "compound.all2"),
        ("guard_exclude_all", "compound.all2"), ("guard_exclude_any", "compound.any2"),
        ("write_true_any", "compound.any2"), ("write_true_all", "compound.all2"),
        ("write_false_all", "compound.all2"), ("write_false_any", "compound.any2")]
    for node, model_id in added:
        model = models[model_id]
        graph["nodes"].append({"id": node, "model": deepcopy(model["identity"]), "configuration_digest": model["configuration_digest"]})
        graph["semantic_exports"].append(endpoint(node))
    feeds = {
        ("select_gate", "guard"): endpoint("guard_select_all"),
        ("exclude_gate", "guard"): endpoint("guard_exclude_any"),
        ("attempt", "authorization"): endpoint("guard_select_all"),
        ("select_commit", "value0"): endpoint("write_true_all"),
        ("select_commit", "value1"): endpoint("write_false_any"),
        ("exclude_commit", "value0"): endpoint("write_false_any"),
        ("exclude_commit", "value1"): endpoint("write_true_all"),
    }
    for wire in graph["wires"]:
        key = (wire["consumer"]["node"], wire["consumer"]["port"])
        if key in feeds:
            wire["producer"] = feeds[key]
    # Explicit complete ordered operands. Duplicate observation ancestry in the
    # second case changes reason multiplicity, without changing truth results.
    operands = [
        ("guard_select_any", [endpoint("evidence", "value") if repeated else endpoint("false"), endpoint("true")]),
        ("guard_select_all", [endpoint("evidence", "value"), endpoint("guard_select_any")]),
        ("guard_exclude_all", [endpoint("not") if repeated else endpoint("false"), endpoint("false") if repeated else endpoint("true")]),
        ("guard_exclude_any", [endpoint("not"), endpoint("guard_exclude_all")]),
        ("write_true_any", [endpoint("false"), endpoint("true")]),
        ("write_true_all", [endpoint("true"), endpoint("write_true_any")]),
        ("write_false_all", [endpoint("false"), endpoint("true")]),
        ("write_false_any", [endpoint("false"), endpoint("write_false_all")]),
    ]
    for node, inputs in operands:
        graph["wires"].extend({"consumer": endpoint(node, f"in{index}"), "producer": producer}
            for index, producer in enumerate(inputs))
    # Supply the complete source occurrence inventory for these explicit trees.
    # This is bookkeeping over authored expressions/wires, with no evaluation.
    roots = {"/document/program/declarations/9/when": ("predicate", select_guard, endpoint("guard_select_all")),
        "/document/program/declarations/10/when": ("predicate", exclude_guard, endpoint("guard_exclude_any"))}
    for declaration, values in ((9, (write_true, write_false)), (10, (write_false, write_true))):
        for index, expression in enumerate(values):
            roots[f"/document/program/declarations/{declaration}/assignments/{index}/value"] = (
                "state_write", expression, endpoint("write_true_all" if expression == write_true else "write_false_any"))
    incoming = {(wire["consumer"]["node"], wire["consumer"]["port"]): wire["producer"] for wire in graph["wires"]}
    inventory = [row for row in graph["occurrences"] if not any(
        row["source_path"] == path or row["source_path"].startswith(path + "/") for path in roots)]

    def occurrence(path: str, role: str, expression: p.Expr, output: dict) -> None:
        inventory.append({"source_path": path, "role": role,
            "disposition": "constant" if expression.op in ("literal", "parameter") else "executable", "targets": [deepcopy(output)]})
        for index, child in enumerate(expression.args):
            port = "in" if expression.op == "not" else f"in{index}"
            occurrence(f"{path}/args/{index}", role, child, incoming[(output["node"], port)])

    for path, (role, expression, output) in roots.items():
        occurrence(path, role, expression, output)
    graph["occurrences"] = sorted(inventory, key=lambda row: row["source_path"])
    graph["authority"].update(source_artifact_digest=digest(original["document"]), library_digest=digest(library))
    contract = request["material_contract"]
    contract["identity"]["id"] = f"artificial.compound.{identity}"
    kernel = contract["body"]["kernel"]
    kernel["library_digest"] = digest(library)
    kernel["nodes"] = [{"local_id": f"local.{node['id']}", "model": deepcopy(models[node["model"]["id"]])} for node in graph["nodes"]]

    def local(output: dict) -> dict:
        return endpoint(f"local.{output['node']}", output["port"])

    kernel["wires"] = [{"from": local(wire["producer"]), "to": local(wire["consumer"])} for wire in graph["wires"]]
    kernel["semantic_exports"] = [local(output) for output in graph["semantic_exports"]]
    targets = [{"kind": kind, "id": node["local_id"]} for node in kernel["nodes"] for kind in ("primitive", "configuration", "replication")]
    targets += [{"kind": "wire", "index": i} for i in range(len(kernel["wires"]))]
    targets += [{"kind": "external_input", "id": row["id"]} for row in kernel["inputs"]]
    targets += [{"kind": "atomic_group", "id": row["id"]} for row in kernel["atomic_groups"]]
    targets += [{"kind": "semantic_export", "index": i} for i in range(len(kernel["semantic_exports"]))] + [{"kind": "slot_layout"}]
    sites = deepcopy(contract["body"]["carriers"][0]["sites"])
    contract["body"]["carriers"] = [{"target": target, "sites": deepcopy(sites)} for target in targets]
    parts["material_binding"]["nodes"] = [{"local_id": f"local.{node['id']}", "node_id": node["id"]} for node in graph["nodes"]]
    pin(contract)
    request["catalog_binding"]["material_contract"] = deepcopy(contract["identity"])
    parts["material_binding"]["contract_digest"] = digest(contract)
    context = request["context"]
    # No additional persistent/control/input record categories arise from pure
    # truth nodes: 2 slots, 2 edge memories, 2 gates, 5 writes/requests per
    # control inventory, 2 historical attempts, and unchanged input grammar.
    # Queue = 2*(2+1+2+2+5)+4*2+2 = 34; causes=34*7=238.
    # The duplicated DAG ancestry needs two ordered reason slots, including
    # duplicates. Unknown register truth remains defined (not missing evidence).
    assert len(graph["nodes"]) == 23 and len(kernel["wires"]) == 38 and len(targets) == 140
    context["record_layout"].update(kernel_digest=digest(kernel), ordered_reason_slots=2 if repeated else 1)
    for provider in context["providers"]:
        for capacity in provider["body"]["capacities"]:
            capacity["record_layout_digest"] = digest(context["record_layout"])
        pin(provider)
    case["expected"].update(request_fingerprint=digest(request), node_count=23, wire_count=38, carrier_count=140,
        initial_selected="unknown", initial_excluded=False, ordered_reason_width=2 if repeated else 1,
        queue_records=34, ordered_cause_slots=238, maximum_tick=11, identifier_bytes=384)
    return case


def build() -> dict:
    seed = json.loads(SEED.read_text())
    if digest(seed["request"]) != SEED_REQUEST:
        raise ValueError("Complete original seed changed; independently review before regeneration")
    return {"schema_version": "biocompiler.policy_material_compound_literals.v0.1",
        "notice": "Artificial source/graph/material fixtures, not empirical mechanisms. Native acceptance pending.",
        "limits": seed["limits"], "cases": [build_case(seed, False), build_case(seed, True)]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    encoded = json.dumps(build(), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.check:
        if OUTPUT.read_text() != encoded:
            raise SystemExit("Compound fixture differs from inert authoring source")
    else:
        OUTPUT.write_text(encoded)


if __name__ == "__main__":
    main()
