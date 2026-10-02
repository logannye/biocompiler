"""Closed public views of completed native fixed builds.

These decoders reconstruct representation only. They never run a legacy model
constructor, parser, registry lookup, checker, selection policy, or manager.
Historical result/record identity and retained selection origins are supplied by
an independently bound native build envelope, not inferred from equal contents.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TypeVar, cast

from biocompiler.core_client import JsonValue
from biocompiler.core_pipeline_provider_views import (
    ALIAS_TAGS, CLASS_FIELDS, FrozenJson, ProviderViewStore, StructuralViews, ViewPath, allocate, array,
    checked_ordered, fields, frozen_mapping, integer, mapping, number, optional, require, strings, text,
)
from biocompiler.compiler.components import ComponentBuild
from biocompiler.compiler.pipeline import PassManager, PipelineResult, StageRecord
from biocompiler.compiler.synthetic import SyntheticBuild
from biocompiler.semantics.context import PayloadFormat, TargetContext
from biocompiler.semantics.types import ScalarLiteral, TypeSpec
from biocompiler.synthesis.selection import SELECTION_VERSION, SyntheticAlternative, SyntheticSelectionResult
from biocompiler.synthesis.policy import COST_VERSION
from biocompiler.synthesis.synthetic import SyntheticCandidate, SyntheticGeneratorConfig
from biocompiler.ir.component_assembly import ComponentAssembly
from biocompiler.ir.mechanism import MechanismNode, MechanismProgram
from biocompiler.core_pipeline_session import encode_document
from biocompiler.verification.components import (
    CLAIM_SCOPE as LINK_SCOPE, CompositionResult, LinkDiagnostic, ResolvedDependency, ResourceUsage,
)
from biocompiler.verification.evidence import (
    CLAIM_SCOPE as CHECK_SCOPE, CheckDiagnostic, CheckOutcome, CheckResult, Counterexample, DependencySnapshot,
    EvidenceKind, RequirementCoverage,
)


class BuildViews(StructuralViews):
    """Finite dataclass field decoders; graph identity belongs to the caller."""

    def scalar(self, value: JsonValue, path: ViewPath = ()) -> ScalarLiteral:
        d = fields(value, 'kind value unit canonical_value type')
        require(d['kind'] == 'scalar', 'Build resource must have scalar representation')
        return self.make(ScalarLiteral, path, value, value=number(d['value']),
            dtype=self.dtype(d['type'], (*path, 'dtype')), unit=text(d['unit']),
            canonical_value=number(d['canonical_value']))

    def target(self, value: JsonValue, path: ViewPath = ()) -> TargetContext:
        d = fields(value, 'context_id context_version payload_format capabilities compartments resources',
            'biocompiler.target.v0.1')
        modality = text(d['payload_format'])
        require(modality in ('DNA', 'RNA'), 'Build target modality differs')
        resources = {key: self.scalar(item, (*path, 'resources', key))
            for key, item in mapping(d['resources']).items()}
        return self.make(TargetContext, path, value, context_id=text(d['context_id']),
            context_version=text(d['context_version']), payload_format=PayloadFormat(modality),
            capabilities=strings(d['capabilities']), compartments=strings(d['compartments']),
            resources=MappingProxyType(resources))

    def check_diagnostic(self, value: JsonValue, path: ViewPath = ()) -> CheckDiagnostic:
        d = fields(value, 'code message requirement_id node_id source')
        return self.make(CheckDiagnostic, path, value, code=text(d['code']), message=text(d['message']),
            requirement_id=optional(d['requirement_id'], text), node_id=optional(d['node_id'], text),
            source=self.source(d['source'], (*path, 'source')))

    def counterexample(self, value: JsonValue, path: ViewPath = ()) -> Counterexample:
        d = fields(value, 'requirement_id time contact_id expected actual rule_id specification_id source')
        expected = fields(d['expected'], 'state range')
        require(text(expected['state']) in ('active', 'inactive'), 'Counterexample state differs')
        mapping(expected['range'])
        return self.make(Counterexample, path, value, requirement_id=text(d['requirement_id']), time=number(d['time']),
            contact_id=optional(d['contact_id'], text), expected=frozen_mapping(d['expected']),
            actual=optional(d['actual'], number), rule_id=text(d['rule_id']), specification_id=text(d['specification_id']),
            source=self.source(d['source'], (*path, 'source')))

    def coverage(self, value: JsonValue, path: ViewPath = ()) -> RequirementCoverage:
        d = fields(value, 'requirement_id activation_deadlines_checked inactive_deadlines_checked incomplete_episode_count cancelled_episode_count')
        return self.make(RequirementCoverage, path, value, requirement_id=text(d['requirement_id']),
            activation_deadlines_checked=integer(d['activation_deadlines_checked']),
            inactive_deadlines_checked=integer(d['inactive_deadlines_checked']),
            incomplete_episode_count=integer(d['incomplete_episode_count']),
            cancelled_episode_count=integer(d['cancelled_episode_count']))

    def check_result(self, value: JsonValue, path: ViewPath = ()) -> CheckResult:
        d = fields(value, 'outcome dependencies checked_requirement_ids diagnostics counterexamples evidence_kind claim_scope coverage',
            'biocompiler.realization_check.v0.1')
        outcome, evidence = text(d['outcome']), text(d['evidence_kind'])
        require(outcome in CheckOutcome._value2member_map_ and evidence == 'model_conditional',
            'Build check enum differs')
        require(d['claim_scope'] == CHECK_SCOPE, 'Build check claim scope differs')
        fields(d['dependencies'], 'behavior behavior_artifact contract domain target mechanism observation_map history horizon checker model_runner reference_evaluator settings')
        dependencies = self.make(DependencySnapshot, (*path, 'dependencies'), d['dependencies'],
            values=frozen_mapping(d['dependencies']))
        return self.make(CheckResult, path, value, outcome=CheckOutcome(outcome), dependencies=dependencies,
            checked_requirement_ids=strings(d['checked_requirement_ids']),
            diagnostics=self.sequence(d['diagnostics'], self.check_diagnostic, (*path, 'diagnostics')),
            counterexamples=self.sequence(d['counterexamples'], self.counterexample, (*path, 'counterexamples')),
            evidence_kind=EvidenceKind(evidence), claim_scope=text(d['claim_scope']), schema_version=text(d['schema_version']),
            coverage=self.sequence(d['coverage'], self.coverage, (*path, 'coverage')))

    def link_diagnostic(self, value: JsonValue, path: ViewPath = ()) -> LinkDiagnostic:
        d = fields(value, 'status code message instance_id requirement_ids')
        require(text(d['status']) in ('fail', 'unknown', 'unsupported'), 'Link diagnostic status differs')
        return self.make(LinkDiagnostic, path, value, status=text(d['status']), code=text(d['code']), message=text(d['message']),
            instance_id=optional(d['instance_id'], text), requirement_ids=strings(d['requirement_ids']))

    def resolved_dependency(self, value: JsonValue, path: ViewPath = ()) -> ResolvedDependency:
        d = fields(value, 'instance_id requirement_id provider_id provider_kind status')
        require(text(d['provider_kind']) in ('encoded_here', 'co_payload', 'host', 'external', 'unresolved'),
            'Resolved dependency provider kind differs')
        require(text(d['status']) in CheckOutcome._value2member_map_, 'Resolved dependency status differs')
        return self.make(ResolvedDependency, path, value, instance_id=text(d['instance_id']),
            requirement_id=text(d['requirement_id']), provider_id=optional(d['provider_id'], text),
            provider_kind=text(d['provider_kind']), status=text(d['status']))

    def resource_usage(self, value: JsonValue, path: ViewPath = ()) -> ResourceUsage:
        d = fields(value, 'pool_id peak_reservation capacity unit status')
        require(text(d['status']) in CheckOutcome._value2member_map_, 'Resource usage status differs')
        return self.make(ResourceUsage, path, value, pool_id=text(d['pool_id']), peak_reservation=optional(d['peak_reservation'], number),
            capacity=optional(d['capacity'], number), unit=text(d['unit']), status=text(d['status']))

    def link_result(self, value: JsonValue, path: ViewPath = ()) -> CompositionResult:
        d = fields(value, 'outcome dependencies checked_requirement_ids diagnostics resolved_dependencies resource_usage claim_scope',
            'biocompiler.component_link_result.v0.3')
        outcome = text(d['outcome'])
        require(outcome in CheckOutcome._value2member_map_, 'Build link outcome differs')
        require(d['claim_scope'] == LINK_SCOPE, 'Build link claim scope differs')
        fields(d['dependencies'], 'request registry registry_lock target checker identities admission_policy')
        return self.make(CompositionResult, path, value, outcome=CheckOutcome(outcome),
            dependencies=frozen_mapping(d['dependencies']), checked_requirement_ids=strings(d['checked_requirement_ids']),
            diagnostics=self.sequence(d['diagnostics'], self.link_diagnostic, (*path, 'diagnostics')),
            resolved_dependencies=self.sequence(d['resolved_dependencies'], self.resolved_dependency, (*path, 'resolved_dependencies')),
            resource_usage=self.sequence(d['resource_usage'], self.resource_usage, (*path, 'resource_usage')),
            claim_scope=text(d['claim_scope']))

    def alternative(self, value: JsonValue, path: ViewPath = ()) -> SyntheticAlternative:
        d = fields(value, 'strategy candidate constraint_violations check generation_error gate_count status',
            'biocompiler.synthetic_alternative.v0.1')
        # The redundant summary stays native-owned. Read its complete scalar
        # shape without invoking the public computed ranking/check properties.
        optional(d['gate_count'], integer)
        require(text(d['status']) in ('pass', 'fail', 'unknown', 'unsupported', 'hard_rejected'), 'Alternative status differs')
        require(text(d['strategy']) in ('native', 'de_morgan'), 'Alternative strategy differs')
        return self.make(SyntheticAlternative, path, value, strategy=text(d['strategy']),
            candidate=None if d['candidate'] is None else self.candidate(d['candidate'], (*path, 'candidate')),
            constraint_violations=strings(d['constraint_violations']),
            check=None if d['check'] is None else self.check_result(d['check'], (*path, 'check')),
            generation_error=optional(d['generation_error'], text))

    def selection(self, value: JsonValue, path: ViewPath = ()) -> SyntheticSelectionResult:
        d = fields(value, 'selection_version cost_version intended_use human_therapeutic_admission request_fingerprint history_fingerprint until config minimize alternatives selected_strategy outcome checked_candidates rejected_candidates search_scope',
            'biocompiler.synthetic_selection_result.v0.1')
        require(d['intended_use'] == 'software_test' and d['human_therapeutic_admission'] == 'not_admitted',
            'Build selection claim tags differ')
        require(d['selection_version'] == SELECTION_VERSION and d['cost_version'] == COST_VERSION
            and d['search_scope'] == 'two_whole_program_conjunction_strategies', 'Build selection profile differs')
        require(optional(d['selected_strategy'], text) in (None, 'native', 'de_morgan'), 'Selected strategy differs')
        require(text(d['outcome']) in ('selected', 'unknown', 'unsupported', 'exhausted'), 'Selection outcome differs')
        require(text(d['minimize']) in ('gate_count', 'none'), 'Selection ranking profile differs')
        integer(d['checked_candidates']); integer(d['rejected_candidates'])
        return self.make(SyntheticSelectionResult, path, value, request_fingerprint=text(d['request_fingerprint']),
            history_fingerprint=text(d['history_fingerprint']), until=optional(d['until'], number),
            config=self.config(d['config'], (*path, 'config')), minimize=text(d['minimize']),
            alternatives=self.sequence(d['alternatives'], self.alternative, (*path, 'alternatives')))


BUILD_FIELDS = {
    **CLASS_FIELDS,
    TargetContext: ('context_id', 'context_version', 'payload_format', 'capabilities', 'compartments', 'resources'),
    ScalarLiteral: ('value', 'dtype', 'unit', 'canonical_value'),
    DependencySnapshot: ('values',),
    CheckDiagnostic: ('code', 'message', 'requirement_id', 'node_id', 'source'),
    Counterexample: ('requirement_id', 'time', 'contact_id', 'expected', 'actual', 'rule_id', 'specification_id', 'source'),
    RequirementCoverage: ('requirement_id', 'activation_deadlines_checked', 'inactive_deadlines_checked', 'incomplete_episode_count', 'cancelled_episode_count'),
    CheckResult: ('outcome', 'dependencies', 'checked_requirement_ids', 'diagnostics', 'counterexamples', 'evidence_kind', 'claim_scope', 'schema_version', 'coverage'),
    LinkDiagnostic: ('status', 'code', 'message', 'instance_id', 'requirement_ids'),
    ResolvedDependency: ('instance_id', 'requirement_id', 'provider_id', 'provider_kind', 'status'),
    ResourceUsage: ('pool_id', 'peak_reservation', 'capacity', 'unit', 'status'),
    CompositionResult: ('outcome', 'dependencies', 'checked_requirement_ids', 'diagnostics', 'resolved_dependencies', 'resource_usage', 'claim_scope'),
    SyntheticAlternative: ('strategy', 'candidate', 'constraint_violations', 'check', 'generation_error'),
    SyntheticSelectionResult: ('request_fingerprint', 'history_fingerprint', 'until', 'config', 'minimize', 'alternatives'),
}


def build_shape(value: object) -> JsonValue:
    """Read only closed stored fields, never properties, equality, or serializers."""
    kind = type(value)
    if value is None or kind in (bool, int, float, str):
        if kind is float:
            number(cast(float, value))
        return [kind.__name__, cast(JsonValue, value)]
    if kind in (CheckOutcome, EvidenceKind, PayloadFormat):
        return [kind.__module__ + '.' + kind.__qualname__, cast(str, object.__getattribute__(value, 'value'))]
    if kind in (tuple, list):
        return [kind.__name__, [build_shape(item) for item in cast(tuple[object, ...] | list[object], value)]]
    if kind in (dict, MappingProxyType):
        members = cast(dict[object, object], value)
        require(all(type(key) is str for key in members), 'Build view mapping keys differ')
        return [kind.__name__, [[cast(str, key), build_shape(item)] for key, item in members.items()]]
    names = BUILD_FIELDS.get(kind)
    require(names is not None, 'Unknown public build view class')
    values = cast(dict[str, object], object.__getattribute__(value, '__dict__'))
    require(tuple(values) == names, 'Build view stored fields differ')
    return [kind.__module__ + '.' + kind.__qualname__, [[name, build_shape(values[name])] for name in cast(tuple[str, ...], names)]]


def synthetic_build(candidate: SyntheticCandidate, result: PipelineResult, manager: PassManager,
                    selection: SyntheticSelectionResult | None) -> SyntheticBuild:
    return allocate(SyntheticBuild, {'candidate': candidate, 'result': result, 'manager': manager, 'selection_result': selection})


def component_build(candidate: SyntheticCandidate, assembly: ComponentAssembly, link: CompositionResult,
                    result: PipelineResult, manager: PassManager, behavior: CheckResult,
                    selection: SyntheticSelectionResult | None) -> ComponentBuild:
    return allocate(ComponentBuild, {'candidate': candidate, 'assembly': assembly, 'link_result': link, 'result': result,
        'manager': manager, 'behavior_result': behavior, 'selection_result': selection})


T = TypeVar('T')


def _frozen_at(value: FrozenJson, path: ViewPath) -> FrozenJson:
    for part in path:
        if type(part) is int:
            require(type(value) is tuple and 0 <= part < len(value),
                'Build parser source index differs')
            value = cast(tuple[FrozenJson, ...], value)[part]
        else:
            require(type(value) in (dict, MappingProxyType), 'Build parser source object differs')
            members = cast(Mapping[str, FrozenJson], value)
            require(part in members, 'Build parser source field is absent')
            value = members[cast(str, part)]
    return value


def _mutable(value: FrozenJson) -> JsonValue:
    if type(value) in (dict, MappingProxyType):
        return {key: _mutable(item) for key, item in cast(Mapping[str, FrozenJson], value).items()}
    if type(value) is tuple:
        return [_mutable(item) for item in value]
    require(value is None or type(value) in (bool, int, float, str), 'Build source contains nonliteral values')
    return cast(JsonValue, value)


class _ParsedCandidateFactory:
    def __init__(self, source: FrozenJson, *, store: ProviderViewStore | None = None,
                 aliases: Mapping[ViewPath, JsonValue] | None = None):
        self.source = source
        self.store, self.aliases = store, dict(aliases or {})
        self.objects: dict[ViewPath, object] = {}

    def __call__(self, kind: type[T], path: ViewPath, document: JsonValue,
                 values: Mapping[str, object], /) -> T:
        # The original MechanismNode/Program parsers call tuple(existing_tuple)
        # for exactly these four fields. Every other field follows fresh closed
        # structural decoding, including source-map strings and all dataclasses.
        values = dict(values)
        names: tuple[str, ...] = ()
        if kind is MechanismNode:
            require(len(path) == 3 and path[:2] == ('mechanism', 'nodes') and type(path[2]) is int,
                'Parsed mechanism node left its closed source path')
            names = ('inputs', 'requirement_ids')
        elif kind is MechanismProgram:
            require(path == ('mechanism',), 'Parsed mechanism left its closed source path')
            names = ('outputs', 'required_capabilities')
        for name in names:
            actual = _frozen_at(self.source, (*path, name))
            require(type(actual) is tuple and all(type(item) is str for item in cast(tuple[object, ...], actual))
                and actual == values[name], 'Parsed candidate tuple differs from its exact historical record')
            values[name] = actual
        if path in self.aliases:
            require(kind is TypeSpec and self.store is not None, 'Candidate type origin reaches another class')
            assert self.store is not None
            result = self.store.bind(kind, self.aliases[path], document, values)
            self.objects[path] = result
            return result
        return allocate(kind, values)

    def complete(self, result: object) -> None:
        require(set(self.objects) == set(self.aliases), 'Candidate type origin was not consumed')
        for path, expected in self.objects.items():
            require(_object_at(result, path) is expected, 'Candidate type origin differs from returned identity')


def parsed_candidate(value: JsonValue, source_payload: FrozenJson) -> SyntheticCandidate:
    require(encode_document(value) == encode_document(_mutable(source_payload)),
        'Build candidate differs from its actual historical parser source')
    return BuildViews(_ParsedCandidateFactory(source_payload)).candidate(value)


def _json_at(value: JsonValue, path: ViewPath) -> JsonValue:
    for part in path:
        if type(part) is int:
            items = array(value)
            require(0 <= part < len(items), 'Build alias index differs')
            value = items[part]
        else:
            members = mapping(value)
            require(part in members, 'Build alias field is absent')
            value = members[cast(str, part)]
    return value


def _object_at(value: object, path: ViewPath) -> object:
    for part in path:
        kind = type(value)
        if kind is tuple:
            require(type(part) is int and 0 <= part < len(cast(tuple[object, ...], value)), 'Build object index differs')
            value = cast(tuple[object, ...], value)[cast(int, part)]
        elif kind in (dict, MappingProxyType):
            require(type(part) is str and part in cast(Mapping[str, object], value), 'Build object key differs')
            value = cast(Mapping[str, object], value)[cast(str, part)]
        else:
            require(type(part) is str and part in BUILD_FIELDS.get(kind, ()), 'Build alias left its closed object schema')
            value = object.__getattribute__(value, cast(str, part))
    return value


class _SelectionFactory:
    def __init__(self, store: ProviderViewStore, document: JsonValue, view: dict[str, JsonValue],
                 requested: SyntheticGeneratorConfig | None):
        self.store, self.document = store, document
        self.bindings: dict[ViewPath, tuple[type[object], JsonValue]] = {}
        self.objects: dict[ViewPath, object] = {}
        self.capabilities: dict[ViewPath, tuple[str, ...]] = {}
        for group in array(view['aliases']):
            raw = fields(group, 'kind paths binding')
            tag = text(raw['kind'])
            require(tag in ALIAS_TAGS, 'Unknown build alias type')
            paths = array(raw['paths'])
            require(bool(paths), 'Build alias has no paths')
            for path in paths:
                items = array(path)
                require(bool(items) and items[0] == 'selection_result'
                    and all(type(item) in (str, int) for item in items), 'Build alias left its selection root')
                self.add(ALIAS_TAGS[tag], tuple(cast(str | int, item) for item in items[1:]), raw['binding'])
        config = fields(view['selection_config'], 'kind object')
        require(config['kind'] == 'host' and requested is not None and store.resolve(config['object']) is requested,
            'Selection did not retain its actual requested configuration')
        self.add(SyntheticGeneratorConfig, ('config',), view['selection_config'])
        alternatives = array(mapping(document)['alternatives'])
        configs = array(view['alternative_configs'])
        require(len(configs) == len(alternatives), 'Selection alternative configuration census differs')
        for index, (alternative, binding) in enumerate(zip(alternatives, configs)):
            candidate = mapping(alternative)['candidate']
            if candidate is None:
                require(binding is None, 'Absent selection candidate carries a configuration binding')
            else:
                require(binding is not None, 'Selection candidate omitted its configuration binding')
                self.add(SyntheticGeneratorConfig, ('alternatives', index, 'candidate', 'generator_config'), binding)
                mechanism_path = ('alternatives', index, 'candidate', 'mechanism')
                self.capabilities[mechanism_path] = store.capabilities(view['required_capabilities'],
                    _json_at(document, (*mechanism_path, 'required_capabilities')))
        if not self.capabilities:
            require(view['required_capabilities'] is None, 'Selection without candidates carries capability origin')

    def add(self, cls: type[object], path: ViewPath, binding: JsonValue) -> None:
        require(path not in self.bindings, 'Duplicate build alias path')
        _json_at(self.document, path)
        self.bindings[path] = (cls, binding)

    def __call__(self, cls: type[T], path: ViewPath, document: JsonValue,
                 values: Mapping[str, object], /) -> T:
        if path in self.capabilities:
            require(cls is MechanismProgram, 'Selection capability slot has another class')
            values = {**values, 'required_capabilities': self.capabilities[path]}
        binding = self.bindings.get(path)
        if binding is None:
            return allocate(cls, values)
        require(binding[0] is cls, 'Build alias reaches another class')
        result = self.store.bind(cls, binding[1], document, values)
        self.objects[path] = result
        return result

    def complete(self, result: object) -> None:
        require(set(self.objects) == set(self.bindings), 'Build alias was not consumed by the structural decoder')
        for path, expected in self.objects.items():
            require(_object_at(result, path) is expected, 'Build alias differs from returned descendant identity')
        for path, expected_tuple in self.capabilities.items():
            require(_object_at(result, (*path, 'required_capabilities')) is expected_tuple,
                'Build capability origin differs from returned identity')


@dataclass(frozen=True)
class _ArtifactView:
    signature: bytes
    value: object


class BuildViewStore:
    """Bounded snapshots of actual completed builds; never recomputes a result."""
    def __init__(self, providers: ProviderViewStore, *, max_objects: int = 100_000,
                 max_retained_bytes: int = 134_217_728,
                 identity_taken: Callable[[str], bool] | None = None):
        self.providers = providers
        self.max_objects, self.max_retained_bytes = max_objects, max_retained_bytes
        self.identity_taken = identity_taken
        self.retained_bytes = 0
        self.artifacts: dict[str, _ArtifactView] = {}
        self.builds: dict[str, tuple[bytes, SyntheticBuild | ComponentBuild]] = {}

    def _retain(self, signature: bytes) -> None:
        require(len(self.artifacts) + len(self.builds) < self.max_objects, 'Build view identity limit exceeded')
        charge = len(signature) + 256
        require(self.retained_bytes + charge <= self.max_retained_bytes, 'Build view retention limit exceeded')
        self.retained_bytes += charge

    def _artifact(self, raw: JsonValue, cls: type[T], decode: Callable[[JsonValue], T]) -> T:
        envelope = fields(raw, 'value binding')
        binding = fields(envelope['binding'], 'kind identity tree')
        require(binding['kind'] == 'native', 'Completed build artifact must have a native origin')
        identity = text(binding['identity'])
        require(bool(identity) and identity not in self.builds and identity not in self.providers.native
            and (self.identity_taken is None or not self.identity_taken(identity)), 'Build artifact identity collides')
        value = checked_ordered(binding['tree'], envelope['value'])
        signature = bytes(encode_document(raw))
        previous = self.artifacts.get(identity)
        candidate = decode(value)
        require(type(candidate) is cls, 'Build artifact decoder returned another class')
        if previous is not None:
            require(previous.signature == signature and type(previous.value) is cls
                and build_shape(previous.value) == build_shape(candidate), 'Build artifact identity was rebound')
            return cast(T, previous.value)
        self._retain(signature)
        self.artifacts[identity] = _ArtifactView(signature, candidate)
        return candidate

    def decode(self, raw: JsonValue, *, kind: str, manager: PassManager,
               result: Callable[[JsonValue], PipelineResult], record: Callable[[JsonValue], StageRecord],
               requested_config: SyntheticGeneratorConfig | None) -> SyntheticBuild | ComponentBuild:
        envelope = fields(raw, 'kind identity result artifacts sources view')
        require(kind in ('synthetic', 'components') and envelope['kind'] == kind, 'Completed build kind differs')
        identity = text(envelope['identity'])
        require(bool(identity) and identity not in self.artifacts and identity not in self.providers.native
            and (self.identity_taken is None or not self.identity_taken(identity)), 'Completed build identity collides')
        signature = bytes(encode_document(raw))
        previous = self.builds.get(identity)
        if previous is not None:
            require(previous[0] == signature, 'Completed build identity was rebound')
            return previous[1]
        artifacts = fields(envelope['artifacts'], 'candidate selection_result' +
            (' assembly link_result behavior_result' if kind == 'components' else ''))
        sources = fields(envelope['sources'], 'candidate')
        source = record(sources['candidate'])
        outcome = result(envelope['result'])
        view = fields(envelope['view'], 'selection_config alternative_configs required_capabilities aliases')
        candidate_origins: dict[ViewPath, JsonValue] = {}
        candidate_identities: set[str] = set()
        selection_aliases: list[JsonValue] = []
        nodes = array(mapping(mapping(mapping(artifacts['candidate'])['value'])['mechanism'])['nodes'])
        for group in array(view['aliases']):
            entry = fields(group, 'kind paths binding')
            paths = array(entry['paths'])
            require(bool(paths), 'Build alias has no paths')
            first = array(paths[0])
            require(bool(first), 'Build alias has an empty path')
            if first[0] == 'selection_result':
                require(all(array(path)[0] == 'selection_result' for path in paths), 'Build alias mixes parsed and generated roots')
                selection_aliases.append(group)
                continue
            require(len(paths) == 1 and entry['kind'] == TypeSpec.__module__ + '.' + TypeSpec.__qualname__
                and len(first) == 6 and first[:3] == ['candidate', 'mechanism', 'nodes']
                and type(first[3]) is int and 0 <= first[3] < len(nodes)
                and first[4:] == ['output', 'dtype'], 'Candidate alias left its exact parsed type path')
            path = tuple(cast(str | int, part) for part in first[1:])
            binding = fields(entry['binding'], 'kind identity tree')
            token = text(binding['identity'])
            require(binding['kind'] == 'native' and bool(token) and token not in candidate_identities
                and path not in candidate_origins, 'Candidate parsed types reused a node origin')
            candidate_identities.add(token)
            candidate_origins[path] = entry['binding']
        require(len(candidate_origins) == len(nodes), 'Candidate parsed type origin census differs')
        candidate_factory = _ParsedCandidateFactory(cast(FrozenJson, source.payload), store=self.providers, aliases=candidate_origins)
        def decode_candidate(value: JsonValue) -> SyntheticCandidate:
            require(encode_document(value) == encode_document(_mutable(cast(FrozenJson, source.payload))),
                'Build candidate differs from its actual historical parser source')
            return BuildViews(candidate_factory).candidate(value)
        candidate = self._artifact(artifacts['candidate'], SyntheticCandidate, decode_candidate)
        candidate_factory.complete(candidate)
        # Cached candidates must still retain the exact historical source tuple
        # instances; matching contents are insufficient when a source changes.
        for index, node in enumerate(candidate.mechanism.nodes):
            for name in ('inputs', 'requirement_ids'):
                require(object.__getattribute__(node, name) is _frozen_at(cast(FrozenJson, source.payload),
                    ('mechanism', 'nodes', index, name)), 'Build candidate changed historical tuple identity')
        for name in ('outputs', 'required_capabilities'):
            require(object.__getattribute__(candidate.mechanism, name) is _frozen_at(cast(FrozenJson, source.payload),
                ('mechanism', name)), 'Build candidate changed historical program tuple identity')
        view = {**view, 'aliases': selection_aliases}
        selection_raw = fields(artifacts['selection_result'], 'value binding')
        selection: SyntheticSelectionResult | None = None
        if selection_raw['value'] is None:
            require(selection_raw['binding'] is None and view['selection_config'] is None
                and view['alternative_configs'] == [] and view['required_capabilities'] is None and view['aliases'] == [],
                'Absent build selection carries origin metadata')
        else:
            factories: list[_SelectionFactory] = []
            def decode_selection(value: JsonValue) -> SyntheticSelectionResult:
                factory = _SelectionFactory(self.providers, value, view, requested_config)
                factories.append(factory)
                return BuildViews(factory).selection(value)
            selection = self._artifact(artifacts['selection_result'], SyntheticSelectionResult, decode_selection)
            factories[0].complete(selection)
        if kind == 'synthetic':
            require(outcome.artifact is source, 'Synthetic build result differs from actual mechanism record')
            built: SyntheticBuild | ComponentBuild = synthetic_build(candidate, outcome, manager, selection)
        else:
            def decode_assembly(value: JsonValue) -> ComponentAssembly:
                require(encode_document(value) == encode_document(_mutable(cast(FrozenJson, outcome.artifact.payload))),
                    'Build assembly differs from its actual historical parser source')
                views = BuildViews()
                target = views.target(mapping(mapping(value)['composition'])['target'], ('composition', 'target'))
                return views.assembly(value, target)
            assembly = self._artifact(artifacts['assembly'], ComponentAssembly, decode_assembly)
            linked = self._artifact(artifacts['link_result'], CompositionResult, BuildViews().link_result)
            behavior = self._artifact(artifacts['behavior_result'], CheckResult, BuildViews().check_result)
            built = component_build(candidate, assembly, linked, outcome, manager, behavior, selection)
        self._retain(signature)
        self.builds[identity] = (signature, built)
        return built
