"""Complete operation authority for mixed exploration and selected-failure replay."""

from dataclasses import replace
import unittest
from unittest.mock import patch

from biocompiler.compiler.verification_workflow import (
    SyntheticVerificationRecord,
    SyntheticVerificationRequest,
    replay_synthetic_verification,
    run_synthetic_verification,
)
from biocompiler.errors import SerializationError
from biocompiler.semantics.evaluator import InputFrame
from biocompiler.verification.evidence import CheckOutcome, DependencySnapshot
from biocompiler.verification.exploration import (
    BooleanInputConfig,
    BooleanInputExplorationReport,
    BooleanObservation,
    FailureSignature,
    enumerate_boolean_histories,
)
from examples.synthetic_verification import (
    ignored_reset,
    mixed_bounds,
    verification_fixture,
)


class SyntheticVerificationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.realization, cls.candidate, cls.history = verification_fixture()
        cls.check_request = SyntheticVerificationRequest(
            cls.realization,
            cls.candidate,
            "check",
            history=cls.history,
            until=9,
        )

    def test_check_json_roundtrip_and_current_replay(self):
        request = SyntheticVerificationRequest.from_json(self.check_request.to_json())
        record = run_synthetic_verification(request)
        self.assertEqual(record.result.outcome, CheckOutcome.PASS)
        imported = SyntheticVerificationRecord.from_json(record.to_json())
        self.assertEqual(
            replay_synthetic_verification(
                imported, expected_request=request
            ).fingerprint,
            record.fingerprint,
        )
        self.assertEqual(
            record.result.dependencies.values["settings"]["verification_mode"],
            "candidate",
        )
        self.assertIn("Historical", record.claim_scope)

    def test_unknown_and_unsupported_are_retained_without_preacceptance(self):
        unknown = run_synthetic_verification(
            replace(self.check_request, history=(self.history[0],))
        )
        self.assertEqual(unknown.result.outcome, CheckOutcome.UNKNOWN)
        from test_synthetic_generation import fixture, exercised_history

        unsupported, sample = fixture(temporal="recently")
        unsupported_candidate = replace(
            self.candidate, request_fingerprint=unsupported.fingerprint
        )
        result = run_synthetic_verification(
            replace(
                self.check_request,
                realization=unsupported,
                candidate=unsupported_candidate,
                history=exercised_history(sample),
                until=7,
            )
        )
        self.assertEqual(result.result.outcome, CheckOutcome.UNSUPPORTED)
        self.assertEqual(
            SyntheticVerificationRecord.from_json(result.to_json()).fingerprint,
            result.fingerprint,
        )

    def test_mixed_bounds_enumerate_cell_reset_and_contact_presence(self):
        bounds = mixed_bounds(self.realization)
        histories = tuple(enumerate_boolean_histories(bounds))
        self.assertEqual(bounds.state_count, 10)
        self.assertEqual(bounds.possible_histories, 100)
        self.assertEqual(len(histories), 100)
        self.assertEqual(
            len({str([frame.to_dict() for frame in history]) for history in histories}),
            100,
        )
        variable = [history[1] for history in histories]
        reset = bounds.cell_observations[0].signal_id
        self.assertEqual(
            {frame.signals[reset].present for frame in variable}, {False, True}
        )
        self.assertTrue(any(not frame.contacts for frame in variable))
        self.assertTrue(
            any(
                frame.contacts
                and not any(sample.present for sample in frame.contacts["x"].values())
                for frame in variable
            )
        )
        for history in histories:
            self.assertEqual(history[-len(bounds.fixed_suffix) :], bounds.fixed_suffix)
        operation = SyntheticVerificationRequest(
            self.realization, self.candidate, "explore", bounds=bounds
        )
        record = run_synthetic_verification(operation)
        self.assertIsInstance(record.result, BooleanInputExplorationReport)
        self.assertTrue(record.result.complete)
        self.assertTrue(record.result.all_passed)
        self.assertEqual(record.result.outcome_counts["pass"], 100)
        self.assertEqual(
            replay_synthetic_verification(
                SyntheticVerificationRecord.from_json(record.to_json()),
                expected_request=operation,
            ).fingerprint,
            record.fingerprint,
        )

    def test_capped_passing_prefix_is_not_complete_or_all_passed(self):
        bounds = mixed_bounds(self.realization, max_histories=3)
        record = run_synthetic_verification(
            SyntheticVerificationRequest(
                self.realization,
                self.candidate,
                "explore",
                bounds=bounds,
            )
        )
        self.assertEqual(record.result.evaluated_histories, 3)
        self.assertEqual(record.result.possible_histories, 100)
        self.assertEqual(record.result.outcome_counts["pass"], 3)
        self.assertFalse(record.result.complete)
        self.assertFalse(record.result.all_passed)
        incomplete_bounds = replace(
            bounds, variable_times=(0,), fixed_suffix=(), max_histories=10
        )
        uncertain = run_synthetic_verification(
            replace(record.request, bounds=incomplete_bounds)
        )
        self.assertTrue(uncertain.result.complete)
        self.assertGreater(uncertain.result.outcome_counts["unknown"], 0)
        self.assertFalse(uncertain.result.all_passed)

    def test_cell_only_space_and_exact_snapshot_inventory(self):
        observation = BooleanObservation("reset")
        bounds = BooleanInputConfig((), (), (0, 1), 2, cell_observations=(observation,))
        self.assertEqual((bounds.state_count, bounds.possible_histories), (2, 4))
        self.assertEqual(len(tuple(enumerate_boolean_histories(bounds))), 4)
        self.assertEqual(
            BooleanInputConfig.from_json(bounds.to_json()).fingerprint,
            bounds.fingerprint,
        )
        with self.assertRaises(SerializationError):
            replace(bounds, fixed_suffix=(InputFrame(2),))
        with self.assertRaises(SerializationError):
            replace(bounds, cell_observations=(observation, observation))
        with self.assertRaises(SerializationError):
            replace(bounds, contact_ids=("x",), observations=(observation,))
        with self.assertRaises(SerializationError):
            replace(bounds, cell_observations=())

    def test_wrong_reset_model_reduces_only_the_selected_inactive_failure(self):
        mutant = ignored_reset(self.candidate, self.realization)
        check = replace(self.check_request, candidate=mutant, mode="model")
        failed = run_synthetic_verification(check)
        self.assertEqual(failed.result.outcome, CheckOutcome.FAIL)
        counterexample = next(
            item
            for item in failed.result.counterexamples
            if item.requirement_id == "memory_readout"
            and item.expected["state"] == "inactive"
        )
        selected = FailureSignature.from_counterexample(counterexample)
        operation = replace(
            check, operation="reduce", signature=selected, max_evaluations=100
        )
        record = run_synthetic_verification(operation)
        self.assertTrue(record.result.one_minimal)
        self.assertLess(len(record.result.history), len(self.history))
        self.assertTrue(selected.matches(record.result.result))
        self.assertEqual(record.result.history[0], self.history[0])
        self.assertEqual(record.result.until, 9)
        self.assertEqual(
            replay_synthetic_verification(
                SyntheticVerificationRecord.from_json(record.to_json()),
                expected_request=operation,
            ).fingerprint,
            record.fingerprint,
        )
        capped = run_synthetic_verification(replace(operation, max_evaluations=1))
        self.assertFalse(capped.result.one_minimal)
        self.assertEqual(capped.result.evaluations, 1)
        with self.assertRaises(SerializationError):
            run_synthetic_verification(replace(operation, candidate=self.candidate))
        # Candidate mode preserves its additional provenance gate rather than
        # relabelling diagnostic model execution as accepted generation.
        structural = run_synthetic_verification(replace(check, mode="candidate"))
        self.assertEqual(structural.result.diagnostics[0].code, "candidate_lineage")

    def test_complete_independent_authority_binds_history_horizon_mode_and_model(self):
        record = run_synthetic_verification(self.check_request)
        for changed in (
            replace(self.check_request, history=(self.history[0],)),
            replace(self.check_request, until=9.0),
            replace(self.check_request, mode="model"),
            replace(
                self.check_request,
                candidate=ignored_reset(self.candidate, self.realization),
                mode="model",
            ),
        ):
            altered = run_synthetic_verification(changed)
            with (
                self.subTest(fingerprint=changed.fingerprint),
                self.assertRaisesRegex(SerializationError, "independent authority"),
            ):
                replay_synthetic_verification(
                    altered, expected_request=self.check_request
                )
        with self.assertRaisesRegex(SerializationError, "complete operation authority"):
            replay_synthetic_verification(record, expected_request=self.realization)

    def test_narrowed_rehashed_campaign_cannot_replay_under_original_bounds(self):
        request = SyntheticVerificationRequest(
            self.realization,
            self.candidate,
            "explore",
            bounds=mixed_bounds(self.realization, max_histories=3),
        )
        for bounds in (
            replace(request.bounds, max_histories=2),
            replace(request.bounds, variable_times=(0,)),
            replace(request.bounds, until=11),
            replace(request.bounds, fixed_suffix=request.bounds.fixed_suffix[:-1]),
        ):
            record = run_synthetic_verification(replace(request, bounds=bounds))
            with self.assertRaisesRegex(SerializationError, "independent authority"):
                replay_synthetic_verification(record, expected_request=request)

    def test_forged_results_and_stale_tool_dependencies_fail_fresh_replay(self):
        record = run_synthetic_verification(self.check_request)
        values = dict(record.result.dependencies.values)
        altered = replace(
            record,
            result=replace(
                record.result,
                dependencies=DependencySnapshot(
                    {
                        **values,
                        "settings": {
                            **values["settings"],
                            "verification_workflow": "forged",
                        },
                    }
                ),
            ),
        )
        with self.assertRaisesRegex(SerializationError, "stale, altered"):
            replay_synthetic_verification(altered, expected_request=self.check_request)
        with patch(
            "biocompiler.verification.realization.CHECKER_VERSION", "changed.v999"
        ):
            with self.assertRaisesRegex(SerializationError, "stale, altered"):
                replay_synthetic_verification(
                    record, expected_request=self.check_request
                )

    def test_strict_json_operation_shapes_and_report_counts(self):
        for mutate in (
            lambda data: data.update(operation="execute_python"),
            lambda data: data.update(mode="trusted_pass"),
            lambda data: data.update(until=None),
            lambda data: data.update(max_evaluations=1),
            lambda data: data.update(extra=True),
            lambda data: data.update(history=[]),
        ):
            data = self.check_request.to_dict()
            mutate(data)
            with self.assertRaises(SerializationError):
                SyntheticVerificationRequest.from_dict(data)
        request = SyntheticVerificationRequest(
            self.realization,
            self.candidate,
            "explore",
            bounds=mixed_bounds(self.realization, max_histories=2),
        )
        record = run_synthetic_verification(request)
        data = record.to_dict()
        data["result"]["complete"] = True
        with self.assertRaises(SerializationError):
            SyntheticVerificationRecord.from_dict(data)
        data = record.to_dict()
        data["result"]["schema_version"] = []
        with self.assertRaises(SerializationError):
            SyntheticVerificationRecord.from_dict(data)


if __name__ == "__main__":
    unittest.main()
