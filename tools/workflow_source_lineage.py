"""Exact public-workflow route witness; historical semantics stay byte-addressed.

Only two separately pinned files may differ. Their entire old and current bytes
are retained. Removing the explicitly enumerated route AST nodes must recover
the complete original AST. This grants no native or behavioral acceptance.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WITNESS = ROOT / "tests/conformance/workflow-routing-source-lineage-v1.json"
WITNESS_SHA256 = "10ad10ead5c832bc8dd4072a08d81e3c128d1bdf519f596569e487520421fab1"
WORKFLOW = "src/biocompiler/compiler/verification_workflow.py"
CLI = "src/biocompiler/cli.py"
HISTORICAL = {
    WORKFLOW: "04d9818933ae3ded190d4139023340f88c1eb7d8f2325173c4c77c056f7b7dd6",
    CLI: "eec53f1b4c3775b40236fc1e9f2bf1f12a37dd0f5a63e4083d1eb9f5a7551fd0",
}
FUNCTIONS = ("run_synthetic_verification", "replay_synthetic_verification")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def tree(raw):
    return ast.parse(raw, type_comments=True)


def structure(node):
    return ast.dump(node, include_attributes=False)


def load_witness():
    raw = WITNESS.read_bytes()
    require(sha(raw) == WITNESS_SHA256, "Workflow route witness bytes differ")
    value = json.loads(raw)
    require(set(value) == {"schema_version", "entries"} and
            value["schema_version"] == "biocompiler.workflow-routing-source-lineage.v1" and
            type(value["entries"]) is list and len(value["entries"]) == 2,
            "Workflow route witness inventory differs")
    result = {entry["path"]: entry for entry in value["entries"]}
    require(set(result) == set(HISTORICAL), "Workflow route witness path inventory differs")
    return result


def _function(module, name):
    matches = [node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == name]
    require(len(matches) == 1, "Workflow route function census differs: " + name)
    return matches[0]


def _strip_sdk(module):
    for name, helper, arguments in (
        (FUNCTIONS[0], "run_record", "request, core=core"),
        (FUNCTIONS[1], "replay_record", "record, expected_request=expected_request, core=core"),
    ):
        function = _function(module, name)
        require(bool(function.args.kwonlyargs) and
                structure(function.args.kwonlyargs[-1]) == structure(ast.arg(arg="core")) and
                structure(function.args.kw_defaults[-1]) == structure(ast.Constant(value=None)),
                "Workflow optional core signature differs")
        expected = tree(f"if core is not None:\n    from biocompiler.workflow_backend import {helper}\n"
                        f"    return {helper}({arguments})\n").body[0]
        require(len(function.body) > 1 and isinstance(function.body[0], ast.Expr) and
                isinstance(function.body[0].value, ast.Constant) and
                isinstance(function.body[0].value.value, str) and
                structure(function.body[1]) == structure(expected),
                "Workflow early optional route differs")
        function.args.kwonlyargs.pop()
        function.args.kw_defaults.pop()
        function.body.pop(1)


def _strip_cli(module):
    # These exact reviewed nodes are populated from the fixed implementation,
    # never from witness-provided executable text or a broad matching pattern.
    from tools.workflow_route_shapes import CLI_HELPER, CLI_BRANCH, CLI_REGISTRATION
    helper = _function(module, "_workflow_core_arguments")
    require(structure(helper) == structure(tree(CLI_HELPER).body[0]), "CLI option helper differs")
    helper_index = module.body.index(helper)
    require(helper_index > 0 and helper_index + 1 < len(module.body) and
            getattr(module.body[helper_index - 1], "name", None) == "_architecture_core_arguments" and
            getattr(module.body[helper_index + 1], "name", None) == "main", "CLI option helper placement differs")
    module.body.remove(helper)
    command = _function(module, "_verification_command")
    require(structure(command.body[0]) == structure(tree(CLI_BRANCH).body[0]), "CLI selected-core branch differs")
    command.body.pop(0)
    main = _function(module, "main")
    expected = {name: structure(tree(code).body[0]) for name, code in CLI_REGISTRATION.items()}
    predecessors = {
        "workflow": structure(tree('workflow.add_argument("--output", type=Path, help="Atomic JSON report destination")').body[0]),
        "replay": structure(tree('replay.add_argument("--output", type=Path)').body[0]),
    }
    found = []
    for node in ast.walk(main):
        for field in ("body", "orelse", "finalbody"):
            body = getattr(node, field, None)
            if not isinstance(body, list):
                continue
            for item in list(body):
                for name, shape in expected.items():
                    if structure(item) == shape:
                        index = body.index(item)
                        require(index > 0 and structure(body[index - 1]) == predecessors[name],
                                "CLI hidden option registration placement differs")
                        require((name == "replay" and node is main) or
                                (name == "workflow" and isinstance(node, ast.For) and
                                 structure(node.target) == structure(ast.Name(id="operation", ctx=ast.Store())) and
                                 structure(node.iter) == structure(tree("('check', 'explore', 'reduce')").body[0].value) and
                                 index == len(body) - 1), "CLI hidden option registration owner differs")
                        found.append(name)
                        body.remove(item)
    require(sorted(found) == sorted(expected), "CLI hidden option registration census differs")


def verify_extension(entry, current, historical_sha256):
    require(type(entry) is dict and set(entry) == {
        "path", "historical_sha256", "historical_source", "routed_sha256", "routed_source"},
        "Workflow route entry fields differ")
    path = entry["path"]
    require(path in HISTORICAL and historical_sha256 == HISTORICAL[path], "Unreviewed historical workflow route")
    historical = entry["historical_source"].encode("utf-8")
    routed = entry["routed_source"].encode("utf-8")
    require(sha(historical) == historical_sha256 == entry["historical_sha256"], "Historical workflow route bytes differ")
    require(current == routed and sha(current) == entry["routed_sha256"], "Current workflow route bytes differ")
    old, new = tree(historical), tree(current)
    (_strip_sdk if path == WORKFLOW else _strip_cli)(new)
    require(structure(old) == structure(new), "Historical workflow default implementation AST differs")
    return {"path": path, "historical_sha256": historical_sha256,
            "current_sha256": sha(current), "kind": "reviewed_public_workflow_route",
            "witness_sha256": WITNESS_SHA256}


def verify_source(root, path, historical_sha256):
    current_path = Path(root) / path
    require(current_path.is_file() and not current_path.is_symlink(), "Missing or linked workflow route source")
    current = current_path.read_bytes()
    if sha(current) == historical_sha256:
        return {"path": path, "historical_sha256": historical_sha256,
                "current_sha256": historical_sha256, "kind": "identical_bytes"}
    entry = load_witness().get(path)
    require(entry is not None, "Captured source bytes differ: " + path)
    return verify_extension(entry, current, historical_sha256)
