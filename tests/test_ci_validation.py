"""Missing or non-successful CI work must never produce a green merge gate."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import ci_validation as ci


class ValidationGateTests(unittest.TestCase):
    def fixture(self):
        expected = {"revision": "a" * 40, "run_id": "123", "run_attempt": "2"}
        needs = {job: {"result": "success"} for job in ci.REQUIRED_NEEDS}
        receipts = [{"schema_version": "biocompiler.ci_job_receipt.v0.1", **expected,
                     "job": job, "variant": variant, "status": "success",
                     "system": ci.CORE_PLATFORMS.get(variant, ("Linux", "x86_64"))[0],
                     "machine": ci.CORE_PLATFORMS.get(variant, ("Linux", "x86_64"))[1],
                     "python_version": variant + ".7" if variant in ci.PYTHONS else "3.12.1"}
                    for job, variant in sorted(ci.EXPECTED_RECEIPTS)]
        accounting = [{"schema": "biocompiler.unittest_shard_accounting.v1",
                       "revision": expected["revision"], "python_version": version + ".7",
                       "status": "pass", "total_tests": 10, "shard_count": 5,
                       "expected_shards": 5, "verified_shards": list(range(5)),
                       "discovered_count": 10, "executed_count": 10,
                       "executed_ids": ["tests.test_" + str(index) for index in range(10)],
                       "shard_seconds": {str(index): 10.0 for index in range(5)},
                       "result_digests": [str(index) * 64 for index in range(5)],
                       "plan_fingerprint": "c" * 64,
                       "discovery_digest": "b" * 64} for version in ci.PYTHONS]
        return needs, receipts, accounting, expected

    def test_requires_independent_job_outcomes_despite_success_receipts(self):
        for state in ("failure", "cancelled", "skipped", "in_progress", None):
            with self.subTest(state=state):
                args = self.fixture()
                args[0]["unit-tests"]["result"] = state
                result = ci.validate(*args)
                self.assertEqual(result["status"], "fail")
                self.assertIn("prerequisite_not_successful:unit-tests", result["problems"])

    def test_all_required_jobs_and_variants_must_exist_exactly_once(self):
        self.assertEqual(ci.validate(*self.fixture())["status"], "pass")
        for mutation in ("missing_job", "unexpected_job", "missing_receipt", "duplicate_receipt",
                         "missing_python", "duplicate_python", "empty_tests", "missing_shard"):
            with self.subTest(mutation=mutation):
                needs, receipts, accounts, authority = self.fixture()
                if mutation == "missing_job":
                    needs.pop("installed-architecture")
                elif mutation == "unexpected_job":
                    needs["unregistered"] = {"result": "success"}
                elif mutation == "missing_receipt":
                    receipts.pop()
                elif mutation == "duplicate_receipt":
                    receipts.append(deepcopy(receipts[0]))
                elif mutation == "missing_python":
                    accounts.pop()
                elif mutation == "duplicate_python":
                    accounts.append(deepcopy(accounts[0]))
                elif mutation == "empty_tests":
                    accounts[0]["total_tests"] = 0
                else:
                    accounts[0]["shard_count"] = 4
                self.assertEqual(ci.validate(needs, receipts, accounts, authority)["status"], "fail")

    def test_stale_revision_run_python_or_accounting_cannot_pass(self):
        for field, value in (("revision", "c" * 40), ("run_id", "124"),
                             ("run_attempt", "3"), ("python_version", "3.9.0")):
            with self.subTest(field=field):
                args = self.fixture()
                target = next(item for item in args[1] if item["variant"] in ci.PYTHONS)
                target[field] = value
                self.assertEqual(ci.validate(*args)["status"], "fail")
        for change in ({"revision": "d" * 40}, {"status": "fail"}, {"python_version": "3.10.1"}):
            args = self.fixture()
            args[2][0].update(change)
            self.assertEqual(ci.validate(*args)["status"], "fail")

    def test_preserved_success_from_same_run_retry_requires_real_job_success(self):
        args = self.fixture()
        args[1][0]["run_attempt"] = "1"
        self.assertEqual(ci.validate(*args)["status"], "pass")
        args[0][args[1][0]["job"]]["result"] = "cancelled"
        self.assertEqual(ci.validate(*args)["status"], "fail")

    def test_accounting_must_retain_complete_inventory_authority_and_timings(self):
        for field, value in (("schema", "unknown"), ("executed_ids", []),
                             ("executed_ids", ["repeated"] * 10), ("executed_count", 9),
                             ("discovered_count", 9), ("verified_shards", [0, 1, 2, 3]),
                             ("result_digests", []), ("plan_fingerprint", ""),
                             ("discovery_digest", None), ("shard_seconds", {"0": 1}),
                             ("shard_seconds", {str(index): float("nan") for index in range(5)})):
            with self.subTest(field=field, value=value):
                args = self.fixture()
                args[2][0][field] = value
                self.assertEqual(ci.validate(*args)["status"], "fail")

    def test_workflow_registry_detects_unaccounted_new_jobs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ci.yml"
            base = "name: Test\njobs:\n" + "".join("  " + key + ":\n    runs-on: ubuntu-latest\n"
                for key in sorted(ci.REQUIRED_NEEDS | {"validation"}))
            path.write_text(base)
            self.assertEqual(ci.workflow_jobs(path), ci.REQUIRED_NEEDS | {"validation"})
            for extra in ("  forgotten_job:\n    runs-on: ubuntu-latest\n", "  inline: {}\n", "  validation:\n"):
                path.write_text(base + extra)
                with self.assertRaises(ValueError):
                    ci.workflow_jobs(path)

    def test_forged_start_identity_and_wrong_runtime_are_rejected(self):
        authority = self.fixture()[3]
        with patch.dict("os.environ", {"GITHUB_JOB": "installed-executable"}), \
             patch.object(ci.platform, "python_version", return_value="3.11.7"):
            start = ci.start_job("installed-executable", "3.11", authority)
            receipt = ci.finish_job(start, authority)
            self.assertEqual(receipt["status"], "success")
            self.assertGreaterEqual(receipt["duration_seconds"], 0)
            with self.assertRaises(ValueError):
                ci.finish_job({**start, "revision": "wrong"}, authority)
            with self.assertRaises(ValueError):
                ci.start_job("installed-executable", "3.14", authority)

    def test_duplicate_json_keys_and_non_object_receipts_cannot_hide_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "receipt.json"
            path.write_text('{"status":"fail","status":"success"}')
            with self.assertRaises(ValueError):
                ci.read_json(path)
            path.write_text('{"duration_seconds":NaN}')
            with self.assertRaises(ValueError):
                ci.read_json(path)
            path.write_text(json.dumps({"status": "success"}))
            self.assertEqual(ci.read_json(path), {"status": "success"})
        args = self.fixture()
        args[1].append([])
        args[2].append(None)
        self.assertEqual(ci.validate(*args)["status"], "fail")

    def test_native_platform_must_match_its_registered_variant(self):
        args = self.fixture()
        native = next(item for item in args[1] if item["variant"] == "macos-arm64")
        native["machine"] = "x86_64"
        self.assertIn("wrong_core_platform:('ocaml-core', 'macos-arm64')", ci.validate(*args)["problems"])
        with patch.dict("os.environ", {"GITHUB_JOB": "ocaml-core"}), \
             patch.object(ci.platform, "system", return_value="Darwin"), \
             patch.object(ci.platform, "machine", return_value="x86_64"):
            with self.assertRaises(ValueError):
                ci.start_job("ocaml-core", "macos-arm64", args[3])


if __name__ == "__main__":
    unittest.main()
