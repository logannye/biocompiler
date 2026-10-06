"""Inert receipt adversaries; these tests never invoke a native executable."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests import test_core_policy_implementation as peers

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("policy_implementation_campaign_test_tool", ROOT / "tools/check_policy_implementation.py")
TOOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TOOL)
IDENTITY = {"revision": "1" * 40, "head_revision": "2" * 40, "run_id": "98765", "run_attempt": "2"}
FIXTURE = ROOT / "core/test/data/policy_implementation_request_v01.json"


def inert_complete(payload, *, unknown=False):
    payload = deepcopy(payload)
    payload["candidate"] = peers.candidate(payload["request"])
    payload["candidate"]["binding"]["catalog_entry"] = payload["request"]["catalog_bindings"][0]["entry_id"]
    result = peers.result(payload, status="requirements_not_satisfied" if unknown else "checked_implementation")
    expected = TOOL.UNKNOWN_EXPECTED if unknown else TOOL.EXPECTED
    report = result["report"]
    report["coverage"].update(histories=expected["histories"], transitions=expected["transitions"],
                              prefixes_started=expected["prefixes"], matched_prefixes=expected["prefixes"])
    report["program_coverage"].update(active_prefixes=2 if unknown else 6, inactive_prefixes=3 if unknown else 41)
    for row in report["requirements"]:
        row["histories"] = {key: expected["histories"] if key == expected["requirements"][row["id"]] else 0
                            for key in ("pass", "fail", "unknown", "unsupported", "not_exercised")}
        if row["id"] == "exclusive_selection":
            row["coverage"].update(samples=126, active=24, inactive=102)
    result["report_fingerprint"] = TOOL.canonical_digest(report)
    return result


def observations(fixture):
    compiled = inert_complete({"request": fixture["request"], "limits": fixture["limits"]})
    unknown = inert_complete({"request": fixture["unknown_control"]["request"], "limits": fixture["limits"]}, unknown=True)
    values = {name: deepcopy(compiled) for name in ("compile", "check-core", "check-verify", "replay-verify",
                                                   "compile-cli", "check-cli", "replay-cli")}
    values.update({"unknown-compile": unknown, "unknown-check": deepcopy(unknown)})
    for name, request, limits, code in (
        ("prefix-limit", TOOL.changed_request(fixture["request"], "prefix"), fixture["limits"], "policy_preservation_prefix_limit"),
        ("source-work-limit", fixture["request"], TOOL.source_work_limits(fixture["limits"]), "policy_execution_work_limit"),
    ):
        result = peers.result({"request": request, "limits": limits, "candidate": compiled["candidate"]}, status="incomplete")
        result["report"]["stopped"]["diagnostic"]["code"] = code
        result["report_fingerprint"] = TOOL.canonical_digest(result["report"])
        values[name] = result
    for name, codes in TOOL.NEGATIVE_CODES.items():
        values[name] = {"status": "unsupported" if name == "verify-producer" else "error",
                        "diagnostics": [{"code": sorted(codes)[0], "message": "Expected native rejection", "path": None}]}
    values["missing-binary"] = {"status": "transport_error", "type": "CoreUnavailable"}
    values["wrong-role"] = {"status": "transport_error", "type": "CoreProtocolError"}
    values["malformed-replay-cli"] = {"status": "error", "operation": "replay-implementation-native",
                                       "message": "policy_implementation_replay: Full wrapper differs"}
    return [{"name": name, "result": values[name]} for name in TOOL.CASE_NAMES]


class ImplementationCampaignTests(unittest.TestCase):
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
                binary.write_bytes(("Nonexecutable inert receipt bytes: " + system + role).encode())
                pins[binary.name] = TOOL.digest_file(binary)
            (slot / "binaries.json").write_text(json.dumps({"revision": IDENTITY["revision"], "system": system,
                                                          "machine": machine, "sha256": pins}))
            self.binaries[system] = pins
        self.fixture = TOOL.checked_fixture(FIXTURE)
        self.paths, self.receipts = [], []
        retained = observations(self.fixture)
        for system, machine in (("Linux", "x86_64"), ("Darwin", "arm64")):
            for minor in (11, 14):
                package = "/installed/biocompiler"
                origins = {name: package + "/" + name.rsplit(".", 1)[-1] + ".py" for name in (
                    "biocompiler.core_client", "biocompiler.core_policy", "biocompiler.core_policy_operational",
                    "biocompiler.core_policy_implementation", "biocompiler.entrypoint", "biocompiler.policy.cli",
                )}
                guard = {"status": "ok", "guard_active": True, "execution_guard_active": True,
                         "python": [3, minor], "executable": "/installed/python", "origins": origins}
                receipt = {"schema_version": TOOL.SCHEMA, "status": "pass", **IDENTITY, "system": system, "machine": machine,
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

    def mutate_outputs(self, mutate):
        for receipt in self.receipts:
            for row in receipt["observations"]:
                mutate(row["name"], row["result"])
                if "report" in row["result"]:
                    row["result"]["report_fingerprint"] = TOOL.canonical_digest(row["result"]["report"])
            receipt["observations_fingerprint"] = TOOL.canonical_digest(receipt["observations"])
        self.write()

    def test_four_slots_require_complete_inputs_census_and_native_manifests(self):
        result = self.compare()
        self.assertEqual(result["status"], "pass")
        self.assertEqual(len(result["slots"]), 4)
        self.assertEqual(result["claim_scope"], "bounded_implementation_preservation_only")
        self.assertEqual(result["export"], "withheld")
        self.receipts[0]["run_attempt"] = "1"
        self.write()
        self.assertEqual(self.compare()["status"], "pass")

    def test_missing_duplicate_extra_and_redirected_receipts_are_rejected(self):
        for paths in (self.paths[:3], [self.paths[0], self.paths[0], *self.paths[2:]], [*self.paths, self.paths[0]]):
            with self.subTest(paths=paths), self.assertRaises(AssertionError):
                self.compare(paths)
        redirected = self.root / "redirect.json"
        redirected.symlink_to(self.paths[0])
        with self.assertRaises(AssertionError):
            self.compare([redirected, *self.paths[1:]])

    def test_stale_failed_or_wrong_platform_and_binary_authority_is_rejected(self):
        original = deepcopy(self.receipts[0])
        for field, value in (("status", "failed"), ("revision", "0" * 40), ("head_revision", "0" * 40), ("run_id", "123"),
                             ("run_attempt", "3"), ("run_attempt", "0"), ("machine", "arm64"), ("python_version", "3.12.0"),
                             ("fixture_sha256", "0" * 64), ("python_semantic_authority", "allowed"), ("binary_sha256", {})):
            self.receipts[0] = {**deepcopy(original), field: value}
            self.write()
            with self.subTest(field=field, value=value), self.assertRaises(AssertionError):
                self.compare()
        self.receipts[0] = original
        self.write()
        (self.native / "linux-x86_64/biocompiler-core").write_bytes(b"changed bytes")
        with self.assertRaisesRegex(AssertionError, "native bytes"):
            self.compare()

    def test_missing_duplicate_reordered_or_rehashed_observations_are_rejected(self):
        original = deepcopy(self.receipts[0])
        for mutate in (lambda v: v["observations"].pop(), lambda v: v["observations"].reverse(),
                       lambda v: v["observations"].append(deepcopy(v["observations"][0])),
                       lambda v: v["observations"][0]["result"]["report"].update(export="allowed")):
            self.receipts[0] = deepcopy(original)
            mutate(self.receipts[0])
            self.receipts[0]["observations_fingerprint"] = TOOL.canonical_digest(self.receipts[0]["observations"])
            self.write()
            with self.assertRaises(AssertionError):
                self.compare()

    def test_identical_rehashed_dropped_requirements_cannot_replace_original_authority(self):
        self.mutate_outputs(lambda name, output: output["report"]["requirements"].clear() if "report" in output else None)
        with self.assertRaisesRegex(AssertionError, "independent authority"):
            self.compare()

    def test_identical_rehashed_wrong_census_still_fails_independent_literal(self):
        def mutate(name, output):
            if "report" in output and output["report"]["status"] == "checked_implementation":
                output["report"]["coverage"].update(transitions=46, prefixes_started=47, matched_prefixes=47)
        self.mutate_outputs(mutate)
        with self.assertRaisesRegex(AssertionError, "census"):
            self.compare()

    def test_unknown_safety_cannot_be_promoted_by_matching_receipts(self):
        def mutate(name, output):
            if name in ("unknown-compile", "unknown-check"):
                output["report"].update(status="checked_implementation", assurance="bounded_requirements_satisfied")
                row = output["report"]["requirements"][-1]
                row["status"] = "pass"
                row["histories"].update(unknown=0, **{"pass": 1})
        self.mutate_outputs(mutate)
        with self.assertRaisesRegex(AssertionError, "census"):
            self.compare()

    def test_missing_disabled_or_foreign_cli_guards_are_rejected(self):
        original = deepcopy(self.receipts[0])
        for mutate in (
            lambda v: v["cli_guards"].pop("compile-cli"),
            lambda v: v["cli_guards"]["compile-cli"].update(execution_guard_active=False),
            lambda v: v["cli_guards"]["check-cli"].update(python=[3, 14]),
            lambda v: v["parent_imports"].update({"biocompiler.compiler": "/installed/biocompiler/compiler.py"}),
            lambda v: v["parent_imports"].update({"biocompiler.core_client": "/other/core_client.py"}),
        ):
            self.receipts[0] = deepcopy(original)
            mutate(self.receipts[0])
            self.write()
            with self.assertRaises(AssertionError):
                self.compare()

    def test_native_controls_require_specific_diagnostics_and_no_success_authority(self):
        original = deepcopy(self.receipts[0])
        for name, replacement in (("changed-guard", {"status": "error", "diagnostics": []}),
                                  ("verify-producer", {"status": "error", "diagnostics": [{"code": "unsupported_operation", "message": "wrong role", "path": None}]}),
                                  ("missing-binary", {"status": "ok", "type": "CoreUnavailable"})):
            self.receipts[0] = deepcopy(original)
            next(row for row in self.receipts[0]["observations"] if row["name"] == name)["result"] = replacement
            self.receipts[0]["observations_fingerprint"] = TOOL.canonical_digest(self.receipts[0]["observations"])
            self.write()
            with self.subTest(name=name), self.assertRaises(AssertionError):
                self.compare()

    def test_cli_errors_require_specific_native_diagnostic_and_empty_stdout(self):
        expected = {"status": "error", "operation": "replay-implementation-native", "message": "policy_implementation_replay: mismatch"}
        self.assertEqual(TOOL.check_cli_error(2, b"", json.dumps(expected).encode(), "replay-implementation-native", "policy_implementation_replay"), expected)
        for code, stdout, error in ((1, b"", expected), (2, b"success", expected),
                                    (2, b"", {**expected, "message": "unrelated crash"}),
                                    (2, b"", {**expected, "operation": "compile-implementation-native"})):
            with self.subTest(code=code, stdout=stdout), self.assertRaises(AssertionError):
                TOOL.check_cli_error(code, stdout, json.dumps(error).encode(), "replay-implementation-native", "policy_implementation_replay")

    def test_cli_retains_actual_output_and_rejects_duplicate_keys_and_boolean_integer_aliases(self):
        outcomes = {row["name"]: row["result"] for row in self.receipts[0]["observations"]}
        expected = outcomes["check-verify"]
        payload = {"request": self.fixture["request"], "candidate": expected["candidate"], "limits": self.fixture["limits"]}
        actual = TOOL.check_cli_success(0, json.dumps(expected).encode(), b"", "check-implementation-native", expected, payload, "verify")
        self.assertEqual(actual, expected)
        self.assertIsNot(actual, expected)
        changed = deepcopy(expected)
        changed["report"]["coverage"]["complete"] = 1
        self.assertEqual(changed, expected)
        for rehash in (False, True):
            if rehash:
                changed["report_fingerprint"] = TOOL.canonical_digest(changed["report"])
            with self.subTest(rehash=rehash), self.assertRaisesRegex(AssertionError, "returned authority"):
                TOOL.check_cli_success(0, json.dumps(changed).encode(), b"", "check-implementation-native", expected, payload, "verify")
        duplicate = json.dumps(expected)[:-1] + ',"schema_version":"duplicate"}'
        with self.assertRaisesRegex(AssertionError, "returned authority"):
            TOOL.check_cli_success(0, duplicate.encode(), b"", "check-implementation-native", expected, payload, "verify")

    def test_full_wrapper_and_actual_inputs_cannot_be_replaced_by_inner_report(self):
        output = self.receipts[0]["observations"][0]["result"]
        payload = {"request": self.fixture["request"], "candidate": output["candidate"], "limits": self.fixture["limits"],
                   "report": output["report"]}
        with self.assertRaisesRegex(AssertionError, "independent authority"):
            TOOL.checked_output(output, "replay-policy-implementation", payload, "verify")
        payload["report"] = output
        payload["request"] = TOOL.changed_request(self.fixture["request"], "span")
        with self.assertRaisesRegex(AssertionError, "independent authority"):
            TOOL.checked_output(output, "replay-policy-implementation", payload, "verify")

    def test_guard_extension_preserves_forbidden_imports_and_semantic_calls(self):
        self.assertTrue(TOOL.ImplementationBoundary.allowed("biocompiler.core_policy_implementation"))
        self.assertTrue(TOOL.ImplementationBoundary.allowed("biocompiler.policy.implementation"))
        self.assertFalse(TOOL.ImportBoundary.allowed("biocompiler.core_policy_implementation"))
        boundary = TOOL.ImplementationBoundary(self.root)
        with self.assertRaises(ImportError):
            boundary.find_spec("biocompiler.compiler")
        for module, function in (("biocompiler.policy.validation", "check"), ("biocompiler.policy.programs", "freeze"),
                                 ("biocompiler.policy.handoff", "prepare_submission")):
            frame = SimpleNamespace(f_globals={"__name__": module}, f_code=SimpleNamespace(co_name=function))
            with self.assertRaises(AssertionError):
                boundary.trace(frame, "call", None)

    def test_control_recipes_are_nonmutating_and_guard_rewire_is_actual_graph_edit(self):
        output = self.receipts[0]["observations"][0]["result"]
        candidate = output["candidate"]
        modified = TOOL.changed_guard(candidate)
        self.assertEqual(modified["binding"], candidate["binding"])
        self.assertEqual(modified["behavior"], candidate["behavior"])
        self.assertNotEqual(modified["implementation"]["wires"], candidate["implementation"]["wires"])
        for kind in ("source", "span", "domain", "prefix", "work"):
            changed = TOOL.changed_request(self.fixture["request"], kind)
            self.assertNotEqual(changed, self.fixture["request"])
        self.assertEqual(self.fixture, TOOL.checked_fixture(FIXTURE))

    def test_literal_catalog_bridge_matches_its_authored_deployment_and_exact_entry(self):
        # Structural fixture regression for the inherited chassis-copy defect;
        # native admission remains the authority for interpreting these records.
        for request in (self.fixture["request"], self.fixture["unknown_control"]["request"]):
            document = request["document"]
            entry = document["implementations"]["implementations"][0]
            bridge = request["catalog_bindings"][0]
            self.assertEqual(entry["chassis"], [document["deployment"]["bindings"][0]["chassis"]["id"]])
            self.assertEqual(entry["payload_formats"], ["RNA"])
            self.assertEqual(bridge["entry_id"], entry["id"])
            self.assertEqual(bridge["entry_digest"], TOOL.canonical_digest(entry))
            self.assertEqual(bridge["operation"], entry["operation"])
            self.assertEqual(bridge["realization"], entry["realization"])

    def test_workflow_runs_both_installed_interpreters_and_compares_exactly_four_slots(self):
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        sdk = workflow.split('\n  architecture-sdk:\n', 1)[1].split('\n  architecture-core-reproducibility:\n', 1)[0]
        slots = re.findall(r'platform: ([a-z0-9_-]+)\n            python-version: "([0-9.]+)"', sdk)
        self.assertCountEqual(slots, [(system, minor) for system in ('linux-x86_64', 'macos-arm64')
                                     for minor in ('3.11', '3.14')])
        self.assertEqual(sdk.count('python "$GITHUB_WORKSPACE/tools/check_policy_implementation.py"'), 1)
        self.assertEqual(workflow.count('python tools/check_policy_implementation.py'), 1)
        self.assertIn('python-version: ${{ matrix.python-version }}', sdk)
        self.assertIn('--core "$GITHUB_WORKSPACE/core/_build/default/bin/core/main.exe"', sdk)
        self.assertIn('--verify "$GITHUB_WORKSPACE/core/_build/default/bin/verify/main.exe"', sdk)
        self.assertIn('--fixture "$GITHUB_WORKSPACE/core/test/data/policy_implementation_request_v01.json"', sdk)
        self.assertIn('sysconfig.get_path("scripts") + "/biocompiler"', sdk)
        for minor in ("3.11", "3.14"):
            expanded = sdk.replace('${{ matrix.python-version }}', minor)
            self.assertIn('cd "$RUNNER_TEMP/policy-implementation-' + minor + '"', expanded)
            self.assertIn('--output "$GITHUB_WORKSPACE/generated/core/policy-implementation-' + minor + '.json"', expanded)
            for system in ("linux-x86_64", "macos-arm64"):
                self.assertEqual(workflow.count(f"--compare artifacts/core/{system}/policy-implementation-{minor}.json"), 1)
        self.assertIn("--native-artifacts artifacts/core", workflow)
        self.assertIn("--fixture core/test/data/policy_implementation_request_v01.json", workflow)
        self.assertIn("--output generated/core-reproducibility/policy-implementation-receipt.json", workflow)


if __name__ == "__main__":
    unittest.main()
