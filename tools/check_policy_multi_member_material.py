"""Hosted exact two-member, two-product staged material witness.

Independent originals and literal outputs; fresh native Core and Verify own
semantics. This campaign supplies development evidence, never empirical proof.
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
    from check_policy_development import identity, pin, source_snapshot
    from check_policy_component_material import ComponentBoundary, NATIVE_PATHS, MAX_RECEIPT, MAX_EVIDENCE, CASE_NAMES
    from check_policy_material import archive_receipt, changed_candidate as legacy_changed_candidate
    from check_policy_staged_component_material import REQUIREMENT_HISTORIES
except ModuleNotFoundError:
    from tools.check_policy_core import canonical_digest, digest_file, read_json
    from tools.check_policy_development import identity, pin, source_snapshot
    from tools.check_policy_component_material import ComponentBoundary, NATIVE_PATHS, MAX_RECEIPT, MAX_EVIDENCE, CASE_NAMES
    from tools.check_policy_material import archive_receipt, changed_candidate as legacy_changed_candidate
    from tools.check_policy_staged_component_material import REQUIREMENT_HISTORIES

SCHEMA = "biocompiler.policy_multi_member_sdk_development.v0.1"
FIXTURE_SCHEMA = "biocompiler.policy_multi_member_original_fixture.v0.1"
INPUTS = ("core/test/data/policy_staged_material_v01.json", "core/test/policy_multi_member_support/literals.ml",
          "core/test/policy_multi_member_support/requests.ml")
TRANSPORT_ID = "fixture.inter_member_transport"
TRANSPORT_MEANING = "Supplied complete identity transfer between two coavailable RNA members; no empirical claim."
SEQUENCES = {"A": ["CCAUGGCUUAAGGAAAA", "CCAUGCCUUAAGGAAAA"],
             "B": ["CCAUGGCUUAAGGAAAA", "CCAUGGGUUAAGGAAAA"]}
OBLIGATIONS = sorted([
    "policy_execution_and_lowering", "temporal_and_uncertainty_semantics", "safety_and_progress_satisfaction",
    "realizability_and_target_suitability", "arbitration_fairness_and_conflict_resolution",
    "effect_authorization_feedback_and_cancellation", "machine_reachability_termination_and_progress",
    "chassis_capability_and_delivery_suitability", "implementation_catalog_applicability", "requested_assurance_not_established",
    "implementation_applicability:multi_member.staged.primitives", "requirement_satisfaction:first_initiation",
    "requirement_satisfaction:second_initiation", *["semantic_definition:" + name for name in
    ("staged.interface", "staged.encounter", "staged.observation", "staged.operation", "staged.lifecycle",
     "exclusion.chassis", "exclusion.environment", "exclusion.delivery", "fixture.realization.primitives", TRANSPORT_ID)]])
CONTEXT_DISCHARGES = sorted(["chassis_capability_and_delivery_suitability", *["semantic_definition:" + name for name in
    ("staged.interface", "exclusion.chassis", "exclusion.environment", "exclusion.delivery", TRANSPORT_ID)]])


def require(condition, message):
    if not condition:
        raise AssertionError(message)


_require = require


def authored_document(root, alternate):
    """Typed transformations of the unchanged independently supplied staged source."""
    from biocompiler import policy as p
    baseline = read_json(root / INPUTS[0], 4_000_000)["request"]["implementation_request"]["document"]
    document = p.from_data(baseline, p.BuildRequest)
    old = next(row for row in document.program.declarations if isinstance(row, p.Parameter))
    first = replace(old, id="product_a")
    second = replace(old, id="product_b", value="fixture.product.gamma" if alternate else "fixture.product.beta")
    declarations = []
    for row in document.program.declarations:
        if isinstance(row, p.Parameter):
            declarations.extend((first, second))
        elif isinstance(row, p.Effect):
            value = first if row.id == "stage_one" else second
            declarations.append(replace(row, parameters=(p.Argument("product", p.Expr("parameter", p.TEXT, ref=p.ref(value))),)))
        else:
            declarations.append(row)
    transport = p.SemanticDefinition(TRANSPORT_ID, "1", "interface", TRANSPORT_MEANING)
    program = replace(document.program, declarations=tuple(declarations),
        semantics=replace(document.program.semantics, definitions=(*document.program.semantics.definitions, transport)),
        source_map=tuple(p.SourceSpan(row.id, "policy_multi_member_source_literal.py", index + 1,
            pattern="regimen" if row.id.startswith("regimen/") else None) for index, row in enumerate(declarations)))
    entry = replace(document.implementations.implementations[0], id="multi_member.staged.primitives", dependencies=(transport.ref,))
    document = replace(document, program=program,
        deployment=replace(document.deployment, payload=replace(document.deployment.payload, member_count=2, orf_count=2, product_count=2)),
        implementations=replace(document.implementations, implementations=(entry,)))
    return document, {"phase":"python_authoring_before_native_semantic_guard", "runtime_semantics":"not_executed",
        "recipe_sha256":digest_file(Path(__file__)), "source_artifact_digest":canonical_digest(p.to_data(document)),
        "declarations":len(declarations), "transport_definition":TRANSPORT_ID,
        "catalog_dependencies":[p.to_data(transport.ref)]}


def independent_original(root, alternate):
    from biocompiler import policy as p
    baseline = read_json(root / INPUTS[0], 4_000_000)
    original = deepcopy(baseline["request"]["implementation_request"])
    original.update(schema_version="biocompiler.policy_realization_request.v0.4",
                    profile="biocompiler.policy_multi_product_prerequisite_inputs.v0.1")
    original["document"] = p.to_data(authored_document(root, alternate)[0])
    models = original["implementation_library"]["models"]
    product = deepcopy(next(model for model in models if model["body"]["primitive"] == "product_constant"))
    product["body"]["configuration"] = {"product":"fixture.product.gamma" if alternate else "fixture.product.beta"}
    product["identity"].update(id="multi_member.primitive.product_b", content_fingerprint=canonical_digest(product["body"]))
    product["configuration_digest"] = canonical_digest(product["body"]["configuration"])
    models.append(product)
    entry = original["document"]["implementations"]["implementations"][0]
    original["catalog_bindings"][0].update(entry_id=entry["id"], entry_digest=canonical_digest(entry),
                                          models=[deepcopy(model["identity"]) for model in models])
    return original, baseline["limits"]


def author_request(original, alternate):
    from biocompiler import policy as p
    from biocompiler.policy.implementation import prepare_request as prepare_implementation
    from biocompiler.policy.component_material import prepare_request
    document, evidence = authored_document(Path(__file__).resolve().parents[1], alternate)
    supplied = original["implementation_request"]
    require(p.to_data(document) == supplied["document"], "Typed multi-member recipe changed the complete original source")
    implementation = prepare_implementation(document, prerequisites=True, multi_product=True, **{key:deepcopy(supplied[key]) for key in
        ("definitions", "operating_domain", "implementation_library", "catalog_bindings", "budgets")})
    request = prepare_request(instanced=True, prerequisites=True, multi_member=True, implementation_request=implementation,
        **{key:deepcopy(original[key]) for key in ("component_library", "composition_rule", "catalog_binding", "input_bindings",
                                                  "resource_bindings", "context", "budgets")})
    require(request == original, "Typed multi-member authoring changed independently supplied authority")
    evidence.update(implementation_request_digest=canonical_digest(implementation), request_digest=canonical_digest(request))
    return request, evidence


def checked_fixture(root, path):
    fixture = read_json(path, 4_000_000)
    require(set(fixture) == {"schema_version","status","acceptance","source_sha256","cases"}
            and fixture["schema_version"] == FIXTURE_SCHEMA and fixture["status"] == "source_declarations_only"
            and fixture["acceptance"] is False, "Unexpected multi-member original fixture")
    require(fixture["source_sha256"] == {name:digest_file(root / name) for name in INPUTS}, "Multi-member original source pins changed")
    require([case["id"] for case in fixture["cases"]] == ["A","B"], "Missing or reordered original cases")
    for case in fixture["cases"]:
        require(set(case) == {"id","request","limits","expected"}, "Changed original case shape")
        expected, outer = case["expected"], case["request"]
        require(set(expected) == {"sequences","molecules","ordered_union","carrier_projections","link_projections","histories","transitions",
                                 "prefixes_started","obligations","prerequisite_closure"}
                and expected["sequences"] == SEQUENCES[case["id"]]
                and [expected[key] for key in ("histories","transitions","prefixes_started")] == [25,86,87]
                and expected["obligations"] == OBLIGATIONS, "Independent multi-member oracle changed")
        require(outer["schema_version"] == "biocompiler.policy_component_material_request.v0.5"
                and outer["profile"] == outer["context"]["profile"] == "biocompiler.policy_multi_member_prerequisite_mrna.v0.1",
                "Multi-member fixture crossed a legacy profile")
        original, limits = independent_original(root, case["id"] == "B")
        require(outer["implementation_request"] == original and case["limits"] == limits,
                "Multi-member original source, models, full operating domain or limits changed")
    return fixture


def checked_graph(candidate, union):
    """Compare the complete literal union, allowing only opaque actual node names."""
    proposal = candidate["assembly_proposal"]["nodes"]
    originals = [(row["slot"], row["node"]) for row in union["nodes"]]
    require([(row["slot"], row["node"]) for row in proposal] == originals
            and len(originals) == len(set(originals)) == 29
            and len({row["actual"] for row in proposal}) == 29,
            "Original-to-actual mapping is not a complete ordered bijection")
    bindings = {(row["slot"], row["node"]):row["actual"] for row in proposal}
    def node(reference):
        return bindings[(reference["slot"], reference["node"])]
    def endpoint(reference):
        return {"node":node(reference), "port":reference["port"]}
    expected = {
        "nodes":[{"id":node(row), "model":row["model"]["identity"],
                  "configuration_digest":row["model"]["configuration_digest"]} for row in union["nodes"]],
        "wires":[{"producer":endpoint(row["producer"]), "consumer":endpoint(row["consumer"])} for row in union["wires"]],
        "inputs":[{**row, "consumer":endpoint(row["consumer"])} for row in union["inputs"]],
        "atomic_groups":[{"id":row["id"], "arbiter":node(row["arbiter"]),
                          "commits":[node(reference) for reference in row["commits"]]} for row in union["atomic_groups"]],
        "semantic_exports":[endpoint(reference) for reference in union["semantic_exports"]]}
    require(len(expected["wires"]) == 55 and len(expected["atomic_groups"]) == 1
            and len(expected["atomic_groups"][0]["commits"]) == 7
            and all(candidate["implementation"][key] == value for key, value in expected.items()),
            "Actual graph differs from independent complete node/model/wire/input/export/atomic-group authority")
    return bindings


def checked_result(result, case):
    from biocompiler.core_policy_component_material import ACCEPTED_STATUS, CLAIM_SCOPE, PREMISE, MULTI_MEMBER_REQUEST_PROFILE
    report, candidate, expected = result["report"], result["candidate"], case["expected"]
    require(report["status"] == ACCEPTED_STATUS and report["profile"] == MULTI_MEMBER_REQUEST_PROFILE
            and report["claim_scope"] == CLAIM_SCOPE and report["premise"] == PREMISE
            and report["assembly_status"] == report["context_status"] == report["prerequisite_status"] == "pass"
            and report["all_original_obligations_discharged"] is True and report["empirical"] == "unassessed"
            and report["artifact"] == report["export"] == "withheld"
            and [row["obligation"] for row in report["obligations"]] == OBLIGATIONS
            and all(row["status"] == "discharged" for row in report["obligations"])
            and [row["id"] for row in report["context"]["discharges"]] == CONTEXT_DISCHARGES,
            "Multi-member result changed complete original obligations or conditional scope")
    closure = deepcopy(report["prerequisites"])
    require(closure == report["context"]["prerequisite_closure"]
            and closure.pop("assembly_fingerprint") == canonical_digest(report["assembly"])
            and closure == expected["prerequisite_closure"], "Original prerequisite graph, providers or complete member/transport allocation changed")
    for key in ("member_allocations","transport_allocations"):
        require(report["context"][key] == expected["prerequisite_closure"][key], "Context allocation differs from original closure")
    for row in report["obligations"]:
        if row["stage"] in ("declared_context","conditional_component_context_conjunction"):
            require(row["evidence"]["prerequisites"] == canonical_digest(report["prerequisites"]), "Context discharge omitted fresh closure pin")
    preservation = report["preservation"]
    require(preservation["preservation"] == "pass" and preservation["coverage"]["complete"] is True
            and [preservation["coverage"][key] for key in ("histories","transitions","prefixes_started","matched_prefixes")] == [25,86,87,87]
            and [row["id"] for row in preservation["requirements"]] == ["first_initiation","second_initiation"]
            and all(row["status"] == "pass" and row["nonvacuous"] is True and row["histories"] == REQUIREMENT_HISTORIES[row["id"]]
                    for row in preservation["requirements"]), "Complete staged domain or nonvacuous initiation requirements changed")
    require(candidate["construction"]["inventory"]["molecules"] == expected["molecules"]
            and [row["sequence"] for row in candidate["construction"]["inventory"]["molecules"]] == expected["sequences"]
            and report["assembly"]["carrier_projections"] == expected["carrier_projections"]
            and len(candidate["implementation"]["nodes"]) == 29 and len(candidate["implementation"]["wires"]) == 55,
            "Complete two-member material or independent graph/carrier census changed")
    bindings = checked_graph(candidate, expected["ordered_union"])
    links = deepcopy(expected["link_projections"])
    for row in links:
        for key in ("producer_endpoint","consumer_endpoint"):
            local = row[key]
            row[key] = {"node":bindings[(local["slot"],local["node"])],"port":local["port"]}
    require(report["assembly"]["link_projections"] == links, "Complete original inter-member transport correspondence changed")
    if result["artifact"] is not None:
        artifact = result["artifact"]
        fasta = "".join(f">rna_{index + 1:04d} alphabet=RNA\n" + member["sequence"] + "\n"
                        for index, member in enumerate(expected["molecules"]))
        require(artifact["fasta"] == fasta and artifact["fasta_sha256"] == hashlib.sha256(fasta.encode()).hexdigest(),
                "Fresh multi-member FASTA omitted, reordered or changed a member")
        manifest = artifact["manifest"]
        require(manifest["request"] == case["request"] and manifest["candidate"] == candidate
                and manifest["limits"] == case["limits"] and manifest["assessment"] == report
                and [row["member_id"] for row in manifest["members"]] == [row["id"] for row in expected["molecules"]]
                and artifact["manifest_sha256"] == canonical_digest(manifest), "Two-member publication lost complete original authority")


def changed_candidate(candidate, kind):
    if kind not in ("guard","state"):
        return legacy_changed_candidate(candidate, kind)
    value = deepcopy(candidate)
    transitions = value["binding"]["transitions"]
    wires = value["implementation"]["wires"]
    if kind == "guard":
        first = next(row for row in wires if row["consumer"] == {"node":transitions[0]["gate"],"port":"guard"})
        alternatives = [row for row in wires if row["consumer"]["port"] == "guard" and row["producer"] != first["producer"]]
        require(alternatives, "Missing independently distinct staged guard mutation")
        first["producer"] = deepcopy(alternatives[0]["producer"])
    else:
        writes = [next(row for row in wires if row["producer"] == {"node":transition["commit"],"port":"machine_write"})
                  for transition in transitions[:2]]
        require(len(writes) == 2 and writes[0]["consumer"] != writes[1]["consumer"], "Missing distinct staged machine-write mutation")
        writes[0]["consumer"], writes[1]["consumer"] = deepcopy(writes[1]["consumer"]), deepcopy(writes[0]["consumer"])
    return value


def exercise_cases(cases, core, verify_transport, verify, sdk, retain, artifacts, input_paths, *,
                   validate_result=checked_result, expected_obligations=OBLIGATIONS):
    """One unchanged 26-observation A/B witness for both explicit environments."""
    from biocompiler.core_client import CoreRejected
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
        validate_result(compiled.result, case)
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
            input_paths=input_paths)
        if exported.report != checked.report or exported.candidate != candidate:
            raise AssertionError("Fresh atomic export changed checked source-to-material evidence")
        validate_result(exported.result, case)
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
                or [row["obligation"] for row in failed.report["obligations"]] != expected_obligations
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


def check_observations(observations, fixture, *, validate_result=None, expected_obligations=OBLIGATIONS):
    """Check complete retained protocol values against independent originals."""
    if validate_result is None:
        validate_result = checked_result
    from biocompiler.core_client import CoreResponse, CORE_VERSION
    from biocompiler.core_policy_component_material import _result
    _require(type(observations) is list and all(type(row) is dict and set(row) == {"case", "name", "result"} for row in observations)
             and [(row["case"], row["name"]) for row in observations] == [(case, name) for case in ("A", "B") for name in CASE_NAMES],
             "Incomplete or reordered component observation census")
    inputs = {}
    for case in fixture["cases"]:
        label, request, limits = case["id"], case["request"], case["limits"]
        values = {row["name"]: row["result"] for row in observations if row["case"] == label}
        compiled = values["compile"]; candidate = compiled["candidate"]
        for name, operation, role in (("compile", "compile", "core"), ("check-verify", "check", "verify"),
                                      ("replay-verify", "replay", "verify"), ("export-verify", "export", "verify"),
                                      ("changed-material", "check", "verify")):
            payload = {"request": request, "limits": limits}
            if operation != "compile":
                payload["candidate"] = changed_candidate(candidate, "material") if name == "changed-material" else candidate
            if operation == "replay":
                payload["report"] = compiled
            result = values[name]
            _result(CoreResponse("retained-component", operation + "-policy-component-material", "ok", result, (), role, CORE_VERSION), payload)
            if name != "changed-material":
                validate_result(result, case)
        _require(compiled == values["check-verify"] == values["replay-verify"] and compiled["artifact"] is None,
                 "Complete fresh component compile/check/replay results differ")
        exported = values["export-verify"]
        _require(exported["candidate"] == candidate and exported["report"] == compiled["report"], "Fresh component export changed its complete checked evidence")
        _require(values["paired-publication"] == archive_receipt(exported), "Paired component publication receipt changed")
        failed = values["changed-material"]
        _require(failed["report"]["status"] == "not_accepted" and failed["artifact"] is None
                 and failed["report"]["assembly_status"] == "fail" and failed["report"]["context_status"] == "unassessed"
                 and failed["report"]["assembly"]["structure"]["content_outcome"] == "fail"
                 and [row["obligation"] for row in failed["report"]["obligations"]] == expected_obligations
                 and all(row["status"] == "unresolved" for row in failed["report"]["obligations"]),
                 "Changed component material gained or lost original authority")
        for name, code in (("changed-guard", "policy_implementation_source_binding"), ("changed-state", "policy_implementation_source_binding"),
                           ("changed-feedback", "policy_implementation_source_binding"), ("changed-configuration", "policy_implementation_contract"),
                           ("rejected-export", "policy_component_material_export_not_accepted"),
                           ("verify-has-no-producer", "unsupported_operation"), ("stale-source", "policy_correspondence")):
            value = values[name]
            _require(type(value) is dict and set(value) == {"status", "diagnostics"}
                     and value["status"] == ("unsupported" if name == "verify-has-no-producer" else "error")
                     and type(value["diagnostics"]) is list and value["diagnostics"]
                     and all(type(row) is dict and set(row) == {"code", "message", "path"} and type(row["message"]) is str
                             and (row["path"] is None or type(row["path"]) is str) for row in value["diagnostics"])
                     and {row["code"] for row in value["diagnostics"]} == {code}, "Component control failed at an unrelated boundary: " + name)
        inputs[label] = {"request": deepcopy(request), "limits": deepcopy(limits), "candidate": deepcopy(candidate),
                         "checked": deepcopy(compiled), "exported": deepcopy(exported)}
    return inputs


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
            and output.suffix == ".json" and not output.exists(), "Use a new multi-member development receipt")
    artifacts = output.with_suffix("")
    artifacts.mkdir(exist_ok=False)
    result = {"schema_version": SCHEMA, "status": "incomplete", "acceptance": False, "identity": hosted,
        "scope": "Hosted source-tree multi-member SDK feedback; installed and release acceptance remain separate.",
        "python": platform.python_version(), "fixture_sha256": fixture_pin, "binary_sha256": binaries,
        "authoring": [], "observations": [], "python_semantic_authority": "forbidden"}
    boundary = None
    previous_profile = sys.getprofile()
    start = time.monotonic()

    def save_report():
        raw = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        require(len(raw) <= MAX_RECEIPT, "Multi-member SDK receipt exceeds bound")
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
                "Multi-member SDK resolved a foreign package")
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
                "Incomplete, duplicated or reordered multi-member SDK observation census")
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
                    "Source, original fixture, run or executable changed during multi-member SDK checking")
            result["source_snapshot_sha256"] = canonical_digest(before)
        except Exception as error:
            result.update(status="failed", source_error=str(error))
        save_report()
        require(result["status"] == "passed", result.get("source_error", result.get("error", "Incomplete multi-member SDK")))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("fixture", "core", "verify", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
