"""Public declaration inspection preserves identity and cannot compile payloads."""

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest

import biocompiler as bc
from biocompiler.cli import main
from biocompiler.ir.molecule_records import MAX_MOLECULE_JSON_BYTES
from examples.circuit_molecules import make_molecule_record


class CircuitMoleculeWorkflowTests(unittest.TestCase):
    def test_public_types_roundtrip_complete_example(self):
        record = make_molecule_record()
        self.assertIsInstance(record, bc.CircuitMoleculeRecord)
        self.assertIsInstance(record.bundle, bc.CircuitMoleculeSet)
        self.assertIsInstance(record.bundle.molecules[0], bc.CircuitMolecule)
        self.assertEqual(
            bc.CircuitMoleculeRecord.from_json(record.to_json() + "\n"), record
        )
        self.assertGreater(len(record.bundle.molecules), 1)
        self.assertFalse(record.bundle.declared_nominal_complete)
        self.assertIsNone(record.experimental_amounts[0].quantity)
        self.assertEqual(len(record.experimental_amounts[0].role_instance_ids), 2)

    def test_compile_refuses_declaration_promotion(self):
        record = make_molecule_record()
        for artifact in (record, record.bundle):
            with self.assertRaises(bc.CompilationUnavailableError) as error:
                bc.compile(artifact)
            self.assertIn(
                "source_correspondence_unverified", error.exception.diagnostics
            )
            self.assertIn(
                "human_therapeutic_use_not_admitted", error.exception.diagnostics
            )

    def test_cli_inspects_declarations_with_separate_claim_dimensions(self):
        record = make_molecule_record()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "declaration.json"
            for artifact in (record, record.bundle, record.bundle.molecules[0]):
                path.write_text(artifact.to_json() + "\n", encoding="utf-8")
                stdout, stderr = io.StringIO(), io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    result = main(["inspect", str(path)])
                self.assertEqual((result, stderr.getvalue()), (0, ""))
                summary = json.loads(stdout.getvalue())
                self.assertEqual(summary["scope"], "declared_molecular_identity")
                self.assertEqual(summary["source_correspondence"], "unverified")
                self.assertEqual(summary["molecular_assembly"], "unverified")
                self.assertEqual(summary["molecular_function"], "unestablished")
                self.assertEqual(summary["human_therapeutic_admission"], "not_admitted")
                self.assertEqual(summary["fingerprint"], artifact.fingerprint)

    def test_cli_raw_bytes_and_unknown_claim_fields_are_rejected(self):
        record = make_molecule_record()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "declaration.json"
            text = record.to_json()
            for bad in (
                text + " " * (MAX_MOLECULE_JSON_BYTES + 1 - len(text.encode())),
                json.dumps(
                    record.to_dict() | {"human_therapeutic_admission": "admitted"}
                ),
            ):
                path.write_text(bad, encoding="utf-8")
                stdout, stderr = io.StringIO(), io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    result = main(["inspect", str(path)])
                self.assertEqual((result, stdout.getvalue()), (2, ""))
                self.assertTrue(stderr.getvalue())

    def test_run_metadata_is_archival_not_experimental_authority(self):
        record = make_molecule_record()
        changed = replace(record, run_metadata={"run": "new-timestamp"})
        self.assertNotEqual(changed.fingerprint, record.fingerprint)
        self.assertEqual(
            changed.experimental_specification_identity,
            record.experimental_specification_identity,
        )
        self.assertEqual(
            changed.nominal_bundle_identity, record.nominal_bundle_identity
        )
        self.assertEqual(
            changed.bundle.request.to_dict(), record.bundle.request.to_dict()
        )


if __name__ == "__main__":
    unittest.main()
