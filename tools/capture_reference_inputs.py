"""Original reviewed file authority, independent of native implementation."""
from pathlib import Path
from dataclasses import replace
import hashlib
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
from biocompiler.registry import reference_builds as source
from biocompiler.registry.references import ReferenceManifest
from tools.reference_package_source_lineage import source_identity


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()


def capture():
    root = ROOT / "data/references/fap_car"
    manifest = ReferenceManifest.from_json((root / "manifest.json").read_text())
    files = {"manifest.json": (root / "manifest.json").read_bytes()}
    for path in sorted(source._retained_paths(manifest)):
        files[path] = (root / path).read_bytes()
    rows = []

    def observe(identity, operation, contents, **arguments):
        row = {"id": identity, "operation": operation, "input": {
            "files": [[name, content.hex()] for name, content in contents.items()], **arguments}}
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for name, content in contents.items():
                path = directory / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            try:
                if operation == "manifest-bytes":
                    value = ReferenceManifest.from_dict(arguments["manifest"]).to_json().encode().hex()
                elif operation == "load":
                    current, retained = source._load_pinned_inputs(directory)
                    value = {"manifest": current.to_dict(), "files": [[k, v.hex()] for k, v in retained.items()]}
                elif operation == "collect":
                    current = ReferenceManifest.from_dict(arguments["reference"])
                    retained = source.collect_reference_files(directory, current)
                    value = [[k, v.hex()] for k, v in retained.items()]
                else:
                    request, current, registry = source.load_reference_inputs(arguments["alphabet"], directory)
                    value = {"request": request.to_dict(), "manifest": current.to_dict(), "registry": registry.to_dict()}
                row["outcome"] = {"status": "return", "value": value}
            except Exception as error:
                row["outcome"] = {"status": "raise", "module": type(error).__module__, "type": type(error).__qualname__, "message": str(error)}
                assert temporary not in str(error), "Platform/path-specific filesystem errors are separate adapter scope."
        rows.append(row)

    observe("load:original", "load", files)
    observe("load:reversed-input", "load", dict(reversed(list(files.items()))))
    observe("load:irrelevant-file", "load", files | {"unused.txt": b"not read or retained"})
    observe("load:compact-manifest", "load", files | {"manifest.json": canonical(manifest.to_dict())})
    observe("load:reordered-manifest", "load", files | {"manifest.json": json.dumps(dict(reversed(list(manifest.to_dict().items())))).encode()})
    for name in files:
        if name != "manifest.json":
            observe("load:altered:" + name, "load", files | {name: files[name] + b"changed"})
    observe("load:wrong-pin", "load", files | {"manifest.json": replace(manifest, version="2").to_json().encode()})
    observe("load:wrong-fields", "load", files | {"manifest.json": b"{}"})
    observe("load:duplicate-key", "load", files | {"manifest.json": b'{"version":1,"version":2}'})
    observe("load:nan", "load", files | {"manifest.json": b'{"version":NaN}'})
    observe("collect:original", "collect", files, reference=manifest.to_dict())
    observe("collect:stale-source", "collect", files, reference=replace(manifest, version="2").to_dict())
    for alphabet in ("DNA", "RNA"):
        observe("prepare:" + alphabet, "prepare", files, alphabet=alphabet)
    for label, note in (("accent-astral", "é 🧬"), ("separators", "line\u2028paragraph\u2029")):
        changed = manifest.to_dict()
        changed["redistribution"]["note"] = note
        observe("manifest-bytes:" + label, "manifest-bytes", files, manifest=changed)
    sources = {path: source_identity(ROOT, path) for path in (
        "src/biocompiler/registry/reference_builds.py", "src/biocompiler/registry/references.py",
        "src/biocompiler/registry/reference_components.py", "src/biocompiler/synthesis/construct.py")}
    return {"schema": "biocompiler.reference_input_snapshot_literals.v1", "sources": sources, "cases": rows}


if __name__ == "__main__":
    Path(sys.argv[1]).write_bytes(canonical(capture()) + b"\n")
