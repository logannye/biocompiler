"""Hosted installed architecture protocol campaign, with frozen full authorities.

The fixture reader is standard-library transport code. It never runs a Python
producer, semantic evaluator or verification function. Test deltas are resolved
before calling the core; neither executable accepts that test storage format.
"""

from __future__ import annotations

import argparse
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
from biocompiler.core_architecture import ArchitectureClient
from biocompiler.core_client import CoreClient, CoreRejected, decode_json, encode_json

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/conformance/architecture-check-v1.json"
CORPUS_PIN = "bb1e0c3de0eaa45e11513b73379d35e6fd6180cac1d19fa9cec41e13ce96d213"
INSTALLED = ("A", "B", "C", "D", "E", "F", "automatic_timing", "automatic_b", "automatic_f",
             "memory_reset", "state_reset", "production_adjustment", "activity_control")
ORIGINAL = ("base", "parameter-default", "parameter-override")
MUTATIONS = (
    "test_helper_cyclic_bootstrap_is_rejected/0",
    "test_delivered_helpers_count_toward_rna_partition_limits/0",
    "test_co_delivery_cannot_be_replaced_by_independent_delivery/0",
    "test_installed_action_cannot_hide_behind_ownership_label/0",
    "test_missing_retained_state_assignment_is_detected/0",
    "test_omitted_plan_placement_and_false_ledger_are_detected/0",
    "test_omitted_plan_placement_and_false_ledger_are_detected/1",
    "test_relabeling_source_model_does_not_prove_changed_operator/0",
)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def digest(value):
    return hashlib.sha256(encode_json(value)).hexdigest()


def _read(path, maximum):
    require(path.is_file() and path.stat().st_size <= maximum, "Missing or oversized fixture: " + path.name)
    return decode_json(path.read_bytes(), limit=maximum)


class Corpus:
    def __init__(self, path=CORPUS):
        self.path = Path(path)
        self.index = _read(self.path, 16 * 1024 * 1024)
        require(self.index["inventory_fingerprint"] == CORPUS_PIN
                and digest({k: v for k, v in self.index.items() if k != "inventory_fingerprint"}) == CORPUS_PIN,
                "Architecture fixture inventory differs from the reviewed complete campaign")
        self.metadata = {item["id"]: item for item in self.index["documents"]}
        self.cases = {item["id"]: item for item in self.index["cases"]}
        require(len(self.metadata) == 463 and len(self.cases) == 293, "Architecture fixture census differs")
        require({path.name for path in self.path.with_suffix("").iterdir()} == {key + ".json" for key in self.metadata},
                "Extra or missing architecture fixture files")
        self.stored = {}

    def document(self, identity):
        metadata = self.metadata[identity]
        raw = self.stored.get(identity)
        if raw is None:
            path = self.path.with_suffix("") / (identity + ".json")
            require(path.stat().st_size == metadata["bytes"], "Stored document byte count differs")
            raw = _read(path, 4_000_000)
            require(digest(raw) == metadata["stored_fingerprint"], "Stored document identity differs")
            self.stored[identity] = raw
        if metadata["format"] == "full":
            require(metadata["base"] is None, "Full document has a delta baseline")
            complete = deepcopy(raw)
        else:
            require(metadata["format"] == "delta" and raw["schema_version"] == "biocompiler.test_document_delta.v1",
                    "Unknown fixture encoding")
            base = metadata["base"]
            require(raw["base"] == base and self.metadata[base]["format"] == "full"
                    and self.metadata[base]["kind"] == metadata["kind"], "Delta baseline differs")
            complete = self.document(base)
            for edit in raw["edits"]:
                require(edit["op"] in ("set", "remove") and edit["path"], "Invalid fixture edit")
                parent = complete
                for key in edit["path"][:-1]:
                    parent = parent[key]
                key = edit["path"][-1]
                if edit["op"] == "remove":
                    require(type(parent) is dict and key in parent, "Invalid fixture removal")
                    del parent[key]
                else:
                    parent[key] = deepcopy(edit["value"])
        require(digest(complete) == identity, "Complete resolved fixture identity differs")
        return complete

    def selected(self):
        ids = ["installed/" + value for value in INSTALLED] + ["case_b/" + value for value in ORIGINAL]
        ids += ["test_payload_architecture_verification.PayloadArchitectureVerificationTests." + value for value in MUTATIONS]
        result = []
        for identity in ids:
            case = self.cases[identity]
            require(not case["native_diagnostic_replacements"] and not case["diagnostic_order_sites"],
                    "Standalone corpus requires exact report identity without diagnostic normalization")
            result.append((case, *(self.document(case[key]) for key in ("request", "build", "assessment"))))
        require(len(result) == 24, "Incomplete standalone fixture census")
        return result


def campaign(clients, corpus, receipt):
    selected = corpus.selected()
    for transport in clients:
        client = ArchitectureClient(transport)
        for case, request, build, expected in selected:
            checked = client.verify(expected_request=request, build=build)
            require(encode_json(checked.assessment) == encode_json(expected), "Complete report differs: " + case["id"])
            replayed = client.replay(expected_request=request, build=build, assessment=expected)
            require(replayed.assessment_fingerprint == checked.assessment_fingerprint, "Fresh replay differs: " + case["id"])
            for operation in ("verify-architecture", "replay-architecture"):
                receipt["checks"].append({"role": transport.role, "id": case["id"], "operation": operation,
                                          "request": case["request"], "build": case["build"], "assessment": case["assessment"],
                                          "outcome": checked.outcome})
        case = corpus.cases["case_b/base"]
        request, build = (corpus.document(case[key]) for key in ("request", "build"))
        for mutant in corpus.index["replay_rejections"]:
            require(mutant["source"] == "case_b/base", "Replay mutant authority changed")
            try:
                client.replay(expected_request=request, build=build, assessment=corpus.document(mutant["assessment"]))
            except CoreRejected as error:
                require(error.response.result is None and [item.code for item in error.response.diagnostics] == [mutant["expected_code"]],
                        "Wrong fresh replay rejection")
            else:
                raise AssertionError("Forged historical report authorized replay")
            receipt["checks"].append({"role": transport.role, "id": mutant["id"], "operation": "replay-architecture", "error": mutant["expected_code"]})
        for operation in ("verify-architecture", "replay-architecture"):
            payload = {"expected_request": request, "build": build}
            if operation == "replay-architecture":
                payload["assessment"] = corpus.document(case["assessment"])
            for name, malformed, code in (("missing-original-request", {k: v for k, v in payload.items() if k != "expected_request"}, "missing_field"),
                                           ("extra-authority", {**payload, "accepted": True}, "unknown_field")):
                try:
                    transport.call(operation, malformed)
                except CoreRejected as error:
                    require(error.response.result is None and [item.code for item in error.response.diagnostics] == [code],
                            "Wrong independent authority-envelope rejection")
                else:
                    raise AssertionError("Malformed authority was accepted")
                receipt["checks"].append({"role": transport.role, "id": name, "operation": operation, "error": code})
    require(len(receipt["checks"]) == 108 and {item["role"] for item in receipt["checks"]} == {"core", "verify"},
            "Missing standalone architecture protocol execution")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", required=True, type=Path)
    parser.add_argument("--verify", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    started = time.monotonic()
    receipt = {"schema_version": "biocompiler.architecture_protocol_conformance.v1", "status": "running", "checks": [],
               "platform": platform.platform(), "python_version": platform.python_version(), "corpus_pin": CORPUS_PIN,
               "package_path": str(Path(biocompiler.__file__).resolve()), "executables": {}}
    try:
        revision = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
        require(os.environ.get("GITHUB_SHA", revision) == revision, "Workflow revision differs")
        receipt.update(revision=revision, source_revision=os.environ.get("GITHUB_HEAD_SHA", revision), run_id=os.environ.get("GITHUB_RUN_ID", "local"))
        require(not Path(biocompiler.__file__).resolve().is_relative_to(ROOT), "Installed package required")
        clients = []
        for role, binary in (("core", args.core), ("verify", args.verify)):
            require(binary.is_absolute() and binary.is_file() and os.access(binary, os.X_OK), "Missing explicit native executable")
            pin = hashlib.sha256(binary.read_bytes()).hexdigest()
            receipt["executables"][role] = {"path": str(binary), "sha256": pin}
            clients.append(CoreClient(binary, role=role, timeout_seconds=60, expected_sha256=pin))
        campaign(clients, Corpus(), receipt)
        receipt["status"], code = "success", 0
    except Exception as error:
        receipt["status"], code = "failure", 1
        receipt["error"] = type(error).__name__ + ": " + str(error)
        print(receipt["error"], file=sys.stderr)
    receipt["completed_checks"] = len(receipt["checks"])
    receipt["duration_seconds"] = round(time.monotonic() - started, 6)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    print(f"Architecture protocol: {receipt['status']}; {receipt['completed_checks']} completed checks")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
