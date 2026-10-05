"""Exact authoring-entrypoint counterpart; archived sources remain immutable.

The legacy branch retains its original implementations and export identities.
Only this finite source transformation and its extra dispatch module can be
projected by original CLI capture controls. No observed output is normalized.
"""
from __future__ import annotations

import ast
from contextlib import contextmanager
import hashlib
import inspect
import json
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
WITNESS = "tests/conformance/policy-entrypoint-source-counterpart-v1.json"
WITNESS_SHA256 = "75db98b705aac4c288ee744ae68caefeee07ac871716f0bc1fac91f15847cc51"
PATHS = frozenset(("src/biocompiler/__init__.py", "src/biocompiler/__main__.py", "pyproject.toml"))
ROUTES = PATHS - {"pyproject.toml"}
ENTRYPOINT = "src/biocompiler/entrypoint.py"
MODULE = "biocompiler.entrypoint"
CONSOLE = "from biocompiler.entrypoint import main\nraise SystemExit(main())\n"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def witness(root=ROOT):
    path = Path(root) / WITNESS
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 200_000,
            "Policy entrypoint witness missing, redirected or oversized")
    raw = path.read_bytes()
    require(sha(raw) == WITNESS_SHA256, "Policy entrypoint witness bytes changed")
    value = json.loads(raw)
    require(set(value["sources"]) == PATHS, "Policy entrypoint source census differs")
    for entry in value["sources"].values():
        require(all(sha(entry[side + "_source"].encode()) == entry[side + "_sha256"] for side in ("before", "after")),
                "Policy entrypoint complete source identity differs")
    before = ast.parse(value["sources"]["src/biocompiler/__init__.py"]["before_source"])
    after = ast.parse(value["sources"]["src/biocompiler/__init__.py"]["after_source"])
    imports = {alias.asname or alias.name: (node.module, alias.name)
               for node in before.body if isinstance(node, ast.ImportFrom) for alias in node.names}
    def assignments(tree):
        return {target.id: ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                for target in node.targets if isinstance(target, ast.Name)
                and target.id in ("__all__", "__version__", "_LEGACY_EXPORTS")}
    old, new = assignments(before), assignments(after)
    require(list(imports.items()) == list(new["_LEGACY_EXPORTS"].items())
            and old["__all__"] == new["__all__"] and old["__version__"] == new["__version__"],
            "Policy lazy exports differ from original identities or order")
    for name, before_text, after_text in (
        ("src/biocompiler/__main__.py", "from biocompiler.cli import main", "from biocompiler.entrypoint import main"),
        ("pyproject.toml", '"biocompiler.cli:main"', '"biocompiler.entrypoint:main"'),
    ):
        entry = value["sources"][name]
        require(entry["before_source"].count(before_text) == 1 and
                entry["before_source"].replace(before_text, after_text, 1) == entry["after_source"],
                "Policy dispatch has an unlisted source edit")
    entry = value["entrypoint"]
    require(entry["path"] == ENTRYPOINT and sha(entry["source"].encode()) == entry["sha256"],
            "Policy dispatch source identity differs")
    return value


def restore(name, current=None, *, root=ROOT):
    value = witness(root)
    require(name in PATHS, "Unknown policy entrypoint source")
    entry = value["sources"][name]
    current = (Path(root) / name).read_bytes() if current is None else current
    require(type(current) is bytes and current == entry["after_source"].encode(),
            "Current policy entrypoint differs from its exact counterpart: " + name)
    return entry["before_source"].encode(), {"path": name, "historical_sha256": entry["before_sha256"],
        "current_sha256": sha(current), "kind": "reviewed_policy_authoring_dispatch",
        "witness_sha256": WITNESS_SHA256}


def verify_source(root, name, historical_sha256):
    original, proof = restore(name, root=root)
    require(sha(original) == historical_sha256, "Policy entrypoint original source identity differs")
    return proof


def verify_entrypoint(root=ROOT):
    entry = witness(root)["entrypoint"]
    path = Path(root) / ENTRYPOINT
    require(path.is_file() and not path.is_symlink() and path.read_bytes() == entry["source"].encode(),
            "Current policy dispatch module differs from its exact counterpart")
    return entry


@contextmanager
def capture_dispatch(frozen):
    """Run a pinned frozen capture with only its console declaration adapted.

    Every original case, fault, assertion and byte-retention path is unchanged.
    The actual console shim and module import are retained in the new receipt.
    """
    declaration = witness()
    for name, identity in declaration["frozen_capture_sources"].items():
        require(sha((ROOT / name).read_bytes()) == identity, "Immutable capture source changed")
    verify_entrypoint()
    for name in PATHS:
        restore(name)
    source = inspect.getsource(frozen.capture)
    count = 2 if frozen.__name__.endswith("freeze_workflow_cli") else 1
    require(source.count('"biocompiler.cli:main"') == count, "Frozen capture console declaration count differs")
    source = source.replace('"biocompiler.cli:main"', '"biocompiler.entrypoint:main"')
    namespace = dict(vars(frozen))
    namespace["ENTRYPOINT"] = CONSOLE
    exec(compile(source, frozen.__file__, "exec"), namespace)
    # The selection capture delegates its child setup to the workflow helper.
    owner = getattr(frozen, "f", frozen)
    with patch.object(owner, "ENTRYPOINT", CONSOLE):
        yield namespace["capture"]


def capture(frozen):
    with capture_dispatch(frozen) as run:
        return run()


def project_environment(actual, projected, baseline):
    entry = verify_entrypoint()
    for row, projected_row in zip(actual["cases"], projected["cases"]):
        require(row["import_audit"]["modules"].get(MODULE) == {"path": ENTRYPOINT, "sha256": entry["sha256"]},
                "Actual CLI did not import the exact authoring dispatch module")
        del projected_row["import_audit"]["modules"][MODULE]
    environment = actual["capture_environment"]
    raw = CONSOLE.encode()
    require(environment["entrypoint_source"] == {"kind": "blob", "bytes": len(raw), "sha256": sha(raw)},
            "Actual CLI console dispatch bytes differ")
    projected["capture_environment"]["entrypoint_source"] = baseline["capture_environment"]["entrypoint_source"].copy()
    if "declared_console_entrypoint" in environment:
        require(environment["declared_console_entrypoint"] == "biocompiler.entrypoint:main",
                "Actual CLI console declaration differs")
        projected["capture_environment"]["declared_console_entrypoint"] = "biocompiler.cli:main"


def project_blobs(actual, blobs, baseline, old_blobs, projected_blobs):
    current = actual["capture_environment"]["entrypoint_source"]
    require(blobs.get(current["sha256"]) == CONSOLE.encode(), "Actual CLI console dispatch content differs")
    old = baseline["capture_environment"]["entrypoint_source"]
    del projected_blobs[current["sha256"]]
    projected_blobs[old["sha256"]] = old_blobs[old["sha256"]]


def native_reference_counterpart(raw):
    """Remove the exact source-only native reader prelude, preserving its body."""
    require(type(raw) is bytes and sha(raw) == "7c6f2680af96720945e4f944e40a759f5f1c925ba7a8bb1ced3cf29ff3389a44",
            "Native authoring source proof differs")
    start = raw.index(b"(* Authoring entrypoints add one exact outer source counterpart.")
    end = raw.index(b"let reference_original root name expected current =", start)
    block = raw[start:end]
    require(len(block) == 1338 and sha(block) == "ffcf1cd923119e20290ba15f41aecb9b63a0fcb8dcf48dc1ddcc5c752ae9e438",
            "Native authoring source proof block differs")
    restored = raw[:start] + raw[end:]
    inserted = b"  let current=policy_entrypoint_original root name current in\n"
    require(restored.count(inserted) == 1, "Native authoring source proof call differs")
    restored = restored.replace(inserted, b"", 1)
    require(sha(restored) == "e9db018e299f112c7e0c606edd6ea51ef1a98bf1bc28ffbb119589a173b1a853",
            "Native preceding package source proof differs")
    return restored
