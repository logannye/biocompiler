"""Public typed source construction, without native execution or fixture recipes."""
import ast
from contextlib import redirect_stdout
import importlib.util
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from biocompiler import policy as p
from biocompiler.policy.research_project import ResearchProject, ResearchProjectError, SourceRecord
from biocompiler.core_client import CoreClient, encode_json
from examples import author_staged_research_project as example

ROOT = Path(__file__).resolve().parents[1]


class TypedStagedExampleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads((ROOT / "data/researcher_alpha/staged-input.json").read_text())

    def reference(self):
        return ResearchProject.from_request(project_id="reference", title="Independent artificial original",
            request=self.packet["request"], limits=self.packet["limits"],
            sources=(SourceRecord("original", "urn:test:original", "1", "a" * 64, "supplied_contracts", "Artificial test terms"),),
            assumptions=("Original independent assumption",))

    def test_public_pattern_constructs_exact_supported_source_except_its_honest_source_map(self):
        with patch.object(CoreClient, "call", side_effect=AssertionError("No native execution")):
            document = example.build_request()
        authored = p.to_data(document)
        original = json.loads(json.dumps(self.packet["request"]["implementation_request"]["document"]))
        self.assertNotEqual(authored["program"]["source_map"], original["program"]["source_map"])
        original["program"]["source_map"] = authored["program"]["source_map"]
        self.assertEqual(encode_json(authored), encode_json(original))
        for span in document.program.source_map:
            self.assertEqual(span.file, "author_staged_research_project.py")
            self.assertGreater(span.line, 1)
        machines = [row for row in document.program.declarations if isinstance(row, p.Machine)]
        transitions = [row for row in document.program.declarations if isinstance(row, p.Transition)]
        self.assertEqual((len(machines), len(machines[0].states), len(transitions)), (1, 5, 7))
        self.assertEqual(next(row for row in transitions if row.id == "regimen/handoff").when, p.TRUE)

    def test_authored_project_keeps_complete_supplied_inputs_limits_and_provenance(self):
        reference = self.reference()
        authored = example.author_project(reference)
        self.assertEqual(authored.component_inputs.data, reference.component_inputs.data)
        self.assertEqual(authored.limits, reference.limits)
        self.assertEqual(authored.sources[:len(reference.sources)], reference.sources)
        self.assertEqual(authored.assumptions[:len(reference.assumptions)], reference.assumptions)
        self.assertEqual(authored.sources[-1].sha256,
                         hashlib.sha256(p.dumps(example.build_request(), indent=None).encode("utf-8")).hexdigest())
        self.assertEqual(authored.request["implementation_request"]["document"], p.to_data(example.build_request()))
        self.assertEqual(authored.preflight().native_status, "not_run")

    def test_standalone_copy_works_outside_checkout_and_has_stable_source_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / "author_staged_research_project.py"
            shutil.copyfile(Path(example.__file__), copy)
            spec = importlib.util.spec_from_file_location("copied_staged_author", copy)
            copied = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(copied)
            with patch.object(CoreClient, "call", side_effect=AssertionError("No native execution")):
                self.assertEqual(p.document_digest(copied.build_request()), p.document_digest(example.build_request()))
                self.assertEqual(copied.author_project(self.reference()).data, example.author_project(self.reference()).data)

    def test_cli_publishes_new_project_and_cannot_overwrite_original(self):
        with tempfile.TemporaryDirectory() as directory:
            reference = Path(directory) / "reference.json"
            output = Path(directory) / "authored.json"
            self.reference().dump(reference)
            original_bytes = reference.read_bytes()
            printed = io.StringIO()
            with redirect_stdout(printed), patch.object(CoreClient, "call", side_effect=AssertionError("No native execution")):
                self.assertEqual(example.main([str(reference), str(output)]), 0)
            self.assertEqual(json.loads(printed.getvalue())["native_status"], "not_run")
            self.assertEqual(ResearchProject.load(output).component_inputs.data, self.reference().component_inputs.data)
            with self.assertRaises(ResearchProjectError):
                example.main([str(reference), str(reference)])
            self.assertEqual(reference.read_bytes(), original_bytes)

    def test_example_imports_only_standard_library_and_public_sdk(self):
        tree = ast.parse(Path(example.__file__).read_text())
        allowed = {"__future__", "argparse", "dataclasses", "hashlib", "json", "pathlib", "typing", "biocompiler"}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                self.assertIn(node.module.split(".")[0], allowed)
                self.assertNotIn("tools", node.module.split("."))
            if isinstance(node, ast.Import):
                for imported in node.names:
                    self.assertIn(imported.name.split(".")[0], allowed)
        self.assertNotIn("read_text", Path(example.__file__).read_text())


if __name__ == "__main__":
    unittest.main()
