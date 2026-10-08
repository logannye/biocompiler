"""Hosted two-observation witness under original, independently authored inputs.

Preserves both independent channels and the complete component campaign controls.
Native Core and producer-free Verify own acceptance; this receipt is development
feedback, not installed or release acceptance.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import fields, is_dataclass, replace
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
        source_document as legacy_source_document, exercise_cases,
    )
    from check_policy_material import OBLIGATIONS as LEGACY_OBLIGATIONS, CONTEXT_DISCHARGES as LEGACY_DISCHARGES
except ModuleNotFoundError:
    from tools.check_policy_core import canonical_digest, digest_file, read_json
    from tools.check_policy_development import identity, pin, source_snapshot
    from tools.check_policy_component_material import (
        ComponentBoundary, NATIVE_PATHS, MAX_RECEIPT, MAX_EVIDENCE, CASE_NAMES,
        source_document as legacy_source_document, exercise_cases,
    )
    from tools.check_policy_material import OBLIGATIONS as LEGACY_OBLIGATIONS, CONTEXT_DISCHARGES as LEGACY_DISCHARGES

SCHEMA = "biocompiler.policy_two_observation_sdk_development.v0.1"
FIXTURE_SCHEMA = "biocompiler.policy_two_observation_original_fixture.v0.1"
INPUTS = (
    "core/test/data/policy_material_request_v01.json",
    "core/test/data/policy_material_state_v01.json",
    "core/test/policy_component_support/literals.ml",
    "core/test/policy_instance_support/literals.ml",
    "core/test/policy_instance_support/requests.ml",
    "core/test/policy_prerequisite_support/literals.ml",
    "core/test/policy_prerequisite_support/requests.ml",
    "core/test/policy_two_observation_support/literals.ml",
    "core/test/policy_two_observation_support/requests.ml",
)
SEQUENCES = {"A": "CCAUGGCUUAAGGAAAA", "B": "CCAUGGCUUAAGGAAAA"}
ENVIRONMENT_ID = "fixture.prerequisite_environment"
ENVIRONMENT_MEANING = "Supplied exact finite environment prerequisite; no new source behavior or empirical evidence."
OBLIGATIONS = sorted([*LEGACY_OBLIGATIONS, "semantic_definition:" + ENVIRONMENT_ID])
CONTEXT_DISCHARGES = sorted([*LEGACY_DISCHARGES, "semantic_definition:" + ENVIRONMENT_ID])


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def checked_fixture(root, path):
    value = read_json(path, 4_000_000)
    require(set(value) == {"schema_version", "status", "acceptance", "source_sha256", "cases"}
            and value["schema_version"] == FIXTURE_SCHEMA
            and value["status"] == "source_declarations_only" and value["acceptance"] is False,
            "Wrong prerequisite original packet")
    require(value["source_sha256"] == {name: digest_file(root / name) for name in INPUTS},
            "Prerequisite originals differ from exact independent source declarations")
    require([case["id"] for case in value["cases"]] == ["A", "B"], "Incomplete original case census")
    for index, case in enumerate(value["cases"]):
        require(set(case) == {"id", "request", "limits", "expected"}, "Unexpected original case fields")
        expected = case["expected"]
        require(set(expected) == {"sequence", "molecules", "carrier_projections", "link_projections",
                    "histories", "transitions", "prefixes_started", "obligations", "prerequisite_closure"}
                and expected["sequence"] == SEQUENCES[case["id"]]
                and [expected[key] for key in ("histories", "transitions", "prefixes_started")] == [36, 42, 43]
                and expected["obligations"] == OBLIGATIONS,
                "Original prerequisite sequence/domain/obligations changed")
        expected_original, old_limits = independent_original(root, index == 1)
        outer = case["request"]
        require(outer["schema_version"] == "biocompiler.policy_component_material_request.v0.4"
                and outer["profile"] == outer["context"]["profile"]
                    == "biocompiler.policy_instance_two_observation_prerequisite_mrna.v0.1"
                and outer["implementation_request"] == expected_original and case["limits"] == old_limits,
                "Two-observation witness changed independently authored source, models, domain or limits")
    return value


def environment_definition():
    """Independent original declaration; not a parsed native expectation."""
    return {"$type": "SemanticDefinition", "id": ENVIRONMENT_ID, "version": "1", "category": "environment",
            "meaning": ENVIRONMENT_MEANING, "parameters": [], "result": None, "clauses": [], "assumptions": [],
            "executor_kind": None, "subject_kind": None}


def interface_reference(original):
    reference = original["document"]["deployment"]["bindings"][0]["chassis"]["interfaces"][0]
    require(reference["id"] == "exclusion.interface", "Original interface authority changed")
    return deepcopy(reference)


def baseline_original(root, state_reading):
    """Retain the existing original inputs and add the same explicit prerequisite."""
    fixture = read_json(Path(root) / INPUTS[int(state_reading)], 4_000_000)
    original = deepcopy(fixture["request"]["implementation_request"])
    original["document"]["program"]["semantics"]["definitions"].append(environment_definition())
    entry = original["document"]["implementations"]["implementations"][0]
    entry["dependencies"] = [interface_reference(original)]
    original["catalog_bindings"][0]["entry_digest"] = canonical_digest(entry)
    return original, fixture["limits"]


def authored_document(root, state_reading):
    """Build the two independent observation declarations using typed Python records."""
    from biocompiler import policy as p
    try:
        from check_policy_prerequisite_material import source_document as prerequisite_document
    except ModuleNotFoundError:
        from tools.check_policy_prerequisite_material import source_document as prerequisite_document
    original, _ = baseline_original(root, state_reading)
    document, evidence = prerequisite_document(original, state_reading)

    def expression(value):
        if isinstance(value, p.Expr) and value.op == "observe":
            require(value.ref.id == "condition", "Unexpected original observation expression")
            return p.all_of(replace(value, ref=replace(value.ref, id="condition_a")),
                            replace(value, ref=replace(value.ref, id="condition_b")))
        if is_dataclass(value):
            return replace(value, **{field.name: expression(getattr(value, field.name)) for field in fields(value)})
        if isinstance(value, tuple):
            return tuple(expression(item) for item in value)
        return value

    declarations = []
    for row in document.program.declarations:
        if isinstance(row, p.Observation):
            declarations.extend((replace(row, id="condition_a", coherence="frame_a"),
                replace(row, id="condition_b", coherence="frame_b", freshness=replace(row.freshness, amount="3"))))
        else:
            declarations.append(expression(row))
    spans = tuple(p.SourceSpan(row.id, "policy_two_observation_source_literal.py", index + 1)
                  for index, row in enumerate(declarations))
    document = replace(document, program=replace(document.program, declarations=tuple(declarations), source_map=spans))
    evidence.update(two_observation_recipe_sha256=digest_file(Path(__file__)),
        source_artifact_digest=canonical_digest(p.to_data(document)), declarations=len(declarations))
    return document, evidence


def independent_original(root, state_reading):
    """Exact supplied source/models/domain recipe, without native interpretation."""
    from biocompiler import policy as p
    original, limits = baseline_original(root, state_reading)
    original.update(schema_version="biocompiler.policy_realization_request.v0.3",
                    profile="biocompiler.policy_two_observation_prerequisite_inputs.v0.1")
    original["document"] = p.to_data(authored_document(root, state_reading)[0])
    domain = original["operating_domain"]
    domain["fixed_observations"] = [
        {"slot": slot, "observation": observation, "available_tick": tick,
         "observed_tick": tick, "status": "valid", "value": tick == 1}
        for tick in (0, 1) for slot in ("e1", "e2") for observation in ("condition_a", "condition_b")]
    domain["observation_factors"] = [
        {"slots": ["e1"], "observation": observation, "ticks": [6],
         "alphabet": "known_truth_and_evidence_status.v1", "age_ticks": [0], "max_rows_per_slot_tick": 1}
        for observation in ("condition_a", "condition_b")]
    domain["feedback_factors"] = []
    models = original["implementation_library"]["models"]
    evidence = next(model for model in models if model["identity"]["id"] == "exclusion.primitive.evidence")
    additions = [("two_observation.primitive.evidence_b", "evidence_bank", {"freshness_ticks": 3})]
    if not state_reading:
        additions.append(("two_observation.primitive.all2", "truth_all", {"arity": 2}))
    for name, primitive, configuration in additions:
        model = deepcopy(evidence)
        model["body"].update(primitive=primitive, configuration=configuration)
        model["identity"].update(id=name, content_fingerprint=canonical_digest(model["body"]))
        model["configuration_digest"] = canonical_digest(configuration)
        models.append(model)
    original["catalog_bindings"][0]["models"] = [deepcopy(model["identity"]) for model in models]
    return original, limits


def source_document(original, state_reading):
    from biocompiler import policy as p
    document, evidence = authored_document(Path(__file__).resolve().parents[1], state_reading)
    require(p.to_data(document) == original["document"],
            "Typed two-observation recipe changed complete original source")
    return document, evidence


def author_request(original, state_reading):
    from biocompiler.policy.implementation import prepare_request as prepare_implementation
    from biocompiler.policy.component_material import prepare_request
    supplied = original["implementation_request"]
    document, evidence = source_document(supplied, state_reading)
    implementation = prepare_implementation(document, prerequisites=True, two_observations=True, **{key: deepcopy(supplied[key]) for key in
        ("definitions", "operating_domain", "implementation_library", "catalog_bindings", "budgets")})
    request = prepare_request(instanced=True, prerequisites=True, two_observations=True, implementation_request=implementation,
        **{key: deepcopy(original[key]) for key in ("component_library", "composition_rule", "catalog_binding",
           "input_bindings", "resource_bindings", "context", "budgets")})
    require(request == original, "Typed authoring changed independently supplied original authority")
    evidence.update(implementation_request_digest=canonical_digest(implementation), request_digest=canonical_digest(request))
    return request, evidence


def checked_result(result, case):
    from biocompiler.core_policy_component_material import ACCEPTED_STATUS, CLAIM_SCOPE, PREMISE, TWO_OBSERVATION_REQUEST_PROFILE
    report, candidate, expected = result["report"], result["candidate"], case["expected"]
    require(report["status"] == ACCEPTED_STATUS and report["profile"] == TWO_OBSERVATION_REQUEST_PROFILE
            and report["claim_scope"] == CLAIM_SCOPE and report["premise"] == PREMISE
            and report["assembly_status"] == report["context_status"] == report["prerequisite_status"] == "pass"
            and report["all_original_obligations_discharged"] is True
            and report["empirical"] == "unassessed" and report["artifact"] == report["export"] == "withheld"
            and [row["obligation"] for row in report["obligations"]] == OBLIGATIONS
            and all(row["status"] == "discharged" for row in report["obligations"])
            and [row["id"] for row in report["context"]["discharges"]] == CONTEXT_DISCHARGES,
            "Prerequisite conjunction changed original obligations or claimed scope")
    closure = deepcopy(report["prerequisites"])
    require(closure == report["context"]["prerequisite_closure"]
            and closure.pop("assembly_fingerprint") == canonical_digest(report["assembly"])
            and closure == expected["prerequisite_closure"],
            "Complete prerequisite graph, providers, original catalog or checked allocations changed")
    for row in report["obligations"]:
        if row["stage"] in ("declared_context", "conditional_component_context_conjunction"):
            require(row["evidence"]["prerequisites"] == canonical_digest(report["prerequisites"]),
                    "Discharged contextual obligation lost its exact prerequisite closure pin")
    preservation = report["preservation"]
    require(preservation["coverage"]["complete"] is True
            and [preservation["coverage"][key] for key in
                 ("histories", "transitions", "prefixes_started", "matched_prefixes")] == [36, 42, 43, 43]
            and [row["id"] for row in preservation["requirements"]]
                == ["request_progress", "initiation_progress", "exclusive_selection"]
            and all(row["status"] == "pass" and row["histories"]["pass"] == 36 for row in preservation["requirements"]),
            "Two-observation result did not completely preserve the independent finite domain")
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
            "Prerequisite witness requires current hosted build paths")
    binaries = {role: pin(root, NATIVE_PATHS[role], executable=True) for role in binary_paths}
    fixture = checked_fixture(root, args.fixture)
    fixture_pin = digest_file(args.fixture)
    output = args.output.resolve()
    require(output.parent == (root / "generated/development-feedback").resolve()
            and output.suffix == ".json" and not output.exists(), "Use a new two-observation development receipt")
    artifacts = output.with_suffix("")
    artifacts.mkdir(exist_ok=False)
    result = {"schema_version": SCHEMA, "status": "incomplete", "acceptance": False, "identity": hosted,
        "scope": "Hosted source-tree two-observation SDK feedback; installed and release acceptance remain separate.",
        "python": platform.python_version(), "fixture_sha256": fixture_pin, "binary_sha256": binaries,
        "authoring": [], "observations": [], "python_semantic_authority": "forbidden"}
    boundary = None
    previous_profile = sys.getprofile()
    start = time.monotonic()

    def save_report():
        raw = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        require(len(raw) <= MAX_RECEIPT, "Two-observation SDK receipt exceeds bound")
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
                "Two-observation SDK resolved a foreign package")
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
                       (args.fixture, *(root / name for name in INPUTS)), validate_result=checked_result, expected_obligations=OBLIGATIONS)
        require([(row["case"], row["name"]) for row in result["observations"]]
                == [(case, name) for case in ("A", "B") for name in CASE_NAMES],
                "Incomplete, duplicated or reordered two-observation SDK observation census")
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
                    "Source, original fixture, run or executable changed during two-observation SDK checking")
            result["source_snapshot_sha256"] = canonical_digest(before)
        except Exception as error:
            result.update(status="failed", source_error=str(error))
        save_report()
        require(result["status"] == "passed", result.get("source_error", result.get("error", "Incomplete two-observation SDK")))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("fixture", "core", "verify", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
