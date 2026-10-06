"""Hosted installed bounded-implementation campaign and four-slot comparison.

Only explicit, already-built native executables interpret policy semantics.
Comparison reads complete retained evidence and independently pinned inputs.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys
import tempfile

try:
    from check_policy_core import (ImportBoundary, canonical_digest, digest_file, native_manifests,
                                   read_json, run_bounded, source_identity)
except ModuleNotFoundError:
    from tools.check_policy_core import (ImportBoundary, canonical_digest, digest_file, native_manifests,
                                         read_json, run_bounded, source_identity)

SCHEMA = "biocompiler.policy_implementation_campaign.v0.1"
FIXTURE_SCHEMA = "biocompiler.policy_implementation_request_fixture.v0.1"
CASE_NAMES = (
    "compile", "check-core", "check-verify", "replay-verify", "unknown-compile", "unknown-check",
    "changed-guard", "changed-behavior", "changed-source", "changed-source-span", "changed-domain",
    "prefix-limit", "source-work-limit", "work-limit", "changed-budget-replay", "forged-rehashed-replay",
    "verify-producer", "missing-binary", "wrong-role", "compile-cli", "check-cli", "replay-cli", "malformed-replay-cli",
)
CLI_CASES = ("compile-cli", "check-cli", "replay-cli", "malformed-replay-cli")
NEGATIVE_CODES = {
    "changed-guard": {"policy_implementation_source_binding"},
    "changed-behavior": {"policy_correspondence"},
    "changed-source": {"policy_correspondence"},
    "changed-source-span": {"policy_correspondence"},
    "changed-domain": {"policy_implementation_contract"},
    "work-limit": {"policy_preservation_publication_work_limit"},
    "changed-budget-replay": {"policy_implementation_replay"},
    "forged-rehashed-replay": {"policy_implementation_replay"},
    "verify-producer": {"unsupported_operation"},
}
EXPECTED = {
    "status": "checked_implementation", "histories": 9, "transitions": 47, "prefixes": 48,
    "created_attempts": 2, "active_prefixes": 6, "inactive_prefixes": 41,
    "requirements": {"request_progress": "pass", "initiation_progress": "pass", "exclusive_selection": "pass"},
    "safety_samples": 126, "safety_active": 24, "safety_inactive": 102,
}
UNKNOWN_EXPECTED = {
    "status": "requirements_not_satisfied", "preservation": "pass", "histories": 1, "transitions": 5, "prefixes": 6,
    "requirements": {"request_progress": "pass", "initiation_progress": "pass", "request_authorization": "pass",
                     "scoped_memory": "unknown"},
}


class ImplementationBoundary(ImportBoundary):
    """Extend transport access without changing any legacy campaign guard."""

    @staticmethod
    def allowed(name: str) -> bool:
        return name in {"biocompiler.core_policy_implementation", "biocompiler.core_policy_operational"} or ImportBoundary.allowed(name)


def checked_fixture(path: Path) -> dict:
    value = read_json(path)
    if (type(value) is not dict or set(value) != {"schema_version", "claim_scope", "request", "limits", "expected", "unknown_control"}
            or value["schema_version"] != FIXTURE_SCHEMA or type(value["claim_scope"]) is not str
            or any(type(value[key]) is not dict for key in ("request", "limits", "expected", "unknown_control"))
            or set(value["unknown_control"]) != {"request", "expected"}
            or type(value["unknown_control"]["request"]) is not dict
            or canonical_digest(value["expected"]) != canonical_digest(EXPECTED)
            or canonical_digest(value["unknown_control"]["expected"]) != canonical_digest(UNKNOWN_EXPECTED)):
        raise AssertionError("Incomplete independently authored implementation request/census fixture")
    return value


def check_literals(report: dict, *, unknown: bool = False) -> None:
    expected = UNKNOWN_EXPECTED if unknown else EXPECTED
    coverage = report["coverage"]
    actual = {"status": report["status"], "histories": coverage["histories"], "transitions": coverage["transitions"],
              "prefixes": coverage["prefixes_started"], "requirements": {row["id"]: row["status"] for row in report["requirements"]}}
    if unknown:
        actual["preservation"] = report["preservation"]
    else:
        actual.update({key: report["program_coverage"][key] for key in ("created_attempts", "active_prefixes", "inactive_prefixes")})
        safety = next(row for row in report["requirements"] if row["id"] == "exclusive_selection")["coverage"]
        actual.update({"safety_" + key: safety[key] for key in ("samples", "active", "inactive")})
    if canonical_digest(actual) != canonical_digest(expected):
        raise AssertionError("Independent implementation history/prefix/nonvacuity/requirement census differs")


def changed_guard(candidate: dict) -> dict:
    changed = deepcopy(candidate)
    rules = {row["source"]: row for row in changed["binding"]["rules"]}
    wires = changed["implementation"]["wires"]
    positive = next(row for row in wires if row["consumer"] == {"node": rules["select"]["gate"], "port": "guard"})
    negative = next(row for row in wires if row["consumer"] == {"node": rules["exclude"]["gate"], "port": "guard"})
    positive["producer"] = deepcopy(negative["producer"])
    return changed


def changed_request(request: dict, kind: str) -> dict:
    changed = deepcopy(request)
    if kind == "source":
        parameter = next(row for row in changed["document"]["program"]["declarations"] if row["$type"] == "Parameter")
        parameter["value"] = "fixture.product.beta"
    elif kind == "span":
        changed["document"]["program"]["source_map"][0]["file"] = "changed-source.py"
    elif kind == "domain":
        changed["operating_domain"]["fixed_observations"][0]["value"] = True
    elif kind == "prefix":
        changed["budgets"]["max_prefixes"] = 1
    elif kind == "work":
        changed["budgets"]["max_work"] = 1
    else:
        raise AssertionError("Unknown installed negative-control recipe")
    return changed


def source_work_limits(limits: dict) -> dict:
    changed = deepcopy(limits)
    changed["source"]["max_work"] = 1
    return changed


def check_import_origins(origins: dict, package: str, required: set[str]) -> None:
    if (type(package) is not str or not Path(package).is_absolute() or ".." in Path(package).parts
            or type(origins) is not dict or not required <= set(origins)):
        raise AssertionError("Missing installed implementation transport or CLI guard evidence")
    for name, path in origins.items():
        if (not ImplementationBoundary.allowed(name) or type(path) is not str or not Path(path).is_absolute()
                or ".." in Path(path).parts or not Path(path).is_relative_to(package)):
            raise AssertionError("Forbidden or foreign installed Python semantic authority")


def check_cli_guard(guard: dict, package: str, python_version: str) -> None:
    if (type(guard) is not dict or set(guard) != {"status", "guard_active", "execution_guard_active", "python", "executable", "origins"}
            or guard["status"] != "ok" or guard["guard_active"] is not True or guard["execution_guard_active"] is not True
            or guard["python"] != [int(part) for part in python_version.split(".")[:2]]
            or type(guard["executable"]) is not str or not Path(guard["executable"]).is_absolute()):
        raise AssertionError("Installed implementation CLI guard did not complete on its declared interpreter")
    check_import_origins(guard["origins"], package,
                         {"biocompiler.entrypoint", "biocompiler.policy.cli", "biocompiler.core_policy_implementation"})


def check_cli_error(returncode: int, stdout: bytes, stderr: bytes, command: str, diagnostic: str) -> dict:
    from biocompiler.core_client import CoreError, decode_json

    if returncode != 2 or stdout:
        raise AssertionError("Corrupt implementation CLI authority did not fail closed with status 2")
    try:
        value = decode_json(stderr)
    except CoreError as error:
        raise AssertionError("Corrupt implementation CLI returned malformed diagnostic JSON") from error
    if (type(value) is not dict or set(value) != {"status", "operation", "message"}
            or value["status"] != "error" or value["operation"] != command or type(value["message"]) is not str
            or not value["message"].startswith(diagnostic + ":")):
        raise AssertionError("Corrupt implementation CLI failed for an unrelated reason")
    return value


def checked_output(result: dict, operation: str, payload: dict, role: str) -> dict:
    from biocompiler.core_client import CORE_VERSION, CoreError, CoreResponse
    from biocompiler.core_policy_implementation import _result

    try:
        return _result(CoreResponse("retained-implementation", operation, "ok", result, (), role, CORE_VERSION), payload).result
    except CoreError as error:
        raise AssertionError("Retained implementation output lost complete independent authority") from error


def check_cli_success(returncode: int, stdout: bytes, stderr: bytes, command: str,
                      expected: dict, payload: dict, role: str) -> dict:
    from biocompiler.core_client import CoreError, decode_json, encode_json

    operation = {"compile-implementation-native": "compile-policy-implementation",
                 "check-implementation-native": "check-policy-implementation",
                 "replay-implementation-native": "replay-policy-implementation"}[command]
    try:
        actual = decode_json(stdout)
        retained = checked_output(actual, operation, payload, role)
    except (CoreError, AssertionError) as error:
        raise AssertionError("Installed implementation CLI changed its complete returned authority") from error
    expected_code = int(retained["report"]["status"] != "checked_implementation")
    if returncode != expected_code or stderr or encode_json(actual) != encode_json(expected):
        raise AssertionError("Installed implementation CLI differs from complete SDK output")
    return retained


def check_observations(observations: list, fixture: dict) -> None:
    if (type(observations) is not list or any(type(row) is not dict or set(row) != {"name", "result"} for row in observations)
            or [row["name"] for row in observations] != list(CASE_NAMES)):
        raise AssertionError("Implementation campaign observations changed or incomplete")
    outputs = {row["name"]: row["result"] for row in observations}
    request, limits = fixture["request"], fixture["limits"]
    candidate = outputs["compile"]["candidate"]
    payload = {"request": request, "candidate": candidate, "limits": limits}
    unknown = {"request": fixture["unknown_control"]["request"], "limits": limits}
    for name, operation, supplied, role in (
        ("compile", "compile-policy-implementation", {"request": request, "limits": limits}, "core"),
        ("check-core", "check-policy-implementation", payload, "core"),
        ("check-verify", "check-policy-implementation", payload, "verify"),
        ("replay-verify", "replay-policy-implementation", {**payload, "report": outputs["check-verify"]}, "verify"),
        ("unknown-compile", "compile-policy-implementation", unknown, "core"),
        ("unknown-check", "check-policy-implementation", {**unknown, "candidate": outputs["unknown-compile"]["candidate"]}, "verify"),
        ("prefix-limit", "check-policy-implementation", {**payload, "request": changed_request(request, "prefix")}, "verify"),
        ("source-work-limit", "check-policy-implementation", {**payload, "limits": source_work_limits(limits)}, "verify"),
        ("compile-cli", "compile-policy-implementation", {"request": request, "limits": limits}, "core"),
        ("check-cli", "check-policy-implementation", payload, "verify"),
        ("replay-cli", "replay-policy-implementation", {**payload, "report": outputs["check-verify"]}, "verify"),
    ):
        checked_output(outputs[name], operation, supplied, role)
    for name in ("check-core", "check-verify", "replay-verify", "compile-cli", "check-cli", "replay-cli"):
        if canonical_digest(outputs[name]) != canonical_digest(outputs["compile"]):
            raise AssertionError("Complete Core/Verify/replay/installed CLI implementation results differ")
    if canonical_digest(outputs["unknown-compile"]) != canonical_digest(outputs["unknown-check"]):
        raise AssertionError("Original UNKNOWN source changed under standalone verification")
    check_literals(outputs["compile"]["report"])
    check_literals(outputs["unknown-compile"]["report"], unknown=True)
    for name, code in (("prefix-limit", "policy_preservation_prefix_limit"), ("source-work-limit", "policy_execution_work_limit")):
        report = outputs[name]["report"]
        if (report["status"] != "incomplete" or report["coverage"]["complete"] is not False
                or report["stopped"]["category"] != "incomplete" or report["stopped"]["diagnostic"]["code"] != code):
            raise AssertionError("Resource control did not retain its exact incomplete disposition: " + name)
    for name, codes in NEGATIVE_CODES.items():
        error = outputs[name]
        expected_status = "unsupported" if name == "verify-producer" else "error"
        if (type(error) is not dict or set(error) != {"status", "diagnostics"} or error["status"] != expected_status
                or type(error["diagnostics"]) is not list or not error["diagnostics"]
                or any(type(row) is not dict or set(row) != {"code", "message", "path"}
                       or type(row["code"]) is not str or type(row["message"]) is not str
                       or row["path"] is not None and type(row["path"]) is not str for row in error["diagnostics"])
                or not codes.intersection(row["code"] for row in error["diagnostics"])):
            raise AssertionError("Implementation negative control lacks its specific native rejection: " + name)
    for name, error_type in (("missing-binary", "CoreUnavailable"), ("wrong-role", "CoreProtocolError")):
        if outputs[name] != {"status": "transport_error", "type": error_type}:
            raise AssertionError("Implementation transport failure acquired fallback authority: " + name)
    check_cli_error(2, b"", json.dumps(outputs["malformed-replay-cli"]).encode(),
                    "replay-implementation-native", "policy_implementation_replay")


def run(args: argparse.Namespace) -> dict:
    checkout = Path(__file__).resolve().parents[1]
    spec = importlib.util.find_spec("biocompiler")
    if spec is None or spec.origin is None:
        raise AssertionError("Install biocompiler before running the hosted implementation campaign")
    package = Path(spec.origin).resolve().parent
    if package.is_relative_to(checkout) or Path.cwd().resolve().is_relative_to(checkout):
        raise AssertionError("Installed campaign requires a non-editable package and working directory outside checkout")
    boundary = ImplementationBoundary(package)
    sys.meta_path.insert(0, boundary)
    sys.setprofile(boundary.trace)
    from biocompiler.core_client import CoreClient, CoreProtocolError, CoreRejected, CoreUnavailable
    from biocompiler.core_policy_implementation import PolicyImplementationClient

    fixture = checked_fixture(args.fixture)
    request, limits = fixture["request"], fixture["limits"]
    core_path, verify_path = args.core.resolve(strict=True), args.verify.resolve(strict=True)
    binary_pins = {"biocompiler-core": digest_file(core_path), "biocompiler-verify": digest_file(verify_path)}
    core = PolicyImplementationClient(CoreClient(core_path, role="core", expected_sha256=binary_pins["biocompiler-core"]))
    verify_transport = CoreClient(verify_path, role="verify", expected_sha256=binary_pins["biocompiler-verify"])
    verify = PolicyImplementationClient(verify_transport)
    observations = []

    def retain(name: str, result: object) -> None:
        observations.append({"name": name, "result": result})

    def rejects(name: str, action) -> None:
        try:
            action()
        except CoreRejected as error:
            if error.response.result is not None or not error.response.diagnostics:
                raise AssertionError("Native rejection retained success authority")
            retain(name, {"status": error.response.status,
                          "diagnostics": [{"code": row.code, "message": row.message, "path": row.path}
                                          for row in error.response.diagnostics]})
        else:
            raise AssertionError("Expected native implementation rejection: " + name)

    def transport_rejects(name: str, error_type, action) -> None:
        try:
            action()
        except error_type as error:
            retain(name, {"status": "transport_error", "type": type(error).__name__})
        else:
            raise AssertionError("Transport control unexpectedly acquired implementation authority: " + name)

    compiled = core.compile(request, limits)
    candidate = compiled.candidate
    retain("compile", compiled.result)
    retain("check-core", core.check(request, candidate, limits).result)
    checked = verify.check(request, candidate, limits)
    retain("check-verify", checked.result)
    retain("replay-verify", verify.replay(request, candidate, limits, checked.result).result)
    unknown_request = fixture["unknown_control"]["request"]
    unknown = core.compile(unknown_request, limits)
    retain("unknown-compile", unknown.result)
    retain("unknown-check", verify.check(unknown_request, unknown.candidate, limits).result)
    rejects("changed-guard", lambda: verify.check(request, changed_guard(candidate), limits))
    behavior = deepcopy(candidate)
    behavior["behavior"]["nodes"].pop()
    rejects("changed-behavior", lambda: verify.check(request, behavior, limits))
    for name, kind in (("changed-source", "source"), ("changed-source-span", "span"), ("changed-domain", "domain")):
        rejects(name, lambda kind=kind: verify.check(changed_request(request, kind), candidate, limits))
    limited_request = changed_request(request, "prefix")
    retain("prefix-limit", verify.check(limited_request, candidate, limits).result)
    retain("source-work-limit", verify.check(request, candidate, source_work_limits(limits)).result)
    rejects("work-limit", lambda: verify.check(changed_request(request, "work"), candidate, limits))
    rejects("changed-budget-replay", lambda: verify.replay(limited_request, candidate, limits, checked.result))
    forged = deepcopy(checked.result)
    forged["report"]["material"] = "produced"
    forged["report_fingerprint"] = canonical_digest(forged["report"])
    rejects("forged-rehashed-replay", lambda: verify.replay(request, candidate, limits, forged))
    rejects("verify-producer", lambda: verify_transport.call("compile-policy-implementation", {"request": request, "limits": limits}))
    with tempfile.TemporaryDirectory(prefix="policy-implementation-cli-") as temporary:
        directory = Path(temporary)
        missing = PolicyImplementationClient(CoreClient(directory / "missing-core", role="core"))
        transport_rejects("missing-binary", CoreUnavailable, lambda: missing.compile(request, limits))
        wrong_role = PolicyImplementationClient(CoreClient(verify_path, role="core", expected_sha256=binary_pins["biocompiler-verify"]))
        transport_rejects("wrong-role", CoreProtocolError, lambda: wrong_role.compile(request, limits))
        for name, value in (("request", request), ("limits", limits), ("candidate", candidate), ("report", checked.result)):
            (directory / (name + ".json")).write_text(json.dumps(value), encoding="utf-8")
        guard_receipt = directory / "guard.json"
        (directory / "sitecustomize.py").write_text(
            "import sys, atexit\nsys.path.insert(0," + repr(str(Path(__file__).resolve().parent)) + ")\n"
            "from check_policy_implementation import ImplementationBoundary\nfrom pathlib import Path\n"
            "boundary=ImplementationBoundary(Path(" + repr(str(package)) + "), Path(" + repr(str(guard_receipt)) + "))\n"
            "sys.meta_path.insert(0,boundary)\nsys.setprofile(boundary.trace)\natexit.register(boundary.finish)\n", encoding="utf-8")
        env = {**os.environ, "PYTHONPATH": str(directory), "PYTHONDONTWRITEBYTECODE": "1"}
        cli_guards = {}
        for name, command, role in (
            ("compile-cli", "compile-implementation-native", "core"),
            ("check-cli", "check-implementation-native", "verify"),
            ("replay-cli", "replay-implementation-native", "verify"),
            ("malformed-replay-cli", "replay-implementation-native", "verify"),
        ):
            if name == "malformed-replay-cli":
                (directory / "report.json").write_text(json.dumps(checked.report), encoding="utf-8")
            binary = core_path if role == "core" else verify_path
            argv = [str(args.console), "policy", command, str(directory / "request.json"),
                    "--limits", str(directory / "limits.json"), "--" + role, str(binary),
                    "--expected-sha256", binary_pins["biocompiler-" + role]]
            payload = {"request": request, "limits": limits}
            if role == "verify":
                argv += ["--candidate", str(directory / "candidate.json")]
                payload["candidate"] = candidate
            if "replay" in name:
                argv += ["--report", str(directory / "report.json")]
                payload["report"] = checked.result
            guard_receipt.unlink(missing_ok=True)
            code, stdout, stderr = run_bounded(argv, cwd=directory, env=env, timeout=60)
            if name == "malformed-replay-cli":
                retain(name, check_cli_error(code, stdout, stderr, command, "policy_implementation_replay"))
            else:
                retain(name, check_cli_success(code, stdout, stderr, command, checked.result, payload, role))
            cli_guards[name] = read_json(guard_receipt)
            check_cli_guard(cli_guards[name], str(package), platform.python_version())
    check_observations(observations, fixture)
    parent_imports = boundary.origins()
    if binary_pins != {"biocompiler-core": digest_file(core_path), "biocompiler-verify": digest_file(verify_path)}:
        raise AssertionError("Selected native binary changed during the installed implementation campaign")
    sys.setprofile(None)
    sys.meta_path.remove(boundary)
    return {"schema_version": SCHEMA, "status": "pass", **source_identity(), "system": platform.system(),
            "machine": platform.machine(), "python_version": platform.python_version(), "fixture_sha256": digest_file(args.fixture),
            "binary_sha256": binary_pins,
            "package": str(package), "parent_imports": parent_imports, "cli_guards": cli_guards, "observations": observations,
            "observations_fingerprint": canonical_digest(observations), "python_semantic_authority": "forbidden"}


def compare(paths: list[Path], native_root: Path, fixture_path: Path) -> dict:
    identity = source_identity()
    binaries = native_manifests(native_root, identity["revision"])
    fixture, fixture_hash = checked_fixture(fixture_path), digest_file(fixture_path)
    expected = {(system, machine, python) for system, machine in (("Linux", "x86_64"), ("Darwin", "arm64"))
                for python in ("3.11", "3.14")}
    found, baseline = set(), None
    for path in paths:
        receipt = read_json(path)
        if (type(receipt) is not dict or set(receipt) != {
            "schema_version", "status", "revision", "head_revision", "run_id", "run_attempt", "system", "machine",
            "python_version", "fixture_sha256", "binary_sha256", "package", "parent_imports", "cli_guards",
            "observations", "observations_fingerprint", "python_semantic_authority",
        } or any(type(receipt[key]) is not str for key in ("system", "machine", "python_version", "run_attempt"))
                or not receipt["run_attempt"].isdecimal()):
            raise AssertionError("Malformed implementation campaign receipt")
        slot = receipt["system"], receipt["machine"], ".".join(receipt["python_version"].split(".")[:2])
        if slot not in expected or slot in found:
            raise AssertionError("Missing, duplicated or unexpected implementation campaign slot")
        found.add(slot)
        if (receipt["schema_version"] != SCHEMA or receipt["status"] != "pass" or receipt["fixture_sha256"] != fixture_hash
                or any(receipt[key] != identity[key] for key in ("revision", "head_revision", "run_id"))
                or not 0 < int(receipt["run_attempt"]) <= int(identity["run_attempt"])
                or receipt["binary_sha256"] != binaries[receipt["system"].lower()]["sha256"]
                or receipt["python_semantic_authority"] != "forbidden"):
            raise AssertionError("Implementation receipt lacks exact current run/source/binary authority")
        check_import_origins(receipt["parent_imports"], receipt["package"], {
            "biocompiler.core_client", "biocompiler.core_policy", "biocompiler.core_policy_operational", "biocompiler.core_policy_implementation",
        })
        if type(receipt["cli_guards"]) is not dict or set(receipt["cli_guards"]) != set(CLI_CASES):
            raise AssertionError("Missing complete implementation CLI guard receipts")
        for guard in receipt["cli_guards"].values():
            check_cli_guard(guard, receipt["package"], receipt["python_version"])
        observations = receipt["observations"]
        if canonical_digest(observations) != receipt["observations_fingerprint"]:
            raise AssertionError("Implementation campaign observations changed or incomplete")
        check_observations(observations, fixture)
        digest = canonical_digest(observations)
        if baseline is not None and baseline != digest:
            raise AssertionError("Complete implementation results differ across installed platform/Python slots")
        baseline = digest
    if found != expected:
        raise AssertionError("All four implementation campaign slots are required")
    return {"schema_version": SCHEMA, **identity, "status": "pass", "slots": sorted(found), "fixture_sha256": fixture_hash,
            "observations_fingerprint": baseline, "claim_scope": "bounded_implementation_preservation_only",
            "material": "unassessed", "export": "withheld"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("core", "verify", "console", "fixture", "output", "native-artifacts"):
        parser.add_argument("--" + name, type=Path, required=name in ("fixture", "output"))
    parser.add_argument("--compare", type=Path, action="append", default=[])
    args = parser.parse_args()
    if args.compare:
        if args.native_artifacts is None:
            parser.error("--compare requires --native-artifacts")
        result = compare(args.compare, args.native_artifacts, args.fixture)
    else:
        if any(getattr(args, name) is None for name in ("core", "verify", "console")):
            parser.error("Campaign requires --core, --verify and --console")
        result = run(args)
    encoded = (json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()
    if len(encoded) > 32 * 1024 * 1024:
        raise AssertionError("Complete implementation campaign receipt exceeds its retained artifact bound")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)


if __name__ == "__main__":
    main()
