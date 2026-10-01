"""Public offline metadata workflows keep R1 incompleteness explicit."""

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest

import biocompiler as bc
from examples.circuit_sources import make_source_inventory
from biocompiler.cli import main


def invoke(*arguments):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(map(str, arguments)))
    return code, out.getvalue(), err.getvalue()


class CircuitSourceWorkflowTests(unittest.TestCase):
    def test_public_inventory_api_keeps_evidence_unassessed(self):
        inventory = make_source_inventory()
        assessment = bc.check_circuit_sources(inventory)
        result = bc.verify_circuit_sources(assessment, expected_inventory=inventory)
        self.assertEqual(result.outcome, bc.CheckOutcome.PASS)
        self.assertEqual(result.claim_scope, "metadata_consistency_only")
        self.assertEqual(result.molecular_readiness, "unassessed")
        self.assertEqual(result.source_bytes, "not_checked")
        self.assertEqual(result.human_admission, "not_admitted")

    def test_cli_check_verify_inspect_and_input_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "inventory.json"
            result = Path(directory) / "assessment.json"
            inventory = make_source_inventory()
            source.write_text(inventory.to_json(), encoding="utf-8")
            code, output, error = invoke(
                "circuit-sources-check", "--inventory", source, "--output", result
            )
            self.assertEqual((code, error), (0, ""))
            summary = json.loads(output)
            self.assertEqual(summary["source_bytes"], "not_checked")
            self.assertEqual(summary["molecular_readiness"], "unassessed")
            code, _, error = invoke(
                "circuit-sources-verify", result, "--expected-inventory", source
            )
            self.assertEqual((code, error), (0, ""))
            for path in (source, result):
                code, output, error = invoke("inspect", path)
                self.assertEqual((code, error), (0, ""))
                self.assertIn("metadata", json.loads(output)["scope"])
            original = source.read_text()
            code, _, _ = invoke(
                "circuit-sources-check", "--inventory", source, "--output", source
            )
            self.assertEqual(code, 2)
            self.assertEqual(source.read_text(), original)

    def test_changed_case_reports_stale_review_without_promoting_gaps(self):
        inventory = make_source_inventory()
        changed = replace(
            inventory, cases=(replace(inventory.cases[0], label="Changed case"),)
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "inventory.json"
            result = Path(directory) / "assessment.json"
            source.write_text(changed.to_json(), encoding="utf-8")
            code, _, _ = invoke(
                "circuit-sources-check", "--inventory", source, "--output", result
            )
            self.assertEqual(code, 1)
            assessment = bc.CircuitSourcesAssessment.from_json(result.read_text())
            self.assertEqual(assessment.outcome, bc.CheckOutcome.FAIL)
            self.assertEqual(assessment.molecular_readiness, "unassessed")
            code, _, _ = invoke(
                "circuit-sources-verify", result, "--expected-inventory", source
            )
            self.assertEqual(code, 1)
            source.write_text(inventory.to_json(), encoding="utf-8")
            code, _, _ = invoke(
                "circuit-sources-verify", result, "--expected-inventory", source
            )
            self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
