"""Mocked hosted SDK orchestration; no native programs or subprocesses execute."""
import hashlib
import json
import subprocess
from copy import deepcopy
from pathlib import Path
import threading
import unittest
from unittest import mock

from tests import test_policy_development as fixtures
from tools import check_policy_development as dev


class PolicyDevelopmentSDKTests(unittest.TestCase):
    def setUp(self):
        self.peer = fixtures.PolicyDevelopmentTests()
        self.peer.setUp()
        self.addCleanup(self.peer.doCleanups)
        self.root = self.peer.root
        dev.prepare(self.root)
        dev.run(self.root)
        self.actions = []

    def command(self, root, output, name, argv):
        self.actions.append((name, argv))
        target = Path(argv[-1])
        target.write_text('{"mock_only":true}\n')
        return {"name": name, "status": "passed", "returncode": 0}

    def run_sdk(self):
        with mock.patch.object(dev, "command", side_effect=self.command):
            return dev.public_sdk(self.root)

    def test_exact_commands_same_build_and_separate_truthful_feedback(self):
        result = self.run_sdk()
        self.assertEqual(result["status"], "passed")
        self.assertIs(result["acceptance"], False)
        self.assertEqual(result["sources_before"], result["sources_after"])
        self.assertEqual(self.actions[0][0], "component-originals")
        self.assertEqual(self.actions[0][1], ["opam", "exec", "--",
            str(self.root / dev.SDK_BINARIES["originals"]),
            *(str(self.root / path) for path in dev.SDK_ORIGINALS),
            str(self.root / "generated/development-feedback/component-originals.json")])
        self.assertEqual(self.actions[1][0], "component-sdk")
        self.assertEqual(set(result["outputs"]), {"component-originals.json", "sdk-witness.json"})
        self.assertEqual(set(result["binaries"]), set(dev.SDK_BINARIES.values()))

    def test_instance_commands_preserve_separate_domain_authority_and_receipts(self):
        with mock.patch.object(dev, "command", side_effect=self.command):
            result = dev.instance_sdk(self.root)
        output = self.root / "generated/development-feedback"
        self.assertEqual(result["schema"], "biocompiler.development-instance-sdk-feedback.v0.1")
        self.assertIs(result["acceptance"], False)
        self.assertEqual(self.actions[0], ("instance-originals", ["opam", "exec", "--",
            str(self.root / dev.SDK_BINARIES["instance_originals"]),
            *(str(self.root / path) for path in dev.INSTANCE_ORIGINALS), str(output / "instance-originals.json")]))
        self.assertEqual(self.actions[1], ("instance-sdk", [dev.sys.executable, "-B",
            str(self.root / "tools/check_policy_instance_material.py"),
            "--fixture", str(output / "instance-originals.json"),
            "--core", str(self.root / dev.SDK_BINARIES["core"]),
            "--verify", str(self.root / dev.SDK_BINARIES["verify"]),
            "--output", str(output / "instance-sdk-witness.json")]))
        self.assertEqual(set(result["outputs"]), {"instance-originals.json", "instance-sdk-witness.json"})
        self.assertFalse((output / "public-sdk.json").exists())

    def test_prerequisite_campaign_uses_seven_original_sources_and_isolated_receipts(self):
        with mock.patch.object(dev, "command", side_effect=self.command):
            result = dev.prerequisite_sdk(self.root)
        output = self.root / "generated/development-feedback"
        self.assertEqual(result["schema"], "biocompiler.development-prerequisite-sdk-feedback.v0.1")
        self.assertEqual(self.actions[0], ("prerequisite-originals", ["opam", "exec", "--",
            str(self.root / dev.SDK_BINARIES["prerequisite_originals"]),
            *(str(self.root / path) for path in dev.PREREQUISITE_ORIGINALS), str(output / "prerequisite-originals.json")]))
        self.assertEqual(len(dev.PREREQUISITE_ORIGINALS), 7)
        self.assertEqual(self.actions[1][0], "prerequisite-sdk")
        self.assertIn(str(self.root / "tools/check_policy_prerequisite_material.py"), self.actions[1][1])
        self.assertEqual(set(result["outputs"]), {"prerequisite-originals.json", "prerequisite-sdk-witness.json"})
        self.assertIs(result["acceptance"], False)
        self.assertFalse((output / "instance-sdk.json").exists())
        self.assertFalse((output / "public-sdk.json").exists())

    def test_two_observation_campaign_uses_nine_original_sources_and_isolated_receipts(self):
        with mock.patch.object(dev, "command", side_effect=self.command):
            result = dev.two_observation_sdk(self.root)
        output = self.root / "generated/development-feedback"
        self.assertEqual(result["schema"], "biocompiler.development-two-observation-sdk-feedback.v0.1")
        self.assertEqual(self.actions[0], ("two-observation-originals", ["opam", "exec", "--",
            str(self.root / dev.SDK_BINARIES["two_observation_originals"]),
            *(str(self.root / path) for path in dev.TWO_OBSERVATION_ORIGINALS), str(output / "two-observation-originals.json")]))
        self.assertEqual(len(dev.TWO_OBSERVATION_ORIGINALS), 9)
        self.assertEqual(self.actions[1][0], "two-observation-sdk")
        self.assertIn(str(self.root / "tools/check_policy_two_observation_material.py"), self.actions[1][1])
        self.assertEqual(set(result["outputs"]), {"two-observation-originals.json", "two-observation-sdk-witness.json"})
        self.assertIs(result["acceptance"], False)
        self.assertFalse((output / "instance-sdk.json").exists())
        self.assertFalse((output / "public-sdk.json").exists())

    def test_multi_member_campaign_uses_three_original_sources_and_isolated_receipts(self):
        with mock.patch.object(dev, "command", side_effect=self.command):
            result = dev.multi_member_sdk(self.root)
        output = self.root / "generated/development-feedback"
        self.assertEqual(result["schema"], "biocompiler.development-multi-member-sdk-feedback.v0.1")
        self.assertEqual(self.actions[0], ("multi-member-originals", ["opam", "exec", "--",
            str(self.root / dev.SDK_BINARIES["multi_member_originals"]),
            *(str(self.root / path) for path in dev.MULTI_MEMBER_ORIGINALS), str(output / "multi-member-originals.json")]))
        self.assertEqual(len(dev.MULTI_MEMBER_ORIGINALS), 3)
        self.assertEqual(self.actions[1][0], "multi-member-sdk")
        self.assertIn(str(self.root / "tools/check_policy_multi_member_material.py"), self.actions[1][1])
        self.assertEqual(set(result["outputs"]), {"multi-member-originals.json", "multi-member-sdk-witness.json"})
        self.assertIs(result["acceptance"], False)
        self.assertFalse((output / "instance-sdk.json").exists())
        self.assertFalse((output / "public-sdk.json").exists())

    def test_grounded_helper_campaign_uses_five_original_sources_and_isolated_receipts(self):
        with mock.patch.object(dev, "command", side_effect=self.command):
            result = dev.grounded_helper_sdk(self.root)
        output = self.root / "generated/development-feedback"
        self.assertEqual(result["schema"], "biocompiler.development-grounded-helper-sdk-feedback.v0.1")
        self.assertEqual(self.actions[0], ("grounded-helper-originals", ["opam", "exec", "--",
            str(self.root / dev.SDK_BINARIES["grounded_helper_originals"]),
            *(str(self.root / path) for path in dev.GROUNDED_HELPER_ORIGINALS), str(output / "grounded-helper-originals.json")]))
        self.assertEqual(len(dev.GROUNDED_HELPER_ORIGINALS), 5)
        self.assertEqual(self.actions[1][0], "grounded-helper-sdk")
        self.assertIn(str(self.root / "tools/check_policy_grounded_helper_material.py"), self.actions[1][1])
        self.assertEqual(set(result["outputs"]), {"grounded-helper-originals.json", "grounded-helper-sdk-witness.json"})
        self.assertIs(result["acceptance"], False)
        self.assertFalse((output / "instance-sdk.json").exists())
        self.assertFalse((output / "public-sdk.json").exists())

    def test_source_or_built_binary_change_rejects_before_launch(self):
        for relative in ("src/empty.py", dev.SDK_BINARIES["core"], dev.SDK_BINARIES["verify"], dev.SDK_BINARIES["originals"]):
            with self.subTest(relative=relative):
                path = self.root / relative
                original = path.read_bytes()
                path.write_bytes(b"changed")
                with self.assertRaises(ValueError):
                    self.run_sdk()
                path.write_bytes(original)
                self.assertEqual(self.actions, [])

    def test_partial_changed_or_reordered_native_records_never_launch(self):
        path = self.root / "generated/development-feedback/feedback.json"
        raw = path.read_bytes()
        original = json.loads(raw)
        mutants = []
        for group in ("actions", "suites"):
            changed = deepcopy(original)
            changed[group].pop()
            mutants.append(changed)
            changed = deepcopy(original)
            changed[group][0]["status"] = "failed"
            mutants.append(changed)
            changed = deepcopy(original)
            changed[group].reverse()
            mutants.append(changed)
            changed = deepcopy(original)
            changed[group][0]["argv"] = ["unreviewed"]
            mutants.append(changed)
        for changed in mutants:
            path.write_text(json.dumps(changed))
            with self.assertRaises(ValueError):
                self.run_sdk()
            self.assertEqual(self.actions, [])
        path.write_bytes(raw)
        log = self.root / "generated/development-feedback/build.log"
        log.write_bytes(b"changed native log")
        with self.assertRaises(ValueError):
            self.run_sdk()
        self.assertEqual(self.actions, [])

    def test_late_native_feedback_or_log_mutation_never_passes(self):
        output = self.root / "generated/development-feedback"
        for name in ("feedback.json", "build.log"):
            path = output / name
            raw = path.read_bytes()
            def mutate(root, destination, action, argv):
                result = self.command(root, destination, action, argv)
                if action == "component-sdk":
                    path.write_bytes(b"late mutation")
                return result
            with self.subTest(name=name), mock.patch.object(dev, "command", side_effect=mutate):
                with self.assertRaises(ValueError):
                    dev.public_sdk(self.root)
            path.write_bytes(raw)
            self.assertEqual(json.loads((output / "public-sdk.json").read_text())["status"], "failed")

    def test_failed_native_or_sdk_and_late_mutation_never_pass(self):
        path = self.root / "generated/development-feedback/feedback.json"
        original = path.read_bytes()
        failed = json.loads(original)
        failed["status"] = "failed"
        path.write_text(json.dumps(failed))
        with self.assertRaises(ValueError):
            self.run_sdk()
        self.assertEqual(self.actions, [])
        path.write_bytes(original)
        with mock.patch.object(dev, "command", return_value={"status": "failed", "returncode": 1}):
            with self.assertRaisesRegex(ValueError, "component-originals failed"):
                dev.public_sdk(self.root)
        original_command = self.command
        def mutate(root, output, name, argv):
            result = original_command(root, output, name, argv)
            if name == "component-sdk":
                (self.root / dev.SDK_BINARIES["core"]).write_bytes(b"late mutation")
            return result
        with mock.patch.object(dev, "command", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "executable changed during"):
                dev.public_sdk(self.root)
        result = json.loads((self.root / "generated/development-feedback/public-sdk.json").read_text())
        self.assertEqual(result["status"], "failed")


class PolicyDevelopmentSelectionSDKTests(unittest.TestCase):
    """Inert command results bind both SDK stages to the same hosted build."""

    def setUp(self):
        self.peer = fixtures.PolicyDevelopmentTests()
        self.peer.setUp()
        self.addCleanup(self.peer.doCleanups)
        self.root = self.peer.root
        for relative in set(dev.SDK_ORIGINALS + dev.SELECTION_ORIGINALS + dev.INSTANCE_ORIGINALS):
            path = self.root / relative
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("independent source declaration\n")
        self.peer.freeze_tree()
        dev.prepare(self.root)
        dev.run(self.root)
        self.actions = []
        with mock.patch.object(dev, "command", side_effect=self.command):
            dev.public_sdk(self.root)
        self.actions.clear()
        self.output = self.root / "generated/development-feedback"

    def command(self, root, output, name, argv):
        self.actions.append((name, argv))
        Path(argv[-1]).write_text('{"mock_only":true}\n')
        log = output / (name + ".log")
        log.write_bytes(b"inert successful command\n")
        return {"name": name, "argv": argv, "log": log.name, "status": "passed", "returncode": 0,
                "log_pin": {"sha256": hashlib.sha256(log.read_bytes()).hexdigest(), "size": log.stat().st_size}}

    def run_sdk(self):
        with mock.patch.object(dev, "command", side_effect=self.command):
            return dev.selection_sdk(self.root)

    def test_exact_selection_mode_commands_sources_and_separate_outputs(self):
        old = (self.output / "public-sdk.json").read_bytes()
        result = self.run_sdk()
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["schema"], "biocompiler.development-selection-sdk-feedback.v0.1")
        self.assertIs(result["acceptance"], False)
        self.assertEqual(result["sources_before"], result["sources_after"])
        self.assertEqual(self.actions[0], ("selection-originals", ["opam", "exec", "--",
            str(self.root / dev.SDK_BINARIES["originals"]), "--selection",
            *(str(self.root / path) for path in dev.SELECTION_ORIGINALS),
            str(self.output / "selection-originals.json")]))
        self.assertEqual(self.actions[1], ("selection-sdk", [dev.sys.executable, "-B",
            str(self.root / "tools/check_policy_component_selection.py"),
            "--fixture", str(self.output / "selection-originals.json"),
            "--core", str(self.root / dev.SDK_BINARIES["core"]),
            "--verify", str(self.root / dev.SDK_BINARIES["verify"]),
            "--output", str(self.output / "selection-sdk-witness.json")]))
        self.assertEqual(tuple(result["source_inputs"]), (
            "core/test/data/policy_material_request_v01.json", "core/test/policy_component_support/literals.ml",
            "core/test/policy_component_support/requests.ml", "core/test/policy_component_support/selection_requests.ml"))
        self.assertEqual(set(result["outputs"]), {"selection-originals.json", "selection-sdk-witness.json"})
        self.assertEqual(result["component_sdk_feedback"], dev.pin(self.root, "generated/development-feedback/public-sdk.json"))
        self.assertEqual((self.output / "public-sdk.json").read_bytes(), old)

    def test_partial_changed_or_reordered_component_campaign_never_launches(self):
        path = self.output / "public-sdk.json"
        raw = path.read_bytes()
        original = json.loads(raw)
        mutants = []
        for key, value in (("status", "failed"), ("acceptance", True), ("schema", "foreign"),
                           ("native_feedback", {}), ("binaries", {}), ("outputs", {})):
            changed = deepcopy(original)
            changed[key] = value
            mutants.append(changed)
        for operation in (lambda rows: rows.pop(), lambda rows: rows.reverse(),
                          lambda rows: rows[0].update(argv=["unreviewed"]),
                          lambda rows: rows[0].update(returncode=False),
                          lambda rows: rows[0].update(log="foreign.log")):
            changed = deepcopy(original)
            operation(changed["actions"])
            mutants.append(changed)
        for index, changed in enumerate(mutants):
            with self.subTest(index=index):
                path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):
                    self.run_sdk()
                self.assertEqual(self.actions, [])
        path.write_bytes(raw)

    def test_empty_successful_component_logs_keep_exact_pins_and_command_checks(self):
        receipt = self.output / "public-sdk.json"
        original = receipt.read_bytes()
        for index, name in enumerate(("component-originals", "component-sdk")):
            log = self.output / (name + ".log")
            original_log = log.read_bytes()
            log.write_bytes(b"")
            document = json.loads(original)
            document["actions"][index]["log_pin"] = {
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "size": 0,
            }
            receipt.write_text(json.dumps(document))
            with self.subTest(log=name):
                self.assertEqual(self.run_sdk()["status"], "passed")
                self.assertEqual(log.read_bytes(), b"")
            self.actions.clear()
            for field, value in (("log_pin", {"sha256": "0" * 64, "size": 0}),
                                 ("log_pin", {"sha256": document["actions"][index]["log_pin"]["sha256"], "size": 1}),
                                 ("status", "failed"), ("returncode", 1)):
                changed = deepcopy(document)
                changed["actions"][index][field] = value
                receipt.write_text(json.dumps(changed))
                with self.subTest(log=name, field=field, value=value), self.assertRaises(ValueError):
                    self.run_sdk()
                self.assertEqual(self.actions, [])
            receipt.write_text(json.dumps(document))
            log.write_bytes(b"changed after empty success")
            with self.assertRaises(ValueError):
                self.run_sdk()
            self.assertEqual(self.actions, [])
            log.write_bytes(original_log)
            receipt.write_bytes(original)

    def test_changed_prerequisite_files_and_selection_sources_never_launch(self):
        files = [self.output / name for name in ("feedback.json", "build.log", "component-originals.log",
                 "component-sdk.log", "component-originals.json", "sdk-witness.json")]
        files += [self.root / path for path in (*dev.SDK_BINARIES.values(), *dev.SELECTION_ORIGINALS)]
        for path in files:
            with self.subTest(path=path):
                raw = path.read_bytes()
                path.write_bytes(b"changed")
                with self.assertRaises((ValueError, KeyError)):
                    self.run_sdk()
                path.write_bytes(raw)
                self.assertEqual(self.actions, [])

    def test_late_change_to_any_prior_authority_or_binary_fails(self):
        files = [self.output / name for name in ("feedback.json", "build.log", "public-sdk.json",
                 "component-sdk.log", "sdk-witness.json", "component-originals.json")]
        files += [self.root / path for path in (*dev.SDK_BINARIES.values(), *dev.SELECTION_ORIGINALS)]
        for path in files:
            raw = path.read_bytes()
            def mutate(root, output, name, argv):
                result = self.command(root, output, name, argv)
                if name == "selection-sdk":
                    path.write_bytes(b"late mutation")
                return result
            with self.subTest(path=path), mock.patch.object(dev, "command", side_effect=mutate):
                with self.assertRaises(ValueError):
                    dev.selection_sdk(self.root)
                self.assertEqual(json.loads((self.output / "selection-public-sdk.json").read_text())["status"], "failed")
            path.write_bytes(raw)

    def test_each_failed_selection_command_retains_failed_feedback(self):
        for failed in ("selection-originals", "selection-sdk"):
            self.actions.clear()
            def command(root, output, name, argv):
                row = self.command(root, output, name, argv)
                if name == failed:
                    row.update(status="failed", returncode=1)
                return row
            with self.subTest(command=failed), mock.patch.object(dev, "command", side_effect=command):
                with self.assertRaisesRegex(ValueError, failed + " failed"):
                    dev.selection_sdk(self.root)
            report = json.loads((self.output / "selection-public-sdk.json").read_text())
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["actions"][-1]["name"], failed)
            self.assertEqual(len(self.actions), 1 if failed == "selection-originals" else 2)

    def test_selection_timeout_retains_incomplete_witness_without_promotion(self):
        witness = self.output / "selection-sdk-witness.json"
        partial = {"status": "incomplete", "acceptance": False,
                   "observations": [{"inert": index} for index in range(26)]}
        observed_timeouts = []

        def launch(argv, *, cwd, stdout, stderr, timeout, check):
            self.assertEqual(cwd, self.root)
            self.assertEqual(stderr, subprocess.STDOUT)
            self.assertFalse(check)
            observed_timeouts.append(timeout)
            if argv[0] == "opam":
                Path(argv[-1]).write_text('{"inert_source_only":true}\n')
                return subprocess.CompletedProcess(argv, 0)
            witness.write_text(json.dumps(partial))
            raise subprocess.TimeoutExpired(argv, timeout)

        with mock.patch.object(dev.subprocess, "run", side_effect=launch):
            with self.assertRaisesRegex(ValueError, "Selection SDK selection-sdk failed"):
                dev.selection_sdk(self.root)
        self.assertEqual(observed_timeouts, [900, 1800])
        report = json.loads((self.output / "selection-public-sdk.json").read_text())
        self.assertEqual(report["status"], "failed")
        self.assertIs(report["acceptance"], False)
        self.assertNotIn("outputs", report)
        failed = report["actions"][-1]
        self.assertEqual(failed["name"], "selection-sdk")
        self.assertEqual(failed["status"], "failed")
        self.assertNotIn("returncode", failed)
        self.assertIn("1800", failed["error"])
        self.assertEqual(failed["log_pin"], {"sha256": hashlib.sha256(b"").hexdigest(), "size": 0})
        self.assertEqual(json.loads(witness.read_text()), partial)

    def test_workflow_retains_both_ordered_sdk_stages(self):
        text = (Path(__file__).resolve().parents[1] / dev.WORKFLOW).read_text()
        commands = []
        for line in text.splitlines():
            if line.strip().startswith("run: ") and line.strip() != "run: |":
                commands.append(line.strip()[5:])
            elif line.startswith("          python "):
                commands.append(line.strip())
        self.assertEqual(commands, [
            "python -B tools/check_policy_development.py prepare",
            "python -B tools/generate_policy_wire_schema.py --check",
            "python -B tools/check_policy_source_context_coverage.py",
            "python -B tools/check_policy_material_rule_coverage.py",
            "python -B tools/check_policy_public_api_coverage.py",
            "python -B tools/migration_inventory.py --check",
            "python -B -m tools.generate_policy_quantitative_composition_fixture --check",
            "python -B -m tools.generate_policy_approximation_fixture --check",
            "python -B -m tools.generate_policy_realization_evidence_fixture --check",
            "python -B tools/check_policy_development.py run",
            "python -B tools/check_policy_quantitative_assurance.py \\",
            "python -B tools/check_policy_development.py sdk-all",
        ])
        self.assertLess(text.index("tools/migration_inventory.py --check"), text.index("uses: ocaml/setup-ocaml@"))
        self.assertEqual(text.count("PYTHONPATH: src"), 3)
        self.assertIn("path: generated/development-feedback/", text)
        self.assertIn("timeout-minutes: 45", text)


class PolicyDevelopmentParallelSDKTests(unittest.TestCase):
    """Exercise real receipt wrappers concurrently around inert child results."""

    def setUp(self):
        self.peer = fixtures.PolicyDevelopmentTests()
        self.peer.setUp()
        self.addCleanup(self.peer.doCleanups)
        self.root = self.peer.root
        for relative in set(dev.SDK_ORIGINALS + dev.SELECTION_ORIGINALS + dev.INSTANCE_ORIGINALS):
            path = self.root / relative
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("independent source declaration\n")
        self.peer.freeze_tree()
        dev.prepare(self.root)
        dev.run(self.root)
        self.output = self.root / "generated/development-feedback"
        self.native = (self.output / "feedback.json").read_bytes()
        self.lock = threading.Lock()
        self.started, self.finished = [], []
        self.active = self.maximum = 0
        self.rendezvous = threading.Barrier(2)
        self.failed = None

    def command(self, root, output, name, argv):
        self.assertEqual(root, self.root)
        self.assertEqual(output, self.output)
        with self.lock:
            self.started.append(name)
            self.active += 1
            self.maximum = max(self.maximum, self.active)
        try:
            if name in ("component-sdk", "staged-source-sdk"):
                self.rendezvous.wait(timeout=5)
            if name.startswith("selection-"):
                public = json.loads((output / "public-sdk.json").read_bytes())
                self.assertEqual(public["status"], "passed")
                self.assertIn("component-sdk", self.finished)
            # Exclusive writes expose any overlap in campaign-owned paths.
            with Path(argv[-1]).open("x") as stream:
                stream.write('{"inert_child_only":true}\n')
            log = output / (name + ".log")
            with log.open("xb") as stream:
                stream.write(b"inert complete command\n")
            return {"name": name, "argv": argv, "log": log.name,
                    "status": "failed" if name == self.failed else "passed",
                    "returncode": 1 if name == self.failed else 0,
                    "elapsed_seconds": 0.0,
                    "log_pin": {"sha256": hashlib.sha256(log.read_bytes()).hexdigest(), "size": log.stat().st_size}}
        finally:
            with self.lock:
                self.active -= 1
                self.finished.append(name)

    def read(self, name):
        return json.loads((self.output / name).read_bytes())

    def test_both_lanes_overlap_keep_dependencies_and_disjoint_complete_receipts(self):
        with mock.patch.object(dev, "command", side_effect=self.command):
            reports = dev.sdk_all(self.root)
        self.assertEqual(dev.PARALLEL_WORKERS, 2)
        self.assertEqual(self.maximum, 2)
        self.assertEqual(self.active, 0)
        self.assertCountEqual(self.started, ["component-originals", "component-sdk", "selection-originals",
            "selection-sdk", "instance-originals", "instance-sdk", "prerequisite-originals", "prerequisite-sdk", "two-observation-originals", "two-observation-sdk", "multi-member-originals", "multi-member-sdk", "grounded-helper-originals", "grounded-helper-sdk", "staged-source-sdk", "staged-material-sdk", "researcher-alpha-sdk"])
        self.assertLess(self.finished.index("component-sdk"), self.finished.index("selection-originals"))
        self.assertLess(self.started.index("instance-sdk"), self.started.index("prerequisite-sdk"))
        self.assertLess(self.started.index("prerequisite-sdk"), self.started.index("two-observation-sdk"))
        self.assertLess(self.started.index("two-observation-sdk"), self.started.index("staged-source-sdk"))
        self.assertLess(self.started.index("staged-source-sdk"), self.started.index("staged-material-sdk"))
        self.assertLess(self.started.index("staged-material-sdk"), self.started.index("researcher-alpha-sdk"))
        self.assertEqual(list(reports), ["public-sdk", "selection-sdk", "instance-sdk", "prerequisite-sdk", "two-observation-sdk", "multi-member-sdk", "grounded-helper-sdk", "staged-source-sdk", "staged-material-sdk", "researcher-alpha-sdk"])
        self.assertTrue(all(row["status"] == "passed" and row["acceptance"] is False for row in reports.values()))
        names = {"public-sdk": "public-sdk.json", "selection-sdk": "selection-public-sdk.json",
                 "instance-sdk": "instance-sdk.json", "prerequisite-sdk": "prerequisite-sdk.json", "two-observation-sdk": "two-observation-sdk.json", "multi-member-sdk": "multi-member-sdk.json", "grounded-helper-sdk": "grounded-helper-sdk.json", "staged-source-sdk": "staged-source-sdk.json", "staged-material-sdk": "staged-material-sdk.json",
                 "researcher-alpha-sdk": "researcher-alpha-sdk.json"}
        for name, report in reports.items():
            self.assertEqual(self.read(names[name]), report)
            self.assertEqual(report["sources_before"], report["sources_after"])
            self.assertEqual(report["native_feedback"], dev.pin(self.root, "generated/development-feedback/feedback.json"))
        self.assertEqual((self.output / "feedback.json").read_bytes(), self.native)

    def check_failed_lane(self, failed):
        self.failed = failed
        with mock.patch.object(dev, "command", side_effect=self.command):
            with self.assertRaisesRegex(ValueError, "Development SDK lanes failed"):
                dev.sdk_all(self.root)
        self.assertEqual(self.active, 0)
        self.assertEqual((self.output / "feedback.json").read_bytes(), self.native)
        if failed == "component-sdk":
            self.assertEqual(self.read("public-sdk.json")["status"], "failed")
            self.assertFalse((self.output / "selection-public-sdk.json").exists())
            self.assertNotIn("selection-originals", self.started)
            self.assertEqual(self.read("staged-source-sdk.json")["status"], "passed")
            self.assertEqual(self.read("staged-material-sdk.json")["status"], "passed")
            self.assertEqual(self.read("researcher-alpha-sdk.json")["status"], "passed")
        else:
            self.assertEqual(self.read("staged-source-sdk.json")["status"], "failed")
            self.assertFalse((self.output / "staged-material-sdk.json").exists())
            self.assertNotIn("staged-material-sdk", self.started)
            self.assertNotIn("researcher-alpha-sdk", self.started)
            self.assertEqual(self.read("public-sdk.json")["status"], "passed")
            self.assertEqual(self.read("selection-public-sdk.json")["status"], "passed")

    def test_component_failure_skips_selection_and_drains_complete_staged_lane(self):
        self.check_failed_lane("component-sdk")

    def test_staged_failure_drains_complete_component_and_selection_lane(self):
        self.check_failed_lane("staged-source-sdk")

    def test_binary_mutation_during_overlap_prevents_both_lane_success(self):
        mutated = threading.Event()

        def command(root, output, name, argv):
            result = self.command(root, output, name, argv)
            if name == "component-sdk":
                (self.root / dev.SDK_BINARIES["core"]).write_bytes(b"changed while both lanes active")
                mutated.set()
            elif name == "staged-source-sdk":
                self.assertTrue(mutated.wait(5))
            return result

        with mock.patch.object(dev, "command", side_effect=command):
            with self.assertRaisesRegex(ValueError, "Development SDK lanes failed"):
                dev.sdk_all(self.root)
        self.assertEqual(self.active, 0)
        self.assertEqual(self.read("public-sdk.json")["status"], "failed")
        self.assertEqual(self.read("staged-source-sdk.json")["status"], "failed")
        self.assertNotIn("selection-sdk", self.started)
        self.assertNotIn("staged-material-sdk", self.started)
