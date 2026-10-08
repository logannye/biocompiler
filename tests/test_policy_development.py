"""Inert fixtures and mocked launches only; this module never runs native code."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest import mock

from tools import check_policy_development as dev


class PolicyDevelopmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        for name in dev.SOURCE_ROOTS[:-1]:
            target = self.root / name
            if target.suffix:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("# inert example\n")
            else:
                target.mkdir(parents=True, exist_ok=True)
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
            "test_policy_provider_prerequisites", "test_policy_prerequisite_material_service", "test_policy_two_observation_material_service", "test_policy_multi_member_material_service", "test_policy_grounded_helper_material_service",
            "test_policy_instance_assembly_rule", "test_policy_instance_material_service",
            "test_policy_staged_generation", "test_policy_staged_binding", "test_policy_staged_component_material", "test_policy_staged_primitives", "test_policy_staged_regimen_source",
            "test_policy_component_fragment", "test_policy_component_material", "test_policy_component_assembly_rule", "test_policy_component_assembly_check",
            "test_policy_component_material_request", "test_policy_component_selection_request",
            "test_policy_component_material_candidate", "test_policy_component_selection_candidate",
            "test_policy_component_selection_common", "test_policy_component_selection_check",
            "test_policy_component_selection_scope", "test_policy_component_selection_producer", "test_policy_generation_admission", "test_policy_generation_producers", "test_policy_component_selection_service", "test_policy_component_context_check",
            "test_policy_component_material_service", "test_protocol", "test_producer_protocol",
            "test_policy_implementation_binding",
            "test_policy_preservation_check", "test_policy_material_binding", "test_policy_material_context",
            "test_policy_material_check", "test_policy_mrna_structure", "test_construction_content"])
        self.assertEqual(self.calls[:2], [
            ["opam", "install", "core/biocompiler_core.opam", "--deps-only", "--with-test", "--yes"],
            ["opam", "exec", "--", "dune", "build", "--root", "core", "@all"]])
        self.assertEqual(len(self.calls), 40)
        self.assertEqual(len(result["suites"]), 38)
        for name, fixtures in (
            ("test_policy_component_selection_request", ["policy_material_request_v01.json", "policy_material_state_v01.json"]),
            ("test_policy_component_material_candidate", ["policy_material_request_v01.json"]),
            ("test_policy_component_selection_candidate", ['policy_material_request_v01.json']),
            ("test_policy_component_selection_common", ['policy_material_request_v01.json', 'policy_material_state_v01.json']),
            ("test_policy_component_selection_check", ['policy_material_request_v01.json']),
            ("test_policy_component_selection_scope", ["policy_material_request_v01.json"]),
            ("test_policy_component_selection_producer", ["policy_material_request_v01.json"]),
            ("test_policy_generation_admission", ['policy_implementation_binding_v01.json']),
            ("test_policy_generation_producers", ['policy_material_request_v01.json', 'policy_material_state_v01.json']),
            ("test_policy_component_selection_service", ["policy_material_request_v01.json"]),
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
        for name in ("test_policy_component_fragment", "test_policy_component_selection_request", "test_policy_component_material_candidate",
                     "test_policy_component_selection_scope", "test_policy_component_selection_service"):
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

    def test_failed_suite_retains_all_outcomes_and_fails(self):
        dev.prepare(self.root)
        self.fail = dev.selected_suites(self.root)[1]["argv"]
        with self.assertRaisesRegex(ValueError, "Focused native suite failed"):
            dev.run(self.root)
        result = self.report()
        self.assertEqual(len(self.calls), 40)
        self.assertEqual([r["status"] for r in result["suites"]].count("passed"), 37)
        self.assertEqual(result["suites"][1]["status"], "failed")
        self.assertEqual(result["status"], "failed")

    def test_native_workers_overlap_but_only_coordinator_persists_original_order(self):
        dev.prepare(self.root)
        suites = dev.selected_suites(self.root)
        first_started, second_finished = threading.Event(), threading.Event()
        lock = threading.Lock()
        active, maximum = 0, 0
        completed, writers = [], []
        coordinator = threading.get_ident()
        original_save = dev.save

        def save(path, value):
            if path.name == "feedback.json":
                writers.append(threading.get_ident())
                self.assertEqual([row["name"] for row in value["suites"]], [row["name"] for row in suites])
            original_save(path, value)

        def launch(argv, **kwargs):
            nonlocal active, maximum
            if argv in (dev.DEPENDENCIES, dev.BUILD):
                self.assertEqual(threading.get_ident(), coordinator)
                return self.launch(argv, **kwargs)
            name = Path(argv[3]).stem
            with lock:
                active += 1
                maximum = max(maximum, active)
            try:
                if name == suites[0]["name"]:
                    first_started.set()
                    self.assertTrue(second_finished.wait(5), "Second native worker did not run")
                elif name == suites[1]["name"]:
                    self.assertTrue(first_started.wait(5), "First native worker did not run")
                result = self.launch(argv, **kwargs)
                with lock:
                    completed.append(name)
                if name == suites[1]["name"]:
                    second_finished.set()
                return result
            finally:
                with lock:
                    active -= 1

        with mock.patch.object(dev.subprocess, "run", side_effect=launch), mock.patch.object(dev, "save", side_effect=save):
            result = dev.run(self.root)
        self.assertEqual(dev.PARALLEL_WORKERS, 2)
        self.assertEqual(maximum, 2)
        self.assertEqual(active, 0)
        self.assertLess(completed.index(suites[1]["name"]), completed.index(suites[0]["name"]))
        self.assertEqual(set(writers), {coordinator})
        self.assertEqual([row["name"] for row in result["suites"]], [row["name"] for row in suites])
        self.assertCountEqual(completed, [row["name"] for row in suites])
        self.assertEqual(len({row["log"] for row in result["suites"]}), 38)
        dev.validate_native_feedback(self.root, result, dev.preparation(self.root))

    def test_parallel_suite_timeout_retains_every_other_outcome(self):
        dev.prepare(self.root)
        selected = dev.selected_suites(self.root)[1]

        def launch(argv, **kwargs):
            result = self.launch(argv, **kwargs)
            if argv == selected["argv"]:
                raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
            return result

        with mock.patch.object(dev.subprocess, "run", side_effect=launch):
            with self.assertRaisesRegex(ValueError, "Focused native suite failed"):
                dev.run(self.root)
        report = self.report()
        self.assertEqual(len(self.calls), 40)
        self.assertEqual([row["name"] for row in report["suites"]], [name for name, _ in dev.SUITES])
        self.assertEqual([row["status"] for row in report["suites"]].count("passed"), 37)
        self.assertEqual(report["suites"][1]["status"], "failed")
        self.assertNotIn("returncode", report["suites"][1])
        self.assertIn("900", report["suites"][1]["error"])
        self.assertEqual(report["status"], "failed")

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

    def test_wall_clock_extension_requires_the_exact_selection_command(self):
        dev.prepare(self.root)
        output = self.root / "generated/development-feedback"
        selection = [dev.sys.executable, "-B", str(self.root / "tools/check_policy_component_selection.py"),
            "--fixture", str(output / "selection-originals.json"),
            "--core", str(self.root / dev.SDK_BINARIES["core"]),
            "--verify", str(self.root / dev.SDK_BINARIES["verify"]),
            "--output", str(output / "selection-sdk-witness.json")]
        cases = [("dependencies", dev.DEPENDENCIES, 900), ("build", dev.BUILD, 900),
                 ("test_policy_component_selection_check", dev.selected_suites(self.root)[0]["argv"], 900),
                 ("component-sdk", selection, 900), ("staged-material-sdk", selection, 900),
                 ("selection-sdk", selection, 1800)]
        for index in (0, 2, 4, 6, 8, 10):
            changed = list(selection)
            changed[index] = "unreviewed-command-or-input"
            cases.append(("selection-sdk", changed, 900))
        for name, argv, timeout in cases:
            (output / (name + ".log")).unlink(missing_ok=True)
            with self.subTest(name=name, argv=argv), mock.patch.object(dev.subprocess, "run",
                    return_value=subprocess.CompletedProcess(argv, 0)) as launch:
                row = dev.command(self.root, output, name, argv)
            self.assertEqual(launch.call_args.args, (argv,))
            self.assertEqual(launch.call_args.kwargs["timeout"], timeout)
            self.assertEqual(row["status"], "passed")
        self.assertEqual(self.calls, [])

    def prepare_staged_sdk(self):
        dev.prepare(self.root)
        dev.run(self.root)
        self.calls.clear()
        self.sdk_output = self.root / "generated/development-feedback"
        self.sdk_witness = self.sdk_output / "staged-source-sdk-witness.json"
        self.sdk_argv = [dev.sys.executable, "-B", str(self.root / "tools/check_policy_staged_regimen_source.py"),
            "--fixture", str(self.root / "core/test/data/policy_staged_regimen_source_v01.json"),
            "--core", str(self.root / dev.SDK_BINARIES["core"]), "--verify", str(self.root / dev.SDK_BINARIES["verify"]),
            "--output", str(self.sdk_witness)]

    def staged_sdk_receipt(self):
        return json.loads((self.sdk_output / "staged-source-sdk.json").read_text())

    def test_staged_source_sdk_uses_fixed_original_same_binaries_and_separate_receipt(self):
        self.prepare_staged_sdk()
        native = (self.sdk_output / "feedback.json").read_bytes()
        self.mutate = lambda argv: self.sdk_witness.write_text('{"inert_witness_only":true}\n')
        result = dev.staged_source_sdk(self.root)
        self.assertEqual(self.calls, [self.sdk_argv])
        self.assertEqual(result["schema"], "biocompiler.development-staged-source-sdk-feedback.v0.1")
        self.assertEqual(result["status"], "passed")
        self.assertIs(result["acceptance"], False)
        self.assertEqual(result["identity"], dev.identity(self.root))
        self.assertEqual(result["sources_before"], result["sources_after"])
        self.assertEqual(set(result["outputs"]), {"staged-source-sdk-witness.json"})
        self.assertEqual(result["outputs"][self.sdk_witness.name], dev.pin(self.root, self.sdk_witness.relative_to(self.root).as_posix()))
        self.assertEqual((self.sdk_output / "feedback.json").read_bytes(), native)
        self.assertEqual(result["actions"][0]["argv"], self.sdk_argv)
        self.assertEqual(result["actions"][0]["returncode"], 0)

    def test_staged_source_sdk_identity_and_source_fail_before_launch(self):
        self.prepare_staged_sdk()
        for field, value in (("GITHUB_REF", "refs/heads/main"), ("GITHUB_SHA", "3" * 40),
                             ("RUNNER_ENVIRONMENT", "self-hosted"), ("GITHUB_WORKFLOW_SHA", "4" * 40)):
            with self.subTest(field=field), mock.patch.dict(os.environ, {field: value}), self.assertRaises(ValueError):
                dev.staged_source_sdk(self.root)
            self.assertEqual(self.calls, [])
            self.assertEqual(self.staged_sdk_receipt()["status"], "failed")
        path = self.root / "core/test/data/policy_staged_regimen_source_v01.json"
        path.write_bytes(b"changed original")
        with self.assertRaises(ValueError):
            dev.staged_source_sdk(self.root)
        self.assertEqual(self.calls, [])

    def test_successful_empty_native_log_requires_exact_pin_status_and_zero_exit(self):
        self.prepare_staged_sdk()
        native = self.report()
        row = next(value for value in native["suites"] if value["name"] == "test_policy_staged_regimen_source")
        log = self.sdk_output / row["log"]
        log.write_bytes(b"")
        row["log_pin"] = {"sha256": hashlib.sha256(b"").hexdigest(), "size": 0}
        prepared = dev.preparation(self.root)
        dev.validate_native_feedback(self.root, native, prepared)
        for key, changed in (("status", "failed"), ("returncode", 1), ("returncode", False),
                             ("log_pin", {"sha256": "0" * 64, "size": 0})):
            original = row[key]
            row[key] = changed
            with self.subTest(field=key, value=changed), self.assertRaises(ValueError):
                dev.validate_native_feedback(self.root, native, prepared)
            row[key] = original
        log.unlink()
        with self.assertRaises(ValueError):
            dev.validate_native_feedback(self.root, native, prepared)

    def test_staged_source_sdk_rejects_incomplete_native_run_and_changed_binary(self):
        self.prepare_staged_sdk()
        path = self.sdk_output / "feedback.json"
        raw = path.read_bytes()
        for key in ("suites", "actions"):
            changed = json.loads(raw)
            changed[key].pop()
            path.write_text(json.dumps(changed))
            with self.subTest(key=key), self.assertRaises(ValueError):
                dev.staged_source_sdk(self.root)
            self.assertEqual(self.calls, [])
        path.write_bytes(raw)
        binary = self.root / dev.SDK_BINARIES["verify"]
        binary.write_bytes(b"different native bytes")
        with self.assertRaisesRegex(ValueError, "differs from completed native build"):
            dev.staged_source_sdk(self.root)
        self.assertEqual(self.calls, [])

    def test_staged_source_sdk_failure_and_missing_witness_never_pass(self):
        self.prepare_staged_sdk()
        self.fail = self.sdk_argv
        with self.assertRaisesRegex(ValueError, "Staged source SDK failed"):
            dev.staged_source_sdk(self.root)
        report = self.staged_sdk_receipt()
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["actions"][0]["returncode"], 1)
        self.assertTrue((self.sdk_output / "staged-source-sdk.log").is_file())
        self.fail = None
        (self.sdk_output / "staged-source-sdk.log").unlink()
        with self.assertRaises(ValueError):
            dev.staged_source_sdk(self.root)
        self.assertEqual(self.staged_sdk_receipt()["status"], "failed")

    def test_staged_source_sdk_late_mutation_cannot_transfer_success(self):
        self.prepare_staged_sdk()
        paths = [self.root / dev.SDK_BINARIES["core"], self.sdk_output / "feedback.json", self.sdk_output / "build.log"]
        for path in paths:
            (self.sdk_output / "staged-source-sdk.log").unlink(missing_ok=True)
            original = path.read_bytes()
            def mutate(argv):
                self.sdk_witness.write_text('{"inert_witness_only":true}\n')
                path.write_bytes(b"late mutation")
            self.mutate = mutate
            with self.subTest(path=path.name), self.assertRaises(ValueError):
                dev.staged_source_sdk(self.root)
            self.assertEqual(self.staged_sdk_receipt()["status"], "failed")
            self.assertIn("source_error", self.staged_sdk_receipt())
            path.write_bytes(original)

    def test_researcher_alpha_sdk_rejects_missing_stale_and_mutated_evidence(self):
        self.prepare_staged_sdk()
        witness = self.sdk_output / "researcher-alpha-sdk-witness.json"
        report_path = self.sdk_output / "researcher-alpha-sdk.json"
        log = self.sdk_output / "researcher-alpha-sdk.log"
        with mock.patch.dict(os.environ, {"GITHUB_SHA": "3" * 40}), self.assertRaises(ValueError):
            dev.researcher_alpha_sdk(self.root)
        self.assertEqual(self.calls, [])
        with self.assertRaisesRegex(ValueError, "researcher-alpha-sdk-witness.json"):
            dev.researcher_alpha_sdk(self.root)
        self.assertEqual(json.loads(report_path.read_text())["status"], "failed")
        log.unlink()
        self.mutate = lambda called: witness.write_text('{"inert_only":true}\n')
        checked = dev.researcher_alpha_sdk(self.root)
        self.assertEqual(checked["schema"], "biocompiler.development-researcher-alpha-feedback.v0.1")
        self.assertEqual(checked["status"], "passed")
        self.assertIs(checked["acceptance"], False)
        self.assertEqual(set(checked["outputs"]), {witness.name})
        self.assertEqual(self.calls[-1], [dev.sys.executable, "-B", str(self.root / "tools/check_researcher_alpha.py"),
            "--expected", str(self.root / "data/researcher_alpha/expected.json"),
            "--core", str(self.root / dev.SDK_BINARIES["core"]), "--verify", str(self.root / dev.SDK_BINARIES["verify"]),
            "--output", str(witness)])
        log.unlink()
        self.mutate = lambda called: (self.root / "examples/researcher_alpha.py").write_text("changed")
        with self.assertRaises(ValueError):
            dev.researcher_alpha_sdk(self.root)
        self.assertEqual(json.loads(report_path.read_text())["status"], "failed")

    def test_staged_material_sdk_fixed_paths_identity_and_failures_are_independent(self):
        self.prepare_staged_sdk()
        witness = self.sdk_output / "staged-material-sdk-witness.json"
        report_path = self.sdk_output / "staged-material-sdk.json"
        log = self.sdk_output / "staged-material-sdk.log"
        argv = [dev.sys.executable, "-B", str(self.root / "tools/check_policy_staged_component_material.py"),
            "--fixture", str(self.root / "core/test/data/policy_staged_material_v01.json"),
            "--core", str(self.root / dev.SDK_BINARIES["core"]), "--verify", str(self.root / dev.SDK_BINARIES["verify"]),
            "--output", str(witness)]
        with mock.patch.dict(os.environ, {"GITHUB_SHA": "3" * 40}), self.assertRaises(ValueError):
            dev.staged_material_sdk(self.root)
        self.assertEqual(self.calls, [])
        self.mutate = lambda called: witness.write_text('{"inert_material_only":true}\n')
        checked = dev.staged_material_sdk(self.root)
        self.assertEqual(self.calls, [argv])
        self.assertEqual(checked["schema"], "biocompiler.development-staged-material-sdk-feedback.v0.1")
        self.assertEqual(checked["status"], "passed")
        self.assertIs(checked["acceptance"], False)
        self.assertEqual(set(checked["outputs"]), {"staged-material-sdk-witness.json"})
        self.assertFalse((self.sdk_output / "staged-source-sdk.json").exists())
        log.unlink()
        self.fail = argv
        with self.assertRaisesRegex(ValueError, "Staged material SDK failed"):
            dev.staged_material_sdk(self.root)
        self.assertEqual(json.loads(report_path.read_text())["actions"][0]["returncode"], 1)
        self.fail = None
        log.unlink()
        feedback = self.sdk_output / "feedback.json"
        def mutate(called):
            witness.write_text('{"inert_material_only":true}\n')
            feedback.write_bytes(b"late mutation")
        self.mutate = mutate
        with self.assertRaisesRegex(ValueError, "Native feedback changed"):
            dev.staged_material_sdk(self.root)
        self.assertEqual(json.loads(report_path.read_text())["status"], "failed")


if __name__ == "__main__":
    unittest.main()
