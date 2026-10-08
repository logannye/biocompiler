"""Fresh processes prove the authoring path does not load semantic modules."""
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PolicyImportTests(unittest.TestCase):
    def run_child(self, source):
        result = subprocess.run([sys.executable, "-c", source], cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_policy_namespace_and_commands_cannot_import_semantic_implementations(self):
        self.run_child('''
import importlib.abc, sys, tempfile
from pathlib import Path
class Deny(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(("biocompiler.compiler", "biocompiler.semantics", "biocompiler.verification", "biocompiler.synthesis", "biocompiler.ir", "biocompiler.models", "biocompiler.backends", "biocompiler.core_", "biocompiler.cli")):
            raise AssertionError("Authoring imported semantic code: " + fullname)
sys.meta_path.insert(0, Deny())
import biocompiler
assert not biocompiler._legacy_loaded
import biocompiler.policy as bp
from biocompiler.entrypoint import main
from biocompiler.policy.examples import build_example
program = build_example("context_gated_response")
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / "policy.json"
    path.write_text(bp.dumps(program))
    assert main(["policy", "inspect", str(path), "--json"]) == 0
    assert main(["policy", "diff", str(path), str(path), "--json"]) == 0
    assert main(["policy", "export-schema", "--output", str(Path(directory) / "schema.json")]) == 0
assert not biocompiler._legacy_loaded
''')

    def test_all_original_exports_retain_identity_and_public_census(self):
        witness = json.loads((ROOT / "tests/conformance/policy-entrypoint-source-counterpart-v1.json").read_text())
        original = ast.parse(witness["sources"]["src/biocompiler/__init__.py"]["before_source"])
        bindings = {alias.asname or alias.name: (node.module, alias.name)
                    for node in original.body if isinstance(node, ast.ImportFrom) for alias in node.names}
        result = self.run_child('''
import importlib, json
import biocompiler
bindings = json.loads(%r)
assert set(biocompiler.__all__) == set(bindings)
assert not biocompiler._legacy_loaded
for name, (module, attribute) in bindings.items():
    assert getattr(biocompiler, name) is getattr(importlib.import_module(module), attribute), name
assert biocompiler._legacy_loaded
print(len(bindings))
''' % json.dumps(bindings))
        self.assertEqual(int(result), 524)

    def test_unknown_root_attribute_does_not_initialize_legacy_exports(self):
        self.run_child('''
import biocompiler
assert "Therapy" in dir(biocompiler)
assert not hasattr(biocompiler, "not_an_export")
assert not biocompiler._legacy_loaded
''')

    def test_module_and_console_targets_use_lightweight_dispatch(self):
        import tomllib
        entry = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["scripts"]["biocompiler"]
        self.assertEqual(entry, "biocompiler.entrypoint:main")
        result = subprocess.run([sys.executable, "-m", "biocompiler", "policy", "--help"], cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src")}, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("export-request", result.stdout)

    def test_source_restoration_rejects_unlisted_bytes_and_keeps_original_exports(self):
        from tools import policy_entrypoint_source_lineage as lineage
        from tools.realization_source_lineage import verify_captured_source
        witness = lineage.witness()
        for name in lineage.ROUTES:
            old, proof = lineage.restore(name)
            self.assertEqual(old.decode(), witness["sources"][name]["before_source"])
            self.assertEqual(verify_captured_source(ROOT, {"path": name, "sha256": lineage.sha(old)}), proof)
            with self.assertRaisesRegex(ValueError, "exact counterpart"):
                lineage.restore(name, (ROOT / name).read_bytes() + b"\n# unreviewed\n")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / lineage.WITNESS
            path.parent.mkdir(parents=True)
            path.write_bytes((ROOT / lineage.WITNESS).read_bytes() + b" ")
            with self.assertRaisesRegex(ValueError, "witness bytes changed"):
                lineage.witness(root)

    def test_workflow_source_scope_checks_current_bytes_and_closed_additions(self):
        from copy import deepcopy
        from tools import policy_entrypoint_source_lineage as lineage
        from tools.check_realization_workflow_corpus import source_scope
        from tools.freeze_realization_workflow import source_inventory
        actual = source_inventory()
        scope = source_scope(actual)
        self.assertEqual(scope["schema_version"], "biocompiler.realization_workflow_source_scope.v2")
        expected_routes = {
            "src/biocompiler/__init__.py",
            "src/biocompiler/__main__.py",
            "src/biocompiler/cli.py",
            "src/biocompiler/compiler/construct.py",
            "src/biocompiler/compiler/molecular.py",
            "src/biocompiler/compiler/pipeline.py",
            "src/biocompiler/compiler/verification_workflow.py",
            "src/biocompiler/synthesis/components.py",
            "src/biocompiler/synthesis/selection.py",
            "src/biocompiler/synthesis/synthetic.py",
        }
        self.assertEqual({row["path"] for row in scope["reviewed_source_routes"]}, expected_routes)
        self.assertEqual(len(scope["reviewed_source_routes"]), len(expected_routes))
        self.assertEqual(scope["reviewed_routes"], scope["reviewed_source_routes"])
        self.assertIn("biocompiler.policy", scope["denied_modules"])
        self.assertIn("examples.expressive_policies", scope["denied_modules"])
        self.assertNotIn("biocompiler.entrypoint", scope["denied_modules"])
        self.assertEqual(lineage.verify_entrypoint()["sha256"],
            next(row["sha256"] for row in actual if row["path"] == lineage.ENTRYPOINT))
        for path in lineage.ROUTES:
            changed = deepcopy(actual)
            next(row for row in changed if row["path"] == path)["sha256"] = "0" * 64
            with self.assertRaisesRegex(AssertionError, "source bytes changed"):
                source_scope(changed)
        with self.assertRaisesRegex(AssertionError, "Unreviewed workflow source addition"):
            source_scope([*actual, {"path": "src/biocompiler/policy/unreviewed.py", "sha256": "0" * 64}])


if __name__ == "__main__":
    unittest.main()
