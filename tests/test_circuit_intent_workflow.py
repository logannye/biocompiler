"""Public author/check/replay boundary, without molecule or admission claims."""

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
from examples.circuit_intent import make_circuit_requests


def invoke(*arguments):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(map(str, arguments)))
    return code, out.getvalue(), err.getvalue()


class CircuitIntentWorkflowTests(unittest.TestCase):
    def test_shared_profile_budget_preflights_pending_items_and_indentation(self):
        from unittest.mock import patch
        from biocompiler.ir.circuit_profile import _bounded_tree, MAX_PROFILE_ITEMS

        # Pending siblings consume the budget before their nested arrays expand.
        value = [[None] * (MAX_PROFILE_ITEMS // 2)] * 2
        with self.assertRaisesRegex(bc.SerializationError, "item limit"):
            _bounded_tree(value)
        request = make_circuit_requests()["product"]
        with patch(
            "biocompiler.ir.serialization.json.dumps",
            side_effect=AssertionError("encoder must not run"),
        ):
            for indent in (1000000000, True, -1, 2.5, " "):
                with self.assertRaisesRegex(bc.SerializationError, "indentation"):
                    request.to_json(indent=indent)

    def test_public_examples_keep_original_authority_and_refuse_compilation(self):
        for request in make_circuit_requests().values():
            checked = bc.check_circuit_intent(request)
            self.assertEqual(
                bc.verify_circuit_intent(checked, expected_request=request), checked
            )
            self.assertEqual(checked.intent_consistency, "consistent")
            self.assertEqual(checked.outcome.value, "unsupported")
            self.assertEqual(checked.empirical_validation, "unknown")
            self.assertEqual(checked.human_therapeutic_admission, "not_admitted")
            with self.assertRaises(bc.CompilationUnavailableError) as error:
                bc.compile(request)
            self.assertTrue(error.exception.diagnostics)

    def test_cli_check_replay_inspect_both_human_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            for label, request in make_circuit_requests().items():
                source, report = (
                    Path(directory) / f"{label}.json",
                    Path(directory) / f"{label}.check.json",
                )
                source.write_text(request.to_json() + "\n", encoding="utf-8")
                code, stdout, stderr = invoke(
                    "circuit-intent-check", "--request", source, "--output", report
                )
                self.assertEqual((code, stderr), (0, ""))
                summary = json.loads(stdout)
                self.assertEqual(summary["molecular_implementation"], "unimplemented")
                self.assertEqual(summary["outcome"], "unsupported")
                self.assertEqual(
                    invoke(
                        "circuit-intent-verify", report, "--expected-request", source
                    )[0],
                    0,
                )
                self.assertEqual(invoke("inspect", source)[0], 0)
                code, stdout, stderr = invoke("inspect", report)
                self.assertEqual((code, stderr), (0, ""))
                self.assertIn("Historical", json.loads(stdout)["inspection"])

    def test_cli_requires_external_original_authority(self):
        request = make_circuit_requests()["product"]
        with tempfile.TemporaryDirectory() as directory:
            source, report = (
                Path(directory) / "request.json",
                Path(directory) / "report.json",
            )
            report.write_text(
                bc.check_circuit_intent(request).to_json(), encoding="utf-8"
            )
            changed = replace(
                request, profile=replace(request.profile, boundary="export")
            )
            source.write_text(changed.to_json(), encoding="utf-8")
            self.assertEqual(
                invoke("circuit-intent-verify", report, "--expected-request", source)[
                    0
                ],
                2,
            )

    def test_no_overwrite_or_publication_of_invalid_input(self):
        request = make_circuit_requests()["product"]
        with tempfile.TemporaryDirectory() as directory:
            source, report = (
                Path(directory) / "request.json",
                Path(directory) / "report.json",
            )
            original = request.to_json()
            source.write_text(original, encoding="utf-8")
            self.assertEqual(
                invoke("circuit-intent-check", "--request", source, "--output", source)[
                    0
                ],
                2,
            )
            self.assertEqual(source.read_text(), original)
            report.symlink_to(source)
            self.assertEqual(
                invoke("circuit-intent-check", "--request", source, "--output", report)[
                    0
                ],
                2,
            )
            self.assertEqual(source.read_text(), original)
            report.unlink()
            source.write_text(
                json.dumps(
                    request.to_dict() | {"molecular_implementation": "verified"}
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                invoke("circuit-intent-check", "--request", source, "--output", report)[
                    0
                ],
                2,
            )
            self.assertFalse(report.exists())

    def test_inspection_respects_raw_request_budget(self):
        request = make_circuit_requests()["reference"]
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "request.json"
            text = request.to_json()
            source.write_text(
                text + " " * (MAX_PROFILE_JSON_BYTES - len(text.encode()) + 1),
                encoding="utf-8",
            )
            code, out, err = invoke("inspect", source)
            self.assertEqual((code, out), (2, ""))
            self.assertIn("byte limit", err)


if __name__ == "__main__":
    unittest.main()
