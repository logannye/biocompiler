"""Default input representation and identities; no native execution evidence."""
from copy import deepcopy
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from types import MappingProxyType
import unittest
from unittest.mock import patch

from biocompiler.core_client import CoreProtocolError
from biocompiler.core_reference_package_origins import input_roots
from biocompiler.ir.composition import CompositionInstance
from biocompiler.ir.construct import ConstructRequest
from biocompiler.registry import reference_builds

ROOT = Path(__file__).resolve().parents[1]


def physical_graph(roots):
    """Independent first-occurrence graph, including complete fields/map order."""
    retained, nodes = {}, []

    def visit(value):
        if isinstance(value, Enum):
            return ['enum', type(value).__qualname__, value.value]
        if value is None or type(value) in (bool, int, float, str):
            return [type(value).__name__, value]
        identity = id(value)
        if identity in retained:
            return ['ref', retained[identity]]
        retained[identity] = index = len(nodes)
        nodes.append(None)
        if is_dataclass(value):
            members = [[field.name, visit(object.__getattribute__(value, field.name))]
                       for field in fields(value)]
            node = ['record', type(value).__module__, type(value).__qualname__, members]
        elif type(value) in (dict, MappingProxyType):
            node = [type(value).__name__, [[visit(key), visit(item)] for key, item in value.items()]]
        elif type(value) in (tuple, list):
            node = [type(value).__name__, [visit(item) for item in value]]
        else:
            raise AssertionError('Unreviewed graph value: ' + str(type(value)))
        nodes[index] = node
        return ['ref', index]

    return [visit(roots), nodes]


class ReferencePackageInputOriginsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.originals = [reference_builds.load_reference_inputs(alphabet, ROOT / 'data/references/fap_car')
                         for alphabet in ('DNA', 'RNA', 'DNA')]
        cls.documents = [[root.to_dict() for root in triple] for triple in cls.originals]

    def hydrate(self, index=0, documents=None):
        return input_roots(('DNA', 'RNA', 'DNA')[index],
                           *deepcopy(self.documents[index] if documents is None else documents))

    def test_complete_three_load_graph_matches_actual_original_constructor(self):
        actual = [self.hydrate(index) for index in range(3)]
        external_origins = (reference_builds.MANIFEST_PIN,
                            reference_builds.REFERENCE_PINS['DNA'],
                            reference_builds.REFERENCE_PINS['RNA'],
                            vars(CompositionInstance)['lifetime'],
                            vars(ConstructRequest)['evidence_policy'])
        self.assertEqual(physical_graph((self.originals, external_origins)),
                         physical_graph((actual, external_origins)))

    def test_every_complete_serialized_root_matches_original(self):
        for index, expected in enumerate(self.documents):
            self.assertEqual([root.to_dict() for root in self.hydrate(index)], expected)

    def test_equal_independent_ranges_domains_and_loads_remain_distinct(self):
        request, _, registry = self.hydrate()
        other, _, other_registry = self.hydrate()
        placement = request.placements[0]
        self.assertEqual(placement.source_range, placement.molecule_range)
        self.assertIsNot(placement.source_range, placement.molecule_range)
        instance = request.composition.instances[0]
        self.assertEqual(instance.required_domain, registry.components[0].supported_domain)
        self.assertIsNot(instance.required_domain, registry.components[0].supported_domain)
        self.assertIsNot(request, other)
        self.assertIsNot(registry.components[0], other_registry.components[0])
        self.assertIsNot(request.composition.registry_lock.components[0],
                         other.composition.registry_lock.components[0])
        self.assertIsNot(registry.components[0].identities[0], other_registry.components[0].identities[0])

    def test_explicit_constructor_shared_values_retain_actual_identity(self):
        request, _, registry = self.hydrate()
        lock = request.composition.registry_lock
        self.assertIs(lock.components[0], request.composition.instances[0].component)
        self.assertIs(lock.components[0], request.placements[0].component)
        self.assertIs(request.references[0].selection.manifest, reference_builds.MANIFEST_PIN)
        self.assertIs(request.placements[0].reference, reference_builds.REFERENCE_PINS['DNA'])
        self.assertIs(lock.identities[0], registry.components[0].evidence[0])
        self.assertIs(lock.identities[1], registry.components[0].identities[3])

    def test_changed_shared_lock_origin_is_rejected(self):
        documents = deepcopy(self.documents[0])
        documents[0]['placements'][0]['component']['content_fingerprint'] = '0' * 64
        with self.assertRaisesRegex(CoreProtocolError, 'constructor origin'):
            self.hydrate(documents=documents)

    def test_reordered_identical_pin_inventory_is_rejected(self):
        documents = deepcopy(self.documents[0])
        identities = documents[0]['composition']['registry_lock']['identities']
        identities[0], identities[1] = identities[1], identities[0]
        with self.assertRaisesRegex(CoreProtocolError, 'constructor origin'):
            self.hydrate(documents=documents)

    def test_selected_alphabet_does_not_select_an_equal_pin(self):
        with self.assertRaisesRegex(CoreProtocolError, 'constructor origin'):
            input_roots('RNA', *deepcopy(self.documents[0]))

    def test_changed_current_default_is_rejected(self):
        with patch.object(reference_builds, 'MANIFEST_PIN', deepcopy(reference_builds.MANIFEST_PIN)):
            with self.assertRaisesRegex(CoreProtocolError, 'defaults changed'):
                self.hydrate()

    def test_extra_fixed_profile_member_is_rejected(self):
        documents = deepcopy(self.documents[0])
        documents[2]['components'].append(deepcopy(documents[2]['components'][0]))
        with self.assertRaisesRegex(CoreProtocolError, 'single-CDS constructor'):
            self.hydrate(documents=documents)

    def test_hydration_never_calls_original_constructors_or_loader(self):
        def forbidden(*args, **kwargs):
            raise AssertionError('Python construction executed in native view hydration')
        with patch.object(reference_builds, 'load_reference_inputs', forbidden), \
                patch.object(reference_builds, 'adapt_reference_component', forbidden), \
                patch.object(reference_builds, 'prepare_reference_construct', forbidden), \
                patch.object(ConstructRequest, '__post_init__', forbidden), \
                patch.object(CompositionInstance, '__post_init__', forbidden):
            self.hydrate()


if __name__ == '__main__':
    unittest.main()
