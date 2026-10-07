"""Inert fixtures and mocked launches only; this module never runs native code."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from tools import check_policy_development as dev


class PolicyDevelopmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        for name in dev.SOURCE_ROOTS[:-1]:
            (self.root / name).mkdir()
        (self.root / "pyproject.toml").write_text("[project]\nname='inert'\n")
        (self.root / "src/empty.py").write_bytes(b"")
        (self.root / "core/test").mkdir()
        (self.root / "core/test/data").mkdir()
        self.stanzas = []
        for name, fixtures in dev.SUITES:
            action = (" (action (run %{test} " + " ".join("%{dep:" + path + "}" for path in fixtures) + "))") if fixtures else ""
            self.stanzas.append(f"(test (name {name}) (modules {name}) (libraries bioc_wire){action})\n")
            for path in fixtures:
                (self.root / "core/test" / path).write_text('{"independent_fixture":true}\n')
        (self.root / "core/test/dune").write_text("".join(self.stanzas))
        self.freeze_tree()
        self.revision, self.tree = "1" * 40, "2" * 40
        self.env = {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
                    "GITHUB_EVENT_NAME": "push", "GITHUB_REF": "refs/heads/codex/dev-policy/example",
                    "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64", "GITHUB_WORKSPACE": str(self.root),
                    "GITHUB_SHA": self.revision, "GITHUB_RUN_ID": "1234", "GITHUB_RUN_ATTEMPT": "2",
                    "GITHUB_REPOSITORY": "owner/repository", "GITHUB_WORKFLOW_SHA": self.revision,
                    "GITHUB_WORKFLOW_REF": "owner/repository/.github/workflows/policy-development.yml@refs/heads/codex/dev-policy/example"}
        for patch in (mock.patch.dict(os.environ, self.env, clear=True),
                      mock.patch.object(dev.platform, "system", return_value="Linux"),
                      mock.patch.object(dev.platform, "machine", return_value="x86_64"),
                      mock.patch.object(dev, "git", side_effect=self.git),
                      mock.patch.object(subprocess, "Popen", side_effect=AssertionError("No real process allowed"))):
            patch.start()
            self.addCleanup(patch.stop)
        self.calls = []
        self.fail = None
        self.omit = None
        self.mutate = None
        patch = mock.patch.object(dev.subprocess, "run", side_effect=self.launch)
        patch.start()
        self.addCleanup(patch.stop)

    def freeze_tree(self):
        rows = []
        for path in sorted(self.root.rglob("*")):
            if path.is_file():
                raw = path.read_bytes()
                blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
                rows.append(f"100644 blob {blob}\t{path.relative_to(self.root).as_posix()}".encode())
        self.index = b"\0".join(rows) + b"\0"

    def git(self, root, *args):
        self.assertEqual(root, self.root)
        if args == ("rev-parse", "HEAD"):
            return self.revision.encode() + b"\n"
        if args == ("rev-parse", "HEAD^{tree}"):
            return self.tree.encode() + b"\n"
        self.assertEqual(args, ("ls-tree", "-r", "-z", "HEAD", "--", *dev.SOURCE_ROOTS))
        return self.index

    def launch(self, argv, *, cwd, stdout, stderr, timeout, check):
        self.assertEqual(cwd, self.root)
        self.assertEqual(stderr, subprocess.STDOUT)
        self.assertFalse(check)
        self.assertEqual(timeout, 900)
        self.calls.append(argv)
        if argv == dev.BUILD:
            for name, _ in dev.SUITES:
                if name != self.omit:
                    binary = self.root / "core/_build/default/test" / (name + ".exe")
                    binary.parent.mkdir(parents=True, exist_ok=True)
                    binary.write_bytes(b"INERT TEST BYTES - NEVER EXECUTED")
                    binary.chmod(0o755)
            for relative in dev.SDK_BINARIES.values():
                binary = self.root / relative
                binary.parent.mkdir(parents=True, exist_ok=True)
                binary.write_bytes(b"INERT SDK BYTES - NEVER EXECUTED")
                binary.chmod(0o755)
        stdout.write(b"mock outcome\n")
        if self.mutate:
            self.mutate(argv)
        return subprocess.CompletedProcess(argv, 1 if argv == self.fail else 0)

    def report(self):
        return json.loads((self.root / "generated/development-feedback/feedback.json").read_text())

    def test_full_fixed_plan_and_truthful_nonacceptance(self):
        dev.prepare(self.root)
        result = dev.run(self.root)
        self.assertEqual([row[0] for row in dev.SUITES], [
            "test_policy_component_fragment", "test_policy_component_material", "test_policy_component_assembly_rule", "test_policy_component_assembly_check",
            "test_policy_component_material_request", "test_policy_component_selection_request",
            "test_policy_component_material_candidate", "test_policy_component_selection_candidate",
            "test_policy_component_selection_common", "test_policy_component_selection_check", "test_policy_component_context_check",
            "test_policy_component_material_service", "test_protocol", "test_producer_protocol",
            "test_policy_implementation_binding",
            "test_policy_preservation_check", "test_policy_material_binding", "test_policy_material_context",
            "test_policy_material_check", "test_policy_mrna_structure", "test_construction_content"])
        self.assertEqual(self.calls[:2], [
            ["opam", "install", "core/biocompiler_core.opam", "--deps-only", "--with-test", "--yes"],
            ["opam", "exec", "--", "dune", "build", "--root", "core", "@all"]])
        self.assertEqual(len(self.calls), 23)
        self.assertEqual(len(result["suites"]), 21)
        for name, fixtures in (
            ("test_policy_component_selection_request", ["policy_material_request_v01.json", "policy_material_state_v01.json"]),
            ("test_policy_component_material_candidate", ["policy_material_request_v01.json"]),
            ("test_policy_component_selection_candidate", ['policy_material_request_v01.json']),
            ("test_policy_component_selection_common", ['policy_material_request_v01.json', 'policy_material_state_v01.json']),
            ("test_policy_component_selection_check", ['policy_material_request_v01.json']),
        ):
            call = next(call for call in self.calls if any(str(arg).endswith(name + ".exe") for arg in call))
            self.assertEqual([Path(arg).name for arg in call[4:]], fixtures)
        self.assertEqual([Path(p).name for p in next(call for call in self.calls if any(str(arg).endswith("test_policy_implementation_binding.exe") for arg in call))[4:]], [
            "policy_implementation_binding_v01.json", "policy_realization_request_v01.json", "policy_exclusion_source_v01.json"])
        self.assertEqual(result["status"], "passed")
        self.assertFalse(result["acceptance"])
        self.assertEqual(result["sources_before"], result["sources_after"])
        self.assertEqual(result["identity"]["tree"], self.tree)
        self.assertTrue(all(row["status"] == "passed" and row["log_pin"]["size"] > 0 for row in result["suites"]))

    def test_identity_failures_precede_every_native_launch(self):
        mutations = {"GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main",
                     "RUNNER_ENVIRONMENT": "self-hosted", "GITHUB_SHA": "3" * 40,
                     "RUNNER_OS": "macOS", "GITHUB_RUN_ATTEMPT": "0", "GITHUB_RUN_ID": "",
                     "GITHUB_WORKFLOW_SHA": "3" * 40, "GITHUB_WORKFLOW_REF": "another/workflow"}
        for field, value in mutations.items():
            with self.subTest(field=field), mock.patch.dict(os.environ, {field: value}):
                with self.assertRaises(ValueError):
                    dev.identity(self.root)
        self.assertEqual(self.calls, [])

    def test_missing_target_and_changed_fixture_order_fail_closed(self):
        for name in ("test_policy_component_fragment", "test_policy_component_selection_request", "test_policy_component_material_candidate"):
            (self.root / "core/test/dune").write_text("".join(stanza for stanza in self.stanzas
                if "(name " + name + ")" not in stanza))
            with self.subTest(suite=name), self.assertRaisesRegex(ValueError, "Missing or changed registered suite"):
                dev.selected_suites(self.root)
        binding_index = next(i for i, stanza in enumerate(self.stanzas)
                             if "(name test_policy_implementation_binding)" in stanza)
        original_binding = self.stanzas[binding_index]
        reversed_binding = original_binding.replace(
            "%{dep:data/policy_implementation_binding_v01.json} %{dep:data/policy_realization_request_v01.json}",
            "%{dep:data/policy_realization_request_v01.json} %{dep:data/policy_implementation_binding_v01.json}")
        self.assertNotEqual(original_binding, reversed_binding)
        changed = list(self.stanzas)
        changed[binding_index] = reversed_binding
        (self.root / "core/test/dune").write_text("".join(changed))
        with self.assertRaisesRegex(ValueError, "Changed native dependency fixture arguments"):
            dev.selected_suites(self.root)
        self.assertEqual(self.calls, [])

    def test_empty_tracked_source_is_retained_and_new_source_rejects(self):
        before = dev.source_snapshot(self.root)
        self.assertEqual(before["src/empty.py"]["size"], 0)
        (self.root / "core/new.ml").write_text("new source")
        with self.assertRaisesRegex(ValueError, "new source files"):
            dev.source_snapshot(self.root)

    def test_source_edit_after_prepare_never_launches_native(self):
        dev.prepare(self.root)
        (self.root / "src/empty.py").write_text("changed")
        with self.assertRaisesRegex(ValueError, "Source differs"):
            dev.run(self.root)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.report()["status"], "failed")

    def test_missing_fixture_prevents_native_launch(self):
        (self.root / "core/test/data/policy_material_state_v01.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing or unsafe input"):
            dev.prepare(self.root)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.report()["status"], "failed")

    def test_build_failure_retains_logs_and_no_success_shaped_suites(self):
        dev.prepare(self.root)
        self.fail = dev.BUILD
        with self.assertRaisesRegex(ValueError, "build failed"):
            dev.run(self.root)
        result = self.report()
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(result["status"], "failed")
        self.assertTrue(all(row["status"] == "not_run" for row in result["suites"]))
        self.assertEqual(result["actions"][1]["returncode"], 1)
        self.assertTrue((self.root / "generated/development-feedback/build.log").is_file())

    def test_missing_executable_is_not_skipped(self):
        dev.prepare(self.root)
        self.omit = "test_policy_component_material"
        with self.assertRaisesRegex(ValueError, "Missing or unsafe input"):
            dev.run(self.root)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(self.report()["status"], "failed")

    def test_failed_suite_retains_all_twenty_one_outcomes_and_fails(self):
        dev.prepare(self.root)
        self.fail = dev.selected_suites(self.root)[1]["argv"]
        with self.assertRaisesRegex(ValueError, "Focused native suite failed"):
            dev.run(self.root)
        result = self.report()
        self.assertEqual(len(self.calls), 23)
        self.assertEqual([r["status"] for r in result["suites"]].count("passed"), 20)
        self.assertEqual(result["suites"][1]["status"], "failed")
        self.assertEqual(result["status"], "failed")

    def test_late_source_mutation_cannot_return_success(self):
        dev.prepare(self.root)
        last = dev.selected_suites(self.root)[-1]["argv"]
        self.mutate = lambda argv: (self.root / "src/empty.py").write_text("late") if argv == last else None
        with self.assertRaisesRegex(ValueError, "Source differs"):
            dev.run(self.root)
        self.assertEqual(self.report()["status"], "failed")
        self.assertIn("source_error", self.report())

    def test_changed_binary_cannot_return_success(self):
        dev.prepare(self.root)
        suites = dev.selected_suites(self.root)
        self.mutate = lambda argv: (self.root / suites[0]["executable"]).write_bytes(b"changed binary") if argv == suites[-1]["argv"] else None
        with self.assertRaisesRegex(ValueError, "Native executable changed"):
            dev.run(self.root)
        self.assertEqual(self.report()["status"], "failed")

    def test_timed_out_command_is_recorded_as_failure(self):
        dev.prepare(self.root)
        with mock.patch.object(dev.subprocess, "run", side_effect=subprocess.TimeoutExpired(dev.DEPENDENCIES, 900)):
            with self.assertRaisesRegex(ValueError, "dependencies failed"):
                dev.run(self.root)
        result = self.report()
        self.assertEqual(result["status"], "failed")
        self.assertIn("error", result["actions"][0])
        self.assertTrue(all(row["status"] == "not_run" for row in result["suites"]))


if __name__ == "__main__":
    unittest.main()
