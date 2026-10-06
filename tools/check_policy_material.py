"""Hosted installed policy-to-mRNA campaign and exact four-slot comparison.

Only explicitly supplied, already-built Core/Verify executables interpret policy
semantics. Python transports inert authority and checks complete receipt bytes.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
from io import BytesIO
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import zipfile

try:
    from check_policy_core import canonical_digest, digest_file, native_manifests, read_json, run_bounded, source_identity
    from check_policy_implementation import ImplementationBoundary, changed_guard, check_cli_error
except ModuleNotFoundError:
    from tools.check_policy_core import canonical_digest, digest_file, native_manifests, read_json, run_bounded, source_identity
    from tools.check_policy_implementation import ImplementationBoundary, changed_guard, check_cli_error

SCHEMA = "biocompiler.policy_material_campaign.v0.1"
FIXTURE_SCHEMA = "biocompiler.policy_material_request_fixture.v0.1"
CASE_NAMES = (
    "compile", "check-core", "check-verify", "replay-verify", "export-core", "export-verify", "export-library",
    "changed-guard", "changed-state", "changed-feedback", "changed-configuration", "changed-material", "changed-catalog",
    "changed-provider", "unsupported-delivery", "prefix-limit", "source-work-limit", "work-limit",
    "changed-budget-replay", "forged-rehashed-replay", "rejected-fresh-export", "verify-producer", "missing-binary", "wrong-role",
    "compile-cli", "check-cli", "replay-cli", "export-cli", "malformed-replay-cli",
)
CLI_CASES = ("compile-cli", "check-cli", "replay-cli", "export-cli", "malformed-replay-cli")
NEGATIVE_CODES = {
    "changed-guard": {"policy_implementation_source_binding"},
    "changed-state": {"policy_implementation_source_binding"},
    "changed-feedback": {"policy_implementation_source_binding"},
    "changed-configuration": {"policy_implementation_contract"},
    "changed-catalog": {"policy_material_catalog_binding"},
    "work-limit": {"policy_material_work_limit"},
    "changed-budget-replay": {"policy_material_replay"},
    "forged-rehashed-replay": {"policy_material_replay"},
    "rejected-fresh-export": {"policy_material_export_not_accepted"},
    "verify-producer": {"unsupported_operation"},
}
EXPECTED = {"status": "checked_material", "claim_scope": "bounded_conditional_policy_to_exact_mrna",
    "material_status": "pass", "context_status": "pass", "empirical": "unassessed", "artifact": "withheld", "export": "withheld",
    "histories": 9, "transitions": 47, "prefixes_started": 48, "node_count": 15, "carrier_count": 92,
    "sequence": "CCAUGGCUUAAGGAAAA", "request_decoding_work": 480657}
OBLIGATIONS = [
    "arbitration_fairness_and_conflict_resolution", "chassis_capability_and_delivery_suitability",
    "effect_authorization_feedback_and_cancellation", "implementation_applicability:exclusion.response.primitives.resolved_chassis",
    "implementation_catalog_applicability", "persistent_encounter_identity_lifetime", "policy_execution_and_lowering",
    "realizability_and_target_suitability", "requested_assurance_not_established", "requirement_satisfaction:exclusive_selection",
    "requirement_satisfaction:initiation_progress", "requirement_satisfaction:request_progress", "safety_and_progress_satisfaction",
    "semantic_definition:exclusion.chassis", "semantic_definition:exclusion.delivery", "semantic_definition:exclusion.effect",
    "semantic_definition:exclusion.encounter", "semantic_definition:exclusion.environment", "semantic_definition:exclusion.interface",
    "semantic_definition:exclusion.lifecycle", "semantic_definition:exclusion.observation", "semantic_definition:fixture.realization.primitives",
    "state_lifetime_capacity_and_inheritance", "temporal_and_uncertainty_semantics",
]
CONTEXT_DISCHARGES = ["chassis_capability_and_delivery_suitability", "semantic_definition:exclusion.chassis",
    "semantic_definition:exclusion.delivery", "semantic_definition:exclusion.environment", "semantic_definition:exclusion.interface"]
REQUIREMENTS = {"exclusive_selection": "pass", "initiation_progress": "pass", "request_progress": "pass"}
MAX_RECEIPT_BYTES = 32 * 1024 * 1024


class MaterialBoundary(ImplementationBoundary):
    @staticmethod
    def allowed(name: str) -> bool:
        return name == "biocompiler.core_policy_material" or ImplementationBoundary.allowed(name)


def checked_fixture(path: Path) -> dict:
    value = read_json(path)
    if (type(value) is not dict or set(value) != {"schema_version", "notice", "request", "limits", "expected", "candidate_parts"}
            or value["schema_version"] != FIXTURE_SCHEMA or type(value["notice"]) is not str
            or any(type(value[key]) is not dict for key in ("request", "limits", "expected", "candidate_parts"))
            or set(value["candidate_parts"]) != {"implementation", "binding", "material_binding", "construction"}):
        raise AssertionError("Incomplete original material fixture; operational behavior must be derived natively")
    expected, request = value["expected"], value["request"]
    keys = set(EXPECTED) | {"request_fingerprint", "source_request_digest", "material_contract_digest", "context_digest", "molecules", "obligations", "context_discharges"}
    if (set(expected) != keys or canonical_digest({key: expected[key] for key in EXPECTED}) != canonical_digest(EXPECTED)
            or expected["obligations"] != OBLIGATIONS or expected["context_discharges"] != CONTEXT_DISCHARGES
            or expected["request_fingerprint"] != canonical_digest(request)
            or any(expected[key] != canonical_digest(request[field]) for key, field in (
                ("source_request_digest", "implementation_request"), ("material_contract_digest", "material_contract"), ("context_digest", "context")))
            or canonical_digest(expected["molecules"]) != canonical_digest(request["material_contract"]["body"]["material_key"])
            or [row["sequence"] for row in expected["molecules"]] != [EXPECTED["sequence"]]):
        raise AssertionError("Independent material molecule/census/authority literal changed")
    return value


def changed_candidate(candidate: dict, kind: str) -> dict:
    if kind == "guard":
        return changed_guard(candidate)
    changed = deepcopy(candidate)
    if kind == "state":
        select = next(row for row in changed["binding"]["rules"] if row["source"] == "select")
        commit = select["commit"]
        wires = changed["implementation"]["wires"]
        first = next(row for row in wires if row["consumer"] == {"node": commit, "port": "value0"})
        other = next(row for row in wires if row["consumer"] == {"node": commit, "port": "value1"})
        first["producer"] = deepcopy(other["producer"])
    elif kind == "feedback":
        feedback = next(row for row in changed["implementation"]["inputs"] if row["kind"] == "feedback")
        feedback["id"] += ".wrong-correlation-route"
    elif kind == "configuration":
        changed["implementation"]["nodes"][0]["configuration_digest"] = "0" * 64
    elif kind == "material":
        construction = changed["construction"]
        molecule = construction["inventory"]["molecules"][0]
        molecule["sequence"] = "G" + molecule["sequence"][1:]
        for role in construction["inventory"]["role_instances"]:
            if role["subject_id"] == molecule["id"]:
                role["subject_fingerprint"] = canonical_digest(molecule)
    else:
        raise AssertionError("Unknown material candidate-control recipe")
    return changed


def changed_request(request: dict, kind: str) -> dict:
    changed = deepcopy(request)
    if kind == "catalog":
        changed["catalog_binding"]["entry_digest"] = "0" * 64
    elif kind == "provider":
        provider = next(row for row in changed["context"]["providers"] if row["body"]["kind"] == "chassis")
        capacity = next(row for row in provider["body"]["capacities"] if row["id"] == "shared.truth")
        capacity["quantity"] = 1
        provider["identity"]["content_fingerprint"] = canonical_digest(provider["body"])
    elif kind == "unsupported":
        changed["context"]["delivery_group"]["mode"] = "independent"
    elif kind == "prefix":
        changed["implementation_request"]["budgets"]["max_prefixes"] = 1
    elif kind == "work":
        changed["budgets"]["max_work"] = 1
    elif kind == "budget":
        changed["budgets"]["max_work"] -= 1
    else:
        raise AssertionError("Unknown original material-control recipe")
    return changed


def source_work_limits(limits: dict) -> dict:
    changed = deepcopy(limits)
    changed["source"]["max_work"] = 1
    return changed


def check_import_origins(origins: dict, package: str, required: set[str]) -> None:
    if (type(package) is not str or not Path(package).is_absolute() or ".." in Path(package).parts
            or type(origins) is not dict or not required <= set(origins)):
        raise AssertionError("Missing installed material transport guard evidence")
    for name, path in origins.items():
        if (not MaterialBoundary.allowed(name) or type(path) is not str or not Path(path).is_absolute()
                or ".." in Path(path).parts or not Path(path).is_relative_to(package)):
            raise AssertionError("Forbidden or foreign installed Python semantic authority")


def check_cli_guard(guard: dict, package: str, python_version: str) -> None:
    if (type(guard) is not dict or set(guard) != {"status", "guard_active", "execution_guard_active", "python", "executable", "origins"}
            or guard["status"] != "ok" or guard["guard_active"] is not True or guard["execution_guard_active"] is not True
            or guard["python"] != [int(part) for part in python_version.split(".")[:2]]
            or type(guard["executable"]) is not str or not Path(guard["executable"]).is_absolute()):
        raise AssertionError("Installed material CLI guard did not complete on its declared interpreter")
    check_import_origins(guard["origins"], package, {"biocompiler.entrypoint", "biocompiler.policy.cli", "biocompiler.core_policy_material"})


def checked_output(result: dict, operation: str, payload: dict, role: str) -> dict:
    from biocompiler.core_client import CORE_VERSION, CoreError, CoreResponse
    from biocompiler.core_policy_material import _result
    try:
        return _result(CoreResponse("retained-material", operation, "ok", result, (), role, CORE_VERSION), payload).result
    except (CoreError, KeyError, TypeError) as error:
        raise AssertionError("Retained material output lost complete independent authority") from error


def archive_receipt(exported: dict, actual: Path | None = None) -> dict:
    """Check packaging bytes only; the artifact came from fresh native checking."""
    from biocompiler.core_client import encode_json
    artifact = exported["artifact"]
    members = (("program.fasta", artifact["fasta"].encode("utf-8")), ("manifest.json", encode_json(artifact["manifest"])))
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
        for name, content in members:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)
    expected = buffer.getvalue()
    if actual is not None:
        if actual.is_symlink() or not actual.is_file() or actual.stat().st_size != len(expected):
            raise AssertionError("Fresh paired publication is missing, redirected or truncated")
        with actual.open("rb") as handle:
            if handle.read(len(expected) + 1) != expected:
                raise AssertionError("Published archive differs from exact native FASTA/manifest bytes")
    return {"format": "RNA_FASTA_and_canonical_manifest_zip", "sha256": hashlib.sha256(expected).hexdigest(), "bytes": len(expected),
            "members": [{"name": name, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)} for name, content in members],
            "fresh_result_fingerprint": canonical_digest(exported)}


def check_literals(result: dict, fixture: dict) -> None:
    report, candidate, expected = result["report"], result["candidate"], fixture["expected"]
    actual = {key: report[key] for key in ("status", "claim_scope", "material_status", "context_status", "empirical", "artifact", "export")}
    actual.update({key: report["preservation"]["coverage"][key] for key in ("histories", "transitions", "prefixes_started")})
    actual["request_decoding_work"] = report["usage"]["request_decoding_work"]
    actual.update(node_count=len(candidate["implementation"]["nodes"]),
                  carrier_count=len(fixture["request"]["material_contract"]["body"]["carriers"]),
                  sequence=candidate["construction"]["inventory"]["molecules"][0]["sequence"])
    if (canonical_digest(actual) != canonical_digest(EXPECTED)
            or canonical_digest(candidate["construction"]["inventory"]["molecules"]) != canonical_digest(expected["molecules"])
            or [row["obligation"] for row in report["obligations"]] != OBLIGATIONS
            or [row["id"] for row in report["context"]["discharges"]] != CONTEXT_DISCHARGES
            or {row["id"]: row["status"] for row in report["preservation"]["requirements"]} != REQUIREMENTS):
        raise AssertionError("Independent material molecule, obligation or finite-domain census differs")


def check_observations(observations: list, fixture: dict) -> None:
    if (type(observations) is not list or any(type(row) is not dict or set(row) != {"name", "result"} for row in observations)
            or [row["name"] for row in observations] != list(CASE_NAMES)):
        raise AssertionError("Material campaign observation inventory changed or incomplete")
    outputs = {row["name"]: row["result"] for row in observations}
    request, limits = fixture["request"], fixture["limits"]
    candidate = outputs["compile"]["candidate"]
    payload = {"request": request, "candidate": candidate, "limits": limits}
    for name, operation, supplied, role in (
        ("compile", "compile-policy-material", {"request": request, "limits": limits}, "core"),
        ("check-core", "check-policy-material", payload, "core"),
        ("check-verify", "check-policy-material", payload, "verify"),
        ("replay-verify", "replay-policy-material", {**payload, "report": outputs["check-verify"]}, "verify"),
        ("export-core", "export-policy-material", payload, "core"),
        ("export-verify", "export-policy-material", payload, "verify"),
        ("changed-material", "check-policy-material", {**payload, "candidate": changed_candidate(candidate, "material")}, "verify"),
        ("changed-provider", "check-policy-material", {**payload, "request": changed_request(request, "provider")}, "verify"),
        ("unsupported-delivery", "check-policy-material", {**payload, "request": changed_request(request, "unsupported")}, "verify"),
        ("prefix-limit", "check-policy-material", {**payload, "request": changed_request(request, "prefix")}, "verify"),
        ("source-work-limit", "check-policy-material", {**payload, "limits": source_work_limits(limits)}, "verify"),
        ("compile-cli", "compile-policy-material", {"request": request, "limits": limits}, "core"),
        ("check-cli", "check-policy-material", payload, "verify"),
        ("replay-cli", "replay-policy-material", {**payload, "report": outputs["check-verify"]}, "verify"),
    ):
        checked_output(outputs[name], operation, supplied, role)
    for name in ("check-core", "check-verify", "replay-verify", "compile-cli", "check-cli", "replay-cli"):
        if canonical_digest(outputs[name]) != canonical_digest(outputs["compile"]):
            raise AssertionError("Complete Core/Verify/replay/CLI material results differ")
    expected_export = {**outputs["compile"], "artifact": outputs["export-core"]["artifact"]}
    for name in ("export-core", "export-verify"):
        if canonical_digest(outputs[name]) != canonical_digest(expected_export):
            raise AssertionError("Fresh Core/Verify material export or retained assessment differs")
    for name in ("export-library", "export-cli"):
        if canonical_digest(outputs[name]) != canonical_digest(archive_receipt(outputs["export-verify"])):
            raise AssertionError("Published native pair changed under installed SDK/CLI export")
    check_literals(outputs["compile"], fixture)
    for name, stage, expected, diagnostic in (
        ("changed-material", "material", "fail", "complete_exact_material_case_evaluation"),
        ("changed-provider", "context", "fail", "shared_capacity_sum_exceeded"),
        ("unsupported-delivery", "context", "unsupported", "independent_delivery_group_unimplemented"),
    ):
        report = outputs[name]["report"]
        if (report["status"] != "not_accepted" or report[stage + "_status"] != expected
                or report["all_original_obligations_discharged"] is not False or outputs[name]["artifact"] is not None):
            raise AssertionError("Material stage negative control acquired acceptance: " + name)
        if stage == "context" and diagnostic not in report[stage]["diagnostics"]:
            raise AssertionError("Context negative control failed for an unrelated reason: " + name)
        if stage == "material" and report[stage]["structure"]["content_outcome"] != "fail":
            raise AssertionError("Altered exact bases did not fail independent reconstruction")
    for name, code in (("prefix-limit", "policy_preservation_prefix_limit"), ("source-work-limit", "policy_execution_work_limit")):
        outer, report = outputs[name]["report"], outputs[name]["report"]["preservation"]
        if (outer["status"] != "not_accepted" or report["status"] != "incomplete" or report["coverage"]["complete"] is not False
                or report["stopped"]["category"] != "incomplete" or report["stopped"]["diagnostic"]["code"] != code):
            raise AssertionError("Exhausted bound did not retain its exact incomplete disposition: " + name)
    for name, codes in NEGATIVE_CODES.items():
        error = outputs[name]
        if (type(error) is not dict or set(error) != {"status", "diagnostics"}
                or error["status"] != ("unsupported" if name == "verify-producer" else "error")
                or type(error["diagnostics"]) is not list or not error["diagnostics"]
                or any(type(row) is not dict or set(row) != {"code", "message", "path"} or type(row["code"]) is not str
                       or type(row["message"]) is not str or row["path"] is not None and type(row["path"]) is not str for row in error["diagnostics"])
                or not codes.intersection(row["code"] for row in error["diagnostics"])):
            raise AssertionError("Material negative control lost specific native rejection: " + name)
    for name, kind in (("missing-binary", "CoreUnavailable"), ("wrong-role", "CoreProtocolError")):
        if outputs[name] != {"status": "transport_error", "type": kind}:
            raise AssertionError("Transport failure acquired material fallback authority")
    check_cli_error(2, b"", json.dumps(outputs["malformed-replay-cli"]).encode(), "replay-material-native", "policy_material_replay")


def run(args: argparse.Namespace) -> dict:
    checkout = Path(__file__).resolve().parents[1]
    spec = importlib.util.find_spec("biocompiler")
    if spec is None or spec.origin is None:
        raise AssertionError("Install biocompiler before running the hosted material campaign")
    package = Path(spec.origin).resolve().parent
    if package.is_relative_to(checkout) or Path.cwd().resolve().is_relative_to(checkout):
        raise AssertionError("Installed campaign requires a non-editable package and working directory outside checkout")
    boundary = MaterialBoundary(package)
    sys.meta_path.insert(0, boundary)
    sys.setprofile(boundary.trace)
    from biocompiler.core_client import CoreClient, CoreProtocolError, CoreRejected, CoreUnavailable, decode_json
    from biocompiler.core_policy_material import PolicyMaterialClient
    from biocompiler.policy.material import export as publish

    fixture = checked_fixture(args.fixture)
    request, limits = fixture["request"], fixture["limits"]
    core_path, verify_path = args.core.resolve(strict=True), args.verify.resolve(strict=True)
    pins = {"biocompiler-core": digest_file(core_path), "biocompiler-verify": digest_file(verify_path)}
    core = PolicyMaterialClient(CoreClient(core_path, role="core", expected_sha256=pins["biocompiler-core"], timeout_seconds=60))
    verify_transport = CoreClient(verify_path, role="verify", expected_sha256=pins["biocompiler-verify"], timeout_seconds=60)
    verify = PolicyMaterialClient(verify_transport)
    observations = []
    def retain(name: str, value: object) -> None:
        observations.append({"name": name, "result": value})
    def rejects(name: str, action) -> None:
        try:
            action()
        except CoreRejected as error:
            if error.response.result is not None or not error.response.diagnostics:
                raise AssertionError("Native rejection retained success authority")
            retain(name, {"status": error.response.status,
                "diagnostics": [{"code": row.code, "message": row.message, "path": row.path} for row in error.response.diagnostics]})
        else:
            raise AssertionError("Expected native material rejection: " + name)
    def transport_rejects(name: str, error_type, action) -> None:
        try:
            action()
        except error_type as error:
            retain(name, {"status": "transport_error", "type": type(error).__name__})
        else:
            raise AssertionError("Transport control acquired material authority: " + name)

    compiled = core.compile(request, limits)
    candidate = compiled.candidate
    retain("compile", compiled.result)
    retain("check-core", core.check(request, candidate, limits).result)
    checked = verify.check(request, candidate, limits)
    retain("check-verify", checked.result)
    retain("replay-verify", verify.replay(request, candidate, limits, checked.result).result)
    retain("export-core", core.export(request, candidate, limits).result)
    exported = verify.export(request, candidate, limits)
    retain("export-verify", exported.result)
    with tempfile.TemporaryDirectory(prefix="policy-material-pair-") as temporary:
        output = Path(temporary) / "program.zip"
        publication = publish(request, candidate=candidate, limits=limits, client=verify, output=output)
        if canonical_digest(publication.result) != canonical_digest(exported.result):
            raise AssertionError("Public library export did not retain the same fresh native result")
        retain("export-library", archive_receipt(publication.result, output))
    for kind in ("guard", "state", "feedback", "configuration"):
        rejects("changed-" + kind, lambda kind=kind: verify.check(request, changed_candidate(candidate, kind), limits))
    wrong_material = changed_candidate(candidate, "material")
    retain("changed-material", verify.check(request, wrong_material, limits).result)
    rejects("changed-catalog", lambda: verify.check(changed_request(request, "catalog"), candidate, limits))
    retain("changed-provider", verify.check(changed_request(request, "provider"), candidate, limits).result)
    retain("unsupported-delivery", verify.check(changed_request(request, "unsupported"), candidate, limits).result)
    retain("prefix-limit", verify.check(changed_request(request, "prefix"), candidate, limits).result)
    retain("source-work-limit", verify.check(request, candidate, source_work_limits(limits)).result)
    rejects("work-limit", lambda: verify.check(changed_request(request, "work"), candidate, limits))
    rejects("changed-budget-replay", lambda: verify.replay(changed_request(request, "budget"), candidate, limits, checked.result))
    forged = deepcopy(checked.result)
    forged["report"]["empirical"] = "validated"
    forged["report_fingerprint"] = canonical_digest(forged["report"])
    rejects("forged-rehashed-replay", lambda: verify.replay(request, candidate, limits, forged))
    rejects("rejected-fresh-export", lambda: verify.export(request, wrong_material, limits))
    rejects("verify-producer", lambda: verify_transport.call("compile-policy-material", {"request": request, "limits": limits}))
    cli_guards = {}
    with tempfile.TemporaryDirectory(prefix="policy-material-cli-") as temporary:
        directory = Path(temporary)
        missing = PolicyMaterialClient(CoreClient(directory / "missing-core", role="core"))
        transport_rejects("missing-binary", CoreUnavailable, lambda: missing.compile(request, limits))
        wrong_role = PolicyMaterialClient(CoreClient(verify_path, role="core", expected_sha256=pins["biocompiler-verify"]))
        transport_rejects("wrong-role", CoreProtocolError, lambda: wrong_role.compile(request, limits))
        for name, value in (("request", request), ("limits", limits), ("candidate", candidate), ("report", checked.result)):
            (directory / (name + ".json")).write_text(json.dumps(value), encoding="utf-8")
        guard_receipt = directory / "guard.json"
        (directory / "sitecustomize.py").write_text(
            "import sys, atexit\nsys.path.insert(0," + repr(str(Path(__file__).resolve().parent)) + ")\n"
            "from check_policy_material import MaterialBoundary\nfrom pathlib import Path\n"
            "boundary=MaterialBoundary(Path(" + repr(str(package)) + "), Path(" + repr(str(guard_receipt)) + "))\n"
            "sys.meta_path.insert(0,boundary)\nsys.setprofile(boundary.trace)\natexit.register(boundary.finish)\n", encoding="utf-8")
        env = {**os.environ, "PYTHONPATH": str(directory), "PYTHONDONTWRITEBYTECODE": "1"}
        for name, command, role in (
            ("compile-cli", "compile-material-native", "core"), ("check-cli", "check-material-native", "verify"),
            ("replay-cli", "replay-material-native", "verify"), ("export-cli", "export-material-native", "verify"),
            ("malformed-replay-cli", "replay-material-native", "verify"),
        ):
            if name == "malformed-replay-cli":
                (directory / "report.json").write_text(json.dumps(checked.report), encoding="utf-8")
            binary = core_path if role == "core" else verify_path
            argv = [str(args.console), "policy", command, str(directory / "request.json"), "--json",
                "--limits", str(directory / "limits.json"), "--" + role, str(binary), "--expected-sha256", pins["biocompiler-" + role], "--timeout", "60"]
            payload = {"request": request, "limits": limits}
            if role == "verify":
                argv += ["--candidate", str(directory / "candidate.json")]
                payload["candidate"] = candidate
            if "replay" in name:
                argv += ["--report", str(directory / "report.json")]
                payload["report"] = checked.result
            output = directory / "cli-program.zip"
            if name == "export-cli":
                argv += ["--output", str(output)]
            guard_receipt.unlink(missing_ok=True)
            code, stdout, stderr = run_bounded(argv, cwd=directory, env=env, timeout=90)
            if name == "malformed-replay-cli":
                retain(name, check_cli_error(code, stdout, stderr, command, "policy_material_replay"))
            elif name == "export-cli":
                notice = decode_json(stdout)
                if code != 0 or stderr or notice != {"status": "written", "operation": command, "output": str(output), "format": "RNA_FASTA_and_canonical_manifest_zip"}:
                    raise AssertionError("Installed CLI did not report exact paired native publication")
                retain(name, archive_receipt(exported.result, output))
            else:
                operation = {"compile-cli": "compile-policy-material", "check-cli": "check-policy-material", "replay-cli": "replay-policy-material"}[name]
                actual = checked_output(decode_json(stdout), operation, payload, role)
                if code != 0 or stderr or canonical_digest(actual) != canonical_digest(checked.result):
                    raise AssertionError("Installed material CLI differs from complete SDK output")
                retain(name, actual)
            cli_guards[name] = read_json(guard_receipt)
            check_cli_guard(cli_guards[name], str(package), platform.python_version())
    check_observations(observations, fixture)
    origins = boundary.origins()
    if pins != {"biocompiler-core": digest_file(core_path), "biocompiler-verify": digest_file(verify_path)}:
        raise AssertionError("Selected native binary changed during installed material campaign")
    sys.setprofile(None)
    sys.meta_path.remove(boundary)
    return {"schema_version": SCHEMA, "status": "pass", **source_identity(), "system": platform.system(), "machine": platform.machine(),
        "python_version": platform.python_version(), "fixture_sha256": digest_file(args.fixture), "binary_sha256": pins,
        "package": str(package), "parent_imports": origins, "cli_guards": cli_guards, "observations": observations,
        "observations_fingerprint": canonical_digest(observations), "python_semantic_authority": "forbidden"}


def compare(paths: list[Path], native_root: Path, fixture_path: Path) -> dict:
    if len(paths) != 4:
        raise AssertionError("All four material campaign slots are required exactly once")
    identity = source_identity()
    binaries = native_manifests(native_root, identity["revision"])
    fixture, fixture_hash = checked_fixture(fixture_path), digest_file(fixture_path)
    expected = {(system, machine, python) for system, machine in (("Linux", "x86_64"), ("Darwin", "arm64")) for python in ("3.11", "3.14")}
    found, baseline, baseline_observations = set(), None, None
    for path in paths:
        receipt = read_json(path)
        if (type(receipt) is not dict or set(receipt) != {"schema_version", "status", "revision", "head_revision", "run_id", "run_attempt",
            "system", "machine", "python_version", "fixture_sha256", "binary_sha256", "package", "parent_imports", "cli_guards", "observations",
            "observations_fingerprint", "python_semantic_authority"}
                or any(type(receipt[key]) is not str for key in ("system", "machine", "python_version", "run_attempt"))
                or not receipt["run_attempt"].isdecimal()):
            raise AssertionError("Malformed material campaign receipt")
        slot = receipt["system"], receipt["machine"], ".".join(receipt["python_version"].split(".")[:2])
        if slot not in expected or slot in found:
            raise AssertionError("Missing, duplicate or unexpected material campaign slot")
        found.add(slot)
        if (receipt["schema_version"] != SCHEMA or receipt["status"] != "pass" or receipt["fixture_sha256"] != fixture_hash
                or any(receipt[key] != identity[key] for key in ("revision", "head_revision", "run_id"))
                or not 0 < int(receipt["run_attempt"]) <= int(identity["run_attempt"])
                or receipt["binary_sha256"] != binaries[receipt["system"].lower()]["sha256"]
                or receipt["python_semantic_authority"] != "forbidden"):
            raise AssertionError("Material receipt lacks exact current run/source/binary authority")
        check_import_origins(receipt["parent_imports"], receipt["package"], {"biocompiler.core_client", "biocompiler.core_policy",
            "biocompiler.core_policy_operational", "biocompiler.core_policy_implementation", "biocompiler.core_policy_material", "biocompiler.policy.material"})
        if type(receipt["cli_guards"]) is not dict or set(receipt["cli_guards"]) != set(CLI_CASES):
            raise AssertionError("Missing complete material CLI guard receipts")
        for guard in receipt["cli_guards"].values():
            check_cli_guard(guard, receipt["package"], receipt["python_version"])
        observations = receipt["observations"]
        if canonical_digest(observations) != receipt["observations_fingerprint"]:
            raise AssertionError("Material campaign observations changed or incomplete")
        digest = canonical_digest(observations)
        if baseline is not None and baseline != digest:
            raise AssertionError("Complete material results and publication bytes differ across four installed slots")
        if baseline is None:
            baseline_observations = observations
        baseline = digest
    if found != expected:
        raise AssertionError("All four material campaign slots are required")
    # Every slot retains the same complete canonical observations, independently
    # bound above to its native bytes and workflow identity. Validate that full
    # common evidence once against the external fixture rather than rerunning
    # the same Python representation checks for identical copies.
    check_observations(baseline_observations, fixture)
    return {"schema_version": SCHEMA, **identity, "status": "pass", "slots": sorted(found), "fixture_sha256": fixture_hash,
        "observations_fingerprint": baseline, "claim_scope": "bounded_conditional_policy_to_exact_mrna",
        "empirical": "unassessed", "artifact": "fresh_native_pair_checked", "export": "fresh_original_input_check_only"}


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
    if len(encoded) > MAX_RECEIPT_BYTES:
        raise AssertionError("Complete material campaign receipt exceeds its retained artifact bound")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(encoded)


if __name__ == "__main__":
    main()
