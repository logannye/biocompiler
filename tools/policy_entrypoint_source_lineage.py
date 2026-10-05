"""Exact authoring-entrypoint counterpart; archived sources remain immutable.

The legacy branch retains its original implementations and export identities.
Only this finite source transformation and its extra dispatch module can be
projected by original CLI capture controls. No observed output is normalized.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WITNESS = "tests/conformance/policy-entrypoint-source-counterpart-v1.json"
WITNESS_SHA256 = "680d26bc0107115e80ed4c6b8e9bae52698acf619e3ae4872e86d7f7ac3404e8"
PATHS = frozenset(("src/biocompiler/__init__.py", "src/biocompiler/__main__.py", "pyproject.toml"))
ROUTES = PATHS - {"pyproject.toml"}
ENTRYPOINT = "src/biocompiler/entrypoint.py"


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
