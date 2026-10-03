"""Exact original sequence evidence; this suite executes no native binary."""
import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "sequence_authority", ROOT / "tools/capture_reference_sequence_export.py"
)
authority = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(authority)
PIN = "8c3b04e08b6bc9c31e82bd82afd085697a67c41388e9bbec8744e28bc00630bd"


class SequenceAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.actual = authority.capture()
        cls.raw = (ROOT / "tests/conformance/reference-sequence-export-314.json").read_bytes()
        cls.frozen = json.loads(cls.raw)
        cls.rows = {row["id"]: row for row in cls.actual["cases"]}

    def test_complete_actual_original_execution(self):
        self.assertEqual(self.actual, self.frozen)
        self.assertEqual(len(self.actual["cases"]), 140)
        self.assertEqual(len(self.rows), 140)
        self.assertEqual({row["operation"] for row in self.rows.values()}, {"make", "verify", "export"})

    def test_runtime_bytes_and_exact_sources(self):
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), PIN)
        self.assertEqual(self.raw, (ROOT / "tests/conformance/reference-sequence-export-311.json").read_bytes())
        for path, pin in self.actual["sources"].items():
            self.assertEqual(hashlib.sha256((authority.ROOT / path).read_bytes()).hexdigest(), pin)

    def test_exact_width_dependent_bytes_and_independent_sequence_identity(self):
        for alphabet in ("DNA", "RNA"):
            results = [self.rows[f"{alphabet}:export-width:{width}"]["outcome"]["value"] for width in (1, 60, 80, 10000)]
            self.assertEqual(len({value["sequence_sha256"] for value in results}), 1)
            self.assertEqual(len({value["molecular_fingerprint"] for value in results}), 1)
            self.assertEqual(len({value["specification"] for value in results}), 1)
            self.assertEqual(len({value["fasta_sha256"] for value in results}), 4)
            for value in results:
                for field in ("fasta", "specification"):
                    self.assertEqual(hashlib.sha256(value[field].encode()).hexdigest(), value[field + "_sha256"])
                    self.assertTrue(value[field].endswith("\n"))
                sequence = "".join(value["fasta"].splitlines()[1:])
                self.assertEqual(hashlib.sha256(sequence.encode("ascii")).hexdigest(), value["sequence_sha256"])

    def test_rehashed_fidelity_does_not_grant_current_export_acceptance(self):
        for alphabet in ("DNA", "RNA"):
            faithful = self.rows[f"{alphabet}:self-rehashed-fidelity"]
            rejected = self.rows[f"{alphabet}:self-rehashed-current-check"]
            self.assertEqual(faithful["input"]["artifact"], rejected["input"]["artifact"])
            self.assertEqual(faithful["outcome"], {"status": "return", "value": True})
            self.assertEqual(rejected["outcome"], {
                "status": "raise", "module": "biocompiler.errors", "type": "SerializationError",
                "message": "Sequence export requires a currently passing independent molecular check: exact_reference; translation_reference; dna_rna_correspondence",
            })

    def test_primitive_validation_and_parser_precedence(self):
        for alphabet in ("DNA", "RNA"):
            for width in ("True", "1.5", "'80'", "None"):
                self.assertEqual(self.rows[f"{alphabet}:export-width:{width}"]["outcome"]["message"], "FASTA line width must be an integer from 1 to 10000.")
            self.assertEqual(self.rows[f"{alphabet}:spec:duplicate"]["outcome"]["message"], "Duplicate JSON key: records.")
            self.assertEqual(self.rows[f"{alphabet}:spec:nan"]["outcome"]["message"], "Invalid JSON number: NaN.")
            self.assertEqual(self.rows[f"{alphabet}:fasta:reference-invalid-utf8"]["outcome"]["message"], "Invalid encoded FASTA reference identity.")


if __name__ == "__main__":
    unittest.main()
