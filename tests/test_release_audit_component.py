"""Independent source-body correspondence and inert component authority controls.

Set BIOCOMPILER_AUDIT_SOURCE_ROOT to the clean component source checkout when
running these stable-tool tests separately from the compiler checkout. Synthetic
fixture packets below test declaration provenance, not native acceptance.
"""
from __future__ import annotations

import ast
import builtins
from contextlib import ExitStack
from copy import deepcopy
import hashlib
import importlib
import json
import os
from pathlib import Path
import stat
import symtable
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get("BIOCOMPILER_AUDIT_SOURCE_ROOT", str(ROOT))).resolve()
sys.path.insert(0, str(ROOT / "tools"))
import release_audit_component as auditor
sys.path[:0] = [str(SOURCE / "tools"), str(SOURCE / "src"), str(SOURCE)]

SPECS = (
    ("audit_sources", "check_policy_development", "source_snapshot", ("audited_sources",)),
    ("audit_fixture", "check_policy_component_fixture", "validate", ("audited_sources",)),
    ("audit_installed", "check_policy_component_material", "validate_installed", ()),
    ("audit_component", "check_policy_component_material", "compare_installed", ("audited_identity", "audited_sources")),
    ("audit_component_producer", "check_policy_material_consumer", "validate_component_producer", ("audited_sources",)),
    ("audit_consumer", "check_policy_material_consumer", "compare", ("audited_identity", "audited_sources")),
    ("audit_authorities", "check_policy_material_prebuilt", "component_authorities", ("audited_sources",)),
    ("audit_component_inputs", "check_policy_material_prebuilt", "component_inputs", ("audited_sources",)),
    ("audit_prebuilt_slot", "check_policy_material_prebuilt", "verify_slot", ("audited_sources",)),
)


def tree_equal(left, right):
    return ast.dump(left, include_attributes=False) == ast.dump(right, include_attributes=False)


def expression(source):
    return ast.parse(source, mode="eval").body


def global_reads(table):
    result = {symbol.get_name() for symbol in table.get_symbols()
              if symbol.is_referenced() and symbol.is_global()}
    for child in table.get_children():
        result.update(global_reads(child))
    return result


def remove_authority_keywords(call, names):
    assert len(call.keywords) >= len(names)
    for key, wanted in zip(call.keywords[-len(names):], names):
        assert key.arg == wanted and tree_equal(key.value, expression(wanted))
    del call.keywords[-len(names):]


def reverse_adapter(node, original, added):
    restored = deepcopy(node)
    assert isinstance(restored.body[0], ast.ImportFrom)
    restored.body.pop(0)
    restored.name = original.name
    for name in reversed(added):
        assert restored.args.kwonlyargs.pop().arg == name
        assert restored.args.kw_defaults.pop() is None
    if node.name == "audit_sources":
        rows = next(item for item in restored.body if isinstance(item, ast.Assign)
                    and any(isinstance(target, ast.Name) and target.id == "rows" for target in item.targets))
        assert tree_equal(rows.value, expression("_source_rows(audited_sources)"))
        rows.value = deepcopy(next(item for item in original.body if isinstance(item, ast.Assign)
                     and any(isinstance(target, ast.Name) and target.id == "rows" for target in item.targets)).value)
        assert tree_equal(restored.body[-2], ast.parse(
            'require(result == audited_sources, "Current source metadata differs from authenticated catalog")').body[0])
        restored.body.pop(-2)
    if node.name == "audit_component_inputs":
        binding = ast.parse('if authority["sources"] != audit_sources(ROOT, audited_sources=audited_sources):\n'
                            '    raise AssertionError("Prebuilt component authority differs from authenticated source catalog")').body[0]
        assert tree_equal(restored.body[1], binding)
        restored.body.pop(1)

    class Restore(ast.NodeTransformer):
        def visit_Call(self, call):
            # This adaptation has a deliberately closed, independently spelled
            # argument map; blindly renaming the callee would miss swapped roles.
            if isinstance(call.func, ast.Name) and call.func.id == "audit_fixture" and node.name == "audit_installed":
                expected = expression('audit_fixture(root, fixture_path, fixture_provenance, identity=identity_value, '
                    'native_sha256={role: binaries["biocompiler-" + role] for role in ("core", "verify")}, '
                    'expected_platform=slot[:2], audited_sources=expected_sources)')
                assert tree_equal(call, expected)
                return expression("validate_fixture_provenance(root, fixture_path, fixture_provenance, identity_value, binaries, slot)")
            self.generic_visit(call)
            if tree_equal(call, expression("dict(audited_identity)")):
                return expression("core.source_identity()" if node.name == "audit_consumer" else "source_identity()")
            if not isinstance(call.func, ast.Name):
                return call
            name = call.func.id
            if name == "audit_sources":
                original_name = {"audit_fixture": "development.source_snapshot", "audit_component": "source_snapshot",
                    "audit_component_producer": "component.source_snapshot", "audit_consumer": "component_support().source_snapshot"}[node.name]
                remove_authority_keywords(call, ("audited_sources",))
                call.func = expression(original_name)
            elif name == "audit_installed":
                call.func = expression("validate_installed" if node.name == "audit_component" else "component.validate_installed")
            elif name == "audit_component":
                assert node.name == "audit_consumer"
                remove_authority_keywords(call, ("audited_identity", "audited_sources"))
                call.func = expression("component_support().compare_installed")
            elif name == "audit_material":
                assert node.name == "audit_consumer"
                remove_authority_keywords(call, ("audited_identity",))
                call.func = expression("material.compare")
            elif name == "audit_component_producer":
                assert node.name == "audit_consumer"
                remove_authority_keywords(call, ("audited_sources",))
                call.func = expression("validate_component_producer")
            elif name == "audit_fixture":
                assert node.name == "audit_authorities"
                remove_authority_keywords(call, ("audited_sources",))
                call.func = expression("fixture_tool.validate")
            elif name == "audit_component_inputs":
                assert node.name == "audit_prebuilt_slot"
                remove_authority_keywords(call, ("audited_sources",))
                call.func = expression("component_inputs")
            return call
    return Restore().visit(restored)


def check_correspondence(source):
    tree = ast.parse(source)
    functions = {item.name: item for item in tree.body if isinstance(item, ast.FunctionDef)}
    assert set(functions) == {row[0] for row in SPECS} | {"_source_rows"}
    module_table = symtable.symtable(source, "release_audit_component.py", "exec")
    top_bindings = {symbol.get_name() for symbol in module_table.get_symbols()
                    if symbol.is_imported() or symbol.is_namespace() or symbol.is_assigned()}
    for table in module_table.get_children():
        assert not global_reads(table) - top_bindings - set(vars(builtins)), table.get_name()
    rows = []
    for name, module_name, original_name, added in SPECS:
        module = importlib.import_module(module_name)
        path = SOURCE / "tools" / (module_name + ".py")
        assert Path(module.__file__).resolve() == path.resolve(), module_name
        raw = path.read_text()
        original = next(item for item in ast.parse(raw).body if isinstance(item, ast.FunctionDef) and item.name == original_name)
        table = next(item for item in symtable.symtable(raw, str(path), "exec").get_children() if item.get_name() == original_name)
        imports = functions[name].body[0]
        assert isinstance(imports, ast.ImportFrom) and imports.module == module_name and imports.level == 0
        imported = {alias.asname or alias.name: getattr(module, alias.name) for alias in imports.names}
        required = global_reads(table) - set(vars(builtins))
        assert set(imported) == required
        for binding in required:
            assert imported[binding] is vars(module)[binding]
        assert tree_equal(reverse_adapter(functions[name], original, added), original), name
        rows.append({"adapter": name, "original": "tools/" + module_name + ".py:" + original_name,
                     "sha256": hashlib.sha256(ast.get_source_segment(raw, original).encode()).hexdigest()})
    return rows


class ComponentAuditTests(unittest.TestCase):
    def setUp(self):
        self.guard = ExitStack(); self.addCleanup(self.guard.close)
        for target in ("subprocess.run", "subprocess.Popen", "subprocess.check_output", "os.system",
                       "os.posix_spawn", "socket.socket", "socket.create_connection", "ctypes.CDLL"):
            self.guard.enter_context(patch(target, side_effect=AssertionError("No process, native load or network in inert audit controls")))
        self.directory = Path(self.guard.enter_context(tempfile.TemporaryDirectory())).resolve()
        self.root = self.directory / "source"; self.root.mkdir()
        # The original roots remain authoritative; write tiny independent files
        # so the complete on-disk census can be checked without Git or a producer.
        for folder in ("core", "src", "tools", "protocol", ".github"):
            (self.root / folder).mkdir()
            (self.root / folder / "literal.txt").write_bytes((folder + "\n").encode())
        (self.root / "pyproject.toml").write_bytes(b"[project]\nname='inert'\n")
        self.catalog = self.source_catalog()

    def source_catalog(self):
        result = {}
        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            raw = path.read_bytes()
            result[path.relative_to(self.root).as_posix()] = {
                "sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw),
                "git_blob": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest(),
                "mode": "100755" if path.stat().st_mode & stat.S_IXUSR else "100644"}
        return result

    def test_all_nine_adapters_restore_exact_original_ast_and_dependency_objects(self):
        rows = check_correspondence(Path(auditor.__file__).read_text())
        self.assertEqual(len(rows), 9)
        self.assertEqual(len({row["original"] for row in rows}), 9)

    def test_correspondence_rejects_dropped_checks_calls_and_authority_changes(self):
        source = Path(auditor.__file__).read_text()
        mutations = (
            ("return result", "return {}"),
            ("len(paths) == 4", "len(paths) == 3"),
            ("archive_receipt(inputs[row['case']]['exported'], path)", "archive_receipt(inputs[row['case']]['exported'])"),
            ("expected_platform=slot[:2]", "expected_platform=slot[1:]"),
            ("audited_sources=expected_sources", "audited_sources={}"),
            ("profile=profile)", "profile='material')"),
            ("check_component_controls(directory, data, component_values, sdk_entries)", "pass"),
            ("audited_identity=audited_identity", "audited_identity={}"),
            ("rows = _source_rows(audited_sources)", "rows = []"),
            ("Current source metadata differs from authenticated catalog", "ignore"),
            ("native_sha256={role: binaries['biocompiler-' + role]", "native_sha256={role: binaries['biocompiler-core']"),
        )
        for old, new in mutations:
            self.assertIn(old, source)
            with self.subTest(old=old), self.assertRaises((AssertionError, KeyError, SyntaxError)):
                check_correspondence(source.replace(old, new, 1))

    def test_source_catalog_matches_bytes_modes_blobs_and_complete_roots_without_git(self):
        result = auditor.audit_sources(self.root, audited_sources=self.catalog)
        self.assertEqual(result, self.catalog)
        self.assertIn(".github/literal.txt", result)
        # Deliberately ignored interpreter/build scratch is exactly the original rule.
        (self.root / "core/_build").mkdir(); (self.root / "core/_build/inert").write_bytes(b"not source")
        (self.root / "src/__pycache__").mkdir(); (self.root / "src/__pycache__/inert").write_bytes(b"not source")
        self.assertEqual(auditor.audit_sources(self.root, audited_sources=self.catalog), self.catalog)

    def test_malformed_catalog_never_becomes_source_authority(self):
        first = next(iter(self.catalog)); original = self.catalog[first]
        cases = [None, {}, {"../foreign": original}, {"core//file": original}, {"core\tfile": original}]
        for key, value in (("sha256", "0" * 64), ("git_blob", "1" * 40), ("mode", "100755"),
                           ("size", True), ("size", original["size"] + 1), ("extra", "open")):
            changed = deepcopy(self.catalog); changed[first][key] = value; cases.append(changed)
        for number, value in enumerate(cases):
            with self.subTest(number=number), self.assertRaises((AssertionError, ValueError)):
                auditor.audit_sources(self.root, audited_sources=value)

    def test_current_source_mutations_and_new_or_redirected_files_are_rejected(self):
        file = self.root / "tools/literal.txt"; original = file.read_bytes()
        file.write_bytes(original + b"changed")
        with self.assertRaises((AssertionError, ValueError)): auditor.audit_sources(self.root, audited_sources=self.catalog)
        file.write_bytes(original)
        file.chmod(0o755)
        with self.assertRaises((AssertionError, ValueError)): auditor.audit_sources(self.root, audited_sources=self.catalog)
        file.chmod(0o644)
        extra = self.root / "core/extra"; extra.write_bytes(b"new")
        with self.assertRaises((AssertionError, ValueError)): auditor.audit_sources(self.root, audited_sources=self.catalog)
        extra.unlink(); file.unlink(); file.symlink_to(self.root / "src/literal.txt")
        with self.assertRaises((AssertionError, ValueError)): auditor.audit_sources(self.root, audited_sources=self.catalog)

    def declaration(self):
        fixture = importlib.import_module("check_policy_component_fixture")
        for name in fixture.INPUTS:
            path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("literal original " + name).encode())
        self.catalog = self.source_catalog()
        supplied = self.directory / "originals"; supplied.mkdir()
        packet = {"schema_version": "biocompiler.policy_component_original_fixture.v0.1",
                  "status": "source_declarations_only", "acceptance": False,
                  "source_sha256": {name: hashlib.sha256((self.root / name).read_bytes()).hexdigest() for name in fixture.INPUTS},
                  "cases": [{"id": label, "request": {}, "limits": {}, "expected": {}} for label in ("A", "B")]}
        original = supplied / "originals.json"; original.write_text(json.dumps(packet))
        for name in ("stdout.log", "stderr.log"): (supplied / name).write_bytes(b"")
        identity = {"revision": "1" * 40, "head_revision": "2" * 40, "run_id": "123", "run_attempt": "2"}
        binaries = {"originals": {"sha256": "3" * 64, "size": 10}, "core": {"sha256": "4" * 64, "size": 11}, "verify": {"sha256": "5" * 64, "size": 12}}
        provenance = {"schema_version": "biocompiler.policy_component_fixture_provenance.v0.1", "status": "source_declarations_only", "acceptance": False,
                      "identity": identity, "platform": {"system": "Linux", "machine": "x86_64"}, "sources": self.catalog,
                      "binaries": binaries, "fixture": {"sha256": hashlib.sha256(original.read_bytes()).hexdigest(), "size": original.stat().st_size},
                      "command": {"argv": fixture.logical_command(), "cwd": "checkout", "returncode": 0,
                                  "logs": {name: {"sha256": hashlib.sha256(b"").hexdigest(), "size": 0} for name in ("stdout.log", "stderr.log")}}}
        path = supplied / "provenance.json"; path.write_text(json.dumps(provenance))
        return original, path, provenance, identity, {role: binaries[role]["sha256"] for role in ("core", "verify")}

    def test_declaration_provenance_validates_current_data_without_emitting_or_running(self):
        original, path, document, identity, binaries = self.declaration()
        checked = auditor.audit_fixture(self.root, original, path, identity=identity, native_sha256=binaries,
                                        expected_platform=("Linux", "x86_64"), audited_sources=self.catalog)
        self.assertEqual(checked, document)
        self.assertIs(checked["acceptance"], False)

    def test_declaration_rejects_self_rehashed_identity_source_role_log_and_scope_changes(self):
        original, path, document, identity, binaries = self.declaration()
        mutations = (
            lambda value: value.update(acceptance=True),
            lambda value: value["identity"].update(revision="9" * 40),
            lambda value: value["identity"].update(run_attempt="3"),
            lambda value: value["platform"].update(machine="arm64"),
            lambda value: value["sources"].clear(),
            lambda value: value["binaries"]["verify"].update(sha256="9" * 64),
            lambda value: value["binaries"].pop("originals"),
            lambda value: value["command"].update(returncode=False),
            lambda value: value["command"]["logs"].pop("stderr.log"),
            lambda value: value["fixture"].update(sha256="9" * 64),
        )
        for number, mutate in enumerate(mutations):
            changed = deepcopy(document); mutate(changed); path.write_text(json.dumps(changed))
            with self.subTest(number=number), self.assertRaises((AssertionError, ValueError)):
                auditor.audit_fixture(self.root, original, path, identity=identity, native_sha256=binaries,
                                      expected_platform=("Linux", "x86_64"), audited_sources=self.catalog)
        path.write_text(json.dumps(document)); (path.parent / "stdout.log").write_bytes(b"changed")
        with self.assertRaises((AssertionError, ValueError)):
            auditor.audit_fixture(self.root, original, path, identity=identity, native_sha256=binaries,
                                  expected_platform=("Linux", "x86_64"), audited_sources=self.catalog)

    def test_old_profile_default_and_component_checks_both_remain_in_consumer_adapter(self):
        import inspect
        self.assertEqual(inspect.signature(auditor.audit_consumer).parameters["profile"].default, "material")
        source = Path(auditor.__file__).read_text()
        tree = ast.parse(source)
        node = next(item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == "audit_consumer")
        names = {ast.unparse(item.func) for item in ast.walk(node) if isinstance(item, ast.Call)}
        self.assertTrue({"audit_component", "audit_material", "check_manifest", "check_worker", "audit_component_producer"} <= names)
        self.assertNotIn("core.source_identity", names)
        self.assertNotIn("component_support().source_snapshot", names)


if __name__ == "__main__":
    unittest.main()
