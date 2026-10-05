"""Run every frozen CLI child against both installed native executable roles.

Complete stdout, stderr, exit status and filesystem observations must equal the
original Python baseline or its single independently pinned argparse runtime
counterpart. Native selection flags and source/guard audit metadata
are explicit additional evidence, never normalized output. Six historical
inspection commands retain their original non-accepting inspection scope.
"""
from __future__ import annotations
if __package__:
    from .check_realization_binaries import executable_path as native_executable
else:
    from check_realization_binaries import executable_path as native_executable


import argparse
from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
from uuid import UUID

if __package__:
    from . import cli_runtime_counterparts as runtime
    from . import freeze_workflow_cli as f
    from . import check_workflow_reproducibility as r
    from . import check_native_workflow_public_sdk as policy
else:
    import cli_runtime_counterparts as runtime
    import freeze_workflow_cli as f
    import check_workflow_reproducibility as r
    import check_native_workflow_public_sdk as policy

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "biocompiler.native_workflow_cli_conformance.v1"
SCOPE = "complete_explicit_native_workflow_cli_and_historical_inspection_no_pipeline_or_export_cutover"
RECEIPT_FILE = "workflow-cli.json"
ARTIFACT_DIRECTORY = "workflow-cli-artifacts"
BASELINE_PIN = "a67edb95f75aa011ed5c059fe8cbe578fbe118d056931e3992f73775e8951da7"
SOURCES = ("tools/check_native_workflow_cli.py", "tools/check_native_workflow_public_sdk.py",
           "tools/freeze_workflow_cli.py", "tests/test_native_workflow_cli_campaign.py",
           "tools/cli_runtime_counterparts.py", "tests/conformance/workflow-cli-runtime-counterparts-v1.json")
canonical, require, digest = r.canonical, r.require, r.digest
PLATFORMS, PYTHONS, ROLES = r.PLATFORMS, r.PYTHONS, r.ROLES
OPERATIONS = {"validate-verification-workflow-authority", "run-verification-workflow", "replay-verification-workflow"}

# Preload installed modules before measuring execution. The actual console or
# module entry point then runs normally; no main-function or transport patches.
STARTUP = r'''
import atexit, hashlib, json, os, pathlib, sys
config = json.loads(pathlib.Path(os.environ["BIOCOMPILER_NATIVE_CLI_CONFIG"]).read_bytes())
sys.path.insert(0, config["tools"])
import check_native_workflow_public_sdk as policy
import biocompiler, biocompiler.cli as cli
biocompiler._load_legacy_exports()
import biocompiler.entrypoint
import biocompiler.workflow_cli
import biocompiler.workflow_backend as backend
import biocompiler.core_workflow_authority
root = pathlib.Path(biocompiler.__file__).resolve().parent
assert not root.is_relative_to(pathlib.Path(config["checkout"]))
fault = config["fault"]
if fault:
    # Inject the original publication fault at the same CLI call sites without
    # altering the now-separate artifact transport's use of the shared os module.
    class PublicationOS:
        def __getattr__(self, name): return getattr(os, name)
    cli.os = PublicationOS()
    kind = fault["kind"]
    if kind in ("replace", "fsync"):
        def broken(*args, **kwargs): raise OSError(fault["message"])
        setattr(cli.os, kind, broken)
    elif kind == "short_write":
        original = cli.os.fdopen
        class Short:
            def __init__(self, stream): self.stream = stream
            def __enter__(self): self.stream.__enter__(); return self
            def __exit__(self, *args): return self.stream.__exit__(*args)
            def __getattr__(self, key): return getattr(self.stream, key)
            def write(self, raw): return self.stream.write(raw[:-1])
        cli.os.fdopen = lambda *args, **kwargs: Short(original(*args, **kwargs))
    elif kind == "serialized_length":
        backend.NativeWorkflowRecord.to_json = lambda self: " " * fault["bytes"]
    else: raise AssertionError("Unknown publication fault")
seen, responses, artifacts, wires = set(), [], {}, {}
cli_calls = {"main", "_verification_command", "_bounded_text", "_publish_report",
             "_workflow_core_arguments", "_register_circuit_infrastructure_commands", "_architecture_core_arguments",
             "_synthetic_producer_core_arguments"}
def guard(frame, event, value):
    module, code = frame.f_globals.get("__name__", ""), frame.f_code
    if event == "call" and module.startswith("biocompiler"):
        entry = (module, code.co_qualname, "input" if policy.input_phase() else "output", policy.frame_owner(frame))
        permitted = (entry[2] == "output" and (
            module in {"biocompiler.workflow_cli", "biocompiler.core_workflow_authority"}
            or module == "biocompiler.cli" and code.co_qualname.split(".<locals>.", 1)[0] in cli_calls
            or module == "biocompiler.entrypoint" and code.co_qualname == "main" and entry[3] == ""
            or module == "biocompiler" and code.co_qualname == "_load_legacy_exports" and entry[3] == ""
            or module == "biocompiler.__main__" and code.co_qualname == "<module>"
            or module == "biocompiler.ir.serialization" and code.co_qualname.split(".<locals>.", 1)[0] in {"parse_json", "require"}
            or module != "biocompiler.compiler.verification_workflow" and policy.allowed_frame(frame)))
        if not permitted: raise AssertionError("Forbidden Python authority on native CLI: " + repr(entry))
        seen.add(entry)
    if event == "return" and module == "biocompiler.core_artifacts" and code.co_name == "_exchange_artifacts" and value is not None:
        raw, exit_code = value
        wire = json.loads(raw)
        if wire["operation"] in config["operations"]:
            identity = hashlib.sha256(raw).hexdigest()
            destination = pathlib.Path(config["native_artifacts"]) / (identity + ".bin")
            if destination.exists(): assert destination.read_bytes() == raw
            else: destination.write_bytes(raw)
            wires[wire["request_id"]] = {"content": {"sha256": identity, "bytes": len(raw)}, "exit_code": exit_code}
    if event == "return" and module == "biocompiler.core_client" and code.co_name == "_response" and value is not None:
        if value.operation in config["operations"]:
            responses.append({"protocol": "biocompiler.core.v1", "request_id": value.request_id,
                "operation": value.operation, "status": value.status, "result": value.result,
                "diagnostics": [{"code": d.code, "message": d.message, "path": d.path} for d in value.diagnostics],
                "core": {"implementation": "ocaml", "version": value.version,
                         "protocol": "biocompiler.core.v1", "executable": value.executable}})
    if event == "return" and module == "biocompiler.core_artifacts" and code.co_name == "call_artifact" and value is not None:
        raw = value.artifact
        identity = hashlib.sha256(raw).hexdigest()
        destination = pathlib.Path(config["native_artifacts"]) / (identity + ".bin")
        if destination.exists(): assert destination.read_bytes() == raw
        else: destination.write_bytes(raw)
        artifacts[value.response.request_id] = {"sha256": identity, "bytes": len(raw)}
def audit():
    active = sys.getprofile() is guard
    sys.setprofile(None)
    modules = {}
    for name, module in sorted(sys.modules.items()):
        if name == "biocompiler" or name.startswith("biocompiler."):
            path = pathlib.Path(module.__file__).resolve()
            assert path.is_relative_to(root)
            relative = "src/biocompiler/" + path.relative_to(root).as_posix()
            modules[name] = {"path": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    result = {"scope": config["scope"], "guard_active": active,
              "functions": sorted(seen), "modules": modules, "package_path": str(root),
              "responses": responses, "native_artifacts": artifacts, "wire_responses": wires}
    pathlib.Path(config["audit"]).write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")
atexit.register(audit)
if config["scope"] == "native_workflow": sys.setprofile(guard)
'''


def baseline():
    document, blobs = f.load()
    require(document["inventory_fingerprint"] == BASELINE_PIN and len(document["cases"]) == 70,
            "Complete immutable CLI baseline changed")
    return document, blobs


def product_sources():
    return {path.relative_to(ROOT).as_posix(): f.sha(path.read_bytes())
            for path in sorted((ROOT / "src/biocompiler").rglob("*.py"))}


def read_artifacts(directory, declared):
    """Read every complete CLI byte member, including legitimate empty streams."""
    directory = Path(directory)
    require(directory.is_dir() and not directory.is_symlink() and type(declared) is dict and
            all(r.pin(key) for key in declared), "Unsafe CLI evidence inventory")
    require({path.name for path in directory.iterdir()} == {key + ".bin" for key in declared},
            "Missing or extra complete CLI content")
    result = {}
    for identity, descriptor in declared.items():
        require(type(descriptor) is dict and set(descriptor) == {"path", "bytes", "sha256"} and
                descriptor["path"] == identity + ".bin" and descriptor["sha256"] == identity and
                type(descriptor["bytes"]) is int and 0 <= descriptor["bytes"] <= f.MAX_OUTPUT + 1,
                "Invalid complete CLI descriptor")
        path = directory / descriptor["path"]
        require(path.is_file() and not path.is_symlink() and path.stat().st_size == descriptor["bytes"],
                "Missing, linked or resized CLI bytes")
        with path.open("rb") as source: raw = source.read(f.MAX_OUTPUT + 2)
        require(len(raw) == descriptor["bytes"] and f.sha(raw) == identity, "Complete CLI bytes differ")
        result[identity] = raw
    return result


class Oracle:
    """Original complete workflow results, independently bound to CLI inputs."""
    def __init__(self):
        corpus = f.Corpus()
        self.cases = {case["id"]: case for case in f.cases(corpus)}
        self.profile = deepcopy(corpus.supplement["profile"])
        require(digest(self.profile) == r.PROFILE_PIN, "Original workflow profile differs")
        self.profile.update(profile="biocompiler.core.verification_workflow.v2",
            implementation_version="biocompiler.ocaml.verification_workflow_service.v0.2",
            presentation_profile="biocompiler.core.verification_workflow.presentation.v1")
        self.records = {}
        for case in corpus.cases():
            if case["expected"] is not None:
                identity = digest(r.decode(case["authority"]))
                require(identity not in self.records or self.records[identity] == case["expected"],
                        "Original CLI authority has contradictory workflow results")
                self.records[identity] = case["expected"]

    def inputs(self, case):
        flag = "--expected-request" if case["argv"][0] == "synthetic-replay" else "--request"
        if flag not in case["argv"]: return None, None
        path = case["argv"][case["argv"].index(flag) + 1]
        path = case["symlinks"].get(path, path)
        return case["files"].get(path), (case["files"].get(case["argv"][1]) if flag == "--expected-request" else None)

    def trace(self, identifier):
        case = self.cases[identifier]
        command = case["argv"][0]
        if command == "inspect" or identifier in {"missing-required-request", "missing-required-replay-authority",
            "unknown-flag", "invalid-json", "invalid-utf8", "input-one-over", "input-at-limit", "missing-input"}:
            return []
        authority, retained = self.inputs(case)
        replay = command == "synthetic-replay"
        first = "validate-verification-workflow-authority" if replay else "run-verification-workflow"
        if identifier in {"invalid-schema", "replay-authority-before-record-error"}:
            return [(first, "error", {"code": "verification_workflow", "path": "authority",
                    "message": "Invalid fields in SyntheticVerificationRequest."}, None)]
        require(authority is not None, "Missing complete original CLI authority")
        source = r.decode(authority)
        require(digest(source) in self.records, "CLI authority is absent from original complete workflow oracle")
        record = self.records[digest(source)]
        if not replay:
            if command != "synthetic-" + source["operation"]:
                return [(first, "error", {"code": "workflow_protocol_command", "path": None,
                    "message": "Command and frozen verification operation disagree."}, None)]
            return [(first, "ok", None, record)]
        result = [(first, "ok", None, canonical(r.decode(record)["request"]))]
        if identifier in {"replay-missing-record", "replay-invalid-json", "replay-invalid-utf8", "replay-input-one-over"}:
            return result
        require(retained is not None, "Missing original replay history")
        if digest(r.decode(retained)["request"]) != digest(r.decode(record)["request"]):
            return result + [("replay-verification-workflow", "error", {"code": "synthetic_verification", "path": None,
                "message": "Verification operation differs from independent authority."}, None)]
        return result + [("replay-verification-workflow", "ok", None, record)]

    def semantic(self, role, identifier, operation, request_id, artifact):
        case = self.cases[identifier]
        authority, retained = self.inputs(case)
        source, normalized = r.decode(authority), r.decode(artifact)
        authority_only = operation == "validate-verification-workflow-authority"
        profile = self.profile
        expected = {"schema_version": "biocompiler.core.verification_workflow_authority_result.v1" if authority_only
                    else "biocompiler.core.verification_workflow_result.v2",
            "profile": "biocompiler.core.verification_workflow_authority.v1" if authority_only else profile["profile"],
            "operation": operation, "request_id": request_id, "executable": role,
            "validation_scope": "fresh_source_authority_only" if authority_only else profile["validation_scope"],
            "implementation_version": "biocompiler.ocaml.verification_workflow_authority.v0.1" if authority_only
                else profile["implementation_version"], "workflow_version": profile["workflow_version"],
            "workflow_operation": source["operation"], "mode": source["mode"],
            "authority_fingerprint": digest(source),
            "request_fingerprint": digest(normalized if authority_only else normalized["request"]),
            "resources": r.effective_resources(profile, None)}
        if not authority_only:
            action, outcome = source["operation"], normalized["result"]
            passed = (outcome["outcome"] == "pass" if action == "check" else
                      outcome["all_passed"] if action == "explore" else outcome["one_minimal"])
            expected.update(retained_record_fingerprint=None if retained is None else digest(r.decode(retained)),
                record_fingerprint=f.sha(artifact), command=case["argv"][0], presentation={
                    "profile": profile["presentation_profile"], "command_exit_code": 0 if retained is not None or passed else 1,
                    "original_frames": len(outcome["original_history"]) if action == "reduce" else None,
                    "reduced_frames": len(outcome["history"]) if action == "reduce" else None})
        return expected


CLI_CALLS = {"main", "_verification_command", "_bounded_text", "_publish_report", "_workflow_core_arguments",
             "_register_circuit_infrastructure_commands", "_architecture_core_arguments", "_synthetic_producer_core_arguments"}


def allowed_cli_call(module, name, phase, owner):
    if phase != "output": return False
    root = name.split(".<locals>.", 1)[0]
    return (module in {"biocompiler.workflow_cli", "biocompiler.core_workflow_authority"}
        or module == "biocompiler.cli" and root in CLI_CALLS
        or module == "biocompiler.entrypoint" and name == "main" and owner == ""
        or module == "biocompiler" and name == "_load_legacy_exports" and owner == ""
        or module == "biocompiler.__main__" and name == "<module>"
        or module == "biocompiler.ir.serialization" and root in {"parse_json", "require"}
        or module != "biocompiler.compiler.verification_workflow" and policy.allowed_call(module, name, phase, owner))


def configure_case(case):
    for folder in (f.ORIGINAL_ROOT, f.CLI_ROOT / "cases"):
        folder.mkdir(exist_ok=True)
        for child in folder.iterdir():
            if child.is_dir() and not child.is_symlink(): shutil.rmtree(child)
            else: child.unlink()
    for name in case["directories"]: f.safe_path(name).mkdir(parents=True, exist_ok=True)
    for name, raw in case["files"].items():
        path = f.safe_path(name); path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    for name, target in case["symlinks"].items():
        path = f.safe_path(name); path.parent.mkdir(parents=True, exist_ok=True)
        f.safe_path(target); path.symlink_to(target)


def run_case(case, role, executable, executable_pin, store):
    configure_case(case)
    scope = "historical_inspection" if case["argv"][0] == "inspect" else "native_workflow"
    before = f.snapshot((f.ORIGINAL_ROOT, f.CLI_ROOT / "cases"), store)
    native_directory = f.CLI_ROOT / "native-artifacts"
    for path in native_directory.iterdir(): path.unlink()
    config = {"tools": str(ROOT / "tools"), "checkout": str(ROOT), "fault": case["fault"],
        "scope": scope, "operations": sorted(OPERATIONS), "audit": str(f.CLI_ROOT / "audit.json"),
        "native_artifacts": str(native_directory)}
    config_path = f.CLI_ROOT / "config.json"
    config_path.write_bytes(canonical(config))
    audit_path = f.CLI_ROOT / "audit.json"; audit_path.unlink(missing_ok=True)
    selected = [] if scope == "historical_inspection" else [
        "--core-executable" if role == "core" else "--verify-executable", str(executable),
        "--core-sha256", executable_pin, "--core-timeout", "300"]
    # Console uses the actual installed script; Python -m uses the actual module.
    console = shutil.which("biocompiler")
    require(console is not None and not Path(console).resolve().is_relative_to(ROOT), "Installed console script missing")
    command = [sys.executable, "-m", "biocompiler"] if case["entrypoint"] == "module" else [console]
    argv = [case["argv"][0], *selected, *case["argv"][1:]]
    environment = {**os.environ, "PYTHONPATH": str(f.CLI_ROOT / "startup"),
        "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8",
        "BIOCOMPILER_NATIVE_CLI_CONFIG": str(config_path)}
    child = subprocess.run([*command, *argv], cwd=f.CLI_ROOT / "cwd", env=environment,
                           capture_output=True, timeout=900)
    require(audit_path.is_file(), "Installed CLI child did not complete the execution audit")
    audit = r.decode(audit_path.read_bytes())
    artifacts = {}
    for path in native_directory.iterdir():
        require(path.is_file() and not path.is_symlink() and path.suffix == ".bin", "Unsafe child native artifact")
        artifacts[path.stem] = store.retain(path.read_bytes())
    return {"id": case["id"], "role": role, "scope": scope, "argv": argv,
        "entrypoint": case["entrypoint"], "fault": case["fault"], "lineage": case["lineage"],
        "files_before": before, "files_after": f.snapshot((f.ORIGINAL_ROOT, f.CLI_ROOT / "cases"), store),
        "exit_code": child.returncode, "stdout": store.retain(child.stdout), "stderr": store.retain(child.stderr),
        "audit": store.retain(canonical(audit)), "native_artifacts": artifacts,
        "console_path": console, "python_executable": sys.executable}


def equal_observations(actual, original, blobs, old_blobs, *, python_version=None):
    expected = runtime.workflow().expected(original, {"exit_code": original["exit_code"],
        **{field: f.restore(original[field], old_blobs) for field in ("stdout", "stderr")}}, python_version)
    require(type(actual["exit_code"]) is int and actual["exit_code"] == expected["exit_code"],
            "CLI exit differs: " + actual["id"])
    for field in ("stdout", "stderr"):
        require(f.restore(actual[field], blobs) == expected[field],
                "Complete CLI " + field + " differs: " + actual["id"])
    for field in ("files_before", "files_after"):
        left, right = actual[field], original[field]
        require(set(left) == set(right), "Complete CLI filesystem membership differs: " + actual["id"])
        for name, expected in right.items():
            require(left[name]["kind"] == expected["kind"], "CLI filesystem kind differs")
            if expected["kind"] == "file":
                require(f.restore(left[name]["content"], blobs) == f.restore(expected["content"], old_blobs),
                        "Complete CLI file bytes differ: " + name)
            else: require(left[name] == expected, "CLI directory or symlink differs")


def validate_audit(row, audit, blobs, sources, oracle):
    require(type(audit) is dict and set(audit) == {"scope", "guard_active", "functions", "modules", "package_path",
            "responses", "native_artifacts", "wire_responses"}, "Unexpected complete CLI audit fields")
    native = row["scope"] == "native_workflow"
    require(audit["scope"] == row["scope"] and type(audit["guard_active"]) is bool and
            audit["guard_active"] == native, "Missing selected-native execution guard")
    require(type(audit["package_path"]) is str and Path(audit["package_path"]).is_absolute() and
            Path(audit["package_path"]).name == "biocompiler" and
            not Path(audit["package_path"]).is_relative_to(ROOT), "Missing installed package origin")
    require(type(audit["modules"]) is dict and "biocompiler.cli" in audit["modules"], "Missing installed product modules")
    for name, item in audit["modules"].items():
        require(type(item) is dict and set(item) == {"path", "sha256"} and
                item["path"] == "src/" + name.replace(".", "/") + ("/__init__.py" if name == "biocompiler" or
                item["path"].endswith("/__init__.py") else ".py") and sources.get(item["path"]) == item["sha256"],
                "Child imported changed or unpinned product source")
    frames = audit["functions"]
    require(type(frames) is list and all(type(entry) is list and len(entry) == 4 and
            all(type(part) is str for part in entry) for entry in frames), "Invalid executed-function tuple")
    require(frames == sorted(frames) and len({tuple(entry) for entry in frames}) == len(frames) and
            all(entry[0] in audit["modules"] and allowed_cli_call(*entry) for entry in frames),
            "Forbidden, unbound or repeated Python authority frame")
    if not native:
        require(not frames and not audit["responses"] and not audit["native_artifacts"] and not audit["wire_responses"],
                "Historical inspection acquired native acceptance")
    else:
        require(any(entry[:2] == ["biocompiler.cli", "main"] for entry in frames), "Actual CLI entry point missing")
    expected_trace = oracle.trace(row["id"])
    require(type(audit["responses"]) is list and len(audit["responses"]) == len(expected_trace),
            "Expected complete preflight/run/replay occurrence sequence missing")
    if expected_trace:
        require(all(any(entry[:2] == [module, name] for entry in frames) for module, name in (
            ("biocompiler.cli", "_verification_command"), ("biocompiler.workflow_cli", "selected_core_command"),
            ("biocompiler.core_client", "_response"), ("biocompiler.core_artifacts", "call_artifact"))),
            "Actual selected CLI and transport execution missing")
    ids = set()
    authority, retained = oracle.inputs(oracle.cases[row["id"]])
    for envelope, (operation, status, diagnostic, artifact) in zip(audit["responses"], expected_trace):
        require(type(envelope) is dict and set(envelope) == {"protocol", "request_id", "operation", "status", "result",
                "diagnostics", "core"}, "Unexpected native CLI response fields")
        identifier = envelope["request_id"]
        require(type(identifier) is str and re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", identifier) and
                str(UUID(identifier)) == identifier and UUID(identifier).version == 4 and
                identifier not in ids,
                "Duplicate or invalid actual request identity")
        ids.add(identifier)
        require(envelope["operation"] == operation and envelope["status"] == status and envelope["core"] == {
            "implementation": "ocaml", "version": "0.1.0", "protocol": "biocompiler.core.v1", "executable": row["role"]}
            and envelope["protocol"] == "biocompiler.core.v1", "CLI used a different operation, order, result or role")
        wire = audit["wire_responses"].get(identifier)
        require(type(wire) is dict and set(wire) == {"content", "exit_code"} and
                type(wire["exit_code"]) is int and wire["exit_code"] == (0 if status == "ok" else 2),
                "Missing complete actual native response or process exit")
        identity = wire["content"]["sha256"]
        require(identity in row["native_artifacts"], "Complete native response bytes missing")
        raw_wire = f.restore(row["native_artifacts"][identity], blobs)
        require(canonical(wire["content"]) == canonical(r.descriptor(raw_wire)) and
                canonical(r.decode(raw_wire)) == canonical(envelope),
                "Actual native response bytes differ from parsed envelope")
        if status == "error":
            require(envelope["result"] is None and envelope["diagnostics"] == [diagnostic] and
                    identifier not in audit["native_artifacts"], "Rejected CLI operation retained acceptance or changed diagnostics")
            require(f.restore(row["stderr"], blobs) == ("biocompiler: " + diagnostic["message"] + "\n").encode(),
                    "CLI did not expose its exact native rejection")
            continue
        require(not envelope["diagnostics"] and identifier in audit["native_artifacts"], "Successful native artifact missing")
        semantic = oracle.semantic(row["role"], row["id"], operation, identifier, artifact)
        expected = {"schema_version": "biocompiler.core.artifact_response.v1",
            "transport": "biocompiler.core.artifact_transport.authority.v1" if operation == "validate-verification-workflow-authority"
                else "biocompiler.core.artifact_transport.v1", "authority": r.descriptor(authority),
            "retained_record": r.descriptor(retained) if operation == "replay-verification-workflow" else None,
            "artifact": r.descriptor(artifact), "result": semantic}
        require(canonical(envelope["result"]) == canonical(expected), "Native CLI receipt differs from complete original authority/artifact")
        body = audit["native_artifacts"][identifier]
        require(type(body) is dict and set(body) == {"sha256", "bytes"} and body["sha256"] in row["native_artifacts"],
                "Complete native artifact body missing")
        raw = f.restore(row["native_artifacts"][body["sha256"]], blobs)
        require(canonical(body) == canonical(r.descriptor(raw)) and raw == artifact,
                "Native CLI full output differs from independently captured original bytes")
        if operation != "validate-verification-workflow-authority" and row["exit_code"] in (0, 1):
            require(semantic["presentation"]["command_exit_code"] == row["exit_code"], "CLI recomputed native exit policy")
    require(set(audit["wire_responses"]) == ids and set(audit["native_artifacts"]) ==
            {item["request_id"] for item in audit["responses"] if item["status"] == "ok"} and
            ({value["sha256"] for value in audit["native_artifacts"].values()} |
             {value["content"]["sha256"] for value in audit["wire_responses"].values()}) == set(row["native_artifacts"]),
            "Unbound complete CLI native artifacts or responses")

def validate(receipt, blobs, original, old_blobs, *, oracle=None):
    oracle = Oracle() if oracle is None else oracle
    require(type(receipt) is dict and set(receipt) <= {"schema_version", "scope", "status", "baseline_pin",
        "revision", "source_revision", "run_id", "python_version", "system", "machine", "native_platform",
        "native_inputs", "product_sources", "campaign_sources", "executables", "checks", "completed_checks",
        "duration_seconds", "artifacts", "artifact_directory"}, "Unexpected CLI receipt fields")
    require(receipt["schema_version"] == SCHEMA and receipt["scope"] == SCOPE and receipt["status"] == "success"
            and receipt["baseline_pin"] == BASELINE_PIN, "Incomplete or different native CLI evidence")
    require(receipt["product_sources"] == product_sources() and receipt["campaign_sources"] == r.source_pins(SOURCES),
            "Native CLI evidence comes from a different tested source")
    require(type(receipt["executables"]) is dict and set(receipt["executables"]) == set(ROLES) and
            all(type(path) is str and Path(path).is_absolute() and Path(path).name == "biocompiler-" + role
                for role, path in receipt["executables"].items()), "Invalid explicitly selected native executable identity")
    expected = {(role, case["id"]): case for role in ROLES for case in original["cases"]}
    seen, projection = set(), []
    for row in receipt["checks"]:
        require(type(row) is dict and set(row) == {"id", "role", "scope", "argv", "entrypoint", "fault", "lineage",
            "files_before", "files_after", "exit_code", "stdout", "stderr", "audit", "native_artifacts",
            "console_path", "python_executable"}, "Unexpected complete CLI occurrence fields")
        key = row["role"], row["id"]
        require(key in expected and key not in seen, "Missing, duplicate or unexpected original CLI occurrence")
        seen.add(key); old = expected[key]
        require(row["scope"] == ("historical_inspection" if old["argv"][0] == "inspect" else "native_workflow") and
                type(row["exit_code"]) is int and Path(row["console_path"]).is_absolute() and
                Path(row["console_path"]).name == "biocompiler" and not Path(row["console_path"]).is_relative_to(ROOT) and
                Path(row["python_executable"]).is_absolute(), "Invalid original CLI scope or runtime identity")
        require(row["entrypoint"] == old["entrypoint"] and row["fault"] == old["fault"] and
                row["lineage"] == old["lineage"], "Original CLI invocation or fault changed")
        selected = [] if old["argv"][0] == "inspect" else ["--core-executable" if row["role"] == "core" else "--verify-executable",
            receipt["executables"][row["role"]], "--core-sha256", receipt["native_inputs"]["sha256"]["biocompiler-" + row["role"]],
            "--core-timeout", "300"]
        require(row["argv"] == [old["argv"][0], *selected, *old["argv"][1:]], "Explicit CLI native selection changed")
        equal_observations(row, old, blobs, old_blobs, python_version=receipt["python_version"])
        audit = r.decode(f.restore(row["audit"], blobs))
        require(canonical(audit) == f.restore(row["audit"], blobs), "Noncanonical complete CLI audit")
        validate_audit(row, audit, blobs, receipt["product_sources"], oracle)
        # Runtime paths and UUIDs remain in retained full evidence. Only validated
        # process metadata and the separately validated exact argparse runtime
        # counterpart are projected for cross-runtime comparison.
        projected = deepcopy(audit["responses"])
        projected_wires = []
        for position, envelope in enumerate(projected):
            identifier = envelope["request_id"]
            identity = audit["wire_responses"][identifier]["content"]["sha256"]
            wire = f.restore(row["native_artifacts"][identity], blobs)
            require(wire.count(canonical(identifier)) == (2 if envelope["status"] == "ok" else 1),
                    "UUID projection would alter unreviewed native wire content")
            envelope["request_id"] = "runtime-request-" + str(position)
            if envelope["status"] == "ok": envelope["result"]["result"]["request_id"] = envelope["request_id"]
            projected_wires.append(r.descriptor(wire.replace(canonical(identifier), canonical(envelope["request_id"]))))
        projection.append({"role": row["role"], "id": row["id"], "responses": projected,
            "wire_responses": projected_wires,
            "native_artifacts": sorted({value["sha256"] for value in audit["native_artifacts"].values()}),
            "stdout": old["stdout"] if row["id"] in runtime.workflow().cases else row["stdout"],
            "stderr": old["stderr"] if row["id"] in runtime.workflow().cases else row["stderr"],
            "exit_code": row["exit_code"], "files_before": row["files_before"], "files_after": row["files_after"]})
    require(seen == set(expected) and receipt["completed_checks"] == 140, "Complete 140-child native CLI matrix narrowed")
    used = set()
    def visit(value):
        if type(value) is dict:
            if value.get("kind") in ("blob", "repeat"):
                f.restore(value, blobs)
                if value["kind"] == "blob": used.add(value["sha256"])
            else:
                for item in value.values(): visit(item)
        elif type(value) is list:
            for item in value: visit(item)
    visit(receipt["checks"])
    require(used == set(blobs), "Unreferenced or missing complete CLI evidence")
    return sorted(projection, key=lambda item: (item["role"], item["id"]))


def campaign_main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("core", "verify", "native-root", "output"): parser.add_argument("--" + name, required=True, type=Path)
    for name in ("core-sha256", "verify-sha256"): parser.add_argument("--" + name, required=True)
    parser.add_argument("--platform", required=True, choices=PLATFORMS)
    args = parser.parse_args(argv)
    require(not Path.cwd().resolve().is_relative_to(ROOT), "Run installed CLI campaign outside checkout")
    native = r.verify_binaries(args.native_root, os.environ.get("GITHUB_SHA"), args.platform)
    require((platform.system(), platform.machine()) == PLATFORMS[args.platform], "Native platform mismatch")
    original, old_blobs = baseline(); cases = f.cases(f.Corpus()); store = f.Store()
    require([item["id"] for item in cases] == [item["id"] for item in original["cases"]], "Original child census changed")
    receipt = {"schema_version": SCHEMA, "scope": SCOPE, "status": "running", "baseline_pin": BASELINE_PIN,
        "revision": os.environ.get("GITHUB_SHA"), "source_revision": os.environ.get("GITHUB_HEAD_SHA", os.environ.get("GITHUB_SHA")),
        "run_id": os.environ.get("GITHUB_RUN_ID"), "python_version": platform.python_version(),
        "system": platform.system(), "machine": platform.machine(), "native_platform": args.platform,
        "native_inputs": native, "product_sources": product_sources(), "campaign_sources": r.source_pins(SOURCES),
        "executables": {"core": str(args.core), "verify": str(args.verify)}, "checks": [], "completed_checks": 0}
    require(receipt["run_id"] and receipt["source_revision"], "Current hosted run metadata missing")
    started, code = time.monotonic(), 1
    try:
        with f.owned_directories():
            for name in ("startup", "cwd", "native-artifacts"): (f.CLI_ROOT / name).mkdir()
            (f.CLI_ROOT / "startup/sitecustomize.py").write_text(STARTUP)
            for role, executable, pin in (("core", args.core, args.core_sha256), ("verify", args.verify, args.verify_sha256)):
                require(executable.is_absolute() and executable.resolve() == (native_executable(args.native_root, role)).resolve()
                        and not executable.is_symlink() and os.access(executable, os.X_OK) and
                        pin == native["sha256"]["biocompiler-" + role], "Unbound native executable")
                for case in cases:
                    row = run_case(case, role, executable, pin, store)
                    receipt["checks"].append(row)
                    old = next(value for value in original["cases"] if value["id"] == case["id"])
                    equal_observations(row, old, store.blobs, old_blobs, python_version=receipt["python_version"])
        receipt.update(status="success", completed_checks=len(receipt["checks"]))
        validate(receipt, store.blobs, original, old_blobs); code = 0
    except Exception as error:
        receipt.update(status="failure", error=type(error).__name__ + ": " + str(error))
        print(receipt["error"], file=sys.stderr)
    receipt.update(completed_checks=len(receipt["checks"]), duration_seconds=round(time.monotonic() - started, 6))
    directory = args.output.with_name(ARTIFACT_DIRECTORY); directory.mkdir(parents=True, exist_ok=True)
    receipt["artifacts"] = {}
    for identity, raw in store.blobs.items():
        path = directory / (identity + ".bin")
        require(not path.is_symlink() and (not path.exists() or path.read_bytes() == raw), "Conflicting CLI evidence")
        path.write_bytes(raw); receipt["artifacts"][identity] = {"path": path.name, "bytes": len(raw), "sha256": identity}
    receipt["artifact_directory"] = directory.name
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_bytes(canonical(receipt) + b"\n")
    print("Installed native CLI:", receipt["status"], receipt["completed_checks"], "actual children")
    return code


def compare(root, native_root, *, revision, source_revision, run_id):
    require(re.fullmatch(r"[0-9a-f]{40}", revision or "") and re.fullmatch(r"[0-9a-f]{40}", source_revision or "")
            and type(run_id) is str and run_id, "Missing current hosted revision identity")
    root, native_root = Path(root), Path(native_root)
    names = {"realization-" + target + "-py" + python for target in PLATFORMS for python in PYTHONS}
    require(root.is_dir() and not root.is_symlink() and native_root.is_dir() and not native_root.is_symlink() and
            {path.name for path in root.iterdir() if path.name.startswith("realization-")} == names, "Incomplete four-way CLI matrix")
    original, old_blobs = baseline(); oracle = Oracle(); reference, receipts = None, {}
    for target, (system, machine) in PLATFORMS.items():
        native = r.verify_binaries(native_root / target, revision, target)
        for python in PYTHONS:
            name = "realization-" + target + "-py" + python; folder = root / name
            require(folder.is_dir() and not folder.is_symlink(), "Unsafe CLI matrix slot")
            inputs, _ = r.read(folder / "native-inputs.json", r.CONTROL_BYTES)
            value, pin = r.read(folder / RECEIPT_FILE)
            require(canonical({key: inputs.get(key) for key in native}) == canonical(native) and
                    inputs.get("run_id") == run_id and inputs.get("source_revision") == source_revision,
                    "CLI native inputs differ from same-run binary bytes")
            require(value["revision"] == revision and value["source_revision"] == source_revision and value["run_id"] == run_id and
                    value["system"] == system and value["machine"] == machine and value["native_platform"] == target and
                    value["python_version"] == inputs["python_version"] and value["python_version"].startswith(python + ".") and
                    value["native_inputs"] == native and value["artifact_directory"] == ARTIFACT_DIRECTORY,
                    "Stale or mixed native CLI receipt")
            blobs = read_artifacts(folder / ARTIFACT_DIRECTORY, value["artifacts"])
            projection = canonical(validate(value, blobs, original, old_blobs, oracle=oracle))
            if reference is None: reference = projection
            else: require(projection == reference, "Full CLI/native artifact observations differ across runtimes")
            receipts[name] = pin
    return {"schema_version": "biocompiler.workflow_cli_reproducibility.v1", "status": "success",
        "revision": revision, "source_revision": source_revision, "run_id": run_id,
        "baseline_pin": BASELINE_PIN, "receipts": receipts, "children_per_runtime": 140,
        "runtime_counterpart_sha256": runtime.workflow().pin,
        "projection": "validated_actual_request_ids_runtime_paths_and_exact_pinned_argparse_runtime_counterpart_only; complete_actual_bytes_retained",
        "observation_sha256": f.sha(reference)}


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if "--compare" not in arguments: return campaign_main(arguments)
    parser = argparse.ArgumentParser(description="Compare complete installed native CLI evidence")
    parser.add_argument("--compare", action="store_true", required=True)
    for name in ("root", "native-root", "output"): parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(arguments)
    value = compare(args.root, args.native_root, revision=os.environ.get("GITHUB_SHA"),
        source_revision=os.environ.get("GITHUB_HEAD_SHA", os.environ.get("GITHUB_SHA")), run_id=os.environ.get("GITHUB_RUN_ID"))
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_bytes(canonical(value) + b"\n")
    print("Complete native CLI evidence matches across four runtimes")
    return 0


if __name__ == "__main__": raise SystemExit(main())
