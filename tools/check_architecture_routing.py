"""Installed public SDK/CLI architecture routing with Python authority blocked.

Frozen complete requests remain the independent authority. Historical public
record codecs may hydrate and serialize native results; they cannot compile,
evaluate, check or authorize export. CLI workers invoke the installed entry
function under the same execution guard and retain separate guard receipts.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

import biocompiler as bc
from biocompiler.architecture_backend import ArchitectureCoreError
from biocompiler.core_architecture import ArchitectureClient
from biocompiler.core_client import CoreClient, CoreRejected, CoreUnavailable, decode_json, encode_json

if __package__:
    from .check_architecture_producer_protocol import CORPUS_PIN, ROOT, Corpus, digest, mutations, require, require_installed
else:
    from check_architecture_producer_protocol import CORPUS_PIN, ROOT, Corpus, digest, mutations, require, require_installed


EXPECTED_CHECKS = 175
_TRANSPORT = frozenset(("biocompiler.core_client", "biocompiler.core_architecture",
                        "biocompiler.core_architecture_producer", "biocompiler.architecture_backend"))
# These are historical construction/import checks, never source evaluation or
# independent acceptance. Names include their nested comprehensions on 3.11.
_CODECS = {
    "biocompiler.compiler.request": (
        "BindingMetadata.__post_init__", "BindingMetadata.from_dict", "BindingMetadata.to_dict",
        "BuildRequest.__post_init__", "BuildRequest.from_dict", "BuildRequest.to_dict",
        "ElaborationProvenance.__post_init__", "ElaborationProvenance.from_dict", "ElaborationProvenance.to_dict",
        "_mapping", "_resolve", "_schema", "_strict_import"),
    "biocompiler.semantics.component_contracts": (
        "DomainCheck.__post_init__", "OperatingDomain.__post_init__", "OperatingDomain.from_dict", "OperatingDomain.to_dict",
        "PortContract.__post_init__", "PortContract.from_dict", "PortContract.to_dict",
        "ValueDomain.__post_init__", "ValueDomain.from_dict", "ValueDomain.to_dict",
        "_schema", "contract_type", "decode_type", "domain_subset"),
    "biocompiler.semantics.context": (
        "HumanTargetContext.__post_init__", "HumanTargetContext.from_dict", "HumanTargetContext.to_dict",
        "TargetContext.__post_init__", "TargetContext.from_dict", "TargetContext.to_dict"),
    "biocompiler.semantics.contracts": (
        "BehaviorRequirement.__post_init__", "BehaviorRequirement.from_dict", "BehaviorRequirement.to_dict", "_string"),
    "biocompiler.semantics.human_target": (
        "HumanHostDependency.__post_init__", "HumanOperatingCondition.__post_init__",
        "HumanTargetContract.__post_init__", "HumanTargetContract.<lambda>", "HumanTargetContract.claims",
        "TargetClaim.__post_init__", "_TargetRecord._check_utf8", "_TargetRecord.from_dict", "_TargetRecord.to_dict",
        "_choice", "_decode_records", "_records"),
    "biocompiler.semantics.molecule_coordinates": (
        "CoordinatePath.__post_init__", "CoordinatePath.length", "CoordinatePath.validate_for",
        "CoordinateSpace.__post_init__", "IndexSpan.__post_init__", "IndexSpan.length"),
    "biocompiler.semantics.payload_execution": (
        "SourceExecutionManifest.__post_init__", "SourceExecutionManifest.from_dict", "SourceExecutionManifest.to_dict"),
    "biocompiler.semantics.payload_requirements": (
        "PayloadOutputRequirement.__post_init__", "PayloadOutputRequirement.from_dict", "PayloadOutputRequirement.to_dict",
        "PayloadDiagnostic.__post_init__", "PayloadDiagnostic.from_dict", "PayloadDiagnostic.to_dict"),
    "biocompiler.semantics.types": (
        "ScalarLiteral.to_dict", "TypeSpec.__mul__", "TypeSpec.__post_init__", "TypeSpec._combine",
        "TypeSpec.compatible", "TypeSpec.from_dict", "TypeSpec.to_dict", "_ScalarType.__new__",
        "_number", "decode_binding", "to_type_spec"),
    "biocompiler.verification.circuit_construction": ("CircuitConstructionAssessment.__post_init__",),
    "biocompiler.verification.payload_architecture": (
        "PayloadArchitectureVerification.__post_init__", "PayloadArchitectureVerification.passed"),
}
_ROUTES = {
    "biocompiler.compiler.workflow": ("compile",),
    "biocompiler.compiler.payload_architecture": ("compile_payload_architecture", "export_payload_architecture"),
    "biocompiler.verification.payload_architecture": ("check_payload_architecture", "verify_payload_architecture"),
    "biocompiler.cli": ("main", "_architecture_core_arguments", "_register_circuit_infrastructure_commands",
                         "_architecture_core_client", "_architecture_core_command", "_architecture_command",
                         "_bounded_text", "_publish_report"),
}


def _allowed_name(name, allowed):
    return any(name == item or name.startswith(item + ".<locals>.") for item in allowed)


def _allowed_frame(frame):
    module = frame.f_globals.get("__name__", "")
    if not module.startswith("biocompiler"):
        return True
    if module in _TRANSPORT or module == "biocompiler.errors" or module.startswith(("biocompiler.ir.", "biocompiler.artifacts.")):
        return True
    code = frame.f_code
    allowed = _CODECS.get(module, ()) + _ROUTES.get(module, ())
    if _allowed_name(code.co_qualname, allowed):
        return True
    # Python versions give generated dataclass constructors different qualnames.
    # Permit only generated methods belonging to the explicitly named records.
    if code.co_filename == "<string>" and code.co_name in {"__init__", "__eq__", "__repr__"}:
        record = type(frame.f_locals.get("self"))
        return record.__module__ == module and any(name.startswith(record.__qualname__ + ".") for name in _CODECS.get(module, ()))
    return False


@contextmanager
def routed_execution():
    previous = sys.getprofile()
    seen = set()

    def guard(frame, event, _argument):
        if event == "call":
            if not _allowed_frame(frame):
                raise AssertionError("Python semantic authority executed on the native route: "
                                     + frame.f_globals.get("__name__", "") + "." + frame.f_code.co_qualname)
            module = frame.f_globals.get("__name__", "")
            if module in _CODECS or module in _ROUTES:
                seen.add(module + "." + frame.f_code.co_qualname)

    sys.setprofile(guard)
    try:
        yield seen
    finally:
        sys.setprofile(previous)


def coherent_mutations(request, build):
    # Reuse the reviewed protocol mutants, including repaired structural pins
    # and the still-untrusted embedded PASS, across both installed surfaces.
    return mutations(request, build)


def _save(path, record):
    path.write_text(record.to_json() + "\n", encoding="utf-8")


def _document(record):
    # Public codecs retain string-enum values in to_dict(). Their bounded JSON
    # representation is the literal wire form, without relaxing transport rules.
    return decode_json(record.to_json(indent=None).encode("utf-8"))


def _write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def _native_rejection(action, *, code=None, unavailable=False):
    try:
        action()
    except ArchitectureCoreError as error:
        if unavailable:
            require(isinstance(error.core_error, CoreUnavailable), "Wrong selected-executable failure")
        else:
            require(isinstance(error.core_error, CoreRejected) and error.core_error.response.result is None
                    and [item.code for item in error.diagnostics] == [code], "Wrong native semantic rejection")
    else:
        raise AssertionError("Selected native failure silently returned a Python result")


def _cli_worker(argv):
    parser = argparse.ArgumentParser(description="Guard the installed CLI entry point")
    parser.add_argument("--guard-receipt", required=True, type=Path)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    arguments = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
    receipt = {"schema_version": "biocompiler.architecture_cli_guard.v1", "status": "failure",
               "package_path": str(Path(bc.__file__).resolve()), "python_semantics_blocked": False}
    try:
        require_installed()
        from biocompiler.cli import main as cli_main
        with routed_execution() as seen:
            code = cli_main(arguments)
        receipt.update(status="success", python_semantics_blocked=True, exit_code=code, allowed_calls=sorted(seen))
    except Exception as error:
        code = 125
        receipt["error"] = type(error).__name__ + ": " + str(error)
        print(receipt["error"], file=sys.stderr)
    args.guard_receipt.parent.mkdir(parents=True, exist_ok=True)
    _write(args.guard_receipt, receipt)
    return code


def _cli(arguments, *, directory, guards, name, expected, preserved=()):
    guard_path = guards / (directory.name + "." + name + ".json")
    before = {path: path.read_bytes() for path in preserved}
    temporaries = {path.name for path in directory.glob(".*.tmp")}
    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--cli-worker",
                             "--guard-receipt", str(guard_path), "--", *map(str, arguments)],
                            capture_output=True, text=True, check=False, timeout=180)
    guard = json.loads(guard_path.read_text(encoding="utf-8"))
    # Actual process diagnostics can contain installation paths. Retain them as
    # run evidence beside the guard receipt, outside canonical artifact identity.
    guard.update(stdout=result.stdout, stderr=result.stderr)
    _write(guard_path, guard)
    require(guard["status"] == "success" and guard["python_semantics_blocked"] is True
            and guard["exit_code"] == result.returncode == expected,
            f"CLI {name}: expected exit {expected}, got {result.returncode}: {result.stderr}; guard={guard.get('error')}")
    require(all(path.read_bytes() == data for path, data in before.items()), "Rejected publication changed existing authority/output")
    require({path.name for path in directory.glob(".*.tmp")} == temporaries, "CLI left partial publication files")
    if expected in (0, 1):
        require(not result.stderr, "Successful checked CLI response wrote stderr")
        summary = json.loads(result.stdout)
        require(set(summary) == {"status", "verification", "diagnostics"}, "CLI summary interface changed")
        (directory / (name + ".json")).write_text(result.stdout, encoding="utf-8")
        return summary
    require(not result.stdout and bool(result.stderr.strip()), "Rejected CLI operation returned an accepted artifact/summary")
    _write(directory / (name + ".json"), {"exit_code": expected, "preserved_output": bool(preserved)})
    return None


def _summary(summary, build, assessment):
    require(summary["status"] == build.status
            and encode_json(summary["verification"]) == encode_json(_document(assessment))
            and encode_json(summary["diagnostics"]) == encode_json(_document(build)["diagnostics"]),
            "Complete public CLI summary disagrees with SDK")


def campaign(core, verify, corpus, artifacts, guards, receipt):
    checks = receipt["checks"]
    require(not checks and core.role == "core" and verify.role == "verify", "Fresh receipt and both roles required")
    artifacts.mkdir(parents=True, exist_ok=True)
    guards.mkdir(parents=True, exist_ok=True)
    require(not any(artifacts.iterdir()) and not any(guards.iterdir()), "Routing evidence destinations must start empty")
    selected = corpus.selected()
    base = None
    core_flags = ["--core-executable", core.executable, "--core-sha256", core.expected_sha256, "--core-timeout", "60"]
    verify_flags = ["--verifier-executable", verify.executable, "--core-sha256", verify.expected_sha256, "--core-timeout", "60"]
    with routed_execution() as seen:
        for prefix, compiled, exported, raw_request, expected in selected:
            directory = artifacts / (prefix.split("/", 1)[1].lower() if prefix.startswith("installed/") else prefix.replace("/", "-"))
            directory.mkdir()
            request = bc.PayloadArchitectureRequest.from_dict(raw_request)
            require(request.fingerprint == compiled["request"], "Public request hydration changed authority")
            request_path, build_path = directory / "request.json", directory / "build.json"
            _save(request_path, request)
            restored = bc.PayloadArchitectureRequest.from_json(request_path.read_text(encoding="utf-8"))
            build = bc.compile(restored, core=core)
            require(isinstance(build, bc.PayloadArchitectureBuild) and build.status == "compiled"
                    and build.fingerprint == compiled["build"] and encode_json(_document(build)) == encode_json(expected),
                    "Public workflow lost exact native build: " + prefix)
            _save(build_path, build)
            checks.append({"id": prefix, "operation": "sdk.compile", "build": build.fingerprint})

            direct = bc.compile_payload_architecture(restored, core=core)
            require(type(direct) is type(build) and direct.to_json() == build.to_json(), "Named compiler route differs: " + prefix)
            checks.append({"id": prefix, "operation": "sdk.compile_payload_architecture", "build": direct.fingerprint})
            require(build.molecules is not None and build.plan is not None and build.construction is not None
                    and isinstance(build.diagnostics, tuple) and isinstance(build.alternatives, tuple), "Historical build interface changed")

            checked = bc.check_payload_architecture(build, expected_request=request, core=core)
            require(isinstance(checked, bc.PayloadArchitectureVerification) and checked.passed
                    and checked.translation_complete and checked.construction_complete, "Public native check is not complete: " + prefix)
            _save(directory / "api.verification.json", checked)
            checks.append({"id": prefix, "operation": "sdk.check", "assessment": checked.fingerprint})
            roundtrip = bc.PayloadArchitectureBuild.from_json(build_path.read_text(encoding="utf-8"))
            replayed = bc.verify_payload_architecture(checked, roundtrip, expected_request=restored, core=core)
            require(type(replayed) is type(checked) and replayed.to_json() == checked.to_json(), "Public fresh replay differs: " + prefix)
            checks.append({"id": prefix, "operation": "sdk.replay", "assessment": replayed.fingerprint})
            pair = bc.export_payload_architecture(build, expected_request=request, core=core)
            require(isinstance(pair, bc.PayloadArchitectureExport) and pair.fingerprint == exported["expected_fingerprint"]
                    and pair.fasta == exported["fasta"], "Public paired export differs from complete frozen authority: " + prefix)
            manifest = _document(pair)["manifest"]
            require(encode_json(manifest["build"]) == encode_json(expected)
                    and encode_json(manifest["verification"]) == encode_json(_document(checked))
                    and manifest["request_fingerprint"] == compiled["request"], "Export detached its full native authority")
            _save(directory / "api.export.json", pair)
            (directory / "payloads.fasta").write_text(pair.fasta, encoding="utf-8")
            _write(directory / "manifest.json", manifest)
            checks.append({"id": prefix, "operation": "sdk.export", "export": pair.fingerprint})
            independent = ArchitectureClient(verify).verify(expected_request=raw_request, build=_document(build))
            require(independent.assessment_fingerprint == checked.fingerprint
                    and encode_json(independent.assessment) == encode_json(_document(checked)), "Separate verifier disagrees with public route")
            _write(directory / "independent.verification.json", independent.assessment)
            checks.append({"id": prefix, "operation": "standalone.verify", "assessment": independent.assessment_fingerprint})

            cli_build, cli_export = directory / "cli.build.json", directory / "cli.export.json"
            for operation, arguments, name in (
                ("cli.build", ["architecture-build", "--request", request_path, "--output", cli_build, *core_flags], "cli.build-summary"),
                ("cli.verify", ["architecture-verify", cli_build, "--expected-request", request_path, *core_flags], "cli.verification"),
                ("cli.standalone.verify", ["architecture-verify", cli_build, "--expected-request", request_path, *verify_flags], "cli.standalone-verification"),
                ("cli.export", ["architecture-export", cli_build, "--expected-request", request_path, "--output", cli_export, *core_flags], "cli.export-summary"),
            ):
                summary = _cli(arguments, directory=directory, guards=guards, name=name, expected=0)
                _summary(summary, build, checked)
                checks.append({"id": prefix, "operation": operation, "exit_code": 0})
            require(cli_build.read_bytes() == build_path.read_bytes()
                    and cli_export.read_bytes() == (directory / "api.export.json").read_bytes(), "Installed CLI changed complete SDK artifacts")
            if prefix == "installed/B":
                base = (request, build, checked, directory)

        require(base is not None, "Missing baseline for authority rejection")
        request, build, checked, directory = base
        for name, raw_request, raw_build in coherent_mutations(_document(request), _document(build)):
            changed_request = bc.PayloadArchitectureRequest.from_dict(raw_request)
            changed_build = bc.PayloadArchitectureBuild.from_dict(raw_build)
            failed = bc.check_payload_architecture(changed_build, expected_request=changed_request, core=core)
            require(failed.to_dict()["outcome"] == "fail", "Mutant must reach fresh semantic failure: " + name)
            checks.append({"id": name, "operation": "sdk.check", "outcome": "fail", "assessment": failed.fingerprint})
            _native_rejection(lambda: bc.export_payload_architecture(changed_build, expected_request=changed_request, core=core),
                              code="architecture_export_rejected")
            checks.append({"id": name, "operation": "sdk.export", "error": "architecture_export_rejected"})
            _native_rejection(lambda: bc.verify_payload_architecture(checked, changed_build, expected_request=changed_request, core=core),
                              code="architecture_assessment_mismatch")
            checks.append({"id": name, "operation": "sdk.replay", "error": "architecture_assessment_mismatch"})
            request_path, build_path = directory / (name + ".request.json"), directory / (name + ".build.json")
            _save(request_path, changed_request)
            _save(build_path, changed_build)
            summary = _cli(["architecture-verify", build_path, "--expected-request", request_path, *core_flags],
                           directory=directory, guards=guards, name=name + ".verification", expected=1)
            _summary(summary, changed_build, failed)
            checks.append({"id": name, "operation": "cli.verify", "exit_code": 1})
            existing = directory / "cli.export.json"
            _cli(["architecture-export", build_path, "--expected-request", request_path, "--output", existing, *core_flags],
                 directory=directory, guards=guards, name=name + ".export-rejection", expected=2, preserved=(existing, request_path, build_path))
            checks.append({"id": name, "operation": "cli.export", "exit_code": 2, "preserved_output": True})

        forged = _document(checked)
        forged["assumptions"].append("Forged historical acceptance assumption.")
        forged_report = bc.PayloadArchitectureVerification.from_dict(forged)
        _native_rejection(lambda: bc.verify_payload_architecture(forged_report, build, expected_request=request, core=core),
                          code="architecture_assessment_mismatch")
        checks.append({"id": "forged-report", "operation": "sdk.replay", "error": "architecture_assessment_mismatch"})

        absent = (guards / "missing-native-executable").resolve()
        require(not absent.exists(), "Missing-executable fixture unexpectedly exists")
        unavailable = CoreClient(absent)
        _native_rejection(lambda: bc.compile(request, core=unavailable), unavailable=True)
        checks.append({"id": "missing-selected-core", "operation": "sdk.compile", "error": "CoreUnavailable"})
        existing_build = directory / "cli.build.json"
        _cli(["architecture-build", "--request", directory / "request.json", "--output", existing_build, "--core-executable", absent],
             directory=directory, guards=guards, name="missing-selected-core", expected=2, preserved=(existing_build,))
        checks.append({"id": "missing-selected-core", "operation": "cli.build", "exit_code": 2, "preserved_output": True})
        for name, path in (("request", directory / "request.json"), ("build", existing_build)):
            _cli(["architecture-export", existing_build, "--expected-request", directory / "request.json", "--output", path, *core_flags],
                 directory=directory, guards=guards, name="input-alias-" + name, expected=2, preserved=(path,))
            checks.append({"id": "input-alias-" + name, "operation": "cli.export", "exit_code": 2, "preserved_output": True})
    require(len(checks) == EXPECTED_CHECKS and len({(item["id"], item["operation"]) for item in checks}) == EXPECTED_CHECKS,
            "Missing or repeated public architecture route execution")
    receipt["allowed_calls"] = sorted(seen)
    receipt["python_semantics_blocked"] = True
    receipt["artifacts"] = {str(path.relative_to(artifacts)): hashlib.sha256(path.read_bytes()).hexdigest()
                            for path in sorted(artifacts.rglob("*")) if path.is_file()}


def main(argv=None):
    arguments = sys.argv[1:] if argv is None else argv
    if arguments[:1] == ["--cli-worker"]:
        return _cli_worker(arguments[1:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", required=True, type=Path)
    parser.add_argument("--verify", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--artifacts", type=Path)
    args = parser.parse_args(arguments)
    started = time.monotonic()
    artifacts = (args.artifacts or args.output.with_suffix("") / "artifacts").resolve()
    guards = args.output.with_suffix("").resolve() / "guards"
    receipt = {"schema_version": "biocompiler.architecture_routing_conformance.v1", "status": "running", "checks": [],
               "platform": platform.platform(), "system": platform.system(), "machine": platform.machine(),
               "python_version": platform.python_version(), "corpus_pin": CORPUS_PIN,
               "package_path": str(Path(bc.__file__).resolve()), "executables": {},
               "artifacts_path": str(artifacts), "guard_receipts_path": str(guards)}
    try:
        revision = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
        require(os.environ.get("GITHUB_SHA", revision) == revision, "Workflow revision differs")
        receipt.update(revision=revision, source_revision=os.environ.get("GITHUB_HEAD_SHA", revision), run_id=os.environ.get("GITHUB_RUN_ID", "local"))
        require_installed()
        clients = []
        for role, binary in (("core", args.core), ("verify", args.verify)):
            require(binary.is_absolute() and binary.is_file() and os.access(binary, os.X_OK), "Missing explicit native executable")
            pin = hashlib.sha256(binary.read_bytes()).hexdigest()
            receipt["executables"][role] = {"path": str(binary), "sha256": pin}
            clients.append(CoreClient(binary, role=role, timeout_seconds=60, expected_sha256=pin))
        campaign(*clients, Corpus(), artifacts, guards, receipt)
        receipt["status"], code = "success", 0
    except Exception as error:
        receipt["status"], code = "failure", 1
        receipt["error"] = type(error).__name__ + ": " + str(error)
        print(receipt["error"], file=sys.stderr)
    receipt["completed_checks"] = len(receipt["checks"])
    receipt["duration_seconds"] = round(time.monotonic() - started, 6)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    _write(args.output, receipt)
    print(f"Architecture routing: {receipt['status']}; {receipt['completed_checks']} completed checks")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
