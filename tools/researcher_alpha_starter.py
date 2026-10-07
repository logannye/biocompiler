"""Assemble a reviewable starter directory after the hosted four-slot gate.

This copies already validated wheels; it never builds or executes them. The
manifest deliberately retains candidate scope. Final CI and actual-main
acceptance remain separate and cannot be inferred from this handoff artifact.
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
    "examples/researcher_alpha.py",
    "docs/researcher-alpha-quickstart.md",
    "docs/researcher-alpha-reference-qualification.md",
    "docs/researcher-alpha-review.md",
    "docs/researcher-alpha-roadmap.md",
    *("data/researcher_alpha/" + name for name in (
        "staged-input.json", "comparison-input.json", "expected.json", "provenance.json",
        "qualification.json", "negative-controls.json")),
)
MAX_FILE = 128 * 1024 * 1024
MAX_TOTAL = 300 * 1024 * 1024


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= MAX_FILE,
            "Missing, redirected or oversized starter input: " + str(path))
    with path.open("rb") as stream:
        raw = stream.read(MAX_FILE + 1)
    require(0 < len(raw) <= MAX_FILE, "Starter input changed its byte bound")
    return raw


def pin(raw):
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}


def plan(args, comparison, natives, *, root=ROOT):
    """Pure bounded copy plan; callers supply results of the complete gate."""
    require(comparison["schema_version"] == "biocompiler.policy_material_prebuilt_campaign.v0.4"
            and comparison["status"] == "pass" and comparison["researcher_project"]["status"] == "pass",
            "Starter requires the complete researcher installed comparison")
    require(set(natives) == {"linux-x86_64", "macos-arm64"}, "Starter requires both validated native platforms")
    expected_slots = {(system, machine, minor) for system, machine in (("Linux", "x86_64"), ("Darwin", "arm64"))
                      for minor in ("3.11", "3.14")}
    require(len(comparison["slots"]) == 4 and {tuple(row["slot"]) for row in comparison["slots"]} == expected_slots,
            "Starter requires every distinct installed runtime slot")
    candidate = json.loads(read(args.release_candidate))
    require(candidate["sdk"] == pin(read(args.sdk)) and candidate["source_revision"] == comparison["head_revision"]
            and candidate["tested_revision"] == comparison["revision"] and candidate["run_id"] == comparison["run_id"],
            "Starter candidate changed its independently checked SDK or source/run identity")
    files = {name: root / name for name in SOURCE_FILES}
    files.update({"wheels/" + args.sdk.name: args.sdk, "evidence/candidate.json": args.release_candidate,
                  "evidence/prebuilt-comparison.json": args.output_dir / "prebuilt-comparison.json"})
    require(json.loads(read(files["evidence/prebuilt-comparison.json"])) == comparison, "Saved comparison differs from the current gate")
    for target, native in sorted(natives.items()):
        wheel = native["native"]
        require(candidate["platforms"][target] == {"name": wheel.name, **pin(read(wheel))}, "Native starter wheel changed after checking")
        files["wheels/" + wheel.name] = wheel
    # The four-slot comparator already checks reproducibility. Retain a complete
    # paired example from its first supplied slot, with the current child pins.
    require(len(args.compare) == 4, "Starter requires four supplied installed receipts")
    evidence = args.compare[0] / "evidence"
    child_raw = read(evidence / "researcher-alpha.json")
    child = json.loads(child_raw)
    require(child["status"] == "pass" and all(child[key] == comparison[key] for key in
            ("revision", "head_revision", "run_id")), "Example receipt changed its tested identity")
    child_slot = [child["system"], child["machine"], ".".join(child["python_version"].split(".")[:2])]
    attempts = [row for row in comparison["researcher_project"]["attempts"] if row["slot"] == child_slot]
    measured_child = pin(child_raw)
    require(len(attempts) == 1 and attempts[0]["run_attempt"] == child["run_attempt"]
            and attempts[0]["receipt"] == {"sha256": measured_child["sha256"], "bytes": measured_child["size"]},
            "Example receipt changed after the independent installed comparison")
    files["evidence/researcher-alpha.json"] = evidence / "researcher-alpha.json"
    for name in ("staged-project.json", "comparison-project.json", "staged.zip", "comparison.zip"):
        relative = "researcher-alpha/" + name
        source = evidence / relative
        measured = pin(read(source))
        require(child["files"][relative] == {"sha256": measured["sha256"], "bytes": measured["size"]},
                "Verified example changed after checking")
        files["verified-examples/" + name] = source
    require(len(files) == len(SOURCE_FILES) + 10, "Starter file census differs")
    metadata = {name: pin(read(path)) for name, path in sorted(files.items())}
    require(sum(row["size"] for row in metadata.values()) <= MAX_TOTAL, "Starter exceeds its total byte bound")
    manifest = {"schema_version": "biocompiler.researcher_alpha_starter.v0.1",
        "status": "installed_candidate", "release_acceptance": "pending_overall_and_actual_main_gates",
        "empirical": "unassessed", "real_researcher_project": "unqualified",
        "source_revision": comparison["head_revision"], "tested_revision": comparison["revision"],
        "run_id": comparison["run_id"], "run_attempt": comparison["run_attempt"],
        "slots": [list(slot) for slot in sorted(expected_slots)], "files": metadata,
        "entrypoint": "docs/researcher-alpha-quickstart.md",
        "review": "docs/researcher-alpha-review.md"}
    return files, manifest


def source_authority(root, revision):
    """Bind distributed documentation and example bytes to the tested Git tree."""
    require(type(revision) is str and re.fullmatch(r"[0-9a-f]{40}", revision), "Invalid starter source revision")
    rows = subprocess.check_output(["git", "ls-tree", "-r", "-z", revision, "--", *SOURCE_FILES], cwd=root)
    result = {}
    for row in filter(None, rows.split(b"\0")):
        header, encoded_name = row.split(b"\t", 1)
        mode, kind, blob = header.decode().split()
        name = encoded_name.decode("utf-8")
        require(name in SOURCE_FILES and name not in result and mode in {"100644", "100755"} and kind == "blob",
                "Unexpected starter source tree entry")
        raw = read(root / name)
        require(hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == blob,
                "Starter source differs from the tested revision")
        result[name] = pin(raw)
    require(set(result) == set(SOURCE_FILES), "Incomplete starter source tree")
    return result


def create_starter(args, comparison, natives):
    require(os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted",
            "Native wheel handoff assembly is hosted-only")
    require(os.environ.get("GITHUB_RUN_ID") == comparison["run_id"]
            and os.environ.get("GITHUB_RUN_ATTEMPT") == comparison["run_attempt"], "Starter is not from the current hosted attempt")
    sources = source_authority(ROOT, comparison["revision"])
    files, manifest = plan(args, comparison, natives)
    require(all(manifest["files"][name] == value for name, value in sources.items()),
            "Starter sources changed during planning")
    target = args.output_dir / "researcher-starter"
    require(not target.exists() and not target.is_symlink(), "Starter destination must be new")
    with tempfile.TemporaryDirectory(prefix=".researcher-starter-", dir=args.output_dir) as temporary:
        staged = Path(temporary) / "researcher-starter"
        staged.mkdir()
        for name, source in files.items():
            raw = read(source)
            require(pin(raw) == manifest["files"][name], "Starter input changed during copying")
            destination = staged / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
            require(pin(read(destination)) == manifest["files"][name], "Starter output differs from supplied bytes")
        (staged / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
        require(all(pin(read(source)) == manifest["files"][name] for name, source in files.items()),
                "Starter input changed during publication")
        staged.rename(target)
    return manifest
