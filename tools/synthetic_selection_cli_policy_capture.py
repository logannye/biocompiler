"""Run the unchanged 72 selection cases through the pinned policy dispatcher.

Original freezer bytes and observations remain immutable. This orchestration
changes only the declared console shim and its truthful source/import metadata.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from tools import freeze_synthetic_selection_cli as frozen
from tools import workflow_cli_policy_capture as dispatch

ROOT = Path(__file__).resolve().parents[1]
FREEZER = "tools/freeze_synthetic_selection_cli.py"
FREEZER_SHA256 = "b181b47e592781a91966e90779f2c667b80f070cbc03cd0390406598b9870520"
POLICY_DENIED_MODULES = ("biocompiler.core_policy", "biocompiler.policy", "examples.expressive_policies")
RETAINED_SOURCES = (
    "src/biocompiler/cli.py", "src/biocompiler/synthesis/selection.py", "src/biocompiler/artifacts/synthetic_build.py",
    "tests/test_synthetic_design_workflows.py", FREEZER, "tools/freeze_workflow_cli.py", "pyproject.toml",
)


def verify_sources():
    path = ROOT / FREEZER
    frozen.require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 128 * 1024
                   and frozen.sha(path.read_bytes()) == FREEZER_SHA256,
                   "Original selection CLI freezer bytes changed")
    return {"selection_freezer_sha256": FREEZER_SHA256, "dispatch": dispatch.verify_sources(ROOT)}


def source_scope():
    scope = frozen.source_scope()
    return {**scope, "schema_version": "biocompiler.synthetic_selection_cli_source_scope.v2",
            "denied_modules": sorted(set(scope["denied_modules"]) | set(POLICY_DENIED_MODULES))}


def capture():
    authority = verify_sources()
    scope = source_scope()
    store, rows = frozen.f.Store(), []
    with frozen.capture_environment():
        (frozen.CLI_ROOT / "biocompiler").write_text(dispatch.ENTRYPOINT)
        cases = [frozen.original_case(), *frozen.supplemental_cases()]
        frozen.require(len(cases) == 72 and len({case["id"] for case in cases}) == 72
                       and Counter(case["entrypoint"] for case in cases) == {"console": 68, "module": 4}
                       and sum(case["origin"] == "original_occurrence" for case in cases) == 1,
                       "Original complete selection CLI case census changed")
        for case in cases:
            rows.append(frozen.f.run_case(case, scope, store))
    frozen.require(source_scope() == scope, "Product source changed during actual selection CLI capture")
    frozen.require(verify_sources() == authority, "Reviewed dispatch source changed during actual selection CLI capture")
    sources = {name: store.retain((ROOT / name).read_bytes()) for name in RETAINED_SOURCES}
    document = {"schema_version": frozen.SCHEMA, "source_scope": scope, "retained_source_bytes": sources,
        "native_reference_fixture_sha256": frozen.NATIVE_FIXTURE_SHA256,
        "capture_environment": {"entrypoint_source": store.retain(dispatch.ENTRYPOINT.encode()),
            "declared_console_entrypoint": "biocompiler.entrypoint:main", "startup": store.retain(frozen.STARTUP.encode()),
            "exclusive_namespaces": [str(frozen.ORIGINAL_ROOT), str(frozen.CLI_ROOT)], "cwd": str(frozen.CLI_ROOT / "cwd"),
            "hash_seed": "0", "io_encoding": "utf-8", "scope": "original_Python_selection_CLI_no_native_execution",
            "path_policy": "exact_preselected_paths_no_observation_normalization"},
        "coverage": {"actual_children": len(rows), "original_occurrences": 1,
            "entrypoints": dict(sorted(Counter(row["entrypoint"] for row in rows).items())),
            "exits": dict(sorted(Counter(str(row["exit_code"]) for row in rows).items()))}, "cases": rows}
    document["inventory_fingerprint"] = frozen.digest(document)
    return document, store.blobs
