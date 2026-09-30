"""Integrated M9 example and CLI boundaries remain explicit after serialization."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

import biocompiler as bc
from biocompiler.cli import main
from examples.molecular_contract import requested_fap_contract


class MolecularExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs, cls.result = requested_fap_contract()

    def inspect(self, value):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifact.json"
            path.write_text(value.to_json(), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["inspect", str(path)]), 0)
            summary = json.loads(output.getvalue())
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["inspect", str(path), "--json"]), 0)
            self.assertEqual(type(value).from_json(output.getvalue()), value)
            return summary

    def test_actual_fap_correspondence_never_completes_requested_payload(self):
        self.assertEqual(self.result.linkage_outcome, bc.CheckOutcome.PASS)
        self.assertEqual(self.result.outcome, bc.CheckOutcome.UNKNOWN)
        self.assertFalse(self.result.passed)
        self.assertTrue(self.result.freshness(*self.inputs).fresh)
        self.assertEqual(
            self.inputs[1].build_request.artifact_scope, "complete_payload"
        )
        with self.assertRaises(bc.CompilationUnavailableError) as captured:
            bc.compile(self.inputs[1])
        self.assertIn(
            "complete_payload_not_promoted",
            {d.code for d in captured.exception.diagnostics},
        )

    def test_saved_contract_and_result_are_inspected_as_unresolved_history(self):
        summary = self.inspect(self.inputs[0])
        self.assertIn("Historical", summary["inspection"])
        self.assertIn("exact_experimental_material", summary["unestablished_claims"])
        summary = self.inspect(self.result)
        self.assertEqual(summary["outcome"], "unknown")
        self.assertEqual(summary["linkage_outcome"], "pass")
        self.assertIn("Historical", summary["inspection"])
        self.assertIn("not molecular behavior acceptance", summary["claim_scope"])
        for record in (
            *self.inputs[0].input_bindings,
            *self.inputs[0].response_bindings,
            *self.inputs[0].parameters,
            *self.inputs[0].evidence,
        ):
            self.inspect(record)

    def test_payload_cli_never_exposes_structural_readiness_as_admission(self):
        from test_payload_profiles import check, fixture

        candidate, reference, retained = fixture()
        result = check(candidate, reference, retained)
        self.assertTrue(result.passed)
        for record in (
            candidate,
            reference,
            result,
            *candidate.regions,
            *candidate.features,
            reference.primary_source,
            *reference.reviews,
        ):
            summary = self.inspect(record)
            if isinstance(record, bc.PayloadResult):
                self.assertEqual(summary["evidence_boundary"], "software_fixture")
                self.assertEqual(summary["reference_promotion"], "not_promoted")
                self.assertIs(summary["compiler_admission"], False)
                self.assertIn("Historical", summary["inspection"])


if __name__ == "__main__":
    unittest.main()
