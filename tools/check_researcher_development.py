"""Opt-in hosted researcher feedback: 31 native suites and 30 SDK observations.

This reuses the complete native build/suite runner and researcher witness. It
never substitutes for the full 140-observation development campaign, installed
validation or release acceptance. No native process runs on import.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import platform
import sys

try:
    from . import check_policy_development as dev
    from . import check_researcher_alpha as researcher
except ImportError:
    import check_policy_development as dev
    import check_researcher_alpha as researcher

SCHEMA = "biocompiler.researcher_development_feedback.v0.1"
WORKFLOW = ".github/workflows/researcher-development.yml"
OUTPUT = "generated/development-feedback"
SEAL = "researcher-feedback.json"
FOLDER = "researcher-alpha-sdk-witness"
MAX_FILE = 16 * 1024 * 1024
MAX_TOTAL = 96 * 1024 * 1024
SCOPE = {"native_suites": 31, "researcher_observations": 30, "researcher_evidence_files": 40,
         "files_before_seal": 78, "files_with_seal": 79,
         "complete_development_sdk_observations": "not_run",
         "installed_validation": "not_run", "release_acceptance": False}
require = dev.require


def exact(left, right):
    return json.dumps(left, sort_keys=True, separators=(",", ":"), allow_nan=False) == json.dumps(
        right, sort_keys=True, separators=(",", ":"), allow_nan=False)


def identity(root):
    require(dev.workflow_route() == WORKFLOW, "Researcher feedback requires its own workflow/ref pair")
    return dev.identity(root)


def evidence_names():
    require(len(dev.SUITES) == 31 and len(researcher.OBSERVATIONS) == 30
            and researcher.PROJECT_IDS == ("staged", "comparison", "authored")
            and researcher.CASE_IDS == ("staged", "comparison"), "Unreviewed researcher feedback census")
    peers = tuple(name + ".json" for name in researcher.OBSERVATIONS)
    peers += tuple(case + suffix for case in researcher.PROJECT_IDS for suffix in ("-project.json", ".zip"))
    peers += tuple(case + "-changed-" + kind + ".zip" for case in researcher.CASE_IDS for kind in ("candidate", "fasta"))
    names = ("preparation.json", "feedback.json", "dependencies.log", "build.log",
             "researcher-alpha-sdk.json", "researcher-alpha-sdk.log", "researcher-alpha-sdk-witness.json")
    names += tuple(name + ".log" for name, _ in dev.SUITES)
    names += tuple(FOLDER + "/" + name for name in peers)
    require(len(peers) == len(set(peers)) == 40 and len(names) == len(set(names)) == 78,
            "Incomplete scoped file census")
    return tuple(sorted(names))


def read(root, name, *, maximum=MAX_FILE, empty=False):
    path = root / name
    require(path.is_file() and all(not parent.is_symlink() for parent in (path, *path.parents))
            and (empty or path.stat().st_size > 0) and path.stat().st_size <= maximum,
            "Missing, redirected or oversized scoped evidence: " + name)
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    require((empty or raw) and len(raw) <= maximum, "Scoped evidence byte bound changed: " + name)
    return raw


def pin(raw):
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}


def inventory(output):
    names = evidence_names()
    require(output.is_dir() and not output.is_symlink(), "Missing or redirected scoped output")
    expected_top = {name for name in names if "/" not in name} | {FOLDER}
    require({path.name for path in output.iterdir()} == expected_top, "Missing, extra or stale scoped output")
    folder = output / FOLDER
    require(folder.is_dir() and not folder.is_symlink(), "Missing or redirected researcher evidence folder")
    require({FOLDER + "/" + path.name for path in folder.iterdir()} == {name for name in names if "/" in name},
            "Missing or extra researcher evidence")
    result, total = {}, 0
    for name in names:
        raw = read(output, name, empty=name.endswith(".log"))
        total += len(raw)
        require(total <= MAX_TOTAL, "Scoped evidence exceeds aggregate byte bound")
        result[name] = pin(raw)
    return result


def document(output, name, maximum=8 * 1024 * 1024):
    return dev.bundle.manifest_document(read(output, name, maximum=maximum))


def validate_researcher(root, output, witness, prepared, binaries):
    """Recheck retained native-result structure and exact projects/pairs, inertly."""
    from biocompiler.core_client import encode_json
    try:
        from .check_researcher_alpha_installed import check_mutant
    except ImportError:
        from check_researcher_alpha_installed import check_mutant
    source_identity = {key: prepared["identity"][key] for key in ("revision", "run_id", "run_attempt")}
    source_identity["head_revision"] = source_identity["revision"]
    require(witness.get("schema_version") == researcher.SCHEMA and witness.get("status") == "passed"
            and witness.get("acceptance") is False and exact(witness.get("identity"), prepared["identity"])
            and exact(witness.get("source_identity"), source_identity)
            and witness.get("python") == platform.python_version()
            and witness.get("python_semantic_authority") == "forbidden"
            and witness.get("source_snapshot_sha256") == researcher.canonical_digest(prepared["sources"]),
            "Incomplete or stale researcher witness")
    require(exact(witness.get("inputs"), researcher.tracked_inputs(root))
            and exact(witness.get("binary_sha256"), {role: binaries[path] for role, path in researcher.NATIVE_PATHS.items()}),
            "Researcher input or native authority changed")
    rows = witness.get("observations")
    require(type(rows) is list and [row.get("name") for row in rows] == list(researcher.OBSERVATIONS),
            "Missing, duplicate or reordered researcher observations")
    observations = {}
    for row in rows:
        name = row["name"]; path = FOLDER + "/" + name + ".json"
        raw = read(output, path)
        require(exact(row, {"name": name, "path": path, "sha256": pin(raw)["sha256"], "bytes": len(raw)}),
                "Researcher observation bytes or path changed")
        observations[name] = dev.bundle.manifest_document(raw)
    packet = researcher.checked_assets(root, root / researcher.EXPECTED)
    researcher.check_observations(observations, packet)
    require(type(witness.get("projects")) is dict and set(witness["projects"]) == set(researcher.PROJECT_IDS)
            and type(witness.get("publications")) is list and len(witness["publications"]) == 3,
            "Missing researcher projects or publications")
    cases = {case["id"]: case for case in packet["expected"]["cases"]}
    for index, case in enumerate(researcher.PROJECT_IDS):
        expected = (researcher.expected_authored_project(packet) if case == "authored"
                    else researcher.expected_project(cases[case], packet))
        original = {key: expected[key] for key in ("request", "limits")}
        path = case + "-project.json"; raw = read(output, FOLDER + "/" + path)
        require(raw == encode_json(expected) and exact(witness["projects"][case], {
            "path": path, "sha256": pin(raw)["sha256"], "project_sha256": researcher.canonical_digest(expected),
            "originals_sha256": researcher.canonical_digest(original)}), "Researcher project original authority differs")
        changed = deepcopy(expected)
        changed["request"]["implementation_request"]["document"]["program"]["source_map"][0]["file"] += ".changed"
        require(observations[case + "-changed-originals"]["changed_project_sha256"] == researcher.canonical_digest(changed),
                "Researcher original mutation differs")
        publication = observations[case + "-paired-publication"]
        require(exact(witness["publications"][index], publication), "Researcher publication differs")
        researcher.archive_receipt(observations[case + "-export-verify"], output / FOLDER / (case + ".zip"))
        if case in researcher.CASE_IDS:
            for kind in ("candidate", "fasta"):
                path = output / FOLDER / (case + "-changed-" + kind + ".zip")
                require(pin(read(output, str(path.relative_to(output))))["sha256"]
                        == observations[case + "-changed-" + kind]["bundle_sha256"], "Researcher mutant bytes changed")
                check_mutant(path, observations[case + "-export-verify"], kind)
    return {"observations": list(observations), "input_pins": witness["inputs"],
            "projects": witness["projects"], "publications": witness["publications"]}


def seal(root):
    output = root / OUTPUT
    hosted = identity(root)
    pins = inventory(output)
    prepared = document(output, "preparation.json")
    require(exact(prepared, dev.preparation(root)) and exact(prepared["identity"], hosted), "Scoped preparation changed")
    native = document(output, "feedback.json")
    dev.validate_native_feedback(root, native, prepared)
    require(exact(native["identity"], hosted) and exact(native["sources_before"], prepared["sources"])
            and exact(native["sources_after"], prepared["sources"]), "Native source or identity types changed")
    expected_commands = [{"name": "dependencies", "argv": dev.DEPENDENCIES}, {"name": "build", "argv": dev.BUILD}]
    expected_commands += prepared["suites"]
    for row, original in zip(native["actions"] + native["suites"], expected_commands):
        require(exact({key: row[key] for key in original}, original)
                and exact(row["log_pin"], pins[original["name"] + ".log"]), "Native command or log pin types changed")
    expected_binaries = [row["executable"] for row in prepared["suites"]] + list(dev.SDK_BINARIES.values())
    binaries = {path: dev.pin(root, path, executable=True) for path in expected_binaries}
    require(exact(native.get("binaries"), binaries) and len(binaries) == 34, "Native binary census or identity changed")
    driver = document(output, "researcher-alpha-sdk.json")
    require(driver.get("schema") == "biocompiler.development-researcher-alpha-feedback.v0.2"
            and driver.get("acceptance") is False and driver.get("status") == "passed"
            and exact(driver.get("identity"), hosted) and exact(driver.get("sources_before"), prepared["sources"])
            and exact(driver.get("sources_after"), prepared["sources"])
            and exact(driver.get("native_feedback"), pins["feedback.json"])
            and exact(driver.get("binaries"), {path: binaries[path] for path in dev.SDK_BINARIES.values()})
            and exact(driver.get("outputs"), {"researcher-alpha-sdk-witness.json": pins["researcher-alpha-sdk-witness.json"]}),
            "Researcher driver lost its complete current authority")
    argv = [sys.executable, "-B", str(root / "tools/check_researcher_alpha.py"),
            "--expected", str(root / researcher.EXPECTED), "--core", str(root / dev.SDK_BINARIES["core"]),
            "--verify", str(root / dev.SDK_BINARIES["verify"]), "--output", str(output / "researcher-alpha-sdk-witness.json")]
    rows = driver.get("actions")
    require(type(rows) is list and len(rows) == 1 and rows[0].get("name") == "researcher-alpha-sdk"
            and exact(rows[0].get("argv"), argv) and rows[0].get("status") == "passed"
            and type(rows[0].get("returncode")) is int and rows[0]["returncode"] == 0
            and rows[0].get("log") == "researcher-alpha-sdk.log"
            and exact(rows[0].get("log_pin"), pins["researcher-alpha-sdk.log"]), "Researcher command or diagnostic log changed")
    witness = document(output, "researcher-alpha-sdk-witness.json", 1024 * 1024)
    retained = validate_researcher(root, output, witness, prepared, binaries)
    require(exact(identity(root), hosted) and exact(dev.preparation(root), prepared)
            and exact({path: dev.pin(root, path, executable=True) for path in binaries}, binaries)
            and exact(inventory(output), pins), "Scoped authority changed during sealing")
    result = {"schema": SCHEMA, "status": "passed", "acceptance": False, "scope": dict(SCOPE),
              "identity": hosted, "source_snapshot_sha256": researcher.canonical_digest(prepared["sources"]),
              "binaries": binaries, "files": pins, "researcher": retained,
              "empirical": "unassessed", "real_researcher_project_qualified": False}
    raw = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    require(len(raw) <= 1024 * 1024 and sum(row["size"] for row in pins.values()) + len(raw) <= MAX_TOTAL,
            "Scoped seal exceeds publication byte bounds")
    with (output / SEAL).open("xb") as stream:
        stream.write(raw)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("prepare", "run", "sdk"))
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    identity(root)  # Reject the wrong route before a delegate or native process.
    if args.stage == "prepare":
        return dev.prepare(root)
    if args.stage == "run":
        return dev.run(root)
    dev.researcher_alpha_sdk(root)
    return seal(root)


if __name__ == "__main__":
    main()
