"""Every Dune fixture argument must receive a real path in the hosted suite."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import re
import tempfile
import unittest
from unittest.mock import patch

from tools import ci_native_bundle as bundle


DIRECTORY_FIXTURES = {
    "BIOCOMPILER_REFERENCE_CONTRACTS_DOCUMENTS": "tests/conformance/reference-contracts-v1",
    "BIOCOMPILER_REFERENCE_PIPELINE_DOCUMENTS": "tests/conformance/reference-pipeline-semantics-v1",
}

# Reviewed source-order/argv projection of core/test/dune at
# 4e20816141d5d28ea5e921a069078b86be64de2d. Neither the current runner nor a
# regenerated current census supplies this historical expected fingerprint.
BASELINE_PLAN_SHA256 = "d1fd1cc1134c7bb5091282b0d7a8e9e67e106c7a8b9b6146080cb1a7d2ecd164"
ADDED_DEPENDENCIES = {
    "test_policy_staged_primitives": ["data/policy_implementation_v01.json"],
    "test_policy_component_selection_candidate": ["data/policy_material_request_v01.json"],
    "test_policy_component_selection_common": ["data/policy_material_request_v01.json", "data/policy_material_state_v01.json"],
    "test_policy_component_selection_check": ["data/policy_material_request_v01.json"],
    "test_policy_component_selection_scope": ["data/policy_material_request_v01.json"],
    "test_policy_component_selection_service": ["data/policy_material_request_v01.json"],
    "test_policy_component_selection_producer": ["data/policy_material_request_v01.json"],
    "test_policy_generation_admission": ["data/policy_implementation_binding_v01.json"],
    "test_policy_generation_producers": ["data/policy_material_request_v01.json", "data/policy_material_state_v01.json"],
    "test_policy_staged_regimen_source": ["data/policy_staged_regimen_source_v01.json"],
    "test_policy_staged_binding": ["data/policy_staged_realization_request_v01.json"],
    "test_policy_staged_component_material": ["data/policy_staged_material_v01.json"],
    "test_policy_staged_generation": ["data/policy_staged_realization_request_v01.json"],
    "test_policy_instance_assembly_rule": ["data/policy_material_request_v01.json", "data/policy_material_state_v01.json"],
    "test_policy_instance_material_service": ["data/policy_material_request_v01.json", "data/policy_material_state_v01.json"],
    "test_policy_provider_prerequisites": ["data/policy_material_request_v01.json", "data/policy_material_state_v01.json"],
    "test_policy_prerequisite_material_service": ["data/policy_material_request_v01.json", "data/policy_material_state_v01.json"],
    "test_policy_two_observation_material_service": ["data/policy_material_request_v01.json", "data/policy_material_state_v01.json"],
    "test_policy_multi_member_material_service": ["data/policy_staged_material_v01.json"],
    "test_policy_grounded_helper_material_service": ["data/policy_staged_material_v01.json"],
    "test_policy_candidate_congruence_check": ["data/policy_implementation_binding_v01.json"],
    "test_policy_candidate_transition_congruence": ["data/policy_primitives_v01.json"],
    "test_policy_admitted_ir": ["data/policy_operational_v01.json", "data/policy_staged_regimen_source_v01.json", "data/policy_implementation_binding_v01.json"],
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

    def declared_suites(self, dune):
        # Independently retain the complete source order and every argv occurrence;
        # deriving expectations from bundle.test_plan would hide its omissions.
        stanzas = [row for row in re.split(r"(?m)(?=^\(test\b)", dune) if row.strip()]
        declared = []
        for stanza in stanzas:
            names = re.findall(r"\(name (test_[a-z0-9_]+)\)", stanza)
            self.assertEqual(len(names), 1, "expected one named Dune test per stanza")
            row = {"name": names[0], "environment": re.findall(
                r"%\{env:(BIOCOMPILER_[A-Z0-9_]+)=missing\}", stanza)}
            dependencies = re.findall(r"%\{dep:(data/[a-z0-9_]+\.json)\}", stanza)
            if dependencies:
                self.assertFalse(row["environment"], "mixed fixture forms are not reviewed")
                row["dependencies"] = dependencies
            declared.append(row)
        self.assertEqual(len(declared), len({row["name"] for row in declared}), "duplicate Dune suite")
        return declared

    def assert_reviewed_census(self, declared):
        self.assertEqual(len(declared), 181, "complete union native suite census changed")
        self.assertEqual(sum("dependencies" in row for row in declared), 63)
        added = [row for row in declared if row["name"] in ADDED_DEPENDENCIES]
        self.assertEqual(added, [{"name": name, "environment": [], "dependencies": dependencies}
                                for name, dependencies in ADDED_DEPENDENCIES.items()],
                         "reviewed additive suite names, order or fixture argv changed")
        baseline = [row for row in declared if row["name"] not in ADDED_DEPENDENCIES]
        self.assertEqual(len(baseline), 158)
        self.assertEqual(sum("dependencies" in row for row in baseline), 40)
        encoded = json.dumps(baseline, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest(), BASELINE_PLAN_SHA256,
                         "historical native suite names, source order or fixture argv changed")

    def assert_native_suite_wiring(self, root, dune, workflow):
        required = set(re.findall(r"%\{env:(BIOCOMPILER_[A-Z0-9_]+)=missing\}", dune))
        self.assertTrue(required)
        self.assertLessEqual({"BIOCOMPILER_ARCHIVE_PYTHON311_CORPUS", "BIOCOMPILER_ARCHIVE_PYTHON314_CORPUS"}, required)
        self.assertLessEqual({"BIOCOMPILER_REFERENCE_PACKAGE_PYTHON311_CORPUS", "BIOCOMPILER_REFERENCE_PACKAGE_PYTHON314_CORPUS",
                              "BIOCOMPILER_REFERENCE_SEQUENCE_EXPORT_CORPUS"}, required)
        suite = workflow.split("      - name: Run every native literal and mutation suite\n", 1)[1]
        suite = suite.split("\n      - name:", 1)[0]
        bindings = re.findall(r'(BIOCOMPILER_[A-Z0-9_]+)="\$GITHUB_WORKSPACE/([^"\n]+)"', suite)
        self.assertEqual(len(bindings), len(dict(bindings)), "duplicate fixture bindings")
        self.assertEqual(set(dict(bindings)), required, "Dune fixture arguments and CI environment differ")
        for name, relative_path in bindings:
            with self.subTest(variable=name):
                self.assert_fixture_path(root, name, relative_path)
        runner = "python tools/ci_native_bundle.py test --path generated/core/native-suites --workers 2"
        self.assertEqual(suite.count(runner), 1, "complete bounded native runner must execute once")
        self.assertIn("set -o pipefail", suite)
        jobs = {match[1]: match[2] for match in re.finditer(
            r"^  ([a-z][a-z0-9-]*):\n(.*?)(?=^  [a-z][a-z0-9-]*:\n|\Z)", workflow, re.M | re.S)}
        native = jobs["ocaml-native-tests"]
        self.assertIn(suite, native)
        self.assertIn("needs: ocaml-build", native)
        restore = "python tools/ci_native_bundle.py restore --path artifacts/native-bundle/native.zip"
        self.assertEqual(native.count(restore), 1)
        self.assertLess(native.index(restore), native.index(runner))
        self.assertIn("name: native-bundle-${{ matrix.platform }}", native)
        build = jobs["ocaml-build"]
        self.assertIn("opam exec -- dune build --root core @all", build)
        self.assertIn("python tools/ci_native_bundle.py bundle --path generated/native-bundle/native.zip", build)
        self.assertIn("name: native-bundle-${{ matrix.platform }}", build)
        declared = self.declared_suites(dune)
        self.assert_reviewed_census(declared)
        self.assertEqual(bundle.test_plan(dune), declared, "runner changed a Dune suite or ordered fixture argv")
        for row in declared:
            for relative in row.get("dependencies", []):
                self.assert_fixture_path(root, row["name"], "core/test/" + relative)
        self.assertEqual(bundle.expected_members(root), {
            "core/_build/default/bin/core/main.exe", "core/_build/default/bin/verify/main.exe",
            "core/_build/default/test/component_fixture_export/main.exe",
            "core/_build/default/test/instance_fixture_export/main.exe",
            "core/_build/default/test/prerequisite_fixture_export/main.exe",
            "core/_build/default/test/two_observation_fixture_export/main.exe",
            "core/_build/default/test/multi_member_fixture_export/main.exe",
            "core/_build/default/test/grounded_helper_fixture_export/main.exe",
            *("core/_build/default/test/" + row["name"] + ".exe" for row in declared),
            *("core/_build/default/test/" + relative for row in declared for relative in row.get("dependencies", []))},
            "compiled bundle omitted or added a native executable or source dependency fixture")
        members = bundle.expected_members(root)
        self.assertEqual(len(members), 215)
        self.assertEqual(sum(path.endswith(".exe") for path in members), 189)
        return declared, dict(bindings)

    def test_reviewed_baseline_projection_rejects_changes_despite_same_total(self):
        root = Path(__file__).resolve().parents[1]
        declared = self.declared_suites((root / "core/test/dune").read_text())
        self.assert_reviewed_census(declared)
        original = next(index for index, row in enumerate(declared)
                        if row["name"] not in ADDED_DEPENDENCIES and "dependencies" in row)
        added = next(index for index, row in enumerate(declared) if row["name"] in ADDED_DEPENDENCIES)
        for index in (original, added):
            changed = json.loads(json.dumps(declared))
            changed[index]["dependencies"][0] = "data/policy_unreviewed.json"
            with self.subTest(index=index), self.assertRaises(AssertionError):
                self.assert_reviewed_census(changed)
        changed = json.loads(json.dumps(declared))
        changed[0], changed[1] = changed[1], changed[0]
        with self.assertRaisesRegex(AssertionError, "historical"):
            self.assert_reviewed_census(changed)

    def test_every_dune_fixture_is_bound_in_the_complete_native_suite(self):
        root = Path(__file__).resolve().parents[1]
        self.assert_native_suite_wiring(root, (root / "core/test/dune").read_text(),
                                       (root / ".github/workflows/ci.yml").read_text())

    def test_bundled_runner_executes_every_original_suite_and_ordered_fixture_argument(self):
        root = Path(__file__).resolve().parents[1]
        dune = (root / "core/test/dune").read_text()
        declared, bindings = self.assert_native_suite_wiring(root, dune, (root / ".github/workflows/ci.yml").read_text())
        with tempfile.TemporaryDirectory() as directory:
            inert = Path(directory).resolve()
            (inert / "core/test").mkdir(parents=True)
            (inert / "core/test/dune").write_text(dune)
            expected = {}
            for row in declared:
                executable = inert / "core/_build/default/test" / (row["name"] + ".exe")
                executable.parent.mkdir(parents=True, exist_ok=True)
                executable.write_bytes(b"INERT: subprocess is mocked; never executable")
                expected[row["name"]] = [str(executable), *(
                    str(root / bindings[name]) for name in row["environment"]), *(
                    str(inert / "core/_build/default/test" / relative) for relative in row.get("dependencies", []))]
                for relative in row.get("dependencies", []):
                    raw = (root / "core/test" / relative).read_bytes()
                    for base in ("core/test", "core/_build/default/test"):
                        path = inert / base / relative
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_bytes(raw)
            observed = []
            def execute(command, **kwargs):
                observed.append(command)
                self.assertEqual(kwargs["cwd"], inert / "core/_build/default/test")
                kwargs["stdout"].write(b"inert scheduling observation\n")
                return subprocess.CompletedProcess(command, 0)
            environment = {name: str(root / path) for name, path in bindings.items()}
            with patch.dict(os.environ, environment, clear=True), \
                    patch.object(bundle.subprocess, "run", side_effect=execute), \
                    patch.object(bundle.ci, "identity", return_value={"revision": "a" * 40, "run_id": "123", "run_attempt": "1"}):
                bundle.run_tests(inert, inert / "receipt", 2)
            self.assertEqual(len(observed), len(expected), "missing or repeated native execution")
            self.assertEqual({Path(argv[0]).stem: argv for argv in observed}, expected)
            receipt = json.loads((inert / "receipt/receipt.json").read_bytes())
            self.assertEqual(receipt["expected"], [row["name"] for row in declared])
            self.assertEqual([(row["name"], row["argv"], row["returncode"]) for row in receipt["tests"]],
                             [(row["name"], expected[row["name"]], 0) for row in declared])
            missing = next(iter(bindings))
            with patch.dict(os.environ, {key: value for key, value in environment.items() if key != missing}, clear=True), \
                    patch.object(bundle.subprocess, "run", side_effect=AssertionError("unbound fixture reached a child")) as child:
                with self.assertRaisesRegex(ValueError, "Missing required native fixture"):
                    bundle.run_tests(inert, inert / "missing-fixture", 2)
                child.assert_not_called()

    def test_missing_duplicate_or_unbound_workflow_fixtures_and_runner_are_rejected(self):
        root = Path(__file__).resolve().parents[1]
        dune = (root / "core/test/dune").read_text()
        workflow = (root / ".github/workflows/ci.yml").read_text()
        binding = next(line for line in workflow.splitlines(keepends=True)
                       if 'BIOCOMPILER_ARCHIVE_PYTHON311_CORPUS="$GITHUB_WORKSPACE/' in line)
        mutations = {
            "missing": workflow.replace(binding, "", 1),
            "duplicate": workflow.replace(binding, binding + binding, 1),
            "unbound": workflow.replace("BIOCOMPILER_ARCHIVE_PYTHON311_CORPUS=", "BIOCOMPILER_UNDECLARED_CORPUS=", 1),
            "runner": workflow.replace("python tools/ci_native_bundle.py test --path generated/core/native-suites --workers 2", "python -c pass", 1),
        }
        for name, changed in mutations.items():
            with self.subTest(mutation=name), self.assertRaises(AssertionError):
                self.assert_native_suite_wiring(root, dune, changed)

    def test_missing_duplicate_or_reordered_runner_suite_arguments_are_rejected(self):
        root = Path(__file__).resolve().parents[1]
        dune = (root / "core/test/dune").read_text()
        workflow = (root / ".github/workflows/ci.yml").read_text()
        declared = self.declared_suites(dune)
        reordered = [{**row, "environment": list(reversed(row["environment"]))} for row in declared]
        dependency_reordered = [{**row, "dependencies":list(reversed(row["dependencies"]))} if "dependencies" in row
                                else row for row in declared]
        self.assertNotEqual(reordered, declared, "mutation requires an original multi-argument suite")
        self.assertNotEqual(dependency_reordered, declared, "mutation requires an original multi-dependency suite")
        for name, changed in (("missing", declared[1:]), ("duplicate", declared + declared[:1]),
                              ("argv", reordered), ("dependency-argv", dependency_reordered)):
            with self.subTest(mutation=name), patch.object(bundle, "test_plan", return_value=changed), self.assertRaises(AssertionError):
                self.assert_native_suite_wiring(root, dune, workflow)


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
