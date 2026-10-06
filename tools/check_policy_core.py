"""Hosted installed-package campaign for native policy source assessment.

Run outside the source checkout with installed Python/Core/Verify artifacts.
This tool never builds, installs, lowers, or evaluates policies in Python.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.abc
import importlib.util
import inspect
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
from types import FrameType, ModuleType
from typing import Any, Sequence

MAX_OUTPUT = 32 * 1024 * 1024
EXPECTED_NAMES = {
    "context_gated_response", "regulated_secretion", "staged_cleanup_repair",
    "encounter_sentinel", "target_sentinel", "local_restraint",
    "coordinated_populations", "lineage_bounded_response",
}


def digest_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_identity() -> dict[str, str]:
    checkout = Path(__file__).resolve().parents[1]
    result = subprocess.run(["git", "-C", str(checkout), "rev-parse", "--verify", "HEAD"],
                            capture_output=True, text=True, check=True, timeout=10)
    revision = result.stdout.strip()
    def valid_revision(value: str) -> bool:
        return len(value) in (40, 64) and all(character in "0123456789abcdef" for character in value)
    if not valid_revision(revision) or os.environ.get("GITHUB_SHA", revision) != revision:
        raise AssertionError("Current checkout does not match the tested GitHub revision")
    head = os.environ.get("GITHUB_HEAD_SHA")
    if head is None and os.environ.get("GITHUB_EVENT_NAME") == "pull_request":
        event_path = os.environ.get("GITHUB_EVENT_PATH")
        if event_path is None:
            raise AssertionError("Pull-request source identity requires its head revision")
        event = read_json(Path(event_path))
        head = event.get("pull_request", {}).get("head", {}).get("sha")
    head = head or revision
    if not valid_revision(head):
        raise AssertionError("Invalid reviewed head revision")
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "0" if run_id == "local" else "")
    if not (run_id == "local" or run_id.isdecimal() and int(run_id) > 0) or not attempt.isdecimal():
        raise AssertionError("Invalid workflow run identity")
    if run_id != "local" and int(attempt) <= 0:
        raise AssertionError("Hosted workflow attempt must be positive")
    return {"revision": revision, "head_revision": head, "run_id": run_id, "run_attempt": attempt}


def native_manifests(root: Path, revision: str) -> dict[str, dict[str, Any]]:
    if not root.is_dir() or root.is_symlink():
        raise AssertionError("Missing or redirected published native artifacts")
    records: dict[str, dict[str, Any]] = {}
    for system, folder, machine in (("Linux", "linux-x86_64", "x86_64"), ("Darwin", "macos-arm64", "arm64")):
        slot = root / folder
        if not slot.is_dir() or slot.is_symlink():
            raise AssertionError("Missing or redirected native platform slot")
        manifest_path = slot / "binaries.json"
        manifest = read_json(manifest_path, 64 * 1024)
        if (type(manifest) is not dict or set(manifest) != {"revision", "system", "machine", "sha256"}
                or manifest["revision"] != revision or manifest["system"] != system or manifest["machine"] != machine
                or type(manifest["sha256"]) is not dict or set(manifest["sha256"]) != {"biocompiler-core", "biocompiler-verify"}):
            raise AssertionError("Published native manifest has a stale source or wrong platform")
        for name, digest in manifest["sha256"].items():
            binary = slot / name
            if (not binary.is_file() or binary.is_symlink() or not 0 < binary.stat().st_size <= 256 * 1024 * 1024
                    or digest_file(binary) != digest):
                raise AssertionError("Published native bytes differ from their binary manifest")
        records[system.lower()] = {"manifest_sha256": digest_file(manifest_path), **manifest}
    return records


def canonical_digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def semantic_digest(value: object) -> str:
    def strip(item: object) -> object:
        if isinstance(item, dict):
            return {key: strip(value) for key, value in item.items() if key not in ("source_map", "provenance")}
        if isinstance(item, list):
            return [strip(value) for value in item]
        return item
    return canonical_digest(strip(value))


def read_json(path: Path, maximum: int = MAX_OUTPUT) -> Any:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > maximum:
        raise AssertionError("Missing, redirected or oversized JSON artifact: " + str(path))
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise AssertionError("Duplicate JSON artifact key")
            result[key] = value
        return result
    def forbidden(value: str) -> Any:
        raise AssertionError("Raw floats/nonfinite values are outside the frozen corpus: " + value)
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                      parse_float=forbidden, parse_constant=forbidden)


def load_cases(path: Path) -> list[dict[str, Any]]:
    fixture = read_json(path, 2 * 1024 * 1024)
    if type(fixture) is not dict or fixture.get("fixture_version") != "biocompiler.policy_native_literals.v0.1":
        raise AssertionError("Wrong frozen native policy corpus")
    cases = fixture.get("cases")
    if type(cases) is not list or len(cases) != 24:
        raise AssertionError("Corpus must contain 24 frozen policy documents")
    expected = {(name, kind) for name in EXPECTED_NAMES for kind in ("program", "request", "submission")}
    actual: set[tuple[str, str]] = set()
    tags = {"program": "PolicyProgram", "request": "BuildRequest", "submission": "CompilationSubmission"}
    for row in cases:
        if type(row) is not dict or set(row) != {"name", "kind", "document", "fingerprint", "artifact_digest", "document_digest"}:
            raise AssertionError("Unexpected frozen corpus row fields")
        identity = row["name"], row["kind"]
        if identity not in expected or identity in actual:
            raise AssertionError("Duplicate or unexpected frozen corpus identity")
        actual.add(identity)
        if type(row["document"]) is not dict or row["document"].get("$type") != tags[row["kind"]]:
            raise AssertionError("Frozen corpus document kind differs")
        if canonical_digest(row["document"]) != row["artifact_digest"]:
            raise AssertionError("Frozen corpus artifact digest differs")
        target = row["document"]["request"] if row["kind"] == "submission" else row["document"]
        if semantic_digest(target) != row["fingerprint"] or semantic_digest(row["document"]) != row["document_digest"]:
            raise AssertionError("Frozen corpus document digest differs")
    if actual != expected:
        raise AssertionError("Incomplete policy corpus")
    return cases


class ImportBoundary(importlib.abc.MetaPathFinder):
    """Constrain both installed processes to authoring and explicit transport."""

    def __init__(self, package: Path, receipt: Path | None = None) -> None:
        self.package = package.resolve()
        self.receipt = receipt
        self.denied: list[str] = []

    @staticmethod
    def guarded(name: str) -> bool:
        return name == "biocompiler" or name.startswith(("biocompiler.", "_biocompiler", "biocompiler_core"))

    @staticmethod
    def allowed(name: str) -> bool:
        return name in {"biocompiler", "biocompiler.core_client", "biocompiler.core_policy",
                        "biocompiler.entrypoint", "biocompiler.__main__", "biocompiler.policy"} or name.startswith("biocompiler.policy.")

    def find_spec(self, fullname: str, path: Sequence[str] | None = None,
                  target: ModuleType | None = None) -> None:
        if self.guarded(fullname) and not self.allowed(fullname):
            self.denied.append(fullname)
            raise ImportError("Native policy campaign forbids Python compiler/evaluator import: " + fullname)
        return None

    def trace(self, frame: FrameType, event: str, argument: object) -> None:
        module = frame.f_globals.get("__name__", "")
        function = frame.f_code.co_name
        forbidden = (module == "biocompiler.policy.validation" and function == "check"
                     or module == "biocompiler.policy.programs" and function == "freeze"
                     or module == "biocompiler.policy.handoff" and function in ("prepare_submission", "assess_capabilities"))
        if event == "call" and forbidden:
            self.denied.append("call:" + module + "." + function)
            raise AssertionError("Native campaign forbids Python authoring-check execution")

    def origins(self) -> dict[str, str]:
        if self.denied:
            raise AssertionError("Forbidden imports were attempted: " + ", ".join(self.denied))
        origins: dict[str, str] = {}
        for name, module in tuple(sys.modules.items()):
            if not self.guarded(name):
                continue
            if not self.allowed(name):
                raise AssertionError("Forbidden Python module already loaded: " + name)
            filename = getattr(module, "__file__", None)
            if not filename or not Path(filename).resolve().is_relative_to(self.package):
                raise AssertionError("Foreign installation module origin: " + name)
            origins[name] = str(Path(filename).resolve())
        return dict(sorted(origins.items()))

    def finish(self) -> None:
        assert self.receipt is not None
        try:
            value: dict[str, object] = {"status": "ok", "origins": self.origins()}
        except Exception as error:
            value = {"status": "error", "message": str(error)}
        value.update({"guard_active": True, "execution_guard_active": True, "python": list(sys.version_info[:2]),
                      "executable": str(Path(sys.executable).resolve())})
        self.receipt.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def run_bounded(command: Sequence[str], *, cwd: Path, env: dict[str, str],
                timeout: float = 45, maximum: int = MAX_OUTPUT) -> tuple[int, bytes, bytes]:
    process = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    buffers = [bytearray(), bytearray()]
    overflow = threading.Event()
    def drain(index: int) -> None:
        stream = process.stdout if index == 0 else process.stderr
        assert stream is not None
        try:
            while chunk := stream.read(65536):
                if len(buffers[index]) + len(chunk) > maximum:
                    overflow.set()
                    process.kill()
                    break
                buffers[index].extend(chunk)
        finally:
            stream.close()
    readers = [threading.Thread(target=drain, args=(index,), daemon=True) for index in (0, 1)]
    for reader in readers:
        reader.start()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired as error:
        process.kill()
        process.wait()
        raise AssertionError("Installed native CLI exceeded its time bound") from error
    finally:
        for reader in readers:
            reader.join(timeout=5)
    if overflow.is_set() or any(reader.is_alive() for reader in readers):
        raise AssertionError("Installed native CLI exceeded its output bound")
    return process.returncode, bytes(buffers[0]), bytes(buffers[1])


def mutations(cases: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any], str, str]]:
    """Independent source edits and required native diagnostic codes."""
    def chosen(kind: str) -> dict[str, Any]:
        return copy.deepcopy(next(row["document"] for row in cases if row["kind"] == kind and row["name"] == "context_gated_response"))
    result: list[tuple[str, dict[str, Any], str, str]] = []
    document = chosen("program")
    document["profile"] = "unsupported.policy"
    result.append(("wrong_profile", document, "rejected", "policy_document"))
    for key in ("document_digest", "program_digest"):
        document = chosen("submission")
        document[key] = "0" * 64
        result.append(("forged_" + key, document, "rejected", "policy_document_digest"))
    document = chosen("submission")
    document["semantic_bundle"]["digest"] = "0" * 64
    result.append(("forged_bundle_pin", document, "rejected", "policy_document_digest"))
    document = chosen("submission")
    document["dependencies"] = []
    result.append(("forged_dependencies", document, "rejected", "policy_document_digest"))
    document = chosen("submission")
    document["required_features"] = []
    result.append(("forged_features", document, "invalid", "submission_features"))
    document = chosen("program")
    document["declarations"].append(copy.deepcopy(document["declarations"][0]))
    result.append(("duplicate_ids", document, "invalid", "duplicate_declaration"))
    document = chosen("program")
    effect = next(row for row in document["declarations"] if row["$type"] == "Effect")
    effect["executor"]["id"] = "missing_executor"
    result.append(("missing_executor", document, "invalid", "missing_reference"))
    document = chosen("program")
    rule = next(row for row in document["declarations"] if row["$type"] == "Rule")
    rule["when"]["args"][0]["scope"] = {"$type": "Ref", "id": "executor", "kind": "Role"}
    result.append(("subject_scope_mismatch", document, "invalid", "expression_scope"))
    document = chosen("request")
    document["deployment"]["bindings"] = []
    result.append(("missing_role_binding", document, "invalid", "deployment_role_coverage"))
    return result


def write_receipt(path: Path, value: dict[str, Any]) -> None:
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    if len(raw) > MAX_OUTPUT:
        raise AssertionError("Campaign receipt exceeds its bounded artifact budget")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".policy-core-", delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.link(temporary, path)
    finally:
        temporary.unlink()


def campaign(core: Path, verify: Path, fixture: Path, console: Path, *,
             progress: dict[str, Any] | None = None) -> dict[str, Any]:
    receipt = progress if progress is not None else {}
    checkout = Path(__file__).resolve().parents[1]
    if Path.cwd().resolve().is_relative_to(checkout):
        raise AssertionError("Run the native campaign from outside the source checkout")
    spec = importlib.util.find_spec("biocompiler")
    if spec is None or spec.origin is None:
        raise AssertionError("An installed biocompiler package is required")
    package = Path(spec.origin).resolve().parent
    if package.is_relative_to(checkout):
        raise AssertionError("The policy campaign requires an installation outside the source checkout")
    if not console.is_absolute() or not console.is_file() or not os.access(console, os.X_OK):
        raise AssertionError("Select an executable installed biocompiler console")
    identity = source_identity()
    machine = platform.machine()
    if (sys.platform, machine) not in (("linux", "x86_64"), ("darwin", "arm64")):
        raise AssertionError("Native campaign requires Linux x86_64 or Darwin arm64")
    selected: dict[str, dict[str, str]] = {}
    for role, executable in (("core", core), ("verify", verify)):
        if not executable.is_absolute() or not executable.is_file() or not os.access(executable, os.X_OK):
            raise AssertionError("Select absolute installed executable paths")
        selected[role] = {"path": str(executable.resolve()), "sha256": digest_file(executable)}
    guard = ImportBoundary(package)
    guard.origins()
    sys.meta_path.insert(0, guard)
    previous_profile = sys.getprofile()
    sys.setprofile(guard.trace)
    try:
        from biocompiler.core_client import CoreClient, CoreRejected
        from biocompiler.core_policy import PolicyClient
        cases = load_cases(fixture)
        clients = {
            "core": PolicyClient(CoreClient(core, role="core", expected_sha256=selected["core"]["sha256"])),
            "verify": PolicyClient(CoreClient(verify, role="verify", expected_sha256=selected["verify"]["sha256"])),
        }
        receipt.update({
            "schema_version": "biocompiler.policy_native_campaign.v0.1", "status": "passed",
            "selected_inputs": {"core": str(core.resolve()), "verify": str(verify.resolve()), "fixture": str(fixture.resolve())},
            "source_identity": identity, "machine": machine,
            "python": sys.version, "python_version": list(sys.version_info[:3]), "sys_platform": sys.platform,
            "interpreter": str(Path(sys.executable).resolve()), "platform": platform.platform(), "installed_package": str(package),
            "executables": selected, "console": {"path": str(console), "sha256": digest_file(console)},
            "fixture": {"path": str(fixture.resolve()), "sha256": digest_file(fixture)},
            "frontend_scope": "independent_native_policy_source_contracts",
            "semantic_execution": "unsupported", "lowering": "unsupported", "sequence_artifact": "withheld",
            "empirical_acceptance": "not_established", "cases": [], "negative_controls": [], "cli": [],
        })
        retained: dict[tuple[str, str], dict[str, Any]] = {}
        for row in cases:
            for role, client in clients.items():
                result = client.assess(row["document"])
                if result.status != "valid":
                    raise AssertionError(f"Native source check failed for {row['name']}/{row['kind']}/{role}: {result.assessment['diagnostics']}")
                if result.document_digest != row["fingerprint"] or result.artifact_digest != row["artifact_digest"]:
                    raise AssertionError("Native source identity differs from the frozen corpus")
                replay = client.replay(expected_document=row["document"], assessment=result.assessment)
                if replay.assessment_fingerprint != result.assessment_fingerprint:
                    raise AssertionError("Fresh native replay changed the assessment identity")
                identity = row["name"], row["kind"]
                if role == "core":
                    retained[identity] = result.assessment
                elif retained[identity] != result.assessment:
                    raise AssertionError("Core and independent Verify source assessments differ")
                forged = copy.deepcopy(result.assessment)
                forged["declarations"] = list(reversed(forged["declarations"]))
                try:
                    client.replay(expected_document=row["document"], assessment=forged)
                except CoreRejected as error:
                    if "policy_assessment_mismatch" not in {diagnostic.code for diagnostic in error.response.diagnostics}:
                        raise AssertionError("Forged replay failed at an unexpected native boundary") from error
                else:
                    raise AssertionError("Native replay accepted a changed ordered declaration ledger")
                receipt["cases"].append({"name": row["name"], "kind": row["kind"], "role": role,
                    "artifact_digest": result.artifact_digest, "document_digest": result.document_digest,
                    "program_digest": result.program_digest, "assessment_fingerprint": result.assessment_fingerprint,
                    "assessment": result.assessment, "fresh_replay": "passed", "forged_replay": "rejected"})
        for name, document, expected, code in mutations(cases):
            for role, client in clients.items():
                try:
                    result = client.assess(document)
                except CoreRejected as error:
                    actual = {diagnostic.code for diagnostic in error.response.diagnostics}
                    if expected != "rejected" or code not in actual:
                        raise AssertionError(f"Unexpected rejection for {name}/{role}: {actual}") from error
                else:
                    actual = {diagnostic["code"] for diagnostic in result.assessment["diagnostics"]}
                    if expected != "invalid" or result.status != "invalid" or code not in actual:
                        raise AssertionError(f"Mutation was not independently diagnosed: {name}/{role}: {actual}")
                receipt["negative_controls"].append({"name": name, "role": role, "expected": expected,
                    "required_diagnostic": code, "diagnostics": sorted(actual), "input_digest": canonical_digest(document)})
        with tempfile.TemporaryDirectory(prefix="biocompiler-policy-native-cli-") as directory:
            work = Path(directory)
            guard_dir = work / "guard"
            guard_dir.mkdir()
            proof_path = work / "origins.json"
            source = ("from __future__ import annotations\nimport atexit, importlib.abc, json, sys\n"
                      "from pathlib import Path\nfrom types import FrameType, ModuleType\nfrom typing import Sequence\n"
                      + inspect.getsource(ImportBoundary)
                      + f"\n_guard = ImportBoundary(Path({str(package)!r}), Path({str(proof_path)!r}))\n"
                      "_guard.origins()\nsys.meta_path.insert(0, _guard)\nsys.setprofile(_guard.trace)\natexit.register(_guard.finish)\n")
            (guard_dir / "sitecustomize.py").write_text(source, encoding="utf-8")
            environment = {key: value for key, value in os.environ.items()
                           if key not in ("PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE")}
            environment.update({"PYTHONPATH": os.pathsep.join((str(guard_dir), str(package.parent))),
                                "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"})
            for row in cases:
                if row["name"] != "context_gated_response":
                    continue
                source_path = work / (row["kind"] + ".json")
                source_path.write_text(json.dumps(row["document"], ensure_ascii=False), encoding="utf-8")
                for role in clients:
                    proof_path.unlink(missing_ok=True)
                    command = [str(console), "policy", "assess-native", str(source_path), "--" + role,
                               selected[role]["path"], "--expected-sha256", selected[role]["sha256"], "--json"]
                    code, stdout, stderr = run_bounded(command, cwd=work, env=environment)
                    proof = read_json(proof_path)
                    if (proof.get("status") != "ok" or proof.get("guard_active") is not True or proof.get("execution_guard_active") is not True
                            or proof.get("python") != list(sys.version_info[:2])
                            or proof.get("executable") != str(Path(sys.executable).resolve())):
                        raise AssertionError("Installed CLI import/interpreter boundary failed")
                    required = {"biocompiler.entrypoint", "biocompiler.policy.cli", "biocompiler.core_policy", "biocompiler.core_client"}
                    if not required <= proof.get("origins", {}).keys():
                        raise AssertionError("CLI did not load the installed public native transport")
                    if code != 0 or stderr or json.loads(stdout) != retained[(row["name"], row["kind"])]:
                        raise AssertionError(f"Installed CLI native result differs: {role}/{row['kind']}: {stderr.decode(errors='replace')}")
                    receipt["cli"].append({"role": role, "kind": row["kind"], "status": "passed", "guard": proof})
        receipt["parent_imports"] = guard.origins()
        receipt["parent_execution_guard"] = True
        receipt["counts"] = {"assessments": len(receipt["cases"]), "fresh_replays": len(receipt["cases"]),
                             "forged_replays": len(receipt["cases"]), "negative_controls": len(receipt["negative_controls"]),
                             "installed_cli": len(receipt["cli"])}
        return receipt
    finally:
        sys.setprofile(previous_profile)
        sys.meta_path.remove(guard)


def compare_receipts(paths: Sequence[Path], *, fixture: Path | None = None,
                     native_artifacts: Path | None = None) -> dict[str, Any]:
    """Compare complete hosted variants while retaining machine provenance."""
    if len(paths) != 4 or len({path.resolve() for path in paths}) != 4:
        raise AssertionError("Comparison requires four distinct hosted receipts")
    workflow_identity = source_identity()
    if workflow_identity["run_id"] == "local":
        raise AssertionError("Hosted comparison requires a current GitHub run identity")
    if native_artifacts is None:
        raise AssertionError("Hosted comparison requires --native-artifacts with published binary bytes")
    published = native_manifests(native_artifacts, workflow_identity["revision"])
    platform_pins: dict[str, dict[str, str]] = {}
    fixture = fixture or Path(__file__).resolve().parents[1] / "core/test/data/policy_documents_v01.json"
    corpus = load_cases(fixture)
    input_rows = {(row["name"], row["kind"]): row for row in corpus}
    expected_controls = {(name, role): (status, code, canonical_digest(document))
                         for name, document, status, code in mutations(corpus) for role in ("core", "verify")}
    expected_variants = {(system, minor) for system in ("linux", "darwin") for minor in (11, 14)}
    receipt_fields = {"schema_version", "status", "selected_inputs", "source_identity", "machine", "python", "python_version", "sys_platform",
        "interpreter", "platform", "installed_package", "executables", "console", "fixture", "frontend_scope",
        "semantic_execution", "lowering", "sequence_artifact", "empirical_acceptance", "cases", "negative_controls",
        "cli", "parent_imports", "parent_execution_guard", "counts"}
    assessment_fields = {"schema_version", "status", "document_digest", "program_digest", "artifact_digest",
        "declarations", "requirements", "required_features", "dependencies", "assumptions", "unresolved_obligations",
        "diagnostics", "semantic_status", "target_status", "lowering", "artifact"}
    expected_counts = {"assessments": 48, "fresh_replays": 48, "forged_replays": 48,
                       "negative_controls": 20, "installed_cli": 6}
    scopes = {"frontend_scope": "independent_native_policy_source_contracts", "semantic_execution": "unsupported",
              "lowering": "unsupported", "sequence_artifact": "withheld", "empirical_acceptance": "not_established"}
    seen: set[tuple[str, int]] = set()
    variants: list[dict[str, Any]] = []
    authority: dict[str, Any] | None = None
    def fingerprint(value: object) -> bool:
        return type(value) is str and len(value) == 64 and all(char in "0123456789abcdef" for char in value)
    def absolute(value: object) -> bool:
        return type(value) is str and Path(value).is_absolute()
    def origins(value: object, package: str, required: set[str]) -> None:
        if type(value) is not dict or not required <= value.keys():
            raise AssertionError("Hosted receipt omits required installed transport origins")
        for name, filename in value.items():
            if (not ImportBoundary.guarded(name) or not ImportBoundary.allowed(name)
                    or not absolute(filename) or not Path(filename).is_relative_to(package)):
                raise AssertionError("Hosted receipt has a forbidden or foreign module origin")
    for path in paths:
        value = read_json(path)
        if (type(value) is not dict or set(value) != receipt_fields or value.get("schema_version") != "biocompiler.policy_native_campaign.v0.1"
                or value.get("status") != "passed" or value.get("counts") != expected_counts
                or any(value.get(key) != expected for key, expected in scopes.items())):
            raise AssertionError("Hosted native policy receipt is incomplete or changes its claim scope")
        if value.get("source_identity") != workflow_identity:
            raise AssertionError("Hosted receipt belongs to a different tested revision, head or workflow run")
        version = value.get("python_version")
        if type(version) is not list or len(version) != 3 or not all(type(part) is int for part in version) or version[0] != 3:
            raise AssertionError("Hosted receipt lacks an exact Python version")
        variant = value.get("sys_platform"), version[1]
        if variant not in expected_variants or variant in seen:
            raise AssertionError("Duplicate or unsupported hosted platform/Python variant")
        seen.add(variant)
        if value.get("machine") != {"linux": "x86_64", "darwin": "arm64"}[variant[0]]:
            raise AssertionError("Hosted receipt has the wrong native machine architecture")
        if (not absolute(value.get("interpreter")) or not absolute(value.get("installed_package"))
                or type(value.get("platform")) is not str or not value["platform"]
                or type(value.get("python")) is not str or not value["python"]):
            raise AssertionError("Hosted receipt lacks interpreter/platform/install provenance")
        expected_platforms = ("Linux-",) if variant[0] == "linux" else ("Darwin-", "macOS-")
        if not value["platform"].startswith(expected_platforms) or not value["python"].startswith(f"3.{version[1]}."):
            raise AssertionError("Hosted platform/interpreter provenance contradicts its variant")
        package = value["installed_package"]
        selected_inputs = value.get("selected_inputs")
        if type(selected_inputs) is not dict or set(selected_inputs) != {"core", "verify", "fixture"} or not all(absolute(item) for item in selected_inputs.values()):
            raise AssertionError("Hosted selected input provenance is incomplete")
        executables = value.get("executables")
        if type(executables) is not dict or set(executables) != {"core", "verify"}:
            raise AssertionError("Hosted receipt lacks both native executable identities")
        for role in ("core", "verify"):
            item = executables[role]
            if type(item) is not dict or set(item) != {"path", "sha256"} or not absolute(item["path"]) or not fingerprint(item["sha256"]):
                raise AssertionError("Hosted executable identity is incomplete")
        pins = {role: executables[role]["sha256"] for role in ("core", "verify")}
        required_pins = {role: published[variant[0]]["sha256"]["biocompiler-" + role] for role in ("core", "verify")}
        if pins != required_pins or variant[0] in platform_pins and platform_pins[variant[0]] != pins:
            raise AssertionError("Hosted executable pins differ from published bytes or the same-platform Python pair")
        platform_pins[variant[0]] = pins
        for field in ("console", "fixture"):
            item = value.get(field)
            if type(item) is not dict or set(item) != {"path", "sha256"} or not absolute(item["path"]) or not fingerprint(item["sha256"]):
                raise AssertionError("Hosted input/console provenance is incomplete")
        if value["fixture"]["sha256"] != digest_file(fixture):
            raise AssertionError("Hosted receipt identifies a different frozen input corpus")
        if value.get("parent_execution_guard") is not True:
            raise AssertionError("Parent execution guard was not established")
        origins(value.get("parent_imports"), package, {"biocompiler", "biocompiler.core_policy", "biocompiler.core_client"})
        rows = value.get("cases")
        expected_cases = {(name, kind, role) for name in EXPECTED_NAMES for kind in ("program", "request", "submission") for role in ("core", "verify")}
        identities: set[tuple[str, str, str]] = set()
        if type(rows) is not list or len(rows) != 48:
            raise AssertionError("Hosted source assessment census is incomplete")
        for row in rows:
            if type(row) is not dict or set(row) != {"name", "kind", "role", "artifact_digest", "document_digest", "program_digest", "assessment_fingerprint", "assessment", "fresh_replay", "forged_replay"}:
                raise AssertionError("Unexpected hosted assessment row fields")
            identity = row.get("name"), row.get("kind"), row.get("role")
            if identity not in expected_cases or identity in identities:
                raise AssertionError("Duplicate or unknown hosted policy case")
            identities.add(identity)
            if row.get("fresh_replay") != "passed" or row.get("forged_replay") != "rejected":
                raise AssertionError("Hosted case lacks fresh and rejection replay evidence")
            for key in ("artifact_digest", "document_digest", "program_digest", "assessment_fingerprint"):
                if not fingerprint(row.get(key)):
                    raise AssertionError("Hosted source identity is malformed")
            source = input_rows[(row["name"], row["kind"])]
            document = source["document"]
            if row["artifact_digest"] != source["artifact_digest"] or row["document_digest"] != source["fingerprint"]:
                raise AssertionError("Hosted case is not bound to the required frozen input")
            if source["kind"] == "submission":
                document = document["request"]
            program = document["program"] if document["$type"] == "BuildRequest" else document
            if row["program_digest"] != semantic_digest(program):
                raise AssertionError("Hosted program identity differs from frozen input")
            assessment = row.get("assessment")
            if (type(assessment) is not dict or set(assessment) != assessment_fields or canonical_digest(assessment) != row["assessment_fingerprint"]
                    or assessment.get("schema_version") != "biocompiler.policy_assessment.v0.1"
                    or assessment.get("status") != "valid" or assessment.get("diagnostics") != []
                    or any(assessment.get(key) != row[key] for key in ("artifact_digest", "document_digest", "program_digest"))
                    or any(assessment.get(key) != expected for key, expected in
                           {"semantic_status": "unresolved", "target_status": "unassessed", "lowering": "unsupported", "artifact": "withheld"}.items())):
                raise AssertionError("Hosted assessment differs from its immutable identity or claim scope")
            prefix = {"program": "/document", "request": "/document/program", "submission": "/document/request/program"}[source["kind"]]
            ledger = [{"id": declaration["id"], "kind": declaration["$type"],
                       "path": prefix + "/declarations/" + str(index), "value": declaration,
                       "sources": [span for span in program["source_map"] if span["declaration_id"] == declaration["id"]]}
                      for index, declaration in enumerate(program["declarations"])]
            if assessment.get("declarations") != ledger or assessment.get("requirements") != [entry for entry in ledger if entry["kind"] == "Requirement"]:
                raise AssertionError("Hosted receipt changed ordered source identity or correspondence")
        controls = value.get("negative_controls")
        if type(controls) is not list or len(controls) != 20 or len({(row["name"], row["role"]) for row in controls}) != 20:
            raise AssertionError("Hosted negative-control census is incomplete")
        for row in controls:
            if type(row) is not dict or set(row) != {"name", "role", "expected", "required_diagnostic", "diagnostics", "input_digest"}:
                raise AssertionError("Unexpected hosted negative-control fields")
            expected = expected_controls.get((row.get("name"), row.get("role")))
            if expected != (row.get("expected"), row.get("required_diagnostic"), row.get("input_digest")):
                raise AssertionError("Hosted mutation is not bound to the required negative input")
            if (row.get("role") not in ("core", "verify") or row.get("expected") not in ("invalid", "rejected")
                    or row.get("required_diagnostic") not in row.get("diagnostics", []) or not fingerprint(row.get("input_digest"))):
                raise AssertionError("Hosted negative control lacks independent rejection evidence")
        cli = value.get("cli")
        expected_cli = {(role, kind) for role in ("core", "verify") for kind in ("program", "request", "submission")}
        if type(cli) is not list or len(cli) != 6 or {(row["role"], row["kind"]) for row in cli} != expected_cli:
            raise AssertionError("Hosted installed console census is incomplete")
        for row in cli:
            if type(row) is not dict or set(row) != {"role", "kind", "status", "guard"}:
                raise AssertionError("Unexpected hosted console evidence fields")
            guard = row.get("guard", {})
            if (type(guard) is not dict or set(guard) != {"status", "origins", "guard_active", "execution_guard_active", "python", "executable"}
                    or row.get("status") != "passed" or guard.get("status") != "ok" or guard.get("guard_active") is not True
                    or guard.get("execution_guard_active") is not True or guard.get("python") != version[:2]
                    or guard.get("executable") != value["interpreter"]):
                raise AssertionError("Installed console guard/interpreter evidence differs")
            origins(guard.get("origins"), package, {"biocompiler.entrypoint", "biocompiler.policy.cli", "biocompiler.core_policy", "biocompiler.core_client"})
        # Only reported machine paths, interpreter version, and executable/console
        # bytes vary. Every source, result, ordering and diagnostic remains exact.
        projection = {"counts": value["counts"], "scopes": scopes, "fixture_sha256": value["fixture"]["sha256"],
                      "cases": rows, "negative_controls": controls,
                      "cli": [{key: row[key] for key in ("role", "kind", "status")} for row in cli]}
        if authority is None:
            authority = projection
        elif projection != authority:
            raise AssertionError("Hosted variants disagree on immutable source assessments or diagnostic controls")
        variants.append({"sys_platform": variant[0], "machine": value["machine"], "python_version": version, "receipt_path": str(path.resolve()),
                         "receipt_sha256": digest_file(path), "executables": executables, "console": value["console"],
                         "interpreter": value["interpreter"], "platform": value["platform"], "installed_package": package})
    if seen != expected_variants:
        raise AssertionError("Missing required hosted platform/Python variant")
    return {"schema_version": "biocompiler.policy_native_comparison.v0.1", "status": "passed",
            "counts": expected_counts, "variants": variants, "source_identity": workflow_identity, "published_binaries": published,
            "source_result_identity": canonical_digest(authority),
            **scopes, "claim_scope": "Exact source-assessment agreement for the retained hosted variants only."}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, default=Path(__file__).resolve().parents[1] / "core/test/data/policy_documents_v01.json")
    parser.add_argument("--console", type=Path)
    parser.add_argument("--native-artifacts", type=Path, help="Comparison-only root containing linux-x86_64 and macos-arm64 published binaries.")
    parser.add_argument("--compare", type=Path, action="append", help="Compare four retained hosted receipts; repeat once per variant.")
    arguments = parser.parse_args(argv)
    if arguments.output.exists() or arguments.output.is_symlink():
        parser.error("--output must name a new receipt")
    if arguments.compare:
        if arguments.core is not None or arguments.verify is not None or arguments.console is not None:
            parser.error("--compare cannot execute a native campaign")
        try:
            result = compare_receipts(arguments.compare, fixture=arguments.fixture, native_artifacts=arguments.native_artifacts)
        except Exception as error:
            write_receipt(arguments.output, {"schema_version": "biocompiler.policy_native_comparison.v0.1",
                "status": "failed", "error": str(error), "lowering": "unsupported", "sequence_artifact": "withheld"})
            print(str(error), file=sys.stderr)
            return 1
        write_receipt(arguments.output, result)
        print(json.dumps({"status": "passed", "variants": 4, "receipt": str(arguments.output)}))
        return 0
    if arguments.native_artifacts is not None:
        parser.error("--native-artifacts applies only to --compare")
    if arguments.core is None or arguments.verify is None:
        parser.error("A native campaign requires --core and --verify")
    progress: dict[str, Any] = {
        "schema_version": "biocompiler.policy_native_campaign.v0.1", "status": "running",
        "selected_inputs": {"core": str(arguments.core), "verify": str(arguments.verify),
                            "fixture": str(arguments.fixture)},
    }
    try:
        selected_console = arguments.console or (Path(shutil.which("biocompiler")) if shutil.which("biocompiler") else None)
        if selected_console is None:
            raise AssertionError("Select --console or install biocompiler on PATH")
        result = campaign(arguments.core, arguments.verify, arguments.fixture,
                          selected_console.resolve(strict=True), progress=progress)
    except Exception as error:
        result = progress
        result.update({"schema_version": "biocompiler.policy_native_campaign.v0.1", "status": "failed",
                  "error": str(error), "python": sys.version, "platform": platform.platform(),
                  "semantic_execution": "unsupported", "lowering": "unsupported", "sequence_artifact": "withheld"})
        write_receipt(arguments.output, result)
        print(str(error), file=sys.stderr)
        return 1
    write_receipt(arguments.output, result)
    print(json.dumps({"status": result["status"], "counts": result["counts"], "receipt": str(arguments.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
