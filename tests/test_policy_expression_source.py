"""Static source representation only; no material or biological acceptance."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from biocompiler.policy import model as m
from biocompiler.policy.serialization import (PolicySerializationError, document_digest,
    dumps, expression_source_schema, from_data, loads, schema, to_data)
from biocompiler.policy.validation import check
from tools import generate_policy_wire_schema as language

ROOT = Path(__file__).resolve().parents[1]


def original():
    cases = json.loads((ROOT / 'core/test/data/policy_documents_v01.json').read_text())['cases']
    return next(case['document'] for case in cases if case['document']['$type'] == 'BuildRequest')


def static_shape():
    """Only a representation fixture; no expression contract is supplied."""
    raw = original()
    raw['profile'] = m.EXPRESSION_SOURCE_PROFILE
    raw['assurance'].update(level='structural', horizon='not_applicable', assumptions=[], tolerances=[])
    return raw


class ExpressionSourceTests(unittest.TestCase):
    def test_explicit_static_root_roundtrips_without_source_rewriting(self):
        raw = static_shape()
        value = from_data(raw, m.BuildRequest)
        self.assertEqual(to_data(value), raw)
        self.assertEqual(loads(dumps(value)), value)
        self.assertEqual(value.assurance.horizon, 'not_applicable')
        self.assertEqual(value.program.profile, m.PROFILE)
        self.assertEqual(value.program.semantics.profile, m.PROFILE)
        raw['assurance']['horizon'] = 'changed'
        self.assertEqual(value.assurance.horizon, 'not_applicable')

    def test_old_profile_cannot_smuggle_static_assurance(self):
        raw = static_shape()
        raw['profile'] = m.PROFILE
        with self.assertRaises(PolicySerializationError):
            from_data(raw)
        with self.assertRaises(PolicySerializationError):
            to_data(replace(from_data(static_shape(), m.BuildRequest), profile=m.PROFILE))
        with self.assertRaises(PolicySerializationError):
            to_data(m.AssuranceRequest((), 'structural', 'not_applicable'))

    def test_static_profile_rejects_temporal_or_nonstructural_assurance(self):
        for field, value in (('horizon', original()['assurance']['horizon']),
                             ('horizon', 'unbounded_requested'), ('level', 'bounded'),
                             ('level', 'proof'), ('assumptions', ['unproved']),
                             ('tolerances', [{'$type': 'Argument'}])):
            raw = static_shape()
            raw['assurance'][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(PolicySerializationError):
                from_data(raw)

    def test_nested_profiles_and_old_submission_remain_closed(self):
        for path in (('program',), ('program', 'semantics')):
            raw = static_shape()
            target = raw
            for key in path:
                target = target[key]
            target['profile'] = m.EXPRESSION_SOURCE_PROFILE
            with self.subTest(path=path), self.assertRaises(PolicySerializationError):
                from_data(raw)
        corpus = json.loads((ROOT / 'core/test/data/policy_documents_v01.json').read_text())['cases']
        submission = next(case['document'] for case in corpus if case['document']['$type'] == 'CompilationSubmission')
        submission['request'] = static_shape()
        with self.assertRaises(PolicySerializationError):
            from_data(submission)

    def test_authoring_retains_unresolved_claims_and_rejects_dynamic_source(self):
        value = from_data(static_shape(), m.BuildRequest)
        report = check(value)
        self.assertEqual(report.status, 'invalid')  # Original runtime example is not a static objective.
        self.assertIn('expression_source_dynamic', {item.code for item in report.diagnostics})
        self.assertIn('expression_material_correspondence', report.deferred_obligations)
        self.assertIn('requested_assurance_not_established', report.deferred_obligations)
        self.assertEqual(report.semantic_status, 'unassessed')

    def test_static_empty_source_is_only_structural_not_material_admission(self):
        value = from_data(static_shape(), m.BuildRequest)
        roles = tuple(item for item in value.program.declarations if isinstance(item, m.Role))
        value = replace(value, program=replace(value.program, declarations=roles, source_map=()),
                        assurance=replace(value.assurance, requirements=()))
        report = check(value)
        self.assertEqual(report.status, 'complete')
        self.assertIn('expression_material_correspondence', report.deferred_obligations)
        self.assertEqual((report.semantic_status, report.target_status), ('unassessed', 'unassessed'))

    def test_default_language_and_frozen_originals_are_unchanged(self):
        specification = language.read_specification()
        self.assertEqual(schema(), {key: value for key, value in specification.items()
                                   if key not in ('$id', 'x-policy-language')})
        self.assertEqual(language.render(specification), (ROOT / language.TARGET).read_text())
        for case in json.loads((ROOT / 'core/test/data/policy_documents_v01.json').read_text())['cases']:
            value = from_data(case['document'])
            self.assertEqual(hashlib.sha256(dumps(value, indent=None).encode()).hexdigest(), case['artifact_digest'])
            self.assertEqual(document_digest(value), case['document_digest'])

    def test_new_schema_is_exact_additive_projection_and_matches_sdk(self):
        specification = language.read_specification()
        language.check_expression_specification(specification)
        expected = json.loads((ROOT / language.EXPRESSION_SPECIFICATION).read_text())
        self.assertEqual(expression_source_schema(), expected)
        changed = deepcopy(expected)
        changed['$defs']['Effect']['additionalProperties'] = True
        with patch.object(Path, 'read_bytes', return_value=json.dumps(changed).encode()):
            with self.assertRaises(language.LanguageSchemaError):
                language.check_expression_specification(specification)

    def test_python_projection_rejects_unreviewed_extension_and_profile_rebinding(self):
        specification = language.read_specification()
        source = (ROOT / language.MODEL).read_text()
        language.check_python_conformance(specification, source)
        for changed in (source.replace('"unbounded_requested", "not_applicable"', '"unbounded_requested", "not_applicable", "any"'),
                        source.replace('"not_applicable"]', '"not_applicable", "any"]', 1),
                        source + '\nEXPRESSION_SOURCE_PROFILE = "changed"\n',
                        source + '\nif True:\n    EXPRESSION_SOURCE_PROFILE = "changed"\n'):
            with self.subTest(mutation=changed[-80:]), self.assertRaises(language.LanguageSchemaError):
                language.check_python_conformance(specification, changed)


if __name__ == '__main__':
    unittest.main()
