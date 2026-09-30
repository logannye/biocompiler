"""Bounded graph alternatives must satisfy authority and independent execution."""

from dataclasses import replace
import unittest
from unittest.mock import patch

import biocompiler as bc
from biocompiler.registry.synthetic import (
    SYNTHETIC_CATALOG,
    TEMPORAL_CATALOG,
    TEMPORAL_PROFILE_VERSION,
)
from biocompiler.synthesis.selection import SyntheticSelectionResult, select_synthetic
from biocompiler.synthesis.synthetic import (
    SyntheticGeneratorConfig,
    _generate_synthetic,
    generate_synthetic,
    check_synthetic_candidate,
)
from examples.temporal_pipeline import build_request
from test_synthetic_generation import exercised_history, fixture
from test_temporal_generation import cell_history, cell_model, freeze


def with_policy(request, *, constraints=None, preferences=None):
    build = replace(
        request.build_request,
        implementation_constraints={} if constraints is None else constraints,
        preferences={} if preferences is None else preferences,
    )
    behavior = bc.lower_to_behavior(build)
    contract = replace(request.contract, behavior_fingerprint=behavior.fingerprint)
    return bc.RealizationRequest.freeze(build, behavior, contract, request.domain)


def without_and(catalog=SYNTHETIC_CATALOG):
    return [item.operation for item in catalog.components if item.operation != "and"]


class SyntheticSelectionTests(unittest.TestCase):
    def setUp(self):
        self.request, self.sample = fixture()
        self.history = exercised_history(self.sample)

    def select(self, request=None, **kwargs):
        return select_synthetic(
            self.request if request is None else request,
            self.history,
            until=7,
            **kwargs,
        )

    def test_both_concrete_graphs_are_checked_before_cost_ranking(self):
        result = self.select()
        self.assertEqual(result.outcome, "selected")
        self.assertEqual(result.selected_strategy, "native")
        self.assertEqual(result.checked_candidates, 2)
        self.assertEqual(result.rejected_candidates, 0)
        self.assertEqual([item.gate_count for item in result.alternatives], [3, 6])
        self.assertTrue(
            all(
                item.check.outcome == bc.CheckOutcome.PASS
                for item in result.alternatives
            )
        )
        native, alternate = (item.candidate for item in result.alternatives)
        self.assertNotEqual(
            native.mechanism.fingerprint, alternate.mechanism.fingerprint
        )
        self.assertTrue(native.mechanism.find("and"))
        self.assertFalse(alternate.mechanism.find("and"))
        self.assertEqual(len(alternate.mechanism.find("not")), 3)
        self.assertEqual(len(alternate.mechanism.find("or")), 1)
        self.assertEqual(native.observation_map, alternate.observation_map)

    def test_authored_operator_constraint_changes_the_actual_graph(self):
        request = with_policy(
            self.request,
            constraints={"allowed_operators": without_and()},
            preferences={"minimize": "gate_count"},
        )
        result = self.select(request)
        self.assertEqual(result.selected_strategy, "de_morgan")
        self.assertEqual(result.checked_candidates, 1)
        self.assertEqual(result.rejected_candidates, 1)
        self.assertEqual(
            result.alternatives[0].constraint_violations, ("operator_not_allowed:and",)
        )
        self.assertFalse(result.candidate.mechanism.find("and"))
        with self.assertRaises(bc.UnsupportedBehaviorError):
            generate_synthetic(request)
        self.assertEqual(
            generate_synthetic(request, config=result.candidate.generator_config),
            result.candidate,
        )

    def test_hard_gate_bound_cannot_be_overridden_by_preference(self):
        request = with_policy(
            self.request,
            constraints={"allowed_operators": without_and(), "max_gate_count": 3},
            preferences={"minimize": "none"},
        )
        result = self.select(request)
        self.assertEqual(result.outcome, "exhausted")
        self.assertIsNone(result.candidate)
        self.assertEqual(result.checked_candidates, 0)
        self.assertEqual(result.rejected_candidates, 2)
        self.assertIn(
            "gate_count_exceeded:6>3", result.alternatives[1].constraint_violations
        )
        self.assertEqual(
            result.to_dict()["search_scope"], "two_whole_program_conjunction_strategies"
        )

    def test_exact_gate_bound_is_inclusive(self):
        request = with_policy(self.request, constraints={"max_gate_count": 3})
        result = self.select(request)
        self.assertEqual(result.selected_strategy, "native")
        self.assertEqual(result.checked_candidates, 1)

    def test_tie_policy_is_stable_even_if_config_starts_with_other_strategy(self):
        request = with_policy(self.request, preferences={"minimize": "none"})
        result = self.select(
            request, config=SyntheticGeneratorConfig(conjunction_strategy="de_morgan")
        )
        self.assertEqual(result.selected_strategy, "native")
        self.assertEqual(result.checked_candidates, 2)
        self.assertEqual(
            self.select(request).selected_strategy, result.selected_strategy
        )

    def test_independent_checker_rejects_faulty_demorgan_rewrite_before_ranking(self):
        def mutated(request, *, config):
            candidate = _generate_synthetic(request, config=config)
            if config.conjunction_strategy == "de_morgan":
                mechanism = replace(
                    candidate.mechanism,
                    nodes=tuple(
                        replace(node, kind="and") if node.kind == "or" else node
                        for node in candidate.mechanism.nodes
                    ),
                )
                candidate = replace(
                    candidate,
                    mechanism=mechanism,
                    component_locks=SYNTHETIC_CATALOG.lock(mechanism),
                )
            return candidate

        with patch(
            "biocompiler.synthesis.selection._generate_synthetic", side_effect=mutated
        ):
            result = self.select()
        self.assertEqual(result.checked_candidates, 2)
        self.assertEqual(result.selected_strategy, "native")
        self.assertEqual(result.alternatives[1].check.outcome, bc.CheckOutcome.FAIL)
        self.assertTrue(result.alternatives[1].check.counterexamples)

    def test_both_execution_failures_exhaust_only_the_declared_search(self):
        def mutated(request, *, config):
            candidate = _generate_synthetic(request, config=config)
            operation = "and" if config.conjunction_strategy == "native" else "or"
            replacement = "or" if operation == "and" else "and"
            mechanism = replace(
                candidate.mechanism,
                nodes=tuple(
                    replace(node, kind=replacement) if node.kind == operation else node
                    for node in candidate.mechanism.nodes
                ),
            )
            return replace(
                candidate,
                mechanism=mechanism,
                component_locks=SYNTHETIC_CATALOG.lock(mechanism),
            )

        with patch(
            "biocompiler.synthesis.selection._generate_synthetic", side_effect=mutated
        ):
            result = self.select()
        self.assertEqual(result.outcome, "exhausted")
        self.assertEqual(result.checked_candidates, 2)
        self.assertEqual(result.rejected_candidates, 2)
        self.assertIsNone(result.candidate)
        self.assertTrue(all(item.check.counterexamples for item in result.alternatives))

    def test_no_conjunction_retains_two_checked_strategy_records(self):
        therapy, cell = cell_model("selection_without_conjunction")
        signal = cell.environment.signal("A")
        action = cell.rest()
        rule = cell.when(signal.present()).do(action)
        request = freeze(
            therapy, cell, ((signal, "cell"),), (("active", rule, action, "cell"),)
        )
        history = cell_history((signal,), ((0, True), (1, False)))
        result = select_synthetic(request, history, until=2)
        self.assertEqual(result.checked_candidates, 2)
        self.assertEqual(result.selected_strategy, "native")
        self.assertEqual(
            result.alternatives[0].candidate.mechanism,
            result.alternatives[1].candidate.mechanism,
        )

    def test_mutated_actual_graph_cannot_bypass_frozen_operator_constraints(self):
        request = with_policy(
            self.request, constraints={"allowed_operators": without_and()}
        )
        candidate = self.select(request).candidate
        mechanism = replace(
            candidate.mechanism,
            nodes=tuple(
                replace(node, kind="and") if node.kind == "or" else node
                for node in candidate.mechanism.nodes
            ),
        )
        wrong = replace(
            candidate,
            mechanism=mechanism,
            component_locks=SYNTHETIC_CATALOG.lock(mechanism),
        )
        result = check_synthetic_candidate(request, wrong, self.history, until=7)
        self.assertEqual(result.outcome, bc.CheckOutcome.FAIL)
        self.assertEqual(result.diagnostics[0].code, "candidate_hard_constraints")

    def test_no_observed_activity_is_unknown_not_exhausted_or_selected(self):
        history = (bc.InputFrame(0, contacts={"x": self.sample(False, False)}),)
        result = select_synthetic(self.request, history, until=7)
        self.assertEqual(result.checked_candidates, 2)
        self.assertEqual(result.outcome, "unknown")
        self.assertIsNone(result.candidate)

    def test_unsupported_source_profile_retains_two_explicit_rejections(self):
        request, sample = fixture(temporal="recently")
        result = select_synthetic(
            request,
            exercised_history(sample),
            until=7,
            config=SyntheticGeneratorConfig(profile_version=TEMPORAL_PROFILE_VERSION),
        )
        self.assertEqual(result.outcome, "unsupported")
        self.assertEqual(result.checked_candidates, 0)
        self.assertTrue(all(item.generation_error for item in result.alternatives))

    def test_unknown_or_malformed_policy_is_never_silently_ignored(self):
        for constraints, preferences in (
            ({"invented": 1}, {}),
            ({}, {"invented": 1}),
            ({"max_gate_count": True}, {}),
            ({"max_gate_count": -1}, {}),
            ({"max_gate_count": None}, {}),
            ({"allowed_operators": "and"}, {}),
            ({"allowed_operators": ["and", "and"]}, {}),
            ({"allowed_operators": ["delay"]}, {}),
            ({}, {"minimize": "biological_cost"}),
        ):
            with self.subTest(constraints=constraints, preferences=preferences):
                request = with_policy(
                    self.request, constraints=constraints, preferences=preferences
                )
                with self.assertRaises(bc.UnsupportedBehaviorError):
                    self.select(request)
                with self.assertRaises(bc.UnsupportedBehaviorError):
                    generate_synthetic(request)

    def test_temporal_contact_scope_and_source_requirements_survive_alternate_graph(
        self,
    ):
        request, history = build_request()
        request = with_policy(
            request, constraints={"allowed_operators": without_and(TEMPORAL_CATALOG)}
        )
        result = select_synthetic(
            request,
            history,
            until=9,
            config=SyntheticGeneratorConfig(profile_version=TEMPORAL_PROFILE_VERSION),
        )
        self.assertEqual(result.selected_strategy, "de_morgan")
        self.assertEqual(
            result.candidate.generator_config.profile_version, TEMPORAL_PROFILE_VERSION
        )
        self.assertTrue(result.candidate.mechanism.find("memory"))
        self.assertTrue(result.candidate.mechanism.find("held_for"))
        self.assertTrue(
            all(
                node.scope == "contact"
                for node in result.candidate.mechanism.find("or")
            )
        )
        self.assertTrue(all(result.candidate.source_map.values()))
        self.assertEqual(
            {
                item
                for ids in result.candidate.behavior_requirement_ids.values()
                for item in ids
            },
            {item.id for item in request.behavior.requirements},
        )

    def test_report_roundtrip_is_deterministic_and_rejects_forged_summaries(self):
        result = self.select()
        self.assertEqual(SyntheticSelectionResult.from_json(result.to_json()), result)
        self.assertEqual(self.select().to_json(), result.to_json())
        for key, value in (
            ("selected_strategy", "de_morgan"),
            ("outcome", "exhausted"),
            ("checked_candidates", 1),
            ("selection_version", "old"),
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                SyntheticSelectionResult.from_dict({**result.to_dict(), key: value})
        wrong = result.to_dict()
        wrong["alternatives"][1]["gate_count"] = 0
        with self.assertRaises(ValueError):
            SyntheticSelectionResult.from_dict(wrong)

    def test_reports_bind_history_horizon_request_and_both_configs(self):
        result = self.select()
        for changes in (
            {"history_fingerprint": "0" * 64},
            {"until": 8},
            {"request_fingerprint": "0" * 64},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                SyntheticSelectionResult.from_dict({**result.to_dict(), **changes})


if __name__ == "__main__":
    unittest.main()
