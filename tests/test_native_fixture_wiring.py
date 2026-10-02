"""Every Dune fixture argument must receive a real path in the hosted suite."""

from pathlib import Path
import re
import unittest


class NativeFixtureWiringTests(unittest.TestCase):
    def test_every_dune_fixture_is_bound_in_the_complete_native_suite(self):
        root = Path(__file__).resolve().parents[1]
        dune = (root / "core/test/dune").read_text()
        required = set(re.findall(r"%\{env:(BIOCOMPILER_[A-Z_]+)=missing\}", dune))
        self.assertTrue(required)
        workflow = (root / ".github/workflows/ci.yml").read_text()
        suite = workflow.split("      - name: Run every native literal and mutation suite\n", 1)[1]
        suite = suite.split("\n      - name:", 1)[0]
        bindings = re.findall(r'(BIOCOMPILER_[A-Z_]+)="\$GITHUB_WORKSPACE/([^"\n]+)"', suite)
        self.assertEqual(len(bindings), len(dict(bindings)), "duplicate fixture bindings")
        self.assertEqual(set(dict(bindings)), required, "Dune fixture arguments and CI environment differ")
        for name, relative_path in bindings:
            with self.subTest(variable=name):
                path = root / relative_path
                self.assertTrue(path.is_file(), relative_path)
                self.assertTrue(path.resolve().is_relative_to(root))
        self.assertIn("opam exec -- dune runtest --root core", suite)


if __name__ == "__main__":
    unittest.main()
