"""Pure Python adversaries for hosted operational campaign receipts and wiring."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests import test_core_policy_operational as peers

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("policy_operational_campaign_test_tool", ROOT / "tools/check_policy_operational.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
IDENTITY = {"revision": "1" * 40, "head_revision": "2" * 40, "run_id": "98765", "run_attempt": "2"}
FIXTURE = ROOT / "core/test/data/policy_operational_v01.json"


def observations(fixture):
    source = {"document": fixture["document"], "definitions": fixture["definitions"]}
    compiled = peers.result(source, "compile-policy")
    checked = {**source, "candidate": compiled["candidate"]}
    payload = {**checked, "timeline": fixture["timeline"]}
    executed = peers.result(payload, "execute-policy")
    execution = executed["report"]["execution"]
    execution["frames"] = [{"time": str(tick), "actions": []} for tick in range(4)]
    execution["attempts"] = [
        {"id": row["id"], "binding": {"encounter": row["encounter"], "generation": 0},
         "subject": row["subject"], "status": row["status"]} for row in fixture["expected_attempts"]]
    execution["usage"]["attempts"] = len(execution["attempts"])
    executed["report_fingerprint"] = peers.digest(executed["report"])
    outcomes = {"compile": compiled, "check": peers.result(checked, "check-policy-lowering"),
                "execute-core": executed, "execute-verify": deepcopy(executed), "replay-verify": deepcopy(executed),
                "compile-cli": deepcopy(compiled), "execute-cli": deepcopy(executed), "replay-cli": deepcopy(executed)}
    for name, codes in TOOL.NEGATIVE_CODES.items():
        outcomes[name] = {"status": "error", "diagnostics": [{"code": sorted(codes)[0], "message": "Expected native rejection", "path": "/document"}]}
    for name, field, value, reason in (
        ("wrong-feedback-target", "subject", "target-2", "identity_mismatch"),
        ("wrong-feedback-attempt", "attempt", "attempt/999", "unknown_attempt"),
    ):
        modified = deepcopy(payload)
        modified["timeline"]["feedback"][0][field] = value
        outcome = deepcopy(executed)
        outcome["request_fingerprint"] = peers.digest(modified)
        outcome["report"]["execution"]["timeline_digest"] = peers.digest(modified["timeline"])
        outcome["report"]["execution"]["attempts"][0]["status"] = "timed_out"
        outcome["report"]["execution"]["frames"][2]["actions"] = [
            {"kind": "feedback_rejected", "microstep": 0,
             "detail": {"id": fixture["timeline"]["feedback"][0]["id"], "attempt": "attempt/1", "reason": reason}}]
        outcome["report_fingerprint"] = peers.digest(outcome["report"])
        outcomes[name] = outcome
    outcomes["forged-replay-cli"] = {"status": "error", "operation": "replay-execution-native",
                                      "message": "policy_execution_replay: Retained report differs"}
    outcomes["work-limit-cli"] = {"status": "error", "operation": "execute-native",
                                   "message": "policy_execution_work_limit: Work exhausted"}
    return [{"name": name, "result": outcomes[name]} for name in TOOL.CASE_NAMES]


class OperationalCampaignTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.native = self.root / "native"
        self.binaries = {}
        for system, folder, machine in (("Linux", "linux-x86_64", "x86_64"), ("Darwin", "macos-arm64", "arm64")):
            slot = self.native / folder
            slot.mkdir(parents=True)
            pins = {}
            for role in ("core", "verify"):
                binary = slot / ("biocompiler-" + role)
                binary.write_bytes(("nonexecutable test bytes: " + system + role).encode())
                pins[binary.name] = TOOL.digest_file(binary)
            (slot / "binaries.json").write_text(json.dumps({"revision": IDENTITY["revision"], "system": system,
                                                          "machine": machine, "sha256": pins}))
            self.binaries[system] = pins
        self.fixture = TOOL.checked_fixture(FIXTURE)
        self.paths = []
        self.receipts = []
        retained = observations(self.fixture)
        for system, machine in (("Linux", "x86_64"), ("Darwin", "arm64")):
            for minor in (11, 14):
                package = "/installed/biocompiler"
                origins = {name: package + "/" + name.rsplit(".", 1)[-1] + ".py"
                           for name in ("biocompiler.core_client", "biocompiler.core_policy", "biocompiler.core_policy_operational",
                                        "biocompiler.entrypoint", "biocompiler.policy.cli")}
                guard = {"status": "ok", "guard_active": True, "execution_guard_active": True,
                         "python": [3, minor], "executable": "/installed/python", "origins": origins}
                receipt = {"schema_version": TOOL.SCHEMA, **IDENTITY, "system": system, "machine": machine,
                           "python_version": f"3.{minor}.0", "fixture_sha256": TOOL.digest_file(FIXTURE),
                           "binary_sha256": self.binaries[system], "package": package, "parent_imports": origins,
                           "cli_guards": {name: deepcopy(guard) for name in TOOL.CLI_CASES},
                           "observations": deepcopy(retained), "observations_fingerprint": TOOL.canonical_digest(retained),
                           "python_semantic_authority": "forbidden"}
                self.receipts.append(receipt)
                self.paths.append(self.root / f"{system}-{minor}.json")
        self.write()

    def write(self):
        for path, receipt in zip(self.paths, self.receipts):
            path.write_text(json.dumps(receipt), encoding="utf-8")

    def compare(self, paths=None):
        with patch.object(TOOL, "source_identity", return_value=IDENTITY):
            return TOOL.compare(self.paths if paths is None else paths, self.native, FIXTURE)

    def test_all_four_exact_slots_rehash_complete_outputs_and_binaries(self):
        receipt = self.compare()
        self.assertEqual(receipt["status"], "pass")
        self.assertEqual(len(receipt["slots"]), 4)
        self.assertEqual(receipt["claim_scope"], "bounded_abstract_source_execution_only")
        # Earlier successful attempts of this exact run/revision remain usable.
        self.receipts[0]["run_attempt"] = "1"
        self.write()
        self.assertEqual(self.compare()["status"], "pass")

    def test_missing_duplicate_extra_or_redirected_slot_is_rejected(self):
        for paths in (self.paths[:3], [self.paths[0], self.paths[0], *self.paths[2:]], [*self.paths, self.paths[0]]):
            with self.subTest(paths=paths), self.assertRaises(AssertionError):
                self.compare(paths)
        redirected = self.root / "redirect.json"
        redirected.symlink_to(self.paths[0])
        with self.assertRaises(AssertionError):
            self.compare([redirected, *self.paths[1:]])

    def test_stale_source_run_platform_fixture_or_binary_authority_is_rejected(self):
        original = deepcopy(self.receipts[0])
        for field, value in (("revision", "0" * 40), ("head_revision", "0" * 40), ("run_id", "123"),
                             ("run_attempt", "3"), ("run_attempt", "0"), ("machine", "arm64"),
                             ("python_version", "3.12.0"), ("fixture_sha256", "0" * 64),
                             ("python_semantic_authority", "allowed"), ("binary_sha256", {})):
            self.receipts[0] = {**deepcopy(original), field: value}
            self.write()
            with self.subTest(field=field, value=value), self.assertRaises(AssertionError):
                self.compare()
        self.receipts[0] = original
        self.write()
        (self.native / "linux-x86_64/biocompiler-core").write_bytes(b"changed native artifact")
        with self.assertRaisesRegex(AssertionError, "native bytes"):
            self.compare()

    def test_tampered_dropped_reordered_or_duplicate_observations_are_rejected(self):
        original = deepcopy(self.receipts[0])
        mutations = (
            lambda value: value["observations"].pop(),
            lambda value: value["observations"].reverse(),
            lambda value: value["observations"].append(deepcopy(value["observations"][0])),
            lambda value: value["observations"][0]["result"]["report"].update(artifact="produced"),
        )
        for mutate in mutations:
            self.receipts[0] = deepcopy(original)
            mutate(self.receipts[0])
            self.receipts[0]["observations_fingerprint"] = TOOL.canonical_digest(self.receipts[0]["observations"])
            self.write()
            with self.assertRaises(AssertionError):
                self.compare()

    def test_identical_forged_outputs_across_slots_do_not_replace_independent_authority(self):
        for receipt in self.receipts:
            for observation in receipt["observations"]:
                outcome = observation["result"]
                if "report" in outcome and "execution" in outcome["report"]:
                    outcome["report"]["execution"]["requirements"].clear()
                    outcome["report_fingerprint"] = TOOL.canonical_digest(outcome["report"])
            receipt["observations_fingerprint"] = TOOL.canonical_digest(receipt["observations"])
        self.write()
        with self.assertRaisesRegex(AssertionError, "independent authority"):
            self.compare()

    def test_missing_or_disabled_cli_guard_and_foreign_imports_are_rejected(self):
        original = deepcopy(self.receipts[0])
        mutations = (
            lambda value: value["cli_guards"].pop("compile-cli"),
            lambda value: value["cli_guards"]["compile-cli"].update(guard_active=False),
            lambda value: value["cli_guards"]["execute-cli"].update(python=[3, 14]),
            lambda value: value["parent_imports"].update({"biocompiler.compiler": "/installed/biocompiler/compiler.py"}),
            lambda value: value["parent_imports"].update({"biocompiler.core_client": "/other/core_client.py"}),
        )
        for mutate in mutations:
            self.receipts[0] = deepcopy(original)
            mutate(self.receipts[0])
            self.write()
            with self.assertRaises(AssertionError):
                self.compare()

    def test_cli_corruption_requires_specific_native_diagnostic_and_empty_stdout(self):
        expected = {"status": "error", "operation": "execute-native", "message": "policy_execution_work_limit: exhausted"}
        self.assertEqual(TOOL.check_cli_error(2, b"", json.dumps(expected).encode(), "execute-native", "policy_execution_work_limit"), expected)
        for code, stdout, error in ((1, b"", expected), (2, b"success", expected),
                                    (2, b"", {**expected, "message": "some unrelated crash"}),
                                    (2, b"", {**expected, "operation": "compile-native"})):
            with self.subTest(code=code, stdout=stdout, error=error), self.assertRaises(AssertionError):
                TOOL.check_cli_error(code, stdout, json.dumps(error).encode(), "execute-native", "policy_execution_work_limit")

    def test_cli_success_retains_actual_checked_output_and_rejects_bool_integer_aliases(self):
        outcomes = {row["name"]: row["result"] for row in self.receipts[0]["observations"]}
        expected = outcomes["execute-verify"]
        payload = {"document": self.fixture["document"], "definitions": self.fixture["definitions"],
                   "candidate": outcomes["compile"]["candidate"], "timeline": self.fixture["timeline"]}
        retained = TOOL.check_cli_success(0, json.dumps(expected).encode(), b"", "execute-native", expected, payload, "verify")
        self.assertEqual(retained, expected)
        self.assertIsNot(retained, expected)
        changed = deepcopy(expected)
        changed["report"]["execution"]["requirements"][0]["coverage"]["samples"] = False
        self.assertEqual(changed, expected)  # Ordinary Python equality hides this corruption.
        with self.assertRaisesRegex(AssertionError, "returned authority"):
            TOOL.check_cli_success(0, json.dumps(changed).encode(), b"", "execute-native", expected, payload, "verify")
        changed["report_fingerprint"] = TOOL.canonical_digest(changed["report"])
        with self.assertRaisesRegex(AssertionError, "returned authority"):
            TOOL.check_cli_success(0, json.dumps(changed).encode(), b"", "execute-native", expected, payload, "verify")
        duplicated = json.dumps(expected)[:-1] + ', "schema_version":"duplicate"}'
        with self.assertRaisesRegex(AssertionError, "returned authority"):
            TOOL.check_cli_success(0, duplicated.encode(), b"", "execute-native", expected, payload, "verify")

    def test_wrong_feedback_must_leave_correlated_attempt_incomplete(self):
        outputs = {row["name"]: row["result"] for row in self.receipts[0]["observations"]}
        execution = outputs["wrong-feedback-target"]["report"]["execution"]
        TOOL.check_feedback_rejection(execution, self.fixture["timeline"], self.fixture["expected_attempts"], "identity_mismatch")
        execution["attempts"][0]["status"] = "completed"
        with self.assertRaises(AssertionError):
            TOOL.check_feedback_rejection(execution, self.fixture["timeline"], self.fixture["expected_attempts"], "identity_mismatch")

    def test_workflow_runs_campaign_in_both_python_versions_and_compares_all_four_slots(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertEqual(workflow.count('"$GITHUB_WORKSPACE/tools/check_policy_operational.py"'), 2)
        self.assertIn('python "$GITHUB_WORKSPACE/tools/check_policy_operational.py"', workflow)
        self.assertIn('"$ROUTING_PYTHON" "$GITHUB_WORKSPACE/tools/check_policy_operational.py"', workflow)
        for minor in ("3.11", "3.14"):
            self.assertIn('cd "$RUNNER_TEMP/policy-operational-' + minor + '"', workflow)
            self.assertIn('--output "$GITHUB_WORKSPACE/generated/core/policy-operational-' + minor + '.json"', workflow)
            for system in ("linux-x86_64", "macos-arm64"):
                self.assertIn(f"--compare artifacts/core/{system}/policy-operational-{minor}.json", workflow)
        self.assertIn("--native-artifacts artifacts/core", workflow)
        self.assertIn("--output generated/core-reproducibility/policy-operational-receipt.json", workflow)


if __name__ == "__main__":
    unittest.main()
