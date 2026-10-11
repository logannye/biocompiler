"""Copy a distinct nominal CAR starter only after its complete installed gate.

This helper reads validated assets as bounded data. It neither builds nor runs
wheels, and its publication remains a candidate until final release gates pass.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = (
    "examples/car_payload.py",
    "docs/car-payload-quickstart.md",
    "docs/car-rm61461-qualification.md",
    "docs/car-public-reference-qualification-2026-10-11.md",
    "docs/car-first-research-task.md",
    "docs/car-expression-material-profile-design.md",
    "data/car_payload/expected.json",
    "src/biocompiler/policy/data/car_rm61461_reference_v01.json",
)
# Accepted pairs and deliberately rejected controls have distinct destinations.
PUBLICATIONS = {
    "base-project.json": "accepted-examples/base-project.json",
    "base.zip": "accepted-examples/base.zip",
    "tight-project.json": "accepted-examples/tight-project.json",
    "tight.zip": "accepted-examples/tight.zip",
    "short-project.json": "rejected-controls/short-project.json",
    "base-changed-candidate.zip": "rejected-controls/base-changed-candidate.zip",
    "base-changed-fasta.zip": "rejected-controls/base-changed-fasta.zip",
}
MAX_FILE = 128 * 1024 * 1024
MAX_TOTAL = 300 * 1024 * 1024
SLOTS = {(system, machine, minor) for system, machine in (("Linux", "x86_64"), ("Darwin", "arm64"))
         for minor in ("3.11", "3.14")}
PREBUILT_SCHEMA = "biocompiler.policy_material_prebuilt_campaign.v0.5"
PREBUILT_CLAIM = "supplied_prebuilt_material_component_staged_researcher_and_car_payload_profiles_only"


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= MAX_FILE,
            "Missing, redirected or oversized CAR starter input: " + str(path))
    with path.open("rb") as stream:
        raw = stream.read(MAX_FILE + 1)
    require(0 < len(raw) <= MAX_FILE, "CAR starter input changed its byte bound")
    return raw


def pin(raw):
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}


def plan(args, comparison, natives, *, root=ROOT):
    """Pure data copy plan; callers first perform the complete independent gate."""
    require(comparison["schema_version"] == PREBUILT_SCHEMA and comparison["status"] == "pass"
            and comparison["claim"] == PREBUILT_CLAIM and comparison["car_payload"]["status"] == "pass"
            and all(comparison[name]["status"] == "pass" for name in (
                "material", "consumer", "component_material", "component_consumer", "staged_material", "researcher_project")),
            "CAR starter requires the complete additive installed comparison")
    require(set(natives) == {"linux-x86_64", "macos-arm64"}, "CAR starter requires both validated native platforms")
    require(len(comparison["slots"]) == 4 and {tuple(row["slot"]) for row in comparison["slots"]} == SLOTS,
            "CAR starter requires every distinct installed runtime slot")
    candidate = json.loads(read(args.release_candidate))
    require(candidate["sdk"] == pin(read(args.sdk)) and candidate["source_revision"] == comparison["head_revision"]
            and candidate["tested_revision"] == comparison["revision"] and candidate["run_id"] == comparison["run_id"],
            "CAR starter candidate changed its checked SDK or source/run identity")
    files = {name: root / name for name in SOURCE_FILES}
    files.update({"wheels/" + args.sdk.name: args.sdk, "evidence/candidate.json": args.release_candidate,
                  "evidence/prebuilt-comparison.json": args.output_dir / "prebuilt-comparison.json"})
    saved = json.loads(read(files["evidence/prebuilt-comparison.json"]))
    require(json.dumps(saved, sort_keys=True, allow_nan=False) == json.dumps(comparison, sort_keys=True, allow_nan=False),
            "Saved CAR parent comparison differs from the current gate")
    for target, native in sorted(natives.items()):
        wheel = native["native"]
        require(candidate["platforms"][target] == {"name": wheel.name, **pin(read(wheel))},
                "CAR starter native wheel changed after checking")
        files["wheels/" + wheel.name] = wheel
    require(len(args.compare) == 4, "CAR starter requires four supplied installed receipts")
    evidence = args.compare[0] / "evidence"
    child_raw = read(evidence / "car-payload.json")
    child = json.loads(child_raw)
    require(child["status"] == "pass" and all(child[key] == comparison[key] for key in ("revision", "head_revision", "run_id"))
            and child["empirical"] == "unassessed" and child["human_use"] == "unassessed"
            and child["real_researcher_project_qualified"] is False,
            "CAR example receipt changed its tested identity or evidence scope")
    child_slot = [child["system"], child["machine"], ".".join(child["python_version"].split(".")[:2])]
    attempts = [row for row in comparison["car_payload"]["attempts"] if row["slot"] == child_slot]
    measured_child = pin(child_raw)
    require(len(attempts) == 1 and attempts[0]["run_attempt"] == child["run_attempt"]
            and attempts[0]["receipt"] == {"sha256": measured_child["sha256"], "bytes": measured_child["size"]},
            "CAR child receipt changed after the independent installed comparison")
    files["evidence/car-payload.json"] = evidence / "car-payload.json"
    for name, destination in PUBLICATIONS.items():
        relative = "car-payload/" + name
        source = evidence / relative
        measured = pin(read(source))
        require(child["files"][relative] == {"sha256": measured["sha256"], "bytes": measured["size"]},
                "CAR publication changed after checking")
        files[destination] = source
    require(len(files) == len(SOURCE_FILES) + len(PUBLICATIONS) + 6, "CAR starter file census differs")
    metadata = {name: pin(read(path)) for name, path in sorted(files.items())}
    require(sum(row["size"] for row in metadata.values()) <= MAX_TOTAL, "CAR starter exceeds its total byte bound")
    manifest = {"schema_version": "biocompiler.car_payload_starter.v0.1", "status": "installed_candidate",
        "release_acceptance": "pending_overall_and_actual_main_gates", "parent_comparison_schema": PREBUILT_SCHEMA,
        "source_revision": comparison["head_revision"], "tested_revision": comparison["revision"],
        "run_id": comparison["run_id"], "run_attempt": comparison["run_attempt"],
        "example_producer_attempt": child["run_attempt"], "slots": [list(slot) for slot in sorted(SLOTS)],
        "content_scope": "conditional_nominal_car_material_and_explicit_rejected_controls",
        "empirical": "unassessed", "human_use": "unassessed", "real_researcher_project": "unqualified",
        "source_reference": "public_rm61461_nominal_reference", "redistribution_or_manufacturing_rights": "not_granted",
        "terminal_chemistry": "explicit_designer_supplied_hydroxyl_not_a_published_physical_batch_fact",
        "files": metadata, "entrypoint": "docs/car-payload-quickstart.md", "qualification": "docs/car-rm61461-qualification.md"}
    return files, manifest


def source_authority(root, revision):
    """Require distributed source bytes to be exactly the hosted tested Git tree."""
    require(type(revision) is str and re.fullmatch(r"[0-9a-f]{40}", revision), "Invalid CAR starter source revision")
    rows = subprocess.check_output(["git", "ls-tree", "-r", "-z", revision, "--", *SOURCE_FILES], cwd=root)
    result = {}
    for row in filter(None, rows.split(b"\0")):
        header, encoded_name = row.split(b"\t", 1)
        mode, kind, blob = header.decode().split()
        name = encoded_name.decode("utf-8")
        require(name in SOURCE_FILES and name not in result and mode in {"100644", "100755"} and kind == "blob",
                "Unexpected CAR starter source tree entry")
        raw = read(root / name)
        require(hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == blob,
                "CAR starter source differs from the tested revision")
        result[name] = pin(raw)
    require(set(result) == set(SOURCE_FILES), "Incomplete CAR starter source tree")
    return result


def create_starter(args, comparison, natives):
    require(os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted",
            "CAR native wheel handoff assembly is hosted-only")
    require(os.environ.get("GITHUB_RUN_ID") == comparison["run_id"]
            and os.environ.get("GITHUB_RUN_ATTEMPT") == comparison["run_attempt"], "CAR starter is not from the current hosted attempt")
    sources = source_authority(ROOT, comparison["revision"])
    files, manifest = plan(args, comparison, natives)
    require(all(manifest["files"][name] == value for name, value in sources.items()), "CAR starter sources changed during planning")
    target = args.output_dir / "car-starter"
    require(not target.exists() and not target.is_symlink(), "CAR starter destination must be new")
    with tempfile.TemporaryDirectory(prefix=".car-starter-", dir=args.output_dir) as temporary:
        staged = Path(temporary) / "car-starter"
        staged.mkdir()
        for name, source in files.items():
            raw = read(source)
            require(pin(raw) == manifest["files"][name], "CAR starter input changed during copying")
            destination = staged / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
            require(pin(read(destination)) == manifest["files"][name], "CAR starter output differs from supplied bytes")
        (staged / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
        require(all(pin(read(source)) == manifest["files"][name] for name, source in files.items()),
                "CAR starter input changed during publication")
        staged.rename(target)
    return manifest
