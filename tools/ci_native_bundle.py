"""Move one hosted native build to independent test jobs, with exact accounting.

The supported Dune test stanzas are deliberately closed. A new action, fixture,
or stanza must be handled explicitly instead of silently losing native coverage.
No compilation is performed by restore or test.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import zipfile

try:
    from . import ci_validation as ci
except ImportError:
    import ci_validation as ci


DEPENDENCY_FIXTURES = {
    "test_policy_provider_prerequisites": ["data/policy_material_request_v01.json", "data/policy_material_state_v01.json"],
    "test_policy_prerequisite_material_service": ["data/policy_material_request_v01.json", "data/policy_material_state_v01.json"],
    "test_policy_two_observation_material_service": ["data/policy_material_request_v01.json", "data/policy_material_state_v01.json"],
    "test_policy_multi_member_material_service": ["data/policy_staged_material_v01.json"],
    "test_policy_grounded_helper_material_service": ["data/policy_staged_material_v01.json"],
    "test_policy_instance_assembly_rule": ["data/policy_material_request_v01.json", "data/policy_material_state_v01.json"],
    "test_policy_instance_material_service": ["data/policy_material_request_v01.json", "data/policy_material_state_v01.json"],
    "test_policy_staged_generation": ["data/policy_staged_realization_request_v01.json"],
    "test_policy_staged_binding": ["data/policy_staged_realization_request_v01.json"],
    "test_policy_staged_component_material": ["data/policy_staged_material_v01.json"],
    "test_policy_staged_primitives": ["data/policy_implementation_v01.json"],
    "test_policy_staged_regimen_source": ["data/policy_staged_regimen_source_v01.json"],
    "test_policy_document": ["data/policy_documents_v01.json"],
    "test_policy_check": ["data/policy_frontend_request.json", "data/policy_frontend_submission.json",
                          "data/policy_documents_v01.json"],
    "test_policy_service": ["data/policy_documents_v01.json"],
    'test_policy_operational': ['data/policy_operational_v01.json'],
    'test_policy_execution': ['data/policy_operational_v01.json'],
    'test_policy_operational_service': ['data/policy_operational_v01.json'],
    'test_policy_realization_source': ['data/policy_realization_source_v01.json'],
    'test_policy_exclusion_source': ['data/policy_exclusion_source_v01.json'],
    'test_policy_operating_domain': ['data/policy_operating_domain_v01.json', 'data/policy_operational_v01.json'],
    'test_policy_implementation': ['data/policy_implementation_v01.json'],
    'test_policy_realization_admission': ['data/policy_realization_request_v01.json', 'data/policy_realization_source_v01.json'],
    'test_policy_domain_reference': ['data/policy_operating_domain_v01.json', 'data/policy_operational_v01.json'],
    'test_policy_primitives': ['data/policy_implementation_v01.json', 'data/policy_primitives_v01.json'],
    'test_policy_trace_correspondence': ['data/policy_implementation_binding_v01.json'],
    'test_policy_implementation_binding': ['data/policy_implementation_binding_v01.json', 'data/policy_realization_request_v01.json', 'data/policy_exclusion_source_v01.json'],
    'test_policy_implementation_lowering': ['data/policy_implementation_binding_v01.json'],
    'test_policy_requirement_monitor': ['data/policy_implementation_binding_v01.json'],
    'test_policy_preservation_check': ['data/policy_implementation_binding_v01.json'],
    'test_construction_content': ['data/construction_content_v01.json'],
    'test_policy_mrna_structure': ['data/policy_mrna_structure_v01.json'],
    'test_policy_implementation_service': ['data/policy_implementation_request_v01.json'],
    'test_policy_material_binding': ['data/policy_material_binding_v01.json'],
    'test_policy_component_fragment': ['data/policy_material_request_v01.json', 'data/policy_material_state_v01.json'],
    'test_policy_component_material': ['data/policy_material_request_v01.json', 'data/policy_material_state_v01.json'],
    'test_policy_component_assembly_rule': ['data/policy_material_request_v01.json', 'data/policy_material_state_v01.json'],
    'test_policy_component_assembly_check': ['data/policy_material_request_v01.json', 'data/policy_material_state_v01.json'],
    'test_policy_component_material_request': ['data/policy_material_request_v01.json', 'data/policy_material_state_v01.json'],
    'test_policy_component_selection_request': ['data/policy_material_request_v01.json', 'data/policy_material_state_v01.json'],
    'test_policy_component_material_candidate': ['data/policy_material_request_v01.json'],
    'test_policy_component_selection_candidate': ['data/policy_material_request_v01.json'],
    'test_policy_component_selection_common': ['data/policy_material_request_v01.json', 'data/policy_material_state_v01.json'],
    'test_policy_component_selection_check': ['data/policy_material_request_v01.json'],
    'test_policy_component_selection_scope': ['data/policy_material_request_v01.json'],
    'test_policy_component_selection_producer': ['data/policy_material_request_v01.json'],
    'test_policy_generation_admission': ['data/policy_implementation_binding_v01.json'],
    'test_policy_generation_producers': ['data/policy_material_request_v01.json', 'data/policy_material_state_v01.json'],
    'test_policy_component_selection_service': ['data/policy_material_request_v01.json'],
    'test_policy_component_context_check': ['data/policy_material_request_v01.json', 'data/policy_material_state_v01.json'],
    'test_policy_component_material_service': ['data/policy_material_request_v01.json', 'data/policy_material_state_v01.json'],
    'test_policy_material_context': ['data/policy_material_context_v01.json'],
    'test_policy_material_check': ['data/policy_material_request_v01.json'],
    'test_policy_material_service': ['data/policy_material_request_v01.json'],
    'test_policy_material_lifecycle': ['data/policy_material_lifecycle_v01.json'],
    'test_policy_material_compound': ['data/policy_material_compound_v01.json'],
    'test_policy_material_domain': ['data/policy_material_domain_v01.json'],
    'test_policy_material_closure': ['data/policy_material_closure_v01.json'],
    'test_policy_material_timing': ['data/policy_material_timing_v01.json'],
    'test_policy_material_state': ['data/policy_material_state_v01.json'],
}


def require(value, message):
    if not value:
        raise ValueError(message)


def manifest_document(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate native manifest key")
            result[key] = value
        return result
    def constant(value):
        raise ValueError("Nonfinite native manifest value: " + value)
    result = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    require(type(result) is dict, "Malformed native manifest")
    return result


def test_plan(text):
    tokens = re.findall(r"\(|\)|[^\s()]+", text)
    offset = 0

    def node():
        nonlocal offset
        require(offset < len(tokens), "Truncated Dune test declaration")
        token = tokens[offset]
        offset += 1
        if token != "(":
            require(token != ")", "Unexpected Dune closing delimiter")
            return token
        result = []
        while offset < len(tokens) and tokens[offset] != ")":
            result.append(node())
        require(offset < len(tokens), "Unclosed Dune test declaration")
        offset += 1
        return result

    result = []
    while offset < len(tokens):
        stanza = node()
        require(isinstance(stanza, list) and stanza and stanza[0] == "test", "Unsupported Dune stanza")
        fields = {}
        for field in stanza[1:]:
            require(isinstance(field, list) and field and field[0] not in fields, "Duplicate or malformed Dune field")
            fields[field[0]] = field[1:]
        require(set(fields) in ({"name", "modules", "libraries"}, {"name", "modules", "libraries", "action"}),
                "Unsupported Dune test fields")
        require(len(fields["name"]) == 1 and re.fullmatch(r"test_[a-z0-9_]+", fields["name"][0]), "Invalid native test name")
        name = fields["name"][0]
        require(fields["modules"] == [name] and all(isinstance(x, str) for x in fields["libraries"]), "Unsupported native test modules")
        action = fields.get("action", [["run", "%{test}"]])
        require(len(action) == 1 and isinstance(action[0], list) and action[0][:2] == ["run", "%{test}"], "Unsupported native test action")
        arguments = action[0][2:]
        if name in DEPENDENCY_FIXTURES:
            dependencies = DEPENDENCY_FIXTURES[name]
            require(arguments == ["%{dep:" + path + "}" for path in dependencies],
                    "Changed native dependency fixture arguments")
            result.append({"name": name, "environment": [], "dependencies": list(dependencies)})
        else:
            require(all(isinstance(arg, str) and re.fullmatch(r"%\{env:BIOCOMPILER_[A-Z0-9_]+=missing\}", arg) for arg in arguments),
                    "Unsupported native test argument")
            result.append({"name": name, "environment": [arg[6:-9] for arg in arguments]})
    require(result and len({row["name"] for row in result}) == len(result), "Empty or duplicated native test census")
    return result


def expected_members(root):
    plan = test_plan((root / "core/test/dune").read_text())
    # The independent declaration emitter is needed by restored hosted jobs.
    # It has no producer/checker dependency and is not a native test suite.
    return {"core/_build/default/bin/core/main.exe", "core/_build/default/bin/verify/main.exe",
            "core/_build/default/test/component_fixture_export/main.exe",
            "core/_build/default/test/instance_fixture_export/main.exe",
            "core/_build/default/test/prerequisite_fixture_export/main.exe",
            "core/_build/default/test/two_observation_fixture_export/main.exe",
            "core/_build/default/test/multi_member_fixture_export/main.exe",
            "core/_build/default/test/grounded_helper_fixture_export/main.exe"} | {
        "core/_build/default/test/" + row["name"] + ".exe" for row in plan} | set(dependency_members(root))


def dependency_members(root):
    """Map closed bundle destinations to complete original source fixtures."""
    plan = test_plan((root / "core/test/dune").read_text())
    return {"core/_build/default/test/" + path: "core/test/" + path
            for row in plan for path in row.get("dependencies", [])}


def fixture_pin(root, relative):
    path = root / relative
    require(path.is_file() and not path.is_symlink()
            and not any(parent.is_symlink() for parent in path.parents if parent != root.parent),
            "Missing or unsafe native dependency fixture: " + relative)
    return file_pin(path)


def file_pin(path):
    require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= 128 * 1024 * 1024, "Unsafe or oversized compiled executable")
    with path.open("rb") as source:
        return {"sha256": hashlib.file_digest(source, "sha256").hexdigest(), "size": path.stat().st_size}


def bundle(root, output):
    require(not output.exists(), "Native bundle must be new")
    paths = sorted(expected_members(root))
    fixtures = dependency_members(root)
    metadata = {"schema": "biocompiler.ci_native_bundle.v1", **ci.identity(),
                "system": ci.platform.system(), "machine": ci.platform.machine(),
                "dune_sha256": hashlib.sha256((root / "core/test/dune").read_bytes()).hexdigest(),
                "files": {name: fixture_pin(root, fixtures[name]) if name in fixtures
                          else file_pin(root / name) for name in paths}}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(metadata, sort_keys=True))
        for name in paths:
            archive.write(root / fixtures.get(name, name), name)


def restore(root, source):
    require(source.is_file() and not source.is_symlink(), "Missing native bundle")
    with zipfile.ZipFile(source) as archive:
        names = archive.namelist()
        wanted = expected_members(root)
        fixtures = dependency_members(root)
        require(len(names) == len(set(names)) and set(names) == wanted | {"manifest.json"}, "Native bundle member census differs")
        require(archive.getinfo("manifest.json").file_size < 1024 * 1024, "Oversized native manifest")
        document = manifest_document(archive.read("manifest.json"))
        identity = ci.identity()
        require(document.get("schema") == "biocompiler.ci_native_bundle.v1"
                and all(document.get(k) == identity[k] for k in ("revision", "run_id"))
                and ci.valid_attempt(document.get("run_attempt"), identity["run_attempt"]), "Stale native bundle")
        require((document.get("system"), document.get("machine")) == (ci.platform.system(), ci.platform.machine()), "Wrong native bundle platform")
        require(document.get("dune_sha256") == hashlib.sha256((root / "core/test/dune").read_bytes()).hexdigest()
                and set(document.get("files", {})) == wanted, "Native test declaration or file census changed")
        # Validate the entire archive before writing any executable. Destination
        # names are derived from current source, never from an archive path.
        for name in sorted(wanted):
            entry = archive.getinfo(name)
            require(0 < entry.file_size <= 128 * 1024 * 1024, "Oversized native member")
            raw = archive.read(name)
            require(document["files"][name] == {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}, "Native member hash mismatch")
            if name in fixtures:
                require(document["files"][name] == fixture_pin(root, fixtures[name]),
                        "Native dependency fixture differs from original source: " + fixtures[name])
            target = root / name
            require(not target.exists() and not target.is_symlink()
                    and not any(p.is_symlink() for p in target.parents if p != root.parent), "Unsafe native restore destination")
        for name in sorted(wanted):
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as handle:
                handle.write(archive.read(name))
            target.chmod(0o644 if name in fixtures else 0o755)
    return document


def run_tests(root, output, workers):
    require(1 <= workers <= 4, "Native test concurrency outside bounded range")
    plan = test_plan((root / "core/test/dune").read_text())
    output.mkdir(parents=True, exist_ok=False)
    commands = []
    for row in plan:
        command = [str(root / "core/_build/default/test" / (row["name"] + ".exe"))]
        file_pin(Path(command[0]))
        for name in row["environment"]:
            value = os.environ.get(name, "")
            require(value and Path(value).is_absolute() and Path(value).exists(), "Missing required native fixture: " + name)
            command.append(value)
        for relative in row.get("dependencies", []):
            original = "core/test/" + relative
            restored = "core/_build/default/test/" + relative
            require(fixture_pin(root, restored) == fixture_pin(root, original),
                    "Native dependency fixture differs from original source: " + original)
            command.append(str(root / restored))
        commands.append((row["name"], command))

    def execute(item):
        name, command = item
        start = time.monotonic()
        print("Native suite started: " + name, flush=True)
        with (output / (name + ".log")).open("xb") as log:
            result = subprocess.run(command, cwd=root / "core/_build/default/test", stdout=log, stderr=subprocess.STDOUT, timeout=1800)
        receipt = {"name": name, "argv": command, "returncode": result.returncode,
                   "duration_seconds": round(time.monotonic() - start, 6), "log": file_pin(output / (name + ".log")) if (output / (name + ".log")).stat().st_size else {"sha256": hashlib.sha256(b"").hexdigest(), "size": 0}}
        print(f"Native suite completed: {name} ({receipt['duration_seconds']}s, exit {result.returncode})", flush=True)
        return receipt

    with ThreadPoolExecutor(max_workers=workers) as executor:
        receipts = list(executor.map(execute, commands))
    ci.write_json(output / "receipt.json", {**ci.identity(), "tests": receipts, "expected": [row["name"] for row in plan]})
    require([row["name"] for row in receipts] == [row["name"] for row in plan]
            and all(row["returncode"] == 0 for row in receipts), "Incomplete or failed native suite census")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("bundle", "restore", "test"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.operation == "bundle":
        bundle(root, args.path)
    elif args.operation == "restore":
        restore(root, args.path)
    else:
        run_tests(root, args.path, args.workers)


if __name__ == "__main__":
    main()
