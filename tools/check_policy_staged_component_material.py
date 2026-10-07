"""Hosted Python authoring through independently checked staged RNA export.

This is a separate development witness. Native Core and producer-free Verify
own semantics; source-tree feedback grants no installed, release or human-use
acceptance. Existing component and selection witness censuses are unchanged.
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
    from check_policy_core import canonical_digest, digest_file, read_json, source_identity
    from check_policy_development import identity, pin, source_snapshot
    from check_policy_component_material import ComponentBoundary, NATIVE_PATHS, MAX_RECEIPT, MAX_EVIDENCE
    from check_policy_material import archive_receipt, changed_candidate
except ModuleNotFoundError:
    from tools.check_policy_core import canonical_digest, digest_file, read_json, source_identity
    from tools.check_policy_development import identity, pin, source_snapshot
    from tools.check_policy_component_material import ComponentBoundary, NATIVE_PATHS, MAX_RECEIPT, MAX_EVIDENCE
    from tools.check_policy_material import archive_receipt, changed_candidate

SCHEMA = "biocompiler.policy_staged_component_sdk_development.v0.1"
FIXTURE = "core/test/data/policy_staged_material_v01.json"
OUTPUT = "generated/development-feedback/staged-material-sdk-witness.json"
INPUTS = (FIXTURE, "core/test/data/policy_staged_realization_request_v01.json",
          "core/test/data/policy_staged_material_seed_v01.json",
          "tools/generate_policy_staged_material_fixture.py", "tools/generate_policy_staged_regimen_fixture.py")
OBSERVATIONS = (
    "compile", "check-verify", "replay-verify", "export-verify", "paired-publication",
    "missing-machine-wire", "wrong-feedback-bank", "wrong-request-owner", "changed-material",
    "rejected-export", "stale-source", "forged-replay", "verify-has-no-producer",
    "insufficient-machine-capacity", "capacity-export", "completion-without-feedback",
)
NEGATIVE_CODES = {
    "missing-machine-wire": "policy_implementation_contract",
    "wrong-feedback-bank": "policy_implementation_source_binding",
    "wrong-request-owner": "policy_implementation_source_binding",
    "rejected-export": "policy_component_material_export_not_accepted",
    "stale-source": "policy_correspondence", "forged-replay": "policy_component_material_replay",
    "verify-has-no-producer": "unsupported_operation", "capacity-export": "policy_component_material_export_not_accepted",
}
SEQUENCE = "CCAUGGCUUAAGGAAAA"
FASTA = ">rna_0001 alphabet=RNA\n" + SEQUENCE + "\n"
REQUIREMENTS = ["first_initiation", "second_initiation"]
# Each encounter has five complete paths: first failure/timeout, or first
# completion followed by three second-stage outcomes. All 25 paired paths
# request stage one; 2 * 2 never request stage two and do not exercise its
# conditional initiation requirement. The other 21 exercise and satisfy it.
REQUIREMENT_HISTORIES = {
    "first_initiation": {"pass": 25, "fail": 0, "unknown": 0, "not_exercised": 0, "unsupported": 0},
    "second_initiation": {"pass": 21, "fail": 0, "unknown": 0, "not_exercised": 4, "unsupported": 0},
}
MACHINE_OBLIGATION = "machine_reachability_termination_and_progress"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def check_census(names):
    require(list(names) == list(OBSERVATIONS), "Incomplete, duplicated or reordered staged observation census")


def checked_fixture(root: Path, path: Path) -> dict:
    require(path.resolve() == (root / FIXTURE).resolve() and not path.is_symlink(), "Use the exact staged original fixture")
    value = read_json(path, 4_000_000)
    require(set(value) == {"schema_version", "notice", "seed_sha256", "request", "limits", "expected"}
            and value["schema_version"] == "biocompiler.policy_staged_material_literals.v0.1",
            "Changed staged original fixture profile")
    expected, original = value["expected"], value["request"]
    require(value["seed_sha256"] == digest_file(root / INPUTS[2])
            and original["implementation_request"] == read_json(root / INPUTS[1], 4_000_000),
            "Staged original material or realization authority changed")
    require(expected["sequence"] == SEQUENCE and expected["fasta"] == FASTA
            and expected["molecule"]["sequence"] == SEQUENCE
            and [expected[key] for key in ("histories", "transitions", "prefixes_started")] == [25, 86, 87]
            and expected["prefixes_after_tick"] == [1, 1, 9, 25, 25, 25]
            and expected["requirements"] == REQUIREMENTS
            and [expected[key] for key in ("node_count", "wire_count", "link_count", "resource_bindings")] == [28, 55, 12, 17]
            and original["context"]["record_layout"]["union_digest"] == canonical_digest(expected["ordered_union"]),
            "Independent staged molecule, graph or finite-domain census changed")
    seed = read_json(root / INPUTS[2], 4_000_000)
    require(seed["expected_molecules"] == [expected["molecule"]], "Staged expected molecule differs from independent material seed")
    return value


def author_request(original: dict) -> tuple[dict, dict]:
    from biocompiler import policy as p
    from biocompiler.policy.implementation import prepare_request as prepare_implementation
    from biocompiler.policy.component_material import prepare_request
    try:
        from generate_policy_staged_material_fixture import build_request
    except ModuleNotFoundError:
        from tools.generate_policy_staged_material_fixture import build_request
    authored = build_request()
    supplied = original["implementation_request"]
    require(p.to_data(authored) == supplied["document"], "Python authoring changed the complete staged original document")
    implementation = prepare_implementation(authored, **{key: deepcopy(supplied[key]) for key in
        ("definitions", "operating_domain", "implementation_library", "catalog_bindings", "budgets")})
    result = prepare_request(implementation_request=implementation, **{key: deepcopy(original[key]) for key in
        ("component_library", "composition_rule", "catalog_binding", "input_bindings", "resource_bindings", "context", "budgets")})
    require(result == original, "Public request preparation changed complete original staged authority")
    return result, {"phase": "python_authoring_before_native_semantic_guard", "runtime_semantics": "not_executed",
        "recipe_sha256": digest_file(Path(build_request.__code__.co_filename)),
        "source_artifact_digest": canonical_digest(p.to_data(authored)), "declarations": len(authored.program.declarations),
        "implementation_request_digest": canonical_digest(implementation), "request_digest": canonical_digest(result)}


def checked_result(result: dict, fixture: dict) -> None:
    from biocompiler.core_policy_component_material import ACCEPTED_STATUS, CLAIM_SCOPE, PREMISE
    report, candidate, expected = result["report"], result["candidate"], fixture["expected"]
    require(report["status"] == ACCEPTED_STATUS and report["claim_scope"] == CLAIM_SCOPE and report["premise"] == PREMISE
            and report["assembly_status"] == report["context_status"] == "pass"
            and report["all_original_obligations_discharged"] is True and report["empirical"] == "unassessed"
            and report["artifact"] == report["export"] == "withheld"
            and all(row["status"] == "discharged" for row in report["obligations"]),
            "Staged conjunction changed its bounded conditional claim")
    preservation = report["preservation"]
    require(preservation["preservation"] == "pass" and preservation["coverage"]["complete"] is True
            and [preservation["coverage"][key] for key in ("histories", "transitions", "prefixes_started", "matched_prefixes")] == [25, 86, 87, 87]
            and [row["id"] for row in preservation["requirements"]] == REQUIREMENTS
            and all(row["status"] == "pass" and row["nonvacuous"] is True
                    and type(row["histories"]) is dict and row["histories"] == REQUIREMENT_HISTORIES[row["id"]]
                    and all(type(count) is int for count in row["histories"].values())
                    for row in preservation["requirements"]), "Staged finite-domain or nonvacuous requirement evidence changed")
    binding = preservation["binding"]
    require(binding["profile"] == "biocompiler.policy_staged_source_graph.v0.1"
            and binding["state_encoding"] == "exact_ordered_source_labels"
            and report["context"]["profile"] == "biocompiler.policy_staged_component_mrna.v0.1",
            "Staged source or context semantics acquired a legacy profile")
    machine = [row for row in report["obligations"] if row["obligation"] == MACHINE_OBLIGATION]
    require(len(machine) == 1 and machine[0]["stage"] == "bounded_machine_semantics_and_declared_requirements"
            and machine[0]["evidence"] == {"preservation": canonical_digest(preservation),
                "machine_binding": canonical_digest(binding), "state_and_terminal_semantics": "exact_bounded_source_correspondence",
                "prefixes": "complete_original_domain", "retained_attempt_identity": "creation_fixed_injective",
                "universal_termination": "not_claimed", "progress": "declared_requirements_only"},
            "Machine obligation broadened or lost its fresh bounded evidence")
    require(candidate["construction"]["inventory"]["molecules"] == [expected["molecule"]]
            and len(candidate["implementation"]["nodes"]) == 28 and len(candidate["implementation"]["wires"]) == 55
            and len(report["assembly"]["link_projections"]) == 12
            and candidate["binding"]["rules"] == candidate["binding"]["states"] == []
            and len(candidate["binding"]["machines"]) == 1 and len(candidate["binding"]["transitions"]) == 7,
            "Exact staged molecule, machine anchors or component inventory changed")


def checked_export(result: dict, fixture: dict) -> None:
    checked_result(result, fixture)
    artifact, candidate, report = result["artifact"], result["candidate"], result["report"]
    require(artifact is not None and artifact["fasta"] == FASTA
            and artifact["fasta_sha256"] == hashlib.sha256(FASTA.encode()).hexdigest(), "Independent exact staged FASTA changed")
    manifest = artifact["manifest"]
    require(manifest["request"] == fixture["request"] and manifest["candidate"] == candidate
            and manifest["limits"] == fixture["limits"] and manifest["assessment"] == report
            and manifest["bindings"]["assessment_fingerprint"] == canonical_digest(report)
            and artifact["manifest_sha256"] == canonical_digest(manifest), "Fresh paired export omitted complete original authority")


def changed_graph(candidate: dict, kind: str) -> dict:
    value = deepcopy(candidate)
    wires = value["implementation"]["wires"]
    bindings = value["binding"]
    if kind == "missing-machine-wire":
        commit = bindings["transitions"][0]["commit"]
        value["implementation"]["wires"] = [wire for wire in wires
            if wire["producer"] != {"node": commit, "port": "machine_write"}]
        require(len(value["implementation"]["wires"]) == len(wires) - 1, "Missing exact original machine-write control")
    elif kind == "wrong-feedback-bank":
        first, second = [row["bank"] for row in bindings["effects"]]
        selected = [wire for wire in wires if wire["producer"] == {"node": first, "port": "events"}]
        require(len(selected) == 3, "Missing stage-one feedback selector routes")
        for wire in selected:
            wire["producer"]["node"] = second
    elif kind == "wrong-request-owner":
        first, second = [row["bank"] for row in bindings["effects"]]
        selected = [wire for wire in wires if wire["consumer"]["port"] == "request"]
        require(len(selected) == 2 and {wire["consumer"]["node"] for wire in selected} == {first, second},
                "Missing distinct stage request owners")
        for wire in selected:
            wire["consumer"]["node"] = second if wire["consumer"]["node"] == first else first
    else:
        raise AssertionError("Unknown staged graph control")
    return value


def deficient_capacity(request: dict) -> dict:
    value, count = deepcopy(request), 0
    for provider in value["context"]["providers"]:
        for capacity in provider["body"]["capacities"]:
            if capacity["unit"] == "machine_state_bits":
                capacity["quantity"] = 2
                count += 1
        provider["identity"]["content_fingerprint"] = canonical_digest(provider["body"])
    require(count == 1, "Missing unique machine-state capacity premise")
    return value


def completion_request(request: dict) -> dict:
    value = deepcopy(request)
    requirements = [row for row in value["implementation_request"]["document"]["program"]["declarations"]
                    if row["$type"] == "Requirement" and row["id"] == "second_initiation"]
    require(len(requirements) == 1 and requirements[0]["response"]["value"] == "initiated", "Changed original initiation requirement")
    requirements[0]["response"]["value"] = "completed"
    return value


def rejected(name, action) -> dict:
    from biocompiler.core_client import CoreRejected
    try:
        action()
    except CoreRejected as error:
        response = error.response
        require(response.result is None and response.diagnostics
                and response.status == ("unsupported" if name == "verify-has-no-producer" else "error")
                and {row.code for row in response.diagnostics} == {NEGATIVE_CODES[name]},
                "Control failed at an unrelated native boundary: " + name)
        return {"status": response.status, "diagnostics": [
            {"code": row.code, "message": row.message, "path": row.path} for row in response.diagnostics]}
    raise AssertionError("Staged mutation acquired acceptance: " + name)


def exercise(fixture, request, core, verify_transport, verify, sdk, retain, artifacts, input_paths):
    limits = fixture["limits"]
    compiled = sdk.compile(request, limits=limits, client=core)
    checked_result(compiled.result, fixture)
    require(compiled.artifact is None, "Compilation bypassed fresh export")
    retain("compile", compiled.result)
    candidate = compiled.candidate
    checked = sdk.check(request, candidate=candidate, limits=limits, client=verify)
    replayed = sdk.replay(request, candidate=candidate, limits=limits, report=checked.result, client=verify)
    require(compiled.result == checked.result == replayed.result, "Fresh producer-free check/replay changed complete staged evidence")
    retain("check-verify", checked.result)
    retain("replay-verify", replayed.result)
    paired = artifacts / "staged-program.zip"
    exported = sdk.export(request, candidate=candidate, limits=limits, client=verify, output=paired, input_paths=input_paths)
    checked_export(exported.result, fixture)
    require(exported.report == checked.report and exported.candidate == candidate, "Fresh paired export changed checked evidence")
    retain("export-verify", exported.result)
    retain("paired-publication", archive_receipt(exported.result, paired))
    payload = {"request": request, "candidate": candidate, "limits": limits}
    for name in ("missing-machine-wire", "wrong-feedback-bank", "wrong-request-owner"):
        retain(name, rejected(name, lambda name=name: verify_transport.call("check-policy-component-material",
            {**payload, "candidate": changed_graph(candidate, name)})))
    material = changed_candidate(candidate, "material")
    failed = sdk.check(request, candidate=material, limits=limits, client=verify)
    require(failed.status == "not_accepted" and failed.artifact is None and failed.report["assembly_status"] == "fail"
            and failed.report["context_status"] == "unassessed"
            and failed.report["assembly"]["structure"]["content_outcome"] == "fail", "Material edit escaped exact-content rejection")
    retain("changed-material", failed.result)
    retain("rejected-export", rejected("rejected-export", lambda: verify_transport.call("export-policy-component-material", {**payload, "candidate": material})))
    stale = deepcopy(request)
    stale["implementation_request"]["document"]["program"]["source_map"][0]["file"] = "changed_staged_source.py"
    retain("stale-source", rejected("stale-source", lambda: verify_transport.call("check-policy-component-material", {**payload, "request": stale})))
    forged = deepcopy(checked.result)
    forged["report"]["preservation"]["coverage"]["histories"] = 1
    retain("forged-replay", rejected("forged-replay", lambda: verify_transport.call("replay-policy-component-material", {**payload, "report": forged})))
    retain("verify-has-no-producer", rejected("verify-has-no-producer", lambda: verify_transport.call("compile-policy-component-material", {"request": request, "limits": limits})))
    deficient = deficient_capacity(request)
    failed = sdk.check(deficient, candidate=candidate, limits=limits, client=verify)
    require(failed.status == "not_accepted" and failed.artifact is None and failed.report["context_status"] == "fail",
            "Insufficient machine capacity acquired acceptance")
    retain("insufficient-machine-capacity", failed.result)
    retain("capacity-export", rejected("capacity-export", lambda: verify_transport.call("export-policy-component-material", {**payload, "request": deficient})))
    cannot_finish = sdk.compile(completion_request(request), limits=limits, client=core)
    require(cannot_finish.status == "not_accepted" and cannot_finish.artifact is None
            and any(row["id"] == "second_initiation" and row["status"] == "fail" for row in cannot_finish.report["preservation"]["requirements"]),
            "Absent external feedback was promoted to guaranteed completion")
    retain("completion-without-feedback", cannot_finish.result)


def run(args: argparse.Namespace) -> dict:
    root = Path(__file__).resolve().parents[1]
    hosted, source, before = identity(root), source_identity(), source_snapshot(root)
    paths = {role: getattr(args, role).resolve(strict=True) for role in NATIVE_PATHS}
    require(all(path == (root / NATIVE_PATHS[role]).resolve() for role, path in paths.items()), "Use the exact current hosted native build")
    binaries = {role: pin(root, relative, executable=True) for role, relative in NATIVE_PATHS.items()}
    fixture = checked_fixture(root, args.fixture)
    inputs = {name: pin(root, name) for name in INPUTS}
    output = args.output.resolve()
    require(output == (root / OUTPUT).resolve() and not args.output.is_symlink() and not output.exists(), "Use the new fixed staged SDK receipt path")
    artifacts = output.with_suffix("")
    artifacts.mkdir(exist_ok=False)
    result = {"schema_version": SCHEMA, "status": "incomplete", "acceptance": False,
        "identity": hosted, "source_identity": source, "python": platform.python_version(), "binary_sha256": binaries,
        "inputs": inputs, "authoring": None, "observations": [], "python_semantic_authority": "forbidden",
        "scope": "Hosted source-tree staged SDK witness; installed, release, empirical and human-use acceptance remain separate."}
    boundary, previous = None, sys.getprofile()
    start = time.monotonic()
    def save():
        raw = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        require(len(raw) <= MAX_RECEIPT, "Staged SDK receipt exceeds its byte bound")
        output.write_bytes(raw)
    def retain(name, value):
        from biocompiler.core_client import encode_json
        index = len(result["observations"])
        require(index < len(OBSERVATIONS) and name == OBSERVATIONS[index], "Changed staged observation order")
        raw = encode_json(value)
        require(len(raw) <= MAX_EVIDENCE, "Staged SDK observation exceeds its evidence bound")
        path = artifacts / (name + ".json")
        with path.open("xb") as stream:
            stream.write(raw)
        result["observations"].append({"name": name, "path": str(path.relative_to(output.parent)),
            "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
        save()
    try:
        sys.path.insert(0, str(root / "src"))
        spec = importlib.util.find_spec("biocompiler")
        require(spec is not None and Path(spec.origin).resolve() == root / "src/biocompiler/__init__.py", "Foreign staged SDK package")
        request, result["authoring"] = author_request(fixture["request"])
        boundary = ComponentBoundary(root / "src/biocompiler")
        sys.meta_path.insert(0, boundary)
        sys.setprofile(boundary.trace)
        from biocompiler.core_client import CoreClient
        from biocompiler.core_policy_component_material import PolicyComponentMaterialClient
        from biocompiler.policy import component_material as sdk
        core = PolicyComponentMaterialClient(CoreClient(paths["core"], role="core", expected_sha256=binaries["core"]["sha256"], timeout_seconds=90))
        transport = CoreClient(paths["verify"], role="verify", expected_sha256=binaries["verify"]["sha256"], timeout_seconds=90)
        verify = PolicyComponentMaterialClient(transport)
        exercise(fixture, request, core, transport, verify, sdk, retain, artifacts, tuple(root / name for name in INPUTS))
        check_census(row["name"] for row in result["observations"])
        result["parent_imports"] = boundary.origins()
        result["status"] = "passed"
    except Exception as error:
        result.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        sys.setprofile(previous)
        if boundary is not None:
            sys.meta_path.remove(boundary)
        result["elapsed_seconds"] = round(time.monotonic() - start, 3)
        try:
            require(identity(root) == hosted and source_identity() == source and source_snapshot(root) == before
                    and {name: pin(root, name) for name in INPUTS} == inputs
                    and {role: pin(root, relative, executable=True) for role, relative in NATIVE_PATHS.items()} == binaries,
                    "Staged source, fixture, native bytes or hosted identity changed during execution")
            result["source_snapshot_sha256"] = canonical_digest(before)
        except Exception as error:
            result.update(status="failed", source_error=str(error))
        save()
        require(result["status"] == "passed", result.get("source_error", result.get("error", "Incomplete staged SDK witness")))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--verify", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(run(parser.parse_args()), sort_keys=True))


if __name__ == "__main__":
    main()
