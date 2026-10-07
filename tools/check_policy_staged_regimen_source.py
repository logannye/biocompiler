"""Hosted source DSL/native witness for independently authored staged timelines.

This development receipt has no installed, biological or release acceptance.
The original document is rebuilt by public Python authoring before installing
the semantic execution guard; all subsequent execution is native transport.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

try:
    from check_policy_core import canonical_digest, digest_file, read_json
    from check_policy_development import identity, source_snapshot, pin
    from check_policy_operational import OperationalBoundary
except ModuleNotFoundError:
    from tools.check_policy_core import canonical_digest, digest_file, read_json
    from tools.check_policy_development import identity, source_snapshot, pin
    from tools.check_policy_operational import OperationalBoundary

SCHEMA = "biocompiler.policy_staged_regimen_source_sdk_development.v0.1"
FIXTURE = "core/test/data/policy_staged_regimen_source_v01.json"
NATIVE_PATHS = {"core": "core/_build/default/bin/core/main.exe", "verify": "core/_build/default/bin/verify/main.exe"}
CASE_IDS = ("both_complete", "first_failure_and_timeout", "second_timeouts", "false_handoff_no_retry",
            "unknown_handoff_no_retry", "wrong_feedback", "reset_generation", "end_scope", "terminal_no_reentry")
NEGATIVES = ("changed-machine-source", "changed-timeout-source", "changed-guard-source", "forged-replay")
OBSERVATIONS = ("compile", "check") + tuple(case + "/" + operation for case in CASE_IDS
    for operation in ("execute-core", "execute-verify", "replay-verify")) + NEGATIVES


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def check_literals(execution: dict, case: dict) -> None:
    """Compare complete bounded states/attempts with inert expected literals."""
    expected = case["expected"]
    require(execution["claim"] == "bounded_supplied_timeline_only", "Execution claim widened")
    require([{key: frame[key] for key in ("time", "machines", "active_attempts")} for frame in execution["frames"]]
            == expected["frames"], case["id"] + ": all literal machine snapshots differ")
    require([{key: value for key, value in attempt.items() if key != "causes"} for attempt in execution["attempts"]]
            == expected["attempts"], case["id"] + ": complete attempt identity/status differs")
    rejected = [{key: action["detail"][key] for key in ("id", "reason")} for frame in execution["frames"]
                for action in frame["actions"] if action["kind"] == "feedback_rejected"]
    require(rejected == expected["feedback_rejected"], "Feedback rejection census differs")
    require(all(frame["states"] == [] for frame in execution["frames"]), "Unexpected state store")
    events = [event for frame in execution["frames"] for event in frame["events"]]
    require([event["id"] for event in events] == [f"event/{i + 1}" for i in range(len(events))], "Event census/order differs")
    by_event, by_attempt = {row["id"]: row for row in events}, {row["id"]: row for row in execution["attempts"]}
    for attempt in execution["attempts"]:
        creation = [event for event in events if event["attempt"] == attempt["id"] and event["kind"] in ("requested", "initiated")]
        require([event["kind"] for event in creation] == ["requested", "initiated"], "Request/initiation order or multiplicity differs")
        require(all(event["binding"] == attempt["binding"] and event["declaration"] == attempt["effect"] for event in creation),
                "Attempt creation lost effect or encounter generation")
        require(len(attempt["causes"]) == 1 and attempt["causes"][0] in by_event, "Missing unique cause")
        cause = by_event[attempt["causes"][0]]
        require(cause["binding"] == attempt["binding"], "Cause belongs to a foreign encounter generation")
        if attempt["effect"] == "stage_one":
            require(cause["kind"] == "rising", "First stage lost rising cause")
        else:
            require(cause["kind"] == "completed" and cause["declaration"] == "stage_one"
                    and cause["attempt"] in by_attempt and by_attempt[cause["attempt"]]["binding"] == attempt["binding"],
                    "Handoff lost correlated first-stage completion")


def exercise(packet: dict, core, verify, retain) -> None:
    from biocompiler.core_client import CoreRejected

    document, definitions = packet["document"], packet["definitions"]
    compiled = core.compile(document, definitions)
    retain("compile", compiled.result)
    candidate = compiled.candidate
    checked = verify.check_lowering(document, definitions, candidate)
    retain("check", checked.result)
    require(checked.candidate == candidate and checked.report == compiled.report, "Fresh Verify differs from Core lowering")
    reports = {}
    for case in packet["cases"]:
        first = core.execute(document, definitions, candidate, case["timeline"])
        second = verify.execute(document, definitions, candidate, case["timeline"])
        replay = verify.replay(document, definitions, candidate, case["timeline"], second.report)
        require(first.result == second.result == replay.result, "Core/Verify/fresh replay differ")
        check_literals(second.report["execution"], case)
        for operation, result in (("execute-core", first), ("execute-verify", second), ("replay-verify", replay)):
            retain(case["id"] + "/" + operation, result.result)
        reports[case["id"]] = second.report

    def reject(name, code, action):
        try:
            action()
        except CoreRejected as error:
            require(error.response.result is None and any(row.code == code for row in error.response.diagnostics),
                    "Negative control failed for an unrelated reason: " + name)
            retain(name, {"status": error.response.status, "diagnostics": [
                {"code": row.code, "message": row.message, "path": row.path} for row in error.response.diagnostics]})
        else:
            raise AssertionError("Expected native rejection: " + name)

    for name in NEGATIVES[:3]:
        changed = deepcopy(document)
        rows = {row["id"]: row for row in changed["declarations"]}
        if name == "changed-machine-source":
            rows["regimen/stages"]["initial"] = "first"
        elif name == "changed-timeout-source":
            rows["stage_one"]["lifecycle"]["timeout"]["amount"] = "3"
        else:
            guard = rows["regimen/handoff"]["when"]
            guard.update(op="literal", args=[], value=True, ref=None, scope=None)
        reject(name, "policy_correspondence", lambda: verify.check_lowering(changed, definitions, candidate))
    report = deepcopy(reports["both_complete"])
    report["execution"]["frames"][2]["machines"][0]["state"] = "completed"
    reject("forged-replay", "policy_execution_replay", lambda: verify.replay(
        document, definitions, candidate, packet["cases"][0]["timeline"], report))


def run(args: argparse.Namespace) -> dict:
    root = Path(__file__).resolve().parents[1]
    hosted, before = identity(root), source_snapshot(root)
    require(args.fixture.resolve() == (root / FIXTURE).resolve(), "Wrong staged source original fixture")
    packet = read_json(args.fixture, 2 * 1024 * 1024)
    require(packet["fixture_version"] == "biocompiler.policy_staged_regimen_source_literals.v0.1"
            and packet["claim_scope"] == "bounded_abstract_source_execution_only"
            and tuple(row["id"] for row in packet["cases"]) == CASE_IDS, "Wrong or incomplete source fixture")
    binaries = {role: pin(root, relative, executable=True) for role, relative in NATIVE_PATHS.items()}
    for role in NATIVE_PATHS:
        require(getattr(args, role).resolve(strict=True) == (root / NATIVE_PATHS[role]).resolve(), "Wrong current native binary")
    fixture_pin = digest_file(args.fixture)
    output = args.output.resolve()
    require(output == (root / "generated/development-feedback/staged-source-sdk-witness.json").resolve() and not output.exists(),
            "Use fresh fixed staged source receipt path")
    artifacts = output.with_suffix("")
    artifacts.mkdir(exist_ok=False)
    receipt = {"schema_version": SCHEMA, "status": "incomplete", "acceptance": False, "identity": hosted,
        "scope": "Hosted source DSL/native execution only; implementation, installed, empirical and release gates remain separate.",
        "python": platform.python_version(), "fixture_sha256": fixture_pin, "binary_sha256": binaries,
        "observations": [], "python_semantic_authority": "forbidden"}
    boundary, previous_profile, start = None, sys.getprofile(), time.monotonic()

    def save():
        raw = (json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        require(len(raw) <= 1024 * 1024, "Staged source receipt too large")
        output.write_bytes(raw)

    def retain(name, value):
        from biocompiler.core_client import encode_json
        index = len(receipt["observations"])
        require(index < len(OBSERVATIONS) and OBSERVATIONS[index] == name, "Changed source observation census")
        raw = encode_json(value)
        require(len(raw) <= 9 * 1024 * 1024, "Source observation too large")
        path = artifacts / (name.replace("/", "--") + ".json")
        with path.open("xb") as stream:
            stream.write(raw)
        receipt["observations"].append({"name": name, "path": str(path.relative_to(output.parent)),
            "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
        save()

    try:
        sys.path.insert(0, str(root / "src"))
        try:
            from generate_policy_staged_regimen_fixture import fixture
        except ModuleNotFoundError:
            from tools.generate_policy_staged_regimen_fixture import fixture
        require(fixture() == packet, "Public authoring changed original source or inert literals")
        receipt["authoring"] = {"document_sha256": canonical_digest(packet["document"]), "exact_original_equal": True}
        boundary = OperationalBoundary(root / "src/biocompiler")
        sys.meta_path.insert(0, boundary)
        sys.setprofile(boundary.trace)
        from biocompiler.core_client import CoreClient
        from biocompiler.core_policy_operational import OperationalPolicyClient
        clients = {role: OperationalPolicyClient(CoreClient(root / relative, role=role,
            expected_sha256=binaries[role]["sha256"], timeout_seconds=120)) for role, relative in NATIVE_PATHS.items()}
        exercise(packet, clients["core"], clients["verify"], retain)
        require([row["name"] for row in receipt["observations"]] == list(OBSERVATIONS), "Incomplete observation census")
        receipt["parent_imports"] = boundary.origins()
        receipt["status"] = "passed"
    except Exception as error:
        receipt.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        sys.setprofile(previous_profile)
        if boundary is not None:
            sys.meta_path.remove(boundary)
        receipt["elapsed_seconds"] = round(time.monotonic() - start, 3)
        try:
            require(identity(root) == hosted and source_snapshot(root) == before and digest_file(args.fixture) == fixture_pin
                    and {role: pin(root, relative, executable=True) for role, relative in NATIVE_PATHS.items()} == binaries,
                    "Original source, native bytes or hosted identity changed")
            receipt["source_snapshot_sha256"] = canonical_digest(before)
        except Exception as error:
            receipt.update(status="failed", source_error=str(error))
        save()
        require(receipt["status"] == "passed", receipt.get("source_error", receipt.get("error", "Incomplete source witness")))
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("fixture", "core", "verify", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args), sort_keys=True))


if __name__ == "__main__":
    main()
