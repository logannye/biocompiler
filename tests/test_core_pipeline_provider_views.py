"""Structural controls; installed native equivalence is a separate campaign."""
from contextlib import ExitStack
import copy
from dataclasses import fields
from types import MappingProxyType
import unittest
from unittest.mock import patch

from biocompiler.core_client import CoreProtocolError
from biocompiler.core_pipeline_provider_views import (
    ALIAS_CLASSES, CLASS_FIELDS, ProviderViewStore, StructuralViews, allocate, checked_ordered, origin_reference,
)
from biocompiler.core_pipeline_manager import _ordered
from biocompiler.pipeline_callback_objects import CallbackObjects
from biocompiler.ir.behavior import BehaviorProgram
from biocompiler.ir.component_assembly import ComponentAssembly
from biocompiler.ir.component_contracts import SequenceReferenceMetadata
from biocompiler.ir.composition import DependencyBinding, Provider, ResourceBinding, ResourcePool
from biocompiler.semantics.types import LEVEL
from biocompiler.synthesis.synthetic import SyntheticCandidate
from tools import capture_pipeline_fixed_provider_semantics as original


class StructuralProviderViewsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.examples = []
        cls.proposals = {}
        for case in original.CASES:
            retained = {'calls': [], 'contexts': {}}
            cls.proposals[case] = retained
            def factory(request, history, *, until, config):
                retained.update(request=request, config=config)
                return original.original_factory(request, history, until=until, config=config)
            def observe(stage, manager, pass_id, ordinal, context, proposal):
                if stage == 'after':
                    retained['calls'].append((pass_id, proposal))
                    retained['contexts'][pass_id] = context
                    if ordinal == 0:
                        cls.examples.append((case, pass_id, proposal.output, proposal.output.to_dict(), context.target))
            original.run_case(case, observe=observe, manager_factory=factory)

    def decode(self, pass_id, document, target, views=None):
        views = views or StructuralViews()
        if pass_id == 'intent_to_behavior':
            return views.behavior(document)
        if pass_id == 'behavior_to_synthetic':
            return views.candidate(document)
        return views.assembly(document, target)

    def test_all_three_actual_fixed_profiles_keep_every_raw_field_and_container(self):
        self.assertEqual(len(self.examples), 9)
        for case, pass_id, value, document, target in self.examples:
            with self.subTest(case=case, pass_id=pass_id):
                result = self.decode(pass_id, document, target)
                self.assertEqual(original.plain(result), original.plain(value))
                self.assertIsNot(result, value)
                self.assertEqual(type(result), type(value))
                if type(result) is ComponentAssembly:
                    self.assertIs(result.composition.target, target)

    def test_hydration_does_not_call_semantic_constructors_parsers_or_serializers(self):
        def forbidden(*args, **kwargs):
            raise AssertionError('Legacy semantic code ran during view hydration')
        with ExitStack() as stack:
            for cls in original.SAFE:
                for method in ('__init__', '__post_init__', 'from_dict', 'to_dict', 'resolve'):
                    if hasattr(cls, method):
                        stack.enter_context(patch.object(cls, method, forbidden))
            for _, pass_id, value, document, target in self.examples:
                result = self.decode(pass_id, document, target)
                self.assertEqual(original.plain(result), original.plain(value))

    def test_default_structural_policy_never_interns_equal_objects(self):
        for _, pass_id, _, document, target in self.examples:
            first = self.decode(pass_id, document, target)
            second = self.decode(pass_id, document, target)
            self.assertIsNot(first, second)
            if type(first) is BehaviorProgram:
                self.assertIsNot(first.nodes[0], second.nodes[0])
            elif type(first) is SyntheticCandidate:
                self.assertIsNot(first.generator_config, second.generator_config)
                self.assertIsNot(first.mechanism, second.mechanism)
            else:
                self.assertIsNot(first.registry, second.registry)
                self.assertIsNot(first.composition, second.composition)

    def test_immutable_domain_maps_keep_input_order(self):
        _, pass_id, _, document, target = next(item for item in self.examples if item[1] == 'intent_to_behavior')
        document = copy.deepcopy(document)
        document['policies'] = {'z': {'two': [2, {'one': 1}]}, 'a': False}
        result = self.decode(pass_id, document, target)
        self.assertIs(type(result.policies), MappingProxyType)
        self.assertEqual(tuple(result.policies), ('z', 'a'))
        self.assertIs(type(result.policies['z']['two']), tuple)
        with self.assertRaises(TypeError):
            result.policies['changed'] = True

    def test_field_census_schema_and_scalar_types_are_closed(self):
        for _, pass_id, _, document, target in self.examples:
            extra = copy.deepcopy(document)
            extra['forged'] = None
            missing = copy.deepcopy(document)
            del missing['schema_version']
            wrong = copy.deepcopy(document)
            wrong['schema_version'] = 'forged.v1'
            for mutant in (extra, missing, wrong):
                with self.assertRaises(CoreProtocolError):
                    self.decode(pass_id, mutant, target)
        views = StructuralViews()
        for value in (True, 1.0, '1', None):
            with self.assertRaises(CoreProtocolError):
                views.source({'file': 'x', 'line': value, 'function': 'f'}, ())
        with self.assertRaises(CoreProtocolError):
            views.lifecycle({'start': float('nan'), 'end': None, 'unit': 's'}, ())
        with self.assertRaises(CoreProtocolError):
            views.lifecycle({'start': True, 'end': None, 'unit': 's'}, ())

    def test_explicit_factory_sees_closed_classes_and_exact_field_paths(self):
        observed = []
        def factory(cls, path, document, values):
            observed.append((cls, path, tuple(values)))
            return allocate(cls, values)
        _, pass_id, value, document, target = next(item for item in self.examples if item[1] == 'behavior_to_synthetic')
        result = self.decode(pass_id, document, target, StructuralViews(factory))
        self.assertEqual(original.plain(result), original.plain(value))
        self.assertEqual(observed[-1][0], SyntheticCandidate)
        self.assertEqual(observed[-1][1], ())
        self.assertEqual(observed[-1][2], tuple(item.name for item in fields(SyntheticCandidate)))
        self.assertTrue(any(path == ('mechanism', 'nodes', 0, 'output', 'dtype') for _, path, _ in observed))

    def test_less_common_composition_fields_are_typed_without_normalization(self):
        views = StructuralViews()
        samples = [
            (DependencyBinding('i', 'r', 'p'), views.dependency_binding),
            (ResourceBinding('i', 'r', 'p'), views.resource_binding),
            (ResourcePool('p', 'resource', 'u', 1.0, 'provider', LEVEL), views.pool),
            (Provider('p', 'host', (), ('target',), ('z', 'a'), ('ref',)), views.provider),
            (SequenceReferenceMetadata('coding_rna', 3, ('unknown',)), views.reference),
        ]
        for value, decode in samples:
            result = decode(value.to_dict(), ())
            self.assertEqual(original.plain(result), original.plain(value))

    def envelopes(self, fixture, objects):
        request = fixture['request']
        host_values = [fixture['config'], request.target]
        for root in ('BOOLEAN', 'LEVEL', 'DURATION', 'defaultLifecycle'):
            host_values.append(origin_reference(request, root, []))
        for field, items in (('domain', request.domain.inputs), ('contract', request.contract.requirements)):
            collection = 'inputs' if field == 'domain' else 'requirements'
            for index in range(len(items)):
                path = [field, collection, index, 'observable']
                host_values.extend((origin_reference(request, 'request', path), origin_reference(request, 'request', path + ['dtype'])))
        host_values.extend(node.source for node in request.behavior.nodes if node.source is not None)
        tokens = []
        def native(value, document):
            index = next((i for i, previous in enumerate(tokens) if previous is value), None)
            if index is None:
                index = len(tokens)
                tokens.append(value)
            return {'kind': 'native', 'identity': 'typed/' + str(index), 'tree': _ordered(document)}
        def binding(value, document):
            if any(value is previous for previous in host_values):
                return {'kind': 'host', 'object': objects.retain(value)}
            return native(value, document)
        for pass_id, proposal in fixture['calls']:
            document = {'output': proposal.output.to_dict(), 'obligations': [],
                'source_links': [dict(vars(link)) for link in proposal.source_links],
                'observation_map': copy.deepcopy(proposal.observation_map), 'search_status': proposal.search_status}
            self.assertEqual(proposal.obligations, ())
            aliases = []
            def visit(value, raw, path):
                cls = type(value)
                if cls in (dict, MappingProxyType):
                    for key, child in value.items():
                        visit(child, raw[key], path + [key])
                elif cls in (tuple, list):
                    # TypeSpec dimensions are scalars with a different wire
                    # representation and introduce no typed child identities.
                    if type(raw) is list:
                        for index, child in enumerate(value):
                            visit(child, raw[index], path + [index])
                elif cls in CLASS_FIELDS:
                    if cls in ALIAS_CLASSES:
                        aliases.append({'kind': cls.__module__ + '.' + cls.__qualname__, 'paths': [path], 'binding': binding(value, raw)})
                    for field in fields(value):
                        if field.name in raw:
                            visit(object.__getattribute__(value, field.name), raw[field.name], path + [field.name])
            visit(proposal.output, document['output'], ['output'])
            for index, link in enumerate(proposal.source_links):
                visit(link, document['source_links'][index], ['source_links', index])
            bindings = {}
            if pass_id == 'behavior_to_synthetic':
                bindings = {'generator_config': binding(proposal.output.generator_config, document['output']['generator_config']),
                    'required_capabilities': {'kind': 'host', 'object': objects.retain(proposal.output.mechanism.required_capabilities)}}
            elif pass_id == 'synthetic_to_components':
                bindings = {name: binding(getattr(proposal.output, name), document['output'][name]) for name in ('registry', 'composition')}
                bindings['composition_target'] = {'kind': 'host', 'object': objects.retain(request.target)}
            yield pass_id, proposal, {'kind': 'proposal', 'value': document,
                'view': {'role': pass_id + '.producer', 'tree': _ordered(document), 'bindings': bindings, 'aliases': aliases}}

    def test_complete_actual_identity_graph_and_external_origins_survive_two_calls(self):
        for case, fixture in self.proposals.items():
            with self.subTest(case=case):
                objects = CallbackObjects()
                store = ProviderViewStore(objects.resolve)
                before, after = original.Ledger(), original.Ledger()
                request = fixture['request']
                for ledger in (before, after):
                    ledger.semantics(request.target, ['target'])
                    ledger.semantics(fixture['config'], ['requested_config'])
                    for name, value in original.source_origins(request):
                        ledger.semantics(value, ['source_origins', name])
                for index, (pass_id, actual, envelope) in enumerate(self.envelopes(fixture, objects)):
                    result = store.decode(envelope, role=pass_id + '.producer', target=request.target,
                        target_document=request.target.to_dict(), requested_config=fixture['config'],
                        input_payload=fixture['contexts'][pass_id].input)
                    self.assertEqual(original.plain(result), original.plain(actual))
                    before.semantics(actual, [index])
                    after.semantics(result, [index])
                    if pass_id == 'behavior_to_synthetic':
                        self.assertIs(result.output.generator_config, actual.output.generator_config if case != 'static:selected_equal'
                            else store.native[envelope['view']['bindings']['generator_config']['identity']].value)
                        if case == 'static:selected_equal':
                            self.assertIsNot(result.output.generator_config, fixture['config'])
                    # Proposal observations must be independently mutable trees.
                    self.assertIs(type(result.observation_map), dict)
                    self.assertIsNot(result.observation_map, actual.observation_map)
                self.assertEqual(after.graph(), before.graph())

    def test_ordered_projection_rejects_repaired_bool_int_and_duplicate_keys(self):
        with self.assertRaisesRegex(CoreProtocolError, 'differs'):
            checked_ordered(['scalar', True], 1)
        with self.assertRaisesRegex(CoreProtocolError, 'Duplicate'):
            checked_ordered(['object', [['key', ['scalar', 1]], ['key', ['scalar', 2]]]], {'key': 2})

    def test_origin_paths_are_exact_and_do_not_invoke_getters(self):
        request = self.proposals['static:requested']['request']
        self.assertIs(origin_reference(request, 'request', ['domain', 'inputs', 0, 'observable']), request.domain.inputs[0].observable)
        for root, path in [('request', ['target']), ('LEVEL', ['kind']), ('request', ['domain', 'inputs', True, 'observable']),
                           ('request', ['domain', 'inputs', -1, 'observable']), ('unknown', [])]:
            with self.assertRaises(CoreProtocolError):
                origin_reference(request, root, path)

    def test_alias_class_paths_tokens_and_limits_fail_closed(self):
        fixture = self.proposals['static:requested']
        objects = CallbackObjects()
        pass_id, _, envelope = next(self.envelopes(fixture, objects))
        def decode(value, store=None):
            return (store or ProviderViewStore(objects.resolve)).decode(value, role=pass_id + '.producer',
                target=fixture['request'].target, target_document=fixture['request'].target.to_dict(),
                input_payload=fixture['contexts'][pass_id].input)
        changed = copy.deepcopy(envelope)
        changed['view']['role'] = 'behavior_to_synthetic.producer'
        with self.assertRaisesRegex(CoreProtocolError, 'role'):
            decode(changed)
        changed = copy.deepcopy(envelope)
        changed['view']['aliases'][0]['kind'] = 'arbitrary.PythonClass'
        with self.assertRaisesRegex(CoreProtocolError, 'class tag'):
            decode(changed)
        changed = copy.deepcopy(envelope)
        changed['view']['aliases'][0]['paths'] = [['output', 'source_fingerprint']]
        with self.assertRaisesRegex(CoreProtocolError, 'not consumed'):
            decode(changed)
        with self.assertRaisesRegex(CoreProtocolError, 'identity limit'):
            decode(envelope, ProviderViewStore(objects.resolve, max_objects=0))
        with self.assertRaisesRegex(CoreProtocolError, 'retention limit'):
            decode(envelope, ProviderViewStore(objects.resolve, max_retained_bytes=0))

    def test_lower_retains_only_exact_context_input_and_root_tuples(self):
        fixture = self.proposals['static:requested']
        objects = CallbackObjects()
        pass_id, _, envelope = next(self.envelopes(fixture, objects))
        source = fixture['contexts'][pass_id].input
        def decode(value, payload):
            return ProviderViewStore(objects.resolve).decode(value, role=pass_id + '.producer',
                target=fixture['request'].target, target_document=fixture['request'].target.to_dict(), input_payload=payload)
        result = decode(envelope, source)
        sources = {node['id']: node for node in source['intent']['nodes']}
        for node in result.output.nodes:
            self.assertIs(node.inputs, sources[node.id]['inputs'])
        self.assertIs(result.output.roots, source['intent']['roots'])
        with self.assertRaisesRegex(CoreProtocolError, 'actual context input'):
            decode(envelope, None)
        for alter in (lambda x: x['output']['nodes'][1].update(inputs=['forged']),
                lambda x: x['output'].update(roots=['forged']),
                lambda x: x['output']['nodes'][1].update(id='forged')):
            changed = copy.deepcopy(envelope)
            alter(changed['value'])
            changed['view']['tree'] = _ordered(changed['value'])
            with self.assertRaisesRegex(CoreProtocolError, 'tuple differs|node identity'):
                decode(changed, source)

    def test_equal_new_child_token_cannot_hide_beneath_reused_root(self):
        fixture = self.proposals['static:requested']
        objects = CallbackObjects()
        store = ProviderViewStore(objects.resolve)
        envelopes = list(self.envelopes(fixture, objects))
        components = [envelope for pass_id, _, envelope in envelopes if pass_id == 'synthetic_to_components']
        def decode(value):
            return store.decode(value, role='synthetic_to_components.producer', target=fixture['request'].target,
                target_document=fixture['request'].target.to_dict(), requested_config=fixture['config'])
        decode(components[0])
        changed = copy.deepcopy(components[1])
        group = next(group for group in changed['view']['aliases'] if group['kind'].endswith('.ComponentLock'))
        old_identity = group['binding']['identity']
        replacements = 0
        for group in changed['view']['aliases']:
            if group['binding'].get('identity') == old_identity:
                group['binding']['identity'] = 'same-fields-new-identity'
                replacements += 1
        self.assertGreaterEqual(replacements, 2)
        # All trees/content remain exact. Only the claimed nested physical
        # identity changes under the already retained composition root.
        with self.assertRaisesRegex(CoreProtocolError, 'actual returned object identity'):
            decode(changed)

    def test_same_value_substituted_host_config_is_not_the_requested_object(self):
        fixture = self.proposals['static:requested']
        objects = CallbackObjects()
        _, _, envelope = next(item for item in self.envelopes(fixture, objects) if item[0] == 'behavior_to_synthetic')
        changed = copy.deepcopy(envelope)
        replacement = StructuralViews().config(fixture['config'].to_dict())
        changed['view']['bindings']['generator_config']['object'] = objects.retain(replacement)
        with self.assertRaisesRegex(CoreProtocolError, 'actual authored configuration'):
            ProviderViewStore(objects.resolve).decode(changed, role='behavior_to_synthetic.producer', target=fixture['request'].target,
                target_document=fixture['request'].target.to_dict(), requested_config=fixture['config'])


if __name__ == '__main__':
    unittest.main()
