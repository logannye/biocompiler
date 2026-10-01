"""Public circuit-scope workflow and exact external-authority boundaries."""

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest

import biocompiler as bc
from biocompiler.cli import main
from biocompiler.ir.circuit_profile import MAX_PROFILE_JSON_BYTES
from biocompiler.verification.circuit_profile import MAX_ASSESSMENT_JSON_BYTES
from examples.circuit_profile import make_profile_requests


def invoke(*arguments):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(map(str, arguments)))
    return code, out.getvalue(), err.getvalue()


class CircuitProfileWorkflowTests(unittest.TestCase):
    def test_public_api_preserves_human_wrappers_without_compiling(self):
        for request in make_profile_requests().values():
            with self.subTest(purpose=request.purpose):
                assessment = bc.check_circuit_profile(request)
                verified = bc.verify_circuit_profile(
                    assessment, expected_request=request
                )
                self.assertEqual(verified.request, request)
                self.assertEqual(verified.molecular_generation, "unimplemented")
                self.assertEqual(verified.human_therapeutic_admission, "not_admitted")
                with self.assertRaises(bc.CompilationUnavailableError) as error:
                    bc.compile(request)
                self.assertTrue(error.exception.diagnostics)
        request = make_profile_requests()["product"]
        self.assertIsInstance(request.source_request, bc.HumanAcceptanceRequest)
        self.assertEqual(request.source_request.target, request.target)

    def test_cli_check_fresh_verify_and_historical_inspection(self):
        with tempfile.TemporaryDirectory() as directory:
            for label, request in make_profile_requests().items():
                source = Path(directory) / f"{label}.request.json"
                output = Path(directory) / f"{label}.assessment.json"
                source.write_text(request.to_json(), encoding="utf-8")
                code, stdout, stderr = invoke(
                    "circuit-profile-check", "--request", source, "--output", output
                )
                self.assertEqual((code, stderr), (0, ""))
                summary = json.loads(stdout)
                self.assertEqual(summary["molecular_generation"], "unimplemented")
                self.assertEqual(summary["human_therapeutic_admission"], "not_admitted")
                expected = bc.check_circuit_profile(request)
                self.assertEqual(
                    bc.CircuitProfileAssessment.from_json(output.read_text()), expected
                )
                code, _, stderr = invoke(
                    "circuit-profile-verify", output, "--expected-request", source
                )
                self.assertEqual((code, stderr), (0, ""))
                code, stdout, _ = invoke("inspect", output)
                self.assertEqual(code, 0)
                self.assertIn("Historical", json.loads(stdout)["inspection"])
                code, stdout, _ = invoke("inspect", source)
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(stdout)["purpose"], request.purpose)

    def test_changed_boundary_authority_refuses_saved_report(self):
        request = make_profile_requests()["product"]
        with tempfile.TemporaryDirectory() as directory:
            expected = Path(directory) / "request.json"
            result = Path(directory) / "assessment.json"
            result.write_text(
                bc.check_circuit_profile(request).to_json(), encoding="utf-8"
            )
            expected.write_text(
                replace(request, boundary="export").to_json(), encoding="utf-8"
            )
            code, _, stderr = invoke(
                "circuit-profile-verify", result, "--expected-request", expected
            )
            self.assertEqual(code, 2)
            self.assertTrue(stderr)

    def test_cli_cannot_overwrite_request_or_accept_unknown_fields(self):
        request = make_profile_requests()["reference"]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "request.json"
            original = request.to_json()
            source.write_text(original, encoding="utf-8")
            code, _, _ = invoke(
                "circuit-profile-check", "--request", source, "--output", source
            )
            self.assertEqual(code, 2)
            self.assertEqual(source.read_text(), original)
            forged = request.to_dict() | {"admitted": True}
            source.write_text(json.dumps(forged), encoding="utf-8")
            output = Path(directory) / "assessment.json"
            code, _, _ = invoke(
                "circuit-profile-check", "--request", source, "--output", output
            )
            self.assertEqual(code, 2)
            self.assertFalse(output.exists())

    def test_inspect_enforces_profile_raw_byte_limits(self):
        request = make_profile_requests()["reference"]
        assessment = bc.check_circuit_profile(request)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifact.json"
            for artifact, limit in (
                (request, MAX_PROFILE_JSON_BYTES),
                (request.source_experiment, MAX_PROFILE_JSON_BYTES),
                (assessment, MAX_ASSESSMENT_JSON_BYTES),
            ):
                document = artifact.to_json()
                padded = document + " " * (limit + 1 - len(document.encode("utf-8")))
                path.write_text(padded, encoding="utf-8")
                code, stdout, stderr = invoke("inspect", path)
                self.assertEqual(code, 2)
                self.assertEqual(stdout, "")
                self.assertIn("byte limit", stderr)


if __name__ == "__main__":
    unittest.main()
