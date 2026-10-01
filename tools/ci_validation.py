"""Fail-closed CI job receipts and the final aggregate validation gate.

Job receipts supply revision/variant/timing identity; GitHub's independent needs
results remain mandatory. A success-shaped receipt never excuses failed,
skipped, cancelled or missing work. Test accounting is produced by test_shards.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time


PYTHONS = ("3.11", "3.14")
PRODUCERS = ("installed-executable", "installed-architecture", "circuit-integration", "integration-examples")
REPRODUCIBILITY = ("executable-rna-reproducibility", "payload-architecture-reproducibility", "circuit-reproducibility")
REQUIRED_NEEDS = frozenset((*PRODUCERS, *REPRODUCIBILITY, "studio-browser",
                            "unit-plan", "unit-tests", "unit-accounting"))
EXPECTED_RECEIPTS = frozenset((job, version) for job in PRODUCERS for version in PYTHONS) | {
    ("studio-browser", "3.11"), *((job, "cross-python") for job in REPRODUCIBILITY),
}


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key: " + key)
            result[key] = value
        return result
    path = Path(path)
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError("CI receipt exceeds input bound")
    def nonfinite(value):
        raise ValueError("Nonfinite JSON number: " + value)
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=nonfinite)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def identity():
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if os.environ.get("GITHUB_SHA", revision) != revision:
        raise ValueError("Checked-out revision differs from the workflow revision")
    return {"revision": revision, "run_id": os.environ.get("GITHUB_RUN_ID", "local"),
            "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "local")}


def start_job(job, variant, expected):
    if (job, variant) not in EXPECTED_RECEIPTS:
        raise ValueError("Unexpected job/variant")
    if os.environ.get("GITHUB_JOB", job) != job:
        raise ValueError("Job receipt differs from executing workflow job")
    actual_python = platform.python_version()
    if variant in PYTHONS and ".".join(actual_python.split(".")[:2]) != variant:
        raise ValueError("Job Python differs from required variant")
    return {"schema_version": "biocompiler.ci_job_start.v0.1", **expected,
            "job": job, "variant": variant, "python_version": actual_python,
            "platform": platform.platform(), "started_at": datetime.now(timezone.utc).isoformat(),
            "started_monotonic": time.monotonic()}


def finish_job(start, expected):
    if start.get("schema_version") != "biocompiler.ci_job_start.v0.1":
        raise ValueError("Unknown job-start receipt")
    if any(start.get(key) != value for key, value in expected.items()):
        raise ValueError("Stale job-start authority")
    current = start_job(start["job"], start["variant"], expected)
    if start["python_version"] != current["python_version"] or start["platform"] != current["platform"]:
        raise ValueError("Job runtime changed during validation")
    elapsed = time.monotonic() - start["started_monotonic"]
    if elapsed < 0:
        raise ValueError("Invalid elapsed validation time")
    return {key: value for key, value in {**start,
        "schema_version": "biocompiler.ci_job_receipt.v0.1", "status": "success",
        "finished_at": current["started_at"], "duration_seconds": round(elapsed, 6),
    }.items() if key != "started_monotonic"}


def workflow_jobs(path):
    """Recognize our explicit job-key layout; unfamiliar layouts fail closed.

    This does not replace GitHub's YAML validator. Keeping direct job keys in a
    simple, explicit layout lets this stdlib-only gate detect a newly added job
    omitted from its prerequisite registry, without a runtime YAML dependency.
    """
    text = Path(path).read_text(encoding="utf-8")
    if text.count("\njobs:\n") != 1:
        raise ValueError("Expected one explicit workflow jobs mapping")
    block = text.split("\njobs:\n", 1)[1]
    keys = []
    for line in block.splitlines():
        if line.startswith("  ") and not line.startswith("   ") and line.strip() and not line.lstrip().startswith("#"):
            match = re.fullmatch(r"  ([A-Za-z_][A-Za-z0-9_-]*):(?:\s+#.*)?", line)
            if match is None:
                raise ValueError("Use explicit standalone workflow job keys")
            keys.append(match[1])
    if len(keys) != len(set(keys)) or set(keys) != REQUIRED_NEEDS | {"validation"}:
        raise ValueError("Workflow job registry and required validation jobs disagree")
    return set(keys)


def validate(needs, receipts, accounting, expected):
    problems = []
    if not isinstance(needs, dict) or set(needs) != REQUIRED_NEEDS:
        problems.append("missing_or_unexpected_prerequisite_jobs")
    if isinstance(needs, dict):
        for job, result in needs.items():
            if not isinstance(result, dict) or result.get("result") != "success":
                problems.append("prerequisite_not_successful:" + job)
    found = {}
    for receipt in receipts:
        if not isinstance(receipt, dict):
            problems.append("job_receipt_not_object")
            continue
        key = (receipt.get("job"), receipt.get("variant"))
        if key not in EXPECTED_RECEIPTS or key in found:
            problems.append("unexpected_or_duplicate_job_receipt:" + str(key))
        found[key] = receipt
        if receipt.get("schema_version") != "biocompiler.ci_job_receipt.v0.1" or receipt.get("status") != "success":
            problems.append("invalid_job_receipt:" + str(key))
        if (any(receipt.get(field) != expected[field] for field in ("revision", "run_id"))
            or not valid_attempt(receipt.get("run_attempt"), expected["run_attempt"])):
            problems.append("stale_job_receipt:" + str(key))
        if key[1] in PYTHONS and ".".join(str(receipt.get("python_version", "")).split(".")[:2]) != key[1]:
            problems.append("wrong_job_python:" + str(key))
    if set(found) != EXPECTED_RECEIPTS:
        problems.append("incomplete_job_variant_coverage")
    versions = {}
    for record in accounting:
        if not isinstance(record, dict):
            problems.append("test_accounting_not_object")
            continue
        version = ".".join(str(record.get("python_version", "")).split(".")[:2])
        if version not in PYTHONS or version in versions:
            problems.append("unexpected_or_duplicate_test_accounting:" + version)
        versions[version] = record
        if (record.get("schema") != "biocompiler.unittest_shard_accounting.v1"
            or record.get("status") != "pass" or record.get("revision") != expected["revision"]):
            problems.append("failed_or_stale_test_accounting:" + version)
        if type(record.get("total_tests")) is not int or record["total_tests"] < 1:
            problems.append("empty_test_accounting:" + version)
        if (type(record.get("shard_count")) is not int or record["shard_count"] != 5
            or record.get("expected_shards") != 5 or record.get("verified_shards") != list(range(5))):
            problems.append("incomplete_shard_accounting:" + version)
        ids = record.get("executed_ids")
        if (not isinstance(ids, list) or not all(isinstance(item, str) and item for item in ids)
            or len(ids) != record.get("total_tests") or len(set(ids)) != len(ids)
            or record.get("discovered_count") != len(ids) or record.get("executed_count") != len(ids)):
            problems.append("inconsistent_test_inventory:" + version)
        digests = record.get("result_digests")
        digest_fields = [record.get("discovery_digest"), record.get("plan_fingerprint")]
        if (not isinstance(digests, list) or len(digests) != 5
            or not all(isinstance(item, str) and re.fullmatch(r"[0-9a-f]{64}", item)
                       for item in digest_fields + (digests if isinstance(digests, list) else []))):
            problems.append("missing_accounting_authority:" + version)
        times = record.get("shard_seconds")
        if (not isinstance(times, dict) or set(times) != {str(index) for index in range(5)}
            or not all(type(value) in (int, float) and math.isfinite(value) and value >= 0
                       for value in times.values())):
            problems.append("incomplete_shard_timings:" + version)
    if set(versions) != set(PYTHONS):
        problems.append("incomplete_python_test_coverage")
    return {"schema_version": "biocompiler.ci_validation.v0.1", **expected,
            "status": "fail" if problems else "pass", "problems": sorted(set(problems)),
            "prerequisites": needs, "jobs": sorted(found.values(), key=lambda item: (str(item.get("job")), str(item.get("variant")))),
            "test_accounting": accounting}


def valid_attempt(recorded, current):
    # GitHub's rerun-failed-jobs keeps already successful jobs from an earlier
    # attempt in this same run/revision. Require its independent needs result;
    # permit the preserved receipt without pretending those jobs ran again.
    if recorded == current == "local":
        return True
    return (isinstance(recorded, str) and recorded.isdecimal()
            and isinstance(current, str) and current.isdecimal()
            and 1 <= int(recorded) <= int(current))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start")
    start.add_argument("--job", required=True)
    start.add_argument("--variant", required=True)
    start.add_argument("--output", required=True)
    finish = sub.add_parser("finish")
    finish.add_argument("--start", required=True)
    finish.add_argument("--output", required=True)
    gate = sub.add_parser("gate")
    gate.add_argument("--receipts", required=True, type=Path)
    gate.add_argument("--accounting", required=True, type=Path)
    gate.add_argument("--workflow", default=".github/workflows/ci.yml")
    gate.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        expected = identity()
        if args.command == "start":
            result = start_job(args.job, args.variant, expected)
        elif args.command == "finish":
            result = finish_job(read_json(args.start), expected)
        else:
            workflow_jobs(args.workflow)
            needs = json.loads(os.environ.get("CI_NEEDS", "null"))
            receipts = [read_json(path) for path in sorted(args.receipts.rglob("*.json"))]
            accounting = [read_json(path) for path in sorted(args.accounting.rglob("*.json"))]
            result = validate(needs, receipts, accounting, expected)
        write_json(args.output, result)
        print(json.dumps(result if args.command == "gate" else {"status": "recorded", **expected}, sort_keys=True))
        return 1 if result.get("status") == "fail" else 0
    except (ValueError, TypeError, KeyError, OSError, subprocess.CalledProcessError) as error:
        write_json(args.output, {"schema_version": "biocompiler.ci_validation.v0.1",
                                "status": "fail", "problems": [str(error)]})
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
