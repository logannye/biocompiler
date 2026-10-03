"""Installed v2 presentation campaign and complete four-way byte comparator.

No product module is imported during fixture loading or comparison. The original
v1 campaign remains independent; this campaign preserves every one of its112
cases per role and adds explicit command, authority and resource observations.
"""
from __future__ import annotations
if __package__:
    from .check_realization_binaries import executable_path as native_executable
else:
    from check_realization_binaries import executable_path as native_executable


import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import platform
import re
import sys
import time

if __package__:
    from . import check_native_workflow as c
    from . import check_workflow_reproducibility as r
else:
    import check_native_workflow as c
    import check_workflow_reproducibility as r

ROOT = Path(__file__).resolve().parents[1]
CORPUS_PIN, CAPTURE_PIN, SUPPLEMENTAL_PIN = c.CORPUS_PIN, c.CAPTURE_PIN, c.SUPPLEMENT_PIN
PROFILE_PIN = "a15cfc3423bc7adc739e37ca81f9ecccde284cb22d666a4b3d0bbd768762d01c"
SCHEMA = "biocompiler.native_workflow_presentation_conformance.v1"
SCOPE = "complete_native_raw_workflow_presentation_sdk_public_cli_and_pipeline_unmigrated"
RECEIPT_FILE, ARTIFACT_DIRECTORY = "workflow-presentation.json", "workflow-presentation-artifacts"
CHECKS_PER_ROLE = 137
SOURCES = ("tools/check_native_workflow_presentation.py", "tests/test_native_workflow_presentation.py",
           "tools/check_native_workflow.py", "tools/check_workflow_reproducibility.py")
ROLES, PYTHONS, PLATFORMS = r.ROLES, r.PYTHONS, r.PLATFORMS
TRANSPORT_MODULES = c.TRANSPORT_MODULES
CONTROL_BYTES = r.CONTROL_BYTES
require, canonical, digest, decode = r.require, r.canonical, r.digest, r.decode
read, Artifacts, descriptor, source_pins = r.read, r.Artifacts, r.descriptor, r.source_pins
verify_binaries = r.verify_binaries


def request_identity(role, case):
    return "workflow-public-" + c.sha((role + "|" + case["id"] + "|" + case["phase"]).encode())[:32]


def project_cases(original):
    require(len(original) == 112, "Original v1 workflow matrix was narrowed")
    result = [{**deepcopy(case), "command": None} for case in original]
    for case in original:
        if case["origin"] == "supplemental":
            command = "synthetic-replay" if case["operation"] == "replay-verification-workflow" else (
                "synthetic-" + decode(case["authority"])["operation"])
            result.append({**deepcopy(case), "id": "command/" + case["id"],
                           "origin": "command_success", "command": command})
    base = next(case for case in original if case["id"] == "supplemental/candidate_pass" and case["phase"] == "run")
    mismatch = {"code": "workflow_protocol_command", "message": "Command and frozen verification operation disagree.", "path": None}
    def reject(name, reference, command, *, operation=None, retained=None, error=mismatch):
        result.append({**deepcopy(reference), "id": "command-boundary/" + name, "phase": "reject",
            "origin": "command_precedence", "command": command,
            "operation": operation or reference["operation"], "retained": retained,
            "expected": None, "error": deepcopy(error), "source_evidence": reference["source_evidence"]})
    reject("wrong-operation", base, "synthetic-explore")
    reject("empty-command", base, "")
    reject("command-before-malformed-record", base, "synthetic-check",
           operation="replay-verification-workflow", retained=b'{"unfinished":')
    invalid = next(case for case in original if case["origin"] == "authority_precedence")
    reject("source-before-run-command", invalid, "synthetic-reduce", operation="run-verification-workflow",
           error=invalid["error"])
    reject("source-before-replay-command-and-record", invalid, "synthetic-check",
           retained=invalid["retained"], error=invalid["error"])
    failure = next(case for case in original if case["error"] is not None and
                   case["error"]["message"] == "Initial history does not exhibit the selected FAIL signature.")
    reject("command-before-execution-failure", failure, "synthetic-check")
    result.append({**deepcopy(base), "id": "presentation/all-five-reductions", "origin": "presentation_resource",
        "command": "synthetic-check", "limits": {"max_work": 1_000_000_000_000, "max_monitor_items": 7_000_000,
            "max_request_bytes": 16_777_216, "max_report_bytes": 1_048_576, "max_report_nodes": 100_000}})
    require(len(result) == CHECKS_PER_ROLE and len({(v["id"], v["phase"]) for v in result}) == CHECKS_PER_ROLE,
            "Complete presentation occurrence matrix changed")
    return result


class Corpus:
    def __init__(self):
        # Golden independently rereads all385 original ledgers and requires the
        # complete exact52 original workflow ID/observation set before projection.
        original = r.Golden()
        self.profile = deepcopy(original.profile)
        self.profile.update(profile="biocompiler.core.verification_workflow.v2",
            implementation_version="biocompiler.ocaml.verification_workflow_service.v0.2",
            presentation_profile="biocompiler.core.verification_workflow.presentation.v1")
        require(digest(self.profile) == PROFILE_PIN, "Independent v2 profile changed")
        self._cases = project_cases(original.cases)

    def cases(self):
        return deepcopy(self._cases)


class Golden:
    def __init__(self):
        corpus = Corpus()
        self.profile, self.cases = corpus.profile, corpus.cases()

    expected = r.Golden.expected


def expected_presentation(case):
    # Derive exclusively from immutable full original bytes, never from native
    # candidate output, receipt claims or a product/workflow constructor.
    record = decode(case["expected"])
    operation, result = record["request"]["operation"], record["result"]
    original_frames = reduced_frames = None
    if operation == "check":
        passed = result["outcome"] == "pass"
    elif operation == "explore":
        passed = result["all_passed"]
        require(type(passed) is bool, "Original exploration status is not Boolean")
    else:
        require(operation == "reduce" and type(result["one_minimal"]) is bool, "Unknown original presentation result")
        passed = result["one_minimal"]
        original_frames, reduced_frames = len(result["original_history"]), len(result["history"])
    return {"profile": "biocompiler.core.verification_workflow.presentation.v1",
        "command_exit_code": 0 if case["operation"] == "replay-verification-workflow" or passed else 1,
        "original_frames": original_frames, "reduced_frames": reduced_frames}


def expected_semantic(profile, role, case, record):
    require(record == case["expected"], "Presentation oracle requires complete original record bytes")
    value = r.expected_semantic(profile, role, case, record)
    value.update(schema_version="biocompiler.core.verification_workflow_result.v2",
                 request_id=request_identity(role, case), command=case["command"],
                 presentation=expected_presentation(case))
    return value


def campaign(clients, corpus, receipt):
    from biocompiler.core_client import CoreRejected
    from biocompiler.core_workflow import WorkflowClient
    cases = corpus.cases()
    for transport in clients:
        client = WorkflowClient(transport)
        for case in cases:
            identity = request_identity(transport.role, case)
            entry = {key: case[key] for key in ("id", "phase", "origin", "operation", "limits", "command")}
            entry.update(role=transport.role, request_id=identity, authority=c.artifact(receipt, case["authority"]),
                retained=None if case["retained"] is None else c.artifact(receipt, case["retained"]),
                expected=None if case["expected"] is None else c.artifact(receipt, case["expected"]),
                source_evidence=None if case["source_evidence"] is None else c.artifact(receipt, canonical(case["source_evidence"])))
            with c.transport_only() as seen:
                try:
                    options = {"limits": case["limits"], "request_id": identity, "command": case["command"]}
                    if case["operation"] == "run-verification-workflow":
                        actual = client.run_public(case["authority"], **options)
                    else:
                        actual = client.replay_public(case["authority"], case["retained"], **options)
                except CoreRejected as error:
                    response = error.response
                    diagnostics = [{"code": d.code, "message": d.message, "path": d.path} for d in response.diagnostics]
                    require(case["error"] is not None and diagnostics == [case["error"]] and response.status == "error",
                            "Exact presentation rejection differs: " + case["id"] + "/" + case["phase"] + " " + str(diagnostics))
                    envelope = {"protocol": "biocompiler.core.v1", "request_id": response.request_id,
                        "operation": response.operation, "status": response.status, "diagnostics": diagnostics, "result": response.result,
                        "core": {"implementation": "ocaml", "version": response.version,
                                 "protocol": "biocompiler.core.v1", "executable": response.executable}}
                    entry.update(status="error", diagnostic=diagnostics[0], record=None, semantic_receipt=None)
                else:
                    require(case["error"] is None and actual.record_json == case["expected"],
                            "Complete original presentation output differs: " + case["id"] + "/" + case["phase"])
                    require(canonical(actual.receipt) == canonical(expected_semantic(corpus.profile, transport.role, case, case["expected"])),
                            "Native presentation differs from independent original record oracle")
                    envelope = c.full_response(actual)
                    entry.update(status="ok", diagnostic=None, record=c.artifact(receipt, actual.record_json),
                        semantic_receipt=c.artifact(receipt, canonical(actual.receipt)))
                entry["envelope"] = c.artifact(receipt, canonical(envelope))
            require(seen == TRANSPORT_MODULES, "Required strict presentation transport path was not exercised")
            entry["guard_modules"] = sorted(seen)
            receipt["checks"].append(entry)
    require(Counter(item["role"] for item in receipt["checks"]) == {"core": CHECKS_PER_ROLE, "verify": CHECKS_PER_ROLE},
            "Complete two-role presentation campaign was narrowed")


def validate_checks(receipt, golden, artifacts):
    expected = golden.expected()
    checks = receipt.get("checks")
    require(type(checks) is list and len(checks) == len(expected) and
            type(receipt.get("completed_checks")) is int and receipt["completed_checks"] == len(expected),
            "Incomplete exact workflow occurrence matrix")
    seen = {}
    fields = {"role", "id", "phase", "origin", "operation", "limits", "request_id", "authority", "retained",
              "expected", "source_evidence", "command", "status", "diagnostic", "record", "semantic_receipt", "envelope", "guard_modules"}
    for check in checks:
        require(type(check) is dict and set(check) == fields, "Incomplete workflow occurrence receipt")
        key = check["role"], check["id"], check["phase"], check["operation"]
        require(key in expected and key not in seen, "Unknown, duplicate or stale workflow occurrence")
        role = key[0]
        case = expected[key]
        require(check["origin"] == case["origin"] and check["command"] == case["command"] and canonical(check["limits"]) == canonical(case["limits"]) and
                check["request_id"] == request_identity(role, case), "Workflow occurrence authority or request identity changed")
        require(check["guard_modules"] == sorted(TRANSPORT_MODULES), "Missing or weakened executed no-fallback guard")
        for name in ("authority", "retained", "expected", "source_evidence"):
            reference = case[name]
            if name == "source_evidence" and reference is not None:
                reference = canonical(reference)
            if reference is None:
                require(check[name] is None, "Unexpected supplied workflow evidence: " + name)
            else:
                require(artifacts.raw(check[name]) == reference, "Complete original occurrence evidence differs: " + name)
        envelope = artifacts.json(check["envelope"])
        expected_envelope = {
            "protocol": "biocompiler.core.v1", "request_id": request_identity(role, case),
            "operation": case["operation"],
            "core": {"implementation": "ocaml", "version": "0.1.0", "protocol": "biocompiler.core.v1", "executable": role},
        }
        if case["error"] is not None:
            require(check["status"] == "error" and canonical(check["diagnostic"]) == canonical(case["error"]) and
                    check["record"] is None and check["semantic_receipt"] is None,
                    "Exact original workflow rejection changed or retained acceptance")
            expected_envelope.update(status="error", result=None, diagnostics=[case["error"]])
        else:
            require(check["status"] == "ok" and check["diagnostic"] is None,
                    "Successful original workflow result was rejected")
            record = artifacts.raw(check["record"])
            require(record == case["expected"] and canonical(decode(record)) == record,
                    "Complete workflow result differs from original oracle")
            semantic = artifacts.json(check["semantic_receipt"])
            expected_receipt = expected_semantic(golden.profile, role, case, record)
            require(canonical(semantic) == canonical(expected_receipt),
                    "Complete workflow semantic authority, identity, profile or resources differ")
            result = {"schema_version": "biocompiler.core.artifact_response.v1",
                      "transport": "biocompiler.core.artifact_transport.v1",
                      "authority": descriptor(case["authority"]), "retained_record": descriptor(case["retained"]),
                      "artifact": descriptor(record), "result": expected_receipt}
            expected_envelope.update(status="ok", result=result, diagnostics=[])
        require(canonical(envelope) == canonical(expected_envelope),
                "Complete native protocol envelope, diagnostics or transport bindings differ")
        seen[key] = check
    require(artifacts.used == set(artifacts.declared), "Unreferenced complete workflow artifact")
    return [seen[key] for key in sorted(seen)]



def compare(root, native_root, *, revision, source_revision, run_id):
    require(type(revision) is str and re.fullmatch(r"[0-9a-f]{40}", revision) and
            type(source_revision) is str and re.fullmatch(r"[0-9a-f]{40}", source_revision) and
            type(run_id) is str and bool(run_id), "Invalid current workflow authority")
    root, native_root = Path(root), Path(native_root)
    require(root.is_dir() and not root.is_symlink() and native_root.is_dir() and not native_root.is_symlink(),
            "Unsafe workflow evidence roots")
    names = {"realization-" + target + "-py" + python for target in PLATFORMS for python in PYTHONS}
    require({path.name for path in root.iterdir() if path.name.startswith("realization-")} == names,
            "Missing or extra four-way workflow matrix slot")
    golden = Golden()
    transport_sources = source_pins("src/" + module.replace(".", "/") + ".py" for module in sorted(TRANSPORT_MODULES))
    campaign_sources = source_pins(SOURCES)
    receipts, natives = {}, {}
    reference = None
    for target, (system, machine) in PLATFORMS.items():
        native_directory = native_root / target
        require(native_directory.is_dir() and not native_directory.is_symlink(), "Unsafe native platform directory")
        native = verify_binaries(native_directory, revision, target)
        natives[target] = native
        for python in PYTHONS:
            name = "realization-" + target + "-py" + python
            directory = root / name
            require(directory.is_dir() and not directory.is_symlink(), "Unsafe workflow matrix directory")
            inputs, inputs_pin = read(directory / "native-inputs.json", CONTROL_BYTES)
            require(canonical({key: inputs.get(key) for key in native}) == canonical(native) and
                    inputs.get("run_id") == run_id and inputs.get("source_revision") == source_revision and
                    type(inputs.get("python_version")) is str and inputs["python_version"].startswith(python + "."),
                    "Stale or mixed same-run native-input receipt")
            receipt, receipt_pin = read(directory / RECEIPT_FILE)
            require(receipt.get("schema_version") == SCHEMA and
                    receipt.get("status") == "success" and
                    receipt.get("scope") == SCOPE and
                    receipt.get("revision") == revision and receipt.get("source_revision") == source_revision and
                    receipt.get("run_id") == run_id and receipt.get("python_version") == inputs["python_version"] and
                    receipt.get("system") == system and receipt.get("machine") == machine and
                    receipt.get("native_platform") == target and
                    receipt.get("corpus_pin") == CORPUS_PIN and receipt.get("supplemental_pin") == SUPPLEMENTAL_PIN and
                    receipt.get("profile_pin") == PROFILE_PIN,
                    "Stale, wrong-platform, incomplete or mixed workflow receipt")
            require(type(receipt.get("package_path")) is str and Path(receipt["package_path"]).is_absolute(),
                    "Missing installed workflow package provenance")
            require(canonical(receipt.get("native_inputs")) == canonical(native),
                    "Workflow selected binaries differ from complete same-revision downloaded bytes")
            require(canonical(receipt.get("transport_sources")) == canonical(transport_sources) and
                    canonical(receipt.get("campaign_sources")) == canonical(campaign_sources),
                    "Installed transport or campaign source differs from tested revision")
            require(receipt.get("artifact_directory") == ARTIFACT_DIRECTORY, "Unsafe workflow sibling artifact path")
            artifacts = Artifacts(directory / ARTIFACT_DIRECTORY, receipt.get("artifacts"))
            checks = validate_checks(receipt, golden, artifacts)
            # Every identity in this cross-platform content census was rehashed
            # from the complete bytes above, and all referenced contents were
            # independently compared with their exact original/profile oracle.
            complete = canonical({"checks": checks, "artifacts": artifacts.verified})
            if reference is None:
                reference = complete
            else:
                require(complete == reference, "Complete four-way workflow bytes or occurrence results differ")
            receipts[name] = {"native_inputs": inputs_pin, "workflow": receipt_pin}
    require(len(receipts) == 4 and reference is not None, "Incomplete four-way workflow matrix")
    return {"schema_version": "biocompiler.workflow_presentation_reproducibility.v1", "status": "success",
            "revision": revision, "source_revision": source_revision, "run_id": run_id,
            "corpus_pin": CORPUS_PIN, "capture_pin": CAPTURE_PIN, "supplemental_pin": SUPPLEMENTAL_PIN,
            "profile_pin": PROFILE_PIN, "receipts": receipts, "native_inputs": natives,
            "complete_results_sha256": hashlib.sha256(reference).hexdigest(),
            "checks_per_role": len(golden.cases), "completed_checks_per_variant": len(golden.expected())}



def campaign_main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", required=True, type=Path)
    parser.add_argument("--verify", required=True, type=Path)
    parser.add_argument("--core-sha256", required=True)
    parser.add_argument("--verify-sha256", required=True)
    parser.add_argument("--native-root", required=True, type=Path)
    parser.add_argument("--platform", required=True, choices=("linux-x86_64", "macos-arm64"))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if __package__:
        from .check_realization_binaries import verify, PLATFORMS
    else:
        from check_realization_binaries import verify, PLATFORMS
    import biocompiler
    from biocompiler.core_client import CoreClient
    import biocompiler.core_artifacts
    import biocompiler.core_workflow
    started = time.monotonic()
    directory = args.output.with_name(ARTIFACT_DIRECTORY)
    directory.mkdir(parents=True, exist_ok=True)
    require(directory.is_dir() and not directory.is_symlink(), "Unsafe workflow artifact directory")
    receipt = {"schema_version": SCHEMA, "status": "running", "scope": SCOPE,
        "corpus_pin": CORPUS_PIN, "supplemental_pin": SUPPLEMENTAL_PIN, "profile_pin": PROFILE_PIN,
        "revision": os.environ.get("GITHUB_SHA"), "source_revision": os.environ.get("GITHUB_HEAD_SHA", os.environ.get("GITHUB_SHA")),
        "run_id": os.environ.get("GITHUB_RUN_ID"), "system": platform.system(), "machine": platform.machine(),
        "python_version": platform.python_version(), "native_platform": args.platform,
        "package_path": str(Path(biocompiler.__file__).resolve()), "checks": [], "artifacts": {},
        "artifact_directory": directory.name, "_artifact_directory": str(directory)}
    code = 1
    try:
        require(not Path.cwd().resolve().is_relative_to(ROOT), "Run native workflow campaign outside checkout")
        require(receipt["run_id"] is not None and receipt["source_revision"] is not None,
                "Same-run hosted source metadata required")
        require((platform.system(), platform.machine()) == PLATFORMS[args.platform], "Host/native platform mismatch")
        for name, module in tuple(sys.modules.items()):
            if name == "biocompiler" or name.startswith("biocompiler."):
                origin = getattr(module, "__file__", None)
                require(origin is None or not Path(origin).resolve().is_relative_to(ROOT), "Source-tree product module loaded: " + name)
        native = verify(args.native_root, receipt["revision"], args.platform)
        receipt["native_inputs"] = native
        pins = {"core": args.core_sha256, "verify": args.verify_sha256}
        clients = []
        for role, path in (("core", args.core), ("verify", args.verify)):
            expected = native_executable(args.native_root, role)
            require(path.is_absolute() and path.resolve() == expected.resolve() and not path.is_symlink()
                    and os.access(path, os.X_OK), "Unbound or nonexecutable installed native binary")
            require(pins[role] == native["sha256"][expected.name], "Explicit release pin differs from same-run native manifest")
            clients.append(CoreClient(path, role=role, expected_sha256=pins[role], timeout_seconds=300))
        receipt["transport_sources"] = {}
        for name in sorted(TRANSPORT_MODULES):
            path = Path(sys.modules[name].__file__)
            pin = c.sha(path.read_bytes())
            relative = "src/" + name.replace(".", "/") + ".py"
            require(pin == c.sha((ROOT / relative).read_bytes()), "Installed workflow transport differs from tested source")
            receipt["transport_sources"][relative] = pin
        receipt["campaign_sources"] = {relative: c.sha((ROOT / relative).read_bytes()) for relative in
            SOURCES}
        corpus = Corpus()
        require(digest(bioc := biocompiler.core_workflow.presentation_capability_profile()) == PROFILE_PIN and bioc == corpus.profile,
                "Installed workflow profile differs from independent oracle")
        campaign(clients, corpus, receipt)
        receipt["status"], code = "success", 0
    except Exception as error:
        receipt["status"] = "failure"
        receipt["error"] = type(error).__name__ + ": " + str(error)
        print(receipt["error"], file=sys.stderr)
    receipt["completed_checks"] = len(receipt["checks"])
    receipt["duration_seconds"] = round(time.monotonic() - started, 6)
    del receipt["_artifact_directory"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(receipt) + b"\n")
    print("Native workflow presentation campaign:", receipt["status"], receipt["completed_checks"], "complete observations")
    return code


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if "--compare" not in arguments:
        return campaign_main(arguments)
    parser = argparse.ArgumentParser(description="Compare every complete v2 presentation occurrence across all four runtimes")
    parser.add_argument("--compare", action="store_true", required=True)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--native-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(arguments)
    result = compare(args.root, args.native_root, revision=os.environ.get("GITHUB_SHA"),
        source_revision=os.environ.get("GITHUB_HEAD_SHA", os.environ.get("GITHUB_SHA")), run_id=os.environ.get("GITHUB_RUN_ID"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(result) + b"\n")
    print("Complete v2 presentation records, commands, rejections and resources match across four required variants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
