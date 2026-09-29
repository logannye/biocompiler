"""Checks that Python authoring preserves biological expressions as data."""

from __future__ import annotations

import unittest

import cellweave as cw


class ExpressionTests(unittest.TestCase):
    def setUp(self):
        self.therapy = cw.Therapy("expressions")
        self.cells = self.therapy.engineer("responders", cell_type="T_cell")
        self.signal = self.cells.internal.signal("activation", type=cw.Level)
        self.condition = self.signal.high()

    def test_symbolic_values_cannot_control_python_branches(self):
        values = (
            self.signal,
            self.condition,
            self.signal > 0.5,
            self.condition.became_true(),
        )
        for value in values:
            with self.subTest(type=type(value).__name__), self.assertRaises(TypeError):
                bool(value)
        with self.assertRaises(TypeError):
            self.condition and self.condition
        with self.assertRaises(TypeError):
            not self.condition
        with self.assertRaises(TypeError):
            0.1 < self.signal < 0.9

    def test_boolean_and_numeric_expressions_compose(self):
        threshold = self.therapy.parameter("threshold", type=cw.Level, default=0.5)
        combined = ((self.signal * 2 + 0.1) > threshold) & ~self.signal.low()
        condition = cw.at_least(2, combined, self.signal.present(), self.signal.high())
        self.cells.when(condition).do(self.cells.report("active"))
        self.assertEqual(len(self.therapy.freeze().find(kind="rule")), 1)

    def test_counting_conditions_rejects_invalid_counts_and_inputs(self):
        for count in (-1, 3, 1.5, True):
            with self.subTest(count=count), self.assertRaises((TypeError, ValueError)):
                cw.at_least(count, self.condition, self.signal.low())
        with self.assertRaises(TypeError):
            cw.at_least(1, self.signal)

    def test_comparisons_and_addition_reject_incompatible_dimensions(self):
        concentration = self.cells.environment.signal("factor", type=cw.Concentration)
        for operation in (
            lambda: concentration > self.signal,
            lambda: concentration + self.signal,
            lambda: concentration > 1.0,
            lambda: concentration + 1.0,
        ):
            with self.subTest(operation=operation), self.assertRaises(TypeError):
                operation()

    def test_physical_units_are_retained_and_comparable(self):
        concentration = self.cells.environment.signal("factor", type=cw.Concentration)
        condition = concentration > cw.Concentration(1, unit="nM")
        self.cells.when(condition).do(self.cells.rest())
        serialized = self.therapy.freeze().to_json()
        self.assertIn("nM", serialized)
        with self.assertRaises((TypeError, ValueError)):
            cw.Duration(1, unit="nM")

    def test_duration_is_required_for_temporal_operators(self):
        duration = self.therapy.parameter("window", type=cw.Duration)
        self.cells.when(self.condition.held_for(duration)).do(self.cells.rest())
        for operation in (
            lambda: self.condition.held_for(self.signal),
            lambda: self.condition.recently(within=self.signal),
            lambda: self.signal.integrated(over=self.signal),
            lambda: self.condition.held_for(5),
        ):
            with self.subTest(operation=operation), self.assertRaises(TypeError):
                operation()

    def test_duration_values_must_be_positive(self):
        for value in (-1, 0):
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                self.condition.held_for(cw.Duration(value, unit="s"))
        invalid_default = self.therapy.parameter(
            "invalid_window", type=cw.Duration, default=cw.Duration(0)
        )
        with self.assertRaises((TypeError, ValueError)):
            self.condition.held_for(invalid_default)

    def test_integral_changes_quantity_dimension(self):
        window = self.therapy.parameter("window", type=cw.Duration)
        accumulated = self.signal.integrated(over=window)
        with self.assertRaises(TypeError):
            accumulated > self.signal
        comparison = accumulated > self.signal * window
        self.cells.when(comparison).do(self.cells.report("accumulated"))
        self.assertTrue(self.therapy.freeze().find(kind="rule"))

    def test_curve_validates_input_and_output_dimensions(self):
        response = self.therapy.parameter(
            "response", type=cw.Curve[cw.Level, cw.ProductionRate]
        )
        self.cells.when(self.condition).do(
            self.cells.secrete("factor", rate=response(self.signal))
        )
        foreign_dimension = self.cells.environment.signal(
            "concentration", type=cw.Concentration
        )
        with self.assertRaises(TypeError):
            response(foreign_dimension)
        with self.assertRaises(TypeError):
            self.cells.secrete("factor", rate=self.signal)
        with self.assertRaises(TypeError):
            self.therapy.parameter("plain", type=cw.Level)(self.signal)

    def test_curve_and_feedback_have_distinct_graph_meanings(self):
        response = self.therapy.parameter(
            "response", type=cw.Curve[cw.Level, cw.ProductionRate]
        )
        first = self.cells.secretion("mapped", product="first_factor")
        second = self.cells.secretion("controlled", product="second_factor")
        self.cells.when(self.condition).do(first.produce(rate=response(self.signal)))
        self.cells.regulate(
            "feedback",
            observed=self.signal,
            target=self.therapy.parameter("setpoint", type=cw.Level),
            actuator=second.rate,
            effect="decrease_observed",
        )
        program = self.therapy.freeze()
        (controller,) = program.find(kind="controller")
        (rule,) = program.find(kind="rule")
        self.assertNotIn(controller.id, rule.inputs)
        self.assertNotEqual(controller.inputs, rule.inputs)

    def test_default_parameters_validate_declared_type(self):
        self.therapy.parameter("level", type=cw.Level, default=0.25)
        self.therapy.parameter(
            "window", type=cw.Duration, default=cw.Duration(2, unit="min")
        )
        with self.assertRaises(TypeError):
            self.therapy.parameter("bad", type=cw.Duration, default=2)
        with self.assertRaises(TypeError):
            self.therapy.parameter("wrong", type=cw.Level, default="high")
        defaults = [p.attributes for p in self.therapy.freeze().find(kind="parameter")]
        self.assertEqual(len(defaults), 2)
        self.assertTrue(all("default" in attributes for attributes in defaults))

    def test_units_are_compared_in_canonical_scale(self):
        interval = cw.Interval(
            cw.Duration(30, unit="s"), cw.Duration(1, unit="min"), type=cw.Duration
        )
        self.therapy.parameter(
            "window_range", type=cw.Interval[cw.Duration], default=interval
        )
        with self.assertRaises(TypeError):
            cw.Interval(
                cw.Duration(2, unit="min"), cw.Duration(30, unit="s"), type=cw.Duration
            )

    def test_concrete_curve_default_survives_serialization(self):
        curve = cw.Curve(
            points=(
                (0, cw.ProductionRate(0, unit="molecules/s")),
                (1, cw.ProductionRate(2, unit="molecules/s")),
            ),
            input=cw.Level,
            output=cw.ProductionRate,
            interpolation="linear",
            extrapolation="clamp",
        )
        response = self.therapy.parameter(
            "response", type=cw.Curve[cw.Level, cw.ProductionRate], default=curve
        )
        self.cells.when(self.condition).do(
            self.cells.secrete("factor", rate=response(self.signal))
        )
        program = self.therapy.freeze()
        restored = cw.IntentProgram.from_json(program.to_json())
        (parameter,) = restored.find(kind="parameter")
        self.assertEqual(parameter.attributes["default"]["interpolation"], "linear")
        self.assertEqual(len(parameter.attributes["default"]["points"]), 2)
        self.assertEqual(restored.fingerprint, program.fingerprint)

    def test_nonfinite_quantities_and_zero_division_are_rejected(self):
        for value in (float("nan"), float("inf"), True):
            with self.subTest(value=value), self.assertRaises(TypeError):
                self.therapy.parameter("bad", type=cw.Level, default=value)
        with self.assertRaises(TypeError):
            self.signal / 0

    def test_observations_and_channels_require_scalar_types(self):
        with self.assertRaises(TypeError):
            self.cells.internal.signal(
                "curve_signal", type=cw.Curve[cw.Level, cw.Level]
            )
        with self.assertRaises(TypeError):
            self.cells.contact.marker("interval_marker", type=cw.Interval[cw.Level])
        with self.assertRaises(TypeError):
            self.therapy.channel(
                "curve_channel", scope="local", type=cw.Curve[cw.Level, cw.Level]
            )

    def test_parameter_redeclaration_rejects_different_type_or_default(self):
        self.therapy.parameter("setting", type=cw.Level, default=0.25)
        self.therapy.parameter("setting", type=cw.Level, default=0.25)
        with self.assertRaises(ValueError):
            self.therapy.parameter("setting", type=cw.Duration)
        with self.assertRaises(ValueError):
            self.therapy.parameter("setting", type=cw.Level, default=0.75)

    def test_controller_target_matches_observation_dimension(self):
        output = self.cells.secretion("output", product="factor")
        wrong_target = self.therapy.parameter("wrong", type=cw.Concentration)
        with self.assertRaises(TypeError):
            self.cells.regulate(
                "bad",
                observed=self.signal,
                target=wrong_target,
                actuator=output.rate,
                effect="decrease_observed",
            )
        self.cells.regulate(
            "interval",
            observed=self.signal,
            target=cw.Interval(0.2, 0.4, type=cw.Level),
            actuator=output.rate,
            effect="decrease_observed",
        )
        self.assertEqual(len(self.therapy.freeze().find(kind="controller")), 1)


if __name__ == "__main__":
    unittest.main()
