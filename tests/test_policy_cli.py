"""Actual authoring commands and atomic publication controls, without native code."""
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biocompiler.entrypoint import main
from biocompiler.policy import model as m
from biocompiler.policy.cli import _write
from biocompiler.policy.serialization import dumps, from_data
from tests.test_policy_handoff import request


class PolicyCliTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.document = request()
        self.input = self.root / "request.json"
        self.input.write_text(dumps(self.document), encoding="utf-8")

    def run_cli(self, *args):
        output, error = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            code = main(["policy", *map(str, args)])
        return code, output.getvalue(), error.getvalue()

    def test_check_json_flag_before_or_after_command(self):
        for args in (("--json", "check", self.input), ("check", self.input, "--json")):
            code, output, error = self.run_cli(*args)
            self.assertEqual((code, error), (0, ""), output)
            report = json.loads(output)
            self.assertEqual(report["status"], "complete")
            self.assertNotIn("accepted", output)

    def test_inspect_and_diff_load_documents_and_expose_real_changes(self):
        code, output, error = self.run_cli("inspect", self.input, "--json")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(json.loads(output)["check"]["status"], "complete")
        other = self.root / "other.json"
        other.write_text(dumps(replace(self.document, program=replace(self.document.program, id="different"))))
        code, output, error = self.run_cli("diff", self.input, other, "--json")
        self.assertEqual((code, error), (1, ""))
        comparison = json.loads(output)
        self.assertTrue(comparison["changes"])
        self.assertIn("different", output)
        code, output, error = self.run_cli("diff", self.input, self.input, "--json")
        self.assertEqual((code, error), (0, ""))
        self.assertTrue(json.loads(output)["identical_document"])

    def test_incomplete_and_malformed_documents_have_distinct_nonzero_exits(self):
        program = self.document.program
        draft = m.PolicyDraft("draft", program.semantics, program.declarations,
                              (m.Hole("missing", "Requirement", "What should hold?"),))
        self.input.write_text(dumps(draft))
        code, output, error = self.run_cli("check", self.input, "--json")
        self.assertEqual((code, error), (1, ""))
        self.assertEqual(json.loads(output)["status"], "incomplete")
        self.input.write_text('{"$type":"os.system"}')
        code, output, error = self.run_cli("check", self.input, "--json")
        self.assertEqual((code, output), (1, ""))
        self.assertEqual(json.loads(error)["status"], "error")

    def test_structural_error_returns_invalid_report_without_native_claim(self):
        invalid = replace(self.document, deployment=replace(self.document.deployment, bindings=()))
        self.input.write_text(dumps(invalid))
        code, output, error = self.run_cli("check", self.input, "--json")
        self.assertEqual((code, error), (1, ""))
        report = json.loads(output)
        self.assertEqual(report["status"], "invalid")
        self.assertTrue(any(item["severity"] == "error" for item in report["diagnostics"]))

    def test_schema_and_complete_request_export_remain_data_only(self):
        for command in ("export-schema", "export-request"):
            destination = self.root / (command + ".json")
            arguments = (self.input,) if command == "export-request" else ()
            with patch("subprocess.Popen", side_effect=AssertionError("No backend dispatch")):
                code, output, error = self.run_cli(command, *arguments, "--output", destination, "--json")
            self.assertEqual((code, error), (0, ""))
            self.assertEqual(json.loads(output)["status"], "written")
            value = json.loads(destination.read_text())
            if command == "export-request":
                self.assertEqual(from_data(value["request"]), self.document)
                self.assertEqual(value["semantic_status"], "unassessed")
                self.assertEqual(value["target_status"], "unassessed")
            else:
                self.assertIn("$schema", value)

    def test_exports_support_stdout_and_io_failures_return_two(self):
        for command, arguments in (("export-schema", ()), ("export-request", (self.input,))):
            code, output, error = self.run_cli(command, *arguments)
            self.assertEqual((code, error), (0, ""))
            self.assertIsInstance(json.loads(output), dict)
        code, output, error = self.run_cli("check", self.root / "missing.json", "--json")
        self.assertEqual((code, output), (2, ""))
        self.assertEqual(json.loads(error)["status"], "error")

    def test_export_refuses_unbound_program_and_preserves_prior_output(self):
        self.input.write_text(dumps(self.document.program))
        output = self.root / "output.json"
        output.write_bytes(b"prior")
        code, _, error = self.run_cli("export-request", self.input, "-o", output, "--replace", "--json")
        self.assertEqual(code, 1, error)
        self.assertEqual(output.read_bytes(), b"prior")

    def test_replacement_requires_explicit_option_and_does_not_replace_input(self):
        output = self.root / "output.json"
        output.write_bytes(b"prior")
        code, _, error = self.run_cli("export-schema", "-o", output, "--json")
        self.assertEqual(code, 2, error)
        self.assertEqual(output.read_bytes(), b"prior")
        code, _, error = self.run_cli("export-schema", "-o", output, "--replace", "--json")
        self.assertEqual(code, 0, error)
        self.assertIn("$schema", json.loads(output.read_text()))
        before = self.input.read_bytes()
        code, _, error = self.run_cli("inspect", self.input, "-o", self.input, "--replace", "--json")
        self.assertEqual(code, 2, error)
        self.assertEqual(self.input.read_bytes(), before)

    def test_output_symlink_and_failed_publication_preserve_existing_files(self):
        target = self.root / "target.json"
        target.write_bytes(b"prior")
        link = self.root / "link.json"
        link.symlink_to(target)
        with self.assertRaises(ValueError):
            _write(link, "new", replace=True)
        for failure in ("fsync", "replace"):
            with patch("biocompiler.policy.cli.os." + failure, side_effect=OSError("fault")):
                with self.assertRaises(OSError):
                    _write(target, "new", replace=True)
            self.assertEqual(target.read_bytes(), b"prior")
            self.assertEqual(list(self.root.glob(".biocompiler-policy-*")), [])

    def test_atomic_no_replace_rejects_racing_output_creation(self):
        output = self.root / "output.json"
        import os
        link = os.link
        def race(source, destination):
            Path(destination).write_bytes(b"racing writer")
            return link(source, destination)
        with patch("biocompiler.policy.cli.os.link", side_effect=race), self.assertRaises(FileExistsError):
            _write(output, "new", replace=False)
        self.assertEqual(output.read_bytes(), b"racing writer")
        self.assertEqual(list(self.root.glob(".biocompiler-policy-*")), [])


if __name__ == "__main__":
    unittest.main()
