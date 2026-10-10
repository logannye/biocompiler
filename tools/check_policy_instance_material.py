"""Hosted instance-composition witness under original, independently authored inputs.

Uses the unchanged source semantics and complete component campaign controls.
Native Core and producer-free Verify own acceptance; this receipt is development
feedback, not installed or release acceptance.
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
    from check_policy_development import identity, pin, source_snapshot
    from check_policy_component_material import (
        ComponentBoundary, NATIVE_PATHS, MAX_RECEIPT, MAX_EVIDENCE, CASE_NAMES,
        source_document, exercise_cases,
    )
    from check_policy_material import OBLIGATIONS, CONTEXT_DISCHARGES
except ModuleNotFoundError:
    from tools.check_policy_core import canonical_digest, digest_file, read_json
    from tools.check_policy_development import identity, pin, source_snapshot
    from tools.check_policy_component_material import (
        ComponentBoundary, NATIVE_PATHS, MAX_RECEIPT, MAX_EVIDENCE, CASE_NAMES,
        source_document, exercise_cases,
    )
    from tools.check_policy_material import OBLIGATIONS, CONTEXT_DISCHARGES

SCHEMA = "biocompiler.policy_instance_sdk_development.v0.1"
FIXTURE_SCHEMA = "biocompiler.policy_instance_original_fixture.v0.1"
INPUTS = (
    "core/test/data/policy_material_request_v01.json",
    "core/test/data/policy_material_state_v01.json",
    "core/test/policy_component_support/literals.ml",
    "core/test/policy_instance_support/literals.ml",
    "core/test/policy_instance_support/requests.ml",
)
SEQUENCES = {"A": "CCAUGGCUUAAGGAAAA", "B": "CCAUGGCUUAAGGAAAA"}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def checked_fixture(root, path):
    value = read_json(path, 4_000_000)
    require(set(value) == {"schema_version", "status", "acceptance", "source_sha256", "cases"}
            and value["schema_version"] == FIXTURE_SCHEMA
            and value["status"] == "source_declarations_only" and value["acceptance"] is False,
            "Wrong instance original packet")
    require(value["source_sha256"] == {name: digest_file(root / name) for name in INPUTS},
            "Instance originals differ from exact independent source declarations")
    require([case["id"] for case in value["cases"]] == ["A", "B"], "Incomplete original case census")
    for case in value["cases"]:
        expected = case["expected"]
        require(expected["sequence"] == SEQUENCES[case["id"]]
                and [expected[key] for key in ("histories", "transitions", "prefixes_started")] == [9, 47, 48]
                and expected["obligations"] == OBLIGATIONS,
                "Original instance sequence/domain/obligations changed")
    return value


def author_request(original, state_reading):
    from biocompiler.policy.implementation import prepare_request as prepare_implementation
    from biocompiler.policy.component_material import prepare_request
    supplied = original["implementation_request"]
    document, evidence = source_document(supplied, state_reading)
    implementation = prepare_implementation(document, **{key: deepcopy(supplied[key]) for key in
        ("definitions", "operating_domain", "implementation_library", "catalog_bindings", "budgets")})
    request = prepare_request(instanced=True, implementation_request=implementation,
        **{key: deepcopy(original[key]) for key in ("component_library", "composition_rule", "catalog_binding",
           "input_bindings", "resource_bindings", "context", "budgets")})
    require(request == original, "Typed authoring changed independently supplied original authority")
    return request, evidence


def checked_result(result, case):
    from biocompiler.core_policy_component_material import ACCEPTED_STATUS, CLAIM_SCOPE, PREMISE, INSTANCE_REQUEST_PROFILE
    report, candidate, expected = result["report"], result["candidate"], case["expected"]
    require(report["status"] == ACCEPTED_STATUS and report["profile"] == INSTANCE_REQUEST_PROFILE
            and report["claim_scope"] == CLAIM_SCOPE and report["premise"] == PREMISE
            and report["assembly_status"] == report["context_status"] == "pass"
            and report["all_original_obligations_discharged"] is True
            and report["empirical"] == "unassessed" and report["artifact"] == report["export"] == "withheld"
            and [row["obligation"] for row in report["obligations"]] == OBLIGATIONS
            and all(row["status"] == "discharged" for row in report["obligations"])
            and [row["id"] for row in report["context"]["discharges"]] == CONTEXT_DISCHARGES,
            "Instance conjunction changed original obligations or claimed scope")
    preservation = report["preservation"]
    require(preservation["coverage"]["complete"] is True
            and [preservation["coverage"][key] for key in
                 ("histories", "transitions", "prefixes_started", "matched_prefixes")] == [9, 47, 48, 48]
            and all(row["status"] == "pass" and row["histories"]["pass"] == 9 for row in preservation["requirements"]),
            "Instance result did not completely preserve the unchanged finite domain")
    require(candidate["construction"]["inventory"]["molecules"] == expected["molecules"]
            and report["assembly"]["carrier_projections"] == expected["carrier_projections"],
            "Exact molecule or instance-qualified carrier correspondence changed")
    bindings = {(row["slot"], row["node"]): row["actual"] for row in candidate["assembly_proposal"]["nodes"]}
    links = deepcopy(expected["link_projections"])
    for row in links:
        for key in ("producer_endpoint", "consumer_endpoint"):
            local = row[key]
            row[key] = {"node": bindings[(local["slot"], local["node"])], "port": local["port"]}
    require(report["assembly"]["link_projections"] == links, "Complete original instance link projections changed")


def run(args):
    root = Path(__file__).resolve().parents[1]
    hosted, before = identity(root), source_snapshot(root)
    binary_paths = {"core": args.core.resolve(strict=True), "verify": args.verify.resolve(strict=True)}
    require(all(path == (root / NATIVE_PATHS[role]).resolve() for role, path in binary_paths.items()),
            "Instance witness requires current hosted build paths")
    binaries = {role: pin(root, NATIVE_PATHS[role], executable=True) for role in binary_paths}
    fixture = checked_fixture(root, args.fixture)
    fixture_pin = digest_file(args.fixture)
    output = args.output.resolve()
    require(output.parent == (root / "generated/development-feedback").resolve()
            and output.suffix == ".json" and not output.exists(), "Use a new instance development receipt")
    artifacts = output.with_suffix("")
    artifacts.mkdir(exist_ok=False)
    result = {"schema_version": SCHEMA, "status": "incomplete", "acceptance": False, "identity": hosted,
        "scope": "Hosted source-tree instance SDK feedback; installed and release acceptance remain separate.",
        "python": platform.python_version(), "fixture_sha256": fixture_pin, "binary_sha256": binaries,
        "authoring": [], "observations": [], "python_semantic_authority": "forbidden"}
    boundary = None
    previous_profile = sys.getprofile()
    start = time.monotonic()

    def save_report():
        raw = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        require(len(raw) <= MAX_RECEIPT, "Instance SDK receipt exceeds bound")
        output.write_bytes(raw)

    def retain(case, name, value):
        from biocompiler.core_client import encode_json
        raw = encode_json(value)
        require(len(raw) <= MAX_EVIDENCE, "Instance observation exceeds evidence bound")
        path = artifacts / f"{case}-{name}.json"
        with path.open("xb") as stream:
            stream.write(raw)
        result["observations"].append({"case": case, "name": name, "path": str(path.relative_to(output.parent)),
            "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
        save_report()

    try:
        sys.path.insert(0, str(root / "src"))
        spec = importlib.util.find_spec("biocompiler")
        require(spec is not None and Path(spec.origin).resolve() == root / "src/biocompiler/__init__.py",
                "Instance SDK resolved a foreign package")
        cases = []
        for case in fixture["cases"]:
            request, authored = author_request(case["request"], case["id"] == "B")
            result["authoring"].append({"case": case["id"], **authored})
            cases.append((case, request))
        boundary = ComponentBoundary(root / "src/biocompiler")
        sys.meta_path.insert(0, boundary)
        sys.setprofile(boundary.trace)
        from biocompiler.core_client import CoreClient
        from biocompiler.core_policy_component_material import PolicyComponentMaterialClient
        from biocompiler.policy import component_material as sdk
        core = PolicyComponentMaterialClient(CoreClient(binary_paths["core"], role="core",
            expected_sha256=binaries["core"]["sha256"], timeout_seconds=90))
        verify_transport = CoreClient(binary_paths["verify"], role="verify",
            expected_sha256=binaries["verify"]["sha256"], timeout_seconds=90)
        verify = PolicyComponentMaterialClient(verify_transport)
        exercise_cases(cases, core, verify_transport, verify, sdk, retain, artifacts,
                       (args.fixture, *(root / name for name in INPUTS)), validate_result=checked_result)
        require([(row["case"], row["name"]) for row in result["observations"]]
                == [(case, name) for case in ("A", "B") for name in CASE_NAMES],
                "Incomplete, duplicated or reordered instance SDK observation census")
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
            require(identity(root) == hosted and source_snapshot(root) == before and digest_file(args.fixture) == fixture_pin
                    and {role: pin(root, NATIVE_PATHS[role], executable=True) for role in binary_paths} == binaries,
                    "Source, original fixture, run or executable changed during instance SDK checking")
            result["source_snapshot_sha256"] = canonical_digest(before)
        except Exception as error:
            result.update(status="failed", source_error=str(error))
        save_report()
        require(result["status"] == "passed", result.get("source_error", result.get("error", "Incomplete instance SDK")))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("fixture", "core", "verify", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
