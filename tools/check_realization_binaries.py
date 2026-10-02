"""Verify downloaded same-revision native inputs before hosted conformance.

This checker reads bytes and metadata; it never builds or executes a binary.
The optional prepare step only restores executable bits lost by artifact upload.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re


PLATFORMS = {"linux-x86_64": ("Linux", "x86_64"), "macos-arm64": ("Darwin", "arm64")}
BINARIES = ("biocompiler-core", "biocompiler-verify")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def file_hash(path, maximum):
    require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= maximum,
            "Missing, symlinked, empty or oversized native input: " + str(path))
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def verify(directory, revision, target):
    require(type(revision) is str and re.fullmatch(r"[0-9a-f]{40}", revision), "Invalid expected revision")
    require(target in PLATFORMS, "Unknown native platform")
    directory = Path(directory)
    path = directory / "binaries.json"
    manifest_hash = file_hash(path, 64 * 1024)

    def unique(pairs):
        fields = {}
        for key, value in pairs:
            require(key not in fields, "Duplicate native manifest field")
            fields[key] = value
        return fields

    def nonfinite(_value):
        raise ValueError("Nonfinite native manifest value")

    manifest = json.loads(path.read_bytes(), object_pairs_hook=unique, parse_constant=nonfinite)
    require(type(manifest) is dict and set(manifest) == {"revision", "system", "machine", "sha256"},
            "Incomplete native binary manifest")
    require(manifest["revision"] == revision and
            (manifest["system"], manifest["machine"]) == PLATFORMS[target],
            "Stale revision or incorrect native platform")
    pins = manifest["sha256"]
    require(type(pins) is dict and set(pins) == set(BINARIES) and
            all(type(pin) is str and re.fullmatch(r"[0-9a-f]{64}", pin) for pin in pins.values()),
            "Incomplete native executable identities")
    for name in BINARIES:
        require(file_hash(directory / name, 256 * 1024 * 1024) == pins[name],
                "Native executable bytes differ from the pinned manifest: " + name)
    return {"schema_version": "biocompiler.native_conformance_inputs.v1", "status": "pass",
            "revision": revision, "native_platform": target, "manifest_sha256": manifest_hash,
            "system": manifest["system"], "machine": manifest["machine"], "sha256": dict(pins)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--revision", default=os.environ.get("GITHUB_SHA"))
    parser.add_argument("--platform", required=True, choices=tuple(PLATFORMS))
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    receipt = verify(args.root, args.revision, args.platform)
    require((platform.system(), platform.machine()) == PLATFORMS[args.platform],
            "Conformance runner differs from downloaded executable platform")
    if args.prepare:
        for name in BINARIES:
            path = args.root / name
            path.chmod(path.stat().st_mode | 0o111)
    receipt.update(run_id=os.environ.get("GITHUB_RUN_ID", "local"),
                   source_revision=os.environ.get("GITHUB_HEAD_SHA", args.revision),
                   python_version=platform.python_version())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("Verified both exact-revision native executables for", args.platform)


if __name__ == "__main__":
    main()
