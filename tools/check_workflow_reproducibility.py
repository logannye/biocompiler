"""Re-read complete workflow evidence across four hosted runtime variants.

This comparator uses standard-library fixture readers only. It never imports
biocompiler, executes a native binary, or treats an uploaded digest as evidence
without reading and hashing the complete corresponding sibling file.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re

if __package__:
    from .check_realization_binaries import PLATFORMS, verify as verify_binaries
else:
    from check_realization_binaries import PLATFORMS, verify as verify_binaries

ROOT = Path(__file__).resolve().parents[1]
CORPUS_PIN = "2f5e7636977f559e046776c1bb92bebf67c8f0e733ca463927f8d3a1aee3d77b"
CAPTURE_PIN = "5e7b74bd456a554dd3b1e3661f25ec42ff00a719b114d19cdd474d9c014b1015"
SUPPLEMENTAL_PIN = "b396f27f2acfb7bb2b5eee4f57ae69eef5028d6ee34d9c7288761bc322a93cdc"
PROFILE_PIN = "6961059d7eb2dc55cef1ede11b09faf37043e9c7cb040da90f6a09f95fa38643"
PYTHONS = ("3.11", "3.14")
ROLES = ("core", "verify")
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
CONTROL_BYTES = 65_536
LIMIT_FIELDS = ("max_work", "max_monitor_items", "max_request_bytes", "max_report_bytes", "max_report_nodes")
TRANSPORT_MODULES = {"biocompiler.core_client", "biocompiler.core_artifacts", "biocompiler.core_workflow"}


def require(value, message):
    if not value:
        raise AssertionError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def pin(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def raw_file(path, maximum=MAX_ARTIFACT_BYTES):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= maximum,
            "Missing, symlinked, empty or oversized evidence: " + str(path))
    with path.open("rb") as source:
        data = source.read(maximum + 1)
    require(0 < len(data) <= maximum and len(data) == path.stat().st_size,
            "Evidence size changed while reading: " + str(path))
    return data


def decode(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate evidence key: " + key)
            result[key] = value
        return result

    def nonfinite(value):
        raise AssertionError("Nonfinite evidence: " + value)

    def finite(value):
        number = float(value)
        require(math.isfinite(number), "Nonfinite evidence number")
        return number

    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=unique, parse_constant=nonfinite, parse_float=finite)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise AssertionError("Malformed complete evidence JSON") from error


def read(path, maximum=32 * 1024 * 1024):
    data = raw_file(path, maximum)
    return decode(data), hashlib.sha256(data).hexdigest()


class Artifacts:
    """Verify the complete inventory up front; load bounded bytes on demand."""

    def __init__(self, directory, declared):
        self.directory = Path(directory)
        require(self.directory.is_dir() and not self.directory.is_symlink(), "Unsafe workflow artifact directory")
        require(type(declared) is dict and all(pin(key) for key in declared), "Invalid workflow artifact inventory")
        require({p.name for p in self.directory.iterdir()} == {key + ".bin" for key in declared},
                "Missing or extra complete workflow artifact")
        self.declared = declared
        self.used = set()
        self.verified = {}
        for identity, entry in declared.items():
            require(type(entry) is dict and set(entry) == {"path", "bytes", "sha256"} and
                    entry["path"] == identity + ".bin" and entry["sha256"] == identity and
                    type(entry["bytes"]) is int and 0 < entry["bytes"] <= MAX_ARTIFACT_BYTES,
                    "Invalid complete workflow artifact descriptor")
            raw = raw_file(self.directory / entry["path"])
            require(len(raw) == entry["bytes"] and hashlib.sha256(raw).hexdigest() == identity,
                    "Complete workflow bytes differ from their declared identity")
            self.verified[identity] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}

    def raw(self, identity, maximum=MAX_ARTIFACT_BYTES):
        require(pin(identity) and identity in self.declared, "Missing complete occurrence artifact")
        self.used.add(identity)
        raw = raw_file(self.directory / self.declared[identity]["path"], maximum)
        require(len(raw) == self.declared[identity]["bytes"] and hashlib.sha256(raw).hexdigest() == identity,
                "Complete workflow artifact changed after inventory verification")
        return raw

    def json(self, identity, maximum=CONTROL_BYTES):
        raw = self.raw(identity, maximum)
        value = decode(raw)
        require(canonical(value) == raw, "Noncanonical complete workflow evidence")
        return value


def effective_resources(profile, reductions):
    resources = decode(canonical(profile["resources"]))
    defaults = resources["workflow"]
    selected = {key: defaults[key] for key in LIMIT_FIELDS} if reductions is None else reductions
    require(type(selected) is dict and set(selected) == set(LIMIT_FIELDS) and
            all(type(selected[key]) is int and 0 < selected[key] <= defaults[key] for key in LIMIT_FIELDS),
            "Invalid expected workflow resource reductions")
    resources["workflow"].update(selected)
    resources["workflow"]["max_evaluation_work"] = min(50_000_000, selected["max_work"])

    def visit(value):
        if type(value) is dict:
            return {key: min(item, selected[key]) if key in selected else visit(item)
                    for key, item in value.items()}
        if type(value) is list:
            return [visit(item) for item in value]
        return value

    resources["realization"] = visit(resources["realization"])
    resources["synthetic"] = visit(resources["synthetic"])
    return resources


def descriptor(raw):
    return None if raw is None else {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def request_identity(role, case):
    return "workflow-" + hashlib.sha256((role + "|" + case["id"] + "|" + case["phase"]).encode()).hexdigest()[:32]


def expected_semantic(profile, role, case, record):
    authority = decode(case["authority"])
    document = decode(record)
    return {
        "schema_version": "biocompiler.core.verification_workflow_result.v1",
        "profile": profile["profile"], "operation": case["operation"],
        "executable": role, "request_id": request_identity(role, case),
        "validation_scope": profile["validation_scope"],
        "implementation_version": profile["implementation_version"],
        "workflow_version": profile["workflow_version"],
        "workflow_operation": authority["operation"], "mode": authority["mode"],
        "authority_fingerprint": digest(authority), "request_fingerprint": digest(document["request"]),
        "retained_record_fingerprint": None if case["retained"] is None else digest(decode(case["retained"])),
        "record_fingerprint": hashlib.sha256(record).hexdigest(),
        "resources": effective_resources(profile, case["limits"]),
    }


class Golden:
    def __init__(self):
        # This fixture reader is deliberately standard-library-only at import.
        # No installed application/transport modules participate in comparison.
        if __package__:
            from .check_native_workflow import Corpus
        else:
            from check_native_workflow import Corpus
        original, _ = read(ROOT / "tests/conformance/realization-workflow-v1.json")
        require(original["inventory_fingerprint"] == CORPUS_PIN and
                digest({key: value for key, value in original.items() if key != "inventory_fingerprint"}) == CORPUS_PIN and
                original["original_capture_fingerprint"] == CAPTURE_PIN,
                "Complete original workflow inventory differs")
        supplemental, _ = read(ROOT / "tests/conformance/verification-workflow-service-v1.json")
        require(supplemental["inventory_fingerprint"] == SUPPLEMENTAL_PIN and
                digest({key: value for key, value in supplemental.items() if key != "inventory_fingerprint"}) == SUPPLEMENTAL_PIN,
                "Independent supplemental workflow inventory differs")
        self.profile = supplemental["profile"]
        require(digest(self.profile) == PROFILE_PIN and supplemental["profile_sha256"] == PROFILE_PIN,
                "Complete workflow profile differs")
        provenance = supplemental["provenance"]
        require(provenance["original_inventory_fingerprint"] == CORPUS_PIN and
                provenance["original_capture_fingerprint"] == CAPTURE_PIN and
                provenance["original_source_files"] == original["source_files"],
                "Supplemental original-source lineage differs")
        self.cases = list(Corpus().cases())
        require(len(self.cases) == 112 and Counter(case["origin"] for case in self.cases) ==
                {"original": 89, "supplemental": 18, "normalization": 2, "resource": 2, "authority_precedence": 1},
                "Complete original/supplemental/resource workflow occurrence census differs")
        original_ids = {case["id"] for case in self.cases if case["origin"] == "original"}
        # Reconstruct the required ID set directly from the immutable source
        # ledgers as well as checking the campaign's projection census.
        metadata = {entry["id"]: entry for entry in original["documents"]}
        original_rows = {}
        for context in original["contexts"]:
            identity = context["ledger"]
            require(pin(identity) and identity in metadata, "Unknown original workflow ledger")
            path = ROOT / "tests/conformance/realization-workflow-v1" / (identity + ".json")
            data = raw_file(path)
            rows = decode(data)
            require(len(data) == metadata[identity]["bytes"] and digest(rows) == identity and
                    type(rows) is list and len(rows) == context["api_calls"] and context["assertion_status"] == "passed",
                    "Complete original workflow source ledger differs")
            for ordinal, call in enumerate(rows):
                if call["api"] in ("run_synthetic_verification", "replay_synthetic_verification"):
                    original_rows[context["id"] + "/api/" + str(ordinal)] = call
        require(len(original_rows) == 52 and original_ids == set(original_rows),
                "An original workflow occurrence was omitted, substituted or deduplicated")
        for case in self.cases:
            if case["origin"] == "original":
                require(canonical(case["source_evidence"]["observation"]) == canonical(original_rows[case["id"]]),
                        "Complete original workflow observation changed during projection")
        require({(decode(case["authority"])["operation"], decode(case["authority"])["mode"])
                 for case in self.cases if case["origin"] == "supplemental"} ==
                {(operation, mode) for operation in ("check", "explore", "reduce") for mode in ("candidate", "model")},
                "Complete operation/mode matrix is missing")

    def expected(self):
        expected = {}
        for role in ROLES:
            for case in self.cases:
                key = role, case["id"], case["phase"], case["operation"]
                require(key not in expected, "Duplicate original workflow occurrence")
                expected[key] = case
        return expected


def validate_checks(receipt, golden, artifacts):
    expected = golden.expected()
    checks = receipt.get("checks")
    require(type(checks) is list and len(checks) == len(expected) and
            type(receipt.get("completed_checks")) is int and receipt["completed_checks"] == len(expected),
            "Incomplete exact workflow occurrence matrix")
    seen = {}
    fields = {"role", "id", "phase", "origin", "operation", "limits", "request_id", "authority", "retained",
              "expected", "source_evidence", "status", "diagnostic", "record", "semantic_receipt", "envelope", "guard_modules"}
    for check in checks:
        require(type(check) is dict and set(check) == fields, "Incomplete workflow occurrence receipt")
        key = check["role"], check["id"], check["phase"], check["operation"]
        require(key in expected and key not in seen, "Unknown, duplicate or stale workflow occurrence")
        role = key[0]
        case = expected[key]
        require(check["origin"] == case["origin"] and canonical(check["limits"]) == canonical(case["limits"]) and
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


def source_pins(paths):
    return {path: hashlib.sha256(raw_file(ROOT / path)).hexdigest() for path in paths}


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
    campaign_sources = source_pins(("tools/check_native_workflow.py", "tests/test_native_workflow_campaign.py"))
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
            receipt, receipt_pin = read(directory / "workflow.json")
            require(receipt.get("schema_version") == "biocompiler.native_workflow_conformance.v1" and
                    receipt.get("status") == "success" and
                    receipt.get("scope") == "complete_native_workflow_sdk_run_replay_only_public_cli_and_pipeline_unmigrated" and
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
            require(receipt.get("artifact_directory") == "workflow-artifacts", "Unsafe workflow sibling artifact path")
            artifacts = Artifacts(directory / "workflow-artifacts", receipt.get("artifacts"))
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
    return {"schema_version": "biocompiler.workflow_reproducibility.v1", "status": "success",
            "revision": revision, "source_revision": source_revision, "run_id": run_id,
            "corpus_pin": CORPUS_PIN, "capture_pin": CAPTURE_PIN, "supplemental_pin": SUPPLEMENTAL_PIN,
            "profile_pin": PROFILE_PIN, "receipts": receipts, "native_inputs": natives,
            "complete_results_sha256": hashlib.sha256(reference).hexdigest(),
            "checks_per_role": len(golden.cases), "completed_checks_per_variant": len(golden.expected())}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--native-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    result = compare(args.root, args.native_root, revision=os.environ.get("GITHUB_SHA"),
                     source_revision=os.environ.get("GITHUB_HEAD_SHA", os.environ.get("GITHUB_SHA")),
                     run_id=os.environ.get("GITHUB_RUN_ID"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(result) + b"\n")
    print("Complete workflow records, rejections and resources match across four required matrix cells")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
