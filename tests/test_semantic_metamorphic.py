"""Behavior-preserving transformations with explicit identity/state preconditions."""

from bisect import bisect_right
import itertools
import json
import unittest

import biocompiler as bc


def contact_program():
    therapy = bc.Therapy("metamorphic-contact")
    cell = therapy.engineer("observer", cell_type="abstract_cell")
    a, b = cell.contact.marker("A"), cell.contact.marker("B")
    ready = (a.present() & b.present()).held_for(bc.Duration(1))
    ordered = (
        a.present()
        .became_true()
        .followed_by(b.present().became_true(), within=bc.Duration(2))
    )
    memory = cell.memory("seen", set_when=ready, duration=bc.Duration(2))
    local, target = cell.rest(), cell.eliminate(cell.contact)
    cell.when(ready).do(
        local.for_(bc.Duration(2)), target.for_(bc.Duration(2)), cell.report("ready")
    )
    cell.on(ordered).do(target.for_(bc.Duration(1)), cell.report("ordered"))
    cell.on(memory.is_set().became_true()).do(cell.report("memory"))
    intent = therapy.freeze()
    observations = (
        (0, {"x": (True, False), "y": (False, True)}),
        (1, {"x": (True, True), "y": (False, True)}),
        (1.5, {"x": (True, True), "y": (True, True)}),
        (3, {"y": (True, True)}),
        (3.5, {}),
        (4, {"x": (True, True)}),
    )
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
        for time, contacts in observations
    )
    return intent, bc.lower_to_behavior(intent), history


def semantic_frames(result, *, contact_inverse=None, collapse_stutter=False):
    """Compare semantic observations, keeping all events/reactions as impulses.

    The same program is required here: graph IDs and provenance stay meaningful.
    A supplied contact map is an inverse bijection, not contact aggregation.
    """
    inverse = contact_inverse or {}
    output = []
    prior = None
    for original in result.frames:
        frame = original.to_dict()
        frame.pop("microsteps")
        for collection in ("actions", "reactions", "events"):
            for item in frame[collection]:
                if item["contact_id"] is not None:
                    item["contact_id"] = inverse.get(
                        item["contact_id"], item["contact_id"]
                    )
            frame[collection].sort(key=lambda value: json.dumps(value, sort_keys=True))
        persistent = (frame["actions"], frame["states"], frame["memories"])
        if (
            not collapse_stutter
            or persistent != prior
            or frame["reactions"]
            or frame["events"]
        ):
            output.append(frame)
        prior = persistent
    return output


def independent_program(order):
    """Branches share no state writes, memory controls or output feedback."""
    therapy = bc.Therapy("metamorphic-independent")
    cell = therapy.engineer("observer", cell_type="abstract_cell")
    signals, states, memories, actions, events = {}, {}, {}, {}, {}
    for branch in order:
        signals[branch] = cell.environment.signal(branch)
        states[branch] = cell.state(
            branch + "-state", values=("idle", "latched"), initial="idle"
        )
        memories[branch] = cell.memory(
            branch + "-memory",
            set_when=signals[branch].present(),
            duration=bc.Duration(2),
        )
        cell.when(signals[branch].present()).do(states[branch].set("latched"))
        state_event = states[branch].is_("latched").became_true()
        memory_event = memories[branch].is_set().became_true()
        events[state_event.node_id] = branch + "-latched-event"
        events[memory_event.node_id] = branch + "-memory-event"
        cell.on(state_event).do(cell.report(branch + "-latched"))
        cell.on(memory_event).do(cell.report(branch + "-memory"))
        action = cell.rest()
        actions[action.node_id] = branch
        cell.when(memories[branch].is_set()).do(action.for_(bc.Duration(3)))
    behavior = bc.lower_to_behavior(therapy.freeze())
    values = (
        (0, {"alpha": True, "beta": False, "gamma": False}),
        (0.5, {"alpha": False, "beta": False, "gamma": False}),
        (1, {"alpha": False, "beta": True, "gamma": True}),
        (1.5, {"alpha": False, "beta": False, "gamma": False}),
        (2, {"alpha": True, "beta": False, "gamma": False}),
    )
    history = tuple(
        bc.InputFrame(
            time,
            {
                signals[name].node_id: bc.SignalSample(present=value)
                for name, value in sample.items()
            },
        )
        for time, sample in values
    )
    return behavior, history, states, memories, actions, events


def named_frames(result, states, memories, actions, events):
    """Declaration edits change IDs; compare explicitly named semantic outputs."""
    return tuple(
        (
            frame.time,
            tuple(
                sorted(
                    (
                        actions[item.action_id],
                        item.contact_id,
                        item.started_at,
                        item.expires_at,
                    )
                    for item in frame.actions
                )
            ),
            tuple(
                sorted(
                    (item.attributes["label"], item.contact_id)
                    for item in frame.reactions
                )
            ),
            tuple(
                sorted((events[item.node_id], item.contact_id) for item in frame.events)
            ),
            tuple(
                sorted(
                    (name, frame.states[item.node_id]) for name, item in states.items()
                )
            ),
            tuple(
                sorted(
                    (name, frame.memories[item.node_id])
                    for name, item in memories.items()
                )
            ),
        )
        for frame in result.frames
    )


class SemanticMetamorphicTests(unittest.TestCase):
    def test_consistent_bijective_contact_renaming_maps_bound_actions_and_events(self):
        _, behavior, history = contact_program()
        baseline = bc.evaluate(behavior, history, until=7)
        self.assertEqual(
            {
                item.contact_id
                for frame in baseline.frames
                for item in frame.actions
                if item.contact_id is not None
            },
            {"x", "y"},
        )
        for renaming in (
            {"x": "zeta", "y": "alpha"},
            {"x": "object-2", "y": "object-1"},
        ):
            with self.subTest(renaming=renaming):
                self.assertEqual(len(set(renaming.values())), len(renaming))
                renamed = tuple(
                    bc.InputFrame(
                        frame.time,
                        frame.signals,
                        {
                            renaming[identity]: values
                            for identity, values in frame.contacts.items()
                        },
                    )
                    for frame in history
                )
                result = bc.evaluate(behavior, renamed, until=7)
                self.assertEqual(
                    semantic_frames(
                        result,
                        contact_inverse={value: key for key, value in renaming.items()},
                    ),
                    semantic_frames(baseline),
                )

    def test_strict_intent_behavior_and_typed_history_roundtrips_preserve_execution(
        self,
    ):
        intent, behavior, history = contact_program()
        restored_intent = bc.IntentProgram.from_json(intent.to_json())
        restored_behavior = bc.BehaviorProgram.from_json(behavior.to_json())
        lowered_again = bc.lower_to_behavior(restored_intent)
        self.assertTrue(bc.verify_lowering(restored_intent, restored_behavior).passed)
        self.assertEqual(restored_behavior.fingerprint, behavior.fingerprint)
        self.assertEqual(lowered_again.fingerprint, behavior.fingerprint)
        serialized_history = json.loads(
            json.dumps([frame.to_dict() for frame in history])
        )
        restored_history = tuple(
            bc.InputFrame(
                frame["time"],
                {
                    key: bc.SignalSample(**value)
                    for key, value in frame["signals"].items()
                },
                {
                    identity: {
                        key: bc.SignalSample(**value) for key, value in values.items()
                    }
                    for identity, values in frame["contacts"].items()
                },
            )
            for frame in serialized_history
        )
        expected = bc.evaluate(behavior, history, until=7).to_dict()
        for program in (restored_behavior, lowered_again):
            self.assertEqual(
                bc.evaluate(program, restored_history, until=7).to_dict(), expected
            )
        reactions = [
            (frame["time"], item["attributes"]["label"])
            for frame in expected["frames"]
            for item in frame["reactions"]
        ]
        self.assertEqual(
            sorted(reactions),
            [(1, "ordered"), (2, "memory"), (2, "ready"), (5, "memory"), (5, "ready")],
        )

    def test_reordering_independent_declarations_preserves_named_observables(self):
        baseline = None
        fingerprints = set()
        for order in itertools.permutations(("alpha", "beta", "gamma")):
            behavior, history, *aliases = independent_program(order)
            fingerprints.add(behavior.fingerprint)
            observed = named_frames(bc.evaluate(behavior, history, until=5), *aliases)
            if baseline is None:
                baseline = observed
                reactions = [
                    (frame[0], label) for frame in baseline for label, _ in frame[2]
                ]
                self.assertIn((0, "alpha-latched"), reactions)
                self.assertIn((1, "beta-latched"), reactions)
                self.assertIn((1, "gamma-latched"), reactions)
                self.assertEqual(baseline[-1][1], ())
                self.assertEqual(
                    baseline[-1][4],
                    (("alpha", "latched"), ("beta", "latched"), ("gamma", "latched")),
                )
            with self.subTest(order=order):
                self.assertEqual(observed, baseline)
        self.assertEqual(len(fingerprints), 6)

    def test_unchanged_complete_snapshots_preserve_events_and_every_deadline(self):
        _, behavior, sparse = contact_program()
        baseline = bc.evaluate(behavior, sparse, until=7)
        times = [frame.time for frame in sparse]
        # Extra polls include exact internal deadlines; each still has the complete
        # last external snapshot, and the horizon remains fixed.
        for inserted in (
            (0.25, 0.75, 2, 2.5, 4.5, 5, 6),
            tuple(index / 4 for index in range(29)),
        ):
            all_times = sorted(set(times) | set(inserted))
            dense = tuple(
                bc.InputFrame(
                    time,
                    sparse[bisect_right(times, time) - 1].signals,
                    sparse[bisect_right(times, time) - 1].contacts,
                )
                for time in all_times
            )
            with self.subTest(inserted=len(inserted)):
                result = bc.evaluate(behavior, dense, until=7)
                self.assertEqual(
                    semantic_frames(result, collapse_stutter=True),
                    semantic_frames(baseline, collapse_stutter=True),
                )
                self.assertGreater(len(result.frames), len(baseline.frames))
        expected_deadlines = {2, 2.5, 4, 4.5, 5, 7}
        self.assertTrue(expected_deadlines <= {frame.time for frame in baseline.frames})

    def test_atomic_snapshot_mapping_order_never_becomes_execution_priority(self):
        _, behavior, history = contact_program()
        reordered = tuple(
            bc.InputFrame(
                frame.time,
                dict(reversed(tuple(frame.signals.items()))),
                {
                    identity: dict(reversed(tuple(values.items())))
                    for identity, values in reversed(tuple(frame.contacts.items()))
                },
            )
            for frame in history
        )
        self.assertEqual(
            semantic_frames(bc.evaluate(behavior, reordered, until=7)),
            semantic_frames(bc.evaluate(behavior, history, until=7)),
        )


if __name__ == "__main__":
    unittest.main()
