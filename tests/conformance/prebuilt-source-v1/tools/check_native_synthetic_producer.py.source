"""Complete installed direct-producer campaign and independent four-runtime checker.

Every original public wire-applicable occurrence is retained, including nested
calls and full errors. Private proposals and injected producers remain explicitly
native-library coverage. Loading fixtures/comparing receipts imports no product.
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
from uuid import UUID

if __package__:
    from . import check_workflow_reproducibility as r
else:
    import check_workflow_reproducibility as r

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/conformance/synthetic-producers-v1.json"
DECLARATION = ROOT / "protocol/synthetic-producer-v1.json"
CORPUS_PIN = "2ed5860ac7143fe4a540c7b648eb5773c2fc52cd9bf43afd8913c3d99616566b"
CAPTURE_PIN = "6bdc57f51626e6427aa68eac823c04de7af7484f115c91f5db9904ba859a6fe0"
PROFILE_PIN = "73d45fad612c18d7e7204027a5e2f829c1ac34a2ad3313ab65cc88f9a10909c8"
SCHEMA = "biocompiler.native_synthetic_producer_conformance.v1"
SCOPE = "direct_core_production_only_original_private_and_injected_library_coverage_no_public_pipeline_or_export_cutover"
RECEIPT_FILE, ARTIFACT_DIRECTORY = "synthetic-producer.json", "synthetic-producer-artifacts"
OPERATIONS = {"generate_synthetic": "generate-synthetic", "select_synthetic": "select-synthetic",
              "adapt_synthetic_components": "adapt-synthetic-components"}
FAMILIES = {"generate-synthetic": "synthetic_generation", "select-synthetic": "synthetic_selection",
            "adapt-synthetic-components": "synthetic_components"}
METHODS = {"generate-synthetic": "generate_document", "select-synthetic": "select_document",
           "adapt-synthetic-components": "adapt_document"}
TRANSPORT_MODULES = {"biocompiler.core_client", "biocompiler.core_synthetic_producer"}
SOURCES = ("tools/check_native_synthetic_producer.py", "tests/test_native_synthetic_producer_campaign.py",
           "tools/check_workflow_reproducibility.py", "tools/check_realization_binaries.py",
           "protocol/synthetic-producer-v1.json")
ROLES, PYTHONS, PLATFORMS = r.ROLES, r.PYTHONS, r.PLATFORMS
require, canonical, digest, decode = r.require, r.canonical, r.digest, r.decode
read, Artifacts, source_pins, verify_binaries = r.read, r.Artifacts, r.source_pins, r.verify_binaries
sha = lambda raw: hashlib.sha256(raw).hexdigest()
UNSUPPORTED = {"code": "unsupported_operation", "message":
    "This executable does not implement the requested operation; no fallback or acceptance is granted.", "path": "/operation"}


def declaration():
    value, _ = read(DECLARATION)
    require(digest(value) == PROFILE_PIN, "Independent producer declaration changed")
    return value


def request_identity(role, case):
    return "synthetic-producer-" + sha((role + "|" + case["id"]).encode())[:32]


def unsupported_detail(message, authority):
    """Recover only the original error's explicit source attachment, no semantics."""
    match = re.fullmatch(r"(.*?) \[([^\]]+)\] at (.*):([0-9]+)", message, re.DOTALL)
    if match is None:
        require(" [n" not in message and " at /__biocompiler_capture__/" not in message,
                "Unclassified original producer source attachment")
        return {"message": message, "node_id": None, "source": None, "formatted": message}
    plain, identity, file, line = match.groups()
    nodes = [node for node in authority["request"]["behavior"]["nodes"] if node["id"] == identity]
    require(len(nodes) == 1 and nodes[0]["source"]["file"] == file and
            nodes[0]["source"]["line"] == int(line), "Original error source differs from original authority")
    return {"message": plain, "node_id": identity, "source": deepcopy(nodes[0]["source"]), "formatted": message}


class Corpus:
    def __init__(self):
        self.index, _ = read(CORPUS)
        require(self.index["inventory_fingerprint"] == CORPUS_PIN and
                digest({k: v for k, v in self.index.items() if k != "inventory_fingerprint"}) == CORPUS_PIN and
                self.index["original_capture_fingerprint"] == CAPTURE_PIN, "Original producer inventory changed")
        require(len(self.index["documents"]) == 5192 and len(self.index["contexts"]) == 381 and
                self.index["coverage"]["api_calls"] == 47901 and
                self.index["coverage"]["original_methods"] == 373, "Complete original cohort was narrowed")
        self.metadata = {row["id"]: row for row in self.index["documents"]}
        require(len(self.metadata) == 5192, "Duplicate original producer document")
        self.cache = {}
        self.declaration = declaration()
        self.profiles = self.declaration
        self.cases, self.library = [], []
        census = Counter()
        for context in self.index["contexts"]:
            ledger = self.document(context["ledger"])
            rows = ledger["observations"]
            require(context["assertion_status"] == "passed" and len(rows) == context["api_calls"],
                    "Incomplete original producer context")
            for ordinal, call in enumerate(rows):
                operation = call["native"]["operation"]
                if operation not in (*OPERATIONS, "_generate_synthetic", "selection_producer_mutation"):
                    continue
                identity = context["id"] + "/api/" + str(ordinal)
                bound = decode(self.document(call["native"]["input"]).encode())
                evidence = {"context": context["id"], "ordinal": ordinal, "observation": call,
                    "source": self.index["source_locations"][call["source"]],
                    "raw_arguments": self.document(call["input"]), "bound_arguments": bound,
                    "python_types": self.document(call["python_types"]),
                    "original_result": self.document(call["result"]) if call["outcome"] == "returned" else None,
                    "properties": self.document(call["properties"]) if "properties" in call else None}
                census[operation, call["outcome"]] += 1
                if operation not in OPERATIONS:
                    self.library.append({"id": identity, "classification": "native_library_only",
                        "reason": "private_proposal" if operation == "_generate_synthetic" else "injected_producer",
                        "evidence": evidence})
                    continue
                native_operation = OPERATIONS[operation]
                profile = self.profiles[FAMILIES[native_operation]]
                payload = {**bound, "profile": profile["profile"], "limits": None}
                require(set(payload) == set(profile["payload_fields"][native_operation]),
                        "Original producer authority cannot be projected without loss")
                error, detail, expected = None, None, evidence["original_result"]
                if call["outcome"] == "raised":
                    code, original = call["native"]["expected_code"], call["error"]
                    if code == "synthetic_generator_unsupported":
                        require(original["module"] == "biocompiler.errors" and original["type"] == "UnsupportedBehaviorError",
                                "Original unsupported exception class differs")
                        detail = unsupported_detail(original["message"], bound)
                    else:
                        require(code == "synthetic_component_acceptance" and original["module"] == "biocompiler.errors"
                                and original["type"] == "SerializationError", "Unclassified original producer rejection")
                        error = {"code": code, "message": original["message"], "path": None}
                self.cases.append({"id": identity, "operation": native_operation, "authority": canonical(payload),
                    "expected": None if expected is None else canonical(expected), "error": error,
                    "generation_error": detail, "evidence": evidence})
        require(census == {("generate_synthetic", "returned"): 1062, ("generate_synthetic", "raised"): 24,
            ("select_synthetic", "returned"): 27, ("select_synthetic", "raised"): 9,
            ("adapt_synthetic_components", "returned"): 99, ("adapt_synthetic_components", "raised"): 5,
            ("_generate_synthetic", "returned"): 1119, ("_generate_synthetic", "raised"): 25,
            ("selection_producer_mutation", "returned"): 2}, "Original complete producer census differs")
        require(len(self.cases) == 1226 and len(self.library) == 1146, "Complete producer projection changed")
        self.verify_cases = []
        for operation in OPERATIONS.values():
            case = deepcopy(next(row for row in self.cases if row["operation"] == operation))
            case["id"] = "verify-role-rejection/" + operation
            self.verify_cases.append(case)

    def document(self, identity):
        require(r.pin(identity) and identity in self.metadata, "Unknown original producer document")
        if identity not in self.cache:
            raw = r.raw_file(CORPUS.with_suffix("") / (identity + ".json"))
            value = decode(raw)
            require(len(raw) == self.metadata[identity]["bytes"] and digest(value) == identity and
                    raw == canonical(value) + b"\n", "Complete original producer document differs")
            self.cache[identity] = value
        return self.cache[identity]

    def expected(self):
        return {**{("core", row["id"]): row for row in self.cases},
                **{("verify", row["id"]): row for row in self.verify_cases}}


def artifact(receipt, raw):
    require(type(raw) is bytes and 0 < len(raw) <= r.MAX_ARTIFACT_BYTES, "Invalid complete producer evidence")
    identity = sha(raw)
    path = Path(receipt["_artifact_directory"]) / (identity + ".bin")
    if path.exists():
        require(not path.is_symlink() and path.read_bytes() == raw, "Conflicting producer evidence")
    else:
        with path.open("xb") as output:
            output.write(raw)
    receipt["artifacts"][identity] = {"path": path.name, "bytes": len(raw), "sha256": identity}
    return identity


@contextmanager
def transport_only():
    previous, imported = sys.getprofile(), builtins.__import__
    seen, exchanges = set(), []
    def imports(name, *args, **kwargs):
        if name.startswith("biocompiler"):
            require(name in TRANSPORT_MODULES, "Python semantic import forbidden: " + name)
        return imported(name, *args, **kwargs)
    def calls(frame, event, result):
        module = frame.f_globals.get("__name__", "")
        if event == "call" and module.startswith("biocompiler"):
            require(module in TRANSPORT_MODULES, "Python semantic execution forbidden: " + module)
            seen.add(module)
        if event == "return" and module == "biocompiler.core_client" and frame.f_code.co_name == "_exchange" and result is not None:
            raw, exit_code = result
            exchanges.append({"request": frame.f_locals["request"], "response": raw, "exit_code": exit_code,
                              "executable": str(frame.f_locals["executable"])})
    sys.setprofile(calls)
    builtins.__import__ = imports
    try:
        yield seen, exchanges
        require(sys.getprofile() is calls and builtins.__import__ is imports, "Producer semantic guard disabled")
    finally:
        sys.setprofile(previous)
        builtins.__import__ = imported


def envelope(role, identity, operation, status, result, diagnostics):
    return {"protocol": "biocompiler.core.v1", "request_id": identity, "operation": operation,
            "status": status, "result": result, "diagnostics": diagnostics,
            "core": {"implementation": "ocaml", "version": "0.1.0", "protocol": "biocompiler.core.v1", "executable": role}}


def request_fingerprint(request):
    """Declared identity projection over frozen bytes; never domain decoding."""
    build = deepcopy(request["build_request"])
    for node in build["intent"]["nodes"]:
        node.pop("source", None)
    build["provenance"].pop("locations", None)
    build["provenance"].pop("recorded_at", None)
    behavior = deepcopy(request["behavior"])
    for key in ("nodes", "requirements"):
        for item in behavior[key]:
            item.pop("source", None)
    return digest({"schema_version": request["schema_version"], "build_request": digest(build),
        "behavior": digest(behavior), "contract": digest(request["contract"]), "domain": digest(request["domain"])})


def expected_semantic(corpus, case):
    profile = corpus.profiles[FAMILIES[case["operation"]]]
    authority = decode(case["authority"])
    record = None if case["expected"] is None else decode(case["expected"])
    identities = {"request_fingerprint": request_fingerprint(authority["request"]),
                  "request_artifact_fingerprint": digest(authority["request"])}
    if "config" in authority:
        # Exact default was captured in the unchanged original producer result.
        config = authority["config"] or {
            "schema_version": "biocompiler.synthetic_generator_config.v0.3",
            "catalog_fingerprint": "f2a4b4c1625b4794028fcd1d0e08785724f957023966a29faafe9374cca77343",
            "conjunction_strategy": "native", "generator_version": "biocompiler.synthetic.generator.v0.4",
            "profile_version": "biocompiler.synthetic.combinational.v0.1", "witness_selection": "closed_band_lower_endpoint"}
        identities["config_fingerprint"] = digest(config)
    if "history" in authority:
        identities["history_ascii_fingerprint"] = sha(json.dumps(authority["history"], sort_keys=True,
            separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode())
    if "candidate" in authority:
        identities["candidate_fingerprint"] = digest(authority["candidate"])
    if record is not None and "request_fingerprint" in record:
        require(record["request_fingerprint"] == identities["request_fingerprint"],
                "Declared byte identity projection differs from independent frozen product")
    return {"schema_version": profile["result_schema"],
        **{key: profile[key] for key in ("profile", "implementation", "service_implementation", "resource_profile",
                                      "resources", "validation_scope", "claim_scope")},
        "supplied_authority_fingerprint": sha(case["authority"]), "authority_identities": identities,
        "outcome": "produced" if record is not None else "unsupported", "record": record,
        "record_fingerprint": None if record is None else sha(case["expected"]), "generation_error": case["generation_error"]}


def validate_capability(raw, role, corpus, identities):
    response = decode(raw)
    require(set(response) == {"protocol", "request_id", "operation", "status", "result", "diagnostics", "core"},
            "Unexpected capability envelope fields")
    identity = response["request_id"]
    try:
        uuid = UUID(identity)
    except (ValueError, TypeError, AttributeError) as error:
        raise AssertionError("Invalid native capability request identity") from error
    require(uuid.version == 4 and str(uuid) == identity and identity not in identities, "Reused/non-v4 capability identity")
    identities.add(identity)
    result = response["result"]
    require(canonical(response) == canonical(envelope(role, identity, "capabilities", "ok", result, [])),
            "Unbound capability response")
    require(type(result) is dict and set(result) == {"schema_version", "operations", "intent_schemas", "canonicalization",
        "validation_scopes", "profiles", "limits", "claim_scope"} and
        result["schema_version"] == "biocompiler.core_capabilities.v1" and result["canonicalization"] == "python-json-v1" and
        type(result["profiles"]) is dict and type(result["claim_scope"]) is str and bool(result["claim_scope"].strip()),
        "Missing or incompatible complete native capabilities")
    for key in ("operations", "intent_schemas", "validation_scopes"):
        items = result[key]
        require(type(items) is list and all(type(item) is str and item.strip() for item in items) and
                len(set(items)) == len(items), "Invalid native capability inventory")
    require(canonical(result["limits"]) == canonical({"max_request_bytes": 16777216, "max_response_bytes": 33554432,
        "max_depth": 128, "max_json_nodes": 250000, "max_string_bytes": 4194304, "max_number_chars": 4300,
        "max_intent_nodes": 50000, "max_graph_edges": 250000}), "Native capability framing limits differ")
    require("capabilities" in result["operations"], "Native capability operation is missing")
    for family, profile in corpus.profiles.items():
        if role == "core":
            require(canonical(result["profiles"].get(family)) == canonical(profile) and
                    all(operation in result["operations"] for operation in profile["operations"]) and
                    profile["validation_scope"] in result["validation_scopes"],
                    "Core producer capability differs from independent declaration")
        else:
            require(family not in result["profiles"] and not set(profile["operations"]) & set(result["operations"]) and
                    profile["validation_scope"] not in result["validation_scopes"],
                    "Verifier advertised a producer")
    projected = deepcopy(response)
    projected["request_id"] = "<capability-uuid4>"
    return identity, projected


def campaign(clients, corpus, receipt):
    from biocompiler.core_client import CoreRejected
    from biocompiler.core_synthetic_producer import SyntheticProducerClient
    clients = {client.role: client for client in clients}
    receipt["library_coverage"] = artifact(receipt, canonical(corpus.library))
    for (role, _identity), case in corpus.expected().items():
        client = clients[role]
        with transport_only() as (seen, exchanges):
            if role == "core":
                adapter = SyntheticProducerClient(client)
                try:
                    result = getattr(adapter, METHODS[case["operation"]])(case["authority"], request_id=request_identity(role, case))
                except CoreRejected:
                    require(case["error"] is not None, "Unexpected producer protocol rejection")
                    result = None
                require(result is None or (result.record_json == case["expected"] and
                    result.receipt_json == canonical(expected_semantic(corpus, case))), "Complete installed producer result differs")
            else:
                try:
                    client.call(case["operation"], decode(case["authority"]), request_id=request_identity(role, case))
                except CoreRejected:
                    pass
                else:
                    raise AssertionError("Verifier dispatched a producer")
            require(seen == (TRANSPORT_MODULES if role == "core" else {"biocompiler.core_client"}),
                    "Installed producer transport path not fully exercised")
        entry = {"id": case["id"], "operation": case["operation"], "role": role,
            "request_id": request_identity(role, case), "authority": artifact(receipt, case["authority"]),
            "expected": None if case["expected"] is None else artifact(receipt, case["expected"]),
            "evidence": artifact(receipt, canonical(case["evidence"])), "guard_modules": sorted(seen), "exchanges": []}
        for exchange in exchanges:
            entry["exchanges"].append({**exchange, "request": artifact(receipt, exchange["request"]),
                                       "response": artifact(receipt, exchange["response"])})
        receipt["checks"].append(entry)
    with transport_only() as (seen, exchanges):
        clients["verify"].capabilities()
    require(seen == {"biocompiler.core_client"} and len(exchanges) == 1, "Verifier capability witness missing")
    receipt["verify_capabilities"] = {**exchanges[0], "request": artifact(receipt, exchanges[0]["request"]),
                                    "response": artifact(receipt, exchanges[0]["response"])}


def validate_checks(receipt, corpus, artifacts):
    expected = corpus.expected()
    require(type(receipt.get("completed_checks")) is int and receipt["completed_checks"] == len(expected) and
            type(receipt.get("checks")) is list and len(receipt["checks"]) == len(expected), "Incomplete producer occurrences")
    require(artifacts.raw(receipt["library_coverage"]) == canonical(corpus.library), "Private/injection coverage was changed or mislabeled")
    identities, seen, projected = set(), set(), []
    for row in receipt["checks"]:
        require(set(row) == {"id", "operation", "role", "request_id", "authority", "expected", "evidence", "guard_modules", "exchanges"},
                "Unexpected producer observation fields")
        key = row["role"], row["id"]
        require(key in expected and key not in seen, "Missing, duplicate or substituted original producer occurrence")
        seen.add(key)
        case, role = expected[key], row["role"]
        require(row["operation"] == case["operation"] and row["request_id"] == request_identity(role, case) and
                artifacts.raw(row["authority"]) == case["authority"] and
                (row["expected"] is None if case["expected"] is None else artifacts.raw(row["expected"]) == case["expected"]) and
                artifacts.raw(row["evidence"]) == canonical(case["evidence"]), "Complete original producer authority/result/evidence differs")
        require(row["guard_modules"] == sorted(TRANSPORT_MODULES if role == "core" else {"biocompiler.core_client"}),
                "Forbidden or missing Python producer guard modules")
        exchanges = row["exchanges"]
        require(type(exchanges) is list and len(exchanges) == (2 if role == "core" else 1), "Missing complete producer process trace")
        projected_exchanges = []
        for ordinal, exchange in enumerate(exchanges):
            require(set(exchange) == {"request", "response", "exit_code", "executable"} and type(exchange["exit_code"]) is int,
                    "Incomplete native wire evidence")
            path = Path(exchange["executable"])
            require(path.is_absolute() and path.name == "biocompiler-" + role, "Wrong/relative native execution path")
            require(str(path) == receipt["executables"][role], "Native trace used a different selected executable")
            wire_request, wire_response = artifacts.raw(exchange["request"]), artifacts.raw(exchange["response"])
            request, response = decode(wire_request), decode(wire_response)
            if role == "core" and ordinal == 0:
                identity, projected_response = validate_capability(wire_response, role, corpus, identities)
                require(request == {"protocol": "biocompiler.core.v1", "request_id": identity, "operation": "capabilities", "payload": {}}
                        and exchange["exit_code"] == 0, "Native negotiation request/exit differs")
                projected_request = {**request, "request_id": "<capability-uuid4>"}
            else:
                require(wire_request == canonical({"protocol": "biocompiler.core.v1", "request_id": row["request_id"],
                    "operation": case["operation"], "payload": decode(case["authority"])}), "Complete producer request bytes differ")
                if role == "verify":
                    wanted = envelope(role, row["request_id"], case["operation"], "unsupported", None, [UNSUPPORTED])
                    exit_code = 3
                elif case["error"] is not None:
                    wanted = envelope(role, row["request_id"], case["operation"], "error", None, [case["error"]])
                    exit_code = 2
                else:
                    wanted = envelope(role, row["request_id"], case["operation"], "ok", expected_semantic(corpus, case), [])
                    exit_code = 0
                require(canonical(response) == canonical(wanted) and exchange["exit_code"] == exit_code,
                        "Complete native producer receipt, record, error or numeric identity differs")
                projected_request, projected_response = request, response
            require(wire_request == canonical(request) and wire_response == canonical(response) + b"\n",
                    "Noncanonical native wire bytes")
            projected_exchanges.append({"request": projected_request, "response": projected_response, "exit_code": exchange["exit_code"]})
        projected.append({**{k: v for k, v in row.items() if k != "exchanges"}, "exchanges": projected_exchanges})
    require(seen == set(expected), "Original producer occurrence omitted")
    exchange = receipt["verify_capabilities"]
    require(set(exchange) == {"request", "response", "exit_code", "executable"} and type(exchange["exit_code"]) is int and exchange["exit_code"] == 0 and
            exchange["executable"] == receipt["executables"]["verify"], "Missing verifier capability trace")
    raw = artifacts.raw(exchange["response"])
    identity, projected_response = validate_capability(raw, "verify", corpus, identities)
    wanted = {"protocol": "biocompiler.core.v1", "request_id": identity, "operation": "capabilities", "payload": {}}
    require(artifacts.raw(exchange["request"]) == canonical(wanted) and raw == canonical(decode(raw)) + b"\n",
            "Verifier capability request/response bytes differ")
    require(artifacts.used == set(artifacts.declared), "Unreferenced complete producer evidence")
    return {"checks": projected, "verify_capabilities": projected_response, "library_coverage": receipt["library_coverage"]}


def compare(root, native_root, *, revision, source_revision, run_id):
    require(type(revision) is str and re.fullmatch(r"[0-9a-f]{40}", revision) and
            type(source_revision) is str and re.fullmatch(r"[0-9a-f]{40}", source_revision) and
            type(run_id) is str and bool(run_id), "Invalid current producer validation authority")
    root, native_root = Path(root), Path(native_root)
    require(root.is_dir() and not root.is_symlink() and native_root.is_dir() and not native_root.is_symlink(), "Unsafe evidence roots")
    names = {"realization-" + target + "-py" + python for target in PLATFORMS for python in PYTHONS}
    require({path.name for path in root.iterdir() if path.name.startswith("realization-")} == names,
            "Missing or extra producer matrix slot")
    corpus, receipts, natives, reference = Corpus(), {}, {}, None
    transport_sources = source_pins("src/" + name.replace(".", "/") + ".py" for name in sorted(TRANSPORT_MODULES))
    campaign_sources = source_pins(SOURCES)
    for target, (system, machine) in PLATFORMS.items():
        native_directory = native_root / target
        require(native_directory.is_dir() and not native_directory.is_symlink(), "Unsafe native platform directory")
        native = verify_binaries(native_directory, revision, target)
        natives[target] = native
        for python in PYTHONS:
            name = "realization-" + target + "-py" + python
            directory = root / name
            require(directory.is_dir() and not directory.is_symlink(), "Unsafe producer runtime directory")
            inputs, inputs_pin = read(directory / "native-inputs.json", r.CONTROL_BYTES)
            require(canonical({key: inputs.get(key) for key in native}) == canonical(native) and
                    inputs.get("run_id") == run_id and inputs.get("source_revision") == source_revision and
                    type(inputs.get("python_version")) is str and inputs["python_version"].startswith(python + "."),
                    "Stale or mixed same-run producer native inputs")
            receipt, receipt_pin = read(directory / RECEIPT_FILE)
            fields = {"schema_version": SCHEMA, "status": "success", "scope": SCOPE,
                "revision": revision, "source_revision": source_revision, "run_id": run_id,
                "python_version": inputs["python_version"], "system": system, "machine": machine,
                "native_platform": target, "corpus_pin": CORPUS_PIN, "capture_pin": CAPTURE_PIN,
                "profile_pin": digest(corpus.profiles), "artifact_directory": ARTIFACT_DIRECTORY,
                "native_inputs": native, "transport_sources": transport_sources, "campaign_sources": campaign_sources}
            for key, value in fields.items():
                require(canonical(receipt.get(key)) == canonical(value), "Stale/mixed producer receipt: " + key)
            require(type(receipt.get("package_path")) is str and Path(receipt["package_path"]).is_absolute(),
                    "Missing installed producer package provenance")
            executables = receipt.get("executables")
            require(type(executables) is dict and set(executables) == set(ROLES) and all(
                type(executables[role]) is str and Path(executables[role]).is_absolute() and
                Path(executables[role]).name == "biocompiler-" + role for role in ROLES) and
                Path(executables["core"]).parent == Path(executables["verify"]).parent,
                "Missing exact selected executable paths")
            artifacts = Artifacts(directory / ARTIFACT_DIRECTORY, receipt.get("artifacts"))
            complete = canonical(validate_checks(receipt, corpus, artifacts))
            if reference is None:
                reference = complete
            else:
                require(complete == reference, "Complete four-runtime producer evidence differs after UUID-only projection")
            receipts[name] = {"native_inputs": inputs_pin, "producer": receipt_pin,
                              "complete_artifacts": artifacts.verified}
    require(len(receipts) == 4 and reference is not None, "Incomplete producer runtime matrix")
    return {"schema_version": "biocompiler.synthetic_producer_reproducibility.v1", "status": "success",
        "revision": revision, "source_revision": source_revision, "run_id": run_id,
        "corpus_pin": CORPUS_PIN, "capture_pin": CAPTURE_PIN, "profile_pin": digest(corpus.profiles),
        "receipts": receipts, "native_inputs": natives, "complete_results_sha256": sha(reference),
        "core_occurrences": len(corpus.cases), "verify_role_rejections": len(corpus.verify_cases),
        "native_library_only_occurrences": len(corpus.library), "completed_checks_per_variant": len(corpus.expected())}


def campaign_main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for role in ROLES:
        parser.add_argument("--" + role, required=True, type=Path)
        parser.add_argument("--" + role + "-sha256", required=True)
    parser.add_argument("--native-root", required=True, type=Path)
    parser.add_argument("--platform", required=True, choices=PLATFORMS)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    import biocompiler
    from biocompiler.core_client import CoreClient
    import biocompiler.core_synthetic_producer
    started = time.monotonic()
    directory = args.output.with_name(ARTIFACT_DIRECTORY)
    directory.mkdir(parents=True, exist_ok=True)
    require(directory.is_dir() and not directory.is_symlink() and not any(directory.iterdir()), "Unsafe/nonempty producer artifact directory")
    receipt = {"schema_version": SCHEMA, "status": "running", "scope": SCOPE,
        "corpus_pin": CORPUS_PIN, "capture_pin": CAPTURE_PIN, "profile_pin": digest(declaration()),
        "revision": os.environ.get("GITHUB_SHA"), "source_revision": os.environ.get("GITHUB_HEAD_SHA", os.environ.get("GITHUB_SHA")),
        "run_id": os.environ.get("GITHUB_RUN_ID"), "system": platform.system(), "machine": platform.machine(),
        "python_version": platform.python_version(), "native_platform": args.platform,
        "package_path": str(Path(biocompiler.__file__).resolve()), "checks": [], "artifacts": {},
        "artifact_directory": directory.name, "_artifact_directory": str(directory)}
    code = 1
    try:
        require(not Path.cwd().resolve().is_relative_to(ROOT), "Run installed producer campaign outside checkout")
        require(receipt["run_id"] is not None and receipt["source_revision"] is not None, "Same-run hosted metadata required")
        require((platform.system(), platform.machine()) == PLATFORMS[args.platform], "Native/host platform mismatch")
        for name, module in tuple(sys.modules.items()):
            if name == "biocompiler" or name.startswith("biocompiler."):
                origin = getattr(module, "__file__", None)
                require(origin is None or not Path(origin).resolve().is_relative_to(ROOT), "Source-tree product loaded: " + name)
        native = verify_binaries(args.native_root, receipt["revision"], args.platform)
        receipt["native_inputs"] = native
        clients, receipt["executables"] = [], {}
        for role in ROLES:
            path, pin = getattr(args, role), getattr(args, role + "_sha256")
            expected = args.native_root / ("biocompiler-" + role)
            require(path.is_absolute() and path.resolve() == expected.resolve() and not path.is_symlink() and os.access(path, os.X_OK),
                    "Unbound or nonexecutable producer input")
            require(pin == native["sha256"][expected.name], "Explicit binary pin differs from same-run manifest")
            clients.append(CoreClient(path, role=role, expected_sha256=pin, timeout_seconds=300))
            receipt["executables"][role] = str(path)
        receipt["transport_sources"] = {}
        for name in sorted(TRANSPORT_MODULES):
            path = Path(sys.modules[name].__file__)
            relative = "src/" + name.replace(".", "/") + ".py"
            pin = sha(path.read_bytes())
            require(pin == sha((ROOT / relative).read_bytes()), "Installed producer adapter differs from tested revision")
            receipt["transport_sources"][relative] = pin
        receipt["campaign_sources"] = source_pins(SOURCES)
        corpus = Corpus()
        campaign(clients, corpus, receipt)
        receipt["completed_checks"] = len(receipt["checks"])
        validate_checks(receipt, corpus, Artifacts(directory, receipt["artifacts"]))
        require(canonical(verify_binaries(args.native_root, receipt["revision"], args.platform)) == canonical(native),
                "Native binaries changed during complete producer campaign")
        receipt["status"], code = "success", 0
    except Exception as error:
        receipt["status"], receipt["error"] = "failure", type(error).__name__ + ": " + str(error)
        print(receipt["error"], file=sys.stderr)
    receipt["completed_checks"] = len(receipt["checks"])
    receipt["duration_seconds"] = round(time.monotonic() - started, 6)
    del receipt["_artifact_directory"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(receipt) + b"\n")
    print("Installed direct producers:", receipt["status"], receipt["completed_checks"], "complete observations")
    return code


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if "--compare" not in arguments:
        return campaign_main(arguments)
    parser = argparse.ArgumentParser(description="Compare complete direct-producer evidence across four runtimes")
    parser.add_argument("--compare", required=True, action="store_true")
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--native-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(arguments)
    result = compare(args.root, args.native_root, revision=os.environ.get("GITHUB_SHA"),
        source_revision=os.environ.get("GITHUB_HEAD_SHA", os.environ.get("GITHUB_SHA")), run_id=os.environ.get("GITHUB_RUN_ID"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(result) + b"\n")
    print("Complete original direct-producer records/errors match across four required runtimes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
