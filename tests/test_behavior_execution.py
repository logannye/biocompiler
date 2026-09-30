"""Observable distinctions required by the abstract behavioral execution profile."""

from __future__ import annotations

import math
import unittest

import biocompiler as bc
from biocompiler.compiler.behavior import lower_to_behavior
from biocompiler.errors import BiocompilerError, UnsupportedBehaviorError
from biocompiler.semantics.evaluator import InputFrame, SignalSample, evaluate


def model(name="trace"):
    therapy = bc.Therapy(name)
    cells = therapy.engineer("responder", cell_type="abstract_cell")
    return therapy, cells


def frame_at(result, time):
    return next(frame for frame in result.frames if frame.time == time)


def requests(frame, action, *, instantaneous=False):
    values = frame.reactions if instantaneous else frame.actions
    return tuple(value for value in values if value.action_id == action.node_id)


def reaction_times(result, action):
    return [
        frame.time
        for frame in result.frames
        for request in requests(frame, action, instantaneous=True)
    ]


class ContactExecutionTests(unittest.TestCase):
    def test_compound_condition_requires_one_contacted_object(self):
        therapy, cells = model()
        a, b = cells.contact.marker("A"), cells.contact.marker("B")
        output = cells.eliminate(cells.contact)
        cells.when(a.present() & b.present()).do(output)
        behavior = lower_to_behavior(therapy.freeze())
        split = InputFrame(
            0,
            contacts={
                "first": {
                    a.node_id: SignalSample(present=True),
                    b.node_id: SignalSample(present=False),
                },
                "second": {
                    a.node_id: SignalSample(present=False),
                    b.node_id: SignalSample(present=True),
                },
            },
        )
        together = InputFrame(
            1,
            contacts={
                "first": {
                    a.node_id: SignalSample(present=True),
                    b.node_id: SignalSample(present=True),
                }
            },
        )
        result = evaluate(behavior, [split, together])
        self.assertFalse(requests(frame_at(result, 0), output))
        self.assertEqual(
            [value.contact_id for value in requests(frame_at(result, 1), output)],
            ["first"],
        )

    def test_environment_condition_broadcasts_into_each_contact_binding(self):
        therapy, cells = model()
        a = cells.contact.marker("A")
        context = cells.environment.signal("context")
        output = cells.eliminate(cells.contact)
        cells.when(a.present() & context.present()).do(output)
        behavior = lower_to_behavior(therapy.freeze())
        contacts = {"one": {a.node_id: SignalSample(present=True)}}
        result = evaluate(
            behavior,
            [
                InputFrame(0, {context.node_id: SignalSample(present=False)}, contacts),
                InputFrame(1, {context.node_id: SignalSample(present=True)}, contacts),
            ],
        )
        self.assertFalse(requests(frame_at(result, 0), output))
        self.assertEqual(len(requests(frame_at(result, 1), output)), 1)

    def test_contact_disappearance_resets_sustained_history(self):
        therapy, cells = model()
        a = cells.contact.marker("A")
        output = cells.report("sustained")
        cells.when(a.present().held_for(bc.Duration(3))).do(output)
        behavior = lower_to_behavior(therapy.freeze())
        contact = {"same": {a.node_id: SignalSample(present=True)}}
        result = evaluate(
            behavior,
            [
                InputFrame(0, contacts=contact),
                InputFrame(2),
                InputFrame(3, contacts=contact),
            ],
            until=6,
        )
        self.assertEqual(reaction_times(result, output), [6])

    def test_time_cannot_accumulate_across_different_contact_identities(self):
        therapy, cells = model()
        a = cells.contact.marker("A")
        output = cells.report("sustained")
        cells.when(a.present().held_for(bc.Duration(3))).do(output)
        result = evaluate(
            lower_to_behavior(therapy.freeze()),
            [
                InputFrame(
                    0, contacts={"first": {a.node_id: SignalSample(present=True)}}
                ),
                InputFrame(
                    2, contacts={"second": {a.node_id: SignalSample(present=True)}}
                ),
            ],
            until=5,
        )
        self.assertEqual(reaction_times(result, output), [5])
        self.assertIsNone(frame_at(result, 5).reactions[0].contact_id)

    def test_disappearance_cancels_contact_pulse_but_not_cell_memory(self):
        therapy, cells = model()
        a = cells.contact.marker("A")
        memory = cells.memory("seen", set_when=a.present())
        output = cells.eliminate(cells.contact)
        cells.when(a.present()).do(output.for_(bc.Duration(5)))
        result = evaluate(
            lower_to_behavior(therapy.freeze()),
            [
                InputFrame(
                    0, contacts={"one": {a.node_id: SignalSample(present=True)}}
                ),
                InputFrame(1),
            ],
            until=6,
        )
        self.assertTrue(requests(frame_at(result, 0), output))
        self.assertFalse(requests(frame_at(result, 1), output))
        self.assertTrue(frame_at(result, 6).memories[memory.node_id])

    def test_local_outputs_aggregate_but_target_actions_keep_object_identity(self):
        therapy, cells = model()
        signal = cells.contact.marker("A")
        local, targeted = cells.report("any_match"), cells.eliminate(cells.contact)
        cells.when(signal.present()).do(local, targeted)
        history = [
            InputFrame(
                time,
                contacts={
                    name: {signal.node_id: SignalSample(present=True)} for name in names
                },
            )
            for time, names in [
                (0, ("first",)),
                (1, ("first", "second")),
                (2, ("second",)),
                (3, ()),
                (4, ("first",)),
            ]
        ]
        result = evaluate(lower_to_behavior(therapy.freeze()), history)
        self.assertEqual(reaction_times(result, local), [0, 4])
        self.assertTrue(
            all(
                value.contact_id is None
                for frame in result.frames
                for value in requests(frame, local, instantaneous=True)
            )
        )
        self.assertEqual(
            {value.contact_id for value in requests(frame_at(result, 1), targeted)},
            {"first", "second"},
        )


class TemporalExecutionTests(unittest.TestCase):
    def test_sustained_condition_runs_timer_without_an_input_snapshot(self):
        therapy, cells = model()
        signal = cells.environment.signal("input")
        output = cells.report("ready")
        cells.when(signal.present().held_for(bc.Duration(3))).do(output)
        result = evaluate(
            lower_to_behavior(therapy.freeze()),
            [InputFrame(0, {signal.node_id: SignalSample(present=True)})],
            until=4,
        )
        self.assertEqual(reaction_times(result, output), [3])

    def test_false_input_at_timer_deadline_prevents_sustained_activation(self):
        therapy, cells = model()
        signal = cells.environment.signal("input")
        output = cells.report("ready")
        cells.when(signal.present().held_for(bc.Duration(3))).do(output)
        result = evaluate(
            lower_to_behavior(therapy.freeze()),
            [
                InputFrame(0, {signal.node_id: SignalSample(present=True)}),
                InputFrame(3, {signal.node_id: SignalSample(present=False)}),
            ],
            until=4,
        )
        self.assertEqual(reaction_times(result, output), [])

    def test_transient_input_does_not_satisfy_sustained_guard(self):
        therapy, cells = model()
        signal = cells.environment.signal("input")
        output = cells.report("ready")
        cells.when(signal.present().held_for(bc.Duration(3))).do(output)
        result = evaluate(
            lower_to_behavior(therapy.freeze()),
            [
                InputFrame(0, {signal.node_id: SignalSample(present=True)}),
                InputFrame(2, {signal.node_id: SignalSample(present=False)}),
            ],
            until=4,
        )
        self.assertFalse(reaction_times(result, output))

    def test_recent_history_expires_at_exclusive_endpoint(self):
        therapy, cells = model()
        signal = cells.environment.signal("input")
        output = cells.rest()
        cells.when(signal.present().recently(within=bc.Duration(3))).do(output)
        result = evaluate(
            lower_to_behavior(therapy.freeze()),
            [
                InputFrame(0, {signal.node_id: SignalSample(present=True)}),
                InputFrame(1, {signal.node_id: SignalSample(present=False)}),
            ],
            until=5,
        )
        self.assertTrue(requests(frame_at(result, 1), output))
        self.assertFalse(requests(frame_at(result, 4), output))

    def test_coincident_events_do_not_satisfy_strict_order(self):
        therapy, cells = model()
        a, b = cells.environment.signal("A"), cells.environment.signal("B")
        output = cells.report("ordered")
        event = (
            a.present()
            .became_true()
            .followed_by(b.present().became_true(), within=bc.Duration(3))
        )
        cells.on(event).do(output)
        result = evaluate(
            lower_to_behavior(therapy.freeze()),
            [
                InputFrame(
                    0,
                    {
                        a.node_id: SignalSample(present=True),
                        b.node_id: SignalSample(present=True),
                    },
                )
            ],
        )
        self.assertFalse(reaction_times(result, output))

    def test_ordered_events_allow_inclusive_window_and_multiple_second_events(self):
        therapy, cells = model()
        a, b = cells.environment.signal("A"), cells.environment.signal("B")
        output = cells.report("ordered")
        cells.on(
            a.present()
            .became_true()
            .followed_by(b.present().became_true(), within=bc.Duration(3))
        ).do(output)
        history = [
            InputFrame(
                time,
                {
                    a.node_id: SignalSample(present=av),
                    b.node_id: SignalSample(present=bv),
                },
            )
            for time, av, bv in [
                (0, True, False),
                (1, False, True),
                (2, False, False),
                (3, False, True),
            ]
        ]
        result = evaluate(lower_to_behavior(therapy.freeze()), history)
        self.assertEqual(reaction_times(result, output), [1, 3])

    def test_microsteps_at_one_timestamp_do_not_count_as_strict_event_order(self):
        therapy, cells = model()
        signal = cells.environment.signal("input")
        state = cells.state("phase", values=("idle", "ready"), initial="idle")
        cells.when(signal.present()).do(state.set("ready"))
        output = cells.report("ordered")
        cells.on(
            signal.present()
            .became_true()
            .followed_by(state.is_("ready").became_true(), within=bc.Duration(3))
        ).do(output)
        result = evaluate(
            lower_to_behavior(therapy.freeze()),
            [InputFrame(0, {signal.node_id: SignalSample(present=True)})],
        )
        self.assertEqual(result.frames[-1].states[state.node_id], "ready")
        self.assertFalse(reaction_times(result, output))

    def test_continuous_actions_and_onset_reports_have_distinct_lifetimes(self):
        therapy, cells = model()
        signal = cells.environment.signal("input")
        ongoing, instant = cells.rest(), cells.report("started")
        cells.when(signal.present()).do(ongoing, instant)
        result = evaluate(
            lower_to_behavior(therapy.freeze()),
            [
                InputFrame(time, {signal.node_id: SignalSample(present=value)})
                for time, value in [(0, True), (1, True), (2, False), (3, True)]
            ],
        )
        self.assertEqual(reaction_times(result, instant), [0, 3])
        self.assertTrue(requests(frame_at(result, 1), ongoing))
        self.assertFalse(requests(frame_at(result, 2), ongoing))

    def test_extra_unchanged_snapshots_do_not_change_temporal_results(self):
        therapy, cells = model()
        signal = cells.environment.signal("input")
        output = cells.report("ready")
        cells.when(signal.present().held_for(bc.Duration(3))).do(output)
        behavior = lower_to_behavior(therapy.freeze())
        sample = {signal.node_id: SignalSample(present=True)}
        sparse = evaluate(behavior, [InputFrame(0, sample)], until=5)
        dense = evaluate(
            behavior, [InputFrame(time, sample) for time in (0, 1, 2, 4)], until=5
        )
        self.assertEqual(reaction_times(sparse, output), [3])
        self.assertEqual(reaction_times(dense, output), [3])

    def test_explicit_horizon_truncates_before_pending_timer(self):
        therapy, cells = model()
        signal = cells.environment.signal("input")
        output = cells.report("ready")
        cells.when(signal.present().held_for(bc.Duration(3))).do(output)
        result = evaluate(
            lower_to_behavior(therapy.freeze()),
            [InputFrame(0, {signal.node_id: SignalSample(present=True)})],
            until=2,
        )
        self.assertEqual(result.horizon, 2)
        self.assertEqual(result.frames[-1].time, 2)
        self.assertFalse(reaction_times(result, output))


class AtomicStateTests(unittest.TestCase):
    def test_equal_python_values_with_distinct_state_types_still_conflict(self):
        therapy, cells = model()
        signal = cells.environment.signal("input")
        state = cells.state("choice", values=("unset", True, 1), initial="unset")
        cells.when(signal.present()).do(state.set(True))
        cells.when(signal.present()).do(state.set(1))
        with self.assertRaisesRegex(BiocompilerError, "[Cc]onflict"):
            evaluate(
                lower_to_behavior(therapy.freeze()),
                [InputFrame(0, {signal.node_id: SignalSample(present=True)})],
            )

    def test_equal_concurrent_assignments_coalesce(self):
        therapy, cells = model()
        a, b = cells.environment.signal("A"), cells.environment.signal("B")
        state = cells.state("phase", values=("idle", "ready"), initial="idle")
        cells.when(a.present()).do(state.set("ready"))
        cells.when(b.present()).do(state.set("ready"))
        result = evaluate(
            lower_to_behavior(therapy.freeze()),
            [
                InputFrame(
                    0,
                    {
                        a.node_id: SignalSample(present=True),
                        b.node_id: SignalSample(present=True),
                    },
                )
            ],
        )
        self.assertEqual(result.frames[-1].states[state.node_id], "ready")

    def test_conflicting_assignments_error_instead_of_using_declaration_order(self):
        for reversed_order in (False, True):
            with self.subTest(reversed_order=reversed_order):
                therapy, cells = model()
                signal = cells.environment.signal("input")
                state = cells.state(
                    "phase", values=("idle", "first", "second"), initial="idle"
                )
                values = ("second", "first") if reversed_order else ("first", "second")
                for value in values:
                    cells.when(signal.present()).do(state.set(value))
                with self.assertRaisesRegex(BiocompilerError, "[Cc]onflict"):
                    evaluate(
                        lower_to_behavior(therapy.freeze()),
                        [InputFrame(0, {signal.node_id: SignalSample(present=True)})],
                    )

    def test_state_transition_cascades_through_same_time_microsteps(self):
        therapy, cells = model()
        signal = cells.environment.signal("input")
        state = cells.state("phase", values=("idle", "middle", "ready"), initial="idle")
        cells.when(state.is_("idle") & signal.present()).do(state.set("middle"))
        cells.when(state.is_("middle")).do(state.set("ready"))
        output = cells.report("ready")
        cells.when(state.is_("ready")).do(output)
        result = evaluate(
            lower_to_behavior(therapy.freeze()),
            [InputFrame(0, {signal.node_id: SignalSample(present=True)})],
        )
        self.assertEqual(result.frames[-1].states[state.node_id], "ready")
        self.assertEqual(reaction_times(result, output), [0])
        self.assertGreater(result.frames[-1].microsteps, 1)

    def test_nonconvergent_state_updates_are_detected(self):
        therapy, cells = model()
        state = cells.state("phase", values=("left", "right"), initial="left")
        cells.when(state.is_("left")).do(state.set("right"))
        cells.when(state.is_("right")).do(state.set("left"))
        with self.assertRaisesRegex(BiocompilerError, "[Mm]icrostep|[Cc]onverg"):
            evaluate(
                lower_to_behavior(therapy.freeze()), [InputFrame(0)], max_microsteps=8
            )


class MemoryAndPulseTests(unittest.TestCase):
    def dependent_memory_program(self):
        therapy, cells = model()
        setting, reset, gate = (
            cells.environment.signal("set"),
            cells.environment.signal("reset"),
            cells.environment.signal("gate"),
        )
        producer = cells.memory(
            "producer",
            set_when=setting.present(),
            reset_when=reset.present(),
            duration=bc.Duration(3),
        )
        consumer = cells.memory("consumer", set_when=producer.is_set() & gate.present())
        output = cells.report("consumer_latched")
        cells.when(consumer.is_set()).do(output)
        return (
            lower_to_behavior(therapy.freeze()),
            setting,
            reset,
            gate,
            producer,
            consumer,
            output,
        )

    def test_memory_consumer_does_not_latch_from_expiring_producer(self):
        behavior, setting, reset, gate, producer, consumer, output = (
            self.dependent_memory_program()
        )
        history = [
            InputFrame(
                time,
                {
                    setting.node_id: SignalSample(present=True),
                    reset.node_id: SignalSample(present=False),
                    gate.node_id: SignalSample(present=gate_value),
                },
            )
            for time, gate_value in [(0, False), (3, True)]
        ]
        result = evaluate(behavior, history)
        self.assertFalse(frame_at(result, 3).memories[producer.node_id])
        self.assertFalse(frame_at(result, 3).memories[consumer.node_id])
        self.assertFalse(reaction_times(result, output))

    def test_memory_consumer_does_not_latch_from_reset_producer(self):
        behavior, setting, reset, gate, producer, consumer, output = (
            self.dependent_memory_program()
        )
        history = [
            InputFrame(
                time,
                {
                    setting.node_id: SignalSample(present=True),
                    reset.node_id: SignalSample(present=reset_value),
                    gate.node_id: SignalSample(present=gate_value),
                },
            )
            for time, reset_value, gate_value in [(0, False, False), (1, True, True)]
        ]
        result = evaluate(behavior, history)
        self.assertFalse(frame_at(result, 1).memories[producer.node_id])
        self.assertFalse(frame_at(result, 1).memories[consumer.node_id])
        self.assertFalse(reaction_times(result, output))

    def guarded_memory_program(self):
        therapy, cells = model()
        setting = cells.environment.signal("set")
        reset = cells.environment.signal("reset")
        gate = cells.environment.signal("gate")
        memory = cells.memory(
            "seen",
            set_when=setting.present(),
            reset_when=reset.present(),
            duration=bc.Duration(3),
        )
        output = cells.report("guarded")
        cells.when(memory.is_set() & gate.present()).do(output)
        return lower_to_behavior(therapy.freeze()), setting, reset, gate, memory, output

    def test_memory_expiry_precedes_a_simultaneous_external_rule_trigger(self):
        behavior, setting, reset, gate, memory, output = self.guarded_memory_program()
        history = [
            InputFrame(
                time,
                {
                    setting.node_id: SignalSample(present=True),
                    reset.node_id: SignalSample(present=False),
                    gate.node_id: SignalSample(present=gate_value),
                },
            )
            for time, gate_value in [(0, False), (3, True)]
        ]
        result = evaluate(behavior, history)
        self.assertFalse(frame_at(result, 3).memories[memory.node_id])
        self.assertFalse(reaction_times(result, output))

    def test_memory_reset_precedes_a_simultaneous_external_rule_trigger(self):
        behavior, setting, reset, gate, memory, output = self.guarded_memory_program()
        history = [
            InputFrame(
                time,
                {
                    setting.node_id: SignalSample(present=True),
                    reset.node_id: SignalSample(present=reset_value),
                    gate.node_id: SignalSample(present=gate_value),
                },
            )
            for time, reset_value, gate_value in [(0, False, False), (1, True, True)]
        ]
        result = evaluate(behavior, history)
        self.assertFalse(frame_at(result, 1).memories[memory.node_id])
        self.assertFalse(reaction_times(result, output))

    def test_refresh_at_old_expiry_does_not_emit_a_spurious_memory_onset(self):
        therapy, cells = model()
        setting = cells.environment.signal("set")
        memory = cells.memory(
            "seen", set_when=setting.present(), duration=bc.Duration(3)
        )
        output = cells.report("memory_onset")
        cells.on(memory.is_set().became_true()).do(output)
        result = evaluate(
            lower_to_behavior(therapy.freeze()),
            [
                InputFrame(time, {setting.node_id: SignalSample(present=value)})
                for time, value in [(0, True), (1, False), (3, True)]
            ],
        )
        self.assertTrue(frame_at(result, 3).memories[memory.node_id])
        self.assertEqual(reaction_times(result, output), [0])

    def test_state_write_settles_memory_reset_before_next_rule_effect(self):
        therapy, cells = model()
        setting, stop = (
            cells.environment.signal("set"),
            cells.environment.signal("stop"),
        )
        phase = cells.state("phase", values=("active", "stopped"), initial="active")
        memory = cells.memory(
            "seen", set_when=setting.present(), reset_when=phase.is_("stopped")
        )
        cells.when(stop.present()).do(phase.set("stopped"))
        output = cells.report("stale_memory")
        cells.when(phase.is_("stopped") & memory.is_set()).do(output)
        result = evaluate(
            lower_to_behavior(therapy.freeze()),
            [
                InputFrame(
                    time,
                    {
                        setting.node_id: SignalSample(present=True),
                        stop.node_id: SignalSample(present=stopped),
                    },
                )
                for time, stopped in [(0, False), (1, True)]
            ],
        )
        self.assertEqual(frame_at(result, 1).states[phase.node_id], "stopped")
        self.assertFalse(frame_at(result, 1).memories[memory.node_id])
        self.assertFalse(reaction_times(result, output))

    def test_local_pulse_survives_loss_of_its_triggering_contact(self):
        therapy, cells = model()
        signal = cells.contact.marker("A")
        output = cells.rest()
        cells.when(signal.present()).do(output.for_(bc.Duration(3)))
        result = evaluate(
            lower_to_behavior(therapy.freeze()),
            [
                InputFrame(
                    0, contacts={"first": {signal.node_id: SignalSample(present=True)}}
                ),
                InputFrame(1),
            ],
            until=3,
        )
        (active,) = requests(frame_at(result, 1), output)
        self.assertIsNone(active.contact_id)
        self.assertFalse(requests(frame_at(result, 3), output))

    def memory_program(self):
        therapy, cells = model()
        setting, reset = (
            cells.environment.signal("set"),
            cells.environment.signal("reset"),
        )
        memory = cells.memory(
            "remembered",
            set_when=setting.present(),
            reset_when=reset.present(),
            duration=bc.Duration(3),
        )
        output = cells.report("remembered")
        cells.when(memory.is_set()).do(output)
        return lower_to_behavior(therapy.freeze()), setting, reset, memory, output

    @staticmethod
    def history(setting, reset, entries):
        return [
            InputFrame(
                time,
                {
                    setting.node_id: SignalSample(present=set_value),
                    reset.node_id: SignalSample(present=reset_value),
                },
            )
            for time, set_value, reset_value in entries
        ]

    def test_continuously_true_setting_does_not_refresh_memory_expiry(self):
        behavior, setting, reset, memory, output = self.memory_program()
        result = evaluate(
            behavior,
            self.history(
                setting, reset, [(0, True, False), (1, True, False), (2, True, False)]
            ),
            until=4,
        )
        self.assertTrue(frame_at(result, 0).memories[memory.node_id])
        self.assertFalse(frame_at(result, 3).memories[memory.node_id])
        self.assertEqual(reaction_times(result, output), [0])

    def test_new_setting_onset_refreshes_memory(self):
        behavior, setting, reset, memory, _ = self.memory_program()
        result = evaluate(
            behavior,
            self.history(
                setting,
                reset,
                [
                    (0, True, False),
                    (1, False, False),
                    (2, True, False),
                    (3, True, False),
                ],
            ),
            until=5,
        )
        self.assertTrue(frame_at(result, 3).memories[memory.node_id])
        self.assertFalse(frame_at(result, 5).memories[memory.node_id])

    def test_reset_wins_over_new_setting_and_old_expiry(self):
        behavior, setting, reset, memory, _ = self.memory_program()
        result = evaluate(
            behavior,
            self.history(
                setting, reset, [(0, True, False), (1, False, False), (3, True, True)]
            ),
        )
        self.assertFalse(frame_at(result, 3).memories[memory.node_id])

    def test_new_setting_wins_over_old_expiry_without_reset(self):
        behavior, setting, reset, memory, _ = self.memory_program()
        result = evaluate(
            behavior,
            self.history(
                setting, reset, [(0, True, False), (1, False, False), (3, True, False)]
            ),
            until=6,
        )
        self.assertTrue(frame_at(result, 3).memories[memory.node_id])
        self.assertFalse(frame_at(result, 6).memories[memory.node_id])

    def test_releasing_reset_does_not_reuse_a_consumed_setting_onset(self):
        behavior, setting, reset, memory, output = self.memory_program()
        result = evaluate(
            behavior,
            self.history(
                setting,
                reset,
                [
                    (0, True, True),
                    (1, True, False),
                    (2, False, False),
                    (3, True, False),
                ],
            ),
        )
        self.assertFalse(frame_at(result, 0).memories[memory.node_id])
        self.assertFalse(frame_at(result, 1).memories[memory.node_id])
        self.assertEqual(reaction_times(result, output), [3])

    def test_new_contact_onset_refreshes_cell_memory_while_old_contact_stays_true(self):
        therapy, cells = model()
        signal = cells.contact.marker("A")
        memory = cells.memory(
            "seen", set_when=signal.present(), duration=bc.Duration(3)
        )
        contact = {signal.node_id: SignalSample(present=True)}
        result = evaluate(
            lower_to_behavior(therapy.freeze()),
            [
                InputFrame(0, contacts={"first": contact}),
                InputFrame(2, contacts={"first": contact, "second": contact}),
                InputFrame(3, contacts={"first": contact, "second": contact}),
            ],
            until=5,
        )
        self.assertTrue(frame_at(result, 3).memories[memory.node_id])
        self.assertFalse(frame_at(result, 5).memories[memory.node_id])

    def test_pulse_retrigger_extends_instead_of_stacking(self):
        therapy, cells = model()
        signal = cells.environment.signal("input")
        output = cells.rest()
        cells.on(signal.present().became_true()).do(output.for_(bc.Duration(3)))
        result = evaluate(
            lower_to_behavior(therapy.freeze()),
            [
                InputFrame(time, {signal.node_id: SignalSample(present=value)})
                for time, value in [(0, True), (1, False), (2, True), (3, True)]
            ],
            until=5,
        )
        active = requests(frame_at(result, 3), output)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].expires_at, 5)
        self.assertFalse(requests(frame_at(result, 5), output))

    def test_condition_pulse_is_not_refreshed_by_continuous_truth(self):
        therapy, cells = model()
        signal = cells.environment.signal("input")
        output = cells.rest()
        cells.when(signal.present()).do(output.for_(bc.Duration(3)))
        result = evaluate(
            lower_to_behavior(therapy.freeze()),
            [
                InputFrame(time, {signal.node_id: SignalSample(present=True)})
                for time in (0, 1, 2)
            ],
            until=4,
        )
        self.assertTrue(requests(frame_at(result, 2), output))
        self.assertFalse(requests(frame_at(result, 3), output))


class ObservationAndBoundaryTests(unittest.TestCase):
    def test_unused_signature_argument_does_not_become_a_runtime_observation(self):
        @bc.signature
        def select(first, unused):
            return first

        therapy, cells = model()
        signal = cells.environment.signal("used")
        unused = cells.environment.signal("unused")
        output = cells.report("selected")
        cells.when(select(signal.present(), unused.present())).do(output)
        result = evaluate(
            lower_to_behavior(therapy.freeze()),
            [InputFrame(0, {signal.node_id: SignalSample(present=True)})],
        )
        self.assertEqual(reaction_times(result, output), [0])

    def test_runtime_division_by_zero_is_an_observation_error(self):
        therapy, cells = model()
        signal = cells.environment.signal("denominator")
        cells.when(1 / signal > 0).do(cells.rest())
        with self.assertRaisesRegex(BiocompilerError, "[Zz]ero|[Aa]rithmetic|[Dd]iv"):
            evaluate(
                lower_to_behavior(therapy.freeze()),
                [InputFrame(0, {signal.node_id: SignalSample(value=0)})],
            )

    def test_numeric_arithmetic_and_qualitative_observations_are_independent(self):
        therapy, cells = model()
        signal = cells.environment.signal("input", type=bc.Level)
        numeric, qualitative = cells.report("numeric"), cells.report("qualitative")
        cells.when(signal * 2 > 1).do(numeric)
        cells.when(signal.high()).do(qualitative)
        result = evaluate(
            lower_to_behavior(therapy.freeze()),
            [InputFrame(0, {signal.node_id: SignalSample(value=0.8, high=False)})],
        )
        self.assertEqual(reaction_times(result, numeric), [0])
        self.assertFalse(reaction_times(result, qualitative))

    def test_numeric_value_does_not_implicitly_define_qualitative_threshold(self):
        therapy, cells = model()
        signal = cells.environment.signal("input")
        cells.when(signal.high()).do(cells.report("high"))
        with self.assertRaisesRegex(BiocompilerError, "high|[Oo]bserv"):
            evaluate(
                lower_to_behavior(therapy.freeze()),
                [InputFrame(0, {signal.node_id: SignalSample(value=100)})],
            )

    def test_physical_signal_values_use_canonical_units(self):
        therapy, cells = model()
        signal = cells.environment.signal("input", type=bc.Concentration)
        output = cells.report("above")
        threshold = bc.Concentration(1, unit="nM")
        cells.when(signal > threshold).do(output)
        result = evaluate(
            lower_to_behavior(therapy.freeze()),
            [
                InputFrame(
                    0,
                    {signal.node_id: SignalSample(value=threshold.canonical_value * 2)},
                )
            ],
        )
        self.assertEqual(reaction_times(result, output), [0])

    def test_missing_required_observation_is_an_error(self):
        therapy, cells = model()
        signal = cells.environment.signal("input")
        cells.when(signal.present()).do(cells.rest())
        with self.assertRaisesRegex(BiocompilerError, "[Mm]issing|[Oo]bserv"):
            evaluate(lower_to_behavior(therapy.freeze()), [InputFrame(0)])

    def test_invalid_histories_and_nonfinite_values_are_rejected(self):
        therapy, cells = model()
        signal = cells.environment.signal("input")
        cells.when(signal > 0).do(cells.rest())
        behavior = lower_to_behavior(therapy.freeze())
        valid = {signal.node_id: SignalSample(value=1)}
        invalid_times = [[], [1], [0, 0], [0, -1], [0, math.nan], [0, math.inf]]
        for times in invalid_times:
            with (
                self.subTest(times=times),
                self.assertRaises((BiocompilerError, ValueError, TypeError)),
            ):
                evaluate(behavior, [InputFrame(time, valid) for time in times])
        for value in (math.nan, math.inf, -math.inf, True):
            with (
                self.subTest(value=value),
                self.assertRaises((BiocompilerError, ValueError, TypeError)),
            ):
                evaluate(
                    behavior,
                    [InputFrame(0, {signal.node_id: SignalSample(value=value)})],
                )

    def test_role_selection_and_evaluation_sessions_do_not_share_memory(self):
        therapy, first = model()
        second = therapy.engineer("other", cell_type="abstract_cell")
        first_signal, second_signal = (
            first.environment.signal("input"),
            second.environment.signal("input"),
        )
        first_memory = first.memory("seen", set_when=first_signal.present())
        second_memory = second.memory("seen", set_when=second_signal.present())
        behavior = lower_to_behavior(therapy.freeze())
        a = evaluate(
            behavior,
            [InputFrame(0, {first_signal.node_id: SignalSample(present=True)})],
            role=first.node_id,
        )
        b = evaluate(
            behavior,
            [InputFrame(0, {second_signal.node_id: SignalSample(present=False)})],
            role=second.node_id,
        )
        again = evaluate(
            behavior,
            [InputFrame(0, {first_signal.node_id: SignalSample(present=False)})],
            role=first.node_id,
        )
        self.assertTrue(a.frames[-1].memories[first_memory.node_id])
        self.assertFalse(b.frames[-1].memories[second_memory.node_id])
        self.assertFalse(again.frames[-1].memories[first_memory.node_id])
        self.assertNotIn(second_memory.node_id, a.frames[-1].memories)

    def test_execution_preserves_requirement_and_source_correspondence(self):
        therapy, cells = model()
        signal = cells.environment.signal("input")
        output = cells.report("started")
        rule = cells.when(signal.present()).do(output)
        behavior = lower_to_behavior(therapy.freeze())
        result = evaluate(
            behavior, [InputFrame(0, {signal.node_id: SignalSample(present=True)})]
        )
        (request,) = requests(result.frames[-1], output, instantaneous=True)
        self.assertEqual(request.rule_id, rule.node_id)
        self.assertTrue(request.requirement_ids)
        self.assertIsNotNone(request.source)
        self.assertIsNotNone(request.rule_source)
        with self.assertRaises(TypeError):
            request.attributes["label"] = "changed"

    def test_unsupported_integral_reports_the_lowering_boundary(self):
        therapy, cells = model()
        signal = cells.environment.signal("input")
        window = bc.Duration(3)
        cells.when(signal.integrated(over=window) > signal * window).do(cells.rest())
        with self.assertRaisesRegex(UnsupportedBehaviorError, "integrated|[Ii]ntegr"):
            lower_to_behavior(therapy.freeze())

    def test_event_action_requires_explicit_duration(self):
        therapy, cells = model()
        signal = cells.environment.signal("input")
        cells.on(signal.present().became_true()).do(cells.rest())
        with self.assertRaisesRegex(UnsupportedBehaviorError, "duration|[Pp]ulse"):
            lower_to_behavior(therapy.freeze())


if __name__ == "__main__":
    unittest.main()
