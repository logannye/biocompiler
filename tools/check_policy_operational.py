"""Hosted installed operational-policy campaign and four-slot receipt comparison.

No native build or Python semantic execution occurs here. Campaign execution
requires explicit already-built binaries; comparison only reads retained data.
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

SCHEMA = "biocompiler.policy_operational_campaign.v0.1"
CASE_NAMES = ("compile", "check", "execute-core", "execute-verify", "replay-verify",
              "missing-definition", "unknown-definition", "duplicate-definition",
              "changed-lowering", "changed-source", "changed-source-span", "forged-replay",
              "wrong-feedback-target", "wrong-feedback-attempt", "work-limit",
              "compile-cli", "execute-cli", "replay-cli", "forged-replay-cli", "work-limit-cli")
CLI_CASES = ("compile-cli", "execute-cli", "replay-cli", "forged-replay-cli", "work-limit-cli")
NEGATIVE_CODES = {
    "missing-definition": {"policy_operational_unsupported"},
    "unknown-definition": {"policy_operational_unsupported"},
    "duplicate-definition": {"policy_operational_unsupported"},
    "changed-lowering": {"policy_correspondence"},
    "changed-source": {"policy_operational_source_invalid", "policy_correspondence"},
    "changed-source-span": {"policy_correspondence"},
    "forged-replay": {"policy_execution_replay"},
    "work-limit": {"policy_execution_work_limit"},
}


class OperationalBoundary(ImportBoundary):
    @staticmethod
    def allowed(name: str) -> bool:
        return name == "biocompiler.core_policy_operational" or ImportBoundary.allowed(name)


def checked_fixture(path: Path) -> dict:
    value = read_json(path)
    if (type(value) is not dict or value.get("fixture_version") != "biocompiler.policy_operational_literals.v0.1"
            or set(value) != {"fixture_version", "document", "definitions", "timeline", "expected_attempts"}
            or type(value["expected_attempts"]) is not list or len(value["expected_attempts"]) != 2
            or any(type(value[key]) is not dict for key in ("document", "definitions", "timeline"))
            or any(type(row) is not dict or set(row) != {"id", "encounter", "subject", "status"}
                   for row in value["expected_attempts"])
            or len({row["id"] for row in value["expected_attempts"]}) != 2):
        raise AssertionError("Incomplete independent operational literal fixture")
    return value


def check_attempt_literals(execution: dict, expected: list[dict]) -> None:
    actual = execution["attempts"]
    projected = [{"id": row["id"], "encounter": row["binding"]["encounter"],
                  "subject": row["subject"], "status": row["status"]} for row in actual]
    if projected != expected:
        raise AssertionError("Correlated completion/timeout literal differs")


def check_feedback_rejection(execution: dict, timeline: dict, expected: list[dict], reason: str) -> None:
    expected_attempts = deepcopy(expected)
    expected_attempts[0]["status"] = "timed_out"
    check_attempt_literals(execution, expected_attempts)
    identifier = timeline["feedback"][0]["id"]
    actions = [action for frame in execution["frames"] for action in frame["actions"]]
    rejected = [action for action in actions if action["kind"] == "feedback_rejected"
                and action["detail"]["id"] == identifier]
    if (len(rejected) != 1 or rejected[0]["detail"]["reason"] != reason
            or any(action["kind"] == "feedback_accepted" and action["detail"]["id"] == identifier for action in actions)):
        raise AssertionError("Wrong feedback changed execution instead of retaining its identity rejection")


def check_import_origins(origins: dict, package: str, required: set[str]) -> None:
    if type(origins) is not dict or not required <= set(origins):
        raise AssertionError("Missing installed transport or CLI import guard evidence")
    for name, path in origins.items():
        if (not OperationalBoundary.allowed(name) or type(path) is not str or not Path(path).is_absolute()
                or ".." in Path(path).parts or not Path(path).is_relative_to(package)):
            raise AssertionError("Forbidden or foreign installed Python semantic authority")


def check_cli_guard(guard: dict, package: str, python_version: str) -> None:
    if (type(guard) is not dict or guard.get("status") != "ok" or guard.get("guard_active") is not True
            or guard.get("execution_guard_active") is not True
            or guard.get("python") != [int(part) for part in python_version.split(".")[:2]]):
        raise AssertionError("Installed CLI import/execution guard did not complete on its declared interpreter")
    check_import_origins(guard.get("origins"), package,
                         {"biocompiler.entrypoint", "biocompiler.policy.cli", "biocompiler.core_policy_operational"})


def check_cli_error(returncode: int, stdout: bytes, stderr: bytes, command: str, diagnostic: str) -> dict:
    if returncode != 2 or stdout:
        raise AssertionError("Corrupt CLI authority did not fail closed with invocation status 2")
    value = json.loads(stderr)
    if (type(value) is not dict or set(value) != {"status", "operation", "message"}
            or value["status"] != "error" or value["operation"] != command
            or not value["message"].startswith(diagnostic + ":")):
        raise AssertionError("Corrupt CLI authority failed for an unrelated reason")
    return value


def check_observations(observations: list, fixture: dict) -> None:
    """Validate retained identities/ledgers, never reproduce native semantics."""
    from biocompiler.core_client import CORE_VERSION, CoreError, CoreResponse
    from biocompiler.core_policy_operational import _result

    if (type(observations) is not list or any(type(row) is not dict or set(row) != {"name", "result"} for row in observations)
            or [row["name"] for row in observations] != list(CASE_NAMES)):
        raise AssertionError("Operational receipt observations changed or incomplete")
    outcomes = {row["name"]: row["result"] for row in observations}
    candidate = outcomes["compile"]["candidate"]
    source = {"document": fixture["document"], "definitions": fixture["definitions"]}
    checked = {**source, "candidate": candidate}
    execution = {**checked, "timeline": fixture["timeline"]}
    for name, operation, payload in (
        ("compile", "compile-policy", source),
        ("check", "check-policy-lowering", checked),
        ("execute-core", "execute-policy", execution),
        ("execute-verify", "execute-policy", execution),
        ("replay-verify", "replay-policy-execution", {**execution, "report": outcomes["execute-verify"]["report"]}),
    ):
        try:
            _result(CoreResponse("retained-observation", operation, "ok", outcomes[name], (), "core", CORE_VERSION), payload)
        except CoreError as error:
            raise AssertionError("Retained operational output lost complete independent authority: " + name) from error
    if (outcomes["execute-core"] != outcomes["execute-verify"] or outcomes["replay-verify"] != outcomes["execute-verify"]
            or outcomes["compile-cli"] != outcomes["compile"] or outcomes["execute-cli"] != outcomes["execute-verify"]
            or outcomes["replay-cli"] != outcomes["replay-verify"]):
        raise AssertionError("Core, Verify, fresh replay and installed CLI outputs differ")
    check_attempt_literals(outcomes["execute-verify"]["report"]["execution"], fixture["expected_attempts"])
    for name, field, value, reason in (
        ("wrong-feedback-target", "subject", "target-2", "identity_mismatch"),
        ("wrong-feedback-attempt", "attempt", "attempt/999", "unknown_attempt"),
    ):
        timeline = deepcopy(fixture["timeline"])
        timeline["feedback"][0][field] = value
        try:
            _result(CoreResponse("retained-observation", "execute-policy", "ok", outcomes[name], (), "verify", CORE_VERSION),
                    {**checked, "timeline": timeline})
        except CoreError as error:
            raise AssertionError("Wrong-feedback control lost its exact mutated input authority") from error
        check_feedback_rejection(outcomes[name]["report"]["execution"], timeline, fixture["expected_attempts"], reason)
    for name, codes in NEGATIVE_CODES.items():
        error = outcomes[name]
        if (type(error) is not dict or set(error) != {"status", "diagnostics"} or error["status"] not in ("error", "unsupported")
                or type(error["diagnostics"]) is not list or not error["diagnostics"]
                or any(type(row) is not dict or set(row) != {"code", "message", "path"} for row in error["diagnostics"])
                or not codes.intersection(row["code"] for row in error["diagnostics"])):
            raise AssertionError("Negative operational control lacks its specific native rejection: " + name)
    for name, command, diagnostic in (
        ("forged-replay-cli", "replay-execution-native", "policy_execution_replay"),
        ("work-limit-cli", "execute-native", "policy_execution_work_limit"),
    ):
        check_cli_error(2, b"", json.dumps(outcomes[name]).encode(), command, diagnostic)


def run(args: argparse.Namespace) -> dict:
    checkout = Path(__file__).resolve().parents[1]
    spec = importlib.util.find_spec("biocompiler")
    if spec is None or spec.origin is None:
        raise AssertionError("Install biocompiler before running the hosted campaign")
    package = Path(spec.origin).resolve().parent
    if package.is_relative_to(checkout) or Path.cwd().resolve().is_relative_to(checkout):
        raise AssertionError("Installed campaign must run outside checkout with non-editable package")
    boundary = OperationalBoundary(package)
    sys.meta_path.insert(0, boundary)
    sys.setprofile(boundary.trace)
    from biocompiler.core_client import CoreClient, CoreRejected
    from biocompiler.core_policy_operational import OperationalPolicyClient

    fixture = checked_fixture(args.fixture)
    document, definitions, timeline = (fixture[key] for key in ("document", "definitions", "timeline"))
    core_path, verify_path = args.core.resolve(strict=True), args.verify.resolve(strict=True)
    core = OperationalPolicyClient(CoreClient(core_path, role="core", expected_sha256=digest_file(core_path)))
    verify = OperationalPolicyClient(CoreClient(verify_path, role="verify", expected_sha256=digest_file(verify_path)))
    observations = []

    def retain(name: str, result: object) -> None:
        observations.append({"name": name, "result": result})

    def rejects(name: str, action) -> None:
        try:
            action()
        except CoreRejected as error:
            if error.response.result is not None or not error.response.diagnostics:
                raise AssertionError("Rejected candidate retained success authority")
            retain(name, {"status": error.response.status,
                          "diagnostics": [{"code": item.code, "message": item.message, "path": item.path}
                                          for item in error.response.diagnostics]})
        else:
            raise AssertionError("Expected native rejection: " + name)

    compiled = core.compile(document, definitions=definitions)
    retain("compile", compiled.result)
    candidate = compiled.candidate
    checked = verify.check_lowering(document, definitions=definitions, candidate=candidate)
    retain("check", checked.result)
    core_execution = core.execute(document, definitions=definitions, candidate=candidate, timeline=timeline)
    execution = verify.execute(document, definitions=definitions, candidate=candidate, timeline=timeline)
    retain("execute-core", core_execution.result)
    retain("execute-verify", execution.result)
    if core_execution.result != execution.result:
        raise AssertionError("Complete Core/Verify reference execution differs")
    # Literal expected outcomes are authored independently of native execution.
    check_attempt_literals(execution.report["execution"], fixture["expected_attempts"])
    replay = verify.replay(document, definitions=definitions, candidate=candidate, timeline=timeline, report=execution.report)
    retain("replay-verify", replay.result)
    if replay.result != execution.result:
        raise AssertionError("Fresh standalone replay changed complete checked execution")
    missing = deepcopy(definitions)
    missing["definitions"].pop()
    rejects("missing-definition", lambda: core.compile(document, definitions=missing))
    unknown = deepcopy(definitions)
    unknown["definitions"][0]["semantics"] = "invented.semantic.v1"
    rejects("unknown-definition", lambda: core.compile(document, definitions=unknown))
    duplicate = deepcopy(definitions)
    duplicate["definitions"].append(duplicate["definitions"][0])
    rejects("duplicate-definition", lambda: core.compile(document, definitions=duplicate))
    mutant = deepcopy(candidate)
    mutant["nodes"] = mutant["nodes"][:-1]
    rejects("changed-lowering", lambda: verify.check_lowering(document, definitions=definitions, candidate=mutant))
    changed = deepcopy(document)
    next(row for row in changed["declarations"] if row["$type"] == "Rule")["when"]["op"] = "not"
    rejects("changed-source", lambda: verify.check_lowering(changed, definitions=definitions, candidate=candidate))
    changed_span = deepcopy(document)
    changed_span["source_map"][0]["line"] += 1
    rejects("changed-source-span", lambda: verify.check_lowering(changed_span, definitions=definitions, candidate=candidate))
    forged = deepcopy(execution.report)
    forged["artifact"] = "produced"
    rejects("forged-replay", lambda: verify.replay(document, definitions=definitions, candidate=candidate,
                                                   timeline=timeline, report=forged))
    wrong_target = deepcopy(timeline)
    wrong_target["feedback"][0]["subject"] = "target-2"
    rejected_target = verify.execute(document, definitions=definitions, candidate=candidate, timeline=wrong_target)
    check_feedback_rejection(rejected_target.report["execution"], wrong_target, fixture["expected_attempts"], "identity_mismatch")
    retain("wrong-feedback-target", rejected_target.result)
    wrong_attempt = deepcopy(timeline)
    wrong_attempt["feedback"][0]["attempt"] = "attempt/999"
    rejected_attempt = verify.execute(document, definitions=definitions, candidate=candidate, timeline=wrong_attempt)
    check_feedback_rejection(rejected_attempt.report["execution"], wrong_attempt, fixture["expected_attempts"], "unknown_attempt")
    retain("wrong-feedback-attempt", rejected_attempt.result)
    limited = deepcopy(timeline)
    limited["bounds"]["max_work"] = 1
    rejects("work-limit", lambda: verify.execute(document, definitions=definitions, candidate=candidate, timeline=limited))
    cli_guards = {}
    with tempfile.TemporaryDirectory(prefix="policy-operational-cli-") as temporary:
        directory = Path(temporary)
        for name, value in (("document", document), ("definitions", definitions), ("candidate", candidate),
                            ("timeline", timeline), ("report", execution.report)):
            (directory / (name + ".json")).write_text(json.dumps(value), encoding="utf-8")
        # The subprocess guard is installed before importing the CLI entrypoint.
        guard = directory / "sitecustomize.py"
        guard_receipt = directory / "guard.json"
        guard.write_text("import sys, atexit\nsys.path.insert(0," + repr(str(Path(__file__).resolve().parent)) + ")\n"
                         "from check_policy_operational import OperationalBoundary\nfrom pathlib import Path\n"
                         "boundary=OperationalBoundary(Path(" + repr(str(package)) + "), Path(" + repr(str(guard_receipt)) + "))\n"
                         "sys.meta_path.insert(0,boundary)\nsys.setprofile(boundary.trace)\natexit.register(boundary.finish)\n", encoding="utf-8")
        env = {**os.environ, "PYTHONPATH": str(directory), "PYTHONDONTWRITEBYTECODE": "1"}
        for name, command, executable, expected in (
                ("compile-cli", "compile-native", "core", compiled.result),
                ("execute-cli", "execute-native", "verify", execution.result),
                ("replay-cli", "replay-execution-native", "verify", replay.result)):
            argv = [str(args.console), "policy", command, str(directory / "document.json"),
                    "--definitions", str(directory / "definitions.json"), "--" + executable,
                    str(core_path if executable == "core" else verify_path), "--expected-sha256",
                    digest_file(core_path if executable == "core" else verify_path)]
            if command != "compile-native":
                argv += ["--candidate", str(directory / "candidate.json"), "--timeline", str(directory / "timeline.json")]
            if command == "replay-execution-native":
                argv += ["--report", str(directory / "report.json")]
            guard_receipt.unlink(missing_ok=True)
            code, stdout, stderr = run_bounded(argv, cwd=directory, env=env, timeout=60)
            expected_code = int(any(row["status"] == "fail" for row in expected["report"].get("execution", {}).get("requirements", [])))
            if code != expected_code or stderr or json.loads(stdout) != expected:
                raise AssertionError(f"Installed {command} failed: {stderr[:2000]!r}")
            cli_guards[name] = read_json(guard_receipt)
            check_cli_guard(cli_guards[name], str(package), platform.python_version())
            retain(name, expected)
        for name, command, changed_file, changed_value, diagnostic in (
            ("forged-replay-cli", "replay-execution-native", "report", forged, "policy_execution_replay"),
            ("work-limit-cli", "execute-native", "timeline", limited, "policy_execution_work_limit"),
        ):
            (directory / (changed_file + ".json")).write_text(json.dumps(changed_value), encoding="utf-8")
            argv = [str(args.console), "policy", command, str(directory / "document.json"), "--json",
                    "--definitions", str(directory / "definitions.json"), "--candidate", str(directory / "candidate.json"),
                    "--timeline", str(directory / "timeline.json"), "--verify", str(verify_path),
                    "--expected-sha256", digest_file(verify_path)]
            if command == "replay-execution-native":
                argv += ["--report", str(directory / "report.json")]
            guard_receipt.unlink(missing_ok=True)
            code, stdout, stderr = run_bounded(argv, cwd=directory, env=env, timeout=60)
            retain(name, check_cli_error(code, stdout, stderr, command, diagnostic))
            cli_guards[name] = read_json(guard_receipt)
            check_cli_guard(cli_guards[name], str(package), platform.python_version())
    if boundary.denied or [row["name"] for row in observations] != list(CASE_NAMES):
        raise AssertionError("Missing campaign cases or forbidden Python authority")
    check_observations(observations, fixture)
    parent_imports = boundary.origins()
    sys.setprofile(None)
    sys.meta_path.remove(boundary)
    return {"schema_version": SCHEMA, **source_identity(), "system": platform.system(), "machine": platform.machine(),
            "python_version": platform.python_version(), "fixture_sha256": digest_file(args.fixture),
            "binary_sha256": {"biocompiler-core": digest_file(core_path), "biocompiler-verify": digest_file(verify_path)},
            "package": str(package), "parent_imports": parent_imports, "cli_guards": cli_guards, "observations": observations,
            "observations_fingerprint": canonical_digest(observations), "python_semantic_authority": "forbidden"}


def compare(paths: list[Path], native_root: Path, fixture_path: Path) -> dict:
    identity = source_identity()
    binaries = native_manifests(native_root, identity["revision"])
    fixture_hash = digest_file(fixture_path)
    fixture = checked_fixture(fixture_path)
    receipts = [read_json(path) for path in paths]
    expected = {(system, machine, python) for system, machine in (("Linux", "x86_64"), ("Darwin", "arm64"))
                for python in ("3.11", "3.14")}
    found = set()
    baseline = None
    for receipt in receipts:
        if (type(receipt) is not dict or set(receipt) != {
            "schema_version", "revision", "head_revision", "run_id", "run_attempt", "system", "machine",
            "python_version", "fixture_sha256", "binary_sha256", "package", "parent_imports", "cli_guards",
            "observations", "observations_fingerprint", "python_semantic_authority",
        } or type(receipt["python_version"]) is not str or type(receipt["run_attempt"]) is not str
                or not receipt["run_attempt"].isdecimal()):
            raise AssertionError("Malformed operational campaign receipt")
        slot = receipt["system"], receipt["machine"], ".".join(receipt["python_version"].split(".")[:2])
        if slot not in expected or slot in found:
            raise AssertionError("Missing, duplicated or unexpected operational campaign slot")
        found.add(slot)
        if (receipt["schema_version"] != SCHEMA or receipt["fixture_sha256"] != fixture_hash
                or any(receipt[key] != identity[key] for key in ("revision", "head_revision", "run_id"))
                or not 0 < int(receipt["run_attempt"]) <= int(identity["run_attempt"])
                or receipt["binary_sha256"] != binaries[receipt["system"].lower()]["sha256"]
                or receipt["python_semantic_authority"] != "forbidden"):
            raise AssertionError("Operational receipt lacks exact current run/source/binary authority")
        observations = receipt["observations"]
        if canonical_digest(observations) != receipt["observations_fingerprint"]:
            raise AssertionError("Operational receipt observations changed or incomplete")
        check_import_origins(receipt["parent_imports"], receipt["package"],
                             {"biocompiler.core_client", "biocompiler.core_policy", "biocompiler.core_policy_operational"})
        if type(receipt["cli_guards"]) is not dict or set(receipt["cli_guards"]) != set(CLI_CASES):
            raise AssertionError("Missing complete installed CLI guard receipts")
        for guard in receipt["cli_guards"].values():
            check_cli_guard(guard, receipt["package"], receipt["python_version"])
        check_observations(observations, fixture)
        if baseline is not None and baseline != observations:
            raise AssertionError("Complete operational results differ across installed platform/Python slots")
        baseline = observations
    if found != expected:
        raise AssertionError("All four operational campaign slots are required")
    return {"schema_version": SCHEMA, **identity, "status": "pass", "slots": sorted(found),
            "fixture_sha256": fixture_hash, "observations_fingerprint": canonical_digest(baseline),
            "claim_scope": "bounded_abstract_source_execution_only"}


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
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
