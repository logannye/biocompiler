"""Transitive link boundaries fail closed on direct and indirect regressions."""

import contextlib
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tools import check_core_boundaries as boundaries


class CoreBoundaryTests(unittest.TestCase):
    def copy_core(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        shutil.copytree(boundaries.ROOT / "core", root / "core", ignore=shutil.ignore_patterns("_build"))
        return root

    def change(self, root, relative, before, after):
        path = root / "core" / relative
        content = path.read_text()
        self.assertIn(before, content)
        path.write_text(content.replace(before, after))

    def test_original_component_fixture_tool_is_private_and_domain_only(self):
        receipt = boundaries.check_boundaries(boundaries.ROOT)
        key = "test_tool:component_originals"
        self.assertEqual(receipt["roles"][key], "test_support")
        self.assertEqual(set(receipt["transitive_dependencies"][key]),
            {"bioc_wire", "bioc_domain", "bioc_policy_component_test_support", "digestif", "zarith"})
        for public in ("biocompiler-core", "biocompiler-verify"):
            self.assertNotIn(key, receipt["transitive_dependencies"]["executable:" + public])
        root = self.copy_core()
        path = root / "core/test/component_fixture_export/dune"
        original = path.read_text()
        for mutant in (
            original.replace("(name main)", "(name main) (public_name component-fixture)"),
            original.replace("(name main)", "(name changed)"),
            original.replace("bioc_domain", "bioc_domain bioc_compiler"),
            original.replace("bioc_policy_component_test_support", ""),
        ):
            with self.subTest(mutant=mutant):
                path.write_text(mutant)
                with self.assertRaises(boundaries.BoundaryError):
                    boundaries.check_boundaries(root)
        path.write_text(original)
        source = root / "core/test/component_fixture_export/main.ml"
        source.write_text(source.read_text() + "\nmodule Forbidden = Bioc_compiler.Policy_lowering\n")
        with self.assertRaisesRegex(boundaries.BoundaryError, "Undeclared local module dependency"):
            boundaries.check_boundaries(root)

    def test_current_actual_dune_graph_has_separate_verifier_and_explicit_trusted_base(self):
        receipt = boundaries.check_boundaries(boundaries.ROOT)
        self.assertEqual(receipt["status"], "pass")
        dependencies = receipt["transitive_dependencies"]["executable:biocompiler-verify"]
        self.assertEqual(set(dependencies), {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_service",
                                            "bioc_realization_checker", "bioc_semantics",
                                            "bioc_candidate_runtime", "digestif", "zarith", "unix"})
        self.assertEqual(receipt["roles"]["bioc_checker"], "checker")
        self.assertEqual(receipt["roles"]["bioc_policy_component_test_support"], "test_support")
        self.assertNotIn("bioc_policy_component_test_support", dependencies)
        self.assertNotIn("bioc_policy_component_test_support", receipt["transitive_dependencies"]["executable:biocompiler-core"])
        self.assertEqual(set(receipt["transitive_dependencies"]["bioc_policy_component_test_support"]),
                         {"bioc_wire", "bioc_domain", "digestif", "zarith"})
        self.assertEqual(receipt["private_modules"]["bioc_checker"],
                         ["construction_reconstruction", "architecture_reconstruction", "reference_check_support"])
        self.assertEqual(len(receipt["native_tests"]), 163)
        self.assertEqual(receipt["roles"]["bioc_semantics"], "source_semantics")
        self.assertEqual(receipt["roles"]["bioc_source_adapter"], "source_semantics")
        self.assertEqual(receipt["roles"]["bioc_compiler"], "compiler")
        self.assertNotIn("bioc_compiler", dependencies)
        self.assertNotIn("bioc_producer_service", dependencies)
        self.assertNotIn("bioc_pipeline_service", dependencies)
        self.assertEqual(receipt["roles"]["bioc_pipeline_service"], "producer")
        self.assertIn("bioc_pipeline_service", receipt["transitive_dependencies"]["executable:biocompiler-core"])
        self.assertIn("bioc_pipeline", receipt["transitive_dependencies"]["bioc_pipeline_service"])
        self.assertEqual(receipt["roles"]["bioc_producer_service"], "producer")
        self.assertIn("bioc_compiler", receipt["transitive_dependencies"]["executable:biocompiler-core"])
        self.assertIn("bioc_checker", receipt["transitive_dependencies"]["bioc_compiler"])
        self.assertIn("bioc_semantics", dependencies)
        self.assertNotIn("bioc_source_adapter", dependencies)
        self.assertEqual(set(receipt["transitive_dependencies"]["bioc_semantics"]),
                         {"bioc_wire", "bioc_domain", "digestif", "zarith"})
        self.assertEqual(receipt["roles"]["bioc_candidate_runtime"], "candidate_runtime")
        self.assertEqual(set(receipt["transitive_dependencies"]["bioc_candidate_runtime"]),
                         {"bioc_wire", "bioc_domain", "digestif", "zarith"})
        self.assertIn("bioc_candidate_runtime", dependencies)
        self.assertEqual(receipt["roles"]["bioc_realization_checker"], "checker")
        self.assertEqual(set(receipt["transitive_dependencies"]["bioc_realization_checker"]),
                         {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_semantics",
                          "bioc_candidate_runtime", "digestif", "zarith"})
        self.assertEqual(receipt["private_modules"]["bioc_realization_checker"], ["realization_monitor", "synthetic_provenance", "synthetic_component_authority"])
        self.assertIn("bioc_realization_checker", dependencies)
        self.assertEqual(receipt["roles"]["bioc_synthetic_producer"], "producer")
        self.assertNotIn("bioc_synthetic_producer", dependencies)
        self.assertIn("bioc_realization_checker", receipt["transitive_dependencies"]["bioc_synthetic_producer"])
        self.assertNotIn("bioc_synthetic_producer", receipt["transitive_dependencies"]["bioc_realization_checker"])
        self.assertEqual(receipt["roles"]["bioc_pipeline"], "compiler")
        self.assertNotIn("bioc_pipeline", dependencies)
        self.assertNotIn("bioc_pipeline", receipt["transitive_dependencies"]["bioc_compiler"])
        self.assertIn("bioc_compiler", receipt["transitive_dependencies"]["bioc_pipeline"])
        self.assertIn("bioc_synthetic_producer", receipt["transitive_dependencies"]["bioc_pipeline"])
        self.assertIn("bioc_realization_checker", receipt["transitive_dependencies"]["bioc_pipeline"])
        self.assertEqual(receipt["shared_trusted_base"], ["bioc_wire", "bioc_domain"])
        self.assertIn("core/lib/checker/intent_check.ml", receipt["source_sha256"])
        self.assertEqual(receipt["native_build_and_semantic_independence"], "separate_hosted_validation_required")

    def test_selection_suites_keep_exact_dependencies_and_original_fixture_arguments(self):
        receipt = boundaries.check_boundaries(boundaries.ROOT)
        expected = {
            "test_policy_component_selection_request": {"bioc_wire", "bioc_domain", "bioc_policy_component_test_support", "zarith"},
            "test_policy_component_material_candidate": {"bioc_wire", "bioc_domain", "bioc_policy_component_test_support"},
            "test_policy_component_selection_candidate": {"bioc_wire", "bioc_domain", "bioc_policy_component_test_support"},
            "test_policy_component_selection_common": {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_realization_checker", "bioc_policy_component_test_support"},
            "test_policy_component_selection_check": {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_realization_checker", "bioc_producer_service", "bioc_policy_component_test_support", "zarith"},
            "test_policy_component_selection_scope": {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_realization_checker", "bioc_producer_service", "bioc_policy_component_test_support"},
            "test_policy_component_selection_service": {"bioc_wire", "bioc_domain", "bioc_service", "bioc_producer_service", "bioc_policy_component_test_support", "unix"},
        }
        root = self.copy_core()
        dune = root / "core/test/dune"
        original = dune.read_text()
        for name, libraries in expected.items():
            self.assertEqual(set(receipt["native_tests"][name]), libraries)
            start = original.index("(test\n (name " + name + ")")
            end = original.index("\n\n", start)
            stanza = original[start:end]
            for changed in (stanza.replace("bioc_domain", "bioc_domain bioc_compiler"),
                            stanza.replace("%{dep:data/policy_material_request_v01.json}", "")):
                with self.subTest(suite=name, changed=changed):
                    dune.write_text(original[:start] + changed + original[end:])
                    with self.assertRaises(boundaries.BoundaryError):
                        boundaries.check_boundaries(root)
            dune.write_text(original)
            source = root / "core/test" / (name + ".ml")
            source_original = source.read_text()
            source.write_text(source_original + "\nmodule Forbidden = Bioc_compiler.Policy_lowering\n")
            with self.subTest(suite=name), self.assertRaisesRegex(boundaries.BoundaryError, "Undeclared local module dependency"):
                boundaries.check_boundaries(root)
            source.write_text(source_original)

    def test_archive_primitive_has_only_wire_and_public_resource_support(self):
        receipt = boundaries.check_boundaries(boundaries.ROOT)
        self.assertEqual(receipt["roles"]["bioc_artifact"], "trusted_primitive")
        self.assertEqual(set(receipt["libraries_and_executables"]["bioc_artifact"]),
                         {"bioc_wire", "bioc_checker", "zarith"})
        self.assertEqual(set(receipt["transitive_dependencies"]["bioc_artifact"]),
                         {"bioc_wire", "bioc_checker", "bioc_domain", "zarith", "digestif"})
        self.assertNotIn("bioc_artifact", receipt["transitive_dependencies"]["executable:biocompiler-verify"])
        self.assertEqual(set(receipt["native_tests"]["test_stored_zip"]),
                         {"bioc_wire", "bioc_checker", "bioc_artifact", "zarith"})
        for original, replacement in (("Bioc_checker.Work_budget", "Bioc_checker.Reference_construct_check"),
                                      ("Bioc_checker.Work_budget", "Bioc_checker")):
            root = self.copy_core()
            path = root / "core/lib/artifact/archive_budget.ml"
            source = path.read_text()
            self.assertIn(original, source)
            path.write_text(source.replace(original, replacement))
            with self.subTest(reference=replacement), self.assertRaisesRegex(
                    boundaries.BoundaryError, "only public checker Work_budget"):
                boundaries.check_boundaries(root)

    def test_reference_package_and_export_have_no_producer_dependencies(self):
        receipt = boundaries.check_boundaries(boundaries.ROOT)
        dependencies = {"bioc_wire", "bioc_domain", "bioc_artifact", "bioc_checker", "zarith", "digestif"}
        for name, role in (("bioc_reference_artifact", "domain"),
                           ("bioc_reference_export", "checker_service")):
            self.assertEqual(receipt["roles"][name], role)
            self.assertEqual(set(receipt["transitive_dependencies"][name]), dependencies)
            self.assertNotIn(name, receipt["transitive_dependencies"]["executable:biocompiler-core"])
            self.assertNotIn(name, receipt["transitive_dependencies"]["executable:biocompiler-verify"])
        self.assertNotIn("bioc_checker", receipt["libraries_and_executables"]["bioc_reference_artifact"])
        self.assertEqual(set(receipt["native_tests"]["test_reference_package_manifest"]),
                         {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_artifact", "bioc_reference_artifact", "zarith"})
        self.assertEqual(set(receipt["native_tests"]["test_reference_sequence_export"]),
                         {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_artifact", "bioc_reference_export", "zarith"})
        root = self.copy_core()
        path = root / "core/lib/reference_export/reference_sequence_export.ml"
        path.write_text(path.read_text() + "\nmodule Producer = Bioc_compiler.Reference_molecular_producer\n")
        with self.assertRaisesRegex(boundaries.BoundaryError, "Undeclared local module dependency"):
            boundaries.check_boundaries(root)

    def test_reference_package_reconstruction_is_a_producer_not_standalone_verify(self):
        receipt = boundaries.check_boundaries(boundaries.ROOT)
        name = "bioc_reference_package_service"
        self.assertEqual(receipt["roles"][name], "producer")
        for dependency in ("bioc_compiler", "bioc_pipeline", "bioc_reference_input",
                           "bioc_reference_artifact", "bioc_reference_export"):
            self.assertIn(dependency, receipt["transitive_dependencies"][name])
        for executable in ("biocompiler-core", "biocompiler-verify"):
            self.assertNotIn(name, receipt["transitive_dependencies"]["executable:" + executable])
        self.assertEqual(receipt["roles"]["bioc_reference_input"], "domain")
        self.assertEqual(set(receipt["transitive_dependencies"]["bioc_reference_input"]),
                         {"bioc_wire", "bioc_domain", "bioc_artifact", "bioc_checker", "zarith", "digestif"})
        # Reviewed checker roles must reject a transitive producer even through
        # an otherwise shared package library.
        graph = dict(receipt["libraries_and_executables"])
        graph["executable:biocompiler-verify"] = ["bioc_wire", name]
        with self.assertRaisesRegex(boundaries.BoundaryError, "transitively depends on a producer"):
            boundaries.validate_graph(graph, receipt["roles"])

    def test_reference_foundation_test_dependencies_and_private_support_are_exact(self):
        expected = {
            "test_legacy_json": {"bioc_wire"},
            "test_reference_domains": {"bioc_wire", "bioc_domain", "zarith"},
            "test_reference_checkers": {"bioc_wire", "bioc_domain", "bioc_checker", "zarith"},
            "test_reference_contracts_corpus": {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_compiler", "zarith"},
            "test_reference_producer_budget": {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_compiler", "zarith"},
            "test_reference_construct_pipeline": {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_compiler", "bioc_pipeline", "zarith"},
            "test_reference_molecular_pipeline": {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_compiler", "bioc_pipeline", "zarith"},
            "test_reference_workflow": {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_compiler", "bioc_pipeline", "bioc_pipeline_service", "zarith"},
    "test_reference_molecular_attempts": {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_compiler", "bioc_pipeline", "bioc_pipeline_service", "zarith"},
            "test_reference_callback_manager": {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_compiler", "bioc_pipeline_service", "zarith"},
        }
        receipt = boundaries.check_boundaries(boundaries.ROOT)
        for stem in ("reference_construct_pipeline", "reference_molecular_pipeline"):
            for relative in ("core/lib/pipeline/" + stem + ".ml", "core/lib/pipeline/" + stem + ".mli",
                             "core/test/test_" + stem + ".ml"):
                self.assertEqual(receipt["source_sha256"][relative],
                                 hashlib.sha256((boundaries.ROOT / relative).read_bytes()).hexdigest())
        for relative in ("core/lib/pipeline_service/reference_workflow.ml",
                         "core/lib/pipeline_service/reference_workflow.mli", "core/test/test_reference_workflow.ml",
                         "core/test/test_reference_callback_manager.ml"):
            self.assertEqual(receipt["source_sha256"][relative],
                             hashlib.sha256((boundaries.ROOT / relative).read_bytes()).hexdigest())
        for name, dependencies in expected.items():
            self.assertEqual(set(receipt["native_tests"][name]), dependencies)
            root = self.copy_core()
            path = root / "core/test/dune"
            source = path.read_text()
            start = source.index("(test\n (name " + name + ")")
            end = source.find("\n\n", start)
            end = len(source) if end < 0 else end
            stanza = source[start:end]
            path.write_text(source[:start] + stanza.replace("(libraries ", "(libraries bioc_service ", 1) + source[end:])
            with self.subTest(suite=name), self.assertRaisesRegex(boundaries.BoundaryError, "native test dependencies"):
                boundaries.check_boundaries(root)
        root = self.copy_core()
        self.change(root, "lib/checker/dune", " architecture_reconstruction reference_check_support)",
                    " architecture_reconstruction)")
        with self.assertRaisesRegex(boundaries.BoundaryError, "private module boundary"):
            boundaries.check_boundaries(root)

    def test_selection_runner_process_access_is_exactly_test_owned(self):
        owner = "test:test_policy_component_selection_service"
        source = boundaries.ROOT / "core/test/test_policy_component_selection_service.ml"
        boundaries.source_boundary(source, boundaries.TESTS[source.stem], owner=owner)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / source.name
            for text in ("let bad = Unix.system", "let bad = Unix.execv", "let bad = Unix.openfile",
                         "let bad = Sys.command", "let bad = Sys.getenv", "let bad = Dynlink.loadfile"):
                path.write_text(text)
                with self.subTest(text=text), self.assertRaises(boundaries.BoundaryError):
                    boundaries.source_boundary(path, set(), owner=owner)
            for module, member in (("Unix", "create_process_env"), ("Sys", "executable_name")):
                path.write_text("let reviewed = " + module + "." + member)
                boundaries.source_boundary(path, set(), owner=owner)
                for changed_owner in ("bioc_service", "bioc_realization_checker", "test:test_protocol"):
                    with self.subTest(owner=changed_owner, member=member), self.assertRaises(boundaries.BoundaryError):
                        boundaries.source_boundary(path, set(), owner=changed_owner)
                other = path.with_name("other.ml")
                other.write_text(path.read_text())
                with self.subTest(member=member), self.assertRaises(boundaries.BoundaryError):
                    boundaries.source_boundary(other, set(), owner=owner)

    def test_descriptor_primitive_cannot_expand_native_or_process_access(self):
        root = self.copy_core()
        self.change(root, "lib/service/artifact_fd_stubs.c", "F_GETFL", "F_GETFD")
        with self.assertRaisesRegex(boundaries.BoundaryError, "primitive source"):
            boundaries.check_boundaries(root)
        root = self.copy_core()
        self.change(root, "lib/service/artifact_io.ml", "Unix.fstat", "Unix.system")
        with self.assertRaisesRegex(boundaries.BoundaryError, "Unreviewed.*Unix"):
            boundaries.check_boundaries(root)
        root = self.copy_core()
        self.change(root, "lib/service/artifact_io.ml", "external duplicate_checked", "external unchecked")
        with self.assertRaisesRegex(boundaries.BoundaryError, "Unreviewed.*external"):
            boundaries.check_boundaries(root)
        root = self.copy_core()
        self.change(root, "lib/service/artifact_io.ml", boundaries.ARTIFACT_EXTERNAL,
                    boundaries.ARTIFACT_EXTERNAL + '\n "unreviewed_native_symbol"')
        with self.assertRaisesRegex(boundaries.BoundaryError, "Unreviewed.*external"):
            boundaries.check_boundaries(root)
        root = self.copy_core()
        (root / "core/lib/service/unreviewed.c").write_text("int unexpected;\n")
        with self.assertRaisesRegex(boundaries.BoundaryError, "source inventory"):
            boundaries.check_boundaries(root)

    def test_descriptor_test_conversion_is_exact_and_does_not_grant_production_access(self):
        declaration = boundaries.ARTIFACT_TEST_EXTERNAL
        for replacement in (declaration.replace("%identity", "unreviewed_symbol"),
                            declaration.replace("raw_fd_number", "other_number"),
                            declaration + '\nexternal another : unit -> int = "unreviewed"'):
            root = self.copy_core()
            self.change(root, "test/test_artifact_io.ml", declaration, replacement)
            with self.subTest(replacement=replacement), self.assertRaisesRegex(
                    boundaries.BoundaryError, "Unreviewed.*external"):
                boundaries.check_boundaries(root)
        root = self.copy_core()
        source = root / "core/lib/checker/intent_check.ml"
        source.write_text(source.read_text() + "\n" + declaration + "\n")
        with self.assertRaisesRegex(boundaries.BoundaryError, "Unreviewed.*external"):
            boundaries.check_boundaries(root)

    def test_transitive_producer_dependency_fails_even_through_neutral_module_names(self):
        graph = {"verify": ["adapter"], "adapter": ["worker"], "worker": []}
        for producer_role in sorted(boundaries.PRODUCER_ROLES):
            with self.subTest(role=producer_role), self.assertRaisesRegex(boundaries.BoundaryError, "transitively"):
                boundaries.validate_graph(graph, {"verify": "verifier", "adapter": "support", "worker": producer_role})
        with self.assertRaisesRegex(boundaries.BoundaryError, "transitively"):
            boundaries.validate_graph(graph, {"verify": "checker", "adapter": "support", "worker": "compiler"})

    def test_candidate_and_source_execution_cannot_depend_on_each_other_transitively(self):
        graph = {"candidate": ["adapter"], "adapter": ["source"], "source": []}
        with self.assertRaisesRegex(boundaries.BoundaryError, "source reference"):
            boundaries.validate_graph(graph, {"candidate": "candidate_runtime", "adapter": "support", "source": "source_semantics"})
        with self.assertRaisesRegex(boundaries.BoundaryError, "candidate execution"):
            boundaries.validate_graph(graph, {"candidate": "source_semantics", "adapter": "support", "source": "candidate_runtime"})
        independent = {"candidate": ["primitive"], "source": ["primitive"], "primitive": []}
        closure = boundaries.validate_graph(independent, {"candidate": "candidate_runtime", "source": "source_semantics", "primitive": "trusted_primitive"})
        self.assertEqual(closure["candidate"], ["primitive"])

    def test_candidate_execution_cannot_reach_producers_or_acceptance_authority(self):
        graph = {"candidate": ["adapter"], "adapter": ["authority"], "authority": []}
        for role in sorted(boundaries.PRODUCER_ROLES | {"checker", "checker_service", "verifier", "core_entrypoint"}):
            with self.subTest(role=role), self.assertRaisesRegex(boundaries.BoundaryError, "acceptance authority"):
                boundaries.validate_graph(graph, {"candidate": "candidate_runtime", "adapter": "support", "authority": role})

    def test_cycles_missing_roles_and_unknown_external_libraries_fail(self):
        cases = [({"a": ["b"], "b": ["a"]}, {"a": "support", "b": "support"}),
                 ({"a": []}, {}), ({"a": ["unexpected"]}, {"a": "support"})]
        for graph, roles in cases:
            with self.subTest(graph=graph), self.assertRaises(boundaries.BoundaryError):
                boundaries.validate_graph(graph, roles)

    def test_changed_direct_dependencies_cannot_bypass_the_reviewed_graph(self):
        for relative, before, after in (
            ("lib/checker/dune", "bioc_wire bioc_domain", "bioc_wire bioc_domain bioc_service"),
            ("lib/realization_checker/dune", "bioc_wire bioc_domain", "bioc_wire bioc_domain bioc_compiler"),
            ("lib/service/dune", "bioc_wire bioc_domain bioc_checker", "bioc_wire bioc_domain bioc_checker unix"),
            ("bin/verify/dune", "bioc_wire bioc_service", "bioc_wire bioc_service bioc_domain"),
        ):
            root = self.copy_core()
            self.change(root, relative, before, after)
            with self.subTest(path=relative), self.assertRaises(boundaries.BoundaryError):
                boundaries.check_boundaries(root)

    def test_candidate_corpus_action_requires_the_complete_external_fixture(self):
        for variable in ("BIOCOMPILER_CANDIDATE_RUNTIME_CORPUS", "BIOCOMPILER_COMPONENT_RUNTIME_CORPUS",
                         "BIOCOMPILER_REALIZATION_FOUNDATION_CORPUS", "BIOCOMPILER_REALIZATION_CHECKS_CORPUS",
                         "BIOCOMPILER_COMPONENT_ACCEPTANCE_CORPUS", "BIOCOMPILER_REFERENCE_CONTRACTS_DOCUMENTS",
                         "BIOCOMPILER_REFERENCE_CONTRACTS_CORPUS", "BIOCOMPILER_REFERENCE_PIPELINE_DOCUMENTS"):
            action = "(action (run %{test} %{env:" + variable + "=missing}))"
            for replacement in ("", "(action (run true))", action + "\n " + action):
                root = self.copy_core()
                self.change(root, "test/dune", action, replacement)
                with self.subTest(variable=variable, replacement=replacement), self.assertRaisesRegex(
                        boundaries.BoundaryError, "Changed native test action"):
                    boundaries.check_boundaries(root)

    def test_new_library_missing_checker_and_implicit_transitive_dependencies_fail(self):
        root = self.copy_core()
        added = root / "core/lib/hidden/dune"
        added.parent.mkdir()
        added.write_text("(library (name hidden) (libraries bioc_wire))")
        with self.assertRaisesRegex(boundaries.BoundaryError, "Unreviewed Dune library"):
            boundaries.check_boundaries(root)
        root = self.copy_core()
        (root / "core/lib/checker/dune").unlink()
        with self.assertRaisesRegex(boundaries.BoundaryError, "Missing reviewed"):
            boundaries.check_boundaries(root)
        root = self.copy_core()
        self.change(root, "dune-project", "(implicit_transitive_deps false)", "(implicit_transitive_deps true)")
        with self.assertRaisesRegex(boundaries.BoundaryError, "implicit_transitive_deps"):
            boundaries.check_boundaries(root)

    def test_generation_foreign_code_preprocessors_and_dynamic_libraries_need_review(self):
        extras = ["(include generated.dune)", "(rule (target injected.ml) (action (copy hidden.ml injected.ml)))",
                  "(library (name bioc_wire) (libraries digestif zarith) (foreign_stubs (language c) (names hidden)))",
                  "(library (name bioc_wire) (libraries digestif zarith) (preprocess (pps hidden)))",
                  "(library (name bioc_wire) (libraries (:include hidden.sexp)))",
                  "(library (name bioc_wire) (libraries %{read:dependencies}))"]
        for extra in extras:
            root = self.copy_core()
            (root / "core/lib/wire/dune").write_text(extra)
            with self.subTest(extra=extra), self.assertRaises(boundaries.BoundaryError):
                boundaries.check_boundaries(root)

    def test_source_escape_hatches_and_undeclared_modules_fail(self):
        mutants = ['let hidden = Sys.command "python3 checker.py"', "module Hidden = Sys",
                   "external hidden : unit -> unit = \"hidden\"", "let hidden = Obj.magic 1",
                   "let hidden = Dynlink.loadfile", "let hidden = Unix.system", "open Bioc_hidden"]
        for mutant in mutants:
            root = self.copy_core()
            source = root / "core/lib/checker/intent_check.ml"
            source.write_text(source.read_text() + "\n" + mutant + "\n")
            with self.subTest(mutant=mutant), self.assertRaises(boundaries.BoundaryError):
                boundaries.check_boundaries(root)

    def test_private_reconstruction_stays_inside_checker_and_out_of_public_interfaces(self):
        for relative, mutant in (
            ("lib/compiler/lowering.ml", "module Hidden = Bioc_checker.Construction_reconstruction"),
            ("lib/compiler/lowering.ml", "open Bioc_checker\nmodule Hidden = Construction_reconstruction"),
            ("lib/checker/intent_check.mli", "module Hidden = Construction_reconstruction"),
            ("lib/checker/intent_check.mli", "val hidden : Construction_reconstruction.t"),
            ("lib/compiler/lowering.ml", "module Hidden = Bioc_checker.Architecture_reconstruction"),
            ("lib/checker/intent_check.mli", "val hidden : Architecture_reconstruction.graph"),
            ("lib/compiler/lowering.ml", "module Hidden = Bioc_checker.Reference_check_support"),
            ("lib/checker/intent_check.mli", "val hidden : Reference_check_support.t"),
            ("test/test_synthetic_candidate_check.ml", "module Hidden = Bioc_realization_checker.Synthetic_provenance"),
            ("test/test_synthetic_candidate_check.ml", "module Hidden = Bioc_realization_checker.Synthetic_component_authority"),
            ("lib/realization_checker/synthetic_candidate_check.mli", "val hidden : Synthetic_provenance.t"),
            ("lib/realization_checker/component_assembly_check.mli", "val hidden : Synthetic_component_authority.t"),
            ("lib/synthetic_producer/generator.ml", "module Hidden = Bioc_realization_checker.Synthetic_provenance"),
            ("lib/synthetic_producer/components.ml", "module Hidden = Bioc_realization_checker.Synthetic_component_authority"),
        ):
            root = self.copy_core()
            source = root / "core" / relative
            source.write_text(source.read_text() + "\n" + mutant + "\n")
            with self.subTest(path=relative, mutant=mutant), self.assertRaisesRegex(boundaries.BoundaryError, "Private checker reconstruction"):
                boundaries.check_boundaries(root)

    def test_corpus_directory_inventory_does_not_grant_production_sys_access(self):
        for relative, mutant in (
            ("lib/checker/intent_check.ml", 'let hidden = Sys.readdir "."'),
            ("test/test_architecture_check.ml", 'let hidden = Sys.command "python3 checker.py"'),
            ("test/test_architecture_check.ml", "module Hidden = Sys"),
            ("lib/source_adapter/source_transport.ml", 'let hidden = Sys.readdir "."'),
            ("test/test_source_transport.ml", 'let hidden = Sys.command "python3 checker.py"'),
            ("test/test_source_transport.ml", "module Hidden = Sys"),
            ("test/test_realization_foundation_corpus.ml", 'let hidden = Sys.command "python3 checker.py"'),
            ("test/test_realization_foundation_corpus.ml", "module Hidden = Sys"),
            ("test/test_reference_contracts_corpus.ml", 'let hidden = Sys.command "python3 checker.py"'),
            ("test/test_reference_contracts_corpus.ml", "module Hidden = Sys"),
            ("lib/checker/reference_check_support.ml", 'let hidden = Sys.readdir "."'),
        ):
            root = self.copy_core()
            source = root / "core" / relative
            source.write_text(source.read_text() + "\n" + mutant + "\n")
            with self.subTest(path=relative, mutant=mutant), self.assertRaisesRegex(boundaries.BoundaryError, "Unreviewed Sys access"):
                boundaries.check_boundaries(root)

    def test_private_module_declaration_cannot_be_removed_or_expanded(self):
        for replacement in ("", "(private_modules construction_reconstruction intent_check)",
                            "(private_modules intent_check)"):
            root = self.copy_core()
            self.change(root, "lib/checker/dune", "(private_modules construction_reconstruction architecture_reconstruction reference_check_support)", replacement)
            with self.subTest(replacement=replacement), self.assertRaisesRegex(boundaries.BoundaryError, "private module boundary"):
                boundaries.check_boundaries(root)
        for removed in ("synthetic_provenance", "synthetic_component_authority"):
            root = self.copy_core()
            declaration = "(private_modules realization_monitor synthetic_provenance synthetic_component_authority)"
            self.change(root, "lib/realization_checker/dune", declaration, declaration.replace(" " + removed, ""))
            with self.subTest(removed=removed), self.assertRaisesRegex(boundaries.BoundaryError, "private module boundary"):
                boundaries.check_boundaries(root)
        root = self.copy_core()
        (root / "core/lib/checker/construction_reconstruction.mli").unlink()
        with self.assertRaisesRegex(boundaries.BoundaryError, "explicit implementation and interface"):
            boundaries.check_boundaries(root)

    def test_comments_strings_and_character_literals_do_not_create_false_dependencies(self):
        root = self.copy_core()
        source = root / "core/lib/checker/intent_check.ml"
        source.write_text(source.read_text() + '''
(* Sys.command (* external *) Bioc_hidden *)
let _example = "Sys.command external Bioc_hidden"
let _quoted = {example|Unix.system Dynlink.loadfile|example}
let _character = 'x'
''')
        self.assertEqual(boundaries.check_boundaries(root)["status"], "pass")

    def test_orphan_source_files_and_duplicate_stanzas_fail(self):
        root = self.copy_core()
        orphan = root / "core/orphan.ml"
        orphan.write_text("let hidden = 1")
        with self.assertRaisesRegex(boundaries.BoundaryError, "no reviewed Dune owner"):
            boundaries.check_boundaries(root)
        root = self.copy_core()
        dune = root / "core/lib/checker/dune"
        dune.write_text(dune.read_text() * 2)
        with self.assertRaisesRegex(boundaries.BoundaryError, "duplicate"):
            boundaries.check_boundaries(root)

    def test_static_receipt_is_reproducible_and_cli_fails_without_rewriting_receipt(self):
        root = self.copy_core()
        output = root / "receipt.json"
        args = ["--root", str(root), "--output", str(output)]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(boundaries.main(args), 0)
            first = output.read_bytes()
            self.assertEqual(boundaries.main(args), 0)
            self.assertEqual(first, output.read_bytes())
            self.assertEqual(json.loads(first)["status"], "pass")
            self.change(root, "lib/checker/dune", "bioc_wire bioc_domain", "bioc_wire bioc_domain unix")
            self.assertEqual(boundaries.main(args), 1)
            self.assertEqual(first, output.read_bytes())

    def test_dune_parser_rejects_unbalanced_duplicate_and_dynamic_fields(self):
        for text in ("(library", ")", "bare", "()"):
            with self.subTest(text=text), self.assertRaises(boundaries.BoundaryError):
                boundaries.sexps(text)
        self.assertEqual(boundaries.sexps('; ignored\n(library (name "sample"))'), [["library", ["name", "sample"]]])
        for stanza in (["library", ["name", "a"], ["name", "a"]], ["library", ["libraries", "%{read:libs}"]]):
            with self.subTest(stanza=stanza), self.assertRaises(boundaries.BoundaryError):
                boundaries.fields(stanza, {"name", "libraries"})


if __name__ == "__main__":
    unittest.main()
