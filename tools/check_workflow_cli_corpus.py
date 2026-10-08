"""Strict excluded-source lineage for the immutable seventy-child CLI baseline.

The frozen capture tool and all observations stay unchanged. This bridge checks
current reviewed source inventories independently, retains their actual metadata,
and projects only source identities covered by exact route witnesses. Full
actual import audits, retained source bytes and metadata remain in the receipt;
An independently pinned argparse runtime counterpart retains its complete actual
bytes. All other observations, environments and sources stay exact.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import workflow_source_lineage as routes
from tools import synthetic_producer_source_lineage as producers
from tools import manager_registration_source_lineage as managers
from tools import cli_runtime_counterparts as runtime
from tools import package_metadata_source_lineage as packaging
from tools import policy_entrypoint_source_lineage as policy_entrypoint
from tools.realization_source_lineage import verify_captured_source, REFERENCE_ROUTES

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
        raw = frozen.restore(reference, blobs)
        require(path.is_file() and not path.is_symlink(), "Archived CLI source bytes changed: " + name)
        if name in routes.HISTORICAL or name in producers.HISTORICAL or name in managers.HISTORICAL or name in REFERENCE_ROUTES or name in policy_entrypoint.ROUTES:
            if name in routes.HISTORICAL:
                entry = routes.load_witness()[name]
                require(raw == entry["historical_source"].encode(), "Archived CLI source bytes changed: " + name)
            elif name in managers.HISTORICAL:
                require(raw == managers.original_source(), "Archived CLI source bytes changed: " + name)
            elif name in policy_entrypoint.ROUTES:
                require(raw == policy_entrypoint.restore(name)[0], "Archived CLI policy route bytes changed: " + name)
            elif name in REFERENCE_ROUTES:
                from tools.reference_original_counterpart import route_source_witness
                require(raw == route_source_witness(name)[0], "Archived CLI reference route bytes changed: " + name)
            else:
                entry = producers.load_witness()[name]
                require(raw == entry["historical_source"].encode(), "Archived CLI source bytes changed: " + name)
            try:
                verify_captured_source(ROOT, {"path": name, "sha256": frozen.sha(raw)})
            except ValueError as error:
                raise AssertionError("Archived CLI source bytes changed: " + name) from error
        elif name == packaging.PATH:
            require(packaging.counterpart(ROOT)[0] == raw,
                    "Archived CLI package metadata changed")
        else:
            require(path.read_bytes() == raw, "Archived CLI source bytes changed: " + name)
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
    require(set(historical) <= set(current), "Historical CLI source bytes missing")
    reviewed_routes = []
    for name, pin in historical.items():
        path = ROOT / name
        require(path.is_file() and not path.is_symlink() and frozen.sha(path.read_bytes()) == current[name],
                "Historical CLI filesystem bytes changed: " + name)
        if current[name] != pin:
            require(name in routes.HISTORICAL or name in producers.HISTORICAL or name in managers.HISTORICAL or name in REFERENCE_ROUTES or name in policy_entrypoint.ROUTES, "Unreviewed historical CLI source change")
            try:
                reviewed_routes.append(verify_captured_source(ROOT, {"path": name, "sha256": pin}))
            except ValueError as error:
                raise AssertionError("Historical CLI source bytes changed: " + name) from error
    require(actual_scope.get("reviewed_routes", []) == reviewed_routes, "CLI reviewed route inventory differs")
    additions = _inventory(actual_scope["reviewed_additions"])
    require(actual_scope.get("reviewed_addition_counterparts") == source.addition_counterparts(additions),
            "CLI reviewed addition counterpart differs")
    require(set(current) - set(historical) == set(additions) and all(current[name] == pin for name, pin in additions.items()),
            "Current CLI excluded source inventory differs")
    require(set(FROZEN_ADDITIONS) <= set(additions) and actual_scope["denied_modules"] ==
            [source.addition_module(name) for name in sorted(additions) if name != policy_entrypoint.ENTRYPOINT], "Current CLI excluded imports are incomplete")
    from tools import workflow_cli_policy_capture as dispatch
    dispatch_proof = dispatch.verify_sources()
    entrypoint = policy_entrypoint.verify_entrypoint()
    shim = dispatch.ENTRYPOINT.encode()
    expected_environment = deepcopy(baseline["capture_environment"])
    expected_environment.update(
        declared_console_entrypoint="biocompiler.entrypoint:main",
        entrypoint_source={"kind": "blob", "bytes": len(shim), "sha256": frozen.sha(shim)})
    require(actual["capture_environment"] == expected_environment,
            "Actual CLI dispatch environment differs from its exact counterpart")
    require(len(actual["cases"]) == len(baseline["cases"]), "Actual CLI child census differs")
    projected = deepcopy(actual)
    for row, projected_row, old in zip(actual["cases"], projected["cases"], baseline["cases"]):
        audit = row["import_audit"]
        require(audit["guard_active"] is True and audit["denied_absent"] is True and
                "biocompiler.cli" in audit["modules"] and
                not (set(actual_scope["denied_modules"]) & set(audit["modules"])), "Actual CLI child imported excluded source")
        require(row["id"] == old["id"] and set(audit["modules"]) ==
                set(old["import_audit"]["modules"]) | {"biocompiler.entrypoint"},
                "Actual CLI child import census differs from exact dispatch counterpart")
        require(audit["modules"]["biocompiler.entrypoint"] ==
                {"path": policy_entrypoint.ENTRYPOINT, "sha256": entrypoint["sha256"]},
                "Actual CLI child dispatch source differs")
        for module, item in audit["modules"].items():
            require(module == "biocompiler" or module.startswith("biocompiler."), "Unrecognized CLI import audit module")
            if module == "biocompiler.entrypoint":
                del projected_row["import_audit"]["modules"][module]
                continue
            require(item["path"] in historical and item["sha256"] == current[item["path"]],
                    "Actual CLI child import source is not historical or exactly witnessed")
            if item["path"] in routes.HISTORICAL or item["path"] in producers.HISTORICAL or item["path"] in managers.HISTORICAL or item["path"] in REFERENCE_ROUTES or item["path"] in policy_entrypoint.ROUTES:
                projected_row["import_audit"]["modules"][module]["sha256"] = historical[item["path"]]
    require(set(actual["retained_source_bytes"]) == set(baseline["retained_source_bytes"]),
            "Actual retained CLI source inventory differs")
    retained_actual = {}
    packaging_counterpart = None
    for name, reference in actual["retained_source_bytes"].items():
        raw = (ROOT / name).read_bytes()
        require(reference == {"kind": "blob", "bytes": len(raw), "sha256": frozen.sha(raw)},
                "Actual retained CLI source byte identity differs: " + name)
        if name in routes.HISTORICAL or name in managers.HISTORICAL or name in REFERENCE_ROUTES or name in policy_entrypoint.ROUTES:
            retained_actual[name] = raw.decode("utf-8")
            projected["retained_source_bytes"][name] = deepcopy(baseline["retained_source_bytes"][name])
        elif name == packaging.PATH:
            _, packaging_counterpart = packaging.counterpart(ROOT, current=raw)
            projected["retained_source_bytes"][name] = deepcopy(baseline["retained_source_bytes"][name])
    projected["capture_environment"] = deepcopy(baseline["capture_environment"])
    projected["source_scope"] = deepcopy(baseline["source_scope"])
    projected["inventory_fingerprint"] = digest({key: value for key, value in projected.items() if key != "inventory_fingerprint"})
    evidence = {
        "schema_version": "biocompiler.workflow_cli_source_lineage.v4",
        "status": "source_lineage_verified", "native_execution": False,
        "baseline_inventory_fingerprint": CORPUS_PIN, "baseline_source_scope_fingerprint": SCOPE_PIN,
        "actual_inventory_fingerprint": actual["inventory_fingerprint"],
        "projected_inventory_fingerprint": projected["inventory_fingerprint"],
        "actual_source_scope": deepcopy(actual_scope),
        "actual_capture": deepcopy(actual),
        "actual_retained_route_sources": retained_actual,
        "packaging_metadata_counterpart": packaging_counterpart,
        "policy_dispatch_counterpart": dispatch_proof,
        "reviewed_routes": reviewed_routes,
        "source_changes": [{"path": name, "previous_sha256": before.get(name),
                            "current_sha256": current.get(name)}
                           for name in sorted(set(before) | set(current)) if before.get(name) != current.get(name)],
        "projection": "exact_witnessed_source_scope_import_hashes_retained_source_references_composed_package_metadata_and_policy_dispatch_only_then_recompute_inventory_fingerprint",
    }
    return projected, evidence


def historical_projection(actual):
    baseline, _ = load_baseline()
    return _project(actual, baseline)


def verify_recapture(actual, blobs, *, python_version=None):
    baseline, old_blobs = load_baseline()
    projected, evidence = _project(actual, baseline)
    projected_blobs = dict(blobs)
    from tools import workflow_cli_policy_capture as dispatch
    current_shim = actual["capture_environment"]["entrypoint_source"]
    old_shim = baseline["capture_environment"]["entrypoint_source"]
    require(frozen.restore(current_shim, blobs) == dispatch.ENTRYPOINT.encode(),
            "Actual CLI dispatch shim content differs")
    del projected_blobs[current_shim["sha256"]]
    projected_blobs[old_shim["sha256"]] = old_blobs[old_shim["sha256"]]
    retained_routes = set(routes.HISTORICAL) | ((set(managers.HISTORICAL) | REFERENCE_ROUTES | policy_entrypoint.ROUTES | {packaging.PATH}) & set(actual["retained_source_bytes"]))
    for name in sorted(retained_routes):
        current_ref = actual["retained_source_bytes"][name]
        old_ref = baseline["retained_source_bytes"][name]
        raw = (ROOT / name).read_bytes()
        require(frozen.restore(current_ref, blobs) == raw, "Actual retained route source content differs")
        if current_ref["sha256"] != old_ref["sha256"]:
            # A route source is projected only as the retained source member.
            # If another observation references the same content, its unchanged
            # reference is caught by the complete document comparison below.
            del projected_blobs[current_ref["sha256"]]
            projected_blobs[old_ref["sha256"]] = old_blobs[old_ref["sha256"]]
    # The only observation projection is an independently executed, immutable
    # Python-runtime counterpart. Retain every actual byte in the receipt and
    # never infer the runtime from whichever formatting happens to be supplied.
    counterparts = runtime.workflow()
    minor = runtime.runtime_minor(python_version)
    counterpart_evidence = []
    for old in baseline["cases"]:
        if old["id"] not in counterparts.cases:
            continue
        rows = [row for row in projected["cases"] if row["id"] == old["id"]]
        require(len(rows) == 1, "Exact CLI counterpart occurrence inventory differs")
        row = rows[0]
        expected = counterparts.expected(old, {"exit_code": old["exit_code"],
            **{field: frozen.restore(old[field], old_blobs) for field in ("stdout", "stderr")}}, minor)
        require(type(row["exit_code"]) is int and row["exit_code"] == expected["exit_code"],
                "Exact CLI runtime counterpart exit differs")
        for field in ("stdout", "stderr"):
            raw = frozen.restore(row[field], blobs)
            require(raw == expected[field], "Exact CLI runtime counterpart " + field + " differs")
            if row[field] != old[field]:
                require(row[field] == {"kind": "blob", "bytes": len(raw), "sha256": frozen.sha(raw)},
                        "Exact CLI runtime counterpart reference differs")
                counterpart_evidence.append({"id": old["id"], "field": field,
                    "actual": deepcopy(row[field]), "baseline": deepcopy(old[field])})
                del projected_blobs[row[field]["sha256"]]
                projected_blobs[old[field]["sha256"]] = old_blobs[old[field]["sha256"]]
                row[field] = deepcopy(old[field])
    projected["inventory_fingerprint"] = digest({key: value for key, value in projected.items()
                                                  if key != "inventory_fingerprint"})
    evidence.update(projected_inventory_fingerprint=projected["inventory_fingerprint"],
        projection="exact_witnessed_source_metadata_composed_package_and_policy_dispatch_and_explicit_pinned_argparse_runtime_counterpart_only_then_recompute_inventory_fingerprint",
        runtime_counterpart={"declaration_sha256": counterparts.pin, "python_minor": minor,
                             "validated_cases": sorted(counterparts.cases), "changes": counterpart_evidence})
    require(projected_blobs == old_blobs, "Complete actual CLI content differs from immutable baseline")
    require(canonical(projected) == canonical(baseline), "Complete actual CLI observations differ from immutable baseline")
    evidence.update(status="complete_original_cli_recapture_equal", coverage=deepcopy(actual["coverage"]),
                    content_documents=len(blobs), content_bytes=sum(map(len, blobs.values())),
                    actual_content_inventory=[{"sha256": name, "bytes": len(body)}
                                              for name, body in sorted(blobs.items())])
    return evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    from tools.workflow_cli_policy_capture import capture
    actual, blobs = capture()
    receipt = verify_recapture(actual, blobs)
    receipt["runtime"] = {"python": sys.version, "platform": sys.platform, "executable": sys.executable,
                          "revision": os.environ.get("GITHUB_SHA")}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Keep every current blob and full actual metadata, independently loadable
    # by the immutable loader. The historical projection never overwrites it.
    actual_path = args.output.with_name(args.output.stem + "-actual.json")
    frozen.write(actual, blobs, actual_path)
    receipt["actual_capture_path"] = actual_path.name
    args.output.write_bytes(canonical(receipt) + b"\n")
    print(json.dumps({"status": receipt["status"], "actual_inventory_fingerprint": receipt["actual_inventory_fingerprint"],
                      "baseline_inventory_fingerprint": CORPUS_PIN, "coverage": receipt["coverage"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
