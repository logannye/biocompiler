"""Hosted actual-binary quantitative assurance SDK campaign.

Runs from source or the installed SDK, retaining complete originals and results.
It does not build native code or turn supplied model/measurement claims into
empirical function evidence. Installed mode authenticates every imported SDK
source file against its actual distribution RECORD.
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
    "approximation": "core/test/data/policy_approximation_v01.json",
    "network": "core/test/data/policy_quantitative_network_v01.json",
    "evidence": "core/test/data/policy_realization_evidence_v01.json",
    "coupled": "core/test/data/policy_quantitative_composition_v01.json",
}
OBSERVATIONS = tuple(name + "-" + operation for name in ("approximation", "evidence", "coupled")
                     for operation in ("originals", "compile", "check", "replay", "export")) + (
    "cumulative-budget", "insufficient-error-bound", "failed-bound-export", "retained-pass-mutation",
    "verifier-production-role", "missing-gated-evidence",
)
NEGATIVE_DIAGNOSTICS = {
    "cumulative-budget": ("error", "policy_quantitative_assurance_work_limit"),
    "failed-bound-export": ("error", "policy_quantitative_assurance_export_not_accepted"),
    "retained-pass-mutation": ("error", "policy_quantitative_assurance_replay"),
    "verifier-production-role": ("unsupported", "unsupported_operation"),
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
            require(record is not None and record.hash is not None and record.hash.mode == "sha256" and record.size == pin["bytes"],
                    "Imported SDK file lacks its complete actual installed RECORD")
            encoded = base64.urlsafe_b64encode(bytes.fromhex(pin["sha256"])).decode().rstrip("=")
            require(record.hash.value == encoded, "Imported SDK source differs from actual installed RECORD")
        result[name] = {"path": str(path), **pin}
    require("biocompiler.core_policy_quantitative_assurance" in result and "biocompiler.policy.approximation" in result,
            "Campaign did not import the quantitative SDK")
    return {"package": str(package), "modules": result, "record_verified": require_installed}


def original_cases(fixtures):
    from biocompiler.core_policy_quantitative_assurance import MAX_WORK, REQUEST_SCHEMA, REQUEST_PROFILE
    from biocompiler.policy.approximation import ApproximationContract
    from biocompiler.policy.quantitative_assurance import QuantitativeAssuranceRequest
    approximation = fixtures["approximation"]
    typed = QuantitativeAssuranceRequest(approximation["material_request"], approximation=ApproximationContract.from_data(approximation["approximation"]))
    def wrapper(material_request, numerical=None, evidence=None):
        return {"schema_version": REQUEST_SCHEMA, "profile": REQUEST_PROFILE, "material_request": material_request,
            "approximation": numerical, "realization_evidence": evidence, "max_work": MAX_WORK}
    coupled = fixtures["coupled"]
    network = coupled["request"]["quantitative"]["network"]["mechanism"]
    names = [row["compartment"] for row in network["reservoirs"]]
    endpoint = {"mechanism": network, "observation": names}
    zero = {"numerator": "0", "denominator": "1", "unit": network["unit"]}
    identity = {"schema_version": "biocompiler.policy_approximation_contract.v0.1",
        "profile": "biocompiler.policy_bounded_sampled_network_approximation.v0.1",
        "horizon_steps": coupled["request"]["implementation_request"]["operating_domain"]["horizon_ticks"] + 1,
        "metric": "coordinatewise_absolute_prefix_error", "coordinates": names, "unit": network["unit"], "maximum_error": zero,
        "links": [{"id": "coupled_identity", "source": endpoint, "target": endpoint, "uncertainty": [], "maximum_error": zero}]}
    coupled_typed = QuantitativeAssuranceRequest(coupled["request"], approximation=ApproximationContract.from_data(identity))
    return [
        ("approximation", typed.to_data(), approximation["limits"], approximation["expected"]["sequence"]),
        ("evidence", wrapper(fixtures["network"]["request"], evidence=fixtures["evidence"]["contract"]), fixtures["network"]["limits"], fixtures["network"]["expected"]["sequence"]),
        ("coupled", coupled_typed.to_data(), coupled["limits"], coupled["expected"]["sequence"]),
    ]


def run(args):
    require(os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted",
            "Actual native campaign is hosted-only; local execution requires separate user authorization")
    from biocompiler.core_client import CoreClient, CoreRejected, encode_json
    from biocompiler.core_policy_quantitative_assurance import (
        PolicyQuantitativeAssuranceClient,
    )
    digest = lambda value: hashlib.sha256(encode_json(value)).hexdigest()
    binaries = {role: Path(getattr(args, role)).absolute() for role in ("core", "verify")}
    binary_pins = {role: file_pin(path, 256 * 1024 * 1024) for role, path in binaries.items()}
    for role, path in binaries.items():
        require(os.access(path, os.X_OK), "Selected native path is not executable")
        expected = getattr(args, role + "_sha256")
        require(expected is None or expected == binary_pins[role]["sha256"], "Selected native bytes differ from external digest")
    fixtures = {name: json.loads((ROOT / path).read_text()) for name, path in FIXTURES.items()}
    fixture_pins = {name: file_pin(ROOT / path, 4 * 1024 * 1024) for name, path in FIXTURES.items()}
    require(fixtures["evidence"]["material_fixture_fingerprint"] == digest(fixtures["network"]),
            "Evidence criterion detached from the independent network original")
    cases = original_cases(fixtures)
    output = args.output.absolute()
    require(output.parent.is_dir() and not output.parent.is_symlink() and not output.exists(), "Use a fresh campaign receipt in an existing output directory")
    sidecars = output.with_suffix("")
    sidecars.mkdir(exist_ok=False)
    identity = source_identity()
    receipt = {"schema_version": "biocompiler.policy_quantitative_assurance_campaign.v0.1", "status": "incomplete",
        "scope": "fresh_native_quantitative_assurance_sdk_with_exact_rna", **identity,
        "platform": platform.system(), "machine": platform.machine(), "python": platform.python_version(),
        "installed": args.require_installed, "binaries": binary_pins, "inputs": fixture_pins,
        "imports": imported_modules(args.require_installed), "campaign_script": file_pin(__file__),
        "observations": [], "empirical_function": "unassessed"}
    require(all(receipt[key] for key in ("revision", "run_id", "run_attempt")), "Hosted source/run identity is absent")

    def save():
        output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")

    def retain(name, value):
        require(name not in {row["name"] for row in receipt["observations"]}, "Duplicate observation identity")
        path = sidecars / (name + ".json")
        raw = encode_json(value, limit=32 * 1024 * 1024)
        with path.open("xb") as stream:
            stream.write(raw)
        receipt["observations"].append({"name": name, "path": str(path.relative_to(output.parent)), **file_pin(path)})
        save()

    core_transport = CoreClient(binaries["core"], role="core", expected_sha256=binary_pins["core"]["sha256"], timeout_seconds=180)
    verify_transport = CoreClient(binaries["verify"], role="verify", expected_sha256=binary_pins["verify"]["sha256"], timeout_seconds=180)
    core = PolicyQuantitativeAssuranceClient(core_transport)
    verify = PolicyQuantitativeAssuranceClient(verify_transport)
    def observe(name, value):
        index = len(receipt["observations"])
        require(index < len(OBSERVATIONS) and name == OBSERVATIONS[index], "Campaign observation order changed")
        retain(name, value)

    def rejected(name, action):
        try:
            action()
        except CoreRejected as error:
            require(error.response.result is None and bool(error.response.diagnostics), "Native rejection lacked complete diagnostics")
            status, code = NEGATIVE_DIAGNOSTICS[name]
            require(error.response.status == status and [row.code for row in error.response.diagnostics] == [code],
                    "Native negative control failed for a different reason: " + name)
            observe(name, {"status": error.response.status, "operation": error.response.operation,
                "executable": error.response.executable, "diagnostics": [{"code": row.code, "message": row.message} for row in error.response.diagnostics]})
        else:
            raise AssertionError("Native adversary accepted: " + name)

    checked_cases = {}
    try:
        for name, original, limits, sequence in cases:
            observe(name + "-originals", {"request": original, "limits": limits, "expected_sequence": sequence})
            compiled = core.compile(original, limits)
            observe(name + "-compile", compiled.result)
            checked = verify.check(original, compiled.candidate, limits)
            observe(name + "-check", checked.result)
            require(checked.export_permitted and checked.report["material"]["status"] == "checked_component_material", "Complete material or requested assurance was withheld")
            require(compiled.result == checked.result, "Producer and independently checked complete evidence differ")
            replayed = verify.replay(original, checked.candidate, limits, checked.result)
            observe(name + "-replay", replayed.result)
            require(replayed.result == checked.result, "Fresh replay changed retained complete original evidence")
            exported = verify.export(original, checked.candidate, limits)
            observe(name + "-export", exported.result)
            artifact = exported.result["artifact"]
            actual_sequence = "".join(line for line in artifact["fasta"].splitlines() if not line.startswith(">"))
            require(actual_sequence == sequence and artifact["manifest"]["request"] == original and artifact["manifest"]["assessment"] == exported.report,
                    "Export differs from independent exact RNA or complete original assurance")
            require(exported.report["empirical_function"] == "unassessed", "Export promoted empirical function")
            if name == "evidence":
                require(checked.report["realization_evidence"]["status"] == "supported" and checked.report["realization_evidence"]["empirical"] == "unassessed", "Supplied synthetic criterion crossed its evidence boundary")
            else:
                require(checked.report["approximation"]["outcome"] == "pass", "Bounded numerical proof missing")
                expected_maximum = "1" if name == "approximation" else "0"
                require(checked.report["approximation"]["composition"]["maximum_error"]["numerator"] == expected_maximum, "Independent approximation error oracle changed")
            checked_cases[name] = checked
        original, limits = cases[0][1:3]
        candidate = checked_cases["approximation"].candidate
        low_work = deepcopy(original)
        low_work["max_work"] = 1
        rejected("cumulative-budget", lambda: verify.check(low_work, candidate, limits))
        too_tight = deepcopy(original)
        too_tight["approximation"]["maximum_error"]["numerator"] = "0"
        failed = verify.check(too_tight, candidate, limits)
        observe("insufficient-error-bound", failed.result)
        require(not failed.export_permitted and failed.report["approximation"]["outcome"] == "fail" and failed.report["material"]["status"] == "checked_component_material",
                "Numerical bound failure changed exact material or retained export authority")
        rejected("failed-bound-export", lambda: verify.export(too_tight, candidate, limits))
        forged = deepcopy(checked_cases["approximation"].result)
        forged["report"]["approximation"]["composition"]["maximum_error"]["numerator"] = "0"
        rejected("retained-pass-mutation", lambda: verify.replay(original, candidate, limits, forged))
        rejected("verifier-production-role", lambda: verify_transport.call("compile-policy-quantitative-assurance", {"request": original, "limits": limits}))
        unassessed = deepcopy(cases[1][1])
        unassessed["realization_evidence"]["dossier"] = None
        unassessed["realization_evidence"]["require_compatibility"] = True
        missing = verify.check(unassessed, checked_cases["evidence"].candidate, cases[1][2])
        observe("missing-gated-evidence", missing.result)
        require(not missing.export_permitted and missing.report["realization_evidence"]["status"] == "unassessed" and missing.report["material"]["status"] == "checked_component_material",
                "Missing supplied evidence changed exact material or ignored explicit gate")
        require(tuple(row["name"] for row in receipt["observations"]) == OBSERVATIONS,
                "Incomplete actual-binary campaign observation census")
        final_imports = imported_modules(args.require_installed)
        require(all(final_imports["modules"].get(name) == value for name, value in receipt["imports"]["modules"].items()),
                "Previously imported SDK bytes changed during the campaign")
        receipt["imports"] = final_imports
        require({role: file_pin(path, 256 * 1024 * 1024) for role, path in binaries.items()} == binary_pins and
                {name: file_pin(ROOT / path, 4 * 1024 * 1024) for name, path in FIXTURES.items()} == fixture_pins,
                "Native or original fixture authority changed during the campaign")
        require(file_pin(__file__) == receipt["campaign_script"] and source_identity() == identity,
                "Campaign source or hosted identity changed during execution")
        receipt["status"] = "pass"
    except Exception as error:
        receipt.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        save()
    print(json.dumps({"status": "pass", "observations": len(OBSERVATIONS), "receipt": str(output), "installed": args.require_installed}))


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
