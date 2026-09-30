"""Independent exhaustive Boolean checks, including incomplete observations."""

from collections.abc import Mapping
from dataclasses import FrozenInstanceError
from itertools import product
import json
import unittest
from unittest.mock import patch

from biocompiler.errors import SerializationError
from biocompiler.ir import circuit_logic as logic
from biocompiler.ir.circuit_logic import (
    BooleanSpec,
    CircuitSignal,
    LogicValue,
    all_equal,
    nand,
    nor,
    parity,
    xnor,
)


A = CircuitSignal("A", "a" * 64)
B = CircuitSignal("B", "b" * 64)
C = CircuitSignal("C", "c" * 64)


class BooleanTruthTableTests(unittest.TestCase):
    def test_all_sixteen_binary_functions_and_complete_evaluation(self):
        identities = set()
        for mask in range(16):
            outputs = tuple(bool(mask & (1 << row)) for row in range(4))
            spec = BooleanSpec((A, B), outputs)
            identities.add(spec.fingerprint)
            for index, (a, b) in enumerate(product((False, True), repeat=2)):
                with self.subTest(mask=mask, row=index):
                    expected = LogicValue.TRUE if outputs[index] else LogicValue.FALSE
                    self.assertIs(spec.evaluate({"A": a, "B": b}), expected)
            self.assertEqual(BooleanSpec.from_json(spec.to_json()), spec)
        self.assertEqual(len(identities), 16)

    def test_unknown_evaluation_matches_independent_completion_sets_for_all_tables(
        self,
    ):
        for mask in range(16):
            outputs = tuple(bool(mask & (1 << row)) for row in range(4))
            spec = BooleanSpec((A, B), outputs)
            for a, b in product((False, True, None), repeat=2):
                compatible = {
                    outputs[2 * int(ca) + int(cb)]
                    for ca, cb in product((False, True), repeat=2)
                    if (a is None or ca == a) and (b is None or cb == b)
                }
                expected = (
                    LogicValue.UNKNOWN
                    if len(compatible) == 2
                    else LogicValue.TRUE
                    if compatible == {True}
                    else LogicValue.FALSE
                )
                with self.subTest(mask=mask, a=a, b=b):
                    self.assertIs(spec.evaluate({"A": a, "B": b}), expected)
                    partial = {
                        key: value
                        for key, value in (("A", a), ("B", b))
                        if value is not None
                    }
                    self.assertIs(spec.evaluate(partial), expected)

    def test_named_gate_truth_tables_have_conventional_msb_order(self):
        gates = (
            (A & B, (False, False, False, True)),
            (A | B, (False, True, True, True)),
            (A ^ B, (False, True, True, False)),
            (nand(A, B), (True, True, True, False)),
            (nor(A, B), (True, False, False, False)),
            (xnor(A, B), (True, False, False, True)),
            (all_equal(A, B), (True, False, False, True)),
            (~A, (True, False)),
        )
        for spec, table in gates:
            with self.subTest(table=table):
                self.assertEqual(spec.outputs, table)

    def test_canonical_input_permutation_preserves_asymmetric_function(self):
        reordered = BooleanSpec((B, A), (False, True, False, False))
        canonical = A & ~B
        self.assertEqual(reordered, canonical)
        self.assertEqual(reordered.inputs, (A, B))
        self.assertEqual(reordered.outputs, (False, False, True, False))
        self.assertEqual(reordered.fingerprint, canonical.fingerprint)
        data = reordered.to_dict()
        data["inputs"].reverse()
        data["outputs"] = [False, True, False, False]
        self.assertEqual(BooleanSpec.from_dict(data), canonical)

    def test_every_three_input_permutation_has_same_canonical_identity(self):
        from itertools import permutations

        expected = (A & ~B) | C
        for signals in permutations((A, B, C)):
            rows = []
            for values in product((False, True), repeat=3):
                values = dict(
                    zip((signal.id for signal in signals), values, strict=True)
                )
                rows.append((values["A"] and not values["B"]) or values["C"])
            actual = BooleanSpec(signals, tuple(rows))
            self.assertEqual(actual, expected)
            self.assertEqual(actual.fingerprint, expected.fingerprint)

    def test_composed_tables_agree_with_independent_full_boolean_evaluation(self):
        expressions = (
            ((A & B) | ~C, lambda a, b, c: (a and b) or not c),
            (nand(A, B, C), lambda a, b, c: not (a and b and c)),
            (nor(A, B, C), lambda a, b, c: not (a or b or c)),
            ((A ^ C) & (B | C), lambda a, b, c: (a != c) and (b or c)),
        )
        for expression, expected in expressions:
            self.assertEqual(
                expression.outputs,
                tuple(expected(*values) for values in product((False, True), repeat=3)),
            )

    def test_parity_even_parity_and_all_equal_are_explicitly_distinct(self):
        self.assertEqual(
            parity(A, B, C).outputs,
            (False, True, True, False, True, False, False, True),
        )
        self.assertEqual(
            xnor(A, B, C).outputs,
            (True, False, False, True, False, True, True, False),
        )
        self.assertEqual(
            all_equal(A, B, C).outputs,
            (True, False, False, False, False, False, False, True),
        )
        self.assertNotEqual(xnor(A, B, C), xnor(xnor(A, B), C))
        self.assertEqual(parity(), BooleanSpec.constant(False))
        self.assertEqual(parity(A), A.expression())
        self.assertEqual(nand(A), ~A)
        self.assertEqual(nor(A), ~A)
        for gate in (xnor, all_equal):
            for values in ((), (A,)):
                with self.assertRaises(SerializationError):
                    gate(*values)
        for gate in (nand, nor):
            with self.assertRaises(SerializationError):
                gate()

    def test_semantic_identity_is_independent_of_expression_spelling(self):
        self.assertEqual((A & B).fingerprint, (B & A).fingerprint)
        self.assertEqual((~(A | B)).fingerprint, ((~A) & (~B)).fingerprint)
        self.assertEqual(((A | B) | C).fingerprint, (A | (B | C)).fingerprint)

    def test_constants_and_simplification_keep_all_observation_obligations(self):
        always_false = A & False
        always_true = A | ~A
        self.assertEqual(always_false.inputs, (A,))
        self.assertEqual(always_true.inputs, (A,))
        self.assertEqual(always_false, BooleanSpec.constant(False, inputs=(A,)))
        self.assertEqual(always_true, BooleanSpec.constant(True, inputs=(A,)))
        self.assertNotEqual(
            always_false.fingerprint, BooleanSpec.constant(False).fingerprint
        )
        self.assertEqual((always_false & B).inputs, (A, B))
        self.assertEqual((always_true | B).inputs, (A, B))
        self.assertIs(always_false.evaluate({}), LogicValue.FALSE)
        self.assertIs(always_true.evaluate({}), LogicValue.TRUE)

    def test_partial_observation_can_resolve_only_when_all_completions_agree(self):
        self.assertIs((A & B).evaluate({"A": False}), LogicValue.FALSE)
        self.assertIs((A & B).evaluate({"A": True}), LogicValue.UNKNOWN)
        self.assertIs((A | B).evaluate({"B": True}), LogicValue.TRUE)
        self.assertIs((A ^ B).evaluate({"A": False}), LogicValue.UNKNOWN)
        self.assertIs((A & B).evaluate({"A": LogicValue.FALSE}), LogicValue.FALSE)
        self.assertIs((A | B).evaluate({"A": LogicValue.TRUE}), LogicValue.TRUE)
        self.assertIs((A ^ B).evaluate({"A": LogicValue.UNKNOWN}), LogicValue.UNKNOWN)
        self.assertIs((A ^ B).evaluate({"A": None}), LogicValue.UNKNOWN)
        self.assertIs(BooleanSpec.constant(True).evaluate({}), LogicValue.TRUE)
        self.assertIs(BooleanSpec.constant(False).evaluate({}), LogicValue.FALSE)

    def test_composition_rejects_conflicting_binding_even_for_constant_functions(self):
        other = CircuitSignal("A", "d" * 64)
        for composition in (
            lambda: A & other,
            lambda: A | other,
            lambda: A ^ other,
            lambda: (A & False) | other,
            lambda: all_equal(A, other),
        ):
            with self.assertRaisesRegex(
                SerializationError, "Conflicting observation binding"
            ):
                composition()
        self.assertEqual((A & A).inputs, (A,))
        self.assertEqual((A ^ A).inputs, (A,))

    def test_reflected_boolean_operators_preserve_signals(self):
        self.assertEqual(True & A, A.expression())
        self.assertEqual(False | A, A.expression())
        self.assertEqual(True ^ A, ~A)
        self.assertEqual(False & A, BooleanSpec.constant(False, inputs=(A,)))

    def test_python_control_flow_refuses_signals_expressions_and_unknown_values(self):
        for value in (A, A & B, *LogicValue):
            with self.subTest(value=repr(value)):
                with self.assertRaises(TypeError):
                    bool(value)
        with self.assertRaises(TypeError):
            _ = A and B
        with self.assertRaises(TypeError):
            _ = A or B
        with self.assertRaises(TypeError):
            _ = not A

    def test_evaluation_rejects_silent_numeric_or_string_coercion(self):
        for value in (0, 1, 0.0, 1.0, "true", "false", "unknown", (), []):
            with self.subTest(value=value):
                with self.assertRaises(SerializationError):
                    A.expression().evaluate({"A": value})
        for observations in ({"B": True}, {0: True}, [True], {"A": True, "B": False}):
            with self.assertRaises(SerializationError):
                A.expression().evaluate(observations)
        for value in (0, 1, "true", LogicValue.TRUE, None):
            with self.assertRaises(SerializationError):
                _ = A & value
            with self.assertRaises(SerializationError):
                BooleanSpec.constant(value)


class BooleanSerializationTests(unittest.TestCase):
    def test_records_are_frozen_and_lists_are_snapshotted(self):
        inputs = [A, B]
        outputs = [False, True, True, False]
        original = BooleanSpec(inputs, outputs)
        inputs.clear()
        outputs[0] = True
        self.assertEqual(original.inputs, (A, B))
        self.assertEqual(original.outputs, (False, True, True, False))
        for record, field in ((A, "id"), (original, "outputs")):
            with self.assertRaises(FrozenInstanceError):
                setattr(record, field, None)
            self.assertEqual(type(record).from_json(record.to_json() + "\n"), record)
            self.assertEqual(type(record).from_dict(record.to_dict()), record)

    def test_invalid_signal_identifiers_and_hashes_are_rejected(self):
        for label in ("", " ", "A B", "9A", "A\n", "a-b", "é", "a" * 65, 1, "\ud800"):
            with self.subTest(label=repr(label)):
                with self.assertRaises(SerializationError):
                    CircuitSignal(label, "a" * 64)
        for binding in ("", "a" * 63, "a" * 65, "A" * 64, "g" * 64, 1):
            with self.assertRaises(SerializationError):
                CircuitSignal("A", binding)
        self.assertEqual(CircuitSignal("_a9", "a" * 64).id, "_a9")

    def test_strict_total_tables_reject_ambiguous_missing_extra_rows_and_duplicates(
        self,
    ):
        for outputs in (
            (),
            (False,),
            (False, True, False),
            (False,) * 5,
            (0, 1, 0, 1),
            None,
        ):
            with self.assertRaises(SerializationError):
                BooleanSpec((A, B), outputs)
        for inputs in (
            (A, A),
            (A, CircuitSignal("A", "b" * 64)),
            ("A",),
            None,
            iter((A,)),
        ):
            with self.assertRaises(SerializationError):
                BooleanSpec(inputs, (False, True))
        with self.assertRaises(SerializationError):
            BooleanSpec.projection("A")

    def test_every_schema_rejects_unknown_missing_and_changed_fields(self):
        for record in (A, A & B):
            for key in record.to_dict():
                data = record.to_dict()
                del data[key]
                with self.assertRaises(SerializationError):
                    type(record).from_dict(data)
            data = record.to_dict()
            data["extra"] = True
            with self.assertRaises(SerializationError):
                type(record).from_dict(data)
            data = record.to_dict()
            data["schema_version"] = "invalid"
            with self.assertRaises(SerializationError):
                type(record).from_dict(data)

    def test_json_rejects_duplicate_fields_nonfinite_numbers_and_invalid_utf8(self):
        for record in (A, A & B):
            valid = record.to_json()
            duplicate = valid[:-1] + ', "schema_version": "duplicate"}'
            for text in (duplicate, "NaN", "Infinity", "{", "\ud800", 1):
                with self.assertRaises(SerializationError):
                    type(record).from_json(text)
        data = (A & B).to_dict()
        data["outputs"][0] = float("nan")
        with self.assertRaises(SerializationError):
            BooleanSpec.from_dict(data)

    def test_maximum_table_roundtrips_with_default_pretty_json_and_lf(self):
        inputs = tuple(CircuitSignal(f"A{index}", "a" * 64) for index in range(8))
        maximum = parity(*inputs)
        self.assertEqual(len(maximum.outputs), 256)
        text = maximum.to_json() + "\n"
        self.assertLessEqual(len(text.encode()), logic.MAX_BOOLEAN_JSON_BYTES)
        self.assertEqual(BooleanSpec.from_json(text), maximum)
        self.assertIs(maximum.evaluate({}), LogicValue.UNKNOWN)

    def test_input_union_and_constructor_bounds_precede_exponential_work(self):
        inputs = tuple(CircuitSignal(f"A{index}", "a" * 64) for index in range(9))
        with self.assertRaisesRegex(SerializationError, "input limit"):
            BooleanSpec(inputs, ())
        with self.assertRaisesRegex(SerializationError, "input limit"):
            BooleanSpec.constant(False, inputs=inputs)
        with self.assertRaisesRegex(SerializationError, "input limit"):
            parity(*inputs)
        data = {
            "schema_version": BooleanSpec.schema_version,
            "inputs": [A.to_dict()] * 9,
            "outputs": [],
        }
        with self.assertRaisesRegex(SerializationError, "input limit"):
            BooleanSpec.from_dict(data)
        with self.assertRaisesRegex(SerializationError, "operand limit"):
            parity(*([True] * (logic.MAX_BOOLEAN_OPERANDS + 1)))

    def test_dictionary_resource_limits_are_checked_before_serialization(self):
        cases = (
            {"extra": [None] * logic.MAX_BOOLEAN_ITEMS},
            {"extra": "a" * (logic.MAX_BOOLEAN_TEXT_BYTES + 1)},
        )
        nested = None
        for _ in range(logic.MAX_BOOLEAN_DEPTH + 2):
            nested = [nested]
        cases += ({"extra": nested},)
        for data in cases:
            with patch.object(
                logic.json, "dumps", side_effect=AssertionError("encoded too soon")
            ):
                with self.assertRaises(SerializationError):
                    BooleanSpec.from_dict(data)
        with self.assertRaises(SerializationError):
            BooleanSpec.from_json(" " * (logic.MAX_BOOLEAN_JSON_BYTES + 1))
        with self.assertRaises(SerializationError):
            BooleanSpec.from_dict({1: True})
        with self.assertRaises(SerializationError):
            BooleanSpec.from_dict({"extra": object()})

    def test_large_mapping_is_rejected_before_iteration(self):
        class LargeMapping(Mapping):
            def __len__(self):
                return logic.MAX_BOOLEAN_ITEMS

            def __iter__(self):
                raise AssertionError("must check declared size first")

            def __getitem__(self, key):
                raise AssertionError("must check declared size first")

        with self.assertRaisesRegex(SerializationError, "item limit"):
            BooleanSpec.from_dict(LargeMapping())

    def test_serialization_reserves_publication_newline_and_bounds_indentation(self):
        original = A & B
        encoded_size = len(original.to_json().encode())
        with patch.object(logic, "MAX_BOOLEAN_JSON_BYTES", encoded_size):
            with self.assertRaisesRegex(SerializationError, "publication newline"):
                original.to_json()
        for indentation in (-1, 9, True, " " * 10000):
            with self.assertRaises(SerializationError):
                original.to_json(indent=indentation)
        self.assertEqual(json.loads(original.to_json(indent=None)), original.to_dict())


if __name__ == "__main__":
    unittest.main()
