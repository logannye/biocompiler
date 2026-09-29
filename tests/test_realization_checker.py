"""Finite-trace acceptance must preserve meaning and reject vacuous success."""

from __future__ import annotations

from dataclasses import replace
import unittest
from unittest.mock import patch

import cellweave as cw
from cellweave.compiler.behavior import lower_to_behavior
from cellweave.errors import SerializationError
from cellweave.ir.mechanism import MechanismNode, MechanismProgram
from cellweave.semantics.evaluator import InputFrame, SignalSample
from cellweave.semantics.realization import (
    BehaviorContract,
    InputDomain,
    Observable,
    OperatingDomain,
    ResponseRequirement,
)
from cellweave.semantics.types import BOOLEAN
from cellweave.verification.evidence import (
    CheckOutcome,
    CheckResult,
    DependencySnapshot,
)
from cellweave.verification.realization import (
    CHECKER_SETTINGS,
    InputBinding,
    ObservationMap,
    OutputBinding,
    check_realization,
    realization_dependencies,
)


def fixture(
    *,
    delay=0.5,
    silent=False,
    always_on=False,
    contact=False,
    wrong_logic=False,
    pulse=False,
):
    therapy = cw.Therapy("finite_response")
    cell = therapy.engineer("observer", cell_type="abstract_cell")
    scope = cell.contact if contact else cell.environment
    first = scope.signal("A")
    signals = [first]
    condition = first.present()
    if contact:
        second = scope.signal("B")
        signals.append(second)
        condition = condition & second.present()
    action = cell.eliminate(cell.contact) if contact else cell.rest()
    specification = action.for_(cw.Duration(4)) if pulse else action
    rule = cell.when(condition).do(specification)
    behavior = lower_to_behavior(therapy.freeze())
    port_scope = "contact" if contact else "cell"
    input_endpoints = tuple(
        Observable(f"input_{index}", BOOLEAN, cell.node_id, port_scope)
        for index in range(len(signals))
    )
    output_endpoint = Observable(
        "response_activity", cw.Level, cell.node_id, port_scope
    )
    inputs = tuple(
        InputDomain(signal.node_id, "present", endpoint, (False, True))
        for signal, endpoint in zip(signals, input_endpoints)
    )
    domain = OperatingDomain(
        "domain",
        "1",
        cell.node_id,
        inputs,
        cw.Duration(8),
        max_contacts=2 if contact else None,
        required_capabilities=("synthetic_fixture",),
    )
    requirement = ResponseRequirement(
        "response",
        rule.node_id,
        specification.node_id,
        output_endpoint,
        cw.Interval(0.9, 1.1),
        cw.Interval(-0.1, 0.1),
        cw.Duration(1),
        cw.Duration(1),
    )
    contract = BehaviorContract("contract", behavior.fingerprint, (requirement,))
    target = cw.TargetContext(
        "fixture", "1", cw.PayloadFormat.RNA, capabilities=("synthetic_fixture",)
    )
    nodes = [
        MechanismNode(f"input{index}", "input", endpoint)
        for index, endpoint in enumerate(input_endpoints)
    ]
    trigger = "input0"
    if contact:
        trigger = "combine"
        nodes.append(
            MechanismNode(
                trigger,
                "or" if wrong_logic else "and",
                Observable("combined", BOOLEAN, cell.node_id, port_scope),
                ("input0", "input1"),
            )
        )

    def numeric(name):
        return Observable(name, cw.Level, cell.node_id, port_scope)

    nodes += [
        MechanismNode("high", "constant", numeric("high"), attributes={"value": 1}),
        MechanismNode("low", "constant", numeric("low"), attributes={"value": 0}),
        MechanismNode(
            "select", "select", numeric("selected"), (trigger, "high", "low")
        ),
    ]
    selected = "low" if silent else "high" if always_on else "select"
    if delay:
        nodes.append(
            MechanismNode(
                "delay",
                "delay",
                numeric("delayed"),
                (selected,),
                {"duration": cw.Duration(delay), "initial": 0},
            )
        )
        selected = "delay"
    nodes.append(
        MechanismNode(
            "output",
            "output",
            output_endpoint,
            (selected,),
            requirement_ids=("response",),
        )
    )
    mechanism = MechanismProgram(
        "candidate",
        tuple(nodes),
        ("output",),
        required_capabilities=("synthetic_fixture",),
    )
    observation_map = ObservationMap(
        tuple(
            InputBinding(signal.node_id, "present", f"input{index}")
            for index, signal in enumerate(signals)
        ),
        (OutputBinding("response", "output"),),
    )
    if contact:

        def snapshot(time, values):
            return InputFrame(
                time,
                contacts={
                    identity: {
                        signal.node_id: SignalSample(present=value)
                        for signal, value in zip(signals, state)
                    }
                    for identity, state in values.items()
                },
            )

        history = [
            snapshot(0, {"first": (True, False), "second": (False, True)}),
            snapshot(2, {"first": (True, True), "second": (False, False)}),
            snapshot(6, {"first": (False, False), "second": (False, False)}),
            snapshot(10, {"first": (False, False), "second": (False, False)}),
        ]
    else:
        history = [
            InputFrame(time, {first.node_id: SignalSample(present=active)})
            for time, active in [(0, False), (2, True), (6, False), (10, False)]
        ]
    return behavior, contract, domain, target, mechanism, observation_map, history


class FiniteTraceCheckerTests(unittest.TestCase):
    def test_missing_and_unknown_model_requirement_references_fail(self):
        for ids, code in [
            ((), "missing_output_lineage"),
            (("unrelated",), "unknown_model_requirement"),
        ]:
            args = list(fixture())
            mechanism = args[4]
            changed = replace(mechanism.get("output"), requirement_ids=ids)
            args[4] = replace(
                mechanism,
                nodes=tuple(
                    changed if item.id == "output" else item for item in mechanism.nodes
                ),
            )
            with self.subTest(ids=ids):
                result = check_realization(*args)
                self.assertIs(result.outcome, CheckOutcome.FAIL)
                self.assertEqual(result.diagnostics[-1].code, code)
                self.assertEqual(result.coverage, ())

    def test_coverage_counts_actual_deadlines_and_incomplete_episodes(self):
        result = check_realization(*fixture())
        (coverage,) = result.coverage
        self.assertEqual(coverage.activation_deadlines_checked, 1)
        self.assertEqual(coverage.inactive_deadlines_checked, 2)
        self.assertEqual(coverage.incomplete_episode_count, 0)
        self.assertEqual(result.exercised_requirement_ids, ("response",))
        incomplete = check_realization(*fixture(), until=2.5)
        self.assertEqual(incomplete.coverage[0].activation_deadlines_checked, 0)
        self.assertEqual(incomplete.coverage[0].incomplete_episode_count, 1)
        self.assertEqual(incomplete.exercised_requirement_ids, ())

    def test_unrepresentable_response_deadline_is_unknown(self):
        args = list(fixture(delay=0))
        requirement = args[1].requirements[0]
        args[1] = replace(
            args[1],
            requirements=(
                replace(requirement, max_activation_delay=cw.Duration(0.25)),
            ),
        )
        signal = args[2].inputs[0].signal_id
        args[6] = [
            InputFrame(0, {signal: SignalSample(present=False)}),
            InputFrame(1e16, {signal: SignalSample(present=True)}),
        ]
        result = check_realization(*args)
        self.assertIs(result.outcome, CheckOutcome.UNKNOWN)
        self.assertIn("numeric_resolution", {item.code for item in result.diagnostics})

    def test_timely_response_passes_with_a_scoped_model_conditional_claim(self):
        result = check_realization(*fixture())
        self.assertIs(result.outcome, CheckOutcome.PASS)
        self.assertEqual(result.evidence_kind.value, "model_conditional")
        self.assertIn("finite", result.claim_scope)
        self.assertIn("not whole-program", result.claim_scope)
        self.assertEqual(result.checked_requirement_ids, ("response",))

    def test_silent_candidate_fails_required_response_at_its_deadline(self):
        result = check_realization(*fixture(silent=True))
        self.assertIs(result.outcome, CheckOutcome.FAIL)
        first = result.counterexamples[0]
        self.assertEqual(first.time, 3)
        self.assertEqual(first.actual, 0)
        self.assertEqual(first.expected["state"], "active")
        self.assertIsNotNone(first.source)

    def test_late_candidate_fails_between_external_snapshots(self):
        result = check_realization(*fixture(delay=2))
        self.assertIs(result.outcome, CheckOutcome.FAIL)
        self.assertIn(3, [item.time for item in result.counterexamples])

    def test_always_on_candidate_fails_inactive_response(self):
        result = check_realization(*fixture(always_on=True))
        self.assertIs(result.outcome, CheckOutcome.FAIL)
        self.assertEqual(result.counterexamples[0].expected["state"], "inactive")

    def test_same_object_logic_passes_but_cross_object_confusion_fails(self):
        self.assertTrue(check_realization(*fixture(contact=True)).passed)
        result = check_realization(*fixture(contact=True, wrong_logic=True))
        self.assertIs(result.outcome, CheckOutcome.FAIL)
        self.assertEqual(
            {item.contact_id for item in result.counterexamples}, {"first", "second"}
        )

    def test_exact_endpoint_meaning_is_required_even_for_identical_units(self):
        args = list(fixture())
        mechanism = args[4]
        output = mechanism.get("output")
        changed = replace(output, output=replace(output.output, id="unrelated_readout"))
        args[4] = replace(
            mechanism,
            nodes=tuple(
                changed if node.id == "output" else node for node in mechanism.nodes
            ),
        )
        result = check_realization(*args)
        self.assertIs(result.outcome, CheckOutcome.FAIL)
        self.assertEqual(result.diagnostics[-1].code, "output_endpoint")

    def test_incompatible_output_units_fail_mapping(self):
        args = list(fixture())
        requirement = args[1].requirements[0]
        requirement = replace(
            requirement,
            observable=replace(requirement.observable, dtype=cw.Concentration),
            active_range=cw.Interval(
                cw.Concentration(1), cw.Concentration(2), type=cw.Concentration
            ),
            inactive_range=cw.Interval(
                cw.Concentration(0), cw.Concentration(0.1), type=cw.Concentration
            ),
        )
        args[1] = replace(args[1], requirements=(requirement,))
        result = check_realization(*args)
        self.assertIs(result.outcome, CheckOutcome.FAIL)
        self.assertEqual(result.diagnostics[-1].code, "output_endpoint")

    def test_incorrect_domain_role_or_scope_fails_source_correspondence(self):
        args = list(fixture(contact=True))
        domains = tuple(
            replace(item, observable=replace(item.observable, scope="cell"))
            for item in args[2].inputs
        )
        args[2] = replace(args[2], inputs=domains)
        result = check_realization(*args)
        self.assertIs(result.outcome, CheckOutcome.FAIL)
        self.assertEqual(result.diagnostics[-1].code, "input_semantics")

    def test_missing_capability_is_not_assumed(self):
        args = list(fixture())
        args[3] = replace(args[3], capabilities=())
        result = check_realization(*args)
        self.assertIs(result.outcome, CheckOutcome.FAIL)
        self.assertEqual(result.diagnostics[-1].code, "missing_capabilities")

    def test_out_of_domain_inputs_are_unknown(self):
        args = list(fixture())
        args[2] = replace(
            args[2],
            inputs=tuple(replace(item, allowed=(False,)) for item in args[2].inputs),
        )
        result = check_realization(*args)
        self.assertIs(result.outcome, CheckOutcome.UNKNOWN)
        self.assertEqual(result.diagnostics[-1].code, "outside_domain")

    def test_excess_contacts_are_out_of_domain(self):
        args = list(fixture(contact=True))
        args[2] = replace(args[2], max_contacts=1)
        result = check_realization(*args)
        self.assertIs(result.outcome, CheckOutcome.UNKNOWN)
        self.assertEqual(result.diagnostics[-1].code, "outside_domain")

    def test_no_exercised_activation_is_unknown_even_when_model_stays_off(self):
        args = list(fixture())
        signal = args[2].inputs[0].signal_id
        args[6] = [
            InputFrame(0, {signal: SignalSample(present=False)}),
            InputFrame(10, {signal: SignalSample(present=False)}),
        ]
        result = check_realization(*args)
        self.assertIs(result.outcome, CheckOutcome.UNKNOWN)
        self.assertIn(
            "unexercised_response", {item.code for item in result.diagnostics}
        )

    def test_empty_history_is_unknown(self):
        args = list(fixture())
        args[6] = []
        result = check_realization(*args)
        self.assertIs(result.outcome, CheckOutcome.UNKNOWN)
        self.assertEqual(result.diagnostics[-1].code, "empty_history")

    def test_short_active_episode_is_not_a_vacuous_pass(self):
        args = list(fixture())
        signal = args[2].inputs[0].signal_id
        args[6] = [
            InputFrame(time, {signal: SignalSample(present=active)})
            for time, active in [(0, False), (2, True), (2.25, False), (10, False)]
        ]
        result = check_realization(*args)
        self.assertIs(result.outcome, CheckOutcome.UNKNOWN)
        self.assertIn("incomplete_episode", {item.code for item in result.diagnostics})

    def test_horizon_truncating_response_deadline_is_unknown(self):
        result = check_realization(*fixture(), until=2.5)
        self.assertIs(result.outcome, CheckOutcome.UNKNOWN)
        self.assertIn("incomplete_episode", {item.code for item in result.diagnostics})

    def test_clear_violation_wins_over_too_short_overall_horizon(self):
        result = check_realization(*fixture(silent=True), until=3)
        self.assertIs(result.outcome, CheckOutcome.FAIL)
        self.assertEqual(result.counterexamples[0].time, 3)

    def test_unknown_future_observation_is_not_read_past_horizon(self):
        args = list(fixture())
        args[6] = args[6][:3] + [InputFrame(100)]
        result = check_realization(*args, until=10)
        self.assertTrue(result.passed)

    def test_missing_input_binding_fails_instead_of_fabricating_an_input(self):
        args = list(fixture())
        args[5] = replace(args[5], inputs=())
        result = check_realization(*args)
        self.assertIs(result.outcome, CheckOutcome.FAIL)
        self.assertEqual(result.diagnostics[-1].code, "input_binding_coverage")

    def test_pulse_contract_binds_wrapper_not_shared_primitive_action(self):
        args = list(fixture(pulse=True))
        self.assertTrue(check_realization(*args).passed)
        requirement = args[1].requirements[0]
        primitive_id = args[0].get(requirement.specification_id).inputs[0]
        args[1] = replace(
            args[1], requirements=(replace(requirement, specification_id=primitive_id),)
        )
        result = check_realization(*args)
        self.assertIs(result.outcome, CheckOutcome.FAIL)
        self.assertEqual(result.diagnostics[-1].code, "requirement_source")


class CheckArtifactTests(unittest.TestCase):
    def test_counterexamples_reject_malformed_expectations_and_actual_values(self):
        result = check_realization(*fixture(silent=True))
        for expected in (
            {},
            {"state": "active", "range": {}},
            {
                "state": [],
                "range": result.counterexamples[0].to_dict()["expected"]["range"],
            },
            {
                "state": "unknown",
                "range": result.counterexamples[0].to_dict()["expected"]["range"],
            },
        ):
            data = result.to_dict()
            data["counterexamples"][0]["expected"] = expected
            with self.subTest(expected=expected), self.assertRaises(SerializationError):
                CheckResult.from_dict(data)
        for actual in (True, "0", {}, [], float("nan"), float("inf"), 10**500):
            data = result.to_dict()
            data["counterexamples"][0]["actual"] = actual
            with self.subTest(actual=actual), self.assertRaises(SerializationError):
                CheckResult.from_dict(data)
        data = result.to_dict()
        data["counterexamples"][0]["expected"]["range"]["lower"]["canonical_value"] = 99
        with self.assertRaises(SerializationError):
            CheckResult.from_dict(data)
        for actual in (None, -1.0):
            data = result.to_dict()
            data["counterexamples"][0]["actual"] = actual
            restored = CheckResult.from_dict(data)
            self.assertEqual(restored.counterexamples[0].actual, actual)

    def test_source_relocation_invalidates_source_bearing_evidence(self):
        args = list(fixture())
        result = check_realization(*args)
        data = args[0].to_dict()
        for node in data["nodes"]:
            if node.get("source"):
                node["source"]["file"] = "relocated.py"
        for requirement in data["requirements"]:
            if requirement.get("source"):
                requirement["source"]["file"] = "relocated.py"
        args[0] = cw.BehaviorProgram.from_dict(data)
        self.assertEqual(args[0].fingerprint, result.dependencies.values["behavior"])
        self.assertEqual(
            result.freshness(realization_dependencies(*args)).changed_dependencies,
            ("behavior_artifact",),
        )

    def test_artifacts_cannot_widen_claims_or_invent_exercised_coverage(self):
        result = check_realization(*fixture())
        for field, value in [
            ("claim_scope", "Universal biological proof"),
            ("coverage", []),
        ]:
            data = result.to_dict()
            data[field] = value
            with self.subTest(field=field), self.assertRaises(SerializationError):
                CheckResult.from_dict(data)
        data = check_realization(*fixture(silent=True)).to_dict()
        data["counterexamples"][0]["requirement_id"] = "unrelated"
        with self.assertRaises(SerializationError):
            CheckResult.from_dict(data)

    def test_result_roundtrip_and_nested_immutability(self):
        result = check_realization(*fixture(silent=True))
        restored = CheckResult.from_json(result.to_json())
        self.assertEqual(restored.fingerprint, result.fingerprint)
        self.assertEqual(restored.to_dict(), result.to_dict())
        with self.assertRaises(TypeError):
            restored.dependencies.values["target"] = "changed"
        with self.assertRaises(TypeError):
            restored.counterexamples[0].expected["state"] = "changed"
        mutable = restored.to_dict()
        mutable["dependencies"]["settings"]["time"] = "changed"
        self.assertNotEqual(mutable, restored.to_dict())

    def test_all_dependency_changes_invalidate_the_claim(self):
        args = list(fixture())
        result = check_realization(*args)
        self.assertTrue(result.is_fresh(realization_dependencies(*args)))
        for key in result.dependencies.values:
            values = result.dependencies.to_dict()
            if key in {"checker", "model_runner", "reference_evaluator"}:
                values[key] += ".changed"
            elif key == "settings":
                values[key]["max_microsteps"] += 1
            elif key == "horizon":
                values[key]["effective"] += 1
            else:
                values[key] = "f" * 64 if values[key] != "f" * 64 else "e" * 64
            with self.subTest(dependency=key):
                report = result.freshness(DependencySnapshot(values))
                self.assertEqual(report.status, "stale")
                self.assertEqual(report.changed_dependencies, (key,))

    def test_public_dependency_helper_detects_context_parameter_and_history_changes(
        self,
    ):
        args = list(fixture())
        result = check_realization(*args)
        changed = list(args)
        changed[3] = replace(args[3], context_version="2")
        self.assertEqual(
            result.freshness(realization_dependencies(*changed)).changed_dependencies,
            ("target",),
        )
        changed = list(args)
        mechanism = args[4]
        delay = replace(
            mechanism.get("delay"),
            attributes={"duration": cw.Duration(0.75), "initial": 0},
        )
        changed[4] = replace(
            mechanism,
            nodes=tuple(
                delay if item.id == delay.id else item for item in mechanism.nodes
            ),
        )
        self.assertEqual(
            result.freshness(realization_dependencies(*changed)).changed_dependencies,
            ("mechanism",),
        )
        changed = list(args)
        signal = args[2].inputs[0].signal_id
        changed[6] = list(args[6]) + [
            InputFrame(11, {signal: SignalSample(present=False)})
        ]
        self.assertEqual(
            result.freshness(realization_dependencies(*changed)).changed_dependencies,
            ("history", "horizon"),
        )
        with patch("cellweave.verification.realization.CHECKER_VERSION", "changed"):
            self.assertEqual(
                result.freshness(realization_dependencies(*args)).changed_dependencies,
                ("checker",),
            )

    def test_incomplete_dependency_record_cannot_be_imported(self):
        data = check_realization(*fixture()).to_dict()
        del data["dependencies"]["model_runner"]
        with self.assertRaises(SerializationError):
            CheckResult.from_dict(data)

    def test_duplicate_json_keys_and_unknown_fields_are_rejected(self):
        with self.assertRaises(SerializationError):
            CheckResult.from_json('{"outcome":"pass","outcome":"fail"}')
        data = check_realization(*fixture()).to_dict()
        data["claimed_universal_proof"] = True
        with self.assertRaises(SerializationError):
            CheckResult.from_dict(data)

    def test_observation_map_roundtrip_and_invalid_fields(self):
        mapping = fixture()[5]
        self.assertEqual(
            ObservationMap.from_json(mapping.to_json()).fingerprint, mapping.fingerprint
        )
        for field in ([], {}, "unrecognized"):
            with self.subTest(field=field), self.assertRaises(SerializationError):
                InputBinding("signal", field, "model")
        with self.assertRaises(TypeError):
            CHECKER_SETTINGS["scope"] = "universal"


if __name__ == "__main__":
    unittest.main()
