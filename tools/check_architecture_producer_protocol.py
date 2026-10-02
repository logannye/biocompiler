"""Installed OCaml architecture production and exact paired-export campaign.

Only frozen complete authorities and stdlib fixture decoding are used. No Python
producer, evaluator or checker executes; the separate verifier checks each fresh
returned candidate. Native executables must be built in the validation environment.
"""

from __future__ import annotations

import argparse
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
from biocompiler.core_architecture import ArchitectureClient
from biocompiler.core_client import CoreClient, CoreRejected, CoreUnsupported, decode_json, encode_json


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/conformance/architecture-producer-v1.json"
CORPUS_PIN = "269e64293c36d52a5ad797c5c2808e52b0072e520992ade9bfa9f5de97dff90a"
INSTALLED = ("A", "B", "C", "D", "E", "F", "automatic_timing", "automatic_b", "automatic_f",
             "memory_reset", "state_reset", "production_adjustment", "activity_control")
ORIGINAL = ("base", "parameter-default", "parameter-override")
EXPECTED_CHECKS = 62
TRANSPORT_MODULES = frozenset(("biocompiler.core_client", "biocompiler.core_architecture",
                               "biocompiler.core_architecture_producer"))


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def digest(value):
    return hashlib.sha256(encode_json(value)).hexdigest()


def _read(path, maximum):
    require(path.is_file() and path.stat().st_size <= maximum, "Missing or oversized fixture: " + path.name)
    return decode_json(path.read_bytes(), limit=maximum)


class Corpus:
    """Resolve only the pinned one-level test-storage format, never domain logic."""

    def __init__(self, path=CORPUS):
        self.path = Path(path)
        self.index = _read(self.path, 16 * 1024 * 1024)
        require(self.index["inventory_fingerprint"] == CORPUS_PIN
                and digest({k: v for k, v in self.index.items() if k != "inventory_fingerprint"}) == CORPUS_PIN,
                "Producer fixture inventory differs from the reviewed complete campaign")
        self.metadata = {item["id"]: item for item in self.index["documents"]}
        self.cases = {item["id"]: item for item in self.index["cases"]}
        require(len(self.metadata) == 166 and len(self.cases) == 193, "Producer fixture census differs")
        require({path.name for path in self.path.with_suffix("").iterdir()} == {key + ".json" for key in self.metadata},
                "Extra or missing producer fixture files")
        self.stored = {}

    def document(self, identity):
        metadata = self.metadata[identity]
        raw = self.stored.get(identity)
        if raw is None:
            path = self.path.with_suffix("") / (identity + ".json")
            require(path.stat().st_size == metadata["bytes"], "Stored document byte count differs")
            raw = _read(path, 4_000_000)
            self.stored[identity] = raw
        require(digest(raw) == metadata["stored_fingerprint"], "Stored document identity differs")
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
        prefixes = ["installed/" + value for value in INSTALLED] + ["case_b/" + value for value in ORIGINAL]
        require(self.index["coverage"]["installed"] == prefixes[:13]
                and self.index["coverage"]["case_b"] == prefixes[13:]
                and self.index["coverage"]["diagnostic_exceptions"] == [], "Incomplete original producer coverage")
        selected = []
        for prefix in prefixes:
            compiled = self.cases[prefix + "/compile/0"]
            exported = self.cases[prefix + "/export/0"]
            require(compiled["operation"] == "compile" and exported["operation"] == "export"
                    and all(compiled[key] == exported[key] for key in ("request", "build")),
                    "Compile/export do not share the original complete authority")
            request, build = (self.document(compiled[key]) for key in ("request", "build"))
            require(build["status"] == "compiled", "Installed complete architecture changed status")
            selected.append((prefix, compiled, exported, request, build))
        require(len(selected) == 16, "Missing installed producer case")
        return selected


def malformed_mutation(request, build):
    """Retain the original stale-role-pin decoder rejection independently."""
    changed = deepcopy(build)
    molecule = changed["construction"]["candidate"]["bundle"]["molecules"][0]
    sequence = molecule["sequence"]
    require(sequence and set(sequence) <= set("ACGU"), "Mutation fixture must have exact RNA bases")
    molecule["sequence"] = ("A" if sequence[0] != "A" else "C") + sequence[1:]
    return "malformed-emitted-base", deepcopy(request), changed


def mutations(request, build):
    """Rehash structural pins without granting authority to the retained PASS."""
    stale = deepcopy(request)
    stale["library"]["assumptions"].append("Changed independently supplied architecture assumption.")
    _, _, changed = malformed_mutation(request, build)
    candidate = changed["construction"]["candidate"]
    molecule = candidate["bundle"]["molecules"][0]
    for role in candidate["bundle"]["role_instances"]:
        if role["subject_id"] == molecule["id"]:
            role["subject_fingerprint"] = digest(molecule)
    changed["construction"]["assessment"]["candidate_fingerprint"] = digest(candidate)
    return (("changed-original-authority", stale, deepcopy(build)),
            ("changed-emitted-base", deepcopy(request), changed))


@contextmanager
def transport_only():
    """Fail on any legacy Python authority execution, including already imported aliases."""
    previous = sys.getprofile()

    def guard(frame, event, _argument):
        if event == "call":
            module = frame.f_globals.get("__name__", "")
            if module.startswith("biocompiler") and module not in TRANSPORT_MODULES:
                raise AssertionError("Python semantic execution is forbidden in installed producer campaign: " + module)

    sys.setprofile(guard)
    try:
        yield
    finally:
        sys.setprofile(previous)


def require_installed():
    require(not Path.cwd().resolve().is_relative_to(ROOT), "Run installed producer campaign outside the checkout")
    require(not Path(biocompiler.__file__).resolve().is_relative_to(ROOT), "Installed package required")
    for name, module in tuple(sys.modules.items()):
        if name == "biocompiler" or name.startswith("biocompiler."):
            origin = getattr(module, "__file__", None)
            require(origin is None or not Path(origin).resolve().is_relative_to(ROOT), "Source-tree package module loaded: " + name)


def _rejection(transport, operation, payload, code, *, unsupported=False):
    try:
        transport.call(operation, payload)
    except CoreRejected as error:
        require(isinstance(error, CoreUnsupported) == unsupported
                and error.response.result is None
                and [item.code for item in error.response.diagnostics] == [code],
                "Wrong fail-closed producer rejection: " + operation)
    else:
        raise AssertionError("Invalid producer authority was accepted: " + operation)


def campaign(core, verify, corpus, receipt):
    from biocompiler.core_architecture_producer import ArchitectureProducerClient, PROFILE

    require(core.role == "core" and verify.role == "verify", "Both independent native roles are required")
    producer, checker = ArchitectureProducerClient(core), ArchitectureClient(verify)
    checks = receipt["checks"]
    require(not checks, "Campaign receipt must start empty")
    for transport in (core, verify):
        capabilities = transport.negotiate("verify-architecture")
        if transport.role == "core":
            require(capabilities.profiles.get("architecture_producer") == PROFILE
                    and {"compile-architecture", "export-architecture"} <= set(capabilities.operations),
                    "Core does not advertise the exact producer profile")
        else:
            require("architecture_producer" not in capabilities.profiles
                    and not {"compile-architecture", "export-architecture"} & set(capabilities.operations),
                    "Independent verifier advertised producer authority")
        checks.append({"role": transport.role, "id": "role-capabilities", "operation": "capabilities"})

    for prefix, compiled, exported, request, expected in corpus.selected():
        result = producer.compile(request=request)
        build = result.build
        require(result.status == "compiled" and result.build_fingerprint == compiled["build"]
                and encode_json(build) == encode_json(expected), "Complete build differs: " + prefix)
        require(result.verification.outcome == "pass" and result.verification.translation_complete
                and result.verification.construction_complete, "Fresh compiled architecture is not complete: " + prefix)
        checks.append({"role": "core", "id": prefix, "operation": "compile-architecture",
                       "request": compiled["request"], "build": result.build_fingerprint, "outcome": result.status})

        independent = checker.verify(expected_request=request, build=build)
        require(independent.outcome == "pass" and independent.translation_complete and independent.construction_complete
                and independent.assessment_fingerprint == result.verification.assessment_fingerprint
                and encode_json(independent.assessment) == encode_json(result.verification.assessment),
                "Separate verifier disagrees with fresh compiled candidate: " + prefix)
        checks.append({"role": "verify", "id": prefix, "operation": "verify-architecture",
                       "request": compiled["request"], "build": result.build_fingerprint,
                       "assessment": independent.assessment_fingerprint, "outcome": independent.outcome})

        pair = producer.export(expected_request=request, build=build)
        require(pair.export_fingerprint == exported["expected_fingerprint"]
                and digest(pair.export) == exported["expected_fingerprint"]
                and pair.fasta == exported["fasta"], "Complete FASTA/manifest pair differs: " + prefix)
        manifest = pair.manifest
        require(manifest["request_fingerprint"] == compiled["request"]
                and encode_json(manifest["build"]) == encode_json(expected)
                and encode_json(manifest["verification"]) == encode_json(independent.assessment)
                and pair.verification.assessment_fingerprint == independent.assessment_fingerprint,
                "Export is not bound to the exact independently checked request and candidate: " + prefix)
        checks.append({"role": "core", "id": prefix, "operation": "export-architecture",
                       "request": compiled["request"], "build": result.build_fingerprint,
                       "export": pair.export_fingerprint, "fasta_sha256": pair.fasta_sha256,
                       "manifest_sha256": pair.manifest_sha256, "assessment": independent.assessment_fingerprint})

    original = corpus.cases["installed/B/compile/0"]
    request, build = (corpus.document(original[key]) for key in ("request", "build"))
    for name, changed_request, changed_build in mutations(request, build):
        independent = checker.verify(expected_request=changed_request, build=changed_build)
        require(independent.outcome == "fail", "Mutant no longer exercises a semantic failure: " + name)
        checks.append({"role": "verify", "id": name, "operation": "verify-architecture", "outcome": independent.outcome,
                       "request": digest(changed_request), "build": digest(changed_build),
                       "assessment": independent.assessment_fingerprint})
        _rejection(core, "export-architecture", {"expected_request": changed_request, "build": changed_build},
                   "architecture_export_rejected")
        checks.append({"role": "core", "id": name, "operation": "export-architecture", "error": "architecture_export_rejected"})

    name, changed_request, changed_build = malformed_mutation(request, build)
    for transport, operation in ((verify, "verify-architecture"), (core, "export-architecture")):
        _rejection(transport, operation, {"expected_request": changed_request, "build": changed_build}, "invalid_molecule_set")
        checks.append({"role": transport.role, "id": name, "operation": operation, "error": "invalid_molecule_set"})

    for operation, payload in (("compile-architecture", {"request": request}),
                               ("export-architecture", {"expected_request": request, "build": build})):
        _rejection(verify, operation, payload, "unsupported_operation", unsupported=True)
        checks.append({"role": "verify", "id": "producer-operation-forbidden", "operation": operation, "error": "unsupported_operation"})
        authority_key = "request" if operation == "compile-architecture" else "expected_request"
        for name, malformed, code in (("missing-original-request", {k: v for k, v in payload.items() if k != authority_key}, "missing_field"),
                                       ("extra-authority", {**payload, "accepted": True}, "unknown_field")):
            _rejection(core, operation, malformed, code)
            checks.append({"role": "core", "id": name, "operation": operation, "error": code})
    require(len(checks) == EXPECTED_CHECKS
            and len({(item["role"], item["id"], item["operation"]) for item in checks}) == EXPECTED_CHECKS,
            "Missing or repeated installed producer protocol execution")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", required=True, type=Path)
    parser.add_argument("--verify", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    started = time.monotonic()
    receipt = {"schema_version": "biocompiler.architecture_producer_protocol_conformance.v1", "status": "running", "checks": [],
               "platform": platform.platform(), "python_version": platform.python_version(), "corpus_pin": CORPUS_PIN,
               "package_path": str(Path(biocompiler.__file__).resolve()), "executables": {}}
    try:
        revision = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
        require(os.environ.get("GITHUB_SHA", revision) == revision, "Workflow revision differs")
        receipt.update(revision=revision, source_revision=os.environ.get("GITHUB_HEAD_SHA", revision), run_id=os.environ.get("GITHUB_RUN_ID", "local"))
        require_installed()
        clients = []
        for role, binary in (("core", args.core), ("verify", args.verify)):
            require(binary.is_absolute() and binary.is_file() and os.access(binary, os.X_OK), "Missing explicit native executable")
            pin = hashlib.sha256(binary.read_bytes()).hexdigest()
            receipt["executables"][role] = {"path": str(binary), "sha256": pin}
            clients.append(CoreClient(binary, role=role, timeout_seconds=60, expected_sha256=pin))
        # Import only the transport module before enabling execution guards: the
        # package initializer may still import unrelated legacy profile classes.
        from biocompiler import core_architecture_producer  # noqa: F401
        with transport_only():
            campaign(*clients, Corpus(), receipt)
        receipt["python_semantics_blocked"] = True
        receipt["status"], code = "success", 0
    except Exception as error:
        receipt["status"], code = "failure", 1
        receipt["error"] = type(error).__name__ + ": " + str(error)
        print(receipt["error"], file=sys.stderr)
    receipt["completed_checks"] = len(receipt["checks"])
    receipt["duration_seconds"] = round(time.monotonic() - started, 6)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(f"Architecture producer protocol: {receipt['status']}; {receipt['completed_checks']} completed checks")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
