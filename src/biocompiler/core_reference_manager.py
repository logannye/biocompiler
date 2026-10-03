"""Explicit persistent Core facade for the checked reference workflows.

The existing public manager methods remain the observable orchestration surface.
Native phases derive contracts, run providers, check results and own acceptance;
Python retains authoring objects and reconstructs their source-bound views.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import sys
from types import MappingProxyType
from typing import Any, cast

from biocompiler.compiler.construct import ConstructBuild
from biocompiler.compiler.molecular import MolecularBuild
from biocompiler.compiler.pipeline import (
    ComponentInputContract, CompletionProfile, PassContract, PassManager,
    PipelineResult, ScopedObligation, StageRecord,
)
from biocompiler.core_client import CoreClient, CoreProtocolError, JsonValue
from biocompiler.core_pipeline_callback_session import _nodes
from biocompiler.core_pipeline_manager import (
    ComponentPreparation, ComponentRegistration, CorePassManager, _NativeProvider,
    _contract_view, _identity, _literal_json, _object, _ordered, _profile_view,
    _register_reference_manager_type, _require, capability_profile,
)
from biocompiler.core_pipeline_provider_views import FrozenJson, array, checked_ordered
from biocompiler.core_pipeline_session import decode_document, encode_document
from biocompiler.core_reference_host import ReferenceHost, HostValue, NativeDefault, sorted_source_links_equal
from biocompiler.core_reference_provider_views import (
    REFERENCE_PROVIDER_ROLES, ReferenceBuildStore, ReferenceOrigins, ReferenceProviderViews,
)
from biocompiler.core_reference_views import ReferenceViews
from biocompiler.errors import SerializationError
from biocompiler.ir.construct import ConstructCandidate, ConstructRequest
from biocompiler.pipeline_callback_objects import HostCompletion
from biocompiler.registry.components import ComponentRegistry
from biocompiler.registry.references import ReferenceManifest


@dataclass(frozen=True)
class ReferenceAdmission:
    contract: ComponentInputContract
    validators: Mapping[str, Callable[..., Any]]


@dataclass(frozen=True)
class _InvocationOrigin:
    role: str
    sequence: int
    origins: ReferenceOrigins


@dataclass(frozen=True)
class _HostOutput:
    value: HostValue
    role: str
    sequence: int


@dataclass(frozen=True)
class _HostProposal:
    value: object
    role: str
    sequence: int


@dataclass(eq=False)
class _FinalSource:
    upstream: object
    reference: JsonValue
    sequence: int | None = None
    phase: int = 0
    checked: tuple[JsonValue, object] | None = None
    check_valid: bool = False
    returned: tuple[JsonValue, object] | None = None


def _upstream_candidate(upstream: Any) -> Any:
    return upstream.candidate


def _upstream_check_candidate(upstream: Any) -> tuple[Any, JsonValue]:
    candidate = upstream.candidate
    if not isinstance(candidate, ConstructCandidate):
        return candidate, None
    _require(type(candidate) is ConstructCandidate, 'Custom reference checker inputs require a deferred profile')
    return candidate, candidate.to_dict()


_SLOTS = {
    'reference_components': (('reference_authority', 'reference_components.authority'),
                             ('component_linkage', 'reference_components.linkage')),
    'components_to_construct': (('layout', 'components_to_construct.layout'),
                                ('layout_composition', 'reference_components.linkage')),
    'construct_to_molecular': (('sequence_identity', 'construct_to_molecular.sequence'),
                               ('encoding_composition', 'construct_to_molecular.composition')),
}


class ReferenceCorePassManager(CorePassManager):
    """One actual Core manager, retained by both public reference Build objects."""
    _EXTRA_ACTIONS = CorePassManager._EXTRA_ACTIONS + (
        'reference-generate', 'reference-emit', 'reference-proposal', 'reference-source-links-equal',
        'reference-upstream-candidate')

    def __init__(self, *args: Any, **kwargs: Any):
        raise TypeError('Use ReferenceCorePassManager.from_construct or from_molecular.')

    @classmethod
    def from_construct(cls, core: CoreClient, request: ConstructRequest, registry: ComponentRegistry,
                       manifests: Mapping[str, ReferenceManifest], *, limits: JsonValue = None,
                       manager_limits: JsonValue = None) -> ConstructBuild:
        manager = cls._initialize(core, request, registry, manifests, molecular=False,
                                  limits=limits, manager_limits=manager_limits)
        return manager._complete_construct()

    @classmethod
    def from_molecular(cls, core: CoreClient, request: ConstructRequest, registry: ComponentRegistry,
                       manifests: Mapping[str, ReferenceManifest], *, limits: JsonValue = None,
                       manager_limits: JsonValue = None) -> MolecularBuild:
        manager = cls._initialize(core, request, registry, manifests, molecular=True,
                                  limits=limits, manager_limits=manager_limits)
        upstream = manager._complete_construct()
        return manager.complete_molecular(upstream)

    @classmethod
    def _initialize(cls, core: CoreClient, request: ConstructRequest, registry: ComponentRegistry,
                    manifests: Mapping[str, ReferenceManifest], *, molecular: bool,
                    limits: JsonValue, manager_limits: JsonValue,
                    _molecular_snapshot: Mapping[str, ReferenceManifest] | None = None) -> ReferenceCorePassManager:
        _require(cls is ReferenceCorePassManager, 'Reference native factories require their exact installed class')
        # Molecular takes its first map snapshot before entering Construct's
        # authoring preflight. No fingerprint, parser or checker runs here.
        if molecular and not isinstance(manifests, Mapping):
            raise SerializationError('Expected a reference manifest mapping.')
        _require(_molecular_snapshot is None or (molecular and type(_molecular_snapshot) is MappingProxyType
            and manifests is _molecular_snapshot), 'Reference upstream snapshot changed its actual owner')
        outer = (_molecular_snapshot if _molecular_snapshot is not None else
                 dict(manifests) if molecular else manifests)
        if not isinstance(request, ConstructRequest):
            raise SerializationError('Expected a frozen ConstructRequest.')
        if not isinstance(registry, ComponentRegistry):
            raise SerializationError('Expected an immutable component registry.')
        if not isinstance(outer, Mapping) or not all(isinstance(key, str) and isinstance(value, ReferenceManifest)
                                                     for key, value in outer.items()):
            raise SerializationError('Expected a reference-set ID to manifest mapping.')
        _require(type(request) is ConstructRequest and type(registry) is ComponentRegistry
                 and all(type(key) is str and type(value) is ReferenceManifest for key, value in outer.items()),
                 'Custom reference authoring subclasses require a deferred profile')
        host = (ReferenceHost(request, registry, MappingProxyType(dict(outer)), _molecular_snapshot)
                if _molecular_snapshot is not None else
                ReferenceHost.for_molecular(request, registry, outer) if molecular else
                ReferenceHost.for_construct(request, registry, outer))
        manager = cls.__new__(cls)
        manager._reference_prepare(core, host=host, limits=limits)
        manager._target = request.composition.target
        manager._fixed_initialization = 'reference'
        try:
            request_document = request.to_dict()
            registry_document = registry.to_dict()
            manifests_document: list[JsonValue] = [[key, value.to_dict()]
                for key, value in host.construct_manifests.items()]
            manager._fixed_target_document = request_document['target']
            objects = manager._objects
            result = manager._call('initialize-reference', {
                'request': request_document, 'request_tree': _ordered(request_document),
                'registry': registry_document, 'registry_tree': _ordered(registry_document),
                'manifests': manifests_document, 'manifests_tree': _ordered(manifests_document),
                'manager_limits': manager_limits, 'target_object': objects.retain(manager._target),
                'request_object': objects.retain(request), 'registry_object': objects.retain(registry),
                'construct_manifests_object': objects.retain(host.construct_manifests),
                'molecular_manifests_object': None if host.molecular_manifests is None else objects.retain(host.molecular_manifests),
                'policy_objects': {name: objects.retain(host.origin(name)) for name in
                    ('translation_policy', 'encoding_policy', 'evidence_policy')},
            })
            _require(manager._fixed_manager_published, 'Reference initialization omitted its actual manager publication')
            completed = _object(result, {'kind', 'manager', 'artifacts', 'target'}, 'Reference initialization')
            _require(completed['artifacts'] == [] and encode_document(completed['target']) == manager._fixed_target_envelope,
                     'Reference initialization changed its published target or artifact census')
            manager._initialization(result, 'reference')
        except BaseException:
            response = manager.session.last_response
            retained = (manager._fixed_manager_published and not manager.session.closed
                and not manager.session.invalidated and response is not None
                and response.operation == 'initialize-reference' and response.status in ('rejected', 'raise'))
            if not retained:
                manager.session._invalidate()
                manager._objects.close()
            raise
        finally:
            manager._fixed_initialization = None
            manager._fixed_target_document = None
        return manager

    def _reference_prepare(self, core: CoreClient, *, host: ReferenceHost, limits: JsonValue = None) -> None:
        self._reference_host = host
        self._reference_molecular_host = host
        self._reference_origins: dict[int, _InvocationOrigin] = {}
        self._reference_outputs: dict[int, _HostOutput] = {}
        self._reference_proposals: dict[int, _HostProposal] = {}
        self._reference_final: _FinalSource | None = None
        self._reference_build_origins: dict[str, tuple[JsonValue, object]] = {}
        self._reference_builds: dict[str, ConstructBuild | MolecularBuild] = {}
        self._reference_origin_bytes = 0
        self._reference_binding_bytes = 0
        self._reference_pending_bytes = 0
        self._reference_generate_callable = host.generate
        self._reference_emit_callable = host.emit
        self._reference_proposal_callable = host.proposal
        self._reference_molecular_proposal_callable = host.proposal
        self._reference_links_callable = sorted_source_links_equal
        self._prepare(core, application=capability_profile(), limits=limits)
        self._reference_provider_views = ReferenceProviderViews(self._objects.resolve)
        self._reference_build_views = ReferenceBuildStore(max_objects=self._objects.limits.max_objects,
            max_retained_bytes=self._session._limits['max_retained_bytes'],
            identity_taken=lambda identity: identity in self._bindings or identity in self._provider_views.native
                or identity in self._build_views.artifacts or identity in self._build_views.builds,
            reserve=self._reference_retention)

    def _reference_retention(self, additional: int = 0) -> None:
        # Same channel reductions and cumulative, no-refund lifetime. The broker
        # separately bounds actual retained handles and arbitrary host callbacks.
        used = (additional + self._reference_origin_bytes + self._reference_build_views.retained_bytes
                + self._reference_binding_bytes + self._reference_pending_bytes + self._result_retained_bytes)
        _require(used <= self._session._limits['max_retained_bytes'], 'Reference view shared retention limit exceeded')

    def _binding(self, binding: Any, *, flavor: str = 'json') -> Any:
        # Every new inherited record/context binding consumes the same allowance
        # as reference origins and Builds. Reserve before the closed decoder can
        # allocate its containers, and reject cross-cache capability collisions.
        if type(binding) is dict and binding.get('kind') == 'native':
            value = _object(binding, {'kind', 'identity', 'tree'}, 'Native reference binding')
            identity = _identity(value['identity'])
            _require(identity not in self._reference_build_views.roots
                and identity not in self._reference_build_views.builds,
                'Native binding identity collides with a reference typed view')
            if identity not in self._bindings:
                charge = len(encode_document(value['tree'])) + 256 * _nodes(value['tree']) + 256
                self._reference_retention(charge)
                self._reference_binding_bytes += charge
        return super()._binding(binding, flavor=flavor)

    def _result_value(self, raw: JsonValue) -> PipelineResult:
        # Core.result retains this exact envelope immediately after hydration.
        # Keep that future receipt reserved while nested record bindings allocate;
        # the inherited receipt counter takes over before returning publicly.
        charge = len(encode_document(raw)) + 256
        self._reference_retention(charge)
        self._reference_pending_bytes += charge
        try:
            return cast(PipelineResult, super()._result_value(raw))
        finally:
            self._reference_pending_bytes -= charge

    def _reference_sequence(self) -> int:
        _require(bool(self._session._handlers), 'Reference action has no actual native command owner')
        return self._session._handlers[-1].sequence

    def _reference_provider(self, raw: JsonValue, role: str) -> Callable[..., Any]:
        value = self._objects.resolve(raw)
        _require(type(value) is _NativeProvider and value._manager is self
            and self._native_providers.get(value._identity) is value
            and self._native_provider_roles[value._identity] == role,
            'Reference registration changed an actual native provider role or owner')
        return cast(Callable[..., Any], value)

    def _reference_validators(self, raw: JsonValue, contract: Any) -> dict[str, Callable[..., Any]]:
        _require(type(raw) is list and contract.id in _SLOTS, 'Unknown reference registration contract')
        items = array(raw)
        expected = _SLOTS[contract.id]
        _require(len(items) == len(expected), 'Reference validator census differs')
        result: dict[str, Callable[..., Any]] = {}
        for item, (name, role) in zip(items, expected):
            pair = array(item)
            _require(type(pair) is list and len(pair) == 2 and pair[0] == name,
                     'Reference validator order or slot differs')
            result[name] = self._reference_provider(pair[1], role)
        _require(tuple(check.id for check in contract.checks) == tuple(result),
                 'Reference validator declarations differ from actual slots')
        return result

    def _reference_obligations(self, raw: JsonValue, declared: Any) -> tuple[ScopedObligation, ...]:
        _require(type(raw) is list and len(raw) == len(declared), 'Reference obligation origin census differs')
        values = []
        for binding, original in zip(array(raw), declared):
            item = _object(binding, {'kind', 'identity', 'tree'}, 'Reference obligation origin')
            _require(item['kind'] == 'native', 'Reference declaration requires native obligation origins')
            value = self._binding(binding, flavor='obligation')
            _require(type(value) is ScopedObligation and vars(value) == vars(original),
                     'Reference obligation differs from its native declaration')
            values.append(value)
        return tuple(values)

    def reference_admission(self) -> ReferenceAdmission:
        return cast(ReferenceAdmission, self._view(self._reference_admission,
            self._call('reference-admission', {}), 'reference admission'))

    def _reference_admission(self, raw: JsonValue) -> ReferenceAdmission:
        value = _object(raw, {'contract', 'validators', 'obligation_objects'}, 'Reference admission')
        contract = _contract_view(value['contract'], admission=True)
        _require(contract.id == 'reference_components', 'Unexpected reference admission contract')
        object.__setattr__(contract, 'obligations', self._reference_obligations(value['obligation_objects'], contract.obligations))
        return ReferenceAdmission(contract, self._reference_validators(value['validators'], contract))

    def reference_registration(self) -> ComponentRegistration:
        return cast(ComponentRegistration, self._view(lambda value: self._reference_registration(value,
            expected='components_to_construct'), self._call('reference-registration', {}), 'reference registration'))

    def _reference_registration(self, raw: JsonValue, *, expected: str) -> ComponentRegistration:
        value = _object(raw, {'contract', 'producer', 'validators', 'obligation_objects'}, 'Reference registration')
        contract = _contract_view(value['contract'], admission=False)
        _require(contract.id == expected, 'Unexpected reference pass contract')
        object.__setattr__(contract, 'introduces', self._reference_obligations(value['obligation_objects'], contract.introduces))
        return ComponentRegistration(contract, self._reference_provider(value['producer'], expected + '.producer'),
                                     self._reference_validators(value['validators'], contract))

    def _complete_construct(self) -> ConstructBuild:
        admission = self.reference_admission()
        self.register_component_input(admission.contract, admission.validators)
        self.admit_component_input(admission.contract.id, 'components', self._reference_host.request)
        self.get('components')
        registration = self.reference_registration()
        self.register(registration.contract, registration.producer, registration.validators)
        record = self.run(registration.contract.id, 'components', 'construct')
        result = self.result('construct', scope='reference_construct')
        return self.finish_reference_construct(record, result)

    def prepare_reference_molecular(self) -> ComponentPreparation:
        return cast(ComponentPreparation, self._view(self._component_preparation,
            self._call('prepare-reference-molecular', {}), 'reference Molecular preparation'))

    def reference_molecular_profile(self, preparation: ComponentPreparation) -> CompletionProfile:
        return cast(CompletionProfile, self._view(_profile_view, self._call('reference-molecular-profile',
            {'preparation_id': self._preparation_id(preparation)}), 'reference Molecular profile'))

    def reference_molecular_registration(self, preparation: ComponentPreparation) -> ComponentRegistration:
        return cast(ComponentRegistration, self._view(lambda value: self._reference_registration(value,
            expected='construct_to_molecular'), self._call('reference-molecular-registration',
            {'preparation_id': self._preparation_id(preparation)}), 'reference Molecular registration'))

    def complete_molecular(self, upstream: ConstructBuild) -> MolecularBuild:
        _require(type(upstream) is ConstructBuild and self._reference_builds.get('construct') is upstream
            and upstream.manager is self and self._reference_host.molecular_manifests is not None,
            'Molecular continuation requires its actual upstream reference build and snapshot')
        preparation = self.prepare_reference_molecular()
        return self._continue_molecular(preparation, upstream)

    def prepare_reference_molecular_public(self, request: ConstructRequest, registry: ComponentRegistry,
            snapshot: Mapping[str, ReferenceManifest]) -> ComponentPreparation:
        """Bind current Molecular authority separately from Construct provenance."""
        _require(type(request) is ConstructRequest and type(registry) is ComponentRegistry
            and type(snapshot) is MappingProxyType,
            'Public Molecular preparation requires its original typed authority and snapshot')
        host = ReferenceHost(request, registry, self._reference_host.construct_manifests, snapshot)
        request_document, registry_document = request.to_dict(), registry.to_dict()
        manifests_document: list[JsonValue] = [[key, value.to_dict()] for key, value in snapshot.items()]
        authority: JsonValue = [request_document, registry_document, manifests_document]
        charge = len(encode_document(authority)) + 256 * _nodes(authority) + 1024
        self._reference_retention(charge)
        self._reference_origin_bytes += charge
        objects = self._objects
        raw = self._call('prepare-reference-molecular-public', {
            'request': request_document, 'request_tree': _ordered(request_document),
            'registry': registry_document, 'registry_tree': _ordered(registry_document),
            'manifests': manifests_document, 'manifests_tree': _ordered(manifests_document),
            'request_object': objects.retain(request), 'registry_object': objects.retain(registry),
            'molecular_manifests_object': objects.retain(snapshot),
            'policy_objects': {name: objects.retain(host.origin(name)) for name in
                ('translation_policy', 'encoding_policy', 'evidence_policy')},
        })
        self._reference_molecular_host = host
        self._reference_emit_callable = host.emit
        self._reference_molecular_proposal_callable = host.proposal
        return cast(ComponentPreparation, self._view(self._component_preparation, raw,
                                                     'public reference Molecular preparation'))

    def complete_molecular_public(self, upstream: object, request: ConstructRequest,
            registry: ComponentRegistry, snapshot: Mapping[str, ReferenceManifest]) -> MolecularBuild:
        # The public route has already read upstream.manager at the original
        # source point. Do not inspect any other upstream fields here.
        preparation = self.prepare_reference_molecular_public(request, registry, snapshot)
        return self._continue_molecular(preparation, upstream)

    def _continue_molecular(self, preparation: ComponentPreparation, upstream: object) -> MolecularBuild:
        for key, identity in preparation.dependencies:
            self.set_dependency(key, identity)
        self.register_completion_profile(self.reference_molecular_profile(preparation))
        registration = self.reference_molecular_registration(preparation)
        self.register(registration.contract, registration.producer, registration.validators)
        record = self.run(registration.contract.id, 'construct', 'molecular')
        result = self.result('molecular', scope='exact_cds')
        return self.finish_reference_molecular(preparation, record, result, upstream=upstream)

    def _reference_finish_arguments(self, record: StageRecord, result: PipelineResult) -> dict[str, JsonValue]:
        receipt = self._result_receipts.get(id(result))
        _require(type(record) is StageRecord and type(result) is PipelineResult and receipt is not None
            and receipt[0] is result and result.artifact is record and self._records.get(record.id) is record,
            'Reference finish requires its actual run record and public result')
        assert receipt is not None
        return {'record_id': self._record_bindings[record.id][0], 'result_sequence': receipt[1]}

    def finish_reference_construct(self, record: StageRecord, result: PipelineResult) -> ConstructBuild:
        raw = self._call('finish-reference-construct', self._reference_finish_arguments(record, result))
        return cast(ConstructBuild, self._reference_build(raw, kind='construct', result=result))

    def finish_reference_molecular(self, preparation: ComponentPreparation, record: StageRecord,
                                  result: PipelineResult, *, upstream: object | None = None) -> MolecularBuild:
        args = self._reference_finish_arguments(record, result)
        args['preparation_id'] = self._preparation_id(preparation)
        args['upstream'] = None if upstream is None else self._objects.retain(upstream)
        _require(self._reference_final is None, 'Reference finish cannot replace an active source invocation')
        source = None if upstream is None else _FinalSource(upstream, args['upstream'])
        self._reference_final = source
        try:
            raw = self._call('finish-reference-molecular', args)
            if source is not None:
                response = self.session.last_response
                _require(source.phase == 2 and source.returned is not None and response is not None
                    and source.sequence == response.sequence,
                    'Reference finish omitted its exact two source candidate reads')
                assert source.returned is not None
                identity = _identity(_object(raw, {'build_id', 'kind', 'candidate', 'check_result', 'result',
                    'construct'}, 'Reference Molecular Build')['build_id'])
                _require(identity not in self._reference_build_origins, 'Reference source Build origin was reused')
                self._reference_build_origins[identity] = source.returned
            return cast(MolecularBuild, self._reference_build(raw, kind='molecular', result=result))
        except CoreProtocolError:
            self._session._invalidate()
            raise
        finally:
            self._reference_final = None

    def _reference_build(self, raw: JsonValue, *, kind: str, result: PipelineResult) -> ConstructBuild | MolecularBuild:
        def hydrate(value: JsonValue) -> ConstructBuild | MolecularBuild:
            item = _object(value, {'build_id', 'kind', 'candidate', 'check_result', 'result', 'construct'}, 'Reference Build')
            _require(item['kind'] == kind, 'Reference finish changed its build kind')
            receipt = self._result_receipts.get(id(result))
            _require(receipt is not None and receipt[0] is result, 'Reference Build lost its exact public result')
            assert receipt is not None
            upstream = self._reference_builds.get('construct') if kind == 'molecular' else None
            origin = self._reference_build_origins.get(_identity(item['build_id']))
            self._reference_retention()
            built = self._reference_build_views.decode(value, manager=self, result=result,
                result_envelope=decode_document(receipt[2]), upstream=upstream if origin is None else None,
                construct_origin=origin)
            self._reference_retention()
            previous = self._reference_builds.get(kind)
            _require(previous is None or previous is built, 'Reference completed Build was replaced')
            self._reference_builds[kind] = built
            return built
        return cast(ConstructBuild | MolecularBuild, self._view(hydrate, raw, 'reference Build'))

    def reference_build_result(self, kind: str) -> ConstructBuild | MolecularBuild:
        _require(kind in ('construct', 'molecular') and kind in self._reference_builds,
                 'Reference Build has not completed on this manager')
        built = self._reference_builds[kind]
        return self._reference_build(self._call('reference-build-result', {'kind': kind}), kind=kind, result=built.result)

    def _invoke(self, action: str, arguments: JsonValue) -> HostCompletion:
        if action == 'native-provider':
            args = _object(arguments, {'provider_id', 'role'}, 'Native reference provider')
            if type(args['role']) is str and args['role'] in REFERENCE_PROVIDER_ROLES:
                identity, role = _identity(args['provider_id']), args['role']
                previous = self._native_providers.get(identity)
                if previous is None:
                    _require(len(self._native_providers) < self._objects.limits.max_providers,
                             'Reference native provider limit exceeded')
                    previous = _NativeProvider(self, identity)
                    self._native_providers[identity] = previous
                    self._native_provider_roles[identity] = role
                else:
                    _require(self._native_provider_roles[identity] == role, 'Reference native provider role was rebound')
                return self._ok(self._objects.retain(previous))
        if action == 'reference-upstream-candidate':
            args = _object(arguments, {'upstream', 'phase'}, 'Reference final source read')
            final_source = self._reference_final
            _require(final_source is not None and self._objects.resolve(args['upstream']) is final_source.upstream
                and encode_document(args['upstream']) == encode_document(final_source.reference),
                'Reference final source belongs to another upstream invocation')
            assert final_source is not None
            sequence = self._reference_sequence()
            _require(final_source.sequence is None or final_source.sequence == sequence,
                'Reference final source belongs to another command')
            final_source.sequence = sequence
            if args['phase'] == 'check':
                _require(final_source.phase == 0, 'Reference final check read was repeated or reordered')
                final_source.phase = 1
                completion = self._host_call(_upstream_check_candidate, final_source.upstream)
                if completion.status != 'ok':
                    return completion
                pair = self._objects.resolve(completion.value)
                _require(type(pair) is tuple and len(pair) == 2, 'Reference source check returned an invalid pair')
                candidate, document = pair
                charge = len(encode_document(document)) + 256 * _nodes(document) + 256
                self._reference_retention(charge)
                self._reference_origin_bytes += charge
                reference = self._objects.retain(candidate)
                final_source.checked, final_source.check_valid = (reference, candidate), document is not None
                return self._ok({'object': reference, 'value': document, 'tree': _ordered(document)})
            _require(args['phase'] == 'return' and final_source.phase == 1 and final_source.checked is not None
                and final_source.check_valid, 'Reference final return read was repeated, reordered or lacks a valid check input')
            final_source.phase = 2
            completion = self._host_call(_upstream_candidate, final_source.upstream)
            if completion.status != 'ok':
                return completion
            charge = 256
            self._reference_retention(charge)
            self._reference_origin_bytes += charge
            final_source.returned = (completion.value, self._objects.resolve(completion.value))
            return self._ok({'object': completion.value})
        if action in ('reference-generate', 'reference-emit'):
            args = _object(arguments, {'input', 'argument', 'tree'}, 'Reference producer input')
            document = checked_ordered(args['tree'], args['argument'])
            charge = (len(encode_document(args['input'])) + len(encode_document(document))
                      + 256 * _nodes(document) + 256)
            self._reference_retention(charge)
            self._reference_origin_bytes += charge
            decoder = ReferenceViews()
            host = self._reference_host if action == 'reference-generate' else self._reference_molecular_host
            function: Callable[[Any], NativeDefault | HostValue]
            if action == 'reference-generate':
                parsed: ConstructRequest | ConstructCandidate = decoder.construct_request(document)
                origins = ReferenceOrigins.construct(parsed, args['input'], parsed_document=document)
                function, role, expected_default = self._reference_generate_callable, 'components_to_construct.producer', NativeDefault.GENERATE
            else:
                parsed = decoder.construct_candidate(document)
                origins = ReferenceOrigins.molecular(parsed, args['input'], parsed_document=document, request=host.request,
                    translation_policy=host.origin('translation_policy'), encoding_policy=host.origin('encoding_policy'),
                    evidence_policy=host.origin('evidence_policy'))
                function, role, expected_default = self._reference_emit_callable, 'construct_to_molecular.producer', NativeDefault.EMIT
            sequence = self._reference_sequence()
            reference = self._objects.retain(parsed)
            self._reference_origins[id(parsed)] = _InvocationOrigin(role, sequence, origins)
            completion = self._host_call(function, parsed)
            if completion.status != 'ok':
                return completion
            output = self._objects.resolve(completion.value)
            if output is expected_default:
                return self._ok({'kind': 'native', 'argument': reference, 'output': None})
            _require(type(output) is HostValue, 'Reference producer callback returned an unknown route')
            self._reference_outputs[id(output)] = _HostOutput(output, role, sequence)
            return self._ok({'kind': 'host', 'argument': reference, 'output': self._objects.retain(output)})
        if action == 'reference-proposal':
            args = _object(arguments, {'output', 'source_links'}, 'Reference paired proposal')
            output = self._objects.resolve(args['output'])
            source = self._reference_outputs.get(id(output))
            _require(source is not None and source.value is output and source.sequence == self._reference_sequence(),
                     'Reference proposal output belongs to another invocation')
            assert source is not None
            _require(type(args['source_links']) is list, 'Reference source links require a complete array')
            decoder = ReferenceViews()
            links = tuple(decoder.source_link(value, ('source_links', index)) for index, value in enumerate(args['source_links']))
            proposal_function = (self._reference_proposal_callable if source.role == 'components_to_construct.producer'
                        else self._reference_molecular_proposal_callable)
            completion = self._host_call(proposal_function, output, links)
            if completion.status != 'ok':
                return completion
            proposal = self._objects.resolve(completion.value)
            self._reference_proposals[id(proposal)] = _HostProposal(proposal, source.role, source.sequence)
            return self._ok(completion.value)
        if action == 'reference-source-links-equal':
            args = _object(arguments, {'actual', 'expected'}, 'Reference source-link comparison')
            _require(type(args['actual']) is list and type(args['expected']) is list, 'Reference source-link comparison requires arrays')
            actual = [self._objects.resolve(item) for item in args['actual']]
            decoder = ReferenceViews()
            expected = [decoder.source_link(item, ('expected', index)) for index, item in enumerate(args['expected'])]
            return self._host_observation(self._host_call(self._reference_links_callable, actual, expected))
        return super()._invoke(action, arguments)

    def _native_return(self, value: JsonValue, *, role: str, input_payload: FrozenJson = None) -> Any:
        if role not in REFERENCE_PROVIDER_ROLES:
            return super()._native_return(value, role=role, input_payload=input_payload)
        def hydrate(raw: JsonValue) -> object:
            item = cast(dict[str, Any], raw)
            _require(type(item) is dict, 'Malformed reference provider result')
            response = self.session.last_response
            _require(response is not None and response.operation == 'call-native-provider',
                     'Reference provider reply lacks its actual command receipt')
            assert response is not None
            origins = None
            paired = None
            if item.get('kind') == 'host':
                proposal = self._objects.resolve(item.get('object'))
                host = self._reference_proposals.get(id(proposal))
                _require(host is not None and host.value is proposal and host.role == role
                         and host.sequence == response.sequence, 'Reference host proposal belongs to another provider command')
                paired = proposal
            elif item.get('kind') == 'proposal':
                view = _object(item.get('view'), {'role', 'tree', 'origins'}, 'Reference provider view')
                roots = view['origins']
                _require(type(roots) is dict and 'parsed' in roots, 'Reference proposal lacks its actual parsed input')
                parsed = self._objects.resolve(roots['parsed'])
                entry = self._reference_origins.get(id(parsed))
                _require(entry is not None and entry.origins.parsed is parsed and entry.role == role
                         and entry.sequence == response.sequence, 'Reference parsed input belongs to another provider command')
                assert entry is not None
                origins = entry.origins
            return self._reference_provider_views.decode(raw, role=role, origins=origins,
                input_document=_literal_json(input_payload), host_result=paired)
        return self._view(hydrate, value, 'reference provider result')


_register_reference_manager_type(ReferenceCorePassManager, sys.modules[__name__])
