"""Coordinate frames preserve nominated origins and explicit traversal order."""

from collections.abc import Mapping
from dataclasses import FrozenInstanceError, replace
from itertools import permutations
import unittest
from unittest.mock import patch

from biocompiler.errors import SerializationError
from biocompiler.ir import molecule_records
from biocompiler.semantics import molecule_coordinates as coordinates
from biocompiler.semantics.molecule_coordinates import (
    CoordinatePath,
    CoordinateSpace,
    IndexSpan,
    MAX_MATERIALIZED_POSITIONS,
    MAX_RESIDUES,
    MAX_SPANS,
)


def space(**changes):
    values = {
        "id": "software_rna_frame",
        "alphabet": "RNA",
        "length": 10,
        "topology": "linear",
        "axis": "5prime_to_3prime",
    }
    values.update(changes)
    return CoordinateSpace(**values)


def path(spans=((2, 5),), strand="+", space_id="software_rna_frame"):
    return CoordinatePath(space_id, tuple(IndexSpan(*span) for span in spans), strand)


class MoleculeCoordinateTests(unittest.TestCase):
    def test_strict_immutable_roundtrip_of_every_coordinate_record(self):
        records = (space(), IndexSpan(2, 5), path(((8, 10), (0, 3))))
        for record in records:
            with self.subTest(schema=type(record).__name__):
                restored = type(record).from_json(record.to_json() + "\n")
                self.assertEqual(restored, record)
                self.assertEqual(restored.fingerprint, record.fingerprint)
                field = next(key for key in record.to_dict() if key != "schema_version")
                with self.assertRaises(FrozenInstanceError):
                    setattr(record, field, None)

    def test_half_open_spans_select_residues_and_preserve_exact_length(self):
        selected = path()
        self.assertEqual(selected.length, 3)
        self.assertEqual(selected.spans[0].length, 3)
        self.assertEqual(selected.positions(space()), (2, 3, 4))
        self.assertIs(selected.validate_for(space()), selected)
        whole = path(((0, 10),))
        self.assertEqual(whole.length, 10)
        self.assertEqual(whole.positions(space()), tuple(range(10)))

    def test_discontinuous_annotations_preserve_order_without_inferred_processing(self):
        selected = path(((6, 8), (1, 3), (4, 5)))
        self.assertEqual(selected.positions(space()), (6, 7, 1, 2, 4))
        self.assertEqual(selected.length, 5)
        self.assertEqual(
            tuple((item.start, item.end) for item in selected.spans),
            ((6, 8), (1, 3), (4, 5)),
        )
        self.assertEqual(CoordinatePath.from_json(selected.to_json()), selected)

    def test_reverse_strand_reverses_each_span_without_reordering_segments(self):
        selected = path(((0, 2), (5, 7)), "-")
        self.assertEqual(selected.positions(space()), (1, 0, 6, 5))
        reversed_segments = replace(selected, spans=tuple(reversed(selected.spans)))
        self.assertEqual(reversed_segments.positions(space()), (6, 5, 1, 0))
        self.assertNotEqual(selected.fingerprint, reversed_segments.fingerprint)
        self.assertNotEqual(
            selected.fingerprint, replace(selected, strand="+").fingerprint
        )

    def test_every_segment_permutation_preserves_its_traversal_and_identity(self):
        spans = ((0, 2), (4, 6), (8, 10))
        identities = set()
        for segments in permutations(spans):
            for strand in ("+", "-"):
                selected = path(segments, strand)
                expected = tuple(
                    index
                    for start, end in segments
                    for index in (
                        range(start, end)
                        if strand == "+"
                        else range(end - 1, start - 1, -1)
                    )
                )
                self.assertEqual(selected.positions(space()), expected)
                identities.add(selected.fingerprint)
        self.assertEqual(len(identities), 12)

    def test_explicit_circular_origin_crossings_are_retained_without_rotation(self):
        circular = space(id="noncoding_circle_frame", topology="circular")
        forward = path(((8, 10), (0, 3)), space_id=circular.id)
        reverse = path(((0, 3), (8, 10)), "-", space_id=circular.id)
        self.assertEqual(forward.positions(circular), (8, 9, 0, 1, 2))
        self.assertEqual(reverse.positions(circular), (2, 1, 0, 9, 8))
        self.assertEqual(forward.length, 5)
        self.assertEqual(reverse.length, 5)
        self.assertEqual(forward.spans[0], IndexSpan(8, 10))
        self.assertNotEqual(forward.fingerprint, reverse.fingerprint)
        wrapped_whole = path(((7, 10), (0, 7)), space_id=circular.id)
        self.assertEqual(wrapped_whole.length, 10)
        self.assertEqual(
            wrapped_whole.positions(circular), (7, 8, 9, 0, 1, 2, 3, 4, 5, 6)
        )

    def test_circular_gapped_path_does_not_require_artificial_origin_adjacent_segments(
        self,
    ):
        circular = space(topology="circular")
        selected = path(((8, 9), (1, 2)))
        self.assertEqual(selected.positions(circular), (8, 1))
        self.assertEqual(selected.length, 2)
        self.assertEqual(circular.topology, "circular")

    def test_circles_do_not_implicitly_wrap_out_of_bounds_or_reverse_endpoints(self):
        circular = space(topology="circular")
        with self.assertRaises(SerializationError):
            path(((8, 3),))
        for spans in (((8, 13),), ((10, 11),), ((11, 11),)):
            with self.assertRaisesRegex(SerializationError, "beyond"):
                path(spans).validate_for(circular)
        with self.assertRaisesRegex(SerializationError, "overlap"):
            path(((7, 10), (0, 8)))

    def test_overlapping_independent_feature_paths_remain_valid(self):
        first = path(((2, 7),))
        second = path(((4, 9),))
        self.assertIs(first.validate_for(space()), first)
        self.assertIs(second.validate_for(space()), second)
        self.assertEqual(
            set(first.positions(space())) & set(second.positions(space())), {4, 5, 6}
        )

    def test_self_overlap_nested_spans_and_duplicate_occurrences_are_rejected(self):
        for spans in (
            ((0, 3), (2, 5)),
            ((2, 5), (0, 3)),
            ((0, 8), (2, 3)),
            ((0, 3), (0, 3)),
            ((4, 8), (5, 6), (0, 2)),
        ):
            with self.subTest(spans=spans):
                with self.assertRaisesRegex(SerializationError, "overlap"):
                    path(spans)
        adjacent = path(((2, 4), (0, 2), (4, 6)))
        self.assertEqual(adjacent.positions(space()), (2, 3, 0, 1, 4, 5))

    def test_single_boundary_annotations_include_both_nominated_ends(self):
        for topology in ("linear", "circular"):
            declared = space(topology=topology)
            for boundary in (0, 4, 10):
                for strand in ("+", "-"):
                    selected = path(((boundary, boundary),), strand)
                    self.assertEqual(selected.length, 0)
                    self.assertEqual(selected.positions(declared, limit=0), ())
                    self.assertIs(selected.validate_for(declared), selected)
                    self.assertEqual(selected.spans[0].start, boundary)
        self.assertNotEqual(path(((0, 0),)).fingerprint, path(((10, 10),)).fingerprint)

    def test_empty_span_mixtures_and_empty_paths_are_rejected(self):
        for spans in ((), ((0, 0), (1, 2)), ((0, 1), (2, 2)), ((1, 1), (2, 2))):
            with self.assertRaises(SerializationError):
                path(spans)

    def test_space_identity_prevents_cross_form_coordinate_substitution(self):
        selected = path()
        for declared in (
            space(id="another_rna_frame"),
            space(id="template_dna_frame", alphabet="DNA"),
            space(id="processed_rna_frame", length=6),
        ):
            with self.assertRaisesRegex(
                SerializationError, "different coordinate space"
            ):
                selected.validate_for(declared)
        with self.assertRaises(SerializationError):
            selected.validate_for(None)

    def test_shorter_space_bounds_are_checked_before_position_enumeration(self):
        selected = path(((2, 6),))
        declared = space(length=5)
        with patch.object(
            coordinates,
            "range",
            create=True,
            side_effect=AssertionError("expanded invalid path"),
        ):
            with self.assertRaisesRegex(SerializationError, "beyond"):
                selected.positions(declared)

    def test_alphabet_axis_and_protein_orientation_are_explicit(self):
        for alphabet in ("DNA", "RNA"):
            declared = space(alphabet=alphabet)
            self.assertEqual(path(strand="-").positions(declared), (4, 3, 2))
            with self.assertRaisesRegex(SerializationError, "axis"):
                replace(declared, axis="N_to_C")
        protein = space(alphabet="protein", axis="N_to_C")
        self.assertEqual(path().positions(protein), (2, 3, 4))
        for selected in (path(strand="-"), path(((0, 0),), "-")):
            with self.assertRaisesRegex(SerializationError, "Protein"):
                selected.validate_for(protein)
        with self.assertRaisesRegex(SerializationError, "axis"):
            replace(protein, axis="5prime_to_3prime")

    def test_exact_integer_coordinates_reject_booleans_floats_and_coercions(self):
        for length in (0, -1, True, False, 10.0, "10", MAX_RESIDUES + 1, 10**10000):
            with self.assertRaises(SerializationError):
                space(length=length)
        for pair in (
            (-1, 1),
            (2, 1),
            (True, 2),
            (0, False),
            (0.0, 2),
            (0, 2.0),
            ("0", 2),
            (0, None),
            (0, MAX_RESIDUES + 1),
        ):
            with self.assertRaises(SerializationError):
                IndexSpan(*pair)
        self.assertEqual(space(length=MAX_RESIDUES).length, MAX_RESIDUES)
        self.assertEqual(IndexSpan(0, MAX_RESIDUES).length, MAX_RESIDUES)

    def test_invalid_nominal_choices_and_text_fail_without_coercion(self):
        for field, values in (
            ("alphabet", ("dna", "amino_acid", [], True, None)),
            ("axis", ("3prime_to_5prime", "C_to_N", [], None)),
            ("topology", ("unknown", [], None)),
            ("id", ("", " value ", "x\n", "\ud800", None)),
        ):
            for value in values:
                with self.subTest(field=field, value=repr(value)):
                    with self.assertRaises(SerializationError):
                        space(**{field: value})
        for strand in ("forward", "reverse", [], True, None):
            with self.assertRaises(SerializationError):
                path(strand=strand)
        for identity in ("", " padded ", "\ud800", None):
            with self.assertRaises(SerializationError):
                path(space_id=identity)

    def test_supplied_mutable_span_list_is_snapshotted_without_sorting(self):
        spans = [IndexSpan(7, 9), IndexSpan(0, 2)]
        selected = CoordinatePath(space().id, spans, "+")
        spans.clear()
        self.assertEqual(selected.spans, (IndexSpan(7, 9), IndexSpan(0, 2)))
        self.assertIsInstance(selected.spans, tuple)
        for spans in (None, ("not a span",), iter((IndexSpan(0, 1),))):
            with self.assertRaises(SerializationError):
                CoordinatePath(space().id, spans, "+")

    def test_span_count_bounds_precede_decoding(self):
        declared = space(length=2 * MAX_SPANS)
        maximum = path(tuple((2 * i, 2 * i + 1) for i in range(MAX_SPANS)))
        self.assertEqual(maximum.length, MAX_SPANS)
        self.assertEqual(len(maximum.positions(declared)), MAX_SPANS)
        data = maximum.to_dict()
        data["spans"].append(IndexSpan(0, 1).to_dict())
        with patch.object(
            IndexSpan, "from_dict", side_effect=AssertionError("decoded too early")
        ):
            with self.assertRaises(SerializationError):
                CoordinatePath.from_dict(data)
        with self.assertRaises(SerializationError):
            CoordinatePath(declared.id, [IndexSpan(0, 1)] * (MAX_SPANS + 1), "+")

    def test_position_view_has_default_and_hard_limits_before_materialization(self):
        declared = space(length=MAX_RESIDUES)
        large = path(((0, MAX_RESIDUES),))
        with patch.object(
            coordinates,
            "range",
            create=True,
            side_effect=AssertionError("expanded too early"),
        ):
            with self.assertRaisesRegex(SerializationError, "position-view"):
                large.positions(declared)
            with self.assertRaisesRegex(SerializationError, "position-view"):
                large.positions(declared, limit=MAX_MATERIALIZED_POSITIONS)
        tiny = path(((0, 3),))
        for limit in (-1, True, 3.0, "3", None, MAX_MATERIALIZED_POSITIONS + 1):
            with self.assertRaises(SerializationError):
                tiny.positions(declared, limit=limit)
        with self.assertRaises(SerializationError):
            tiny.positions(declared, limit=2)
        self.assertEqual(tiny.positions(declared, limit=3), (0, 1, 2))
        default = path(((0, coordinates.DEFAULT_POSITION_LIMIT),))
        self.assertEqual(
            len(default.positions(declared)), coordinates.DEFAULT_POSITION_LIMIT
        )

    def test_every_schema_rejects_missing_unknown_and_changed_fields(self):
        for record in (space(), IndexSpan(2, 5), path()):
            for field in record.to_dict():
                data = record.to_dict()
                del data[field]
                with self.assertRaises(SerializationError):
                    type(record).from_dict(data)
            for extra in ({"schema_version": "unknown"}, {"extra": True}):
                with self.assertRaises(SerializationError):
                    type(record).from_dict(record.to_dict() | extra)
            duplicate = record.to_json()[:-1] + ', "schema_version": "duplicate"}'
            with self.assertRaises(SerializationError):
                type(record).from_json(duplicate)

    def test_hostile_imports_reject_cycles_deep_nonfinite_and_excessive_records(self):
        cyclic = []
        cyclic.append(cyclic)
        deep = None
        for _ in range(molecule_records.MAX_MOLECULE_DEPTH + 2):
            deep = [deep]
        for data in (
            cyclic,
            deep,
            {"bad": object()},
            {1: True},
            {"bad": 1 << 5000},
            {"bad": float("nan")},
        ):
            with self.assertRaises(SerializationError):
                CoordinatePath.from_dict(data)
        for text in (
            "NaN",
            "Infinity",
            "\ud800",
            " " * (molecule_records.MAX_MOLECULE_JSON_BYTES + 1),
        ):
            with self.assertRaises(SerializationError):
                CoordinateSpace.from_json(text)
        with self.assertRaises(SerializationError):
            CoordinateSpace.from_dict({"bad": "x" * (MAX_RESIDUES + 1)})

    def test_huge_mapping_rejects_before_iteration(self):
        class HugeMapping(Mapping):
            def __len__(self):
                return molecule_records.MAX_MOLECULE_ITEMS

            def __iter__(self):
                raise AssertionError("must reject declared size first")

            def __getitem__(self, key):
                raise AssertionError("must reject declared size first")

        with self.assertRaisesRegex(SerializationError, "item limit"):
            CoordinatePath.from_dict(HugeMapping())

    def test_pretty_json_reserves_publication_newline_and_bounds_indentation(self):
        record = path()
        byte_count = len(record.to_json().encode())
        with patch.object(molecule_records, "MAX_MOLECULE_JSON_BYTES", byte_count):
            with self.assertRaisesRegex(SerializationError, "publication newline"):
                record.to_json()
        for indent in (-1, True, " " * 10000, 9):
            with self.assertRaises(SerializationError):
                record.to_json(indent=indent)
        self.assertEqual(CoordinatePath.from_json(record.to_json(indent=None)), record)


if __name__ == "__main__":
    unittest.main()
