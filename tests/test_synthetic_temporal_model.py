"""Literal timeline oracles for independent sustained, pulse and memory models."""

from dataclasses import replace
import unittest
from unittest.mock import patch

from biocompiler.errors import SerializationError
from biocompiler.ir.mechanism import MechanismNode, MechanismProgram
from biocompiler.models.synthetic import (
    ModelInputFrame,
    ModelTrace,
    SyntheticModelError,
    run_model,
)
from biocompiler.semantics.realization import Observable
from biocompiler.semantics.types import BOOLEAN, Duration, Level


def node(name, kind, inputs=(), *, scope="cell", dtype=BOOLEAN, attrs=None):
    return MechanismNode(
        name,
        kind,
        Observable(f"meaning:{name}", dtype, "observer", scope, "abstract"),
        inputs,
        {} if attrs is None else attrs,
    )


def program(*nodes, outputs=("output",)):
    return MechanismProgram("temporal fixture", nodes, outputs)


def held(*, scope="cell", duration=2):
    return program(
        node("input", "input", scope=scope),
        node("held", "held_for", ("input",), scope=scope,
             attrs={"duration": Duration(duration)}),
        node("output", "output", ("held",), scope=scope),
    )


def pulsed(*, input_scope="cell", output_scope="cell", duration=2):
    nodes = [
        node("input", "input", scope=input_scope),
        node("event", "onset", ("input",), scope=input_scope),
    ]
    trigger = "event"
    if input_scope == "contact" and output_scope == "cell":
        nodes.append(node("trigger", "any_contact", ("event",)))
        trigger = "trigger"
    return program(
        *nodes,
        node("pulse", "pulse", (trigger,), scope=output_scope,
             attrs={"duration": Duration(duration)}),
        node("output", "output", ("pulse",), scope=output_scope),
    )


def remembered(*, input_scope="cell", duration=2):
    nodes = [
        node("input", "input", scope=input_scope),
        node("reset", "input"),
        node("event", "onset", ("input",), scope=input_scope),
    ]
    trigger = "event"
    if input_scope == "contact":
        nodes.append(node("trigger", "any_contact", ("event",)))
        trigger = "trigger"
    return program(
        *nodes,
        node("memory", "memory", (trigger, "reset"),
             attrs={"duration": None if duration is None else Duration(duration)}),
        node("output", "output", ("memory",)),
    )


def values(trace, output="output"):
    return [(frame.time, frame.values[output]) for frame in trace.frames]


def cell_history(*snapshots):
    return [ModelInputFrame(time, {"input": value}) for time, value in snapshots]


def memory_history(*snapshots):
    return [
        ModelInputFrame(time, {"input": value, "reset": reset})
        for time, value, reset in snapshots
    ]


class SustainedModelTests(unittest.TestCase):
    def test_full_initial_interval_then_immediate_falling_edge(self):
        trace = run_model(held(), cell_history((0, True), (3, False)), until=4)
        self.assertEqual(values(trace), [(0, False), (2, True), (3, False), (4, False)])

    def test_interruption_at_deadline_cancels_then_restarts_full_interval(self):
        trace = run_model(held(), cell_history((0, True), (2, False), (3, True)), until=6)
        self.assertEqual(values(trace), [(0, False), (2, False), (3, False), (5, True), (6, True)])

    def test_unchanged_snapshot_does_not_restart_timer(self):
        trace = run_model(held(), cell_history((0, True), (1, True)), until=2)
        self.assertEqual(values(trace), [(0, False), (1, False), (2, True)])

    def test_horizon_truncates_before_deadline(self):
        trace = run_model(held(), cell_history((0, True)), until=1)
        self.assertEqual(values(trace), [(0, False), (1, False)])

    def test_nested_holds_schedule_causal_deadlines(self):
        first = held()
        candidate = replace(first, nodes=(
            *first.nodes[:2],
            node("second", "held_for", ("held",), attrs={"duration": Duration(3)}),
            replace(first.nodes[-1], inputs=("second",)),
        ))
        self.assertEqual(
            values(run_model(candidate, cell_history((0, True)), until=6)),
            [(0, False), (2, False), (5, True), (6, True)],
        )

    def test_contacts_have_separate_timers_and_new_episodes(self):
        trace = run_model(held(scope="contact"), [
            ModelInputFrame(0, contacts={"a": {"input": True}}),
            ModelInputFrame(1, contacts={"a": {"input": True}, "b": {"input": True}}),
            ModelInputFrame(2, contacts={"b": {"input": True}}),
            ModelInputFrame(3, contacts={"a": {"input": True}, "b": {"input": True}}),
        ], until=5)
        self.assertEqual([
            (frame.time, {key: value["output"] for key, value in frame.contacts.items()})
            for frame in trace.frames
        ], [
            (0, {"a": False}), (1, {"a": False, "b": False}),
            (2, {"b": False}), (3, {"a": False, "b": True}),
            (5, {"a": True, "b": True}),
        ])


class PulseModelTests(unittest.TestCase):
    def test_startup_trigger_and_excluded_expiry(self):
        self.assertEqual(
            values(run_model(pulsed(), cell_history((0, True)), until=3)),
            [(0, True), (2, False), (3, False)],
        )

    def test_sustained_true_does_not_refresh_on_snapshots(self):
        self.assertEqual(
            values(run_model(pulsed(), cell_history((0, True), (1, True)), until=3)),
            [(0, True), (1, True), (2, False), (3, False)],
        )

    def test_rearmed_trigger_at_expiry_refreshes_without_glitch(self):
        self.assertEqual(
            values(run_model(pulsed(), cell_history((0, True), (1, False), (2, True)), until=5)),
            [(0, True), (1, True), (2, True), (4, False), (5, False)],
        )

    def test_successive_contact_onsets_refresh_even_when_aggregate_stays_true(self):
        trace = run_model(pulsed(input_scope="contact"), [
            ModelInputFrame(0, contacts={"a": {"input": True}}),
            ModelInputFrame(1, contacts={"a": {"input": True}, "b": {"input": True}}),
        ], until=4)
        self.assertEqual(values(trace), [(0, True), (1, True), (3, False), (4, False)])

    def test_cell_pulse_survives_contact_disappearance(self):
        trace = run_model(pulsed(input_scope="contact"), [
            ModelInputFrame(0, contacts={"a": {"input": True}}), ModelInputFrame(1)
        ], until=3)
        self.assertEqual(values(trace), [(0, True), (1, True), (2, False), (3, False)])

    def test_contact_pulse_is_cleared_and_reappearance_rearms(self):
        contact = {"a": {"input": True}}
        trace = run_model(pulsed(input_scope="contact", output_scope="contact"), [
            ModelInputFrame(0, contacts=contact), ModelInputFrame(1),
            ModelInputFrame(2, contacts=contact),
        ], until=4)
        self.assertEqual([
            (frame.time, {key: value["output"] for key, value in frame.contacts.items()})
            for frame in trace.frames
        ], [(0, {"a": True}), (1, {}), (2, {"a": True}), (4, {"a": False})])

    def test_cell_event_broadcast_does_not_retrigger_for_late_contact(self):
        trace = run_model(pulsed(output_scope="contact"), [
            ModelInputFrame(0, {"input": True}, {"a": {}}),
            ModelInputFrame(1, {"input": True}, {"a": {}, "b": {}}),
        ], until=2)
        self.assertEqual([
            (frame.time, {key: value["output"] for key, value in frame.contacts.items()})
            for frame in trace.frames
        ], [(0, {"a": True}), (1, {"a": True, "b": False}), (2, {"a": False, "b": False})])


class MemoryModelTests(unittest.TestCase):
    def test_sustained_set_does_not_refresh_memory(self):
        self.assertEqual(values(run_model(remembered(), memory_history(
            (0, True, False), (1, True, False)), until=3)),
            [(0, True), (1, True), (2, False), (3, False)])

    def test_set_event_wins_old_expiry(self):
        self.assertEqual(values(run_model(remembered(), memory_history(
            (0, True, False), (1, False, False), (2, True, False)), until=4)),
            [(0, True), (1, True), (2, True), (4, False)])

    def test_reset_dominates_simultaneous_set_and_expiry(self):
        self.assertEqual(values(run_model(remembered(), memory_history(
            (0, True, False), (1, False, False), (2, True, True),
            (3, True, False)), until=4)),
            [(0, True), (1, True), (2, False), (3, False), (4, False)])

    def test_startup_reset_suppresses_set_until_new_onset(self):
        self.assertEqual(values(run_model(remembered(), memory_history(
            (0, True, True), (1, True, False), (2, False, False),
            (3, True, False)), until=5)),
            [(0, False), (1, False), (2, False), (3, True), (5, False)])

    def test_permanent_memory_retains_after_set_false_and_resets(self):
        self.assertEqual(values(run_model(remembered(duration=None), memory_history(
            (0, True, False), (1, False, False), (10, False, True)), until=11)),
            [(0, True), (1, True), (10, False), (11, False)])

    def test_contact_onsets_refresh_cell_memory_and_removal_preserves_it(self):
        trace = run_model(remembered(input_scope="contact"), [
            ModelInputFrame(0, {"reset": False}, {"a": {"input": True}}),
            ModelInputFrame(1, {"reset": False}, {"a": {"input": True}, "b": {"input": True}}),
            ModelInputFrame(2, {"reset": False}),
        ], until=4)
        self.assertEqual(values(trace), [(0, True), (1, True), (2, True), (3, False), (4, False)])

    def test_downstream_latch_never_sees_expired_or_reset_producer(self):
        # Consumer is deliberately named/specified before its producer. The
        # gate's rise coincides with producer expiry/reset; no transient true
        # producer may irreversibly latch the consumer.
        candidate = program(
            node("gate", "input"), node("set", "input"), node("reset", "input"),
            node("set_event", "onset", ("set",)),
            node("z_producer", "memory", ("set_event", "reset"), attrs={"duration": Duration(2)}),
            node("combined", "and", ("z_producer", "gate")),
            node("consume_event", "onset", ("combined",)),
            node("never", "constant", attrs={"value": False}),
            node("a_consumer", "memory", ("consume_event", "never"), attrs={"duration": None}),
            node("output", "output", ("a_consumer",)),
        )
        for time, reset in ((2, False), (1, True)):
            with self.subTest(time=time, reset=reset):
                trace = run_model(candidate, [
                    ModelInputFrame(0, {"set": True, "reset": False, "gate": False}),
                    ModelInputFrame(time, {"set": True, "reset": reset, "gate": True}),
                ], until=3)
                self.assertEqual(values(trace), [(0, False), (time, False), (3, False)])

    def test_simultaneous_producer_refresh_does_not_rearm_downstream_onset(self):
        candidate = remembered()
        candidate = replace(candidate, nodes=(
            *candidate.nodes[:-1],
            node("downstream_event", "onset", ("memory",)),
            node("downstream", "memory", ("downstream_event", "reset"),
                 attrs={"duration": Duration(3)}),
            node("output", "output", ("downstream",)),
        ))
        trace = run_model(candidate, memory_history(
            (0, True, False), (1, False, False), (2, True, False)), until=5)
        self.assertEqual(
            values(trace),
            [(0, True), (1, True), (2, True), (3, False), (4, False), (5, False)],
        )


class TemporalArtifactTests(unittest.TestCase):
    def test_temporal_roundtrips_and_independent_runner(self):
        for candidate, history in (
            (held(), cell_history((0, True))),
            (pulsed(), cell_history((0, True))),
            (remembered(), memory_history((0, True, False))),
        ):
            with self.subTest(candidate=candidate.to_dict()), patch(
                "biocompiler.semantics.evaluator.evaluate",
                side_effect=AssertionError("Independent model called its oracle"),
            ):
                restored = MechanismProgram.from_json(candidate.to_json())
                self.assertEqual(restored.fingerprint, candidate.fingerprint)
                trace = run_model(restored, history, until=3)
                self.assertEqual(ModelTrace.from_json(trace.to_json()), trace)

    def test_old_mechanism_schema_and_runner_are_rejected(self):
        data = held().to_dict()
        data["schema_version"] = "biocompiler.mechanism.synthetic.v0.1"
        with self.assertRaises(SerializationError):
            MechanismProgram.from_dict(data)
        trace = run_model(held(), cell_history((0, True))).to_dict()
        trace["model_version"] = "biocompiler.synthetic.runner.v0.1"
        with self.assertRaises(SerializationError):
            ModelTrace.from_dict(trace)

    def test_durations_are_positive_typed_values_and_null_is_memory_only(self):
        for kind in ("held_for", "pulse", "memory"):
            for duration in (0, 2, Duration(0), Duration(-1), Level(2)):
                with (
                    self.subTest(kind=kind, duration=duration),
                    self.assertRaises(SerializationError),
                ):
                    node("bad", kind, attrs={"duration": duration})
        for kind in ("held_for", "pulse"):
            with self.subTest(kind=kind), self.assertRaises(SerializationError):
                node("bad", kind, attrs={"duration": None})
        with self.assertRaises(SerializationError):
            node("bad", "onset", attrs={"duration": Duration(2)})

    def test_boolean_ports_cell_memory_and_event_triggers_are_required(self):
        for candidate in (held(), pulsed(), remembered()):
            target = (
                "held" if candidate.find("held_for")
                else "pulse" if candidate.find("pulse")
                else "memory"
            )
            with self.subTest(target=target), self.assertRaises(SerializationError):
                replace(candidate, nodes=tuple(
                    replace(item, output=replace(item.output, dtype=Level))
                    if item.id == target else item
                    for item in candidate.nodes
                ))
        for candidate, target in ((pulsed(), "pulse"), (remembered(), "memory")):
            with (
                self.subTest(target=target),
                self.assertRaisesRegex(SerializationError, "Trigger requires onset"),
            ):
                replace(candidate, nodes=tuple(
                    replace(item, inputs=("input", *item.inputs[1:]))
                    if item.id == target else item
                    for item in candidate.nodes
                ))
        candidate = remembered()
        with self.assertRaisesRegex(SerializationError, "Memory requires cell scope"):
            replace(candidate, nodes=tuple(
                replace(item, output=replace(item.output, scope="contact"))
                if item.id == "memory" else item
                for item in candidate.nodes
            ))

    def test_temporal_deadlines_must_advance_finite_representable_time(self):
        for candidate, history in (
            (held(duration=1), cell_history((0, False), (1e20, True))),
            (pulsed(duration=1), cell_history((0, False), (1e20, True))),
            (remembered(duration=1), memory_history((0, False, False), (1e20, True, False))),
            (held(duration=1e308), cell_history((0, False), (1e308, True))),
        ):
            with (
                self.subTest(kind=candidate.nodes[-2].kind),
                self.assertRaises(SyntheticModelError),
            ):
                run_model(candidate, history)

    def test_event_values_cannot_escape_as_continuous_levels(self):
        candidate = pulsed()
        event = candidate.get("event")
        invalid = (
            node("invalid", "output", ("event",)),
            node("invalid", "select", ("event", "input", "input")),
            node("invalid", "and", ("event", "input")),
            node("invalid", "held_for", ("event",),
                 attrs={"duration": Duration(2)}),
            node("invalid", "onset", ("event",)),
            node("invalid", "memory", ("event", "event"),
                 attrs={"duration": None}),
        )
        for consumer in invalid:
            with (
                self.subTest(kind=consumer.kind),
                self.assertRaisesRegex(SerializationError, "continuous level"),
            ):
                program(
                    candidate.get("input"), event, consumer,
                    node("output", "output", ("input",)),
                )

        # Event aggregation preserves event status, so a cell-level public
        # readout cannot disguise contact onsets as a persistent Boolean.
        with self.assertRaisesRegex(SerializationError, "continuous level"):
            program(
                node("input", "input", scope="contact"),
                node("event", "onset", ("input",), scope="contact"),
                node("aggregate", "any_contact", ("event",)),
                node("output", "output", ("aggregate",)),
            )


if __name__ == "__main__":
    unittest.main()
