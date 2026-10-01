"""Nominal observation authority never supplies inferred biological measurements."""

from dataclasses import FrozenInstanceError, replace
import json
import unittest
from unittest.mock import patch

from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_logic import LogicValue
from biocompiler.ir.circuit_observations import (
    MAX_OBSERVATION_JSON_BYTES,
    MAX_OBSERVATION_TEXT_BYTES,
    CircuitObservation,
    CircuitProduct,
    NumericInterval,
    ObservationEncoding,
    ObservationEntity,
    ObservationSample,
    ObservationScope,
    ObservationWindow,
    ProductKind,
    QuantityKind,
    classify_observation,
)
from biocompiler.ir.serialization import JsonArtifact


def observation(**changes):
    # Artificial nominal identities and thresholds exercise software only.
    values = {
        "id": "software-input",
        "entity": ObservationEntity("software_fixture", "signal-A", "1", "unknown"),
        "quantity": QuantityKind.MIRNA_ACTIVITY,
        "compartment": "cytoplasm",
        "scope": ObservationScope.CELL_ACCESSIBLE,
        "window": ObservationWindow("software-origin", 1, 1, "h", "instant"),
        "encoding": ObservationEncoding("qualitative", "qualitative"),
    }
    values.update(changes)
    return CircuitObservation(**values)


def numeric_observation(**changes):
    values = {
        "encoding": ObservationEncoding(
            "numeric",
            "fixture_activity_units",
            NumericInterval(0, 1, True, False),
            NumericInterval(2, 3),
            NumericInterval(0, 4),
        ),
    }
    values.update(changes)
    return observation(**values)


class CircuitObservationTests(unittest.TestCase):
    def records(self):
        item = numeric_observation()
        return (
            item.entity,
            item.window,
            item.encoding.low,
            item.encoding,
            item,
            ObservationSample(item, 2),
            CircuitProduct(
                "software-output",
                ProductKind.RNA_PRODUCT,
                replace(item, quantity=QuantityKind.RNA_ABUNDANCE),
            ),
        )

    def test_immutable_roundtrips_retain_full_nominal_identity(self):
        for original in self.records():
            with self.subTest(record=type(original).__name__):
                restored = type(original).from_json(original.to_json() + "\n")
                self.assertEqual(restored, original)
                self.assertEqual(restored.fingerprint, original.fingerprint)
                field = next(
                    key for key in original.to_dict() if key != "schema_version"
                )
                with self.assertRaises(FrozenInstanceError):
                    setattr(original, field, None)

    def test_imports_reject_unknown_missing_changed_and_duplicate_fields(self):
        for item in self.records():
            for field in item.to_dict():
                data = item.to_dict()
                del data[field]
                with self.subTest(record=type(item).__name__, missing=field):
                    with self.assertRaises(SerializationError):
                        type(item).from_dict(data)
            for extra in ({"extra": True}, {"schema_version": "unknown.v99"}):
                with self.assertRaises(SerializationError):
                    type(item).from_dict(item.to_dict() | extra)
            duplicate = item.to_json()[:-1] + ', "schema_version": "duplicate"}'
            with self.assertRaises(SerializationError):
                type(item).from_json(duplicate)

    def test_entity_unknowns_are_explicit_and_not_wildcards(self):
        item = observation()
        for field in ("namespace", "accession", "version", "isoform"):
            for value in (None, "", "   ", " label ", "x\n", True):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(SerializationError):
                        replace(item.entity, **{field: value})
            changed = replace(item, entity=replace(item.entity, **{field: "different"}))
            self.assertNotEqual(changed.fingerprint, item.fingerprint)
            with self.assertRaisesRegex(SerializationError, "identity"):
                classify_observation(item, ObservationSample(changed, "HIGH"))

    def test_all_quantity_kinds_remain_nominally_distinct(self):
        item = observation()
        identities = set()
        for kind in QuantityKind:
            changed = replace(item, quantity=kind)
            identities.add(changed.fingerprint)
            if kind != item.quantity:
                with self.assertRaisesRegex(SerializationError, "identity"):
                    classify_observation(item, ObservationSample(changed, "HIGH"))
        self.assertEqual(len(identities), len(QuantityKind))

    def test_mimic_dose_does_not_become_intracellular_activity(self):
        intracellular = numeric_observation()
        supplied_dose = replace(
            intracellular,
            quantity=QuantityKind.LIGAND_CONCENTRATION,
            compartment="extracellular",
            scope=ObservationScope.EXTERNAL,
            encoding=replace(intracellular.encoding, unit="nM"),
        )
        with self.assertRaisesRegex(SerializationError, "identity"):
            classify_observation(intracellular, ObservationSample(supplied_dose, 2))

    def test_numerically_equal_representations_do_not_change_pinned_authority(self):
        item = numeric_observation()
        changed = replace(item, window=replace(item.window, start=1.0))
        self.assertEqual(item.to_dict(), changed.to_dict())
        self.assertNotEqual(item.fingerprint, changed.fingerprint)
        with self.assertRaisesRegex(SerializationError, "identity"):
            classify_observation(item, ObservationSample(changed, 2))

    def test_compartment_scope_unit_time_and_encoding_are_authoritative(self):
        item = numeric_observation()
        changes = (
            replace(item, compartment="nucleus"),
            replace(item, scope=ObservationScope.EVALUATOR),
            replace(item, scope=ObservationScope.EXTERNAL),
            replace(item, encoding=replace(item.encoding, unit="another_unit")),
            replace(
                item, encoding=replace(item.encoding, high=NumericInterval(2.5, 3))
            ),
            replace(item, window=replace(item.window, reference="another-origin")),
            replace(item, window=replace(item.window, start=60, end=60, unit="min")),
            replace(item, window=replace(item.window, start=0, aggregation="mean")),
            replace(
                item,
                window=ObservationWindow("unknown", None, None, "unknown", "unknown"),
            ),
        )
        for changed in changes:
            with self.subTest(changed=changed):
                with self.assertRaisesRegex(SerializationError, "identity"):
                    classify_observation(item, ObservationSample(changed, 3))

    def test_qualitative_labels_do_not_create_numeric_cutoffs(self):
        item = observation()
        for value, expected in (
            ("HIGH", LogicValue.TRUE),
            ("LOW", LogicValue.FALSE),
            ("UNKNOWN", LogicValue.UNKNOWN),
        ):
            self.assertIs(
                classify_observation(item, ObservationSample(item, value)), expected
            )
        for value in (0, 1, True, None, "high", "TRUE"):
            with self.assertRaises(SerializationError):
                ObservationSample(item, value)
        with self.assertRaises(SerializationError):
            ObservationEncoding("qualitative", "nM")
        with self.assertRaises(SerializationError):
            ObservationEncoding("qualitative", "qualitative", NumericInterval(0, 1))

    def test_numeric_boundaries_gaps_and_out_of_range_are_explicit(self):
        item = numeric_observation()
        for value, expected in (
            (-1, LogicValue.UNKNOWN),
            (0, LogicValue.FALSE),
            (0.5, LogicValue.FALSE),
            (1, LogicValue.UNKNOWN),
            (1.5, LogicValue.UNKNOWN),
            (2, LogicValue.TRUE),
            (3, LogicValue.TRUE),
            (3.5, LogicValue.UNKNOWN),
            (4, LogicValue.UNKNOWN),
            (5, LogicValue.UNKNOWN),
            ("UNKNOWN", LogicValue.UNKNOWN),
        ):
            with self.subTest(value=value):
                self.assertIs(
                    classify_observation(item, ObservationSample(item, value)), expected
                )
        for value in (True, False, None, "HIGH", float("inf"), float("nan"), 10**400):
            with self.assertRaises(SerializationError):
                ObservationSample(item, value)

    def test_missing_and_ambiguous_are_unknown_even_for_qualitative(self):
        for item in (observation(), numeric_observation()):
            for status in ("missing", "ambiguous"):
                self.assertIs(
                    classify_observation(item, ObservationSample(item, None, status)),
                    LogicValue.UNKNOWN,
                )
                with self.assertRaises(SerializationError):
                    ObservationSample(item, 0, status)
            with self.assertRaises(SerializationError):
                ObservationSample(item, None, "not-measured")

    def test_adjacent_intervals_must_not_both_include_shared_boundary(self):
        with self.assertRaisesRegex(SerializationError, "overlap"):
            ObservationEncoding(
                "numeric", "1", NumericInterval(0, 1), NumericInterval(1, 2)
            )
        for low_inclusive, high_inclusive in (
            (True, False),
            (False, True),
            (False, False),
        ):
            encoding = ObservationEncoding(
                "numeric",
                "1",
                NumericInterval(0, 1, True, low_inclusive),
                NumericInterval(1, 2, high_inclusive, True),
            )
            item = numeric_observation(encoding=encoding)
            expected = (
                LogicValue.FALSE
                if low_inclusive
                else LogicValue.TRUE
                if high_inclusive
                else LogicValue.UNKNOWN
            )
            self.assertIs(
                classify_observation(item, ObservationSample(item, 1)), expected
            )

    def test_invalid_intervals_and_containment(self):
        for args in (
            (2, 1),
            (0, 0, False, True),
            (0, 0, True, False),
            (True, 1),
            (0, float("inf")),
            (0, 1, 1, True),
        ):
            with self.assertRaises(SerializationError):
                NumericInterval(*args)
        single = NumericInterval(1, 1)
        self.assertTrue(single.contains(1))
        self.assertFalse(single.contains(0))
        with self.assertRaises(SerializationError):
            ObservationEncoding(
                "numeric", "1", NumericInterval(3, 4), NumericInterval(0, 1)
            )
        for allowed in (NumericInterval(0, 4, False, True), NumericInterval(0, 2.5)):
            with self.assertRaisesRegex(SerializationError, "Allowed range"):
                replace(numeric_observation().encoding, allowed_range=allowed)

    def test_observation_windows_preserve_unknown_and_exact_timing(self):
        unknown = ObservationWindow("unknown", None, None, "unknown", "unknown")
        self.assertEqual(ObservationWindow.from_json(unknown.to_json()), unknown)
        instant = ObservationWindow("trigger", 1, 1, "s", "instant")
        for change in (
            {"aggregation": "unsupported"},
            {"start": 2},
            {"unit": "fortnight"},
            {"start": None},
            {"end": float("inf")},
            {"reference": "unknown"},
            {"aggregation": "mean"},
            {"aggregation": "unknown"},
        ):
            with self.assertRaises(SerializationError):
                replace(instant, **change)
        for change in ({"reference": "trigger"}, {"unit": "s"}, {"start": 0}):
            with self.assertRaises(SerializationError):
                replace(unknown, **change)
        for mode in ("mean", "integral", "any", "all"):
            self.assertEqual(
                ObservationWindow("trigger", -1, 1, "s", mode).aggregation, mode
            )

    def test_product_kinds_require_distinct_output_quantities(self):
        mapping = {
            ProductKind.PROTEIN_EXPRESSION: QuantityKind.TRANSLATION_RATE,
            ProductKind.MATURE_PROTEIN_QUANTITY: QuantityKind.PROTEIN_ABUNDANCE,
            ProductKind.REPORTER_FLUORESCENCE: QuantityKind.FLUORESCENCE,
            ProductKind.BIOLOGICAL_ACTIVITY: QuantityKind.DOWNSTREAM_ACTIVITY,
            ProductKind.RNA_PRODUCT: QuantityKind.RNA_ABUNDANCE,
        }
        for kind, quantity in mapping.items():
            for observed_quantity in QuantityKind:
                item = observation(quantity=observed_quantity)
                if observed_quantity == quantity:
                    self.assertEqual(
                        CircuitProduct("output", kind, item).observation, item
                    )
                else:
                    with self.assertRaisesRegex(
                        SerializationError, "different semantics"
                    ):
                        CircuitProduct("output", kind, item)

    def test_direct_authoring_requires_typed_nominal_kinds(self):
        item = observation()
        with self.assertRaises(SerializationError):
            replace(item, quantity="mirna_activity")
        with self.assertRaises(SerializationError):
            replace(item, scope="cell_accessible")
        with self.assertRaises(SerializationError):
            CircuitProduct(
                "output",
                "rna_product",
                replace(item, quantity=QuantityKind.RNA_ABUNDANCE),
            )
        imported = CircuitObservation.from_dict(item.to_dict())
        self.assertIsInstance(imported.quantity, QuantityKind)
        self.assertIsInstance(imported.scope, ObservationScope)

    def test_invalid_choice_types_raise_schema_errors(self):
        item = observation()
        for value in ([], {}, True, None):
            with self.assertRaises(SerializationError):
                replace(item.encoding, mode=value)
            with self.assertRaises(SerializationError):
                replace(item.window, aggregation=value)
            with self.assertRaises(SerializationError):
                replace(item.window, unit=value)
            with self.assertRaises(SerializationError):
                ObservationSample(item, None, status=value)
        with self.assertRaises(SerializationError):
            replace(numeric_observation().encoding, unit="unknown")

    def test_bounded_inputs_reject_large_deep_and_nonfinite_data(self):
        item = observation()
        for value in ("a" * (MAX_OBSERVATION_TEXT_BYTES + 1), "\ud800"):
            with self.assertRaises(SerializationError):
                replace(item, id=value)
        with self.assertRaises(SerializationError):
            CircuitObservation.from_json(" " * (MAX_OBSERVATION_JSON_BYTES + 1))
        deep = {"x": None}
        for _ in range(30):
            deep = {"x": deep}
        for data in (deep, {"x": [0] * 1000}, {"x": object()}, {1: "non-string-key"}):
            with self.assertRaises(SerializationError):
                CircuitObservation.from_dict(data)
        for value in ("NaN", "Infinity", "-Infinity"):
            with self.assertRaises(SerializationError):
                NumericInterval.from_json(
                    json.dumps(NumericInterval(0, 1).to_dict()).replace(
                        '"upper": 1', '"upper": ' + value
                    )
                )

    def test_oversized_text_rejected_before_stripping_or_encoding(self):
        class ExpensiveText(str):
            def strip(self, *args):
                raise AssertionError("oversized text must be rejected before stripping")

            def encode(self, *args, **kwargs):
                raise AssertionError("oversized text must be rejected before encoding")

        item = observation()
        oversized = ExpensiveText("x" * (MAX_OBSERVATION_TEXT_BYTES + 1))
        with self.assertRaisesRegex(SerializationError, "text limit"):
            replace(item, id=oversized)
        with self.assertRaisesRegex(SerializationError, "text limit"):
            CircuitObservation.from_dict(item.to_dict() | {"id": oversized})
        with self.assertRaisesRegex(SerializationError, "byte limit"):
            CircuitObservation.from_json(
                ExpensiveText("x" * (MAX_OBSERVATION_JSON_BYTES + 1))
            )
        # Character-count checks do not replace the UTF-8 byte budget.
        with self.assertRaisesRegex(SerializationError, "text limit"):
            replace(item, id="é" * MAX_OBSERVATION_TEXT_BYTES)
        with self.assertRaisesRegex(SerializationError, "byte limit"):
            CircuitObservation.from_json("é" * MAX_OBSERVATION_JSON_BYTES)

    def test_all_ascii_controls_including_del_are_rejected(self):
        item = observation()
        for control in (*range(32), 127):
            with self.subTest(control=control):
                with self.assertRaises(SerializationError):
                    replace(item, id="name" + chr(control) + "suffix")
                with self.assertRaises(SerializationError):
                    CircuitObservation.from_dict(
                        item.to_dict()
                        | {"compartment": "cell" + chr(control) + "space"}
                    )

    def test_indentation_is_bounded_before_encoding(self):
        item = observation()
        for indent in (-1, 9, True, False, 1.0, " " * 10000, [], {}):
            with self.subTest(indent=repr(indent)[:40]):
                with patch.object(
                    JsonArtifact,
                    "to_json",
                    side_effect=AssertionError("encoded too soon"),
                ):
                    with self.assertRaisesRegex(SerializationError, "indentation"):
                        item.to_json(indent=indent)
        for indent in (None, 0, 8):
            self.assertEqual(json.loads(item.to_json(indent=indent)), item.to_dict())


if __name__ == "__main__":
    unittest.main()
