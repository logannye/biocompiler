"""Representation controls for public builds; hosted replay establishes parity."""
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import fields as dataclass_fields, is_dataclass
from enum import Enum
from types import MappingProxyType
import unittest
from unittest.mock import patch

from biocompiler.core_client import CoreProtocolError
from biocompiler.core_pipeline_build_views import BuildViewStore, BuildViews, build_shape, parsed_candidate, synthetic_build, component_build
from biocompiler.core_pipeline_provider_views import ALIAS_CLASSES, CLASS_FIELDS, ProviderViewStore, origin_reference
from biocompiler.core_pipeline_manager import _ordered
from biocompiler.pipeline_callback_objects import CallbackObjects
from biocompiler.compiler.components import run_component_pipeline
from biocompiler.compiler.synthetic import run_synthetic_pipeline
from tools import capture_pipeline_fixed_provider_semantics as original
from tools import capture_pipeline_fixed_build_semantics as original_builds


def plain(value):
    if isinstance(value, Enum):
        return (type(value).__module__, type(value).__qualname__, value.value)
    if value is None or type(value) in (str, bool, int, float):
        return (type(value).__name__, value)
    if type(value) in (dict, MappingProxyType):
        return (type(value).__name__, tuple((key, plain(item)) for key, item in value.items()))
    if type(value) in (tuple, list):
        return (type(value).__name__, tuple(plain(item) for item in value))
    if is_dataclass(value):
        return (type(value).__module__, type(value).__qualname__, tuple(vars(value)),
            tuple((field.name, plain(object.__getattribute__(value, field.name))) for field in dataclass_fields(value)))
    raise AssertionError(type(value))


def classes(value):
    if is_dataclass(value):
        yield type(value)
        for field in dataclass_fields(value):
            yield from classes(object.__getattribute__(value, field.name))
    elif type(value) in (dict, MappingProxyType):
        for item in value.values():
            yield from classes(item)
    elif type(value) in (tuple, list):
        for item in value:
            yield from classes(item)


class BuildViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.examples = []
        cls.builds = []
        for case in original.CASES:
            request, history, until, config = original.authority(case)
            synthetic = run_synthetic_pipeline(request, history, until=until, config=config)
            component = run_component_pipeline(request, history, until=until, config=config)
            cls.builds.extend((synthetic, component))
            for kind, value in (("candidate", synthetic.candidate), ("candidate", component.candidate),
                    ("assembly", component.assembly), ("link_result", component.link_result),
                    ("check_result", component.behavior_result)):
                cls.examples.append((kind, value, value.to_dict()))
            if synthetic.selection_result is not None:
                cls.examples.append(("selection", synthetic.selection_result, synthetic.selection_result.to_dict()))
            if component.selection_result is not None:
                cls.examples.append(("selection", component.selection_result, component.selection_result.to_dict()))

    def decode(self, kind, value):
        views = BuildViews()
        if kind == "assembly":
            target = views.target(value["composition"]["target"], ("composition", "target"))
            return views.assembly(value, target)
        return getattr(views, kind)(value)

    def test_complete_original_final_artifact_fields_and_mapping_order(self):
        self.assertEqual(len(self.examples), 17)
        for kind, expected, value in self.examples:
            with self.subTest(kind=kind):
                actual = self.decode(kind, value)
                self.assertEqual(plain(actual), plain(expected))
                self.assertIs(type(actual), type(expected))
                self.assertIsNot(actual, expected)

    def test_no_legacy_constructors_parsers_serializers_or_selection_properties(self):
        def forbidden(*args, **kwargs):
            raise AssertionError("Legacy semantics executed during build view hydration")
        targets = {cls for _, value, _ in self.examples for cls in classes(value)}
        with ExitStack() as stack:
            for cls in targets:
                for name in ("__init__", "__post_init__", "from_dict", "to_dict", "resolve"):
                    if hasattr(cls, name):
                        stack.enter_context(patch.object(cls, name, forbidden))
            from biocompiler.synthesis.selection import SyntheticAlternative, SyntheticSelectionResult
            for cls, names in ((SyntheticAlternative, ("gate_count", "status")),
                    (SyntheticSelectionResult, ("selected_strategy", "candidate", "outcome", "checked_candidates", "rejected_candidates"))):
                for name in names:
                    stack.enter_context(patch.object(cls, name, property(forbidden)))
            for kind, expected, value in self.examples:
                self.assertEqual(plain(self.decode(kind, value)), plain(expected))

    def test_parsed_artifact_roots_and_descendants_are_fresh(self):
        for kind, _, value in self.examples:
            first, second = self.decode(kind, value), self.decode(kind, value)
            self.assertIsNot(first, second)
            if kind == "candidate":
                self.assertIsNot(first.generator_config, second.generator_config)
                self.assertIsNot(first.mechanism.nodes[0].output, second.mechanism.nodes[0].output)
            elif kind == "assembly":
                self.assertIsNot(first.registry, second.registry)
                self.assertIsNot(first.composition, second.composition)
                self.assertIsNot(first.composition.target, second.composition.target)
                self.assertIsNot(first.composition.instances[0].component, first.composition.registry_lock.components[0])

    def test_exact_historical_parser_tuple_recipe_and_manager_record_identity(self):
        for original_build in self.builds:
            record = original_build.manager.get("mechanism")
            value = original_build.candidate.to_dict()
            candidate = parsed_candidate(value, record.payload)
            self.assertEqual(build_shape(candidate), build_shape(original_build.candidate))
            for index, node in enumerate(candidate.mechanism.nodes):
                self.assertIs(node.inputs, record.payload["mechanism"]["nodes"][index]["inputs"])
                self.assertIs(node.requirement_ids, record.payload["mechanism"]["nodes"][index]["requirement_ids"])
                self.assertIs(original_build.candidate.mechanism.nodes[index].inputs, node.inputs)
            self.assertIs(candidate.mechanism.outputs, record.payload["mechanism"]["outputs"])
            self.assertIs(candidate.mechanism.required_capabilities, record.payload["mechanism"]["required_capabilities"])
            self.assertIsNot(candidate, original_build.candidate)
            self.assertIsNot(candidate.generator_config, original_build.candidate.generator_config)
            bad = deepcopy(value)
            bad["request_fingerprint"] = "0" * 64
            with self.assertRaisesRegex(CoreProtocolError, "historical parser source"):
                parsed_candidate(bad, record.payload)
            if hasattr(original_build, "assembly"):
                assembly = self.decode("assembly", original_build.assembly.to_dict())
                view = component_build(candidate, assembly, original_build.link_result, original_build.result,
                    original_build.manager, original_build.behavior_result, original_build.selection_result)
                self.assertIsNot(view.assembly.composition.target, original_build.manager.target)
            else:
                view = synthetic_build(candidate, original_build.result, original_build.manager, original_build.selection_result)
            self.assertIs(view.manager, original_build.manager)
            self.assertIs(view.result, original_build.result)
            self.assertIs(view.result.artifact, original_build.result.artifact)

    def test_missing_extra_schema_and_scalar_kinds_fail_closed(self):
        for kind, _, document in self.examples:
            for mutation in (lambda x: x.update(extra=None), lambda x: x.pop("schema_version"),
                    lambda x: x.update(schema_version="forged.v1")):
                value = deepcopy(document)
                mutation(value)
                with self.assertRaises(CoreProtocolError):
                    self.decode(kind, value)
        report = deepcopy(next(value for kind, _, value in self.examples if kind == "check_result"))
        report["coverage"][0]["activation_deadlines_checked"] = True
        with self.assertRaises(CoreProtocolError):
            BuildViews().check_result(report)
        report["coverage"][0]["activation_deadlines_checked"] = 1
        report["outcome"] = "accepted"
        with self.assertRaises(CoreProtocolError):
            BuildViews().check_result(report)


class BuildEnvelopeFixture:
    """Encode actual Python source origins, never infer identity from contents."""
    def __init__(self, objects):
        self.objects = objects
        self.request = objects['authority_objects']['request']
        self.callbacks = CallbackObjects()
        self.tokens = []
        self.hosts = [self.request.target, objects['requested_config']]
        self.hosts.extend(value for _, value in original.source_origins(self.request))
        self.providers = ProviderViewStore(self.callbacks.resolve)
        self.store = BuildViewStore(self.providers)

    def native(self, value, document):
        index = next((index for index, previous in enumerate(self.tokens) if previous is value), None)
        if index is None:
            index = len(self.tokens)
            self.tokens.append(value)
        return {'kind': 'native', 'identity': 'fixture/' + str(index), 'tree': _ordered(document)}

    def binding(self, value, document):
        if any(value is previous for previous in self.hosts):
            return {'kind': 'host', 'object': self.callbacks.retain(value)}
        return self.native(value, document)

    def aliases(self, root, document, prefix):
        aliases = []
        def visit(value, raw, path):
            cls = type(value)
            if cls in (dict, MappingProxyType):
                for key, child in value.items():
                    visit(child, raw[key], [*path, key])
            elif cls in (tuple, list):
                if type(raw) is list:
                    for index, child in enumerate(value):
                        visit(child, raw[index], [*path, index])
            elif is_dataclass(value):
                if cls in ALIAS_CLASSES:
                    aliases.append({'kind': cls.__module__ + '.' + cls.__qualname__,
                        'paths': [path], 'binding': self.binding(value, raw)})
                for field in dataclass_fields(value):
                    if field.name in raw:
                        visit(object.__getattribute__(value, field.name), raw[field.name], [*path, field.name])
        visit(root, document, prefix)
        return aliases

    def provider(self, name, proposal):
        role = {'lower': 'intent_to_behavior', 'generate': 'behavior_to_synthetic',
            'components': 'synthetic_to_components'}[name] + '.producer'
        value = {'output': proposal.output.to_dict(), 'obligations': [],
            'source_links': [dict(vars(link)) for link in proposal.source_links],
            'observation_map': deepcopy(proposal.observation_map), 'search_status': proposal.search_status}
        bindings = {}
        if name == 'generate':
            bindings = {'generator_config': self.binding(proposal.output.generator_config, value['output']['generator_config']),
                'required_capabilities': {'kind': 'host', 'object': self.callbacks.retain(proposal.output.mechanism.required_capabilities)}}
        elif name == 'components':
            bindings = {name: self.binding(getattr(proposal.output, name), value['output'][name]) for name in ('registry', 'composition')}
            bindings['composition_target'] = {'kind': 'host', 'object': self.callbacks.retain(self.request.target)}
        return role, {'kind': 'proposal', 'value': value, 'view': {'role': role, 'tree': _ordered(value),
            'bindings': bindings, 'aliases': self.aliases(proposal.output, value['output'], ['output'])}}

    def envelope(self, kind):
        build = self.objects['synthetic' if kind == 'synthetic' else 'component']
        artifact_names = ['candidate', 'selection_result'] + (['assembly', 'link_result', 'behavior_result'] if kind == 'components' else [])
        artifacts = {}
        for name in artifact_names:
            artifact = getattr(build, name)
            document = None if artifact is None else artifact.to_dict()
            artifacts[name] = {'value': document, 'binding': None if artifact is None else self.native(artifact, document)}
        selection = build.selection_result
        view = {'selection_config': None, 'alternative_configs': [], 'required_capabilities': None, 'aliases': []}
        if selection is not None:
            value = artifacts['selection_result']['value']
            view['selection_config'] = self.binding(selection.config, value['config'])
            view['alternative_configs'] = [None if alternative.candidate is None else
                self.binding(alternative.candidate.generator_config, raw['candidate']['generator_config'])
                for alternative, raw in zip(selection.alternatives, value['alternatives'])]
            if any(item.candidate is not None for item in selection.alternatives):
                view['required_capabilities'] = {'kind': 'host', 'object': self.callbacks.retain(
                    origin_reference(self.request, 'syntheticCapabilities', []))}
            view['aliases'] = self.aliases(selection, value, ['selection_result'])
        from biocompiler.semantics.types import TypeSpec
        for index, node in enumerate(build.candidate.mechanism.nodes):
            view['aliases'].append({'kind': TypeSpec.__module__ + '.' + TypeSpec.__qualname__,
                'paths': [['candidate', 'mechanism', 'nodes', index, 'output', 'dtype']],
                'binding': self.native(node.output.dtype, artifacts['candidate']['value']['mechanism']['nodes'][index]['output']['dtype'])})
        return {'kind': kind, 'identity': 'build/' + kind, 'result': {'fixture_result': kind},
            'artifacts': artifacts, 'sources': {'candidate': {'fixture_record': 'mechanism'}}, 'view': view}

    def decode(self, kind, envelope=None):
        return self.store.decode(envelope or self.envelope(kind), kind=kind, manager=self.objects['synthetic'].manager,
            result=lambda raw: self.objects['synthetic' if raw['fixture_result'] == 'synthetic' else 'component'].result,
            record=lambda raw: dict(self.objects['component_records'])[raw['fixture_record']],
            requested_config=self.objects['requested_config'])


class BuildStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.retained = []
        original_builds.capture(retain=cls.retained)

    def test_complete_six_authority_graph_including_every_container_and_source_origin(self):
        self.assertEqual(len(self.retained), 6)
        for objects in self.retained:
            fixture = BuildEnvelopeFixture(objects)
            actual = dict(objects)
            actual['producer_returns'] = []
            # Decode the historical build before invoking provider views, which
            # independently checks selected-config token reuse in this order.
            actual['synthetic'] = fixture.decode('synthetic')
            actual['component'] = fixture.decode('components')
            for name, proposal in objects['producer_returns']:
                role, envelope = fixture.provider(name, proposal)
                value = fixture.providers.decode(envelope, role=role, target=fixture.request.target,
                    target_document=fixture.request.target.to_dict(), requested_config=objects['requested_config'],
                    input_payload=dict(objects['component_records'])['request'].payload if name == 'lower' else None)
                actual['producer_returns'].append((name, value))
                if name == 'generate':
                    actual['selected_config'] = value.output.generator_config
            before = original_builds.observe_case('control', objects)
            after = original_builds.observe_case('control', actual)
            if after != before:
                paired, reverse = {}, {}
                def graph_diff(left, right, path=()):
                    if type(left) is dict and set(left) == {'ref'} and type(right) is dict and set(right) == {'ref'}:
                        a, b = left['ref'], right['ref']
                        if b in paired:
                            return None if paired[b] == a else (path, 'alias split', paired[b], a, b)
                        if a in reverse:
                            return path, 'alias merged', reverse[a], b
                        paired[b], reverse[a] = a, b
                        return graph_diff(after['nodes'][int(a.split('/')[1])], before['nodes'][int(b.split('/')[1])], path)
                    if type(left) is dict and type(right) is dict and left.keys() == right.keys():
                        for key in left:
                            found = graph_diff(left[key], right[key], (*path, key))
                            if found is not None:
                                return found
                        return None
                    if type(left) is list and type(right) is list and len(left) == len(right):
                        for index, (a, b) in enumerate(zip(left, right)):
                            found = graph_diff(a, b, (*path, index))
                            if found is not None:
                                return found
                        return None
                    return None if left == right else (path, repr(left)[:120], repr(right)[:120])
                found = graph_diff(after['roots'], before['roots'])
                if found is not None:
                    self.fail(str(found))
                def difference(left, right, path=()):
                    if type(left) is not type(right):
                        return path, type(left).__name__, type(right).__name__
                    if type(left) is dict and left.keys() == right.keys():
                        return next((difference(left[key], right[key], (*path, key))
                            for key in left if left[key] != right[key]), None)
                    if type(left) is list and len(left) == len(right):
                        return next((difference(a, b, (*path, index)) for index, (a, b)
                            in enumerate(zip(left, right)) if a != b), None)
                    return path, repr(left)[:200], repr(right)[:200]
                self.fail(str(difference(after, before)))
            self.assertIs(actual['synthetic'].candidate, actual['component'].candidate)
            self.assertIs(actual['component'], fixture.decode('components'))
            self.assertIs(actual['component'].result, objects['component'].result)

    def test_rebound_root_nested_alias_or_historical_source_never_hides_in_cache(self):
        objects = self.retained[-1]
        fixture = BuildEnvelopeFixture(objects)
        fixture.decode('synthetic')
        raw = fixture.envelope('components')
        # A different exact alias token with identical ordered value must not
        # disappear beneath an already cached selection root.
        mutant = deepcopy(raw)
        binding = mutant['view']['alternative_configs'][0]
        binding['identity'] += '/forged'
        with self.assertRaisesRegex(CoreProtocolError, 'descendant identity'):
            fixture.decode('components', mutant)
        fixture = BuildEnvelopeFixture(objects)
        fixture.decode('synthetic')
        raw = fixture.envelope('components')
        raw['artifacts']['candidate']['binding']['identity'] = raw['artifacts']['selection_result']['binding']['identity']
        with self.assertRaises(CoreProtocolError):
            fixture.decode('components', raw)
        fixture = BuildEnvelopeFixture(objects)
        raw = fixture.envelope('synthetic')
        raw['artifacts']['candidate']['value']['request_fingerprint'] = '0' * 64
        raw['artifacts']['candidate']['binding']['tree'] = _ordered(raw['artifacts']['candidate']['value'])
        with self.assertRaisesRegex(CoreProtocolError, 'historical parser source'):
            fixture.decode('synthetic', raw)

    def test_capability_origin_and_metadata_census_are_closed(self):
        fixture = BuildEnvelopeFixture(self.retained[-1])
        raw = fixture.envelope('synthetic')
        equal_copy = tuple(['synthetic_signal_graph'])
        raw['view']['required_capabilities'] = {'kind': 'host', 'object': fixture.callbacks.retain(equal_copy)}
        with self.assertRaisesRegex(CoreProtocolError, 'actual source constant'):
            fixture.decode('synthetic', raw)
        for mutate in (lambda x: x['view'].update(extra=None),
                lambda x: x['view']['alternative_configs'].pop(),
                lambda x: x['sources'].update(extra=None),
                lambda x: x['artifacts'].update(extra=None)):
            fixture = BuildEnvelopeFixture(self.retained[-1])
            raw = fixture.envelope('synthetic')
            mutate(raw)
            with self.assertRaises(CoreProtocolError):
                fixture.decode('synthetic', raw)
        fixture = BuildEnvelopeFixture(self.retained[0])
        fixture.store.max_retained_bytes = 1
        with self.assertRaisesRegex(CoreProtocolError, 'retention limit'):
            fixture.decode('synthetic')

    def test_candidate_type_origin_census_path_class_and_equal_value_identity_are_closed(self):
        def removed(value):
            value['view']['aliases'].pop()
        def duplicate(value):
            value['view']['aliases'].append(deepcopy(value['view']['aliases'][-1]))
        def wrong_kind(value):
            value['view']['aliases'][-1]['kind'] = 'biocompiler.semantics.realization.Observable'
        def wrong_node(value):
            value['view']['aliases'][-1]['paths'][0][3] = 1000000
        def merged(value):
            aliases = value['view']['aliases']
            aliases[-1]['binding'] = deepcopy(aliases[-2]['binding'])
        for mutate in (removed, duplicate, wrong_kind, wrong_node, merged):
            fixture = BuildEnvelopeFixture(self.retained[0])
            raw = fixture.envelope('synthetic')
            mutate(raw)
            with self.assertRaises(CoreProtocolError):
                fixture.decode('synthetic', raw)
        fixture = BuildEnvelopeFixture(self.retained[0])
        fixture.decode('synthetic')
        raw = fixture.envelope('components')
        # Replace one declared parsed node token by a new equal-valued token:
        # the already returned candidate must expose the declared object.
        raw['view']['aliases'][0]['binding']['identity'] += '/equal-copy'
        with self.assertRaisesRegex(CoreProtocolError, 'returned identity'):
            fixture.decode('components', raw)


if __name__ == "__main__":
    unittest.main()
