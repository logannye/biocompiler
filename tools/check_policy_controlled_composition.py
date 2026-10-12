"""Hosted actual-binary controlled source/domain admission campaign.

This finite campaign retains complete original requests and results. It never
builds native code, executes an activity model, constructs RNA, or establishes
biological function. Installed imports are checked against their actual RECORD.
"""
from __future__ import annotations

import argparse
import base64
from copy import deepcopy
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import sys

try:
    from .check_policy_core import source_identity
except ImportError:
    from check_policy_core import source_identity

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = {
    "request": "core/test/data/policy_controlled_request_v014.json",
    "source": "core/test/data/policy_controlled_source_v01.json",
    "domain": "core/test/data/policy_controlled_domain_v01.json",
}
OBSERVATIONS = (
    "baseline-original", "baseline-core", "baseline-verify",
    "cartesian-original", "cartesian-core", "cartesian-verify",
    "stale-model-pin", "extra-source-declaration", "domain-contradiction",
    "freshness-mismatch", "request-work-exhaustion", "domain-work-exhaustion",
    "closed-field", "transport-cancellation",
)
NEGATIVE_DIAGNOSTICS = {
    "stale-model-pin": "controlled_authority_admission",
    "extra-source-declaration": "policy_controlled_source",
    "domain-contradiction": "policy_controlled_domain_contradiction",
    "freshness-mismatch": "policy_controlled_domain_binding",
    "request-work-exhaustion": "policy_controlled_service_work_limit",
    "domain-work-exhaustion": "controlled_domain_exhausted",
    "closed-field": "unknown_field",
}


def require(value, message):
    if not value:
        raise AssertionError(message)


def file_pin(path, maximum=32 * 1024 * 1024):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "Missing or redirected campaign input: " + str(path))
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    require(0 < len(raw) <= maximum, "Campaign file exceeds its byte bound")
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def imported_modules(require_installed):
    import biocompiler
    package = Path(biocompiler.__file__).resolve().parent
    if require_installed:
        require(not package.is_relative_to(ROOT), "Installed campaign imported the source checkout")
        distribution = importlib.metadata.distribution("biocompiler")
        records = {Path(distribution.locate_file(row)).resolve(): row for row in distribution.files or ()}
    else:
        require(package == ROOT / "src/biocompiler", "Source campaign imported another SDK")
        records = {}
    result = {}
    for name, module in sorted(sys.modules.items()):
        if name != "biocompiler" and not name.startswith("biocompiler."):
            continue
        location = getattr(module, "__file__", None)
        require(location is not None, "Imported SDK module has no verifiable source")
        path = Path(location).resolve()
        require(path.is_relative_to(package) and path.suffix == ".py", "SDK import escaped selected package")
        pin = file_pin(path)
        if require_installed:
            record = records.get(path)
            require(record is not None and record.hash is not None and record.hash.mode == "sha256"
                    and record.size == pin["bytes"], "Imported SDK file lacks its complete installed RECORD")
            encoded = base64.urlsafe_b64encode(bytes.fromhex(pin["sha256"])).decode().rstrip("=")
            require(record.hash.value == encoded, "Imported SDK source differs from actual installed RECORD")
        result[name] = {"path": str(path), **pin}
    require("biocompiler.core_policy_controlled_composition" in result,
            "Campaign did not import the controlled-admission transport")
    return {"package": str(package), "modules": result, "record_verified": require_installed}


def cartesian(original):
    """Independent literal factors: four RNA pairs times three evidence rows."""
    result = deepcopy(original)
    domain = result["operating_domain"]
    domain["physical_factors"] = [{"input": key, "ticks": [1], "values": ["absent", "present"]}
                                  for key in ("rna_a", "rna_b")]
    domain["evidence_factors"] = [{"input": "controller", "ticks": [2],
                                   "statuses": ["valid", "missing"], "age_ticks": [0]}]
    return result


def adversaries(original):
    values = {name: deepcopy(original) for name in NEGATIVE_DIAGNOSTICS}
    values["stale-model-pin"]["mechanism_model"]["body"]["delays"]["onset_ticks"] = 3
    declarations = values["extra-source-declaration"]["source_authority"]["document"]["program"]["declarations"]
    declarations.append(deepcopy(declarations[-1]))
    values["domain-contradiction"]["operating_domain"]["fixed_inputs"][1]["event"] = "start"
    values["freshness-mismatch"]["operating_domain"]["inputs"][1]["freshness_ticks"] = 2
    values["request-work-exhaustion"]["budgets"]["max_work"] = 1
    values["domain-work-exhaustion"]["operating_domain"]["limits"]["max_work"] = 1
    values["closed-field"]["accepted"] = True
    return values


def run(args):
    require(os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted",
            "Actual native campaign is hosted-only; local execution needs separate user authorization")
    from biocompiler.core_client import CoreClient, CoreRejected, CoreCancelled, encode_json
    from biocompiler.core_policy_controlled_composition import PolicyControlledCompositionClient, OPERATION

    binaries = {role: Path(getattr(args, role)).absolute() for role in ("core", "verify")}
    binary_pins = {role: file_pin(path, 256 * 1024 * 1024) for role, path in binaries.items()}
    for role, path in binaries.items():
        require(os.access(path, os.X_OK), "Selected native path is not executable")
        expected = getattr(args, role + "_sha256")
        require(expected is None or expected == binary_pins[role]["sha256"], "Native bytes differ from external digest")
    fixture_pins = {name: file_pin(ROOT / path, 4 * 1024 * 1024) for name, path in FIXTURES.items()}
    fixtures = {name: json.loads((ROOT / path).read_text()) for name, path in FIXTURES.items()}
    original = fixtures["request"]
    require(original["source_authority"]["document"] == fixtures["source"]
            and original["operating_domain"] == fixtures["domain"], "Complete request detached from independent literals")
    output = args.output.absolute()
    require(output.parent.is_dir() and not output.parent.is_symlink() and not output.exists(),
            "Use a fresh campaign receipt in an existing output directory")
    sidecars = output.with_suffix("")
    sidecars.mkdir(exist_ok=False)
    identity = source_identity()
    require(identity["run_id"].isdecimal() and int(identity["run_id"]) > 0
            and int(identity["run_attempt"]) > 0, "Hosted source/run/attempt identity is absent")
    receipt = {"schema_version": "biocompiler.policy_controlled_composition_campaign.v0.1", "status": "incomplete",
        "scope": "fresh_native_original_authority_and_complete_finite_input_domain_only", **identity,
        "platform": platform.system(), "machine": platform.machine(), "python": platform.python_version(),
        "installed": args.require_installed, "binaries": binary_pins, "inputs": fixture_pins,
        "imports": imported_modules(args.require_installed), "campaign_script": file_pin(__file__),
        "observations": [], "behavior": "not_performed", "construction": "not_performed", "empirical": "unassessed"}

    def save():
        output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")

    def observe(name, value):
        index = len(receipt["observations"])
        require(index < len(OBSERVATIONS) and OBSERVATIONS[index] == name, "Campaign observation order/census changed")
        path = sidecars / (name + ".json")
        raw = encode_json(value, limit=16 * 1024 * 1024)
        with path.open("xb") as stream:
            stream.write(raw)
        receipt["observations"].append({"name": name, "path": str(path.relative_to(output.parent)), **file_pin(path)})
        save()

    transports = {role: CoreClient(path, role=role, expected_sha256=binary_pins[role]["sha256"], timeout_seconds=180)
                  for role, path in binaries.items()}
    clients = {role: PolicyControlledCompositionClient(transport) for role, transport in transports.items()}
    try:
        save()
        # Oracles are literal combinatorics, never copied from compiler results.
        for name, request, census in (("baseline", original, (1, 11, 12)),
                                       ("cartesian", cartesian(original), (12, 113, 114))):
            observe(name + "-original", {"request": request, "expected": {
                "histories": census[0], "transitions": census[1], "prefixes": census[2]}})
            results = {}
            for role in ("core", "verify"):
                response = clients[role].admit(request)
                result, report = response.result, response.report
                counts = report["domain_counters"]
                require(tuple(counts[key] for key in ("histories", "transitions", "prefixes")) == census,
                        "Complete original-domain census differs from independent oracle")
                require(result["artifact"] is None and report["stage"] == "admission"
                        and report["behavior_status"] == "not_performed"
                        and report["construction_status"] == "not_performed" and report["empirical_status"] == "unassessed",
                        "Source/domain admission crossed its assurance boundary")
                observe(name + "-" + role, {"request_id": response.request_id, "operation": response.operation,
                    "executable": response.executable, "original_request": request, "result": result})
                results[role] = result
            require(results["core"] == results["verify"], "Core/Verify fresh admission differs")
        for name, request in adversaries(original).items():
            # Direct bounded transport deliberately reaches native ingress even
            # when the public typed helper rejects this shape earlier.
            try:
                transports["verify"].call(OPERATION, {"request": request})
            except CoreRejected as error:
                response = error.response
                require(response.status == "error" and response.result is None
                        and [row.code for row in response.diagnostics] == [NEGATIVE_DIAGNOSTICS[name]],
                        "Negative control failed at another stage: " + name)
                observe(name, {"original_request": request, "status": response.status,
                    "request_id": response.request_id, "operation": response.operation, "executable": response.executable,
                    "diagnostics": [{"code": row.code, "message": row.message, "path": row.path}
                                    for row in response.diagnostics]})
            else:
                raise AssertionError("Native adversary accepted: " + name)
        try:
            clients["verify"].admit(original, cancelled=lambda: True)
        except CoreCancelled:
            observe("transport-cancellation", {"original_request": original, "status": "cancelled",
                "phase": "before_native_launch", "accepted_result": None})
        else:
            raise AssertionError("Cancelled transport published admission")
        require(tuple(row["name"] for row in receipt["observations"]) == OBSERVATIONS, "Incomplete campaign census")
        final_imports = imported_modules(args.require_installed)
        require(all(final_imports["modules"].get(name) == pin for name, pin in receipt["imports"]["modules"].items()),
                "Imported SDK authority changed during execution")
        receipt["imports"] = final_imports
        require({role: file_pin(path, 256 * 1024 * 1024) for role, path in binaries.items()} == binary_pins
                and {name: file_pin(ROOT / path, 4 * 1024 * 1024) for name, path in FIXTURES.items()} == fixture_pins,
                "Original fixture or native authority changed during execution")
        require(file_pin(__file__) == receipt["campaign_script"] and source_identity() == identity,
                "Campaign source or hosted identity changed during execution")
        receipt["status"] = "pass"
    except Exception as error:
        receipt.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        save()
    print(json.dumps({"status": "pass", "observations": len(OBSERVATIONS), "receipt": str(output),
                      "installed": args.require_installed}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--verify", type=Path, required=True)
    parser.add_argument("--core-sha256")
    parser.add_argument("--verify-sha256")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-installed", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
