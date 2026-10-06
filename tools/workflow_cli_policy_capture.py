"""Recapture the original CLI cases through the exactly witnessed dispatcher.

The historical freezer and corpus stay immutable. Its case definitions, child
runner, import guard, byte store and exclusive namespaces are used unchanged;
only this explicit orchestration supplies the current declared console shim.
No observation or captured source byte is projected here.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import tomllib

from tools import freeze_workflow_cli as frozen
from tools import package_metadata_source_lineage as packaging
from tools import policy_entrypoint_source_lineage as policy


ROOT = Path(__file__).resolve().parents[1]
FREEZER = "tools/freeze_workflow_cli.py"
FREEZER_SHA256 = "a811548539232ee29f8fd1c52620e51778c2bf895df62847db4474591ec89564"
DECLARED_ENTRYPOINT = "biocompiler.entrypoint:main"
ENTRYPOINT = "from biocompiler.entrypoint import main\nraise SystemExit(main())\n"
RETAINED_SOURCES = (
    "src/biocompiler/cli.py", "src/biocompiler/__main__.py", "src/biocompiler/compiler/verification_workflow.py",
    "tests/test_synthetic_design_workflows.py", "tests/test_verification_campaign.py",
    "tests/test_synthetic_verification_workflow.py", FREEZER, "pyproject.toml",
)


def verify_sources(root=ROOT):
    """Check complete original helper bytes and the composed dispatch witness."""
    root = Path(root)
    path = root / FREEZER
    frozen.require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 128 * 1024
                   and frozen.sha(path.read_bytes()) == FREEZER_SHA256,
                   "Original workflow CLI freezer bytes changed")
    witness = policy.witness(root)
    dispatcher = policy.verify_entrypoint(root)
    routes = []
    for name in sorted(policy.ROUTES):
        path = root / name
        frozen.require(path.is_file() and not path.is_symlink(), "Redirected policy dispatch route: " + name)
        _, proof = policy.restore(name, root=root)
        routes.append(proof)
    _, metadata = packaging.counterpart(root)
    declared = tomllib.loads((root / "pyproject.toml").read_text())["project"]["scripts"]["biocompiler"]
    witnessed = tomllib.loads(witness["sources"]["pyproject.toml"]["after_source"])["project"]["scripts"]["biocompiler"]
    frozen.require(declared == witnessed == DECLARED_ENTRYPOINT == "biocompiler.entrypoint:main"
                   and ENTRYPOINT == "from biocompiler.entrypoint import main\nraise SystemExit(main())\n",
                   "Current workflow CLI capture shim differs from the witnessed console declaration")
    return {"freezer_sha256": FREEZER_SHA256, "policy_witness_sha256": policy.WITNESS_SHA256,
            "dispatcher": {"path": dispatcher["path"], "sha256": dispatcher["sha256"]},
            "routes": routes, "package_metadata": metadata,
            "declared_console_entrypoint": declared, "entrypoint_sha256": frozen.sha(ENTRYPOINT.encode())}


def capture():
    authority = verify_sources()
    original = frozen.Corpus()
    scope = frozen.actual_sources(original)
    cases = frozen.cases(original)
    frozen.require(len(cases) == 70 and len({case["id"] for case in cases}) == 70
                   and Counter(case["entrypoint"] for case in cases) == {"console": 66, "module": 4},
                   "Original complete workflow CLI case census changed")
    store = frozen.Store()
    rows = []
    with frozen.owned_directories():
        (frozen.CLI_ROOT / "startup").mkdir(); (frozen.CLI_ROOT / "cwd").mkdir()
        (frozen.CLI_ROOT / "startup/sitecustomize.py").write_text(frozen.STARTUP)
        (frozen.CLI_ROOT / "biocompiler").write_text(ENTRYPOINT)
        for case in cases:
            rows.append(frozen.run_case(case, scope, store))
    frozen.require(frozen.actual_sources(original) == scope, "Product source changed during actual CLI capture")
    frozen.require(verify_sources() == authority, "Reviewed dispatch source changed during actual CLI capture")
    sources = {path: store.retain((ROOT / path).read_bytes()) for path in RETAINED_SOURCES}
    document = {"schema_version": frozen.SCHEMA, "original_corpus_pin": frozen.CORPUS_PIN,
        "supplement_pin": frozen.SUPPLEMENT_PIN, "source_scope": scope, "retained_source_bytes": sources,
        "capture_environment": {"entrypoint": ["python", str(frozen.CLI_ROOT / "biocompiler")],
            "module_entrypoint": ["python", "-m", "biocompiler"],
            "entrypoint_source": store.retain(ENTRYPOINT.encode()), "declared_console_entrypoint": DECLARED_ENTRYPOINT,
            "exclusive_namespaces": [str(frozen.ORIGINAL_ROOT), str(frozen.CLI_ROOT)], "cwd": str(frozen.CLI_ROOT / "cwd"),
            "hash_seed": "0", "io_encoding": "utf-8", "startup": store.retain(frozen.STARTUP.encode()),
            "path_policy": "exact paths chosen before execution; no postprocessing; collision fails",
            "size_recipes": "lossless repeated ASCII spaces and optional trailing newline",
            "scope": "original Python public CLI children only; native routing remains unvalidated"},
        "coverage": {"actual_children": len(rows), "original_occurrences": 16,
            "entrypoints": dict(sorted(Counter(row["entrypoint"] for row in rows).items())),
            "commands": dict(sorted(Counter(row["argv"][0] for row in rows).items())),
            "exits": dict(sorted(Counter(str(row["exit_code"]) for row in rows).items()))}, "cases": rows}
    document["inventory_fingerprint"] = frozen.digest(document)
    return document, store.blobs
