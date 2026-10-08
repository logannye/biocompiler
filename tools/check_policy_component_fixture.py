"""Hosted declaration emission and inert provenance checks for component inputs.

The private domain-only executable emits supplied originals, never candidates or
acceptance. Installed workers receive data and exact build provenance; they do
not receive or execute the private emitter.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

try:
    from . import check_policy_core as core, check_policy_development as development
except ImportError:
    import check_policy_core as core
    import check_policy_development as development

SCHEMA = "biocompiler.policy_component_fixture_provenance.v0.1"
FIXTURE_SCHEMA = "biocompiler.policy_component_original_fixture.v0.1"
OUTPUT = "generated/core/component-originals"
INPUTS = development.SDK_ORIGINALS
BINARIES = development.SDK_BINARIES
PLATFORMS = {("Linux", "x86_64"), ("Darwin", "arm64")}
MAX_FIXTURE = 4_000_000
MAX_PROVENANCE = 8 * 1024 * 1024
MAX_LOG = 1024 * 1024


def require(value, message):
    if not value:
        raise AssertionError(message)


def pin(path, maximum, *, empty=False):
    path = Path(path)
    require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)),
            "Missing or redirected component fixture input")
    with path.open("rb") as stream:
        raw = stream.read(maximum + 1)
    require((empty or raw) and len(raw) <= maximum, "Component fixture input exceeds its byte bound")
    return {"sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw)}


def read(path, maximum):
    before = pin(path, maximum)
    value = core.read_json(Path(path), maximum)
    require(before == pin(path, maximum), "Component fixture changed during decoding")
    return value


def binary_pins(root):
    return {role: development.pin(root, path, executable=True) for role, path in BINARIES.items()}


def logical_command():
    return ["opam", "exec", "--", BINARIES["originals"], *INPUTS, OUTPUT + "/originals.json"]


def hosted_identity(root):
    require(os.environ.get("GITHUB_ACTIONS") == "true"
            and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted",
            "Component fixture emission requires hosted execution")
    require(Path(os.environ.get("GITHUB_WORKSPACE", "")).resolve() == root.resolve(),
            "Component fixture has a foreign workspace")
    actual = (platform.system(), platform.machine())
    require(actual in PLATFORMS, "Unsupported component fixture native platform")
    expected_runner = ("Linux", "X64") if actual[0] == "Linux" else ("macOS", "ARM64")
    require((os.environ.get("RUNNER_OS"), os.environ.get("RUNNER_ARCH")) == expected_runner,
            "Component fixture runner differs from actual platform")
    identity = core.source_identity()
    check_identity(identity, identity)
    return identity


def check_identity(producer, consumer):
    keys = {"revision", "head_revision", "run_id", "run_attempt"}
    require(type(producer) is dict and type(consumer) is dict and set(producer) == set(consumer) == keys,
            "Component fixture identity fields differ")
    for value in (producer, consumer):
        require(all(type(value[key]) is str and re.fullmatch(r"[0-9a-f]{40}", value[key])
                    for key in ("revision", "head_revision"))
                and all(type(value[key]) is str and re.fullmatch(r"[1-9][0-9]{0,19}", value[key])
                        for key in ("run_id", "run_attempt")), "Invalid component fixture identity")
    require(all(producer[key] == consumer[key] for key in ("revision", "head_revision", "run_id"))
            and int(producer["run_attempt"]) <= int(consumer["run_attempt"]),
            "Component fixture lacks same source/run and nonfuture attempt")


def check_packet(root, path):
    packet = read(path, MAX_FIXTURE)
    require(type(packet) is dict and set(packet) == {"schema_version", "status", "acceptance", "source_sha256", "cases"}
            and packet["schema_version"] == FIXTURE_SCHEMA and packet["status"] == "source_declarations_only"
            and packet["acceptance"] is False
            and packet["source_sha256"] == {name: pin(root / name, MAX_FIXTURE)["sha256"] for name in INPUTS},
            "Component originals differ from independently supplied source declarations")
    cases = packet["cases"]
    require(type(cases) is list and len(cases) == 2 and all(type(case) is dict for case in cases)
            and [case.get("id") for case in cases] == ["A", "B"]
            and all(set(case) == {"id", "request", "limits", "expected"}
                    and all(type(case[key]) is dict for key in ("request", "limits", "expected")) for case in cases),
            "Component original case inventory differs")
    return packet


def validate(root, fixture_path, provenance_path, *, identity, native_sha256, expected_platform=None):
    """Check externally bound emitted data without invoking any native program."""
    root, fixture_path, provenance_path = Path(root), Path(fixture_path), Path(provenance_path)
    require(fixture_path.name == "originals.json" and provenance_path.name == "provenance.json"
            and fixture_path.parent == provenance_path.parent, "Component fixture pair paths differ")
    before = {name: pin(fixture_path.parent / name, maximum, empty=name.endswith(".log")) for name, maximum in
              (("originals.json", MAX_FIXTURE), ("provenance.json", MAX_PROVENANCE),
               ("stdout.log", MAX_LOG), ("stderr.log", MAX_LOG))}
    value = read(provenance_path, MAX_PROVENANCE)
    require(type(value) is dict and set(value) == {"schema_version", "status", "acceptance", "identity", "platform",
            "sources", "binaries", "fixture", "command"} and value["schema_version"] == SCHEMA
            and value["status"] == "source_declarations_only" and value["acceptance"] is False,
            "Component fixture provenance is incomplete or changes authority scope")
    check_identity(value["identity"], identity)
    require(type(value["platform"]) is dict and set(value["platform"]) == {"system", "machine"},
            "Component fixture platform fields differ")
    actual_platform = (value["platform"]["system"], value["platform"]["machine"])
    require(actual_platform in PLATFORMS and (expected_platform is None or actual_platform == tuple(expected_platform)),
            "Component fixture platform differs")
    require(core.canonical_digest(value["sources"]) == core.canonical_digest(development.source_snapshot(root)),
            "Component fixture build sources changed")
    binaries = value["binaries"]
    require(type(binaries) is dict and set(binaries) == set(BINARIES)
            and type(native_sha256) is dict and set(native_sha256) == {"core", "verify"},
            "Component fixture binary inventory differs")
    for role, record in binaries.items():
        require(type(record) is dict and set(record) == {"sha256", "size"}
                and type(record["size"]) is int and 0 < record["size"] <= 128 * 1024 * 1024
                and type(record["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", record["sha256"]),
                "Invalid component fixture executable pin")
        if role != "originals":
            require(record["sha256"] == native_sha256[role], "Component fixture differs from externally pinned native role")
    expected_command = {
        "argv": logical_command(), "cwd": "checkout", "returncode": 0,
        "logs": {name: before[name] for name in ("stdout.log", "stderr.log")}}
    require(core.canonical_digest(value["fixture"]) == core.canonical_digest(before["originals.json"])
            and core.canonical_digest(value["command"]) == core.canonical_digest(expected_command),
        "Component fixture command, complete logs or output changed")
    check_packet(root, fixture_path)
    require(before == {name: pin(fixture_path.parent / name, MAX_FIXTURE if name == "originals.json" else
            MAX_PROVENANCE if name == "provenance.json" else MAX_LOG, empty=name.endswith(".log")) for name in before},
            "Component fixture evidence changed during validation")
    return value


def emit(root):
    root = Path(root)
    identity = hosted_identity(root)  # Reject local execution before any native launch.
    sources, binaries = development.source_snapshot(root), binary_pins(root)
    output = root / OUTPUT
    output.mkdir(parents=True, exist_ok=False)
    report = {"schema_version": SCHEMA, "status": "incomplete", "acceptance": False,
              "identity": identity, "platform": {"system": platform.system(), "machine": platform.machine()},
              "sources": sources, "binaries": binaries, "fixture": None, "command": None}
    argv = ["opam", "exec", "--", str(root / BINARIES["originals"]),
            *(str(root / path) for path in INPUTS), str(output / "originals.json")]
    try:
        completed = subprocess.run(argv, cwd=root, capture_output=True, timeout=90, check=False)
        for name, raw in (("stdout.log", completed.stdout), ("stderr.log", completed.stderr)):
            require(len(raw) <= MAX_LOG, "Component fixture command log exceeded its bound")
            (output / name).write_bytes(raw)
        report["command"] = {"argv": logical_command(), "cwd": "checkout", "returncode": completed.returncode,
            "logs": {name: pin(output / name, MAX_LOG, empty=True) for name in ("stdout.log", "stderr.log")}}
        require(completed.returncode == 0, "Component fixture declaration emission failed")
        check_packet(root, output / "originals.json")
        report["fixture"] = pin(output / "originals.json", MAX_FIXTURE)
        require(sources == development.source_snapshot(root) and binaries == binary_pins(root)
                and identity == hosted_identity(root), "Component fixture authority changed during emission")
        report["status"] = "source_declarations_only"
    finally:
        raw = (json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        require(len(raw) <= MAX_PROVENANCE, "Component provenance exceeds its bound")
        (output / "provenance.json").write_bytes(raw)
    validate(root, output / "originals.json", output / "provenance.json", identity=identity,
             native_sha256={role: binaries[role]["sha256"] for role in ("core", "verify")},
             expected_platform=(platform.system(), platform.machine()))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("emit",))
    parser.parse_args()
    emit(Path(__file__).resolve().parents[1])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
