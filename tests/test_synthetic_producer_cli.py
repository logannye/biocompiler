"""Public selection CLI preserves report bytes, errors and publication policy."""
from argparse import Namespace
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from biocompiler.cli import _bounded_text, _publish_report
from biocompiler.core_client import CoreProtocolError
from biocompiler.errors import SerializationError
from biocompiler.synthetic_producer_cli import selection_command
from test_core_synthetic_producer_public import fixture_executable, literals, encoded


class SyntheticProducerCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.positive, cls.negative = literals()

    def invoke(self, args, *, publish_report=_publish_report):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = selection_command(args, bounded_text=_bounded_text, publish_report=publish_report)
        return code, stdout.getvalue(), stderr.getvalue()

    def arguments(self, directory, executable):
        return Namespace(request=directory / "request.json", output=directory / "report.json", core_executable=executable,
            core_sha256=hashlib.sha256(executable.read_bytes()).hexdigest(), core_timeout=None)

    def test_actual_python_children_preserve_all_four_original_outputs_and_exit_codes(self):
        with tempfile.TemporaryDirectory(prefix="bioc-public-cli-") as temporary:
            directory = Path(temporary)
            executable = fixture_executable(directory)
            args = self.arguments(directory, executable)
            for fixture in self.positive:
                args.request.write_bytes(encoded(fixture["payload"]["build_request"]))
                args.output.unlink(missing_ok=True)
                with self.subTest(name=fixture["name"]), \
                        patch("biocompiler.cli.SyntheticBuildRequest.from_json", side_effect=AssertionError("Python source acceptance")), \
                        patch("biocompiler.cli.select_synthetic", side_effect=AssertionError("Python ranking")):
                    code, stdout, stderr = self.invoke(args)
                expected = fixture["expected"]
                self.assertEqual(code, expected["presentation"]["exit_code"])
                production = expected["production"]
                if production["outcome"] == "unsupported":
                    self.assertEqual(stdout, "")
                    self.assertEqual(stderr, "biocompiler: " + production["generation_error"]["formatted"] + "\n")
                    self.assertFalse(args.output.exists())
                else:
                    report = json.dumps(production["record"], sort_keys=True, indent=2, ensure_ascii=False) + "\n"
                    self.assertEqual(stdout, report)
                    self.assertEqual(stderr, "")
                    self.assertEqual(args.output.read_bytes(), report.encode())
                self.assertFalse(list(directory.glob(".report.json.*.tmp")))

    def test_original_native_authority_errors_keep_exact_messages_and_no_publication(self):
        with tempfile.TemporaryDirectory(prefix="bioc-public-cli-errors-") as temporary:
            directory = Path(temporary)
            args = self.arguments(directory, fixture_executable(directory))
            for fixture in self.negative:
                args.request.write_bytes(encoded(fixture["build_request"]))
                with self.subTest(name=fixture["name"]):
                    self.assertEqual(self.invoke(args), (2, "", "biocompiler: " + fixture["message"] + "\n"))
                self.assertFalse(args.output.exists())

    def test_original_json_syntax_errors_happen_before_any_core_call(self):
        cases = ((b'{"a":1,"a":2}', "Duplicate JSON key: a."), (b'{"a":NaN}', "Invalid JSON number: NaN."))
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            args = self.arguments(directory, fixture_executable(directory))
            for raw, expected in cases:
                args.request.write_bytes(raw)
                with patch("biocompiler.core_client._exchange") as exchange:
                    self.assertEqual(self.invoke(args), (2, "", "biocompiler: " + expected + "\n"))
                exchange.assert_not_called()
            args.request.write_bytes(b"{")
            with patch("biocompiler.core_client._exchange") as exchange:
                code, stdout, stderr = self.invoke(args)
            self.assertEqual((code, stdout), (2, ""))
            self.assertTrue(stderr.startswith("biocompiler: Invalid artifact JSON:"))
            exchange.assert_not_called()

    def test_existing_publication_rejections_and_atomic_errors_preserve_output(self):
        with tempfile.TemporaryDirectory(prefix="bioc-public-cli-publish-") as temporary:
            directory = Path(temporary)
            args = self.arguments(directory, fixture_executable(directory))
            raw = encoded(self.positive[0]["payload"]["build_request"])
            args.request.write_bytes(raw)
            args.output = args.request
            self.assertEqual(self.invoke(args), (2, "", "biocompiler: A report cannot overwrite its independent input authority.\n"))
            self.assertEqual(args.request.read_bytes(), raw)
            args.output = directory / "absent" / "report.json"
            self.assertEqual(self.invoke(args), (2, "", "biocompiler: Report destination parent must already exist.\n"))
            args.output = directory / "report.json"
            args.output.write_bytes(b"previous output")
            with patch("biocompiler.cli.os.replace", side_effect=OSError("Original atomic replace failure")):
                self.assertEqual(self.invoke(args), (2, "", "biocompiler: Original atomic replace failure\n"))
            self.assertEqual(args.output.read_bytes(), b"previous output")
            self.assertFalse(list(directory.glob(".report.json.*.tmp")))

    def test_explicit_core_options_require_valid_selection_and_never_fall_back(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            args = self.arguments(directory, fixture_executable(directory))
            args.request.write_bytes(encoded(self.positive[0]["payload"]["build_request"]))
            args.core_executable = None
            with patch("biocompiler.core_client._exchange") as exchange:
                self.assertEqual(self.invoke(args), (2, "", "biocompiler: Core timeout and digest options require an explicit executable.\n"))
            exchange.assert_not_called()
            args.core_executable = Path("/nonexistent/biocompiler-core")
            code, stdout, stderr = self.invoke(args)
            self.assertEqual((code, stdout), (2, ""))
            self.assertIn("Selected core is not executable", stderr)
            args.core_timeout = False
            self.assertEqual(self.invoke(args), (2, "", "biocompiler: Core timeout must be a finite positive number\n"))


if __name__ == "__main__":
    unittest.main()
