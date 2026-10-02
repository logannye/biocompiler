"""Rehash complete realization evidence across both platforms and Python versions.

Only safe downloaded sibling files are read. No binary is executed and no
biocompiler module is imported by this independent receipt/fixture comparator.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re

if __package__:
    from .check_realization_binaries import PLATFORMS, verify as verify_binaries
else:
    from check_realization_binaries import PLATFORMS, verify as verify_binaries

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/conformance/realization-protocol-v1.json"
CORPUS_PIN = "9261f5fc259e6d79e56df6bf9cc5ee528e795aa5dd2ef8bc4dcc7b63dfd4d4bf"
BASE_PIN = "d32009a03f0af00de4da60f0244c210ba15b9ff89e828ea56c82b5f9e4a73331"
PYTHONS = ("3.11", "3.14")
REQUIRED_ROUTES = {
    "biocompiler.verification.realization.realization_dependencies",
    "biocompiler.verification.realization.check_realization",
    "biocompiler.synthesis.synthetic.check_synthetic_candidate",
    "biocompiler.compiler.components.check_component_behavior",
    "biocompiler.compiler.components.check_component_assembly",
}
APIS = {
    "realization_dependencies": ("realization", "realization-dependencies"),
    "check_realization": ("realization", "verify-realization"),
    "check_synthetic_candidate": ("synthetic_candidate", "verify-synthetic-candidate"),
    "check_component_behavior": ("component_behavior", "verify-component-behavior"),
    "check_component_assembly": ("component_assembly", "verify-component-assembly"),
}


def require(value, message):
    if not value:
        raise AssertionError(message)


def canonical(value, *, ascii=False):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=ascii,
                      allow_nan=False).encode("ascii" if ascii else "utf-8")


def digest(value, *, ascii=False):
    return hashlib.sha256(canonical(value, ascii=ascii)).hexdigest()


def pin(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def read(path, maximum=32 * 1024 * 1024):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= maximum,
            "Missing, symlinked, empty or oversized evidence: " + str(path))
    def unique(pairs):
        result = {}
        for key,value in pairs:
            require(key not in result, "Duplicate evidence key: " + key)
            result[key] = value
        return result
    def nonfinite(value):
        raise AssertionError("Nonfinite evidence: " + value)
    data = path.read_bytes()
    return json.loads(data, object_pairs_hook=unique, parse_constant=nonfinite), hashlib.sha256(data).hexdigest()


class Golden:
    def __init__(self, path=CORPUS):
        self.path = Path(path)
        self.index, _ = read(path)
        require(self.index["inventory_fingerprint"] == CORPUS_PIN and
                digest({k:v for k,v in self.index.items() if k != "inventory_fingerprint"}) == CORPUS_PIN,
                "Reviewed protocol corpus pin differs")
        base_path = ROOT / self.index["baseline"]["path"]
        require(base_path.resolve().is_relative_to(ROOT / "tests/conformance"), "Unsafe original corpus reference")
        self.base_path = base_path
        self.base, _ = read(base_path)
        require(self.base["inventory_fingerprint"] == BASE_PIN and
                digest({k:v for k,v in self.base.items() if k != "inventory_fingerprint"}) == BASE_PIN,
                "Original full acceptance corpus pin differs")
        self.metadata = {d["id"]:d for d in self.index["documents"]}
        self.base_metadata = {d["id"]:d for d in self.base["documents"]}
        self.cache = {}
        self.profile_doc = self.document(self.index["profiles"])
        self.profiles = self.profile_doc["capability_profiles"]
        self.cases = self.index["cases"] + self.index["additional_cases"]

    def document(self, identity):
        if identity not in self.cache:
            base = identity.startswith("baseline:")
            key = identity.removeprefix("baseline:")
            metadata = (self.base_metadata if base else self.metadata)[key]
            path = (self.base_path if base else self.path).with_suffix("") / (key + ".json")
            value, _ = read(path)
            require(path.stat().st_size == metadata["bytes"] and digest(value) == key, "Golden full document differs")
            self.cache[identity] = value
        return self.cache[identity]

    def payload(self, case, replay=False):
        value = self.document(case["input"])
        raw = json.loads(value) if isinstance(value,str) else json.loads(canonical(value))
        if case.get("version_mutation"):
            raw = raw["authority"]
        if "request" in raw:
            raw["expected_request"] = raw.pop("request")
        family, operation = APIS[case["api"]]
        payload = {"profile":self.profiles[family]["profile"],"limits":None,**raw}
        if replay:
            operation = operation.replace("verify-", "replay-", 1)
            payload["assessment"] = self.document(case["historical_result"])
        return operation,payload

    def expected(self, kind):
        expected = {}
        for role in ("core","verify"):
            for case in self.cases:
                operation,_ = self.payload(case)
                expected[role,case["id"],operation] = (case,case["error"],False)
                if kind == "protocol" and case["result"] is not None and operation.startswith("verify-"):
                    replay = operation.replace("verify-","replay-",1)
                    error = {"code":"realization_assessment_mismatch"} if case.get("version_mutation") else None
                    expected[role,case["id"],replay] = (case,error,True)
                    if case.get("version_mutation"):
                        expected[role,case["id"] + "/current-policy",replay] = (case,None,True)
            if kind == "protocol":
                by_id = {c["id"]:c for c in self.cases}
                for entry in self.index["boundary_cases"]:
                    case = by_id[entry["source"]]
                    operation,_ = self.payload(case,entry["replay"])
                    expected[role,entry["id"],operation] = (case,{"code":entry["code"]},entry["replay"])
        count = self.index["coverage"]["protocol_checks_per_role" if kind == "protocol" else "sdk_checks_per_role"]
        require(len(expected) == 2 * count, "Golden expected matrix contains a duplicate or missing occurrence")
        return expected


def artifacts(directory, declared):
    require(directory.is_dir() and not directory.is_symlink(), "Missing or unsafe full-report directory")
    require(type(declared) is dict and all(pin(key) for key in declared), "Invalid full-artifact inventory")
    require({p.name for p in directory.iterdir()} == {key + ".json" for key in declared}, "Missing or extra full report artifact")
    values = {}
    for identity,entry in declared.items():
        require(entry == {"bytes":entry.get("bytes"),"path":identity + ".json","canonical_sha256":identity} and
                type(entry["bytes"]) is int, "Invalid artifact descriptor")
        path = directory / entry["path"]
        value,_ = read(path, 40 * 1024 * 1024)
        require(path.stat().st_size == entry["bytes"] and digest(value) == identity and
                path.read_bytes() == canonical(value) + b"\n", "Full actual report bytes differ")
        values[identity] = value
    return values


def validate_checks(receipt, kind, golden, values):
    expected = golden.expected(kind)
    checks = receipt.get("checks")
    require(type(checks) is list and len(checks) == len(expected) and
            receipt.get("completed_checks") == len(expected), "Incomplete exact occurrence matrix")
    seen = {}
    used = set()
    for check in checks:
        key = check.get("role"),check.get("id"),check.get("operation")
        require(key in expected and key not in seen, "Unknown, duplicate or stale occurrence")
        case,error,replay = expected[key]
        require(pin(check.get("artifact")) and check["artifact"] in values, "Missing complete occurrence artifact")
        value = values[check["artifact"]]
        used.add(check["artifact"])
        common = {"role","id","operation","artifact"}
        if error is not None:
            require(set(check) == common | {"error"} and check["error"] == error["code"], "Expected rejection changed")
            require(type(value) is dict and set(value) == {"status","result","diagnostics"} and
                    value["status"] == "error" and value["result"] is None and len(value["diagnostics"]) == 1,
                    "Rejected call retained an accepted result")
            diagnostic = value["diagnostics"][0]
            require(set(diagnostic) == {"code","message","path"} and diagnostic["code"] == error["code"]
                    and type(diagnostic["message"]) is str and bool(diagnostic["message"])
                    and (diagnostic["path"] is None or type(diagnostic["path"]) is str), "Incomplete original error signature")
            if "message" in error:
                require(diagnostic["message"] == error["message"], "Original complete rejection message differs")
        else:
            report = golden.document(case["result"])
            family = golden.profiles[APIS[case["api"]][0]]
            dependency = case["api"] == "realization_dependencies"
            encoding = family["dependency_encoding" if dependency else "assessment_encoding"]
            report_pin = digest(report,ascii=encoding == "python-json-ascii-v1")
            outcome = None if dependency else report["outcome"]
            if kind == "routing":
                require(set(check) == common | {"report","outcome"} and check["report"] == report_pin
                        and check["outcome"] == outcome and canonical(value) == canonical(report),
                        "SDK full record or family identity differs from original oracle")
            else:
                label = "dependencies" if dependency else "assessment"
                operation,payload = golden.payload(case,replay)
                authority_pin = digest({k:v for k,v in payload.items() if k != "assessment"})
                require(set(check) == common | {"authority",label,"outcome"} and check["authority"] == authority_pin
                        and check[label] == report_pin and check["outcome"] == outcome, "Protocol occurrence identities differ")
                fields = golden.profile_doc["dependency_result_fields" if dependency else "result_fields"]
                require(set(value) == set(fields) and canonical(value[label]) == canonical(report)
                        and value[label + "_fingerprint"] == report_pin and
                        value["supplied_authority_fingerprint"] == authority_pin and
                        value["authority_identities"] == case["authority_identities"], "Complete protocol envelope/oracle differs")
                for field in ("profile","implementation","service_implementation","validation_scope","claim_scope"):
                    source = "dependency_" + field if dependency and field in ("validation_scope","claim_scope") else field
                    require(value[field] == family[source], "Negotiated report scope/version differs")
                require(value["resources"] == family["resources"] and
                        value["resource_profile"] == family["resources"]["protocol"]["profile"] and
                        value["schema_version"] == family["result_schemas"][operation], "Full resources/schema differ")
        seen[key] = check
    require(used == set(values), "Unreferenced actual artifact")
    return [seen[key] for key in sorted(seen)]


def compare(root, native_root, *, revision, source_revision, run_id):
    require(type(revision) is str and re.fullmatch(r"[0-9a-f]{40}",revision) and
            type(source_revision) is str and re.fullmatch(r"[0-9a-f]{40}",source_revision) and
            type(run_id) is str and bool(run_id), "Invalid current workflow authority")
    root,native_root = Path(root),Path(native_root)
    golden = Golden()
    references, receipts, natives = {}, {}, {}
    for target,(system,machine) in PLATFORMS.items():
        native = verify_binaries(native_root / target, revision, target)
        natives[target] = native
        for python in PYTHONS:
            name = "realization-" + target + "-py" + python
            directory = root / name
            require(directory.is_dir() and not directory.is_symlink(), "Missing realization matrix slot: " + name)
            inputs,inputs_pin = read(directory / "native-inputs.json", 64 * 1024)
            require({k:inputs.get(k) for k in native} == native and inputs.get("run_id") == run_id and
                    inputs.get("source_revision") == source_revision and
                    type(inputs.get("python_version")) is str and inputs["python_version"].startswith(python + "."),
                    "Stale/mixed native-input runtime receipt")
            receipt_pins = {"native_inputs":inputs_pin}
            for kind in ("protocol","routing"):
                receipt,receipt_pin = read(directory / (kind + ".json"), 32 * 1024 * 1024)
                require(receipt.get("schema_version") == "biocompiler.realization_" + kind + "_conformance.v1" and
                        receipt.get("status") == "success" and receipt.get("revision") == revision and
                        receipt.get("source_revision") == source_revision and receipt.get("run_id") == run_id and
                        receipt.get("python_version") == inputs["python_version"] and
                        type(receipt.get("platform")) is str and receipt.get("system") == system and
                        receipt.get("machine") == machine and receipt.get("corpus_pin") == CORPUS_PIN and
                        receipt.get("baseline_pin") == BASE_PIN and type(receipt.get("package_path")) is str and
                        receipt.get("scope") == "direct_operations_only_no_workflow_archive_or_export_migration",
                        "Stale, wrong-platform, incomplete or mixed campaign receipt")
                require(set(receipt.get("executables",{})) == {"core","verify"}, "Missing executable role")
                for role,binary in (("core","biocompiler-core"),("verify","biocompiler-verify")):
                    item = receipt["executables"][role]
                    require(set(item) == {"path","sha256"} and type(item["path"]) is str and
                            Path(item["path"]).is_absolute() and item["sha256"] == native["sha256"][binary],
                            "Selected executable differs from downloaded exact-revision bytes")
                if kind == "routing":
                    guard = receipt.get("guard",{})
                    require(guard.get("status") == "passed" and
                            guard.get("input_hydration") == "outside_guard_before_native_call" and
                            guard.get("snapshot_request_rehydration") == "forbidden_during_native_call" and
                            type(guard.get("allowed_executed_functions")) is list and
                            REQUIRED_ROUTES <= set(guard["allowed_executed_functions"]) and
                            "biocompiler.compiler.request.RealizationRequest.__post_init__" not in guard["allowed_executed_functions"],
                            "Missing executed SDK no-fallback guard receipt")
                require(receipt.get("artifact_directory") == kind + "-reports", "Unsafe sibling artifact path")
                values = artifacts(directory / (kind + "-reports"), receipt.get("artifacts"))
                checks = validate_checks(receipt,kind,golden,values)
                canonical_result = canonical({"checks":checks,"artifacts":values})
                if kind in references:
                    require(canonical_result == references[kind], "Complete four-way realization bytes or occurrence results differ")
                else:
                    references[kind] = canonical_result
                receipt_pins[kind] = receipt_pin
            receipts[name] = receipt_pins
    require(len(receipts) == 4, "Incomplete four-way realization matrix")
    return {"schema_version":"biocompiler.realization_reproducibility.v1","status":"success",
            "revision":revision,"source_revision":source_revision,"run_id":run_id,
            "corpus_pin":CORPUS_PIN,"baseline_pin":BASE_PIN,"receipts":receipts,"native_inputs":natives,
            "complete_results":{kind:hashlib.sha256(value).hexdigest() for kind,value in references.items()},
            "protocol_checks_per_role":golden.index["coverage"]["protocol_checks_per_role"],
            "sdk_checks_per_role":golden.index["coverage"]["sdk_checks_per_role"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",required=True,type=Path)
    parser.add_argument("--native-root",required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    args = parser.parse_args(argv)
    result = compare(args.root,args.native_root,revision=os.environ.get("GITHUB_SHA"),
                     source_revision=os.environ.get("GITHUB_HEAD_SHA",os.environ.get("GITHUB_SHA")),
                     run_id=os.environ.get("GITHUB_RUN_ID"))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2) + "\n")
    print("Complete realization protocol/routing artifacts match across four required matrix cells")
    return 0


if __name__ == "__main__": raise SystemExit(main())
