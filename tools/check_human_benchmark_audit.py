"""Offline integrity/relationship check for the M11.1 audit, not biological validation."""

import hashlib
import json
from pathlib import Path, PurePosixPath
import sys


ROOT = Path(__file__).resolve().parents[1]
AUDIT = Path("data/evidence/m11-human-benchmarks")
DIMENSIONS = {
    "exact_sequence", "complete_molecule", "quantitative_measurements",
    "available_model", "biological_context", "reuse_terms", "material_correspondence",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def indexed(rows, label):
    ids = [row["id"] for row in rows]
    require(len(ids) == len(set(ids)) and all(ids), f"Duplicate/empty {label} ID")
    return dict(zip(ids, rows))


def check(root=ROOT):
    root = root.resolve()
    directory = root / AUDIT
    lock = read_json(directory / "audit.lock.json")
    require(lock["schema"] == "biocompiler.human_benchmark_audit_lock.v1", "Lock schema")
    paths = []
    for record in lock["files"]:
        name = record["path"]
        path = PurePosixPath(name)
        require(not path.is_absolute() and ".." not in path.parts, "Unsafe lock path")
        target = root / name
        require(target.resolve().is_relative_to(root), "Lock path escapes repository")
        content = target.read_bytes()
        require(len(content) == record["bytes"], f"Size changed: {name}")
        require(hashlib.sha256(content).hexdigest() == record["sha256"], f"Hash changed: {name}")
        paths.append(name)
    require(len(paths) == len(set(paths)), "Duplicate locked path")
    actual = {str(p.relative_to(root)) for p in directory.rglob("*")
              if p.is_file() and p != directory / "audit.lock.json"}
    required = actual | {"docs/m11-human-benchmark-audit.md", "tools/check_human_benchmark_audit.py"}
    require(set(paths) == required, "Audit lock inventory mismatch")

    audit = read_json(directory / "audit.json")
    inventory = read_json(directory / "source-inventory.json")
    require(audit["schema"] == "biocompiler.human_benchmark_audit.v1", "Audit schema")
    require(inventory["schema"] == "biocompiler.human_benchmark_sources.v1", "Source schema")
    sources = indexed(inventory["sources"], "source")
    candidates = indexed(audit["candidates"], "candidate")
    gaps = indexed(audit["gaps"], "gap")
    for source in sources.values():
        require(source["url"].startswith("https://"), "Expected public HTTPS source")
        for field in ("version", "locators", "access", "reuse", "checked_on"):
            require(bool(source[field]), f"Missing source field: {field}")
    for candidate in candidates.values():
        require(set(candidate["assessment"]) == DIMENSIONS, "Incomplete candidate comparison")
        require(all(candidate["assessment"].values()), "Empty candidate assessment")
        require(candidate["source_ids"] and set(candidate["source_ids"]) <= sources.keys(), "Unknown source")
        require(candidate["blocking_gap_ids"] and set(candidate["blocking_gap_ids"]) <= gaps.keys(), "Unknown gap")
        require(candidate["evidence_contexts"], "Missing biological context")
        require(candidate["complete_therapeutic_benchmark"] is False, "Audit cannot promote a benchmark")
        require(candidate["compiler_admission"] is False, "Audit cannot grant compiler admission")
        require(candidate["independent_predictive_validation"] == "not_established", "Unexpected validation claim")
    decision = audit["decision"]
    require(decision["status"] == "defer_complete_therapeutic_benchmark", "Unexpected v1 decision")
    require(decision["selected_therapeutic_candidate"] is None, "Therapeutic selection remains open")
    require(set(decision["prioritized_behavior_leads"]) <= candidates.keys(), "Unknown prioritized candidate")
    require(decision["supporting_reporter_candidate"] in candidates, "Unknown reporter candidate")
    for field in ("reference_promoted", "compiler_admission", "human_compilation_enabled"):
        require(decision[field] is False, f"Audit cannot change {field}")
    require(decision["m11_2_through_6"] == "open", "Later M11 gates remain open")
    require(audit["evaluation"]["independent_evaluation_established"] is False, "No independent evaluation established")
    for receipt in inventory["external_source_receipts"]:
        require(receipt["source_id"] in sources, "Unknown external receipt source")
        require(receipt["retention"] == "external_review_cache_not_redistributed", "External source retention mislabeled")

    review = read_json(directory / "review.json")
    require(review["status"] == "reviewed_with_explicit_scientific_gaps", "Independent audit review pending")
    required_review = {str(AUDIT / "audit.json"), str(AUDIT / "source-inventory.json"),
                       "docs/m11-human-benchmark-audit.md", "tools/check_human_benchmark_audit.py"}
    require({r["path"] for r in review["reviewed_files"]} == required_review, "Review scope mismatch")
    for record in review["reviewed_files"]:
        digest = hashlib.sha256((root / record["path"]).read_bytes()).hexdigest()
        require(digest == record["sha256"], f"Reviewed file changed: {record['path']}")
    retained = directory / "retained"
    historical = (retained / "historical-equalizer-lock.json").read_bytes()
    recheck = read_json(retained / "equalizer-recheck.json")
    require(hashlib.sha256(historical).hexdigest() == recheck["benchmark_lock_sha256"], "Historical receipt mismatch")
    require(recheck["status"] == "PASS_STATIC_EVIDENCE_AUDIT", "Unexpected historical recheck result")
    print(json.dumps({"status": "PASS_AUDIT_INTEGRITY_ONLY", "candidates": len(candidates),
                      "sources": len(sources), "gaps": len(gaps), "compiler_admission": False,
                      "external_bundle_reconstructed": False, "model_execution": False}))


if __name__ == "__main__":
    try:
        check()
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"Audit check failed: {exc}", file=sys.stderr)
        sys.exit(1)
