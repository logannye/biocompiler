"""Strict closed authoring wire authority and immutable roundtrip controls."""
from dataclasses import dataclass, replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biocompiler.policy import model as m
from biocompiler.policy.serialization import (
    DEFAULT_LIMITS, PolicySerializationError, document_digest, dump, dumps,
    from_data, load, loads, schema, to_data,
)


def program():
    return m.PolicyProgram('example', m.SemanticBundle('semantics', '1'), (
        m.Subject('target', 'cell', 'stable'),
        m.Parameter('large', m.INTEGER, 9007199254740993),
    ), (m.SourceSpan('target', 'authored.py', 7),))


class PolicySerializationTests(unittest.TestCase):
    def test_roundtrip_preserves_exact_scalar_types_and_declared_kind_fields(self):
        original = program()
        restored = loads(dumps(original), m.PolicyProgram)
        self.assertEqual(restored, original)
        self.assertIs(type(restored.declarations[1].value), int)
        reference = m.Ref('target', 'Subject')
        self.assertEqual(to_data(reference), {'$type': 'Ref', 'id': 'target', 'kind': 'Subject'})
        self.assertEqual(from_data(to_data(reference)), reference)

    def test_determinism_and_provenance_separation(self):
        original = program()
        relocated = replace(original, source_map=(m.SourceSpan('target', '/elsewhere.py', 109),))
        self.assertNotEqual(dumps(original), dumps(relocated))
        self.assertEqual(document_digest(original), document_digest(relocated))
        self.assertNotEqual(document_digest(original), document_digest(replace(original, id='changed')))
        self.assertNotEqual(document_digest(original), document_digest(m.PolicyDraft(
            original.id, original.semantics, original.declarations, source_map=original.source_map)))
        self.assertEqual(dumps(original), dumps(loads(dumps(original))))

    def test_decimal_text_and_float_rejection(self):
        value = m.Quantity('0.000000000000000000000000001', m.Unit('s', 'time', 'duration'))
        self.assertEqual(loads(dumps(value)), value)
        for raw in ('1.0', 'NaN', 'Infinity', '-Infinity', '-0.0'):
            with self.subTest(raw=raw), self.assertRaises(PolicySerializationError):
                loads(raw)
        raw = to_data(value)
        for invalid in (1.0, True, 'NaN', 'Infinity', '1e99999999999999999999999999'):
            with self.subTest(invalid=invalid), self.assertRaises(PolicySerializationError):
                from_data({**raw, 'amount': invalid})

    def test_unknown_missing_duplicate_and_incompatible_declarations(self):
        data = to_data(program())
        invalid = ({**data, '$type': 'os.system'}, {**data, 'surprise': 1},
                   {key: value for key, value in data.items() if key != 'declarations'},
                   {**data, 'declarations': [{'kind': 'Subject'}]})
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(PolicySerializationError):
                from_data(value)
        with self.assertRaises(PolicySerializationError):
            loads('{"$type":"Ref","id":"a","id":"b","kind":"Subject"}')
        with self.assertRaises(PolicySerializationError):
            loads(dumps(program()), m.BuildRequest)

    def test_no_truth_integer_coercion_or_arbitrary_objects(self):
        data = to_data(m.SourceSpan('target', 'a.py', 1))
        for value in (True, '1', 1.0):
            with self.subTest(value=value), self.assertRaises(PolicySerializationError):
                from_data({**data, 'line': value})
        with self.assertRaises(PolicySerializationError):
            from_data({'$type': 'Ref', 'id': object(), 'kind': 'Subject'})
        with self.assertRaises(PolicySerializationError):
            dumps(m.SourceSpan('target', 'a.py', True))

    def test_registry_is_closed_against_later_python_subclasses(self):
        with self.assertRaises(TypeError):
            @dataclass(frozen=True)
            class LocalExtension(m.Record):
                value: str
        with self.assertRaises(PolicySerializationError):
            from_data({'$type': 'LocalExtension', 'value': 'no execution'})

    def test_bounded_before_deep_parse_and_after_unicode_decoding(self):
        limits = replace(DEFAULT_LIMITS, max_depth=4)
        with self.assertRaises(PolicySerializationError):
            loads('[' * 5000 + '0' + ']' * 5000, limits=limits)
        for raw in (b'\xff', '"\\ud800"', '"' + '\ud800' + '"'):
            with self.subTest(raw=repr(raw)), self.assertRaises(PolicySerializationError):
                loads(raw)
        with self.assertRaises(PolicySerializationError):
            loads('1' * (DEFAULT_LIMITS.max_number_characters + 1))
        with self.assertRaises(PolicySerializationError):
            loads(dumps(program()), limits=replace(DEFAULT_LIMITS, max_bytes=32))
        with self.assertRaises(PolicySerializationError):
            from_data(to_data(program()), limits=replace(DEFAULT_LIMITS, max_nodes=8))

    def test_atomic_dump_never_overwrites_existing_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'policy.json'
            dump(program(), target)
            original = target.read_bytes()
            self.assertEqual(load(target), program())
            with self.assertRaises(FileExistsError):
                dump(replace(program(), id='different'), target)
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual([path.name for path in target.parent.iterdir()], ['policy.json'])

    def test_aggregate_payload_is_bounded_before_full_json_allocation(self):
        value = m.Ref('x' * 128, 'y' * 128)
        wire = {'$type': 'Ref', 'id': value.id, 'kind': value.kind}
        limits = replace(DEFAULT_LIMITS, max_bytes=200)
        with patch('biocompiler.policy.serialization.json.dumps',
                   side_effect=AssertionError('Oversized graph reached the JSON renderer')):
            with self.assertRaises(PolicySerializationError):
                to_data(value, limits=limits)
            with self.assertRaises(PolicySerializationError):
                from_data(wire, limits=limits)

    def test_schema_comes_from_exact_registry_and_retains_semantic_kind(self):
        document = schema()
        self.assertEqual(set(document['$defs']), set(m.REGISTRY))
        self.assertEqual(document['$defs']['Ref']['properties']['$type'], {'const': 'Ref'})
        self.assertEqual(document['$defs']['Ref']['properties']['kind'], {'type': 'string'})
        self.assertFalse(document['$defs']['Ref']['additionalProperties'])
        self.assertEqual(schema(m.PolicyProgram)['$ref'], '#/$defs/PolicyProgram')
        self.assertEqual(json.loads(json.dumps(document)), document)


if __name__ == '__main__':
    unittest.main()
