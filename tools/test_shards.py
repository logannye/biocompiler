"""Discover, balance, execute and account for fresh stdlib unittest shards.

Duration hints affect placement only. A plan or a retained PASS never replaces
discovery or execution. Run plan, run and verify with the same Python version
and checkout. Whole classes stay together to preserve unittest class fixtures.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import platform
import signal
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = Path(__file__).with_name("test_shard_weights.json")
PLAN_SCHEMA = "biocompiler.unittest_shard_plan.v1"
RESULT_SCHEMA = "biocompiler.unittest_shard_result.v1"
ACCOUNTING_SCHEMA = "biocompiler.unittest_shard_accounting.v1"
SUCCESS = {"success", "skipped", "expected_failure"}
JSON_MAX_BYTES = 20_000_000
# Plans retain the complete tracked source/data inventory. Large conformance
# corpora can exceed the result/weight bound without adding a single test.
PLAN_MAX_BYTES = 64 * 1024 * 1024


class ShardError(ValueError):
    """Missing, stale, contradictory or incomplete test accounting."""


def require(condition, message):
    if not condition:
        raise ShardError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def read_json(path, *, max_bytes=JSON_MAX_BYTES):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "Duplicate JSON key: " + key)
            result[key] = value
        return result

    def nonfinite(value):
        raise ShardError("Nonfinite JSON number: " + value)

    require(type(max_bytes) is int and max_bytes > 0, "Invalid shard JSON byte limit.")
    require(Path(path).stat().st_size <= max_bytes, f"Shard JSON input exceeds the {max_bytes}-byte limit.")
    # Bound the actual read too: a file can grow after the initial size check.
    with Path(path).open("rb") as stream:
        payload = stream.read(max_bytes + 1)
    require(len(payload) <= max_bytes, f"Shard JSON input exceeds the {max_bytes}-byte limit.")
    return json.loads(payload.decode("utf-8"), object_pairs_hook=unique,
                      parse_constant=nonfinite)


def write_json(path, value, *, max_bytes=JSON_MAX_BYTES):
    require(type(max_bytes) is int and max_bytes > 0, "Invalid shard JSON byte limit.")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoder = json.JSONEncoder(indent=2, sort_keys=True, allow_nan=False)
    with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent,
                                     prefix="." + path.name, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            written = 0
            for chunk in encoder.iterencode(value):
                raw = chunk.encode("utf-8")
                written += len(raw)
                # Reserve the final newline before committing any output.
                require(written + 1 <= max_bytes,
                        f"Shard JSON output exceeds the {max_bytes}-byte limit.")
                stream.write(raw)
            stream.write(b"\n")
            stream.flush()
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def environment(root):
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    return {"revision": revision, "python": platform.python_version(),
            "implementation": platform.python_implementation()}


def source_inventory(root, start_directory):
    """Bind tracked source/data plus newly discovered Python files, without outputs."""
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
    paths = {Path(name) for name in tracked if name}
    paths.update(path.relative_to(root) for path in (root / start_directory).rglob("*.py"))
    paths.add(Path(__file__).resolve().relative_to(root))
    return {path.as_posix(): hashlib.sha256((root / path).read_bytes()).hexdigest()
            for path in sorted(paths) if (root / path).is_file()}


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


@dataclass
class Discovery:
    tests: dict
    manifest: dict


def discover(root=ROOT, start_directory="tests", pattern="test*.py"):
    root = Path(root).resolve()
    start = (root / start_directory).resolve()
    require(start.is_relative_to(root) and start.is_dir(), "Test directory must be inside the checkout.")
    # Match `python -m unittest discover -s tests`: expose examples/tools, never
    # add src (CI must exercise the independently installed package).
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    loader = unittest.TestLoader()
    suite = loader.discover(str(start), pattern=pattern)
    require(not loader.errors, "Discovery failed:\n" + "\n".join(loader.errors))
    tests, classes = {}, {}
    for test in flatten(suite):
        identity = test.id()
        require(isinstance(identity, str) and bool(identity), "Test ID must be nonempty.")
        require(identity not in tests, "Duplicate discovered test ID: " + identity)
        tests[identity] = test
        class_id = type(test).__module__ + "." + type(test).__qualname__
        classes.setdefault(class_id, []).append(identity)
    require(bool(tests), "Discovery found no tests.")
    manifest = {"start_directory": start.relative_to(root).as_posix(), "pattern": pattern,
                "test_ids": sorted(tests),
                "classes": {key: sorted(value) for key, value in sorted(classes.items())},
                "source_files": source_inventory(root, start.relative_to(root))}
    manifest["digest"] = digest(manifest)
    return Discovery(tests, manifest)


def make_plan(discovery, env, shards=5, weights=None):
    require(type(shards) is int and 1 <= shards <= 100, "Invalid shard count.")
    weights = {} if weights is None else weights
    require(isinstance(weights, dict), "Weights must be an object.")
    hints = weights.get("classes", {})
    require(isinstance(hints, dict), "Class weights must be an object.")
    default = weights.get("unknown_seconds_per_test", 2.0)
    require(type(default) in (int, float) and math.isfinite(default) and default > 0,
            "Invalid conservative default test duration.")
    units = []
    for class_id, identities in discovery.manifest["classes"].items():
        if class_id in hints:
            hint = hints[class_id]
            require(isinstance(hint, dict) and type(hint.get("tests")) is int
                    and hint["tests"] > 0 and type(hint.get("seconds")) in (int, float)
                    and math.isfinite(hint["seconds"]) and hint["seconds"] >= 0,
                    "Invalid class duration hint: " + class_id)
            # New methods get at least the conservative unknown-test weight.
            count = min(len(identities), hint["tests"])
            seconds = hint["seconds"] * count / hint["tests"] + default * max(0, len(identities) - count)
        else:
            seconds = default * len(identities)
        units.append((max(0.001, seconds), class_id))
    allocations = [{"index": index, "class_ids": [], "test_ids": [], "estimated_seconds": 0.0}
                   for index in range(shards)]
    for seconds, class_id in sorted(units, key=lambda value: (-value[0], value[1])):
        selected = min(allocations, key=lambda item: (item["estimated_seconds"], item["index"]))
        selected["class_ids"].append(class_id)
        selected["estimated_seconds"] += seconds
    for selected in allocations:
        selected["class_ids"].sort()
        selected["test_ids"] = [identity for class_id in selected["class_ids"]
                                for identity in discovery.manifest["classes"][class_id]]
        selected["estimated_seconds"] = round(selected["estimated_seconds"], 6)
    plan = {"schema": PLAN_SCHEMA, "environment": env, "discovery": discovery.manifest,
            "shard_count": shards, "weights_digest": digest(weights), "shards": allocations}
    plan["fingerprint"] = digest(plan)
    validate_plan(plan, discovery, env)
    return plan


def validate_plan(plan, discovery, env):
    require(isinstance(plan, dict) and set(plan) == {"schema", "environment", "discovery", "shard_count",
            "weights_digest", "shards", "fingerprint"}, "Malformed shard plan.")
    require(plan["schema"] == PLAN_SCHEMA, "Unsupported shard plan schema.")
    require(plan["fingerprint"] == digest({key: value for key, value in plan.items() if key != "fingerprint"}),
            "Shard plan fingerprint mismatch.")
    require(digest(plan["environment"]) == digest(env), "Stale plan revision or Python environment.")
    require(digest(plan["discovery"]) == digest(discovery.manifest), "Stale or incomplete source discovery.")
    count = plan["shard_count"]
    require(type(count) is int and 1 <= count <= 100 and isinstance(plan["shards"], list)
            and len(plan["shards"]) == count, "Shard inventory mismatch.")
    all_ids, all_classes = [], []
    for index, shard in enumerate(plan["shards"]):
        require(isinstance(shard, dict) and set(shard) == {"index", "class_ids", "test_ids", "estimated_seconds"},
                "Malformed shard assignment.")
        require(type(shard["index"]) is int and shard["index"] == index, "Shard indices are not exact.")
        require(isinstance(shard["class_ids"], list) and isinstance(shard["test_ids"], list),
                "Shard IDs must be arrays.")
        require(all(isinstance(value, str) for value in shard["class_ids"] + shard["test_ids"]), "Invalid shard ID.")
        require(set(shard["class_ids"]) <= discovery.manifest["classes"].keys(), "Unknown test class.")
        expected = [identity for class_id in shard["class_ids"] for identity in discovery.manifest["classes"][class_id]]
        require(shard["test_ids"] == expected, "Class tests omitted, added, reordered or split.")
        require(type(shard["estimated_seconds"]) in (int, float) and math.isfinite(shard["estimated_seconds"])
                and shard["estimated_seconds"] >= 0, "Invalid shard estimate.")
        all_ids.extend(shard["test_ids"])
        all_classes.extend(shard["class_ids"])
    require(Counter(all_ids) == Counter(discovery.tests.keys()), "Tests missing, extra or duplicated across shards.")
    require(Counter(all_classes) == Counter(discovery.manifest["classes"].keys()), "Classes missing or duplicated across shards.")


class TimedResult(unittest.TextTestResult):
    def __init__(self, *args, checkpoint, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []
        self.fixture_errors = []
        self.class_fixture_seconds = {}
        self.checkpoint = checkpoint
        self.current = None

    def startTest(self, test):
        super().startTest(test)
        self.started = time.perf_counter()
        self.current = {"id": test.id(), "class_id": type(test).__module__ + "." + type(test).__qualname__,
                        "status": "running", "seconds": 0.0, "subtests": []}
        self.records.append(self.current)

    def _mark(self, test, status):
        if self.current is not None and self.current["id"] == test.id():
            self.current["status"] = status
        else:
            self.fixture_errors.append({"id": test.id(), "status": status})

    def addSuccess(self, test):
        super().addSuccess(test)
        self._mark(test, "success")

    def addError(self, test, err):
        super().addError(test, err)
        self._mark(test, "error")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._mark(test, "failure")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._mark(test, "skipped")

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self._mark(test, "expected_failure")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._mark(test, "unexpected_success")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        status = "success" if err is None else "failure" if issubclass(err[0], test.failureException) else "error"
        self.current["subtests"].append({"id": subtest.id(), "status": status})
        if err is not None:
            self._mark(test, status)

    def stopTest(self, test):
        if self.current is not None:
            self.current["seconds"] = round(time.perf_counter() - self.started, 6)
        super().stopTest(test)
        self.current = None
        self.checkpoint(self)


class TimedSuite(unittest.TestSuite):
    """Time fixture hooks while retaining the standard unittest lifecycle."""

    def _handleClassSetUp(self, test, result):
        changed = getattr(result, "_previousTestClass", None) is not type(test)
        started = time.perf_counter()
        try:
            super()._handleClassSetUp(test, result)
        finally:
            if changed:
                self._record_fixture(type(test), result, started)

    def _tearDownPreviousClass(self, test, result):
        previous = getattr(result, "_previousTestClass", None)
        changed = previous is not None and previous is not (type(test) if test is not None else None)
        started = time.perf_counter()
        try:
            super()._tearDownPreviousClass(test, result)
        finally:
            if changed:
                self._record_fixture(previous, result, started)

    @staticmethod
    def _record_fixture(cls, result, started):
        identity = cls.__module__ + "." + cls.__qualname__
        result.class_fixture_seconds[identity] = round(result.class_fixture_seconds.get(identity, 0.0)
                                                       + time.perf_counter() - started, 6)


def summarize_classes(records, fixtures=None):
    classes = {}
    for record in records:
        row = classes.setdefault(record["class_id"], {"tests": 0, "seconds": 0.0,
                                "test_seconds": 0.0, "fixture_seconds": 0.0, "statuses": {}})
        row["tests"] += 1
        row["seconds"] = round(row["seconds"] + record["seconds"], 6)
        row["test_seconds"] = row["seconds"]
        status = record["status"]
        row["statuses"][status] = row["statuses"].get(status, 0) + 1
    for identity, seconds in (fixtures or {}).items():
        row = classes.setdefault(identity, {"tests": 0, "seconds": 0.0,
                                 "test_seconds": 0.0, "fixture_seconds": 0.0, "statuses": {}})
        row["fixture_seconds"] = seconds
        row["seconds"] = round(row["test_seconds"] + seconds, 6)
    return classes


def execute_shard(plan, discovery, env, index, output, *, stream=None):
    receipt = {"schema": RESULT_SCHEMA, "plan_fingerprint": plan.get("fingerprint"),
               "environment": env, "discovery_digest": discovery.manifest["digest"],
               "shard_index": index, "status": "validation_error", "selected_ids": [],
               "tests": [], "classes": {}, "class_fixture_seconds": {}, "fixture_errors": [],
               "errors": [], "elapsed_seconds": 0.0}
    started = time.perf_counter()

    def save(result=None):
        if result is not None:
            receipt["tests"] = result.records
            receipt["fixture_errors"] = result.fixture_errors
            receipt["class_fixture_seconds"] = result.class_fixture_seconds
        receipt["classes"] = summarize_classes(receipt["tests"], receipt["class_fixture_seconds"])
        receipt["elapsed_seconds"] = round(time.perf_counter() - started, 6)
        write_json(output, receipt)

    result = None
    try:
        validate_plan(plan, discovery, env)
        require(type(index) is int and 0 <= index < plan["shard_count"], "Invalid shard index.")
        receipt["selected_ids"] = plan["shards"][index]["test_ids"]
        receipt["status"] = "running"
        save()
        result = TimedResult(unittest.runner._WritelnDecorator(stream or sys.stderr), True, 2, checkpoint=save)
        runner = unittest.TextTestRunner(stream=stream or sys.stderr, verbosity=2,
                                        resultclass=lambda *args, **kwargs: result)
        runner.run(TimedSuite(discovery.tests[identity] for identity in receipt["selected_ids"]))
        ids = [record["id"] for record in result.records]
        complete = Counter(ids) == Counter(receipt["selected_ids"])
        receipt["status"] = "success" if complete and result.wasSuccessful() and not result.fixture_errors else "failure"
    except (KeyboardInterrupt, SystemExit) as error:
        receipt["status"] = "cancelled"
        receipt["errors"].append(type(error).__name__)
    except Exception as error:
        receipt["errors"].append(type(error).__name__ + ": " + str(error))
        receipt["status"] = "validation_error" if result is None else "error"
    finally:
        save(result)
    return receipt


def verify_results(plan, discovery, env, results):
    validate_plan(plan, discovery, env)
    require(len(results) == plan["shard_count"], "Missing or extra shard result.")
    seen, covered = set(), []
    for receipt in results:
        require(isinstance(receipt, dict) and receipt.get("schema") == RESULT_SCHEMA, "Invalid shard result.")
        index = receipt.get("shard_index")
        require(type(index) is int and 0 <= index < plan["shard_count"] and index not in seen,
                "Duplicate, invalid or missing shard index.")
        seen.add(index)
        require(receipt.get("plan_fingerprint") == plan["fingerprint"]
                and digest(receipt.get("environment")) == digest(env)
                and receipt.get("discovery_digest") == discovery.manifest["digest"], "Stale shard result authority.")
        selected = plan["shards"][index]["test_ids"]
        require(receipt.get("selected_ids") == selected, "Shard result selected IDs differ from plan.")
        require(receipt.get("status") == "success" and receipt.get("fixture_errors") == []
                and receipt.get("errors") == [], "Failed, cancelled or incomplete shard.")
        require(type(receipt.get("elapsed_seconds")) in (int, float)
                and math.isfinite(receipt["elapsed_seconds"]) and receipt["elapsed_seconds"] >= 0,
                "Invalid shard duration.")
        fixtures = receipt.get("class_fixture_seconds")
        require(isinstance(fixtures, dict) and set(fixtures) <= set(plan["shards"][index]["class_ids"])
                and all(type(value) in (int, float) and math.isfinite(value) and value >= 0
                        for value in fixtures.values()), "Invalid class fixture duration.")
        records = receipt.get("tests")
        require(isinstance(records, list), "Missing executed-test records.")
        for record in records:
            require(isinstance(record, dict) and set(record) == {"id", "class_id", "status", "seconds", "subtests"},
                    "Malformed executed-test record.")
            require(record["id"] in discovery.tests, "Extra executed test.")
            expected_class = type(discovery.tests[record["id"]]).__module__ + "." + type(discovery.tests[record["id"]]).__qualname__
            require(record["class_id"] == expected_class and record["status"] in SUCCESS,
                    "Wrong class or unsuccessful test result.")
            require(type(record["seconds"]) in (int, float) and math.isfinite(record["seconds"])
                    and record["seconds"] >= 0, "Invalid test duration.")
            require(isinstance(record["subtests"], list) and all(isinstance(item, dict)
                    and item.get("status") in SUCCESS for item in record["subtests"]), "Failed or malformed subtest.")
        ids = [record["id"] for record in records]
        require(Counter(ids) == Counter(selected), "Executed tests missing, extra or duplicated.")
        require(digest(receipt.get("classes")) == digest(summarize_classes(records, fixtures)), "Class accounting mismatch.")
        covered.extend(ids)
    require(Counter(covered) == Counter(discovery.tests.keys()), "Global test coverage is not exact and unique.")
    return {"schema": ACCOUNTING_SCHEMA, "status": "pass", "environment": env,
            "revision": env["revision"], "python_version": env["python"],
            "total_tests": len(covered), "shard_count": plan["shard_count"],
            "shard_seconds": {str(item["shard_index"]): item["elapsed_seconds"] for item in results},
            "plan_fingerprint": plan["fingerprint"], "discovery_digest": discovery.manifest["digest"],
            "expected_shards": plan["shard_count"], "verified_shards": sorted(seen),
            "discovered_count": len(discovery.tests), "executed_count": len(covered),
            "executed_ids": sorted(covered), "result_digests": sorted(digest(item) for item in results)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    plan_args = commands.add_parser("plan")
    plan_args.add_argument("--start-directory", default="tests")
    plan_args.add_argument("--pattern", default="test*.py")
    plan_args.add_argument("--shards", type=int, default=5)
    plan_args.add_argument("--weights", type=Path, default=WEIGHTS)
    plan_args.add_argument("--output", type=Path, required=True)
    for command in ("run", "verify"):
        subparser = commands.add_parser(command)
        subparser.add_argument("--plan", type=Path, required=True)
        subparser.add_argument("--output", type=Path, required=True)
        if command == "run":
            subparser.add_argument("--shard", type=int, required=True)
        else:
            subparser.add_argument("--result", type=Path, action="append", default=[])
    args = parser.parse_args(argv)
    failure = {"schema": ACCOUNTING_SCHEMA if args.command == "verify" else RESULT_SCHEMA,
               "status": "validation_error", "errors": []}
    protected = [getattr(args, "plan", None), *getattr(args, "result", [])]
    if any(path is not None and path.resolve() == args.output.resolve() for path in protected):
        parser.error("Output cannot overwrite a plan or result input.")
    previous = signal.getsignal(signal.SIGTERM)

    def interrupted(signum, frame):
        raise KeyboardInterrupt("SIGTERM")

    signal.signal(signal.SIGTERM, interrupted)
    try:
        env = environment(args.root)
        if args.command == "plan":
            found = discover(args.root, args.start_directory, args.pattern)
            output = make_plan(found, env, args.shards, read_json(args.weights))
            write_json(args.output, output, max_bytes=PLAN_MAX_BYTES)
        else:
            plan = read_json(args.plan, max_bytes=PLAN_MAX_BYTES)
            found = discover(args.root, plan["discovery"]["start_directory"], plan["discovery"]["pattern"])
            if args.command == "run":
                output = execute_shard(plan, found, env, args.shard, args.output)
            else:
                output = verify_results(plan, found, env, [read_json(path) for path in args.result])
                write_json(args.output, output)
        print(json.dumps({"command": args.command, "status": output.get("status", "planned"),
                          "output": str(args.output), "revision": env["revision"], "python": env["python"]}))
        return 0 if output.get("status", "success") in {"success", "pass"} else 1
    except (Exception, KeyboardInterrupt) as error:
        if isinstance(error, KeyboardInterrupt):
            failure["status"] = "cancelled"
        if args.command == "verify":
            failure["status"] = "fail"
        failure["errors"].append(type(error).__name__ + ": " + str(error))
        write_json(args.output, failure)
        print(failure["errors"][0], file=sys.stderr)
        return 1
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    raise SystemExit(main())
