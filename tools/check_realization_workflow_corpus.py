#!/usr/bin/env python3
"""Explicit source-addition lineage for the immutable whole-workflow corpus.

This is a capture-only scope witness. It grants no product authority and never
relabels current source metadata as historical metadata. Historical bytes stay
pinned; two exactly witnessed routes preserve the complete original default AST.
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
    "src/biocompiler/core_pipeline_manager.py": "0add1b9594c4632b90e7333eabf89af3f174a3faabcdaec255430380d369ff73",
    "src/biocompiler/core_pipeline_callback_session.py": "0ff388509eb9c123b87cf5decc1f35cf5eaca61a02d84a756beba7150de17018",
    "src/biocompiler/pipeline_callback_objects.py": "ac5198795c3e80cff511e0fe372dc578a983d8be947e41dd9debd9f719da9eec",
    "src/biocompiler/core_pipeline_session.py": "b0c744d8f3a38b1681805250ccf93884ba866678527cf366bcf08ff326da080d",
    "src/biocompiler/core_synthetic_inspection.py": "5ab68d6f1dac300af1e0d7431f5ba45aa2df493c1f446a8ccd67b56ae831178f",
    "src/biocompiler/core_synthetic_producer_public.py": "15db52841e774d4fdf42ed937dfe173ca844cae920fb6419bbc54eec70c31082",
    "src/biocompiler/synthetic_producer_cli.py": "4e500dd094e41841fa15635b1be6a805a0b3b992de574dda888f4d91fa881221",
    "src/biocompiler/core_synthetic_producer.py": "233ae7ffd5a10e7158b1ac833194aa4b5b05de5334e73adf77aad9d081fb1917",
    "src/biocompiler/synthetic_producer_backend.py": "99584aaa6be87849ebf1cc5eea0ba0821b86f4ca03abc190b0261a8903647db3",
    "src/biocompiler/core_workflow.py": "43b57b87a2d89db200463d8aed8b7eea7e262cf1c4ea02c772843598dbda90df",
    "src/biocompiler/core_artifacts.py": "77cf4dc31efb782c7fbb44fe8e79714a60e2e20374f9e7569fdce8f70d8ec59a",
    "src/biocompiler/workflow_backend.py": "81958a4fc1147b2ea10eae7c7bac15a68338b1cb21b738805ae04538c7bdc1db",
    "src/biocompiler/core_workflow_authority.py": "ded29c7cd4c16241812bd7f677b0c962d185a724fef1cd7294c7e899c7c32d66",
    "src/biocompiler/workflow_cli.py": "641cf7f6451e52c5dd4a09a28c75c89329191aa373aed36cc9dc92c573207bd5",
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
    routes = []
    for path in sorted(set(before) & set(current)):
        if before[path] != current[path]:
            from tools.workflow_source_lineage import HISTORICAL
            from tools.synthetic_producer_source_lineage import HISTORICAL as PRODUCERS
            from tools.realization_source_lineage import verify_captured_source
            require(path in HISTORICAL or path in PRODUCERS, "Historical workflow source bytes changed: " + path)
            try:
                route = verify_captured_source(ROOT, {"path": path, "sha256": before[path]})
            except ValueError as error:
                raise AssertionError("Historical workflow source bytes changed: " + path) from error
            require(route["current_sha256"] == current[path], "Historical workflow source bytes changed: " + path)
            routes.append(route)
    additions = {path: current[path] for path in sorted(set(current) - set(before))}
    for path, sha in additions.items():
        require(REVIEWED_ADDITIONS.get(path) == sha, "Unreviewed workflow source addition: " + path)
        require(digest((ROOT / path).read_bytes()) == sha, "Reviewed addition bytes changed")
    modules = []
    for path in additions:
        require(path.startswith("src/") and path.endswith(".py"), "Unreviewed addition import shape")
        modules.append(path[4:-3].replace("/", "."))
    result = {
        "schema_version": "biocompiler.realization_workflow_source_scope.v2" if routes else "biocompiler.realization_workflow_source_scope.v1",
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
    if routes:
        result["reviewed_routes"] = routes
    return result


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
