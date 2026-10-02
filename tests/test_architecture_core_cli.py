"""Architecture CLI selection/publication contracts; native execution is hosted.

The bridge outputs below are typed stand-ins for fresh native operation results.
Protocol and semantic parity are covered by their dedicated retained campaigns.
"""

from contextlib import ExitStack, contextmanager, redirect_stderr, redirect_stdout
from copy import deepcopy
from dataclasses import replace
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from biocompiler.cli import main
from biocompiler.core_client import CoreCancelled, CoreProtocolError, CoreTimeout, CoreUnavailable
from biocompiler.ir.architecture_build import PayloadArchitectureBuild, PayloadArchitectureExport, PayloadArchitectureRequest
from biocompiler.verification.evidence import CheckOutcome
from biocompiler.verification.payload_architecture import PayloadArchitectureVerification


FIXTURES = Path(__file__).parent / "conformance" / "case-b" / "base"
BRIDGE = "biocompiler.architecture_backend."
PYTHON_SEMANTICS = (
    "biocompiler.compiler.payload_architecture.compile_payload_architecture",
    "biocompiler.compiler.payload_architecture.export_payload_architecture",
    "biocompiler.compiler.payload_architecture.derive_source_execution",
    "biocompiler.compiler.payload_architecture.match_architecture_refinement",
    "biocompiler.compiler.payload_architecture.build_circuit_construction",
    "biocompiler.semantics.payload_execution.derive_source_execution",
    "biocompiler.semantics.payload_execution.lower_to_behavior",
    "biocompiler.verification.payload_architecture.check_payload_architecture",
    "biocompiler.verification.payload_architecture.verify_payload_architecture",
)


def invoke(*arguments):
    stdout, stderr = StringIO(), StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main([str(item) for item in arguments])
    return code, stdout.getvalue(), stderr.getvalue()


@contextmanager
def forbid_python_semantics():
    with ExitStack() as stack:
        for name in PYTHON_SEMANTICS:
            stack.enter_context(patch(name, side_effect=AssertionError("Python semantic execution: " + name)))
        yield


class ArchitectureCoreCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw_request = json.loads((FIXTURES / "request.json").read_text(encoding="utf-8"))
        cls.raw_build = json.loads((FIXTURES / "candidate.json").read_text(encoding="utf-8"))
        cls.request = PayloadArchitectureRequest.from_dict(cls.raw_request)
        cls.build = PayloadArchitectureBuild.from_dict(cls.raw_build)
        cls.assessment = PayloadArchitectureVerification(
            cls.request.fingerprint, cls.build.fingerprint, CheckOutcome.PASS, True, True, ())
        cls.exported = PayloadArchitectureExport(
            ">artificial-rna alphabet=RNA\nAUGUAA\n",
            {"request_fingerprint": cls.request.fingerprint, "build": cls.raw_build,
             "verification": cls.assessment.to_dict(), "delivered_member_ids": ["artificial-rna"],
             "source_authority": "Retain the independently supplied request separately."})

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.request_path = self.root / "request.json"
        self.build_path = self.root / "build.json"
        self.output = self.root / "output.json"
        self.request_path.write_text(json.dumps(self.raw_request), encoding="utf-8")
        self.build_path.write_text(json.dumps(self.raw_build), encoding="utf-8")

    def command(self, operation, *options):
        if operation == "build":
            return ("architecture-build", "--request", self.request_path, "--output", self.output, *options)
        return ("architecture-" + operation, self.build_path, "--expected-request", self.request_path,
                *(("--output", self.output) if operation == "export" else ()), *options)

    def bridge(self, operation, *, build=None, assessment=None):
        build = self.build if build is None else build
        assessment = self.assessment if assessment is None else assessment
        if operation == "build":
            return patch(BRIDGE + "compile_document", return_value=(build, assessment, object()))
        if operation == "verify":
            return patch(BRIDGE + "check_document", return_value=(build, assessment, object()))
        return patch(BRIDGE + "export_document", return_value=(self.exported, build, assessment, object()))

    def assert_summary(self, stdout, *, build=None, assessment=None):
        build = self.build if build is None else build
        assessment = self.assessment if assessment is None else assessment
        self.assertEqual(json.loads(stdout), {"status": build.status, "verification": assessment.to_dict(),
                                              "diagnostics": [gap.to_dict() for gap in build.diagnostics]})

    def test_selected_core_routes_each_command_once_and_preserves_public_json(self):
        for operation, method in (("build", "compile_document"), ("verify", "check_document"), ("export", "export_document")):
            with self.subTest(operation=operation), forbid_python_semantics(), self.bridge(operation) as selected, ExitStack() as stack:
                for other in {"compile_document", "check_document", "export_document"} - {method}:
                    stack.enter_context(patch(BRIDGE + other, side_effect=AssertionError("Unexpected second operation")))
                code, stdout, stderr = invoke(*self.command(operation, "--core-executable", sys.executable))
            self.assertEqual((code, stderr), (0, ""))
            self.assert_summary(stdout)
            selected.assert_called_once()
            core = selected.call_args.kwargs["core"]
            self.assertEqual((core.executable, core.role, core.timeout_seconds, core.expected_sha256),
                             (Path(sys.executable), "core", 30.0, None))
            if operation != "verify":
                artifact = self.build if operation == "build" else self.exported
                self.assertEqual(self.output.read_bytes(), (artifact.to_json() + "\n").encode("utf-8"))

    def test_verifier_role_and_explicit_transport_options_are_forwarded(self):
        with self.bridge("verify") as selected, forbid_python_semantics():
            code, stdout, stderr = invoke(*self.command("verify", "--verifier-executable", sys.executable,
                                                         "--core-timeout", "7.5", "--core-sha256", "a" * 64))
        self.assertEqual((code, stderr), (0, ""))
        self.assert_summary(stdout)
        core = selected.call_args.kwargs["core"]
        self.assertEqual((core.role, core.timeout_seconds, core.expected_sha256), ("verify", 7.5, "a" * 64))
        self.assertFalse(self.output.exists())

    def test_raw_authority_reaches_bridge_without_domain_normalization(self):
        request = deepcopy(self.raw_request)
        request["library"]["assumptions"] = ["z-last", "a-first"]
        original_source = deepcopy(request["circuit"]["profile"]["source_request"])
        self.assertNotEqual(request, PayloadArchitectureRequest.from_dict(request).to_dict())
        self.request_path.write_text(json.dumps(request), encoding="utf-8")
        for operation in ("build", "verify", "export"):
            with self.subTest(operation=operation), self.bridge(operation) as selected, forbid_python_semantics():
                self.assertEqual(invoke(*self.command(operation, "--core-executable", sys.executable))[0], 0)
            passed = selected.call_args.args[0] if operation == "build" else selected.call_args.kwargs["expected_request"]
            self.assertEqual(passed, request)
            self.assertEqual(passed["circuit"]["profile"]["source_request"], original_source)
            if operation != "build":
                self.assertEqual(selected.call_args.kwargs["build"], self.raw_build)

    def test_all_incomplete_build_statuses_are_published_with_exit_one(self):
        for status in ("unsupported", "no_solution", "search_exhausted"):
            build = replace(self.build, plan=None, construction=None, status=status)
            assessment = replace(self.assessment, build_fingerprint=build.fingerprint,
                                 translation_complete=False, construction_complete=False)
            with self.subTest(status=status), self.bridge("build", build=build, assessment=assessment), forbid_python_semantics():
                code, stdout, stderr = invoke(*self.command("build", "--core-executable", sys.executable))
            self.assertEqual((code, stderr), (1, ""))
            self.assert_summary(stdout, build=build, assessment=assessment)
            self.assertEqual(PayloadArchitectureBuild.from_json(self.output.read_text()).status, status)

    def test_failed_verification_returns_one_without_publishing(self):
        assessment = replace(self.assessment, outcome=CheckOutcome.FAIL,
                             translation_complete=False, construction_complete=False)
        with self.bridge("verify", assessment=assessment), forbid_python_semantics():
            code, stdout, stderr = invoke(*self.command("verify", "--verifier-executable", sys.executable))
        self.assertEqual((code, stderr), (1, ""))
        self.assert_summary(stdout, assessment=assessment)
        self.assertFalse(self.output.exists())

    def test_partial_export_keeps_construction_scope_without_requiring_translation_complete(self):
        build = replace(self.build, status="partial")
        assessment = replace(self.assessment, build_fingerprint=build.fingerprint,
                             translation_complete=False, unresolved=("unresolved supplied contract",))
        with self.bridge("export", build=build, assessment=assessment), forbid_python_semantics():
            code, stdout, stderr = invoke(*self.command("export", "--core-executable", sys.executable))
        self.assertEqual((code, stderr), (0, ""))
        self.assert_summary(stdout, build=build, assessment=assessment)
        self.assertTrue(self.output.exists())

    def test_transport_failure_has_exit_two_no_fallback_and_preserves_existing_output(self):
        for error in (CoreUnavailable("missing selected binary"), CoreTimeout("native timeout"),
                      CoreCancelled("cancelled"), CoreProtocolError("incompatible native profile")):
            self.output.write_bytes(b"previous complete pair")
            with self.subTest(error=type(error).__name__), forbid_python_semantics(), \
                    patch(BRIDGE + "export_document", side_effect=error) as selected:
                code, stdout, stderr = invoke(*self.command("export", "--core-executable", sys.executable))
            self.assertEqual((code, stdout), (2, ""))
            self.assertIn(str(error), stderr)
            selected.assert_called_once()
            self.assertEqual(self.output.read_bytes(), b"previous complete pair")
            self.assertEqual(sorted(path.name for path in self.root.iterdir()), ["build.json", "output.json", "request.json"])

    def test_missing_binary_rejects_before_exchange_without_python_fallback(self):
        with forbid_python_semantics(), patch("biocompiler.core_client._exchange") as exchange:
            code, stdout, stderr = invoke(*self.command("build", "--core-executable", self.root / "missing-core"))
        self.assertEqual((code, stdout), (2, ""))
        self.assertIn("not executable", stderr)
        exchange.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_invalid_selection_options_fail_before_file_or_bridge_work(self):
        self.request_path.unlink()
        options = (("--core-timeout", "2"), ("--core-sha256", "a" * 64),
                   ("--core-executable", "relative-core"),
                   ("--core-executable", sys.executable, "--core-timeout", "0"),
                   ("--core-executable", sys.executable, "--core-timeout", "-1"),
                   ("--core-executable", sys.executable, "--core-timeout", "nan"),
                   ("--core-executable", sys.executable, "--core-timeout", "inf"),
                   ("--core-executable", sys.executable, "--core-sha256", "A" * 64))
        with patch(BRIDGE + "compile_document") as selected:
            for flags in options:
                with self.subTest(flags=flags):
                    code, stdout, stderr = invoke(*self.command("build", *flags))
                    self.assertEqual((code, stdout), (2, ""))
                    self.assertTrue(stderr)
                    self.assertNotIn("No such file", stderr)
        selected.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_verifier_option_is_exclusive_and_verification_only(self):
        for operation, options in (("verify", ("--core-executable", sys.executable, "--verifier-executable", sys.executable)),
                                   ("build", ("--verifier-executable", sys.executable)),
                                   ("export", ("--verifier-executable", sys.executable))):
            with self.subTest(operation=operation), redirect_stderr(StringIO()), self.assertRaises(SystemExit) as error:
                main([str(item) for item in self.command(operation, *options)])
            self.assertEqual(error.exception.code, 2)

    def test_strict_raw_json_rejection_precedes_bridge_and_publication(self):
        for raw in (b'{"duplicate":0,"duplicate":1}', b'{"value":NaN}', b'\xff', b'[] trailing'):
            self.request_path.write_bytes(raw)
            with self.subTest(raw=raw), patch(BRIDGE + "compile_document") as selected:
                code, stdout, stderr = invoke(*self.command("build", "--core-executable", sys.executable))
            self.assertEqual((code, stdout), (2, ""))
            self.assertTrue(stderr)
            selected.assert_not_called()
            self.assertFalse(self.output.exists())

    def test_output_input_collisions_and_symlinks_preserve_authority(self):
        original = self.request_path.read_bytes()
        for destination in (self.request_path, self.root / "alias.json"):
            if destination != self.request_path:
                destination.symlink_to(self.request_path)
            with self.subTest(destination=destination.name), self.bridge("build"), forbid_python_semantics():
                code, stdout, stderr = invoke("architecture-build", "--request", self.request_path,
                    "--output", destination, "--core-executable", sys.executable)
            self.assertEqual((code, stdout), (2, ""))
            self.assertIn("independent input authority", stderr)
            self.assertEqual(self.request_path.read_bytes(), original)
        unrelated = self.root / "unrelated.txt"
        unrelated.write_bytes(b"unrelated")
        self.output.symlink_to(unrelated)
        with self.bridge("export"), forbid_python_semantics():
            code, _, _ = invoke(*self.command("export", "--core-executable", sys.executable))
        self.assertEqual(code, 2)
        self.assertEqual(unrelated.read_bytes(), b"unrelated")

    def test_atomic_export_failures_preserve_pair_and_remove_temporary_output(self):
        for failure in ("fsync", "replace"):
            self.output.write_bytes(b"previous complete pair")
            with self.subTest(failure=failure), self.bridge("export"), forbid_python_semantics(), \
                    patch("biocompiler.cli.os." + failure, side_effect=OSError("publication failed")):
                code, stdout, stderr = invoke(*self.command("export", "--core-executable", sys.executable))
            self.assertEqual((code, stdout), (2, ""))
            self.assertIn("publication failed", stderr)
            self.assertEqual(self.output.read_bytes(), b"previous complete pair")
            self.assertFalse(list(self.root.glob(".output.json.*.tmp")))

    def test_no_option_preserves_reference_route_and_existing_summary(self):
        with patch("biocompiler.compiler.payload_architecture.compile_payload_architecture", return_value=self.build) as compile_python, \
                patch("biocompiler.verification.payload_architecture.check_payload_architecture", return_value=self.assessment) as check_python, \
                patch(BRIDGE + "compile_document", side_effect=AssertionError("Implicit core selection")):
            code, stdout, stderr = invoke(*self.command("build"))
        self.assertEqual((code, stderr), (0, ""))
        self.assert_summary(stdout)
        compile_python.assert_called_once()
        check_python.assert_called_once()
        self.assertEqual(self.output.read_bytes(), (self.build.to_json() + "\n").encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
