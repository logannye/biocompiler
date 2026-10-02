"""Installed whole-workflow campaign preserving every frozen public occurrence.

Importing this module reads no product modules and executes no native program.
Corpus projection is shared with the independent artifact comparator. Production
imports happen only when executing the explicitly selected installed binaries.
"""
from __future__ import annotations

import argparse
import builtins
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/conformance/realization-workflow-v1.json"
CORPUS_PIN = "2f5e7636977f559e046776c1bb92bebf67c8f0e733ca463927f8d3a1aee3d77b"
CAPTURE_PIN = "5e7b74bd456a554dd3b1e3661f25ec42ff00a719b114d19cdd474d9c014b1015"
SUPPLEMENT = ROOT / "tests/conformance/verification-workflow-service-v1.json"
SUPPLEMENT_PIN = "b396f27f2acfb7bb2b5eee4f57ae69eef5028d6ee34d9c7288761bc322a93cdc"
PROFILE_PIN = "6961059d7eb2dc55cef1ede11b09faf37043e9c7cb040da90f6a09f95fa38643"
SCHEMA = "biocompiler.native_workflow_conformance.v1"
SCOPE = "complete_native_workflow_sdk_run_replay_only_public_cli_and_pipeline_unmigrated"
OPERATIONS = {"run_synthetic_verification": "run-verification-workflow",
              "replay_synthetic_verification": "replay-verification-workflow"}
TRANSPORT_MODULES = frozenset(("biocompiler.core_client", "biocompiler.core_artifacts", "biocompiler.core_workflow"))
LIMIT_FIELDS = ("max_work", "max_monitor_items", "max_request_bytes", "max_report_bytes", "max_report_nodes")
VERSION_CONTEXT = "tests/test_synthetic_verification_workflow.py::SyntheticVerificationWorkflowTests.test_forged_results_and_stale_tool_dependencies_fail_fresh_replay"
NOMINAL_ID = "tests/test_synthetic_verification_workflow.py::SyntheticVerificationWorkflowTests.test_complete_independent_authority_binds_history_horizon_mode_and_model/api/243"
CHECKER_VERSION = "biocompiler.realization_checker.v0.3"
CHECKS_PER_ROLE = 112


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    return sha(canonical(value))


def read(path, maximum=64 * 1024 * 1024):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= maximum,
            "Missing, linked, empty or oversized workflow fixture: " + str(path))
    payload = path.read_bytes()
    value = json.loads(payload)
    require(payload == canonical(value) + b"\n", "Noncanonical complete workflow fixture")
    return value


def pinned(path, pin):
    value = read(path)
    require(value["inventory_fingerprint"] == pin and
            digest({key: item for key, item in value.items() if key != "inventory_fingerprint"}) == pin,
            "Pinned complete workflow inventory changed")
    return value


def request_id(role, case):
    return "workflow-" + sha((role + "|" + case["id"] + "|" + case["phase"]).encode())[:32]


def expected_resources(profile, limits):
    resources = deepcopy(profile["resources"])
    if limits is None:
        return resources
    require(set(limits) == set(LIMIT_FIELDS), "Incomplete workflow reduction")
    resources["workflow"].update(limits)
    resources["workflow"]["max_evaluation_work"] = min(50_000_000, limits["max_work"])
    def reduced(value):
        if isinstance(value, dict):
            return {key: min(item, limits[key]) if key in limits else reduced(item) for key, item in value.items()}
        if isinstance(value, list):
            return [reduced(item) for item in value]
        return value
    resources["realization"] = reduced(resources["realization"])
    resources["synthetic"] = reduced(resources["synthetic"])
    return resources


class Corpus:
    """Complete deterministic projection; no sampling or occurrence deduplication."""

    def __init__(self, path=CORPUS, supplement=SUPPLEMENT):
        self.path = Path(path)
        self.index = pinned(self.path, CORPUS_PIN)
        self.supplement = pinned(supplement, SUPPLEMENT_PIN)
        require(self.index["original_capture_fingerprint"] == CAPTURE_PIN, "Original capture changed")
        require(self.index["coverage"]["original_methods"] == 376 and len(self.index["contexts"]) == 385,
                "Original unchanged cohort was narrowed")
        self.metadata = {item["id"]: item for item in self.index["documents"]}
        require(len(self.metadata) == 11522, "Original complete document inventory changed")
        self.profile = self.supplement["profile"]
        require(digest(self.profile) == PROFILE_PIN == self.supplement["profile_sha256"], "Workflow profile changed")
        require(self.supplement["provenance"]["original_inventory_fingerprint"] == CORPUS_PIN and
                self.supplement["provenance"]["original_source_files"] == self.index["source_files"],
                "Supplemental original-source lineage changed")
        require(len(self.supplement["cases"]) == 9 and digest(self.supplement["cases"]) ==
                "f8067df471f33d826f11ad568811285622fe52511c47f1aef2a0fb92ce041eba", "Nine full independent records changed")
        self.cache = {}

    def document(self, identity):
        require(re.fullmatch(r"[0-9a-f]{64}", identity) is not None and identity in self.metadata,
                "Unknown original workflow document")
        if identity not in self.cache:
            path = self.path.with_suffix("") / (identity + ".json")
            require(path.stat().st_size == self.metadata[identity]["bytes"], "Original complete document size changed")
            self.cache[identity] = read(path)
        value = self.cache[identity]
        require(digest(value) == identity, "Original complete document content changed")
        return deepcopy(value)

    def cases(self):
        result = []
        counts = Counter()
        def add(identity, phase, operation, authority, *, retained=None, expected=None, error=None,
                origin="original", evidence=None, limits=None):
            result.append({"id": identity, "phase": phase, "origin": origin, "operation": operation,
                "authority": authority if type(authority) is bytes else canonical(authority),
                "retained": retained if type(retained) is bytes or retained is None else canonical(retained),
                "expected": expected if type(expected) is bytes or expected is None else canonical(expected),
                "error": error, "limits": limits, "source_evidence": evidence})
        stale = {"code": "synthetic_verification", "message": "Verification evidence is stale, altered or unsupported by current tools.", "path": None}
        def checker(value, version):
            value = deepcopy(value)
            value["result"]["dependencies"]["checker"] = version
            return value
        for context in self.index["contexts"]:
            rows = self.document(context["ledger"])
            require(len(rows) == context["api_calls"] and context["assertion_status"] == "passed", "Original full context differs")
            for ordinal, call in enumerate(rows):
                if call["api"] not in OPERATIONS:
                    continue
                identity = context["id"] + "/api/" + str(ordinal)
                counts[call["api"], call["outcome"]] += 1
                require(call["native"]["stage"] == "workflow_kernel", "Original workflow call was reclassified")
                bound = json.loads(self.document(call["native"]["input"]))
                replay = call["api"] == "replay_synthetic_verification"
                authority = bound["expected_request" if replay else "request"]
                retained = bound.get("record") if replay else None
                expected = None
                if call["outcome"] == "returned":
                    expected = self.document(call["result"])
                    if call["result_format"] == "python_json_text": expected = json.loads(expected)
                evidence = {"context": context["id"], "ordinal": ordinal, "observation": call,
                    "source": self.index["source_locations"][call["source"]],
                    "python_types": self.document(call["python_types"]),
                    "raw_arguments": self.document(call["input"]), "bound_arguments": bound,
                    "original_result": expected}
                if identity == VERSION_CONTEXT + "/api/134":
                    require(call.get("policy_override") == {"checker_version": "changed.v999"} and
                            call["error"]["message"] == stale["message"], "Original replay mutation changed")
                    add(identity, "current-policy-counterpart", OPERATIONS[call["api"]], authority,
                        retained=retained, expected=retained, evidence=evidence)
                    add(identity, "original-stale-policy", OPERATIONS[call["api"]], authority,
                        retained=checker(retained, "changed.v999"), error=stale, evidence=evidence)
                    continue
                if identity == VERSION_CONTEXT + "/api/135":
                    require(call.get("policy_override") == {"checker_version": "changed.v999"} and
                            expected["result"]["dependencies"]["checker"] == "changed.v999", "Original run mutation changed")
                    current = checker(expected, CHECKER_VERSION)
                    add(identity, "current-policy-counterpart", OPERATIONS[call["api"]], authority, expected=current, evidence=evidence)
                    add(identity, "fresh-replay", "replay-verification-workflow", authority, retained=current, expected=current, evidence=evidence)
                    add(identity, "original-stale-policy", "replay-verification-workflow", authority, retained=expected, error=stale, evidence=evidence)
                    continue
                require("policy_override" not in call, "Unreviewed original policy override")
                error = None
                if call["outcome"] == "raised":
                    original = call["error"]
                    require(original["module"] == "biocompiler.errors" and original["type"] == "SerializationError", "New original exception family")
                    message = original["message"]
                    if identity == NOMINAL_ID:
                        require(message == "Fresh replay needs independently trusted complete operation authority." and
                                authority["schema_version"] == "biocompiler.realization_request.v0.1", "Nominal boundary changed")
                        error = {"code": "verification_workflow", "message": "Invalid fields in SyntheticVerificationRequest.", "path": "authority"}
                    elif message in (stale["message"], "Verification operation differs from independent authority."):
                        error = {"code": "synthetic_verification", "message": message, "path": None}
                    elif message == "Initial history does not exhibit the selected FAIL signature.":
                        error = {"code": "verification_exploration", "message": message, "path": None}
                    else:
                        raise AssertionError("Unreviewed original workflow exception: " + identity)
                add(identity, "original", OPERATIONS[call["api"]], authority, retained=retained, expected=expected, error=error, evidence=evidence)
                if expected is not None and not replay:
                    add(identity, "fresh-replay", "replay-verification-workflow", authority, retained=expected, expected=expected, evidence=evidence)
        require(counts == {("run_synthetic_verification", "returned"): 35, ("run_synthetic_verification", "raised"): 1,
                           ("replay_synthetic_verification", "returned"): 4, ("replay_synthetic_verification", "raised"): 12},
                "Every original 52 workflow occurrence must remain present")
        require(len(result) == 89, "Original full run/replay/current-policy projection changed")
        for item in self.supplement["cases"]:
            expected = item["expected"]
            require(digest(expected) == item["fingerprint"], "Independent complete supplemental record changed")
            for replay in (False, True):
                add("supplemental/" + item["name"], "replay" if replay else "run",
                    "replay-verification-workflow" if replay else "run-verification-workflow", expected["request"],
                    retained=expected if replay else None, expected=expected, origin="supplemental")
        base = next(item["expected"] for item in self.supplement["cases"] if item["name"] == "candidate_pass")
        reordered = deepcopy(base["request"])
        reordered["candidate"]["component_locks"].reverse()
        require(canonical(reordered) != canonical(base["request"]), "Missing normalization witness")
        add("boundary/normalized-authority", "run", "run-verification-workflow", reordered, expected=base, origin="normalization")
        altered = deepcopy(base); altered["request"] = reordered
        add("boundary/raw-retained-order", "replay", "replay-verification-workflow", base["request"], retained=altered, error=stale, origin="normalization")
        defaults = {key: self.profile["resources"]["workflow"][key] for key in LIMIT_FIELDS}
        add("boundary/work-one", "run", "run-verification-workflow", base["request"], origin="resource",
            limits={**defaults, "max_work": 1}, error={"code": "workflow_work_limit", "message":
                "Independent checker work limit exceeded under biocompiler.verification_workflow.resources.v1.", "path": None})
        add("boundary/output-one-under", "run", "run-verification-workflow", base["request"], origin="resource",
            limits={**defaults, "max_report_bytes": len(canonical(base)) - 1}, error={"code": "verification_exploration_limit",
                "message": "Verification workflow exceeds its native resource boundary.", "path": ""})
        model = deepcopy(next(item["expected"]["request"] for item in self.supplement["cases"] if item["name"] == "model_pass"))
        model["realization"]["behavior"]["name"] = "forged"
        add("boundary/authority-before-malformed-record", "replay", "replay-verification-workflow", model,
            retained=b'{"unfinished":', origin="authority_precedence", error={"code": "lowering_source_identity",
                "message": "Source semantic fingerprint and program identity match.", "path": None})
        require(len(result) == CHECKS_PER_ROLE and len({(item["id"], item["phase"]) for item in result}) == CHECKS_PER_ROLE,
                "Complete native workflow projection changed or contains duplicate occurrences")
        return result


@contextmanager
def transport_only():
    previous, imported = sys.getprofile(), builtins.__import__
    seen = set()
    def imports(name, *args, **kwargs):
        if name.startswith("biocompiler"):
            require(name in TRANSPORT_MODULES, "Python semantic import is forbidden: " + name)
        return imported(name, *args, **kwargs)
    def calls(frame, event, _argument):
        if event == "call":
            module = frame.f_globals.get("__name__", "")
            if module.startswith("biocompiler"):
                require(module in TRANSPORT_MODULES, "Python semantic execution is forbidden: " + module + "." + frame.f_code.co_qualname)
                seen.add(module)
    builtins.__import__ = imports
    sys.setprofile(calls)
    try:
        yield seen
        require(sys.getprofile() is calls and builtins.__import__ is imports,
                "Strict workflow semantic guard was replaced or disabled")
    finally:
        sys.setprofile(previous)
        builtins.__import__ = imported


def artifact(receipt, raw):
    require(type(raw) is bytes and len(raw) <= 64 * 1024 * 1024, "Invalid complete workflow artifact bytes")
    identity = sha(raw)
    path = Path(receipt["_artifact_directory"]) / (identity + ".bin")
    if path.exists():
        require(not path.is_symlink() and path.read_bytes() == raw, "Conflicting complete workflow artifact")
    else:
        with path.open("xb") as target: target.write(raw)
    receipt["artifacts"][identity] = {"path": path.name, "bytes": len(raw), "sha256": identity}
    return identity


def full_response(result):
    return {"protocol": "biocompiler.core.v1", "request_id": result.request_id,
        "operation": result.operation, "status": "ok", "diagnostics": [], "result": result.envelope,
        "core": {"implementation": "ocaml", "version": "0.1.0", "protocol": "biocompiler.core.v1", "executable": result.executable}}


def campaign(clients, corpus, receipt):
    from biocompiler.core_client import CoreRejected
    from biocompiler.core_workflow import WorkflowClient
    cases = corpus.cases()
    for transport in clients:
        client = WorkflowClient(transport)
        for case in cases:
            identity = request_id(transport.role, case)
            entry = {key: case[key] for key in ("id", "phase", "origin", "operation", "limits")}
            entry.update(role=transport.role, request_id=identity, authority=artifact(receipt, case["authority"]),
                retained=None if case["retained"] is None else artifact(receipt, case["retained"]),
                expected=None if case["expected"] is None else artifact(receipt, case["expected"]),
                source_evidence=None if case["source_evidence"] is None else artifact(receipt, canonical(case["source_evidence"])))
            with transport_only() as seen:
                try:
                    if case["operation"] == "run-verification-workflow":
                        actual = client.run(case["authority"], limits=case["limits"], request_id=identity)
                    else:
                        actual = client.replay(case["authority"], case["retained"], limits=case["limits"], request_id=identity)
                except CoreRejected as error:
                    response = error.response
                    diagnostics = [{"code": d.code, "message": d.message, "path": d.path} for d in response.diagnostics]
                    require(case["error"] is not None and diagnostics == [case["error"]] and response.status == "error",
                            "Exact native rejection differs: " + case["id"] + "/" + case["phase"] + " " + str(diagnostics))
                    envelope = {"protocol": "biocompiler.core.v1", "request_id": response.request_id,
                        "operation": response.operation, "status": response.status, "diagnostics": diagnostics, "result": response.result,
                        "core": {"implementation": "ocaml", "version": response.version,
                                 "protocol": "biocompiler.core.v1", "executable": response.executable}}
                    entry.update(status="error", diagnostic=diagnostics[0], record=None, semantic_receipt=None)
                else:
                    require(case["error"] is None and actual.record_json == case["expected"],
                            "Complete original workflow output differs: " + case["id"] + "/" + case["phase"])
                    envelope = full_response(actual)
                    entry.update(status="ok", diagnostic=None, record=artifact(receipt, actual.record_json),
                        semantic_receipt=artifact(receipt, canonical(actual.receipt)))
                entry["envelope"] = artifact(receipt, canonical(envelope))
            require(seen == TRANSPORT_MODULES, "Required strict workflow transport path was not exercised")
            entry["guard_modules"] = sorted(seen)
            receipt["checks"].append(entry)
    require(Counter(item["role"] for item in receipt["checks"]) == {"core": CHECKS_PER_ROLE, "verify": CHECKS_PER_ROLE},
            "Complete two-role workflow campaign was narrowed")


def main(argv=None):
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
    directory = args.output.with_name("workflow-artifacts")
    directory.mkdir(parents=True, exist_ok=True)
    require(directory.is_dir() and not directory.is_symlink(), "Unsafe workflow artifact directory")
    receipt = {"schema_version": SCHEMA, "status": "running", "scope": SCOPE,
        "corpus_pin": CORPUS_PIN, "supplemental_pin": SUPPLEMENT_PIN, "profile_pin": PROFILE_PIN,
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
            expected = args.native_root / ("biocompiler-" + role)
            require(path.is_absolute() and path.resolve() == expected.resolve() and not path.is_symlink()
                    and os.access(path, os.X_OK), "Unbound or nonexecutable installed native binary")
            require(pins[role] == native["sha256"][expected.name], "Explicit release pin differs from same-run native manifest")
            clients.append(CoreClient(path, role=role, expected_sha256=pins[role], timeout_seconds=300))
        receipt["transport_sources"] = {}
        for name in sorted(TRANSPORT_MODULES):
            path = Path(sys.modules[name].__file__)
            pin = sha(path.read_bytes())
            relative = "src/" + name.replace(".", "/") + ".py"
            require(pin == sha((ROOT / relative).read_bytes()), "Installed workflow transport differs from tested source")
            receipt["transport_sources"][relative] = pin
        receipt["campaign_sources"] = {relative: sha((ROOT / relative).read_bytes()) for relative in
            ("tools/check_native_workflow.py", "tests/test_native_workflow_campaign.py")}
        corpus = Corpus()
        require(digest(bioc := biocompiler.core_workflow.capability_profile()) == PROFILE_PIN and bioc == corpus.profile,
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
    print("Native workflow campaign:", receipt["status"], receipt["completed_checks"], "complete observations")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
