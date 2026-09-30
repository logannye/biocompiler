"""Literal cross-operator timelines for the abstract behavioral semantics oracle.

Expected timelines are hand-written from the documented contract. Helpers only
name and sort observables; they never compute deadlines or trigger conditions.
"""

from dataclasses import dataclass
import unittest

import biocompiler as bc


@dataclass(frozen=True)
class Scenario:
    name: str
    history: tuple
    horizon: float
    expected: tuple


def step(time, active=(), reactions=(), memories=()):
    return time, tuple(sorted(active)), tuple(sorted(reactions)), tuple(memories)


def observable_timeline(result, actions, memories=()):
    """Drop only stutter frames, retaining every reaction and observable change."""
    timeline = []
    prior_state = None
    for frame in result.frames:
        active = []
        for action in frame.actions:
            label = actions[action.action_id]
            if action.contact_id is not None:
                label += ":" + action.contact_id
            if action.expires_at is not None:
                label += f"@{action.started_at:g}..{action.expires_at:g}"
            active.append(label)
        reactions = []
        for reaction in frame.reactions:
            label = reaction.attributes["label"]
            if reaction.contact_id is not None:
                label += ":" + reaction.contact_id
            reactions.append(label)
        current = step(
            frame.time,
            active,
            reactions,
            [frame.memories[memory.node_id] for memory in memories],
        )
        state = current[1], current[3]
        if state != prior_state or reactions:
            timeline.append(current)
        prior_state = state
    return tuple(timeline)


def cell_model(name):
    therapy = bc.Therapy(name)
    return therapy, therapy.engineer("observer", cell_type="abstract_cell")


def signal_history(signals, entries):
    return tuple(
        bc.InputFrame(
            time,
            {
                signal.node_id: bc.SignalSample(present=value)
                for signal, value in zip(signals, values)
            },
        )
        for time, *values in entries
    )


CONTACT_CASES = (
    Scenario(
        "same_object_sustains",
        ((0, {"x": (True, True)}),),
        5,
        (
            step(0, memories=(False,)),
            step(2, ("local@2..5", "target:x@2..5"), ("memory", "qualified"), (True,)),
            step(5, memories=(False,)),
        ),
    ),
    Scenario(
        "split_objects_never_combine",
        ((0, {"x": (True, False), "y": (False, True)}),),
        5,
        (step(0, memories=(False,)),),
    ),
    Scenario(
        "split_then_same_starts_new_dwell",
        ((0, {"x": (True, False), "y": (False, True)}), (1, {"x": (True, True)})),
        6,
        (
            step(0, memories=(False,)),
            step(3, ("local@3..6", "target:x@3..6"), ("memory", "qualified"), (True,)),
            step(6, memories=(False,)),
        ),
    ),
    Scenario(
        "transient_below_dwell",
        ((0, {"x": (True, True)}), (1.5, {"x": (True, False)})),
        5,
        (step(0, memories=(False,)),),
    ),
    Scenario(
        "false_at_dwell_deadline",
        ((0, {"x": (True, True)}), (2, {"x": (False, True)})),
        5,
        (step(0, memories=(False,)),),
    ),
    Scenario(
        "identity_swap_cannot_share_dwell",
        ((0, {"x": (True, True)}), (1, {"y": (True, True)})),
        6,
        (
            step(0, memories=(False,)),
            step(3, ("local@3..6", "target:y@3..6"), ("memory", "qualified"), (True,)),
            step(6, memories=(False,)),
        ),
    ),
    Scenario(
        "dropout_cancels_bound_pulse_only",
        ((0, {"x": (True, True)}), (3, {})),
        5,
        (
            step(0, memories=(False,)),
            step(2, ("local@2..5", "target:x@2..5"), ("memory", "qualified"), (True,)),
            step(3, ("local@2..5",), memories=(True,)),
            step(5, memories=(False,)),
        ),
    ),
    Scenario(
        "reappearance_is_fresh_episode",
        ((0, {"x": (True, True)}), (3, {}), (4, {"x": (True, True)})),
        9,
        (
            step(0, memories=(False,)),
            step(2, ("local@2..5", "target:x@2..5"), ("memory", "qualified"), (True,)),
            step(3, ("local@2..5",), memories=(True,)),
            step(5, memories=(False,)),
            step(6, ("local@6..9", "target:x@6..9"), ("memory", "qualified"), (True,)),
            step(9, memories=(False,)),
        ),
    ),
)

ORDER_CASES = (
    Scenario(
        "coincident_events_are_not_ordered",
        ((0, False, False), (1, True, True)),
        4,
        (step(0), step(1, ("recent",), ("recent-onset",))),
    ),
    Scenario(
        "inclusive_order_deadline_before_recent_expiry",
        ((0, True, False), (0.5, False, False), (2, False, True)),
        3,
        (step(0), step(2, ("recent",), ("ordered", "recent-onset")), step(2.5)),
    ),
    Scenario(
        "recent_endpoint_exclusive_and_order_window_past",
        ((0, True, False), (0.5, False, False), (2.5, False, True)),
        4,
        (step(0),),
    ),
    Scenario(
        "first_event_can_justify_multiple_seconds",
        (
            (0, True, False),
            (0.5, False, False),
            (1, False, True),
            (1.5, False, False),
            (2, False, True),
        ),
        3,
        (
            step(0),
            step(1, ("recent",), ("ordered", "recent-onset")),
            step(1.5),
            step(2, ("recent",), ("ordered", "recent-onset")),
            step(2.5),
        ),
    ),
)

MEMORY_CASES = (
    Scenario(
        "expiry_precedes_simultaneous_consumer_gate",
        ((0, True, False, False), (2, True, False, True)),
        4,
        (
            step(0, reactions=("producer-onset",), memories=(True, False)),
            step(2, memories=(False, False)),
        ),
    ),
    Scenario(
        "refresh_at_expiry_has_no_glitch",
        ((0, True, False, False), (1, False, False, False), (2, True, False, True)),
        4,
        (
            step(0, reactions=("producer-onset",), memories=(True, False)),
            step(2, ("consumer",), ("consumer-onset",), (True, True)),
            step(3, memories=(True, False)),
            step(4, memories=(False, False)),
        ),
    ),
    Scenario(
        "reset_dominates_refresh_and_expiry",
        (
            (0, True, False, False),
            (1, False, False, False),
            (2, True, True, True),
            (3, True, False, True),
        ),
        4,
        (
            step(0, reactions=("producer-onset",), memories=(True, False)),
            step(2, memories=(False, False)),
        ),
    ),
    Scenario(
        "reset_release_requires_new_setting_onset",
        (
            (0, True, True, True),
            (1, True, False, True),
            (2, False, False, True),
            (3, True, False, True),
        ),
        5,
        (
            step(0, memories=(False, False)),
            step(3, ("consumer",), ("consumer-onset", "producer-onset"), (True, True)),
            step(4, memories=(True, False)),
            step(5, memories=(False, False)),
        ),
    ),
    Scenario(
        "already_latched_consumer_keeps_own_expiry",
        ((0, True, False, True), (0.5, True, True, True)),
        3,
        (
            step(0, ("consumer",), ("consumer-onset", "producer-onset"), (True, True)),
            step(0.5, ("consumer",), memories=(False, True)),
            step(1, memories=(False, False)),
        ),
    ),
)

PULSE_CASES = (
    Scenario(
        "continuous_truth_does_not_refresh",
        ((0, True), (1, True), (3, True)),
        4,
        (step(0, ("pulse@0..2",), ("onset",)), step(2)),
    ),
    Scenario(
        "new_onset_replaces_old_deadline",
        ((0, True), (0.5, False), (1.5, True), (1.75, False)),
        4,
        (
            step(0, ("pulse@0..2",), ("onset",)),
            step(1.5, ("pulse@1.5..3.5",), ("onset",)),
            step(3.5),
        ),
    ),
    Scenario(
        "retrigger_at_expiry_has_no_empty_interval",
        ((0, True), (1, False), (2, True)),
        4,
        (
            step(0, ("pulse@0..2",), ("onset",)),
            step(2, ("pulse@2..4",), ("onset",)),
            step(4),
        ),
    ),
    Scenario(
        "later_retrigger_preserves_real_gap",
        ((0, True), (1, False), (2.5, True)),
        4.5,
        (
            step(0, ("pulse@0..2",), ("onset",)),
            step(2),
            step(2.5, ("pulse@2.5..4.5",), ("onset",)),
            step(4.5),
        ),
    ),
)


class SemanticRegressionMatrixTests(unittest.TestCase):
    def test_contact_dwell_pulses_and_memory_matrix(self):
        therapy, cell = cell_model("contact-matrix")
        a, b = cell.contact.marker("A"), cell.contact.marker("B")
        guard = (a.present() & b.present()).held_for(bc.Duration(2))
        memory = cell.memory("seen", set_when=guard, duration=bc.Duration(3))
        local, target = cell.rest(), cell.eliminate(cell.contact)
        cell.when(guard).do(
            local.for_(bc.Duration(3)),
            target.for_(bc.Duration(3)),
            cell.report("qualified"),
        )
        cell.on(memory.is_set().became_true()).do(cell.report("memory"))
        behavior = bc.lower_to_behavior(therapy.freeze())
        for case in CONTACT_CASES:
            history = tuple(
                bc.InputFrame(
                    time,
                    contacts={
                        identity: {
                            a.node_id: bc.SignalSample(present=values[0]),
                            b.node_id: bc.SignalSample(present=values[1]),
                        }
                        for identity, values in contacts.items()
                    },
                )
                for time, contacts in case.history
            )
            with self.subTest(case=case.name):
                result = bc.evaluate(behavior, history, until=case.horizon)
                self.assertEqual(
                    observable_timeline(
                        result,
                        {local.node_id: "local", target.node_id: "target"},
                        (memory,),
                    ),
                    case.expected,
                )

    def test_order_and_recent_window_matrix(self):
        therapy, cell = cell_model("order-matrix")
        a, b = cell.environment.signal("A"), cell.environment.signal("B")
        cell.on(
            a.present()
            .became_true()
            .followed_by(b.present().became_true(), within=bc.Duration(2))
        ).do(cell.report("ordered"))
        active = cell.rest()
        cell.when(a.present().recently(within=bc.Duration(2)) & b.present()).do(
            active, cell.report("recent-onset")
        )
        behavior = bc.lower_to_behavior(therapy.freeze())
        for case in ORDER_CASES:
            with self.subTest(case=case.name):
                result = bc.evaluate(
                    behavior, signal_history((a, b), case.history), until=case.horizon
                )
                self.assertEqual(
                    observable_timeline(result, {active.node_id: "recent"}),
                    case.expected,
                )

    def test_memory_causal_settlement_matrix(self):
        therapy, cell = cell_model("memory-matrix")
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
        active = cell.rest()
        cell.when(consumer.is_set()).do(active)
        cell.on(producer.is_set().became_true()).do(cell.report("producer-onset"))
        cell.on(consumer.is_set().became_true()).do(cell.report("consumer-onset"))
        behavior = bc.lower_to_behavior(therapy.freeze())
        for case in MEMORY_CASES:
            with self.subTest(case=case.name):
                result = bc.evaluate(
                    behavior,
                    signal_history((setting, reset, gate), case.history),
                    until=case.horizon,
                )
                self.assertEqual(
                    observable_timeline(
                        result, {active.node_id: "consumer"}, (producer, consumer)
                    ),
                    case.expected,
                )

    def test_condition_and_event_pulse_lifetime_matrix(self):
        for mode in ("condition", "event"):
            therapy, cell = cell_model("pulse-matrix-" + mode)
            signal = cell.environment.signal("trigger")
            output = cell.rest()
            guard = signal.present()
            rule = (
                cell.when(guard)
                if mode == "condition"
                else cell.on(guard.became_true())
            )
            rule.do(output.for_(bc.Duration(2)), cell.report("onset"))
            behavior = bc.lower_to_behavior(therapy.freeze())
            for case in PULSE_CASES:
                with self.subTest(mode=mode, case=case.name):
                    result = bc.evaluate(
                        behavior,
                        signal_history((signal,), case.history),
                        until=case.horizon,
                    )
                    self.assertEqual(
                        observable_timeline(result, {output.node_id: "pulse"}),
                        case.expected,
                    )


if __name__ == "__main__":
    unittest.main()
