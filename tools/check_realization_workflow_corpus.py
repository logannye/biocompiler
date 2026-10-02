#!/usr/bin/env python3
"""Explicit source-addition lineage for the immutable whole-workflow corpus.

This is a capture-only scope witness. It grants no product authority and never
relabels current source metadata as historical metadata. Existing source files
must retain every pinned byte; only separately reviewed additions are allowed.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib.abc
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/conformance/realization-workflow-v1.json"
CORPUS_PIN = "2f5e7636977f559e046776c1bb92bebf67c8f0e733ca463927f8d3a1aee3d77b"
# Each addition requires a fresh explicit review and hash. Wildcards and amended
# hashes for historical source files are deliberately unsupported.
REVIEWED_ADDITIONS = {
    "src/biocompiler/core_workflow.py": "c2e1a16518756f89f6bb84437e2f77634be2983986376e837b548d51047df9d0",
    "src/biocompiler/core_artifacts.py": "9cf24948c12d617dc783317b4f16330e1be69feba64cfec70767288556011e4e",
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def require(value, message):
    if not value:
        raise AssertionError(message)


def historical_sources():
    index = json.loads(CORPUS.read_bytes())
    require(index["inventory_fingerprint"] == CORPUS_PIN and digest(canonical(
        {key: value for key, value in index.items() if key != "inventory_fingerprint"})) == CORPUS_PIN,
        "Immutable workflow source-scope inventory changed")
    return index["source_files"]


def source_scope(actual, *, allow_missing_tests=False):
    historical = historical_sources()
    before = {row["path"]: row["sha256"] for row in historical}
    current = {row["path"]: row["sha256"] for row in actual}
    require(len(current) == len(actual), "Duplicate current workflow source")
    missing = set(before) - set(current)
    require(not missing or allow_missing_tests and all(path.startswith("tests/") for path in missing),
            "Historical workflow authority source is missing")
    for path in set(before) & set(current):
        require(before[path] == current[path], "Historical workflow source bytes changed: " + path)
    additions = {path: current[path] for path in sorted(set(current) - set(before))}
    for path, sha in additions.items():
        require(REVIEWED_ADDITIONS.get(path) == sha, "Unreviewed workflow source addition: " + path)
        require(digest((ROOT / path).read_bytes()) == sha, "Reviewed addition bytes changed")
    modules = []
    for path in additions:
        require(path.startswith("src/") and path.endswith(".py"), "Unreviewed addition import shape")
        modules.append(path[4:-3].replace("/", "."))
    return {
        "schema_version": "biocompiler.realization_workflow_source_scope.v1",
        "historical_corpus_pin": CORPUS_PIN,
        "historical_sources": historical,
        "actual_sources": actual,
        "historical_source_inventory_sha256": digest(canonical(historical)),
        "actual_source_inventory_sha256": digest(canonical(actual)),
        "reviewed_additions": [{"path": path, "sha256": sha} for path, sha in additions.items()],
        "denied_modules": modules,
        "omitted_tests_for_focused_instrumentation": sorted(missing),
        "comparison": "exact_original_observations_and_documents_after_explicit_historical_source_projection_only",
    }


@contextmanager
def deny_added_modules(scope):
    modules = tuple(scope["denied_modules"])
    require(all(name not in sys.modules for name in modules),
            "Reviewed added transport module was imported before original cohort capture")

    class Deny(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if any(fullname == name or fullname.startswith(name + ".") for name in modules):
                raise AssertionError("Original cohort tried to import excluded source addition: " + fullname)
            return None

    finder = Deny()
    sys.meta_path.insert(0, finder)
    try:
        yield
        require(all(name not in sys.modules for name in modules),
                "Original cohort imported a reviewed excluded transport module")
    finally:
        sys.meta_path.remove(finder)


def historical_projection(document, scope):
    require(document["source_files"] == scope["actual_sources"],
            "Source-scope receipt does not describe the actual capture")
    require(not scope["omitted_tests_for_focused_instrumentation"],
            "Focused capture cannot become a whole-corpus source projection")
    return {**document, "source_files": scope["historical_sources"]}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    sys.path[:0] = [str(ROOT), str(ROOT / "src")]
    from tools.freeze_realization_workflow import source_inventory
    scope = source_scope(source_inventory())
    args.output.write_bytes(canonical({"status": "source_lineage_verified",
        "native_execution": False, "scope": scope}) + b"\n")
