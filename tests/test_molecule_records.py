"""Generic molecular authority has bounded strict input and streamed output."""

from collections.abc import Mapping
from dataclasses import replace
import unittest
from unittest.mock import patch

from biocompiler.errors import SerializationError
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.ir.molecule_records import (
    DeclarationProvenance,
    MAX_MOLECULE_ITEMS,
    MAX_MOLECULE_DEPTH,
    MAX_MOLECULE_JSON_BYTES,
)
from examples.circuit_molecules import make_molecule_record


class MoleculeRecordTests(unittest.TestCase):
    def test_provenance_does_not_invent_authority(self):
        unknown = DeclarationProvenance("unknown", (), None, "Not reported")
        pin = PinnedIdentity("source", "software-only", "1", "a" * 64)
        declared = DeclarationProvenance(
            "declared", (pin,), "fixture:notice", "Software declaration only"
        )
        for item in (unknown, declared):
            self.assertEqual(DeclarationProvenance.from_json(item.to_json()), item)
        for kwargs in (
            {"status": "verified"},
            {"reason": ""},
            {"locator": "invented"},
            {"authority": (pin,)},
        ):
            with self.assertRaises(SerializationError):
                replace(unknown, **kwargs)
        with self.assertRaises(SerializationError):
            replace(declared, authority=())
        with self.assertRaises(SerializationError):
            replace(declared, authority=(pin, pin))

    def test_hostile_mapping_rejects_before_iteration(self):
        class TooMany(Mapping):
            def __len__(self):
                return MAX_MOLECULE_ITEMS

            def __getitem__(self, key):
                raise AssertionError("Must reject count before indexing")

            def __iter__(self):
                raise AssertionError("Must reject count before iteration")

        with self.assertRaisesRegex(SerializationError, "item limit"):
            DeclarationProvenance.from_dict(TooMany())

    def test_cyclic_deep_and_pending_trees_are_bounded(self):
        cycle = []
        cycle.append(cycle)
        deep = None
        for _ in range(MAX_MOLECULE_DEPTH + 2):
            deep = [deep]
        for value, message in (
            ({"cycle": cycle}, "Cyclic"),
            ({"deep": deep}, "nesting"),
            ({"pending": [[None] * (MAX_MOLECULE_ITEMS // 2)] * 2}, "item limit"),
        ):
            with (
                self.subTest(message=message),
                self.assertRaisesRegex(SerializationError, message),
            ):
                DeclarationProvenance.from_dict(value)

    def test_duplicate_fields_nonfinite_unknown_fields_and_raw_bytes_reject(self):
        for text in (
            '{"status":"unknown","status":"declared"}',
            '{"value":NaN}',
            '{"value":Infinity}',
            " " * (MAX_MOLECULE_JSON_BYTES + 1),
        ):
            with self.assertRaises(SerializationError):
                DeclarationProvenance.from_json(text)
        unknown = DeclarationProvenance("unknown", (), None, "Not reported")
        with self.assertRaises(SerializationError):
            DeclarationProvenance.from_dict(unknown.to_dict() | {"verified": True})

    def test_streaming_serialization_bounds_pretty_expansion(self):
        record = make_molecule_record()
        nested = [[] for _ in range(12000)]
        for _ in range(60):
            nested = [nested]
        record = replace(record, run_metadata={"nested": nested})
        self.assertLess(len(record.to_json().encode()), MAX_MOLECULE_JSON_BYTES)
        with patch(
            "biocompiler.ir.molecule_records.json.dumps",
            side_effect=AssertionError("Whole-document encoding is forbidden here"),
        ):
            with self.assertRaisesRegex(SerializationError, "byte limit"):
                record.to_json(indent=8)
        for indent in (True, -1, 9, 1.5, " "):
            with self.assertRaisesRegex(SerializationError, "indentation"):
                record.to_json(indent=indent)


if __name__ == "__main__":
    unittest.main()
