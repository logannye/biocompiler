#!/usr/bin/env python3
"""Freeze actual original workflow CLI children before optional native routing.

DRAFT CHECKPOINT: syntax and case census only. No child cohort has run and no
golden corpus has been generated or independently reproduced. Do not use this
tool as validation evidence until those checks and a focused test suite pass.

All original occurrences remain separate. Exact paths are supplied before the
child starts; stdout, stderr, exit codes and filesystem bytes are never edited.
Size-boundary bytes use lossless repetition recipes, never truncated snapshots.
This tool intentionally rejects changed original sources: a future source bridge
must be separately reviewed, rather than rewriting this baseline's lineage.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.check_native_workflow import Corpus, canonical, sha, digest, require, CORPUS_PIN, SUPPLEMENT_PIN
from tools.check_realization_workflow_corpus import source_scope

CORPUS = ROOT / "tests/conformance/workflow-cli-v1.json"
ORIGINAL_ROOT = Path("/tmp/biocompiler-workflow-conformance-v1")
CLI_ROOT = Path("/tmp/biocompiler-workflow-cli-v1")
SCHEMA = "biocompiler.workflow_cli_capture.v1"
MAX_INPUT = 16 * 1024 * 1024
MAX_OUTPUT = 64 * 1024 * 1024

# The public entry point remains `python -m biocompiler`. This startup fixture
# only denies newly added transport imports and injects named publication I/O
# failures already represented by original unittest.mock cases. It neither
# replaces main nor substitutes any checker, workflow result, or report summary.
STARTUP = r'''import atexit, hashlib, importlib.abc, json, os, pathlib, sys
config = json.loads(pathlib.Path(os.environ["BIOCOMPILER_CLI_CAPTURE_CONFIG"]).read_bytes())
denied = tuple(config["denied_modules"])
class Deny(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + ".") for name in denied):
            raise AssertionError("Original CLI imported excluded transport: " + fullname)
        return None
finder = Deny()
sys.meta_path.insert(0, finder)
assert not any(name in sys.modules for name in denied)
fault = config["fault"]
if fault is not None:
    import biocompiler.cli as cli
    kind = fault["kind"]
    if kind in ("replace", "fsync"):
        def broken(*args, **kwargs):
            raise OSError(fault["message"])
        setattr(cli.os, kind, broken)
    elif kind == "short_write":
        original_fdopen = cli.os.fdopen
        class Short:
            def __init__(self, stream): self.stream = stream
            def __enter__(self): self.stream.__enter__(); return self
            def __exit__(self, *args): return self.stream.__exit__(*args)
            def __getattr__(self, name): return getattr(self.stream, name)
            def write(self, data): return self.stream.write(data[:-1])
        cli.os.fdopen = lambda *args, **kwargs: Short(original_fdopen(*args, **kwargs))
    elif kind == "serialized_length":
        # Runs the real workflow first; only the later publication serializer
        # is a deliberate boundary fault. This output has no semantic claim.
        cli.SyntheticVerificationRecord.to_json = lambda self: " " * fault["bytes"]
    else:
        raise AssertionError("Unknown explicitly frozen publication fault")
def audit():
    root = pathlib.Path(config["root"])
    modules = {}
    for name, module in sorted(sys.modules.items()):
        if name == "biocompiler" or name.startswith("biocompiler."):
            path = pathlib.Path(module.__file__)
            relative = path.relative_to(root).as_posix()
            modules[name] = {"path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    record = {"modules": modules, "guard_active": finder in sys.meta_path,
              "denied_absent": not any(name in sys.modules for name in denied)}
    pathlib.Path(config["audit"]).write_text(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
atexit.register(audit)
'''


class Store:
    def __init__(self): self.blobs = {}
    def retain(self, raw):
        require(type(raw) is bytes, "CLI captures require exact bytes")
        identity = sha(raw)
        # Huge adversarial whitespace remains exactly reconstructable.
        if len(raw) > 1024 * 1024 and (raw == b" " * len(raw) or raw == b" " * (len(raw) - 1) + b"\n"):
            body = len(raw) - (1 if raw.endswith(b"\n") else 0)
            return {"kind": "repeat", "byte": 32, "count": body,
                    "suffix_hex": "0a" if raw.endswith(b"\n") else "", "bytes": len(raw), "sha256": identity}
        self.blobs[identity] = raw
        return {"kind": "blob", "bytes": len(raw), "sha256": identity}


def restore(reference, blobs):
    require(type(reference) is dict and set(reference) in (
        {"kind", "bytes", "sha256"}, {"kind", "byte", "count", "suffix_hex", "bytes", "sha256"}),
        "Unknown exact CLI byte recipe")
    if reference["kind"] == "blob": raw = blobs[reference["sha256"]]
    else:
        require(reference["kind"] == "repeat" and reference["byte"] == 32 and
                type(reference["count"]) is int and 1024 * 1024 < reference["count"] <= MAX_OUTPUT + 1 and
                reference["suffix_hex"] in ("", "0a"), "Unsupported CLI repetition recipe")
        raw = bytes((reference["byte"],)) * reference["count"] + bytes.fromhex(reference["suffix_hex"])
    require(len(raw) == reference["bytes"] and sha(raw) == reference["sha256"], "Changed exact CLI bytes")
    return raw


def actual_sources(original):
    names = {item["path"] for item in original.index["source_files"]}
    for folder in (ROOT / "src/biocompiler", ROOT / "examples"):
        names.update(path.relative_to(ROOT).as_posix() for path in folder.rglob("*.py"))
    sources = [{"path": name, "sha256": sha((ROOT / name).read_bytes())} for name in sorted(names)]
    return source_scope(sources)


def original_cases(original):
    cases = []
    for context in original.index["contexts"]:
        for position, call in enumerate(original.document(context["ledger"])):
            if call["api"] != "workflow.cli": continue
            invocation = json.loads(original.document(call["input"]))
            require(invocation["kwargs"] == {} and len(invocation["args"]) == 1,
                    "Unreviewed original CLI call signature")
            before = original.document(call["files_before"])
            fault = call.get("publication_override")
            if fault:
                require(fault == {"operation": "os.replace", "error": {
                    "module": "builtins", "type": "OSError", "message": "disk unavailable"}},
                    "Unreviewed original publication override")
                fault = {"kind": "replace", "message": "disk unavailable"}
            cases.append({"id": context["id"] + "/api/" + str(position), "origin": "original_occurrence",
                "argv": invocation["args"][0], "files": {name: value["text"].encode() for name, value in before.items()},
                "directories": [], "symlinks": {}, "fault": fault,
                "lineage": {"context": context, "position": position, "call": call,
                            "source": original.index["source_locations"][call["source"]]},
                "original_expected": {"exit_code": original.document(call["result"]),
                    "stdout": original.document(call["stdout"]).encode(),
                    "stderr": original.document(call["stderr"]).encode(),
                    "files_after": original.document(call["files_after"])}})
    require(len(cases) == 16 and Counter(case["argv"][0] for case in cases) == {
        "inspect": 6, "synthetic-check": 5, "synthetic-explore": 2,
        "synthetic-reduce": 1, "synthetic-replay": 2}, "Original16 CLI census changed")
    return cases


def cases(original):
    result = original_cases(original)
    supplement = {row["name"]: row for row in original.supplement["cases"]}
    def add(name, argv, *, authority=None, retained=None, files=None, directories=(), symlinks=None,
            fault=None, lineage=None):
        folder = CLI_ROOT / "cases" / name
        paths = {"REQUEST": str(folder / "request.json"), "RECORD": str(folder / "record.json"),
                 "OUTPUT": str(folder / "output.json"), "ROOT": str(folder)}
        def expand(value):
            for key, path in paths.items(): value = value.replace("{" + key + "}", path)
            return value
        data = {expand(key): value for key, value in (files or {}).items()}
        if authority is not None: data[paths["REQUEST"]] = authority
        if retained is not None: data[paths["RECORD"]] = retained
        result.append({"id": name, "origin": "independent_boundary" if lineage is None else "supplemental_original",
            "argv": [expand(value) for value in argv], "files": data,
            "directories": [expand(value) for value in directories],
            "symlinks": {expand(key): expand(value) for key, value in (symlinks or {}).items()},
            "fault": fault, "lineage": lineage, "original_expected": None})
    for name, row in supplement.items():
        record = canonical(row["expected"])
        authority = canonical(row["expected"]["request"])
        lineage = {"supplemental_name": name, "full_record_sha256": sha(record), "supplement_pin": SUPPLEMENT_PIN}
        add(name + "-run", ["synthetic-" + row["expected"]["request"]["operation"], "--request", "{REQUEST}", "--output", "{OUTPUT}"],
            authority=authority, lineage=lineage)
        add(name + "-replay", ["synthetic-replay", "{RECORD}", "--expected-request", "{REQUEST}", "--output", "{OUTPUT}"],
            authority=authority, retained=record, lineage=lineage)
    # Preserve the complete original capped reduction; do not regenerate its
    # expected result by altering or sampling a successful reduction.
    nonminimal = []
    for context in original.index["contexts"]:
        if not context["id"].endswith("test_wrong_reset_model_reduces_only_the_selected_inactive_failure"): continue
        for position, call in enumerate(original.document(context["ledger"])):
            if call["api"] == "run_synthetic_verification" and call["outcome"] == "returned":
                record = original.document(call["result"])
                if isinstance(record, str): record = json.loads(record)
                if record["request"]["operation"] == "reduce" and not record["result"]["one_minimal"]:
                    nonminimal.append((record, {"context": context["id"], "position": position, "call": call}))
    require(len(nonminimal) == 1, "Original nonminimal reduction census changed")
    record, lineage = nonminimal[0]
    for replay in (False, True):
        add("nonminimal-" + ("replay" if replay else "run"),
            ["synthetic-replay", "{RECORD}", "--expected-request", "{REQUEST}", "--output", "{OUTPUT}"] if replay else
            ["synthetic-reduce", "--request", "{REQUEST}", "--output", "{OUTPUT}"],
            authority=canonical(record["request"]), retained=canonical(record) if replay else None, lineage=lineage)
    passed = supplement["candidate_pass"]["expected"]
    authority, retained = canonical(passed["request"]), canonical(passed)
    check = ["synthetic-check", "--request", "{REQUEST}"]
    replay = ["synthetic-replay", "{RECORD}", "--expected-request", "{REQUEST}"]
    prior = {"{OUTPUT}": b"prior diagnostic evidence"}
    add("default-no-output", check, authority=authority)
    add("replay-default-no-output", replay, authority=authority, retained=retained)
    add("noncanonical-request-whitespace-and-order", check + ["--output", "{OUTPUT}"],
        authority=json.dumps(dict(reversed(list(passed["request"].items()))), ensure_ascii=False, indent=3).encode() + b"\n")
    add("command-mismatch", ["synthetic-explore", "--request", "{REQUEST}", "--output", "{OUTPUT}"], authority=authority, files=prior)
    for name, raw in (("invalid-json", b'{"unfinished":'), ("invalid-utf8", b'\xff'),
                      ("input-one-over", b" " * (MAX_INPUT + 1)), ("input-at-limit", b" " * MAX_INPUT),
                      ("invalid-schema", b'{"schema_version":"wrong"}')):
        add(name, check + ["--output", "{OUTPUT}"], authority=raw, files=prior)
    add("missing-input", check + ["--output", "{OUTPUT}"], files=prior)
    add("missing-output-parent", check + ["--output", "{ROOT}/missing/output.json"], authority=authority)
    add("directory-output", check + ["--output", "{OUTPUT}"], authority=authority, directories=("{OUTPUT}",))
    add("symlink-output", check + ["--output", "{OUTPUT}"], authority=authority,
        files={"{ROOT}/target.json": b"prior diagnostic evidence"}, symlinks={"{OUTPUT}": "{ROOT}/target.json"})
    add("input-output-alias", check + ["--output", "{REQUEST}"], authority=authority)
    add("resolved-input-output-alias", check + ["--output", "{ROOT}/nested/../request.json"], authority=authority,
        directories=("{ROOT}/nested",))
    add("symlink-input-output-alias", ["synthetic-check", "--request", "{ROOT}/alias.json", "--output", "{REQUEST}"],
        authority=authority, symlinks={"{ROOT}/alias.json": "{REQUEST}"})
    add("replay-missing-record", replay + ["--output", "{OUTPUT}"], authority=authority, files=prior)
    for name, raw in (("replay-invalid-json", b'{"unfinished":'), ("replay-invalid-utf8", b'\xff'),
                      ("replay-input-one-over", b" " * (MAX_OUTPUT + 1))):
        add(name, replay + ["--output", "{OUTPUT}"], authority=authority, retained=raw, files=prior)
    add("replay-authority-before-record-error", replay + ["--output", "{OUTPUT}"],
        authority=b'{"schema_version":"wrong"}', retained=b'{"unfinished":', files=prior)
    add("replay-output-record-alias", replay + ["--output", "{RECORD}"], authority=authority, retained=retained)
    add("replay-output-authority-alias", replay + ["--output", "{REQUEST}"], authority=authority, retained=retained)
    for name, fault in (("publication-fsync", {"kind": "fsync", "message": "capture fsync unavailable"}),
                        ("publication-short-write", {"kind": "short_write"}),
                        ("publication-size-at-limit", {"kind": "serialized_length", "bytes": MAX_OUTPUT - 1}),
                        ("publication-size-one-over", {"kind": "serialized_length", "bytes": MAX_OUTPUT})):
        add(name, check + ["--output", "{OUTPUT}"], authority=authority, files=prior, fault=fault)
    add("missing-required-request", ["synthetic-check"])
    add("missing-required-replay-authority", ["synthetic-replay", "{RECORD}"], retained=retained)
    add("unknown-flag", check + ["--unknown-workflow-option"], authority=authority)
    require(len({case["id"] for case in result}) == len(result), "Duplicate actual child occurrence")
    return result


@contextmanager
def owned_directories():
    owned = []
    try:
        for path in (ORIGINAL_ROOT, CLI_ROOT):
            path.mkdir()  # Never reuse or erase another process's directory.
            owned.append(path)
        yield
    finally:
        for path in reversed(owned): shutil.rmtree(path)


def safe_path(value):
    path = Path(value)
    require(path.is_absolute() and any(path.is_relative_to(root) and path != root
            for root in (ORIGINAL_ROOT, CLI_ROOT / "cases")), "CLI fixture path leaves exclusive namespaces")
    return path


def snapshot(roots, store):
    result = {}
    for root in roots:
        for path in sorted(root.rglob("*")):
            if path.is_symlink(): result[str(path)] = {"kind": "symlink", "target": os.readlink(path)}
            elif path.is_dir(): result[str(path)] = {"kind": "directory"}
            else:
                require(path.is_file() and path.stat().st_size <= MAX_OUTPUT + 1, "Unexpected CLI filesystem member")
                result[str(path)] = {"kind": "file", "content": store.retain(path.read_bytes())}
    return result


def run_case(case, scope, store):
    # Each occurrence gets the exact original pre-state, including prior report
    # contents. No sibling command can supply a cached semantic result.
    for folder in (ORIGINAL_ROOT, CLI_ROOT / "cases"):
        folder.mkdir(exist_ok=True)
        for child in folder.iterdir():
            if child.is_dir() and not child.is_symlink(): shutil.rmtree(child)
            else: child.unlink()
    for name in case["directories"]: safe_path(name).mkdir(parents=True, exist_ok=True)
    for name, raw in case["files"].items():
        path = safe_path(name); path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    for name, target in case["symlinks"].items():
        path = safe_path(name); path.parent.mkdir(parents=True, exist_ok=True); safe_path(target); path.symlink_to(target)
    before = snapshot((ORIGINAL_ROOT, CLI_ROOT / "cases"), store)
    config = {"root": str(ROOT), "denied_modules": scope["denied_modules"], "fault": case["fault"],
              "audit": str(CLI_ROOT / "audit.json")}
    (CLI_ROOT / "config.json").write_bytes(canonical(config))
    audit_path = CLI_ROOT / "audit.json"
    audit_path.unlink(missing_ok=True)
    child = subprocess.run([sys.executable, "-m", "biocompiler", *case["argv"]], cwd=CLI_ROOT / "cwd",
        env={**os.environ, "PYTHONPATH": os.pathsep.join((str(CLI_ROOT / "startup"), str(ROOT / "src"))),
             "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8",
             "BIOCOMPILER_CLI_CAPTURE_CONFIG": str(CLI_ROOT / "config.json")},
        capture_output=True, timeout=60)
    require(audit_path.is_file(), "Actual public child did not complete its import audit")
    audit = json.loads(audit_path.read_bytes())
    require(audit["guard_active"] and audit["denied_absent"] and "biocompiler.cli" in audit["modules"],
            "Actual public child bypassed baseline import/source guard")
    pins = {item["path"]: item["sha256"] for item in scope["actual_sources"]}
    require(all(pins.get(item["path"]) == item["sha256"] for item in audit["modules"].values()),
            "Actual child imported an unpinned product source")
    after = snapshot((ORIGINAL_ROOT, CLI_ROOT / "cases"), store)
    expected = case["original_expected"]
    if expected is not None:
        require((child.returncode, child.stdout, child.stderr) ==
                (expected["exit_code"], expected["stdout"], expected["stderr"]),
                "Actual child differs from original CLI occurrence: " + case["id"])
        observed = {}
        for item in case["argv"][1:]:
            path = Path(item)
            if path.is_file():
                raw = path.read_bytes()
                observed[item] = {"bytes": len(raw), "sha256": sha(raw), "text": raw.decode()}
        require(observed == expected["files_after"], "Actual child files differ from full original observation")
    require(not any(Path(name).name.startswith(".") and Path(name).suffix == ".tmp" for name in after),
            "Publication left a temporary file")
    return {"id": case["id"], "origin": case["origin"], "argv": case["argv"], "fault": case["fault"],
        "lineage": case["lineage"], "files_before": before, "files_after": after,
        "exit_code": child.returncode, "stdout": store.retain(child.stdout), "stderr": store.retain(child.stderr),
        "import_audit": audit, "original_full_observation_equal": expected is not None}


def capture():
    original = Corpus()
    scope = actual_sources(original)
    store = Store()
    rows = []
    with owned_directories():
        (CLI_ROOT / "startup").mkdir(); (CLI_ROOT / "cwd").mkdir()
        (CLI_ROOT / "startup/sitecustomize.py").write_text(STARTUP)
        for case in cases(original):
            rows.append(run_case(case, scope, store))
    require(actual_sources(original) == scope, "Product source changed during actual CLI capture")
    sources = {path: store.retain((ROOT / path).read_bytes()) for path in (
        "src/biocompiler/cli.py", "src/biocompiler/__main__.py", "src/biocompiler/compiler/verification_workflow.py",
        "tests/test_synthetic_design_workflows.py", "tests/test_verification_campaign.py",
        "tests/test_synthetic_verification_workflow.py", "tools/freeze_workflow_cli.py")}
    document = {"schema_version": SCHEMA, "original_corpus_pin": CORPUS_PIN, "supplement_pin": SUPPLEMENT_PIN,
        "source_scope": scope, "retained_source_bytes": sources,
        "capture_environment": {"entrypoint": ["python", "-m", "biocompiler"],
            "exclusive_namespaces": [str(ORIGINAL_ROOT), str(CLI_ROOT)], "cwd": str(CLI_ROOT / "cwd"),
            "hash_seed": "0", "io_encoding": "utf-8", "startup": store.retain(STARTUP.encode()),
            "path_policy": "exact paths chosen before execution; no postprocessing; collision fails",
            "size_recipes": "lossless repeated ASCII spaces and optional trailing newline",
            "scope": "original Python public CLI children only; native routing remains unvalidated"},
        "coverage": {"actual_children": len(rows), "original_occurrences": 16,
            "commands": dict(sorted(Counter(row["argv"][0] for row in rows).items())),
            "exits": dict(sorted(Counter(str(row["exit_code"]) for row in rows).items()))}, "cases": rows}
    document["inventory_fingerprint"] = digest(document)
    return document, store.blobs


def write(document, blobs, target=CORPUS):
    target = Path(target); target.parent.mkdir(parents=True, exist_ok=True)
    directory = target.with_suffix("")
    directory.mkdir(exist_ok=True)
    for identity, raw in blobs.items():
        path = directory / (identity + ".bin")
        if path.exists(): require(path.read_bytes() == raw, "Existing CLI content identity changed")
        else: path.write_bytes(raw)
    target.write_bytes(canonical(document) + b"\n")


def load(target=CORPUS):
    target = Path(target); raw = target.read_bytes(); document = json.loads(raw)
    require(raw == canonical(document) + b"\n", "Noncanonical CLI inventory")
    require(document["inventory_fingerprint"] == digest({key: value for key, value in document.items()
            if key != "inventory_fingerprint"}), "CLI inventory identity changed")
    blobs = {}
    for path in target.with_suffix("").iterdir():
        require(path.is_file() and not path.is_symlink() and path.suffix == ".bin", "Unexpected CLI content member")
        body = path.read_bytes(); require(path.stem == sha(body), "CLI content identity changed")
        blobs[path.stem] = body
    used = set()
    def walk(value):
        if isinstance(value, dict):
            if value.get("kind") in ("blob", "repeat"):
                restore(value, blobs)
                if value["kind"] == "blob": used.add(value["sha256"])
            else:
                for item in value.values(): walk(item)
        elif isinstance(value, list):
            for item in value: walk(item)
    walk(document)
    require(used == set(blobs), "Unreferenced or missing complete CLI content")
    return document, blobs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=CORPUS)
    args = parser.parse_args()
    require(args.freeze != args.check, "Select exactly one --freeze or --check")
    document, blobs = capture()
    if args.freeze: write(document, blobs, args.output)
    else:
        expected, old_blobs = load(args.output)
        require(canonical(document) == canonical(expected) and blobs == old_blobs,
                "Fresh complete CLI child capture differs from immutable baseline")
    print(json.dumps({"status": "frozen" if args.freeze else "complete_recapture_equal",
        "inventory_fingerprint": document["inventory_fingerprint"], "coverage": document["coverage"],
        "content_bytes": sum(map(len, blobs.values())), "content_documents": len(blobs)}, sort_keys=True))


if __name__ == "__main__": main()
