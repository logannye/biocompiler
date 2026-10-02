"""Explicit byte-exact CLI counterparts for supported Python runtime families.

Each immutable declaration binds one baseline case and full observations from
separately executed runtimes. No text transformation, wildcard, or formatting
normalization is permitted. Consumers retain actual bytes before projecting a
validated counterpart solely for cross-runtime comparison.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import platform
import re

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / "tests/conformance/workflow-cli-runtime-counterparts-v1.json"
WORKFLOW_SHA256 = "93d8ffeb4ec490839d7906151f92df7b3fb43d31c94f8f2fa983f93aeb6ac8db"
SCHEMA = "biocompiler.cli_runtime_counterparts.v1"
SUPPORTED = ("3.11", "3.14")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def runtime_minor(version=None):
    version = platform.python_version() if version is None else version
    require(type(version) is str and re.fullmatch(r"[0-9]+\.[0-9]+(?:\.[0-9]+)?", version) is not None,
            "Invalid exact CLI Python runtime")
    minor = ".".join(version.split(".")[:2])
    require(minor in SUPPORTED, "Unsupported exact CLI Python runtime: " + version)
    return minor


def bytes_record(raw):
    require(type(raw) is bytes, "Counterpart observations require exact bytes")
    return {"bytes": len(raw), "sha256": sha(raw), "hex": raw.hex()}


def decode_bytes(value):
    require(type(value) is dict and set(value) == {"bytes", "sha256", "hex"} and
            type(value["bytes"]) is int and type(value["hex"]) is str and
            re.fullmatch(r"(?:[0-9a-f]{2})*", value["hex"]) is not None,
            "Invalid full CLI counterpart bytes")
    raw = bytes.fromhex(value["hex"])
    require(value == bytes_record(raw), "CLI counterpart byte identity differs")
    return raw


class Counterparts:
    def __init__(self, path, pin, baseline_pin):
        raw = Path(path).read_bytes()
        require(sha(raw) == pin, "Immutable CLI runtime counterpart bytes changed")
        value = json.loads(raw)
        require(type(value) is dict and set(value) == {"schema_version", "baseline_inventory_fingerprint",
                "baseline_python_minor", "supported_python_minors", "cases", "provenance"} and
                value["schema_version"] == SCHEMA and value["baseline_inventory_fingerprint"] == baseline_pin and
                value["baseline_python_minor"] == "3.14" and value["supported_python_minors"] == list(SUPPORTED),
                "CLI runtime counterpart declaration differs")
        require(type(value["cases"]) is list and value["cases"], "Missing exact CLI runtime counterparts")
        cases = {}
        for case in value["cases"]:
            require(type(case) is dict and set(case) == {"id", "baseline_case_sha256", "observations"} and
                    type(case["id"]) is str and case["id"] not in cases and
                    re.fullmatch(r"[0-9a-f]{64}", case["baseline_case_sha256"]) is not None and
                    type(case["observations"]) is dict and set(case["observations"]) == set(SUPPORTED),
                    "Invalid or duplicate exact CLI counterpart case")
            for observation in case["observations"].values():
                require(type(observation) is dict and set(observation) == {"exit_code", "stdout", "stderr"} and
                        type(observation["exit_code"]) is int, "Invalid complete CLI counterpart observation")
                decode_bytes(observation["stdout"]); decode_bytes(observation["stderr"])
            cases[case["id"]] = case
        self.pin, self.baseline_pin, self.cases = pin, baseline_pin, cases

    def expected(self, original, baseline_observation, version=None):
        """Return exact expected bytes; baseline case identity includes argv and audit."""
        minor = runtime_minor(version)
        require(type(baseline_observation) is dict and set(baseline_observation) == {"exit_code", "stdout", "stderr"} and
                type(baseline_observation["exit_code"]) is int and
                type(baseline_observation["stdout"]) is bytes and type(baseline_observation["stderr"]) is bytes,
                "Invalid original CLI observation")
        case = self.cases.get(original["id"])
        if case is None:
            return dict(baseline_observation)
        require(sha(canonical(original)) == case["baseline_case_sha256"], "Exact CLI counterpart baseline case changed")
        archived = case["observations"]["3.14"]
        require(baseline_observation == {"exit_code": archived["exit_code"],
                "stdout": decode_bytes(archived["stdout"]), "stderr": decode_bytes(archived["stderr"])},
                "Exact CLI counterpart original bytes changed")
        actual = case["observations"][minor]
        return {"exit_code": actual["exit_code"], "stdout": decode_bytes(actual["stdout"]),
                "stderr": decode_bytes(actual["stderr"])}


def workflow():
    return Counterparts(WORKFLOW_PATH, WORKFLOW_SHA256,
                        "a67edb95f75aa011ed5c059fe8cbe578fbe118d056931e3992f73775e8951da7")
