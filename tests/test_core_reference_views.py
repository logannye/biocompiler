"""Complete original representations without Python semantic execution."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import fields as dataclass_fields
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from biocompiler import core_reference_views as views
from biocompiler.core_client import CoreProtocolError
from biocompiler.core_pipeline_provider_views import allocate
from biocompiler.core_pipeline_session import encode_document
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.ir.components import ComponentLock
from biocompiler.registry.components import ComponentRegistry, RegistryLock
from biocompiler.semantics.context import TargetContext
from biocompiler.semantics.types import DURATION

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'tests/conformance/reference-contracts-v1.json'
PIN = 'f0d3acadad15fbc29f195fc1a7dae875e8fb027565ec20fdbe1934fec7f3cf1b'
KINDS = {
    'reference-record': ('reference_record', views.ReferenceRecord),
    'reference-manifest': ('reference_manifest', views.ReferenceManifest),
    'reference-selection': ('reference_selection', views.ReferenceSelection),
    'sequence-range': ('sequence_range', views.SequenceRange),
    'construct-reference': ('construct_reference', views.ConstructReference),
    'construct-molecule': ('construct_molecule', views.ConstructMolecule),
    'component-placement': ('component_placement', views.ComponentPlacement),
    'construct-feature': ('construct_feature', views.ConstructFeature),
    'construct-junction': ('construct_junction', views.ConstructJunction),
    'regulatory-relationship': ('regulatory_relationship', views.RegulatoryRelationship),
    'construct-dependency': ('construct_dependency', views.ConstructDependency),
    'layout-evidence-policy': ('layout_evidence_policy', views.LayoutEvidencePolicy),
    'construct-request': ('construct_request', views.ConstructRequest),
    'construct-candidate': ('construct_candidate', views.ConstructCandidate),
    'feature-status': ('feature_status', views.FeatureStatus),
    'translation-policy': ('translation_policy', views.TranslationPolicy),
    'encoding-policy': ('encoding_policy', views.EncodingPolicy),
    'encoding-evidence-policy': ('encoding_evidence_policy', views.EncodingEvidencePolicy),
    'encoding-change': ('encoding_change', views.EncodingChange),
    'molecular-record': ('molecular_record', views.MolecularRecord),
    'molecular-artifact': ('molecular_artifact', views.MolecularArtifact),
    'construct-result': ('construct_result', views.ConstructResult),
    'molecular-result': ('molecular_result', views.MolecularResult),
}


def forbidden(*args, **kwargs):
    raise AssertionError('Reference structural hydration entered legacy semantics')


class CoreReferenceViewsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = INDEX.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == PIN
        index = json.loads(raw)
        cls.rows = []
        seen = set()
        for row in index['observations']:
            operation, result = row['operation'], row['outcome']
            if not operation.startswith('decode-') or result['status'] != 'return':
                continue
            kind = operation[7:].removesuffix('-json')
            identity = kind, result['value']
            if identity in seen:
                continue
            seen.add(identity)
            data = (INDEX.with_suffix('') / (result['value'] + '.json')).read_bytes()
            assert hashlib.sha256(data[:-1]).hexdigest() == result['value']
            assert data.endswith(b'\n')
            document = json.loads(data)
            name, record_type = KINDS[kind]
            # The original expected object is built before the execution guard.
            original = record_type.from_dict(document)
            cls.rows.append((kind, name, document, result, original))
        assert len(cls.rows) == 437
        assert {row[0] for row in cls.rows} == set(KINDS)

    def sample(self, kind):
        return deepcopy(next(row[2] for row in self.rows if row[0] == kind))

    def test_every_complete_original_record_and_identity_without_semantic_calls(self):
        decoder = views.ReferenceViews()
        classes = {row[1] for row in KINDS.values()} | {
            views.ConstructDiagnostic, views.MolecularDiagnostic, views.MolecularCheck,
            views.CompositionRequest, ComponentRegistry, RegistryLock, ComponentLock,
            PinnedIdentity, TargetContext,
        }
        with ExitStack() as stack:
            for record_type in classes:
                for name in ('__init__', '__post_init__', 'from_dict', 'from_json'):
                    if hasattr(record_type, name):
                        stack.enter_context(patch.object(record_type, name, forbidden))
            for path in (
                'biocompiler.registry.references.normalize_sequence',
                'biocompiler.registry.references.translate_cds',
                'biocompiler.registry.references.ReferenceManifest.record',
                'biocompiler.registry.reference_components.adapt_reference_component',
                'biocompiler.registry.components.ComponentRegistry.resolve',
                'biocompiler.synthesis.construct.generate_construct',
                'biocompiler.backends.reference.emit_reference_sequence',
                'biocompiler.verification.construct.check_construct',
                'biocompiler.verification.construct.check_construct_request',
                'biocompiler.verification.molecular.check_molecular',
                'biocompiler.ir.serialization.fingerprint',
            ):
                stack.enter_context(patch(path, forbidden))
            actual = [getattr(decoder, name)(document) for _, name, document, _, _ in self.rows]
        for (kind, _, document, result, original), value in zip(self.rows, actual):
            with self.subTest(kind=kind, fingerprint=result['fingerprint']):
                self.assertIs(type(value), type(original))
                self.assertEqual(value, original)
                self.assertEqual(value.to_dict(), document)
                self.assertEqual(value.fingerprint, result['fingerprint'])
                if 'layout_fingerprint' in result:
                    self.assertEqual(value.layout_fingerprint, result['layout_fingerprint'])
                self.assertEqual({field.name for field in dataclass_fields(value)}, set(vars(value)))

    def test_equal_documents_remain_fresh_objects_without_identity_authority(self):
        decoder = views.ReferenceViews()
        raw = self.sample('construct-request')
        first, second = decoder.construct_request(raw), decoder.construct_request(raw)
        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertIsNot(first.composition, second.composition)
        self.assertIsNot(first.target, second.target)
        self.assertIs(first.target, first.composition.target)
        self.assertIs(first.registry_lock, first.composition.registry_lock)
        self.assertIsNot(first.placements[0], second.placements[0])

    def test_redundant_target_preserves_exact_numeric_types(self):
        decoder = views.ReferenceViews()
        raw = self.sample('construct-request')
        quantity = {'kind': 'scalar', 'value': 1, 'unit': 's',
            'canonical_value': 1, 'type': DURATION.to_dict()}
        raw['composition']['target']['resources'] = {'duration': quantity}
        raw['target'] = deepcopy(raw['composition']['target'])
        self.assertEqual(encode_document(decoder.construct_request(raw).to_dict()),
            encode_document(raw))
        for field in ('value', 'canonical_value'):
            for replacement in (True, 1.0):
                changed = deepcopy(raw)
                changed['target']['resources']['duration'][field] = replacement
                with self.subTest(field=field, replacement=replacement), self.assertRaises(CoreProtocolError):
                    decoder.construct_request(changed)
        floating = deepcopy(raw)
        for target in (floating['target'], floating['composition']['target']):
            target['resources']['duration']['value'] = 1.0
            target['resources']['duration']['canonical_value'] = 1.0
        self.assertEqual(encode_document(decoder.construct_request(floating).to_dict()),
            encode_document(floating))

    def test_explicit_factory_receives_actual_paths_types_documents_and_fields(self):
        raw = self.sample('construct-candidate')
        original = views.ReferenceViews().construct_candidate(raw)
        wanted = ('root', 'placements', 0, 'source_range')
        retained = original.placements[0].source_range
        events = []
        def factory(kind, path, document, fields):
            events.append((kind, path, deepcopy(document), tuple(fields)))
            if path == wanted:
                self.assertIs(kind, views.SequenceRange)
                self.assertEqual(document, raw['placements'][0]['source_range'])
                self.assertEqual(set(fields), {'start', 'end'})
                return retained
            return allocate(kind, fields)
        result = views.ReferenceViews(factory).construct_candidate(raw, ('root',))
        self.assertIs(result.placements[0].source_range, retained)
        self.assertIsNot(result.placements[0].molecule_range, retained)
        self.assertIsNot(result.placements[0], original.placements[0])
        self.assertEqual(result.to_dict(), raw)
        self.assertEqual(sum(path == wanted for _, path, _, _ in events), 1)
        self.assertEqual(events[-1][1], ('root',))
        self.assertEqual(events[-1][2], raw)

    def test_nested_metadata_is_frozen_and_detached_from_wire_containers(self):
        raw = self.sample('reference-manifest')
        before = deepcopy(raw)
        value = views.ReferenceViews().reference_manifest(raw)
        self.assertEqual(raw, before)
        with self.assertRaises(TypeError):
            value.sources[0]['id'] = 'changed'
        with self.assertRaises(TypeError):
            value.records[0].normalization['policy'] = 'changed'
        with self.assertRaises(TypeError):
            value.translation['genetic_code'] = 999
        raw['sources'][0]['id'] = 'changed'
        raw['records'][0]['normalization']['policy'] = 'changed'
        self.assertEqual(value.to_dict(), before)

    def test_representation_edits_cannot_replace_derived_inventory_or_claim_tags(self):
        decoder = views.ReferenceViews()
        mutations = [
            ('sequence-range', 'sequence_range', lambda d: d.update(start=True)),
            ('sequence-range', 'sequence_range', lambda d: d.update(convention='other')),
            ('reference-manifest', 'reference_manifest', lambda d: d.update(schema_version='other')),
            ('construct-request', 'construct_request', lambda d: d.update(target={})),
            ('construct-request', 'construct_request', lambda d: d.update(nodes=[])),
            ('construct-candidate', 'construct_candidate', lambda d: d.update(nodes=[])),
            ('molecular-record', 'molecular_record', lambda d: d.update(length=True)),
            ('molecular-record', 'molecular_record', lambda d: d.update(length=d['length'] + 1)),
            ('molecular-artifact', 'molecular_artifact', lambda d: d.update(nodes=[])),
            ('molecular-artifact', 'molecular_artifact', lambda d: d.update(human_therapeutic_admission='admitted')),
            ('construct-result', 'construct_result', lambda d: d.update(outcome='certified')),
            ('molecular-result', 'molecular_result', lambda d: d.update(unknown_field='accepted')),
        ]
        for kind, name, change in mutations:
            raw = self.sample(kind)
            change(raw)
            with self.subTest(kind=kind, method=name), self.assertRaises(CoreProtocolError):
                getattr(decoder, name)(raw)


if __name__ == '__main__':
    unittest.main()
