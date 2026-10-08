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

try:
    from .prebuilt_release_pipeline import CAMPAIGN_GROUPS
    from . import ci_change_scope, ci_job_census
except ImportError:
    from prebuilt_release_pipeline import CAMPAIGN_GROUPS
    import ci_change_scope
    import ci_job_census


PYTHONS = ("3.11", "3.14")
PRODUCERS = ("installed-executable", "installed-architecture", "circuit-integration", "integration-examples")
REPRODUCIBILITY = ("executable-rna-reproducibility", "payload-architecture-reproducibility", "circuit-reproducibility")
CORE_PLATFORMS = {"linux-x86_64": ("Linux", "x86_64"), "macos-arm64": ("Darwin", "arm64")}
REALIZATION_VARIANTS = {f"{name}-py{version}": (system, machine, version)
                        for name, (system, machine) in CORE_PLATFORMS.items() for version in PYTHONS}
CAMPAIGN_VARIANTS = {f"{variant}-{group}": runtime for variant, runtime in REALIZATION_VARIANTS.items()
                     for group in CAMPAIGN_GROUPS}
RUNTIME_VARIANTS = {**REALIZATION_VARIANTS, **CAMPAIGN_VARIANTS}
PLATFORM_JOBS = frozenset(("ocaml-build", "ocaml-native-tests", "ocaml-core"))
RUNTIME_JOBS = {"architecture-sdk": REALIZATION_VARIANTS, "realization-conformance": REALIZATION_VARIANTS,
                "installed-campaigns": CAMPAIGN_VARIANTS, "policy-prebuilt-installed": REALIZATION_VARIANTS}
REQUIRED_NEEDS = frozenset((*PRODUCERS, *REPRODUCIBILITY, "studio-browser",
                            "ci-preflight", "ocaml-build", "ocaml-native-tests", "architecture-sdk", "installed-campaigns",
                            "unit-plan", "unit-tests", "unit-accounting", "ocaml-core", "studio-typescript",
                            "architecture-core-reproducibility", "realization-conformance", "realization-core-reproducibility", "prebuilt-core-assembly", "prebuilt-core-validation",
                            "policy-prebuilt-sdk", "policy-prebuilt-installed", "policy-prebuilt-reproducibility"))
EXPECTED_RECEIPTS = frozenset((job, version) for job in PRODUCERS for version in PYTHONS) | {
    *(("ci-preflight", version) for version in PYTHONS),
    *((job, variant) for job in ("ocaml-build", "ocaml-native-tests") for variant in CORE_PLATFORMS),
    *(("architecture-sdk", variant) for variant in REALIZATION_VARIANTS),
    *(("installed-campaigns", variant) for variant in CAMPAIGN_VARIANTS),
    ("studio-browser", "3.11"), *((job, "cross-python") for job in REPRODUCIBILITY),
    ("studio-typescript", "3.11"), *(("ocaml-core", variant) for variant in CORE_PLATFORMS),
    ("architecture-core-reproducibility", "cross-platform"),
    *(("realization-conformance", variant) for variant in REALIZATION_VARIANTS),
    ("realization-core-reproducibility", "cross-platform"),
    ("prebuilt-core-assembly", "cross-platform"),
    ("prebuilt-core-validation", "cross-platform"),
    ("policy-prebuilt-sdk", "cross-platform"),
    *(("policy-prebuilt-installed", variant) for variant in REALIZATION_VARIANTS),
    ("policy-prebuilt-reproducibility", "cross-platform"),
}


ROUTING_NEEDS = frozenset(("change-scope", "docs-validation"))
WORKFLOW_NEEDS = REQUIRED_NEEDS | ROUTING_NEEDS


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
    if job in PLATFORM_JOBS and (platform.system(), platform.machine()) != CORE_PLATFORMS[variant]:
        raise ValueError("Core build platform differs from required variant")
    if job in RUNTIME_JOBS:
        system, machine, version = RUNTIME_JOBS[job][variant]
        if (platform.system(), platform.machine(), ".".join(actual_python.split(".")[:2])) != (system, machine, version):
            raise ValueError("Realization conformance runtime differs from required variant")
    return {"schema_version": "biocompiler.ci_job_start.v0.1", **expected,
            "job": job, "variant": variant, "python_version": actual_python,
            "system": platform.system(), "machine": platform.machine(),
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
    if len(keys) != len(set(keys)) or set(keys) != WORKFLOW_NEEDS | {"validation"}:
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
        if key[0] in PLATFORM_JOBS and (receipt.get("system"), receipt.get("machine")) != CORE_PLATFORMS.get(key[1]):
            problems.append("wrong_core_platform:" + str(key))
        if key[0] in RUNTIME_JOBS:
            actual = (receipt.get("system"), receipt.get("machine"),
                      ".".join(str(receipt.get("python_version", "")).split(".")[:2]))
            if actual != RUNTIME_JOBS[key[0]].get(key[1]):
                problems.append("wrong_realization_runtime:" + str(key))
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


def concrete_job(job, variant):
    """Bind a receipt slot to GitHub's explicit matrix display name."""
    runners = {"linux-x86_64": "ubuntu-24.04", "macos-arm64": "macos-14"}
    if job in PLATFORM_JOBS:
        return f"{job} ({runners[variant]}, {variant})"
    if job in RUNTIME_JOBS:
        platform_name, runtime = variant.split("-py", 1)
        version, *group = runtime.split("-")
        values = [runners[platform_name], platform_name, version, *group]
        if job == "policy-prebuilt-installed":
            values.append({"linux-x86_64": "manylinux_2_39_x86_64",
                           "macos-arm64": "macosx_14_0_arm64"}[platform_name])
        return job + " (" + ", ".join(values) + ")"
    if job in (*PRODUCERS, "ci-preflight"):
        return f"{job} ({variant})"
    return job


def full_job_families():
    families = {job: set() for job in REQUIRED_NEEDS}
    for job, variant in EXPECTED_RECEIPTS:
        families[job].add(concrete_job(job, variant))
    for job in ("unit-plan", "unit-accounting"):
        families[job] = {f"{job} ({version})" for version in PYTHONS}
    families["unit-tests"] = {f"unit-tests ({version}, {shard})" for version in PYTHONS for shard in range(5)}
    return families


def full_job_names():
    return set().union(*full_job_families().values()) | {"Validation complete"}


def validate_routed(root, needs, receipts, accounting, expected, plan, docs, run, pages, *, env=None, event=None):
    """Select an explicit gate without weakening the existing full validator.

    Source policy and changed Git objects are rechecked independently. Actual job
    outcomes authenticate producing attempts, including preserved successful jobs
    on a failed-job retry. Documentation success never emits the full schema.
    """
    require = ci_change_scope.require
    require(isinstance(needs, dict) and set(needs) == WORKFLOW_NEEDS,
            "Missing or unexpected routed prerequisite jobs")
    checked = ci_change_scope.validate_plan(root, plan, env=env, event=event)
    authority = checked["identity"]
    require(all(authority[key] == expected[key] for key in ("revision", "run_id"))
            and valid_attempt(authority["run_attempt"], expected["run_attempt"]),
            "Scope and final gate identities disagree")
    scope = checked["scope"]
    require(scope in ("full", "docs_only"), "Unknown validation scope")
    census = ci_job_census.validate_census(
        {"run": run, "pages": pages}, expected={**authority, **expected, "workflow_path": authority["workflow"]},
        scope=scope, full_job_names=full_job_names(), skipped_job_keys=REQUIRED_NEEDS,
        full_job_families=full_job_families())
    selected = census["selected"]
    def outcome(job, result):
        require(isinstance(needs[job], dict) and needs[job].get("result") == result,
                "Unexpected routed prerequisite outcome: " + job)
    def producer(job, record):
        require(str(selected[job]["run_attempt"]) == record["run_attempt"],
                "Receipt differs from actual producing attempt: " + job)
    outcome("change-scope", "success")
    require(needs["change-scope"].get("outputs", {}).get("scope") == scope,
            "Scope job output disagrees with checked plan")
    producer("change-scope", authority)
    if scope == "full":
        outcome("docs-validation", "skipped")
        require(docs is None, "Unexpected documentation receipt on full route")
        result = validate({job: needs[job] for job in REQUIRED_NEEDS}, receipts, accounting, expected)
        # The legacy validator diagnoses malformed slots before indexing them.
        if result["status"] == "pass":
            for receipt in receipts:
                producer(concrete_job(receipt["job"], receipt["variant"]), receipt)
        result.update(scope="full", routing={"plan": checked, "job_census": census})
        return result
    outcome("docs-validation", "success")
    for job in REQUIRED_NEEDS:
        outcome(job, "skipped")
    require(not receipts and not accounting, "Native/test evidence present on documentation route")
    checked_docs = ci_change_scope.validate_docs(root, checked, docs, env=env, event=event)
    producer("docs-validation", checked_docs["identity"])
    return {"schema_version": "biocompiler.ci_documentation_validation.v0.1", **expected,
            "status": "pass", "scope": "docs_only", "acceptance": False, "problems": [],
            "native_validation": "not_run", "installed_validation": "not_run",
            "package_release_qualified": False, "prerequisites": needs,
            "routing": {"plan": checked, "job_census": census}, "documentation": checked_docs}


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
    gate.add_argument("--scope-plan", required=True, type=Path)
    gate.add_argument("--docs-receipt", required=True, type=Path)
    gate.add_argument("--run-metadata", required=True, type=Path)
    gate.add_argument("--job-pages", required=True, type=Path)
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
            result = validate_routed(Path(args.workflow).resolve().parents[2], needs, receipts, accounting,
                expected, read_json(args.scope_plan),
                read_json(args.docs_receipt) if args.docs_receipt.exists() else None,
                read_json(args.run_metadata), read_json(args.job_pages))
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
