"""Source-only realization witnesses; no native execution or acceptance claims."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest

from biocompiler import policy as p
from biocompiler.policy import patterns
from tools import generate_policy_realization_fixture as fixture_tool

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "core/test/data/policy_realization_source_v01.json"


def literal_program():
    """Direct declarations independently spelling the intended builder expansion."""
    bundle = fixture_tool.semantic_bundle()
    refs = {definition.id: definition.ref for definition in bundle.definitions}
    role = p.Ref("executor", "Role")
    target = p.Ref("encounter/target", "Subject")
    encounter = p.Ref("encounter", "Encounter")
    clock = p.Ref("clock", "Clock")
    scope = p.Scope("encounter", encounter)
    observed = p.Expr("observe", p.TRUTH, ref=p.Ref("condition", "Observation"), scope=target)
    state = p.Expr("state", p.TRUTH, ref=p.Ref("seen", "StateStore"), scope=encounter)
    requested = p.Expr("effect_event", p.EVENT, ref=p.Ref("response", "Effect"), value="requested", scope=target)
    initiated = replace(requested, value="initiated")
    rising = p.Expr("rising", p.EVENT, (observed,))
    declarations = (
        p.Role("executor", (refs["fixture.interface"],)),
        p.Subject("encounter/target", "cell", "encounter", role, encounter),
        p.Encounter("encounter", role, target, refs["fixture.encounter"], "explicit_event"),
        p.Clock("clock", "availability", p.quantity(1, p.SECOND)),
        p.Observation("condition", role, target, p.TRUTH, refs["fixture.observation"], clock, "cell", "event", "frame", p.quantity(2, p.SECOND)),
        p.StateStore("seen", p.TRUTH, scope, False, 2, "reject", "encounter", None, "not_applicable"),
        p.Parameter("product", p.TEXT, "fixture.product.alpha"),
        p.Effect("response", refs["fixture.effect"], role, target,
                 p.EffectLifecycle("continuous", "continue", "defer", "unsupported", "feedback", "feedback", refs["fixture.lifecycle"], p.quantity(2, p.SECOND)),
                 (p.Argument("product", p.Expr("parameter", p.TEXT, ref=p.Ref("product", "Parameter"))),)),
        p.Rule("respond", role, rising, observed, "defer", (p.Ref("response", "Effect"),),
               (p.Assignment(p.Ref("seen", "StateStore"), p.TRUE),), p.Arbitration("exclusive", "reject", "reject", "forbidden", "none")),
        p.Requirement("request_progress", "progress", "An uncontested known rising observation requests the product within one tick.", scope,
                      condition=p.TRUE, response=requested, deadline=p.quantity(1, p.SECOND), horizon=p.quantity(4, p.SECOND), trigger=rising, clock=clock),
        p.Requirement("initiation_progress", "progress", "Each request initiates its own correlated attempt within one tick.", scope,
                      condition=p.TRUE, response=initiated, deadline=p.quantity(1, p.SECOND), horizon=p.quantity(4, p.SECOND), trigger=requested, clock=clock),
        p.Requirement("request_authorization", "progress", "Each request has known-true evidence by its one-tick deadline; same-tick authorization is a separate preservation obligation.", scope,
                      condition=p.TRUE, response=observed, deadline=p.quantity(1, p.SECOND), horizon=p.quantity(4, p.SECOND), trigger=requested, clock=clock),
        p.Requirement("scoped_memory", "safety", "Known true evidence implies this encounter recorded its response at the settled tick.", scope,
                      condition=p.Expr("any", p.TRUTH, (p.Expr("not", p.TRUTH, (observed,)), state)), horizon=p.quantity(4, p.SECOND)),
    )
    return p.PolicyProgram("realization_source_literal", bundle, declarations,
                           tuple(p.SourceSpan(item.id, "policy_realization_source_literal.py", index + 1)
                                 for index, item in enumerate(declarations)))


class PolicyRealizationSourceFixtureTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(PATH.read_text(encoding="utf-8"))
        self.request = p.from_data(self.fixture["document"], p.BuildRequest)

    def test_frozen_bytes_and_independent_literal_expansion_match(self):
        self.assertEqual(PATH.read_text(encoding="utf-8"), fixture_tool.encoded_fixture())
        self.assertEqual(p.to_data(literal_program()), p.to_data(self.request.program))
        self.assertEqual(p.to_data(fixture_tool.build_request()), self.fixture["document"])
        self.assertEqual(p.check(self.request).status, "complete")
        self.assertEqual(p.check(self.request).semantic_status, "unassessed")

    def test_complete_request_product_and_definition_authorities_survive_roundtrip(self):
        reopened = p.loads(p.dumps(self.request), p.BuildRequest)
        self.assertEqual(reopened, self.request)
        self.assertEqual(p.document_digest(reopened), p.document_digest(self.request))
        self.assertEqual(reopened.deployment.route, "in_vivo")
        chassis = reopened.deployment.bindings[0].chassis
        self.assertEqual((chassis.species, chassis.recipient_class), ("human", "immune"))
        self.assertEqual((reopened.deployment.payload.format, reopened.deployment.payload.member_count,
                          reopened.deployment.payload.product_count), ("RNA", 1, 1))
        self.assertEqual(reopened.implementations.implementations, ())
        self.assertEqual((reopened.assurance.level, reopened.assurance.horizon.amount), ("bounded", "4"))
        declarations = {item.id: item for item in reopened.program.declarations}
        self.assertEqual(declarations["product"], p.Parameter("product", p.TEXT, "fixture.product.alpha"))
        self.assertEqual(declarations["response"].parameters,
                         (p.Argument("product", p.Expr("parameter", p.TEXT, ref=p.Ref("product", "Parameter"))),))
        definitions = {item.id: item for item in reopened.program.semantics.definitions}
        for descriptor in self.fixture["definitions"]["definitions"]:
            self.assertEqual(descriptor["definition"], p.to_data(definitions[descriptor["definition"]["id"]].ref))
        submission = p.prepare_submission(reopened)
        self.assertEqual(submission.request, reopened)
        self.assertEqual(submission.backend_execution, "not_performed")
        self.assertEqual(submission.semantic_status, "unassessed")
        self.assertEqual(submission.outstanding_obligations,
                         tuple(sorted(p.check(reopened).deferred_obligations)))

    def test_requirements_do_not_claim_guaranteed_completion(self):
        requirements = {item.id: item for item in self.request.program.declarations if isinstance(item, p.Requirement)}
        self.assertEqual(set(requirements), {"request_progress", "initiation_progress", "request_authorization", "scoped_memory"})
        self.assertEqual(set(self.request.assurance.requirements), set(requirements))
        self.assertEqual((requirements["request_progress"].trigger.op, requirements["request_progress"].response.value), ("rising", "requested"))
        self.assertEqual((requirements["initiation_progress"].trigger.value, requirements["initiation_progress"].response.value), ("requested", "initiated"))
        self.assertEqual(requirements["request_authorization"].response.op, "observe")
        for requirement in requirements.values():
            self.assertEqual(requirement.scope, p.Scope("encounter", p.Ref("encounter", "Encounter")))
            if requirement.kind == "progress":
                self.assertEqual(requirement.deadline.amount, "1")
                self.assertNotEqual(requirement.response.value, "completed")

    def test_two_distinct_encounters_and_all_feedback_branches_are_literal_witnesses(self):
        cases = {case["id"]: case for case in self.fixture["timelines"]}
        self.assertEqual(set(cases), {"completion_and_timeout", "failure_and_timeout", "both_timeout",
                                     "stale_before_response", "invalid_before_response"})
        for name in ("completion_and_timeout", "failure_and_timeout", "both_timeout"):
            timeline = cases[name]["timeline"]
            self.assertEqual([(x["id"], x["target"]) for x in timeline["encounters"]], [("e1", "target-1"), ("e2", "target-2")])
            self.assertEqual([(x["available_at"], x["encounter"], x["value"]) for x in timeline["observations"]],
                             [("0", "e1", False), ("0", "e2", False), ("1", "e1", True), ("2", "e2", True)])
            self.assertEqual(cases[name]["literal_expectations"]["settled_memory_at_one"], {"e1": True, "e2": False})
            self.assertEqual(cases[name]["literal_expectations"]["authorization_closed_at"], ["1", "2"])
        self.assertEqual(cases["completion_and_timeout"]["timeline"]["feedback"][0]["outcome"], "completed")
        self.assertEqual(cases["failure_and_timeout"]["timeline"]["feedback"][0]["outcome"], "failed")
        self.assertEqual(cases["both_timeout"]["timeline"]["feedback"], [])
        for name in ("stale_before_response", "invalid_before_response"):
            expected = cases[name]["literal_expectations"]
            self.assertEqual(expected["requirements"]["scoped_memory"], "unknown")
            self.assertEqual(expected["requests"], [])

    def test_near_neighbor_edits_are_exact_and_have_independent_structural_expectations(self):
        expected = {"opposite_guard": "complete", "lost_memory_write": "complete", "different_product": "complete",
                    "longer_assurance": "complete", "unknown_assurance_requirement": "invalid", "stale_effect_definition": "invalid"}
        self.assertEqual({case["id"]: case["expected_authoring_status"] for case in self.fixture["source_edits"]}, expected)
        for case in self.fixture["source_edits"]:
            with self.subTest(case=case["id"]):
                reconstructed = deepcopy(self.fixture["document"])
                parent = reconstructed
                for key in case["path"][:-1]:
                    parent = parent[key]
                self.assertEqual(parent[case["path"][-1]], case["before"])
                parent[case["path"][-1]] = case["after"]
                self.assertEqual(reconstructed, case["document"])
                mutated = p.from_data(case["document"], p.BuildRequest)
                report = p.check(mutated)
                self.assertEqual(report.status, expected[case["id"]])
                self.assertTrue(set(case["required_diagnostics"]) <= {item.code for item in report.diagnostics})
                self.assertNotEqual(p.document_digest(mutated), p.document_digest(self.request))
                self.assertEqual(case["native_validation"], "not_performed")

    def test_source_only_scope_and_missing_downstream_authorities_remain_explicit(self):
        self.assertEqual((self.fixture["stage"], self.fixture["native_validation"], self.fixture["artifact"]),
                         ("source_authority_only", "not_performed", "withheld"))
        self.assertIn("closed_executable_operating_domain", self.fixture["pending_authorities"])
        self.assertIn("complete_mrna_template_roots_and_chemistry", self.fixture["pending_authorities"])
        self.assertIn("independent_implementation_models", self.fixture["pending_authorities"])
        self.assertEqual(len(self.fixture["coverage_limits"]), 3)
        for case in self.fixture["timelines"]:
            self.assertEqual(case["literal_expectations"]["status"], "unvalidated_source_semantics_expectation")
        detached = p.to_data(self.request)
        detached["assurance"]["requirements"].clear()
        self.assertEqual(len(self.request.assurance.requirements), 4)

    def test_namespaced_pattern_instances_preserve_separate_state_and_effect_references(self):
        bundle = fixture_tool.semantic_bundle()
        definitions = {item.id: item.ref for item in bundle.definitions}
        builder = p.ProgramBuilder("composition_literal", semantics=bundle)
        executor = builder.executor("executor", requires=(definitions["fixture.interface"],))
        clock = builder.clock("clock", basis="availability", resolution=p.quantity(1, p.SECOND))
        instances = []
        for name in ("first", "second"):
            with builder.namespace(name):
                encounter = builder.encounter("encounter", executor=executor, contract=definitions["fixture.encounter"])
                observation = builder.observe("condition", observer=executor, subject=encounter.target, value_type=p.TRUTH,
                    contract=definitions["fixture.observation"], clock=clock, access="cell", coverage="event", coherence=name, freshness=p.quantity(2, p.SECOND))
                effect = builder.effect("response", executor=executor, subject=encounter.target, contract=definitions["fixture.effect"],
                    lifecycle=p.EffectLifecycle("initiation", "continue", "defer", "unsupported", "feedback", "feedback", definitions["fixture.lifecycle"]),
                    parameters=(p.Argument("product", p.literal("fixture.product.alpha")),))
                scope = p.Scope("encounter", p.ref(encounter))
                arbitration = p.Arbitration("exclusive", "reject", "reject", "forbidden", "none")
                rule = patterns.once_per_scope(builder, "once", executor=p.ref(executor), scope=scope, on=observation.updated,
                    permitted=observation.expression, effect=p.ref(effect), lifetime="encounter", arbitration=arbitration)
                seen_ref = p.Ref(name + "/once/seen", "StateStore")
                manual = p.Rule(name + "/once/respond", p.ref(executor), observation.updated,
                    p.all_of(observation.expression, p.not_(p.Expr("state", p.TRUTH, ref=seen_ref, scope=p.ref(encounter)))),
                    "defer", (p.ref(effect),), (p.Assignment(seen_ref, p.TRUE),), arbitration)
                self.assertEqual(p.to_data(rule), p.to_data(manual))
                instances.append(rule)
        program = p.loads(p.dumps(builder.freeze()), p.PolicyProgram)
        states = [item for item in program.declarations if isinstance(item, p.StateStore)]
        self.assertEqual([state.id for state in states], ["first/once/seen", "second/once/seen"])
        self.assertNotEqual(states[0].scope, states[1].scope)
        self.assertNotEqual(instances[0].effects, instances[1].effects)
        self.assertNotEqual(instances[0].assignments, instances[1].assignments)


if __name__ == "__main__":
    unittest.main()
