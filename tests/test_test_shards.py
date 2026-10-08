"""Fresh discovery and exact shard accounting cannot be replaced by saved PASS."""

import copy
import hashlib
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

    def test_complete_large_source_plan_roundtrips_and_executes_without_dropping_inventory(self):
        found = fixture([[passing]])
        # Model the growing content-addressed corpus with complete path/hash
        # entries, not padding or a smaller substitute test inventory.
        found.manifest["source_files"] = {
            f"tests/conformance/checked-pipeline-v1/{index:064x}.json": "b" * 64
            for index in range(120_000)
        }
        found.manifest["digest"] = sharding.digest({
            key: value for key, value in found.manifest.items() if key != "digest"})
        plan_path = self.root / "large-plan.json"
        weights_path = self.root / "weights.json"
        weights_path.write_text("{}")
        result_path = self.root / "result.json"
        accounting_path = self.root / "accounting.json"
        with patch.object(sharding, "environment", return_value=ENV), \
             patch.object(sharding, "discover", return_value=found), \
             patch("sys.stdout", io.StringIO()), patch("sys.stderr", io.StringIO()):
            self.assertEqual(sharding.main(["plan", "--shards", "1", "--weights", str(weights_path),
                                           "--output", str(plan_path)]), 0)
            self.assertGreater(plan_path.stat().st_size, sharding.JSON_MAX_BYTES)
            self.assertLessEqual(plan_path.stat().st_size, sharding.PLAN_MAX_BYTES)
            with self.assertRaisesRegex(sharding.ShardError, "input exceeds"):
                sharding.read_json(plan_path)
            saved = sharding.read_json(plan_path, max_bytes=sharding.PLAN_MAX_BYTES)
            self.assertEqual(saved["discovery"], found.manifest)
            sharding.validate_plan(saved, found, ENV)
            self.assertEqual(sharding.main(["run", "--plan", str(plan_path), "--shard", "0",
                                           "--output", str(result_path)]), 0)
            self.assertEqual(sharding.main(["verify", "--plan", str(plan_path), "--result", str(result_path),
                                           "--output", str(accounting_path)]), 0)
        accounting = sharding.read_json(accounting_path)
        self.assertEqual(accounting["executed_ids"], sorted(found.tests))
        self.assertEqual(accounting["discovery_digest"], found.manifest["digest"])

    def test_json_reader_and_atomic_writer_agree_at_exact_byte_boundary(self):
        path = self.root / "bounded.json"
        value = {"unicode": "é😀", "number": 1.0}
        expected = (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
        sharding.write_json(path, value, max_bytes=len(expected))
        self.assertEqual(path.read_bytes(), expected)
        self.assertEqual(sharding.read_json(path, max_bytes=len(expected)), value)
        with self.assertRaisesRegex(sharding.ShardError, "input exceeds"):
            sharding.read_json(path, max_bytes=len(expected) - 1)
        # A stale small stat result cannot bypass the actual bounded read.
        with patch.object(Path, "stat") as metadata:
            metadata.return_value.st_size = 0
            with self.assertRaisesRegex(sharding.ShardError, "input exceeds"):
                sharding.read_json(path, max_bytes=len(expected) - 1)
        with self.assertRaisesRegex(sharding.ShardError, "output exceeds"):
            sharding.write_json(path, value, max_bytes=len(expected) - 1)
        self.assertEqual(path.read_bytes(), expected)
        self.assertEqual(list(self.root.iterdir()), [path])

    def test_plan_writer_and_reader_reject_the_same_oversized_plan(self):
        found = fixture()
        plan_path = self.root / "plan.json"
        weights_path = self.root / "weights.json"
        weights_path.write_text("{}")
        sharding.write_json(plan_path, sharding.make_plan(found, ENV, 1))
        original_size = plan_path.stat().st_size
        output = self.root / "failure.json"
        with patch.object(sharding, "PLAN_MAX_BYTES", original_size - 1), \
             patch.object(sharding, "environment", return_value=ENV), \
             patch.object(sharding, "discover", return_value=found), \
             patch("sys.stdout", io.StringIO()), patch("sys.stderr", io.StringIO()):
            self.assertEqual(sharding.main(["plan", "--shards", "1", "--weights", str(weights_path),
                                           "--output", str(output)]), 1)
            self.assertIn("output exceeds", sharding.read_json(output)["errors"][0])
            self.assertEqual(sharding.main(["run", "--plan", str(plan_path), "--shard", "0",
                                           "--output", str(output)]), 1)
            self.assertIn("input exceeds", sharding.read_json(output)["errors"][0])

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


class PlanRuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "tests").mkdir()
        self.found = fixture()
        self.plan = sharding.make_plan(self.found, ENV, 2)
        self.path = self.root / "plan.json"

    def invoke(self, plan=None, *, minor="3.11", revision=None, sources=None, raw=None):
        self.path.write_text(json.dumps(self.plan if plan is None else plan) if raw is None else raw)
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sharding.subprocess, "check_output", return_value=revision or ENV["revision"]), \
             patch.object(sharding, "source_inventory", return_value=(self.found.manifest["source_files"]
                          if sources is None else sources)), \
             patch.object(sharding, "discover", side_effect=AssertionError("Selector imported tests")) as discover, \
             patch.object(sharding, "environment", side_effect=AssertionError("Selector used bootstrap runtime")) as env, \
             patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            status = sharding.main(["--root", str(self.root), "runtime", "--plan", str(self.path),
                                    "--python-minor", minor])
        discover.assert_not_called()
        env.assert_not_called()
        return status, stdout.getvalue(), stderr.getvalue()

    def reject(self, plan=None, *, message, **kwargs):
        status, stdout, stderr = self.invoke(plan, **kwargs)
        self.assertEqual(status, 1)
        self.assertEqual(stdout, "")
        self.assertIn(message, stderr)

    def repin_discovery(self, plan):
        manifest = plan["discovery"]
        manifest["digest"] = sharding.digest({key: value for key, value in manifest.items() if key != "digest"})
        return repin(plan)

    def test_selector_outputs_only_the_exact_planned_patch_without_bootstrap_runtime_or_discovery(self):
        for minor, version in (("3.11", "3.11.16"), ("3.14", "3.14.7")):
            with self.subTest(version=version):
                plan = copy.deepcopy(self.plan)
                plan["environment"]["python"] = version
                self.assertEqual(self.invoke(repin(plan), minor=minor), (0, version + "\n", ""))

    def test_real_patch_drift_still_rejects_before_selection_and_exact_environment_still_runs(self):
        self.assertEqual(self.invoke(), (0, "3.11.16\n", ""))
        output = self.root / "result.json"
        drifted = sharding.execute_shard(self.plan, self.found, {**ENV, "python": "3.11.17"}, 0,
                                         output, stream=io.StringIO())
        self.assertEqual(drifted["status"], "validation_error")
        self.assertEqual(drifted["errors"], ["ShardError: Stale plan revision or Python environment."])
        self.assertEqual(drifted["selected_ids"], [])
        self.assertEqual(drifted["tests"], [])
        exact = sharding.execute_shard(self.plan, self.found, ENV, 0, output, stream=io.StringIO())
        self.assertEqual(exact["status"], "success")
        self.assertEqual(exact["selected_ids"], self.plan["shards"][0]["test_ids"])

    def test_rehashed_version_injections_ranges_suffixes_and_noncanonical_spellings_never_emit(self):
        values = [None, 31116, True, "", "3.11", "3.11.*", ">=3.11.16", "3.11.16 - 3.11.17",
                  "3.11.16\nother=value", "3.11.16\r", "3.11.16%0Aother=value", "3.11.16t",
                  "3.11.16rc1", "3.11.16+local", "3.011.16", "3.11.016", "03.11.16",
                  " 3.11.16", "3.11.16 ", "3.11.16$(echo injected)", "3.11.16\x00", "3.11.1000"]
        for value in values:
            with self.subTest(value=value):
                plan = copy.deepcopy(self.plan)
                plan["environment"]["python"] = value
                self.reject(repin(plan), message="one canonical stable full version")

    def test_requested_minor_must_be_canonical_and_match_the_planned_cohort(self):
        for minor in ("3", "3.11.16", "3.011", "3.11\n", "3.11.*", "pypy3.11", "4.11"):
            with self.subTest(minor=minor):
                self.reject(minor=minor, message="Requested Python minor")
        self.reject(minor="3.14", message="minor differs from requested cohort")

    def test_closed_cpython_environment_and_exact_current_revision_are_required(self):
        for field, value, message in (("implementation", "PyPy", "must be CPython"),
                                      ("revision", "A" * 40, "Malformed plan revision"),
                                      ("revision", "a" * 39, "Malformed plan revision"),
                                      ("revision", "c" * 40, "Stale plan revision"),
                                      ("extra", "ignored", "Malformed plan runtime environment")):
            with self.subTest(field=field, value=value):
                plan = copy.deepcopy(self.plan)
                plan["environment"][field] = value
                self.reject(repin(plan), message=message)
        self.reject(revision="d" * 40, message="Stale plan revision")

    def test_plan_schema_fingerprint_and_closed_envelope_are_validated(self):
        self.reject([], message="Malformed shard plan")
        plan = copy.deepcopy(self.plan)
        plan["schema"] = "another_schema"
        self.reject(repin(plan), message="Unsupported shard plan schema")
        plan = copy.deepcopy(self.plan)
        plan["extra"] = True
        self.reject(repin(plan), message="Malformed shard plan")
        plan = copy.deepcopy(self.plan)
        plan["fingerprint"] = "0" * 64
        self.reject(plan, message="fingerprint mismatch")
        plan = copy.deepcopy(self.plan)
        plan["weights_digest"] = "not-a-digest"
        self.reject(repin(plan), message="Malformed plan weights digest")

    def test_rehashed_discovery_shapes_and_inventories_are_checked_without_importing(self):
        for mode, message in (("extra", "Malformed plan discovery"), ("digest", "discovery digest mismatch"),
                              ("duplicate_id", "sorted and unique"), ("class_omission", "class inventory"),
                              ("bad_source_pin", "Malformed plan source inventory"),
                              ("bad_source_path", "Malformed plan source inventory"),
                              ("bad_pattern", "Malformed plan discovery pattern")):
            with self.subTest(mode=mode):
                plan = copy.deepcopy(self.plan)
                manifest = plan["discovery"]
                if mode == "extra": manifest["extra"] = True
                elif mode == "digest": manifest["digest"] = "0" * 64
                elif mode == "duplicate_id": manifest["test_ids"].append(manifest["test_ids"][0])
                elif mode == "class_omission": manifest["classes"].pop(next(iter(manifest["classes"])))
                elif mode == "bad_source_pin": manifest["source_files"]["tests/fixture.py"] = "bad"
                elif mode == "bad_source_path": manifest["source_files"]["../outside.py"] = "b" * 64
                else: manifest["pattern"] = "../test*.py"
                self.reject(repin(plan) if mode == "digest" else self.repin_discovery(plan), message=message)

    def test_rehashed_shard_omissions_duplicates_and_extra_fields_are_rejected(self):
        for mode, message in (("omit", "omitted, added, reordered or split"),
                              ("duplicate", "Classes missing or duplicated"),
                              ("extra", "Malformed shard assignment")):
            with self.subTest(mode=mode):
                plan = copy.deepcopy(self.plan)
                shard = plan["shards"][0]
                if mode == "omit": shard["test_ids"].pop()
                elif mode == "duplicate":
                    shard["class_ids"].append(shard["class_ids"][0])
                    shard["test_ids"].extend(plan["discovery"]["classes"][shard["class_ids"][0]])
                else: shard["extra"] = True
                self.reject(repin(plan), message=message if mode != "duplicate" else "Tests missing, extra or duplicated")

    def test_rehashed_source_changes_and_omissions_cannot_select_a_runtime(self):
        for mode in ("changed", "omitted", "extra"):
            with self.subTest(mode=mode):
                plan = copy.deepcopy(self.plan)
                if mode == "changed": plan["discovery"]["source_files"]["tests/fixture.py"] = "c" * 64
                elif mode == "omitted":
                    plan["discovery"]["source_files"] = {"another.py": "b" * 64}
                else: plan["discovery"]["source_files"]["another.py"] = "b" * 64
                self.reject(self.repin_discovery(plan), message="Stale plan source inventory")
        self.reject(sources={"tests/fixture.py": "d" * 64}, message="Stale plan source inventory")

    def test_absolute_traversing_and_symlink_escaped_discovery_directories_are_rejected(self):
        for start in ("../tests", "/tmp", "tests/../tests", "tests//nested", "tests\\nested", "tests/."):
            with self.subTest(start=start):
                plan = copy.deepcopy(self.plan)
                plan["discovery"]["start_directory"] = start
                self.reject(self.repin_discovery(plan), message="canonical relative path")
        with tempfile.TemporaryDirectory() as outside:
            (self.root / "escape").symlink_to(outside, target_is_directory=True)
            plan = copy.deepcopy(self.plan)
            plan["discovery"]["start_directory"] = "escape"
            self.reject(self.repin_discovery(plan), message="inside the checkout")

    def test_bounded_json_ingress_rejects_duplicate_nonfinite_malformed_and_oversized_data(self):
        for raw, message in (("{", "JSONDecodeError"), ('{"schema":1,"schema":2}', "Duplicate JSON key"),
                             ('{"x":NaN}', "Nonfinite JSON number")):
            with self.subTest(raw=raw):
                self.reject(raw=raw, message=message)
        with patch.object(sharding, "PLAN_MAX_BYTES", 100):
            self.reject(message="input exceeds")

    def test_actual_current_source_bytes_are_hashed_but_test_module_is_never_imported(self):
        source = self.root / "tests/fixture.py"
        source.write_text('raise RuntimeError("must not import this test module")\n')
        tool = self.root / "tools/test_shards.py"
        tool.parent.mkdir()
        tool.write_text("# inert source inventory fixture\n")
        plan = copy.deepcopy(self.plan)
        plan["discovery"]["source_files"] = {
            path.relative_to(self.root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (source, tool)}
        self.repin_discovery(plan)

        def git(command, **kwargs):
            if command == ["git", "rev-parse", "HEAD"]: return ENV["revision"]
            self.assertEqual(command, ["git", "ls-files", "-z"])
            return b"tests/fixture.py\0tools/test_shards.py\0"

        with patch.object(sharding, "__file__", str(tool)), \
             patch.object(sharding.subprocess, "check_output", side_effect=git), \
             patch.object(sharding, "discover", side_effect=AssertionError("Imported test module")):
            self.assertEqual(sharding.plan_runtime(plan, self.root, "3.11"), "3.11.16")
            source.write_text(source.read_text() + "# changed current bytes\n")
            with self.assertRaisesRegex(sharding.ShardError, "Stale plan source inventory"):
                sharding.plan_runtime(plan, self.root, "3.11")


if __name__ == "__main__":
    unittest.main()
