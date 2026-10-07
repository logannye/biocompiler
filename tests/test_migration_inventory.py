"""The migration census must be complete, reproducible and fail closed."""

import argparse
import ast
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import migration_inventory as inventory


class MigrationInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.actual = inventory.build_inventory(inventory.ROOT)

    def test_research_project_remains_authoring_and_fresh_native_transport(self):
        entries = [entry for entry in self.actual['entries']
                   if entry['current_implementation']['source'] == 'policy.research_project']
        self.assertTrue(entries)
        for entry in entries:
            contract = self.actual['contracts'][entry['contract']]
            self.assertEqual(contract['target_owner'], 'Python')
            self.assertEqual(contract['source_authority'],
                'explicit_original_project_and_supplied_component_authority_only_fresh_native_checks_authorize_conditional_paired_export')
            self.assertEqual(contract['disposition'],
                'retain_public_project_authoring_and_supplied_inputs_with_fresh_native_verification_before_export')
            self.assertEqual(entry['migration_state'], 'legacy')

    def fixture(self, *, package="__version__ = '0.1.0'\n", cli=None, server=None):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        files = {
            "pyproject.toml": '[project]\nname="fixture"\nversion="0.1.0"\n[project.scripts]\nbiocompiler="biocompiler.cli:main"\n',
            "src/biocompiler/__init__.py": package,
            "src/biocompiler/cli.py": cli or '''import argparse

def main(argv=None):
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers()
    for operation in ("verify", "export"):
        command = commands.add_parser("fixture-" + operation)
        command.add_argument("--expected-request", required=True)
        if operation == "export":
            command.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    raise RuntimeError("inventory must never execute product code")
''',
            "src/biocompiler/studio/server.py": server or '_POST = {}\n_STATIC = {}\n',
            "tests/test_fixture.py": 'from biocompiler import Example\nvalue = "fixture-verify"\n',
        }
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return root

    def test_real_export_census_resolves_every_explicit_all_symbol(self):
        expected = set()
        for path in (inventory.ROOT / "src/biocompiler").rglob("*.py"):
            parts = list(path.relative_to(inventory.ROOT / "src").with_suffix("").parts)
            if parts[-1] == "__init__":
                parts.pop()
            module = ".".join(parts)
            tree = ast.parse(path.read_text())
            for node in tree.body:
                if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
                    expected.update("export:" + module + "." + name for name in ast.literal_eval(node.value))
        actual = {entry["id"] for entry in self.actual["entries"] if entry["category"] == "export"}
        self.assertEqual(expected, actual)
        self.assertGreater(len(actual), 500)

    def test_static_cli_census_matches_independently_constructed_argparse_tree(self):
        from biocompiler import cli
        captured = []

        class Captured(Exception):
            pass

        def capture(parser, *args, **kwargs):
            captured.append(parser)
            raise Captured

        with patch.object(argparse.ArgumentParser, "parse_args", capture):
            with self.assertRaises(Captured):
                cli.main([])
        parsers = {}
        for action in captured[0]._actions:
            if isinstance(action, argparse._SubParsersAction):
                parsers.update(action.choices)
        from biocompiler.policy.cli import _parser
        for action in _parser()._actions:
            if isinstance(action, argparse._SubParsersAction):
                parsers.update({"policy " + name: parser for name, parser in action.choices.items()})
        actual = {entry["value"]: entry for entry in self.actual["entries"] if entry["category"] == "cli_command"}
        self.assertEqual(set(parsers), set(actual))
        for name, parser in parsers.items():
            expected_flags = {option for action in parser._actions for option in (action.option_strings or [action.dest])
                              if option not in {"-h", "--help"}}
            static_flags = {flag for argument in actual[name]["arguments"] for flag in argument["flags"]}
            self.assertEqual(expected_flags, static_flags, name)

    def test_static_json_profile_metadata_is_parsed_without_executing_code(self):
        def resolve(name):
            self.assertEqual(name, "_PROFILE_JSON")
            return '{"profile":"fixture.profile.v1","size":9007199254740993}'
        expression = ast.parse("json.loads(_PROFILE_JSON)", mode="eval").body
        self.assertEqual(inventory.literal(expression, resolve),
                         {"profile": "fixture.profile.v1", "size": 9007199254740993})
        for text in ('{"x":1,"x":2}', '{"x":NaN}', '{broken'):
            with self.assertRaises(inventory.InventoryError):
                inventory.literal(expression, lambda _: text)
        for expression in ("json.loads(dynamic())", "json.loads(9)",
                           "json.loads('{}', object_hook=execute)", "other.loads('{}')"):
            with self.assertRaises(inventory.InventoryError):
                inventory.literal(ast.parse(expression, mode="eval").body, resolve)

    def test_qualified_discovered_module_constants_are_inert_and_exact(self):
        root = self.fixture()
        (root / "src/biocompiler/constants.py").write_text(
            "LIMIT = 13\nMAXIMUM = LIMIT * 3\nraise RuntimeError('must not execute')\n")
        declarations = (
            "from biocompiler import constants as limits\n",
            "from . import constants as limits\n",
            "import biocompiler.constants as limits\n",
        )
        for imported in declarations:
            with self.subTest(imported=imported):
                (root / "src/biocompiler/consumer.py").write_text(
                    imported + "PROFILE = {'limit': limits.LIMIT, 'maximum': limits.MAXIMUM}\n"
                    "raise RuntimeError('must not execute')\n")
                sources = inventory.Sources(root)
                self.assertEqual(sources.value("biocompiler.consumer", "PROFILE"),
                                 {"limit": 13, "maximum": 39})
        (root / "src/biocompiler/consumer.py").write_text(
            "from biocompiler.constants import MAXIMUM as CAP\nPROFILE = {'limit': CAP}\n")
        self.assertEqual(inventory.Sources(root).value("biocompiler.consumer", "PROFILE"),
                         {"limit": 39})

    def test_qualified_constant_lookup_rejects_unresolved_or_dynamic_sources(self):
        root = self.fixture()
        (root / "src/biocompiler/constants.py").write_text("LIMIT = 13\nDYNAMIC = execute()\n")
        for declaration in (
            "from biocompiler import constants as limits\nPROFILE = limits.MISSING\n",
            "from biocompiler import constants as limits\nPROFILE = limits.DYNAMIC\n",
            "from external import constants as limits\nPROFILE = limits.LIMIT\n",
            "from biocompiler import absent as limits\nPROFILE = limits.LIMIT\n",
        ):
            with self.subTest(declaration=declaration):
                (root / "src/biocompiler/consumer.py").write_text(declaration)
                with self.assertRaises(inventory.InventoryError):
                    inventory.Sources(root).value("biocompiler.consumer", "PROFILE")

    def test_qualified_constant_cycle_retains_fail_closed_boundary(self):
        root = self.fixture()
        (root / "src/biocompiler/constants.py").write_text(
            "from biocompiler import consumer as original\nLIMIT = original.PROFILE\n")
        (root / "src/biocompiler/consumer.py").write_text(
            "from biocompiler import constants as limits\nPROFILE = limits.LIMIT\n")
        with self.assertRaisesRegex(inventory.InventoryError, "Cyclic constant"):
            inventory.Sources(root).value("biocompiler.consumer", "PROFILE")

    def test_package_attribute_cannot_be_mistaken_for_same_named_module(self):
        for package in (
            "constants = {'LIMIT': 91}\n",
            "class constants:\n    LIMIT = 91\n",
            "from biocompiler.other import constants\n",
        ):
            with self.subTest(package=package):
                root = self.fixture(package=package)
                (root / "src/biocompiler/constants.py").write_text("LIMIT = 13\n")
                (root / "src/biocompiler/other.py").write_text("class constants:\n    LIMIT = 91\n")
                (root / "src/biocompiler/consumer.py").write_text(
                    "from biocompiler import constants as limits\nPROFILE = limits.LIMIT\n")
                with self.assertRaisesRegex(inventory.InventoryError, "Ambiguous imported module constant"):
                    inventory.Sources(root).value("biocompiler.consumer", "PROFILE")

    def test_dynamic_package_lookup_requires_exact_reviewed_lazy_guard(self):
        hook = '''def __getattr__(name: str):
    if name not in _LEGACY_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    _load_legacy_exports()
    return globals()[name]
'''
        prefix = "_LEGACY_EXPORTS = {}\n__all__ = []\n"
        root = self.fixture(package=prefix + hook)
        (root / "src/biocompiler/constants.py").write_text("LIMIT = 13\n")
        (root / "src/biocompiler/consumer.py").write_text(
            "from biocompiler import constants as limits\nPROFILE = limits.LIMIT\n")
        self.assertEqual(inventory.Sources(root).value("biocompiler.consumer", "PROFILE"), 13)
        for package in (
            "def __getattr__(name):\n    return type('Shadow', (), {'LIMIT': 91})\n",
            prefix + hook.replace("name not in", "name in"),
            prefix + "@unknown\n" + hook,
            prefix + "AttributeError = RuntimeError\n" + hook,
            prefix + "__getattr__ = dynamic()\n",
        ):
            with self.subTest(package=package):
                (root / "src/biocompiler/__init__.py").write_text(package)
                with self.assertRaisesRegex(inventory.InventoryError, "Dynamic imported module constant"):
                    inventory.Sources(root).value("biocompiler.consumer", "PROFILE")

    def test_real_schema_and_module_declarations_cannot_disappear(self):
        modules = {source["path"] for source in self.actual["sources"].values() if source["path"].endswith(".py") and source["path"].startswith("src/")}
        expected_modules = {path.relative_to(inventory.ROOT).as_posix() for path in (inventory.ROOT / "src/biocompiler").rglob("*.py")}
        self.assertEqual(expected_modules, modules)
        schemas = {(self.actual["sources"][entry["current_implementation"]["source"]]["path"], entry["current_implementation"]["line"])
                   for entry in self.actual["entries"] if entry["category"] == "schema"}
        expected = set()
        for relative in expected_modules:
            tree = ast.parse((inventory.ROOT / relative).read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "schema_version" and node.value:
                    expected.add((relative, node.lineno))
                elif isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "schema_version" for target in node.targets):
                    expected.add((relative, node.lineno))
        self.assertEqual(expected, schemas)

    def test_every_record_has_resolvable_owner_authority_tasks_and_test_evidence(self):
        identities = [entry["id"] for entry in self.actual["entries"]]
        self.assertEqual(len(identities), len(set(identities)))
        for entry in self.actual["entries"]:
            contract = self.actual["contracts"][entry["contract"]]
            self.assertIn(contract["target_owner"], {"Python", "OCaml", "TypeScript"})
            self.assertTrue(contract["source_authority"])
            self.assertTrue(contract["dependent_tasks"])
            self.assertTrue(contract["compatibility_contract"])
            self.assertTrue(contract["disposition"])
            self.assertEqual(entry["migration_state"], "legacy")
            coverage = self.actual["test_reference_sets"][entry["test_coverage"]]
            self.assertEqual(coverage["execution_status"], "not_measured_by_inventory")
            for index in coverage["file_indices"]:
                self.assertTrue((inventory.ROOT / self.actual["test_source_files"][index]).is_file())
            self.assertIn(entry["current_implementation"]["source"], self.actual["sources"])

    def test_loop_commands_preserve_conditional_argument_contracts_without_execution(self):
        result = inventory.build_inventory(self.fixture())
        commands = {entry["value"]: entry for entry in result["entries"] if entry["category"] == "cli_command"}
        self.assertEqual(set(commands), {"fixture-verify", "fixture-export"})
        self.assertEqual(commands["fixture-verify"]["source_authority_flags"], ["--expected-request"])
        self.assertEqual([arg["flags"] for arg in commands["fixture-export"]["arguments"]], [["--expected-request"], ["--output"]])

    def test_reproducible_custom_outputs_and_check_reject_stale_or_missing_files(self):
        root = self.fixture()
        output, document = root / "custom.json", root / "custom.md"
        args = ["--root", str(root), "--output", str(output), "--markdown", str(document)]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(inventory.main(args), 0)
            first = output.read_bytes()
            self.assertEqual(inventory.main(args), 0)
            self.assertEqual(output.read_bytes(), first)
            self.assertEqual(json.loads(first), inventory.build_inventory(root))
            self.assertEqual(inventory.main([*args, "--check"]), 0)
            source = root / "src/biocompiler/__init__.py"
            source.write_text(source.read_text() + "\n# changed source identity\n")
            self.assertEqual(inventory.main([*args, "--check"]), 1)
            self.assertEqual(output.read_bytes(), first, "check must not rewrite stale evidence")
            output.unlink()
            self.assertEqual(inventory.main([*args, "--check"]), 1)

    def test_missing_duplicate_or_dynamic_exports_fail(self):
        cases = [
            "__all__ = ['Missing']\n",
            "def example(): pass\n__all__ = ['example', 'example']\n",
            "__all__ = runtime_exports()\n",
            "__all__ = []\n__all__.append('hidden')\n",
            "__all__ = []\n__all__ += ['hidden']\n",
            "__all__ = []\n__all__[0] = 'hidden'\n",
            "__all__ = []\nalias = __all__\nalias.append('hidden')\n",
            "if True:\n    __all__ = ['hidden']\n",
            "__all__ = []\n__all__ = []\n",
            "from biocompiler.cli import *\n",
        ]
        for package in cases:
            with self.subTest(package=package), self.assertRaises(inventory.InventoryError):
                inventory.build_inventory(self.fixture(package=package))

    def test_alias_exports_resolve_to_source_and_class_contract(self):
        root = self.fixture(package="from biocompiler.frontend import Original as Renamed\n__all__ = ['Renamed']\n")
        (root / "src/biocompiler/frontend.py").write_text("class Original:\n    def method(self, value: str) -> str:\n        return value\n")
        result = inventory.build_inventory(root)
        exported = next(entry for entry in result["entries"] if entry["category"] == "export")
        self.assertEqual(exported["implementation_symbol"], "biocompiler.frontend.Original")
        self.assertEqual(result["contracts"][exported["contract"]]["target_owner"], "Python")
        defined = next(entry for entry in result["entries"] if entry.get("symbol") == "Original")
        self.assertEqual(defined["public_methods"], [{"name": "method", "signature": "self, value: str"}])

    def test_dynamic_schema_and_invalid_python_fail(self):
        for package in ("SCHEMA_VERSION = runtime_version()\n", "class Broken(:\n"):
            with self.subTest(package=package), self.assertRaises(inventory.InventoryError):
                inventory.build_inventory(self.fixture(package=package))

    def test_dynamic_duplicate_or_unreachable_cli_registration_fails(self):
        cases = [
            'name = unknown()\n    commands.add_parser(name)',
            'commands.add_parser("duplicate")\n    commands.add_parser("duplicate")',
            'commands.add_parser("ok")\n    args = parser.parse_args(argv)\n    commands.add_parser("unreachable")',
        ]
        for registration in cases:
            cli = "import argparse\ndef main(argv=None):\n    parser = argparse.ArgumentParser()\n    commands = parser.add_subparsers()\n    " + registration + "\n    args = parser.parse_args(argv)\n"
            with self.subTest(registration=registration), self.assertRaises(inventory.InventoryError):
                inventory.build_inventory(self.fixture(cli=cli))

    def test_unmapped_studio_direct_route_or_dynamic_table_fails(self):
        for server in ('_POST = runtime_routes()\n_STATIC = {}\n',
                       '_POST = {}\n_STATIC = {}\n_POST.update(runtime_routes())\n',
                       '_POST = {}\n_STATIC = {}\n_STATIC["/hidden"] = "hidden.html"\n',
                       '_POST = {}\n_STATIC = {}\ndef route(self):\n    if self.path == "/api/new": return None\n',
                       '_POST = {}\n_STATIC = {}\nUNMAPPED = "/api/new"\n'):
            with self.subTest(server=server), self.assertRaises(inventory.InventoryError):
                inventory.build_inventory(self.fixture(server=server))

    def test_unknown_module_ownership_fails_instead_of_assigning_generic_owner(self):
        root = self.fixture()
        (root / "src/biocompiler/new_authority.py").write_text("def accept(): pass\n")
        with self.assertRaisesRegex(inventory.InventoryError, "No reviewed ownership rule"):
            inventory.build_inventory(root)


if __name__ == "__main__":
    unittest.main()
