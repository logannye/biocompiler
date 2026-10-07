"""Inert adapter correspondence and hostile retained-starter controls.

Set BIOCOMPILER_RESEARCHER_SOURCE_ROOT to the frozen researcher source checkout.
Synthetic wheel/example bytes below are never executable acceptance evidence.
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
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get("BIOCOMPILER_RESEARCHER_SOURCE_ROOT", str(ROOT))).resolve()
sys.path.insert(0, str(ROOT / "tools"))
import release_audit_researcher as auditor
sys.path[:0] = [str(SOURCE / "tools"), str(SOURCE / "src"), str(SOURCE)]
HAS_SOURCE = (SOURCE / "tools/researcher_alpha_starter.py").is_file()


def tree_equal(left, right):
    return ast.dump(left, include_attributes=False) == ast.dump(right, include_attributes=False)


def global_reads(table):
    names = {symbol.get_name() for symbol in table.get_symbols()
             if symbol.is_referenced() and symbol.is_global()}
    for child in table.get_children():
        names.update(global_reads(child))
    return names


def check_correspondence(source):
    """Restore a single closed adaptation, checking dependency object identity."""
    tree = ast.parse(source)
    adapter = next(node for node in tree.body
                   if isinstance(node, ast.FunctionDef) and node.name == "audit_prebuilt_slot")
    module = importlib.import_module("check_policy_material_prebuilt")
    path = SOURCE / "tools/check_policy_material_prebuilt.py"
    assert Path(module.__file__).resolve() == path
    raw = path.read_text()
    original = next(node for node in ast.parse(raw).body
                    if isinstance(node, ast.FunctionDef) and node.name == "verify_slot")
    table = next(node for node in symtable.symtable(raw, str(path), "exec").get_children()
                 if node.get_name() == "verify_slot")
    imports = adapter.body[0]
    assert isinstance(imports, ast.ImportFrom) and imports.module == module.__name__ and imports.level == 0
    required = global_reads(table) - set(vars(builtins))
    assert {alias.asname or alias.name for alias in imports.names} == required
    assert all(not alias.asname and getattr(module, alias.name) is vars(module)[alias.name]
               for alias in imports.names)
    restored = deepcopy(adapter)
    restored.name = "verify_slot"
    restored.body.pop(0)
    assert restored.args.kwonlyargs.pop().arg == "audited_sources"
    assert restored.args.kw_defaults.pop() is None
    replaced = []

    class Reverse(ast.NodeTransformer):
        def visit_Call(self, call):
            self.generic_visit(call)
            if isinstance(call.func, ast.Name) and call.func.id == "audit_component_inputs":
                expected = ast.parse("audit_component_inputs(producer, directory / 'evidence', authority, "
                                     "identity, expected_binary, slot, audited_sources=audited_sources)",
                                     mode="eval").body
                assert tree_equal(call, expected)
                call.func.id = "component_inputs"
                call.keywords.pop()
                replaced.append(True)
            return call

    restored = Reverse().visit(restored)
    assert len(replaced) == 1
    assert tree_equal(restored, original)
    module_table = symtable.symtable(source, "release_audit_researcher.py", "exec")
    bindings = {symbol.get_name() for symbol in module_table.get_symbols()
                if symbol.is_imported() or symbol.is_namespace() or symbol.is_assigned()}
    assert all(not global_reads(table) - bindings - set(vars(builtins))
               for table in module_table.get_children())


@unittest.skipUnless(HAS_SOURCE, "Set BIOCOMPILER_RESEARCHER_SOURCE_ROOT to researcher source")
class ResearcherAuditTests(unittest.TestCase):
    def setUp(self):
        self.guard = ExitStack()
        self.addCleanup(self.guard.close)
        # Main-tool imports deliberately prioritize the stable audit checkout.
        # Each correspondence test independently selects its original source
        # modules, then restores the previous interpreter module/path state.
        self.guard.enter_context(patch.object(sys, "path", [
            str(SOURCE / "tools"), str(SOURCE / "src"), str(SOURCE), *sys.path]))
        self.guard.enter_context(patch.dict(sys.modules))
        for name, module in list(sys.modules.items()):
            origin = getattr(module, "__file__", None)
            if not origin:
                continue
            expected = SOURCE / "tools" / (name + ".py")
            if "." not in name and expected.is_file() and Path(origin).resolve() != expected:
                sys.modules.pop(name, None)
            elif name == "biocompiler" or name.startswith("biocompiler."):
                if not Path(origin).resolve().is_relative_to(SOURCE / "src"):
                    sys.modules.pop(name, None)
        for target in ("subprocess.run", "subprocess.Popen", "subprocess.check_output", "os.system",
                       "os.posix_spawn", "socket.socket", "socket.create_connection", "ctypes.CDLL"):
            self.guard.enter_context(patch(target, side_effect=AssertionError("Inert audit cannot execute or connect")))
        self.starter = importlib.import_module("researcher_alpha_starter")
        self.guard.enter_context(patch.object(self.starter, "source_authority", side_effect=AssertionError("No Git source helper")))
        self.guard.enter_context(patch.object(self.starter, "create_starter", side_effect=AssertionError("No hosted assembler")))
        self.folder = Path(self.guard.enter_context(tempfile.TemporaryDirectory())).resolve()

    def test_adapter_preserves_every_original_check_and_dependency(self):
        check_correspondence(Path(auditor.__file__).read_text())

    def test_exact_reviewed_source_function_pins(self):
        expected = {
            "check_policy_material_prebuilt": {"verify_slot", "staged_identity", "researcher_identity", "check_commands"},
            "check_policy_staged_material_installed": {"input_pins", "check_observations", "validate_installed", "compare_installed"},
            "check_researcher_alpha_installed": {"input_pins", "check_origins", "expected_project", "check_mutant", "validate_installed", "compare_installed"},
            "check_researcher_alpha": {"checked_assets", "check_census", "check_observations"},
            "researcher_alpha_starter": {"plan"},
        }
        self.assertEqual(set(auditor.SOURCE_FUNCTION_PINS),
                         {"tools/" + module + ".py:" + function for module, functions in expected.items() for function in functions})
        for location, digest in auditor.SOURCE_FUNCTION_PINS.items():
            name, function = location.rsplit(":", 1)
            raw = (SOURCE / name).read_text()
            node = next(node for node in ast.parse(raw).body if isinstance(node, ast.FunctionDef) and node.name == function)
            self.assertEqual(hashlib.sha256(ast.get_source_segment(raw, node).encode()).hexdigest(), digest, location)

    def test_correspondence_rejects_omitted_checks_or_substituted_authority(self):
        raw = Path(auditor.__file__).read_text()
        mutations = (
            ("audited_sources=audited_sources)", "audited_sources={})"),
            ("staged.validate_installed(producer,", "staged.input_pins(producer,"),
            ("researcher.validate_installed(producer,", "researcher.input_pins(producer,"),
            ("expected_sources=authority['sources']", "expected_sources={}"),
            ("researcher_identity(producer,", "staged_identity(producer,"),
            ("check_component_controls(directory, data, component_values, sdk_entries)", "pass"),
            ("researcher_path=researcher_path)", "researcher_path=None)"),
            ("from check_policy_material_prebuilt import CASES,", "from check_policy_material_prebuilt import CASES as OTHER,"),
        )
        # Mutate only the adapted body, so authority helpers before it cannot
        # accidentally absorb a test edit intended for the correspondence check.
        offset = raw.index("def audit_prebuilt_slot(")
        for old, new in mutations:
            self.assertIn(old, raw[offset:])
            changed = raw[:offset] + raw[offset:].replace(old, new, 1)
            with self.subTest(old=old), self.assertRaises((AssertionError, KeyError, SyntaxError)):
                check_correspondence(changed)

    @staticmethod
    def pin(raw, *, child=False):
        return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes" if child else "size": len(raw)}

    def fixture(self):
        source = self.folder / "source"
        source.mkdir()
        catalog, contents = {}, {}
        for name in self.starter.SOURCE_FILES:
            raw = ("INERT INDEPENDENT SOURCE: " + name + "\n").encode()
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            catalog[name] = {**self.pin(raw), "git_blob": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest(), "mode": "100644"}
            contents[name] = raw
        slots = [self.folder / ("slot-" + str(index)) for index in range(4)]
        evidence = slots[0] / "evidence"
        (evidence / "researcher-alpha").mkdir(parents=True)
        identity = {"revision": "1" * 40, "head_revision": "2" * 40, "run_id": "123", "run_attempt": "2"}
        child = {**identity, "status": "pass", "system": "Linux", "machine": "x86_64", "python_version": "3.11.15", "files": {}}
        for name in ("staged-project.json", "comparison-project.json", "staged.zip", "comparison.zip"):
            raw = ("INERT RETAINED EXAMPLE: " + name).encode()
            (evidence / "researcher-alpha" / name).write_bytes(raw)
            child["files"]["researcher-alpha/" + name] = self.pin(raw, child=True)
            contents["verified-examples/" + name] = raw
        child_raw = json.dumps(child).encode()
        (evidence / "researcher-alpha.json").write_bytes(child_raw)
        contents["evidence/researcher-alpha.json"] = child_raw
        slot_names = sorted((system, machine, minor) for system, machine in (("Linux", "x86_64"), ("Darwin", "arm64"))
                            for minor in ("3.11", "3.14"))
        comparison = {**identity, "schema_version": "biocompiler.policy_material_prebuilt_campaign.v0.4", "status": "pass",
                      "slots": [{"slot": list(slot)} for slot in slot_names],
                      "researcher_project": {"status": "pass", "attempts": [{"slot": ["Linux", "x86_64", "3.11"],
                          "run_attempt": "2", "receipt": self.pin(child_raw, child=True)}]}}
        sdk = self.folder / "sdk.whl"
        sdk.write_bytes(b"INERT SDK, NEVER INSTALLED")
        contents["wheels/sdk.whl"] = sdk.read_bytes()
        natives = {}
        candidate = {"source_revision": identity["head_revision"], "tested_revision": identity["revision"],
                     "run_id": identity["run_id"], "sdk": self.pin(sdk.read_bytes()), "platforms": {}}
        for name in ("linux-x86_64", "macos-arm64"):
            path = self.folder / (name + ".whl")
            path.write_bytes(("INERT NATIVE, NEVER EXECUTED: " + name).encode())
            natives[name] = {"native": path}
            candidate["platforms"][name] = {"name": path.name, **self.pin(path.read_bytes())}
            contents["wheels/" + path.name] = path.read_bytes()
        output = self.folder / "output"
        output.mkdir()
        candidate_path = self.folder / "candidate.json"
        candidate_path.write_text(json.dumps(candidate))
        contents["evidence/candidate.json"] = candidate_path.read_bytes()
        (output / "prebuilt-comparison.json").write_text(json.dumps(comparison))
        contents["evidence/prebuilt-comparison.json"] = (output / "prebuilt-comparison.json").read_bytes()
        manifest = {"schema_version": "biocompiler.researcher_alpha_starter.v0.1", "status": "installed_candidate",
                    "release_acceptance": "pending_overall_and_actual_main_gates", "empirical": "unassessed",
                    "real_researcher_project": "unqualified", "source_revision": identity["head_revision"],
                    "tested_revision": identity["revision"], "run_id": identity["run_id"], "run_attempt": identity["run_attempt"],
                    "slots": [list(slot) for slot in slot_names], "files": {name: self.pin(raw) for name, raw in sorted(contents.items())},
                    "entrypoint": "docs/researcher-alpha-quickstart.md", "review": "docs/researcher-alpha-review.md"}
        directory = output / "researcher-starter"
        directory.mkdir()
        for name, raw in contents.items():
            path = directory / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        (directory / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
        args = SimpleNamespace(sdk=sdk, release_candidate=candidate_path, output_dir=output, compare=slots)
        return directory, args, comparison, natives, source, catalog, manifest

    def audit(self, values):
        directory, args, comparison, natives, source, catalog, _ = values
        return auditor.audit_starter(directory, args, comparison, natives, source_root=source, audited_sources=catalog)

    def test_inert_handoff_matches_independent_complete_manifest(self):
        values = self.fixture()
        result = self.audit(values)
        self.assertEqual(result, values[-1])
        self.assertEqual(len(result["files"]), 21)
        self.assertEqual(result["release_acceptance"], "pending_overall_and_actual_main_gates")

    def test_self_rehashed_source_or_manifest_cannot_promote_authority(self):
        values = self.fixture()
        directory, _, _, _, source, catalog, manifest = values
        for field, replacement in (("status", "accepted"), ("empirical", "established"),
                                   ("release_acceptance", "complete"), ("real_researcher_project", "qualified")):
            changed = deepcopy(manifest)
            changed[field] = replacement
            (directory / "manifest.json").write_text(json.dumps(changed, sort_keys=True, indent=2) + "\n")
            with self.subTest(field=field), self.assertRaisesRegex(AssertionError, "manifest"):
                self.audit(values)
        (directory / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
        name = "docs/researcher-alpha-review.md"
        raw = (source / name).read_bytes()
        (source / name).write_bytes(raw + b"changed source")
        (directory / name).write_bytes(raw + b"changed source")
        changed = deepcopy(manifest)
        changed["files"][name] = self.pin(raw + b"changed source")
        (directory / "manifest.json").write_text(json.dumps(changed, sort_keys=True, indent=2) + "\n")
        with self.assertRaisesRegex(AssertionError, "authenticated catalog"):
            self.audit(values)
        self.assertEqual(catalog[name]["sha256"], self.pin(raw)["sha256"])

    def test_catalog_requires_every_document_and_exact_byte_blob_mode(self):
        values = self.fixture()
        catalog = values[-2]
        original = deepcopy(catalog)
        name = "docs/researcher-alpha-quickstart.md"
        for mutate in (lambda: catalog.pop(name), lambda: catalog[name].update(git_blob="0" * 40),
                       lambda: catalog[name].update(mode="100755"), lambda: catalog[name].update(size=True),
                       lambda: catalog.update({"../foreign": catalog[name]})):
            mutate()
            with self.assertRaises((AssertionError, ValueError)):
                self.audit(values)
            catalog.clear()
            catalog.update(deepcopy(original))

    def test_missing_extra_or_redirected_retained_contents_are_rejected(self):
        values = self.fixture()
        directory = values[0]
        path = directory / "docs/researcher-alpha-review.md"
        original = path.read_bytes()
        path.unlink()
        with self.assertRaisesRegex(AssertionError, "census"):
            self.audit(values)
        path.symlink_to(values[4] / "docs/researcher-alpha-review.md")
        with self.assertRaisesRegex(AssertionError, "Redirected"):
            self.audit(values)
        path.unlink()
        path.write_bytes(original)
        (directory / "extra").mkdir()
        with self.assertRaisesRegex(AssertionError, "Unexpected"):
            self.audit(values)

    def test_changed_example_and_child_cannot_self_authorize_after_comparison(self):
        values = self.fixture()
        evidence = values[1].compare[0] / "evidence"
        child_path = evidence / "researcher-alpha.json"
        child = json.loads(child_path.read_bytes())
        path = evidence / "researcher-alpha/staged.zip"
        path.write_bytes(b"a new artifact with fresh self hashes")
        child["files"]["researcher-alpha/staged.zip"] = self.pin(path.read_bytes(), child=True)
        child_path.write_text(json.dumps(child))
        with self.assertRaisesRegex(ValueError, "independent installed comparison"):
            self.audit(values)

    def test_original_authority_is_rechecked_after_plan(self):
        values = self.fixture()
        real_plan = self.starter.plan
        name = "docs/researcher-alpha-review.md"
        def changed_plan(*args, **kwargs):
            result = real_plan(*args, **kwargs)
            (values[4] / name).write_bytes(b"late source change")
            return result
        with patch.object(self.starter, "plan", side_effect=changed_plan), self.assertRaises(AssertionError):
            self.audit(values)

    def test_installed_profile_wrapper_rejects_missing_or_duplicate_slots(self):
        for directories in ([], [self.folder] * 4):
            with self.assertRaisesRegex(AssertionError, "Four distinct"):
                auditor.audit_installed_profiles(directories, None, None, {}, {}, audited_sources={})


if __name__ == "__main__":
    unittest.main()
