"""Check an already installed authoring package from outside its checkout.

Run with the installation's Python interpreter. --installed-root must contain
both the imported package and --scripts/biocompiler (for example a pip --target
directory or a complete virtual environment). This tool installs nothing.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import importlib.abc
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from types import ModuleType
from typing import Sequence

MAX_OUTPUT = 2 * 1024 * 1024
EXPECTED_EXAMPLES = (
    "context_gated_response", "regulated_secretion", "staged_cleanup_repair",
    "encounter_sentinel", "target_sentinel", "local_restraint",
    "coordinated_populations", "lineage_bounded_response",
)


class ImportBoundary(importlib.abc.MetaPathFinder):
    """Allow only the authoring subtree and its two installed entry points."""

    def __init__(self, root: Path, receipt: Path | None = None) -> None:
        self.root = root.resolve()
        self.receipt = receipt
        self.denied: list[str] = []

    @staticmethod
    def guarded(name: str) -> bool:
        return name == "biocompiler" or name.startswith(("biocompiler.", "_biocompiler", "biocompiler_core"))

    @staticmethod
    def allowed(name: str) -> bool:
        return name in ("biocompiler", "biocompiler.policy", "biocompiler.entrypoint", "biocompiler.__main__") or name.startswith("biocompiler.policy.")

    def find_spec(self, fullname: str, path: Sequence[str] | None = None,
                  target: ModuleType | None = None) -> None:
        if self.guarded(fullname) and not self.allowed(fullname):
            self.denied.append(fullname)
            raise ImportError("Installed authoring check forbids semantic/compiler/core import: " + fullname)
        return None

    def origins(self) -> dict[str, str]:
        if self.denied:
            raise AssertionError("Forbidden import was attempted: " + ", ".join(self.denied))
        result: dict[str, str] = {}
        for name, module in tuple(sys.modules.items()):
            if not self.guarded(name):
                continue
            if not self.allowed(name):
                raise AssertionError("Forbidden module was already loaded: " + name)
            filename = getattr(module, "__file__", None)
            if not filename or not Path(filename).resolve().is_relative_to(self.root):
                raise AssertionError("Module is outside installed root: " + name)
            result[name] = str(Path(filename).resolve())
        return dict(sorted(result.items()))

    def finish(self) -> None:
        assert self.receipt is not None
        try:
            value: dict[str, object] = {"status": "ok", "origins": self.origins()}
        except Exception as error:
            value = {"status": "error", "message": str(error)}
        value.update({"guard_active": True, "python": list(sys.version_info[:2]),
                      "executable": str(Path(sys.executable).resolve())})
        self.receipt.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def run_bounded(command: Sequence[str], *, cwd: Path, env: dict[str, str],
                maximum: int = MAX_OUTPUT, timeout: float = 30) -> tuple[int, bytes, bytes]:
    """Drain both pipes concurrently; terminate before retaining excess output."""
    process = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    retained: list[bytearray] = [bytearray(), bytearray()]
    overflow = threading.Event()

    def drain(index: int) -> None:
        stream = process.stdout if index == 0 else process.stderr
        assert stream is not None
        try:
            while chunk := stream.read(65536):
                if len(retained[index]) + len(chunk) > maximum:
                    overflow.set()
                    process.kill()
                    break
                retained[index].extend(chunk)
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
        raise AssertionError("Installed CLI exceeded its time bound") from error
    finally:
        for reader in readers:
            reader.join(timeout=5)
    if overflow.is_set() or any(reader.is_alive() for reader in readers):
        raise AssertionError("Installed CLI exceeded its output bound")
    return process.returncode, bytes(retained[0]), bytes(retained[1])


def _read_json(path: Path) -> object:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_OUTPUT:
        raise AssertionError("Missing, redirected or oversized output: " + str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def check_install(installed_root: Path, scripts: Path) -> dict[str, object]:
    root, scripts = installed_root.resolve(strict=True), scripts.resolve(strict=True)
    checkout = Path(__file__).resolve().parents[1]
    if (checkout / "src/biocompiler").is_dir():
        if Path.cwd().resolve().is_relative_to(checkout) or root.is_relative_to(checkout):
            raise AssertionError("Run against an installation outside the checkout, from an outside working directory")
    console = (scripts / "biocompiler").resolve(strict=True)
    if not scripts.is_relative_to(root) or not console.is_relative_to(scripts) or not console.is_file() or not os.access(console, os.X_OK):
        raise AssertionError("The executable console must be inside --scripts inside --installed-root")
    if (root / "biocompiler/__init__.py").is_file():
        sys.path.insert(0, str(root))
    guard = ImportBoundary(root)
    # Refuse an already contaminated interpreter before installing the finder.
    guard.origins()
    sys.meta_path.insert(0, guard)
    try:
        import biocompiler.policy as p
        from biocompiler.policy import examples

        origins = guard.origins()
        package_parent = Path(origins["biocompiler"]).parent.parent
        if tuple(examples.NAMES) != EXPECTED_EXAMPLES:
            raise AssertionError("Installed abstract example census differs")
        records: list[dict[str, object]] = []
        commands = 0
        with tempfile.TemporaryDirectory(prefix="biocompiler-policy-install-") as directory:
            work = Path(directory)
            guard_dir = work / "import-guard"
            guard_dir.mkdir()
            receipt = work / "cli-origin.json"
            # Exercise the actual installed console executable. Its interpreter
            # loads this stdlib-only guard before importing biocompiler.
            source = ("from __future__ import annotations\nimport atexit, importlib.abc, json, sys\n"
                      "from pathlib import Path\nfrom types import ModuleType\nfrom typing import Sequence\n"
                      + inspect.getsource(ImportBoundary)
                      + f"\n_guard = ImportBoundary(Path({str(root)!r}), Path({str(receipt)!r}))\n"
                      "sys.meta_path.insert(0, _guard)\natexit.register(_guard.finish)\n")
            (guard_dir / "sitecustomize.py").write_text(source, encoding="utf-8")
            environment = {key: value for key, value in os.environ.items()
                           if key not in ("PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE")}
            environment.update({"PYTHONPATH": os.pathsep.join((str(guard_dir), str(package_parent))),
                                "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"})

            def cli(*arguments: str, expected: int = 0) -> object:
                nonlocal commands
                receipt.unlink(missing_ok=True)
                code, stdout, stderr = run_bounded([str(console), "policy", "--json", *arguments], cwd=work, env=environment)
                proof = _read_json(receipt)
                assert isinstance(proof, dict)
                if proof.get("status") != "ok" or proof.get("guard_active") is not True:
                    raise AssertionError("Installed console import guard failed: " + str(proof))
                if proof.get("python") != list(sys.version_info[:2]) or proof.get("executable") != str(Path(sys.executable).resolve()):
                    raise AssertionError("Installed console used a different Python interpreter")
                imported = proof.get("origins")
                if not isinstance(imported, dict) or not {"biocompiler", "biocompiler.policy", "biocompiler.entrypoint", "biocompiler.policy.cli"} <= imported.keys():
                    raise AssertionError("Console did not import the installed public policy entry point")
                if code != expected:
                    raise AssertionError(f"Console {arguments[0]} expected exit {expected}, received {code}: {stderr.decode('utf-8', errors='replace')}")
                if bool(stdout) == bool(stderr):
                    raise AssertionError("Console must write exactly one JSON response stream")
                commands += 1
                return json.loads(stdout or stderr)

            for name in EXPECTED_EXAMPLES:
                program, request = examples.build_example(name), examples.build_request(name)
                assert isinstance(program, p.PolicyProgram) and isinstance(request, p.BuildRequest)
                assert p.document_digest(program) == p.document_digest(request.program)
                for document in (program, request):
                    report = p.check(document)
                    assert report.status == "complete" and not report.errors, (name, report.to_dict())
                    assert report.semantic_status == report.target_status == "unassessed"
                    assert p.from_data(p.to_data(document), type(document)) == document
                    assert p.loads(p.dumps(document), type(document)) == document
                    view = p.inspect(document)
                    assert view["document_digest"] == p.document_digest(document)
                    assert view["semantic_status"] == view["target_status"] == "unassessed"
                    assert view["graph"] == p.graph(document)
                    assert p.graph(document)["unmatched_reference_count"] == 0
                    html = document._repr_html_()
                    assert "unassessed" in html and "<script" not in html.lower()
                    assert p.diff(document, document)["identical_document"] is True
                altered = replace(program, id="<script>authoring-control</script>")
                assert "<script>" not in altered._repr_html_() and "&lt;script&gt;" in altered._repr_html_()
                assert p.diff(program, altered)["identical_declaration_content"] is False
                request_path = work / (name + ".request.json")
                p.dump(request, request_path)
                assert p.load(request_path, p.BuildRequest) == request
                submission = p.prepare_submission(request)
                assert isinstance(submission, p.CompilationSubmission)
                assert submission.semantic_status == submission.target_status == "unassessed"
                assert submission.backend_execution == "not_performed" and submission.request == request
                submission_path = work / (name + ".submission.json")
                p.dump(submission, submission_path)
                assert p.load(submission_path, p.CompilationSubmission) == submission
                missing = p.assess_capabilities(request, p.BackendCapabilities("absent-backend", "0", (), ()))
                assert missing.status == "unsupported" and missing.unsupported_features and not missing.profile_supported
                assert missing.semantic_status == "unassessed" and missing.backend_execution == "not_performed"
                assert cli("check", str(request_path)) == p.check(request).to_dict()
                exported = work / (name + ".cli-submission.json")
                cli("export-request", str(request_path), "-o", str(exported))
                assert _read_json(exported) == p.to_data(submission)
                records.append({"name": name, "request_digest": p.document_digest(request),
                                "required_features": len(submission.required_features)})

            schema_path = work / "schema.json"
            cli("export-schema", "-o", str(schema_path))
            assert _read_json(schema_path) == p.schema()
            assert p.schema(p.CompilationSubmission)["$ref"] == "#/$defs/CompilationSubmission"
            assert cli("inspect", str(request_path)) == p.inspect(request)
            assert cli("diff", str(request_path), str(request_path)) == p.diff(request, request)
            # Existing exports remain intact until explicit replacement.
            before = exported.read_bytes()
            cli("export-request", str(request_path), "-o", str(exported), expected=2)
            assert exported.read_bytes() == before
            cli("export-request", str(request_path), "-o", str(exported), "--replace")
            draft_path, rejected = work / "draft.json", work / "rejected.json"
            draft = p.PolicyDraft("unresolved", program.semantics, program.declarations,
                                  (p.Hole("remaining", "policy", "Resolve the design choice."),))
            p.dump(draft, draft_path)
            assert cli("check", str(draft_path), expected=1) == p.check(draft).to_dict()
            cli("export-request", str(draft_path), "-o", str(rejected), expected=1)
            assert not rejected.exists()
        return {"schema_version": "biocompiler.policy_install_check.v0.1", "status": "passed",
                "python": list(sys.version_info[:3]), "installed_root": str(root), "console": str(console),
                "examples": records, "cli_commands": commands, "module_origins": guard.origins(),
                "semantic_status": "unassessed", "backend_execution": "not_performed",
                "scope": "Installed pure-Python authoring API and console only; no compiler or native acceptance."}
    finally:
        sys.meta_path.remove(guard)


def main(argv: Sequence[str] | None = None) -> int:
    if not __debug__:
        raise RuntimeError("Installed checks require Python assertions enabled")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed-root", required=True, type=Path)
    parser.add_argument("--scripts", required=True, type=Path)
    arguments = parser.parse_args(argv)
    print(json.dumps(check_install(arguments.installed_root, arguments.scripts), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
