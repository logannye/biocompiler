"""Static inventory controls only: no native policy imports or execution."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
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
        names = set(self.source_names) | {self.original["syntax_ledger"], coverage.COMPONENT_LEDGER}
        names.update(row["path"] for row in self.original["witness_sources"])
        names.update(coverage.COMPONENT_WITNESSES)
        for name in names:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(coverage.ROOT / name, target)
        return root

    def test_reviewed_inventory_is_current_without_semantic_acceptance(self):
        result = coverage.check()
        self.assertEqual(result["rules"], 62)
        self.assertEqual(result["sources"], 140)
        self.assertEqual(result["witness_sources"], 30)
        self.assertEqual(result["rules_with_pending_witnesses"], 16)
        self.assertEqual(result["status"], "source_inventory_current")
        self.assertEqual(result["semantic_proof"], "not_established")
        self.assertEqual(result["test_execution"], "not_performed")
        self.assertEqual(result["component_route"], {"rules": 19, "sources": 47, "witness_sources": 35,
            "status": "source_inventory_current", "semantic_proof": "not_established", "test_execution": "not_performed",
            "historical_feedback": "reference_only_not_reauthenticated_or_transferred"})
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

    def test_component_route_cannot_be_promoted_into_old_whole_kernel_rules(self):
        self.assertEqual(len(coverage.COMPONENT_ROUTE_SOURCES), 44)
        self.assertEqual(len(coverage.COMPONENT_SHARED_SOURCES), 3)
        for path in coverage.COMPONENT_ROUTE_SOURCES:
            row = next(value for value in self.original["sources"] if value["path"] == path)
            self.assertEqual(row["disposition"], "outside_route")
            self.assertEqual(row["reason"], coverage.COMPONENT_REASON)
        path = "core/lib/realization_checker/policy_component_material_check.ml"
        self.rejected(lambda value: next(row for row in value["sources"] if row["path"] == path).update(disposition="rule_owner"),
                      "Changed route exception")

    def test_component_meaning_and_witness_identity_cannot_be_reassigned_by_repins(self):
        original = coverage.decode(coverage.read(coverage.ROOT, coverage.COMPONENT_LEDGER))
        mutations = [lambda value: value["rules"].pop(),
                     lambda value: value["sources"].pop(),
                     lambda value: value["witness_sources"].reverse(),
                     lambda value: value["rules"][0].update(evidence_scope="hosted_pass"),
                     lambda value: value["rules"][0].update(scope="unrestricted reusable biological components"),
                     lambda value: value["historical_development_feedback"].update(revision="0" * 40),
                     lambda value: value["rules"][0].update(negative=deepcopy(value["rules"][1]["positive"]))]
        for mutation in mutations:
            ledger = deepcopy(original); mutation(ledger)
            with self.subTest(mutation=mutation), self.assertRaises(coverage.CoverageError):
                coverage.check_component(coverage.ROOT, ledger)
        # The replacement points to a real, current, pinned assertion; only the
        # independently reviewed meaning map distinguishes its wrong purpose.
        ledger = deepcopy(original)
        ledger["rules"][0]["negative"] = deepcopy(ledger["rules"][1]["positive"])
        with self.assertRaisesRegex(coverage.CoverageError, "meaning/witness/provenance metadata"):
            coverage.check_component(coverage.ROOT, ledger)

    def test_component_source_and_anchor_drift_have_separate_boundaries(self):
        root = self.checkout()
        ledger = coverage.decode(coverage.read(root, coverage.COMPONENT_LEDGER))
        path = root / "core/lib/domain/policy_component_fragment.ml"
        path.write_text(path.read_text() + '\nlet future = "biocompiler.component_future.v1"\n')
        with self.assertRaisesRegex(coverage.CoverageError, "Stale component source hash"):
            coverage.check_component(root, ledger)
        next(row for row in ledger["sources"] if row["path"] == path.relative_to(root).as_posix())["sha256"] = coverage.digest(path.read_bytes())
        with self.assertRaisesRegex(coverage.CoverageError, "guard/profile census"):
            coverage.check_component(root, ledger)
        ledger = coverage.decode(coverage.read(coverage.ROOT, coverage.COMPONENT_LEDGER))
        ledger["rules"][0]["positive"][0]["anchor"] = "invented source assertion"
        with self.assertRaisesRegex(coverage.CoverageError, "Missing component source anchor"):
            coverage.check_component(coverage.ROOT, ledger)

    def before_selection_publication(self):
        ledger = coverage.decode(coverage.read(coverage.ROOT, coverage.COMPONENT_LEDGER))
        added_sources = {
            *coverage.COMPONENT_SHARED_SOURCES,
            *[f"core/lib/service/{name}.{suffix}" for name in
              ("policy_component_material_format", "policy_component_selection_service") for suffix in ("ml", "mli")],
            "src/biocompiler/core_policy_component_selection.py", "src/biocompiler/policy/component_selection.py"}
        added_witnesses = {"core/test/test_policy_component_selection_scope.ml",
            "core/test/test_policy_component_selection_service.ml",
            "tests/test_core_policy_component_selection.py", "tests/test_policy_component_selection.py",
            "tools/check_policy_component_selection.py", "tests/test_policy_component_selection_witness.py"}
        self.assertEqual([row["id"] for row in ledger["rules"][-4:]], [
            "component.selection_publication_resources", "component.selection_scope",
            "component.selection_export", "component.selection_sdk"])
        self.assertIn("The preceding checker-batch limitation", ledger["limitations"][-1])
        ledger["sources"] = [row for row in ledger["sources"] if row["path"] not in added_sources]
        ledger["witness_sources"] = [row for row in ledger["witness_sources"] if row["path"] not in added_witnesses]
        ledger["rules"] = ledger["rules"][:-4]
        ledger["limitations"] = ledger["limitations"][:-1]
        # Only these three implementation anchors moved in the shared-scope
        # factoring. Restore them to verify the exact prior reviewed meaning.
        rule = next(row for row in ledger["rules"] if row["id"] == "component.checked_selection")
        self.assertEqual([pointer["anchor"] for pointer in rule["owners"]], [
            "let check_in ~scope ~candidate:proposed ~limits = protect scope (fun () ->",
            "spend scope budget child_allowance;", "let selected = match matches,winner with"])
        for pointer, anchor in zip(rule["owners"], [
            "let check ~request:original ~candidate:proposed ~limits =",
            "W.charge budget child_allowance;", "let accepted_value = match matches,winner with"]):
            pointer["anchor"] = anchor
        return ledger

    def test_selection_publication_preserves_fifteen_rules_and_shared_authorities(self):
        projected = self.before_selection_publication()
        encoded = json.dumps(coverage.component_metadata(projected), sort_keys=True,
                             separators=(",", ":"), ensure_ascii=False).encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest(),
                         "f95fedd7eeb9641704488414a256669c5a17682182b571f5feffd9fed88993ef")
        for path in coverage.COMPONENT_SHARED_SOURCES:
            row = next(value for value in self.original["sources"] if value["path"] == path)
            self.assertNotIn(path, coverage.ROUTE_EXCEPTIONS)
            self.assertNotEqual(row["disposition"], "outside_route")

    def before_selection_checks(self):
        ledger = self.before_selection_publication()
        added_sources = {f"core/lib/{directory}/{name}.{suffix}" for directory, name in (
            ("domain", "policy_component_selection_candidate"),
            ("realization_checker", "policy_component_selection_common"),
            ("realization_checker", "policy_component_selection_check"),
        ) for suffix in ("ml", "mli")}
        added_witnesses = {"core/test/test_policy_component_selection_candidate.ml",
                           "core/test/test_policy_component_selection_common.ml",
                           "core/test/test_policy_component_selection_check.ml",
                           "core/test/policy_component_support/selection_requests.ml"}
        self.assertEqual([row["id"] for row in ledger["rules"][-3:]], [
            "component.selection_candidate_codec", "component.selection_common_authority", "component.checked_selection"])
        self.assertIn("The preceding codec-batch limitation records its original boundary", ledger["limitations"][-1])
        ledger["sources"] = [row for row in ledger["sources"] if row["path"] not in added_sources]
        ledger["witness_sources"] = [row for row in ledger["witness_sources"] if row["path"] not in added_witnesses]
        ledger["rules"] = ledger["rules"][:-3]
        ledger["limitations"] = ledger["limitations"][:-1]
        return ledger

    def test_selection_checks_preserve_all_twelve_previous_rules_and_provenance(self):
        projected = self.before_selection_checks()
        metadata = {key: value for key, value in projected.items() if key not in {"sources", "witness_sources"}}
        metadata["source_paths"] = [row["path"] for row in projected["sources"]]
        metadata["witness_paths"] = [row["path"] for row in projected["witness_sources"]]
        encoded = json.dumps(metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest(),
                         "ee305db3815b0810f3b142d091d119be23d1ecaa25053d4409f52cab5cab629d")

    def test_selection_codec_addition_preserves_all_reviewed_component_meaning(self):
        ledger = self.before_selection_checks()
        self.assertEqual([row["id"] for row in ledger["rules"][-2:]],
                         ["component.selection_request_codec", "component.material_candidate_codec"])
        self.assertIn("Selection checking, common-authority validation", ledger["limitations"][-1])
        self.assertIn("public selection route and fresh selection export remain unimplemented", ledger["limitations"][-1])
        # Remove only this reviewed additive batch. This independent projection
        # must retain the exact old ten-rule meaning, pointers and provenance;
        # rehashing source bodies cannot rewrite those historical obligations.
        added_sources = {f"core/lib/domain/{name}.{suffix}" for name in (
            "policy_component_selection_request", "policy_component_material_candidate"
        ) for suffix in ("ml", "mli")}
        added_witnesses = {"core/test/test_policy_component_selection_request.ml",
                           "core/test/test_policy_component_material_candidate.ml"}
        projected = {key: value for key, value in ledger.items() if key not in {"sources", "witness_sources"}}
        projected["source_paths"] = [row["path"] for row in ledger["sources"] if row["path"] not in added_sources]
        projected["witness_paths"] = [row["path"] for row in ledger["witness_sources"] if row["path"] not in added_witnesses]
        projected["rules"] = projected["rules"][:-2]
        projected["limitations"] = projected["limitations"][:-1]
        encoded = json.dumps(projected, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest(),
                         "cc880bf2ecf3a5ed8bebfd83cd6fac872a3c432dda0a0c902e53ede18afd6216")

    def test_new_domain_codec_inventory_cannot_omit_sources_or_claim_acceptance(self):
        original = coverage.decode(coverage.read(coverage.ROOT, coverage.COMPONENT_LEDGER))
        for name in ("selection_request", "material_candidate"):
            owner = "core/lib/domain/policy_component_" + name + ".ml"
            witness = "core/test/test_policy_component_" + name + ".ml"
            rule = next(row for row in original["rules"] if row["id"] == "component." + name + "_codec")
            self.assertIn(owner, [row["path"] for row in rule["owners"]])
            self.assertTrue(all(row["path"] == witness for key in ("positive", "negative") for row in rule[key]))
            self.assertEqual(rule["evidence_scope"], "source_only_not_executed_by_this_gate")
            for key, path in (("sources", owner), ("sources", owner + "i"), ("witness_sources", witness)):
                ledger = deepcopy(original)
                ledger[key] = [row for row in ledger[key] if row["path"] != path]
                with self.subTest(codec=name, omitted=path), self.assertRaisesRegex(coverage.CoverageError, "census"):
                    coverage.check_component(coverage.ROOT, ledger)
            ledger = deepcopy(original)
            next(row for row in ledger["rules"] if row["id"] == rule["id"])["limits"] = "Selection and export accepted."
            with self.subTest(codec=name), self.assertRaisesRegex(coverage.CoverageError, "meaning/witness/provenance metadata"):
                coverage.check_component(coverage.ROOT, ledger)


    def test_selection_checks_require_every_source_witness_and_source_only_claim(self):
        original = coverage.decode(coverage.read(coverage.ROOT, coverage.COMPONENT_LEDGER))
        for suffix, owner, identity in (
            ("candidate", "domain", "component.selection_candidate_codec"),
            ("common", "realization_checker", "component.selection_common_authority"),
            ("check", "realization_checker", "component.checked_selection"),
        ):
            name = "policy_component_selection_" + suffix
            source = "core/lib/" + owner + "/" + name + ".ml"
            witness = "core/test/test_" + name + ".ml"
            row = next(row for row in original["rules"] if row["id"] == identity)
            self.assertIn(source, [pointer["path"] for pointer in row["owners"]])
            self.assertTrue(all(pointer["path"] == witness for key in ("positive", "negative") for pointer in row[key]))
            self.assertEqual(row["evidence_scope"], "source_only_not_executed_by_this_gate")
            for key, path in (("sources", source), ("sources", source + "i"), ("witness_sources", witness)):
                ledger = deepcopy(original)
                ledger[key] = [item for item in ledger[key] if item["path"] != path]
                with self.subTest(rule=identity, omitted=path), self.assertRaisesRegex(coverage.CoverageError, "census"):
                    coverage.check_component(coverage.ROOT, ledger)
            ledger = deepcopy(original)
            next(item for item in ledger["rules"] if item["id"] == identity)["evidence_scope"] = "hosted_execution_pass"
            with self.subTest(rule=identity), self.assertRaisesRegex(coverage.CoverageError, "upgraded to execution proof"):
                coverage.check_component(coverage.ROOT, ledger)
        support = "core/test/policy_component_support/selection_requests.ml"
        ledger = deepcopy(original)
        ledger["witness_sources"] = [row for row in ledger["witness_sources"] if row["path"] != support]
        with self.assertRaisesRegex(coverage.CoverageError, "census"):
            coverage.check_component(coverage.ROOT, ledger)


if __name__ == "__main__":
    unittest.main()
