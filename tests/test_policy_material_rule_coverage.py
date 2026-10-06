"""Static inventory controls only: no native policy imports or execution."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import shutil
import tempfile
import unittest

from tools import check_policy_material_rule_coverage as coverage


class PolicyMaterialRuleCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = coverage.decode(coverage.read(coverage.ROOT, coverage.LEDGER))
        cls.source_names = coverage.discover(coverage.ROOT)

    def setUp(self):
        self.ledger = deepcopy(self.original)

    def rejected(self, mutate, message):
        mutate(self.ledger)
        with self.assertRaisesRegex(coverage.CoverageError, message):
            coverage.check(coverage.ROOT, self.ledger)

    def checkout(self):
        directory = tempfile.TemporaryDirectory(prefix="policy-material-rule-coverage-")
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        names = set(self.source_names) | {self.original["syntax_ledger"]}
        names.update(row["path"] for row in self.original["witness_sources"])
        for name in names:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(coverage.ROOT / name, target)
        return root

    def test_reviewed_inventory_is_current_without_semantic_acceptance(self):
        result = coverage.check()
        self.assertEqual(result["rules"], 62)
        self.assertEqual(result["sources"], 96)
        self.assertEqual(result["witness_sources"], 30)
        self.assertEqual(result["rules_with_pending_witnesses"], 16)
        self.assertEqual(result["status"], "source_inventory_current")
        self.assertEqual(result["semantic_proof"], "not_established")
        self.assertEqual(result["test_execution"], "not_performed")
        self.assertEqual(len(coverage.decode(coverage.read(coverage.ROOT, self.original["syntax_ledger"]))["entries"]), 612)

    def test_omitted_duplicate_reordered_or_invented_family_is_rejected(self):
        for mutate in (
            lambda value: value["rules"].pop(),
            lambda value: value["rules"].append(deepcopy(value["rules"][0])),
            lambda value: value["rules"].reverse(),
            lambda value: value["rules"][0].update(id="authoring.invented"),
        ):
            with self.subTest(mutation=mutate):
                self.ledger = deepcopy(self.original)
                self.rejected(mutate, "rule census")

    def test_signature_compound_and_lifecycle_rows_retain_distinguishing_source_controls(self):
        rules = {row["id"]: row for row in self.original["rules"]}
        for identity in ("operational.effect_signature", "operational.lifecycle", "implementation.state",
                         "implementation.expression_wiring", "implementation.attempts"):
            row = rules[identity]
            self.assertEqual(row["witness_status"], "source_witnesses_present")
            self.assertTrue(row["positive"] and row["negative"])
            self.assertFalse(row["gaps"])
            for kind in ("positive", "negative"):
                self.assertTrue(all(item["evidence_scope"] == "source_only_not_executed_by_this_gate" for item in row[kind]))
        paths = {row["path"] for row in self.original["witness_sources"]}
        for filename in ("policy_material_lifecycle_v01.json", "policy_material_compound_v01.json",
                         "policy_material_request_v01.json", "policy_operational_v01.json"):
            self.assertIn("core/test/data/" + filename, paths)

    def test_new_pipeline_module_requires_classification(self):
        root = self.checkout()
        (root / "core/lib/checker/policy_new_gate.ml").write_text('let profile = "biocompiler.policy_new.v0.1"\n')
        with self.assertRaisesRegex(coverage.CoverageError, "Unclassified.*pipeline source"):
            coverage.check(root, self.ledger)

    def test_native_body_change_is_not_hidden_by_unchanged_guard_count(self):
        root = self.checkout()
        name = "core/lib/checker/policy_admission.ml"
        path = root / name
        text = path.read_text()
        self.assertIn("<= 4096", text)
        path.write_text(text.replace("<= 4096", "<= 4095", 1))
        with self.assertRaisesRegex(coverage.CoverageError, "Stale reviewed source hash"):
            coverage.check(root, self.ledger)

    def test_changed_profile_or_guard_census_requires_review_even_with_new_hash(self):
        for appended in ('\nlet new_profile = "biocompiler.policy_unreviewed.v0.1"\n', '\nlet new_guard x = Diagnostic.require x "new" "new"\n'):
            with self.subTest(appended=appended):
                root = self.checkout()
                name = "core/lib/checker/policy_admission.ml"
                path = root / name
                path.write_text(path.read_text() + appended)
                ledger = deepcopy(self.original)
                next(row for row in ledger["sources"] if row["path"] == name)["sha256"] = coverage.digest(path.read_bytes())
                with self.assertRaisesRegex(coverage.CoverageError, "Changed guard/profile census"):
                    coverage.check(root, ledger)

    def test_public_nonpolicy_dispatch_is_pinned(self):
        root = self.checkout()
        path = root / "core/lib/service/service.ml"
        path.write_text(path.read_text() + '\nlet extra_public_route = "unchecked-material"\n')
        with self.assertRaisesRegex(coverage.CoverageError, "Stale reviewed source hash"):
            coverage.check(root, self.ledger)
        for name in ("core/lib/producer_service/producer_service.ml", "core/lib/wire/protocol.ml",
                     "core/bin/core/main.ml", "core/bin/verify/main.ml", "src/biocompiler/entrypoint.py",
                     "src/biocompiler/policy/cli.py", "src/biocompiler/core_distribution.py"):
            self.assertIn(name, self.source_names)

    def test_only_closed_route_exceptions_are_allowed(self):
        def mutate(value):
            next(row for row in value["sources"] if row["path"] == "core/lib/service/policy_material_service.ml")["disposition"] = "outside_route"
        self.rejected(mutate, "Unreviewed pipeline exception")

    def test_witness_source_and_exact_anchor_both_remain_bound(self):
        root = self.checkout()
        path = root / "core/test/test_policy_material_service.ml"
        path.write_text(path.read_text() + "\n(* Changed witness after review. *)\n")
        with self.assertRaisesRegex(coverage.CoverageError, "Stale witness source hash"):
            coverage.check(root, self.ledger)
        self.rejected(lambda value: value["rules"][0]["negative"][0]["source"].update(anchor="missing distinguishing assertion"),
                      "missing exact source anchor")

    def test_owners_cannot_point_to_unreviewed_paths_or_missing_anchors(self):
        for change in ({"path": "../../foreign.ml"}, {"anchor": "invented restriction"}, {"occurrence": True}):
            with self.subTest(change=change):
                self.ledger = deepcopy(self.original)
                self.rejected(lambda value: value["rules"][0]["owners"][0].update(change),
                              "unclassified reference|missing exact source anchor")

    def test_missing_witness_requires_explicit_pending_gap(self):
        self.rejected(lambda value: value["rules"][0].update(positive=[]), "Missing witness must remain pending")
        self.ledger = deepcopy(self.original)
        self.rejected(lambda value: value["rules"][0].update(witness_status="complete"), "Witness status contradicts gaps")

    def test_context_with_missing_control_cannot_be_relabelled_complete(self):
        def mutate(value):
            row = next(row for row in value["rules"] if row["id"] == "implementation.source_family")
            # Newly indexed controls must not make this adversary depend on
            # which reviewed family currently happens to lack a witness.
            row.update(negative=[], gaps=[], witness_status="source_witnesses_present")
        self.rejected(mutate, "Missing witness must remain pending")

    def test_source_pointers_cannot_claim_native_execution(self):
        self.rejected(lambda value: value["rules"][0]["positive"][0].update(evidence_scope="hosted_pass"),
                      "Witness upgraded to execution proof")
        self.ledger = deepcopy(self.original)
        self.rejected(lambda value: value.update(claim_scope="semantic_complete"), "Wrong contextual coverage claim")

    def test_closed_schema_rejects_extra_acceptance_and_duplicate_json_keys(self):
        self.rejected(lambda value: value.update(accepted=True), "missing or extra fields")
        with self.assertRaisesRegex(coverage.CoverageError, "Duplicate ledger key"):
            coverage.decode(b'{"schema_version":"one","schema_version":"two"}')
        with self.assertRaisesRegex(coverage.CoverageError, "Nonfinite JSON"):
            coverage.decode(b'{"limit":NaN}')

    def test_unknown_stage_disposition_and_invalid_witness_shape_fail_closed(self):
        mutations = (
            lambda value: value["rules"][0].update(stage="universal"),
            lambda value: value["rules"][0]["outside_context"].update(disposition="accepted"),
            lambda value: value["witness_sources"][0].update(path=[]),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                self.ledger = deepcopy(self.original)
                self.rejected(mutate, "Unknown contextual stage|no explicit outcome|paths must be strings")

    def test_lexical_census_skips_comments_strings_and_character_literals(self):
        raw = b'''(* require (* Diagnostic.fail *) "biocompiler.hidden.v1" *)
let quote = '"'
let letter : 'a option = None
let label = "require Diagnostic.fail"
let profile = "biocompiler.visible.v1"
let check x = Diagnostic.require x "code" "message"
'''
        result = coverage.census("sample.ml", raw)
        self.assertEqual(result["guards"], {"Diagnostic.require": 1})
        self.assertEqual(result["profile_literals"], {"biocompiler.visible.v1": 1})
        self.assertEqual(result["kind"], "ocaml_lexical_guard_identifier_census_not_calls")

    def test_bounded_file_read_and_repository_path(self):
        with tempfile.TemporaryDirectory(prefix="rule-coverage-bound-") as directory:
            root = Path(directory)
            path = root / "large.json"
            with path.open("wb") as handle:
                handle.truncate(coverage.MAX_BYTES + 1)
            with self.assertRaisesRegex(coverage.CoverageError, "exceeds static inventory bound"):
                coverage.read(root, "large.json")
            with self.assertRaisesRegex(coverage.CoverageError, "escapes repository"):
                coverage.source(root, "../foreign.json")


if __name__ == "__main__":
    unittest.main()
