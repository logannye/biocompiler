"""Fresh discovery and exact shard accounting cannot be replaced by saved PASS."""

import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import test_shards as sharding


ENV = {"revision": "a" * 40, "python": "3.11.16", "implementation": "CPython"}


def passing(self):
    self.assertTrue(True)


def fixture(groups=None):
    groups = groups or [[passing, passing], [passing], [passing, passing]]
    tests, classes = {}, {}
    for index, methods in enumerate(groups):
        cls = type("ShardFixture" + str(index), (unittest.TestCase,),
                   {"__module__": __name__, **{"test_" + str(offset): method
                    for offset, method in enumerate(methods)}})
        identities = []
        for name in sorted(key for key in cls.__dict__ if key.startswith("test_")):
            test = cls(name)
            tests[test.id()] = test
            identities.append(test.id())
        classes[cls.__module__ + "." + cls.__qualname__] = identities
    manifest = {"start_directory": "tests", "pattern": "test*.py", "test_ids": sorted(tests),
                "classes": classes, "source_files": {"tests/fixture.py": "b" * 64}}
    manifest["digest"] = sharding.digest(manifest)
    return sharding.Discovery(tests, manifest)


def repin(plan):
    plan["fingerprint"] = sharding.digest({key: value for key, value in plan.items() if key != "fingerprint"})
    return plan


class TestShardAccountingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def execute(self, found, plan, index):
        return sharding.execute_shard(plan, found, ENV, index,
                                      self.root / ("result-" + str(index) + ".json"), stream=io.StringIO())

    def test_deterministic_balancing_preserves_classes_and_includes_new_tests(self):
        found = fixture()
        class_ids = list(found.manifest["classes"])
        weights = {"classes": {class_ids[0]: {"tests": 1, "seconds": 30}}}
        first = sharding.make_plan(found, ENV, 5, weights)
        self.assertEqual(first, sharding.make_plan(found, ENV, 5, weights))
        self.assertEqual(len(first["shards"]), 5)
        ids = [identity for shard in first["shards"] for identity in shard["test_ids"]]
        self.assertCountEqual(ids, found.tests)
        self.assertEqual(len(ids), len(set(ids)))
        owner = next(shard for shard in first["shards"] if class_ids[0] in shard["class_ids"])
        self.assertEqual(owner["estimated_seconds"], 32.0)
        self.assertTrue(set(found.manifest["classes"][class_ids[0]]) <= set(owner["test_ids"]))

    def test_every_shard_including_empty_shards_must_finish_for_exact_accounting(self):
        found = fixture()
        plan = sharding.make_plan(found, ENV, 5)
        results = [self.execute(found, plan, index) for index in range(5)]
        checked = sharding.verify_results(plan, found, ENV, results)
        self.assertEqual(checked["status"], "pass")
        self.assertEqual(checked["total_tests"], 5)
        self.assertEqual(checked["shard_count"], 5)
        self.assertEqual(checked["revision"], ENV["revision"])
        self.assertEqual(checked["python_version"], ENV["python"])
        self.assertEqual(checked["executed_ids"], sorted(found.tests))
        self.assertTrue(all((self.root / ("result-" + str(index) + ".json")).exists() for index in range(5)))

    def test_rehashed_plan_cannot_omit_duplicate_add_or_split_test_inventory(self):
        found = fixture()
        plan = sharding.make_plan(found, ENV, 2)
        for mode in ("omit", "duplicate", "extra", "split_class"):
            with self.subTest(mode=mode):
                mutant = copy.deepcopy(plan)
                owner = next(shard for shard in mutant["shards"] if shard["test_ids"])
                if mode == "omit":
                    removed = owner["class_ids"].pop()
                    owner["test_ids"] = [value for value in owner["test_ids"]
                                         if value not in found.manifest["classes"][removed]]
                elif mode == "duplicate":
                    owner["class_ids"].append(owner["class_ids"][0])
                    owner["test_ids"].extend(found.manifest["classes"][owner["class_ids"][0]])
                elif mode == "extra":
                    owner["test_ids"].append("undeclared.test")
                else:
                    owner["test_ids"].pop()
                with self.assertRaises(sharding.ShardError):
                    sharding.validate_plan(repin(mutant), found, ENV)

    def test_revision_python_source_content_and_new_test_make_plan_stale(self):
        found = fixture()
        plan = sharding.make_plan(found, ENV, 2)
        for environment in ({**ENV, "revision": "c" * 40}, {**ENV, "python": "3.14.7"}):
            with self.assertRaisesRegex(sharding.ShardError, "environment"):
                sharding.validate_plan(plan, found, environment)
        changed = fixture()
        changed.manifest["source_files"]["tests/fixture.py"] = "d" * 64
        with self.assertRaisesRegex(sharding.ShardError, "discovery"):
            sharding.validate_plan(plan, changed, ENV)
        with self.assertRaises(sharding.ShardError):
            sharding.validate_plan(plan, fixture([[passing] * 3]), ENV)

    def test_failed_test_and_failed_subtest_emit_artifacts_and_fail_aggregation(self):
        def failure(self):
            self.fail("intentional failure")

        def subtest_failure(self):
            with self.subTest(case=1):
                self.assertEqual(1, 2)

        for body in (failure, subtest_failure):
            with self.subTest(body=body.__name__):
                found = fixture([[body, passing]])
                plan = sharding.make_plan(found, ENV, 1)
                result = self.execute(found, plan, 0)
                self.assertEqual(result["status"], "failure")
                self.assertEqual(len(result["tests"]), 2)
                self.assertEqual(sharding.read_json(self.root / "result-0.json"), result)
                with self.assertRaisesRegex(sharding.ShardError, "Failed"):
                    sharding.verify_results(plan, found, ENV, [result])

    def test_class_fixture_runs_once_and_fixture_failure_cannot_hide_missing_tests(self):
        found = fixture([[passing, passing]])
        cls = type(next(iter(found.tests.values())))
        calls = []
        cls.setUpClass = classmethod(lambda cls: calls.append("setup"))
        cls.tearDownClass = classmethod(lambda cls: calls.append("teardown"))
        plan = sharding.make_plan(found, ENV, 1)
        result = self.execute(found, plan, 0)
        self.assertEqual(result["status"], "success")
        self.assertEqual(calls, ["setup", "teardown"])

        def broken(cls):
            raise RuntimeError("fixture failed")

        cls.setUpClass = classmethod(broken)
        result = self.execute(found, plan, 0)
        self.assertEqual(result["status"], "failure")
        self.assertTrue(result["fixture_errors"])
        with self.assertRaises(sharding.ShardError):
            sharding.verify_results(plan, found, ENV, [result])

    def test_cancelled_missing_and_duplicate_shards_are_rejected(self):
        def cancelled(self):
            raise KeyboardInterrupt("intentional cancellation")

        found = fixture([[cancelled], [passing]])
        plan = sharding.make_plan(found, ENV, 2)
        results = [self.execute(found, plan, index) for index in range(2)]
        self.assertIn("cancelled", [result["status"] for result in results])
        for invalid in (results, results[:1], [results[1], results[1]]):
            with self.assertRaises(sharding.ShardError):
                sharding.verify_results(plan, found, ENV, invalid)

    def test_success_labels_cannot_hide_missing_duplicated_or_failed_records(self):
        found = fixture()
        plan = sharding.make_plan(found, ENV, 1)
        original = self.execute(found, plan, 0)
        for mode in ("missing", "duplicate", "failed", "wrong_class", "stale", "subtest", "nan"):
            with self.subTest(mode=mode):
                result = copy.deepcopy(original)
                if mode == "missing":
                    result["tests"].pop()
                elif mode == "duplicate":
                    result["tests"].append(copy.deepcopy(result["tests"][0]))
                elif mode == "failed":
                    result["tests"][0]["status"] = "failure"
                elif mode == "wrong_class":
                    result["tests"][0]["class_id"] = "other.class"
                elif mode == "stale":
                    result["environment"]["revision"] = "c" * 40
                elif mode == "subtest":
                    result["tests"][0]["subtests"].append({"id": "case", "status": "failure"})
                else:
                    result["tests"][0]["seconds"] = float("nan")
                with self.assertRaises(sharding.ShardError):
                    sharding.verify_results(plan, found, ENV, [result])

    def test_skips_expected_failure_and_unexpected_success_preserve_unittest_semantics(self):
        @unittest.skip("explicit fixture skip")
        def skipped(self):
            self.fail("must not execute")

        @unittest.expectedFailure
        def expected(self):
            self.fail("expected")

        found = fixture([[skipped, expected]])
        plan = sharding.make_plan(found, ENV, 1)
        result = self.execute(found, plan, 0)
        self.assertEqual({record["status"] for record in result["tests"]}, {"skipped", "expected_failure"})
        self.assertEqual(sharding.verify_results(plan, found, ENV, [result])["status"], "pass")
        unexpected = unittest.expectedFailure(passing)
        found = fixture([[unexpected]])
        plan = sharding.make_plan(found, ENV, 1)
        result = self.execute(found, plan, 0)
        self.assertEqual(result["tests"][0]["status"], "unexpected_success")
        self.assertEqual(result["status"], "failure")
        del passing.__unittest_expecting_failure__

    def test_import_rejects_duplicate_json_keys_and_nonfinite_numbers(self):
        path = self.root / "bad.json"
        for content in ('{"shards": [], "shards": []}', '{"seconds":NaN}', '{"seconds":Infinity}'):
            path.write_text(content)
            with self.assertRaises(sharding.ShardError):
                sharding.read_json(path)

    def test_cli_re_discovers_for_runner_and_aggregator_and_writes_failure_receipt(self):
        found = fixture()
        plan_path = self.root / "plan.json"
        weights_path = self.root / "weights.json"
        weights_path.write_text('{}')
        with patch.object(sharding, "environment", return_value=ENV), \
             patch.object(sharding, "discover", return_value=found) as discovery, \
             patch("sys.stdout", io.StringIO()), patch("sys.stderr", io.StringIO()):
            self.assertEqual(sharding.main(["plan", "--shards", "1", "--weights", str(weights_path),
                                           "--output", str(plan_path)]), 0)
            result_path = self.root / "result.json"
            self.assertEqual(sharding.main(["run", "--plan", str(plan_path), "--shard", "0",
                                           "--output", str(result_path)]), 0)
            output_path = self.root / "accounting.json"
            self.assertEqual(sharding.main(["verify", "--plan", str(plan_path), "--result", str(result_path),
                                           "--output", str(output_path)]), 0)
            self.assertEqual(discovery.call_count, 3)
            self.assertEqual(json.loads(output_path.read_text())["status"], "pass")
            self.assertEqual(sharding.main(["verify", "--plan", str(plan_path), "--output", str(output_path)]), 1)
            self.assertEqual(json.loads(output_path.read_text())["status"], "fail")

    def test_discovery_import_errors_and_duplicate_ids_fail_before_planning(self):
        test = next(iter(fixture().tests.values()))
        with patch.object(unittest.TestLoader, "discover", return_value=unittest.TestSuite([test, test])):
            with self.assertRaisesRegex(sharding.ShardError, "Duplicate discovered"):
                sharding.discover(sharding.ROOT)
        loader = unittest.TestLoader()
        loader.errors = ["deliberate import failure"]
        with patch.object(unittest, "TestLoader", return_value=loader), \
             patch.object(loader, "discover", return_value=unittest.TestSuite()):
            with self.assertRaisesRegex(sharding.ShardError, "Discovery failed"):
                sharding.discover(sharding.ROOT)


if __name__ == "__main__":
    unittest.main()
