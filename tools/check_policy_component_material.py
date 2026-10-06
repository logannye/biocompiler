"""Hosted development witness: Python DSL through exact component mRNA export.

Source fixtures come from the private domain-only declaration emitter, never a
producer. Native Core and producer-free Verify perform all runtime semantics.
This is focused development feedback, not installed or release acceptance.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
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
    from check_policy_material import MaterialBoundary, changed_candidate, archive_receipt, OBLIGATIONS, CONTEXT_DISCHARGES
except ModuleNotFoundError:
    from tools.check_policy_core import canonical_digest, digest_file, read_json
    from tools.check_policy_development import identity, source_snapshot, pin
    from tools.check_policy_material import MaterialBoundary, changed_candidate, archive_receipt, OBLIGATIONS, CONTEXT_DISCHARGES

SCHEMA = "biocompiler.policy_component_sdk_development.v0.1"
FIXTURE_SCHEMA = "biocompiler.policy_component_original_fixture.v0.1"
INPUTS = (
    "core/test/data/policy_material_request_v01.json", "core/test/data/policy_material_state_v01.json",
    "core/test/policy_component_support/literals.ml", "core/test/policy_component_support/requests.ml",
)
NATIVE_PATHS = {"core": "core/_build/default/bin/core/main.exe", "verify": "core/_build/default/bin/verify/main.exe"}
EXPECTED = {
    "A": {"sequence": "CCAUGGCUUAAGGAAAA", "carriers": 96, "nodes": 15, "wires": 22},
    "B": {"sequence": "CGCAUGGCUUAAGGAAAA", "carriers": 107, "nodes": 17, "wires": 25},
}
MAX_RECEIPT = 1024 * 1024
MAX_EVIDENCE = 9 * 1024 * 1024


class ComponentBoundary(MaterialBoundary):
    @staticmethod
    def allowed(name: str) -> bool:
        return name == "biocompiler.core_policy_component_material" or MaterialBoundary.allowed(name)


def source_document(original: dict, state_reading: bool):
    """Independently author the complete source; supplied models remain external."""
    from biocompiler import policy as p
    try:
        from generate_policy_exclusion_fixture import build_request
    except ModuleNotFoundError:
        from tools.generate_policy_exclusion_fixture import build_request
    authored = build_request()
    definitions = original["document"]["program"]["semantics"]["definitions"]
    authored_definitions = p.to_data(authored.program.semantics)["definitions"]
    if (definitions[:len(authored_definitions)] != authored_definitions or len(definitions) != len(authored_definitions) + 1
            or definitions[-1]["id"] != "fixture.realization.primitives"):
        raise AssertionError("Original realization definitions changed the independent Python recipe")
    semantics = replace(authored.program.semantics,
        definitions=(*authored.program.semantics.definitions, p.from_data(definitions[-1], p.SemanticDefinition)))
    authored = replace(authored, program=replace(authored.program, semantics=semantics),
        implementations=p.from_data(original["document"]["implementations"], p.ImplementationCatalogLock))
    if state_reading:
        selected = next(value for value in authored.program.declarations if isinstance(value, p.StateStore) and value.id == "selected")
        declarations = tuple(replace(value, when=p.all_of(value.when, p.not_(selected.expression)),
            assignments=(value.assignments[0], replace(value.assignments[1], value=selected.expression)))
            if isinstance(value, p.Rule) and value.id == "select" else value for value in authored.program.declarations)
        authored = replace(authored, program=replace(authored.program, id="state.prestate_and_guard", declarations=declarations,
            source_map=tuple(replace(span, file="policy_state_prestate_and_guard.py") for span in authored.program.source_map)))
    if p.to_data(authored) != original["document"]:
        raise AssertionError("Python DSL document differs from the independent complete original")
    return authored, {"phase": "python_authoring_before_native_semantic_guard", "runtime_semantics": "not_executed",
        "recipe_sha256": digest_file(Path(build_request.__code__.co_filename)),
        "source_artifact_digest": canonical_digest(p.to_data(authored)), "declarations": len(authored.program.declarations)}


def author_request(original: dict, state_reading: bool) -> tuple[dict, dict]:
    from biocompiler.policy.implementation import prepare_request as prepare_implementation
    from biocompiler.policy.component_material import prepare_request
    supplied = original["implementation_request"]
    document, evidence = source_document(supplied, state_reading)
    implementation = prepare_implementation(document, **{key: deepcopy(supplied[key]) for key in
        ("definitions", "operating_domain", "implementation_library", "catalog_bindings", "budgets")})
    result = prepare_request(implementation_request=implementation, **{key: deepcopy(original[key]) for key in
        ("component_library", "composition_rule", "catalog_binding", "input_bindings", "resource_bindings", "context", "budgets")})
    if result != original:
        raise AssertionError("Public request preparation changed complete original component authority")
    evidence.update(implementation_request_digest=canonical_digest(implementation), request_digest=canonical_digest(result))
    return result, evidence


def checked_fixture(root: Path, path: Path) -> dict:
    packet = read_json(path, 4_000_000)
    if (type(packet) is not dict or set(packet) != {"schema_version", "status", "acceptance", "source_sha256", "cases"}
            or packet["schema_version"] != FIXTURE_SCHEMA or packet["status"] != "source_declarations_only" or packet["acceptance"] is not False
            or packet["source_sha256"] != {name: digest_file(root / name) for name in INPUTS}
            or type(packet["cases"]) is not list or [case.get("id") for case in packet["cases"]] != ["A", "B"]):
        raise AssertionError("Original component declarations lack exact current independent source provenance")
    for index, case in enumerate(packet["cases"]):
        if set(case) != {"id", "request", "limits", "expected"}:
            raise AssertionError("Unexpected original component case fields")
        old = read_json(root / INPUTS[index], 4_000_000)
        expected = case["expected"]
        if (case["request"]["implementation_request"] != old["request"]["implementation_request"] or case["limits"] != old["limits"]
                or set(expected) != {"molecules", "carrier_projections", "link_projections", "histories", "transitions", "prefixes_started", "obligations"}
                or expected["obligations"] != OBLIGATIONS or [expected[key] for key in ("histories", "transitions", "prefixes_started")] != [9, 47, 48]
                or [row["sequence"] for row in expected["molecules"]] != [EXPECTED[case["id"]]["sequence"]]
                or len(expected["carrier_projections"]) != EXPECTED[case["id"]]["carriers"]
                or [row["link"] for row in expected["link_projections"]] != ["product", "request", "authorization"]):
            raise AssertionError("Independent source/domain/material literal inventory changed")
    return packet


def checked_result(result: dict, case: dict) -> None:
    from biocompiler.core_policy_component_material import ACCEPTED_STATUS, CLAIM_SCOPE, PREMISE
    report, candidate, expected = result["report"], result["candidate"], case["expected"]
    if (report["status"] != ACCEPTED_STATUS or report["claim_scope"] != CLAIM_SCOPE or report["premise"] != PREMISE
            or report["assembly_status"] != "pass" or report["context_status"] != "pass"
            or report["all_original_obligations_discharged"] is not True or report["empirical"] != "unassessed"
            or report["artifact"] != "withheld" or report["export"] != "withheld"
            or [row["obligation"] for row in report["obligations"]] != OBLIGATIONS
            or any(row["status"] != "discharged" for row in report["obligations"])
            or [row["id"] for row in report["context"]["discharges"]] != CONTEXT_DISCHARGES):
        raise AssertionError("Complete source-to-material conjunction or original obligations differ")
    preservation = report["preservation"]
    if (preservation["coverage"]["complete"] is not True
            or [preservation["coverage"][key] for key in ("histories", "transitions", "prefixes_started", "matched_prefixes")] != [9, 47, 48, 48]
            or [row["id"] for row in preservation["requirements"]] != ["request_progress", "initiation_progress", "exclusive_selection"]
            or any(row["status"] != "pass" or row["histories"]["pass"] != 9 for row in preservation["requirements"])):
        raise AssertionError("Complete bounded domain or hard requirements changed")
    if (candidate["construction"]["inventory"]["molecules"] != expected["molecules"]
            or report["assembly"]["carrier_projections"] != expected["carrier_projections"]
            or len(candidate["implementation"]["nodes"]) != EXPECTED[case["id"]]["nodes"]
            or len(candidate["implementation"]["wires"]) != EXPECTED[case["id"]]["wires"]):
        raise AssertionError("Exact complete molecule or original component projection differs")
    # Only alpha-renaming comes from the untrusted proposal. Original endpoints,
    # sites, join and order come from independently authored source declarations.
    bindings = {(row["slot"], row["node"]): row["actual"] for row in candidate["assembly_proposal"]["nodes"]}
    links = deepcopy(expected["link_projections"])
    for row in links:
        for key in ("producer_endpoint", "consumer_endpoint"):
            local = row[key]
            row[key] = {"node": bindings[(local["slot"], local["node"])], "port": local["port"]}
    if report["assembly"]["link_projections"] != links:
        raise AssertionError("Complete declared cross-link projections changed")


def run(args: argparse.Namespace) -> dict:
    root = Path(__file__).resolve().parents[1]
    hosted, before = identity(root), source_snapshot(root)  # before any native launch
    binary_paths = {"core": args.core.resolve(strict=True), "verify": args.verify.resolve(strict=True)}
    if any(path != (root / NATIVE_PATHS[role]).resolve() for role, path in binary_paths.items()):
        raise AssertionError("Development witness requires the exact current build's Core and Verify paths")
    binaries = {role: pin(root, NATIVE_PATHS[role], executable=True) for role in binary_paths}
    fixture = checked_fixture(root, args.fixture)
    fixture_pin = digest_file(args.fixture)
    output = args.output.resolve()
    if output.parent != (root / "generated/development-feedback").resolve() or output.suffix != ".json" or output.exists():
        raise AssertionError("Use one new JSON development receipt in the fixed evidence directory")
    artifacts = output.with_suffix("")
    artifacts.mkdir(exist_ok=False)
    result = {"schema_version": SCHEMA, "status": "incomplete", "acceptance": False, "identity": hosted,
        "scope": "Hosted source-tree Python DSL/component SDK witness only; installed and release gates remain separate.",
        "python": platform.python_version(), "fixture_sha256": fixture_pin, "binary_sha256": binaries,
        "authoring": [], "observations": [], "python_semantic_authority": "forbidden"}
    boundary = None
    previous_profile = sys.getprofile()
    start = time.monotonic()

    def save_report():
        raw = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        if len(raw) > MAX_RECEIPT:
            raise AssertionError("Development SDK receipt exceeded its bound")
        output.write_bytes(raw)

    def retain(case: str, name: str, value: dict):
        from biocompiler.core_client import encode_json
        raw = encode_json(value)
        if len(raw) > MAX_EVIDENCE:
            raise AssertionError("Complete SDK observation exceeded its evidence bound")
        path = artifacts / f"{case}-{name}.json"
        with path.open("xb") as stream:
            stream.write(raw)
        result["observations"].append({"case": case, "name": name, "path": str(path.relative_to(output.parent)),
            "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
        save_report()

    try:
        sys.path.insert(0, str(root / "src"))
        spec = importlib.util.find_spec("biocompiler")
        if spec is None or Path(spec.origin).resolve() != root / "src/biocompiler/__init__.py":
            raise AssertionError("Development SDK resolved a foreign package")
        cases = []
        for case in fixture["cases"]:
            request, authored = author_request(case["request"], case["id"] == "B")
            result["authoring"].append({"case": case["id"], **authored})
            cases.append((case, request))
        drivers = [request["component_library"]["components"][1] for _, request in cases]
        if drivers[0] != drivers[1]:
            raise AssertionError("Reusable driver full original authority changed across source programs")
        result["shared_driver_fingerprint"] = canonical_digest(drivers[0])
        boundary = ComponentBoundary(root / "src/biocompiler")
        sys.meta_path.insert(0, boundary)
        sys.setprofile(boundary.trace)
        from biocompiler.core_client import CoreClient, CoreRejected
        from biocompiler.core_policy_component_material import PolicyComponentMaterialClient
        from biocompiler.policy import component_material as sdk
        core = PolicyComponentMaterialClient(CoreClient(binary_paths["core"], role="core", expected_sha256=binaries["core"]["sha256"], timeout_seconds=90))
        verify_transport = CoreClient(binary_paths["verify"], role="verify", expected_sha256=binaries["verify"]["sha256"], timeout_seconds=90)
        verify = PolicyComponentMaterialClient(verify_transport)

        def rejected(case, name, codes, action):
            try:
                action()
            except CoreRejected as error:
                response = error.response
                if response.result is not None or not response.diagnostics or {row.code for row in response.diagnostics} != set(codes):
                    raise AssertionError("Control failed at an unrelated native boundary: " + name) from error
                retain(case, name, {"status": response.status,
                    "diagnostics": [{"code": row.code, "message": row.message, "path": row.path} for row in response.diagnostics]})
            else:
                raise AssertionError("Native mutation acquired acceptance: " + name)

        for case, request in cases:
            label, limits = case["id"], case["limits"]
            compiled = sdk.compile(request, limits=limits, client=core)
            checked_result(compiled.result, case)
            if compiled.artifact is not None:
                raise AssertionError("Compilation exported without a fresh export request")
            retain(label, "compile", compiled.result)
            candidate = compiled.candidate
            checked = sdk.check(request, candidate=candidate, limits=limits, client=verify)
            replayed = sdk.replay(request, candidate=candidate, limits=limits, report=checked.result, client=verify)
            if compiled.result != checked.result or checked.result != replayed.result:
                raise AssertionError("Fresh producer-free Verify/check/replay changed complete evidence")
            retain(label, "check-verify", checked.result)
            retain(label, "replay-verify", replayed.result)
            paired = artifacts / f"{label}-program.zip"
            exported = sdk.export(request, candidate=candidate, limits=limits, client=verify, output=paired,
                input_paths=(args.fixture, *(root / name for name in INPUTS)))
            if exported.report != checked.report or exported.candidate != candidate:
                raise AssertionError("Fresh atomic export changed checked source-to-material evidence")
            checked_result(exported.result, case)
            retain(label, "export-verify", exported.result)
            retain(label, "paired-publication", archive_receipt(exported.result, paired))
            for kind in ("guard", "state", "feedback", "configuration"):
                codes = {"policy_implementation_contract" if kind == "configuration" else "policy_implementation_source_binding"}
                rejected(label, "changed-" + kind, codes,
                    lambda kind=kind: sdk.check(request, candidate=changed_candidate(candidate, kind), limits=limits, client=verify))
            changed = changed_candidate(candidate, "material")
            failed = sdk.check(request, candidate=changed, limits=limits, client=verify)
            if (failed.status != "not_accepted" or failed.artifact is not None or failed.report["assembly_status"] != "fail"
                    or failed.report["context_status"] != "unassessed"
                    or failed.report["assembly"]["structure"]["content_outcome"] != "fail"
                    or [row["obligation"] for row in failed.report["obligations"]] != OBLIGATIONS
                    or any(row["status"] != "unresolved" for row in failed.report["obligations"])):
                raise AssertionError("Changed material did not fail fresh exact-content checking")
            retain(label, "changed-material", failed.result)
            rejected(label, "rejected-export", {"policy_component_material_export_not_accepted"},
                lambda: verify.export(request, changed, limits))
            rejected(label, "verify-has-no-producer", {"unsupported_operation"},
                lambda: verify_transport.call("compile-policy-component-material", {"request": request, "limits": limits}))
            altered = deepcopy(request)
            altered["implementation_request"]["document"]["program"]["source_map"][0]["file"] = "edited_after_component_compile.py"
            rejected(label, "stale-source", {"policy_correspondence"}, lambda: verify.check(altered, candidate, limits))
        result["parent_imports"] = boundary.origins()
        result["status"] = "passed"
    except Exception as error:
        result.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        sys.setprofile(previous_profile)
        if boundary is not None:
            sys.meta_path.remove(boundary)
        result["elapsed_seconds"] = round(time.monotonic() - start, 3)
        try:
            if (identity(root) != hosted or source_snapshot(root) != before or digest_file(args.fixture) != fixture_pin
                    or {role: pin(root, NATIVE_PATHS[role], executable=True) for role in binary_paths} != binaries):
                raise AssertionError("Original source, fixture, run or native bytes changed during SDK checking")
            result["source_snapshot_sha256"] = canonical_digest(before)
        except Exception as error:
            result.update(status="failed", source_error=str(error))
        save_report()
        if result["status"] != "passed":
            raise AssertionError(result.get("source_error", result.get("error", "Incomplete component SDK witness")))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("fixture", "core", "verify", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    result = run(parser.parse_args())
    print(json.dumps({"status": result["status"], "acceptance": False, "observations": len(result["observations"])}))


if __name__ == "__main__":
    main()
