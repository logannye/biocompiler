"""Explicit native manager adapter and process-local typed inspection views.

The native process owns registration, freshness, checks and acceptance. Retained
Python objects support trusted authoring and callbacks at native-requested stages.
This opt-in adapter does not change the default Python manager or fixed pipelines.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
from types import MappingProxyType
from typing import Any, cast

from biocompiler.artifacts.provenance import SourceLink
from biocompiler.compiler.passes import PassResult
from biocompiler.compiler.request import RealizationRequest
from biocompiler.compiler.pipeline import (
    ArtifactStatus, CheckDecision, CompletionProfile, ComponentInputContract,
    NoCandidateFound, PassContext, PassContract, PassManager, PipelineError,
    PipelineResult, ScopedObligation, StageRecord,
)
from biocompiler.core_client import CoreClient, CoreProtocolError, JsonValue
from biocompiler.core_pipeline_callback_session import (
    CallbackRejected, CallbackResponse, CorePipelineCallbackSession, _BROKER_ACTIONS,
)
from biocompiler.core_pipeline_session import decode_document, encode_document
from biocompiler.errors import SerializationError, UnsupportedBehaviorError
from biocompiler.ir.stages import Stage
from biocompiler.pipeline_callback_objects import CallbackObjects, HostCompletion
from biocompiler.semantics.context import HumanTargetContext, TargetContext
from biocompiler.semantics.evaluator import InputFrame
from biocompiler.synthesis.synthetic import SyntheticGeneratorConfig
from biocompiler.verification.evidence import CheckOutcome, EvidenceKind, Obligation

_APPLICATION_JSON = "{\"acceptance\":\"native_manager_checks_and_freshness_only;inspection_and_host_sidecars_cannot_import_accepted_records\",\"actions\":{\"hydrate-context\":{\"fields\":[\"context_id\",\"document\",\"bindings\"],\"result\":\"object_reference\"},\"native-provider\":{\"fields\":[\"provider_id\"],\"result\":\"object_reference\"},\"ordered-json\":{\"fields\":[\"object\"],\"result\":\"ordered_tree\"},\"provider-reference\":{\"fields\":[\"object\"],\"result\":\"host_or_native_provider_reference\"},\"set-equal\":{\"fields\":[\"object\",\"values\"],\"result\":\"boolean\"},\"source-link-set-equal\":{\"fields\":[\"objects\",\"expected\"],\"result\":\"boolean\"}},\"argument\":\"--pipeline-callback-session-v1\",\"authoring_boundary\":\"canonical_typed_contract_target_profile_fields;opaque_payload_configuration_provider_and_validator_objects_are_read_at_native_requested_points\",\"bindings\":{\"host\":[\"kind\",\"object\"],\"native\":[\"kind\",\"identity\",\"tree\"]},\"broker_actions\":{\"attr\":{\"fields\":[\"object\",\"name\"],\"result\":\"object_reference\"},\"attr-default\":{\"fields\":[\"object\",\"name\",\"default\"],\"result\":\"object_reference\"},\"bind-provider\":{\"fields\":[\"provider_id\",\"object\"],\"result\":\"null\"},\"call\":{\"fields\":[\"callable\",\"args\",\"kwargs\"],\"result\":\"object_reference\"},\"call-provider\":{\"fields\":[\"provider_id\",\"context\"],\"result\":\"object_reference\"},\"callable\":{\"fields\":[\"object\"],\"result\":\"boolean\"},\"compare\":{\"fields\":[\"left\",\"right\",\"operator\"],\"result\":\"boolean\"},\"contains\":{\"fields\":[\"container\",\"item\"],\"result\":\"boolean\"},\"dict\":{\"fields\":[\"object\"],\"result\":\"object_reference\"},\"document\":{\"fields\":[\"object\"],\"result\":\"object_reference\"},\"enum\":{\"fields\":[\"type\",\"value\"],\"result\":\"object_reference\"},\"freeze-json\":{\"fields\":[\"object\"],\"result\":\"object_reference\"},\"get-item\":{\"fields\":[\"object\",\"key\"],\"result\":\"object_reference\"},\"is-instance\":{\"fields\":[\"object\",\"type\"],\"result\":\"boolean\"},\"is-none\":{\"fields\":[\"object\"],\"result\":\"boolean\"},\"iter\":{\"fields\":[\"object\"],\"result\":\"object_reference\"},\"json\":{\"fields\":[\"object\"],\"result\":\"json\"},\"len\":{\"fields\":[\"object\"],\"result\":\"integer\"},\"list\":{\"fields\":[\"object\"],\"result\":\"object_reference\"},\"literal\":{\"fields\":[\"kind\",\"value\"],\"result\":\"object_reference\"},\"lookup\":{\"fields\":[\"object\",\"entries\"],\"result\":\"object_reference\"},\"mapping-items\":{\"fields\":[\"object\"],\"result\":\"object_reference\"},\"mapping-keys\":{\"fields\":[\"object\"],\"result\":\"object_reference\"},\"mapping-values\":{\"fields\":[\"object\"],\"result\":\"object_reference\"},\"merge\":{\"fields\":[\"object\",\"before\",\"after\"],\"result\":\"object_reference\"},\"next\":{\"fields\":[\"object\"],\"result\":\"iterator_step\"},\"release\":{\"fields\":[\"handles\"],\"result\":\"null\"},\"set-attribute-equal\":{\"fields\":[\"objects\",\"name\",\"values\"],\"result\":\"boolean\"},\"truth\":{\"fields\":[\"object\"],\"result\":\"boolean\"},\"tuple\":{\"fields\":[\"object\"],\"result\":\"object_reference\"},\"vars\":{\"fields\":[\"object\"],\"result\":\"object_reference\"}},\"channel\":\"biocompiler.pipeline_callback_channel.v1\",\"claim_scope\":\"software_contract_conditional_translation_and_scoped_completion;no_empirical_or_human_use_acceptance\",\"comparison_operators\":[\"eq\",\"ne\",\"is\",\"is-not\"],\"compatibility_pending\":[\"complete_original_installed_replay\",\"fixed_public_registration_interception\",\"arbitrary_authoring_subclass_and_scalar_operator_semantics\",\"default_cutover\"],\"context_bindings\":[\"input\",\"output\",\"target\",\"configuration\",\"dependencies\",\"requirements\",\"source_links\",\"observation_map\"],\"context_identity\":\"actual_native_context_physical_identity;distinct_producer_and_validation_contexts;one_validation_context_shared_by_its_validators\",\"dependencies_encoding\":\"ordered_unique_string_identity_pairs\",\"enum_types\":[\"EvidenceKind\",\"CheckOutcome\",\"Stage\",\"ArtifactStatus\",\"PayloadFormat\"],\"executable\":\"core\",\"expected_rejection_fields\":[\"module\",\"type\",\"message\",\"attributes\"],\"failure\":\"expected_logical_rejection_and_opaque_host_exception_preserve_actual_partial_manager;malformed_resource_internal_or_uncertain_io_failure_closes_authority\",\"host_execution\":\"trusted_host_code_cpu_and_opaque_captures_outside_native_work_and_json_memory_bounds\",\"iterator_step_fields\":[\"exhausted\",\"object\"],\"lifecycle\":\"one_initialization_attempt_per_channel;existing_channel_close_is_top_level_only;no_reconnect_retry_or_state_import\",\"limits\":\"all_native_framing_application_import_callback_and_publication_work_uses_one_channel_lifetime_ancestor;retention_is_cumulative_no_refund\",\"literal_kinds\":[\"json\",\"tuple\",\"set\"],\"manager_limits\":\"initialization_once;null_defaults_or_complete_positive_integer_reductions\",\"native_provider_context\":\"only_exact_retained_context_from_this_live_manager;no_external_context_import\",\"native_provider_result_kinds\":[\"proposal\",\"decision\",\"invalid\"],\"object_reference\":{\"fields\":[\"handle\"],\"scope\":\"one_live_trusted_host_broker_physical_identity\"},\"obligation_objects\":\"array_of_actual_host_references_matching_canonical_obligation_slots;whole_tuple_sidecar_preserves_add_input_and_admission_collection_identity;run_allocates_a_new_tuple_reusing_elements;sidecars_do_not_grant_acceptance\",\"operations\":{\"add-input\":{\"fields\":[\"identity\",\"stage\",\"requirements\",\"obligations\",\"obligation_objects\",\"payload\",\"obligations_object\"],\"result\":\"record\"},\"admit-component-input\":{\"fields\":[\"contract_id\",\"identity\",\"payload\"],\"result\":\"record\"},\"artifact\":{\"fields\":[\"name\"],\"result\":\"canonical_immutable_build_artifact\"},\"call-native-provider\":{\"fields\":[\"provider_id\",\"context_id\"],\"result\":\"native_provider_result\"},\"get\":{\"fields\":[\"identity\"],\"result\":\"record\"},\"initialize-components\":{\"fields\":[\"request\",\"history\",\"until\",\"config\",\"manager_limits\",\"target_object\"],\"result\":\"initialization\"},\"initialize-empty\":{\"fields\":[\"target\",\"dependencies\",\"completion_profiles\",\"manager_limits\",\"target_object\"],\"result\":\"initialization\"},\"initialize-synthetic\":{\"fields\":[\"request\",\"history\",\"until\",\"config\",\"manager_limits\",\"target_object\"],\"result\":\"initialization\"},\"inspect\":{\"fields\":[],\"result\":\"historical_observation_only\"},\"register\":{\"fields\":[\"contract\",\"producer\",\"validators\",\"obligation_objects\"],\"result\":\"null\"},\"register-completion-profile\":{\"fields\":[\"profile\"],\"result\":\"null\"},\"register-component-input\":{\"fields\":[\"contract\",\"validators\",\"obligation_objects\",\"obligations_object\",\"requirements_object\"],\"result\":\"null\"},\"result\":{\"fields\":[\"identity\",\"scope\"],\"result\":\"pipeline_result\"},\"run\":{\"fields\":[\"pass_id\",\"input_id\",\"output_id\",\"configuration\"],\"result\":\"record\"},\"set-dependency\":{\"fields\":[\"key\",\"identity\"],\"result\":\"null\"},\"target\":{\"fields\":[],\"result\":\"target\"}},\"ordered_tree\":{\"array\":[\"array\",\"ordered_trees\"],\"object\":[\"object\",\"ordered_unique_key_tree_pairs\"],\"scalar\":[\"scalar\",\"json_scalar\"]},\"profile\":\"biocompiler.core.pipeline_callback_manager.v1\",\"provider_reference\":{\"host\":[\"kind\",\"object\"],\"native\":[\"kind\",\"provider_id\"]},\"record_bindings\":[\"record_id\",\"payload\",\"dependencies\",\"requirements\",\"obligations\",\"obligation_objects\",\"checks\",\"provenance\"],\"record_identity\":\"one_token_per_actual_native_record_physical_identity_including_rejected_and_stored_before_error_records;not_content_hash_or_import\",\"results\":{\"initialization\":[\"kind\",\"manager\",\"artifacts\",\"target\"],\"native_provider_result\":[\"kind\",\"value\"],\"pipeline_result\":[\"value\",\"artifact\"],\"record\":[\"value\",\"bindings\"],\"target\":[\"value\",\"binding\"]},\"schema_version\":\"biocompiler.pipeline_callback_manager_declaration.v1\",\"source_links_binding\":\"null_for_native_context_default_or_complete_host_or_native_collection_binding;tuple_identity_and_element_identity_preserved\"}"


def capability_profile() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_APPLICATION_JSON))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CoreProtocolError(message)


def _object(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == fields, label + ' has missing or unknown fields')
    return cast(dict[str, Any], value)


def _identity(value: Any) -> str:
    _require(type(value) is str and 0 < len(value.encode('utf-8')) <= 128, 'Invalid native view identity')
    return cast(str, value)


def _ordered(value: Any) -> JsonValue:
    """Capture insertion order without inspecting unrelated authored objects."""
    if isinstance(value, Mapping):
        return ['object', [[key, _ordered(item)] for key, item in value.items()]]
    if isinstance(value, (tuple, list)):
        return ['array', [_ordered(item) for item in value]]
    return ['scalar', value]


def _unordered(tree: Any) -> Any:
    _require(type(tree) is list and len(tree) == 2 and type(tree[0]) is str, 'Malformed native ordered value')
    kind, value = tree
    if kind == 'scalar':
        _require(value is None or type(value) in (bool, int, float, str), 'Malformed native scalar')
        return value
    _require(type(value) is list, 'Malformed native ordered collection')
    if kind == 'array':
        return tuple(_unordered(item) for item in value)
    _require(kind == 'object', 'Unknown native ordered value kind')
    result: dict[str, Any] = {}
    for item in value:
        _require(type(item) is list and len(item) == 2 and type(item[0]) is str and item[0] not in result,
                 'Malformed or duplicate native ordered key')
        result[item[0]] = _unordered(item[1])
    return MappingProxyType(result)


def _frozen(value: Any) -> Any:
    """View-only freezing of an already bounded, literal native JSON document."""
    if type(value) is dict:
        return MappingProxyType({key: _frozen(item) for key, item in value.items()})
    if type(value) is list:
        return tuple(_frozen(item) for item in value)
    return value


def _raw_fields(cls: Any, values: Mapping[str, Any]) -> Any:
    """Hydrate a native-checked value without rerunning Python semantic checks."""
    result = object.__new__(cls)
    for name, value in values.items():
        object.__setattr__(result, name, value)
    return result


def _obligation(value: Any) -> Any:
    _require(isinstance(value, Mapping) and set(value) == {'id', 'scope', 'evidence_kind', 'description'},
             'Malformed native obligation view')
    return _raw_fields(ScopedObligation, {**value, 'evidence_kind': EvidenceKind(value['evidence_kind'])})


@dataclass(frozen=True)
class _Binding:
    document: bytes
    flavor: str
    value: Any


class _NativeProvider:
    """A live native closure capability, minted only by this manager's channel."""
    def __init__(self, manager: CorePassManager, identity: str):
        self._manager = manager
        self._identity = identity

    def __call__(self, context: Any) -> Any:
        return self._manager._call_native(self._identity, context)


class CorePassManager(PassManager):  # type: ignore[misc]
    """A nominal PassManager whose operations execute in one explicit Core.

    No inherited Python manager constructor, acceptance or freshness method is
    called. Arbitrary contract subclasses are not silently serialized by this
    explicit profile; authored payloads and callbacks remain deferred capabilities.
    """
    _EXTRA_ACTIONS = ('ordered-json', 'hydrate-context', 'native-provider', 'provider-reference',
                      'set-equal', 'source-link-set-equal')

    def __init__(self, core: CoreClient, *, target: Any, dependencies: Any,
                 completion_profiles: Any = (), limits: JsonValue = None,
                 manager_limits: JsonValue = None):
        if not isinstance(target, TargetContext):
            raise SerializationError('A pipeline needs a target context.')
        if not isinstance(dependencies, Mapping):
            raise SerializationError('Dependencies must be a mapping.')
        _require(type(target) in (TargetContext, HumanTargetContext), 'Custom target subclasses require a deferred authoring profile')
        profiles = [self._profile_document(profile) for profile in completion_profiles]
        entries: list[JsonValue] = [[key, value] for key, value in dependencies.items()]
        self._prepare(core, application=capability_profile(), limits=limits)
        self._target = target
        try:
            result = self._call('initialize-empty', {'target': target.to_dict(), 'dependencies': entries,
                'completion_profiles': cast(JsonValue, profiles), 'manager_limits': manager_limits,
                'target_object': self._objects.retain(target)})
            self._initialization(result, 'empty')
        except BaseException:
            self._session._invalidate()
            self._objects.close()
            raise

    @staticmethod
    def _profile_document(profile: Any) -> dict[str, JsonValue]:
        if not isinstance(profile, CompletionProfile):
            raise SerializationError('Invalid completion profile.')
        _require(type(profile) is CompletionProfile, 'Custom completion profile subclasses require deferred authoring')
        return {'scope': profile.scope, 'stage': profile.stage.value,
                'schema': profile.schema, 'obligations': list(profile.obligations)}

    def _initialization(self, raw: JsonValue, kind: str) -> None:
        value = _object(raw, {'kind', 'manager', 'artifacts', 'target'}, 'Native manager initialization')
        _require(value['kind'] == kind and value['manager'] is True and type(value['artifacts']) is list,
                 'Native manager initialization changed its kind or state')
        target = _object(value['target'], {'value', 'binding'}, 'Native target')
        actual = self._binding(target['binding'], flavor='target')
        _require(actual is self._target, 'Native manager did not retain its authored target object')

    @classmethod
    def from_synthetic(cls, core: CoreClient, request: Any, history: Any, *, until: JsonValue = None,
                       config: Any = None, limits: JsonValue = None, manager_limits: JsonValue = None) -> CorePassManager:
        return cls._fixed(core, request, history, until=until, config=config, limits=limits,
                          manager_limits=manager_limits, components=False)

    @classmethod
    def from_components(cls, core: CoreClient, request: Any, history: Any, *, until: JsonValue = None,
                        config: Any = None, limits: JsonValue = None, manager_limits: JsonValue = None) -> CorePassManager:
        return cls._fixed(core, request, history, until=until, config=config, limits=limits,
                          manager_limits=manager_limits, components=True)

    @classmethod
    def _fixed(cls, core: CoreClient, request: Any, history: Any, *, until: JsonValue,
               config: Any, limits: JsonValue, manager_limits: JsonValue, components: bool) -> CorePassManager:
        # The two public initializers deliberately materialize history at
        # different points. Keep their existing authoring order explicit.
        frames = tuple(history) if components else None
        if not isinstance(request, RealizationRequest):
            raise TypeError('Expected a frozen RealizationRequest.')
        _require(type(request) is RealizationRequest, 'Custom realization subclasses require deferred authoring')
        if request.build_request.artifact_scope != 'synthetic_realization':
            raise PipelineError('The request must explicitly select synthetic_realization scope.')
        config = SyntheticGeneratorConfig() if config is None else config
        if not isinstance(config, SyntheticGeneratorConfig):
            raise TypeError('Expected a SyntheticGeneratorConfig.')
        _require(type(config) is SyntheticGeneratorConfig, 'Custom generator configuration requires deferred authoring')
        if frames is None:
            frames = tuple(history)
        _require(all(type(frame) is InputFrame for frame in frames), 'Native fixed history requires regular InputFrame values')
        manager = cls.__new__(cls)
        manager._prepare(core, application=capability_profile(), limits=limits)
        manager._target = request.target
        kind = 'components' if components else 'synthetic'
        try:
            result = manager._call('initialize-' + kind, {'request': request.to_dict(),
                'history': [frame.to_dict() for frame in frames], 'until': until, 'config': config.to_dict(),
                'manager_limits': manager_limits, 'target_object': manager._objects.retain(request.target)})
            manager._initialization(result, kind)
        except BaseException:
            manager._session._invalidate()
            manager._objects.close()
            raise
        return manager

    @property
    def session(self) -> CorePipelineCallbackSession:
        return self._session

    @property
    def target(self) -> Any:
        return self._target

    def set_dependency(self, key: Any, identity: Any) -> None:
        self._unit('set-dependency', {'key': key, 'identity': identity})

    def register_completion_profile(self, profile: Any) -> None:
        self._unit('register-completion-profile', {'profile': self._profile_document(profile)})

    def register(self, contract: Any, producer: Callable[..., Any], validators: Mapping[str, Callable[..., Any]]) -> None:
        if not isinstance(contract, PassContract):
            raise SerializationError('Invalid pass contract.')
        _require(type(contract) is PassContract, 'Custom pass contract subclasses require deferred authoring')
        self._unit('register', {'contract': contract.to_dict(), 'producer': self._objects.retain(producer),
            'validators': self._objects.retain(validators),
            'obligation_objects': [self._objects.retain(item) for item in contract.introduces]})

    def register_component_input(self, contract: Any, validators: Mapping[str, Callable[..., Any]]) -> None:
        if not isinstance(contract, ComponentInputContract):
            raise SerializationError('Invalid component input contract.')
        _require(type(contract) is ComponentInputContract, 'Custom component contracts require deferred authoring')
        self._unit('register-component-input', {'contract': contract.to_dict(), 'validators': self._objects.retain(validators),
            'obligation_objects': [self._objects.retain(item) for item in contract.obligations],
            'obligations_object': self._objects.retain(contract.obligations),
            'requirements_object': self._objects.retain(contract.requirements)})

    def add_input(self, identity: Any, payload: Any, *, stage: Any = Stage.INTENT,
                  requirements: Any = (), obligations: Any = ()) -> Any:
        _require(type(requirements) in (tuple, list) and type(obligations) in (tuple, list),
                 'Custom input collections require a deferred authoring profile')
        _require(all(type(value) is ScopedObligation for value in obligations),
                 'Custom obligation objects require a deferred authoring profile')
        return self._record(self._call('add-input', {'identity': identity,
            'stage': stage.value if isinstance(stage, Stage) else stage,
            'requirements': list(requirements), 'obligations': [value.to_dict() for value in obligations],
            'obligation_objects': [self._objects.retain(value) for value in obligations],
            'obligations_object': self._objects.retain(obligations), 'payload': self._objects.retain(payload)}))

    def admit_component_input(self, contract_id: Any, identity: Any, payload: Any) -> Any:
        return self._record(self._call('admit-component-input', {'contract_id': contract_id,
            'identity': identity, 'payload': self._objects.retain(payload)}))

    def get(self, identity: Any) -> Any:
        # Re-enter the native manager even when a view is cached: it owns current
        # dependency and ancestry freshness, including callback mutations.
        return self._record(self._call('get', {'identity': identity}))

    def run(self, pass_id: Any, input_id: Any, output_id: Any, *, configuration: Any = None) -> Any:
        return self._record(self._call('run', {'pass_id': pass_id, 'input_id': input_id, 'output_id': output_id,
            'configuration': None if configuration is None else self._objects.retain(configuration)}))

    def result(self, identity: Any, *, scope: Any) -> Any:
        raw = self._call('result', {'identity': identity, 'scope': scope})
        return self._view(self._result_value, raw, 'pipeline result')

    def _result_value(self, raw: JsonValue) -> Any:
        envelope = _object(raw, {'value', 'artifact'}, 'Pipeline result')
        value = _object(envelope['value'], {'status', 'artifact', 'scope', 'unresolved'}, 'Pipeline result value')
        artifact = self._record(envelope['artifact'])
        _require(encode_document(value['artifact']) == self._record_bindings[artifact.id][1],
                 'Pipeline result artifact differs from its record binding')
        # The native result decides which obligations remain. Preserve each
        # actual stored obligation object when constructing this fresh wrapper.
        declarations = value['artifact']['obligations']
        _require(type(declarations) is list and len(declarations) == len(artifact.obligations)
            and type(value['unresolved']) is list and type(value['scope']) is str,
            'Malformed native result obligations or scope')
        objects = {item['id']: (encode_document(item), actual)
            for item, actual in zip(declarations, artifact.obligations)}
        unresolved_items = []
        seen: set[str] = set()
        for item in value['unresolved']:
            declaration = _object(item, {'id', 'scope', 'evidence_kind', 'description'}, 'Unresolved obligation')
            key = declaration['id']
            _require(type(key) is str and key not in seen and key in objects,
                'Unknown or repeated unresolved obligation')
            _require(encode_document(declaration) == objects[key][0], 'Unresolved obligation differs from its stored declaration')
            seen.add(key)
            unresolved_items.append(objects[key][1])
        unresolved = tuple(unresolved_items)
        return PipelineResult(ArtifactStatus(value['status']), artifact, value['scope'], unresolved)

    def _unit(self, operation: str, arguments: JsonValue) -> None:
        result = self._call(operation, arguments)
        if result is not None:
            self._session._invalidate()
            raise CoreProtocolError('Native unit operation returned an unexpected value')

    def inspect(self) -> JsonValue:
        return self._call('inspect', {})

    def historical(self, identity: str) -> Any:
        snapshot = self.inspect()
        if type(snapshot) is not dict or type(snapshot.get('records')) is not dict:
            self._session._invalidate()
            raise CoreProtocolError('Native inspection omitted its historical records')
        records = cast(dict[str, JsonValue], snapshot['records'])
        return self._record(records[identity])

    def artifact(self, name: str) -> JsonValue:
        return self._call('artifact', {'name': name})

    def close(self) -> None:
        self._session.close()
        self._objects.close()

    def __enter__(self) -> CorePassManager:
        self._session.__enter__()
        return self

    def __exit__(self, kind: Any, value: Any, traceback: Any) -> None:
        self._session.__exit__(kind, value, traceback)
        self._objects.close()

    def _record(self, raw: JsonValue) -> Any:
        return self._view(self._record_value, raw, 'record view or binding')

    def _view(self, hydrate: Callable[[Any], Any], raw: Any, label: str) -> Any:
        try:
            return hydrate(raw)
        except (CoreProtocolError, KeyError, ValueError, TypeError) as error:
            self._session._invalidate()
            raise CoreProtocolError('Invalid native ' + label) from error

    def _record_value(self, raw: JsonValue) -> Any:
        envelope = _object(raw, {'value', 'bindings'}, 'Native stage record envelope')
        value = _object(envelope['value'], {'schema_version', 'id', 'stage', 'payload', 'requirements',
            'obligations', 'discharged', 'dependencies', 'parent', 'pass_id', 'pass_identity', 'checks',
            'provenance', 'accepted'}, 'Native stage record')
        _require(value['schema_version'] == 'biocompiler.stage_record.v0.1' and type(value['id']) is str
                 and type(value['accepted']) is bool, 'Invalid native stage record shape')
        bindings = _object(envelope['bindings'], set(capability_profile()['record_bindings']), 'Native record bindings')
        identity, token = value['id'], _identity(bindings['record_id'])
        document, signature = encode_document(value), encode_document(envelope)
        previous = self._record_bindings.get(identity)
        if previous is not None:
            _require(previous == (token, document) and self._record_envelopes[identity] == signature,
                     'Native stored record identity was reused or rebound')
            return self._records[identity]
        elements = tuple(self._binding(item, flavor='obligation') for item in bindings['obligation_objects'])
        obligations = self._obligations_binding(bindings['obligations'], elements)
        record = StageRecord(identity, Stage(value['stage']), self._binding(bindings['payload']),
            self._binding(bindings['requirements']), obligations, tuple(value['discharged']),
            self._binding(bindings['dependencies']), value['parent'], value['pass_id'], value['pass_identity'],
            self._binding(bindings['checks']), self._binding(bindings['provenance']), value['accepted'])
        self._records[identity] = record
        self._record_bindings[identity] = (token, document)
        self._record_envelopes[identity] = signature
        return record

    def _obligations_binding(self, binding: Any, elements: tuple[Any, ...]) -> Any:
        _require(type(binding) is dict and type(binding.get('kind')) is str, 'Invalid obligation collection binding')
        if binding['kind'] == 'host':
            result = self._binding(binding)
            if type(result) is list:
                # This explicit authoring profile permits regular builtin
                # lists. Arbitrary collection/mutation timing is not imported
                # as equivalent to the original manager's deferred conversion.
                result = tuple(result)
            _require(type(result) is tuple and len(result) == len(elements)
                and all(left is right for left, right in zip(result, elements)),
                'Obligation collection differs from its retained element identities')
            return result
        value = _object(binding, {'kind', 'identity', 'tree'}, 'Native obligation collection')
        _require(value['kind'] == 'native', 'Unknown obligation collection kind')
        identity, document = _identity(value['identity']), encode_document(value['tree'])
        previous = self._bindings.get(identity)
        if previous is not None:
            _require(previous.document == document and previous.flavor == 'obligations', 'Obligation collection was rebound')
            _require(len(previous.value) == len(elements) and all(left is right for left, right in zip(previous.value, elements)),
                     'Native obligation collection changed its element identities')
            return previous.value
        shape = _unordered(value['tree'])
        _require(type(shape) is tuple and len(shape) == len(elements), 'Incomplete native obligation collection')
        _require(len(self._bindings) < self._objects.limits.max_objects, 'Native view binding limit exceeded')
        self._bindings[identity] = _Binding(document, 'obligations', elements)
        return elements

    def _prepare(self, core: CoreClient, *, application: JsonValue, limits: JsonValue = None) -> None:
        self._objects = CallbackObjects()
        self._bindings: dict[str, _Binding] = {}
        self._contexts: dict[str, tuple[bytes, Any]] = {}
        self._context_ids: dict[int, str] = {}
        self._native_providers: dict[str, _NativeProvider] = {}
        self._records: dict[str, Any] = {}
        self._record_bindings: dict[str, tuple[str, bytes]] = {}
        self._record_envelopes: dict[str, bytes] = {}
        self._target = None
        # Keep these callable objects stable. Merely dispatching an action must
        # not allocate a fresh bound-method identity in the retained registry.
        self._set_equal = lambda value, values: set(value) == set(values)
        self._source_link_equal = lambda values, expected: set(values) == set(expected)
        self._ordered_callable = _ordered
        self._session = CorePipelineCallbackSession(core, application=application, objects=self._objects,
            limits=limits, allowed_actions=_BROKER_ACTIONS + self._EXTRA_ACTIONS, invocation_handler=self._invoke)

    def _ok(self, value: JsonValue) -> HostCompletion:
        return HostCompletion('ok', encode_document(value, max_bytes=self._objects.limits.max_document_bytes,
            max_nodes=self._objects.limits.max_document_nodes))

    def _host_call(self, function: Callable[..., Any], *values: Any) -> HostCompletion:
        return self._objects.execute('call', {'callable': self._objects.retain(function),
            'args': [self._objects.retain(value) for value in values], 'kwargs': {}})

    def _host_observation(self, completion: HostCompletion) -> HostCompletion:
        if completion.status != 'ok':
            return completion
        return self._objects.execute('json', {'object': completion.value})

    def _invoke(self, action: str, arguments: JsonValue) -> HostCompletion:
        if action == 'ordered-json':
            value = self._objects.resolve(_object(arguments, {'object'}, 'Ordered JSON action')['object'])
            return self._host_observation(self._host_call(self._ordered_callable, value))
        if action == 'set-equal':
            args = _object(arguments, {'object', 'values'}, 'Set comparison action')
            _require(type(args['values']) is list and all(value is None or type(value) in (str, int, float, bool)
                for value in args['values']), 'Set comparison literals must be scalar values')
            return self._host_observation(self._host_call(self._set_equal,
                self._objects.resolve(args['object']), args['values']))
        if action == 'source-link-set-equal':
            args = _object(arguments, {'objects', 'expected'}, 'Source link set action')
            _require(type(args['objects']) is list and type(args['expected']) is list, 'Source link sets require arrays')
            actual = [self._objects.resolve(reference) for reference in args['objects']]
            expected = [SourceLink(**_object(value, {'requirement_id', 'source_node_id', 'target_node_id', 'pass_name'},
                'Expected source link')) for value in args['expected']]
            return self._host_observation(self._host_call(self._source_link_equal, actual, expected))
        if action == 'native-provider':
            identity = _identity(_object(arguments, {'provider_id'}, 'Native provider action')['provider_id'])
            previous = self._native_providers.get(identity)
            if previous is None:
                previous = _NativeProvider(self, identity)
                self._native_providers[identity] = previous
            return self._ok(self._objects.retain(previous))
        if action == 'provider-reference':
            reference = _object(arguments, {'object'}, 'Provider identity action')['object']
            value = self._objects.resolve(reference)
            if type(value) is _NativeProvider:
                _require(value._manager is self and self._native_providers.get(value._identity) is value,
                         'Foreign or forged native provider capability')
                return self._ok({'kind': 'native', 'provider_id': value._identity})
            return self._ok({'kind': 'host', 'object': reference})
        if action == 'hydrate-context':
            return self._hydrate_context(arguments)
        _require(action in _BROKER_ACTIONS, 'Unknown native manager action')
        return self._objects.execute(action, arguments)

    def _binding(self, binding: Any, *, flavor: str = 'json') -> Any:
        _require(type(binding) is dict and type(binding.get('kind')) is str, 'Malformed native view binding')
        if binding['kind'] == 'host':
            value = _object(binding, {'kind', 'object'}, 'Host view binding')
            return self._objects.resolve(value['object'])
        value = _object(binding, {'kind', 'identity', 'tree'}, 'Native view binding')
        _require(value['kind'] == 'native', 'Unknown view binding kind')
        identity = _identity(value['identity'])
        document = encode_document(value['tree'])
        previous = self._bindings.get(identity)
        if previous is not None:
            _require(previous.document == document and previous.flavor == flavor,
                     'Native view identity was rebound to changed content or type')
            return previous.value
        _require(len(self._bindings) < self._objects.limits.max_objects, 'Native view binding limit exceeded')
        result = _unordered(value['tree'])
        if flavor == 'obligation':
            result = _obligation(result)
        elif flavor == 'default-observation':
            _require(type(result) is MappingProxyType and not result, 'Native context default observation must be empty')
            result = {}
        elif flavor == 'target':
            # Every initializer retains the actual authored target. Hydrating a
            # new equivalent target would silently lose its public identity.
            raise CoreProtocolError('Native target must retain its authored local object')
        else:
            _require(flavor == 'json', 'Unknown native view flavor')
        self._bindings[identity] = _Binding(document, flavor, result)
        return result

    def _hydrate_context(self, arguments: JsonValue) -> HostCompletion:
        args = _object(arguments, {'context_id', 'document', 'bindings'}, 'Native context action')
        identity = _identity(args['context_id'])
        signature = encode_document(args)
        previous = self._contexts.get(identity)
        if previous is not None:
            _require(previous[0] == signature, 'Native context identity was rebound')
            return self._ok(self._objects.retain(previous[1]))
        _require(len(self._contexts) < self._objects.limits.max_objects, 'Native context limit exceeded')
        keys = {'input', 'output', 'target', 'configuration', 'dependencies', 'requirements', 'source_links', 'observation_map'}
        _object(args['document'], keys, 'Native context document')
        bindings = _object(args['bindings'], keys, 'Native context bindings')
        links = bindings['source_links']
        if links is None:
            source_links = tuple(SourceLink(**_object(item,
                {'requirement_id', 'source_node_id', 'target_node_id', 'pass_name'}, 'Native source link'))
                for item in args['document']['source_links'])
        else:
            source_links = self._binding(links)
        context = PassContext(self._binding(bindings['input']),
            None if bindings['output'] is None else self._binding(bindings['output']),
            self._binding(bindings['target'], flavor='target'), self._binding(bindings['configuration']),
            self._binding(bindings['dependencies']), self._binding(bindings['requirements']),
            source_links, self._binding(bindings['observation_map'],
                flavor='default-observation' if bindings['output'] is None else 'json'))
        self._contexts[identity] = (signature, context)
        self._context_ids[id(context)] = identity
        return self._ok(self._objects.retain(context))

    def _call_native(self, identity: str, context: Any) -> Any:
        token = self._context_ids.get(id(context))
        _require(token is not None and self._contexts[token][1] is context,
                 'Native providers require an actual context from this live manager')
        return self._native_return(self._call('call-native-provider', {'provider_id': identity, 'context_id': token}))

    def _native_return(self, value: JsonValue) -> Any:
        return self._view(self._native_return_value, value, 'provider result')

    def _native_return_value(self, value: JsonValue) -> Any:
        envelope = _object(value, {'kind', 'value'}, 'Native provider result')
        kind, result = envelope['kind'], envelope['value']
        if kind == 'invalid':
            return _frozen(result)
        if kind == 'decision':
            decision = _object(result, {'outcome', 'detail', 'evidence'}, 'Native check decision')
            return _raw_fields(CheckDecision, {'outcome': CheckOutcome(decision['outcome']),
                'detail': decision['detail'], 'evidence': _frozen(decision['evidence'])})
        _require(kind == 'proposal', 'Unknown native provider result kind')
        proposal = _object(result, {'output', 'obligations', 'source_links', 'observation_map', 'search_status'}, 'Native pass result')
        obligations = tuple(_raw_fields(Obligation, {**_object(item,
            {'requirement_id', 'description', 'evidence_kind', 'evidence_refs'}, 'Native proposal obligation'),
            'evidence_kind': EvidenceKind(item['evidence_kind']), 'evidence_refs': tuple(item['evidence_refs'])})
            for item in proposal['obligations'])
        links = tuple(SourceLink(**_object(item, {'requirement_id', 'source_node_id', 'target_node_id', 'pass_name'},
            'Native proposal source link')) for item in proposal['source_links'])
        return PassResult(_frozen(proposal['output']), obligations, links,
            _frozen(proposal['observation_map']), proposal['search_status'])

    def _call(self, operation: str, arguments: JsonValue) -> JsonValue:
        error: BaseException | None = None
        response: CallbackResponse | None = None
        try:
            response = self._session.call(operation, arguments)
        except CallbackRejected as rejected:
            try:
                error = self._exception(rejected.response.result)
            except BaseException:
                self._session._invalidate()
                raise
        if error is not None:
            raise error
        assert response is not None
        return response.result

    def _exception(self, raw: JsonValue) -> BaseException:
        value = _object(raw, {'module', 'type', 'message', 'attributes'}, 'Native application exception')
        _require(all(type(value[key]) is str for key in ('module', 'type', 'message')) and type(value['attributes']) is dict,
                 'Malformed native exception descriptor')
        classes: dict[tuple[str, str], Any] = {
            ('biocompiler.compiler.pipeline', 'PipelineError'): PipelineError,
            ('biocompiler.compiler.pipeline', 'NoCandidateFound'): NoCandidateFound,
            ('biocompiler.errors', 'SerializationError'): SerializationError,
            ('biocompiler.errors', 'UnsupportedBehaviorError'): UnsupportedBehaviorError,
            ('builtins', 'ValueError'): ValueError, ('builtins', 'TypeError'): TypeError,
            ('builtins', 'KeyError'): KeyError,
        }
        cls = classes.get((value['module'], value['type']))
        _require(cls is not None, 'Native application returned an undeclared exception class')
        assert cls is not None
        attributes = value['attributes']
        if cls is NoCandidateFound:
            _object(attributes, {'pass_id', 'configuration', 'dependencies'}, 'No-candidate exception attributes')
            error: BaseException = cls.__new__(cls)
            BaseException.__init__(error, value['message'])
            for key, item in attributes.items():
                object.__setattr__(error, key, _frozen(item))
            return error
        _require(not attributes, 'Unexpected native exception attributes')
        return cast(BaseException, cls(value['message']))
