"""Source correspondence, physical observations and bounded secretion semantics."""

from contextlib import redirect_stdout
from dataclasses import FrozenInstanceError, replace
import io
import json
from pathlib import Path
import tempfile
import unittest

import biocompiler as bc
from biocompiler.cli import main as cli_main
from examples.human_behavior import example_trace, make_human_behavior, sample
from examples.human_target import make_human_target


def rate(value):
    return bc.ProductionRate(value, unit="molecules/s")


def rates(lower, upper):
    return bc.Interval(rate(lower), rate(upper), type=bc.ProductionRate)


class HumanBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.request = make_human_behavior()
        self.contract = self.request.contract
        self.trace = example_trace()

    def bind(self, **changes):
        return replace(self.request, contract=replace(self.contract, **changes))

    def source_change(self, node_id, **changes):
        original = self.request.build_request.intent
        intent = replace(
            original,
            nodes=tuple(
                replace(node, **changes) if node.id == node_id else node
                for node in original.nodes
            ),
        )
        return replace(
            self.request,
            build_request=bc.BuildRequest.freeze(
                intent, target=self.request.target, artifact_scope="complete_payload"
            ),
        )

    def test_roundtrip_retains_source_and_units(self):
        restored = bc.HumanBehaviorRequest.from_json(self.request.to_json())
        self.assertEqual(restored.fingerprint, self.request.fingerprint)
        self.assertEqual(
            restored.build_request.intent.to_dict(),
            self.request.build_request.intent.to_dict(),
        )
        self.assertEqual(restored.contract.predicate.threshold.unit, "nM")
        self.assertEqual(
            restored.contract.response.active_range.lower.unit, "molecules/s"
        )
        for artifact in (
            self.contract,
            self.contract.input_measurement,
            self.contract.predicate,
            self.trace[0],
        ):
            self.assertEqual(type(artifact).from_json(artifact.to_json()), artifact)

    def test_missing_fields_unknown_keys_and_versions_rejected(self):
        for artifact in (
            self.request,
            self.contract,
            self.contract.input_measurement,
            self.contract.predicate,
            self.trace[0],
        ):
            for key in artifact.to_dict():
                with self.subTest(artifact=type(artifact), missing=key):
                    data = artifact.to_dict()
                    del data[key]
                    with self.assertRaises(bc.SerializationError):
                        type(artifact).from_dict(data)
            for change in ({"schema_version": "future"}, {"validated": True}):
                data = {**artifact.to_dict(), **change}
                with self.assertRaises(bc.SerializationError):
                    type(artifact).from_dict(data)

    def test_fixed_lifecycle_cannot_be_relabelled(self):
        for key in (
            "profile",
            "initialization",
            "persistence",
            "termination",
            "retrigger",
        ):
            data = self.contract.to_dict()
            data[key] = "arbitrary"
            with self.subTest(key=key), self.assertRaises(bc.SerializationError):
                bc.ConditionalSecretionContract.from_dict(data)

    def test_duplicate_json_nonfinite_and_bad_unicode_rejected(self):
        document = self.request.to_json()
        with self.assertRaises(bc.SerializationError):
            bc.HumanBehaviorRequest.from_json(
                document.replace(
                    '"product": "declared_product"',
                    '"product": "declared_product", "product": "other"',
                )
            )
        with self.assertRaises(bc.SerializationError):
            replace(self.contract.input_measurement, meaning="bad\ud800")
        for value in (float("inf"), float("nan")):
            data = self.trace[0].to_dict()
            data["input_value"]["value"] = value
            with self.assertRaises(bc.SerializationError):
                bc.SecretionSample.from_dict(data)

    def test_immutable_and_every_contract_dimension_changes_identity(self):
        with self.assertRaises(FrozenInstanceError):
            self.contract.product = "another"
        changes = (
            {"horizon": bc.Duration(11)},
            {
                "input_measurement": replace(
                    self.contract.input_measurement,
                    method="Another declared measurement",
                )
            },
            {
                "predicate": replace(
                    self.contract.predicate, threshold=bc.Concentration(4, unit="nM")
                )
            },
            {"initial_range": rates(0, 0.01)},
            {
                "response": replace(
                    self.contract.response, max_activation_delay=bc.Duration(1)
                )
            },
            {
                "response_support": replace(
                    self.contract.response_support, limitations="Different uncertainty"
                )
            },
        )
        for change in changes:
            with self.subTest(change=change):
                self.assertNotEqual(
                    self.bind(**change).fingerprint, self.request.fingerprint
                )
        dna = replace(self.request.target, payload_format=bc.PayloadFormat.DNA)
        self.assertNotEqual(
            replace(
                self.request,
                build_request=replace(self.request.build_request, target=dna),
            ).fingerprint,
            self.request.fingerprint,
        )

    def test_evaluator_only_input_cannot_drive_the_cell(self):
        with self.assertRaises(bc.SerializationError):
            self.bind(
                input_measurement=replace(
                    self.contract.input_measurement, access="external_evaluator"
                )
            )
        with self.assertRaises(bc.SerializationError):
            self.bind(
                output_measurement=replace(
                    self.contract.output_measurement, access="cell"
                )
            )

    def test_type_and_compartment_correspondence_cannot_be_inferred(self):
        incoming = self.contract.input_measurement
        for observable in (
            replace(incoming.observable, compartment="undeclared"),
            replace(incoming.observable, role="missing"),
        ):
            with (
                self.subTest(observable=observable),
                self.assertRaises(bc.SerializationError),
            ):
                self.bind(input_measurement=replace(incoming, observable=observable))
        with self.assertRaises(bc.SerializationError):
            self.bind(predicate=replace(self.contract.predicate, threshold=bc.Level(5)))
        with self.assertRaises(bc.SerializationError):
            replace(incoming, observable=replace(incoming.observable, scope="contact"))

    def test_no_universal_domain_or_vacuous_threshold(self):
        for threshold in (0, 11):
            with (
                self.subTest(threshold=threshold),
                self.assertRaises(bc.SerializationError),
            ):
                self.bind(
                    predicate=replace(
                        self.contract.predicate,
                        threshold=bc.Concentration(threshold, unit="nM"),
                    )
                )
        with self.assertRaises(bc.SerializationError):
            self.bind(horizon=bc.Duration(3))

    def test_initial_and_response_rates_are_consistent(self):
        for initial in (rates(-1, 0), rates(0, 0.2)):
            with (
                self.subTest(initial=initial),
                self.assertRaises(bc.SerializationError),
            ):
                self.bind(initial_range=initial)
        with self.assertRaises(bc.SerializationError):
            self.bind(
                response=replace(
                    self.contract.response,
                    active_range=rates(0, 0.05),
                    inactive_range=rates(2, 3),
                )
            )

    def test_exact_source_links_and_product_are_required(self):
        for change in (
            {"goal_id": "missing"},
            {"input_signal_id": self.contract.goal_id},
            {"product": "another_product"},
            {
                "predicate": replace(
                    self.contract.predicate, predicate_id=self.contract.goal_id
                )
            },
            {"response": replace(self.contract.response, rule_id="missing")},
        ):
            with self.subTest(change=change), self.assertRaises(bc.SerializationError):
                self.bind(**change)

    def test_source_predicate_direction_cannot_be_reversed(self):
        with self.assertRaises(bc.SerializationError):
            self.bind(predicate=replace(self.contract.predicate, operator="<"))
        source = self.request.build_request.intent
        nodes = tuple(
            replace(node, attributes={"band": "low"})
            if node.id == self.contract.predicate.predicate_id
            else node
            for node in source.nodes
        )
        build = bc.BuildRequest.freeze(
            replace(source, nodes=nodes), target=self.request.target
        )
        request = bc.HumanBehaviorRequest(
            build,
            replace(
                self.contract, predicate=replace(self.contract.predicate, operator="<")
            ),
        )
        self.assertTrue(
            request.contract.predicate.accepts(bc.Concentration(1, unit="nM"))
        )

    def test_extra_source_goal_is_not_silently_dropped(self):
        source = self.request.build_request.intent
        goal = next(node for node in source.nodes if node.kind == "goal")
        extra = replace(goal, id="n999999", attributes={"name": "unmapped_goal"})
        intent = replace(
            source, nodes=(*source.nodes, extra), roots=(*source.roots, extra.id)
        )
        with self.assertRaises(bc.SerializationError):
            replace(
                self.request,
                build_request=bc.BuildRequest.freeze(
                    intent, target=self.request.target
                ),
            )

    def test_legacy_target_cannot_replace_human_target(self):
        target = bc.TargetContext("legacy", "1", bc.PayloadFormat.RNA)
        with self.assertRaises(bc.SerializationError):
            replace(
                self.request,
                build_request=replace(self.request.build_request, target=target),
            )
        with self.assertRaises(bc.SerializationError):
            replace(
                self.request,
                build_request=replace(
                    self.request.build_request, target=make_human_target()
                ),
            )

    def test_evidence_references_are_resolved_but_never_promoted(self):
        cited = replace(
            self.contract.response_support, basis="cited", evidence_ids=("missing",)
        )
        with self.assertRaises(bc.SerializationError):
            self.bind(response_support=cited)
        from tests.test_human_target import fixture_evidence

        evidence = fixture_evidence(id="missing")
        target = replace(
            self.request.target,
            human_target=replace(
                self.request.target.human_target, evidence=(evidence,)
            ),
        )
        request = bc.HumanBehaviorRequest(
            replace(self.request.build_request, target=target),
            replace(self.contract, response_support=cited),
        )
        self.assertEqual(
            request.contract.unresolved_evidence, self.contract.unresolved_evidence
        )
        self.assertFalse(hasattr(request, "passed"))

    def test_symbolic_source_still_cannot_use_general_lowering_or_compilation(self):
        with self.assertRaises(bc.UnsupportedBehaviorError):
            bc.lower_to_behavior(self.request.build_request)
        with self.assertRaises(bc.CompilationUnavailableError) as error:
            bc.compile(self.request)
        diagnostics = {item.code: item for item in error.exception.diagnostics}
        self.assertIn("human_target_applicability_unestablished", diagnostics)
        self.assertEqual(
            diagnostics["human_behavior_empirical_support_unestablished"].node_id,
            self.contract.goal_id,
        )

    def test_exact_deadlines_and_closed_ranges_pass(self):
        result = bc.check_secretion_trace(self.request, self.trace)
        self.assertEqual(result.outcome, "pass")
        self.assertEqual(set(result.coverage), {"active", "inactive", "recovered"})
        self.assertEqual(result.request_fingerprint, self.request.fingerprint)
        self.assertEqual(result.to_dict()["biological_applicability"], "unestablished")
        for rate_value in (2, 3):
            changed = tuple(
                replace(item, output_value=rate(rate_value))
                if item.time.canonical_value in (3, 6)
                else item
                for item in self.trace
            )
            self.assertEqual(
                bc.check_secretion_trace(self.request, changed).outcome, "pass"
            )

    def test_threshold_inclusion_and_units_are_explicit(self):
        threshold = self.contract.predicate
        self.assertTrue(threshold.accepts(bc.Concentration(5, unit="nM")))
        self.assertFalse(
            replace(threshold, operator=">").accepts(bc.Concentration(5, unit="nM"))
        )
        self.assertTrue(threshold.accepts(bc.Concentration(0.006, unit="uM")))

    def test_never_responding_trace_fails_and_never_activated_trace_is_unknown(self):
        silent = tuple(replace(item, output_value=rate(0)) for item in self.trace)
        self.assertEqual(bc.check_secretion_trace(self.request, silent).outcome, "fail")
        result = bc.check_secretion_trace(
            self.request, (sample(0, 0, 0), sample(10, 0, 0))
        )
        self.assertEqual(result.outcome, "unknown")
        self.assertIn("unexercised_active_interval", result.diagnostics)

    def test_deadline_between_samples_is_checked(self):
        trace = (
            sample(0, 0, 0),
            sample(1, 6, 0),
            sample(4, 6, 2.5),
            sample(6, 0, 2.5),
            sample(7, 0, 0),
            sample(10, 0, 0),
        )
        result = bc.check_secretion_trace(self.request, trace)
        self.assertEqual(result.outcome, "fail")
        self.assertIn("active_range_violation_at:3", result.diagnostics)

    def test_persistence_and_termination_failures_are_detected(self):
        persistence = (*self.trace[:3], sample(4, 6, 0), *self.trace[3:])
        recovery = (*self.trace[:4], sample(8, 0, 0), self.trace[-1])
        for trace, diagnostic in (
            (persistence, "active_range_violation_at:4"),
            (recovery, "inactive_range_violation_at:7"),
        ):
            result = bc.check_secretion_trace(self.request, trace)
            self.assertEqual(result.outcome, "fail")
            self.assertIn(diagnostic, result.diagnostics)

    def test_initial_input_and_output_are_checked_without_prehistory(self):
        for initial, diagnostic in (
            (sample(0, 6, 0), "initial_input_must_be_inactive"),
            (sample(0, 0, 0.08), "initial_output_outside_initial_range"),
        ):
            result = bc.check_secretion_trace(self.request, (initial, *self.trace[1:]))
            self.assertEqual(result.outcome, "fail")
            self.assertIn(diagnostic, result.diagnostics)

    def test_out_of_domain_is_unknown_and_horizon_is_not_extrapolated(self):
        result = bc.check_secretion_trace(
            self.request, (sample(0, 11, 0), *self.trace[1:])
        )
        self.assertEqual(result.outcome, "unknown")
        result = bc.check_secretion_trace(
            self.request, (*self.trace[:-1], sample(9, 0, 0))
        )
        self.assertEqual(result.outcome, "unknown")
        self.assertIn("trace_ends_before_declared_horizon", result.diagnostics)

    def test_cancelled_activation_and_simultaneous_deadline_have_no_hidden_latch(self):
        for cessation in (2, 3):
            trace = (
                sample(0, 0, 0),
                sample(1, 6, 0),
                sample(cessation, 0, 0),
                sample(10, 0, 0),
            )
            result = bc.check_secretion_trace(self.request, trace)
            self.assertEqual(result.outcome, "unknown")
            self.assertNotIn("active", result.coverage)

    def test_retrigger_replaces_pending_recovery_deadline(self):
        trace = (
            sample(0, 0, 0),
            sample(1, 6, 0),
            sample(3, 6, 2.5),
            sample(4, 0, 2.5),
            sample(4.5, 6, 0),
            sample(6.5, 6, 2.5),
            sample(7, 0, 2.5),
            sample(8, 0, 0),
            sample(10, 0, 0),
        )
        self.assertEqual(bc.check_secretion_trace(self.request, trace).outcome, "pass")

    def test_zero_delays_enforce_new_values_at_transition(self):
        request = self.bind(
            response=replace(
                self.contract.response,
                max_activation_delay=bc.Duration(0),
                max_deactivation_delay=bc.Duration(0),
            )
        )
        trace = (sample(0, 0, 0), sample(1, 6, 2.5), sample(6, 0, 0), sample(10, 0, 0))
        self.assertEqual(bc.check_secretion_trace(request, trace).outcome, "pass")
        self.assertEqual(bc.check_secretion_trace(request, self.trace).outcome, "fail")

    def test_instantaneous_endpoint_is_not_positive_duration_coverage(self):
        trace = (
            sample(0, 0, 0),
            sample(1, 6, 0),
            sample(3, 6, 2.5),
            sample(9, 0, 2.5),
            sample(10, 0, 0),
        )
        result = bc.check_secretion_trace(self.request, trace)
        self.assertEqual(result.outcome, "unknown")
        self.assertIn("unexercised_recovered_interval", result.diagnostics)

    def test_malformed_traces_are_errors_not_default_values(self):
        for trace in (
            (),
            (sample(1, 0, 0),),
            (sample(0, 0, 0), sample(0, 0, 0)),
            (sample(0, 0, 0), sample(11, 0, 0)),
            (sample(0, 0, 0), sample(4, 0, 0), sample(3, 0, 0)),
        ):
            with self.subTest(trace=trace), self.assertRaises(bc.SerializationError):
                bc.check_secretion_trace(self.request, trace)
        with self.assertRaises(bc.TypeMismatchError):
            bc.check_secretion_trace(
                self.request,
                (
                    replace(self.trace[0], output_value=bc.Concentration(1)),
                    *self.trace[1:],
                ),
            )

    def test_dependencies_and_imported_results_cannot_self_certify(self):
        original = bc.check_secretion_trace(self.request, self.trace)
        changed = bc.check_secretion_trace(
            self.request, (*self.trace[:3], sample(4, 6, 2.4), *self.trace[3:])
        )
        self.assertNotEqual(original.trace_fingerprint, changed.trace_fingerprint)
        self.assertEqual(
            bc.SecretionTraceResult.from_json(original.to_json()), original
        )
        for changes in (
            {"biological_applicability": "validated"},
            {"scope": "all_human_cells"},
            {"checker": "untrusted"},
        ):
            with self.assertRaises(bc.SerializationError):
                bc.SecretionTraceResult.from_dict({**original.to_dict(), **changes})

    def test_cli_retains_scope_and_unresolved_evidence(self):
        artifacts = (self.request, bc.check_secretion_trace(self.request, self.trace))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "artifact.json"
            for artifact in artifacts:
                path.write_text(artifact.to_json())
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(cli_main(["inspect", str(path)]), 0)
                summary = json.loads(output.getvalue())
                self.assertEqual(summary["fingerprint"], artifact.fingerprint)
                self.assertIn("biological", summary["inspection"].lower())


if __name__ == "__main__":
    unittest.main()
