"""Verify historical capture source or the narrowly pinned optional-core edit.

Old corpus hashes continue to identify the exact archived Python source. Current
source is separately pinned; removing only the five reviewed optional routes
must recover the entire historical AST. This is source lineage, not a substitute
for replaying the original observations or validating the native implementation.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WITNESS = ROOT / "tests/conformance/realization-routing-source-lineage-v1.json"
WITNESS_SHA256 = "c84f36b02467ac245611c6cf899a0c85344147ef6abaa0e811992ecf578cb994"
ROUTES = {
    "src/biocompiler/compiler/components.py": (
        "check_component_behavior", "check_component_assembly"),
    "src/biocompiler/synthesis/synthetic.py": ("check_synthetic_candidate",),
    "src/biocompiler/verification/realization.py": (
        "realization_dependencies", "check_realization"),
}


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_witness():
    raw = WITNESS.read_bytes()
    if sha256(raw) != WITNESS_SHA256:
        raise ValueError("Source-lineage witness bytes differ")
    value = json.loads(raw)
    if (value["schema"] != "biocompiler.realization-routing-source-lineage.v1"
            or len(value["entries"]) != len(ROUTES)
            or {entry["path"] for entry in value["entries"]} != set(ROUTES)):
        raise ValueError("Source-lineage witness inventory differs")
    return {entry["path"]: entry for entry in value["entries"]}


def verify_route_extension(entry, current: bytes, historical_sha256: str):
    """Check both byte identities and whole-file AST preservation, without exec."""
    path = entry["path"]
    expected = ROUTES.get(path)
    if expected is None or tuple(entry["functions"]) != expected:
        raise ValueError("Unreviewed source route")
    original = entry["historical_source"].encode("utf-8")
    if (sha256(original) != historical_sha256
            or entry["historical_sha256"] != historical_sha256):
        raise ValueError("Historical source bytes differ")
    if sha256(current) != entry["routed_sha256"]:
        raise ValueError("Current routed source bytes differ")
    old_tree = ast.parse(original, filename=path, type_comments=True)
    new_tree = ast.parse(current, filename=path, type_comments=True)
    guard = ast.dump(ast.parse("core is not None", mode="eval").body)
    found = []
    for node in new_tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name not in expected:
            continue
        found.append(node.name)
        if (not node.args.kwonlyargs or node.args.kwonlyargs[-1].arg != "core"
                or node.args.kwonlyargs[-1].annotation is not None
                or not isinstance(node.args.kw_defaults[-1], ast.Constant)
                or node.args.kw_defaults[-1].value is not None):
            raise ValueError("Optional core signature differs")
        routes = [item for item in node.body if isinstance(item, ast.If)
                  and ast.dump(item.test) == guard]
        if len(routes) != 1 or routes[0].orelse:
            raise ValueError("Optional core guard differs")
        node.args.kwonlyargs.pop()
        node.args.kw_defaults.pop()
        node.body.remove(routes[0])
    if tuple(found) != expected:
        raise ValueError("Optional core function census differs")
    if ast.dump(new_tree) != ast.dump(old_tree):
        raise ValueError("Historical default implementation AST differs")
    return {"path": path, "historical_sha256": historical_sha256,
            "current_sha256": sha256(current), "kind": "reviewed_optional_core_route"}


def verify_captured_source(root: Path, entry):
    """Reject every uncaptured edit except the separately pinned routing witness."""
    current = (root / entry["path"]).read_bytes()
    if sha256(current) == entry["sha256"]:
        return {"path": entry["path"], "historical_sha256": entry["sha256"],
                "current_sha256": entry["sha256"], "kind": "identical_bytes"}
    from tools.synthetic_selection_cli_source_lineage import CLI, verify_source as verify_selection_cli
    if entry["path"] == CLI:
        return verify_selection_cli(root, entry["sha256"])
    from tools.synthetic_producer_source_lineage import HISTORICAL as PRODUCERS, verify_source as verify_producer
    if entry["path"] in PRODUCERS:
        return verify_producer(root, entry["path"], entry["sha256"])
    from tools.manager_registration_source_lineage import HISTORICAL as MANAGERS, verify_source as verify_manager
    if entry["path"] in MANAGERS:
        return verify_manager(root, entry["path"], entry["sha256"])
    witness = load_witness().get(entry["path"])
    if witness is None:
        from tools.workflow_source_lineage import HISTORICAL, verify_source
        if entry["path"] in HISTORICAL:
            return verify_source(root, entry["path"], entry["sha256"])
        raise ValueError("Captured source bytes differ: " + entry["path"])
    return verify_route_extension(witness, current, entry["sha256"])
