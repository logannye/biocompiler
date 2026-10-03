"""Explicit native manager adapter and process-local typed inspection views.

The native process owns registration, freshness, checks and acceptance. Retained
Python objects support trusted authoring and callbacks at native-requested stages.
This opt-in adapter does not change the default Python manager or fixed pipelines.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
from pathlib import Path
import sys
from types import FunctionType, MappingProxyType, ModuleType
from typing import Any, cast

from biocompiler.artifacts.provenance import SourceLink
from biocompiler.compiler.passes import PassResult
from biocompiler.compiler.request import RealizationRequest
from biocompiler.compiler.pipeline import (
    ArtifactStatus, CheckDecision, CheckSpec, CompletionProfile, ComponentInputContract,
    NoCandidateFound, PassContext, PassContract, PassManager, PipelineError,
    PipelineResult, ScopedObligation, StageRecord,
)
from biocompiler.core_client import CoreClient, CoreProtocolError, JsonValue
from biocompiler.core_pipeline_callback_session import (
    CallbackRejected, CallbackResponse, CorePipelineCallbackSession, _BROKER_ACTIONS,
)
from biocompiler.core_pipeline_session import decode_document, encode_document
from biocompiler.core_pipeline_provider_views import (
    FrozenJson, PROVIDER_ROLES, ProviderOutput, ProviderViewStore, StructuralViews, origin_reference,
)
from biocompiler.core_pipeline_build_views import BuildViewStore
from biocompiler.compiler.synthetic import SyntheticBuild
from biocompiler.compiler.components import ComponentBuild
from biocompiler.errors import SerializationError, UnsupportedBehaviorError
from biocompiler.ir.stages import Stage
from biocompiler.pipeline_callback_objects import CallbackObjects, HostCompletion
from biocompiler.semantics.context import HumanTargetContext, PayloadFormat, TargetContext
from biocompiler.semantics.evaluator import InputFrame
from biocompiler.synthesis.synthetic import SyntheticGeneratorConfig
from biocompiler.verification.evidence import CheckOutcome, EvidenceKind, Obligation

_APPLICATION_JSON = '{"acceptance":"native_manager_checks_and_freshness_only;inspection_and_host_sidecars_cannot_import_accepted_records","actions":{"hydrate-context":{"fields":["context_id","document","bindings"],"result":"object_reference"},"manager-created":{"fields":["target"],"result":"null"},"native-provider":{"fields":["provider_id","role"],"result":"object_reference"},"ordered-json":{"fields":["object"],"result":"ordered_tree"},"origin-reference":{"fields":["root","path"],"result":"object_reference"},"provider-reference":{"fields":["object"],"result":"host_or_native_provider_reference"},"reference-emit":{"fields":["input","argument","tree"],"result":"reference_source_result"},"reference-generate":{"fields":["input","argument","tree"],"result":"reference_source_result"},"reference-proposal":{"fields":["output","source_links"],"result":"object_reference"},"reference-source-links-equal":{"fields":["actual","expected"],"result":"boolean"},"register-fixed":{"fields":["contract","producer","validators","obligation_objects"],"result":"null"},"set-equal":{"fields":["object","values"],"result":"boolean"},"source-link-set-equal":{"fields":["objects","expected"],"result":"boolean"}},"argument":"--pipeline-callback-session-v1","authoring_boundary":"canonical_typed_contract_target_profile_fields;opaque_payload_configuration_provider_and_validator_objects_are_read_at_native_requested_points","bindings":{"host":["kind","object"],"native":["kind","identity","tree"]},"broker_actions":{"attr":{"fields":["object","name"],"result":"object_reference"},"attr-default":{"fields":["object","name","default"],"result":"object_reference"},"bind-provider":{"fields":["provider_id","object"],"result":"null"},"call":{"fields":["callable","args","kwargs"],"result":"object_reference"},"call-provider":{"fields":["provider_id","context"],"result":"object_reference"},"callable":{"fields":["object"],"result":"boolean"},"compare":{"fields":["left","right","operator"],"result":"boolean"},"contains":{"fields":["container","item"],"result":"boolean"},"dict":{"fields":["object"],"result":"object_reference"},"document":{"fields":["object"],"result":"object_reference"},"enum":{"fields":["type","value"],"result":"object_reference"},"freeze-json":{"fields":["object"],"result":"object_reference"},"get-item":{"fields":["object","key"],"result":"object_reference"},"is-instance":{"fields":["object","type"],"result":"boolean"},"is-none":{"fields":["object"],"result":"boolean"},"iter":{"fields":["object"],"result":"object_reference"},"json":{"fields":["object"],"result":"json"},"len":{"fields":["object"],"result":"integer"},"list":{"fields":["object"],"result":"object_reference"},"literal":{"fields":["kind","value"],"result":"object_reference"},"lookup":{"fields":["object","entries"],"result":"object_reference"},"mapping-items":{"fields":["object"],"result":"object_reference"},"mapping-keys":{"fields":["object"],"result":"object_reference"},"mapping-values":{"fields":["object"],"result":"object_reference"},"merge":{"fields":["object","before","after"],"result":"object_reference"},"next":{"fields":["object"],"result":"iterator_step"},"release":{"fields":["handles"],"result":"null"},"set-attribute-equal":{"fields":["objects","name","values"],"result":"boolean"},"truth":{"fields":["object"],"result":"boolean"},"tuple":{"fields":["object"],"result":"object_reference"},"vars":{"fields":["object"],"result":"object_reference"}},"channel":"biocompiler.pipeline_callback_channel.v1","claim_scope":"software_contract_conditional_translation_and_scoped_completion;no_empirical_or_human_use_acceptance","comparison_operators":["eq","ne","is","is-not"],"compatibility_pending":["complete_original_installed_replay","fixed_public_registration_interception","arbitrary_authoring_subclass_and_scalar_operator_semantics","default_cutover"],"component_continuation":{"failure":"actual_partial_manager_and_previous_successful_mutations_preserved_on_logical_or_host_failure;fatal_channel_failures_close_authority","finish":"exact_retained_actual_run_record_incarnation_and_matching_actual_result_command_sequence_owner_stage_scope;no_recomputation_or_import_of_accepted_result","limits":"all_preparations_origins_build_views_and_retained_result_receipts_charged_to_channel_lifetime_work_and_retention","obligation_objects":"ordered_native_binding_descriptors_matching_contract_introduces_slots;structural_host_views_returned_as_strong_host_references_during_actual_register;native_validation_remains_authoritative","order":["prepare-components","ordered_actual_set-dependency_calls","component-profile","actual_register-completion-profile","component-registration","actual_register","actual_run","actual_result","finish-components"],"owner":"same_live_manager_and_actual_retained_synthetic_build;one_preparation_attempt;preparation_id_is_channel_scoped_native_capability","preparation":"native_adaptation_and_ordered_dependencies_only;profile_and_registration_constructors_remain_after_prior_actual_mutations","registration":"actual_native_contract_and_physical_fixed_producer_and_validator_closures;ordered_validator_name_and_host_reference_pairs"},"context_bindings":["input","output","target","configuration","dependencies","requirements","source_links","observation_map"],"context_identity":"actual_native_context_physical_identity;distinct_producer_and_validation_contexts;one_validation_context_shared_by_its_validators","default_generator_config":{"catalog_fingerprint":"f2a4b4c1625b4794028fcd1d0e08785724f957023966a29faafe9374cca77343","conjunction_strategy":"native","generator_version":"biocompiler.synthetic.generator.v0.4","profile_version":"biocompiler.synthetic.combinational.v0.1","schema_version":"biocompiler.synthetic_generator_config.v0.3","witness_selection":"closed_band_lower_endpoint"},"default_generator_config_authority":"exact_negotiated_native_Config_make_default;fresh_closed_Python_representation_before_initialization;native_import_and_catalog_validation_remain_authoritative","dependencies_encoding":"ordered_unique_string_identity_pairs","enum_types":["EvidenceKind","CheckOutcome","Stage","ArtifactStatus","PayloadFormat"],"executable":"core","expected_rejection_attributes":"fresh_ordered_tree_with_exact_canonical_attributes_projection;no_cached_binding_or_context_container_reuse;NoCandidateFound_retains_pass_configuration_and_dependency_order","expected_rejection_fields":["module","type","message","attributes","attributes_tree"],"failure":"expected_logical_rejection_and_opaque_host_exception_preserve_actual_partial_manager;malformed_resource_internal_or_uncertain_io_failure_closes_authority","fixed_build_view":{"absent_selection":"value_and_binding_null;selection_config_and_required_capabilities_null;alternative_configs_empty_and_no_selection_aliases;candidate_type_aliases_remain_required","aliases":"selection_paths_start_selection_result_alternatives_nonnegative_index_candidate_then_closed_typed_candidate_path_with_same_eight_provider_alias_tags;candidate_paths_only_TypeSpec_at_candidate_mechanism_nodes_nonnegative_index_output_dtype;no_assembly_or_report_aliases","alternative_configs":"ordered_candidate_slots;null_only_without_candidate;native_constructor_origin_bindings;selected_slot_reuses_actual_fixed_provider_selected_config_origin","artifact_fields":["value","binding"],"artifact_identity":"dedicated_retained_actual_build_artifact_origins;never_manager_frozen_json_or_provider_output_roots;upstream_candidate_and_selection_shared_only_from_actual_retained_synthetic_build","artifacts":{"components":["candidate","selection_result","assembly","link_result","behavior_result"],"synthetic":["candidate","selection_result"]},"candidate_source":"actual_historical_upstream_mechanism_record_envelope;parsed_node_inputs_and_requirement_ids_and_program_outputs_and_required_capabilities_retain_source_tuple_identity","candidate_type_origins":"one_retained_actual_parsed_type_origin_per_upstream_candidate_physical_identity_node_and_argument_path;distinct_even_when_fields_equal;same_origin_used_by_actual_component_provider_registry_descendants","fields":["selection_config","alternative_configs","required_capabilities","aliases"],"fresh_roots":"parsed_candidate_and_assembly_are_fresh_from_original_frozen_payload;assembly_composition_target_is_fresh_and_not_manager_target","kinds":["synthetic","components"],"required_capabilities":"null_without_selection_candidates;otherwise_actual_syntheticCapabilities_constant_host_binding;only_generated_selection_and_provider_candidates_share_this_tuple","result":"actual_historical_pipeline_result_and_record_envelope;finish_reuses_exact_public_result_wrapper_from_result_sequence;historical_views_do_not_grant_fresh_acceptance","selection_config":"actual_requested_host_configuration","sources":["candidate"]},"fixed_registration":{"failure":"published_manager_retained_only_after_exact_completed_rejected_or_opaque_raise_initialization_reply_on_open_channel;fatal_or_uncertain_channel_closes_authority","hook":"source_ordered_actual_fixed_contract_native_producer_ordered_validators_and_introduced_obligations;invoke_current_public_register_once;ignore_return_without_inspection;no_implicit_fallback","native_registration":"only_actual_nested_register_commands_mutate_the_live_manager;producer_wrappers_and_original_native_validator_identity_preserved","publication":"exact_actual_manager_and_authored_target_before_first_input_or_registration;once_per_fixed_initialization;no_manager_replacement","roles":["intent_to_behavior","behavior_to_synthetic","synthetic_to_components"],"staged_components":"existing_actual_public_register_call_only;no_second_register_fixed_hook;unchanged_contract_and_actual_native_validator_enable_host_source_link_capability_independently_of_producer_wrapper"},"fixed_request_tree":"ordered_tree_from_same_authoring_serialization_as_request;exact_canonical_projection_required_before_native_import;retained_order_is_not_acceptance","host_execution":"trusted_host_code_cpu_and_opaque_captures_outside_native_work_and_json_memory_bounds","inspection_order":{"combined_provider_history":"actual_successful_insertion_order;pass_fingerprint_string_or_component_input_tag_and_fingerprint_pair;replacements_preserve_position","fields":["dependencies","passes","component_inputs","provider_history","component_input_history","records","profiles","combined_provider_history","validators"],"mapping_order":"unique_complete_snapshot_key_arrays","provider_fields":["provider_id","object"],"providers":"exact_reachable_snapshot_provider_token_census;stable_bijection_to_actual_retained_callable_identity;no_user_equality_or_hash","scope":"manager_mapping_and_validator_order_only;nested_unobserved_json_order_not_generalized;historical_observation_cannot_grant_acceptance","validator_maps":["passes","component_inputs","provider_history","component_input_history"],"validators":"four_exact_registration_maps_of_unique_complete_validator_key_arrays"},"inspection_references":{"authority":"inspection_only;references_cannot_import_records_or_grant_fresh_acceptance;existing_inspect_ordered_unchanged","definitions":"ordered_complete_record_envelopes_exactly_for_first_compact_publication_of_each_actual_record_incarnation_in_order_records;no_duplicates_unused_definitions_or_rebinding","record_reference_fields":["record_id"],"resolution":"same_channel_earlier_or_current_definitions_only;exact_record_name_and_incarnation_bijection;checked_immutable_full_envelope_expansion_without_get_result_or_acceptance_query","retention":"strong_actual_record_identity_and_definition_publication_census_charged_to_existing_channel_lifetime;publication_marked_only_after_complete_response_assembly","snapshot":"same_complete_historical_state_as_inspect_ordered_with_records_replaced_by_incarnation_references;all_other_fields_and_orders_unchanged"},"iterator_step_fields":["exhausted","object"],"lifecycle":"one_initialization_attempt_per_channel;existing_channel_close_is_top_level_only;no_reconnect_retry_or_state_import","limits":"all_native_framing_application_import_callback_and_publication_work_uses_one_channel_lifetime_ancestor;retention_is_cumulative_no_refund","literal_kinds":["json","tuple","set"],"manager_limits":"initialization_once;null_defaults_or_complete_positive_integer_reductions","native_provider_context":"only_exact_retained_context_from_this_live_manager;no_external_context_import","native_provider_result_kinds":["proposal","decision","invalid"],"native_provider_view":{"alias_fields":["kind","paths","binding"],"alias_kinds":["biocompiler.ir.intent.SourceLocation","biocompiler.semantics.types.TypeSpec","biocompiler.semantics.realization.Observable","biocompiler.semantics.component_contracts.OperatingDomain","biocompiler.semantics.component_contracts.ValueDomain","biocompiler.ir.component_contracts.PinnedIdentity","biocompiler.ir.components.ComponentLock","biocompiler.ir.composition.LifecycleInterval"],"alias_paths":"unique_closed_typed_field_and_nonnegative_array_index_paths_relative_to_complete_value;exact_class_and_shape;slot_overlap_requires_identical_binding","bindings_by_role":{"behavior_to_synthetic.producer":["generator_config","required_capabilities"],"behavior_to_synthetic.validator":[],"intent_to_behavior.producer":[],"intent_to_behavior.validator":[],"synthetic_to_components.producer":["registry","composition","composition_target"],"synthetic_to_components.validator":[]},"fields":["role","tree","bindings","aliases"],"identity":"explicit_actual_host_objects_or_retained_native_constructor_origins;strong_lifetime_retention;never_equal_content_interning;charged_to_channel_limits","invalid":"view_is_null_only_for_invalid_result","lower_context_tuples":"intent_to_behavior_producer_only;BehaviorNode_inputs_and_BehaviorProgram_roots_reuse_exact_actual_owner_context_input_intent_tuples_after_source_node_identity_and_complete_slot_value_checks;no_extra_manager_calls_or_semantic_parser","role_authority":"actual_fixed_native_closure_and_manager_owner;immutable_provider_registration_binding","roles":["intent_to_behavior.producer","intent_to_behavior.validator","behavior_to_synthetic.producer","behavior_to_synthetic.validator","synthetic_to_components.producer","synthetic_to_components.validator"],"scope":"closed_structural_public_views_only;no_semantic_parsers_or_acceptance;fresh_proposal_and_output_roots","tree":"complete_value_ordered_tree;canonical_projection_matches_value"},"object_reference":{"fields":["handle"],"scope":"one_live_trusted_host_broker_physical_identity"},"obligation_objects":"array_of_actual_host_references_matching_canonical_obligation_slots;whole_tuple_sidecar_preserves_add_input_and_admission_collection_identity;run_allocates_a_new_tuple_reusing_elements;sidecars_do_not_grant_acceptance","operations":{"add-input":{"fields":["identity","stage","requirements","obligations","obligation_objects","payload","obligations_object"],"result":"record"},"admit-component-input":{"fields":["contract_id","identity","payload"],"result":"record"},"artifact":{"fields":["name"],"result":"canonical_immutable_build_artifact"},"build-result":{"fields":["kind"],"result":"fixed_build"},"call-native-provider":{"fields":["provider_id","context_id"],"result":"native_provider_result"},"component-profile":{"fields":["preparation_id"],"result":"completion_profile"},"component-registration":{"fields":["preparation_id"],"result":"component_registration"},"finish-components":{"fields":["preparation_id","record_id","result_sequence"],"result":"fixed_build"},"finish-reference-construct":{"fields":["record_id","result_sequence"],"result":"reference_build"},"finish-reference-molecular":{"fields":["preparation_id","record_id","result_sequence"],"result":"reference_build"},"get":{"fields":["identity"],"result":"record"},"initialize-components":{"fields":["request","request_tree","history","until","config","manager_limits","target_object","request_object","config_object"],"result":"initialization"},"initialize-empty":{"fields":["target","dependencies","completion_profiles","manager_limits","target_object"],"result":"initialization"},"initialize-reference":{"fields":["request","request_tree","registry","registry_tree","manifests","manifests_tree","manager_limits","target_object","request_object","registry_object","construct_manifests_object","molecular_manifests_object","policy_objects"],"result":"initialization"},"initialize-synthetic":{"fields":["request","request_tree","history","until","config","manager_limits","target_object","request_object","config_object"],"result":"initialization"},"inspect":{"fields":[],"result":"historical_observation_only"},"inspect-ordered":{"fields":[],"result":"ordered_historical_observation_only"},"inspect-ordered-references":{"fields":[],"result":"referenced_historical_observation_only"},"prepare-components":{"fields":[],"result":"component_preparation"},"prepare-reference-molecular":{"fields":[],"result":"component_preparation"},"reference-admission":{"fields":[],"result":"reference_admission"},"reference-build-result":{"fields":["kind"],"result":"reference_build"},"reference-molecular-profile":{"fields":["preparation_id"],"result":"completion_profile"},"reference-molecular-registration":{"fields":["preparation_id"],"result":"component_registration"},"reference-registration":{"fields":[],"result":"component_registration"},"register":{"fields":["contract","producer","validators","obligation_objects"],"result":"null"},"register-completion-profile":{"fields":["profile"],"result":"null"},"register-component-input":{"fields":["contract","validators","obligation_objects","obligations_object","requirements_object"],"result":"null"},"result":{"fields":["identity","scope"],"result":"pipeline_result"},"run":{"fields":["pass_id","input_id","output_id","configuration"],"result":"record"},"set-dependency":{"fields":["key","identity"],"result":"null"},"target":{"fields":[],"result":"target"}},"ordered_tree":{"array":["array","ordered_trees"],"object":["object","ordered_unique_key_tree_pairs"],"scalar":["scalar","json_scalar"]},"origin_reference":{"authority":"exact_retained_regular_authoring_objects_and_closed_stored_fields;no_dynamic_attribute_or_property_lookup;representation_only","constant_paths":"empty_only","observable_suffix":"optional_dtype_followed_by_zero_or_more_arguments_nonnegative_integer_pairs","request_paths":[["domain","inputs","nonnegative_integer","observable"],["contract","requirements","nonnegative_integer","observable"],["behavior","nodes","nonnegative_integer","source"]],"roots":["request","BOOLEAN","DURATION","LEVEL","defaultLifecycle","syntheticCapabilities"],"synthetic_capabilities":"empty_path_only;exact_unique_tuple_code_constant_of_audited_original_generate_synthetic;closed_structural_reference_only;never_execute_generator"},"profile":"biocompiler.core.pipeline_callback_manager.v1","provider_reference":{"host":["kind","object"],"native":["kind","provider_id"]},"record_bindings":["record_id","payload","dependencies","requirements","obligations","obligation_objects","checks","provenance"],"record_identity":"one_token_per_actual_native_record_physical_identity_including_rejected_and_stored_before_error_records;not_content_hash_or_import","reference_workflow":{"build":"fresh_closed_candidate_and_check_result_views;exact_historical_public_manager_result;Molecular_construct_is_actual_upstream_Construct_candidate;native_artifact_origins_are_separate_from_frozen_payloads","construct_order":["initialize-reference","reference-admission","actual_register-component-input","actual_admit-component-input","actual_get","reference-registration","actual_register","actual_run","actual_result","finish-reference-construct"],"finish":"actual_run_record_and_result_sequence;historical_result_retained;independent_native_final_checks;no_serialized_acceptance_import","host_result":"reference_producers_only;kind_host_with_actual_paired_PassResult_object_reference;no_conversion_or_acceptance","initialization":"ordered_request_registry_and_manifest_documents_with_exact_canonical_projection;actual_authored_target;one_manager_created_publication","limits":"one_shared_channel_lifetime_work_and_cumulative_retention_for_every_phase_callback_origin_and_build;native_semantic_resource_failures_remain_fatal","molecular_order":["prepare-reference-molecular","six_ordered_actual_set-dependency_calls","reference-molecular-profile","actual_register-completion-profile","reference-molecular-registration","actual_register","actual_run","actual_result","finish-reference-molecular"],"owner":"one_actual_native_manager;source_ordered_public_calls;no_hidden_get_or_result","phase_authority":"actual_successful_manager_operation_objects_and_command_sequence;unrelated_generic_calls_do_not_advance;explicit_wrong_phase_or_foreign_capability_is_fatal","provider_view":{"binding":"actual_per_invocation_parsed_host_object;native_output_physical_identity;no_equal_content_or_last_call_interning","construct_origins":["parsed"],"decision_origins":[],"fields":["role","tree","origins"],"molecular_origins":["parsed","request","translation_policy","encoding_policy","evidence_policy"]},"roles":["reference_components.authority","reference_components.linkage","components_to_construct.producer","components_to_construct.layout","construct_to_molecular.producer","construct_to_molecular.sequence","construct_to_molecular.composition"],"scope":"historical_exact_reference_utilities;not_new_product_backends;no_empirical_or_complete_payload_claim","shared_provider":"reference_components.linkage_is_one_actual_closure_for_component_linkage_and_layout_composition","source_argument":"input_is_actual_context_input;argument_and_tree_are_the_complete_fresh_native_parsed_value;host_origin_binds_both_without_python_semantic_parsing","source_callback":"each_original_callpoint_performs_dynamic_host_default_lookup_after_native_parse;verified_default_runs_native_producer;replacement_runs_once_and_remains_opaque_until_deferred_manager_materialization","source_links":"expected_first_sorted_four_field_tuples;duplicates_preserved;actual_host_attribute_order_equality_and_exceptions"},"results":{"component_preparation":["preparation_id","dependencies"],"component_registration":["contract","producer","validators","obligation_objects"],"fixed_build":["kind","identity","result","artifacts","sources","view"],"initialization":["kind","manager","artifacts","target"],"native_provider_result":["kind","value","view"],"ordered_historical_observation_only":["snapshot","order","providers"],"pipeline_result":["value","artifact"],"record":["value","bindings"],"reference_admission":["contract","validators","obligation_objects"],"reference_build":["build_id","kind","candidate","check_result","result","construct"],"reference_source_result":["kind","argument","output"],"referenced_historical_observation_only":["snapshot","order","providers","record_definitions"],"target":["value","binding"]},"schema_version":"biocompiler.pipeline_callback_manager_declaration.v1","source_links_binding":"null_for_native_context_default_or_complete_host_or_native_collection_binding;tuple_identity_and_element_identity_preserved"}'


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


def _literal_json(value: Any) -> JsonValue:
    """Project only a locally decoded ordered tree back to literal JSON."""
    if type(value) is MappingProxyType:
        return {key: _literal_json(item) for key, item in value.items()}
    if type(value) is tuple:
        return [_literal_json(item) for item in value]
    _require(value is None or type(value) in (bool, int, float, str), 'Malformed native scalar')
    return cast(JsonValue, value)


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


def _strings(value: Any) -> tuple[str, ...]:
    _require(type(value) is list and all(type(item) is str for item in value), 'Malformed native string array')
    return tuple(value)


def _check_view(value: Any) -> Any:
    value = _object(value, {'id', 'evidence_kind', 'discharges'}, 'Inspected check specification')
    _require(type(value['id']) is str and type(value['evidence_kind']) is str, 'Malformed inspected check fields')
    return _raw_fields(CheckSpec, {**value, 'evidence_kind': EvidenceKind(value['evidence_kind']),
        'discharges': _strings(value['discharges'])})


def _contract_view(raw: Any, *, admission: bool) -> Any:
    texts: tuple[str, ...]
    arrays: tuple[str, ...]
    if admission:
        texts = ('id', 'version', 'schema')
        arrays = ('requirements', 'dependency_keys', 'operation_path')
        extra = {'stage', 'checks', 'obligations'}
    else:
        texts = ('id', 'version', 'input_schema', 'output_schema', 'profile', 'profile_version')
        arrays = ('supported_operations', 'dependency_keys', 'required_capabilities', 'consumes_requirements',
            'assumptions', 'changed_properties', 'invalidated_analyses', 'operation_path')
        extra = {'input_stage', 'output_stage', 'checks', 'targets', 'introduces',
            'requires_source_map', 'requires_observation_map'}
    value = _object(raw, set(texts) | set(arrays) | extra, 'Inspected contract')
    _require(all(type(value[key]) is str for key in texts) and type(value['checks']) is list,
        'Malformed inspected contract fields')
    result = {key: value[key] for key in texts}
    result.update({key: _strings(value[key]) for key in arrays})
    result['checks'] = tuple(_check_view(item) for item in value['checks'])
    key = 'obligations' if admission else 'introduces'
    _require(type(value[key]) is list and all(type(item) is dict
        and all(type(field) is str for field in item.values()) for item in value[key]),
        'Malformed inspected contract obligations')
    result[key] = tuple(_obligation(item) for item in value[key])
    if admission:
        _require(value['stage'] == Stage.COMPONENTS.value, 'Malformed inspected admission stage')
        return _raw_fields(ComponentInputContract, result)
    _require(type(value['input_stage']) is str and type(value['output_stage']) is str
        and type(value['requires_source_map']) is bool and type(value['requires_observation_map']) is bool,
        'Malformed inspected pass stage or mapping requirements')
    result.update(input_stage=Stage(value['input_stage']), output_stage=Stage(value['output_stage']),
        targets=tuple(PayloadFormat(item) for item in _strings(value['targets'])),
        requires_source_map=value['requires_source_map'], requires_observation_map=value['requires_observation_map'])
    return _raw_fields(PassContract, result)


def _profile_view(raw: Any) -> Any:
    value = _object(raw, {'scope', 'stage', 'schema', 'obligations'}, 'Inspected completion profile')
    _require(all(type(value[key]) is str for key in ('scope', 'stage', 'schema')), 'Malformed inspected profile fields')
    return _raw_fields(CompletionProfile, {**value, 'stage': Stage(value['stage']), 'obligations': _strings(value['obligations'])})


@dataclass(frozen=True)
class _Binding:
    document: bytes
    flavor: str
    value: Any


@dataclass(frozen=True)
class ManagerInspection:
    """Historical state and the explicitly observed Python dictionary orders.

    Provider values are actual retained local callables. Neither this view nor
    its record envelopes can be imported as current manager acceptance. Nested
    JSON order outside the declared manager and validator maps is not inferred.
    """
    snapshot: Mapping[str, Any]
    order: Mapping[str, Any]
    providers: Mapping[str, Any]


@dataclass(frozen=True)
class ComponentPreparation:
    """An owned native continuation and its ordered dependency publications."""
    identity: str
    dependencies: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ComponentRegistration:
    contract: PassContract
    producer: Callable[..., Any]
    validators: Mapping[str, Callable[..., Any]]


class _NativeProvider:
    """A live native closure capability, minted only by this manager's channel."""
    def __init__(self, manager: CorePassManager, identity: str):
        self._manager = manager
        self._identity = identity

    def __call__(self, context: Any) -> Any:
        return self._manager._call_native(self._identity, context)


_REFERENCE_MANAGER_TYPE: type[Any] | None = None
_REFERENCE_MANAGER_MODULE: ModuleType | None = None


def _register_reference_manager_type(kind: type[Any], module: ModuleType) -> None:
    """Install one exact canonical adapter class, without importing it here."""
    global _REFERENCE_MANAGER_TYPE, _REFERENCE_MANAGER_MODULE
    expected = Path(__file__).resolve().with_name('core_reference_manager.py')
    namespace = vars(module)
    method = vars(kind).get('_reference_prepare')
    _require(type(module) is ModuleType and namespace.get('__name__') == 'biocompiler.core_reference_manager'
        and sys.modules.get('biocompiler.core_reference_manager') is module
        and Path(namespace.get('__file__', '')).resolve() == expected
        and namespace.get('__spec__') is not None
        and Path(namespace['__spec__'].origin).resolve() == expected
        and namespace.get('ReferenceCorePassManager') is kind
        and kind.__module__ == 'biocompiler.core_reference_manager'
        and kind.__name__ == 'ReferenceCorePassManager' and kind.__bases__ == (CorePassManager,)
        and type(method) is FunctionType and method.__globals__ is namespace
        and Path(method.__code__.co_filename).resolve() == expected,
        'Reference native manager class is not its canonical installed source')
    _require(_REFERENCE_MANAGER_TYPE is None or (_REFERENCE_MANAGER_TYPE is kind and _REFERENCE_MANAGER_MODULE is module),
        'Reference native manager class cannot be replaced')
    _REFERENCE_MANAGER_TYPE, _REFERENCE_MANAGER_MODULE = kind, module


def _require_native_manager(value: Any) -> None:
    reference = _REFERENCE_MANAGER_TYPE
    ordinary = type(value) is CorePassManager
    _require(ordinary or (reference is not None and type(value) is reference
        and sys.modules.get('biocompiler.core_reference_manager') is _REFERENCE_MANAGER_MODULE
        and _REFERENCE_MANAGER_MODULE is not None
        and vars(_REFERENCE_MANAGER_MODULE).get('ReferenceCorePassManager') is reference),
        'Custom native manager subclasses require a separate authoring profile')
    namespace = object.__getattribute__(value, '__dict__')
    _require(type(namespace.get('_objects')) is CallbackObjects
        and type(namespace.get('_session')) is CorePipelineCallbackSession,
        'Native manager registration requires its initialized session')


class CorePassManager(PassManager):  # type: ignore[misc]
    """A nominal PassManager whose operations execute in one explicit Core.

    No inherited Python manager constructor, acceptance or freshness method is
    called. Arbitrary contract subclasses are not silently serialized by this
    explicit profile; authored payloads and callbacks remain deferred capabilities.
    """
    _EXTRA_ACTIONS: tuple[str, ...] = ('ordered-json', 'hydrate-context', 'native-provider', 'provider-reference',
                      'set-equal', 'source-link-set-equal', 'origin-reference',
                      'manager-created', 'register-fixed')

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
        self._provider_target_document: JsonValue = target['value']

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
        config = StructuralViews().config(capability_profile()['default_generator_config']) if config is None else config
        if not isinstance(config, SyntheticGeneratorConfig):
            raise TypeError('Expected a SyntheticGeneratorConfig.')
        _require(type(config) is SyntheticGeneratorConfig, 'Custom generator configuration requires deferred authoring')
        if frames is None:
            frames = tuple(history)
        _require(all(type(frame) is InputFrame for frame in frames), 'Native fixed history requires regular InputFrame values')
        manager = cls.__new__(cls)
        manager._prepare(core, application=capability_profile(), limits=limits)
        manager._target = request.target
        manager._provider_request = request
        manager._provider_config = config
        kind = 'components' if components else 'synthetic'
        manager._fixed_initialization = kind
        try:
            request_document = request.to_dict()
            manager._fixed_target_document = request_document['build_request']['target']
            result = manager._call('initialize-' + kind, {'request': request_document,
                'request_tree': _ordered(request_document),
                'history': [frame.to_dict() for frame in frames], 'until': until, 'config': config.to_dict(),
                'manager_limits': manager_limits, 'target_object': manager._objects.retain(request.target),
                'config_object': manager._objects.retain(config), 'request_object': manager._objects.retain(request)})
            _require(manager._fixed_manager_published, 'Fixed initialization omitted its actual manager publication')
            completed = _object(result, {'kind', 'manager', 'artifacts', 'target'}, 'Fixed initialization')
            _require(encode_document(completed['target']) == manager._fixed_target_envelope,
                     'Fixed initialization changed its published target capability')
            manager._initialization(result, kind)
        except BaseException:
            response = manager._session.last_response
            retained = (manager._fixed_manager_published and not manager._session.closed
                and not manager._session.invalidated and response is not None
                and response.operation == 'initialize-' + kind and response.status in ('rejected', 'raise'))
            if not retained:
                manager._session._invalidate()
                manager._objects.close()
            raise
        finally:
            manager._fixed_initialization = None
            manager._fixed_target_document = None
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
        _require_native_manager(self)
        # Keep the current public base slot observable by existing wrappers.
        PassManager.register(self, contract, producer, validators)

    def _native_register(self, contract: Any, producer: Callable[..., Any], validators: Mapping[str, Callable[..., Any]]) -> None:
        _require_native_manager(self)
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
        result = self._view(self._result_value, raw, 'pipeline result')
        response = self._session.last_response
        _require(response is not None and type(response.sequence) is int, 'Native result omitted its command receipt')
        assert response is not None
        signature = encode_document(raw)
        if len(self._result_receipts) >= self._objects.limits.max_objects or self._result_retained_bytes + len(signature) + 256 > 134_217_728:
            self._session._invalidate()
            raise CoreProtocolError('Public result receipt retention limit exceeded')
        self._result_retained_bytes += len(signature) + 256
        self._result_receipts[id(result)] = (result, response.sequence, signature)
        return result

    def build_result(self, kind: str) -> SyntheticBuild | ComponentBuild:
        """View an actual historical fixed build without rerunning manager checks."""
        _require(kind in ('synthetic', 'components'), 'Unknown completed build kind')
        raw = self._call('build-result', {'kind': kind})
        return self._build_value(raw, kind=kind, result=self._result_value)

    def _build_value(self, raw: JsonValue, *, kind: str,
                     result: Callable[[JsonValue], PipelineResult]) -> SyntheticBuild | ComponentBuild:
        try:
            return cast(SyntheticBuild | ComponentBuild, self._view(
                lambda value: self._build_views.decode(value, kind=kind, manager=self, result=result,
                    record=self._record, requested_config=self._provider_config), raw, 'completed build'))
        except BaseException:
            self._session._invalidate()
            raise

    def prepare_components(self) -> ComponentPreparation:
        raw = self._call('prepare-components', {})
        return cast(ComponentPreparation, self._view(self._component_preparation, raw, 'component preparation'))

    def _component_preparation(self, raw: JsonValue) -> ComponentPreparation:
        value = _object(raw, {'preparation_id', 'dependencies'}, 'Component preparation')
        identity = _identity(value['preparation_id'])
        _require(identity not in self._preparations and type(value['dependencies']) is list,
            'Component preparation was reused or malformed')
        _require(len(self._preparations) < self._objects.limits.max_objects, 'Component preparation identity limit exceeded')
        entries: list[tuple[str, str]] = []
        seen: set[str] = set()
        for pair in value['dependencies']:
            _require(type(pair) is list and len(pair) == 2 and all(type(item) is str for item in pair)
                and pair[0] not in seen, 'Malformed or repeated prepared dependency')
            seen.add(pair[0])
            entries.append((pair[0], pair[1]))
        result = ComponentPreparation(identity, tuple(entries))
        self._preparations[identity] = result
        return result

    def _preparation_id(self, preparation: ComponentPreparation) -> str:
        _require(type(preparation) is ComponentPreparation and self._preparations.get(preparation.identity) is preparation,
            'Component preparation does not belong to this manager')
        return preparation.identity

    def component_profile(self, preparation: ComponentPreparation) -> CompletionProfile:
        raw = self._call('component-profile', {'preparation_id': self._preparation_id(preparation)})
        return cast(CompletionProfile, self._view(_profile_view, raw, 'component completion profile'))

    def component_registration(self, preparation: ComponentPreparation) -> ComponentRegistration:
        raw = self._call('component-registration', {'preparation_id': self._preparation_id(preparation)})
        return cast(ComponentRegistration, self._view(self._component_registration, raw, 'component registration'))

    def _component_registration(self, raw: JsonValue) -> ComponentRegistration:
        return self._fixed_registration(raw, expected_pass='synthetic_to_components')

    def _fixed_registration(self, raw: JsonValue, *, expected_pass: str | None = None) -> ComponentRegistration:
        value = _object(raw, {'contract', 'producer', 'validators', 'obligation_objects'}, 'Fixed registration')
        contract = _contract_view(value['contract'], admission=False)
        _require(contract.id in ('intent_to_behavior', 'behavior_to_synthetic', 'synthetic_to_components')
            and (expected_pass is None or contract.id == expected_pass), 'Unexpected fixed registration contract')
        _require(type(value['obligation_objects']) is list and len(value['obligation_objects']) == len(contract.introduces),
            'Prepared obligation origin census differs')
        for binding in value['obligation_objects']:
            origin = _object(binding, {'kind', 'identity', 'tree'}, 'Prepared native obligation origin')
            _require(origin['kind'] == 'native', 'Prepared obligation must retain its declared native origin')
        obligations = tuple(self._binding(item, flavor='obligation') for item in value['obligation_objects'])
        for declared, actual in zip(contract.introduces, obligations):
            _require(type(actual) is ScopedObligation and vars(actual) == vars(declared),
                'Prepared obligation differs from its declared native origin')
        object.__setattr__(contract, 'introduces', obligations)
        producer = self._objects.resolve(value['producer'])
        _require(type(producer) is _NativeProvider and producer._manager is self
            and self._native_providers.get(producer._identity) is producer
            and self._native_provider_roles[producer._identity] == contract.id + '.producer',
            'Prepared producer is not its actual native closure')
        _require(type(value['validators']) is list, 'Malformed prepared validator order')
        validators: dict[str, Callable[..., Any]] = {}
        for pair in value['validators']:
            _require(type(pair) is list and len(pair) == 2 and type(pair[0]) is str and pair[0] not in validators,
                'Malformed or repeated prepared validator')
            validator = self._objects.resolve(pair[1])
            _require(type(validator) is _NativeProvider and validator._manager is self
                and self._native_providers.get(validator._identity) is validator
                and self._native_provider_roles[validator._identity] == contract.id + '.validator',
                'Prepared validator is not its actual native closure')
            validators[pair[0]] = validator
        _require(set(validators) == {check.id for check in contract.checks}, 'Prepared validator census differs from contract')
        return ComponentRegistration(contract, producer, validators)

    def finish_components(self, preparation: ComponentPreparation, result: PipelineResult) -> ComponentBuild:
        identity = self._preparation_id(preparation)
        retained = self._result_receipts.get(id(result))
        _require(retained is not None and retained[0] is result, 'Component finish requires its actual public result wrapper')
        assert retained is not None
        artifact = result.artifact
        _require(self._records.get(artifact.id) is artifact, 'Component finish result has a foreign artifact')
        raw = self._call('finish-components', {'preparation_id': identity,
            'record_id': self._record_bindings[artifact.id][0], 'result_sequence': retained[1]})
        def retained_result(envelope: JsonValue) -> PipelineResult:
            _require(encode_document(envelope) == retained[2], 'Completed build changed its actual result response')
            return result
        built = self._build_value(raw, kind='components', result=retained_result)
        _require(type(built) is ComponentBuild and built.result is result, 'Completed component build replaced its public result')
        return cast(ComponentBuild, built)

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

    def inspect_ordered(self) -> ManagerInspection:
        raw = self._call('inspect-ordered', {})
        return cast(ManagerInspection, self._view(self._ordered_inspection, raw, 'ordered manager inspection'))

    def inspect_ordered_references(self) -> ManagerInspection:
        """Inspect full historical state using immutable record definitions once.

        Only transport repetition is removed. Each call still observes the
        native manager; stored record views retain their original identities.
        """
        raw = self._call('inspect-ordered-references', {})
        return cast(ManagerInspection, self._view(self._referenced_inspection, raw, 'referenced manager inspection'))

    def _referenced_inspection(self, raw: JsonValue) -> ManagerInspection:
        envelope = _object(raw, {'snapshot', 'order', 'providers', 'record_definitions'}, 'Referenced inspection')
        snapshot, order = envelope['snapshot'], envelope['order']
        _require(type(snapshot) is dict and type(snapshot.get('records')) is dict
            and type(order) is dict and type(order.get('records')) is list, 'Malformed referenced record inventory')
        records, names = snapshot['records'], order['records']
        _require(all(type(name) is str for name in names) and len(names) == len(records)
            and set(names) == set(records), 'Incomplete or repeated referenced record order')
        references: dict[str, str] = {}
        for name in names:
            reference = _object(records[name], {'record_id'}, 'Historical record reference')
            references[name] = _identity(reference['record_id'])
        _require(len(set(references.values())) == len(references), 'Record incarnation has multiple snapshot names')
        new = [(name, token) for name, token in references.items() if token not in self._inspection_record_ids]
        definitions = envelope['record_definitions']
        _require(type(definitions) is list and len(definitions) == len(new), 'Incomplete or repeated record definitions')
        _require(len(self._inspection_record_ids) + len(new) <= self._objects.limits.max_objects,
            'Inspection record identity limit exceeded')
        pending: dict[str, str] = {}
        for (name, token), definition in zip(new, definitions):
            value = _object(definition, {'value', 'bindings'}, 'Inspection record definition')
            _require(type(value['bindings']) is dict and value['bindings'].get('record_id') == token,
                'Record definition differs from its first-reference order')
            record = self._record(value)
            _require(record.id == name, 'Record definition has another snapshot name')
            pending[token] = name
        known = {**self._inspection_record_ids, **pending}
        expanded: dict[str, JsonValue] = {}
        for name, token in references.items():
            _require(known.get(token) == name and name in self._record_envelopes
                and self._record_bindings[name][0] == token, 'Unknown or rebound inspection record reference')
            # The existing cache contains the complete checked immutable
            # envelope. This makes no native get/result or freshness query.
            expanded[name] = decode_document(self._record_envelopes[name])
        result = self._ordered_inspection({'snapshot': {**snapshot, 'records': expanded},
            'order': order, 'providers': envelope['providers']})
        self._inspection_record_ids.update(pending)
        return result

    def inspection_state(self) -> dict[str, Any]:
        """Observe typed historical state without invoking freshness or acceptance.

        The returned dictionaries are detached mutable views, in original
        insertion order. Callables, target and stored records retain their actual
        identities. The complete native receipt remains ``session.last_response``.
        """
        inspected = self.inspect_ordered()
        return cast(dict[str, Any], self._view(self._inspection_state, inspected, 'typed historical manager state'))

    def _inspection_state(self, inspected: ManagerInspection) -> dict[str, Any]:
        snapshot, providers = inspected.snapshot, inspected.providers
        _require(encode_document(_literal_json(snapshot['target'])) == encode_document(self._target.to_dict()),
            'Inspected target differs from the supplied target')
        registrations: dict[str, dict[str, Any]] = {}
        for name in ('passes', 'component_inputs', 'provider_history', 'component_input_history'):
            admission = name in ('component_inputs', 'component_input_history')
            values: dict[str, Any] = {}
            for key, row in snapshot[name].items():
                contract = _contract_view(_literal_json(row['contract']), admission=admission)
                validators = {check: providers[token] for check, token in row['validators'].items()}
                values[key] = (contract, validators) if admission else (contract, providers[row['producer']], validators)
            registrations[name] = values
        history: dict[Any, Any] = {}
        for key in inspected.order['combined_provider_history']:
            if type(key) is str:
                history[key] = registrations['provider_history'][key]
            else:
                history[key] = registrations['component_input_history'][key[1]]
        return {'_target': self._target, '_dependencies': dict(snapshot['dependencies']),
            '_passes': registrations['passes'], '_component_inputs': registrations['component_inputs'],
            '_provider_history': history, '_records': {key: self._records[key] for key in snapshot['records']},
            '_profiles': {key: _profile_view(_literal_json(value)) for key, value in snapshot['profiles'].items()}}

    def _ordered_inspection(self, raw: JsonValue) -> ManagerInspection:
        envelope = _object(raw, {'snapshot', 'order', 'providers'}, 'Ordered manager inspection')
        maps = ('dependencies', 'passes', 'component_inputs', 'provider_history',
                'component_input_history', 'records', 'profiles')
        registrations = {'passes', 'component_inputs', 'provider_history', 'component_input_history'}
        snapshot = _object(envelope['snapshot'], set(maps) | {'target'}, 'Manager inspection snapshot')
        order = _object(envelope['order'], set(maps) | {'validators', 'combined_provider_history'}, 'Manager inspection order')
        validator_order = _object(order['validators'], registrations, 'Validator map orders')
        _require(type(snapshot['target']) is dict, 'Manager inspection target must be an object')

        def ordered_keys(keys: Any, values: Any, label: str) -> None:
            _require(type(values) is dict and type(keys) is list
                and all(type(key) is str for key in keys)
                and len(keys) == len(values) and set(keys) == set(values),
                'Incomplete or repeated ' + label + ' order')

        referenced: set[str] = set()
        observed: dict[str, Any] = {'target': snapshot['target']}
        for name in maps:
            values, keys = snapshot[name], order[name]
            ordered_keys(keys, values, name)
            observed[name] = {key: values[key] for key in keys}
            if name not in registrations:
                continue
            orders = _object(validator_order[name], set(values), name + ' validator orders')
            for key, registration in observed[name].items():
                fields = {'contract', 'validators'}
                if name in ('passes', 'provider_history'):
                    fields.add('producer')
                row = _object(registration, fields, 'Inspected registration')
                _require(type(row['contract']) is dict, 'Inspected contract must be an object')
                ordered_keys(orders[key], row['validators'], 'validator')
                row = {**row, 'validators': {item: row['validators'][item] for item in orders[key]}}
                observed[name][key] = row
                if 'producer' in row:
                    referenced.add(_identity(row['producer']))
                referenced.update(_identity(provider) for provider in row['validators'].values())
        for key, record in observed['records'].items():
            _require(self._record(record).id == key, 'Inspection record key differs from its actual incarnation')

        combined = order['combined_provider_history']
        _require(type(combined) is list, 'Combined provider history must be an array')
        passes: list[str] = []
        admissions: list[str] = []
        for entry in combined:
            if type(entry) is str:
                passes.append(entry)
            else:
                _require(type(entry) is list and len(entry) == 2
                    and entry[0] == 'component_input' and type(entry[1]) is str,
                    'Malformed combined provider history key')
                admissions.append(entry[1])
        _require(passes == order['provider_history'] and admissions == order['component_input_history'],
            'Combined provider history omits, repeats or reorders a registration')

        _require(type(envelope['providers']) is list, 'Provider bindings must be an array')
        providers: dict[str, Any] = {}
        physical: dict[int, str] = {}
        for entry in envelope['providers']:
            entry = _object(entry, {'provider_id', 'object'}, 'Inspected provider binding')
            identity = _identity(entry['provider_id'])
            _require(identity in referenced and identity not in providers, 'Extra or repeated inspected provider token')
            actual = self._objects.resolve(entry['object'])
            _require(callable(actual), 'Inspected provider is not an actual callable')
            other = physical.get(id(actual), self._inspection_provider_ids.get(id(actual)))
            _require(other is None or other == identity, 'Actual callable was rebound to another native provider token')
            previous = self._inspection_providers.get(identity)
            _require(previous is None or previous is actual, 'Native provider token was rebound to another callable')
            if type(actual) is _NativeProvider:
                _require(actual._manager is self and actual._identity == identity
                    and self._native_providers.get(identity) is actual, 'Foreign or forged inspected native provider')
            providers[identity] = actual
            physical[id(actual)] = identity
        _require(set(providers) == referenced, 'Inspection omitted a reachable actual provider')
        _require(len(set(self._inspection_providers) | referenced) <= self._objects.limits.max_providers,
            'Inspected provider identity limit exceeded')
        self._inspection_providers.update(providers)
        self._inspection_provider_ids.update(physical)
        return ManagerInspection(_frozen(observed), _frozen(order), MappingProxyType(providers))

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
        _require(identity not in self._provider_views.native and identity not in self._build_views.artifacts
            and identity not in self._build_views.builds, 'Obligation identity collides with a typed view')
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
        self._native_provider_roles: dict[str, str] = {}
        self._provider_views = ProviderViewStore(self._objects.resolve, max_objects=self._objects.limits.max_objects,
            identity_taken=lambda identity: identity in self._bindings
                or identity in self._build_views.artifacts or identity in self._build_views.builds)
        self._build_views = BuildViewStore(self._provider_views, max_objects=self._objects.limits.max_objects,
            identity_taken=lambda identity: identity in self._bindings)
        self._preparations: dict[str, ComponentPreparation] = {}
        self._result_receipts: dict[int, tuple[PipelineResult, int, bytes]] = {}
        self._result_retained_bytes = 0
        self._provider_request: object = None
        self._provider_config: SyntheticGeneratorConfig | None = None
        self._provider_target_document = None
        self._fixed_initialization: str | None = None
        self._fixed_manager_published = False
        self._fixed_target_document: JsonValue = None
        self._fixed_target_envelope: bytes | None = None
        self._inspection_providers: dict[str, Any] = {}
        self._inspection_provider_ids: dict[int, str] = {}
        self._records: dict[str, Any] = {}
        self._record_bindings: dict[str, tuple[str, bytes]] = {}
        self._record_envelopes: dict[str, bytes] = {}
        self._inspection_record_ids: dict[str, str] = {}
        self._target = None
        # Keep these callable objects stable. Merely dispatching an action must
        # not allocate a fresh bound-method identity in the retained registry.
        self._set_equal = lambda value, values: set(value) == set(values)
        self._source_link_equal = lambda values, expected: set(values) == set(expected)
        self._ordered_callable = _ordered
        self._fixed_register_callable = self._register_fixed
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

    def _register_fixed(self, contract: PassContract, producer: Callable[..., Any],
                        validators: Mapping[str, Callable[..., Any]]) -> None:
        # The original caller discards register's return; no conversion or
        # retention of an arbitrary wrapper return may introduce a new effect.
        self.register(contract, producer, validators)

    def _invoke(self, action: str, arguments: JsonValue) -> HostCompletion:
        if action == 'manager-created':
            _require(self._fixed_initialization is not None and not self._fixed_manager_published,
                     'Unexpected or repeated fixed manager publication')
            args = _object(arguments, {'target'}, 'Fixed manager publication')
            target = _object(args['target'], {'value', 'binding'}, 'Published fixed target')
            _require(self._binding(target['binding'], flavor='target') is self._target,
                     'Published fixed manager changed its actual authored target')
            _require(encode_document(target['value']) == encode_document(self._fixed_target_document),
                     'Published fixed target differs from the exact authored document')
            self._provider_target_document = target['value']
            self._fixed_target_envelope = encode_document(args['target'])
            self._fixed_manager_published = True
            return self._ok(None)
        if action == 'register-fixed':
            _require(self._fixed_initialization is not None and self._fixed_manager_published,
                     'Fixed registration requires its active published manager')
            registration = self._fixed_registration(arguments)
            completion = self._host_call(self._fixed_register_callable,
                registration.contract, registration.producer, registration.validators)
            return self._ok(None) if completion.status == 'ok' else completion
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
            args = _object(arguments, {'provider_id', 'role'}, 'Native provider action')
            identity, role = _identity(args['provider_id']), args['role']
            _require(type(role) is str and role in PROVIDER_ROLES, 'Unknown native provider closure role')
            previous = self._native_providers.get(identity)
            if previous is None:
                previous = _NativeProvider(self, identity)
                self._native_providers[identity] = previous
                self._native_provider_roles[identity] = role
            else:
                _require(self._native_provider_roles[identity] == role, 'Native provider closure role was rebound')
            return self._ok(self._objects.retain(previous))
        if action == 'origin-reference':
            args = _object(arguments, {'root', 'path'}, 'Native provider origin action')
            _require(type(args['root']) is str, 'Provider origin root must be a string')
            return self._ok(self._objects.retain(origin_reference(self._provider_request, args['root'], args['path'])))
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
        _require(identity not in self._provider_views.native and identity not in self._build_views.artifacts
            and identity not in self._build_views.builds, 'Native view identity collides with a typed view')
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
        _require(identity in self._native_provider_roles, 'Unknown native provider capability')
        return self._native_return(self._call('call-native-provider', {'provider_id': identity, 'context_id': token}),
            role=self._native_provider_roles[identity], input_payload=context.input)

    def _native_return(self, value: JsonValue, *, role: str, input_payload: FrozenJson = None) -> PassResult[ProviderOutput] | CheckDecision | FrozenJson:
        try:
            return self._view(lambda raw: self._provider_views.decode(raw, role=role, target=self._target,
                target_document=self._provider_target_document, requested_config=self._provider_config,
                input_payload=input_payload), value, 'provider result')
        except BaseException:
            # A partially materialized typed graph has no reusable authority,
            # including when allocation or cancellation interrupts hydration.
            self._session._invalidate()
            raise

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
        value = _object(raw, {'module', 'type', 'message', 'attributes', 'attributes_tree'}, 'Native application exception')
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
        # Exception snapshots are independent recursive copies, not retained
        # context bindings. Canonical bytes distinguish bool/int/float values
        # that Python equality would otherwise conflate.
        attributes = _unordered(value['attributes_tree'])
        _require(type(attributes) is MappingProxyType, 'Native exception attributes must be an ordered object')
        _require(encode_document(_literal_json(attributes)) == encode_document(value['attributes']),
                 'Native exception attributes differ from their ordered tree')
        if cls is NoCandidateFound:
            _require(tuple(attributes) == ('pass_id', 'configuration', 'dependencies'),
                     'No-candidate exception attributes have missing, unknown or misordered fields')
            _require(type(attributes['pass_id']) is str
                and type(attributes['configuration']) is MappingProxyType
                and type(attributes['dependencies']) is MappingProxyType
                and all(type(item) is str for item in attributes['dependencies'].values()),
                'Malformed no-candidate exception attribute kinds')
            error: BaseException = cls.__new__(cls)
            BaseException.__init__(error, value['message'])
            for key, item in attributes.items():
                object.__setattr__(error, key, item)
            return error
        _require(not attributes, 'Unexpected native exception attributes')
        return cast(BaseException, cls(value['message']))
