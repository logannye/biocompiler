"""Hosted Python DSL through complete native selection check/replay/paired export.

The domain-only fixture supplies originals, not acceptance. Core produces each
supplied child candidate separately; no selection generation operation exists.
Every selection check and export freshly crosses its real Core/Verify boundary.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import sys
import time

try:
    from check_policy_core import canonical_digest, digest_file, read_json
    from check_policy_development import identity, source_snapshot, pin
    from check_policy_component_material import ComponentBoundary, author_request, NATIVE_PATHS, MAX_RECEIPT, MAX_EVIDENCE
    from check_policy_material import archive_receipt, OBLIGATIONS
except ModuleNotFoundError:
    from tools.check_policy_core import canonical_digest, digest_file, read_json
    from tools.check_policy_development import identity, source_snapshot, pin
    from tools.check_policy_component_material import ComponentBoundary, author_request, NATIVE_PATHS, MAX_RECEIPT, MAX_EVIDENCE
    from tools.check_policy_material import archive_receipt, OBLIGATIONS

SCHEMA = "biocompiler.policy_component_selection_sdk_development.v0.1"
FIXTURE_SCHEMA = "biocompiler.policy_component_selection_original_fixture.v0.1"
INPUTS = ("core/test/data/policy_material_request_v01.json", "core/test/policy_component_support/literals.ml",
          "core/test/policy_component_support/requests.ml", "core/test/policy_component_support/selection_requests.ml")
OBSERVATIONS = ("child-short-compile", "child-long-compile", "check-core", "check-verify", "replay-core", "replay-verify",
    "export-core", "paired-core", "export-verify", "paired-verify", "long-check", "long-export", "long-paired",
    "no-eligible-check", "no-eligible-export", "loser-rank-check", "loser-rank-export", "loser-rank-paired", "stale-replay",
    "verify-no-selection-producer", "core-no-selection-producer")
EXPECTED = {"short_rna": "CCAUGGCUUAAGGAAAA", "long_rna": "CGCAUGGCUUAAGGAAAA",
            "histories": 9, "transitions": 47, "prefixes_started": 48, "obligations": OBLIGATIONS}


class SelectionBoundary(ComponentBoundary):
    @staticmethod
    def allowed(name: str) -> bool:
        return name == "biocompiler.core_policy_component_selection" or ComponentBoundary.allowed(name)


def checked_fixture(root: Path, path: Path) -> dict:
    packet = read_json(path, 4_000_000)
    if (type(packet) is not dict or set(packet) != {"schema_version", "status", "acceptance", "source_sha256", "request", "limits", "expected"}
            or packet["schema_version"] != FIXTURE_SCHEMA or packet["status"] != "source_declarations_only" or packet["acceptance"] is not False
            or packet["source_sha256"] != {name: digest_file(root / name) for name in INPUTS}
            or packet["expected"] != EXPECTED):
        raise AssertionError("Selection originals lack exact current source provenance or independent literals")
    source = read_json(root / INPUTS[0], 4_000_000)
    original = packet["request"]
    rows = original["alternatives"]
    if (len(rows) != 2 or {row["id"] for row in rows} != {"short", "long"}
            or {row["id"]: row["rank"] for row in rows} != {"short": 1, "long": 0}
            or any(row["request"]["implementation_request"] != source["request"]["implementation_request"] for row in rows)
            or packet["limits"] != source["limits"] or original["predicate"] != {"max_total_nt": 17}
            or original["budgets"] != {"profile": "biocompiler.policy_component_selection_resources.v0.2", "max_work": 17000000000,
                                       "max_report_bytes": 8323072, "max_report_nodes": 1000000}):
        raise AssertionError("Selection fixture changed the one-A program, complete rank census, limits or explicit publication budget")
    return packet


def checked_result(value: dict, *, winner: str | None, maximum: int) -> None:
    report = value["report"]
    expected_status = "checked_selection" if winner is not None else "no_eligible_alternative"
    if (report["status"] != expected_status or report["selected_id"] != winner or report["winner_matches"] is not True
            or report["all_inner_accepted"] is not True or report["census_complete"] is not True
            or report["empirical"] != "unassessed" or report["artifact"] != "withheld" or report["export"] != "withheld"
            or [row["id"] for row in report["alternatives"]] != ["long", "short"]):
        raise AssertionError("Native selection lost its complete census, exact winner or conditional claim")
    for row in report["alternatives"]:
        sequence = EXPECTED[row["id"] + "_rna"]
        inner = row["inner"]
        if (row["total_nt"] != len(sequence) or row["sequence_sha256"] != hashlib.sha256(sequence.encode()).hexdigest()
                or row["eligible"] is not (len(sequence) <= maximum) or inner["status"] != "checked_component_material"
                or inner["all_original_obligations_discharged"] is not True
                or [item["obligation"] for item in inner["obligations"]] != OBLIGATIONS
                or any(item["status"] != "discharged" for item in inner["obligations"])):
            raise AssertionError("A winning or losing child lost literal RNA or complete original obligation discharge")
        preservation = inner["preservation"]
        if (preservation["coverage"]["complete"] is not True
                or [preservation["coverage"][key] for key in ("histories", "transitions", "prefixes_started", "matched_prefixes")] != [9, 47, 48, 48]
                or [item["id"] for item in preservation["requirements"]] != ["request_progress", "initiation_progress", "exclusive_selection"]
                or any(item["status"] != "pass" or item["histories"]["pass"] != 9 for item in preservation["requirements"])):
            raise AssertionError("Selection omitted a child's complete source/domain/requirement obligations")
    artifact = value["artifact"]
    if artifact is not None:
        if winner is None or artifact["fasta"] != ">rna_0001 alphabet=RNA\n" + EXPECTED[winner + "_rna"] + "\n":
            raise AssertionError("Selected export differs from independently declared exact RNA")
        manifest = artifact["manifest"]
        if ([row["id"] for row in manifest["request"]["alternatives"]] != ["short", "long"]
                or manifest["candidate"] != value["candidate"] or manifest["assessment"] != report
                or manifest["selected"]["id"] != winner or len(manifest["members"]) != 1):
            raise AssertionError("Outer manifest lost complete original order, candidate or selected material")


def exercise(request, limits, child_core, core, verify, core_transport, verify_transport, sdk, retain, artifacts, input_paths):
    from biocompiler.core_client import CoreRejected
    candidates = []
    for name in ("short", "long"):
        original = next(row["request"] for row in request["alternatives"] if row["id"] == name)
        produced = child_core.compile(original, limits)
        if produced.status != "checked_component_material" or produced.artifact is not None:
            raise AssertionError("Child producer did not provide a checked candidate without export")
        retain("child-" + name + "-compile", produced.result)
        candidates.append({"id": name, "candidate": produced.candidate})
    candidate = {"schema_version": "biocompiler.policy_component_selection_candidate.v0.1", "alternatives": candidates, "selected_id": "short"}
    checked = []
    for name, client in (("core", core), ("verify", verify)):
        value = sdk.check(request, candidate=candidate, limits=limits, client=client)
        checked_result(value.result, winner="short", maximum=17)
        retain("check-" + name, value.result)
        checked.append(value)
    if checked[0].result != checked[1].result:
        raise AssertionError("Fresh Core and producer-free Verify evidence differ")
    for name, client in (("core", core), ("verify", verify)):
        replayed = sdk.replay(request, candidate=candidate, limits=limits, report=checked[1].result, client=client)
        if replayed.result != checked[1].result:
            raise AssertionError("Fresh complete selection replay changed evidence")
        retain("replay-" + name, replayed.result)
    exports = []
    for name, client in (("core", core), ("verify", verify)):
        path = artifacts / (name + "-program.zip")
        exported = sdk.export(request, candidate=candidate, limits=limits, client=client, output=path, input_paths=input_paths)
        checked_result(exported.result, winner="short", maximum=17)
        if exported.report != checked[1].report:
            raise AssertionError("Fresh paired publication changed prior complete assessment")
        retain("export-" + name, exported.result)
        retain("paired-" + name, archive_receipt(exported.result, path))
        exports.append(exported)
    if (exports[0].result != exports[1].result
            or (artifacts / "core-program.zip").read_bytes() != (artifacts / "verify-program.zip").read_bytes()):
        raise AssertionError("Core/Verify exact paired bytes differ")
    larger, long_candidate = deepcopy(request), deepcopy(candidate)
    larger["predicate"]["max_total_nt"] = 18
    long_candidate["selected_id"] = "long"
    long_checked = sdk.check(larger, candidate=long_candidate, limits=limits, client=verify)
    checked_result(long_checked.result, winner="long", maximum=18)
    retain("long-check", long_checked.result)
    long_path = artifacts / "long-program.zip"
    long_export = sdk.export(larger, candidate=long_candidate, limits=limits, client=verify, output=long_path, input_paths=input_paths)
    checked_result(long_export.result, winner="long", maximum=18)
    retain("long-export", long_export.result)
    retain("long-paired", archive_receipt(long_export.result, long_path))

    def rejected(name, code, action, *, expected_status="error"):
        try:
            action()
        except CoreRejected as error:
            response = error.response
            if response.status != expected_status or response.result is not None or [row.code for row in response.diagnostics] != [code]:
                raise AssertionError("Selection control failed at a different native boundary: " + name) from error
            retain(name, {"status": response.status,
                "diagnostics": [{"code": row.code, "message": row.message, "path": row.path} for row in response.diagnostics]})
        else:
            raise AssertionError("Selection control acquired unexpected acceptance: " + name)

    empty, none_candidate = deepcopy(request), deepcopy(candidate)
    empty["predicate"]["max_total_nt"] = 16
    none_candidate["selected_id"] = None
    no_eligible = sdk.check(empty, candidate=none_candidate, limits=limits, client=verify)
    checked_result(no_eligible.result, winner=None, maximum=16)
    retain("no-eligible-check", no_eligible.result)
    rejected("no-eligible-export", "policy_component_selection_export_not_accepted", lambda: verify.export(empty, none_candidate, limits))
    edited = deepcopy(request)
    next(row for row in edited["alternatives"] if row["id"] == "long")["rank"] = 2
    changed = sdk.check(edited, candidate=candidate, limits=limits, client=verify)
    checked_result(changed.result, winner="short", maximum=17)
    retain("loser-rank-check", changed.result)
    changed_path = artifacts / "loser-rank-program.zip"
    changed_export = sdk.export(edited, candidate=candidate, limits=limits, client=verify, output=changed_path, input_paths=input_paths)
    checked_result(changed_export.result, winner="short", maximum=17)
    if (changed_export.artifact["fasta"] != exports[1].artifact["fasta"]
            or changed_export.artifact["manifest_sha256"] == exports[1].artifact["manifest_sha256"]):
        raise AssertionError("Unchanged winner erased the changed losing original")
    retain("loser-rank-export", changed_export.result)
    retain("loser-rank-paired", archive_receipt(changed_export.result, changed_path))
    rejected("stale-replay", "policy_component_selection_replay",
        lambda: verify.replay(edited, candidate, limits, checked[1].result))
    for name, transport in (("verify", verify_transport), ("core", core_transport)):
        rejected(name + "-no-selection-producer", "unsupported_operation",
            lambda transport=transport: transport.call("compile-policy-component-selection", {"request": request, "limits": limits}), expected_status="unsupported")


def run(args: argparse.Namespace) -> dict:
    root = Path(__file__).resolve().parents[1]
    hosted, before = identity(root), source_snapshot(root)
    binary_paths = {"core": args.core.resolve(strict=True), "verify": args.verify.resolve(strict=True)}
    if any(path != (root / NATIVE_PATHS[role]).resolve() for role, path in binary_paths.items()):
        raise AssertionError("Selection SDK requires the exact current hosted Core/Verify build")
    binaries = {role: pin(root, NATIVE_PATHS[role], executable=True) for role in binary_paths}
    fixture = checked_fixture(root, args.fixture)
    fixture_pin = digest_file(args.fixture)
    output = args.output.resolve()
    if output != (root / "generated/development-feedback/selection-sdk-witness.json").resolve() or output.exists():
        raise AssertionError("Use one fresh receipt at the fixed selection evidence path")
    artifacts = output.with_suffix("")
    artifacts.mkdir(exist_ok=False)
    receipt = {"schema_version": SCHEMA, "status": "incomplete", "acceptance": False, "identity": hosted,
        "scope": "Hosted source-tree Python DSL/selection SDK witness only; installed and release gates remain separate.",
        "python": platform.python_version(), "fixture_sha256": fixture_pin, "binary_sha256": binaries,
        "authoring": [], "observations": [], "python_semantic_authority": "forbidden"}
    boundary, previous_profile = None, sys.getprofile()
    start = time.monotonic()

    def save():
        raw = (json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        if len(raw) > MAX_RECEIPT:
            raise AssertionError("Selection SDK receipt exceeds its bound")
        output.write_bytes(raw)

    def retain(name, value):
        from biocompiler.core_client import encode_json
        index = len(receipt["observations"])
        if index >= len(OBSERVATIONS) or name != OBSERVATIONS[index]:
            raise AssertionError("Selection SDK changed its complete observation census")
        raw = encode_json(value)
        if len(raw) > MAX_EVIDENCE:
            raise AssertionError("Selection SDK observation exceeds its bound")
        path = artifacts / ("selection-" + name + ".json")
        with path.open("xb") as stream:
            stream.write(raw)
        receipt["observations"].append({"case": "selection", "name": name, "path": str(path.relative_to(output.parent)),
            "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
        save()

    try:
        sys.path.insert(0, str(root / "src"))
        spec = importlib.util.find_spec("biocompiler")
        if spec is None or Path(spec.origin).resolve() != root / "src/biocompiler/__init__.py":
            raise AssertionError("Selection SDK resolved a foreign source package")
        originals = []
        for row in fixture["request"]["alternatives"]:
            request, authored = author_request(row["request"], False)
            originals.append({"id": row["id"], "rank": row["rank"], "request": request})
            receipt["authoring"].append({"case": row["id"], **authored})
        boundary = SelectionBoundary(root / "src/biocompiler")
        sys.meta_path.insert(0, boundary)
        sys.setprofile(boundary.trace)
        from biocompiler.core_client import CoreClient
        from biocompiler.core_policy_component_material import PolicyComponentMaterialClient
        from biocompiler.core_policy_component_selection import PolicyComponentSelectionClient
        from biocompiler.policy import component_selection as sdk
        request = sdk.prepare_request(alternatives=originals, predicate=deepcopy(fixture["request"]["predicate"]), budgets=deepcopy(fixture["request"]["budgets"]))
        if request != fixture["request"]:
            raise AssertionError("Public selection preparation changed any complete original")
        transports = {role: CoreClient(path, role=role, expected_sha256=binaries[role]["sha256"], timeout_seconds=120)
                      for role, path in binary_paths.items()}
        clients = {role: PolicyComponentSelectionClient(value) for role, value in transports.items()}
        exercise(request, fixture["limits"], PolicyComponentMaterialClient(transports["core"]), clients["core"], clients["verify"],
            transports["core"], transports["verify"], sdk, retain, artifacts, (args.fixture, *(root / name for name in INPUTS)))
        if [row["name"] for row in receipt["observations"]] != list(OBSERVATIONS):
            raise AssertionError("Selection SDK omitted a mandatory fresh observation")
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
            if (identity(root) != hosted or source_snapshot(root) != before or digest_file(args.fixture) != fixture_pin
                    or {role: pin(root, NATIVE_PATHS[role], executable=True) for role in binary_paths} != binaries):
                raise AssertionError("Source, original fixture, hosted identity or native bytes changed during selection SDK witness")
            receipt["source_snapshot_sha256"] = canonical_digest(before)
        except Exception as error:
            receipt.update(status="failed", source_error=str(error))
        save()
        if receipt["status"] != "passed":
            raise AssertionError(receipt.get("source_error", receipt.get("error", "Incomplete selection SDK witness")))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("fixture", "core", "verify", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    result = run(parser.parse_args())
    print(json.dumps({"status": result["status"], "acceptance": False, "observations": len(result["observations"])}))


if __name__ == "__main__":
    main()
