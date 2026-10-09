"""Hosted opt-in development feedback; never a release-acceptance receipt.

Only the existing closed Dune parser supplies executable fixture arguments.
All commands are fixed here; a supplied document cannot choose a native target.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import sys
import time

try:
    from . import ci_native_bundle as bundle
except ImportError:
    import ci_native_bundle as bundle

SCHEMA = "biocompiler.development-feedback.v0.1"
WORKFLOW = ".github/workflows/policy-development.yml"
SOURCE_ROOTS = ("core", "src", "tools", "protocol", ".github", "data/researcher_alpha",
                "examples/researcher_alpha.py", "pyproject.toml")
SUITES = (
    ("test_policy_admitted_ir", ('data/policy_operational_v01.json', 'data/policy_staged_regimen_source_v01.json', 'data/policy_implementation_binding_v01.json')),
    ("test_policy_finite_machine", ('data/policy_finite_machine_v01.json',)),
    ("test_policy_refinement", ('data/policy_finite_machine_v01.json',)),
    ("test_policy_quantitative", ('data/policy_quantitative_v01.json',)),
    ("test_policy_provider_prerequisites", ("data/policy_material_request_v01.json", "data/policy_material_state_v01.json")),
    ("test_policy_prerequisite_material_service", ("data/policy_material_request_v01.json", "data/policy_material_state_v01.json")),
    ("test_policy_two_observation_material_service", ("data/policy_material_request_v01.json", "data/policy_material_state_v01.json")),
    ("test_policy_multi_member_material_service", ("data/policy_staged_material_v01.json",)),
    ("test_policy_grounded_helper_material_service", ("data/policy_staged_material_v01.json",)),
    ("test_policy_instance_assembly_rule", ("data/policy_material_request_v01.json", "data/policy_material_state_v01.json")),
    ("test_policy_instance_material_service", ("data/policy_material_request_v01.json", "data/policy_material_state_v01.json")),
    ("test_policy_staged_generation", ("data/policy_staged_realization_request_v01.json",)),
    ("test_policy_staged_binding", ("data/policy_staged_realization_request_v01.json",)),
    ("test_policy_staged_component_material", ("data/policy_staged_material_v01.json",)),
    ("test_policy_staged_primitives", ("data/policy_implementation_v01.json",)),
    ("test_policy_staged_regimen_source", ("data/policy_staged_regimen_source_v01.json",)),
    ("test_policy_component_fragment", ("data/policy_material_request_v01.json", "data/policy_material_state_v01.json")),
    ("test_policy_component_material", ("data/policy_material_request_v01.json", "data/policy_material_state_v01.json")),
    ("test_policy_component_assembly_rule", ("data/policy_material_request_v01.json", "data/policy_material_state_v01.json")),
    ("test_policy_component_assembly_check", ("data/policy_material_request_v01.json", "data/policy_material_state_v01.json")),
    ("test_policy_component_material_request", ("data/policy_material_request_v01.json", "data/policy_material_state_v01.json")),
    ("test_policy_component_selection_request", ("data/policy_material_request_v01.json", "data/policy_material_state_v01.json")),
    ("test_policy_component_material_candidate", ("data/policy_material_request_v01.json",)),
    ("test_policy_component_selection_candidate", ('data/policy_material_request_v01.json',)),
    ("test_policy_component_selection_common", ('data/policy_material_request_v01.json', 'data/policy_material_state_v01.json')),
    ("test_policy_component_selection_check", ('data/policy_material_request_v01.json',)),
    ("test_policy_component_selection_scope", ("data/policy_material_request_v01.json",)),
    ("test_policy_component_selection_producer", ("data/policy_material_request_v01.json",)),
    ("test_policy_generation_admission", ("data/policy_implementation_binding_v01.json",)),
    ("test_policy_generation_producers", ("data/policy_material_request_v01.json", "data/policy_material_state_v01.json",)),
    ("test_policy_component_selection_service", ("data/policy_material_request_v01.json",)),
    ("test_policy_component_context_check", ("data/policy_material_request_v01.json", "data/policy_material_state_v01.json")),
    ("test_policy_component_material_service", ("data/policy_material_request_v01.json", "data/policy_material_state_v01.json")),
    ("test_protocol", ()),
    ("test_producer_protocol", ()),
    ("test_policy_implementation_binding", ("data/policy_implementation_binding_v01.json", "data/policy_realization_request_v01.json", "data/policy_exclusion_source_v01.json")),
    ("test_policy_preservation_check", ("data/policy_implementation_binding_v01.json",)),
    ("test_policy_candidate_congruence_check", ("data/policy_implementation_binding_v01.json",)),
    ("test_policy_candidate_transition_congruence", ("data/policy_primitives_v01.json",)),
    ("test_policy_material_binding", ("data/policy_material_binding_v01.json",)),
    ("test_policy_material_context", ("data/policy_material_context_v01.json",)),
    ("test_policy_material_check", ("data/policy_material_request_v01.json",)),
    ("test_policy_mrna_structure", ("data/policy_mrna_structure_v01.json",)),
    ("test_construction_content", ("data/construction_content_v01.json",)),
)
DEPENDENCIES = ["opam", "install", "core/biocompiler_core.opam", "--deps-only", "--with-test", "--yes"]
BUILD = ["opam", "exec", "--", "dune", "build", "--root", "core", "@all"]
COMMAND_TIMEOUT_SECONDS = 900
SELECTION_SDK_TIMEOUT_SECONDS = 1800
PARALLEL_WORKERS = 2
SDK_BINARIES = {
    "originals": "core/_build/default/test/component_fixture_export/main.exe",
    "instance_originals": "core/_build/default/test/instance_fixture_export/main.exe",
    "prerequisite_originals": "core/_build/default/test/prerequisite_fixture_export/main.exe",
    "two_observation_originals": "core/_build/default/test/two_observation_fixture_export/main.exe",
    "multi_member_originals": "core/_build/default/test/multi_member_fixture_export/main.exe",
    "grounded_helper_originals": "core/_build/default/test/grounded_helper_fixture_export/main.exe",
    "core": "core/_build/default/bin/core/main.exe",
    "verify": "core/_build/default/bin/verify/main.exe",
}
SDK_ORIGINALS = (
    "core/test/data/policy_material_request_v01.json", "core/test/data/policy_material_state_v01.json",
    "core/test/policy_component_support/literals.ml", "core/test/policy_component_support/requests.ml",
)
INSTANCE_ORIGINALS = (
    "core/test/data/policy_material_request_v01.json", "core/test/data/policy_material_state_v01.json",
    "core/test/policy_component_support/literals.ml",
    "core/test/policy_instance_support/literals.ml", "core/test/policy_instance_support/requests.ml",
)
PREREQUISITE_ORIGINALS = INSTANCE_ORIGINALS + (
    "core/test/policy_prerequisite_support/literals.ml", "core/test/policy_prerequisite_support/requests.ml",
)
TWO_OBSERVATION_ORIGINALS = PREREQUISITE_ORIGINALS + (
    "core/test/policy_two_observation_support/literals.ml", "core/test/policy_two_observation_support/requests.ml",
)
MULTI_MEMBER_ORIGINALS = (
    "core/test/data/policy_staged_material_v01.json",
    "core/test/policy_multi_member_support/literals.ml", "core/test/policy_multi_member_support/requests.ml",
)
GROUNDED_HELPER_ORIGINALS = MULTI_MEMBER_ORIGINALS + (
    "core/test/policy_grounded_helper_support/literals.ml", "core/test/policy_grounded_helper_support/requests.ml",
)
SELECTION_ORIGINALS = (
    "core/test/data/policy_material_request_v01.json",
    "core/test/policy_component_support/literals.ml", "core/test/policy_component_support/requests.ml",
    "core/test/policy_component_support/selection_requests.ml",
)


def require(value, message):
    if not value:
        raise ValueError(message)


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root)


def identity(root):
    env = os.environ
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("RUNNER_ENVIRONMENT") == "github-hosted",
            "Development native work requires GitHub-hosted execution")
    require(env.get("GITHUB_EVENT_NAME") == "push", "Development lane only admits push events")
    ref = env.get("GITHUB_REF", "")
    require(re.fullmatch(r"refs/heads/codex/dev-policy/[A-Za-z0-9][A-Za-z0-9._/-]*", ref) is not None,
            "Development lane requires an opt-in branch")
    require((env.get("RUNNER_OS"), env.get("RUNNER_ARCH"), platform.system(), platform.machine()) ==
            ("Linux", "X64", "Linux", "x86_64"), "Development lane requires hosted Linux x86_64")
    require(Path(env.get("GITHUB_WORKSPACE", "")).resolve() == root, "Wrong hosted workspace")
    revision = env.get("GITHUB_SHA", "")
    require(re.fullmatch(r"[0-9a-f]{40}", revision) is not None, "Invalid push revision")
    require(git(root, "rev-parse", "HEAD").decode().strip() == revision, "Stale checkout revision")
    tree = git(root, "rev-parse", "HEAD^{tree}").decode().strip()
    require(re.fullmatch(r"[0-9a-f]{40}", tree) is not None, "Invalid source tree identity")
    run_id, attempt = env.get("GITHUB_RUN_ID", ""), env.get("GITHUB_RUN_ATTEMPT", "")
    require(all(re.fullmatch(r"[1-9][0-9]{0,19}", x) for x in (run_id, attempt)), "Invalid run or attempt")
    repository = env.get("GITHUB_REPOSITORY", "")
    require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is not None, "Invalid repository")
    require(env.get("GITHUB_WORKFLOW_REF") == f"{repository}/{WORKFLOW}@{ref}"
            and env.get("GITHUB_WORKFLOW_SHA") == revision, "Wrong development workflow identity")
    return {"revision": revision, "tree": tree, "run_id": run_id, "run_attempt": attempt,
            "event": "push", "ref": ref, "repository": repository,
            "workflow_ref": env["GITHUB_WORKFLOW_REF"], "system": "Linux", "machine": "x86_64"}


def pin(root, relative, executable=False, allow_empty=False):
    path = root / relative
    require(path.is_file() and not path.is_symlink() and all(not p.is_symlink() for p in path.parents
            if p != root.parent), "Missing or unsafe input: " + relative)
    require((allow_empty or path.stat().st_size > 0) and path.stat().st_size <= 128 * 1024 * 1024,
            "Empty or oversized input: " + relative)
    if executable:
        require(os.access(path, os.X_OK), "Native executable is not executable: " + relative)
    raw = path.read_bytes()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}


def source_snapshot(root):
    """Check actual bytes against HEAD blobs, including a full source-file census."""
    rows = git(root, "ls-tree", "-r", "-z", "HEAD", "--", *SOURCE_ROOTS).split(b"\0")
    result = {}
    for row in filter(None, rows):
        header, name = row.split(b"\t", 1)
        mode, kind, blob = header.decode().split()
        relative = name.decode("utf-8")
        require(mode in {"100644", "100755"} and kind == "blob", "Unsupported tracked source kind")
        path = root / relative
        require(relative not in result and not Path(relative).is_absolute() and ".." not in Path(relative).parts,
                "Unsafe or duplicated tracked source")
        metadata = pin(root, relative, allow_empty=True)
        raw = path.read_bytes()
        actual_blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        require(actual_blob == blob and bool(path.stat().st_mode & stat.S_IXUSR) == (mode == "100755"),
                "Source differs from checked revision: " + relative)
        result[relative] = {**metadata, "sha256": hashlib.sha256(raw).hexdigest(),
                            "size": len(raw), "git_blob": blob, "mode": mode}
    require(result, "Empty tracked source census")
    present = set()
    for relative in SOURCE_ROOTS:
        base = root / relative
        if base.is_file():
            present.add(relative)
            continue
        require(base.is_dir() and not base.is_symlink(), "Missing source root: " + relative)
        for parent, directories, files in os.walk(base, followlinks=False):
            directories[:] = [name for name in directories if name != "__pycache__"
                              and Path(parent, name) != root / "core/_build"]
            require(all(not Path(parent, name).is_symlink() for name in directories), "Symlinked source directory")
            for name in files:
                path = Path(parent, name)
                present.add(path.relative_to(root).as_posix())
    require(present == set(result), "Tracked source census changed or new source files appeared")
    return result


def selected_suites(root):
    plan = {row["name"]: row for row in bundle.test_plan((root / "core/test/dune").read_text())}
    result = []
    for name, fixtures in SUITES:
        require(name in plan and plan[name].get("environment") == []
                and plan[name].get("dependencies", []) == list(fixtures), "Missing or changed registered suite: " + name)
        paths = ["core/test/" + path for path in fixtures]
        result.append({"name": name, "executable": "core/_build/default/test/" + name + ".exe",
                       "fixtures": {path: pin(root, path) for path in paths},
                       "argv": ["opam", "exec", "--", str(root / "core/_build/default/test" / (name + ".exe")),
                                *(str(root / path) for path in paths)]})
    return result


def save(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def feedback():
    return {"schema": SCHEMA, "acceptance": False,
            "scope": "Fixed focused native suites; development feedback only, no release acceptance.",
            "status": "incomplete", "actions": [], "suites": [
                {"name": name, "status": "not_run"} for name, _ in SUITES]}


def preparation(root):
    return {"schema": SCHEMA, "identity": identity(root), "sources": source_snapshot(root),
            "suites": selected_suites(root)}


def prepare(root):
    output = root / "generated/development-feedback"
    output.mkdir(parents=True, exist_ok=False)
    report = feedback()
    try:
        prepared = preparation(root)
        save(output / "preparation.json", prepared)
        report.update(status="prepared", identity=prepared["identity"])
    except Exception as error:
        report.update(status="failed", error=str(error))
        raise
    finally:
        save(output / "feedback.json", report)


def _selection_sdk_argv(root):
    output = root / "generated/development-feedback"
    return [sys.executable, "-B", str(root / "tools/check_policy_component_selection.py"),
            "--fixture", str(output / "selection-originals.json"),
            "--core", str(root / SDK_BINARIES["core"]),
            "--verify", str(root / SDK_BINARIES["verify"]),
            "--output", str(output / "selection-sdk-witness.json")]


def command(root, output, name, argv):
    # Only this exact fixed orchestration command gets the longer wall-clock
    # envelope. Its mandatory observations and native work budgets are unchanged.
    timeout = (SELECTION_SDK_TIMEOUT_SECONDS
               if name == "selection-sdk" and argv == _selection_sdk_argv(root)
               else COMMAND_TIMEOUT_SECONDS)
    start = time.monotonic()
    row = {"name": name, "argv": argv, "log": name + ".log", "status": "failed"}
    with (output / row["log"]).open("xb") as log:
        try:
            result = subprocess.run(argv, cwd=root, stdout=log, stderr=subprocess.STDOUT,
                                    timeout=timeout, check=False)
            row.update(returncode=result.returncode, status="passed" if result.returncode == 0 else "failed")
        except (OSError, subprocess.TimeoutExpired) as error:
            row["error"] = str(error)
    row["elapsed_seconds"] = time.monotonic() - start
    row["log_pin"] = {"sha256": hashlib.sha256((output / row["log"]).read_bytes()).hexdigest(),
                      "size": (output / row["log"]).stat().st_size}
    return row


def run(root):
    output = root / "generated/development-feedback"
    report = feedback()
    prepared = None
    try:
        raw = (output / "preparation.json").read_bytes()
        require(len(raw) <= 8 * 1024 * 1024, "Oversized development preparation")
        prepared = bundle.manifest_document(raw)
        require(prepared == preparation(root), "Development preparation identity or source changed")
        report["identity"] = prepared["identity"]
        report["sources_before"] = prepared["sources"]
        for name, argv in (("dependencies", DEPENDENCIES), ("build", BUILD)):
            require(preparation(root) == prepared, "Source or identity changed before native work")
            row = command(root, output, name, argv)
            report["actions"].append(row)
            save(output / "feedback.json", report)
            require(row["status"] == "passed", "Development " + name + " failed")
        suites = prepared["suites"]
        binary_paths = [row["executable"] for row in suites] + list(SDK_BINARIES.values())
        binaries = {path: pin(root, path, executable=True) for path in binary_paths}
        report["binaries"] = binaries
        def execute_suite(suite):
            require(preparation(root) == prepared, "Source or identity changed before native suite")
            require(pin(root, suite["executable"], executable=True) == binaries[suite["executable"]],
                    "Native executable changed before suite")
            row = command(root, output, suite["name"], suite["argv"])
            return {**suite, **row}

        # Each worker owns one command log. Only this coordinator writes the
        # receipt, with rows in the original order even when completion differs.
        errors = {}
        print(f"Starting {len(suites)} native suites with {PARALLEL_WORKERS} workers", flush=True)
        with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
            pending = {executor.submit(execute_suite, suite): index for index, suite in enumerate(suites)}
            for completed, future in enumerate(as_completed(pending), 1):
                index = pending[future]
                try:
                    report["suites"][index] = future.result()
                except Exception as error:
                    report["suites"][index] = {**suites[index], "status": "not_run", "error": str(error)}
                    errors[index] = error
                save(output / "feedback.json", report)
                row = report["suites"][index]
                elapsed = f"{row['elapsed_seconds']:.3f}s" if "elapsed_seconds" in row else "not launched"
                print(f"Native suite completed {completed}/{len(suites)}: {row['name']} ({row['status']}, {elapsed})", flush=True)
        if errors:
            raise errors[min(errors)]
        require(all(row["status"] == "passed" for row in report["suites"]), "Focused native suite failed")
        require({path: pin(root, path, executable=True) for path in binaries} == binaries, "Native executable changed during suites")
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=str(error))
        raise
    finally:
        try:
            after = preparation(root)
            report["sources_after"] = after["sources"]
            require(prepared == after, "Source or identity changed after native work")
        except Exception as error:
            report.update(status="failed", source_error=str(error))
        save(output / "feedback.json", report)
        require(report["status"] == "passed", report.get("source_error", report.get("error", "Incomplete development feedback")))
    return report


def validate_native_feedback(root, native, prepared):
    require(native.get("schema") == SCHEMA and native.get("acceptance") is False
            and native.get("status") == "passed" and native.get("identity") == prepared["identity"]
            and native.get("sources_before") == native.get("sources_after") == prepared["sources"],
            "SDK requires the complete successful focused native run on these sources")
    actions = native.get("actions")
    suites = native.get("suites")
    require(type(actions) is list and len(actions) == 2 and type(suites) is list
            and len(suites) == len(prepared["suites"]), "Incomplete native command census")
    expected = [{"name": "dependencies", "argv": DEPENDENCIES}, {"name": "build", "argv": BUILD}]
    expected += prepared["suites"]
    for row, original in zip(actions + suites, expected):
        name = original["name"]
        require(type(row) is dict and all(row.get(key) == value for key, value in original.items())
                and row.get("status") == "passed" and type(row.get("returncode")) is int
                and row["returncode"] == 0 and row.get("log") == name + ".log",
                "Changed native command record: " + name)
        require(row.get("log_pin") == pin(root, "generated/development-feedback/" + name + ".log", allow_empty=True),
                "Changed native command log: " + name)


def public_sdk(root, *, instance=False, prerequisites=False, two_observations=False, multi_member=False, grounded_helper=False):
    """Use the same hosted build for original declarations and the public SDK.

    The domain-only helper exports independent source fixtures. Core and Verify
    subsequently check candidates; no fixture report grants acceptance.
    """
    output = root / "generated/development-feedback"
    require(sum((instance, prerequisites, two_observations, multi_member, grounded_helper)) <= 1, "Select one SDK profile")
    original_paths = GROUNDED_HELPER_ORIGINALS if grounded_helper else MULTI_MEMBER_ORIGINALS if multi_member else TWO_OBSERVATION_ORIGINALS if two_observations else PREREQUISITE_ORIGINALS if prerequisites else INSTANCE_ORIGINALS if instance else SDK_ORIGINALS
    exporter = SDK_BINARIES["grounded_helper_originals" if grounded_helper else "multi_member_originals" if multi_member else "two_observation_originals" if two_observations else "prerequisite_originals" if prerequisites else "instance_originals" if instance else "originals"]
    packet_name = "grounded-helper-originals" if grounded_helper else "multi-member-originals" if multi_member else "two-observation-originals" if two_observations else "prerequisite-originals" if prerequisites else "instance-originals" if instance else "component-originals"
    campaign_name = "grounded-helper-sdk" if grounded_helper else "multi-member-sdk" if multi_member else "two-observation-sdk" if two_observations else "prerequisite-sdk" if prerequisites else "instance-sdk" if instance else "component-sdk"
    report_name = "grounded-helper-sdk.json" if grounded_helper else "multi-member-sdk.json" if multi_member else "two-observation-sdk.json" if two_observations else "prerequisite-sdk.json" if prerequisites else "instance-sdk.json" if instance else "public-sdk.json"
    witness_name = "grounded-helper-sdk-witness.json" if grounded_helper else "multi-member-sdk-witness.json" if multi_member else "two-observation-sdk-witness.json" if two_observations else "prerequisite-sdk-witness.json" if prerequisites else "instance-sdk-witness.json" if instance else "sdk-witness.json"
    script = "tools/check_policy_grounded_helper_material.py" if grounded_helper else "tools/check_policy_multi_member_material.py" if multi_member else "tools/check_policy_two_observation_material.py" if two_observations else "tools/check_policy_prerequisite_material.py" if prerequisites else "tools/check_policy_instance_material.py" if instance else "tools/check_policy_component_material.py"
    report = {"schema": "biocompiler.development-grounded-helper-sdk-feedback.v0.1" if grounded_helper else "biocompiler.development-multi-member-sdk-feedback.v0.1" if multi_member else "biocompiler.development-two-observation-sdk-feedback.v0.1" if two_observations else "biocompiler.development-prerequisite-sdk-feedback.v0.1" if prerequisites else "biocompiler.development-instance-sdk-feedback.v0.1" if instance else "biocompiler.development-sdk-feedback.v0.1", "acceptance": False,
              "scope": "hosted source-tree SDK feedback; installed and release acceptance remain separate",
              "status": "failed", "actions": []}
    prepared = None
    binaries = {}
    try:
        prepared = bundle.manifest_document((output / "preparation.json").read_bytes())
        require(prepared == preparation(root), "SDK source or hosted identity differs from native preparation")
        native_pin = pin(root, "generated/development-feedback/feedback.json")
        native = bundle.manifest_document((output / "feedback.json").read_bytes())
        validate_native_feedback(root, native, prepared)
        require(pin(root, "generated/development-feedback/feedback.json") == native_pin,
                "Native feedback changed during validation")
        report.update(identity=prepared["identity"], sources_before=prepared["sources"],
                      native_feedback=native_pin)
        binaries = {path: pin(root, path, executable=True) for path in SDK_BINARIES.values()}
        require(all(native["binaries"].get(path) == value for path, value in binaries.items()),
                "SDK executable differs from the completed native build")
        report["binaries"] = binaries
        fixture = output / (packet_name + ".json")
        witness = output / witness_name
        commands = (
            (packet_name, ["opam", "exec", "--", str(root / exporter),
                *(str(root / path) for path in original_paths), str(fixture)]),
            (campaign_name, [sys.executable, "-B", str(root / script),
                "--fixture", str(fixture), "--core", str(root / SDK_BINARIES["core"]),
                "--verify", str(root / SDK_BINARIES["verify"]), "--output", str(witness)]),
        )
        for name, argv in commands:
            require(preparation(root) == prepared, "SDK source or identity changed before execution")
            require({path: pin(root, path, executable=True) for path in binaries} == binaries,
                    "SDK executable changed before execution")
            row = command(root, output, name, argv)
            report["actions"].append(row)
            save(output / report_name, report)
            require(row["status"] == "passed", "Public SDK " + name + " failed")
        require(fixture.stat().st_size <= 4_000_000 and witness.stat().st_size <= 1024 * 1024,
                "SDK original or witness receipt exceeds its bound")
        report["outputs"] = {path.name: pin(root, path.relative_to(root).as_posix()) for path in (fixture, witness)}
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=str(error))
        raise
    finally:
        try:
            after = preparation(root)
            report["sources_after"] = after["sources"]
            require(prepared == after, "SDK source or identity changed after execution")
            require({path: pin(root, path, executable=True) for path in binaries} == binaries,
                    "SDK executable changed during execution")
            if "native_feedback" in report:
                require(pin(root, "generated/development-feedback/feedback.json") == report["native_feedback"],
                        "Native feedback changed during SDK execution")
                validate_native_feedback(root, bundle.manifest_document((output / "feedback.json").read_bytes()), prepared)
        except Exception as error:
            report.update(status="failed", source_error=str(error))
        save(output / report_name, report)
        require(report["status"] == "passed", report.get("source_error", report.get("error", "Incomplete SDK feedback")))
    return report


def validate_public_sdk_feedback(root, report, prepared, native_pin, binaries):
    """Keep the existing component SDK campaign a checked prerequisite."""
    require(report.get("schema") == "biocompiler.development-sdk-feedback.v0.1"
            and report.get("acceptance") is False and report.get("status") == "passed"
            and report.get("identity") == prepared["identity"]
            and report.get("sources_before") == report.get("sources_after") == prepared["sources"]
            and report.get("native_feedback") == native_pin and report.get("binaries") == binaries,
            "Selection SDK requires the unchanged successful component SDK campaign")
    output = root / "generated/development-feedback"
    fixture, witness = output / "component-originals.json", output / "sdk-witness.json"
    expected = (
        ("component-originals", ["opam", "exec", "--", str(root / SDK_BINARIES["originals"]),
            *(str(root / path) for path in SDK_ORIGINALS), str(fixture)]),
        ("component-sdk", [sys.executable, "-B", str(root / "tools/check_policy_component_material.py"),
            "--fixture", str(fixture), "--core", str(root / SDK_BINARIES["core"]),
            "--verify", str(root / SDK_BINARIES["verify"]), "--output", str(witness)]),
    )
    actions = report.get("actions")
    require(type(actions) is list and len(actions) == len(expected), "Incomplete component SDK command census")
    for row, (name, argv) in zip(actions, expected):
        require(type(row) is dict and row.get("name") == name and row.get("argv") == argv
                and row.get("status") == "passed" and type(row.get("returncode")) is int
                and row["returncode"] == 0 and row.get("log") == name + ".log"
                and row.get("log_pin") == pin(root, "generated/development-feedback/" + name + ".log", allow_empty=True),
                "Changed component SDK command or log: " + name)
    require(fixture.stat().st_size <= 4_000_000 and witness.stat().st_size <= 1024 * 1024,
            "Component SDK output exceeds its bound")
    require(report.get("outputs") == {path.name: pin(root, path.relative_to(root).as_posix())
                                     for path in (fixture, witness)}, "Changed component SDK output")


def selection_sdk(root):
    """Exercise explicit candidate preparation and independent selection APIs."""
    output = root / "generated/development-feedback"
    report = {"schema": "biocompiler.development-selection-sdk-feedback.v0.1", "acceptance": False,
              "scope": "hosted source-tree selection SDK feedback; installed and release acceptance remain separate",
              "status": "failed", "actions": []}
    prepared = None
    binaries = {}
    try:
        prepared = bundle.manifest_document((output / "preparation.json").read_bytes())
        require(prepared == preparation(root), "Selection SDK source or hosted identity differs from native preparation")
        native_pin = pin(root, "generated/development-feedback/feedback.json")
        native = bundle.manifest_document((output / "feedback.json").read_bytes())
        validate_native_feedback(root, native, prepared)
        require(pin(root, "generated/development-feedback/feedback.json") == native_pin,
                "Native feedback changed during selection validation")
        binaries = {path: pin(root, path, executable=True) for path in SDK_BINARIES.values()}
        require(all(native["binaries"].get(path) == value for path, value in binaries.items()),
                "Selection SDK executable differs from the completed native build")
        public_pin = pin(root, "generated/development-feedback/public-sdk.json")
        validate_public_sdk_feedback(root, bundle.manifest_document((output / "public-sdk.json").read_bytes()),
                                     prepared, native_pin, binaries)
        require(pin(root, "generated/development-feedback/public-sdk.json") == public_pin,
                "Component SDK feedback changed during selection validation")
        source_inputs = {path: pin(root, path) for path in SELECTION_ORIGINALS}
        require(all(prepared["sources"].get(path, {}).get("sha256") == value["sha256"]
                    and prepared["sources"][path]["size"] == value["size"]
                    for path, value in source_inputs.items()), "Selection original source pin changed")
        report.update(identity=prepared["identity"], sources_before=prepared["sources"],
                      native_feedback=native_pin, component_sdk_feedback=public_pin,
                      source_inputs=source_inputs, binaries=binaries)
        fixture, witness = output / "selection-originals.json", output / "selection-sdk-witness.json"
        commands = (
            ("selection-originals", ["opam", "exec", "--", str(root / SDK_BINARIES["originals"]),
                "--selection", *(str(root / path) for path in SELECTION_ORIGINALS), str(fixture)]),
            ("selection-sdk", _selection_sdk_argv(root)),
        )
        for name, argv in commands:
            require(preparation(root) == prepared, "Selection SDK source or identity changed before execution")
            require({path: pin(root, path, executable=True) for path in binaries} == binaries,
                    "Selection SDK executable changed before execution")
            row = command(root, output, name, argv)
            report["actions"].append(row)
            save(output / "selection-public-sdk.json", report)
            require(row["status"] == "passed", "Selection SDK " + name + " failed")
        require(fixture.stat().st_size <= 4_000_000 and witness.stat().st_size <= 1024 * 1024,
                "Selection SDK original or witness receipt exceeds its bound")
        report["outputs"] = {path.name: pin(root, path.relative_to(root).as_posix()) for path in (fixture, witness)}
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=str(error))
        raise
    finally:
        try:
            after = preparation(root)
            report["sources_after"] = after["sources"]
            require(prepared == after, "Selection SDK source or identity changed after execution")
            require({path: pin(root, path, executable=True) for path in binaries} == binaries,
                    "Selection SDK executable changed during execution")
            if "native_feedback" in report:
                require(pin(root, "generated/development-feedback/feedback.json") == report["native_feedback"],
                        "Native feedback changed during selection SDK execution")
                validate_native_feedback(root, bundle.manifest_document((output / "feedback.json").read_bytes()), prepared)
                require(pin(root, "generated/development-feedback/public-sdk.json") == report["component_sdk_feedback"],
                        "Component SDK feedback changed during selection SDK execution")
                validate_public_sdk_feedback(root, bundle.manifest_document((output / "public-sdk.json").read_bytes()),
                                             prepared, report["native_feedback"], binaries)
        except Exception as error:
            report.update(status="failed", source_error=str(error))
        save(output / "selection-public-sdk.json", report)
        require(report["status"] == "passed", report.get("source_error", report.get("error", "Incomplete selection SDK feedback")))
    return report


def staged_source_sdk(root):
    """Bind the fixed staged-source Python campaign to the same hosted build."""
    output = root / "generated/development-feedback"
    report = {"schema": "biocompiler.development-staged-source-sdk-feedback.v0.1", "acceptance": False,
              "scope": "hosted staged source DSL feedback; material, installed and release acceptance remain separate",
              "status": "failed", "actions": []}
    prepared = None
    binaries = {}
    try:
        prepared = bundle.manifest_document((output / "preparation.json").read_bytes())
        require(prepared == preparation(root), "Staged SDK sources or hosted identity changed")
        native_pin = pin(root, "generated/development-feedback/feedback.json")
        native = bundle.manifest_document((output / "feedback.json").read_bytes())
        validate_native_feedback(root, native, prepared)
        report.update(identity=prepared["identity"], sources_before=prepared["sources"], native_feedback=native_pin)
        binaries = {path: pin(root, path, executable=True) for path in SDK_BINARIES.values()}
        require(all(native["binaries"].get(path) == value for path, value in binaries.items()),
                "Staged SDK executable differs from completed native build")
        report["binaries"] = binaries
        witness = output / "staged-source-sdk-witness.json"
        argv = [sys.executable, "-B", str(root / "tools/check_policy_staged_regimen_source.py"),
                "--fixture", str(root / "core/test/data/policy_staged_regimen_source_v01.json"),
                "--core", str(root / SDK_BINARIES["core"]), "--verify", str(root / SDK_BINARIES["verify"]),
                "--output", str(witness)]
        row = command(root, output, "staged-source-sdk", argv)
        report["actions"].append(row)
        require(row["status"] == "passed", "Staged source SDK failed")
        require(witness.stat().st_size <= 1024 * 1024, "Staged source SDK receipt exceeds its bound")
        report["outputs"] = {witness.name: pin(root, witness.relative_to(root).as_posix())}
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=str(error))
        raise
    finally:
        try:
            after = preparation(root)
            report["sources_after"] = after["sources"]
            require(prepared == after, "Staged SDK source changed during execution")
            require({path: pin(root, path, executable=True) for path in binaries} == binaries,
                    "Staged SDK native executable changed during execution")
            if "native_feedback" in report:
                require(pin(root, "generated/development-feedback/feedback.json") == report["native_feedback"],
                        "Native feedback changed during staged SDK execution")
                validate_native_feedback(root, bundle.manifest_document((output / "feedback.json").read_bytes()), prepared)
        except Exception as error:
            report.update(status="failed", source_error=str(error))
        save(output / "staged-source-sdk.json", report)
        require(report["status"] == "passed", report.get("source_error", report.get("error", "Incomplete staged source SDK")))
    return report

def staged_material_sdk(root):
    """Bind the fixed staged-material Python campaign to the same hosted build."""
    output = root / "generated/development-feedback"
    report = {"schema": "biocompiler.development-staged-material-sdk-feedback.v0.1", "acceptance": False,
              "scope": "hosted staged material DSL feedback; installed and release acceptance remain separate",
              "status": "failed", "actions": []}
    prepared = None
    binaries = {}
    try:
        prepared = bundle.manifest_document((output / "preparation.json").read_bytes())
        require(prepared == preparation(root), "Staged SDK sources or hosted identity changed")
        native_pin = pin(root, "generated/development-feedback/feedback.json")
        native = bundle.manifest_document((output / "feedback.json").read_bytes())
        validate_native_feedback(root, native, prepared)
        report.update(identity=prepared["identity"], sources_before=prepared["sources"], native_feedback=native_pin)
        binaries = {path: pin(root, path, executable=True) for path in SDK_BINARIES.values()}
        require(all(native["binaries"].get(path) == value for path, value in binaries.items()),
                "Staged SDK executable differs from completed native build")
        report["binaries"] = binaries
        witness = output / "staged-material-sdk-witness.json"
        argv = [sys.executable, "-B", str(root / "tools/check_policy_staged_component_material.py"),
                "--fixture", str(root / "core/test/data/policy_staged_material_v01.json"),
                "--core", str(root / SDK_BINARIES["core"]), "--verify", str(root / SDK_BINARIES["verify"]),
                "--output", str(witness)]
        row = command(root, output, "staged-material-sdk", argv)
        report["actions"].append(row)
        require(row["status"] == "passed", "Staged material SDK failed")
        require(witness.stat().st_size <= 1024 * 1024, "Staged material SDK receipt exceeds its bound")
        report["outputs"] = {witness.name: pin(root, witness.relative_to(root).as_posix())}
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=str(error))
        raise
    finally:
        try:
            after = preparation(root)
            report["sources_after"] = after["sources"]
            require(prepared == after, "Staged SDK source changed during execution")
            require({path: pin(root, path, executable=True) for path in binaries} == binaries,
                    "Staged SDK native executable changed during execution")
            if "native_feedback" in report:
                require(pin(root, "generated/development-feedback/feedback.json") == report["native_feedback"],
                        "Native feedback changed during staged SDK execution")
                validate_native_feedback(root, bundle.manifest_document((output / "feedback.json").read_bytes()), prepared)
        except Exception as error:
            report.update(status="failed", source_error=str(error))
        save(output / "staged-material-sdk.json", report)
        require(report["status"] == "passed", report.get("source_error", report.get("error", "Incomplete staged material SDK")))
    return report


def researcher_alpha_sdk(root):
    """Run the public project example against the same authenticated native build."""
    output = root / "generated/development-feedback"
    report = {"schema": "biocompiler.development-researcher-alpha-feedback.v0.1", "acceptance": False,
              "scope": "source-tree public project workflow; installed, release and empirical acceptance remain separate",
              "status": "failed", "actions": []}
    prepared, binaries = None, {}
    try:
        prepared = bundle.manifest_document((output / "preparation.json").read_bytes())
        require(prepared == preparation(root), "Research SDK sources or hosted identity changed")
        native_pin = pin(root, "generated/development-feedback/feedback.json")
        native = bundle.manifest_document((output / "feedback.json").read_bytes())
        validate_native_feedback(root, native, prepared)
        binaries = {path: pin(root, path, executable=True) for path in SDK_BINARIES.values()}
        require(all(native["binaries"].get(path) == value for path, value in binaries.items()),
                "Research SDK executable differs from completed native build")
        report.update(identity=prepared["identity"], sources_before=prepared["sources"],
                      native_feedback=native_pin, binaries=binaries)
        witness = output / "researcher-alpha-sdk-witness.json"
        argv = [sys.executable, "-B", str(root / "tools/check_researcher_alpha.py"),
                "--expected", str(root / "data/researcher_alpha/expected.json"),
                "--core", str(root / SDK_BINARIES["core"]), "--verify", str(root / SDK_BINARIES["verify"]),
                "--output", str(witness)]
        row = command(root, output, "researcher-alpha-sdk", argv)
        report["actions"].append(row)
        require(row["status"] == "passed", "Research SDK campaign failed")
        require(witness.stat().st_size <= 1024 * 1024, "Research SDK receipt exceeds its bound")
        report["outputs"] = {witness.name: pin(root, witness.relative_to(root).as_posix())}
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=str(error))
        raise
    finally:
        try:
            after = preparation(root)
            report["sources_after"] = after["sources"]
            require(prepared == after, "Research SDK source changed during execution")
            require({path: pin(root, path, executable=True) for path in binaries} == binaries,
                    "Research SDK executable changed during execution")
            if "native_feedback" in report:
                require(pin(root, "generated/development-feedback/feedback.json") == report["native_feedback"],
                        "Native feedback changed during research SDK execution")
                validate_native_feedback(root, bundle.manifest_document((output / "feedback.json").read_bytes()), prepared)
        except Exception as error:
            report.update(status="failed", source_error=str(error))
        save(output / "researcher-alpha-sdk.json", report)
        require(report["status"] == "passed", report.get("source_error", report.get("error", "Incomplete research SDK")))
    return report


def grounded_helper_sdk(root):
    return public_sdk(root, grounded_helper=True)


def multi_member_sdk(root):
    return public_sdk(root, multi_member=True)


def two_observation_sdk(root):
    return public_sdk(root, two_observations=True)


def prerequisite_sdk(root):
    return public_sdk(root, prerequisites=True)


def instance_sdk(root):
    return public_sdk(root, instance=True)


def sdk_all(root):
    """Overlap two isolated SDK process lanes without sharing witness state.

    Selection retains its successful component receipt prerequisite. Each
    campaign still owns its existing paths and launches its guarded SDK in a
    separate process; no witness callback or native budget is parallelized.
    """
    lanes = (
        (("public-sdk", public_sdk), ("selection-sdk", selection_sdk)),
        (("instance-sdk", instance_sdk), ("prerequisite-sdk", prerequisite_sdk), ("two-observation-sdk", two_observation_sdk), ("multi-member-sdk", multi_member_sdk), ("grounded-helper-sdk", grounded_helper_sdk), ("staged-source-sdk", staged_source_sdk), ("staged-material-sdk", staged_material_sdk),
         ("researcher-alpha-sdk", researcher_alpha_sdk)),
    )

    def execute_lane(lane):
        return {name: campaign(root) for name, campaign in lane}

    reports, errors = {}, {}
    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
        pending = {executor.submit(execute_lane, lane): index for index, lane in enumerate(lanes)}
        # Drain both lanes even if one fails; completed diagnostic receipts must
        # survive, and no background campaign may outlive the final outcome.
        for future in as_completed(pending):
            index = pending[future]
            name = " -> ".join(name for name, _ in lanes[index])
            try:
                reports[index] = future.result()
                print(f"SDK lane completed: {name} (passed)", flush=True)
            except Exception as error:
                errors[index] = lanes[index][0][0] + ": " + str(error)
                print(f"SDK lane completed: {name} (failed: {error})", flush=True)
    require(not errors, "Development SDK lanes failed: " + "; ".join(errors[index] for index in sorted(errors)))
    return {name: report for index in range(len(lanes)) for name, report in reports[index].items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "run", "public-sdk", "selection-sdk", "staged-source-sdk", "staged-material-sdk", "researcher-alpha-sdk", "instance-sdk", "prerequisite-sdk", "two-observation-sdk", "multi-member-sdk", "grounded-helper-sdk", "sdk-all"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        {"prepare": prepare, "run": run, "public-sdk": public_sdk, "selection-sdk": selection_sdk, "staged-source-sdk": staged_source_sdk, "staged-material-sdk": staged_material_sdk, "researcher-alpha-sdk": researcher_alpha_sdk, "instance-sdk": instance_sdk, "prerequisite-sdk": prerequisite_sdk, "two-observation-sdk": two_observation_sdk, "multi-member-sdk": multi_member_sdk, "grounded-helper-sdk": grounded_helper_sdk, "sdk-all": sdk_all}[args.command](root)
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
