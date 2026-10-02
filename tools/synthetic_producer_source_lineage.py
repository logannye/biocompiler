"""Exact additive producer routes chained through immutable earlier witnesses.

The immediate parent and current whole-file bytes are separately pinned. Earlier
realization/workflow witnesses remain unchanged and validate the retained parent
before this stage validates its exact additive AST nodes. No source hash waiver,
product execution, behavior normalization or native acceptance occurs here.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WITNESS = ROOT / "tests/conformance/synthetic-producer-routing-source-lineage-v1.json"
WITNESS_SHA256 = "c643b4a7526955f2ca8e92a3a07c2d720e2e1fd145ef51bc78dcbcb0e357599f"
PARENT_REVISION = "d89f90d1c130c816ffad424316de65ee7053dbc3"
SYNTHETIC = "src/biocompiler/synthesis/synthetic.py"
SELECTION = "src/biocompiler/synthesis/selection.py"
COMPONENTS = "src/biocompiler/synthesis/components.py"
HISTORICAL = {
    SYNTHETIC: "94b9ff83b411d734ccd18c1ae7191d684be204151ebfc7141be8bfbfb35bdd4b",
    SELECTION: "6337ec4e394e0f684344d29b97bc0a411fb2aa4917d53d48e8082566397bae60",
    COMPONENTS: "ae548945c03b8dca75208abec47fee2e62bc03cceb7958ed645905813e5f2cb0",
}
ROUTES = {
    SYNTHETIC: ("generate_synthetic", "generate_record", "request, config=config, core=core"),
    SELECTION: ("select_synthetic", "select_record", "request, history, until=until, config=config, core=core"),
    COMPONENTS: ("adapt_synthetic_components", "adapt_record", "request, candidate, history, until=until, core=core"),
}
FUNCTIONS = {value[0]: path for path, value in ROUTES.items()}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def tree(raw):
    return ast.parse(raw, type_comments=True)


def structure(value):
    return ast.dump(value, include_attributes=False)


def function(module, name):
    nodes = [node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == name]
    require(len(nodes) == 1, "Producer route function census differs: " + name)
    return nodes[0]


def load_witness():
    raw = WITNESS.read_bytes()
    require(sha(raw) == WITNESS_SHA256, "Producer route witness bytes differ")
    value = json.loads(raw)
    require(set(value) == {"schema_version", "parent_revision", "entries"} and
            value["schema_version"] == "biocompiler.synthetic-producer-routing-source-lineage.v1" and
            value["parent_revision"] == PARENT_REVISION and type(value["entries"]) is list and
            len(value["entries"]) == len(HISTORICAL), "Producer route witness inventory differs")
    entries = {entry["path"]: entry for entry in value["entries"]}
    require(set(entries) == set(HISTORICAL), "Producer route path inventory differs")
    return entries


def strip_sdk(module, path):
    name, helper, arguments = ROUTES[path]
    node = function(module, name)
    require(node.args.kwonlyargs and structure(node.args.kwonlyargs[-1]) == structure(ast.arg(arg="core")) and
            structure(node.args.kw_defaults[-1]) == structure(ast.Constant(value=None)),
            "Producer optional core signature differs")
    expected = tree(f"if core is not None:\n    from biocompiler.synthetic_producer_backend import {helper}\n"
                    f"    return {helper}({arguments})\n").body[0]
    require(len(node.body) > 1 and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str) and structure(node.body[1]) == structure(expected),
            "Producer early optional route differs")
    node.args.kwonlyargs.pop()
    node.args.kw_defaults.pop()
    node.body.pop(1)


def verify_extension(entry, current, historical_sha256):
    require(type(entry) is dict and set(entry) == {"path", "historical_sha256", "historical_source", "routed_sha256", "routed_source"},
            "Producer route entry fields differ")
    path = entry["path"]
    require(path in HISTORICAL and historical_sha256 == HISTORICAL[path], "Unreviewed historical producer route")
    historical, routed = entry["historical_source"].encode(), entry["routed_source"].encode()
    require(sha(historical) == historical_sha256 == entry["historical_sha256"], "Historical producer route bytes differ")
    require(current == routed and sha(current) == entry["routed_sha256"], "Current producer route bytes differ")
    old, new = tree(historical), tree(current)
    strip_sdk(new, path)
    require(structure(old) == structure(new), "Historical producer default implementation AST differs")
    return {"path": path, "historical_sha256": historical_sha256, "current_sha256": sha(current),
            "kind": "reviewed_public_synthetic_producer_route", "witness_sha256": WITNESS_SHA256}


def verify_source(root, path, historical_sha256):
    source = Path(root) / path
    require(source.is_file() and not source.is_symlink(), "Missing or linked producer route source")
    current = source.read_bytes()
    if sha(current) == historical_sha256:
        return {"path": path, "historical_sha256": historical_sha256,
                "current_sha256": historical_sha256, "kind": "identical_bytes"}
    entry = load_witness().get(path)
    require(entry is not None, "Captured source bytes differ: " + path)
    latest = verify_extension(entry, current, HISTORICAL[path])
    if historical_sha256 == HISTORICAL[path]:
        return latest
    parent = entry["historical_source"].encode()
    if path == SYNTHETIC:
        from tools import realization_source_lineage as earlier
        previous = earlier.verify_route_extension(earlier.load_witness()[path], parent, historical_sha256)
        previous["witness_sha256"] = earlier.WITNESS_SHA256
    else:
        raise ValueError("Unreviewed historical producer source identity")
    require(previous["current_sha256"] == latest["historical_sha256"], "Producer source witness chain is discontinuous")
    return {"path": path, "historical_sha256": historical_sha256, "current_sha256": latest["current_sha256"],
            "kind": "reviewed_public_synthetic_producer_route_chain", "witness_sha256": WITNESS_SHA256,
            "lineage": [previous, latest]}
