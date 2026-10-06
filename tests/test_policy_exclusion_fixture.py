"""Independent source-shape and literal controls, without semantic execution."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from biocompiler import policy as p
from tools import generate_policy_exclusion_fixture as generator
from tools import generate_policy_realization_fixture as original

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "core/test/data/policy_exclusion_source_v01.json"


class PolicyExclusionFixtureTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(PATH.read_text())
        self.request = p.from_data(self.fixture["document"], p.BuildRequest)
        self.declarations = {value.id: value for value in self.request.program.declarations}

    def test_frozen_fixture_is_a_separate_complete_request_and_preserves_original(self):
        self.assertEqual(PATH.read_text(), generator.encoded_fixture())
        self.assertEqual(p.check(self.request).status, "complete")
        self.assertEqual(p.check(self.request).semantic_status, "unassessed")
        self.assertEqual(p.loads(p.dumps(self.request), p.BuildRequest), self.request)
        original_path = ROOT / "core/test/data/policy_realization_source_v01.json"
        self.assertEqual(original_path.read_text(), original.encoded_fixture())
        first = p.from_data(json.loads(original_path.read_text())["document"], p.BuildRequest)
        self.assertNotEqual(p.document_digest(first), p.document_digest(self.request))
        self.assertIn("scoped_memory", {value.id for value in first.program.declarations})
        self.assertNotIn("scoped_memory", self.declarations)
        self.assertEqual(self.request.deployment.route, "in_vivo")
        chassis = self.request.deployment.bindings[0].chassis
        self.assertEqual((chassis.species, chassis.recipient_class), ("human", "immune"))
        self.assertEqual(self.request.implementations.implementations, ())
        self.assertEqual((self.request.assurance.level, self.request.assurance.horizon.amount), ("bounded", "6"))

    def test_resolved_catalog_has_distinct_identity_and_retains_original_mismatch_control(self):
        def digest(value):
            return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

        fixture = json.loads((ROOT / "core/test/data/policy_implementation_binding_v01.json").read_text())
        positive = fixture["cases"][1]
        self.assertEqual(positive["name"], "exclusion_sibling_resolved_chassis")
        request = positive["request"]
        document = request["document"]
        entry = document["implementations"]["implementations"][0]
        self.assertEqual(entry["id"], "exclusion.response.primitives.resolved_chassis")
        self.assertEqual(entry["chassis"], [document["deployment"]["bindings"][0]["chassis"]["id"]])
        self.assertEqual(request["catalog_bindings"][0]["entry_id"], entry["id"])
        self.assertEqual(request["catalog_bindings"][0]["entry_digest"], digest(entry))
        self.assertEqual(positive["proposed"]["catalog_entry"], entry["id"])
        self.assertEqual(positive["expected"]["request_fingerprint"], digest(request))
        self.assertEqual(positive["expected"]["implementation_fingerprint"], digest(positive["implementation"]))
        self.assertEqual(positive["implementation"]["authority"]["source_artifact_digest"], digest(document))
        self.assertEqual(positive["implementation"]["authority"]["implementation_catalog_digest"], digest(document["implementations"]))
        self.assertEqual(len(fixture["negative_controls"]), 1)
        control = fixture["negative_controls"][0]
        self.assertEqual(control["expected_diagnostic"], "policy_realization_chassis")
        original = control["case"]
        original_document = original["request"]["document"]
        original_entry = original_document["implementations"]["implementations"][0]
        self.assertEqual(original["name"], "exclusion_sibling")
        self.assertEqual(original_entry["chassis"], ["fixture.human_immune"])
        self.assertEqual(original_document["deployment"]["bindings"][0]["chassis"]["id"], "exclusion.human_immune")
        self.assertNotEqual(original_entry["id"], entry["id"])
        for key in ("program", "deployment", "assurance"):
            self.assertEqual(document[key], original_document[key])
        self.assertEqual(document["program"]["declarations"], self.fixture["document"]["program"]["declarations"])
        self.assertEqual(self.fixture["document"]["implementations"]["implementations"], [])
        self.assertEqual(p.check(p.from_data(document, p.BuildRequest)).status, "complete")

    def test_literal_stores_rules_and_safety_match_independent_direct_declarations(self):
        scope = p.Scope("encounter", p.Ref("encounter", "Encounter"))
        selected = p.StateStore("selected", p.TRUTH, scope, False, 2, "reject", "encounter", None, "not_applicable")
        excluded = p.StateStore("excluded", p.TRUTH, scope, False, 2, "reject", "encounter", None, "not_applicable")
        self.assertEqual(self.declarations["selected"], selected)
        self.assertEqual(self.declarations["excluded"], excluded)
        observed = p.Expr("observe", p.TRUTH, ref=p.Ref("condition", "Observation"), scope=p.Ref("encounter/target", "Subject"))
        arbitration = p.Arbitration("exclusive", "reject", "reject", "forbidden", "none")
        select = p.Rule("select", p.Ref("executor", "Role"), p.rising(observed), observed, "defer", (p.Ref("response", "Effect"),),
            (p.Assignment(p.ref(selected), p.TRUE), p.Assignment(p.ref(excluded), p.FALSE)), arbitration)
        exclude = p.Rule("exclude", p.Ref("executor", "Role"), p.rising(p.not_(observed)), p.not_(observed), "defer", (),
            (p.Assignment(p.ref(selected), p.FALSE), p.Assignment(p.ref(excluded), p.TRUE)), arbitration)
        self.assertEqual(self.declarations["select"], select)
        self.assertEqual(self.declarations["exclude"], exclude)
        self.assertEqual(self.declarations["exclusive_selection"].condition, p.not_(p.all_of(selected.expression, excluded.expression)))
        self.assertEqual(self.declarations["response"].lifecycle.on_loss, "continue")
        self.assertEqual(self.declarations["response"].lifecycle.cancellation, "unsupported")
        self.assertEqual(self.declarations["exclude"].effects, ())
        self.assertEqual(self.declarations["product"], p.Parameter("product", p.TEXT, "fixture.product.alpha"))

    def test_requirement_and_definition_authority_is_complete(self):
        requirements = {value.id: value for value in self.request.program.declarations if isinstance(value, p.Requirement)}
        self.assertEqual(set(requirements), {"request_progress", "initiation_progress", "exclusive_selection"})
        self.assertEqual(set(self.request.assurance.requirements), set(requirements))
        self.assertEqual(requirements["request_progress"].response.value, "requested")
        self.assertEqual(requirements["initiation_progress"].response.value, "initiated")
        self.assertTrue(all(value.horizon.amount == "6" for value in requirements.values()))
        definitions = {value.id: value for value in self.request.program.semantics.definitions}
        for entry in self.fixture["definitions"]["definitions"]:
            self.assertEqual(entry["definition"], p.to_data(definitions[entry["definition"]["id"]].ref))
        submission = p.prepare_submission(self.request)
        self.assertEqual(submission.backend_execution, "not_performed")
        self.assertIn("implementation_catalog_applicability", submission.outstanding_obligations)

    def test_positive_literals_exercise_both_branches_encounters_and_continuing_attempts(self):
        cases = {case["id"]: case for case in self.fixture["timelines"]}
        self.assertEqual(set(cases), {"failure_and_timeouts", "exclusion_preserves_live_attempt", "invalid_after_selection",
                                     "missing_without_selection", "invalid_without_selection"})
        for name in ("failure_and_timeouts", "exclusion_preserves_live_attempt", "invalid_after_selection"):
            expected = cases[name]["literal_expectations"]
            self.assertEqual([(row["encounter"], row["time"]) for row in expected["requests"]], [("e1", "1"), ("e2", "2"), ("e1", "3")])
            self.assertEqual(expected["requirements"], {"request_progress": "pass", "initiation_progress": "pass", "exclusive_selection": "pass"})
            states = {row["time"]: row for row in expected["state_frames"]}
            self.assertEqual(states["1"]["e1"], {"selected": True, "excluded": False})
            self.assertEqual(states["2"]["e1"], {"selected": False, "excluded": True})
            self.assertEqual(states["2"]["e2"], {"selected": True, "excluded": False})
            self.assertEqual(states["3"]["e2"], {"selected": False, "excluded": True})
        self.assertEqual(cases["failure_and_timeouts"]["literal_expectations"]["terminal_outcomes"], ["failed", "timed_out", "timed_out"])
        self.assertEqual(cases["exclusion_preserves_live_attempt"]["literal_expectations"]["active_at_two"], ["attempt/1", "attempt/2"])
        self.assertEqual(cases["exclusion_preserves_live_attempt"]["timeline"]["feedback"], [])
        self.assertEqual([row["status"] for row in cases["invalid_after_selection"]["timeline"]["observations"][-2:]], ["invalid", "conflicting"])
        self.assertTrue(all(int(row["available_at"]) <= 3 for row in cases["failure_and_timeouts"]["timeline"]["observations"]))

    def test_unknown_histories_remain_visible_without_whole_domain_acceptance(self):
        for case in self.fixture["timelines"]:
            expected = case["literal_expectations"]
            self.assertEqual(expected["status"], "unvalidated_source_semantics_expectation")
            for states in expected["state_frames"]:
                for encounter in ("e1", "e2"):
                    self.assertFalse(states[encounter]["selected"] and states[encounter]["excluded"])
            if case["id"] in ("missing_without_selection", "invalid_without_selection"):
                self.assertEqual(expected["requests"], [])
                self.assertEqual(expected["requirements"], {"request_progress": "unknown", "initiation_progress": "unknown", "exclusive_selection": "pass"})
        self.assertEqual((self.fixture["stage"], self.fixture["native_validation"], self.fixture["artifact"]),
                         ("source_authority_only", "not_performed", "withheld"))
        self.assertIn("closed_executable_operating_domain", self.fixture["pending_authorities"])
        self.assertIn("complete_mrna_template_roots_and_chemistry", self.fixture["pending_authorities"])
        self.assertEqual(len(self.fixture["coverage_limits"]), 3)

    def test_source_mutations_have_exact_independent_failure_dispositions(self):
        expected = {
            "select_sets_both": {"kind": "requirement_failure", "id": "exclusive_selection", "status": "fail"},
            "exclude_sets_both": {"kind": "requirement_failure", "id": "exclusive_selection", "status": "fail"},
            "opposite_select_guard": {"kind": "requirement_failure", "id": "request_progress", "status": "fail"},
            "simultaneous_opposed_writes": {"kind": "execution_rejection", "diagnostic": "policy_execution_exclusive"},
        }
        self.assertEqual({case["id"]: case["expected_native_result"] for case in self.fixture["source_edits"]}, expected)
        for case in self.fixture["source_edits"]:
            with self.subTest(case=case["id"]):
                reconstructed = deepcopy(self.fixture["document"])
                current = reconstructed
                for part in case["path"][:-1]:
                    current = current[part]
                self.assertEqual(current[case["path"][-1]], case["before"])
                current[case["path"][-1]] = case["after"]
                self.assertEqual(reconstructed, case["document"])
                request = p.from_data(case["document"], p.BuildRequest)
                self.assertEqual(p.check(request).status, "complete")
                self.assertNotEqual(p.document_digest(request), p.document_digest(self.request))
                self.assertEqual(case["native_validation"], "not_performed")


if __name__ == "__main__":
    unittest.main()
