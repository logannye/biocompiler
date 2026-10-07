"""Typed SDK and CLI transport tests with inert adversarial Python peers."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from biocompiler.core_client import CoreTimeout
from biocompiler.policy import operational
from biocompiler.policy.cli import main
from biocompiler.policy.serialization import dump
from tests import test_core_policy_operational as peer_tools


class OperationalPolicySdkCliTests(unittest.TestCase):
    def setUp(self):
        self.peer = peer_tools.OperationalPolicyTransportTests()
        self.peer.setUp()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.document = self.root / "policy.json"
        dump(self.peer.authoring, self.document)
        self.definitions = self.write("definitions.json", self.peer.definitions)
        self.candidate = self.write("candidate.json", self.peer.candidate)
        self.timeline = self.write("timeline.json", self.peer.timeline)
        self.report = self.write("report.json", peer_tools.report(self.peer.payload(), executing=True))

    def write(self, name, value):
        path = self.root / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def args(self, command):
        arguments = [command, str(self.document), "--core", sys.executable, "--definitions", str(self.definitions)]
        if command != "compile-native":
            arguments += ["--candidate", str(self.candidate)]
        if command in ("execute-native", "replay-execution-native"):
            arguments += ["--timeline", str(self.timeline)]
        if command == "replay-execution-native":
            arguments += ["--report", str(self.report)]
        return arguments

    def run_cli(self, arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(arguments)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_typed_bridge_only_serializes_complete_original_documents(self):
        with self.peer.exchange(), patch("biocompiler.policy.validation.check", side_effect=AssertionError("Python semantic fallback")):
            compiled = operational.compile(self.peer.authoring, definitions=self.peer.definitions, client=self.peer.client)
            checked = operational.check_lowering(self.peer.authoring, definitions=self.peer.definitions,
                                                 candidate=compiled.candidate, client=self.peer.client)
            executed = operational.execute(self.peer.authoring, definitions=self.peer.definitions,
                                           candidate=compiled.candidate, timeline=self.peer.timeline, client=self.peer.client)
            replayed = operational.replay(self.peer.authoring, definitions=self.peer.definitions,
                                          candidate=compiled.candidate, timeline=self.peer.timeline,
                                          report=executed.report, client=self.peer.client)
        self.assertEqual(compiled.report, checked.report)
        self.assertEqual(executed.report, replayed.report)
        self.assertEqual(self.peer.calls[-1]["payload"]["document"], self.peer.document)

    def test_typed_bridge_refuses_unfrozen_or_executable_objects(self):
        for document in (self.peer.document, object(), lambda: self.peer.authoring):
            with self.subTest(document=type(document)), self.assertRaises(TypeError):
                operational.compile(document, definitions=self.peer.definitions, client=self.peer.client)

    def test_all_cli_operations_print_complete_native_json(self):
        for command, operation in (("compile-native", "compile-policy"), ("check-lowering-native", "check-policy-lowering"),
                                   ("execute-native", "execute-policy"), ("replay-execution-native", "replay-policy-execution")):
            with self.subTest(command=command), self.peer.exchange():
                code, stdout, stderr = self.run_cli(self.args(command))
            self.assertEqual((code, stderr), (0, ""), stdout)
            value = json.loads(stdout)
            self.assertEqual(value["candidate"], self.peer.candidate)
            self.assertEqual(value["report"]["artifact"], "withheld")
            self.assertEqual(self.peer.calls[-1]["operation"], operation)

    def test_cli_requires_explicit_backend_and_original_authority_files(self):
        for arguments in (
            ["compile-native", str(self.document), "--definitions", str(self.definitions)],
            ["compile-native", str(self.document), "--verify", sys.executable, "--definitions", str(self.definitions)],
            ["execute-native", str(self.document), "--core", sys.executable],
        ):
            with self.subTest(arguments=arguments), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main(arguments)
            self.assertEqual(error.exception.code, 2)

    def test_cli_accepts_prior_wrappers_but_rechecks_external_document_and_definitions(self):
        wrapper = peer_tools.result(self.peer.payload(), "execute-policy")
        self.candidate.write_text(json.dumps(wrapper), encoding="utf-8")
        self.report.write_text(json.dumps(wrapper), encoding="utf-8")
        with self.peer.exchange():
            code, stdout, stderr = self.run_cli(self.args("replay-execution-native"))
        self.assertEqual((code, stderr), (0, ""), stdout)
        self.assertEqual(self.peer.calls[-1]["payload"]["document"], self.peer.document)
        self.assertEqual(self.peer.calls[-1]["payload"]["definitions"], self.peer.definitions)
        self.assertEqual(self.peer.calls[-1]["payload"]["report"], wrapper["report"])

    def test_cli_writes_atomically_and_cannot_replace_any_input_authority(self):
        output = self.root / "execution.json"
        with self.peer.exchange():
            code, stdout, stderr = self.run_cli([*self.args("execute-native"), "--output", str(output), "--json"])
        self.assertEqual((code, stderr), (0, ""), stdout)
        self.assertEqual(json.loads(stdout)["status"], "written")
        self.assertEqual(json.loads(output.read_text())["report"]["execution"]["status"], "complete")
        for path in (self.document, self.definitions, self.candidate, self.timeline, self.report):
            before = path.read_bytes()
            with self.subTest(path=path.name), self.peer.exchange():
                code, stdout, stderr = self.run_cli([*self.args("replay-execution-native"), "--output", str(path), "--replace", "--json"])
            self.assertEqual(code, 2, stderr)
            self.assertEqual(path.read_bytes(), before)

    def test_cli_protocol_failure_withholds_output_and_does_not_fall_back(self):
        output = self.root / "output.json"
        output.write_bytes(b"existing result")
        with self.peer.exchange(failure=CoreTimeout("native timeout")), patch("biocompiler.policy.validation.check", side_effect=AssertionError("Python fallback")):
            code, stdout, stderr = self.run_cli([*self.args("execute-native"), "--output", str(output), "--replace", "--json"])
        self.assertEqual((code, stdout), (2, ""))
        self.assertIn("native timeout", json.loads(stderr)["message"])
        self.assertEqual(output.read_bytes(), b"existing result")

    def test_cli_requirement_failure_has_distinct_exit_without_withholding_trace(self):
        for status, expected_exit in (("pass", 0), ("fail", 1), ("unknown", 0), ("unsupported", 0)):
            def mutate(value):
                value["report"]["execution"]["requirements"][0]["status"] = status
                value["report_fingerprint"] = peer_tools.digest(value["report"])
            with self.subTest(status=status), self.peer.exchange(mutate=mutate):
                code, stdout, stderr = self.run_cli(self.args("execute-native"))
            self.assertEqual((code, stderr), (expected_exit, ""), stdout)
            self.assertEqual(json.loads(stdout)["report"]["execution"]["requirements"][0]["status"], status)

    def test_cli_json_inputs_are_inert_and_reject_duplicate_keys(self):
        for text in ('__import__("os").system("false")', '{"profile":"first","profile":"second"}'):
            self.definitions.write_text(text, encoding="utf-8")
            with self.subTest(text=text), patch("subprocess.Popen", side_effect=AssertionError("Must not execute input")):
                code, stdout, stderr = self.run_cli([*self.args("compile-native"), "--json"])
            self.assertEqual((code, stdout), (2, ""))
            self.assertEqual(json.loads(stderr)["status"], "error")


if __name__ == "__main__":
    unittest.main()
