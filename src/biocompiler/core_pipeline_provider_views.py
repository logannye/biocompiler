"""Closed structural views of native fixed-provider results.

These functions allocate existing public data classes from checked wire fields.
They perform representation checks only. Constructors, semantic parsers, graph
checks, registry resolution and content-based object interning are never used.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Protocol, TypeAlias, TypeVar, cast

from biocompiler.core_client import CoreProtocolError, JsonValue
from biocompiler.core_pipeline_session import encode_document
from biocompiler.artifacts.provenance import SourceLink
from biocompiler.compiler.passes import PassResult
from biocompiler.compiler.pipeline import CheckDecision
from biocompiler.compiler.request import RealizationRequest
from biocompiler.ir.behavior import BehaviorNode, BehaviorProgram
from biocompiler.ir.component_assembly import ComponentAssembly
from biocompiler.ir.component_contracts import (
    ComponentRecord, DependencyRequirement, ParameterProvenance, PinnedIdentity,
    ProvidedCapability, ResourceReservation, SequenceReferenceMetadata, SyntheticOperatorModel,
)
from biocompiler.ir.components import ComponentLock
from biocompiler.ir.composition import (
    CompositionInstance, CompositionRequest, Connection, DependencyBinding,
    LifecycleInterval, Provider, ResourceBinding, ResourcePool,
)
from biocompiler.ir.intent import SourceLocation
from biocompiler.ir.mechanism import MechanismNode, MechanismProgram
from biocompiler.registry.components import ComponentRegistry, RegistryLock
from biocompiler.semantics.component_contracts import OperatingDomain, PortContract, ValueDomain
from biocompiler.semantics.context import HumanTargetContext, TargetContext
from biocompiler.semantics.contracts import BehaviorRequirement
from biocompiler.semantics.realization import (
    BehaviorContract, InputDomain, Observable, OperatingDomain as RequestDomain, ResponseRequirement,
)
from biocompiler.semantics.types import BOOLEAN, DURATION, LEVEL, TypeSpec
from biocompiler.synthesis.synthetic import SyntheticCandidate, SyntheticGeneratorConfig
from biocompiler.verification.realization import InputBinding, ObservationMap, OutputBinding
from biocompiler.verification.evidence import CheckOutcome, EvidenceKind, Obligation

T = TypeVar('T')
Scalar: TypeAlias = None | bool | int | float | str
FrozenJson: TypeAlias = Scalar | tuple['FrozenJson', ...] | Mapping[str, 'FrozenJson']
ViewPath: TypeAlias = tuple[str | int, ...]
ProviderOutput: TypeAlias = BehaviorProgram | SyntheticCandidate | ComponentAssembly

PROVIDER_ROLES = frozenset((
    'intent_to_behavior.producer', 'intent_to_behavior.validator',
    'behavior_to_synthetic.producer', 'behavior_to_synthetic.validator',
    'synthetic_to_components.producer', 'synthetic_to_components.validator',
))


def require(value: bool, message: str) -> None:
    if not value:
        raise CoreProtocolError(message)


def allocate(kind: type[T], fields: Mapping[str, object]) -> T:
    """Called only with a closed class and explicitly decoded declared fields."""
    value = object.__new__(kind)
    for name, item in fields.items():
        object.__setattr__(value, name, item)
    return value


class ObjectFactory(Protocol):
    """Session-owned identity policy; the decoder never guesses shared values."""
    def __call__(self, kind: type[T], path: ViewPath, document: JsonValue,
                 fields: Mapping[str, object], /) -> T: ...


def fresh_object(kind: type[T], path: ViewPath, document: JsonValue,
                 fields: Mapping[str, object]) -> T:
    return allocate(kind, fields)


def text(value: JsonValue) -> str:
    require(type(value) is str, 'Provider field requires a string')
    return cast(str, value)


def integer(value: JsonValue) -> int:
    require(type(value) is int, 'Provider field requires an integer')
    return cast(int, value)


def boolean(value: JsonValue) -> bool:
    require(type(value) is bool, 'Provider field requires a Boolean')
    return cast(bool, value)


def number(value: JsonValue) -> int | float:
    require(type(value) in (int, float), 'Provider field requires a number')
    result = cast(int | float, value)
    require(not isinstance(result, float) or math.isfinite(result), 'Provider number must be finite')
    return result


def array(value: JsonValue) -> list[JsonValue]:
    require(type(value) is list, 'Provider field requires an array')
    return cast(list[JsonValue], value)


def mapping(value: JsonValue) -> dict[str, JsonValue]:
    require(type(value) is dict and all(type(key) is str for key in value), 'Provider field requires an object')
    return cast(dict[str, JsonValue], value)


def fields(value: JsonValue, names: str, schema: str | None = None,
           optional: str = '') -> dict[str, JsonValue]:
    result = mapping(value)
    required, allowed = set(names.split()), set(optional.split())
    if schema is not None:
        required.add('schema_version')
        require(result.get('schema_version') == schema, 'Provider view schema differs')
    require(required <= set(result) <= required | allowed, 'Provider view has missing or unknown fields')
    return result


def strings(value: JsonValue) -> tuple[str, ...]:
    return tuple(text(item) for item in array(value))


def frozen(value: JsonValue) -> FrozenJson:
    if type(value) is dict:
        return MappingProxyType({key: frozen(item) for key, item in mapping(value).items()})
    if type(value) is list:
        return tuple(frozen(item) for item in array(value))
    require(value is None or type(value) in (str, bool, int, float), 'Invalid provider JSON scalar')
    if type(value) is float:
        number(value)
    return cast(Scalar, value)


def frozen_mapping(value: JsonValue) -> Mapping[str, FrozenJson]:
    return MappingProxyType({key: frozen(item) for key, item in mapping(value).items()})


def string_map(value: JsonValue) -> Mapping[str, tuple[str, ...]]:
    return MappingProxyType({key: strings(item) for key, item in mapping(value).items()})


def optional(value: JsonValue, decode: Callable[[JsonValue], T]) -> T | None:
    return None if value is None else decode(value)


def ordered_value(tree: JsonValue) -> JsonValue:
    """Decode the closed ordered tree to fresh mutable JSON containers."""
    pair = array(tree)
    require(len(pair) == 2 and type(pair[0]) is str, 'Malformed provider ordered tree')
    kind, value = pair
    if kind == 'scalar':
        require(value is None or type(value) in (str, bool, int, float), 'Malformed provider ordered scalar')
        if type(value) is float:
            number(value)
        return value
    if kind == 'array':
        return [ordered_value(item) for item in array(value)]
    require(kind == 'object', 'Unknown provider ordered tree tag')
    result: dict[str, JsonValue] = {}
    for item in array(value):
        entry = array(item)
        require(len(entry) == 2, 'Malformed provider ordered member')
        key = text(entry[0])
        require(key not in result, 'Duplicate provider ordered member')
        result[key] = ordered_value(entry[1])
    return result


def checked_ordered(tree: JsonValue, value: JsonValue) -> JsonValue:
    result = ordered_value(tree)
    require(encode_document(result) == encode_document(value), 'Provider ordered tree differs from canonical value')
    return result


class StructuralViews:
    """Explicit typed schemas; a caller supplies any reviewed identity policy."""
    def __init__(self, factory: ObjectFactory = fresh_object):
        self.factory = factory

    def make(self, cls: type[T], path: ViewPath, document: JsonValue, **values: object) -> T:
        return self.factory(cls, path, document, values)

    def sequence(self, value: JsonValue, decode: Callable[[JsonValue, ViewPath], T], path: ViewPath) -> tuple[T, ...]:
        return tuple(decode(item, (*path, index)) for index, item in enumerate(array(value)))

    def source(self, value: JsonValue, path: ViewPath) -> SourceLocation | None:
        if value is None:
            return None
        d = fields(value, 'file line function')
        return self.make(SourceLocation, path, value, file=text(d['file']), line=integer(d['line']), function=text(d['function']))

    def dtype(self, value: JsonValue, path: ViewPath) -> TypeSpec:
        d = fields(value, 'kind name dimensions arguments')
        return self.make(TypeSpec, path, value, kind=text(d['kind']), name=text(d['name']),
            dimensions=tuple((key, integer(power)) for key, power in mapping(d['dimensions']).items()),
            arguments=self.sequence(d['arguments'], self.dtype, (*path, 'arguments')))

    def requirement(self, value: JsonValue, path: ViewPath) -> BehaviorRequirement:
        d = fields(value, 'id kind source_node_id lineage', optional='source')
        return self.make(BehaviorRequirement, path, value, id=text(d['id']), kind=text(d['kind']),
            source_node_id=text(d['source_node_id']), lineage=strings(d['lineage']),
            source=self.source(d.get('source'), (*path, 'source')))

    def behavior_node(self, value: JsonValue, path: ViewPath) -> BehaviorNode:
        d = fields(value, 'id kind inputs attributes data_type role contact_bound requirement_ids', optional='source')
        return self.make(BehaviorNode, path, value, id=text(d['id']), kind=text(d['kind']), inputs=strings(d['inputs']),
            attributes=frozen_mapping(d['attributes']), data_type=optional(d['data_type'], frozen_mapping),
            role=optional(d['role'], text), source=self.source(d.get('source'), (*path, 'source')),
            contact_bound=boolean(d['contact_bound']), requirement_ids=strings(d['requirement_ids']))

    def behavior(self, value: JsonValue, path: ViewPath = ()) -> BehaviorProgram:
        d = fields(value, 'schema_version name nodes roots source_fingerprint requirements source_links policies parameter_bindings')
        require(d['schema_version'] in ('biocompiler.behavior.v0.1', 'biocompiler.behavior.v0.2'), 'Unknown behavior view schema')
        return self.make(BehaviorProgram, path, value, name=text(d['name']),
            nodes=self.sequence(d['nodes'], self.behavior_node, (*path, 'nodes')), roots=strings(d['roots']),
            source_fingerprint=text(d['source_fingerprint']),
            requirements=self.sequence(d['requirements'], self.requirement, (*path, 'requirements')),
            source_links=string_map(d['source_links']), policies=frozen_mapping(d['policies']),
            parameter_bindings=frozen_mapping(d['parameter_bindings']), schema_version=text(d['schema_version']))

    def observable(self, value: JsonValue, path: ViewPath) -> Observable:
        d = fields(value, 'id dtype role scope compartment', 'biocompiler.observable.v0.1')
        return self.make(Observable, path, value, id=text(d['id']), dtype=self.dtype(d['dtype'], (*path, 'dtype')),
            role=text(d['role']), scope=text(d['scope']), compartment=text(d['compartment']))

    def mechanism_node(self, value: JsonValue, path: ViewPath) -> MechanismNode:
        d = fields(value, 'id kind output inputs attributes requirement_ids')
        return self.make(MechanismNode, path, value, id=text(d['id']), kind=text(d['kind']),
            output=self.observable(d['output'], (*path, 'output')), inputs=strings(d['inputs']),
            attributes=frozen_mapping(d['attributes']), requirement_ids=strings(d['requirement_ids']))

    def mechanism(self, value: JsonValue, path: ViewPath) -> MechanismProgram:
        d = fields(value, 'name nodes outputs required_capabilities', 'biocompiler.mechanism.synthetic.v0.2')
        return self.make(MechanismProgram, path, value, name=text(d['name']),
            nodes=self.sequence(d['nodes'], self.mechanism_node, (*path, 'nodes')), outputs=strings(d['outputs']),
            required_capabilities=strings(d['required_capabilities']), schema_version=text(d['schema_version']))

    def input_binding(self, value: JsonValue, path: ViewPath) -> InputBinding:
        d = fields(value, 'signal_id field mechanism_input_id')
        return self.make(InputBinding, path, value, signal_id=text(d['signal_id']), field=text(d['field']),
            mechanism_input_id=text(d['mechanism_input_id']))

    def output_binding(self, value: JsonValue, path: ViewPath) -> OutputBinding:
        d = fields(value, 'requirement_id mechanism_output_id')
        return self.make(OutputBinding, path, value, requirement_id=text(d['requirement_id']), mechanism_output_id=text(d['mechanism_output_id']))

    def observations(self, value: JsonValue, path: ViewPath) -> ObservationMap:
        d = fields(value, 'inputs outputs', 'biocompiler.observation_map.v0.1')
        return self.make(ObservationMap, path, value, inputs=self.sequence(d['inputs'], self.input_binding, (*path, 'inputs')),
            outputs=self.sequence(d['outputs'], self.output_binding, (*path, 'outputs')))

    def config(self, value: JsonValue, path: ViewPath = ()) -> SyntheticGeneratorConfig:
        d = fields(value, 'profile_version generator_version catalog_fingerprint witness_selection conjunction_strategy',
            'biocompiler.synthetic_generator_config.v0.3')
        return self.make(SyntheticGeneratorConfig, path, value, profile_version=text(d['profile_version']),
            generator_version=text(d['generator_version']), catalog_fingerprint=optional(d['catalog_fingerprint'], text),
            witness_selection=text(d['witness_selection']), conjunction_strategy=text(d['conjunction_strategy']))

    def component_lock(self, value: JsonValue, path: ViewPath) -> ComponentLock:
        d = fields(value, 'node_id component_id version content_fingerprint', 'biocompiler.component_lock.v0.1')
        return self.make(ComponentLock, path, value, node_id=text(d['node_id']), component_id=text(d['component_id']),
            version=text(d['version']), content_fingerprint=text(d['content_fingerprint']))

    def candidate(self, value: JsonValue, path: ViewPath = ()) -> SyntheticCandidate:
        d = fields(value, 'intended_use human_therapeutic_admission request_fingerprint mechanism observation_map source_map behavior_requirement_ids component_locks generator_config',
            'biocompiler.synthetic_candidate.v0.4')
        require(d['intended_use'] == 'software_test' and d['human_therapeutic_admission'] == 'not_admitted', 'Candidate view claim tags differ')
        return self.make(SyntheticCandidate, path, value, request_fingerprint=text(d['request_fingerprint']),
            mechanism=self.mechanism(d['mechanism'], (*path, 'mechanism')),
            observation_map=self.observations(d['observation_map'], (*path, 'observation_map')),
            source_map=string_map(d['source_map']), behavior_requirement_ids=string_map(d['behavior_requirement_ids']),
            component_locks=self.sequence(d['component_locks'], self.component_lock, (*path, 'component_locks')),
            generator_config=self.config(d['generator_config'], (*path, 'generator_config')))

    def value_domain(self, value: JsonValue, path: ViewPath) -> ValueDomain:
        d = fields(value, 'kind dtype unit values lower upper reason', 'biocompiler.component_value_domain.v0.1')
        return self.make(ValueDomain, path, value, kind=text(d['kind']), dtype=self.dtype(d['dtype'], (*path, 'dtype')),
            unit=text(d['unit']), values=tuple(boolean(item) for item in array(d['values'])),
            lower=optional(d['lower'], number), upper=optional(d['upper'], number), reason=optional(d['reason'], text))

    def operating_domain(self, value: JsonValue, path: ViewPath) -> OperatingDomain:
        d = fields(value, 'constraints', 'biocompiler.component_operating_domain.v0.1')
        return self.make(OperatingDomain, path, value, constraints=MappingProxyType({
            key: self.value_domain(item, (*path, 'constraints', key)) for key, item in mapping(d['constraints']).items()}))

    def port(self, value: JsonValue, path: ViewPath) -> PortContract:
        d = fields(value, 'id direction meaning dtype unit role scope compartment timing initialization domain',
            'biocompiler.component_port.v0.2')
        return self.make(PortContract, path, value, id=text(d['id']), direction=text(d['direction']), meaning=text(d['meaning']),
            dtype=self.dtype(d['dtype'], (*path, 'dtype')), unit=text(d['unit']), role=text(d['role']), scope=text(d['scope']),
            compartment=text(d['compartment']), timing=text(d['timing']),
            initialization=self.value_domain(d['initialization'], (*path, 'initialization')),
            domain=self.value_domain(d['domain'], (*path, 'domain')))

    def identity(self, value: JsonValue, path: ViewPath) -> PinnedIdentity:
        d = fields(value, 'kind id version content_fingerprint', 'biocompiler.component_identity.v0.1')
        return self.make(PinnedIdentity, path, value, kind=text(d['kind']), id=text(d['id']), version=text(d['version']),
            content_fingerprint=text(d['content_fingerprint']))

    def parameter(self, value: JsonValue, path: ViewPath) -> ParameterProvenance:
        d = fields(value, 'id value source method', 'biocompiler.component_parameter.v0.1')
        return self.make(ParameterProvenance, path, value, id=text(d['id']),
            value=self.value_domain(d['value'], (*path, 'value')), source=self.identity(d['source'], (*path, 'source')),
            method=text(d['method']))

    def dependency(self, value: JsonValue, path: ViewPath) -> DependencyRequirement:
        d = fields(value, 'id capability role scope compartment required', 'biocompiler.component_dependency.v0.1')
        return self.make(DependencyRequirement, path, value, id=text(d['id']), capability=text(d['capability']),
            role=text(d['role']), scope=text(d['scope']), compartment=text(d['compartment']), required=boolean(d['required']))

    def capability(self, value: JsonValue, path: ViewPath) -> ProvidedCapability:
        d = fields(value, 'id role scope compartment', 'biocompiler.component_capability.v0.1')
        return self.make(ProvidedCapability, path, value, id=text(d['id']), role=text(d['role']),
            scope=text(d['scope']), compartment=text(d['compartment']))

    def reservation(self, value: JsonValue, path: ViewPath) -> ResourceReservation:
        d = fields(value, 'id resource amount unit dtype reusable role scope compartment', 'biocompiler.component_resource_reservation.v0.1')
        return self.make(ResourceReservation, path, value, id=text(d['id']), resource=text(d['resource']),
            amount=optional(d['amount'], number), unit=text(d['unit']), dtype=self.dtype(d['dtype'], (*path, 'dtype')),
            reusable=boolean(d['reusable']), role=text(d['role']), scope=text(d['scope']), compartment=text(d['compartment']))

    def reference(self, value: JsonValue, path: ViewPath) -> SequenceReferenceMetadata:
        d = fields(value, 'artifact_class sequence_length unknown_features completeness', 'biocompiler.component_sequence_reference.v0.1')
        return self.make(SequenceReferenceMetadata, path, value, artifact_class=text(d['artifact_class']),
            sequence_length=integer(d['sequence_length']), unknown_features=strings(d['unknown_features']), completeness=text(d['completeness']))

    def operator(self, value: JsonValue, path: ViewPath) -> SyntheticOperatorModel:
        d = fields(value, 'operation attributes input_ports output_port policy', 'biocompiler.synthetic_operator_model.v0.1')
        return self.make(SyntheticOperatorModel, path, value, operation=text(d['operation']), attributes=frozen_mapping(d['attributes']),
            input_ports=strings(d['input_ports']), output_port=text(d['output_port']), policy=text(d['policy']))

    def component(self, value: JsonValue, path: ViewPath) -> ComponentRecord:
        d = fields(value, 'id version classification implementation_role supported_targets ports supported_domain identities assumptions guarantees evidence parameters dependencies capabilities resources reference_metadata synthetic_model',
            'biocompiler.component_record.v0.2')
        return self.make(ComponentRecord, path, value, id=text(d['id']), version=text(d['version']),
            classification=text(d['classification']), implementation_role=text(d['implementation_role']),
            supported_targets=strings(d['supported_targets']), ports=self.sequence(d['ports'], self.port, (*path, 'ports')),
            supported_domain=self.operating_domain(d['supported_domain'], (*path, 'supported_domain')),
            identities=self.sequence(d['identities'], self.identity, (*path, 'identities')), assumptions=strings(d['assumptions']),
            guarantees=strings(d['guarantees']), evidence=self.sequence(d['evidence'], self.identity, (*path, 'evidence')),
            parameters=self.sequence(d['parameters'], self.parameter, (*path, 'parameters')),
            dependencies=self.sequence(d['dependencies'], self.dependency, (*path, 'dependencies')),
            capabilities=self.sequence(d['capabilities'], self.capability, (*path, 'capabilities')),
            resources=self.sequence(d['resources'], self.reservation, (*path, 'resources')),
            reference_metadata=None if d['reference_metadata'] is None else self.reference(d['reference_metadata'], (*path, 'reference_metadata')),
            synthetic_model=None if d['synthetic_model'] is None else self.operator(d['synthetic_model'], (*path, 'synthetic_model')))

    def registry(self, value: JsonValue, path: ViewPath) -> ComponentRegistry:
        d = fields(value, 'id version components', 'biocompiler.component_registry.v0.2')
        return self.make(ComponentRegistry, path, value, id=text(d['id']), version=text(d['version']),
            components=self.sequence(d['components'], self.component, (*path, 'components')))

    def registry_lock(self, value: JsonValue, path: ViewPath) -> RegistryLock:
        d = fields(value, 'registry_id registry_version registry_fingerprint components identities', 'biocompiler.component_registry_lock.v0.1')
        return self.make(RegistryLock, path, value, registry_id=text(d['registry_id']), registry_version=text(d['registry_version']),
            registry_fingerprint=text(d['registry_fingerprint']), components=self.sequence(d['components'], self.component_lock, (*path, 'components')),
            identities=self.sequence(d['identities'], self.identity, (*path, 'identities')))

    def lifecycle(self, value: JsonValue, path: ViewPath) -> LifecycleInterval:
        d = fields(value, 'start end unit')
        return self.make(LifecycleInterval, path, value, start=number(d['start']), end=optional(d['end'], number), unit=text(d['unit']))

    def instance(self, value: JsonValue, path: ViewPath) -> CompositionInstance:
        d = fields(value, 'id component required_domain placement lifetime requirement_ids source')
        return self.make(CompositionInstance, path, value, id=text(d['id']), component=self.component_lock(d['component'], (*path, 'component')),
            required_domain=self.operating_domain(d['required_domain'], (*path, 'required_domain')), placement=text(d['placement']),
            lifetime=self.lifecycle(d['lifetime'], (*path, 'lifetime')), requirement_ids=strings(d['requirement_ids']),
            source=self.source(d['source'], (*path, 'source')))

    def connection(self, value: JsonValue, path: ViewPath) -> Connection:
        d = fields(value, 'producer_instance producer_port consumer_instance consumer_port')
        return self.make(Connection, path, value, producer_instance=text(d['producer_instance']), producer_port=text(d['producer_port']),
            consumer_instance=text(d['consumer_instance']), consumer_port=text(d['consumer_port']))

    def provider(self, value: JsonValue, path: ViewPath) -> Provider:
        d = fields(value, 'id kind capabilities supported_targets depends_on evidence_refs')
        return self.make(Provider, path, value, id=text(d['id']), kind=text(d['kind']),
            capabilities=self.sequence(d['capabilities'], self.capability, (*path, 'capabilities')),
            supported_targets=strings(d['supported_targets']), depends_on=strings(d['depends_on']), evidence_refs=strings(d['evidence_refs']))

    def dependency_binding(self, value: JsonValue, path: ViewPath) -> DependencyBinding:
        d = fields(value, 'instance_id requirement_id provider_id')
        return self.make(DependencyBinding, path, value, instance_id=text(d['instance_id']), requirement_id=text(d['requirement_id']), provider_id=text(d['provider_id']))

    def pool(self, value: JsonValue, path: ViewPath) -> ResourcePool:
        d = fields(value, 'id resource unit capacity provider_id dtype')
        return self.make(ResourcePool, path, value, id=text(d['id']), resource=text(d['resource']), unit=text(d['unit']),
            capacity=optional(d['capacity'], number), provider_id=text(d['provider_id']), dtype=self.dtype(d['dtype'], (*path, 'dtype')))

    def resource_binding(self, value: JsonValue, path: ViewPath) -> ResourceBinding:
        d = fields(value, 'instance_id reservation_id pool_id')
        return self.make(ResourceBinding, path, value, instance_id=text(d['instance_id']), reservation_id=text(d['reservation_id']), pool_id=text(d['pool_id']))

    def composition(self, value: JsonValue, target: TargetContext, path: ViewPath) -> CompositionRequest:
        d = fields(value, 'target registry_lock instances connections providers dependency_bindings resource_pools resource_bindings requirement_ids',
            'biocompiler.composition_request.v0.1')
        # The session has checked this exact retained target against its binding.
        # The decoder neither imports nor reconstructs target semantics.
        return self.make(CompositionRequest, path, value, target=target, registry_lock=self.registry_lock(d['registry_lock'], (*path, 'registry_lock')),
            instances=self.sequence(d['instances'], self.instance, (*path, 'instances')),
            connections=self.sequence(d['connections'], self.connection, (*path, 'connections')),
            providers=self.sequence(d['providers'], self.provider, (*path, 'providers')),
            dependency_bindings=self.sequence(d['dependency_bindings'], self.dependency_binding, (*path, 'dependency_bindings')),
            resource_pools=self.sequence(d['resource_pools'], self.pool, (*path, 'resource_pools')),
            resource_bindings=self.sequence(d['resource_bindings'], self.resource_binding, (*path, 'resource_bindings')),
            requirement_ids=strings(d['requirement_ids']))

    def assembly(self, value: JsonValue, target: TargetContext, path: ViewPath = ()) -> ComponentAssembly:
        d = fields(value, 'registry composition request_fingerprint candidate_fingerprint observation_map behavior_sources nodes',
            'biocompiler.component_assembly.v0.2')
        for node in array(d['nodes']):
            node_fields = fields(node, 'id kind')
            text(node_fields['id'])
            require(node_fields['kind'] == 'component_instance', 'Assembly inventory tag differs')
        return self.make(ComponentAssembly, path, value, registry=self.registry(d['registry'], (*path, 'registry')),
            composition=self.composition(d['composition'], target, (*path, 'composition')),
            request_fingerprint=text(d['request_fingerprint']), candidate_fingerprint=text(d['candidate_fingerprint']),
            behavior_sources=string_map(d['behavior_sources']), observation_map=self.observations(d['observation_map'], (*path, 'observation_map')))

    def source_link(self, value: JsonValue, path: ViewPath) -> SourceLink:
        d = fields(value, 'requirement_id source_node_id target_node_id pass_name')
        return self.make(SourceLink, path, value, requirement_id=text(d['requirement_id']), source_node_id=text(d['source_node_id']),
            target_node_id=text(d['target_node_id']), pass_name=text(d['pass_name']))

    def obligation(self, value: JsonValue, path: ViewPath) -> Obligation:
        d = fields(value, 'requirement_id description evidence_kind evidence_refs')
        evidence = text(d['evidence_kind'])
        kinds = {item.value: item for item in EvidenceKind}
        require(evidence in kinds, 'Unknown provider obligation evidence kind')
        return self.make(Obligation, path, value, requirement_id=text(d['requirement_id']), description=text(d['description']),
            evidence_kind=kinds[evidence], evidence_refs=strings(d['evidence_refs']))

    def proposal(self, value: JsonValue, role: str, target: TargetContext | None = None) -> PassResult[ProviderOutput]:
        d = fields(value, 'output obligations source_links observation_map search_status')
        output: ProviderOutput
        if role == 'intent_to_behavior.producer':
            output = self.behavior(d['output'], ('output',))
        elif role == 'behavior_to_synthetic.producer':
            output = self.candidate(d['output'], ('output',))
        else:
            require(role == 'synthetic_to_components.producer' and target is not None, 'Unknown or incomplete typed producer role')
            assert target is not None
            output = self.assembly(d['output'], target, ('output',))
        return self.make(PassResult, (), value, output=output,
            obligations=self.sequence(d['obligations'], self.obligation, ('obligations',)),
            source_links=self.sequence(d['source_links'], self.source_link, ('source_links',)),
            observation_map=mapping(d['observation_map']), search_status=text(d['search_status']))

    def decision(self, value: JsonValue, role: str) -> CheckDecision:
        require(role in PROVIDER_ROLES and role.endswith('.validator'), 'Unknown typed validator role')
        d = fields(value, 'outcome detail evidence')
        outcome = text(d['outcome'])
        outcomes = {item.value: item for item in CheckOutcome}
        require(outcome in outcomes, 'Unknown provider check outcome')
        return self.make(CheckDecision, (), value, outcome=outcomes[outcome], detail=text(d['detail']), evidence=frozen_mapping(d['evidence']))


# Closed source-reviewed field layouts; wire data cannot select a Python class.
CLASS_FIELDS: dict[type[object], tuple[str, ...]] = {
    PassResult: ('output', 'obligations', 'source_links', 'observation_map', 'search_status'),
    SourceLocation: ('file', 'line', 'function'),
    TypeSpec: ('kind', 'name', 'dimensions', 'arguments'),
    BehaviorRequirement: ('id', 'kind', 'source_node_id', 'lineage', 'source'),
    BehaviorNode: ('id', 'kind', 'inputs', 'attributes', 'data_type', 'role', 'source', 'contact_bound', 'requirement_ids'),
    BehaviorProgram: ('name', 'nodes', 'roots', 'source_fingerprint', 'requirements', 'source_links', 'policies', 'parameter_bindings', 'schema_version'),
    Observable: ('id', 'dtype', 'role', 'scope', 'compartment'),
    MechanismNode: ('id', 'kind', 'output', 'inputs', 'attributes', 'requirement_ids'),
    MechanismProgram: ('name', 'nodes', 'outputs', 'required_capabilities', 'schema_version'),
    InputBinding: ('signal_id', 'field', 'mechanism_input_id'),
    OutputBinding: ('requirement_id', 'mechanism_output_id'),
    ObservationMap: ('inputs', 'outputs'),
    SyntheticGeneratorConfig: ('profile_version', 'generator_version', 'catalog_fingerprint', 'witness_selection', 'conjunction_strategy'),
    ComponentLock: ('node_id', 'component_id', 'version', 'content_fingerprint'),
    SyntheticCandidate: ('request_fingerprint', 'mechanism', 'observation_map', 'source_map', 'behavior_requirement_ids', 'component_locks', 'generator_config'),
    ValueDomain: ('kind', 'dtype', 'unit', 'values', 'lower', 'upper', 'reason'),
    OperatingDomain: ('constraints',),
    PortContract: ('id', 'direction', 'meaning', 'dtype', 'unit', 'role', 'scope', 'compartment', 'timing', 'initialization', 'domain'),
    PinnedIdentity: ('kind', 'id', 'version', 'content_fingerprint'),
    ParameterProvenance: ('id', 'value', 'source', 'method'),
    DependencyRequirement: ('id', 'capability', 'role', 'scope', 'compartment', 'required'),
    ProvidedCapability: ('id', 'role', 'scope', 'compartment'),
    ResourceReservation: ('id', 'resource', 'amount', 'unit', 'dtype', 'reusable', 'role', 'scope', 'compartment'),
    SequenceReferenceMetadata: ('artifact_class', 'sequence_length', 'unknown_features', 'completeness'),
    SyntheticOperatorModel: ('operation', 'attributes', 'input_ports', 'output_port', 'policy'),
    ComponentRecord: ('id', 'version', 'classification', 'implementation_role', 'supported_targets', 'ports', 'supported_domain', 'identities', 'assumptions', 'guarantees', 'evidence', 'parameters', 'dependencies', 'capabilities', 'resources', 'reference_metadata', 'synthetic_model'),
    ComponentRegistry: ('id', 'version', 'components'),
    RegistryLock: ('registry_id', 'registry_version', 'registry_fingerprint', 'components', 'identities'),
    LifecycleInterval: ('start', 'end', 'unit'),
    CompositionInstance: ('id', 'component', 'required_domain', 'placement', 'lifetime', 'requirement_ids', 'source'),
    Connection: ('producer_instance', 'producer_port', 'consumer_instance', 'consumer_port'),
    Provider: ('id', 'kind', 'capabilities', 'supported_targets', 'depends_on', 'evidence_refs'),
    DependencyBinding: ('instance_id', 'requirement_id', 'provider_id'),
    ResourcePool: ('id', 'resource', 'unit', 'capacity', 'provider_id', 'dtype'),
    ResourceBinding: ('instance_id', 'reservation_id', 'pool_id'),
    CompositionRequest: ('target', 'registry_lock', 'instances', 'connections', 'providers', 'dependency_bindings', 'resource_pools', 'resource_bindings', 'requirement_ids'),
    ComponentAssembly: ('registry', 'composition', 'request_fingerprint', 'candidate_fingerprint', 'behavior_sources', 'observation_map'),
    SourceLink: ('requirement_id', 'source_node_id', 'target_node_id', 'pass_name'),
}
CLASS_TAGS = {cls.__module__ + "." + cls.__qualname__: cls for cls in CLASS_FIELDS}
ALIAS_CLASSES = frozenset((SourceLocation, TypeSpec, Observable, OperatingDomain, ValueDomain,
    PinnedIdentity, ComponentLock, LifecycleInterval))
ALIAS_TAGS = {tag: cls for tag, cls in CLASS_TAGS.items() if cls in ALIAS_CLASSES}


def raw_shape(value: object) -> JsonValue:
    """Observe only exact closed regular values, with no user operators."""
    cls = type(value)
    if value is None or cls in (str, bool, int, float):
        if cls is float:
            number(cast(float, value))
        return [cls.__name__, cast(JsonValue, value)]
    if cls in (TargetContext, HumanTargetContext):
        # Targets are retained host capabilities checked by the manager. They
        # cannot be rebuilt from this provider schema or equated by content.
        return ['retained-target', id(value)]
    if cls in (tuple, list):
        return [cls.__name__, [raw_shape(item) for item in cast(tuple[object, ...] | list[object], value)]]
    if cls in (dict, MappingProxyType):
        entries = cast(Mapping[object, object], value)
        require(all(type(key) is str for key in entries), 'Typed host mapping key differs')
        return [cls.__name__, [[cast(str, key), raw_shape(item)] for key, item in entries.items()]]
    names = CLASS_FIELDS.get(cls)
    require(names is not None, 'Unsupported typed host object class')
    assert names is not None
    values = cast(dict[str, object], object.__getattribute__(value, '__dict__'))
    require(tuple(values) == names, 'Typed host object fields or order differ')
    return [cls.__module__ + '.' + cls.__qualname__, [[name, raw_shape(values[name])] for name in names]]


def same_fields(value: object, cls: type[object], values: Mapping[str, object]) -> bool:
    require(type(value) is cls, 'Typed host binding class differs')
    return bytes(encode_document(raw_shape(value))) == bytes(encode_document(raw_shape(allocate(cls, values))))


def _raw_field(value: object, cls: type[object], name: str) -> object:
    require(type(value) is cls, 'Provider origin requires exact regular classes')
    fields = cast(dict[str, object], object.__getattribute__(value, '__dict__'))
    require(name in fields, 'Provider origin field is absent')
    return fields[name]


def _raw_index(value: object, index: JsonValue) -> object:
    require(type(value) is tuple and type(index) is int, 'Provider origin requires a tuple index')
    items, position = cast(tuple[object, ...], value), cast(int, index)
    require(0 <= position < len(items), 'Provider origin index is out of bounds')
    return items[position]


def origin_reference(request: object, root: str, path: JsonValue) -> object:
    """The only authored/global origin paths in the fixed provider profile."""
    parts = array(path)
    constants: dict[str, object] = {
        'BOOLEAN': BOOLEAN, 'DURATION': DURATION, 'LEVEL': LEVEL,
        'defaultLifecycle': CompositionInstance.__dataclass_fields__['lifetime'].default,
    }
    if root in constants:
        require(not parts, 'Named provider origins require an empty path')
        return constants[root]
    require(root == 'request' and len(parts) >= 4, 'Unknown provider origin root or path')
    head = parts[:2]
    if head == ['behavior', 'nodes']:
        require(len(parts) == 4 and parts[3] == 'source', 'Unknown behavior source origin path')
        behavior = _raw_field(request, RealizationRequest, 'behavior')
        node = _raw_index(_raw_field(behavior, BehaviorProgram, 'nodes'), parts[2])
        result = _raw_field(node, BehaviorNode, 'source')
        require(type(result) is SourceLocation, 'Provider source origin is absent or has a custom class')
        return result
    require(parts[3] == 'observable', 'Unknown authored observable origin path')
    if head == ['domain', 'inputs']:
        domain = _raw_field(request, RealizationRequest, 'domain')
        item = _raw_index(_raw_field(domain, RequestDomain, 'inputs'), parts[2])
        result = _raw_field(item, InputDomain, 'observable')
    else:
        require(head == ['contract', 'requirements'], 'Unknown authored provider origin path')
        contract = _raw_field(request, RealizationRequest, 'contract')
        item = _raw_index(_raw_field(contract, BehaviorContract, 'requirements'), parts[2])
        result = _raw_field(item, ResponseRequirement, 'observable')
    require(type(result) is Observable, 'Provider observable origin has a custom class')
    if len(parts) == 4:
        return result
    require(parts[4] == 'dtype' and len(parts) % 2 == 1, 'Unknown authored dtype origin path')
    result = _raw_field(result, Observable, 'dtype')
    for index in range(5, len(parts), 2):
        require(parts[index] == 'arguments', 'Unknown authored type argument origin path')
        result = _raw_index(_raw_field(result, TypeSpec, 'arguments'), parts[index + 1])
    require(type(result) is TypeSpec, 'Provider dtype origin has a custom class')
    return result


@dataclass(frozen=True)
class _RetainedView:
    cls: type[object]
    document: bytes
    value: object


def _path(value: JsonValue) -> ViewPath:
    parts = array(value)
    require(bool(parts) and all(type(item) in (str, int) for item in parts), 'Malformed typed alias path')
    return tuple(cast(str | int, item) for item in parts)


def _at(value: JsonValue, path: ViewPath) -> JsonValue:
    for part in path:
        if type(part) is int:
            items = array(value)
            require(0 <= part < len(items), 'Typed alias index is out of bounds')
            value = items[part]
        else:
            members = mapping(value)
            require(part in members, 'Typed alias field is absent')
            value = members[cast(str, part)]
    return value


class ProviderViewStore:
    """Strong bounded native identities; never an acceptance or semantic cache."""
    def __init__(self, resolve: Callable[[JsonValue], object], *, max_objects: int = 100_000,
                 max_retained_bytes: int = 134_217_728, identity_taken: Callable[[str], bool] | None = None):
        self.resolve = resolve
        self.max_objects = max_objects
        self.max_retained_bytes = max_retained_bytes
        self.retained_bytes = 0
        self.native: dict[str, _RetainedView] = {}
        self.identity_taken = identity_taken

    def bind(self, cls: type[T], binding: JsonValue, document: JsonValue, values: Mapping[str, object]) -> T:
        raw = mapping(binding)
        if raw.get('kind') == 'host':
            fields(binding, 'kind object')
            value = self.resolve(raw['object'])
            require(same_fields(value, cls, values), 'Typed host binding fields differ from native view')
            return cast(T, value)
        fields(binding, 'kind identity tree')
        require(raw['kind'] == 'native', 'Unknown typed view binding kind')
        identity = text(raw['identity'])
        require(bool(identity), 'Empty typed native identity')
        require(self.identity_taken is None or not self.identity_taken(identity), 'Typed native identity collides with another view')
        checked_ordered(raw['tree'], document)
        signature = bytes(encode_document(raw['tree']))
        previous = self.native.get(identity)
        if previous is not None:
            require(previous.cls is cls and previous.document == signature, 'Typed native identity was rebound')
            require(same_fields(previous.value, cls, values), 'Typed native identity changed nested fields')
            return cast(T, previous.value)
        require(len(self.native) < self.max_objects, 'Typed native identity limit exceeded')
        # Retention is cumulative. The full ordered signature is kept so neither
        # a digest collision nor an equal differently ordered graph can rebind it.
        charge = len(signature) + 256
        require(self.retained_bytes + charge <= self.max_retained_bytes, 'Typed view retention limit exceeded')
        self.retained_bytes += charge
        result = allocate(cls, values)
        self.native[identity] = _RetainedView(cls, signature, result)
        return result

    def decode(self, envelope: JsonValue, *, role: str, target: TargetContext,
               target_document: JsonValue, requested_config: SyntheticGeneratorConfig | None = None) -> PassResult[ProviderOutput] | CheckDecision | FrozenJson:
        raw = fields(envelope, 'kind value view')
        require(role in PROVIDER_ROLES, 'Unknown native provider capability role')
        if raw['kind'] == 'invalid':
            require(raw['view'] is None, 'Invalid provider result cannot carry a typed view')
            return frozen(raw['value'])
        view = fields(raw['view'], 'role tree bindings aliases')
        require(view['role'] == role, 'Provider result role differs from its actual native capability')
        value = checked_ordered(view['tree'], raw['value'])
        bindings = mapping(view['bindings'])
        factory = _AliasFactory(self, value, view['aliases'])
        if raw['kind'] == 'decision':
            require(not bindings and not array(view['aliases']), 'Check decisions cannot import typed identity bindings')
            result: PassResult[ProviderOutput] | CheckDecision = StructuralViews(factory).decision(value, role)
        else:
            require(raw['kind'] == 'proposal', 'Unknown typed native provider result kind')
            if role == 'intent_to_behavior.producer':
                require(not bindings, 'Behavior provider cannot bind captured output roots')
            elif role == 'behavior_to_synthetic.producer':
                fields(view['bindings'], 'generator_config')
                config_binding = mapping(bindings['generator_config'])
                if config_binding.get('kind') == 'host':
                    fields(bindings['generator_config'], 'kind object')
                    require(requested_config is not None and self.resolve(config_binding['object']) is requested_config,
                        'Synthetic provider did not retain its actual authored configuration')
                factory.add(SyntheticGeneratorConfig, ('output', 'generator_config'), bindings['generator_config'])
            else:
                require(role == 'synthetic_to_components.producer', 'Proposal role is not a fixed producer')
                fields(view['bindings'], 'registry composition composition_target')
                factory.add(ComponentRegistry, ('output', 'registry'), bindings['registry'])
                factory.add(CompositionRequest, ('output', 'composition'), bindings['composition'])
                target_binding = fields(bindings['composition_target'], 'kind object')
                require(target_binding['kind'] == 'host' and self.resolve(target_binding['object']) is target,
                    'Composition did not retain its actual authored target')
                require(encode_document(_at(value, ('output', 'composition', 'target'))) == encode_document(target_document),
                    'Composition target document differs from its retained authority')
            result = StructuralViews(factory).proposal(value, role, target)
        factory.complete(result)
        return result


class _AliasFactory:
    def __init__(self, store: ProviderViewStore, value: JsonValue, aliases: JsonValue):
        self.store, self.value = store, value
        self.bindings: dict[ViewPath, tuple[type[object], JsonValue]] = {}
        self.visited: set[ViewPath] = set()
        self.objects: dict[ViewPath, object] = {}
        for group in array(aliases):
            raw = fields(group, 'kind paths binding')
            tag = text(raw['kind'])
            require(tag in ALIAS_TAGS, 'Unknown typed alias class tag')
            paths = array(raw['paths'])
            require(bool(paths), 'Typed alias group has no paths')
            for path in paths:
                self.add(ALIAS_TAGS[tag], _path(path), raw['binding'], overlap=False)

    def add(self, cls: type[object], path: ViewPath, binding: JsonValue, *, overlap: bool = True) -> None:
        require(cls in CLASS_FIELDS, 'Typed binding requires a closed view class')
        _at(self.value, path)
        previous = self.bindings.get(path)
        require(previous is None or overlap and previous[0] is cls
            and encode_document(previous[1]) == encode_document(binding), 'Conflicting or duplicate typed alias path')
        self.bindings[path] = cls, binding

    def __call__(self, cls: type[T], path: ViewPath, document: JsonValue, values: Mapping[str, object]) -> T:
        binding = self.bindings.get(path)
        if binding is None:
            return allocate(cls, values)
        require(binding[0] is cls, 'Typed alias path reaches a different view class')
        self.visited.add(path)
        result = self.store.bind(cls, binding[1], document, values)
        self.objects[path] = result
        return result

    def complete(self, result: object) -> None:
        require(self.visited == set(self.bindings), 'Typed alias path was not consumed by a closed decoder')
        for path, expected in self.objects.items():
            value = result
            for part in path:
                cls = type(value)
                if cls is tuple:
                    value = _raw_index(value, part)
                elif cls in (dict, MappingProxyType):
                    require(type(part) is str, 'Typed returned alias requires a mapping key')
                    value = cast(Mapping[str, object], value)[cast(str, part)]
                else:
                    require(type(part) is str and part in CLASS_FIELDS.get(cls, ()), 'Typed returned alias left its closed schema')
                    value = _raw_field(value, cls, cast(str, part))
            require(value is expected, 'Typed alias differs from the actual returned object identity')
