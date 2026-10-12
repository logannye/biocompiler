"""Preparation preserves exact supplied inputs without evaluating a mechanism."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import unittest

from biocompiler.core_client import encode_json
from biocompiler.policy import model as m
from biocompiler.policy.controlled_composition import (
    CONTRACT_SCHEMA, PROFILE, SOURCE_AUTHORITY_SCHEMA, ActivityDeadlines, ActivityReadout,
    ActualActivityDelays, ControllerBinding, ControlledCompositionContractDescription,
    ProductMemberBinding, SourceAuthoritySnapshot,
)
from biocompiler.policy.serialization import from_data
from tests.test_policy_controlled_composition_source import shape_fixture

ROOT = Path(__file__).resolve().parents[1]


def contract():
    return ControlledCompositionContractDescription(
        products=(ProductMemberBinding(m.Ref('product_a', 'Parameter'), 'rna_a', 'cds', m.DefinitionRef('a', '1', 'a' * 64)),
                  ProductMemberBinding(m.Ref('product_b', 'Parameter'), 'rna_b', 'cds', m.DefinitionRef('b', '1', 'b' * 64))),
        controller=ControllerBinding(m.DefinitionRef('drug', '1', 'd' * 64), m.Ref('executor', 'Role')),
        readout=ActivityReadout(m.Ref('controlled', 'ControlledActivity'), m.DefinitionRef('activity.readout', '1', '1' * 64)),
        actual_delays=ActualActivityDelays(2, 3, 4),
        requested_deadlines=ActivityDeadlines(5, 6, 7, 8, 9))


def context():
    return {'project_id': 'fixture', 'title': 'Artificial source description',
            'sources': [{'id': 'original', 'locator': 'supplied:fixture', 'version': '1',
                         'sha256': 'c' * 64, 'role': 'artificial', 'reuse_terms': 'fixture only'}],
            'assumptions': ['Supplied contracts; no biological evidence is asserted.']}


def snapshot():
    return SourceAuthoritySnapshot(document=from_data(shape_fixture(), m.BuildRequest),
                                   control_contract=contract(), project_context=context())


class ControlledCompositionDescriptionTests(unittest.TestCase):
    def test_versioned_closed_contract_keeps_actual_and_requested_delays_independent(self):
        value = contract()
        raw = value.to_data()
        self.assertEqual((raw['schema_version'], raw['profile']), (CONTRACT_SCHEMA, PROFILE))
        self.assertEqual(raw['actual_delays'], {'onset_ticks': 2, 'cessation_ticks': 3, 'reactivation_ticks': 4})
        self.assertEqual(raw['requested_deadlines'], {'onset_ticks': 5, 'controller_off_ticks': 6,
                         'antigen_off_ticks': 7, 'component_off_ticks': 8, 'reactivation_ticks': 9})
        self.assertEqual(ControlledCompositionContractDescription.from_data(raw), value)
        impossible = replace(value, requested_deadlines=ActivityDeadlines(1, 1, 1, 1, 1))
        self.assertEqual(impossible.actual_delays, value.actual_delays)
        self.assertEqual(ControlledCompositionContractDescription.from_data(impossible.to_data()), impossible)
        # This layer retains a potentially contradictory request for later checking.

    def test_ticks_reject_bool_float_zero_negative_and_unbounded_values(self):
        for value in (True, False, 0, -1, 1.0, '1', 10_001):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ActualActivityDelays(value, 1, 1)
            with self.subTest(deadline=value), self.assertRaises(ValueError):
                ActivityDeadlines(1, value, 1, 1, 1)

    def test_closed_literals_and_field_inventories_cannot_claim_acceptance(self):
        for key, value in (('mechanism', 'stochastic'), ('initial_activity', 'active'),
                           ('profile', 'old'), ('schema_version', 'old'), ('native_accepted', True)):
            raw = contract().to_data()
            raw[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                ControlledCompositionContractDescription.from_data(raw)
        for key in contract().to_data():
            raw = contract().to_data()
            del raw[key]
            with self.subTest(missing=key), self.assertRaises(ValueError):
                ControlledCompositionContractDescription.from_data(raw)
        raw = contract().to_data()
        raw['readout']['physical_bands'].append('unknown')
        with self.assertRaises(ValueError):
            ControlledCompositionContractDescription.from_data(raw)
        raw = contract().to_data()
        raw['controller']['scope'] = 'encounter'
        with self.assertRaises(ValueError):
            ControlledCompositionContractDescription.from_data(raw)

    def test_member_order_and_complete_original_reference_pins_are_retained(self):
        value = contract()
        with self.assertRaises(ValueError):
            replace(value, products=(value.products[0], value.products[0]))
        changed = replace(value, products=tuple(reversed(value.products)))
        self.assertNotEqual(encode_json(changed.to_data()), encode_json(value.to_data()))
        with self.assertRaises(ValueError):
            SourceAuthoritySnapshot(document=snapshot().document, control_contract=changed, project_context=context())
        with self.assertRaises(ValueError):
            replace(value.controller, definition=m.DefinitionRef('drug', '1', 'not-a-digest'))

    def test_snapshot_is_deeply_detached_and_preserves_all_project_context(self):
        raw_context = context()
        value = SourceAuthoritySnapshot(document=from_data(shape_fixture(), m.BuildRequest),
                                        control_contract=contract(), project_context=raw_context)
        before = value.canonical_bytes
        raw_context['sources'][0]['sha256'] = 'e' * 64
        raw_context['assumptions'].clear()
        detached = value.to_data()
        detached['project_context']['title'] = 'mutated'
        detached['control_contract']['actual_delays']['onset_ticks'] = 99
        self.assertEqual(value.canonical_bytes, before)
        self.assertEqual(value.project_context, context())
        self.assertEqual(value.control_contract, contract())
        self.assertEqual(SourceAuthoritySnapshot.from_data(value.to_data()), value)
        with self.assertRaises(FrozenInstanceError):
            value._snapshot_json = b'changed'
        self.assertEqual((value.native_status, value.material_status), ('not_performed', 'not_performed'))

    def test_exact_closed_snapshot_and_context_reject_omitted_or_extra_authority(self):
        value = snapshot()
        for key in value.to_data():
            raw = value.to_data()
            del raw[key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                SourceAuthoritySnapshot.from_data(raw)
        mutations = [lambda r: r.update(native_accepted=True),
                     lambda r: r['project_context'].update(unknown_field='hidden'),
                     lambda r: r['project_context']['sources'][0].pop('reuse_terms'),
                     lambda r: r['project_context']['sources'].append(deepcopy(r['project_context']['sources'][0])),
                     lambda r: r['control_contract']['readout']['definition'].update(digest='f' * 64)]
        for index, mutate in enumerate(mutations):
            raw = value.to_data()
            mutate(raw)
            with self.subTest(index=index), self.assertRaises(ValueError):
                SourceAuthoritySnapshot.from_data(raw)

    def test_snapshot_revalidates_frozen_description_wire_values(self):
        for nested, field, invalid in (('actual_delays', 'onset_ticks', True),
                                       ('readout', 'physical_bands', ('background', 'unknown')),
                                       ('controller', 'scope', 'encounter')):
            value = contract()
            # Deliberately bypass the frozen helper constructor; capture must still
            # validate the complete serialized original independently.
            object.__setattr__(getattr(value, nested), field, invalid)
            with self.subTest(field=field), self.assertRaises(ValueError):
                SourceAuthoritySnapshot(document=from_data(shape_fixture(), m.BuildRequest),
                                        control_contract=value, project_context=context())

    def test_source_replacement_changes_identity_without_repairing_model_or_provenance(self):
        value = snapshot()
        source = value.document
        changed_source = replace(source, assurance=replace(source.assurance,
                                 horizon=m.Quantity('31', source.assurance.horizon.unit)))
        changed = value.with_document(changed_source)
        self.assertNotEqual(value.sha256, changed.sha256)
        self.assertEqual(value.control_contract, changed.control_contract)
        self.assertEqual(value.project_context, changed.project_context)
        self.assertEqual(value.control_contract.products[0].product_definition.digest,
                         changed.control_contract.products[0].product_definition.digest)
        with self.assertRaises(ValueError):
            value.with_document(replace(source, profile=m.PROFILE))

    def test_canonical_identity_covers_provenance_and_rejects_normalization(self):
        value = snapshot()
        reordered = dict(reversed(list(value.to_data().items())))
        self.assertEqual(SourceAuthoritySnapshot.from_data(reordered).sha256, value.sha256)
        raw = value.to_data()
        raw['project_context']['sources'][0]['reuse_terms'] = 'Changed terms'
        changed = SourceAuthoritySnapshot.from_data(raw)
        self.assertNotEqual(value.sha256, changed.sha256)
        raw = value.to_data()
        raw['document']['assurance']['horizon']['amount'] = '30.0'
        with self.assertRaisesRegex(ValueError, 'normalized'):
            SourceAuthoritySnapshot.from_data(raw)

    def test_reserved_vocabulary_matches_inert_description_versions(self):
        vocabulary = json.loads((ROOT / 'protocol/controlled-composition-profile-v0.1.json').read_text())
        self.assertEqual(vocabulary['versions']['control_contract'], CONTRACT_SCHEMA)
        self.assertEqual(vocabulary['versions']['source_authority'], SOURCE_AUTHORITY_SCHEMA)
        self.assertEqual(vocabulary['material_profile'], PROFILE)


if __name__ == '__main__':
    unittest.main()
