"""Complete original package bytes; never execute a native candidate or checker."""
from pathlib import Path
from dataclasses import replace
import hashlib
import json
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
import biocompiler
from biocompiler.compiler import reference as source
from biocompiler.registry import reference_builds
from biocompiler.registry.references import ReferenceManifest
from biocompiler.artifacts.manifest import RunMetadata
from biocompiler.artifacts.archive import read_archive
from tools.reference_package_source_lineage import source_identity


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()


def capture():
    directory = ROOT / "data/references/fap_car"
    manifest = ReferenceManifest.from_json((directory / "manifest.json").read_text())
    files = {"manifest.json": (directory / "manifest.json").read_bytes()}
    for path in sorted(reference_builds._retained_paths(manifest)):
        files[path] = (directory / path).read_bytes()
    cases = []
    for identity, alphabet, width, metadata, version, changed_tool, invalid in (
        ("DNA:default", "DNA", 80, None, None, False, False),
        ("RNA:default", "RNA", 80, None, None, False, False),
        ("DNA:width1", "DNA", 1, None, None, False, False),
        ("RNA:width10000", "RNA", 10000, None, None, False, False),
        ("DNA:run-metadata", "DNA", 80, RunMetadata("2026-10-02T00:00:00Z", "fixture", {"work": "/reference-fixture"}), None, False, False),
        ("DNA:current-sdk", "DNA", 80, None, "fixture-current-sdk", False, False),
        ("RNA:current-tool", "RNA", 80, None, None, True, False),
        ("DNA:unsupported-layout", "DNA", 80, None, None, False, True),
    ):
        request = source.prepare_reference_build(alphabet, directory, fasta_line_width=width)
        if invalid:
            molecule = replace(request.construct.molecules[0], length=request.construct.molecules[0].length + 1)
            request = replace(request, construct=replace(request.construct, molecules=(molecule,)))
        row = {"id": identity, "input": {"request": request.to_dict(), "files": [[k, v.hex()] for k, v in files.items()],
            "run_metadata": None if metadata is None else metadata.to_dict(),
            "package_version": version or biocompiler.__version__, "changed_tool": changed_tool}}
        calls = []
        originals = {name: getattr(source, name) for name in ("load_reference_inputs", "collect_reference_files", "run_molecular_pipeline", "export_reference_sequence", "check_composition", "check_construct", "_tools")}
        contexts = []
        from contextlib import ExitStack
        with ExitStack() as stack:
            for name, original in originals.items():
                def wrapped(*args, __name=name, __source=original, **kwargs):
                    calls.append(__name)
                    result = __source(*args, **kwargs)
                    if __name == "run_molecular_pipeline":
                        contexts.append(result)
                    return result
                stack.enter_context(patch.object(source, name, wrapped))
            stack.enter_context(patch.object(biocompiler, "__version__", row["input"]["package_version"]))
            if changed_tool:
                stack.enter_context(patch.object(source, "MOLECULAR_CHECKER_VERSION", "fixture-current-checker"))
            try:
                result = source.build_reference_package(request, directory, run_metadata=metadata)
                actual_manifest, members, actual_metadata = read_archive(result.data)
                row["outcome"] = {"status": "return", "value": {
                    "request": result.request.to_dict(), "manifest": actual_manifest.to_dict(),
                    "data": result.data.hex(), "archive_sha256": result.archive_sha256,
                    "build_fingerprint": result.build_fingerprint,
                    "files": [[k, v.hex()] for k, v in members.items()],
                    "run_metadata": None if actual_metadata is None else actual_metadata.to_dict()}}
            except Exception as error:
                row["outcome"] = {"status": "raise", "module": type(error).__module__, "type": type(error).__qualname__, "message": str(error)}
        row["calls"] = calls
        cases.append(row)
    sources = {path: source_identity(ROOT, path) for path in (
        "src/biocompiler/compiler/reference.py", "src/biocompiler/compiler/construct.py", "src/biocompiler/compiler/molecular.py",
        "src/biocompiler/artifacts/sequences.py", "src/biocompiler/artifacts/manifest.py", "src/biocompiler/artifacts/archive.py",
        "src/biocompiler/artifacts/archive_container.py", "src/biocompiler/registry/reference_builds.py")}
    return {"schema": "biocompiler.reference_package_workflow_literals.v1", "sources": sources, "cases": cases}


if __name__ == "__main__":
    Path(sys.argv[1]).write_bytes(canonical(capture()) + b"\n")
