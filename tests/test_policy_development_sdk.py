"""Mocked hosted SDK orchestration; no native programs or subprocesses execute."""
import json
from copy import deepcopy
from pathlib import Path
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
