"""Pure preparation controls over independent complete artificial originals."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import unittest

from biocompiler.core_client import encode_json
from biocompiler.policy.controlled_material import ControlledCompositionRequest, ControlledBudgets

ROOT = Path(__file__).resolve().parents[1]


def literal():
    return json.loads((ROOT / 'core/test/data/policy_controlled_request_v014.json').read_text())


class ControlledMaterialPreparationTests(unittest.TestCase):
    def test_independent_literal_retains_complete_source_domain_and_molecular_authority(self):
        raw = literal()
        value = ControlledCompositionRequest.from_request(raw)
        self.assertEqual(value.to_request(), raw)
        self.assertEqual(value.source_authority.document.program.id, raw['source_authority']['document']['program']['id'])
        self.assertEqual(tuple(member.id for member in value.template.output_members), ('rna-a', 'rna-b'))
        self.assertEqual(value.native_status, 'not_performed')
        self.assertFalse(hasattr(value, 'compile'))
        self.assertFalse(hasattr(value, 'checked_material'))
        source = json.loads((ROOT / 'core/test/data/policy_controlled_source_v01.json').read_text())
        domain = json.loads((ROOT / 'core/test/data/policy_controlled_domain_v01.json').read_text())
        self.assertEqual(raw['source_authority']['document'], source)
        self.assertEqual(raw['operating_domain'], domain)

    def test_snapshots_do_not_alias_caller_or_returned_nested_objects(self):
        raw = literal(); value = ControlledCompositionRequest.from_request(raw)
        expected = value.to_request()
        raw['material_authority']['members'][0]['product']['sequence'] = 'MG'
        exported = value.to_request(); exported['source_authority']['project_context']['title'] = 'mutated'
        self.assertEqual(value.to_request(), expected)
        with self.assertRaises(FrozenInstanceError):
            value._json = b'{}'

    def test_native_correspondence_remains_pending_and_pins_are_never_repaired(self):
        raw = literal()
        raw['mechanism_model']['identity']['content_fingerprint'] = '0' * 64
        raw['material_authority']['members'][0]['product']['identity']['content_fingerprint'] = '1' * 64
        value = ControlledCompositionRequest.from_request(raw)
        self.assertEqual(value.to_request(), raw)
        self.assertEqual(value.native_status, 'not_performed')

    def test_source_deadline_edits_do_not_synthesize_actual_delays(self):
        raw = literal()
        expected = deepcopy(raw['source_authority']['control_contract']['actual_delays'])
        raw['source_authority']['control_contract']['requested_deadlines']['onset_ticks'] = 1
        value = ControlledCompositionRequest.from_request(raw)
        self.assertEqual(value.to_request()['source_authority']['control_contract']['actual_delays'], expected)

    def test_every_authority_root_is_required_and_closed(self):
        raw = literal()
        for key in raw:
            changed = deepcopy(raw); del changed[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                ControlledCompositionRequest.from_request(changed)
        raw['checked_material'] = {}
        with self.assertRaises(ValueError):
            ControlledCompositionRequest.from_request(raw)

    def test_meaning_bearing_nested_records_reject_extra_fields(self):
        paths = [('mechanism_model', 'body'), ('mechanism_model', 'body', 'ports', 4),
                 ('material_authority', 'members', 0, 'product'), ('context', 'co_delivery'),
                 ('operating_domain', 'inputs', 0), ('operating_domain', 'initial', 'evidence', 'antigen'),
                 ('assembly', 'product_bindings', 0)]
        for path in paths:
            raw = literal(); record = raw
            for key in path: record = record[key]
            record['uninterpreted'] = True
            with self.subTest(path=path), self.assertRaises((ValueError, TypeError)):
                ControlledCompositionRequest.from_request(raw)

    def test_no_third_member_unknown_region_or_missing_chemistry_shape(self):
        mutations = [lambda x: x['material_authority']['members'].append(deepcopy(x['material_authority']['members'][0])),
                     lambda x: x['material_authority']['members'][0]['regions'].pop('utr5'),
                     lambda x: x['material_authority']['members'][0].pop('chemistry'),
                     lambda x: x['material_authority']['members'][0]['product'].__setitem__('sequence', 'MA*')]
        for mutate in mutations:
            raw = literal(); mutate(raw)
            with self.assertRaises((ValueError, TypeError)):
                ControlledCompositionRequest.from_request(raw)

    def test_executor_activity_scope_cannot_be_encounter_scoped(self):
        raw = literal(); raw['mechanism_model']['body']['ports'][4]['scope'] = 'encounter_generation'
        with self.assertRaises(ValueError):
            ControlledCompositionRequest.from_request(raw)

    def test_resource_scalars_reject_bool_float_negative_and_unbounded(self):
        for value in (True, 1.0, -1, 0, 1_000_000_001):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ControlledBudgets(max_work=value).to_data()
        raw = literal(); raw['resources']['evidence_records'] = 1
        with self.assertRaises(ValueError):
            ControlledCompositionRequest.from_request(raw)

    def test_original_project_authority_changes_whole_request_identity(self):
        raw = literal(); first = ControlledCompositionRequest.from_request(raw)
        raw['source_authority']['project_context']['title'] += ' changed'
        second = ControlledCompositionRequest.from_request(raw)
        self.assertNotEqual(first.sha256, second.sha256)
        self.assertEqual(encode_json(first.to_request()), first._json)

    def test_source_has_explicit_full_product_descriptors(self):
        definitions = literal()['source_authority']['document']['program']['semantics']['definitions']
        products = [item for item in definitions if item['id'].startswith('artificial.product-')]
        self.assertEqual(len(products), 2)
        for item in products:
            self.assertEqual([p['id'] for p in item['parameters']], ['product_identity', 'product_version', 'product_sha256'])
            self.assertEqual(len(item['parameters'][2]['value']), 64)


if __name__ == '__main__':
    unittest.main()
