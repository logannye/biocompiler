"""Source-origin structural controls; native integration runs in hosted CI."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import fields as dataclass_fields, replace
from types import MappingProxyType
import unittest
from unittest.mock import patch

from biocompiler import core_reference_provider_views as views
from biocompiler.compiler.construct import run_construct_pipeline
from biocompiler.compiler.molecular import run_molecular_pipeline
from biocompiler.compiler.passes import PassResult
from biocompiler.compiler.pipeline import CheckDecision
from biocompiler.core_client import CoreProtocolError
from biocompiler.core_pipeline_manager import _ordered
from biocompiler.core_pipeline_provider_views import allocate
from biocompiler.core_reference_views import ReferenceViews
from biocompiler.pipeline_callback_objects import CallbackObjects
from biocompiler.semantics.types import Level
from biocompiler.synthesis.construct import generate_construct
from biocompiler.backends.reference import emit_reference_sequence
from biocompiler.verification.evidence import CheckOutcome
from examples.reference_construct import reference_request


def forbidden(*args, **kwargs):
    raise AssertionError('Reference view entered legacy semantics')


def proposal_document(output):
    return {'output': output.to_dict(), 'obligations': [], 'source_links': [
        {'requirement_id': 'req', 'source_node_id': 'source',
         'target_node_id': 'target', 'pass_name': 'test'}],
        'observation_map': {}, 'search_status': 'candidate'}


def artifact(value, identity):
    return {'value': value, 'binding': {'kind': 'native', 'identity': identity, 'tree': _ordered(value)}}


def result_document(result):
    return {'value': {'status': result.status.value, 'scope': result.scope,
                     'artifact_id': result.artifact.id,
                     'unresolved': [item.to_dict() for item in result.unresolved]},
            'artifact': result.artifact.to_dict()}


def nonempty_objects(value, found=None):
    found = {} if found is None else found
    kind = type(value)
    if kind in (tuple, list, dict, MappingProxyType):
        if not value:
            return found
        children = value.values() if kind in (dict, MappingProxyType) else value
    elif kind in views.REFERENCE_FIELDS:
        children = vars(value).values()
    else:
        return found
    if id(value) in found:
        return found
    found[id(value)] = value
    for child in children:
        nonempty_objects(child, found)
    return found


class ReferenceProviderViewsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.examples = []
        for alphabet in ('DNA', 'RNA'):
            request, manifest, registry = reference_request(alphabet)
            saved = {'request': request, 'registry': registry, 'alphabet': alphabet}
            def construct(*args):
                saved['construct_build'] = run_construct_pipeline(*args)
                return saved['construct_build']
            def generate(parsed):
                saved['parsed_request'] = parsed
                saved['construct_output'] = generate_construct(parsed)
                return saved['construct_output']
            def emit(authored, parsed, original_registry, manifests):
                saved['parsed_construct'] = parsed
                saved['molecular_output'] = emit_reference_sequence(authored, parsed, original_registry, manifests)
                return saved['molecular_output']
            with patch('biocompiler.compiler.molecular.run_construct_pipeline', construct), \
                 patch('biocompiler.compiler.construct.generate_construct', generate), \
                 patch('biocompiler.compiler.molecular.emit_reference_sequence', emit):
                saved['molecular_build'] = run_molecular_pipeline(request, registry, {manifest.reference_set_id: manifest})
            cls.examples.append(saved)

    def provider(self, example, molecular=False):
        broker = CallbackObjects()
        if molecular:
            parsed = example['parsed_construct']
            document = parsed.to_dict()
            origin = views.ReferenceOrigins.molecular(parsed, document,
                request=example['request'],
                translation_policy=vars(views.MolecularRecord)['translation_policy'],
                encoding_policy=vars(views.MolecularArtifact)['encoding_policy'],
                evidence_policy=vars(views.MolecularArtifact)['evidence_policy'])
            objects = {name: getattr(origin, name) for name in
                ('parsed', 'request', 'translation_policy', 'encoding_policy', 'evidence_policy')}
            output = example['molecular_output']
            role = 'construct_to_molecular.producer'
        else:
            parsed = example['parsed_request']
            document = parsed.to_dict()
            origin = views.ReferenceOrigins.construct(parsed, document)
            objects = {'parsed': parsed}
            output = example['construct_output']
            role = 'components_to_construct.producer'
        value = proposal_document(output)
        wire = {'kind': 'proposal', 'value': value, 'view': {
            'role': role, 'tree': _ordered(value),
            'origins': {key: broker.retain(item) for key, item in objects.items()}}}
        return broker, views.ReferenceProviderViews(broker.resolve), origin, document, wire, output, role

    def builds(self, example):
        construct, molecular = example['construct_build'], example['molecular_build']
        first = {'build_id': 'build/construct', 'kind': 'construct',
                 'candidate': artifact(construct.candidate.to_dict(), 'candidate/construct'),
                 'check_result': artifact(construct.check_result.to_dict(), 'check/construct'),
                 'result': result_document(construct.result), 'construct': None}
        second = {'build_id': 'build/molecular', 'kind': 'molecular',
                  'candidate': artifact(molecular.candidate.to_dict(), 'candidate/molecular'),
                  'check_result': artifact(molecular.check_result.to_dict(), 'check/molecular'),
                  'result': result_document(molecular.result), 'construct': deepcopy(first['candidate'])}
        return first, second

    def test_complete_original_fields_and_all_whole_construct_origins(self):
        for example in self.examples:
            _, decoder, origins, source, wire, original, role = self.provider(example)
            first = decoder.decode(wire, role=role, origins=origins, input_document=source)
            second = decoder.decode(wire, role=role, origins=origins, input_document=source)
            self.assertIs(type(first), PassResult)
            self.assertEqual(views.reference_shape(first.output), views.reference_shape(original))
            self.assertIsNot(first, second)
            self.assertIsNot(first.output, second.output)
            self.assertIs(first.output.registry_lock, origins.parsed.composition.registry_lock)
            for name in ('molecules', 'placements', 'features', 'junctions',
                         'regulatory_relations', 'dependencies', 'evidence_policy'):
                self.assertIs(getattr(first.output, name), getattr(origins.parsed, name))
            self.assertIsNot(first.output.assumptions, origins.parsed.assumptions)
            self.assertIsNot(first.output.registry_lock.components[0], first.output.placements[0].component)
            self.assertIsNot(first.source_links, second.source_links)
            self.assertIsNot(first.source_links[0], second.source_links[0])
            self.assertIsNot(first.observation_map, second.observation_map)

    def test_closed_layout_census_and_exact_scalar_order_projection(self):
        for kind, names in views.REFERENCE_FIELDS.items():
            self.assertEqual(tuple(item.name for item in dataclass_fields(kind)), names)
        _, decoder, origins, source, wire, _, role = self.provider(self.examples[0])
        bad = deepcopy(wire)
        bad['view']['tree'] = _ordered({**bad['value'], 'search_status': True})
        with self.assertRaises(CoreProtocolError):
            decoder.decode(bad, role=role, origins=origins, input_document=source)
        # Fresh parsing retains arbitrary authored JSON map order, and binding
        # validation must observe it rather than canonicalize it away.
        source = deepcopy(source)
        resources = {'z': Level(1).to_dict(), 'a': Level(2).to_dict()}
        source['composition']['target']['resources'] = resources
        source['target']['resources'] = deepcopy(resources)
        parsed = ReferenceViews().construct_request(source)
        reordered = deepcopy(source)
        reordered['composition']['target']['resources'] = {'a': resources['a'], 'z': resources['z']}
        reordered['target']['resources'] = {'a': resources['a'], 'z': resources['z']}
        with self.assertRaisesRegex(CoreProtocolError, 'origin fields'):
            views.ReferenceOrigins.construct(parsed, reordered)

    def test_complete_molecular_origins_defaults_and_fresh_fields(self):
        for example in self.examples:
            _, decoder, origins, source, wire, original, role = self.provider(example, True)
            first = decoder.decode(wire, role=role, origins=origins, input_document=source).output
            second = decoder.decode(wire, role=role, origins=origins, input_document=source).output
            self.assertEqual(views.reference_shape(first), views.reference_shape(original))
            self.assertIsNot(first, second)
            self.assertIsNot(first.records, second.records)
            a, b = first.records[0], second.records[0]
            self.assertIsNot(a, b)
            self.assertIsNot(a.feature_statuses, b.feature_statuses)
            self.assertIs(first.registry_lock, origins.parsed.registry_lock)
            self.assertIs(a.reference_selection, example['request'].references[0].selection)
            placement = origins.parsed.placements[0]
            for name in ('component', 'source_range', 'molecule_range', 'source'):
                self.assertIs(getattr(a, name), getattr(placement, name))
            self.assertIs(a.features, origins.parsed.features)
            self.assertIs(a.translation_policy, origins.translation_policy)
            self.assertIs(first.encoding_policy, origins.encoding_policy)
            self.assertIs(first.evidence_policy, origins.evidence_policy)
            self.assertIsNot(a.requirement_ids, placement.requirement_ids)

    def test_no_semantic_constructors_parsers_serializers_or_checkers_run(self):
        prepared = [self.provider(example, molecular) for example in self.examples for molecular in (False, True)]
        builds = [(example, *self.builds(example)) for example in self.examples]
        with ExitStack() as stack:
            for kind in views.REFERENCE_FIELDS:
                for name in ('__init__', '__post_init__', 'from_dict', 'from_json', 'to_dict'):
                    if hasattr(kind, name):
                        stack.enter_context(patch.object(kind, name, forbidden))
            for path in ('biocompiler.registry.components.ComponentRegistry.resolve',
                         'biocompiler.registry.references.ReferenceManifest.record',
                         'biocompiler.synthesis.construct.generate_construct',
                         'biocompiler.backends.reference.emit_reference_sequence',
                         'biocompiler.verification.construct.check_construct',
                         'biocompiler.verification.construct.check_construct_request',
                         'biocompiler.verification.molecular.check_molecular'):
                stack.enter_context(patch(path, forbidden))
            for _, decoder, origins, source, wire, original, role in prepared:
                actual = decoder.decode(wire, role=role, origins=origins, input_document=source)
                self.assertEqual(views.reference_shape(actual.output), views.reference_shape(original))
            for example, first, second in builds:
                store = views.ReferenceBuildStore()
                c = store.decode(first, manager=example['construct_build'].manager,
                    result=example['construct_build'].result, result_envelope=first['result'])
                m = store.decode(second, manager=c.manager, result=example['molecular_build'].result,
                    result_envelope=second['result'], upstream=c)
                self.assertIs(m.construct, c.candidate)

    def test_bound_origin_rejects_equal_copy_wrong_input_order_kind_and_policy(self):
        broker, decoder, origins, source, wire, _, role = self.provider(self.examples[0])
        bad = deepcopy(wire)
        bad['view']['origins']['parsed'] = broker.retain(ReferenceViews().construct_request(source))
        with self.assertRaisesRegex(CoreProtocolError, 'actual callback object'):
            decoder.decode(bad, role=role, origins=origins, input_document=source)
        changed = deepcopy(source)
        changed['assumptions'] = ['different']
        with self.assertRaisesRegex(CoreProtocolError, 'different provider input'):
            decoder.decode(wire, role=role, origins=origins, input_document=changed)
        for mutate in (lambda v: v['view']['origins'].update(extra={'handle': 'object/0'}),
                       lambda v: v['view'].update(role='construct_to_molecular.producer'),
                       lambda v: v['value']['output']['molecules'][0].update(length=True)):
            bad = deepcopy(wire); mutate(bad)
            bad['view']['tree'] = _ordered(bad['value'])
            with self.assertRaises(CoreProtocolError):
                decoder.decode(bad, role=role, origins=origins, input_document=source)
        molecular = self.examples[0]
        with self.assertRaisesRegex(CoreProtocolError, 'class default'):
            views.ReferenceOrigins.molecular(molecular['parsed_construct'], molecular['parsed_construct'].to_dict(),
                request=molecular['request'], translation_policy=replace(vars(views.MolecularRecord)['translation_policy']),
                encoding_policy=vars(views.MolecularArtifact)['encoding_policy'],
                evidence_policy=vars(views.MolecularArtifact)['evidence_policy'])

    def test_decisions_fresh_deeply_frozen_ordered_and_closed_roles(self):
        original = CheckDecision(CheckOutcome.PASS, 'checked', {'z': {'b': [1, False]}, 'a': 2.0})
        document = original.to_dict()
        for role in views.REFERENCE_PROVIDER_ROLES - views._PRODUCERS:
            wire = {'kind': 'decision', 'value': document,
                    'view': {'role': role, 'tree': _ordered(document), 'origins': {}}}
            decoder = views.ReferenceProviderViews(forbidden)
            a, b = decoder.decode(wire, role=role), decoder.decode(wire, role=role)
            self.assertEqual(views.reference_shape(a), views.reference_shape(original))
            self.assertIsNot(a, b); self.assertIsNot(a.evidence, b.evidence)
            self.assertEqual(tuple(a.evidence), ('z', 'a'))
            self.assertIs(type(a.evidence), MappingProxyType)
            self.assertIs(type(a.evidence['z']['b']), tuple)
            with self.assertRaises(CoreProtocolError):
                decoder.decode(wire, role='synthetic_to_components.validator')

    def test_normalized_parsed_document_does_not_replace_actual_input_identity(self):
        broker, decoder, origins, source, wire, _, role = self.provider(self.examples[0])
        raw = deepcopy(source)
        del raw['source_request_fingerprint']
        # The native parser's canonical representation is independent of the
        # raw caller document; its added optional field does not rewrite input.
        normalized = deepcopy(source)
        normalized['source_request_fingerprint'] = None
        parsed = ReferenceViews().construct_request(normalized)
        origins = views.ReferenceOrigins.construct(parsed, raw, parsed_document=normalized)
        wire['view']['origins']['parsed'] = broker.retain(parsed)
        actual = decoder.decode(wire, role=role, origins=origins, input_document=raw)
        self.assertIs(actual.output.placements, parsed.placements)
        with self.assertRaisesRegex(CoreProtocolError, 'different provider input'):
            decoder.decode(wire, role=role, origins=origins, input_document=normalized)

    def test_opaque_host_return_is_exact_and_never_inspected(self):
        class Hostile:
            def __getattribute__(self, name):
                raise AssertionError('Output was observed')
        proposal = PassResult(Hostile(), (), ())
        broker = CallbackObjects()
        wire = {'kind': 'host', 'object': broker.retain(proposal)}
        decoder = views.ReferenceProviderViews(broker.resolve)
        self.assertIs(decoder.decode(wire, role='components_to_construct.producer', host_result=proposal), proposal)
        with self.assertRaisesRegex(CoreProtocolError, 'paired proposal'):
            decoder.decode(wire, role='components_to_construct.producer', host_result=PassResult(None, (), ()))

    def test_public_builds_preserve_exact_manager_result_and_upstream_only(self):
        for example in self.examples:
            first, second = self.builds(example)
            store = views.ReferenceBuildStore()
            original_c, original_m = example['construct_build'], example['molecular_build']
            c = store.decode(first, manager=original_c.manager, result=original_c.result, result_envelope=first['result'])
            m = store.decode(second, manager=original_m.manager, result=original_m.result,
                             result_envelope=second['result'], upstream=c)
            self.assertIs(type(c), views.ConstructBuild); self.assertIs(type(m), views.MolecularBuild)
            self.assertIs(c.manager, m.manager); self.assertIs(c.manager, original_c.manager)
            self.assertIs(c.result, original_c.result); self.assertIs(m.result, original_m.result)
            self.assertIs(m.construct, c.candidate)
            for actual, original in ((c, original_c), (m, original_m)):
                self.assertEqual(views.reference_shape(actual.candidate), views.reference_shape(original.candidate))
                self.assertEqual(views.reference_shape(actual.check_result), views.reference_shape(original.check_result))
                candidate_ids = nonempty_objects(actual.candidate)
                for root in (actual.result.artifact.payload, example['construct_output'], example['molecular_output'], example['request']):
                    self.assertFalse(set(candidate_ids) & set(nonempty_objects(root)))
            self.assertIsNot(m.candidate.encoding_policy, vars(views.MolecularArtifact)['encoding_policy'])
            self.assertIs(store.decode(first, manager=c.manager, result=c.result, result_envelope=first['result']), c)
            self.assertIs(store.decode(second, manager=m.manager, result=m.result,
                result_envelope=second['result'], upstream=c), m)

    def test_opaque_final_source_capability_and_physical_root_are_exact(self):
        example = self.examples[0]
        _, envelope = self.builds(example)
        original = example['molecular_build']
        broker = CallbackObjects()
        class Opaque:
            def __getattribute__(self, name):
                raise AssertionError('Opaque returned root must not be inspected')
            def __eq__(self, other):
                raise AssertionError('Opaque returned root must not be compared')
        root = Opaque()
        reference = broker.retain(root)
        envelope['construct'] = {'value': None, 'binding': {'kind': 'host', 'object': reference}}
        origin = (reference, root)
        store = views.ReferenceBuildStore()
        built = store.decode(envelope, manager=original.manager, result=original.result,
            result_envelope=envelope['result'], construct_origin=origin)
        self.assertIs(built.construct, root)
        self.assertIs(store.decode(envelope, manager=original.manager, result=original.result,
            result_envelope=envelope['result'], construct_origin=origin), built)
        for other in ((reference, Opaque()), (broker.retain(Opaque()), root)):
            with self.assertRaises(CoreProtocolError):
                store.decode(envelope, manager=original.manager, result=original.result,
                    result_envelope=envelope['result'], construct_origin=other)
        for change in (lambda raw: raw['construct'].update(value={}),
                       lambda raw: raw['construct']['binding'].update(object=broker.retain(Opaque())),
                       lambda raw: raw['construct']['binding'].update(extra=None)):
            wrong = deepcopy(envelope)
            change(wrong)
            with self.assertRaises(CoreProtocolError):
                views.ReferenceBuildStore().decode(wrong, manager=original.manager, result=original.result,
                    result_envelope=envelope['result'], construct_origin=origin)

    def test_build_identity_record_and_result_mutants_fail_without_content_interning(self):
        example = self.examples[0]
        first, second = self.builds(example)
        original = example['construct_build']
        for change in (
            lambda v: v.update(build_id='candidate/construct'),
            lambda v: v['check_result']['binding'].update(identity='candidate/construct'),
            lambda v: v['candidate']['value']['assumptions'].append('changed'),
            lambda v: v['candidate']['binding'].update(kind='host'),
        ):
            bad = deepcopy(first); change(bad)
            bad['candidate']['binding']['tree'] = _ordered(bad['candidate']['value'])
            with self.assertRaises(CoreProtocolError):
                views.ReferenceBuildStore().decode(bad, manager=original.manager,
                    result=original.result, result_envelope=first['result'])
        store = views.ReferenceBuildStore()
        c = store.decode(first, manager=original.manager, result=original.result, result_envelope=first['result'])
        with self.assertRaisesRegex(CoreProtocolError, 'rebound'):
            store.decode(first, manager=original.manager, result=replace(original.result), result_envelope=first['result'])
        bad = deepcopy(second); bad['construct']['binding']['identity'] = 'same-value-different-origin'
        with self.assertRaisesRegex(CoreProtocolError, 'earlier build origin'):
            store.decode(bad, manager=c.manager, result=example['molecular_build'].result,
                         result_envelope=second['result'], upstream=c)
        other = deepcopy(first)
        other['build_id'] = 'other-build'
        other['candidate']['binding']['identity'] = 'other-candidate'
        other['check_result']['binding']['identity'] = 'other-check'
        d = store.decode(other, manager=original.manager, result=original.result, result_envelope=first['result'])
        self.assertIsNot(d.candidate, c.candidate)
        self.assertIsNot(d.candidate.placements[0], c.candidate.placements[0])

    def test_resources_fail_before_domain_allocation_and_host_hooks_are_closed(self):
        example = self.examples[0]
        first, _ = self.builds(example)
        with patch.object(ReferenceViews, 'construct_candidate', forbidden):
            with self.assertRaisesRegex(CoreProtocolError, 'retention limit'):
                views.ReferenceBuildStore(max_objects=1).decode(first,
                    manager=example['construct_build'].manager, result=example['construct_build'].result,
                    result_envelope=first['result'])
        class Hostile:
            def __getattribute__(self, name):
                raise AssertionError('Host descriptor ran')
            def __eq__(self, other):
                raise AssertionError('Host equality ran')
        with self.assertRaises(CoreProtocolError):
            views.reference_shape(Hostile())
        loop = []; loop.append(loop)
        with self.assertRaisesRegex(CoreProtocolError, 'resource limit'):
            views.reference_shape(loop)

    def test_cached_root_cannot_hide_equal_copy_or_changed_descendant(self):
        example = self.examples[0]
        first, second = self.builds(example)
        for mutate in (
            lambda c: object.__setattr__(c.candidate.placements[0], 'orientation', 'reverse'),
            lambda c: object.__setattr__(c, 'candidate', ReferenceViews().construct_candidate(first['candidate']['value'])),
            lambda c: object.__setattr__(c.candidate, 'placements',
                ReferenceViews().construct_candidate(first['candidate']['value']).placements),
        ):
            store = views.ReferenceBuildStore()
            c = store.decode(first, manager=example['construct_build'].manager,
                result=example['construct_build'].result, result_envelope=first['result'])
            mutate(c)
            with self.assertRaisesRegex(CoreProtocolError, 'cached .* changed'):
                store.decode(first, manager=c.manager, result=c.result, result_envelope=first['result'])


if __name__ == '__main__':
    unittest.main()
