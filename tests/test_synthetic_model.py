"""Independent synthetic graph execution, typing and temporal boundaries."""

from dataclasses import FrozenInstanceError, replace
import json
import math
import unittest
from unittest.mock import patch

from cellweave.errors import SerializationError
from cellweave.ir.mechanism import MechanismNode, MechanismProgram
from cellweave.models.synthetic import (
    MODEL_RUNNER_VERSION,
    ModelInputFrame,
    ModelTrace,
    SyntheticModelError,
    run_model,
)
from cellweave.semantics.realization import Observable
from cellweave.semantics.types import (
    BOOLEAN,
    Concentration,
    Duration,
    Level,
    ProductionRate,
)


def port(name, dtype=BOOLEAN, scope="cell", compartment="abstract"):
    return Observable(name, dtype, "responder", scope, compartment)


def node(
    name, kind, inputs=(), *, dtype=BOOLEAN, scope="cell", attrs=None, requirements=()
):
    return MechanismNode(
        name,
        kind,
        port(f"meaning:{name}", dtype, scope),
        inputs,
        attrs or {},
        requirements,
    )


def delayed(*, scope="cell", dtype=BOOLEAN, initial=False):
    return MechanismProgram(
        "inertial fixture",
        (
            node("input", "input", dtype=dtype, scope=scope),
            node(
                "delay",
                "delay",
                ("input",),
                dtype=dtype,
                scope=scope,
                attrs={"duration": Duration(2), "initial": initial},
            ),
            node(
                "output",
                "output",
                ("delay",),
                dtype=dtype,
                scope=scope,
                requirements=("response",),
            ),
        ),
        ("output",),
        ("synthetic.boolean",),
    )


def values(trace):
    return [(frame.time, frame.values["output"]) for frame in trace.frames]


class InertialModelTests(unittest.TestCase):
    def test_timer_fires_without_an_external_snapshot(self):
        trace = run_model(delayed(), [ModelInputFrame(0, {"input": True})], until=3)
        self.assertEqual(values(trace), [(0, False), (2, True), (3, True)])

    def test_transient_input_cancels_pending_transition(self):
        trace = run_model(
            delayed(),
            [ModelInputFrame(0, {"input": True}), ModelInputFrame(1, {"input": False})],
            until=3,
        )
        self.assertEqual(values(trace), [(0, False), (1, False), (3, False)])

    def test_external_input_wins_at_exact_timer_deadline(self):
        trace = run_model(
            delayed(),
            [ModelInputFrame(0, {"input": True}), ModelInputFrame(2, {"input": False})],
            until=3,
        )
        self.assertTrue(all(not value for _, value in values(trace)))

    def test_falling_transition_uses_the_same_explicit_delay(self):
        trace = run_model(
            delayed(),
            [ModelInputFrame(0, {"input": True}), ModelInputFrame(3, {"input": False})],
            until=5,
        )
        self.assertEqual(values(trace), [(0, False), (2, True), (3, True), (5, False)])

    def test_new_numeric_pending_value_restarts_full_delay(self):
        trace = run_model(
            delayed(dtype=Level, initial=0),
            [ModelInputFrame(0, {"input": 1}), ModelInputFrame(1, {"input": 2})],
            until=4,
        )
        self.assertEqual(values(trace), [(0, 0), (1, 0), (3, 2), (4, 2)])

    def test_unchanged_snapshots_do_not_retrigger_delay(self):
        program = delayed()
        a = run_model(program, [ModelInputFrame(0, {"input": True})], until=2)
        b = run_model(
            program,
            [ModelInputFrame(0, {"input": True}), ModelInputFrame(1, {"input": True})],
            until=2,
        )
        self.assertEqual(a.frames[-1].values, b.frames[-1].values)
        self.assertTrue(b.frames[-1].values["output"])

    def test_delays_cascade_in_topological_order(self):
        first = delayed()
        second = node(
            "second",
            "delay",
            ("delay",),
            attrs={"duration": Duration(3), "initial": False},
        )
        program = replace(
            first,
            nodes=(
                *first.nodes[:2],
                second,
                replace(first.nodes[-1], inputs=("second",)),
            ),
        )
        trace = run_model(program, [ModelInputFrame(0, {"input": True})], until=6)
        self.assertEqual(values(trace), [(0, False), (2, False), (5, True), (6, True)])

    def test_initial_state_and_sessions_are_independent(self):
        program = delayed(initial=True)
        trace = run_model(program, [ModelInputFrame(0, {"input": False})], until=2)
        self.assertEqual(values(trace), [(0, True), (2, False)])
        again = run_model(program, [ModelInputFrame(0, {"input": False})])
        self.assertEqual(values(again), [(0, True)])

    def test_runner_does_not_call_behavior_evaluator(self):
        with patch(
            "cellweave.semantics.evaluator.evaluate",
            side_effect=AssertionError("The independent model called its oracle"),
        ):
            trace = run_model(delayed(), [ModelInputFrame(0, {"input": True})], until=2)
        self.assertTrue(trace.frames[-1].values["output"])


class ContactModelTests(unittest.TestCase):
    def test_disappearance_cancels_contact_timer_and_reappearance_restarts(self):
        contact = {"one": {"input": True}}
        trace = run_model(
            delayed(scope="contact"),
            [
                ModelInputFrame(0, contacts=contact),
                ModelInputFrame(1),
                ModelInputFrame(2, contacts=contact),
            ],
            until=4,
        )
        self.assertEqual([frame.time for frame in trace.frames], [0, 1, 2, 4])
        self.assertFalse(trace.frames[2].contacts["one"]["output"])
        self.assertTrue(trace.frames[3].contacts["one"]["output"])

    def test_same_object_logic_then_explicit_existential_reduction(self):
        program = MechanismProgram(
            "contacts",
            (
                node("a", "input", scope="contact"),
                node("b", "input", scope="contact"),
                node("gate", "input"),
                node("match", "and", ("a", "b", "gate"), scope="contact"),
                node("any", "any_contact", ("match",)),
                node("output", "output", ("any",)),
            ),
            ("output",),
        )
        trace = run_model(
            program,
            [
                ModelInputFrame(
                    0,
                    {"gate": True},
                    {"one": {"a": True, "b": False}, "two": {"a": False, "b": True}},
                ),
                ModelInputFrame(1, {"gate": True}, {"one": {"a": True, "b": True}}),
                ModelInputFrame(2, {"gate": False}, {"one": {"a": True, "b": True}}),
                ModelInputFrame(3, {"gate": True}),
            ],
        )
        self.assertEqual(values(trace), [(0, False), (1, True), (2, False), (3, False)])

    def test_missing_contact_observation_is_not_false(self):
        with self.assertRaisesRegex(SyntheticModelError, "missing"):
            run_model(
                delayed(scope="contact"), [ModelInputFrame(0, contacts={"one": {}})]
            )


class TypedModelTests(unittest.TestCase):
    def test_compare_and_select_keep_canonical_physical_units(self):
        program = MechanismProgram(
            "units",
            (
                node("concentration", "input", dtype=Concentration),
                node(
                    "threshold",
                    "constant",
                    dtype=Concentration,
                    attrs={"value": Concentration(1, unit="M")},
                ),
                node(
                    "above",
                    "compare",
                    ("concentration", "threshold"),
                    attrs={"operator": "gt"},
                ),
                node(
                    "high",
                    "constant",
                    dtype=ProductionRate,
                    attrs={"value": ProductionRate(2)},
                ),
                node(
                    "low",
                    "constant",
                    dtype=ProductionRate,
                    attrs={"value": ProductionRate(0)},
                ),
                node(
                    "selected", "select", ("above", "high", "low"), dtype=ProductionRate
                ),
                node("output", "output", ("selected",), dtype=ProductionRate),
            ),
            ("output",),
        )
        trace = run_model(
            program,
            [
                ModelInputFrame(0, {"concentration": 500}),
                ModelInputFrame(1, {"concentration": 2000}),
            ],
        )
        self.assertEqual(values(trace), [(0, 0), (1, 2)])

    def test_boolean_and_scalar_inputs_are_not_interchangeable(self):
        for program, value in ((delayed(), 1), (delayed(dtype=Level, initial=0), True)):
            with self.subTest(value=value), self.assertRaises(SyntheticModelError):
                run_model(program, [ModelInputFrame(0, {"input": value})])

    def test_dimension_mismatch_is_rejected(self):
        with self.assertRaisesRegex(SerializationError, "dimensions"):
            MechanismProgram(
                "bad",
                (
                    node("a", "input", dtype=Duration),
                    node("b", "input", dtype=Concentration),
                    node("test", "compare", ("a", "b"), attrs={"operator": "gt"}),
                    node("output", "output", ("test",)),
                ),
                ("output",),
            )

    def test_dimensional_constants_and_duration_require_typed_units(self):
        with self.assertRaises(SerializationError):
            node("constant", "constant", dtype=Duration, attrs={"value": 5})
        with self.assertRaises(SerializationError):
            node("delay", "delay", ("input",), attrs={"duration": 2, "initial": False})
        value = Duration(2).to_dict()
        value["canonical_value"] = 20
        with self.assertRaises(SerializationError):
            node(
                "delay",
                "delay",
                ("input",),
                attrs={"duration": value, "initial": False},
            )

    def test_nonfinite_values_and_invalid_histories_fail_explicitly(self):
        for invalid in (math.inf, math.nan, -math.inf):
            with self.subTest(invalid=invalid), self.assertRaises(SyntheticModelError):
                ModelInputFrame(0, {"input": invalid})
        for times in ([], [1], [0, 0], [0, 2, 1]):
            with self.subTest(times=times), self.assertRaises(SyntheticModelError):
                run_model(
                    delayed(),
                    [ModelInputFrame(time, {"input": True}) for time in times],
                )
        with self.assertRaises(SyntheticModelError):
            run_model(delayed(), [ModelInputFrame(0, {})])


class MechanismArtifactTests(unittest.TestCase):
    def test_immutable_roundtrip_preserves_semantic_identity_and_provenance(self):
        program = delayed()
        copy = MechanismProgram.from_json(program.to_json())
        self.assertEqual(copy.fingerprint, program.fingerprint)
        self.assertEqual(copy.get("output").requirement_ids, ("response",))
        self.assertEqual(copy.get("output").output.id, "meaning:output")
        with self.assertRaises(TypeError):
            copy.get("delay").attributes["duration"]["canonical_value"] = 5
        data = copy.to_dict()
        data["nodes"][0]["output"]["id"] = "different meaning"
        self.assertNotEqual(
            MechanismProgram.from_dict(data).fingerprint, program.fingerprint
        )

    def test_cycles_missing_refs_and_implicit_reduction_are_rejected(self):
        program = delayed()
        bad_delay = replace(program.get("delay"), inputs=("delay",))
        with self.assertRaisesRegex(SerializationError, "cycle"):
            replace(
                program, nodes=(program.get("input"), bad_delay, program.get("output"))
            )
        with self.assertRaisesRegex(SerializationError, "Unknown input"):
            replace(
                program,
                nodes=(
                    program.get("input"),
                    replace(program.get("delay"), inputs=("absent",)),
                    program.get("output"),
                ),
            )
        with self.assertRaisesRegex(SerializationError, "any_contact"):
            MechanismProgram(
                "bad reduction",
                (
                    node("input", "input", scope="contact"),
                    node("output", "output", ("input",)),
                ),
                ("output",),
            )

    def test_compartment_and_role_crossings_are_explicitly_unsupported(self):
        first = node("input", "input")
        for output in (
            Observable("out", BOOLEAN, "other_role"),
            port("out", compartment="other_compartment"),
        ):
            with self.subTest(output=output), self.assertRaises(SerializationError):
                MechanismProgram(
                    "bad context",
                    (first, MechanismNode("output", "output", output, ("input",))),
                    ("output",),
                )

    def test_serialized_node_order_does_not_schedule_execution(self):
        program = delayed()
        reversed_program = replace(program, nodes=tuple(reversed(program.nodes)))
        history = [ModelInputFrame(0, {"input": True})]
        self.assertEqual(
            values(run_model(program, history, until=2)),
            values(run_model(reversed_program, history, until=2)),
        )

    def test_unknown_fields_duplicate_json_keys_and_nonfinite_json_fail(self):
        data = delayed().to_dict()
        data["extra"] = True
        with self.assertRaises(SerializationError):
            MechanismProgram.from_dict(data)
        with self.assertRaises(SerializationError):
            MechanismProgram.from_json('{"name":"a","name":"b"}')
        with self.assertRaises(SerializationError):
            MechanismProgram.from_json('{"name": NaN}')

    def test_trace_is_frozen_versioned_and_bound_to_exact_model(self):
        program = delayed()
        inputs = {"input": True}
        frame = ModelInputFrame(0, inputs)
        inputs.clear()
        trace = run_model(program, [frame], until=2)
        copy = ModelTrace.from_json(trace.to_json())
        self.assertEqual(copy.fingerprint, trace.fingerprint)
        self.assertEqual(copy.program_fingerprint, program.fingerprint)
        self.assertEqual(copy.model_version, MODEL_RUNNER_VERSION)
        with self.assertRaises(FrozenInstanceError):
            frame.time = 1
        with self.assertRaises(TypeError):
            copy.frames[-1].values["output"] = False
        data = json.loads(copy.to_json())
        data["frames"][-1]["values"]["output"] = False
        self.assertTrue(copy.frames[-1].values["output"])


if __name__ == "__main__":
    unittest.main()
