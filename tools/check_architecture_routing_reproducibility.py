"""Compare complete installed architecture artifacts across two Pythons/platforms.

Only downloaded sibling paths are authoritative locations. Absolute installation
and artifact paths in source receipts are retained as run metadata, never opened.
This stdlib-only gate neither executes binaries nor imports compiler semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
CORPUS_PIN = "269e64293c36d52a5ad797c5c2808e52b0072e520992ade9bfa9f5de97dff90a"
PLATFORMS = {"linux-x86_64": ("Linux", "x86_64"), "macos-arm64": ("Darwin", "arm64")}
PYTHONS = ("3.11", "3.14")
INSTALLED = ("A", "B", "C", "D", "E", "F", "automatic_timing", "automatic_b", "automatic_f",
             "memory_reset", "state_reset", "production_adjustment", "activity_control")
CASES = tuple("installed/" + value for value in INSTALLED) + tuple("case_b/" + value for value in ("base", "parameter-default", "parameter-override"))
CASE_FILES = ("request.json", "build.json", "api.verification.json", "api.export.json", "payloads.fasta",
              "manifest.json", "independent.verification.json", "cli.build-summary.json", "cli.verification.json",
              "cli.standalone-verification.json", "cli.export-summary.json", "cli.build.json", "cli.export.json")
MUTATIONS = ("changed-original-authority", "changed-emitted-base")
EXPECTED_CHECKS = 175


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _hash(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _file_hash(path, maximum):
    require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= maximum,
            "Missing, empty, symlinked or oversized evidence: " + str(path))
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _read(path, maximum=8 * 1024 * 1024):
    pin = _file_hash(path, maximum)

    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate evidence JSON key: " + key)
            result[key] = value
        return result

    def invalid(value):
        raise AssertionError("Nonfinite evidence JSON: " + value)

    value = json.loads(path.read_bytes(), object_pairs_hook=unique, parse_constant=invalid)
    require(type(value) is dict, "Evidence JSON must be an object")
    return value, pin


def expected_artifacts():
    folders = [value.lower() for value in INSTALLED] + ["case_b-" + value for value in ("base", "parameter-default", "parameter-override")]
    paths = {folder + "/" + filename for folder in folders for filename in CASE_FILES}
    paths.update("b/" + name + suffix for name in MUTATIONS
                 for suffix in (".request.json", ".build.json", ".verification.json", ".export-rejection.json"))
    paths.update("b/" + name + ".json" for name in ("missing-selected-core", "input-alias-request", "input-alias-build"))
    require(len(paths) == 219, "Internal complete artifact census changed")
    return paths


def expected_checks():
    """Explicit outcome/field contract; None marks a required SHA-256 value."""
    checks = {}
    for case in CASES:
        for operation, field in (("sdk.compile", "build"), ("sdk.compile_payload_architecture", "build"),
                                 ("sdk.check", "assessment"), ("sdk.replay", "assessment"),
                                 ("sdk.export", "export"), ("standalone.verify", "assessment")):
            checks[case, operation] = {field: None}
        for operation in ("cli.build", "cli.verify", "cli.standalone.verify", "cli.export"):
            checks[case, operation] = {"exit_code": 0}
    for name in MUTATIONS:
        checks[name, "sdk.check"] = {"outcome": "fail", "assessment": None}
        checks[name, "sdk.export"] = {"error": "architecture_export_rejected"}
        checks[name, "sdk.replay"] = {"error": "architecture_assessment_mismatch"}
        checks[name, "cli.verify"] = {"exit_code": 1}
        checks[name, "cli.export"] = {"exit_code": 2, "preserved_output": True}
    checks["forged-report", "sdk.replay"] = {"error": "architecture_assessment_mismatch"}
    checks["missing-selected-core", "sdk.compile"] = {"error": "CoreUnavailable"}
    for name, operation in (("missing-selected-core", "cli.build"), ("input-alias-request", "cli.export"), ("input-alias-build", "cli.export")):
        checks[name, operation] = {"exit_code": 2, "preserved_output": True}
    require(len(checks) == EXPECTED_CHECKS, "Internal complete check census changed")
    return checks


def _checks(receipt):
    supplied = receipt.get("checks")
    require(type(supplied) is list and len(supplied) == EXPECTED_CHECKS
            and type(receipt.get("completed_checks")) is int and receipt["completed_checks"] == EXPECTED_CHECKS,
            "Incomplete routed check census")
    expected = expected_checks()
    seen = {}
    for item in supplied:
        require(type(item) is dict and type(item.get("id")) is str and type(item.get("operation")) is str,
                "Invalid routed check record")
        key = item["id"], item["operation"]
        require(key in expected and key not in seen, "Unknown or repeated routed check identity")
        require(set(item) == {"id", "operation"} | set(expected[key]), "Routed check fields changed")
        for field, value in expected[key].items():
            require(_hash(item[field]) if value is None else type(item[field]) is type(value) and item[field] == value,
                    "Routed check result/pin differs: " + repr(key))
        seen[key] = item
    require(set(seen) == set(expected), "Missing required routed check")
    for case in CASES:
        require(seen[case, "sdk.compile"]["build"] == seen[case, "sdk.compile_payload_architecture"]["build"],
                "Named and workflow compiler pins differ")
        require(len({seen[case, operation]["assessment"] for operation in ("sdk.check", "sdk.replay", "standalone.verify")}) == 1,
                "Fresh SDK replay and independent verification pins differ")
    return [seen[key] for key in sorted(seen)]


def _artifacts(directory, declared):
    require(directory.is_dir() and not directory.is_symlink(), "Missing artifact directory")
    require(type(declared) is dict and set(declared) == expected_artifacts()
            and all(_hash(value) for value in declared.values()), "Incomplete or extra declared artifact inventory")
    actual = {}
    for path in sorted(directory.rglob("*")):
        require(not path.is_symlink(), "Symlink in canonical artifact inventory")
        if path.is_dir():
            continue
        relative = path.relative_to(directory).as_posix()
        require(relative in declared, "Extra canonical artifact: " + relative)
        actual[relative] = _file_hash(path, 16 * 1024 * 1024)
    require(actual == declared, "Missing artifact or exact artifact digest differs")
    return actual


def compare(root, *, revision, source_revision, run_id):
    require(type(revision) is str and re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", revision)
            and type(source_revision) is str and re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", source_revision)
            and type(run_id) is str and bool(run_id), "Invalid current workflow authority")
    root = Path(root)
    require(root.is_dir(), "Missing downloaded native artifact root")
    sources, binaries = {}, {}
    baseline_artifacts = baseline_checks = None
    for platform_name, (system, machine) in PLATFORMS.items():
        slot = root / platform_name
        require(slot.is_dir() and not slot.is_symlink(), "Missing native platform evidence: " + platform_name)
        manifest, manifest_pin = _read(slot / "binaries.json", 64 * 1024)
        require(set(manifest) == {"revision", "system", "machine", "sha256"}
                and manifest["revision"] == revision and manifest["system"] == system and manifest["machine"] == machine,
                "Stale revision or wrong native binary platform")
        pins = manifest["sha256"]
        require(type(pins) is dict and set(pins) == {"biocompiler-core", "biocompiler-verify"}
                and all(_hash(pin) for pin in pins.values()), "Incomplete native binary identities")
        for name, pin in pins.items():
            require(_file_hash(slot / name, 256 * 1024 * 1024) == pin, "Native binary bytes differ from manifest")
        binaries[platform_name] = {"manifest_sha256": manifest_pin, **manifest}
        for python in PYTHONS:
            name = "architecture-routing-" + python
            receipt, receipt_pin = _read(slot / (name + ".json"))
            require(receipt.get("schema_version") == "biocompiler.architecture_routing_conformance.v1"
                    and receipt.get("status") == "success" and receipt.get("python_semantics_blocked") is True,
                    "Routing campaign did not complete under its execution guard")
            require(receipt.get("revision") == revision and receipt.get("source_revision") == source_revision
                    and receipt.get("run_id") == run_id, "Stale or mixed routing workflow authority")
            require(receipt.get("system") == system and receipt.get("machine") == machine
                    and type(receipt.get("python_version")) is str
                    and re.fullmatch(re.escape(python) + r"\.\d+", receipt["python_version"]), "Wrong routed Python/native platform")
            require(receipt.get("corpus_pin") == CORPUS_PIN, "Routing corpus authority changed")
            executables = receipt.get("executables")
            require(type(executables) is dict and set(executables) == {"core", "verify"}, "Missing routed executable role")
            for role in ("core", "verify"):
                record = executables[role]
                require(type(record) is dict and set(record) == {"path", "sha256"}
                        and type(record["path"]) is str and bool(record["path"])
                        and record["sha256"] == pins["biocompiler-" + role], "Routing executable differs from its platform binary")
            checks = _checks(receipt)
            # Do not consult receipt['artifacts_path'] or follow that host path.
            inventory = _artifacts(slot / name / "artifacts", receipt.get("artifacts"))
            if baseline_artifacts is None:
                baseline_artifacts, baseline_checks = inventory, checks
            else:
                require(inventory == baseline_artifacts, "Four-way exact canonical artifacts differ")
                require(checks == baseline_checks, "Four-way routed operation results differ")
            sources[platform_name + "/" + python] = {
                "path": platform_name + "/" + name + ".json", "sha256": receipt_pin,
                "metadata": {key: value for key, value in receipt.items() if key not in {"checks", "artifacts"}},
                "checks_sha256": _digest(checks), "artifacts_sha256": _digest(inventory),
            }
    require(len(sources) == 4 and baseline_artifacts, "Missing four-way installed evidence")
    return {"schema_version": "biocompiler.architecture_routing_reproducibility.v1", "status": "success",
            "revision": revision, "source_revision": source_revision, "run_id": run_id, "corpus_pin": CORPUS_PIN,
            "compared_runs": 4, "checks_per_run": EXPECTED_CHECKS, "cases": list(CASES),
            "artifact_count": len(baseline_artifacts), "artifacts": baseline_artifacts,
            "artifacts_sha256": _digest(baseline_artifacts), "platform_binaries": binaries, "source_receipts": sources}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        revision = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
        require(os.environ.get("GITHUB_SHA", revision) == revision, "Comparison checkout differs from workflow revision")
        result = compare(args.root, revision=revision, source_revision=os.environ.get("GITHUB_HEAD_SHA", revision),
                         run_id=os.environ.get("GITHUB_RUN_ID", "local"))
        code = 0
    except Exception as error:
        result = {"schema_version": "biocompiler.architecture_routing_reproducibility.v1", "status": "failure",
                  "error": type(error).__name__ + ": " + str(error)}
        print(result["error"], file=sys.stderr)
        code = 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("Architecture routing reproducibility:", result["status"])
    return code


if __name__ == "__main__":
    raise SystemExit(main())
