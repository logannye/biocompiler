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


def executable_path(directory, role):
    require(role in ('core', 'verify'), 'Unknown native executable role')
    layout = os.environ.get('BIOCOMPILER_NATIVE_INPUT_LAYOUT', 'artifact')
    require(layout in ('artifact', 'installed'), 'Unknown explicit native input layout')
    if layout == 'installed':
        from biocompiler.core_distribution import installed_distribution
        selected = installed_distribution()
        require(Path(directory) == selected.package_root, 'Installed role root differs from owned package')
        return selected.executable(role)
    return Path(directory) / ('biocompiler-' + role)


def verify(directory, revision, target):
    layout = os.environ.get('BIOCOMPILER_NATIVE_INPUT_LAYOUT', 'artifact')
    require(layout in ('artifact', 'installed'), 'Unknown explicit native input layout')
    if layout == 'installed':
        return verify_installed(directory, revision, target,
            source_revision=os.environ.get('GITHUB_HEAD_SHA'), run_id=os.environ.get('GITHUB_RUN_ID'),
            core=executable_path(directory, 'core'), verify_binary=executable_path(directory, 'verify'))['native']
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
        require(os.environ.get('BIOCOMPILER_NATIVE_INPUT_LAYOUT', 'artifact') == 'artifact', 'Installed executables must never be repaired')
        for name in BINARIES:
            path = args.root / name
            path.chmod(path.stat().st_mode | 0o111)
    receipt.update(run_id=os.environ.get("GITHUB_RUN_ID", "local"),
                   source_revision=os.environ.get("GITHUB_HEAD_SHA", args.revision),
                   python_version=platform.python_version())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("Verified both exact-revision native executables for", args.platform)


def verify_installed(directory, revision, target, *, source_revision, run_id, core, verify_binary):
    """Explicit installed-layout evidence; no executable copy, chmod or process."""
    from biocompiler.core_distribution import installed_distribution
    selected = installed_distribution()
    ownership = selected.ownership()
    require(ownership['tested_revision'] == revision and ownership['native_platform'] == target
        and ownership['source_revision'] == source_revision and ownership['run_id'] == run_id,
        'Installed source/tested/run/platform authority differs')
    root = Path(directory)
    require(root.is_absolute() and root == selected.package_root,
        'Installed campaign root is not the actual owned package')
    for role, supplied in (('core', core), ('verify', verify_binary)):
        path = Path(supplied)
        require(path.is_absolute() and path == selected.executable(role),
            'Installed campaign executable is not its exact owned path')
    manifest = json.loads(selected.binaries_bytes)
    native = {'schema_version': 'biocompiler.native_conformance_inputs.v1', 'status': 'pass',
        'revision': revision, 'native_platform': target,
        'manifest_sha256': hashlib.sha256(selected.binaries_bytes).hexdigest(),
        'system': manifest['system'], 'machine': manifest['machine'], 'sha256': dict(manifest['sha256'])}
    return {'schema_version': 'biocompiler.installed_native_conformance_inputs.v1',
        'native': native, 'ownership': ownership,
        'documents': {'release.json': selected.release_bytes.decode('utf-8'),
            'distribution.json': selected.distribution_bytes.decode('utf-8'),
            'binaries.json': selected.binaries_bytes.decode('utf-8'),
            'linkage.json': selected.linkage_bytes.decode('utf-8')}}


if __name__ == "__main__":
    main()
