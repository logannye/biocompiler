"""Closed, source-bound views for the reference pipeline callbacks and builds.

Native code owns translation and acceptance.  This module only reconstructs
public records and the finite identity recipes of the original reference
providers.  Equal contents never establish a shared origin.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
from types import MappingProxyType
from typing import TypeAlias, TypeVar, cast

from biocompiler.compiler.construct import ConstructBuild
from biocompiler.compiler.molecular import MolecularBuild
from biocompiler.compiler.passes import PassResult
from biocompiler.compiler.pipeline import CheckDecision, PassManager, PipelineResult, StageRecord
from biocompiler.core_client import JsonValue
from biocompiler.core_pipeline_build_views import BUILD_FIELDS
from biocompiler.core_pipeline_provider_views import (
    ViewPath, allocate, array, checked_ordered, fields, frozen_mapping, mapping,
    number, require, text,
)
from biocompiler.core_pipeline_session import decode_document, encode_document
from biocompiler.core_reference_views import ReferenceViews
from biocompiler.semantics.coordinates import SequenceRange
from biocompiler.registry.references import ReferenceRecord, ReferenceManifest
from biocompiler.registry.reference_components import ReferenceSelection
from biocompiler.ir.construct import (
    ConstructReference, ConstructMolecule, ComponentPlacement,
    ConstructFeature, ConstructJunction, RegulatoryRelationship,
    ConstructDependency, LayoutEvidencePolicy, ConstructRequest, ConstructCandidate,
)
from biocompiler.ir.molecular import (
    FeatureStatus, TranslationPolicy, EncodingPolicy, EncodingEvidencePolicy,
    EncodingChange, MolecularRecord, MolecularArtifact,
)
from biocompiler.verification.construct import ConstructDiagnostic, ConstructResult
from biocompiler.verification.molecular import MolecularDiagnostic, MolecularCheck, MolecularResult
from biocompiler.ir.composition import CompositionRequest
from biocompiler.semantics.context import PayloadFormat
from biocompiler.verification.evidence import CheckOutcome, EvidenceKind

T = TypeVar('T')
ReferenceOutput: TypeAlias = ConstructCandidate | MolecularArtifact
ReferenceBuild: TypeAlias = ConstructBuild | MolecularBuild

REFERENCE_PROVIDER_ROLES = frozenset((
    'reference_components.authority', 'reference_components.linkage',
    'components_to_construct.producer', 'components_to_construct.layout',
    'construct_to_molecular.producer', 'construct_to_molecular.sequence',
    'construct_to_molecular.composition',
))
_PRODUCERS = frozenset(('components_to_construct.producer', 'construct_to_molecular.producer'))
_POLICY_DEFAULTS = (vars(MolecularRecord)['translation_policy'],
                    vars(MolecularArtifact)['encoding_policy'],
                    vars(MolecularArtifact)['evidence_policy'])

# Literal source-reviewed layouts. Neither the wire nor a host subclass selects
# a class, attribute descriptor, constructor or serializer.
REFERENCE_FIELDS: dict[type[object], tuple[str, ...]] = {
    **BUILD_FIELDS,
    SequenceRange: ('start', 'end'),
    ReferenceRecord: ('reference_id', 'variant_id', 'version', 'alphabet', 'artifact_class', 'orientation', 'source_id', 'source_locator', 'raw_sequence_text', 'raw_text_sha256', 'sequence', 'sequence_sha256', 'length', 'normalization', 'linked_reference_ids', 'completeness', 'unknown_features', 'evidence_relationships'),
    ReferenceManifest: ('reference_set_id', 'version', 'sources', 'records', 'translation', 'reviews', 'status', 'unresolved_discrepancies', 'redistribution', 'schema_version'),
    ReferenceSelection: ('manifest', 'reference'),
    ConstructReference: ('instance_id', 'selection'),
    ConstructMolecule: ('id', 'alphabet', 'artifact_class', 'length', 'component_order', 'topology', 'completeness', 'unknown_features', 'compartment'),
    ComponentPlacement: ('instance_id', 'molecule_id', 'component', 'reference', 'source_range', 'molecule_range', 'orientation', 'reading_frame', 'requirement_ids', 'source'),
    ConstructFeature: ('id', 'molecule_id', 'kind', 'range', 'source_reference', 'source_range', 'source_locator', 'provenance', 'orientation'),
    ConstructJunction: ('id', 'molecule_id', 'left_instance', 'right_instance', 'kind', 'range', 'choice', 'provenance'),
    RegulatoryRelationship: ('id', 'kind', 'regulator_instance', 'target_instance', 'provenance', 'assumptions'),
    ConstructDependency: ('id', 'consumer_molecule', 'provider_molecule', 'kind', 'assumption', 'requirement_ids'),
    LayoutEvidencePolicy: ('semantic_properties', 'invalidated_analyses'),
    ConstructRequest: ('composition', 'references', 'molecules', 'placements', 'features', 'junctions', 'regulatory_relations', 'dependencies', 'assumptions', 'source_request_fingerprint', 'evidence_policy'),
    ConstructCandidate: ('request_fingerprint', 'composition_fingerprint', 'registry_lock', 'molecules', 'placements', 'features', 'junctions', 'regulatory_relations', 'dependencies', 'assumptions', 'evidence_policy'),
    FeatureStatus: ('feature', 'status', 'scope', 'reason', 'value'),
    TranslationPolicy: ('genetic_code', 'start_codon', 'stop_convention', 'protein_length_includes_stop'),
    EncodingPolicy: ('mode', 'optimization', 'transformations'),
    EncodingEvidencePolicy: ('semantic_properties', 'invalidated_analyses'),
    EncodingChange: ('id', 'record_id', 'before_sequence_sha256', 'after_sequence_sha256', 'changed_properties', 'reason', 'preservation_claims'),
    MolecularRecord: ('id', 'instance_id', 'molecule_id', 'alphabet', 'artifact_class', 'sequence', 'sequence_sha256', 'component', 'reference_selection', 'source_range', 'molecule_range', 'features', 'feature_statuses', 'orientation', 'reading_frame', 'translation_policy', 'completeness', 'unknown_features', 'evidence_relationships', 'requirement_ids', 'source'),
    MolecularArtifact: ('request_fingerprint', 'construct_fingerprint', 'layout_fingerprint', 'registry_lock', 'profile', 'records', 'encoding_policy', 'evidence_policy', 'changes', 'source_request_fingerprint', 'artifact_scope'),
    ConstructDiagnostic: ('status', 'code', 'message', 'instance_id', 'molecule_id', 'requirement_ids', 'source'),
    ConstructResult: ('outcome', 'dependencies', 'checked_requirement_ids', 'diagnostics', 'claim_scope'),
    MolecularDiagnostic: ('status', 'code', 'message', 'record_id', 'instance_id', 'molecule_id', 'requirement_ids', 'source'),
    MolecularCheck: ('record_id', 'check', 'outcome', 'expected_fingerprint', 'actual_fingerprint', 'message'),
    MolecularResult: ('outcome', 'dependencies', 'checked_requirement_ids', 'diagnostics', 'checks', 'claim_scope'),
    CheckDecision: ('outcome', 'detail', 'evidence'),
}


def _members(value: object, kind: type[object]) -> dict[str, object]:
    require(type(value) is kind, 'Reference origin requires its exact regular class')
    names = REFERENCE_FIELDS.get(kind)
    require(names is not None, 'Unknown reference origin class')
    values = cast(dict[str, object], object.__getattribute__(value, '__dict__'))
    require(type(values) is dict and tuple(values) == names, 'Reference origin fields or order differ')
    return values


def reference_shape(value: object, *, max_nodes: int = 1_000_000) -> JsonValue:
    """Observe closed stored fields, including scalar kinds and container order.

    This is a bounded structural observation; no properties, user equality,
    hashes, serializers or constructors run. Cycles fail at the depth boundary.
    """
    remaining = max_nodes

    def visit(item: object, depth: int) -> JsonValue:
        nonlocal remaining
        require(remaining > 0 and depth <= 128, 'Reference shape resource limit exceeded')
        remaining -= 1
        kind = type(item)
        if item is None or kind in (bool, int, float, str):
            if kind is float:
                number(cast(float, item))
            return [kind.__name__, cast(JsonValue, item)]
        if kind in (CheckOutcome, EvidenceKind, PayloadFormat):
            return [kind.__module__ + '.' + kind.__qualname__,
                    cast(str, object.__getattribute__(item, '_value_'))]
        if kind in (tuple, list):
            return [kind.__name__, [visit(child, depth + 1)
                for child in cast(tuple[object, ...] | list[object], item)]]
        if kind in (dict, MappingProxyType):
            members = cast(Mapping[object, object], item)
            require(all(type(key) is str for key in members), 'Reference mapping key differs')
            return [kind.__name__, [[cast(str, key), visit(child, depth + 1)]
                for key, child in members.items()]]
        values = _members(item, kind)
        return [kind.__module__ + '.' + kind.__qualname__,
                [[name, visit(child, depth + 1)] for name, child in values.items()]]

    return visit(value, 0)


def _same(left: object, right: object) -> None:
    require(encode_document(reference_shape(left)) == encode_document(reference_shape(right)),
            'Reference origin fields differ from the native view')


def _one(value: object) -> object:
    require(type(value) is tuple, 'Reference origin requires its exact tuple')
    items = cast(tuple[object, ...], value)
    require(len(items) == 1, 'Reference producer origin requires one source member')
    return items[0]


@dataclass(frozen=True, eq=False)
class ReferenceOrigins:
    """Per-invocation host roots, created at the actual source callback boundary."""
    parsed: ConstructRequest | ConstructCandidate
    source_bytes: bytes
    parsed_bytes: bytes
    request: ConstructRequest | None = None
    translation_policy: TranslationPolicy | None = None
    encoding_policy: EncodingPolicy | None = None
    evidence_policy: EncodingEvidencePolicy | None = None

    @classmethod
    def construct(cls, parsed: ConstructRequest, source_document: JsonValue, *,
                  parsed_document: JsonValue = None) -> ReferenceOrigins:
        complete = source_document if parsed_document is None else parsed_document
        _same(parsed, ReferenceViews().construct_request(complete))
        return cls(parsed, bytes(encode_document(source_document)), cls._document(complete))

    @classmethod
    def molecular(cls, parsed: ConstructCandidate, source_document: JsonValue, *,
                  request: ConstructRequest, translation_policy: TranslationPolicy,
                  encoding_policy: EncodingPolicy, evidence_policy: EncodingEvidencePolicy,
                  parsed_document: JsonValue = None) -> ReferenceOrigins:
        complete = source_document if parsed_document is None else parsed_document
        _same(parsed, ReferenceViews().construct_candidate(complete))
        _members(request, ConstructRequest)
        require(translation_policy is _POLICY_DEFAULTS[0] is vars(MolecularRecord)['translation_policy']
            and encoding_policy is _POLICY_DEFAULTS[1] is vars(MolecularArtifact)['encoding_policy']
            and evidence_policy is _POLICY_DEFAULTS[2] is vars(MolecularArtifact)['evidence_policy'],
            'Reference policy origin is not its actual class default')
        return cls(parsed, bytes(encode_document(source_document)), cls._document(complete), request,
                   translation_policy, encoding_policy, evidence_policy)

    @staticmethod
    def _document(value: JsonValue) -> bytes:
        # The parsed native representation may fill optional source fields.
        # Retain it separately from the actual input, including map order.
        encode_document(value)
        return json.dumps(value, ensure_ascii=False, allow_nan=False,
                          separators=(',', ':')).encode('utf-8')


class _OriginFactory:
    def __init__(self, role: str, origins: ReferenceOrigins):
        self.role, self.origins = role, origins
        self.applied: set[str] = set()

    @staticmethod
    def replace(values: dict[str, object], name: str, source: object) -> None:
        _same(values[name], source)
        values[name] = source

    def __call__(self, kind: type[T], path: ViewPath, document: JsonValue,
                 fields: Mapping[str, object], /) -> T:
        values = dict(fields)
        origin = self.origins
        if self.role == 'components_to_construct.producer' and path == ('output',):
            require(kind is ConstructCandidate, 'Construct producer root class differs')
            source = _members(origin.parsed, ConstructRequest)
            composition = _members(source['composition'], CompositionRequest)
            self.replace(values, 'registry_lock', composition['registry_lock'])
            for name in ('molecules', 'placements', 'features', 'junctions',
                         'regulatory_relations', 'dependencies', 'evidence_policy'):
                self.replace(values, name, source[name])
            self.applied.add('construct')
        elif self.role == 'construct_to_molecular.producer':
            source = _members(origin.parsed, ConstructCandidate)
            if path == ('output', 'records', 0):
                require(kind is MolecularRecord, 'Molecular producer record class differs')
                placement = _members(_one(source['placements']), ComponentPlacement)
                request = _members(origin.request, ConstructRequest)
                reference = _members(_one(request['references']), ConstructReference)
                for name in ('component', 'source_range', 'molecule_range', 'source'):
                    self.replace(values, name, placement[name])
                self.replace(values, 'reference_selection', reference['selection'])
                self.replace(values, 'features', source['features'])
                self.replace(values, 'translation_policy', origin.translation_policy)
                self.applied.add('record')
            elif path == ('output',):
                require(kind is MolecularArtifact, 'Molecular producer root class differs')
                _one(values['records'])
                self.replace(values, 'registry_lock', source['registry_lock'])
                self.replace(values, 'encoding_policy', origin.encoding_policy)
                self.replace(values, 'evidence_policy', origin.evidence_policy)
                self.applied.add('molecular')
        return allocate(kind, values)


class ReferenceProviderViews:
    """Decode only the result of an already-bound native provider invocation."""
    def __init__(self, resolve: Callable[[JsonValue], object]):
        self.resolve = resolve

    def decode(self, envelope: JsonValue, *, role: str,
               origins: ReferenceOrigins | None = None, input_document: JsonValue = None,
               host_result: object = None) -> object:
        require(role in REFERENCE_PROVIDER_ROLES, 'Unknown reference provider role')
        raw = mapping(envelope)
        if raw.get('kind') == 'host':
            fields(envelope, 'kind object')
            require(role in _PRODUCERS and host_result is not None,
                    'Reference host result lacks its paired proposal')
            result = self.resolve(raw['object'])
            require(result is host_result, 'Reference host result differs from its paired proposal')
            return result
        fields(envelope, 'kind value view')
        view = fields(raw['view'], 'role tree origins')
        require(view['role'] == role, 'Reference provider view role differs')
        value = checked_ordered(view['tree'], raw['value'])
        refs = mapping(view['origins'])
        if role not in _PRODUCERS:
            require(raw['kind'] == 'decision' and not refs, 'Reference decision cannot import origins')
            decision = fields(value, 'outcome detail evidence')
            outcomes = {item.value: item for item in CheckOutcome}
            outcome = text(decision['outcome'])
            require(outcome in outcomes, 'Unknown reference decision outcome')
            return allocate(CheckDecision, {'outcome': outcomes[outcome],
                'detail': text(decision['detail']), 'evidence': frozen_mapping(decision['evidence'])})
        require(raw['kind'] == 'proposal' and type(origins) is ReferenceOrigins,
                'Reference proposal lacks its actual invocation origins')
        assert origins is not None
        require(origins.source_bytes == bytes(encode_document(input_document)),
                'Reference parsed origin belongs to a different provider input')
        complete = decode_document(origins.parsed_bytes)
        parsed = (ReferenceViews().construct_request(complete)
                  if role == 'components_to_construct.producer'
                  else ReferenceViews().construct_candidate(complete))
        _same(origins.parsed, parsed)
        expected: dict[str, object] = {'parsed': origins.parsed}
        if role == 'construct_to_molecular.producer':
            expected.update(request=origins.request, translation_policy=origins.translation_policy,
                encoding_policy=origins.encoding_policy, evidence_policy=origins.evidence_policy)
        require(set(refs) == set(expected), 'Reference provider origin census differs')
        for name, original in expected.items():
            require(original is not None and self.resolve(refs[name]) is original,
                    'Reference provider origin differs from its actual callback object')
        factory = _OriginFactory(role, origins)
        decoder = ReferenceViews(factory)
        proposal = fields(value, 'output obligations source_links observation_map search_status')
        require(proposal['obligations'] == [] and not mapping(proposal['observation_map'])
                and proposal['search_status'] == 'candidate', 'Reference default proposal fields differ')
        output: ReferenceOutput
        if role == 'components_to_construct.producer':
            output = decoder.construct_candidate(proposal['output'], ('output',))
            require(factory.applied == {'construct'}, 'Incomplete Construct origin recipe')
        else:
            output = decoder.molecular_artifact(proposal['output'], ('output',))
            require(factory.applied == {'record', 'molecular'}, 'Incomplete Molecular origin recipe')
        return allocate(PassResult, {'output': output, 'obligations': (),
            'source_links': decoder.sequence(proposal['source_links'], decoder.source_link, ('source_links',)),
            'observation_map': {}, 'search_status': 'candidate'})


def _json(value: object, depth: int = 0) -> JsonValue:
    """Copy the already-frozen record representation without a serializer."""
    kind = type(value)
    require(depth <= 128, 'Reference record payload nesting limit exceeded')
    if value is None or kind in (bool, int, float, str):
        if kind is float:
            number(cast(float, value))
        return cast(JsonValue, value)
    if kind in (tuple, list):
        return [_json(item, depth + 1) for item in cast(tuple[object, ...] | list[object], value)]
    require(kind in (dict, MappingProxyType), 'Reference record payload is not closed JSON')
    members = cast(Mapping[object, object], value)
    require(all(type(key) is str for key in members), 'Reference record payload key differs')
    return {cast(str, key): _json(item, depth + 1) for key, item in members.items()}


@dataclass(frozen=True)
class _Root:
    identity: str
    signature: bytes
    shape: bytes
    value: object
    objects: tuple[object, ...]


@dataclass(frozen=True)
class _Build:
    signature: bytes
    value: ReferenceBuild
    manager: PassManager
    result: PipelineResult
    upstream: ConstructBuild | None
    roots: tuple[str, ...]
    construct_origin: tuple[JsonValue, object] | None


class ReferenceBuildStore:
    """Bounded historical views keyed by actual native origins, never hashes."""
    def __init__(self, *, max_objects: int = 100_000, max_retained_bytes: int = 134_217_728,
                 identity_taken: Callable[[str], bool] | None = None,
                 reserve: Callable[[int], None] | None = None):
        require(type(max_objects) is int and max_objects > 0
                and type(max_retained_bytes) is int and max_retained_bytes > 0,
                'Reference view limits must be positive integers')
        self.max_objects, self.max_retained_bytes = max_objects, max_retained_bytes
        self.identity_taken = identity_taken
        self.reserve = reserve
        self.retained_bytes = 0
        self.retained_nodes = 0
        self.roots: dict[str, _Root] = {}
        self.builds: dict[str, _Build] = {}

    def _root(self, item: JsonValue, decode: Callable[[JsonValue], T], *, expected: object = None) -> T:
        raw = fields(item, 'value binding')
        binding = fields(raw['binding'], 'kind identity tree')
        require(binding['kind'] == 'native', 'Reference build requires a native artifact origin')
        identity = text(binding['identity'])
        require(bool(identity) and identity not in self.builds
                and (self.identity_taken is None or not self.identity_taken(identity)),
                'Reference build artifact origin is empty or foreign')
        ordered = checked_ordered(binding['tree'], raw['value'])
        signature = bytes(encode_document(binding['tree']))
        previous = self.roots.get(identity)
        if previous is not None:
            require(expected is not None and previous.value is expected
                    and previous.signature == signature, 'Reference build artifact origin was reused or rebound')
            self._unchanged(previous)
            return cast(T, previous.value)
        require(expected is None, 'Reference upstream candidate lacks its actual earlier build origin')
        result = decode(ordered)
        self.roots[identity] = _Root(identity, signature, bytes(encode_document(reference_shape(result))),
                                     result, self._objects(result))
        return result

    @staticmethod
    def _objects(value: object) -> tuple[object, ...]:
        retained: dict[int, object] = {}

        def visit(item: object) -> None:
            kind = type(item)
            if kind in (tuple, list):
                if kind is tuple and not item:
                    return
                children = cast(tuple[object, ...] | list[object], item)
            elif kind in (dict, MappingProxyType):
                children = tuple(cast(Mapping[str, object], item).values())
            elif kind in REFERENCE_FIELDS:
                children = tuple(_members(item, kind).values())
            else:
                return
            if id(item) in retained:
                return
            retained[id(item)] = item
            for child in children:
                visit(child)

        # The preceding shape walk already enforces the same graph's limits.
        visit(value)
        return tuple(retained.values())

    @staticmethod
    def _unchanged(root: _Root) -> None:
        require(root.shape == bytes(encode_document(reference_shape(root.value))),
                'Reference cached artifact fields changed')
        current = ReferenceBuildStore._objects(root.value)
        require(len(current) == len(root.objects) and all(left is right for left, right in zip(current, root.objects)),
                'Reference cached artifact descendant identity changed')

    def decode(self, envelope: JsonValue, *, manager: PassManager, result: PipelineResult,
               result_envelope: JsonValue, upstream: ConstructBuild | None = None,
               construct_origin: tuple[JsonValue, object] | None = None) -> ReferenceBuild:
        raw = fields(envelope, 'build_id kind candidate check_result result construct')
        identity, kind = text(raw['build_id']), text(raw['kind'])
        require(bool(identity) and kind in ('construct', 'molecular'), 'Unknown reference build identity or kind')
        require(encode_document(raw['result']) == encode_document(result_envelope),
                'Reference build result differs from its actual public result reply')
        require(type(result) is PipelineResult, 'Reference build requires its actual public result')
        result_fields = cast(dict[str, object], object.__getattribute__(result, '__dict__'))
        record = result_fields.get('artifact')
        require(type(record) is StageRecord, 'Reference build result lacks its actual historical record')
        record_fields = cast(dict[str, object], object.__getattribute__(record, '__dict__'))
        candidate_envelope = fields(raw['candidate'], 'value binding')
        require(encode_document(candidate_envelope['value']) == encode_document(_json(record_fields.get('payload'))),
                'Reference build candidate differs from its actual historical payload')
        signature = bytes(encode_document(envelope))
        if construct_origin is not None:
            require(kind == 'molecular', 'Only Molecular Build can retain a source-returned Construct root')
            source = fields(raw['construct'], 'value binding')
            binding = fields(source['binding'], 'kind object')
            require(source['value'] is None and binding['kind'] == 'host'
                    and encode_document(binding['object']) == encode_document(construct_origin[0]),
                    'Reference Build changed its actual second candidate read')
        previous = self.builds.get(identity)
        if previous is not None:
            require(previous.signature == signature and previous.manager is manager
                    and previous.result is result and previous.upstream is upstream,
                    'Reference build identity was rebound')
            require((previous.construct_origin is None and construct_origin is None) or
                (previous.construct_origin is not None and construct_origin is not None
                 and previous.construct_origin[1] is construct_origin[1]
                 and encode_document(previous.construct_origin[0]) == encode_document(construct_origin[0])),
                'Reference Build source-returned root was rebound')
            stored = cast(dict[str, object], object.__getattribute__(previous.value, '__dict__'))
            names = ('candidate', 'check_result', 'result', 'manager') if kind == 'construct' else (
                'construct', 'candidate', 'check_result', 'result', 'manager')
            require(tuple(stored) == names and stored['manager'] is manager and stored['result'] is result
                and stored['candidate'] is self.roots[previous.roots[0]].value
                and stored['check_result'] is self.roots[previous.roots[1]].value
                and (kind == 'construct' or
                     (construct_origin is not None and stored['construct'] is construct_origin[1]) or
                     (construct_origin is None and upstream is not None and stored['construct'] is upstream.candidate)),
                'Reference cached build fields changed')
            for root_id in previous.roots:
                self._unchanged(self.roots[root_id])
            return previous.value
        require(identity not in self.roots and (self.identity_taken is None or not self.identity_taken(identity)),
                'Reference build identity collides with another origin')
        root_ids = [text(fields(fields(raw[name], 'value binding')['binding'],
                               'kind identity tree')['identity'])
                    for name in ('candidate', 'check_result')]
        require(identity not in root_ids and len(set(root_ids)) == len(root_ids),
                'Reference build root identities collide')
        # Precharge the complete retained wire tree, including keys. A typed
        # object/container cannot outnumber these nodes in the closed decoders.
        def count(value: JsonValue, depth: int = 0) -> int:
            require(depth <= 128, 'Reference build nesting limit exceeded')
            total = 1
            if type(value) is list:
                for item in value:
                    total += count(item, depth + 1)
            elif type(value) is dict:
                for item in value.values():
                    total += 1 + count(item, depth + 1)
            return total
        nodes = count(envelope)
        charge = len(signature) * 2 + nodes * 256
        require(self.retained_nodes + nodes <= self.max_objects
                and self.retained_bytes + charge <= self.max_retained_bytes,
                'Reference build retention limit exceeded')
        if self.reserve is not None:
            self.reserve(charge)
        self.retained_nodes += nodes
        self.retained_bytes += charge
        decoder = ReferenceViews()
        if kind == 'construct':
            require(raw['construct'] is None and upstream is None, 'Construct build cannot import an upstream candidate')
            candidate = self._root(raw['candidate'], decoder.construct_candidate)
            check = self._root(raw['check_result'], decoder.construct_result)
            value: ReferenceBuild = allocate(ConstructBuild, {'candidate': candidate, 'check_result': check,
                'result': result, 'manager': manager})
        else:
            if construct_origin is None:
                require(type(upstream) is ConstructBuild and upstream.manager is manager,
                        'Molecular build lacks its actual upstream Construct build')
                assert upstream is not None
                construct: object = self._root(raw['construct'], decoder.construct_candidate, expected=upstream.candidate)
            else:
                # The source reads this field after its independent check. It
                # may be unrelated to the first candidate or even a typed record;
                # retaining it does not change the native report or acceptance.
                construct = construct_origin[1]
            artifact = self._root(raw['candidate'], decoder.molecular_artifact)
            molecular_check = self._root(raw['check_result'], decoder.molecular_result)
            value = allocate(MolecularBuild, {'construct': construct, 'candidate': artifact,
                'check_result': molecular_check, 'result': result, 'manager': manager})
        if kind == 'molecular' and construct_origin is None:
            root_ids.append(text(fields(fields(raw['construct'], 'value binding')['binding'],
                                        'kind identity tree')['identity']))
        self.builds[identity] = _Build(signature, value, manager, result, upstream, tuple(root_ids), construct_origin)
        return value
