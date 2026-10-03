open Bioc_wire
open Bioc_domain
module M = Bioc_compiler.Pass_manager
module W = Bioc_checker.Work_budget
module C = Pipeline_contract
module Ch = Callback_channel
module H = Host_bridge
module S = Bioc_pipeline.Synthetic_pipeline
module P = Bioc_pipeline.Component_pipeline
module G = Bioc_synthetic_producer.Generator
module V = Fixed_provider_views
module RC = Bioc_pipeline.Reference_construct_pipeline
module RM = Bioc_pipeline.Reference_molecular_pipeline
module RW = Reference_workflow
module RD = Reference_construct
module RG = Bioc_compiler.Reference_construct_producer
module RE = Bioc_compiler.Reference_sequence_emitter
let declaration=Json.parse {declaration|{"acceptance":"native_manager_checks_and_freshness_only;inspection_and_host_sidecars_cannot_import_accepted_records","actions":{"hydrate-context":{"fields":["context_id","document","bindings"],"result":"object_reference"},"manager-created":{"fields":["target"],"result":"null"},"native-provider":{"fields":["provider_id","role"],"result":"object_reference"},"ordered-json":{"fields":["object"],"result":"ordered_tree"},"ordered-merge":{"fields":["object","before","after","before_tree","after_tree"],"result":"object_reference"},"origin-reference":{"fields":["root","path"],"result":"object_reference"},"provider-reference":{"fields":["object"],"result":"host_or_native_provider_reference"},"reference-emit":{"fields":["input","argument","tree"],"result":"reference_source_result"},"reference-generate":{"fields":["input","argument","tree"],"result":"reference_source_result"},"reference-proposal":{"fields":["output","source_links"],"result":"object_reference"},"reference-source-links-equal":{"fields":["actual","expected"],"result":"boolean"},"reference-upstream-candidate":{"fields":["upstream","phase"],"result":"reference_upstream_candidate"},"register-fixed":{"fields":["contract","producer","validators","obligation_objects"],"result":"null"},"set-equal":{"fields":["object","values"],"result":"boolean"},"source-link-set-equal":{"fields":["objects","expected"],"result":"boolean"}},"argument":"--pipeline-callback-session-v1","authoring_boundary":"canonical_typed_contract_target_profile_fields;opaque_payload_configuration_provider_and_validator_objects_are_read_at_native_requested_points","bindings":{"host":["kind","object"],"native":["kind","identity","tree"]},"broker_actions":{"attr":{"fields":["object","name"],"result":"object_reference"},"attr-default":{"fields":["object","name","default"],"result":"object_reference"},"bind-provider":{"fields":["provider_id","object"],"result":"null"},"call":{"fields":["callable","args","kwargs"],"result":"object_reference"},"call-provider":{"fields":["provider_id","context"],"result":"object_reference"},"callable":{"fields":["object"],"result":"boolean"},"compare":{"fields":["left","right","operator"],"result":"boolean"},"contains":{"fields":["container","item"],"result":"boolean"},"dict":{"fields":["object"],"result":"object_reference"},"document":{"fields":["object"],"result":"object_reference"},"enum":{"fields":["type","value"],"result":"object_reference"},"freeze-json":{"fields":["object"],"result":"object_reference"},"get-item":{"fields":["object","key"],"result":"object_reference"},"is-instance":{"fields":["object","type"],"result":"boolean"},"is-none":{"fields":["object"],"result":"boolean"},"iter":{"fields":["object"],"result":"object_reference"},"json":{"fields":["object"],"result":"json"},"len":{"fields":["object"],"result":"integer"},"list":{"fields":["object"],"result":"object_reference"},"literal":{"fields":["kind","value"],"result":"object_reference"},"lookup":{"fields":["object","entries"],"result":"object_reference"},"mapping-items":{"fields":["object"],"result":"object_reference"},"mapping-keys":{"fields":["object"],"result":"object_reference"},"mapping-values":{"fields":["object"],"result":"object_reference"},"merge":{"fields":["object","before","after"],"result":"object_reference"},"next":{"fields":["object"],"result":"iterator_step"},"release":{"fields":["handles"],"result":"null"},"set-attribute-equal":{"fields":["objects","name","values"],"result":"boolean"},"truth":{"fields":["object"],"result":"boolean"},"tuple":{"fields":["object"],"result":"object_reference"},"vars":{"fields":["object"],"result":"object_reference"}},"channel":"biocompiler.pipeline_callback_channel.v1","claim_scope":"software_contract_conditional_translation_and_scoped_completion;no_empirical_or_human_use_acceptance","comparison_operators":["eq","ne","is","is-not"],"compatibility_pending":["complete_original_installed_replay","fixed_public_registration_interception","arbitrary_authoring_subclass_and_scalar_operator_semantics","default_cutover"],"component_continuation":{"failure":"actual_partial_manager_and_previous_successful_mutations_preserved_on_logical_or_host_failure;fatal_channel_failures_close_authority","finish":"exact_retained_actual_run_record_incarnation_and_matching_actual_result_command_sequence_owner_stage_scope;no_recomputation_or_import_of_accepted_result","limits":"all_preparations_origins_build_views_and_retained_result_receipts_charged_to_channel_lifetime_work_and_retention","obligation_objects":"ordered_native_binding_descriptors_matching_contract_introduces_slots;structural_host_views_returned_as_strong_host_references_during_actual_register;native_validation_remains_authoritative","order":["prepare-components","ordered_actual_set-dependency_calls","component-profile","actual_register-completion-profile","component-registration","actual_register","actual_run","actual_result","finish-components"],"owner":"same_live_manager_and_actual_retained_synthetic_build;one_preparation_attempt;preparation_id_is_channel_scoped_native_capability","preparation":"native_adaptation_and_ordered_dependencies_only;profile_and_registration_constructors_remain_after_prior_actual_mutations","registration":"actual_native_contract_and_physical_fixed_producer_and_validator_closures;ordered_validator_name_and_host_reference_pairs"},"context_bindings":["input","output","target","configuration","dependencies","requirements","source_links","observation_map"],"context_identity":"actual_native_context_physical_identity;distinct_producer_and_validation_contexts;one_validation_context_shared_by_its_validators","default_generator_config":{"catalog_fingerprint":"f2a4b4c1625b4794028fcd1d0e08785724f957023966a29faafe9374cca77343","conjunction_strategy":"native","generator_version":"biocompiler.synthetic.generator.v0.4","profile_version":"biocompiler.synthetic.combinational.v0.1","schema_version":"biocompiler.synthetic_generator_config.v0.3","witness_selection":"closed_band_lower_endpoint"},"default_generator_config_authority":"exact_negotiated_native_Config_make_default;fresh_closed_Python_representation_before_initialization;native_import_and_catalog_validation_remain_authoritative","dependencies_encoding":"ordered_unique_string_identity_pairs","enum_types":["EvidenceKind","CheckOutcome","Stage","ArtifactStatus","PayloadFormat"],"executable":"core","expected_rejection_attributes":"fresh_ordered_tree_with_exact_canonical_attributes_projection;no_cached_binding_or_context_container_reuse;NoCandidateFound_retains_pass_configuration_and_dependency_order","expected_rejection_fields":["module","type","message","attributes","attributes_tree"],"failure":"expected_logical_rejection_and_opaque_host_exception_preserve_actual_partial_manager;malformed_resource_internal_or_uncertain_io_failure_closes_authority","fixed_build_view":{"absent_selection":"value_and_binding_null;selection_config_and_required_capabilities_null;alternative_configs_empty_and_no_selection_aliases;candidate_type_aliases_remain_required","aliases":"selection_paths_start_selection_result_alternatives_nonnegative_index_candidate_then_closed_typed_candidate_path_with_same_eight_provider_alias_tags;candidate_paths_only_TypeSpec_at_candidate_mechanism_nodes_nonnegative_index_output_dtype;no_assembly_or_report_aliases","alternative_configs":"ordered_candidate_slots;null_only_without_candidate;native_constructor_origin_bindings;selected_slot_reuses_actual_fixed_provider_selected_config_origin","artifact_fields":["value","binding"],"artifact_identity":"dedicated_retained_actual_build_artifact_origins;never_manager_frozen_json_or_provider_output_roots;upstream_candidate_and_selection_shared_only_from_actual_retained_synthetic_build","artifacts":{"components":["candidate","selection_result","assembly","link_result","behavior_result"],"synthetic":["candidate","selection_result"]},"candidate_source":"actual_historical_upstream_mechanism_record_envelope;parsed_node_inputs_and_requirement_ids_and_program_outputs_and_required_capabilities_retain_source_tuple_identity","candidate_type_origins":"one_retained_actual_parsed_type_origin_per_upstream_candidate_physical_identity_node_and_argument_path;distinct_even_when_fields_equal;same_origin_used_by_actual_component_provider_registry_descendants","fields":["selection_config","alternative_configs","required_capabilities","aliases"],"fresh_roots":"parsed_candidate_and_assembly_are_fresh_from_original_frozen_payload;assembly_composition_target_is_fresh_and_not_manager_target","kinds":["synthetic","components"],"required_capabilities":"null_without_selection_candidates;otherwise_actual_syntheticCapabilities_constant_host_binding;only_generated_selection_and_provider_candidates_share_this_tuple","result":"actual_historical_pipeline_result_and_record_envelope;finish_reuses_exact_public_result_wrapper_from_result_sequence;historical_views_do_not_grant_fresh_acceptance","selection_config":"actual_requested_host_configuration","sources":["candidate"]},"fixed_registration":{"failure":"published_manager_retained_only_after_exact_completed_rejected_or_opaque_raise_initialization_reply_on_open_channel;fatal_or_uncertain_channel_closes_authority","hook":"source_ordered_actual_fixed_contract_native_producer_ordered_validators_and_introduced_obligations;invoke_current_public_register_once;ignore_return_without_inspection;no_implicit_fallback","native_registration":"only_actual_nested_register_commands_mutate_the_live_manager;producer_wrappers_and_original_native_validator_identity_preserved","publication":"exact_actual_manager_and_authored_target_before_first_input_or_registration;once_per_fixed_initialization;no_manager_replacement","roles":["intent_to_behavior","behavior_to_synthetic","synthetic_to_components"],"staged_components":"existing_actual_public_register_call_only;no_second_register_fixed_hook;unchanged_contract_and_actual_native_validator_enable_host_source_link_capability_independently_of_producer_wrapper"},"fixed_request_tree":"ordered_tree_from_same_authoring_serialization_as_request;exact_canonical_projection_required_before_native_import;retained_order_is_not_acceptance","host_execution":"trusted_host_code_cpu_and_opaque_captures_outside_native_work_and_json_memory_bounds","inspection_order":{"combined_provider_history":"actual_successful_insertion_order;pass_fingerprint_string_or_component_input_tag_and_fingerprint_pair;replacements_preserve_position","fields":["dependencies","passes","component_inputs","provider_history","component_input_history","records","profiles","combined_provider_history","validators"],"mapping_order":"unique_complete_snapshot_key_arrays","provider_fields":["provider_id","object"],"providers":"exact_reachable_snapshot_provider_token_census;stable_bijection_to_actual_retained_callable_identity;no_user_equality_or_hash","scope":"manager_mapping_and_validator_order_only;nested_unobserved_json_order_not_generalized;historical_observation_cannot_grant_acceptance","validator_maps":["passes","component_inputs","provider_history","component_input_history"],"validators":"four_exact_registration_maps_of_unique_complete_validator_key_arrays"},"inspection_references":{"authority":"inspection_only;references_cannot_import_records_or_grant_fresh_acceptance;existing_inspect_ordered_unchanged","definitions":"ordered_complete_record_envelopes_exactly_for_first_compact_publication_of_each_actual_record_incarnation_in_order_records;no_duplicates_unused_definitions_or_rebinding","record_reference_fields":["record_id"],"resolution":"same_channel_earlier_or_current_definitions_only;exact_record_name_and_incarnation_bijection;checked_immutable_full_envelope_expansion_without_get_result_or_acceptance_query","retention":"strong_actual_record_identity_and_definition_publication_census_charged_to_existing_channel_lifetime;publication_marked_only_after_complete_response_assembly","snapshot":"same_complete_historical_state_as_inspect_ordered_with_records_replaced_by_incarnation_references;all_other_fields_and_orders_unchanged"},"iterator_step_fields":["exhausted","object"],"lifecycle":"one_initialization_attempt_per_channel;existing_channel_close_is_top_level_only;no_reconnect_retry_or_state_import","limits":"all_native_framing_application_import_callback_and_publication_work_uses_one_channel_lifetime_ancestor;retention_is_cumulative_no_refund","literal_kinds":["json","tuple","set"],"manager_limits":"initialization_once;null_defaults_or_complete_positive_integer_reductions","native_provider_context":"only_exact_retained_context_from_this_live_manager;no_external_context_import","native_provider_result_kinds":["proposal","decision","invalid"],"native_provider_view":{"alias_fields":["kind","paths","binding"],"alias_kinds":["biocompiler.ir.intent.SourceLocation","biocompiler.semantics.types.TypeSpec","biocompiler.semantics.realization.Observable","biocompiler.semantics.component_contracts.OperatingDomain","biocompiler.semantics.component_contracts.ValueDomain","biocompiler.ir.component_contracts.PinnedIdentity","biocompiler.ir.components.ComponentLock","biocompiler.ir.composition.LifecycleInterval"],"alias_paths":"unique_closed_typed_field_and_nonnegative_array_index_paths_relative_to_complete_value;exact_class_and_shape;slot_overlap_requires_identical_binding","bindings_by_role":{"behavior_to_synthetic.producer":["generator_config","required_capabilities"],"behavior_to_synthetic.validator":[],"intent_to_behavior.producer":[],"intent_to_behavior.validator":[],"synthetic_to_components.producer":["registry","composition","composition_target"],"synthetic_to_components.validator":[]},"fields":["role","tree","bindings","aliases"],"identity":"explicit_actual_host_objects_or_retained_native_constructor_origins;strong_lifetime_retention;never_equal_content_interning;charged_to_channel_limits","invalid":"view_is_null_only_for_invalid_result","lower_context_tuples":"intent_to_behavior_producer_only;BehaviorNode_inputs_and_BehaviorProgram_roots_reuse_exact_actual_owner_context_input_intent_tuples_after_source_node_identity_and_complete_slot_value_checks;no_extra_manager_calls_or_semantic_parser","role_authority":"actual_fixed_native_closure_and_manager_owner;immutable_provider_registration_binding","roles":["intent_to_behavior.producer","intent_to_behavior.validator","behavior_to_synthetic.producer","behavior_to_synthetic.validator","synthetic_to_components.producer","synthetic_to_components.validator"],"scope":"closed_structural_public_views_only;no_semantic_parsers_or_acceptance;fresh_proposal_and_output_roots","tree":"complete_value_ordered_tree;canonical_projection_matches_value"},"object_reference":{"fields":["handle"],"scope":"one_live_trusted_host_broker_physical_identity"},"obligation_objects":"array_of_actual_host_references_matching_canonical_obligation_slots;whole_tuple_sidecar_preserves_add_input_and_admission_collection_identity;run_allocates_a_new_tuple_reusing_elements;sidecars_do_not_grant_acceptance","operations":{"add-input":{"fields":["identity","stage","requirements","obligations","obligation_objects","payload","obligations_object"],"result":"record"},"admit-component-input":{"fields":["contract_id","identity","payload"],"result":"record"},"artifact":{"fields":["name"],"result":"canonical_immutable_build_artifact"},"build-result":{"fields":["kind"],"result":"fixed_build"},"call-native-provider":{"fields":["provider_id","context_id"],"result":"native_provider_result"},"component-profile":{"fields":["preparation_id"],"result":"completion_profile"},"component-registration":{"fields":["preparation_id"],"result":"component_registration"},"finish-components":{"fields":["preparation_id","record_id","result_sequence"],"result":"fixed_build"},"finish-reference-construct":{"fields":["record_id","result_sequence"],"result":"reference_build"},"finish-reference-molecular":{"fields":["preparation_id","record_id","result_sequence","upstream"],"result":"reference_build"},"get":{"fields":["identity"],"result":"record"},"initialize-components":{"fields":["request","request_tree","history","until","config","manager_limits","target_object","request_object","config_object"],"result":"initialization"},"initialize-empty":{"fields":["target","dependencies","completion_profiles","manager_limits","target_object"],"result":"initialization"},"initialize-reference":{"fields":["request","request_tree","registry","registry_tree","manifests","manifests_tree","manager_limits","target_object","request_object","registry_object","construct_manifests_object","molecular_manifests_object","policy_objects"],"result":"initialization"},"initialize-synthetic":{"fields":["request","request_tree","history","until","config","manager_limits","target_object","request_object","config_object"],"result":"initialization"},"inspect":{"fields":[],"result":"historical_observation_only"},"inspect-ordered":{"fields":[],"result":"ordered_historical_observation_only"},"inspect-ordered-references":{"fields":[],"result":"referenced_historical_observation_only"},"prepare-components":{"fields":[],"result":"component_preparation"},"prepare-reference-molecular":{"fields":[],"result":"component_preparation"},"prepare-reference-molecular-public":{"fields":["request","request_tree","registry","registry_tree","manifests","manifests_tree","request_object","registry_object","molecular_manifests_object","policy_objects"],"result":"component_preparation"},"reference-admission":{"fields":[],"result":"reference_admission"},"reference-build-result":{"fields":["kind"],"result":"reference_build"},"reference-molecular-profile":{"fields":["preparation_id"],"result":"completion_profile"},"reference-molecular-registration":{"fields":["preparation_id"],"result":"component_registration"},"reference-registration":{"fields":[],"result":"component_registration"},"register":{"fields":["contract","producer","validators","obligation_objects"],"result":"null"},"register-completion-profile":{"fields":["profile"],"result":"null"},"register-component-input":{"fields":["contract","validators","obligation_objects","obligations_object","requirements_object"],"result":"null"},"result":{"fields":["identity","scope"],"result":"pipeline_result"},"run":{"fields":["pass_id","input_id","output_id","configuration"],"result":"record"},"set-dependency":{"fields":["key","identity"],"result":"null"},"target":{"fields":[],"result":"target"}},"ordered_merge":"native_before_and_after_mapping_order_carried_as_complete_duplicate_free_ordered_trees;exact_canonical_projection_required_before_original_host_mapping_unpack;complete_expansion_precharged_to_channel_lifetime;no_host_semantics_or_acceptance_import","ordered_tree":{"array":["array","ordered_trees"],"object":["object","ordered_unique_key_tree_pairs"],"scalar":["scalar","json_scalar"]},"origin_reference":{"authority":"exact_retained_regular_authoring_objects_and_closed_stored_fields;no_dynamic_attribute_or_property_lookup;representation_only","constant_paths":"empty_only","observable_suffix":"optional_dtype_followed_by_zero_or_more_arguments_nonnegative_integer_pairs","request_paths":[["domain","inputs","nonnegative_integer","observable"],["contract","requirements","nonnegative_integer","observable"],["behavior","nodes","nonnegative_integer","source"]],"roots":["request","BOOLEAN","DURATION","LEVEL","defaultLifecycle","syntheticCapabilities"],"synthetic_capabilities":"empty_path_only;exact_unique_tuple_code_constant_of_audited_original_generate_synthetic;closed_structural_reference_only;never_execute_generator"},"profile":"biocompiler.core.pipeline_callback_manager.v1","provider_reference":{"host":["kind","object"],"native":["kind","provider_id"]},"record_bindings":["record_id","payload","dependencies","requirements","obligations","obligation_objects","checks","provenance"],"record_identity":"one_token_per_actual_native_record_physical_identity_including_rejected_and_stored_before_error_records;not_content_hash_or_import","reference_workflow":{"build":"fresh_closed_candidate_and_check_result_views;exact_historical_public_manager_result;Molecular_construct_is_actual_second_upstream_candidate_read_or_native_default;host_return_root_conveys_no_acceptance","construct_order":["initialize-reference","reference-admission","actual_register-component-input","actual_admit-component-input","actual_get","reference-registration","actual_register","actual_run","actual_result","finish-reference-construct"],"final_source":"after_native_molecular_parse_read_actual_upstream_candidate_for_fresh_independent_check;after_check_read_again_and_retain_actual_opaque_return_root;no_unused_Build_fields_or_identity_requirement","finish":"actual_run_record_and_result_sequence;historical_result_retained;independent_native_final_checks;no_serialized_acceptance_import","host_result":"reference_producers_only;kind_host_with_actual_paired_PassResult_object_reference;no_conversion_or_acceptance","initialization":"ordered_request_registry_and_manifest_documents_with_exact_canonical_projection;actual_authored_target;one_manager_created_publication","limits":"one_shared_channel_lifetime_work_and_cumulative_retention_for_every_phase_callback_origin_and_build;native_semantic_resource_failures_remain_fatal","molecular_authority":"explicit_public_request_registry_and_outer_manifest_snapshot;retained_construct_manager_provenance_is_separate;all_native_limits_and_budget_use_actual_upstream_owner","molecular_order":["prepare-reference-molecular","six_ordered_actual_set-dependency_calls","reference-molecular-profile","actual_register-completion-profile","reference-molecular-registration","actual_register","actual_run","actual_result","finish-reference-molecular"],"owner":"one_actual_native_manager;source_ordered_public_calls;no_hidden_get_or_result","phase_authority":"actual_successful_manager_operation_objects_and_command_sequence;unrelated_generic_calls_do_not_advance;explicit_wrong_phase_or_foreign_capability_is_fatal","provider_view":{"binding":"actual_per_invocation_parsed_host_object;native_output_physical_identity;no_equal_content_or_last_call_interning","construct_origins":["parsed"],"decision_origins":[],"fields":["role","tree","origins"],"molecular_origins":["parsed","request","translation_policy","encoding_policy","evidence_policy"]},"roles":["reference_components.authority","reference_components.linkage","components_to_construct.producer","components_to_construct.layout","construct_to_molecular.producer","construct_to_molecular.sequence","construct_to_molecular.composition"],"scope":"historical_exact_reference_utilities;not_new_product_backends;no_empirical_or_complete_payload_claim","shared_provider":"reference_components.linkage_is_one_actual_closure_for_component_linkage_and_layout_composition","source_argument":"input_is_actual_context_input;argument_and_tree_are_the_complete_fresh_native_parsed_value;host_origin_binds_both_without_python_semantic_parsing","source_callback":"each_original_callpoint_performs_dynamic_host_default_lookup_after_native_parse;verified_default_runs_native_producer;replacement_runs_once_and_remains_opaque_until_deferred_manager_materialization","source_links":"expected_first_sorted_four_field_tuples;duplicates_preserved;actual_host_attribute_order_equality_and_exceptions"},"results":{"component_preparation":["preparation_id","dependencies"],"component_registration":["contract","producer","validators","obligation_objects"],"fixed_build":["kind","identity","result","artifacts","sources","view"],"initialization":["kind","manager","artifacts","target"],"native_provider_result":["kind","value","view"],"ordered_historical_observation_only":["snapshot","order","providers"],"pipeline_result":["value","artifact"],"record":["value","bindings"],"reference_admission":["contract","validators","obligation_objects"],"reference_build":["build_id","kind","candidate","check_result","result","construct"],"reference_source_result":["kind","argument","output"],"reference_upstream_candidate":{"check":["object","value","tree"],"return":["object"]},"referenced_historical_observation_only":["snapshot","order","providers","record_definitions"],"target":["value","binding"]},"schema_version":"biocompiler.pipeline_callback_manager_declaration.v1","source_links_binding":"null_for_native_context_default_or_complete_host_or_native_collection_binding;tuple_identity_and_element_identity_preserved"}|declaration}
let str value=Json.String value
let obj fields=Json.Object fields
let get key raw=Json.field key (Json.object_fields raw)
let text key raw=Json.string(get key raw)
let fail message=Diagnostic.fail "pipeline_callback_manager_protocol" message
let require condition message=if not condition then fail message
let number raw=Z.to_int(Json.integer raw)
let defaults=obj(List.filter(fun(key,_)->not(List.mem key ["profile";"work";"retention"]))
  (Json.object_fields(M.limits_json M.default_limits)))
type sidecar={elements:Json.t list;whole:Json.t option;requirements:Json.t option}
type record_view={record:C.Stage_record.t;bindings:Json.t}
type context_view={context:C.Pass_context.t;context_id:string;
  context_requirements:Json.t;context_dependencies:Json.t;mutable hydrated:Json.t option;mutable host_links:M.host_value list option}
type fixed_provider={owner:M.t;role:S.provider_role;candidate:Json.t option;
  mutable view_bindings:(string*(Json.t*Json.t)) list}
type reference_provider={reference_owner:M.t;reference_role:string}
type provider_view={provider:M.provider;provider_id:string;host:Json.t option;
  mutable proxy:Json.t option;mutable fixed:fixed_provider option;
  mutable reference:reference_provider option}
type fixed_authority={request:Realization_request.t;frames:Execution_data.Input_frame.t list;
  until:Runtime_number.t option}
type component_phase=
  | Updating_dependencies of (string*string) list
  | Profile_available of P.profiled
  | Profile_registered of P.profiled
  | Registration_available of P.registration
  | Registration_installed of P.registration
  | Component_ran of P.registration*C.Stage_record.t
  | Component_result of P.registration*C.Stage_record.t*int*C.Pipeline_result.t
  | Component_finished
type component_workflow={preparation_id:string;owner:M.t;prepared:P.prepared;mutable phase:component_phase}
type completed_build=Synthetic_build of S.t | Component_build of P.t
type build_view={build:completed_build;build_id:string;mutable build_envelope:Json.t option}
type build_artifact=Build_candidate of Synthetic_authority.Candidate.t
  | Build_selection of Synthetic_selection.Result.t | Build_assembly of Component_assembly.t
  | Build_link of Composition_evidence.Result.t | Build_behavior of Realization_evidence.Check_result.t
  | Build_construct of RD.Candidate.t | Build_construct_check of Reference_construct_evidence.Result.t
  | Build_molecular of Reference_molecular.Artifact.t | Build_molecular_check of Reference_molecular_evidence.Result.t
type t={mutable channel:Ch.t option;mutable bridge:H.t option;mutable initialized:bool;
  mutable live:M.t option;mutable manager_limits:M.limits;mutable manager_json:Json.t;
  mutable target_binding:Json.t option;mutable artifacts:(string*Json.t) list;
  mutable requested_config:(Json.t*Json.t) option;
  mutable fixed_request:Json.t option;mutable origins:(string*Json.t) list;
  mutable authority:fixed_authority option;mutable upstream:S.t option;
  mutable reference_mode:bool;mutable reference_workflow:RW.t option;mutable reference_roots:Json.t option;
  mutable reference_molecular_roots:Json.t option;
  mutable reference_outputs:(Json.t*string*Json.t) list;
  mutable reference_builds:(string*Json.t) list;
  mutable reference_preparation:string option;
  mutable component_attempted:bool;mutable component_workflow:component_workflow option;mutable builds:(string*build_view) list;
  mutable build_artifacts:(build_artifact*Json.t) list;
  mutable selection_views:(Synthetic_selection.Result.t*Json.t) list;
  mutable candidate_types:(Synthetic_authority.Candidate.t*string*int list*Json.t*Json.t) list;
  mutable providers:provider_view list;mutable contexts:context_view list;
  mutable records:record_view list;mutable compact_records:C.Stage_record.t list;mutable bindings:(Json.t*Json.t) list;
  mutable frozen:(Json.t*Json.t) list;mutable executions:(int*(Json.t*Json.t)) list;
  mutable pass_sidecars:(C.Pass_contract.t*sidecar) list;
  mutable admission_sidecars:(C.Component_input_contract.t*sidecar) list;
  mutable input_sidecar:sidecar option;mutable next_identity:int}
let channel (state:t)=match state.channel with Some value->value | None->fail "Channel has not been installed."
let work (state:t)=Ch.budget(channel state)
let charge (state:t)=W.charge(work state) 1
let codec (state:t)=C.Codec.make_limits ~max_bytes:33_554_432 ~max_nodes:1_000_000 ~charge:(W.charge(work state)) ()
let manager_codec (state:t)=C.Codec.make_limits ~max_bytes:(number(get "max_document_bytes" state.manager_json))
  ~max_nodes:(number(get "max_document_nodes" state.manager_json)) ~charge:(W.charge(work state)) ()
let retain (state:t) raw=let size=C.Codec.measure ~limits:(codec state) raw in
  Ch.retain_bytes(channel state)(size.bytes+64)
let identity (state:t) prefix=charge state;require(state.next_identity<1_000_000) "Application identity limit exhausted.";
  let value=prefix^"/"^string_of_int state.next_identity in
  retain state(str value);state.next_identity<-state.next_identity+1;value
let find (state:t) predicate values=List.find_opt(fun value->charge state;predicate value) values
let map (state:t) f values=List.map(fun value->charge state;f value) values
let unique_names (state:t) values=List.sort_uniq(fun left right->
  W.charge(work state)(String.length left+String.length right+1);String.compare left right) values
let invoke (state:t) action arguments=Ch.invoke(channel state) ~action ~arguments
let rec ordered (state:t) raw=charge state;match raw with
  | Json.Object fields->Json.Array[str "object";Json.Array(map state(fun(key,value)->Json.Array[str key;ordered state value]) fields)]
  | Json.Array values->Json.Array[str "array";Json.Array(map state(ordered state) values)]
  | value->Json.Array[str "scalar";value]
let rec unordered (state:t) depth raw=
  charge state;require(depth<=128) "Ordered host value exceeds its depth bound.";
  match raw with
  | Json.Array[Json.String "scalar";value]->
      (match value with Json.Array _ | Json.Object _->fail "Ordered scalar contains a collection." | _->value)
  | Json.Array[Json.String "array";Json.Array values]->Json.Array(map state(unordered state(depth+1)) values)
  | Json.Array[Json.String "object";Json.Array values]->
      let fields=map state(function Json.Array[Json.String key;value]->key,unordered state(depth+1) value
        | _->fail "Invalid ordered mapping entry.") values in
      let names=map state fst fields in
      require(List.length names=List.length(unique_names state names)) "Duplicate ordered mapping key.";
      Json.Object fields
  | _->fail "Malformed ordered host value."
let bridge (state:t)=match state.bridge with Some value->value | None->
  let invoke ~action ~arguments=
    if action="json" then (
      let tree=invoke state "ordered-json" arguments in
      let size=C.Codec.measure ~limits:(codec state) tree in
      Ch.retain_bytes(channel state)(size.bytes+64);
      let raw=unordered state 0 tree in
      state.frozen<-(raw,get "object" arguments)::state.frozen;raw)
    else if action="merge" then (
      let before=get "before" arguments and after=get "after" arguments in
      (* Canonical frames sort object keys. Reserve the complete ordered-tree
         expansion before allocating it, then carry both exact projections. *)
      let expansion raw=let size=C.Codec.measure ~limits:(codec state) raw in
        size.bytes+64*size.nodes+128 in
      Ch.retain_bytes(channel state)(expansion before+expansion after);
      invoke state "ordered-merge" (obj["object",get "object" arguments;
        "before",before;"after",after;
        "before_tree",ordered state before;"after_tree",ordered state after]))
    else invoke state action arguments in
  let value=H.create ~budget:(work state) ~invoke () in state.bridge<-Some value;value
let host (state:t) raw=H.of_reference(bridge state) raw
let host_binding (state:t) raw=ignore(host state raw);obj["kind",str "host";"object",raw]
let reserve_ordered (state:t) raw=
  let size=C.Codec.measure ~limits:(codec state) raw in
  (* Each source node gains at most two tags, collection delimiters and one
     identity-table slot. The codec ceiling bounds the arithmetic below. Reserve
     the complete conservative expansion before constructing the ordered tree. *)
  Ch.retain_bytes(channel state)(size.bytes+64*size.nodes+512)
let fresh_ordered (state:t) raw=reserve_ordered state raw;ordered state raw
let fresh_native_binding (state:t) raw=
  reserve_ordered state raw;
  obj["kind",str "native";"identity",str(identity state "value");"tree",ordered state raw]
let native_binding (state:t) raw=
  match find state(fun(previous,_)->previous==raw) state.bindings with
  | Some(_,value)->value
  | None->
      let value=fresh_native_binding state raw in
      state.bindings<-(raw,value)::state.bindings;value
let binding (state:t) raw=match find state(fun(previous,_)->previous==raw) state.frozen with
  | Some(_,reference)->host_binding state reference | None->native_binding state raw
let deps raw=obj(List.map(fun(key,value)->key,str value) raw)
let strings values=Json.Array(List.map str values)
let live (state:t)=match state.live with Some value->value | None->fail "This channel has no live manager."
let record_view (state:t) record=match find state(fun value->value.record==record) state.records with
  | Some value->value | None->fail "Unobserved native record incarnation."
let record_envelope (state:t) record=let view=record_view state record in
  obj["value",C.Stage_record.to_json record;"bindings",view.bindings]
let native_sidecar (state:t) obligations={
  elements=map state(fun value->native_binding state(C.Scoped_obligation.to_json value)) obligations;
  whole=None;requirements=None}
let source_sidecar (state:t) record=
  let fields=(record_view state record).bindings in
  {elements=Json.array(get "obligation_objects" fields);whole=Some(get "obligations" fields);
   requirements=Some(get "requirements" fields)}
let pass_sidecar (state:t) contract=match find state(fun(previous,_)->previous==contract) state.pass_sidecars with
  | Some(_,value)->value | None->native_sidecar state(C.Pass_contract.introduces contract)
let admission_sidecar (state:t) contract=match find state(fun(previous,_)->previous==contract) state.admission_sidecars with
  | Some(_,value)->value | None->native_sidecar state(C.Component_input_contract.obligations contract)
let origin_sidecar (state:t)=function
  | M.Input_origin->state.input_sidecar
  | M.Admission_origin contract->Some(admission_sidecar state contract)
  | M.Pass_origin(source,contract)->
      let original=source_sidecar state source and introduced=pass_sidecar state contract in
      Some {elements=original.elements@introduced.elements;whole=None;requirements=original.requirements}
let execution_bindings (state:t) execution origin dependencies requirements=
  match find state(fun(id,_)->id=execution) state.executions with
  | Some(_,values)->values
  | None->
      let source=origin_sidecar state origin in
      let requirements=match source with Some{requirements=Some value;_}->value
        | _->native_binding state(strings requirements) in
      let dependencies=native_binding state(deps dependencies) in
      retain state(obj["dependencies",dependencies;"requirements",requirements]);
      state.executions<-(execution,(dependencies,requirements))::state.executions;
      dependencies,requirements
let observe (state:t) supplied event=
  require(supplied==work state) "Observer received a foreign lifetime budget.";
  match event with
  | M.Context_created(execution,origin,context)->
      let dependencies,requirements=execution_bindings state execution origin
        (C.Pass_context.dependencies context)(C.Pass_context.requirements context) in
      let context_id=identity state "context" in retain state(C.Pass_context.to_json context);
      state.contexts<-{context;context_id;context_requirements=requirements;
        context_dependencies=dependencies;hydrated=None;host_links=None}::state.contexts
  | M.Record_stored(execution,origin,record)->
      let dependencies,requirements=execution_bindings state execution origin
        (C.Stage_record.dependencies record)(C.Stage_record.requirements record) in
      let sidecar=match origin_sidecar state origin with Some value->value
        | None->native_sidecar state(C.Stage_record.obligations record) in
      require(List.length sidecar.elements=List.length(C.Stage_record.obligations record))
        "Obligation sidecar inventory disagrees with native record.";
      let obligations=match sidecar.whole with Some value->value
        | None->native_binding state(Json.Array(map state C.Scoped_obligation.to_json(C.Stage_record.obligations record))) in
      let bindings=obj["record_id",str(identity state "record");
        "payload",binding state(C.Stage_record.payload record);"dependencies",dependencies;
        "requirements",requirements;"obligations",obligations;
        "obligation_objects",Json.Array sidecar.elements;
        "checks",binding state(C.Stage_record.checks record);"provenance",binding state(C.Stage_record.provenance record)] in
      retain state bindings;state.records<-{record;bindings}::state.records
let target_envelope (state:t)=obj["value",Build_request.Target.to_json(M.target(live state));
  "binding",Option.get state.target_binding]
let hydrate (state:t) context=
  let entry=match find state(fun value->value.context==context) state.contexts with
    | Some value->value | None->fail "Callback supplied an unobserved context." in
  match entry.hydrated with Some value->value | None->
  let host_links=M.callback_source_links(live state) in
  entry.host_links<-host_links;
  let source_links=match host_links with
    | None->Json.Null
    | Some values->
        (match H.tuple_origin(bridge state) values with
         | Some value->host_binding state(H.reference(bridge state) value)
         | None->fail "Host source links have no original tuple identity.") in
  let bindings=obj["input",binding state(C.Pass_context.input context);
    "output",Option.fold ~none:Json.Null ~some:(binding state)(C.Pass_context.output context);
    "target",Option.get state.target_binding;"configuration",binding state(C.Pass_context.configuration context);
    "dependencies",entry.context_dependencies;"requirements",entry.context_requirements;
    "source_links",source_links;"observation_map",
      (match C.Pass_context.output context with
       | None->fresh_native_binding state(C.Pass_context.observation_map context)
       | Some _->binding state(C.Pass_context.observation_map context))] in
  let value=invoke state "hydrate-context" (obj["context_id",str entry.context_id;
    "document",C.Pass_context.to_json context;"bindings",bindings]) in
  ignore(host state value);retain state value;entry.hydrated<-Some value;value
let provider_entry (state:t) provider=match find state(fun value->value.provider==provider) state.providers with
  | Some value->value | None->
      Ch.retain_bytes(channel state)128;
      let value={provider;provider_id=identity state "provider";host=None;proxy=None;fixed=None;reference=None} in
      state.providers<-value::state.providers;value
let role_name=function
  | S.Intent_to_behavior_producer->"intent_to_behavior.producer"
  | S.Intent_to_behavior_validator->"intent_to_behavior.validator"
  | S.Behavior_to_synthetic_producer _->"behavior_to_synthetic.producer"
  | S.Behavior_to_synthetic_validator->"behavior_to_synthetic.validator"
  | S.Synthetic_to_components_producer _->"synthetic_to_components.producer"
  | S.Synthetic_to_components_validator->"synthetic_to_components.validator"
let observe_provider (state:t) supplied owner provider role=
  require(supplied==work state) "Fixed provider metadata received a foreign lifetime budget.";
  Ch.retain_bytes(channel state)128;
  let entry=provider_entry state provider in
  require(entry.host=None && entry.fixed=None && entry.reference=None && entry.proxy=None) "Fixed provider metadata was rebound.";
  let candidate=match role with S.Synthetic_to_components_producer value->
    let size=Synthetic_authority.Candidate.canonical_size value.candidate in
    W.charge(work state)(128*(size+1));Ch.retain_bytes(channel state)(8*size+256);
    Some(Synthetic_authority.Candidate.to_json value.candidate)
    | _->None in
  entry.fixed<-Some {owner;role;candidate;view_bindings=[]}
let observe_reference_provider (state:t) supplied owner provider role=
  require(supplied==work state && owner==live state)
    "Reference provider metadata received another manager or lifetime budget.";
  Ch.retain_bytes(channel state)128;
  let entry=provider_entry state provider in
  require(entry.host=None && entry.fixed=None && entry.reference=None && entry.proxy=None)
    "Reference provider metadata was rebound.";
  entry.reference<-Some {reference_owner=owner;reference_role=role}
let observe_construct_provider state supplied owner provider role=
  observe_reference_provider state supplied owner provider(match role with
    | RC.Authority_validator->"reference_components.authority"
    | RC.Linkage_validator->"reference_components.linkage"
    | RC.Construct_producer->"components_to_construct.producer"
    | RC.Layout_validator->"components_to_construct.layout")
let observe_molecular_provider state supplied owner provider role=
  observe_reference_provider state supplied owner provider(match role with
    | RM.Emit->"construct_to_molecular.producer"
    | RM.Sequence_identity->"construct_to_molecular.sequence"
    | RM.Encoding_composition->"construct_to_molecular.composition")
let fixed_provider (entry:provider_view)=match entry.fixed with
  | Some value->value | None->fail "Native provider lacks a fixed closure role."
let equivalent_json (state:t) left right=
  C.Codec.encode ~limits:(codec state) left=C.Codec.encode ~limits:(codec state) right
let fixed_binding (state:t) (fixed:fixed_provider) key raw=
  match find state(fun(previous,_)->
    W.charge(work state)(String.length previous+String.length key+1);previous=key) fixed.view_bindings with
  | Some(_, (prior,value))->
      require(equivalent_json state prior raw) "A retained provider origin was rebound to different fields.";value
  | None->
      Ch.retain_bytes(channel state)(String.length key+128);
      let value=fresh_native_binding state raw in
      fixed.view_bindings<-(key,(raw,value))::fixed.view_bindings;value
let origin_binding (state:t) root path=
  Ch.retain_bytes(channel state)256;
  let arguments=obj["root",str root;"path",Json.Array path] in
  let size=C.Codec.measure ~limits:(codec state) arguments in
  Ch.retain_bytes(channel state)(size.bytes+128);
  let key=C.Codec.encode ~limits:(codec state) arguments in
  match find state(fun(previous,_)->
    W.charge(work state)(String.length previous+String.length key+1);previous=key) state.origins with
  | Some(_,value)->value
  | None->
      let reference=invoke state "origin-reference" arguments in
      let value=host_binding state reference in
      retain state reference;state.origins<-(key,value)::state.origins;value
let candidate_type_binding (state:t) candidate node_id indices raw=
  let nodes=Json.array(get "nodes"(get "mechanism"(Synthetic_authority.Candidate.to_json candidate))) in
  let node=match find state(fun node->let actual=text "id" node in
    W.charge(work state)(String.length actual+String.length node_id+1);actual=node_id)nodes with
    | Some value->value | None->fail "A parsed type origin names no upstream candidate node." in
  let rec descend value=function
    | []->value
    | index::rest->charge state;require(index>=0) "A parsed type origin has a negative argument index.";
        let rec nth remaining=function
          | []->fail "A parsed type origin names no upstream type argument."
          | value::tail->charge state;if remaining=0 then value else nth(remaining-1)tail in
        descend(nth index(Json.array(get "arguments" value)))rest in
  let expected=descend(get "dtype"(get "output" node))indices in
  require(equivalent_json state expected raw) "A parsed type origin differs from its actual upstream fields.";
  match find state(fun(previous,name,path,_,_)->
    W.charge(work state)(String.length name+String.length node_id+List.length path+List.length indices+1);
    previous==candidate && name=node_id && path=indices)state.candidate_types with
  | Some(_,_,_,prior,binding)->
      require(equivalent_json state prior raw) "A retained parsed type origin was rebound.";binding
  | None->
      Ch.retain_bytes(channel state)(String.length node_id+32*List.length indices+192);
      let binding=fresh_native_binding state raw in
      state.candidate_types<-(candidate,node_id,indices,raw,binding)::state.candidate_types;binding
let candidate_type_aliases (state:t) candidate=
  List.mapi(fun index node->charge state;Ch.retain_bytes(channel state)512;
    let raw=get "dtype"(get "output" node) in
    let binding=candidate_type_binding state candidate(text "id" node)[] raw in
    obj["kind",str "biocompiler.semantics.types.TypeSpec";
      "paths",Json.Array[Json.Array[str "candidate";str "mechanism";str "nodes";Json.int index;str "output";str "dtype"]];
      "binding",binding])
    (Json.array(get "nodes"(get "mechanism"(Synthetic_authority.Candidate.to_json candidate))))
let provider_view (state:t) (entry:provider_view) kind value=
  let fixed=fixed_provider entry in
  require(fixed.owner==live state) "Fixed provider belongs to another manager incarnation.";
  let producer=match fixed.role with
    | S.Intent_to_behavior_producer | S.Behavior_to_synthetic_producer _ | S.Synthetic_to_components_producer _->true
    | S.Intent_to_behavior_validator | S.Behavior_to_synthetic_validator | S.Synthetic_to_components_validator->false in
  require((kind="proposal")=producer) "Fixed provider returned a result inconsistent with its observed role.";
  (* Source volume is measured before constructing paths, tables or ordered
     trees. Each metadata allocation is additionally prepaid by its builder;
     there is no new allowance or refund outside the lifetime channel budget. *)
  ignore(C.Codec.measure ~limits:(codec state) value);
  let bindings=if not producer then obj[] else
    let output=get "output" value in
    match fixed.role with
    | S.Behavior_to_synthetic_producer config->
        let raw=get "generator_config" output in
        let actual=match config.config_origin with
          | S.Requested->
              let expected,binding=match state.requested_config with Some value->value
                | None->fail "Fixed config lacks its authored origin." in
              require(equivalent_json state expected raw) "Fixed config differs from its authored origin.";binding
          | S.Selected->fixed_binding state fixed "selected-config" raw in
        obj["generator_config",actual;"required_capabilities",origin_binding state "syntheticCapabilities" []]
    | S.Synthetic_to_components_producer _->
        obj["registry",fixed_binding state fixed "registry"(get "registry" output);
          "composition",fixed_binding state fixed "composition"(get "composition" output);
          "composition_target",Option.get state.target_binding]
    | S.Intent_to_behavior_producer->obj[]
    | S.Intent_to_behavior_validator | S.Behavior_to_synthetic_validator | S.Synthetic_to_components_validator->
        fail "Validator entered a producer view." in
  let aliases=if not producer then [] else
    let request=match state.fixed_request with Some value->value | None->fail "Fixed provider has no retained request." in
    let sites=V.aliases ~charge:(W.charge(work state)) ~reserve:(Ch.retain_bytes(channel state))
      ~request ~candidate:fixed.candidate ~role:fixed.role value in
    let fresh=ref [] and grouped=ref [] in
    List.iter(fun (site:V.site)->charge state;
      let actual=match site.origin with
        | V.Host(root,path)->origin_binding state root path
        | V.Upstream_type(node,indices)->
            (match fixed.role with
             | S.Synthetic_to_components_producer origin->candidate_type_binding state origin.candidate node indices site.value
             | _->fail "A parsed upstream type origin escaped its component provider.")
        | V.Retained key->
            W.charge(work state)(String.length key+8);Ch.retain_bytes(channel state)(String.length key+32);
            fixed_binding state fixed ("alias/"^key) site.value
        | V.Fresh key->
            (match find state(fun(previous,_)->
              W.charge(work state)(String.length previous+String.length key+1);previous=key) !fresh with
             | Some(_, (prior,binding))->
                 require(equivalent_json state prior site.value) "A fresh constructor origin has inconsistent fields.";binding
             | None->
                 Ch.retain_bytes(channel state)(String.length key+128);
                 let binding=fresh_native_binding state site.value in
                 fresh:=(key,(site.value,binding))::!fresh;binding) in
      Ch.retain_bytes(channel state)256;
      let key=match text "kind" actual with
        | "native"->"native/"^text "identity" actual
        | "host"->"host/"^text "handle"(get "object" actual)
        | _->fail "Malformed typed origin binding." in
      match find state(fun(previous,_,_,_,_)->
        W.charge(work state)(String.length previous+String.length key+1);previous=key) !grouped with
      | Some(_,kind,prior,_,paths)->
          require(kind=site.kind && equivalent_json state prior site.value) "One typed object acquired inconsistent class or fields.";
          Ch.retain_bytes(channel state)32;paths:=site.path::!paths
      | None->
          Ch.retain_bytes(channel state)(String.length key+192);
          grouped:=(key,site.kind,site.value,actual,ref[site.path])::!grouped)sites;
    map state(fun(_,kind,_,binding,paths)->obj["kind",str kind;
      "paths",Json.Array(map state(fun path->Json.Array path)(List.rev !paths));"binding",binding])
      (List.rev !grouped) in
  obj["role",str(role_name fixed.role);"tree",fresh_ordered state value;
    "bindings",bindings;"aliases",Json.Array aliases]
let provider_reference (state:t) entry=match entry.host,entry.proxy with
  | Some value,_ | None,Some value->value
  | None,None->let role=match entry.reference with
      | Some value->value.reference_role | None->role_name(fixed_provider entry).role in
      let value=invoke state "native-provider" (obj["provider_id",str entry.provider_id;"role",str role]) in
      ignore(host state value);retain state value;entry.proxy<-Some value;value
let publish_fixed_manager (state:t) supplied manager=
  require(supplied==work state) "Fixed manager publication received a foreign lifetime budget.";
  require(state.live=None) "Fixed initialization published a second live manager.";
  state.live<-Some manager;
  Ch.retain_bytes(channel state)256;
  let result=invoke state "manager-created"(obj["target",target_envelope state]) in
  require(result=Json.Null) "Manager publication returned replacement authority."
let register_fixed (state:t) supplied manager contract ~producer ~validators=
  require(supplied==work state && manager==live state)
    "Fixed registration received another live manager or lifetime budget.";
  Ch.retain_bytes(channel state)512;
  let contract_json=C.Pass_contract.to_json contract in
  retain state contract_json;
  let producer=provider_reference state(provider_entry state producer) in
  let validators=map state(fun(key,provider)->Ch.retain_bytes(channel state)(String.length key+96);
    Json.Array[str key;provider_reference state(provider_entry state provider)])validators in
  let obligations=(native_sidecar state(C.Pass_contract.introduces contract)).elements in
  let arguments=obj["contract",contract_json;"producer",producer;"validators",Json.Array validators;
    "obligation_objects",Json.Array obligations] in
  retain state arguments;
  let result=invoke state "register-fixed" arguments in
  require(result=Json.Null) "Fixed registration returned replacement authority."
let remember_build (state:t) kind build=
  require(not(List.mem_assoc kind state.builds)) "A completed build snapshot cannot be replaced.";
  Ch.retain_bytes(channel state)256;
  let view={build;build_id=identity state "build";build_envelope=None} in
  state.builds<-state.builds@[kind,view]
let save_synthetic_build (state:t) value=
  match state.upstream with
  | Some previous->require(previous==value) "Component continuation changed its actual upstream build."
  | None->state.upstream<-Some value;remember_build state "synthetic"(Synthetic_build value)
let save_component_build (state:t) value=
  save_synthetic_build state(P.upstream value);
  remember_build state "components"(Component_build value)
let same_build_artifact left right=match left,right with
  | Build_candidate left,Build_candidate right->left==right
  | Build_selection left,Build_selection right->left==right
  | Build_assembly left,Build_assembly right->left==right
  | Build_link left,Build_link right->left==right
  | Build_behavior left,Build_behavior right->left==right
  | Build_construct left,Build_construct right->left==right
  | Build_construct_check left,Build_construct_check right->left==right
  | Build_molecular left,Build_molecular right->left==right
  | Build_molecular_check left,Build_molecular_check right->left==right
  | _->false
let build_artifact (state:t) origin raw=
  let binding=match find state(fun(previous,_)->same_build_artifact previous origin)state.build_artifacts with
    | Some(_,value)->value
    | None->Ch.retain_bytes(channel state)128;
        let value=fresh_native_binding state raw in
        state.build_artifacts<-(origin,value)::state.build_artifacts;value in
  Ch.retain_bytes(channel state)128;
  obj["value",raw;"binding",binding]
let selection_view (state:t) selection=
  match selection with
  | None->obj["selection_config",Json.Null;"alternative_configs",Json.Array[];
      "required_capabilities",Json.Null;"aliases",Json.Array[]]
  | Some selection->
    (match find state(fun(previous,_)->previous==selection)state.selection_views with
     | Some(_,value)->value
     | None->
       Ch.retain_bytes(channel state)512;
       let requested_config=Synthetic_selection.Result.config selection in
       let requested_raw=Synthetic_authority.Config.to_json requested_config in
       let original,selection_config=match state.requested_config with Some value->value
         | None->fail "Selection lacks its actual requested configuration." in
       require(equivalent_json state original requested_raw) "Selection changed its original requested configuration.";
       let grouped=ref [] and any_candidate=ref false in
       let aliases index candidate actual_config=
         Ch.retain_bytes(channel state)256;
         let raw=Synthetic_authority.Candidate.to_json candidate in
         let role=S.Behavior_to_synthetic_producer {requested_config;selected_config=actual_config;config_origin=S.Selected} in
         (* Both source implementations use the same generator constructor for
            each alternative. This is its explicit origin recipe, not a new
            provider capability or a proposal submitted for acceptance. *)
         let sites=V.aliases ~charge:(W.charge(work state)) ~reserve:(Ch.retain_bytes(channel state))
           ~request:(Option.get state.fixed_request) ~candidate:None ~role(obj["output",raw]) in
         List.iter(fun(site:V.site)->charge state;
           let binding=match site.origin with V.Host(root,path)->origin_binding state root path
             | V.Fresh _ | V.Retained _ | V.Upstream_type _->fail "Selection generator acquired an undeclared shared construction origin." in
           let suffix=match site.path with Json.String "output"::rest->rest
             | _->fail "Selection generator origin escaped its candidate." in
           Ch.retain_bytes(channel state)(256+32*List.length suffix);
           let path=str "selection_result"::str "alternatives"::Json.int index::str "candidate"::suffix in
           let key=text "handle"(get "object" binding) in
           match find state(fun(previous,_,_,_,_)->
             W.charge(work state)(String.length previous+String.length key+1);previous=key) !grouped with
           | Some(_,kind,prior,_,paths)->
               require(kind=site.kind && equivalent_json state prior site.value) "Selection source identity changed typed fields.";
               paths:=path::!paths
           | None->Ch.retain_bytes(channel state)(String.length key+192);
               grouped:=(key,site.kind,site.value,binding,ref[path])::!grouped)sites in
       let alternatives=Synthetic_selection.Result.alternatives selection in
       let configs=List.mapi(fun index alternative->charge state;Ch.retain_bytes(channel state)64;
         match Synthetic_selection.Alternative.candidate alternative with
         | None->Json.Null
         | Some candidate->
           any_candidate:=true;
           let actual=Synthetic_authority.Candidate.generator_config candidate in
           let raw=Synthetic_authority.Config.to_json actual in
           let selected=find state(fun entry->match entry.fixed with
             | Some {role=S.Behavior_to_synthetic_producer config;owner;_}->
                 owner==live state && config.config_origin=S.Selected && config.selected_config==actual
             | _->false)state.providers in
           let binding=match selected with
             | Some entry->fixed_binding state(fixed_provider entry)"selected-config" raw
             | None->fresh_native_binding state raw in
           aliases index candidate actual;binding)alternatives in
       let aliases=map state(fun(_,kind,_,binding,paths)->obj["kind",str kind;
         "paths",Json.Array(map state(fun path->Json.Array path)(List.rev !paths));"binding",binding])
         (List.rev !grouped) in
       let value=obj["selection_config",selection_config;"alternative_configs",Json.Array configs;
         "required_capabilities",(if !any_candidate then origin_binding state "syntheticCapabilities" [] else Json.Null);
         "aliases",Json.Array aliases] in
       retain state value;state.selection_views<-(selection,value)::state.selection_views;value)
let build_result (state:t) kind=
  require(List.mem kind["synthetic";"components"]) "Unknown completed build kind.";
  let entry=match List.assoc_opt kind state.builds with Some value->value
    | None->fail "No such completed historical build." in
  match entry.build_envelope with Some value->value | None->
  Ch.retain_bytes(channel state)1024;
  let upstream,record,result,extra=match entry.build with
    | Synthetic_build value->value,S.record value,S.result value,[]
    | Component_build value->P.upstream value,P.record value,P.result value,
        ["assembly",build_artifact state(Build_assembly(P.assembly value))(Component_assembly.to_json(P.assembly value));
         "link_result",build_artifact state(Build_link(P.link_result value))(Composition_evidence.Result.to_json(P.link_result value));
         "behavior_result",build_artifact state(Build_behavior(P.behavior_result value))(Realization_evidence.Check_result.to_json(P.behavior_result value))] in
  let candidate=S.candidate upstream and selection=S.selection_result upstream in
  let candidate_aliases=candidate_type_aliases state candidate in
  let candidate=build_artifact state(Build_candidate candidate)(Synthetic_authority.Candidate.to_json candidate) in
  let selected_view=selection_view state selection in
  let selected_aliases=Json.array(get "aliases" selected_view) in
  W.charge(work state)(List.length candidate_aliases+1);
  Ch.retain_bytes(channel state)(32*List.length candidate_aliases+256);
  let view=obj(List.map(fun(key,value)->if key="aliases" then key,Json.Array(candidate_aliases@selected_aliases)
    else key,value)(Json.object_fields selected_view)) in
  let selected=match selection with None->obj["value",Json.Null;"binding",Json.Null]
    | Some value->build_artifact state(Build_selection value)(Synthetic_selection.Result.to_json value) in
  let value=obj["kind",str kind;"identity",str entry.build_id;
    "result",obj["value",C.Pipeline_result.to_json result;"artifact",record_envelope state record];
    "artifacts",obj(["candidate",candidate;"selection_result",selected]@extra);
    "sources",obj["candidate",record_envelope state(S.record upstream)];
    "view",view] in
  retain state value;entry.build_envelope<-Some value;value
let workflow (state:t) identity=
  match state.component_workflow with
  | Some value when value.preparation_id=identity && value.owner==live state->value
  | _->fail "Unknown component preparation capability."
let prepare_components (state:t)=
  require(not state.component_attempted && not(List.mem_assoc "components" state.builds))
    "Component continuation has already been attempted.";
  state.component_attempted<-true;
  let upstream=match state.upstream with Some value->value | None->fail "No completed synthetic build is available." in
  let authority=match state.authority with Some value->value | None->fail "No retained fixed authoring authority." in
  (* The adapter's existing cumulative publication bound covers its captured
     registry/composition. Reserve it before starting the actual adaptation. *)
  Ch.retain_bytes(channel state)(number(get "max_report_bytes"(get "shared"
    (Bioc_synthetic_producer.Components.limits_json Bioc_synthetic_producer.Components.default_limits))));
  Ch.retain_bytes(channel state)512;
  let prepared=P.prepare ~budget:(work state) ~manager_limits:state.manager_limits ?until:authority.until
    authority.request authority.frames upstream in
  let dependencies=P.dependencies prepared in
  List.iter(fun(key,value)->charge state;
    Ch.retain_bytes(channel state)(6*(String.length key+String.length value)+128))dependencies;
  let encoded=Json.Array(map state(fun(key,value)->Json.Array[str key;str value])dependencies) in
  retain state encoded;
  let preparation_id=identity state "component-preparation" in
  state.component_workflow<-Some {preparation_id;owner=live state;prepared;phase=Updating_dependencies dependencies};
  obj["preparation_id",str preparation_id;"dependencies",encoded]
let component_profile (state:t) preparation_id=
  let workflow=workflow state preparation_id in
  (match workflow.phase with Updating_dependencies []->() | _->fail "Component dependencies are not complete.");
  let value=P.prepare_profile ~budget:(work state) workflow.prepared in
  let raw=C.Completion_profile.to_json(P.completion_profile value) in
  retain state raw;workflow.phase<-Profile_available value;raw
let component_registration (state:t) preparation_id=
  let workflow=workflow state preparation_id in
  let profile=match workflow.phase with Profile_registered value->value
    | _->fail "Component completion profile has not been registered." in
  let value=P.prepare_registration ~budget:(work state) ~provider_observer:(observe_provider state) profile in
  let contract=P.contract value in
  let contract_json=C.Pass_contract.to_json contract in
  retain state contract_json;
  let producer=provider_reference state(provider_entry state(P.producer value)) in
  let validators=map state(fun(key,provider)->Json.Array[str key;provider_reference state(provider_entry state provider)])
    (P.validators value) in
  let obligations=(native_sidecar state(C.Pass_contract.introduces contract)).elements in
  let raw=obj["contract",contract_json;"producer",producer;"validators",Json.Array validators;
    "obligation_objects",Json.Array obligations] in
  retain state raw;workflow.phase<-Registration_available value;raw
let intern_provider (state:t) raw=
  ignore(host state raw);
  let descriptor=invoke state "provider-reference" (obj["object",raw]) in
  match text "kind" descriptor with
  | "native"->
      Json.exact_fields ["kind";"provider_id"] (Json.object_fields descriptor);
      let token=text "provider_id" descriptor in
      (match find state(fun value->value.provider_id=token && value.host=None) state.providers with
       | Some value->value.provider | None->fail "Unknown native provider capability.")
  | "host"->
      Json.exact_fields ["kind";"object"] (Json.object_fields descriptor);
      let raw=get "object" descriptor in let object_value=host state raw in
      (match find state(fun value->match value.host with None->false
        | Some reference->host state reference==object_value) state.providers with
       | Some value->value.provider
       | None->
           let provider_id=identity state "provider" in
           let callback supplied context=
             require(supplied==work state) "Provider received a foreign lifetime budget.";
             let context=hydrate state context in
             host state(invoke state "call-provider" (obj["provider_id",str provider_id;"context",context])) in
           let provider=M.bind_host_provider(live state) callback in
           retain state raw;
            let entry={provider;provider_id;host=Some raw;proxy=None;fixed=None;reference=None} in
           state.providers<-entry::state.providers;
           let result=invoke state "bind-provider" (obj["provider_id",str provider_id;"object",raw]) in
           require(result=Json.Null) "Provider binding returned a value.";provider)
  | _->fail "Malformed provider capability descriptor."
let equivalent (state:t) supplied left right=
  require(supplied==work state) "Provider comparison received a foreign lifetime budget.";
  let left=provider_reference state(provider_entry state left) in
  let right=provider_reference state(provider_entry state right) in
  Json.boolean(invoke state "compare"(obj["left",left;"right",right;"operator",str "eq"]))
let callable (state:t) value=Json.boolean(invoke state "callable"(obj["object",value]))
let each_host (state:t) object_ref action=
  let cursor=(host state object_ref).M.iter(work state) in
  let rec loop count=charge state;require(count<100_000) "Host mapping inventory limit exhausted.";
    match cursor.next(work state) with None->true | Some value->if action value then loop(count+1) else false in
  loop 0
let deferred_validators (state:t) ?producer validators=
  let value=host state validators in
  {M.validate=(fun supplied->
    require(supplied==work state) "Validator materialization received a foreign budget.";
    (match producer with None->true | Some value->callable state value) &&
    value.is_instance supplied M.Mapping &&
    let values=invoke state "mapping-values"(obj["object",validators]) in
    each_host state values(fun value->callable state(H.reference(bridge state)value)));
   keys_match=(fun _ names->Json.boolean(invoke state "set-equal"(obj["object",validators;"values",strings names])));
   snapshot=(fun supplied->
    require(supplied==work state) "Validator snapshot received a foreign budget.";
    let dictionary=invoke state "dict"(obj["object",validators]) in ignore(host state dictionary);
    let items=invoke state "mapping-items"(obj["object",dictionary]) in
    let result=ref [] in
    ignore(each_host state items(fun item->
      let key=item.M.get_item supplied(M.Json_value(Json.int 0)) in
      let value=item.M.get_item supplied(M.Json_value(Json.int 1)) in
      let key=Json.string(key.freeze supplied) in
      let provider=intern_provider state(H.reference(bridge state)value) in
      result:=(key,provider)::!result;true));List.rev !result)}
let self_certifying (state:t) producer validators _=
  let values=invoke state "mapping-values"(obj["object",validators]) in
  not(each_host state values(fun value->not(Json.boolean(invoke state "compare"
    (obj["left",H.reference(bridge state)value;"right",producer;"operator",str "is"])))))
let imported (state:t) decoder raw=
  let charged=ref 0 in let budget=work state in
  let limits=C.Codec.make_limits ~max_bytes:(number(get "max_document_bytes" state.manager_json))
    ~max_nodes:(number(get "max_document_nodes" state.manager_json))
    ~charge:(fun amount->W.charge budget amount;charged:= !charged+amount) () in
  ignore(C.Codec.encode ~limits raw);
  if !charged>W.remaining budget/127 then W.charge budget(W.remaining budget+1);
  W.charge budget(!charged*127);decoder raw
let set_limits (state:t) raw=
  let raw=if raw=Json.Null then defaults else raw in
  let supplied=Json.object_fields raw and expected=Json.object_fields defaults in
  Json.exact_fields(List.map fst expected) supplied;
  List.iter(fun(key,maximum)->let value=Json.integer(Json.field key supplied) in
    require(Z.sign value>0 && Z.compare value(Json.integer maximum)<=0) "Invalid manager limit reduction.") expected;
  let n key=number(get key raw) in
  state.manager_json<-raw;state.manager_limits<-M.make_limits ~max_records:(n "max_records")
    ~max_providers:(n "max_providers") ~max_retained_items:(n "max_retained_items")
    ~max_retained_bytes:(n "max_retained_bytes") ~max_call_depth:(n "max_call_depth")
    ~max_ancestor_depth:(n "max_ancestor_depth") ~max_document_bytes:(n "max_document_bytes")
    ~max_document_nodes:(n "max_document_nodes") ()
let retain_fixed (state:t) components request config until=
  retain state(Realization_request.to_json request);
  let catalog_bytes=max(Synthetic_authority.Catalog.canonical_size Synthetic_authority.combinational_catalog)
    (Synthetic_authority.Catalog.canonical_size Synthetic_authority.temporal_catalog) in
  Ch.retain_bytes(channel state) catalog_bytes;
  retain state(Synthetic_authority.Config.to_json(Option.value config ~default:(Synthetic_authority.Config.make())));
  Option.iter(fun value->retain state(Runtime_number.to_json value)) until;
  let build=Realization_request.build_request request in
  if Build_request.implementation_constraints build<>[] || Build_request.preferences build<>[] then
    Ch.retain_bytes(channel state)(number(get "max_report_bytes"(get "shared"
      (Bioc_synthetic_producer.Selection.limits_json Bioc_synthetic_producer.Selection.default_limits))));
  if components then Ch.retain_bytes(channel state)(number(get "max_report_bytes"(get "shared"
    (Bioc_synthetic_producer.Components.limits_json Bioc_synthetic_producer.Components.default_limits))))
let initialize (state:t) kind payload=
  require(not state.initialized) "Initialization has already been attempted.";
  state.initialized<-true;retain state payload;set_limits state(get "manager_limits" payload);
  state.target_binding<-Some(host_binding state(get "target_object" payload));
  let budget=work state and observer=observe state and validator_equivalent=equivalent state in
  let provider_observer=observe_provider state in
  let manager_created=publish_fixed_manager state and register_fixed=register_fixed state in
  if kind="empty" then (
    let target=imported state(fun raw->Build_request.Target.of_json raw)(get "target" payload) in
    let dependencies=map state(function Json.Array[Json.String key;Json.String value]->key,value
      | _->fail "Dependencies must be ordered name/identity pairs.")(Json.array(get "dependencies" payload)) in
    let names=List.map fst dependencies in
    require(List.length names=List.length(unique_names state names)) "Duplicate dependency names.";
    let completion_profiles=map state(fun raw->C.Completion_profile.of_json ~limits:(manager_codec state) raw)
      (Json.array(get "completion_profiles" payload)) in
    state.live<-Some(M.create ~budget ~limits:state.manager_limits ~observer ~validator_equivalent
      ~target ~dependencies ~completion_profiles ()))
  else (
    let tree=get "request_tree" payload in
    let size=C.Codec.measure ~limits:(codec state) tree in
    (* Removing ordered-tree tags allocates at most the encoded input tree's
       volume; reserve this new document before reconstructing its maps. *)
    Ch.retain_bytes(channel state)(size.bytes+64);
    let request_raw=unordered state 0 tree in
    require(equivalent_json state request_raw(get "request" payload))
      "Ordered request differs from the canonical initialization authority.";
    let request=imported state(fun raw->Realization_request.of_json raw)request_raw in
    let frames=map state(fun raw->imported state(fun raw->Execution_data.Input_frame.of_json raw) raw)(Json.array(get "history" payload)) in
    let until=match get "until" payload with Json.Null->None | raw->Some(Runtime_number.of_json raw) in
    let raw_config=get "config" payload in
    require(raw_config<>Json.Null) "Fixed initialization requires its explicit authored configuration.";
    let config=Some(imported state(fun raw->Synthetic_authority.Config.of_json raw) raw_config) in
    let config_binding=host_binding state(get "config_object" payload) in
    state.requested_config<-Some(raw_config,config_binding);
    ignore(host state(get "request_object" payload));
    state.fixed_request<-Some request_raw;
    Ch.retain_bytes(channel state)256;
    state.authority<-Some {request;frames;until};
    map state(fun value->retain state(Execution_data.Input_frame.to_json value)) frames |> ignore;
    retain_fixed state(kind="components") request config until;
    let artifact name raw=retain state raw;state.artifacts<-state.artifacts@[name,raw] in
    let selection=function None->Json.Null | Some value->Synthetic_selection.Result.to_json value in
    if kind="synthetic" then match S.attempt ~budget ~manager_limits:state.manager_limits
      ~observer ~provider_observer ~manager_created ~register_fixed ~validator_equivalent ?until ?config request frames with
      | S.Failed failure->state.live<-failure.manager;raise failure.error
      | S.Completed value->state.live<-Some(S.manager value);
          save_synthetic_build state value;
          artifact "candidate"(Synthetic_authority.Candidate.to_json(S.candidate value));
          artifact "pipeline_result"(C.Pipeline_result.to_json(S.result value));
          artifact "selection_result"(selection(S.selection_result value))
    else match P.attempt ~budget ~manager_limits:state.manager_limits
      ~observer ~provider_observer ~manager_created ~register_fixed ~validator_equivalent ?until ?config request frames with
      | P.Failed failure->state.live<-failure.manager;raise failure.error
      | P.Completed value->state.live<-Some(P.manager value);
          save_component_build state value;
          artifact "candidate"(Synthetic_authority.Candidate.to_json(P.candidate value));
          artifact "pipeline_result"(C.Pipeline_result.to_json(P.result value));
          artifact "selection_result"(selection(P.selection_result value));
          artifact "assembly"(Component_assembly.to_json(P.assembly value));
          artifact "link_result"(Composition_evidence.Result.to_json(P.link_result value));
          artifact "behavior_result"(Realization_evidence.Check_result.to_json(P.behavior_result value)));
  obj["kind",str kind;"manager",Json.Bool true;"artifacts",strings(List.map fst state.artifacts);
    "target",target_envelope state]
let reference_workflow (state:t)=match state.reference_workflow with
  | Some value->(match RW.owner value with Some owner when owner==live state->value
      | _->fail "Reference workflow manager is unavailable.")
  | None->fail "No reference workflow is active."
let reference_notice (state:t) ~sequence operation=
  Option.iter(fun workflow->RW.notice workflow ~budget:(work state) ~owner:(live state) ~sequence operation)
    state.reference_workflow
let reference_limits (state:t)=
  let ceilings=RD.Codec.limits_json RD.default_limits in
  RD.Codec.make_limits ~max_bytes:(min(number(get "max_document_bytes" state.manager_json))(number(get "max_bytes" ceilings)))
    ~max_nodes:(min(number(get "max_document_nodes" state.manager_json))(number(get "max_nodes" ceilings)))
    ~charge:(W.charge(work state)) ()
let reference_producer_limits (state:t)=
  let bytes=number(get "max_document_bytes" state.manager_json)
  and nodes=number(get "max_document_nodes" state.manager_json) in
  RG.make_limits ~max_input_bytes:(min 33_554_432 bytes) ~max_input_nodes:(min 1_000_000 nodes)
    ~max_output_bytes:(min 16_777_216 bytes) ~max_output_nodes:(min 1_000_000 nodes) ()
let reference_argument (state:t) action ~input argument=
  let reply=invoke state action(obj["input",input;"argument",argument;"tree",fresh_ordered state argument]) in
  Json.exact_fields["kind";"argument";"output"](Json.object_fields reply);
  ignore(host state(get "argument" reply));retain state reply;
  (match text "kind" reply with
   | "native"->require(get "output" reply=Json.Null) "Native reference default returned a host output."
   | "host"->ignore(host state(get "output" reply))
   | _->fail "Unknown reference source callback result.");reply
let remember_reference_output (state:t) role output argument=
  let origins=if role="components_to_construct.producer" then obj["parsed",argument] else
    let roots=match state.reference_molecular_roots,state.reference_roots with
      | Some value,_ | None,Some value->value
      | None,None->fail "Reference authoring roots are absent." in
    let policies=get "policy_objects" roots in
    obj["parsed",argument;"request",get "request_object" roots;
      "translation_policy",get "translation_policy" policies;"encoding_policy",get "encoding_policy" policies;
      "evidence_policy",get "evidence_policy" policies] in
  let size=C.Codec.measure ~limits:(codec state) output in
  (* A direct call or later validation failure may never store a manager record,
     but this origin table still owns the complete output. Reserve that retained
     tree before adding its entry, including collection and role cells. *)
  Ch.retain_bytes(channel state)(size.bytes+32*size.nodes+String.length role+128);
  retain state origins;
  (* Key by the actual generator's immutable JSON object, never by equal bytes
     or a last-call slot. Reentrant calls can finish in a different order. *)
  state.reference_outputs<-(output,role,origins)::state.reference_outputs
let reference_host_proposal (state:t) supplied ~output ~source_links=
  require(supplied==work state) "Reference proposal received a foreign lifetime budget.";
  let arguments=obj["output",H.reference(bridge state) output;
    "source_links",Json.Array(map state C.Source_link.to_json source_links)] in
  retain state arguments;host state(invoke state "reference-proposal" arguments)
let reference_generator_bridge (state:t):RC.generator_bridge={
  generate=(fun supplied ~input request->
    require(supplied==work state) "Reference generator received a foreign lifetime budget.";
    let reply=reference_argument state "reference-generate" ~input(RD.Request.to_json request) in
    if text "kind" reply="host" then RC.Host_candidate(host state(get "output" reply)) else
    let candidate=RG.generate ~parent:supplied ~limits:(reference_producer_limits state) request in
    remember_reference_output state "components_to_construct.producer"(RD.Candidate.to_json candidate)(get "argument" reply);
    RC.Native_candidate candidate);
  host_proposal=reference_host_proposal state}
let reference_emitter_bridge (state:t):RM.emitter_bridge={
  emit=(fun supplied ~input ~request ~construct ~registry ~manifests->
    require(supplied==work state) "Reference emitter received a foreign lifetime budget.";
    let reply=reference_argument state "reference-emit" ~input(RD.Candidate.to_json construct) in
    if text "kind" reply="host" then RM.Host_artifact(host state(get "output" reply)) else
    let candidate=RE.emit ~parent:supplied ~limits:(reference_producer_limits state)
      ~request ~construct ~registry ~manifests () in
    remember_reference_output state "construct_to_molecular.producer"(Reference_molecular.Artifact.to_json candidate)(get "argument" reply);
    RM.Native_artifact candidate);
  host_proposal=reference_host_proposal state}
let reference_links_equal (state:t) supplied ~actual ~expected=
  require(supplied==work state) "Reference link comparison received a foreign lifetime budget.";
  let arguments=obj["actual",Json.Array(map state(H.reference(bridge state)) actual);
    "expected",Json.Array(map state C.Source_link.to_json expected)] in
  retain state arguments;Json.boolean(invoke state "reference-source-links-equal" arguments)
let reference_provider_view (state:t) entry kind value=
  let role=match entry.reference with
    | Some value when value.reference_owner==live state->value.reference_role
    | _->fail "Reference provider belongs to another manager incarnation." in
  let producer=List.mem role["components_to_construct.producer";"construct_to_molecular.producer"] in
  require((producer && kind="proposal") || (not producer && kind="decision"))
    "Reference provider returned a result inconsistent with its observed role.";
  let origins=if not producer then obj[] else
    let output=get "output" value in
    match find state(fun(previous,previous_role,_)->previous==output && previous_role=role)state.reference_outputs with
    | Some(_,_,origins)->origins
    | None->fail "Reference proposal has no actual generator invocation origins." in
  obj["role",str role;"tree",fresh_ordered state value;"origins",origins]
let reference_registration (state:t) contract producer validators=
  let raw=C.Pass_contract.to_json contract in retain state raw;
  let producer=provider_reference state(provider_entry state producer) in
  let validators=map state(fun(key,value)->Json.Array[str key;provider_reference state(provider_entry state value)])validators in
  let obligations=(native_sidecar state(C.Pass_contract.introduces contract)).elements in
  let value=obj["contract",raw;"producer",producer;"validators",Json.Array validators;
    "obligation_objects",Json.Array obligations] in retain state value;value
let initialize_reference (state:t) payload=
  require(not state.initialized) "Initialization has already been attempted.";
  state.initialized<-true;state.reference_mode<-true;retain state payload;set_limits state(get "manager_limits" payload);
  state.target_binding<-Some(host_binding state(get "target_object" payload));
  let decode name tree_name=
    let tree=get tree_name payload in reserve_ordered state tree;
    let raw=unordered state 0 tree in
    require(equivalent_json state raw(get name payload)) "Ordered reference authority differs from its canonical document.";raw in
  let request_raw=decode "request" "request_tree" in
  let registry_raw=decode "registry" "registry_tree" in
  let manifests_raw=decode "manifests" "manifests_tree" in
  let request=RD.Request.of_json ~limits:(reference_limits state) request_raw in
  let registry=imported state(fun raw->Component_registry.of_json raw)registry_raw in
  let manifests=map state(function Json.Array[Json.String key;raw]->
      key,Reference_manifest.of_json ~limits:(reference_limits state) raw
    | _->fail "Reference manifests require ordered name/document pairs.")(Json.array manifests_raw) in
  List.iter(fun key->ignore(host state(get key payload)))
    ["request_object";"registry_object";"construct_manifests_object"];
  let molecular=get "molecular_manifests_object" payload in
  if molecular<>Json.Null then ignore(host state molecular);
  let policies=get "policy_objects" payload in
  Json.exact_fields["translation_policy";"encoding_policy";"evidence_policy"](Json.object_fields policies);
  List.iter(fun(_,value)->ignore(host state value))(Json.object_fields policies);
  let roots=obj(List.map(fun key->key,get key payload)
    ["request_object";"registry_object";"construct_manifests_object";"molecular_manifests_object";"policy_objects"]) in
  retain state roots;state.reference_roots<-Some roots;
  let workflow=RW.create ~budget:(work state) ~retain_bytes:(Ch.retain_bytes(channel state)) ~manager_limits:state.manager_limits () in
  state.reference_workflow<-Some workflow;
  ignore(RW.initialize_construct workflow ~budget:(work state) ~validator_equivalent:(equivalent state)
    ~observer:(observe state) ~manager_created:(publish_fixed_manager state) ~request ~registry ~manifests ());
  obj["kind",str "reference";"manager",Json.Bool true;"artifacts",Json.Array[];"target",target_envelope state]
let reference_admission (state:t)=
  let admission=RW.prepare_admission(reference_workflow state) ~budget:(work state)
    ~provider_observer:(observe_construct_provider state) () in
  let contract=RC.admission_contract admission in
  let validators=map state(fun(key,value)->Json.Array[str key;provider_reference state(provider_entry state value)])
    (RC.admission_validators admission) in
  let obligations=(native_sidecar state(C.Component_input_contract.obligations contract)).elements in
  let raw=obj["contract",C.Component_input_contract.to_json contract;"validators",Json.Array validators;
    "obligation_objects",Json.Array obligations] in retain state raw;raw
let reference_construct_registration (state:t)=
  let registration=RW.prepare_construct_registration(reference_workflow state) ~budget:(work state)
    ~provider_observer:(observe_construct_provider state) ~generator_bridge:(reference_generator_bridge state)
    ~host_links_equal:(reference_links_equal state) () in
  reference_registration state(RC.contract registration)(RC.producer registration)(RC.validators registration)
let reference_preparation (state:t) token=
  require(state.reference_preparation=Some token) "Unknown reference Molecular preparation capability.";
  reference_workflow state
let reference_prepared (state:t) prepared=
  let token=identity state "reference-preparation" in
  let dependencies=Json.Array(map state(fun(key,value)->Json.Array[str key;str value])(RM.dependencies prepared)) in
  let raw=obj["preparation_id",str token;"dependencies",dependencies] in
  retain state raw;state.reference_preparation<-Some token;raw
let prepare_reference_molecular_public (state:t) payload=
  let workflow=reference_workflow state in
  retain state payload;
  let decode name tree_name=
    let tree=get tree_name payload in reserve_ordered state tree;
    let raw=unordered state 0 tree in
    require(equivalent_json state raw(get name payload)) "Ordered Molecular authority differs from its canonical document.";
    raw in
  let request_raw=decode "request" "request_tree" in
  let registry_raw=decode "registry" "registry_tree" in
  let manifests_raw=decode "manifests" "manifests_tree" in
  let request=RD.Request.of_json ~limits:(reference_limits state) request_raw in
  let registry=imported state(fun raw->Component_registry.of_json raw)registry_raw in
  let manifests=map state(function Json.Array[Json.String key;raw]->
      key,Reference_manifest.of_json ~limits:(reference_limits state) raw
    | _->fail "Molecular manifests require ordered name/document pairs.")(Json.array manifests_raw) in
  require(List.length manifests=List.length(unique_names state(map state fst manifests)))
    "Molecular manifest authority repeats a mapping key.";
  List.iter(fun key->ignore(host state(get key payload)))
    ["request_object";"registry_object";"molecular_manifests_object"];
  let policies=get "policy_objects" payload in
  Json.exact_fields["translation_policy";"encoding_policy";"evidence_policy"](Json.object_fields policies);
  List.iter(fun(_,value)->ignore(host state value))(Json.object_fields policies);
  let roots=obj(List.map(fun key->key,get key payload)
    ["request_object";"registry_object";"molecular_manifests_object";"policy_objects"]) in
  let prepared=RW.prepare_molecular ~authority:({request;registry;manifests}:RM.authority)
    workflow ~budget:(work state) () in
  retain state roots;state.reference_molecular_roots<-Some roots;
  reference_prepared state prepared
let reference_final_source (state:t) upstream : RM.final_source_bridge=
  ignore(host state upstream);retain state upstream;
  let call supplied phase=
    require(supplied==work state) "Reference final source received a foreign lifetime budget.";
    invoke state "reference-upstream-candidate"(obj["upstream",upstream;"phase",str phase]) in
  {check_construct=(fun supplied->
      let reply=call supplied "check" in
      Json.exact_fields["object";"value";"tree"](Json.object_fields reply);
      ignore(host state(get "object" reply));retain state reply;
      let tree=get "tree" reply in reserve_ordered state tree;
      let raw=unordered state 0 tree in
      require(equivalent_json state raw(get "value" reply)) "Ordered final Construct differs from its canonical document.";
      if raw=Json.Null then Diagnostic.fail "reference_molecular" "Invalid molecular checker artifacts.";
      RD.Candidate.of_json ~limits:(reference_limits state) raw);
   return_construct=(fun supplied->
      let reply=call supplied "return" in
      Json.exact_fields["object"](Json.object_fields reply);
      retain state reply;host state(get "object" reply))}
let reference_build_result (state:t) kind=
  require(List.mem kind["construct";"molecular"]) "Unknown reference build kind.";
  match List.assoc_opt kind state.reference_builds with Some value->value | None->
  let workflow=reference_workflow state in
  let candidate,check_result,record,result,construct=if kind="construct" then
    let value=match RW.construct_build workflow with Some value->value | None->fail "No completed Construct build." in
    build_artifact state(Build_construct(RC.candidate value))(RD.Candidate.to_json(RC.candidate value)),
    build_artifact state(Build_construct_check(RC.check_result value))(Reference_construct_evidence.Result.to_json(RC.check_result value)),
    RC.record value,RC.result value,Json.Null
  else let value=match RW.molecular_build workflow with Some value->value | None->fail "No completed Molecular build." in
    build_artifact state(Build_molecular(RM.candidate value))(Reference_molecular.Artifact.to_json(RM.candidate value)),
    build_artifact state(Build_molecular_check(RM.check_result value))(Reference_molecular_evidence.Result.to_json(RM.check_result value)),
    RM.record value,RM.result value,
    (match RM.returned_construct value with
     | Some value->obj["value",Json.Null;"binding",host_binding state(H.reference(bridge state)value)]
     | None->build_artifact state(Build_construct(RM.construct value))(RD.Candidate.to_json(RM.construct value))) in
  let raw=obj["build_id",str(identity state "reference-build");"kind",str kind;
    "candidate",candidate;"check_result",check_result;"construct",construct;
    "result",obj["value",C.Pipeline_result.to_json result;"artifact",record_envelope state record]] in
  retain state raw;state.reference_builds<-(kind,raw)::state.reference_builds;raw
let reference_record (state:t) token=
  match find state(fun (value:record_view)->text "record_id" value.bindings=token)state.records with
  | Some value->value.record | None->fail "Unknown reference run record capability."
let authored_sidecar (state:t) obligations payload ~whole ~requirements=
  let refs=Json.array(get "obligation_objects" payload) in
  require(List.length refs=List.length obligations) "Obligation metadata does not match its typed slots.";
  {elements=map state(host_binding state) refs;
   whole=(if whole then Some(host_binding state(get "obligations_object" payload)) else None);
   requirements=(if requirements then Some(host_binding state(get "requirements_object" payload)) else None)}
let snapshot (state:t) ~provider_identity=
  let raw=M.inspect(live state) ~provider_identity in
  let records=Json.object_fields(get "records" raw) in
  let records=map state(fun(name,_)->
    let entry=match find state(fun value->C.Stage_record.id value.record=name) state.records with
      | Some value->value | None->fail "Historical manager record has no incarnation metadata." in
    name,record_envelope state entry.record) records in
  obj(List.map(fun(key,value)->key,(if key="records" then obj records else value))(Json.object_fields raw))
let inspect (state:t)=snapshot state ~provider_identity:(fun provider->(provider_entry state provider).provider_id)
let inspect_ordered (state:t)=
  let reachable=ref [] in
  let provider_identity provider=
    let entry=provider_entry state provider in
    if not(List.exists(fun previous->charge state;previous==entry) !reachable) then
      reachable:=entry::!reachable;
    entry.provider_id in
  let snapshot=snapshot state ~provider_identity in
  let order=M.inspection_order(live state) in
  (* Resolve only providers referenced by this historical snapshot. Rejected
     registrations may have interned additional host objects; they remain
     callback traffic evidence and are not presented as manager registrations. *)
  let providers=map state(fun entry->obj["provider_id",str entry.provider_id;
    "object",provider_reference state entry])(List.rev !reachable) in
  obj["snapshot",snapshot;"order",order;"providers",Json.Array providers]
let inspect_ordered_references (state:t)=
  (* Definitions are already retained actual records. This operation allocates
     only reference/envelope cells and a delivered-identity census; it never
     performs freshness checks, reconstructs a manager or imports acceptance. *)
  Ch.retain_bytes(channel state)1024;
  let reachable=ref [] in
  let provider_identity provider=
    let entry=provider_entry state provider in
    if not(List.exists(fun previous->charge state;previous==entry) !reachable) then (
      Ch.retain_bytes(channel state)96;reachable:=entry::!reachable);
    entry.provider_id in
  let raw=M.inspect(live state) ~provider_identity in
  let order=M.inspection_order(live state) in
  let providers=map state(fun entry->Ch.retain_bytes(channel state)256;
    obj["provider_id",str entry.provider_id;"object",provider_reference state entry])(List.rev !reachable) in
  (* Resolve any first-use host proxies before reading the publication census.
     A nested inspection during that continuation may itself deliver records. *)
  let published=ref state.compact_records and definitions=ref [] in
  let records=map state(fun(name,document)->
    (* M.inspect uses Stage_record.to_json's retained immutable document, so
       physical document identity names its exact incarnation even if a nested
       command has since stored another record with the same public name. *)
    let entry=match find state(fun value->C.Stage_record.to_json value.record==document)state.records with
      | Some value->value | None->fail "Compact inspection lacks its actual historical record." in
    let actual=C.Stage_record.id entry.record in
    W.charge(work state)(String.length actual+String.length name+1);
    require(actual=name) "Compact inspection record metadata differs from its actual manager state.";
    Ch.retain_bytes(channel state)256;
    if not(List.exists(fun previous->charge state;previous==entry.record) !published) then (
      (* Prepay new list/envelope cells. The immutable document and binding
         trees are shared with the strongly retained original record view. *)
      Ch.retain_bytes(channel state)256;
      definitions:=record_envelope state entry.record::!definitions;
      published:=entry.record::!published);
    name,obj["record_id",get "record_id" entry.bindings])
    (Json.object_fields(get "records" raw)) in
  let snapshot=obj(map state(fun(key,value)->key,if key="records" then obj records else value)(Json.object_fields raw)) in
  W.charge(work state)(List.length !definitions+1);
  Ch.retain_bytes(channel state)(32*List.length !definitions+256);
  let result=obj["snapshot",snapshot;"order",order;"providers",Json.Array providers;
    "record_definitions",Json.Array(List.rev !definitions)] in
  (* Do not consume definition publication after a failed assembly/preflight.
     A subsequent uncertain write closes the channel, so no retry can observe
     an undelivered census on another live authority. *)
  ignore(C.Codec.measure ~limits:(codec state) result);
  state.compact_records<- !published;result
let dispatch_value (state:t) ~sequence operation payload=
  let declared=try get operation(get "operations" declaration) with Diagnostic.Error _->fail "Unknown manager operation." in
  Json.exact_fields(List.map Json.string(Json.array(get "fields" declared)))(Json.object_fields payload);
  let field key=get key payload and name key=text key payload in
  match operation with
  | "initialize-empty"->initialize state "empty" payload
  | "initialize-synthetic"->initialize state "synthetic" payload
  | "initialize-components"->initialize state "components" payload
  | "initialize-reference"->initialize_reference state payload
  | "reference-admission"->reference_admission state
  | "reference-registration"->reference_construct_registration state
  | "reference-build-result"->reference_build_result state(name "kind")
  | "finish-reference-construct"->
      ignore(RW.finish_construct(reference_workflow state) ~budget:(work state)
        ~record:(reference_record state(name "record_id")) ~result_sequence:(number(field "result_sequence")));
      reference_build_result state "construct"
  | "prepare-reference-molecular"->
      let roots=match state.reference_roots with Some value->value | None->fail "Reference authoring roots are absent." in
      require(get "molecular_manifests_object" roots<>Json.Null) "Molecular continuation lacks its authored manifest snapshot.";
      let prepared=RW.prepare_molecular(reference_workflow state) ~budget:(work state) () in
      reference_prepared state prepared
  | "prepare-reference-molecular-public"->prepare_reference_molecular_public state payload
  | "reference-molecular-profile"->
      let profile=RW.prepare_molecular_profile(reference_preparation state(name "preparation_id")) ~budget:(work state) () in
      let raw=C.Completion_profile.to_json(RM.completion_profile profile) in retain state raw;raw
  | "reference-molecular-registration"->
      let registration=RW.prepare_molecular_registration(reference_preparation state(name "preparation_id")) ~budget:(work state)
        ~provider_observer:(observe_molecular_provider state) ~emitter_bridge:(reference_emitter_bridge state)
        ~host_links_equal:(reference_links_equal state) () in
      reference_registration state(RM.contract registration)(RM.producer registration)(RM.validators registration)
  | "finish-reference-molecular"->
      let final_source_bridge=match field "upstream" with Json.Null->None
        | value->Some(reference_final_source state value) in
      ignore(RW.finish_molecular ?final_source_bridge(reference_preparation state(name "preparation_id")) ~budget:(work state)
        ~record:(reference_record state(name "record_id")) ~result_sequence:(number(field "result_sequence")));
      reference_build_result state "molecular"
  | "build-result"->build_result state(name "kind")
  | "prepare-components"->prepare_components state
  | "component-profile"->component_profile state(name "preparation_id")
  | "component-registration"->component_registration state(name "preparation_id")
  | "finish-components"->
      let workflow=workflow state(name "preparation_id") in
      let registration,record,result=match workflow.phase with
        | Component_result(registration,record,result_sequence,result)
          when result_sequence=number(field "result_sequence") &&
            text "record_id"(record_view state record).bindings=name "record_id"->registration,record,result
        | _->fail "Component finish lacks its actual matching run/result capabilities." in
      let value=P.finish ~budget:(work state) registration ~record ~result in
      save_component_build state value;workflow.phase<-Component_finished;
      build_result state "components"
  | "target"->target_envelope state
  | "inspect"->inspect state
  | "inspect-ordered"->inspect_ordered state
  | "inspect-ordered-references"->inspect_ordered_references state
  | "get"->let identity=name "identity" in
      let record=M.get(live state) identity in
      reference_notice state ~sequence(RW.Got {identity;record});record_envelope state record
  | "result"->let manager=live state in
      let value=M.result manager ~identity:(name "identity") ~scope:(name "scope") in
      (* A result already retains the actual record whose freshness it checked.
         Envelope publication must not add a second manager read. *)
      let record=C.Pipeline_result.artifact value in
      reference_notice state ~sequence(RW.Result_returned {identity=name "identity";scope=name "scope";result=value});
      (match state.component_workflow with
       | Some ({phase=Component_ran(registration,previous);_} as workflow)
         when workflow.owner==manager && record==previous && name "identity"="components" && name "scope"="synthetic_components"->
           retain state(C.Pipeline_result.to_json value);
           workflow.phase<-Component_result(registration,record,sequence,value)
       | _->());
      obj["value",C.Pipeline_result.to_json value;
        "artifact",record_envelope state record]
  | "set-dependency"->
      let key=name "key" and value=name "identity" in
      M.set_dependency(live state)key value;
      reference_notice state ~sequence(RW.Dependency_set(key,value));
      (match state.component_workflow with
       | Some ({phase=Updating_dependencies((expected_key,expected_value)::rest);_} as workflow)->
           W.charge(work state)(String.length key+String.length value+String.length expected_key+String.length expected_value+1);
           if key=expected_key && value=expected_value then workflow.phase<-Updating_dependencies rest
       | _->());Json.Null
  | "register-completion-profile"->let manager=live state in
      let profile=C.Completion_profile.of_json ~limits:(manager_codec state)(field "profile") in
      M.register_completion_profile manager profile;
      reference_notice state ~sequence(RW.Profile_registered profile);
      (match state.component_workflow with
       | Some ({phase=Profile_available value;_} as workflow) when workflow.owner==manager->
           if equivalent_json state(C.Completion_profile.to_json profile)(C.Completion_profile.to_json(P.completion_profile value)) then
             workflow.phase<-Profile_registered value
       | _->());Json.Null
  | "add-input"->let manager=live state in
      let stage=C.stage_of_json(field "stage") in
      let requirements=List.map Json.string(Json.array(field "requirements")) in
      let obligations=map state(fun raw->C.Scoped_obligation.of_json ~limits:(manager_codec state) raw)(Json.array(field "obligations")) in
      let sidecar=authored_sidecar state obligations payload ~whole:true ~requirements:false in
      let prior=state.input_sidecar in
      state.input_sidecar<-Some sidecar;
      Fun.protect ~finally:(fun()->state.input_sidecar<-prior)(fun()->
        record_envelope state(M.add_host_input manager ~identity:(name "identity") ~stage ~requirements ~obligations
          (host state(field "payload"))))
  | "admit-component-input"->let contract_id=name "contract_id" and identity=name "identity" in
      let record=M.admit_host_component_input(live state) ~contract_id ~identity(host state(field "payload")) in
      reference_notice state ~sequence(RW.Admitted {contract_id;identity;record});record_envelope state record
  | "run"->let configuration=match field "configuration" with Json.Null->None | raw->Some(host state raw) in
      let record=M.run_host(live state) ~pass_id:(name "pass_id") ~input_id:(name "input_id")
        ~output_id:(name "output_id") ?configuration () in
      reference_notice state ~sequence(RW.Ran {pass_id=name "pass_id";input_id=name "input_id";
        output_id=name "output_id";default_configuration=Option.is_none configuration;record});
      (match state.component_workflow with
       | Some ({phase=Registration_installed value;_} as workflow)
         when name "pass_id"=C.Pass_contract.id(P.contract value) && name "input_id"="mechanism" &&
           name "output_id"="components" && configuration=None->workflow.phase<-Component_ran(value,record)
       | _->());record_envelope state record
  | "register"->let manager=live state in
      let contract=C.Pass_contract.of_json ~limits:(manager_codec state)(field "contract") in
      let sidecar=authored_sidecar state(C.Pass_contract.introduces contract) payload ~whole:false ~requirements:false in
      let producer=field "producer" and validators=field "validators" in
      let deferred=deferred_validators state ~producer validators in
      let actual_validators=ref [] and actual_producer=ref None in
      let captured={deferred with M.snapshot=(fun budget->
        let values=deferred.M.snapshot budget in actual_validators:=values;values)} in
      M.register_deferred manager contract ~producer:(fun _->let value=intern_provider state producer in
        actual_producer:=Some value;value)
        ~self_certifying:(self_certifying state producer validators) captured;
      (match !actual_producer with Some producer->
        reference_notice state ~sequence(RW.Pass_registered(contract,producer,!actual_validators))
       | None->fail "Successful registration did not retain its actual producer.");
      retain state(field "contract");state.pass_sidecars<-(contract,sidecar)::state.pass_sidecars;
      (match state.component_workflow with
       | Some ({phase=Registration_available value;_} as workflow) when workflow.owner==manager->
           if equivalent_json state(C.Pass_contract.to_json contract)(C.Pass_contract.to_json(P.contract value)) then (
             (* The actual manager has already accepted this registration. A
                wrapped producer does not remove the original fixed validator's
                explicit ability to compare real deferred host source links. *)
             List.iter(fun(expected_key,expected_provider)->
               if List.exists(fun(key,provider)->
                 W.charge(work state)(String.length key+String.length expected_key+1);
                 key=expected_key && provider==expected_provider) !actual_validators then
                 M.allow_host_source_links manager expected_provider)(P.validators value);
             workflow.phase<-Registration_installed value)
       | _->());Json.Null
  | "register-component-input"->let manager=live state in
      let contract=C.Component_input_contract.of_json ~limits:(manager_codec state)(field "contract") in
      let sidecar=authored_sidecar state(C.Component_input_contract.obligations contract) payload ~whole:true ~requirements:true in
      let deferred=deferred_validators state(field "validators") and actual_validators=ref [] in
      let captured={deferred with M.snapshot=(fun budget->let values=deferred.M.snapshot budget in
        actual_validators:=values;values)} in
      M.register_component_input_deferred manager contract captured;
      reference_notice state ~sequence(RW.Input_registered(contract,!actual_validators));
      retain state(field "contract");state.admission_sidecars<-(contract,sidecar)::state.admission_sidecars;Json.Null
  | "artifact"->(match List.assoc_opt(name "name") state.artifacts with
      | Some value->value | None->fail "No such completed build artifact.")
  | "call-native-provider"->
      let provider=match find state(fun value->value.provider_id=name "provider_id" && value.host=None) state.providers with
        | Some value->value | None->fail "Unknown native provider capability." in
      (match provider.reference with Some value->
        require(value.reference_owner==live state) "Reference provider belongs to another manager incarnation."
       | None->require((fixed_provider provider).owner==live state) "Fixed provider belongs to another manager incarnation.");
      let context=match find state(fun value->value.context_id=name "context_id") state.contexts with
        | Some value->value | None->fail "Unknown native context capability." in
      let returned=M.invoke_provider(live state) ~host_links:context.host_links provider.provider context.context in
      (match returned,provider.reference with
       | M.Host_return value,Some role when List.mem role.reference_role
           ["components_to_construct.producer";"construct_to_molecular.producer"]->
           obj["kind",str "host";"object",H.reference(bridge state) value]
       | _->
      let kind,value=match returned with
        | M.Proposal value->"proposal",C.Pass_result.to_json value
        | M.Decision value->"decision",C.Check_decision.to_json value
        | M.Invalid_return value->"invalid",value
        | M.Host_return _->fail "Native provider returned a foreign host result." in
      let view=if kind="invalid" then Json.Null else match provider.reference with
        | Some _->reference_provider_view state provider kind value
        | None->provider_view state provider kind value in
      obj["kind",str kind;"value",value;"view",view])
  | _->fail "Unsupported manager operation."
let exception_json (state:t) owner kind message attributes=
  retain state(str message);
  let attributes_tree=fresh_ordered state attributes in
  obj["module",str owner;"type",str kind;"message",str message;
    "attributes",attributes;"attributes_tree",attributes_tree]
let exception_dependencies (state:t) values=
  (* Dependency names and identities already exist in the manager. Reserve a
     conservative escaped representation and its new collection cells before
     constructing the error's independent dependency document. *)
  Ch.retain_bytes(channel state)64;
  List.iter(fun(key,value)->charge state;
    Ch.retain_bytes(channel state)(6*(String.length key+String.length value)+128)) values;
  obj(map state(fun(key,value)->key,str value) values)
let reject (state:t)=function
  | Diagnostic.Error diagnostic when diagnostic.code="pipeline_error"->
      Some(exception_json state "biocompiler.compiler.pipeline" "PipelineError" diagnostic.message(obj[]))
  | Diagnostic.Error diagnostic when List.mem diagnostic.code["pipeline_serialization";"pipeline_contract"]->
      Some(exception_json state "biocompiler.errors" "SerializationError" diagnostic.message(obj[]))
  | Diagnostic.Error diagnostic when state.reference_mode && List.mem diagnostic.code
      ["reference_construct";"reference_manifest";"reference_molecular";
       "reference_construct_evidence";"reference_molecular_evidence";
       "reference_construct_producer";"reference_sequence_emitter";"verification_exploration"]->
      (* These are the reference declarations' original SerializationError
         leaves. Resource, phase, capability and protocol errors stay fatal. *)
      Some(exception_json state "biocompiler.errors" "SerializationError" diagnostic.message(obj[]))
  | M.No_candidate_found value->
      let dependencies=exception_dependencies state value.dependencies in
      Some(exception_json state "biocompiler.compiler.pipeline" "NoCandidateFound" value.message
        (obj["pass_id",str value.pass_id;"configuration",value.configuration;"dependencies",dependencies]))
  | G.Unsupported value->Some(exception_json state "biocompiler.errors" "UnsupportedBehaviorError"(G.format_error value)(obj[]))
  | _->None
let dispatch (state:t) _ (command:Ch.command)=
  try Ch.Success(dispatch_value state ~sequence:command.sequence command.operation command.arguments)
  with cause->match reject state cause with Some value->Ch.Rejected value | None->raise cause
let create ~io ()=
  let state={channel=None;bridge=None;initialized=false;live=None;manager_limits=M.default_limits;
    manager_json=defaults;target_binding=None;requested_config=None;fixed_request=None;origins=[];artifacts=[];providers=[];contexts=[];records=[];compact_records=[];
     authority=None;upstream=None;component_attempted=false;component_workflow=None;builds=[];build_artifacts=[];selection_views=[];candidate_types=[];
     reference_mode=false;reference_workflow=None;reference_roots=None;reference_molecular_roots=None;reference_outputs=[];reference_builds=[];reference_preparation=None;
    bindings=[];frozen=[];executions=[];pass_sidecars=[];admission_sidecars=[];
    input_sidecar=None;next_identity=0} in
  let value=Ch.create ~io ~application:declaration ~dispatch:(dispatch state) () in
  state.channel<-Some value;state
let release (state:t)=
   state.reference_mode<-false;
   Option.iter RW.close state.reference_workflow;state.reference_workflow<-None;
   state.reference_roots<-None;state.reference_molecular_roots<-None;state.reference_outputs<-[];state.reference_builds<-[];state.reference_preparation<-None;
  Option.iter H.close state.bridge;state.bridge<-None;state.live<-None;state.target_binding<-None;state.requested_config<-None;state.fixed_request<-None;state.origins<-[];
  state.artifacts<-[];state.providers<-[];state.contexts<-[];state.records<-[];state.compact_records<-[];state.bindings<-[];
  state.authority<-None;state.upstream<-None;state.component_workflow<-None;state.builds<-[];
  state.build_artifacts<-[];state.selection_views<-[];state.candidate_types<-[];
  state.frozen<-[];state.executions<-[];state.pass_sidecars<-[];state.admission_sidecars<-[];state.input_sidecar<-None
let run (state:t)=Fun.protect ~finally:(fun()->release state)(fun()->Ch.run(channel state))
let is_closed (state:t)=Ch.is_closed(channel state)
