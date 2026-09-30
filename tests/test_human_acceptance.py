"""Boundary, provenance and non-vacuity checks for conjunctive acceptance."""

from contextlib import redirect_stdout
from dataclasses import FrozenInstanceError, replace
import io
from pathlib import Path
import tempfile
import unittest

import biocompiler as bc
from biocompiler.cli import main as cli_main
from examples.human_acceptance import example_trace, make_human_acceptance, sample
from examples.human_deployment import co_payload_fixture, make_human_deployment


class HumanAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.request = make_human_acceptance()
        self.trace = example_trace()
        self.contract = self.request.acceptance

    def check(self, trace=None, request=None):
        return bc.check_human_acceptance(
            request or self.request, self.trace if trace is None else trace
        )

    def assertDiagnostic(self, result, outcome, prefix):
        self.assertEqual(result.outcome, outcome, result.diagnostics)
        self.assertTrue(
            any(item.startswith(prefix) for item in result.diagnostics),
            result.diagnostics,
        )

    def test_roundtrip_all_records_and_frozen_authority(self):
        result = self.check()
        self.assertEqual(result.outcome, "pass", result.diagnostics)
        for artifact in (
            self.request,
            self.contract,
            self.contract.input_availability,
            self.contract.shutdown,
            self.trace[0],
            result,
        ):
            restored = type(artifact).from_json(artifact.to_json())
            self.assertEqual(restored.to_dict(), artifact.to_dict())
            self.assertEqual(restored.fingerprint, artifact.fingerprint)
            with self.assertRaises(FrozenInstanceError):
                artifact.schema_version = "forged"
        self.assertEqual(result.to_dict()["actuator_support"], "unimplemented")
        self.assertEqual(result.to_dict()["biological_applicability"], "unestablished")
        self.assertTrue(result.unresolved_evidence)

    def test_strict_import_rejects_missing_extra_versions_and_promotion(self):
        for artifact in (
            self.request,
            self.contract,
            self.contract.input_availability,
            self.contract.shutdown,
            self.trace[0],
            self.check(),
        ):
            for key in artifact.to_dict():
                data = artifact.to_dict()
                del data[key]
                with (
                    self.subTest(artifact=type(artifact), key=key),
                    self.assertRaises(bc.SerializationError),
                ):
                    type(artifact).from_dict(data)
            for patch in ({"validated": True}, {"schema_version": "future"}):
                with self.assertRaises(bc.SerializationError):
                    type(artifact).from_dict({**artifact.to_dict(), **patch})
        for artifact, patch in (
            (self.contract, {"combination": "shutdown_overrides_source"}),
            (self.contract.shutdown, {"overrides_source_guard": True}),
            (self.check(), {"actuator_support": "validated"}),
        ):
            with self.assertRaises(bc.SerializationError):
                type(artifact).from_dict({**artifact.to_dict(), **patch})

    def test_nulls_units_nonfinite_and_invalid_strings_fail(self):
        for kwargs in (
            {"input_status": "cell_unavailable"},
            {"input_value": None},
            {"input_status": []},
            {"control_status": "off"},
        ):
            with self.assertRaises(bc.SerializationError):
                replace(self.trace[0], **kwargs)
        for kwargs in (
            {"output_value": bc.Duration(1)},
            {"context_value": bc.Concentration(1)},
            {"input_value": bc.Level(1)},
        ):
            with self.assertRaises(bc.TypeMismatchError):
                self.check((replace(self.trace[0], **kwargs), *self.trace[1:]))
        with self.assertRaises(bc.SerializationError):
            replace(self.contract.shutdown, request_definition="bad\ud800")
        data = self.trace[0].to_dict()
        data["time"]["value"] = float("nan")
        with self.assertRaises(bc.SerializationError):
            bc.AcceptanceSample.from_dict(data)

    def test_stale_behavior_role_compartment_and_measurement_alias_rejected(self):
        with self.assertRaises(bc.SerializationError):
            replace(
                self.request,
                acceptance=replace(self.contract, behavior_fingerprint="0" * 64),
            )
        observable = self.contract.healthy_measurement.observable
        for patch in (
            {"role": "unrelated"},
            {"compartment": "nucleus"},
            {
                "id": self.request.behavior_request.contract.input_measurement.observable.id
            },
        ):
            with self.assertRaises(bc.SerializationError):
                replace(
                    self.request,
                    acceptance=replace(
                        self.contract,
                        healthy_measurement=replace(
                            self.contract.healthy_measurement,
                            observable=replace(observable, **patch),
                        ),
                    ),
                )
        with self.assertRaises(bc.SerializationError):
            replace(
                self.contract,
                healthy_measurement=replace(
                    self.contract.healthy_measurement, access="cell"
                ),
            )

    def test_healthy_domain_and_conflicting_rate_bounds_rejected(self):
        with self.assertRaises(bc.SerializationError):
            replace(self.contract, healthy_range=self.contract.context_domain)
        for patch in (
            {"background_ceiling": bc.ProductionRate(0.2, unit="molecules/s")},
            {"peak_ceiling": bc.ProductionRate(1, unit="molecules/s")},
            {"max_response_duration": bc.Duration(0)},
        ):
            with self.assertRaises(bc.SerializationError):
                replace(self.request, acceptance=replace(self.contract, **patch))
        with self.assertRaises(bc.SerializationError):
            replace(
                self.request,
                acceptance=replace(
                    self.contract,
                    shutdown=replace(
                        self.contract.shutdown, response_delay=bc.Duration(16)
                    ),
                ),
            )

    def test_unknown_evidence_reference_rejected_and_citations_never_verified(self):
        claim = replace(
            self.contract.bounds_support, basis="cited", evidence_ids=("missing",)
        )
        with self.assertRaises(bc.SerializationError):
            replace(
                self.request, acceptance=replace(self.contract, bounds_support=claim)
            )
        changed = replace(
            self.request,
            acceptance=replace(
                self.contract,
                bounds_support=replace(self.contract.bounds_support, basis="assumed"),
            ),
        )
        self.assertIn(
            "acceptance.bounds_support", self.check(request=changed).unresolved_evidence
        )

    def test_peak_bound_applies_during_activation_and_recovery_grace(self):
        for time, cue in ((2, 6), (6.5, 0)):
            trace = sorted(
                (*self.trace, sample(time, cue=cue, rate=4.01)),
                key=lambda item: item.time.canonical_value,
            )
            self.assertDiagnostic(self.check(trace), "fail", "peak_ceiling_exceeded")

    def test_same_predicate_values_do_not_restart_activation_deadline(self):
        trace = list(self.trace)
        trace[2] = sample(3, cue=8)
        trace.insert(2, sample(2, cue=7))
        self.assertDiagnostic(self.check(trace), "fail", "active_range_violation_at:3")

    def test_source_transition_at_deadline_replaces_pending_activation(self):
        trace = list(self.trace)
        trace[2] = sample(3)
        trace[3] = sample(6)
        result = self.check(trace)
        self.assertDiagnostic(result, "unknown", "unexercised_active_interval")
        self.assertFalse(any("range_violation" in item for item in result.diagnostics))

    def test_each_prohibition_scenario_needs_positive_coverage(self):
        for mode, prefix in (
            ("healthy", "unexercised_healthy_interval"),
            ("loss", "unexercised_input_loss_recovered_interval"),
        ):
            trace = (
                [replace(item, context_value=bc.Level(1)) for item in self.trace]
                if mode == "healthy"
                else list(self.trace)
            )
            if mode == "loss":
                trace[5] = sample(8)
            self.assertDiagnostic(self.check(trace), "unknown", prefix)

    def test_peak_exact_boundary_is_allowed_during_grace(self):
        # Starting secretion earlier lengthens its bout; supply a compatible bound.
        request = replace(
            self.request,
            acceptance=replace(self.contract, max_response_duration=bc.Duration(5)),
        )
        trace = (*self.trace[:2], sample(2, cue=6, rate=4), *self.trace[2:])
        self.assertEqual(self.check(trace, request).outcome, "pass")

    def test_background_ceiling_applies_to_initial_and_healthy_intervals(self):
        for index in (0, 4):
            trace = list(self.trace)
            trace[index] = replace(
                trace[index], output_value=bc.ProductionRate(0.11, unit="molecules/s")
            )
            self.assertDiagnostic(
                self.check(trace), "fail", "healthy_background_exceeded"
            )

    def test_healthy_context_does_not_override_active_source_rule(self):
        for output in (0, 2.5, None):
            trace = list(self.trace)
            trace[2] = sample(3, cue=6, rate=output, context=0)
            result = self.check(trace)
            self.assertDiagnostic(
                result, "fail", "required_active_conflicts_with_healthy"
            )

    def test_maximum_bout_is_continuous_across_samples_and_input_changes(self):
        self.assertEqual(self.check().outcome, "pass")  # [3,7) is exactly four seconds.
        request = replace(
            self.request,
            acceptance=replace(self.contract, max_response_duration=bc.Duration(3.99)),
        )
        self.assertDiagnostic(
            self.check(request=request), "fail", "response_duration_exceeded"
        )
        split = sorted(
            (*self.trace, sample(4, cue=7, rate=2.6), sample(5, cue=8, rate=2.2)),
            key=lambda item: item.time.canonical_value,
        )
        self.assertDiagnostic(
            self.check(split, request), "fail", "response_duration_exceeded"
        )

    def test_active_persistence_and_recovery_remain_required(self):
        early_stop = (*self.trace[:3], sample(4, cue=6, rate=0), *self.trace[3:])
        self.assertDiagnostic(self.check(early_stop), "fail", "active_range_violation")
        trace = list(self.trace)
        trace[4] = sample(7, rate=2.5)
        self.assertDiagnostic(self.check(trace), "fail", "inactive_range_violation")

    def test_input_loss_deadline_checked_without_sample_at_deadline(self):
        trace = list(self.trace)
        trace[5] = sample(8, cue=None, rate=0.5, input_status="cell_unavailable")
        self.assertDiagnostic(
            self.check(trace), "fail", "input_loss_recovered_background_exceeded_at:9"
        )
        trace.insert(6, sample(9, cue=None, input_status="cell_unavailable"))
        self.assertEqual(self.check(trace).outcome, "pass")

    def test_evaluator_missing_input_is_unknown_not_zero_or_cell_failure(self):
        trace = list(self.trace)
        trace[5] = sample(8, cue=None, input_status="unobserved")
        result = self.check(trace)
        self.assertDiagnostic(result, "unknown", "input_unobserved")
        self.assertNotIn("input_loss_recovered", result.coverage)

    def test_reacquisition_restarts_timing_without_inventing_prior_guard(self):
        # Reacquisition at 10 starts a new activation clock, while a later
        # shutdown request remains an additional requirement.
        trace = list(self.trace)
        trace[6] = sample(10, cue=6)
        trace.insert(7, sample(11, cue=6, rate=0))
        result = self.check(trace)
        self.assertFalse(
            any("active_range_violation_at:11" in item for item in result.diagnostics)
        )
        # Maintain the cue to its deadline to exercise its actual requirement.
        trace[8] = sample(12, cue=6, control="shutdown")
        self.assertDiagnostic(self.check(trace), "fail", "active_range_violation_at:12")

    def test_shutdown_latches_and_later_clear_does_not_cancel_it(self):
        trace = list(self.trace)
        trace[-1] = sample(16, rate=0.2, control="clear")
        self.assertDiagnostic(
            self.check(trace), "fail", "shutdown_background_exceeded_at:16"
        )

    def test_repeated_shutdown_requests_do_not_restart_deadline(self):
        trace = list(self.trace)
        trace[-2] = sample(12, rate=0.2, control="shutdown")
        trace.insert(-1, sample(12.5, rate=0.2, control="shutdown"))
        self.assertDiagnostic(
            self.check(trace), "fail", "shutdown_background_exceeded_at:13"
        )

    def test_known_active_shutdown_conflict_is_explicit(self):
        trace = list(self.trace)
        trace[2] = sample(3, cue=6, rate=2.5, control="shutdown")
        self.assertDiagnostic(
            self.check(trace), "fail", "required_active_conflicts_with_shutdown_at:4"
        )

    def test_unknown_measurements_do_not_hide_known_prohibitions(self):
        for patch in (
            {"input_value": bc.Concentration(100, unit="nM")},
            {"context_value": None},
            {"context_value": bc.Level(10)},
            {"control_status": "unobserved"},
        ):
            trace = list(self.trace)
            trace[2] = replace(trace[2], **patch)
            self.assertEqual(self.check(trace).outcome, "unknown")
            trace[2] = replace(
                trace[2], output_value=bc.ProductionRate(5, unit="molecules/s")
            )
            self.assertDiagnostic(self.check(trace), "fail", "peak_ceiling_exceeded")

    def test_missing_output_and_negative_grace_output(self):
        trace = list(self.trace)
        trace[2] = replace(trace[2], output_value=None)
        self.assertDiagnostic(self.check(trace), "unknown", "output_unobserved")
        trace = (*self.trace[:2], sample(2, cue=6, rate=-0.01), *self.trace[2:])
        self.assertDiagnostic(self.check(trace), "fail", "negative_secretion_rate")

    def test_positive_duration_coverage_and_final_horizon_required(self):
        self.assertDiagnostic(
            self.check(self.trace[:-1]), "unknown", "trace_ends_before_declared_horizon"
        )
        trace = list(self.trace)
        trace[-2] = sample(12)
        trace[-1] = sample(16, control="shutdown")
        self.assertDiagnostic(
            self.check(trace), "unknown", "unexercised_shutdown_interval"
        )
        self.assertDiagnostic(
            self.check((sample(0), sample(16))),
            "unknown",
            "unexercised_active_interval",
        )

    def test_initialization_order_horizon_and_duplicate_times(self):
        for trace in (
            (),
            self.trace[1:],
            (self.trace[0], self.trace[0]),
            (*self.trace, sample(17)),
        ):
            with self.assertRaises(bc.SerializationError):
                self.check(trace)
        self.assertDiagnostic(
            self.check((sample(0, cue=6), *self.trace[1:])),
            "fail",
            "initial_input_must_be_available_and_inactive",
        )
        self.assertDiagnostic(
            self.check((sample(0, control="shutdown"), *self.trace[1:])),
            "fail",
            "initial_control_must_be_clear",
        )

    def test_fractional_deadline_and_latest_transition_boundary(self):
        # Exact decimal arithmetic: 8.1 + 0.2 is the represented 8.3 boundary.
        request = replace(
            self.request,
            acceptance=replace(
                self.contract,
                input_availability=replace(
                    self.contract.input_availability, response_delay=bc.Duration(0.2)
                ),
            ),
        )
        trace = list(self.trace)
        trace[5] = sample(8.1, cue=None, rate=0.5, input_status="cell_unavailable")
        trace.insert(6, sample(8.3, cue=None, input_status="cell_unavailable"))
        self.assertEqual(self.check(trace, request).outcome, "pass")
        trace[6] = sample(8.31, cue=None, input_status="cell_unavailable")
        self.assertDiagnostic(
            self.check(trace, request),
            "fail",
            "input_loss_recovered_background_exceeded_at:83/10",
        )

    def test_deployment_unknown_unsupported_and_failure_are_retained(self):
        unknown = make_human_deployment().deployment
        deployment = self.request.deployment_request
        for contract, expected in (
            (replace(deployment.deployment, exposures=unknown.exposures), "unknown"),
            (
                replace(deployment.deployment, co_payloads=(co_payload_fixture(),)),
                "unsupported",
            ),
        ):
            request = replace(
                self.request,
                deployment_request=replace(deployment, deployment=contract),
            )
            self.assertEqual(self.check(request=request).outcome, expected)
            trace = (*self.trace[:2], sample(2, cue=6, rate=5), *self.trace[2:])
            self.assertEqual(self.check(trace, request).outcome, "fail")

    def test_identity_tracks_constraints_deployment_and_observations(self):
        result = self.check()
        self.assertTrue(result.is_current(self.request, self.trace))
        request = replace(
            self.request,
            acceptance=replace(self.contract, max_response_duration=bc.Duration(5)),
        )
        self.assertFalse(result.is_current(request, self.trace))
        trace = (*self.trace[:-1], sample(16, context=0))
        self.assertFalse(result.is_current(self.request, trace))
        deployment = self.request.deployment_request
        request = replace(
            self.request,
            deployment_request=replace(
                deployment,
                deployment=replace(
                    deployment.deployment,
                    unintended_recipients=replace(
                        deployment.deployment.unintended_recipients,
                        description="Changed recipient concern",
                    ),
                ),
            ),
        )
        self.assertFalse(result.is_current(request, self.trace))

    def test_imported_pass_never_changes_fresh_acceptance(self):
        imported = bc.HumanAcceptanceResult.from_json(self.check().to_json())
        self.assertEqual(imported.outcome, "pass")
        trace = (*self.trace[:2], sample(2, cue=6, rate=5), *self.trace[2:])
        self.assertEqual(self.check(trace).outcome, "fail")
        with self.assertRaises(bc.SerializationError):
            replace(imported, coverage=("active",))

    def test_compile_retains_unimplemented_shutdown_and_missing_evidence(self):
        with self.assertRaises(bc.CompilationUnavailableError) as error:
            bc.compile(self.request)
        codes = {item.code for item in error.exception.diagnostics}
        self.assertNotIn("human_acceptance_contract_missing", codes)
        self.assertTrue(
            {
                "external_shutdown_actuator_unimplemented",
                "input_loss_response_unimplemented",
                "human_acceptance_empirical_support_unestablished",
                "deployment_empirical_support_unestablished",
            }
            <= codes
        )

    def test_incomplete_human_request_reports_missing_acceptance_authority(self):
        with self.assertRaises(bc.CompilationUnavailableError) as error:
            bc.compile(self.request.deployment_request)
        self.assertIn(
            "human_acceptance_contract_missing",
            {item.code for item in error.exception.diagnostics},
        )

    def test_cli_inspects_all_new_artifacts_without_promoting_results(self):
        artifacts = (
            self.request,
            self.contract,
            self.contract.input_availability,
            self.contract.shutdown,
            self.trace[0],
            self.check(),
        )
        with tempfile.TemporaryDirectory() as directory:
            for index, artifact in enumerate(artifacts):
                path = Path(directory) / f"{index}.json"
                path.write_text(artifact.to_json())
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(cli_main(["inspect", str(path)]), 0)
                if isinstance(artifact, bc.HumanAcceptanceResult):
                    self.assertIn("rerun check_human_acceptance", output.getvalue())


if __name__ == "__main__":
    unittest.main()
