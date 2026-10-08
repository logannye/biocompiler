"""Hosted Python DSL through exact component mRNA export.

Source fixtures come from the private domain-only declaration emitter, never a
producer. Native Core and producer-free Verify perform all runtime semantics.
Default mode is development feedback. Explicit installed mode retains separately
versioned four-slot evidence; neither mode alone establishes release acceptance.
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
import os
import re
import sys
import time

try:
    from check_policy_core import canonical_digest, digest_file, read_json, source_identity, native_manifests
    from check_policy_development import identity, source_snapshot, pin
    from check_policy_material import MaterialBoundary, changed_candidate, archive_receipt, OBLIGATIONS, CONTEXT_DISCHARGES
except ModuleNotFoundError:
    from tools.check_policy_core import canonical_digest, digest_file, read_json, source_identity, native_manifests
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


def exercise_cases(cases, core, verify_transport, verify, sdk, retain, artifacts, input_paths):
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
            input_paths=input_paths)
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

        exercise_cases(cases, core, verify_transport, verify, sdk, retain, artifacts,
                       (args.fixture, *(root / name for name in INPUTS)))
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


INSTALLED_SCHEMA = "biocompiler.policy_component_material_campaign.v0.1"
INSTALLED_SCOPE = "installed_sdk_bounded_conditional_component_material"
CASE_NAMES = ("compile", "check-verify", "replay-verify", "export-verify", "paired-publication",
              "changed-guard", "changed-state", "changed-feedback", "changed-configuration", "changed-material",
              "rejected-export", "verify-has-no-producer", "stale-source")
SLOTS = {(system, machine, minor) for system, machine in (("Linux", "x86_64"), ("Darwin", "arm64"))
         for minor in ("3.11", "3.14")}
REQUIRED_MODULES = {"biocompiler", "biocompiler.core_client", "biocompiler.core_policy", "biocompiler.core_policy_operational",
                    "biocompiler.core_policy_implementation", "biocompiler.core_policy_material",
                    "biocompiler.core_policy_component_material", "biocompiler.policy.component_material", "biocompiler.policy.material"}


def _require(value, message):
    if not value:
        raise AssertionError(message)


def _sha(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def bounded_pin(path, maximum=MAX_EVIDENCE, *, executable=False):
    path = Path(path)
    _require(path.is_file() and not path.is_symlink(), "Missing or redirected component evidence")
    if executable:
        _require(os.access(path, os.X_OK), "Component executable is not executable")
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    _require(0 < len(raw) <= maximum, "Component evidence exceeds its byte bound")
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def installed_source_modules(root):
    package = root / "src/biocompiler"
    return {path.relative_to(package).as_posix(): bounded_pin(path) for path in sorted(package.rglob("*.py"))}


def installed_package_modules(root, package):
    package = Path(package)
    _require(package.is_dir() and not package.is_symlink() and not package.resolve().is_relative_to(root.resolve()),
             "Component campaign requires an installed package outside checkout")
    paths = list(package.rglob("*"))
    _require(not any(path.is_symlink() for path in paths), "Installed package contains redirected files")
    actual = {path.relative_to(package).as_posix(): bounded_pin(path) for path in sorted(paths) if path.is_file() and path.suffix == ".py"}
    _require(actual == installed_source_modules(root), "Installed Python source differs from the complete reviewed package")
    return actual


def check_installed_origins(origins, package, modules):
    _require(type(package) is str and Path(package).is_absolute() and ".." not in Path(package).parts,
             "Missing installed package origin")
    _require(type(origins) is dict and REQUIRED_MODULES <= set(origins), "Missing component transport/publication origins")
    for name, origin in origins.items():
        _require(ComponentBoundary.allowed(name), "Forbidden Python semantic module in installed component campaign")
        relative = name.removeprefix("biocompiler").lstrip(".").replace(".", "/")
        alternatives = ((relative + ".py", relative + "/__init__.py") if relative else ("__init__.py",))
        matches = [path for path in alternatives if path in modules]
        _require(len(matches) == 1 and origin == str(Path(package) / matches[0]), "Foreign installed component module origin")


def validate_fixture_provenance(root, fixture_path, provenance_path, identity_value, binaries, slot):
    try:
        from check_policy_component_fixture import validate
    except ModuleNotFoundError:
        from tools.check_policy_component_fixture import validate
    return validate(root, fixture_path, provenance_path, identity=identity_value,
                    native_sha256={role: binaries["biocompiler-" + role] for role in ("core", "verify")},
                    expected_platform=slot[:2])



def fixture_authority_pins(fixture_path, provenance_path):
    """Retain the complete four-file source-declaration transport, including empty logs."""
    try:
        from check_policy_component_fixture import pin as fixture_pin, MAX_LOG
    except ModuleNotFoundError:
        from tools.check_policy_component_fixture import pin as fixture_pin, MAX_LOG
    fixture_path, provenance_path = Path(fixture_path), Path(provenance_path)
    _require(fixture_path.parent == provenance_path.parent, "Component original authority pair is not co-located")
    return {"fixture": bounded_pin(fixture_path, 4_000_000), "provenance": bounded_pin(provenance_path),
            **{name: fixture_pin(fixture_path.parent / name, MAX_LOG, empty=True)
               for name in ("stdout.log", "stderr.log")}}


def check_observations(observations, fixture):
    """Check complete retained protocol values against independent originals."""
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
                checked_result(result, case)
        _require(compiled == values["check-verify"] == values["replay-verify"] and compiled["artifact"] is None,
                 "Complete fresh component compile/check/replay results differ")
        exported = values["export-verify"]
        _require(exported["candidate"] == candidate and exported["report"] == compiled["report"], "Fresh component export changed its complete checked evidence")
        _require(values["paired-publication"] == archive_receipt(exported), "Paired component publication receipt changed")
        failed = values["changed-material"]
        _require(failed["report"]["status"] == "not_accepted" and failed["artifact"] is None
                 and failed["report"]["assembly_status"] == "fail" and failed["report"]["context_status"] == "unassessed"
                 and failed["report"]["assembly"]["structure"]["content_outcome"] == "fail"
                 and [row["obligation"] for row in failed["report"]["obligations"]] == OBLIGATIONS
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


def _retained(path, root, pin_value, maximum):
    _require(type(path) is str and not Path(path).is_absolute() and ".." not in Path(path).parts, "Unsafe component evidence path")
    actual = root / path
    _require(actual.resolve().is_relative_to(root.resolve()) and not any(p.is_symlink() for p in (actual, *actual.parents) if p != root.parent),
             "Redirected component evidence path")
    _require(type(pin_value) is dict and set(pin_value) == {"sha256", "bytes"} and _sha(pin_value["sha256"])
             and type(pin_value["bytes"]) is int and bounded_pin(actual, maximum) == pin_value, "Retained component evidence bytes changed")
    return actual


def validate_installed(receipt, evidence_root, fixture, fixture_path, identity_value, binaries, *, expected_sources,
                       fixture_provenance, expected_slot=None):
    root = Path(__file__).resolve().parents[1]; evidence_root = Path(evidence_root)
    authority = fixture_authority_pins(fixture_path, fixture_provenance)
    fields = {"schema_version", "status", "revision", "head_revision", "run_id", "run_attempt", "system", "machine", "python_version",
              "scope", "fixture_sha256", "fixture_provenance_sha256", "binary_sha256", "package", "installed_modules", "parent_imports",
              "source_snapshot_sha256", "authoring", "shared_driver_fingerprint", "observations", "observations_fingerprint", "publications", "python_semantic_authority"}
    _require(type(receipt) is dict and set(receipt) == fields and receipt["schema_version"] == INSTALLED_SCHEMA and receipt["status"] == "pass",
             "Not a complete installed component campaign receipt")
    _require(type(receipt["python_version"]) is str and re.fullmatch(r"3\.(11|14)\.[0-9]+", receipt["python_version"]) is not None,
             "Invalid installed component runtime")
    slot = receipt["system"], receipt["machine"], ".".join(receipt["python_version"].split(".")[:2])
    _require(slot in SLOTS and (expected_slot is None or slot == expected_slot), "Wrong or unexpected installed component slot")
    _require(all(receipt[key] == identity_value[key] for key in ("revision", "head_revision", "run_id"))
             and type(receipt["run_attempt"]) is str and re.fullmatch(r"[1-9][0-9]*", receipt["run_attempt"]) is not None
             and int(receipt["run_attempt"]) <= int(identity_value["run_attempt"]), "Stale installed component source/run/attempt")
    _require(set(binaries) == {"biocompiler-core", "biocompiler-verify"} and all(_sha(value) for value in binaries.values())
             and receipt["binary_sha256"] == binaries and receipt["fixture_sha256"] == bounded_pin(fixture_path, 4_000_000)["sha256"]
             and receipt["fixture_provenance_sha256"] == bounded_pin(fixture_provenance, MAX_EVIDENCE)["sha256"]
             and receipt["source_snapshot_sha256"] == canonical_digest(expected_sources), "Installed component external identity differs")
    _require(receipt["scope"] == INSTALLED_SCOPE and receipt["python_semantic_authority"] == "forbidden", "Installed component scope promoted")
    validate_fixture_provenance(root, fixture_path, fixture_provenance, identity_value, binaries, slot)
    _require(fixture == checked_fixture(root, fixture_path), "Component original fixture was replaced")
    _require(not Path(receipt["package"]).resolve().is_relative_to(root.resolve()), "Installed package belongs to checkout")
    _require(receipt["installed_modules"] == installed_source_modules(root), "Installed component module inventory differs")
    check_installed_origins(receipt["parent_imports"], receipt["package"], receipt["installed_modules"])
    authoring = [{"case": case["id"], **author_request(case["request"], case["id"] == "B")[1]} for case in fixture["cases"]]
    _require(receipt["authoring"] == authoring, "Complete original Python authoring evidence changed")
    drivers = [case["request"]["component_library"]["components"][1] for case in fixture["cases"]]
    _require(drivers[0] == drivers[1] and receipt["shared_driver_fingerprint"] == canonical_digest(drivers[0]), "Reusable original driver changed")
    rows = receipt["observations"]
    _require(type(rows) is list and all(type(row) is dict and set(row) == {"case", "name", "path", "sha256", "bytes"} for row in rows)
             and [(row["case"], row["name"]) for row in rows] == [(case, name) for case in ("A", "B") for name in CASE_NAMES], "Incomplete installed observation files")
    observations = []
    folder = None
    paths = []
    for row in rows:
        path = _retained(row["path"], evidence_root, {key: row[key] for key in ("sha256", "bytes")}, MAX_EVIDENCE)
        _require(path.name == row["case"] + "-" + row["name"] + ".json", "Renamed component observation")
        folder = folder or path.parent
        _require(path.parent == folder, "Component observations split across unrelated directories")
        observations.append({"case": row["case"], "name": row["name"], "result": read_json(path, MAX_EVIDENCE)})
        paths.append(path)
    _require(receipt["observations_fingerprint"] == canonical_digest(observations), "Complete installed observations changed")
    inputs = check_observations(observations, fixture)
    pubs = receipt["publications"]
    _require(type(pubs) is list and all(type(row) is dict and set(row) == {"case", "path", "sha256", "bytes"} for row in pubs)
             and [row["case"] for row in pubs] == ["A", "B"], "Missing or reordered paired component ZIPs")
    for row in pubs:
        path = _retained(row["path"], evidence_root, {key: row[key] for key in ("sha256", "bytes")}, MAX_EVIDENCE)
        _require(path.parent == folder and path.name == row["case"] + "-program.zip", "Foreign component paired ZIP path")
        archive_receipt(inputs[row["case"]]["exported"], path); paths.append(path)
    _require(folder is not None and set(folder.iterdir()) == set(paths), "Missing or extra component evidence file")
    for row in (*rows, *pubs):
        _retained(row["path"], evidence_root, {key: row[key] for key in ("sha256", "bytes")}, MAX_EVIDENCE)
    _require(fixture_authority_pins(fixture_path, fixture_provenance) == authority,
             "Original component authority changed while validating evidence")
    return inputs


def run_installed(args):
    root = Path(__file__).resolve().parents[1]
    _require(os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted",
             "Installed component native campaign is hosted-only")
    hosted, before = source_identity(), source_snapshot(root)
    _require(hosted["run_id"] != "local", "Installed component campaign needs a hosted run")
    slot = platform.system(), platform.machine(), f"{sys.version_info.major}.{sys.version_info.minor}"
    _require(slot in SLOTS and not Path.cwd().resolve().is_relative_to(root), "Installed campaign requires a supported runtime outside checkout")
    binaries = {"biocompiler-core": args.core_sha256, "biocompiler-verify": args.verify_sha256}
    _require(all(_sha(value) for value in binaries.values()), "External Core/Verify SHA256 pins are required")
    binary_paths = {role: getattr(args, role).absolute() for role in ("core", "verify")}
    measured = {role: bounded_pin(path, 256 * 1024 * 1024, executable=True) for role, path in binary_paths.items()}
    _require(all(measured[role]["sha256"] == binaries["biocompiler-" + role] for role in measured), "Native executable differs from external authority")
    fixture = checked_fixture(root, args.fixture)
    originals = fixture_authority_pins(args.fixture, args.fixture_provenance)
    validate_fixture_provenance(root, args.fixture, args.fixture_provenance, hosted, binaries, slot)
    spec = importlib.util.find_spec("biocompiler")
    _require(spec is not None and spec.origin is not None, "Install the reviewed component SDK")
    package = Path(spec.origin).resolve().parent
    modules = installed_package_modules(root, package)
    output = args.output.absolute()
    _require(not output.exists() and output.suffix == ".json" and output.parent.is_dir() and not output.parent.is_symlink(), "Use one fresh installed JSON receipt")
    artifacts = output.with_suffix(""); artifacts.mkdir(exist_ok=False)
    result = {"schema_version": INSTALLED_SCHEMA, "status": "incomplete", **hosted, "system": slot[0], "machine": slot[1],
        "python_version": platform.python_version(), "scope": INSTALLED_SCOPE, "fixture_sha256": originals["fixture"]["sha256"],
        "fixture_provenance_sha256": originals["provenance"]["sha256"], "binary_sha256": binaries, "package": str(package),
        "installed_modules": modules, "source_snapshot_sha256": canonical_digest(before), "parent_imports": {},
        "authoring": [], "shared_driver_fingerprint": None, "observations": [], "observations_fingerprint": None,
        "publications": [], "python_semantic_authority": "forbidden"}
    def save():
        raw = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        _require(len(raw) <= MAX_RECEIPT, "Installed receipt exceeded its bound"); output.write_bytes(raw)
    def retain(case, name, value):
        from biocompiler.core_client import encode_json
        raw = encode_json(value); _require(len(raw) <= MAX_EVIDENCE, "Installed observation exceeded its bound")
        path = artifacts / f"{case}-{name}.json"
        with path.open("xb") as stream: stream.write(raw)
        result["observations"].append({"case": case, "name": name, "path": str(path.relative_to(output.parent)), **bounded_pin(path)})
        save()
    boundary = ComponentBoundary(package); previous = sys.getprofile()
    try:
        # Authoring precedes the semantic-execution guard, exactly as in the
        # development witness; every imported module still belongs to package.
        boundary.origins()
        cases = []
        for case in fixture["cases"]:
            request, authored = author_request(case["request"], case["id"] == "B")
            cases.append((case, request)); result["authoring"].append({"case": case["id"], **authored})
        drivers = [request["component_library"]["components"][1] for _, request in cases]
        _require(drivers[0] == drivers[1], "Reusable driver differs between complete originals")
        result["shared_driver_fingerprint"] = canonical_digest(drivers[0])
        sys.meta_path.insert(0, boundary); sys.setprofile(boundary.trace)
        from biocompiler.core_client import CoreClient
        from biocompiler.core_policy_component_material import PolicyComponentMaterialClient
        from biocompiler.policy import component_material as sdk
        core = PolicyComponentMaterialClient(CoreClient(binary_paths["core"], role="core", expected_sha256=binaries["biocompiler-core"], timeout_seconds=90))
        transport = CoreClient(binary_paths["verify"], role="verify", expected_sha256=binaries["biocompiler-verify"], timeout_seconds=90)
        exercise_cases(cases, core, transport, PolicyComponentMaterialClient(transport), sdk, retain, artifacts,
                       (args.fixture, args.fixture_provenance, *(root / name for name in INPUTS)))
        result["parent_imports"] = boundary.origins()
        check_installed_origins(result["parent_imports"], str(package), modules)
        for case in ("A", "B"):
            path = artifacts / f"{case}-program.zip"
            result["publications"].append({"case": case, "path": str(path.relative_to(output.parent)), **bounded_pin(path)})
        observations = [{"case": row["case"], "name": row["name"], "result": read_json(output.parent / row["path"], MAX_EVIDENCE)} for row in result["observations"]]
        result["observations_fingerprint"] = canonical_digest(observations)
        result["status"] = "pass"
    except Exception as error:
        result.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        sys.setprofile(previous)
        if boundary in sys.meta_path: sys.meta_path.remove(boundary)
        try:
            _require(source_identity() == hosted and source_snapshot(root) == before and installed_package_modules(root, package) == modules,
                     "Installed source/run/package changed during component checking")
            _require({role: bounded_pin(path, 256 * 1024 * 1024, executable=True) for role, path in binary_paths.items()} == measured
                     and fixture_authority_pins(args.fixture, args.fixture_provenance) == originals,
                     "Original component fixture/provenance/native bytes changed")
            if result["status"] == "pass":
                _require(boundary.origins() == result["parent_imports"], "Installed imports changed at completion")
                validate_installed(result, output.parent, fixture, args.fixture, hosted, binaries, expected_sources=before,
                                   fixture_provenance=args.fixture_provenance, expected_slot=slot)
                _require(boundary.origins() == result["parent_imports"] and source_identity() == hosted
                         and source_snapshot(root) == before and installed_package_modules(root, package) == modules,
                         "Installed source/import identity changed during final validation")
                _require({role: bounded_pin(path, 256 * 1024 * 1024, executable=True) for role, path in binary_paths.items()} == measured,
                         "Native bytes changed during final validation")
        except Exception as error:
            result.update(status="failed", source_error=str(error))
        save()
        if result["status"] != "pass":
            raise AssertionError(result.get("source_error", result.get("error", "Incomplete installed component campaign")))
    return result


def compare_installed(paths, native_root, fixture_path, fixture_provenances):
    root = Path(__file__).resolve().parents[1]
    hosted, sources = source_identity(), source_snapshot(root)
    binaries = native_manifests(Path(native_root), hosted["revision"])
    fixture = checked_fixture(root, fixture_path)
    _require(len(paths) == 4 and set(fixture_provenances) == {("Linux", "x86_64"), ("Darwin", "arm64")}, "All four component slots and both fixture authorities are required")
    found, baseline, attempts = set(), None, []
    authorities = []
    retained = [(Path(fixture_path), 4_000_000, bounded_pin(fixture_path, 4_000_000))]
    for path in paths:
        path = Path(path); receipt_pin = bounded_pin(path, MAX_RECEIPT)
        retained.append((path, MAX_RECEIPT, receipt_pin))
        receipt = read_json(path, MAX_RECEIPT)
        platform_key = receipt.get("system"), receipt.get("machine")
        _require(platform_key in fixture_provenances, "Unexpected component platform")
        slot = (*platform_key, ".".join(receipt.get("python_version", "").split(".")[:2]))
        _require(slot not in found, "Duplicate component slot"); found.add(slot)
        local_fixture = Path(fixture_provenances[platform_key]).parent / "originals.json"
        _require(bounded_pin(local_fixture, 4_000_000) == bounded_pin(fixture_path, 4_000_000)
                 and checked_fixture(root, local_fixture) == fixture, "Platform original component packets differ")
        authorities.append((local_fixture, Path(fixture_provenances[platform_key]),
                            fixture_authority_pins(local_fixture, fixture_provenances[platform_key])))
        validate_installed(receipt, path.parent, fixture, local_fixture, hosted, binaries[platform_key[0].lower()]["sha256"],
                           expected_sources=sources, fixture_provenance=fixture_provenances[platform_key], expected_slot=slot)
        retained.extend((path.parent / row["path"], MAX_EVIDENCE, {key: row[key] for key in ("sha256", "bytes")})
                        for row in (*receipt["observations"], *receipt["publications"]))
        fingerprint = receipt["observations_fingerprint"]
        _require(baseline is None or baseline == fingerprint, "Complete component outputs differ across installed slots")
        baseline = fingerprint; attempts.append({"slot": list(slot), "run_attempt": receipt["run_attempt"], "receipt": receipt_pin})
    _require(all(bounded_pin(path, maximum) == expected for path, maximum, expected in retained)
             and all(fixture_authority_pins(original, provenance) == expected for original, provenance, expected in authorities)
             and native_manifests(Path(native_root), hosted["revision"]) == binaries,
             "Retained component comparison evidence or native authority changed")
    _require(found == SLOTS and source_identity() == hosted and source_snapshot(root) == sources, "Incomplete component slots or changed comparison authority")
    return {"schema_version": INSTALLED_SCHEMA, "status": "pass", **hosted, "slots": sorted(found), "attempts": attempts,
            "fixture_sha256": bounded_pin(fixture_path, 4_000_000)["sha256"], "observations_fingerprint": baseline,
            "scope": INSTALLED_SCOPE, "empirical": "unassessed", "python_semantic_authority": "forbidden"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("fixture", "core", "verify", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--installed", action="store_true")
    parser.add_argument("--fixture-provenance", type=Path)
    parser.add_argument("--core-sha256")
    parser.add_argument("--verify-sha256")
    args = parser.parse_args()
    if args.installed:
        _require(args.fixture_provenance is not None, "Installed campaign requires original fixture provenance")
        result = run_installed(args)
    else:
        _require(args.fixture_provenance is None and args.core_sha256 is None and args.verify_sha256 is None,
                 "Installed authority options cannot change development mode")
        result = run(args)
    print(json.dumps({"status": result["status"], "acceptance": False, "observations": len(result["observations"])}))


if __name__ == "__main__":
    main()
