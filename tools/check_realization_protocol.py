"""Complete installed realization protocol campaign from pinned original calls.

Fixture loading is standard-library transport work. Every captured occurrence is
executed, including nested calls, original errors and actual-child observations.
The Python reference implementation is used only by the separate freeze/tests.
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
import platform
import subprocess
import sys
import time

import biocompiler
from biocompiler.core_client import CoreClient, CoreRejected, decode_json, encode_json
from biocompiler.core_realization import RealizationClient

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/conformance/realization-protocol-v1.json"
CORPUS_PIN = "9261f5fc259e6d79e56df6bf9cc5ee528e795aa5dd2ef8bc4dcc7b63dfd4d4bf"
BASE = ROOT / "tests/conformance/synthetic-acceptance-v1.json"
BASE_PIN = "d32009a03f0af00de4da60f0244c210ba15b9ff89e828ea56c82b5f9e4a73331"
BASE_CAPTURE_PIN = "9b17701d25eb2dfe1ecef87eccc46dc506475ae34d90fcce8bcda88b6e058f29"
PROFILES_PATH = ROOT / "docs/migration-realization-protocol-profiles.json"
APIS = {
    "realization_dependencies": ("realization", "realization-dependencies"),
    "check_realization": ("realization", "verify-realization"),
    "check_synthetic_candidate": ("synthetic_candidate", "verify-synthetic-candidate"),
    "check_component_behavior": ("component_behavior", "verify-component-behavior"),
    "check_component_assembly": ("component_assembly", "verify-component-assembly"),
}
EXPECTED_API_COUNTS = {"realization_dependencies": 1996, "check_realization": 1080,
    "check_synthetic_candidate": 906, "check_component_behavior": 85, "check_component_assembly": 52}
VERSION_CONTEXT = "tests/test_synthetic_verification_workflow.py::SyntheticVerificationWorkflowTests.test_forged_results_and_stale_tool_dependencies_fail_fresh_replay"
VERSION_MUTATIONS = {
    "tests/test_realization_checker.py::CheckArtifactTests.test_public_dependency_helper_detects_context_parameter_and_history_changes/api/5":
        ("realization_dependencies", "changed", 540),
    **{VERSION_CONTEXT + "/api/" + str(n): (api, "changed.v999", 271)
       for n, api in ((128, "check_synthetic_candidate"), (130, "realization_dependencies"),
                      (190, "check_realization"), (191, "realization_dependencies"))},
}
TRANSPORT_MODULES = frozenset(("biocompiler.core_client", "biocompiler.core_realization"))


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def canonical(value, *, ascii=False):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=ascii,
                      allow_nan=False).encode("ascii" if ascii else "utf-8")


def digest(value, *, ascii=False):
    return hashlib.sha256(canonical(value, ascii=ascii)).hexdigest()


def read_json(path, maximum=16 * 1024 * 1024):
    require(path.is_file() and path.stat().st_size <= maximum, "Missing or oversized fixture: " + str(path))
    return json.loads(path.read_bytes())


class Baseline:
    """Read the entire pinned ledger without importing a semantic Python module."""
    def __init__(self, path=BASE):
        self.path = Path(path)
        self.index = read_json(self.path)
        require(self.index["inventory_fingerprint"] == BASE_PIN and
                digest({k: v for k, v in self.index.items() if k != "inventory_fingerprint"}) == BASE_PIN,
                "Original acceptance inventory differs")
        require(self.index["original_capture_fingerprint"] == BASE_CAPTURE_PIN,
                "Original capture identity differs")
        self.metadata = {item["id"]: item for item in self.index["documents"]}
        self.cache = {}
        require(len(self.metadata) == 4910 and len(self.index["contexts"]) == 381,
                "Original complete source/document census differs")

    def document(self, identity):
        metadata = self.metadata[identity]
        if identity not in self.cache:
            path = self.path.with_suffix("") / (identity + ".json")
            require(path.stat().st_size == metadata["bytes"], "Original document size differs")
            value = read_json(path, 32 * 1024 * 1024)
            require(digest(value) == identity, "Original document identity differs")
            self.cache[identity] = value
        # Recheck cached data as callers can inspect the reader in integrity tests.
        require(digest(self.cache[identity]) == identity, "Cached original document identity differs")
        return deepcopy(self.cache[identity])

    def occurrences(self):
        for context in self.index["contexts"]:
            rows = self.document(context["ledger"])["observations"]
            require(len(rows) == context["api_calls"] and context["assertion_status"] == "passed",
                    "Original assertion/ledger census differs")
            for ordinal, call in enumerate(rows):
                if call["api"] in APIS:
                    yield context, ordinal, call


class Corpus:
    def __init__(self, path=CORPUS, *, baseline=None):
        self.path = Path(path)
        self.index = read_json(self.path)
        require(self.index["inventory_fingerprint"] == CORPUS_PIN and
                digest({k: v for k, v in self.index.items() if k != "inventory_fingerprint"}) == CORPUS_PIN,
                "Realization protocol inventory differs from reviewed full campaign")
        self.baseline = baseline or Baseline()
        require(self.index["baseline"]["inventory_fingerprint"] == BASE_PIN and
                self.index["baseline"]["original_capture_fingerprint"] == BASE_CAPTURE_PIN,
                "Protocol source lineage differs")
        self.metadata = {entry["id"]: entry for entry in self.index["documents"]}
        self.cache = {}
        require({p.name for p in self.path.with_suffix("").iterdir()} ==
                {identity + ".json" for identity in self.metadata}, "Extra or missing protocol documents")
        self.profiles = self.document(self.index["profiles"]) ["capability_profiles"]
        self.cases = self.index["cases"]
        self.extra = self.index["additional_cases"]
        require(Counter(c["api"] for c in self.cases) == EXPECTED_API_COUNTS,
                "Original 4119 direct observations were narrowed")
        require(sum(c["result"] is not None and c["api"] != "realization_dependencies"
                    for c in self.cases) == 2112, "Original 2112 replay observations were narrowed")

    def document(self, identity):
        if identity.startswith("baseline:"):
            return self.baseline.document(identity.removeprefix("baseline:"))
        metadata = self.metadata[identity]
        if identity not in self.cache:
            path = self.path.with_suffix("") / (identity + ".json")
            require(path.stat().st_size == metadata["bytes"], "Protocol document size differs")
            self.cache[identity] = read_json(path, 32 * 1024 * 1024)
        require(digest(self.cache[identity]) == identity, "Protocol document identity differs")
        return deepcopy(self.cache[identity])

    def authority(self, case):
        value = self.document(case["input"])
        if isinstance(value, str):
            value = json.loads(value)
        if case.get("version_mutation"):
            value = value["authority"]
        return value

    def payload(self, case, *, replay=False, current=False):
        authority = self.authority(case)
        if "request" in authority:
            authority["expected_request"] = authority.pop("request")
        family, operation = APIS[case["api"]]
        payload = {"profile": self.profiles[family]["profile"], "limits": None, **authority}
        if replay:
            require(operation.startswith("verify-"), "Dependencies have no replay operation")
            operation = "replay-" + operation.removeprefix("verify-")
            payload["assessment"] = self.document(case["result"] if current else case["historical_result"])
        return operation, payload


@contextmanager
def transport_only():
    previous = sys.getprofile()
    seen = set()
    def guard(frame, event, _argument):
        if event == "call":
            module = frame.f_globals.get("__name__", "")
            if module.startswith("biocompiler"):
                require(module in TRANSPORT_MODULES,
                        "Python semantic execution is forbidden: " + module + "." + frame.f_code.co_qualname)
                seen.add(module)
    sys.setprofile(guard)
    try:
        yield seen
    finally:
        sys.setprofile(previous)


def require_installed():
    require(not Path.cwd().resolve().is_relative_to(ROOT), "Run installed realization campaign outside the checkout")
    require(not Path(biocompiler.__file__).resolve().is_relative_to(ROOT), "Installed package required")
    for name, module in tuple(sys.modules.items()):
        origin = getattr(module, "__file__", None)
        if name == "biocompiler" or name.startswith("biocompiler."):
            require(origin is None or not Path(origin).resolve().is_relative_to(ROOT),
                    "Source-tree package module loaded: " + name)


def check_result(result, operation, payload, expected, corpus, identities):
    family = next(f for f, p in corpus.profiles.items() if operation in p["operations"])
    profile = corpus.profiles[family]
    dependency = operation == "realization-dependencies"
    kind = "dependencies" if dependency else "assessment"
    fields = corpus.document(corpus.index["profiles"])["dependency_result_fields" if dependency else "result_fields"]
    require(set(result) == set(fields), "Result envelope fields differ: " + operation)
    require(canonical(result[kind]) == canonical(expected), "Complete original record differs: " + operation)
    require(result[kind + "_fingerprint"] == digest(expected,
            ascii=profile["dependency_encoding" if dependency else "assessment_encoding"] == "python-json-ascii-v1"),
            "Report-family canonical identity differs")
    require(result["supplied_authority_fingerprint"] == digest({k: v for k, v in payload.items() if k != "assessment"}),
            "Complete raw supplied authority identity differs")
    require(set(result["authority_identities"]) == set(profile["authority_identity_fields"]),
            "Authority identity shape differs")
    require(result["authority_identities"] == identities, "Complete original typed authority identities differ")
    for key in ("profile", "implementation", "service_implementation", "validation_scope", "claim_scope"):
        source = "dependency_" + key if dependency and key in ("validation_scope", "claim_scope") else key
        require(result[key] == profile[source], "Result negotiated field differs: " + key)
    require(result["schema_version"] == profile["result_schemas"][operation], "Result schema differs")
    require(result["resource_profile"] == profile["resources"]["protocol"]["profile"], "Protocol resource identity differs")
    if payload["limits"] is None:
        require(result["resources"] == profile["resources"], "Default complete nested resources differ")
    return {"authority": result["supplied_authority_fingerprint"], kind: result[kind + "_fingerprint"],
            "outcome": None if dependency else expected["outcome"]}


def invoke(transport, operation, payload):
    # Import metadata before the guard; all operation work stays inside it.
    return RealizationClient(transport).call(operation, payload)


def raw_result(value):
    # Client API returns a complete wrapper, never an imported semantic record.
    return value.envelope


def rejected(transport, operation, payload, code, *, message=None):
    try:
        transport.call(operation, payload)
    except CoreRejected as error:
        require(error.response.result is None and [d.code for d in error.response.diagnostics] == [code],
                "Wrong fail-closed rejection: " + operation + "/" + code)
        if message is not None:
            require(error.response.diagnostics[0].message == message, "Original complete error message differs")
        return {"status": error.response.status, "result": None,
                "diagnostics": [{"code": d.code, "message": d.message, "path": d.path}
                                for d in error.response.diagnostics]}
    else:
        raise AssertionError("Invalid authority accepted: " + operation + "/" + code)


def artifact(receipt, value):
    """Publish actual complete records once; every occurrence points to them."""
    identity = digest(value)
    encoded = canonical(value) + b"\n"
    directory = receipt.get("_artifact_directory")
    if directory is not None:
        path = Path(directory) / (identity + ".json")
        if path.exists():
            require(path.read_bytes() == encoded, "Conflicting actual report artifact")
        else:
            path.write_bytes(encoded)
    receipt.setdefault("artifacts", {})[identity] = {"bytes": len(encoded),
        "path": identity + ".json", "canonical_sha256": identity}
    return identity


def campaign(clients, corpus, receipt):
    for transport in clients:
        for case in [*corpus.cases, *corpus.extra]:
            operation, payload = corpus.payload(case)
            with transport_only():
                if case["result"] is None:
                    actual = rejected(transport, operation, payload, case["error"]["code"], message=case["error"]["message"])
                    detail = {"error": case["error"]["code"], "artifact": artifact(receipt, actual)}
                else:
                    actual = raw_result(invoke(transport, operation, payload))
                    detail = check_result(actual, operation, payload, corpus.document(case["result"]), corpus, case["authority_identities"])
                    detail["artifact"] = artifact(receipt, actual)
            receipt["checks"].append({"role": transport.role, "id": case["id"], "operation": operation, **detail})
            if case["result"] is not None and operation.startswith("verify-"):
                replay, replay_payload = corpus.payload(case, replay=True)
                with transport_only():
                    if case.get("version_mutation"):
                        actual = rejected(transport, replay, replay_payload, "realization_assessment_mismatch")
                        detail = {"error": "realization_assessment_mismatch", "artifact": artifact(receipt, actual)}
                    else:
                        actual = raw_result(invoke(transport, replay, replay_payload))
                        detail = check_result(actual, replay, replay_payload, corpus.document(case["result"]), corpus,
                                              case["authority_identities"])
                        detail["artifact"] = artifact(receipt, actual)
                receipt["checks"].append({"role": transport.role, "id": case["id"], "operation": replay, **detail})
                if case.get("version_mutation"):
                    replay, replay_payload = corpus.payload(case, replay=True, current=True)
                    with transport_only():
                        actual = raw_result(invoke(transport, replay, replay_payload))
                        detail = check_result(actual, replay, replay_payload, corpus.document(case["result"]), corpus,
                                              case["authority_identities"])
                        detail["artifact"] = artifact(receipt, actual)
                    receipt["checks"].append({"role": transport.role, "id": case["id"] + "/current-policy", "operation": replay, **detail})
        boundary_campaign(transport, corpus, receipt)


def boundary_campaign(transport, corpus, receipt):
    for entry in corpus.index["boundary_cases"]:
        case = next(c for c in [*corpus.cases, *corpus.extra] if c["id"] == entry["source"])
        operation, payload = corpus.payload(case, replay=entry["replay"], current=True)
        for edit in entry["edits"]:
            parent = payload
            for key in edit["path"][:-1]:
                parent = parent[key]
            if edit["op"] == "remove":
                del parent[edit["path"][-1]]
            else:
                parent[edit["path"][-1]] = deepcopy(edit["value"])
        with transport_only():
            actual = rejected(transport, operation, payload, entry["code"])
        receipt["checks"].append({"role": transport.role, "id": entry["id"], "operation": operation,
                                 "error": entry["code"], "artifact": artifact(receipt, actual)})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", required=True, type=Path)
    parser.add_argument("--verify", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    return run_main(args, campaign, "biocompiler.realization_protocol_conformance.v1")


def run_main(args, execute, schema):
    started = time.monotonic()
    receipt = {"schema_version": schema, "status": "running", "checks": [],
        "platform": platform.platform(), "system": platform.system(), "machine": platform.machine(),
        "python_version": platform.python_version(),
        "corpus_pin": CORPUS_PIN, "baseline_pin": BASE_PIN, "package_path": str(Path(biocompiler.__file__).resolve()),
        "executables": {}, "scope": "direct_operations_only_no_workflow_archive_or_export_migration"}
    directory = args.output.with_suffix("").with_name(args.output.stem + "-reports")
    directory.mkdir(parents=True, exist_ok=True)
    receipt["_artifact_directory"] = str(directory)
    try:
        require_installed()
        revision = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
        require(os.environ.get("GITHUB_SHA", revision) == revision, "Workflow revision differs")
        receipt.update(revision=revision, source_revision=os.environ.get("GITHUB_HEAD_SHA", revision),
                       run_id=os.environ.get("GITHUB_RUN_ID", "local"))
        clients = []
        for role, binary in (("core", args.core), ("verify", args.verify)):
            require(binary.is_absolute() and binary.is_file() and os.access(binary, os.X_OK), "Missing explicit native executable")
            pin = hashlib.sha256(binary.read_bytes()).hexdigest()
            receipt["executables"][role] = {"path": str(binary), "sha256": pin}
            clients.append(CoreClient(binary, role=role, timeout_seconds=60, expected_sha256=pin))
        corpus = Corpus()
        execute(clients, corpus, receipt)
        expected = corpus.index["coverage"]["sdk_checks_per_role" if "routing" in schema else "protocol_checks_per_role"]
        require(Counter(x["role"] for x in receipt["checks"]) == {"core": expected, "verify": expected},
                "Complete executable-role/call matrix differs")
        receipt["status"], code = "success", 0
    except Exception as error:
        receipt["status"], code = "failure", 1
        receipt["error"] = type(error).__name__ + ": " + str(error)
        print(receipt["error"], file=sys.stderr)
    receipt["completed_checks"] = len(receipt["checks"])
    receipt["artifact_directory"] = directory.name
    del receipt["_artifact_directory"]
    receipt["duration_seconds"] = round(time.monotonic() - started, 6)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(f"Realization campaign: {receipt['status']}; {receipt['completed_checks']} completed checks")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
