"""Transitive link boundaries fail closed on direct and indirect regressions."""

import contextlib
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

    def test_current_actual_dune_graph_has_separate_verifier_and_explicit_trusted_base(self):
        receipt = boundaries.check_boundaries(boundaries.ROOT)
        self.assertEqual(receipt["status"], "pass")
        dependencies = receipt["transitive_dependencies"]["executable:biocompiler-verify"]
        self.assertEqual(set(dependencies), {"bioc_wire", "bioc_domain", "bioc_checker", "bioc_service", "digestif", "zarith"})
        self.assertEqual(receipt["roles"]["bioc_checker"], "checker")
        self.assertEqual(receipt["roles"]["bioc_semantics"], "source_semantics")
        self.assertEqual(receipt["roles"]["bioc_source_adapter"], "source_semantics")
        self.assertEqual(receipt["roles"]["bioc_compiler"], "compiler")
        self.assertNotIn("bioc_compiler", dependencies)
        self.assertNotIn("bioc_producer_service", dependencies)
        self.assertEqual(receipt["roles"]["bioc_producer_service"], "producer")
        self.assertIn("bioc_compiler", receipt["transitive_dependencies"]["executable:biocompiler-core"])
        self.assertIn("bioc_checker", receipt["transitive_dependencies"]["bioc_compiler"])
        self.assertNotIn("bioc_semantics", dependencies)
        self.assertNotIn("bioc_source_adapter", dependencies)
        self.assertEqual(set(receipt["transitive_dependencies"]["bioc_semantics"]),
                         {"bioc_wire", "bioc_domain", "digestif", "zarith"})
        self.assertEqual(receipt["roles"]["bioc_candidate_runtime"], "candidate_runtime")
        self.assertEqual(set(receipt["transitive_dependencies"]["bioc_candidate_runtime"]),
                         {"bioc_wire", "bioc_domain", "digestif", "zarith"})
        self.assertNotIn("bioc_candidate_runtime", dependencies)
        self.assertEqual(receipt["shared_trusted_base"], ["bioc_wire", "bioc_domain"])
        self.assertIn("core/lib/checker/intent_check.ml", receipt["source_sha256"])
        self.assertEqual(receipt["native_build_and_semantic_independence"], "separate_hosted_validation_required")

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
            ("lib/service/dune", "bioc_wire bioc_domain bioc_checker", "bioc_wire bioc_domain bioc_checker unix"),
            ("bin/verify/dune", "bioc_wire bioc_service", "bioc_wire bioc_service bioc_domain"),
        ):
            root = self.copy_core()
            self.change(root, relative, before, after)
            with self.subTest(path=relative), self.assertRaises(boundaries.BoundaryError):
                boundaries.check_boundaries(root)

    def test_candidate_corpus_action_requires_the_complete_external_fixture(self):
        for variable in ("BIOCOMPILER_CANDIDATE_RUNTIME_CORPUS", "BIOCOMPILER_COMPONENT_RUNTIME_CORPUS"):
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
            self.change(root, "lib/checker/dune", "(private_modules construction_reconstruction architecture_reconstruction)", replacement)
            with self.subTest(replacement=replacement), self.assertRaisesRegex(boundaries.BoundaryError, "private module boundary"):
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
