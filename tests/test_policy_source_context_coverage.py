"""Inert source/index drift adversaries; never execute therapeutic semantics."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from tools import check_policy_source_context_coverage as coverage


class PolicySourceContextCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = coverage.decode(coverage.read(coverage.ROOT, coverage.LEDGER))

    def setUp(self):
        self.ledger = deepcopy(self.original)

    def reject(self, mutate, message):
        mutate(self.ledger)
        with self.assertRaisesRegex(coverage.CoverageError, message):
            coverage.check(coverage.ROOT, self.ledger)

    def checkout(self):
        directory = tempfile.TemporaryDirectory(prefix="policy-source-context-")
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        names = set(coverage.SOURCE_PINS) | set(coverage.INPUT_PINS)
        names |= {coverage.SYNTAX_LEDGER, coverage.FAMILY_LEDGER, coverage.LEDGER}
        for name in names:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(coverage.ROOT / name, target)
        return root

    def edit(self, root, name, before, after, repin_ast=False):
        path = root / name
        text = path.read_text()
        self.assertIn(before, text)
        path.write_text(text.replace(before, after, 1))
        row = next(row for row in self.ledger["sources"] if row["path"] == name)
        row["sha256"] = coverage.digest(path.read_bytes())
        if repin_ast:
            row["ast"] = coverage.ast_closure(path.read_bytes(), name)

    def test_current_bounded_slice_leaves_full_census_and_semantics_open(self):
        result = coverage.check()
        self.assertEqual((result["rules"], result["contexts"], result["sources"]), (40, 43, 15))
        self.assertEqual((result["syntax_rows"], result["families"]), (612, 62))
        self.assertEqual(result["status"], "source_slice_current")
        self.assertEqual(result["whole_source_census"], "open")
        self.assertEqual(result["whole_stack_census"], "open")
        self.assertEqual(result["witness_sufficiency"], "not_assessed")
        self.assertEqual(result["semantic_proof"], "not_established")
        self.assertEqual(result["native_execution"], "not_performed")

    def test_metering_reanchor_preserves_all_previous_reviewed_declarations(self):
        # Only file dependencies, review metadata and native line locations
        # changed. Restore those exact reviewed differences, then require the
        # original digest of all predicates, contexts, provenance and open gaps.
        # No source hash, current helper or regenerated expected result supplies
        # the historical expected value.
        projected = deepcopy(self.original)
        added = {"core/lib/checker/policy_generation_meter.ml",
                 "core/lib/checker/policy_generation_meter.mli"}
        dependencies = [row for row in projected["sources"] if row["path"] in added]
        self.assertEqual({row["path"] for row in dependencies}, added)
        self.assertTrue(all(row["disposition"] == "shared_metering_dependency"
                            and row["ast"] is None for row in dependencies))
        projected["sources"] = [row for row in projected["sources"] if row["path"] not in added]
        projected["reviewed_source"] = {
            "head": "a85b1112ff35ba988a71cc969bfabdfefb354cfe",
            "tree": "7d22ca4c27eafcd36f018b3f262ef87404a3caf6",
            "source_note": "Production source unchanged at this review; witness-only follow-ups do not transfer hosted evidence.",
        }
        offsets = set()
        for group in ("rules", "contexts"):
            for row in projected[group]:
                for owner in row["owners"]:
                    if owner["path"] == "core/lib/checker/policy_check.ml":
                        first, last = owner["first_line"], owner["last_line"]
                        # The functor/import block shifts the first two regions
                        # seven lines; the added spend callback shifts later
                        # regions one more. Every region body is unchanged.
                        if (first, last) in {(28, 28), (29, 34)}:
                            offset = 7
                        else:
                            self.assertGreaterEqual(first, 69)
                            offset = 8
                        offsets.add(offset)
                        owner["first_line"] -= offset
                        owner["last_line"] -= offset
        self.assertEqual(offsets, {7, 8})
        self.assertEqual(coverage.digest(coverage.canonical(coverage.declarations(projected))),
                         "669803616f63fae728494cf781fad87d04ee51e039b4b99d3f1c667a4118d37c")

    def test_metering_dependency_cannot_be_omitted_or_self_repinned(self):
        for suffix in ("ml", "mli"):
            name = "core/lib/checker/policy_generation_meter." + suffix
            with self.subTest(suffix=suffix):
                self.ledger = deepcopy(self.original)
                self.reject(lambda value: value.update(sources=[row for row in value["sources"]
                                                               if row["path"] != name]), "closed source paths")
                self.ledger = deepcopy(self.original)
                root = self.checkout()
                path = root / name
                path.write_bytes(path.read_bytes() + b"\n(* unreviewed dependency change *)\n")
                row = next(row for row in self.ledger["sources"] if row["path"] == name)
                row["sha256"] = coverage.digest(path.read_bytes())
                with self.assertRaisesRegex(coverage.CoverageError, "Unreviewed complete source pin"):
                    coverage.check(root, self.ledger)

    def test_rules_are_closed_including_duplicates_and_reordering(self):
        for mutation in (lambda rows: rows.pop(), lambda rows: rows.append(deepcopy(rows[0])),
                         lambda rows: rows.reverse(), lambda rows: rows[0].update(id="source.new")):
            with self.subTest(mutation=mutation):
                self.ledger = deepcopy(self.original)
                self.reject(lambda value: mutation(value["rules"]), "closed rule IDs")

    def test_contexts_are_closed_including_duplicates_and_reordering(self):
        for mutation in (lambda rows: rows.pop(), lambda rows: rows.append(deepcopy(rows[0])),
                         lambda rows: rows.reverse(), lambda rows: rows[0].update(id="source.context.new")):
            with self.subTest(mutation=mutation):
                self.ledger = deepcopy(self.original)
                self.reject(lambda value: mutation(value["contexts"]), "closed context IDs")

    def test_removed_or_invented_source_dependency_is_rejected(self):
        for mutate in (lambda value: value["sources"].pop(),
                       lambda value: value["sources"].append(deepcopy(value["sources"][0]))):
            self.ledger = deepcopy(self.original)
            self.reject(mutate, "closed source paths")

    def test_source_hash_change_requires_review_before_interpretation(self):
        root = self.checkout()
        path = root / "src/biocompiler/policy/validation.py"
        path.write_text(path.read_text() + "\n# unreviewed\n")
        with self.assertRaisesRegex(coverage.CoverageError, "Stale source hash"):
            coverage.check(root, self.ledger)

    def test_repinned_caller_flag_is_rejected(self):
        root = self.checkout()
        self.edit(root, "src/biocompiler/policy/validation.py", "owner, positive=False)", "owner, positive=True)")
        with self.assertRaisesRegex(coverage.CoverageError, "Changed Python AST/caller closure"):
            coverage.check(root, self.ledger)

    def test_repinned_caller_path_is_rejected(self):
        root = self.checkout()
        self.edit(root, "src/biocompiler/policy/validation.py", 'path + "/freshness"', 'path + "/wrong_freshness"')
        with self.assertRaisesRegex(coverage.CoverageError, "Changed Python AST/caller closure"):
            coverage.check(root, self.ledger)

    def test_repinned_helper_body_with_same_call_names_is_rejected(self):
        root = self.checkout()
        self.edit(root, "src/biocompiler/policy/validation.py", "left.kind != right.kind", "left.kind == right.kind")
        with self.assertRaisesRegex(coverage.CoverageError, "Changed Python AST/caller closure"):
            coverage.check(root, self.ledger)

    def test_repinned_new_caller_is_rejected(self):
        root = self.checkout()
        self.edit(root, "src/biocompiler/policy/validation.py", "self.duration(item.freshness,",
                  "self.duration(item.resolution, path, owner)\n            self.duration(item.freshness,")
        with self.assertRaisesRegex(coverage.CoverageError, "Changed Python AST/caller closure"):
            coverage.check(root, self.ledger)

    def test_rehashing_both_source_and_ast_cannot_approve_changed_call(self):
        root = self.checkout()
        self.edit(root, "src/biocompiler/policy/validation.py", "owner, positive=False)", "owner, positive=True)", repin_ast=True)
        with self.assertRaisesRegex(coverage.CoverageError, "Unreviewed Python AST/caller closure"):
            coverage.check(root, self.ledger)

    def test_repinned_comment_change_still_requires_complete_source_review(self):
        root = self.checkout()
        self.edit(root, "src/biocompiler/policy/validation.py", "from __future__ import annotations",
                  "# reviewed AST alone is insufficient\nfrom __future__ import annotations", repin_ast=True)
        # Location changes also alter the independently pinned closure. Append
        # instead to isolate the whole-source check from all AST locations.
        path = root / "src/biocompiler/policy/validation.py"
        path.write_bytes((coverage.ROOT / "src/biocompiler/policy/validation.py").read_bytes() + b"\n# appended\n")
        row = next(row for row in self.ledger["sources"] if row["path"].endswith("/validation.py"))
        row["sha256"] = coverage.digest(path.read_bytes())
        row["ast"] = coverage.ast_closure(path.read_bytes(), row["path"])
        with self.assertRaisesRegex(coverage.CoverageError, "Unreviewed complete source pin"):
            coverage.check(root, self.ledger)

    def test_repinned_native_body_cannot_be_approved_by_matching_guard_count(self):
        root = self.checkout()
        self.edit(root, "core/lib/checker/policy_check.ml", "let compatible", "let compatible_changed")
        with self.assertRaisesRegex(coverage.CoverageError, "Unreviewed complete source pin"):
            coverage.check(root, self.ledger)

    def test_source_dependency_model_change_is_rejected_without_product_import(self):
        root = self.checkout()
        self.edit(root, "src/biocompiler/policy/model.py", '"population", "lineage", "region"',
                  '"population", "lineage", "region", "unreviewed"', repin_ast=True)
        with self.assertRaisesRegex(coverage.CoverageError, "Unreviewed Python AST/caller closure"):
            coverage.check(root, self.ledger)

    def test_ast_helper_dependency_is_closed_and_only_stdlib_is_permitted(self):
        coverage.inert_helper(coverage.read(coverage.ROOT, coverage.AST_HELPER))
        for statement in ("import biocompiler.policy", "from other import parser", "from . import other"):
            with self.subTest(statement=statement), self.assertRaisesRegex(coverage.CoverageError, "non-stdlib dependency"):
                coverage.inert_helper(statement.encode())
        root = self.checkout()
        self.edit(root, coverage.AST_HELPER, "import ast", "import ast\nimport biocompiler.policy", repin_ast=True)
        with self.assertRaisesRegex(coverage.CoverageError, "Unreviewed Python AST/caller closure"):
            coverage.check(root, self.ledger)

    def test_malformed_python_is_parsed_inertly_and_rejected(self):
        with self.assertRaisesRegex(coverage.CoverageError, "Cannot parse inert Python"):
            coverage.ast_closure(b"def broken(:\n", "broken.py")

    def test_ledger_cannot_invent_parity_or_mark_counterexamples_executed(self):
        for mutate in (lambda value: value["stage_differences"].clear(),
                       lambda value: value["stage_differences"][0].update(status="equivalent"),
                       lambda value: value["stage_differences"][1].update(status="native_pass")):
            self.ledger = deepcopy(self.original)
            self.reject(mutate, "Unreviewed source predicates/contexts/stage differences")

    def test_exact_three_stage_differences_preserve_native_only_and_scope_qualifications(self):
        differences = {row["id"]: row for row in self.original["stage_differences"]}
        self.assertEqual(set(differences), {"native_source.payload_persistence_duration",
                         "native_source.encounter_reset_owner", "native_source.message_state_correlation_owner"})
        for row in differences.values():
            self.assertEqual(row["status"], "source_predicted_difference_not_executed")
        contexts = {row["id"]: row for row in self.original["contexts"]}
        for identity in ("duration.payload_persistence", "duration.effector_persistence", "access.message_state_correlation"):
            self.assertTrue(all(owner["path"].endswith("policy_check.ml")
                                for owner in contexts["source.context." + identity]["owners"]))
        self.assertIn("executor scope only", contexts["source.context.access.state_reset"]["notes"])

    def test_context_flags_paths_and_predicate_text_are_independently_reviewed(self):
        for mutate in (lambda value: value["contexts"][15]["parameters"].update(positive=False),
                       lambda value: value["contexts"][0].update(path_template="/wrong"),
                       lambda value: value["rules"][0].update(predicate="All types are valid")):
            self.ledger = deepcopy(self.original)
            self.reject(mutate, "Unreviewed source predicates/contexts")

    def test_reference_links_reject_dangling_and_duplicate_values(self):
        for key, bad in (("syntax_ids", "field:Missing.subject"), ("family_ids", "operational.missing"),
                         ("predicate_ids", "source.missing")):
            for duplicate in (False, True):
                with self.subTest(key=key, duplicate=duplicate):
                    self.ledger = deepcopy(self.original)
                    def mutate(value):
                        values = value["contexts"][0][key]
                        values.append(values[0] if duplicate else bad)
                    self.reject(mutate, "Dangling or duplicate")

    def test_changed_existing_link_is_not_accepted_just_because_target_exists(self):
        self.reject(lambda value: value["contexts"][0].update(syntax_ids=["field:Role.id"]),
                    "Unreviewed source predicates/contexts")

    def test_owner_requires_exact_region_and_ast_linkage(self):
        for patch_value in ({"first_line": True}, {"last_line": 999999}, {"region_sha256": "0" * 64},
                            {"python_calls": []}, {"path": "../foreign.py"}):
            self.ledger = deepcopy(self.original)
            self.reject(lambda value: value["contexts"][0]["owners"][0].update(patch_value),
                        "Invalid source region|exceeds file|Changed source anchor|Unclassified source owner")

    def test_no_ocaml_ast_or_source_disposition_upgrade(self):
        self.reject(lambda value: value["sources"][0].update(ast={}), "OCaml source must not claim inferred")
        self.ledger = deepcopy(self.original)
        self.reject(lambda value: value["sources"][0].update(disposition="source_rule_owner"),
                    "Unreviewed source predicates/contexts")

    def test_original_counterexample_inputs_are_bound_without_running_mutations(self):
        root = self.checkout()
        name = next(iter(coverage.INPUT_PINS))
        path = root / name
        path.write_bytes(path.read_bytes() + b"\n")
        row = next(row for row in self.ledger["counterexample_inputs"] if row["path"] == name)
        row["sha256"] = coverage.digest(path.read_bytes())
        with self.assertRaisesRegex(coverage.CoverageError, "Changed original counterexample input"):
            coverage.check(root, self.ledger)

    def test_complementary_ledgers_remain_closed_without_status_inheritance(self):
        root = self.checkout()
        for name, key in ((coverage.SYNTAX_LEDGER, "entries"), (coverage.FAMILY_LEDGER, "rules")):
            path = root / name
            original = path.read_bytes()
            value = json.loads(original)
            value[key].pop()
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(coverage.CoverageError, "Changed (612 syntax|62 family) census"):
                coverage.check(root, self.ledger)
            path.write_bytes(original)

    def test_acceptance_and_scope_cannot_be_upgraded(self):
        for mutate, message in (
            (lambda value: value.update(accepted=True), "missing or extra fields"),
            (lambda value: value.update(claim_scope="complete"), "Wrong source-slice"),
            (lambda value: value["counts"].update(whole_stack_census="complete"), "Changed bounded census"),
            (lambda value: value["rules"][0].update(evidence="native_pass"), "Invented semantic/execution")):
            self.ledger = deepcopy(self.original)
            self.reject(mutate, message)

    def test_duplicate_nonfinite_and_noninteger_json_is_rejected(self):
        for raw, message in ((b'{"x":0,"x":1}', "Duplicate JSON key"),
                             (b'{"x":NaN}', "Nonfinite JSON"),
                             (b'{"x":1.5}', "closed JSON scalar"), (b'"\xff"', "Invalid bounded JSON")):
            with self.subTest(raw=raw), self.assertRaisesRegex(coverage.CoverageError, message):
                coverage.decode(raw)

    def test_json_bounds_reject_oversized_structures(self):
        values = ["x" * (coverage.MAX_STRING + 1), [None] * (coverage.MAX_LIST + 1), 1 << 257]
        deep = None
        for _ in range(coverage.MAX_DEPTH + 1):
            deep = [deep]
        values.append(deep)
        for value in values:
            with self.subTest(kind=type(value).__name__), self.assertRaisesRegex(coverage.CoverageError, "bound exceeded"):
                coverage.bounded(value)
        with self.assertRaisesRegex(coverage.CoverageError, "byte bound"):
            coverage.decode(b" " * (coverage.MAX_BYTES + 1))
        with patch.object(coverage, "MAX_NODES", 2), self.assertRaisesRegex(coverage.CoverageError, "node bound"):
            coverage.bounded([1, 2])

    def test_unsafe_and_escaping_paths_reject_before_reads(self):
        root = self.checkout()
        for name in ("../foreign", "/etc/passwd", "src/../other", "src//other", "src\\other"):
            with self.subTest(name=name), self.assertRaisesRegex(coverage.CoverageError, "source path"):
                coverage.read(root, name)
        (root / "escape").symlink_to(root.parent)
        with self.assertRaisesRegex(coverage.CoverageError, "escaping source path"):
            coverage.read(root, "escape/outside")

    def test_source_read_is_bounded_and_missing_files_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "large").write_bytes(b"x" * 11)
            with patch.object(coverage, "MAX_BYTES", 10), self.assertRaisesRegex(coverage.CoverageError, "Source byte bound"):
                coverage.read(root, "large")
            with self.assertRaisesRegex(coverage.CoverageError, "Missing or escaping"):
                coverage.read(root, "missing")


if __name__ == "__main__":
    unittest.main()
