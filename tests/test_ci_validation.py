"""Missing or non-successful CI work must never produce a green merge gate."""

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import ci_validation as ci


class ValidationGateTests(unittest.TestCase):
    def test_prebuilt_material_requires_assembly_every_owned_slot_and_comparison(self):
        jobs = {"policy-prebuilt-sdk", "policy-prebuilt-installed", "policy-prebuilt-reproducibility"}
        self.assertTrue(jobs <= ci.REQUIRED_NEEDS)
        expected = {(job, "cross-platform") for job in jobs - {"policy-prebuilt-installed"}}
        expected |= {("policy-prebuilt-installed", variant) for variant in ci.REALIZATION_VARIANTS}
        self.assertEqual({pair for pair in ci.EXPECTED_RECEIPTS if pair[0] in jobs}, expected)
        for pair in expected:
            for mutation in ("missing", "duplicate", "failed_job", "skipped_job", "stale_run"):
                with self.subTest(pair=pair, mutation=mutation):
                    needs, receipts, accounts, authority = self.fixture()
                    receipt = next(row for row in receipts if (row["job"], row["variant"]) == pair)
                    if mutation == "missing":
                        receipts.remove(receipt)
                    elif mutation == "duplicate":
                        receipts.append(deepcopy(receipt))
                    elif mutation in {"failed_job", "skipped_job"}:
                        needs[pair[0]]["result"] = "failure" if mutation == "failed_job" else "skipped"
                    else:
                        receipt["run_id"] = "other"
                    self.assertEqual(ci.validate(needs, receipts, accounts, authority)["status"], "fail")

    def test_prebuilt_slot_cannot_claim_another_python_or_native_platform(self):
        for variant in ci.REALIZATION_VARIANTS:
            for field, value in (("python_version", "3.10.0"), ("system", "wrong"), ("machine", "wrong")):
                with self.subTest(variant=variant, field=field):
                    args = self.fixture()
                    receipt = next(row for row in args[1] if row["job"] == "policy-prebuilt-installed" and row["variant"] == variant)
                    receipt[field] = value
                    self.assertEqual(ci.validate(*args)["status"], "fail")
        with patch.dict("os.environ", {"GITHUB_JOB": "policy-prebuilt-installed"}), \
             patch.object(ci.platform, "system", return_value="Linux"), \
             patch.object(ci.platform, "machine", return_value="x86_64"), \
             patch.object(ci.platform, "python_version", return_value="3.11.7"):
            authority = self.fixture()[3]
            self.assertEqual(ci.start_job("policy-prebuilt-installed", "linux-x86_64-py3.11", authority)["job"],
                             "policy-prebuilt-installed")
            with self.assertRaises(ValueError):
                ci.start_job("policy-prebuilt-installed", "linux-x86_64-py3.14", authority)

    def fixture(self):
        expected = {"revision": "a" * 40, "run_id": "123", "run_attempt": "2"}
        needs = {job: {"result": "success"} for job in ci.REQUIRED_NEEDS}
        receipts = [{"schema_version": "biocompiler.ci_job_receipt.v0.1", **expected,
                     "job": job, "variant": variant, "status": "success",
                     "system": ci.REALIZATION_VARIANTS.get(variant, ci.CORE_PLATFORMS.get(variant, ("Linux", "x86_64")))[0],
                     "machine": ci.REALIZATION_VARIANTS.get(variant, ci.CORE_PLATFORMS.get(variant, ("Linux", "x86_64")))[1],
                     "python_version": (ci.REALIZATION_VARIANTS[variant][2] + ".7" if variant in ci.REALIZATION_VARIANTS
                                        else variant + ".7" if variant in ci.PYTHONS else "3.12.1")}
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

    def test_architecture_core_comparison_requires_success_and_exact_receipt(self):
        job = "architecture-core-reproducibility"
        self.assertIn(job, ci.REQUIRED_NEEDS)
        self.assertIn((job, "cross-platform"), ci.EXPECTED_RECEIPTS)
        for mutation in ("missing_job", "failure", "skipped", "cancelled", "missing_receipt",
                         "duplicate_receipt", "wrong_variant", "stale_revision"):
            with self.subTest(mutation=mutation):
                needs, receipts, accounts, authority = self.fixture()
                receipt = next(item for item in receipts if item["job"] == job)
                if mutation == "missing_job":
                    needs.pop(job)
                elif mutation in {"failure", "skipped", "cancelled"}:
                    needs[job]["result"] = mutation
                elif mutation == "missing_receipt":
                    receipts.remove(receipt)
                elif mutation == "duplicate_receipt":
                    receipts.append(deepcopy(receipt))
                elif mutation == "wrong_variant":
                    receipt["variant"] = "cross-python"
                else:
                    receipt["revision"] = "f" * 40
                self.assertEqual(ci.validate(needs, receipts, accounts, authority)["status"], "fail")

    def test_realization_matrix_requires_both_pythons_on_both_native_platforms(self):
        expected = {f"{name}-py{version}" for name in ci.CORE_PLATFORMS for version in ci.PYTHONS}
        self.assertEqual(set(ci.REALIZATION_VARIANTS), expected)
        for variant in expected:
            for field, invalid in (("system", "wrong"), ("machine", "wrong"), ("python_version", "3.10.9")):
                with self.subTest(variant=variant, field=field):
                    args = self.fixture()
                    receipt = next(row for row in args[1] if row["job"] == "realization-conformance" and row["variant"] == variant)
                    receipt[field] = invalid
                    self.assertIn("wrong_realization_runtime:" + str(("realization-conformance", variant)),
                                  ci.validate(*args)["problems"])
        authority = self.fixture()[3]
        with patch.dict("os.environ", {"GITHUB_JOB": "realization-conformance"}), \
             patch.object(ci.platform, "system", return_value="Darwin"), \
             patch.object(ci.platform, "machine", return_value="arm64"), \
             patch.object(ci.platform, "python_version", return_value="3.11.7"):
            self.assertEqual(ci.start_job("realization-conformance", "macos-arm64-py3.11", authority)["variant"],
                             "macos-arm64-py3.11")
            with self.assertRaisesRegex(ValueError, "runtime differs"):
                ci.start_job("realization-conformance", "macos-arm64-py3.14", authority)

    def test_secondary_python_cannot_relabel_native_job_runtime(self):
        authority = self.fixture()[3]
        with patch.dict("os.environ", {"GITHUB_JOB": "ocaml-core"}), \
             patch.object(ci.platform, "system", return_value="Linux"), \
             patch.object(ci.platform, "machine", return_value="x86_64"), \
             patch.object(ci.platform, "python_version", return_value="3.11.7") as version:
            start = ci.start_job("ocaml-core", "linux-x86_64", authority)
            version.return_value = "3.14.0"
            with self.assertRaisesRegex(ValueError, "runtime changed"):
                ci.finish_job(start, authority)

    def test_complete_workflow_campaign_is_required_before_matrix_receipts(self):
        text = (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text()
        matrix = text.split("\n  realization-conformance:\n", 1)[1].split("\n  realization-core-reproducibility:", 1)[0]
        commands = ["tools/check_realization_protocol.py", "tools/check_realization_routing.py",
                    "tools/check_native_workflow.py"]
        for command in commands:
            self.assertIn(command, matrix)
            self.assertLess(matrix.index(command), matrix.index("Record successful complete conformance"))
        for binding in ("--core-sha256", "--verify-sha256", "--native-root", "--platform ${{ matrix.platform }}"):
            self.assertIn(binding, matrix)
        comparison = text.split("\n  realization-core-reproducibility:\n", 1)[1].split("\n  studio-typescript:", 1)[0]
        for command in ("tools/check_realization_reproducibility.py", "tools/check_workflow_reproducibility.py"):
            self.assertIn(command, comparison)
            self.assertLess(comparison.index(command), comparison.index("Record successful complete comparison"))
        self.assertIn("generated/realization-reproducibility/*.json", comparison)

    def test_checked_in_workflow_registers_cross_platform_architecture_gate(self):
        workflow = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
        self.assertEqual(ci.workflow_jobs(workflow), ci.REQUIRED_NEEDS | {"validation"})
        text = workflow.read_text(encoding="utf-8")
        comparison = text.split("\n  architecture-core-reproducibility:\n", 1)[1].split("\n  studio-typescript:", 1)[0]
        self.assertIn("    needs: ocaml-core\n", comparison)
        for target in ("artifacts/core/linux-x86_64", "artifacts/core/macos-arm64",
                       "--root artifacts/core --output generated/core-reproducibility/receipt.json"):
            self.assertIn(target, comparison)
        self.assertIn("      - architecture-core-reproducibility\n", text.split("\n  validation:\n", 1)[1])
        native = text.split("\n  ocaml-core:\n", 1)[1].split("\n  architecture-core-reproducibility:\n", 1)[0]
        for version in ci.PYTHONS:
            self.assertIn("architecture-routing-" + version + ".json", native)
        self.assertIn("          update-environment: false\n", native)
        self.assertIn("${{ steps.routing_python314.outputs.python-path }}", native)


    def test_realization_campaigns_are_required_on_every_runtime_and_compared_whole(self):
        workflow = Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml"
        self.assertEqual(ci.workflow_jobs(workflow), ci.REQUIRED_NEEDS | {"validation"})
        text = workflow.read_text()
        matrix = text.split("\n  realization-conformance:\n", 1)[1].split("\n  realization-core-reproducibility:\n", 1)[0]
        self.assertIn("    needs: ocaml-core\n", matrix)
        for target in ci.CORE_PLATFORMS:
            self.assertEqual(matrix.count("            platform: " + target + "\n"), 2)
        for version in ci.PYTHONS:
            self.assertEqual(matrix.count('            python-version: "' + version + '"\n'), 2)
        for command in ("check_realization_binaries.py", "check_realization_protocol.py", "check_realization_routing.py"):
            self.assertIn(command, matrix)
        self.assertNotIn("--sample", matrix)
        self.assertNotIn("continue-on-error", matrix)
        self.assertIn("          fail-fast: false", matrix.replace("      fail-fast", "          fail-fast"))
        gate = text.split("\n  validation:\n", 1)[1]
        self.assertIn("      - realization-conformance\n", gate)
        self.assertIn("      - realization-core-reproducibility\n", gate)
        comparison = text.split("\n  realization-core-reproducibility:\n", 1)[1].split("\n  studio-typescript:\n", 1)[0]
        self.assertIn("needs: [ocaml-core, realization-conformance]", comparison)
        self.assertIn("check_realization_reproducibility.py", comparison)
        self.assertIn("--native-root artifacts/core", comparison)

    def test_policy_consumer_requires_offline_execution_and_all_four_comparisons(self):
        text = (Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml").read_text()
        self.assertEqual(text.count('--network required'), 2)
        self.assertNotIn('--network deferred', text)
        for version in ci.PYTHONS:
            self.assertIn(f'--producer-receipt "$GITHUB_WORKSPACE/generated/core/policy-material-{version}.json"', text)
            self.assertIn(f'generated/core/policy-consumer-{version}.log', text)
            for target in ci.CORE_PLATFORMS:
                self.assertIn(f'--compare artifacts/core/{target}/policy-consumer-{version}.json', text)
                self.assertIn(f'--producer-receipts artifacts/core/{target}/policy-material-{version}.json', text)
        self.assertIn('--output generated/core-reproducibility/policy-consumer-receipt.json', text)


if __name__ == "__main__":
    unittest.main()
