"""Bounded exploration reports coverage honestly and reductions preserve failures."""

from dataclasses import replace
import hashlib
import json
import unittest

from cellweave.errors import SerializationError
from cellweave.ir.serialization import fingerprint
from cellweave.semantics.evaluator import InputFrame, SignalSample
from cellweave.semantics.types import Interval
from cellweave.verification.evidence import (
    CheckDiagnostic,
    CheckOutcome,
    CheckResult,
    Counterexample,
    DependencySnapshot,
    RequirementCoverage,
)
from cellweave.verification.exploration import (
    EXPLORATION_VERSION,
    AdversarialConfig,
    BooleanContactConfig,
    BooleanObservation,
    ExplorationReport,
    FailureSignature,
    HistoryCase,
    ReductionResult,
    enumerate_boolean_histories,
    explore_boolean_histories,
    generate_adversarial_histories,
    reduce_counterexample,
)


def result_for(
    history,
    until,
    outcome=CheckOutcome.PASS,
    *,
    code="selected_failure",
    requirement="response",
    contact=None,
):
    history_hash = hashlib.sha256(
        json.dumps(
            [frame.to_dict() for frame in history],
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
    dependencies = DependencySnapshot(
        {
            **{
                key: "1" * 64
                for key in (
                    "behavior",
                    "behavior_artifact",
                    "contract",
                    "domain",
                    "target",
                    "mechanism",
                    "observation_map",
                )
            },
            "history": history_hash,
            "horizon": {"until": until, "effective": until},
            "checker": "test_checker",
            "model_runner": "test_model",
            "reference_evaluator": "test_evaluator",
            "settings": {"fixture": True},
        }
    )
    diagnostics = (
        ()
        if outcome is CheckOutcome.PASS
        else (
            CheckDiagnostic(
                code,
                "Explicit selected failure or incompleteness.",
                requirement,
                "node",
            ),
        )
    )
    return CheckResult(
        outcome,
        dependencies,
        (requirement,),
        diagnostics=diagnostics,
        coverage=(
            RequirementCoverage(
                requirement,
                1 if outcome is CheckOutcome.PASS else 0,
                1 if outcome is CheckOutcome.PASS else 0,
            ),
        ),
    )


def bounds(*, max_histories=10000):
    return BooleanContactConfig(
        ("object",),
        (BooleanObservation("signal"),),
        (0, 1),
        3,
        (InputFrame(2, contacts={"object": {"signal": SignalSample(present=False)}}),),
        max_histories,
    )


class BooleanExplorationTests(unittest.TestCase):
    def test_full_presence_and_boolean_state_product_has_no_missing_or_duplicate_histories(
        self,
    ):
        config = bounds()
        histories = tuple(enumerate_boolean_histories(config))
        self.assertEqual(config.state_count, 3)
        self.assertEqual(config.possible_histories, 9)
        self.assertEqual(len(histories), 9)
        self.assertEqual(
            len(
                {
                    fingerprint([frame.to_dict() for frame in history])
                    for history in histories
                }
            ),
            9,
        )
        states = {
            json.dumps(history[0].to_dict()["contacts"], sort_keys=True)
            for history in histories
        }
        self.assertEqual(len(states), 3)
        self.assertIn("{}", states)
        self.assertTrue(
            all(history[-1] == config.fixed_suffix[0] for history in histories)
        )
        self.assertEqual(tuple(frame.time for frame in histories[0]), (0, 1, 2))

    def test_report_counts_outcomes_and_coverage_separately_from_enumeration_completion(
        self,
    ):
        config = bounds()

        def evaluate(history, *, until):
            first = history[0].contacts.get("object", {}).get("signal")
            outcome = CheckOutcome.UNKNOWN if first is None else CheckOutcome.PASS
            return result_for(history, until, outcome)

        report = explore_boolean_histories(config, evaluate)
        self.assertTrue(report.complete)
        self.assertFalse(report.all_passed)
        self.assertEqual(
            report.outcome_counts,
            {"pass": 6, "fail": 0, "unknown": 3, "unsupported": 0},
        )
        self.assertEqual(report.coverage_totals[0].activation_deadlines_checked, 6)
        self.assertEqual(report.coverage_totals[0].inactive_deadlines_checked, 6)
        self.assertEqual(report.evaluated_histories, 9)
        self.assertNotIn("history", report.shared_dependencies)
        self.assertIn("not whole-profile", report.claim_scope)
        self.assertEqual(ExplorationReport.from_json(report.to_json()), report)
        with self.assertRaises(TypeError):
            report.shared_dependencies["contract"] = "2" * 64
        with self.assertRaises(TypeError):
            report.outcome_counts["pass"] = 9

    def test_capped_prefix_never_claims_exhaustive_completion_or_all_passed(self):
        config = BooleanContactConfig(
            ("x", "y"),
            (BooleanObservation("a"), BooleanObservation("b")),
            (0, 1, 2, 3, 4, 5),
            6,
            max_histories=7,
        )
        report = explore_boolean_histories(
            config, lambda history, until: result_for(history, until)
        )
        self.assertEqual(config.state_count, 25)
        self.assertEqual(report.possible_histories, 25**6)
        self.assertEqual(report.evaluated_histories, 7)
        self.assertFalse(report.complete or report.all_passed)
        self.assertEqual(report.outcome_counts["pass"], 7)
        changed = report.to_dict()
        changed["complete"] = True
        with self.assertRaisesRegex(SerializationError, "Inconsistent"):
            ExplorationReport.from_dict(changed)

    def test_callback_results_must_match_history_horizon_dependencies_and_requirements(
        self,
    ):
        config = bounds()

        def stale(history, *, until):
            result = result_for(history, until)
            return replace(
                result,
                dependencies=DependencySnapshot(
                    {**result.dependencies.to_dict(), "history": "0" * 64}
                ),
            )

        def horizon(history, *, until):
            return result_for(history, until + 1)

        def changed_model(history, *, until):
            result = result_for(history, until)
            return replace(
                result,
                dependencies=DependencySnapshot(
                    {
                        **result.dependencies.to_dict(),
                        "model_runner": str(fingerprint(history[-2].to_dict())),
                    }
                ),
            )

        def changed_requirements(history, *, until):
            return result_for(
                history,
                until,
                requirement="changed" if history[1].contacts else "response",
            )

        for callback in (
            stale,
            horizon,
            changed_model,
            changed_requirements,
            lambda history, until: True,
        ):
            with (
                self.subTest(callback=callback.__name__),
                self.assertRaises(SerializationError),
            ):
                explore_boolean_histories(config, callback)

    def test_unicode_ids_use_the_existing_checkers_history_hash_format(self):
        config = replace(bounds(), contact_ids=("細胞",), fixed_suffix=())
        report = explore_boolean_histories(
            config, lambda history, until: result_for(history, until)
        )
        self.assertTrue(report.all_passed)

    def test_lone_unicode_surrogates_are_rejected_in_configs_and_results(self):
        bad = "invalid" + chr(0xD800)
        with self.assertRaisesRegex(SerializationError, "UTF-8"):
            BooleanObservation(bad)
        with self.assertRaisesRegex(SerializationError, "UTF-8"):
            replace(bounds(), contact_ids=(bad,))
        data = bounds().to_dict()
        data["contact_ids"] = [bad]
        with self.assertRaisesRegex(SerializationError, "UTF-8"):
            BooleanContactConfig.from_json(json.dumps(data))

        def evaluate(history, *, until):
            result = result_for(history, until, CheckOutcome.UNKNOWN)
            return replace(
                result,
                diagnostics=(replace(result.diagnostics[0], message=bad),),
            )

        with self.assertRaisesRegex(SerializationError, "UTF-8"):
            explore_boolean_histories(bounds(), evaluate)

    def test_config_rejects_invalid_times_observations_suffixes_and_imports(self):
        config = bounds()
        self.assertEqual(BooleanContactConfig.from_json(config.to_json()), config)
        for changes in (
            {"variable_times": (1, 2)},
            {"variable_times": (0, 0)},
            {"variable_times": (0, True)},
            {"until": 0},
            {"max_histories": 0},
            {"max_histories": True},
            {
                "observations": (
                    BooleanObservation("signal"),
                    BooleanObservation("signal"),
                )
            },
            {
                "fixed_suffix": (
                    InputFrame(2, contacts={"object": {"signal": SignalSample()}}),
                )
            },
            {
                "fixed_suffix": (
                    InputFrame(
                        2, contacts={"other": {"signal": SignalSample(present=True)}}
                    ),
                )
            },
        ):
            with self.subTest(changes=changes), self.assertRaises(SerializationError):
                replace(config, **changes)
        for field, value in (
            ("observations", {}),
            ("fixed_suffix", [None]),
            ("variable_times", "0,1"),
            ("contact_ids", None),
        ):
            data = config.to_dict()
            data[field] = value
            with self.subTest(field=field), self.assertRaises(SerializationError):
                BooleanContactConfig.from_dict(data)


class AdversarialHistoryTests(unittest.TestCase):
    def test_seeded_histories_cover_named_transitions_and_separate_incomplete_case(
        self,
    ):
        config = AdversarialConfig(
            replace(bounds(), variable_times=(0, 0.25, 0.5, 1), fixed_suffix=()), 123, 5
        )
        cases = generate_adversarial_histories(config)
        self.assertEqual(cases, generate_adversarial_histories(config))
        self.assertEqual(len(cases), 10)
        named = {case.id: case for case in cases}
        active = named["startup_active"].history[0]
        self.assertTrue(active.contacts["object"]["signal"].present)
        oscillation = named["rapid_oscillation"].history
        self.assertEqual(
            [frame.contacts["object"]["signal"].present for frame in oscillation],
            [True, False, True, False],
        )
        dropout = named["dropout_reappearance"].history
        self.assertTrue(
            dropout[0].contacts and not dropout[1].contacts and dropout[2].contacts
        )
        incomplete = named["incomplete_observation"]
        self.assertTrue(incomplete.intentionally_incomplete)
        self.assertIsNone(incomplete.history[0].contacts["object"]["signal"].present)
        self.assertEqual(sum(case.intentionally_incomplete for case in cases), 1)
        self.assertTrue(
            all(case.config_fingerprint == config.fingerprint for case in cases)
        )
        self.assertEqual(AdversarialConfig.from_json(config.to_json()), config)
        self.assertTrue(
            all(HistoryCase.from_json(case.to_json()) == case for case in cases)
        )
        other = generate_adversarial_histories(replace(config, seed=124))
        self.assertNotEqual(
            [case.history for case in cases if case.kind == "seeded"],
            [case.history for case in other if case.kind == "seeded"],
        )
        self.assertEqual(
            [case.history for case in cases if case.kind != "seeded"],
            [case.history for case in other if case.kind != "seeded"],
        )

    def test_adversarial_sampling_does_not_allocate_its_huge_cartesian_product(self):
        config = AdversarialConfig(
            BooleanContactConfig(
                tuple(f"c{i}" for i in range(8)),
                tuple(BooleanObservation(f"s{i}") for i in range(8)),
                tuple(range(16)),
                16,
                max_histories=1,
            ),
            0,
            1,
        )
        cases = generate_adversarial_histories(config)
        self.assertEqual(len(cases), 6)
        self.assertGreater(config.bounds.possible_histories, 10**200)
        self.assertTrue(all(len(case.history) == 16 for case in cases))


class CounterexampleReductionTests(unittest.TestCase):
    def test_deletion_preserves_initial_state_horizon_and_selected_failure_not_unknown(
        self,
    ):
        history = tuple(
            InputFrame(
                time,
                contacts={"object": {"signal": SignalSample(present=bool(time % 2))}},
            )
            for time in range(6)
        )
        calls = []

        def evaluate(frames, *, until):
            calls.append((frames, until))
            times = {frame.time for frame in frames}
            if 4 not in times:
                return result_for(
                    frames, until, CheckOutcome.UNKNOWN, code="incomplete_observation"
                )
            if 2 not in times:
                return result_for(
                    frames, until, CheckOutcome.FAIL, code="another_failure"
                )
            return result_for(frames, until, CheckOutcome.FAIL)

        initial = evaluate(history, until=6)
        signature = FailureSignature.from_diagnostic(initial.diagnostics[0])
        reduced = reduce_counterexample(history, 6, evaluate, signature)
        self.assertEqual(tuple(frame.time for frame in reduced.history), (0, 2, 4))
        self.assertTrue(reduced.one_minimal)
        self.assertEqual(reduced.history[0], history[0])
        self.assertTrue(all(until == 6 for _, until in calls))
        self.assertTrue(signature.matches(reduced.result))
        for index in range(1, len(reduced.history)):
            trial = reduced.history[:index] + reduced.history[index + 1 :]
            self.assertFalse(signature.matches(evaluate(trial, until=6)))
        self.assertEqual(ReductionResult.from_json(reduced.to_json()), reduced)
        self.assertEqual(FailureSignature.from_json(signature.to_json()), signature)

    def test_response_signature_keeps_obligation_object_and_state_without_fixing_failure_time(
        self,
    ):
        expected = {"state": "active", "range": Interval(0.9, 1.1).to_dict()}
        example = Counterexample("response", 2, "x", expected, 0, "rule", "spec")
        signature = FailureSignature.from_counterexample(example)
        self.assertEqual(
            signature,
            FailureSignature.from_counterexample(replace(example, time=3, actual=0.1)),
        )
        for mutation in (
            replace(example, contact_id="y"),
            replace(example, specification_id="other"),
            replace(example, expected={**expected, "state": "inactive"}),
        ):
            self.assertNotEqual(
                signature, FailureSignature.from_counterexample(mutation)
            )

    def test_budget_exhaustion_and_different_initial_failure_never_claim_minimality(
        self,
    ):
        history = tuple(InputFrame(time) for time in range(4))

        def evaluate(frames, until):
            return result_for(frames, until, CheckOutcome.FAIL)

        signature = FailureSignature.from_diagnostic(
            evaluate(history, 5).diagnostics[0]
        )
        reduced = reduce_counterexample(
            history, 5, evaluate, signature, max_evaluations=1
        )
        self.assertEqual(reduced.history, history)
        self.assertEqual(reduced.evaluations, 1)
        self.assertFalse(reduced.one_minimal)
        with self.assertRaisesRegex(SerializationError, "Initial history"):
            reduce_counterexample(
                history, 5, evaluate, replace(signature, code="other")
            )
        completed = reduce_counterexample(history, 5, evaluate, signature)
        self.assertEqual(completed.history, history[:1])
        self.assertTrue(completed.one_minimal)

    def test_import_rejects_changed_requirement_inventory_and_reducer_policy(self):
        history = tuple(InputFrame(time) for time in range(3))

        def evaluate(frames, *, until):
            return result_for(frames, until, CheckOutcome.FAIL)

        signature = FailureSignature.from_diagnostic(
            evaluate(history, until=4).diagnostics[0]
        )
        reduced = reduce_counterexample(history, 4, evaluate, signature)
        self.assertEqual(reduced.reducer_version, EXPLORATION_VERSION)
        data = reduced.to_dict()
        data["result"]["checked_requirement_ids"].append("invented_requirement")
        with self.assertRaisesRegex(SerializationError, "requirement inventory"):
            ReductionResult.from_json(json.dumps(data))
        data = reduced.to_dict()
        data["reducer_version"] = "different-policy"
        with self.assertRaisesRegex(SerializationError, "policy version"):
            ReductionResult.from_json(json.dumps(data))

    def test_reduction_rejects_stale_callback_results_or_changed_model_dependencies(
        self,
    ):
        history = tuple(InputFrame(time) for time in range(3))
        initial = result_for(history, 4, CheckOutcome.FAIL)
        signature = FailureSignature.from_diagnostic(initial.diagnostics[0])
        with self.assertRaisesRegex(SerializationError, "stale"):
            reduce_counterexample(history, 4, lambda frames, until: initial, signature)

        def changed(frames, *, until):
            result = result_for(frames, until, CheckOutcome.FAIL)
            return replace(
                result,
                dependencies=DependencySnapshot(
                    {
                        **result.dependencies.to_dict(),
                        "mechanism": str(len(frames)) * 64,
                    }
                ),
            )

        with self.assertRaisesRegex(SerializationError, "dependencies"):
            reduce_counterexample(history, 4, changed, signature)


if __name__ == "__main__":
    unittest.main()
