"""Saved behavior artifacts use the same strict inspection boundary as intent."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

import biocompiler as bc
from biocompiler.cli import main


class BehaviorCliTests(unittest.TestCase):
    def setUp(self):
        therapy = bc.Therapy("inspection")
        cell = therapy.engineer("observer", cell_type="abstract_cell")
        cell.when(cell.environment.signal("A").present()).do(cell.report("seen"))
        self.behavior = bc.lower_to_behavior(therapy.freeze())

    def inspect(self, document, *, full=False):
        with tempfile.TemporaryDirectory(prefix="biocompiler-behavior-") as directory:
            path = Path(directory) / "behavior.json"
            path.write_text(document, encoding="utf-8")
            output, error = io.StringIO(), io.StringIO()
            with redirect_stdout(output), redirect_stderr(error):
                status = main(["inspect", str(path), *(["--json"] if full else [])])
            return status, output.getvalue(), error.getvalue()

    def test_summary_and_lossless_json_inspection(self):
        status, output, error = self.inspect(self.behavior.to_json())
        self.assertEqual(status, 0, error)
        self.assertEqual(json.loads(output), self.behavior.summary())
        status, output, error = self.inspect(self.behavior.to_json(), full=True)
        self.assertEqual(status, 0, error)
        self.assertEqual(bc.BehaviorProgram.from_json(output), self.behavior)

    def test_duplicate_keys_cannot_bypass_strict_behavior_parser(self):
        document = self.behavior.to_json()
        corrupted = '{"name":"untrusted",' + document.lstrip()[1:]
        status, output, error = self.inspect(corrupted)
        self.assertEqual(status, 2)
        self.assertEqual(output, "")
        self.assertIn("Duplicate", error)

    def test_unknown_schema_and_wrong_document_shape_are_diagnostics(self):
        future = self.behavior.to_dict()
        future["schema_version"] = "biocompiler.behavior.v99"
        for document in (
            json.dumps(future),
            "[]",
            "null",
            "[" * 2000 + "0" + "]" * 2000,
        ):
            with self.subTest(document=document):
                status, output, error = self.inspect(document)
                self.assertEqual(status, 2)
                self.assertEqual(output, "")
                self.assertIn("biocompiler:", error)


if __name__ == "__main__":
    unittest.main()
