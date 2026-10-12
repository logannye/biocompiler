"""Additive source representation and isolation, not semantic or native acceptance."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from biocompiler.policy import model as m
from biocompiler.policy.serialization import (
    PolicySerializationError, controlled_composition_source_schema, document_digest,
    dumps, expression_source_schema, from_data, loads, schema, to_data,
)
from biocompiler.policy.validation import check
from tools import generate_policy_wire_schema as language

ROOT = Path(__file__).resolve().parents[1]
WIRE_FIXTURES = ROOT / 'data/controlled_composition_v01/source-wire'
SOURCE_SHAPE_SHA256 = '9776ee3d0a0305c392b71798a32f0d12030bb4ae41e552f20a47f02128c0b55d'
NEGATIVE_MUTATIONS_SHA256 = 'cfda91f6bd400850c7fef3315f124090b245dd5d706289e5f4366f4c13c6473f'


def shape_fixture():
    """Frozen original bytes; no compatible realization or source admission asserted."""
    return json.loads((WIRE_FIXTURES / 'source-shape.json').read_bytes())


class ControlledCompositionSourceTests(unittest.TestCase):
    def test_frozen_original_wire_bytes_and_negative_inventory(self):
        for name, digest in (('source-shape.json', SOURCE_SHAPE_SHA256),
                             ('negative-mutations.json', NEGATIVE_MUTATIONS_SHA256)):
            blob = (WIRE_FIXTURES / name).read_bytes()
            self.assertEqual(hashlib.sha256(blob).hexdigest(), digest)
            self.assertEqual(blob, json.dumps(json.loads(blob), sort_keys=True,
                             separators=(',', ':'), ensure_ascii=False).encode() + b'\n')
        inventory = json.loads((WIRE_FIXTURES / 'negative-mutations.json').read_bytes())
        self.assertEqual(set(inventory), {'fixture_kind', 'status', 'source_sha256', 'cases'})
        self.assertEqual(inventory['fixture_kind'], 'controlled_composition_source_wire_negative_mutations')
        self.assertEqual(inventory['status'], 'shape_only_no_source_admission')
        self.assertEqual(inventory['source_sha256'], SOURCE_SHAPE_SHA256)
        self.assertEqual(len(inventory['cases']), 20)
        self.assertEqual(len({case['id'] for case in inventory['cases']}), 20)
        for case in inventory['cases']:
            expected_keys = {'id', 'op', 'path', 'expected'}
            if case['op'] != 'remove':
                expected_keys.add('value')
            self.assertEqual(set(case), expected_keys)
            self.assertEqual(case['expected'], 'representation_rejection')
            raw = shape_fixture()
            container = raw
            for part in case['path'][:-1]:
                container = container[part]
            key = case['path'][-1]
            if case['op'] == 'remove':
                del container[key]
            elif case['op'] in ('replace', 'add'):
                self.assertEqual(key in container, case['op'] == 'replace')
                container[key] = deepcopy(case['value'])
            else:
                self.fail('Unknown mutation operation')
            with self.subTest(case=case['id']), self.assertRaises(PolicySerializationError):
                from_data(raw)

    def test_additive_root_roundtrips_without_claiming_semantic_acceptance(self):
        raw = shape_fixture()
        value = from_data(raw, m.BuildRequest)
        self.assertIs(type(value.program.declarations[-1]), m.ControlledActivity)
        self.assertEqual(to_data(value), raw)
        self.assertEqual(loads(dumps(value)), value)
        self.assertEqual(value.program.semantics.profile, m.PROFILE)
        raw['program']['declarations'][-1]['products'].clear()
        self.assertEqual(len(value.program.declarations[-1].products), 2)

    def test_legacy_authoring_checker_does_not_promote_controlled_representation(self):
        report = check(from_data(shape_fixture(), m.BuildRequest))
        self.assertEqual(report.status, 'invalid')
        self.assertTrue({'unsupported_profile', 'unsupported_declaration'} <=
                        {diagnostic.code for diagnostic in report.diagnostics})

    def test_activity_band_is_typed_and_cannot_escape_profile_scope(self):
        value = from_data(shape_fixture(), m.BuildRequest)
        activity = value.program.declarations[-1]
        expression = activity.band()
        self.assertEqual((expression.op, expression.value_type, expression.ref, expression.scope),
                         ('activity_band', m.TEXT, m.Ref('controlled', 'ControlledActivity'), activity.subject))
        with self.assertRaises(PolicySerializationError):
            to_data(expression)
        # A typed expression can be transported within the versioned root;
        # this deliberately invalid truth gate still awaits native admission.
        nested = replace(activity, gate=expression)
        controlled = replace(value, program=replace(value.program,
                             declarations=(*value.program.declarations[:-1], nested)))
        self.assertEqual(loads(dumps(controlled)), controlled)
        with self.assertRaises(PolicySerializationError):
            to_data(replace(controlled, profile=m.PROFILE,
                            program=replace(controlled.program, profile=m.PROFILE)))

    def test_old_profiles_and_standalone_new_records_remain_closed(self):
        controlled = from_data(shape_fixture(), m.BuildRequest)
        for value in (controlled.program, controlled.program.declarations[-1],
                      replace(controlled.program, profile=m.PROFILE),
                      replace(controlled, profile=m.PROFILE),
                      replace(controlled, profile=m.EXPRESSION_SOURCE_PROFILE)):
            with self.subTest(kind=type(value).__name__), self.assertRaises(PolicySerializationError):
                to_data(value)
        raw = shape_fixture()
        for replacement in (m.PROFILE, m.EXPRESSION_SOURCE_PROFILE):
            changed = deepcopy(raw)
            changed['profile'] = replacement
            changed['program']['profile'] = m.PROFILE
            with self.subTest(profile=replacement), self.assertRaises(PolicySerializationError):
                from_data(changed)
        cases = json.loads((ROOT / 'core/test/data/policy_documents_v01.json').read_text())['cases']
        submission = next(case['document'] for case in cases if case['document']['$type'] == 'CompilationSubmission')
        submission['request'] = raw
        with self.assertRaises(PolicySerializationError):
            from_data(submission)

    def test_profile_and_assurance_crossovers_reject_on_both_paths(self):
        original_value = from_data(shape_fixture(), m.BuildRequest)
        mutations = [
            lambda r: r['program'].update(profile=m.PROFILE),
            lambda r: r['program']['semantics'].update(profile=m.CONTROLLED_COMPOSITION_SOURCE_PROFILE),
            lambda r: r['assurance'].update(horizon='not_applicable'),
            lambda r: r['assurance'].update(horizon='unbounded_requested'),
            lambda r: r['assurance'].update(level='structural'),
            lambda r: r['assurance'].update(level='proof'),
        ]
        for index, mutate in enumerate(mutations):
            raw = shape_fixture()
            mutate(raw)
            with self.subTest(index=index), self.assertRaises(PolicySerializationError):
                from_data(raw)
        with self.assertRaises(PolicySerializationError):
            to_data(replace(original_value, assurance=replace(original_value.assurance, horizon='not_applicable')))

    def test_exact_activity_fields_and_product_tuple_arity_are_closed(self):
        for count in (0, 1, 3):
            raw = shape_fixture()
            activity = raw['program']['declarations'][-1]
            activity['products'] = [activity['products'][0]] * count
            with self.subTest(count=count), self.assertRaises(PolicySerializationError):
                from_data(raw)
        for change in ('missing', 'extra', 'wrong_tag'):
            raw = shape_fixture()
            activity = raw['program']['declarations'][-1]
            if change == 'missing':
                del activity['readout']
            elif change == 'extra':
                activity['native_accepted'] = True
            else:
                activity['$type'] = 'Effect'
            with self.subTest(change=change), self.assertRaises(PolicySerializationError):
                from_data(raw)

    def test_independent_schema_and_generated_table_match_clients(self):
        specification = language.read_controlled_specification()
        self.assertEqual(controlled_composition_source_schema(), specification)
        self.assertEqual(language.render_controlled(specification), (ROOT / language.CONTROLLED_TARGET).read_text())
        source = (ROOT / language.MODEL).read_text()
        language.check_python_conformance(language.read_specification(), source)
        for mutation in (source.replace('    products: tuple[Ref, Ref]', '    products: tuple[Ref, ...]'),
                         source + '\nCONTROLLED_COMPOSITION_SOURCE_PROFILE = "changed"\n',
                         source + '\nif True:\n    ControlledActivity = object\n'):
            with self.subTest(mutation=mutation[-90:]), self.assertRaises(language.LanguageSchemaError):
                language.check_python_conformance(language.read_specification(), mutation)
        changed = deepcopy(specification)
        changed['$defs']['Effect']['additionalProperties'] = True
        with patch.object(Path, 'read_bytes', return_value=json.dumps(changed).encode()):
            with self.assertRaises(language.LanguageSchemaError):
                language.read_controlled_specification(language.read_specification())

    def test_generation_does_not_execute_the_sdk(self):
        specification = language.read_controlled_specification()
        expected = language.render_controlled(specification)
        with patch.object(language, 'ROOT', Path('/missing-sdk')):
            self.assertEqual(language.render_controlled(specification), expected)

    def test_old_schemas_and_frozen_documents_retain_exact_authority(self):
        base = language.read_specification()
        self.assertEqual(schema(), {key: value for key, value in base.items() if key not in ('$id', 'x-policy-language')})
        self.assertEqual(expression_source_schema(), json.loads((ROOT / language.EXPRESSION_SPECIFICATION).read_text()))
        self.assertEqual(language.render(base), (ROOT / language.TARGET).read_text())
        self.assertNotIn('ControlledActivity', schema()['$defs'])
        for case in json.loads((ROOT / 'core/test/data/policy_documents_v01.json').read_text())['cases']:
            value = from_data(case['document'])
            self.assertEqual(hashlib.sha256(dumps(value, indent=None).encode()).hexdigest(), case['artifact_digest'])
            self.assertEqual(document_digest(value), case['document_digest'])


if __name__ == '__main__':
    unittest.main()
