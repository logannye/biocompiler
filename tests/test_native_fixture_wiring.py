"""Every Dune fixture argument must receive a real path in the hosted suite."""

from pathlib import Path
import re
import tempfile
import unittest


DIRECTORY_FIXTURES = {
    "BIOCOMPILER_REFERENCE_CONTRACTS_DOCUMENTS": "tests/conformance/reference-contracts-v1",
    "BIOCOMPILER_REFERENCE_PIPELINE_DOCUMENTS": "tests/conformance/reference-pipeline-semantics-v1",
}


class NativeFixtureWiringTests(unittest.TestCase):
    def assert_fixture_path(self, root, name, relative_path):
        path = root / relative_path
        self.assertTrue(path.resolve().is_relative_to(root.resolve()), "fixture escaped repository")
        if name in DIRECTORY_FIXTURES:
            self.assertEqual(relative_path, DIRECTORY_FIXTURES[name], "declared document directory changed")
            self.assertTrue(path.is_dir(), "document fixture is not a directory: " + relative_path)
        else:
            self.assertTrue(path.is_file(), "file fixture is not a file: " + relative_path)

    def test_every_dune_fixture_is_bound_in_the_complete_native_suite(self):
        root = Path(__file__).resolve().parents[1]
        dune = (root / "core/test/dune").read_text()
        required = set(re.findall(r"%\{env:(BIOCOMPILER_[A-Z0-9_]+)=missing\}", dune))
        self.assertTrue(required)
        self.assertLessEqual({"BIOCOMPILER_ARCHIVE_PYTHON311_CORPUS", "BIOCOMPILER_ARCHIVE_PYTHON314_CORPUS"}, required)
        self.assertLessEqual({"BIOCOMPILER_REFERENCE_PACKAGE_PYTHON311_CORPUS", "BIOCOMPILER_REFERENCE_PACKAGE_PYTHON314_CORPUS",
                              "BIOCOMPILER_REFERENCE_SEQUENCE_EXPORT_CORPUS"}, required)
        workflow = (root / ".github/workflows/ci.yml").read_text()
        suite = workflow.split("      - name: Run every native literal and mutation suite\n", 1)[1]
        suite = suite.split("\n      - name:", 1)[0]
        bindings = re.findall(r'(BIOCOMPILER_[A-Z0-9_]+)="\$GITHUB_WORKSPACE/([^"\n]+)"', suite)
        self.assertEqual(len(bindings), len(dict(bindings)), "duplicate fixture bindings")
        self.assertEqual(set(dict(bindings)), required, "Dune fixture arguments and CI environment differ")
        for name, relative_path in bindings:
            with self.subTest(variable=name):
                self.assert_fixture_path(root, name, relative_path)
        self.assertIn("opam exec -- dune runtest --root core", suite)


    def test_only_exact_declared_document_directories_are_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, relative in DIRECTORY_FIXTURES.items():
                path = root / relative
                path.mkdir(parents=True)
                self.assert_fixture_path(root, name, relative)
                with self.subTest(variable=name), self.assertRaisesRegex(AssertionError, "not a file"):
                    self.assert_fixture_path(root, "BIOCOMPILER_UNDECLARED_DOCUMENTS", relative)
                other = next(value for value in DIRECTORY_FIXTURES.values() if value != relative)
                with self.subTest(variable=name), self.assertRaisesRegex(AssertionError, "directory changed"):
                    self.assert_fixture_path(root, name, other)
            fixture = root / "literal.json"
            fixture.write_text("{}")
            self.assert_fixture_path(root, "BIOCOMPILER_LITERAL", "literal.json")

    def test_declared_directory_cannot_be_missing_or_replaced_by_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, relative in DIRECTORY_FIXTURES.items():
                with self.subTest(variable=name), self.assertRaisesRegex(AssertionError, "not a directory"):
                    self.assert_fixture_path(root, name, relative)
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}")
                with self.subTest(variable=name), self.assertRaisesRegex(AssertionError, "not a directory"):
                    self.assert_fixture_path(root, name, relative)

    def test_fixture_symlink_cannot_escape_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "repository"
            root.mkdir()
            outside = base / "literal.json"
            outside.write_text("{}")
            (root / "literal.json").symlink_to(outside)
            with self.assertRaisesRegex(AssertionError, "escaped repository"):
                self.assert_fixture_path(root, "BIOCOMPILER_LITERAL", "literal.json")


if __name__ == "__main__":
    unittest.main()
