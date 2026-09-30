"""Independent literal timelines for generated temporal software mechanisms."""

from dataclasses import replace
import unittest

import biocompiler as bc
from biocompiler.compiler.synthetic import run_synthetic_pipeline
from biocompiler.models.synthetic import ModelInputFrame, run_model
from biocompiler.registry.synthetic import SYNTHETIC_CATALOG, TEMPORAL_PROFILE_VERSION
from biocompiler.semantics.types import BOOLEAN
from biocompiler.synthesis.components import adapt_synthetic_components
from biocompiler.synthesis.synthetic import (
    SyntheticCandidate,
    SyntheticGeneratorConfig,
    check_synthetic_candidate,
    generate_synthetic,
)
from biocompiler.verification.exploration import (
    BooleanContactConfig,
    BooleanObservation,
    explore_boolean_histories,
)
from examples.temporal_pipeline import build_request
from test_semantic_matrix import CONTACT_CASES, MEMORY_CASES, PULSE_CASES


def temporal_config():
    return SyntheticGeneratorConfig(profile_version=TEMPORAL_PROFILE_VERSION)


def freeze(therapy, cell, signals, outputs):
    """Freeze explicit exact digital bands; no expected timing is computed here."""
    target = bc.TargetContext(
        "synthetic",
        "1",
        bc.PayloadFormat.RNA,
        capabilities=("synthetic_signal_graph",),
    )
    build = bc.BuildRequest.freeze(
        therapy.freeze(), target=target, artifact_scope="synthetic_realization"
    )
    behavior = bc.lower_to_behavior(build)
    contract = bc.BehaviorContract(
        "exact_readouts",
        behavior.fingerprint,
        tuple(
            bc.ResponseRequirement(
                label,
                rule.node_id,
                action.node_id,
                bc.Observable(label, bc.Level, cell.role, scope=scope),
                bc.Interval(1, 1),
                bc.Interval(0, 0),
                bc.Duration(0),
                bc.Duration(0),
            )
            for label, rule, action, scope in outputs
        ),
    )
    domain = bc.OperatingDomain(
        "temporal_inputs",
        "1",
        cell.role,
        tuple(
            bc.InputDomain(
                signal.node_id,
                "present",
                bc.Observable(signal.node_id, BOOLEAN, cell.role, scope=scope),
                (False, True),
            )
            for signal, scope in signals
        ),
        bc.Duration(0.25),
        max_contacts=2,
    )
    return bc.RealizationRequest.freeze(build, behavior, contract, domain)


def cell_model(name):
    therapy = bc.Therapy(name)
    return therapy, therapy.engineer("observer", cell_type="abstract_cell")


def contact_history(signals, rows):
    return tuple(
        bc.InputFrame(
            time,
            contacts={
                identity: {
                    signal.node_id: bc.SignalSample(present=value)
                    for signal, value in zip(signals, values)
                }
                for identity, values in contacts.items()
            },
        )
        for time, contacts in rows
    )


def cell_history(signals, rows):
    return tuple(
        bc.InputFrame(
            time,
            {
                signal.node_id: bc.SignalSample(present=value)
                for signal, value in zip(signals, values)
            },
        )
        for time, *values in rows
    )


def squash(rows):
    """Discard only repeated output states, without interpreting temporal rules."""
    result = []
    for time, active in rows:
        state = tuple(sorted(active))
        if not result or result[-1][1] != state:
            result.append((time, state))
    return tuple(result)


def model_timeline(request, candidate, history, horizon):
    """Translate declared observation bindings and label direct model outputs."""
    domains = {(item.signal_id, item.field): item for item in request.domain.inputs}
    mapped = []
    for frame in history:
        values = {}
        contacts = {identity: {} for identity in frame.contacts}
        for binding in candidate.observation_map.inputs:
            domain = domains[binding.signal_id, binding.field]
            if domain.scope == "cell":
                values[binding.mechanism_input_id] = getattr(
                    frame.signals[binding.signal_id], binding.field
                )
            else:
                for identity, samples in frame.contacts.items():
                    contacts[identity][binding.mechanism_input_id] = getattr(
                        samples[binding.signal_id], binding.field
                    )
        mapped.append(ModelInputFrame(frame.time, values, contacts))
    labels = {
        item.mechanism_output_id: item.requirement_id
        for item in candidate.observation_map.outputs
    }
    trace = run_model(candidate.mechanism, mapped, until=horizon)
    return squash(
        (
            frame.time,
            (
                [labels[ref] for ref, value in frame.values.items() if value == 1]
                + [
                    labels[ref] + ":" + identity
                    for identity, values in frame.contacts.items()
                    for ref, value in values.items()
                    if value == 1
                ]
            ),
        )
        for frame in trace.frames
    )


class TemporalGenerationTests(unittest.TestCase):
    def assert_timeline(self, request, history, horizon, expected, *, outcome=None):
        candidate = generate_synthetic(request, config=temporal_config())
        self.assertEqual(model_timeline(request, candidate, history, horizon), expected)
        result = check_synthetic_candidate(request, candidate, history, until=horizon)
        if outcome is None:
            self.assertIn(
                result.outcome, (bc.CheckOutcome.PASS, bc.CheckOutcome.UNKNOWN), result
            )
        else:
            self.assertEqual(result.outcome, outcome, result)
        return candidate

    def test_existing_literal_contact_matrix_is_preserved_by_generation(self):
        therapy, cell = cell_model("temporal_contact_matrix")
        a, b = cell.contact.marker("A"), cell.contact.marker("B")
        guard = (a.present() & b.present()).held_for(bc.Duration(2))
        memory = cell.memory("seen", set_when=guard, duration=bc.Duration(3))
        local = cell.rest().for_(bc.Duration(3))
        target = cell.eliminate(cell.contact).for_(bc.Duration(3))
        remembered = cell.rest()
        pulse_rule = cell.when(guard).do(local, target)
        memory_rule = cell.when(memory.is_set()).do(remembered)
        request = freeze(
            therapy,
            cell,
            ((a, "contact"), (b, "contact")),
            (
                ("local", pulse_rule, local, "cell"),
                ("target", pulse_rule, target, "contact"),
                ("memory", memory_rule, remembered, "cell"),
            ),
        )
        for case in CONTACT_CASES:
            expected = squash(
                (
                    time,
                    [label.split("@")[0] for label in active]
                    + (["memory"] if memories[0] else []),
                )
                for time, active, _, memories in case.expected
            )
            with self.subTest(case=case.name):
                self.assert_timeline(
                    request,
                    contact_history((a, b), case.history),
                    case.horizon,
                    expected,
                )

    def test_existing_literal_pulse_matrix_condition_and_event(self):
        for mode in ("condition", "event"):
            therapy, cell = cell_model("temporal_pulse_" + mode)
            signal = cell.environment.signal("trigger")
            output = cell.rest().for_(bc.Duration(2))
            guard = signal.present()
            rule = (
                cell.when(guard)
                if mode == "condition"
                else cell.on(guard.became_true())
            ).do(output)
            request = freeze(
                therapy, cell, ((signal, "cell"),), (("pulse", rule, output, "cell"),)
            )
            for case in PULSE_CASES:
                expected = squash(
                    (time, [label.split("@")[0] for label in active])
                    for time, active, _, _ in case.expected
                )
                with self.subTest(mode=mode, case=case.name):
                    self.assert_timeline(
                        request,
                        cell_history((signal,), case.history),
                        case.horizon,
                        expected,
                        outcome=bc.CheckOutcome.PASS,
                    )

    def test_existing_literal_dependent_memory_matrix(self):
        therapy, cell = cell_model("temporal_memory_matrix")
        setting, reset, gate = (
            cell.environment.signal(name) for name in ("set", "reset", "gate")
        )
        producer = cell.memory(
            "producer",
            set_when=setting.present(),
            reset_when=reset.present(),
            duration=bc.Duration(2),
        )
        consumer = cell.memory(
            "consumer",
            set_when=producer.is_set() & gate.present(),
            duration=bc.Duration(1),
        )
        outputs = []
        for label, memory in (("producer", producer), ("consumer", consumer)):
            action = cell.rest()
            rule = cell.when(memory.is_set()).do(action)
            outputs.append((label, rule, action, "cell"))
        request = freeze(
            therapy,
            cell,
            tuple((item, "cell") for item in (setting, reset, gate)),
            outputs,
        )
        for case in MEMORY_CASES:
            expected = squash(
                (
                    time,
                    [
                        label
                        for label, active in zip(("producer", "consumer"), memories)
                        if active
                    ],
                )
                for time, _, _, memories in case.expected
            )
            with self.subTest(case=case.name):
                self.assert_timeline(
                    request,
                    cell_history((setting, reset, gate), case.history),
                    case.horizon,
                    expected,
                )

    def test_held_for_fall_and_rapid_rerise_start_a_complete_new_interval(self):
        therapy, cell = cell_model("held_for_restart")
        signal = cell.environment.signal("A")
        output = cell.rest()
        rule = cell.when(signal.present().held_for(bc.Duration(2))).do(output)
        request = freeze(
            therapy, cell, ((signal, "cell"),), (("held", rule, output, "cell"),)
        )
        history = cell_history(
            (signal,), ((0, True), (3, False), (3.25, True), (6, False))
        )
        candidate = self.assert_timeline(
            request,
            history,
            7,
            ((0, ()), (2, ("held",)), (3, ()), (5.25, ("held",)), (6, ())),
            outcome=bc.CheckOutcome.PASS,
        )
        # Keep the output wiring, but substitute the old two-edge inertial delay.
        mechanism = replace(
            candidate.mechanism,
            nodes=tuple(
                replace(
                    node,
                    kind="delay",
                    attributes={
                        "duration": bc.Duration(2).to_dict(),
                        "initial": False,
                    },
                )
                if node.kind == "held_for"
                else node
                for node in candidate.mechanism.nodes
            ),
        )
        result = bc.check_realization(
            request.behavior,
            request.contract,
            request.domain,
            request.target,
            mechanism,
            candidate.observation_map,
            history,
            until=7,
        )
        self.assertEqual(result.outcome, bc.CheckOutcome.FAIL)

    def test_cell_temporal_operand_runs_without_contacts_and_survives_dropout(self):
        therapy, cell = cell_model("cell_timer_broadcast")
        signal, marker = cell.environment.signal("A"), cell.contact.marker("B")
        output = cell.eliminate(cell.contact)
        rule = cell.when(
            signal.present().held_for(bc.Duration(2)) & marker.present()
        ).do(output)
        request = freeze(
            therapy,
            cell,
            ((signal, "cell"), (marker, "contact")),
            (("held", rule, output, "contact"),),
        )
        history = tuple(
            bc.InputFrame(
                time,
                {signal.node_id: bc.SignalSample(present=True)},
                {
                    identity: {marker.node_id: bc.SignalSample(present=present)}
                    for identity, present in contacts.items()
                },
            )
            for time, contacts in (
                (0, {}),
                (3, {"x": True}),
                (4, {}),
                (5, {"x": True}),
                (6, {"x": False}),
            )
        )
        self.assert_timeline(
            request,
            history,
            7,
            ((0, ()), (3, ("held:x",)), (4, ()), (5, ("held:x",)), (6, ())),
            outcome=bc.CheckOutcome.PASS,
        )

    def test_contact_timers_do_not_share_sustained_intervals(self):
        therapy, cell = cell_model("independent_dwell")
        marker = cell.contact.marker("A")
        output = cell.eliminate(cell.contact)
        rule = cell.when(marker.present().held_for(bc.Duration(2))).do(output)
        request = freeze(
            therapy, cell, ((marker, "contact"),), (("held", rule, output, "contact"),)
        )
        history = contact_history(
            (marker,),
            (
                (0, {"x": (True,), "y": (False,)}),
                (1, {"x": (True,), "y": (True,)}),
                (4, {"x": (False,), "y": (False,)}),
            ),
        )
        self.assert_timeline(
            request,
            history,
            5,
            ((0, ()), (2, ("held:x",)), (3, ("held:x", "held:y")), (4, ())),
            outcome=bc.CheckOutcome.PASS,
        )

    def test_contact_event_refresh_differs_from_cell_condition_pulse(self):
        for mode, expected in (
            ("condition", ((0, ("pulse",)), (2, ()))),
            ("event", ((0, ("pulse",)), (3, ()))),
        ):
            therapy, cell = cell_model("contact_" + mode)
            marker = cell.contact.marker("A")
            action = cell.rest().for_(bc.Duration(2))
            rule = (
                cell.when(marker.present())
                if mode == "condition"
                else cell.on(marker.present().became_true())
            ).do(action)
            request = freeze(
                therapy,
                cell,
                ((marker, "contact"),),
                (("pulse", rule, action, "cell"),),
            )
            history = contact_history(
                (marker,),
                (
                    (0, {"x": (True,), "y": (False,)}),
                    (1, {"x": (True,), "y": (True,)}),
                    (4, {"x": (False,), "y": (False,)}),
                ),
            )
            self.assert_timeline(
                request, history, 5, expected, outcome=bc.CheckOutcome.PASS
            )

    def test_new_contact_onset_refreshes_memory_while_another_remains_active(self):
        therapy, cell = cell_model("contact_memory_refresh")
        marker = cell.contact.marker("A")
        memory = cell.memory("seen", set_when=marker.present(), duration=bc.Duration(2))
        output = cell.rest()
        rule = cell.when(memory.is_set()).do(output)
        request = freeze(
            therapy, cell, ((marker, "contact"),), (("memory", rule, output, "cell"),)
        )
        history = contact_history(
            (marker,),
            (
                (0, {"x": (True,), "y": (False,)}),
                (1, {"x": (True,), "y": (True,)}),
                (4, {}),
            ),
        )
        self.assert_timeline(
            request,
            history,
            5,
            ((0, ("memory",)), (3, ())),
            outcome=bc.CheckOutcome.PASS,
        )

    def test_memory_without_duration_remains_set_until_reset(self):
        therapy, cell = cell_model("latched_memory")
        setting, reset = (cell.environment.signal(name) for name in ("set", "reset"))
        memory = cell.memory(
            "seen", set_when=setting.present(), reset_when=reset.present()
        )
        output = cell.rest()
        rule = cell.when(memory.is_set()).do(output)
        request = freeze(
            therapy,
            cell,
            ((setting, "cell"), (reset, "cell")),
            (("memory", rule, output, "cell"),),
        )
        history = cell_history(
            (setting, reset),
            ((0, True, False), (1, False, False), (8, False, True), (9, False, False)),
        )
        self.assert_timeline(
            request,
            history,
            10,
            ((0, ("memory",)), (8, ())),
            outcome=bc.CheckOutcome.PASS,
        )

    def test_premature_pulse_expiry_fails_independent_check(self):
        therapy, cell = cell_model("pulse_expiry_mutation")
        signal = cell.environment.signal("trigger")
        output = cell.rest().for_(bc.Duration(2))
        rule = cell.on(signal.present().became_true()).do(output)
        request = freeze(
            therapy, cell, ((signal, "cell"),), (("pulse", rule, output, "cell"),)
        )
        history = cell_history((signal,), ((0, True), (1, False)))
        candidate = self.assert_timeline(
            request,
            history,
            3,
            ((0, ("pulse",)), (2, ())),
            outcome=bc.CheckOutcome.PASS,
        )
        wrong = replace(
            candidate,
            mechanism=replace(
                candidate.mechanism,
                nodes=tuple(
                    replace(node, attributes={"duration": bc.Duration(1).to_dict()})
                    if node.kind == "pulse"
                    else node
                    for node in candidate.mechanism.nodes
                ),
            ),
        )
        result = check_synthetic_candidate(request, wrong, history, until=3)
        self.assertEqual(result.outcome, bc.CheckOutcome.FAIL)
        self.assertTrue(result.counterexamples)

    def test_bounded_dwell_campaign_covers_all_81_declared_histories(self):
        therapy, cell = cell_model("bounded_dwell_generation")
        marker = cell.contact.marker("A")
        output = cell.rest()
        rule = cell.when(marker.present().held_for(bc.Duration(2))).do(output)
        request = freeze(
            therapy, cell, ((marker, "contact"),), (("held", rule, output, "cell"),)
        )
        candidate = generate_synthetic(request, config=temporal_config())
        # One named contact: absent, present/false, present/true at each of
        # 0, 1, 2, 3 seconds. Every history then gets the same active/inactive
        # suffix at 5 and 8 seconds and is checked only through 9 seconds.
        bounds = BooleanContactConfig(
            ("x",),
            (BooleanObservation(marker.node_id),),
            (0, 1, 2, 3),
            9,
            fixed_suffix=contact_history(
                (marker,), ((5, {"x": (True,)}), (8, {"x": (False,)}))
            ),
            max_histories=81,
        )
        report = explore_boolean_histories(
            bounds,
            lambda history, *, until: check_synthetic_candidate(
                request, candidate, history, until=until
            ),
        )
        self.assertEqual(report.possible_histories, 81)
        self.assertEqual(report.evaluated_histories, 81)
        self.assertTrue(report.complete)
        self.assertTrue(report.all_passed)

    def test_temporal_profile_still_rejects_unsupported_recent_history(self):
        therapy, cell = cell_model("unsupported_recently")
        signal = cell.environment.signal("A")
        output = cell.rest()
        rule = cell.when(signal.present().recently(within=bc.Duration(2))).do(output)
        request = freeze(
            therapy, cell, ((signal, "cell"),), (("recent", rule, output, "cell"),)
        )
        with self.assertRaises(bc.UnsupportedBehaviorError) as caught:
            generate_synthetic(request, config=temporal_config())
        self.assertIsNotNone(caught.exception.node_id)
        self.assertIsNotNone(caught.exception.source)

    def test_explicit_profile_roundtrip_and_pipeline_keep_software_scope(self):
        request, history = build_request()
        with self.assertRaises(bc.UnsupportedBehaviorError):
            generate_synthetic(request)
        build = run_synthetic_pipeline(
            request, history, until=9, config=temporal_config()
        )
        candidate = build.candidate
        self.assertEqual(SyntheticCandidate.from_dict(candidate.to_dict()), candidate)
        self.assertEqual(candidate.to_dict()["intended_use"], "software_test")
        self.assertEqual(
            candidate.to_dict()["human_therapeutic_admission"], "not_admitted"
        )
        self.assertTrue(build.result.unresolved)
        self.assertEqual(
            check_synthetic_candidate(request, candidate, history, until=9).outcome,
            bc.CheckOutcome.PASS,
        )

    def test_temporal_candidate_cannot_enter_stateless_component_linking(self):
        request, history = build_request()
        candidate = generate_synthetic(request, config=temporal_config())
        with self.assertRaisesRegex(ValueError, "stateless combinational"):
            adapt_synthetic_components(request, candidate, history, until=9)

    def test_profile_catalog_and_schema_pins_reject_stale_authority(self):
        for changes in (
            {"profile_version": "biocompiler.synthetic.temporal.v999"},
            {"catalog_fingerprint": SYNTHETIC_CATALOG.fingerprint},
            {"schema_version": "biocompiler.synthetic_generator_config.v0.1"},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                SyntheticGeneratorConfig.from_dict(
                    {**temporal_config().to_dict(), **changes}
                )
        request, _ = build_request()
        candidate = generate_synthetic(request, config=temporal_config())
        with self.assertRaises(ValueError):
            SyntheticCandidate.from_dict(
                {
                    **candidate.to_dict(),
                    "schema_version": "biocompiler.synthetic_candidate.v0.2",
                }
            )


if __name__ == "__main__":
    unittest.main()
