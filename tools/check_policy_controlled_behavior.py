"""Hosted actual-binary finite controlled behavior campaign.

Every semantic result comes from fresh native construction/checking/replay.
Python only retains identities, exact originals and finite literal assertions;
material joining and empirical qualification remain outside this checkpoint.
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
FIXTURES = {"request": "core/test/data/policy_controlled_behavior_v01.json"}
OBSERVATIONS = (
    "baseline-original", "construct-core", "check-core", "check-verify", "replay-core", "replay-verify",
    "missing-readout-original", "missing-readout-core", "missing-readout-verify",
    "late-model-original", "late-model-core", "late-model-verify",
    "upper-bound-onset-original", "upper-bound-onset-core", "upper-bound-onset-verify",
    "request-binding", "assembly-delay", "assembly-context", "replay-forgery",
    "missing-readout-authority", "future-readout", "request-work-exhaustion",
    "domain-work-exhaustion", "closed-field", "verify-construction", "transport-cancellation",
)
NEGATIVE_DIAGNOSTICS = {
    "request-binding": "controlled_behavior_request_binding",
    "assembly-delay": "controlled_behavior_assembly_binding",
    "assembly-context": "controlled_behavior_assembly_binding",
    "replay-forgery": "controlled_behavior_assessment_mismatch",
    "missing-readout-authority": "missing_field",
    "future-readout": "controlled_behavior_request",
    "request-work-exhaustion": "controlled_behavior_service_work_limit",
    "domain-work-exhaustion": "controlled_domain_exhausted",
    "closed-field": "unknown_field",
    "verify-construction": "unsupported_operation",
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
    require("biocompiler.core_policy_controlled_behavior" in result,
            "Campaign did not import the controlled-behavior transport")
    return {"package": str(package), "modules": result, "record_verified": require_installed}


def missing_readout(original):
    changed = deepcopy(original)
    changed["readout_evidence"]["samples"][3].update(status="missing", observed_tick=None)
    return changed


def late_model(original, onset_ticks=3):
    """Alter only supplied actual onset and its pins; source bound stays two."""
    changed = deepcopy(original)
    authority = changed["original"]
    authority["mechanism_model"]["body"]["delays"]["onset_ticks"] = onset_ticks
    authority["source_authority"]["control_contract"]["actual_delays"]["onset_ticks"] = onset_ticks
    body = json.dumps(authority["mechanism_model"]["body"], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    identity = authority["mechanism_model"]["identity"]
    identity["content_fingerprint"] = hashlib.sha256(body).hexdigest()
    authority["catalog_binding"]["model_identity"] = deepcopy(identity)
    return changed


def adversaries(original, candidate, report):
    """Exact mutations retained with originals; none invokes a Python evaluator."""
    check = "check-policy-controlled-behavior"
    base = {"request": original, "candidate": candidate}
    cases = {name: (check, deepcopy(base)) for name in NEGATIVE_DIAGNOSTICS}
    cases["request-binding"][1]["request"] = missing_readout(original)
    cases["assembly-delay"][1]["candidate"]["implementation"]["primitives"][6]["onset_ticks"] = 3
    cases["assembly-context"][1]["candidate"]["implementation"]["context"]["slot"] = "foreign-slot"
    forged = deepcopy(report); forged["material_status"] = "joined"
    cases["replay-forgery"] = ("replay-policy-controlled-behavior", {**deepcopy(base), "report": forged})
    cases["missing-readout-authority"][1]["request"].pop("readout_evidence")
    cases["future-readout"][1]["request"]["readout_evidence"]["samples"][0]["observed_tick"] = 1
    cases["request-work-exhaustion"][1]["request"]["original"]["budgets"]["max_work"] = 1
    cases["domain-work-exhaustion"][1]["request"]["original"]["operating_domain"]["limits"]["max_work"] = 1
    # Rebind only the outer request pin so native admission reaches the original
    # domain budget instead of stopping at candidate/request identity first.
    raw = json.dumps(cases["domain-work-exhaustion"][1]["request"], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    cases["domain-work-exhaustion"][1]["candidate"]["request_fingerprint"] = hashlib.sha256(raw).hexdigest()
    cases["closed-field"][1]["extra"] = {}
    cases["verify-construction"] = ("construct-policy-controlled-behavior", {"request": deepcopy(original)})
    return cases


def run(args):
    require(os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted",
            "Actual native campaign is hosted-only; local execution needs separate user authorization")
    from biocompiler.core_client import CoreClient, CoreRejected, CoreCancelled, PROTOCOL, encode_json
    from biocompiler.core_policy_controlled_behavior import PolicyControlledBehaviorClient
    from biocompiler.policy.controlled_behavior import ControlledBehaviorRequest, construct_behavior, check_behavior, replay_behavior

    binaries = {role: Path(getattr(args, role)).absolute() for role in ("core", "verify")}
    binary_pins = {role: file_pin(path, 256 * 1024 * 1024) for role, path in binaries.items()}
    for role, path in binaries.items():
        require(os.access(path, os.X_OK), "Selected native path is not executable")
        expected = getattr(args, role + "_sha256")
        require(expected is None or expected == binary_pins[role]["sha256"], "Native bytes differ from external digest")
    fixture_pins = {name: file_pin(ROOT / path, 4 * 1024 * 1024) for name, path in FIXTURES.items()}
    fixtures = {name: json.loads((ROOT / path).read_text()) for name, path in FIXTURES.items()}
    original = fixtures["request"]
    output = args.output.absolute()
    require(output.parent.is_dir() and not output.parent.is_symlink() and not output.exists(),
            "Use a fresh campaign receipt in an existing output directory")
    sidecars = output.with_suffix("")
    sidecars.mkdir(exist_ok=False)
    identity = source_identity()
    require(identity["run_id"].isdecimal() and int(identity["run_id"]) > 0
            and int(identity["run_attempt"]) > 0, "Hosted source/run/attempt identity is absent")
    receipt = {"schema_version": "biocompiler.policy_controlled_behavior_campaign.v0.1", "status": "incomplete",
        "scope": "fresh_native_conditional_behavior_original_model_source_and_complete_domain_only", **identity,
        "platform": platform.system(), "machine": platform.machine(), "python": platform.python_version(),
        "installed": args.require_installed, "binaries": binary_pins, "inputs": fixture_pins,
        "imports": imported_modules(args.require_installed), "campaign_script": file_pin(__file__),
        "observations": [], "material": "not_joined", "therapeutic_export": "withheld", "empirical": "unassessed"}

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

    decoded_responses = {}

    class RecordingClient(CoreClient):
        """Retain every field of actual decoded native responses, without replacement."""
        def call(self, operation, payload, **kwargs):
            try:
                response = super().call(operation, payload, **kwargs)
            except CoreRejected as error:
                response = error.response
                decoded_responses[(self.role, response.request_id)] = response
                raise
            decoded_responses[(self.role, response.request_id)] = response
            return response

    def response_evidence(response):
        actual = decoded_responses[(response.executable, response.request_id)]
        frame = {"protocol": PROTOCOL, "request_id": actual.request_id, "operation": actual.operation,
            "status": actual.status, "result": actual.result,
            "diagnostics": [{"code": row.code, "message": row.message, "path": row.path} for row in actual.diagnostics],
            "core": {"implementation": "ocaml", "version": actual.version, "protocol": PROTOCOL, "executable": actual.executable}}
        raw = encode_json(frame, limit=16 * 1024 * 1024)
        return {"status": actual.status, "canonical_decoded_response": frame,
                "canonical_decoded_response_sha256": hashlib.sha256(raw).hexdigest(),
                "canonical_decoded_response_bytes": len(raw),
                "response_pin_scope": "canonical_complete_decoded_native_response_not_raw_transport_whitespace"}

    transports = {role: RecordingClient(path, role=role, expected_sha256=binary_pins[role]["sha256"], timeout_seconds=180)
                  for role, path in binaries.items()}
    clients = {role: PolicyControlledBehaviorClient(transport) for role, transport in transports.items()}
    try:
        save()
        expected_census = {"histories": 2, "transitions": 20, "prefixes": 21}
        observe("baseline-original", {"request": original, "expected_census": expected_census,
            "expected_scope": "conditional_behavior_only"})
        typed = ControlledBehaviorRequest.from_request(original)
        built = construct_behavior(typed, client=clients["core"])
        candidate = built.candidate

        def retained(name, request, response):
            result, report = response.result, response.report
            require(result["artifact"] is None and report["stage"] == "behavior"
                    and report["material_status"] == "not_joined" and report["empirical_status"] == "unassessed"
                    and report["human_use"] == "unassessed" and report["therapeutic_export"] == "withheld",
                    "Behavior checkpoint crossed material or empirical boundaries")
            require(report["domain"]["completion"] == "complete"
                    and all(report["domain"]["counters"][key] == value for key, value in expected_census.items()),
                    "Full two-history exploration changed independent literal census")
            observe(name, {"request_id": response.request_id, "operation": response.operation,
                "executable": response.executable, "original_request": request, "result": result, **response_evidence(response)})

        require(built.report["status"] == "checked_controlled_behavior" and built.report["outcome"] == "pass"
                and all(built.report["coverage"].values()), "Literal reversible behavior lacks complete non-vacuous acceptance")
        retained("construct-core", original, built)
        checked = {}
        for role in ("core", "verify"):
            checked[role] = check_behavior(typed, candidate=candidate, client=clients[role])
            retained("check-" + role, original, checked[role])
            require(checked[role].report == built.report, "Independent checker changed constructor's fresh report")
        require(checked["core"].result == checked["verify"].result, "Core/Verify checking differs")
        for role in ("core", "verify"):
            replayed = replay_behavior(typed, candidate=candidate, report=built.report, client=clients[role])
            retained("replay-" + role, original, replayed)
            require(replayed.report == built.report, "Fresh replay changed complete saved assessment")
        for name, request, expected in (("missing-readout", missing_readout(original), "unknown"),
                                        ("late-model", late_model(original), "fail"),
                                        ("upper-bound-onset", late_model(original, onset_ticks=10000), "fail")):
            observe(name + "-original", {"request": request, "expected_outcome": expected})
            altered = ControlledBehaviorRequest.from_request(request)
            produced = construct_behavior(altered, client=clients["core"])
            verified = check_behavior(altered, candidate=produced.candidate, client=clients["verify"])
            require(produced.report == verified.report and verified.report["status"] == "not_accepted"
                    and verified.report["outcome"] == expected and verified.report["model_correspondence"] == "pass",
                    "Fresh altered authority did not fail at its intended semantic layer: " + name)
            if name == "missing-readout":
                require(verified.report["evidence_status"] == "unknown", "Missing evidence became false/background")
            else:
                onset = next(row for row in verified.report["requirements"] if row["id"] == "onset")
                require(onset["fail"] > 0 and verified.report["counterexample"] is not None,
                        "Actual delay did not retain the original source deadline failure and witness")
            if name == "upper-bound-onset":
                witness = verified.report["counterexample"]
                trace = witness["trace"]
                require(verified.report["domain"]["pending_at_horizon"] is True
                        and witness["pending_at_horizon"] is True
                        and len(trace) == 11 and len(witness["source_monitor"]["history"]) == 11,
                        "Upper-bound delay lost its complete pending horizon witness")
                require(all(frame["input"]["tick"] == tick
                            and frame["candidate"] == {"tick": tick, "band": "background", "activation_generation": None}
                            and frame["model_reference"] == frame["candidate"]
                            for tick, frame in enumerate(trace))
                        and verified.report["coverage"]["active"] is False,
                        "Upper-bound actual onset produced activity inside the unchanged horizon")
            retained(name + "-core", request, produced)
            retained(name + "-verify", request, verified)
        for name, (operation, payload) in adversaries(original, candidate, built.report).items():
            try:
                transports["verify"].call(operation, payload)
            except CoreRejected as error:
                response = error.response
                expected_status = "unsupported" if name == "verify-construction" else "error"
                require(response.status == expected_status and response.result is None
                        and [row.code for row in response.diagnostics] == [NEGATIVE_DIAGNOSTICS[name]],
                        "Negative control failed at another stage: " + name)
                observe(name, {"payload": payload, "status": response.status, "request_id": response.request_id,
                    "operation": response.operation, "executable": response.executable,
                    "diagnostics": [{"code": row.code, "message": row.message, "path": row.path} for row in response.diagnostics],
                    **response_evidence(response)})
            else:
                raise AssertionError("Native adversary accepted: " + name)
        try:
            clients["verify"].check_behavior(original, candidate, cancelled=lambda: True)
        except CoreCancelled:
            observe("transport-cancellation", {"original_request": original, "candidate": candidate,
                "status": "cancelled", "phase": "before_native_launch", "accepted_result": None})
        else:
            raise AssertionError("Cancelled transport published behavioral acceptance")
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
