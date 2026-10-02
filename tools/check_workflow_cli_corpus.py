"""Strict excluded-source lineage for the immutable seventy-child CLI baseline.

The frozen capture tool and all observations stay unchanged. This bridge checks
current reviewed source inventories independently, retains their actual metadata,
and projects only source_scope for an exact comparison with the archived CLI
baseline. Historical sources and retained source bytes cannot be normalized.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys

if __package__:
    from . import freeze_workflow_cli as frozen
    from . import check_realization_workflow_corpus as source
else:
    import freeze_workflow_cli as frozen
    import check_realization_workflow_corpus as source

ROOT = Path(__file__).resolve().parents[1]
CORPUS_PIN = "a67edb95f75aa011ed5c059fe8cbe578fbe118d056931e3992f73775e8951da7"
SCOPE_PIN = "393e6ebdb7b622086a3025e495714223640dca5a7ae524c0f31f467c4c64f660"
FROZEN_ADDITIONS = {
    "src/biocompiler/core_artifacts.py": "9cf24948c12d617dc783317b4f16330e1be69feba64cfec70767288556011e4e",
    "src/biocompiler/core_workflow.py": "43b57b87a2d89db200463d8aed8b7eea7e262cf1c4ea02c772843598dbda90df",
}
canonical, digest, require = frozen.canonical, frozen.digest, frozen.require


def _inventory(rows):
    require(type(rows) is list and all(type(row) is dict and set(row) == {"path", "sha256"} for row in rows),
            "Invalid complete CLI source inventory")
    result = {}
    for row in rows:
        path, pin = row["path"], row["sha256"]
        require(type(path) is str and not Path(path).is_absolute() and ".." not in Path(path).parts and
                type(pin) is str and len(pin) == 64 and all(char in "0123456789abcdef" for char in pin) and
                path not in result, "Duplicate or unsafe CLI source identity")
        result[path] = pin
    return result


def load_baseline():
    document, blobs = frozen.load()
    require(document["inventory_fingerprint"] == CORPUS_PIN and len(blobs) == 114 and
            document["coverage"]["actual_children"] == 70 and len(document["cases"]) == 70,
            "Immutable complete CLI baseline changed")
    scope = document["source_scope"]
    require(digest(scope) == SCOPE_PIN, "Archived CLI source scope changed")
    historical = source.historical_sources()
    original = _inventory(historical)
    require(len(original) == 240 and not (set(original) & set(FROZEN_ADDITIONS)),
            "Original CLI historical source census changed")
    # The old excluded module identities are independently pinned here and in the
    # archived CLI inventory. They are not inferred from today's reviewed hashes.
    expected_actual = [{"path": path, "sha256": pin} for path, pin in sorted({**original, **FROZEN_ADDITIONS}.items())]
    expected_scope = {
        "schema_version": "biocompiler.realization_workflow_source_scope.v1",
        "historical_corpus_pin": source.CORPUS_PIN,
        "historical_sources": historical,
        "actual_sources": expected_actual,
        "historical_source_inventory_sha256": digest(historical),
        "actual_source_inventory_sha256": digest(expected_actual),
        "reviewed_additions": [{"path": path, "sha256": pin} for path, pin in sorted(FROZEN_ADDITIONS.items())],
        "denied_modules": [path[4:-3].replace("/", ".") for path in sorted(FROZEN_ADDITIONS)],
        "omitted_tests_for_focused_instrumentation": [],
        "comparison": "exact_original_observations_and_documents_after_explicit_historical_source_projection_only",
    }
    require(canonical(scope) == canonical(expected_scope), "Archived CLI scope is not the independently pinned original inventory")
    for name, reference in document["retained_source_bytes"].items():
        _inventory([{"path": name, "sha256": reference["sha256"]}])
        path = ROOT / name
        require(path.is_file() and not path.is_symlink() and
                path.read_bytes() == frozen.restore(reference, blobs), "Archived CLI source bytes changed: " + name)
    return document, blobs


def current_scope():
    # actual_sources recomputes every historical path plus the complete current
    # src/biocompiler and examples inventories. source_scope checks each byte
    # identity against the historical inventory or explicit reviewed additions.
    return frozen.actual_sources(frozen.Corpus())


def _project(actual, baseline):
    require(type(actual) is dict and set(actual) == set(baseline), "Incomplete actual CLI capture metadata")
    require(actual["inventory_fingerprint"] == digest({key: value for key, value in actual.items()
            if key != "inventory_fingerprint"}), "Actual CLI capture identity changed")
    actual_scope = actual["source_scope"]
    expected_scope = current_scope()
    require(canonical(actual_scope) == canonical(expected_scope), "Actual CLI source scope does not match current reviewed bytes")
    require(not actual_scope["omitted_tests_for_focused_instrumentation"], "Focused CLI source capture cannot become full evidence")
    require(canonical(actual_scope["historical_sources"]) == canonical(baseline["source_scope"]["historical_sources"]) and
            actual_scope["historical_corpus_pin"] == source.CORPUS_PIN and
            actual_scope["historical_source_inventory_sha256"] == digest(actual_scope["historical_sources"]),
            "Immutable historical CLI source inventory changed")
    historical = _inventory(baseline["source_scope"]["historical_sources"])
    current = _inventory(actual_scope["actual_sources"])
    before = _inventory(baseline["source_scope"]["actual_sources"])
    require(set(historical) <= set(current) and all(current[path] == pin for path, pin in historical.items()),
            "Historical CLI source bytes changed")
    for name, pin in historical.items():
        path = ROOT / name
        require(path.is_file() and not path.is_symlink() and frozen.sha(path.read_bytes()) == pin,
                "Historical CLI filesystem bytes changed: " + name)
    additions = _inventory(actual_scope["reviewed_additions"])
    require(set(current) - set(historical) == set(additions) and all(current[name] == pin for name, pin in additions.items()),
            "Current CLI excluded source inventory differs")
    require(set(FROZEN_ADDITIONS) <= set(additions) and actual_scope["denied_modules"] ==
            [name[4:-3].replace("/", ".") for name in sorted(additions)], "Current CLI excluded imports are incomplete")
    for row in actual["cases"]:
        audit = row["import_audit"]
        require(audit["guard_active"] is True and audit["denied_absent"] is True and
                "biocompiler.cli" in audit["modules"] and
                not (set(actual_scope["denied_modules"]) & set(audit["modules"])), "Actual CLI child imported excluded source")
        for module, item in audit["modules"].items():
            require(module == "biocompiler" or module.startswith("biocompiler."), "Unrecognized CLI import audit module")
            require(item["path"] in historical and item["sha256"] == historical[item["path"]],
                    "Actual CLI child import source is not historical")
    projected = deepcopy(actual)
    projected["source_scope"] = deepcopy(baseline["source_scope"])
    projected["inventory_fingerprint"] = digest({key: value for key, value in projected.items() if key != "inventory_fingerprint"})
    evidence = {
        "schema_version": "biocompiler.workflow_cli_source_lineage.v1",
        "status": "source_lineage_verified", "native_execution": False,
        "baseline_inventory_fingerprint": CORPUS_PIN, "baseline_source_scope_fingerprint": SCOPE_PIN,
        "actual_inventory_fingerprint": actual["inventory_fingerprint"],
        "projected_inventory_fingerprint": projected["inventory_fingerprint"],
        "actual_source_scope": deepcopy(actual_scope),
        "source_changes": [{"path": name, "historical_excluded_sha256": before.get(name),
                            "current_excluded_sha256": current.get(name)}
                           for name in sorted(set(before) | set(current)) if before.get(name) != current.get(name)],
        "projection": "source_scope_only_then_recompute_inventory_fingerprint",
    }
    return projected, evidence


def historical_projection(actual):
    baseline, _ = load_baseline()
    return _project(actual, baseline)


def verify_recapture(actual, blobs):
    baseline, old_blobs = load_baseline()
    projected, evidence = _project(actual, baseline)
    require(blobs == old_blobs, "Complete actual CLI content differs from immutable baseline")
    require(canonical(projected) == canonical(baseline), "Complete actual CLI observations differ from immutable baseline")
    evidence.update(status="complete_original_cli_recapture_equal", coverage=deepcopy(actual["coverage"]),
                    content_documents=len(blobs), content_bytes=sum(map(len, blobs.values())))
    return evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    actual, blobs = frozen.capture()
    receipt = verify_recapture(actual, blobs)
    receipt["runtime"] = {"python": sys.version, "platform": sys.platform, "executable": sys.executable,
                          "revision": os.environ.get("GITHUB_SHA")}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(receipt) + b"\n")
    print(json.dumps({"status": receipt["status"], "actual_inventory_fingerprint": receipt["actual_inventory_fingerprint"],
                      "baseline_inventory_fingerprint": CORPUS_PIN, "coverage": receipt["coverage"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
