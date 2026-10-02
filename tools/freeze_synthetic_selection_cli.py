"""Retain complete original synthetic-select CLI children before native routing.

The original test method runs unchanged. Additional cases execute the original
command with full source authority, including every public-import diagnostic
fixture and publication boundary. All paths are selected before execution; no
stdout, stderr, filesystem content, or exit status is normalized.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import re
import sys
import tomllib
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import freeze_workflow_cli as f

CORPUS = ROOT / "tests/conformance/synthetic-selection-cli-v1.json"
SCHEMA = "biocompiler.synthetic_selection_cli_capture.v1"
ORIGINAL_ROOT = Path("/tmp/biocompiler-synthetic-selection-original-v1")
CLI_ROOT = Path("/tmp/biocompiler-synthetic-selection-cli-v1")
ORIGINAL_METHOD = "test_component_package_and_selection_cli_report_actual_scope"
NATIVE_FIXTURES = "core/test/test_synthetic_producer_public_protocol.ml"
NATIVE_FIXTURE_SHA256 = "56d63cd634c8172f60e1698ca5ea028ad93a016c0da2682b8912262832347bcb"
STARTUP = f.STARTUP.replace("cli.SyntheticVerificationRecord.to_json", "cli.SyntheticSelectionResult.to_json")
canonical, digest, sha, require = f.canonical, f.digest, f.sha, f.require


@contextmanager
def capture_environment():
    with patch.object(f, "ORIGINAL_ROOT", ORIGINAL_ROOT), patch.object(f, "CLI_ROOT", CLI_ROOT):
        with f.owned_directories():
            (CLI_ROOT / "startup").mkdir(); (CLI_ROOT / "cwd").mkdir()
            (CLI_ROOT / "startup/sitecustomize.py").write_text(STARTUP)
            (CLI_ROOT / "biocompiler").write_text(f.ENTRYPOINT)
            yield


def source_scope():
    paths = {path.relative_to(ROOT).as_posix() for folder in ("src/biocompiler", "examples")
             for path in (ROOT / folder).rglob("*.py")}
    paths.update({"tests/test_synthetic_design_workflows.py", "tools/freeze_synthetic_selection_cli.py",
                  "tools/freeze_workflow_cli.py", NATIVE_FIXTURES, "pyproject.toml"})
    excluded = {"src/biocompiler/" + name + ".py" for name in (
        "core_artifacts", "core_workflow", "core_workflow_authority", "workflow_backend", "workflow_cli",
        "core_synthetic_producer", "synthetic_producer_backend", "core_synthetic_producer_public", "synthetic_producer_cli")}
    require(excluded <= paths, "Missing excluded migration transport source")
    rows = [{"path": name, "sha256": sha((ROOT / name).read_bytes())} for name in sorted(paths)]
    return {"schema_version": "biocompiler.synthetic_selection_cli_source_scope.v1",
            "actual_sources": rows, "source_inventory_sha256": digest(rows),
            "denied_modules": [name[4:-3].replace("/", ".") for name in sorted(excluded)]}


def reference_fixtures():
    raw = (ROOT / NATIVE_FIXTURES).read_bytes()
    require(sha(raw) == NATIVE_FIXTURE_SHA256, "Pinned complete public authority fixtures changed")
    text = raw.decode()
    positive, rejected = text.split("let rejected_literals = [", 1)
    pattern = r"Json.parse \{literal\|(.*?)\|literal\}"
    positives = [json.loads(value) for value in re.findall(pattern, positive)]
    errors = [json.loads(value) for value in re.findall(pattern, rejected)]
    require(len(positives) == 4 and len(errors) == 42, "Complete original authority fixture census differs")
    return positives, errors


def original_case():
    # Run the complete original unit method and its assertions. Intercept only
    # the public CLI boundary to retain its complete pre/post observations.
    from tests import test_synthetic_design_workflows as original
    actual_main = original.main
    calls = []
    @contextmanager
    def fixed_directory(*args, **kwargs):
        require(not args and not kwargs, "Unexpected original temporary-directory options")
        path = ORIGINAL_ROOT / "original"
        path.mkdir()
        try: yield str(path)
        finally: pass  # Child preparation replaces this exclusively owned pre-state.
    def observe(arguments):
        if arguments[0] != "synthetic-select":
            return actual_main(arguments)
        argv = [str(value) for value in arguments]
        before = {str(path): path.read_bytes() for path in ORIGINAL_ROOT.rglob("*") if path.is_file()}
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err): code = actual_main(argv)
        sys.stdout.write(out.getvalue()); sys.stderr.write(err.getvalue())
        after = {}
        for item in argv[1:]:
            path = Path(item)
            if path.is_file():
                raw = path.read_bytes()
                after[item] = {"bytes": len(raw), "sha256": sha(raw), "text": raw.decode()}
        calls.append({"id": ORIGINAL_METHOD, "origin": "original_occurrence", "argv": argv,
            "entrypoint": "console", "files": before, "directories": [], "symlinks": {}, "fault": None,
            "lineage": {"module": original.__name__, "class": "SyntheticDesignWorkflowTests",
                "method": ORIGINAL_METHOD, "source_sha256": sha(Path(original.__file__).read_bytes())},
            "original_expected": {"exit_code": code, "stdout": out.getvalue().encode(),
                                  "stderr": err.getvalue().encode(), "files_after": after}})
        return code
    test = original.SyntheticDesignWorkflowTests(ORIGINAL_METHOD)
    result = unittest.TestResult()
    with patch.object(original.tempfile, "TemporaryDirectory", fixed_directory), patch.object(original, "main", observe):
        unittest.TestSuite([test]).run(result)
    require(result.wasSuccessful() and result.testsRun == 1 and len(calls) == 1,
            "Original complete selection CLI test failed: " + repr(result.errors + result.failures))
    return calls[0]


def supplemental_cases():
    result = []
    positives, errors = reference_fixtures()
    def add(name, raw=None, *, argv=None, files=None, directories=(), symlinks=None, fault=None,
            lineage=None, entrypoint="console"):
        folder = CLI_ROOT / "cases" / name
        paths = {"REQUEST": str(folder / "request.json"), "OUTPUT": str(folder / "output.json"), "ROOT": str(folder)}
        def expand(value):
            for key, path in paths.items(): value = value.replace("{" + key + "}", path)
            return value
        inputs = {expand(name): value for name, value in (files or {}).items()}
        if raw is not None: inputs[paths["REQUEST"]] = raw
        argv = argv or ["synthetic-select", "--request", "{REQUEST}", "--output", "{OUTPUT}"]
        result.append({"id": name, "origin": "reference_authority" if lineage else "independent_boundary",
            "argv": [expand(value) for value in argv], "entrypoint": entrypoint, "files": inputs,
            "directories": [expand(value) for value in directories],
            "symlinks": {expand(key): expand(value) for key, value in (symlinks or {}).items()},
            "fault": fault, "lineage": lineage, "original_expected": None})
    for row in positives:
        authority = row["payload"]["build_request"]
        for entry in ("console", "module"):
            add(row["name"] + "-" + entry, canonical(authority), entrypoint=entry,
                lineage={"native_fixture": row["name"], "authority_sha256": digest(authority), "fixture_sha256": NATIVE_FIXTURE_SHA256})
    prior = {"{OUTPUT}": b"prior selection report"}
    for row in errors:
        add("malformed-" + row["name"], canonical(row["build_request"]), files=prior,
            lineage={"native_fixture": row["name"], "original_error_message": row["message"],
                     "authority_sha256": digest(row["build_request"]), "fixture_sha256": NATIVE_FIXTURE_SHA256})
    authority = canonical(positives[0]["payload"]["build_request"])
    command = ["synthetic-select", "--request", "{REQUEST}"]
    add("default-no-output", authority, argv=command)
    def reverse(value):
        if isinstance(value, dict): return {key: reverse(item) for key, item in reversed(list(value.items()))}
        if isinstance(value, list): return [reverse(item) for item in value]
        return value
    add("noncanonical-authority", json.dumps(reverse(json.loads(authority)), indent=3, ensure_ascii=False).encode() + b"\n")
    for name, raw in (("invalid-json", b'{"unfinished":'), ("invalid-utf8", b'\xff'),
                      ("input-at-limit", b" " * f.MAX_INPUT), ("input-one-over", b" " * (f.MAX_INPUT + 1))):
        add(name, raw, files=prior)
    add("missing-input", files=prior)
    add("missing-output-parent", authority, argv=command + ["--output", "{ROOT}/missing/output.json"])
    add("directory-output", authority, directories=("{OUTPUT}",))
    add("symlink-output", authority, files={"{ROOT}/target.json": b"prior selection report"},
        symlinks={"{OUTPUT}": "{ROOT}/target.json"})
    add("input-output-alias", authority, argv=command + ["--output", "{REQUEST}"])
    add("resolved-input-output-alias", authority, argv=command + ["--output", "{ROOT}/nested/../request.json"],
        directories=("{ROOT}/nested",))
    add("symlink-input-output-alias", authority,
        argv=["synthetic-select", "--request", "{ROOT}/alias.json", "--output", "{REQUEST}"],
        symlinks={"{ROOT}/alias.json": "{REQUEST}"})
    for name, fault in (("publication-replace", {"kind": "replace", "message": "disk unavailable"}),
                        ("publication-fsync", {"kind": "fsync", "message": "capture fsync unavailable"}),
                        ("publication-short-write", {"kind": "short_write"}),
                        ("publication-size-at-limit", {"kind": "serialized_length", "bytes": f.MAX_OUTPUT - 1}),
                        ("publication-size-one-over", {"kind": "serialized_length", "bytes": f.MAX_OUTPUT})):
        add(name, authority, files=prior, fault=fault)
    add("missing-required-request", argv=["synthetic-select"])
    add("unknown-flag", authority, argv=command + ["--unknown-synthetic-option"])
    add("help", argv=["synthetic-select", "--help"])
    require(len({row["id"] for row in result}) == len(result), "Duplicate original CLI case")
    return result


def capture():
    scope = source_scope()
    require(tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["scripts"]["biocompiler"] == "biocompiler.cli:main",
            "Public CLI entry point changed")
    store, rows = f.Store(), []
    with capture_environment():
        cases = [original_case(), *supplemental_cases()]
        for case in cases: rows.append(f.run_case(case, scope, store))
    require(source_scope() == scope, "Product sources changed during original CLI capture")
    sources = {name: store.retain((ROOT / name).read_bytes()) for name in (
        "src/biocompiler/cli.py", "src/biocompiler/synthesis/selection.py", "src/biocompiler/artifacts/synthetic_build.py",
        "tests/test_synthetic_design_workflows.py", "tools/freeze_synthetic_selection_cli.py", "tools/freeze_workflow_cli.py", "pyproject.toml")}
    document = {"schema_version": SCHEMA, "source_scope": scope, "retained_source_bytes": sources,
        "native_reference_fixture_sha256": NATIVE_FIXTURE_SHA256,
        "capture_environment": {"entrypoint_source": store.retain(f.ENTRYPOINT.encode()), "startup": store.retain(STARTUP.encode()),
            "exclusive_namespaces": [str(ORIGINAL_ROOT), str(CLI_ROOT)], "cwd": str(CLI_ROOT / "cwd"),
            "hash_seed": "0", "io_encoding": "utf-8", "scope": "original_Python_selection_CLI_no_native_execution",
            "path_policy": "exact_preselected_paths_no_observation_normalization"},
        "coverage": {"actual_children": len(rows), "original_occurrences": 1,
            "entrypoints": dict(sorted(Counter(row["entrypoint"] for row in rows).items())),
            "exits": dict(sorted(Counter(str(row["exit_code"]) for row in rows).items()))}, "cases": rows}
    document["inventory_fingerprint"] = digest(document)
    return document, store.blobs


def load(path=CORPUS): return f.load(path)
def write(document, blobs, path=CORPUS): return f.write(document, blobs, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=CORPUS)
    args = parser.parse_args()
    require(args.freeze != args.check, "Select exactly one freeze/check")
    document, blobs = capture()
    if args.freeze: write(document, blobs, args.output)
    else:
        expected, old_blobs = load(args.output)
        require(canonical(document) == canonical(expected) and blobs == old_blobs,
                "Complete original selection CLI capture changed")
    print(json.dumps({"status": "frozen" if args.freeze else "complete_recapture_equal",
        "inventory_fingerprint": document["inventory_fingerprint"], "coverage": document["coverage"],
        "content_documents": len(blobs), "content_bytes": sum(map(len, blobs.values()))}, sort_keys=True))


if __name__ == "__main__": main()
