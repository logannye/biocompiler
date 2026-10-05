open Bioc_wire
open Bioc_domain
module B=Bioc_artifact.Archive_budget
module Ch=Bioc_pipeline_service.Callback_channel
module CM=Bioc_pipeline_service.Callback_manager
module D=Bioc_reference_artifact.Reference_package_manifest
module I=Bioc_reference_input.Reference_inputs
module Inputs=Bioc_reference_package_service.Reference_build_inputs
module S=Bioc_reference_package_service.Reference_package_workflow
module Rebuild=Bioc_reference_package_service.Reference_package_rebuild
module X=Bioc_reference_export.Reference_sequence_codec
module Export=Bioc_reference_export.Reference_sequence_export
module Pio=Bioc_package_io.Package_io
module V=Bioc_pipeline.Reference_molecular_pipeline
module Codec=Verification_exploration.Codec
let profile="biocompiler.core.reference_package_application.v1"
exception Invalid_request_utf8 of string
let str value=Json.String value
let protocol message=Diagnostic.fail "callback_channel_protocol" message
let require value message=if not value then protocol message
let fields names raw=let values=Json.object_fields raw in Json.exact_fields names values;values
let at key values=Json.field key values
let text raw=Json.string raw
let natural raw=let value=Json.integer raw in
  require(Z.sign value>=0 && Z.fits_int value)"Package capability sequence is outside its native range.";Z.to_int value
let optional f=function Json.Null->None|raw->Some(f raw)
let limits budget=Codec.make_limits ~max_bytes:(B.limits budget).max_member_bytes
  ~max_nodes:(B.limits budget).max_json_nodes ~charge:(B.charge budget)()
let own_json budget raw=let size=Codec.measure ~limits:(limits budget)raw in
  B.reserve budget(size.bytes+128*size.nodes+256);raw
let equal budget left right=let left=Codec.encode ~limits:(limits budget)left in
  let right=Codec.encode ~limits:(limits budget)right in
  B.charge budget(String.length left+String.length right+1);String.equal left right
let codec budget=let l=B.limits budget in
  Verification_exploration.Codec.make_limits ~max_bytes:(min l.max_member_bytes Limits.max_response_bytes)
    ~max_nodes:(min l.max_json_nodes Limits.max_json_nodes) ~charge:(B.charge budget)()
(* Older immutable domains use fixed local parser limits rather than a
   caller-supplied codec. Prepay their bounded construction work and ownership
   on this same package ancestor, as the existing manager importer does. *)
let imported budget decoder raw=
  let size=Codec.measure ~limits:(codec budget)raw in
  B.reserve budget(16*size.bytes+256*size.nodes+512);
  let charged=ref 0 in
  let l=B.limits budget in
  let controls=Codec.make_limits ~max_bytes:(min l.max_member_bytes Limits.max_request_bytes)
    ~max_nodes:(min l.max_json_nodes Limits.max_json_nodes)
    ~charge:(fun amount->B.charge budget amount;charged:= !charged+amount)() in
  ignore(Codec.encode ~limits:controls raw);B.product budget !charged 127;decoder raw
let alphabet=function "DNA"->Reference_manifest.DNA|"RNA"->Reference_manifest.RNA|_->
  Diagnostic.fail "reference_inputs" "The reviewed reference build supports only DNA or RNA."
let hex_char n="0123456789abcdef".[n]
let hex budget bytes=
  require(String.length bytes<=(B.limits budget).max_member_bytes)"Package member exceeds its transport bound.";
  B.product budget(String.length bytes)2;B.reserve budget(2*String.length bytes+64);
  String.init(2*String.length bytes)(fun i->let c=Char.code bytes.[i/2] in hex_char(if i mod 2=0 then c lsr 4 else c land 15))
let unhex budget raw=
  let value=text raw in let count=String.length value in
  require(count mod 2=0 && count/2<=(B.limits budget).max_member_bytes)"Package member hex is outside its transport bound.";
  B.charge budget(count+1);B.reserve budget(count/2+64);
  let digit=function '0'..'9' as c->Char.code c-48|'a'..'f'as c->Char.code c-87|_->protocol"Package bytes require lowercase hexadecimal." in
  String.init(count/2)(fun i->Char.chr(16*digit value.[2*i]+digit value.[2*i+1]))
let member_json budget values=
  B.reserve budget(128*List.length values+128);
  Json.Array(List.map(fun(name,bytes)->Json.Array[str name;str(hex budget bytes)])values)
let manifests budget raw=
  ignore(Codec.measure ~limits:(limits budget)raw);
  List.map(function Json.Array[Json.String name;value]->name,Reference_manifest.of_json ~limits:(codec budget)value
    |_->protocol"Reference manifests require ordered name/declaration pairs.")(Json.array raw)
let manifests_json values=Json.Array(List.map(fun(name,value)->Json.Array[str name;Reference_manifest.to_json value])values)
let codec_json budget value=own_json budget(Json.Object[
  "fasta",str(X.fasta value);"specification",str(X.specification value);
  "line_width",Json.int(X.line_width value);"sequence_sha256",str(X.sequence_sha256 value);
  "molecular_fingerprint",str(X.molecular_fingerprint value)])
let operation_names=["package-inputs";"package-collect";"package-prepare";"package-build";
  "package-export";"package-reconstruct";"package-output";"package-check-native";
  "package-import-inputs";"package-import-files";"package-tools-native";"package-check-evaluate"]
let declaration=Json.parse {application|{"actions":{"package-check":{"arguments":["name","arguments","check_id"],"result":"native_or_host"},"package-check-value":{"arguments":["name","value"],"result":"report_reference"},"package-collect":{"arguments":"reference_manifest","result":"capability"},"package-construct":{"arguments":["artifact"],"result":"construct_candidate"},"package-export":{"arguments":["request","construct","artifact","registry","manifests","line_width"],"result":"native_or_host"},"package-get":{"arguments":["identity"],"result":"completed_sequence"},"package-load":{"arguments":["alphabet"],"result":"capability"},"package-read":{"arguments":["kind","path"],"result":"lowercase_hex"},"package-rebuild":{"arguments":["request","files","run_metadata"],"result":"capability"},"package-report-document":{"arguments":"report_reference","result":"report_document"},"package-report-export":{"arguments":"report_reference","result":"export_report_observation"},"package-report-passed":{"arguments":"report_reference","result":"boolean"},"package-result":{"arguments":["identity","scope"],"result":"completed_sequence"},"package-run":{"arguments":["request","registry","manifests"],"result":"molecular_build_capability"},"package-tools":{"arguments":"null","result":"tool_pins"},"package-version":{"arguments":"null","result":"string"}},"authority":"Actual same-channel manager capabilities and fresh native checks; host reports and transported bytes grant no acceptance.","manager":{"acceptance":"native_manager_checks_and_freshness_only;inspection_and_host_sidecars_cannot_import_accepted_records","actions":{"hydrate-context":{"fields":["context_id","document","bindings"],"result":"object_reference"},"manager-created":{"fields":["target"],"result":"null"},"native-provider":{"fields":["provider_id","role"],"result":"object_reference"},"ordered-json":{"fields":["object"],"result":"ordered_tree"},"ordered-merge":{"fields":["object","before","after","before_tree","after_tree"],"result":"object_reference"},"origin-reference":{"fields":["root","path"],"result":"object_reference"},"provider-reference":{"fields":["object"],"result":"host_or_native_provider_reference"},"reference-emit":{"fields":["preparation_id","provider_id","input","argument","tree"],"result":"reference_source_result"},"reference-generate":{"fields":["input","argument","tree"],"result":"reference_source_result"},"reference-molecular-proposal":{"fields":["preparation_id","output","source_links"],"result":"object_reference"},"reference-molecular-provider":{"fields":["preparation_id","provider_id","role"],"result":"object_reference"},"reference-proposal":{"fields":["output","source_links"],"result":"object_reference"},"reference-source-links-equal":{"fields":["actual","expected"],"result":"boolean"},"reference-upstream-candidate":{"fields":["upstream","phase"],"result":"reference_upstream_candidate"},"register-fixed":{"fields":["contract","producer","validators","obligation_objects"],"result":"null"},"set-equal":{"fields":["object","values"],"result":"boolean"},"source-link-set-equal":{"fields":["objects","expected"],"result":"boolean"}},"argument":"--pipeline-callback-session-v1","authoring_boundary":"canonical_typed_contract_target_profile_fields;opaque_payload_configuration_provider_and_validator_objects_are_read_at_native_requested_points","bindings":{"host":["kind","object"],"native":["kind","identity","tree"]},"broker_actions":{"attr":{"fields":["object","name"],"result":"object_reference"},"attr-default":{"fields":["object","name","default"],"result":"object_reference"},"bind-provider":{"fields":["provider_id","object"],"result":"null"},"call":{"fields":["callable","args","kwargs"],"result":"object_reference"},"call-provider":{"fields":["provider_id","context"],"result":"object_reference"},"callable":{"fields":["object"],"result":"boolean"},"compare":{"fields":["left","right","operator"],"result":"boolean"},"contains":{"fields":["container","item"],"result":"boolean"},"dict":{"fields":["object"],"result":"object_reference"},"document":{"fields":["object"],"result":"object_reference"},"enum":{"fields":["type","value"],"result":"object_reference"},"freeze-json":{"fields":["object"],"result":"object_reference"},"get-item":{"fields":["object","key"],"result":"object_reference"},"is-instance":{"fields":["object","type"],"result":"boolean"},"is-none":{"fields":["object"],"result":"boolean"},"iter":{"fields":["object"],"result":"object_reference"},"json":{"fields":["object"],"result":"json"},"len":{"fields":["object"],"result":"integer"},"list":{"fields":["object"],"result":"object_reference"},"literal":{"fields":["kind","value"],"result":"object_reference"},"lookup":{"fields":["object","entries"],"result":"object_reference"},"mapping-items":{"fields":["object"],"result":"object_reference"},"mapping-keys":{"fields":["object"],"result":"object_reference"},"mapping-values":{"fields":["object"],"result":"object_reference"},"merge":{"fields":["object","before","after"],"result":"object_reference"},"next":{"fields":["object"],"result":"iterator_step"},"release":{"fields":["handles"],"result":"null"},"set-attribute-equal":{"fields":["objects","name","values"],"result":"boolean"},"truth":{"fields":["object"],"result":"boolean"},"tuple":{"fields":["object"],"result":"object_reference"},"vars":{"fields":["object"],"result":"object_reference"}},"channel":"biocompiler.pipeline_callback_channel.v1","claim_scope":"software_contract_conditional_translation_and_scoped_completion;no_empirical_or_human_use_acceptance","comparison_operators":["eq","ne","is","is-not"],"compatibility_pending":["complete_original_installed_replay","fixed_public_registration_interception","arbitrary_authoring_subclass_and_scalar_operator_semantics","default_cutover"],"component_continuation":{"failure":"actual_partial_manager_and_previous_successful_mutations_preserved_on_logical_or_host_failure;fatal_channel_failures_close_authority","finish":"exact_retained_actual_run_record_incarnation_and_matching_actual_result_command_sequence_owner_stage_scope;no_recomputation_or_import_of_accepted_result","limits":"all_preparations_origins_build_views_and_retained_result_receipts_charged_to_channel_lifetime_work_and_retention","obligation_objects":"ordered_native_binding_descriptors_matching_contract_introduces_slots;structural_host_views_returned_as_strong_host_references_during_actual_register;native_validation_remains_authoritative","order":["prepare-components","ordered_actual_set-dependency_calls","component-profile","actual_register-completion-profile","component-registration","actual_register","actual_run","actual_result","finish-components"],"owner":"same_live_manager_and_actual_retained_synthetic_build;one_preparation_attempt;preparation_id_is_channel_scoped_native_capability","preparation":"native_adaptation_and_ordered_dependencies_only;profile_and_registration_constructors_remain_after_prior_actual_mutations","registration":"actual_native_contract_and_physical_fixed_producer_and_validator_closures;ordered_validator_name_and_host_reference_pairs"},"context_bindings":["input","output","target","configuration","dependencies","requirements","source_links","observation_map"],"context_identity":"actual_native_context_physical_identity;distinct_producer_and_validation_contexts;one_validation_context_shared_by_its_validators","default_generator_config":{"catalog_fingerprint":"f2a4b4c1625b4794028fcd1d0e08785724f957023966a29faafe9374cca77343","conjunction_strategy":"native","generator_version":"biocompiler.synthetic.generator.v0.4","profile_version":"biocompiler.synthetic.combinational.v0.1","schema_version":"biocompiler.synthetic_generator_config.v0.3","witness_selection":"closed_band_lower_endpoint"},"default_generator_config_authority":"exact_negotiated_native_Config_make_default;fresh_closed_Python_representation_before_initialization;native_import_and_catalog_validation_remain_authoritative","dependencies_encoding":"ordered_unique_string_identity_pairs","enum_types":["EvidenceKind","CheckOutcome","Stage","ArtifactStatus","PayloadFormat"],"executable":"core","expected_rejection_attributes":"fresh_ordered_tree_with_exact_canonical_attributes_projection;no_cached_binding_or_context_container_reuse;NoCandidateFound_retains_pass_configuration_and_dependency_order","expected_rejection_fields":["module","type","message","attributes","attributes_tree"],"failure":"expected_logical_rejection_and_opaque_host_exception_preserve_actual_partial_manager;malformed_resource_internal_or_uncertain_io_failure_closes_authority","fixed_build_view":{"absent_selection":"value_and_binding_null;selection_config_and_required_capabilities_null;alternative_configs_empty_and_no_selection_aliases;candidate_type_aliases_remain_required","aliases":"selection_paths_start_selection_result_alternatives_nonnegative_index_candidate_then_closed_typed_candidate_path_with_same_eight_provider_alias_tags;candidate_paths_only_TypeSpec_at_candidate_mechanism_nodes_nonnegative_index_output_dtype;no_assembly_or_report_aliases","alternative_configs":"ordered_candidate_slots;null_only_without_candidate;native_constructor_origin_bindings;selected_slot_reuses_actual_fixed_provider_selected_config_origin","artifact_fields":["value","binding"],"artifact_identity":"dedicated_retained_actual_build_artifact_origins;never_manager_frozen_json_or_provider_output_roots;upstream_candidate_and_selection_shared_only_from_actual_retained_synthetic_build","artifacts":{"components":["candidate","selection_result","assembly","link_result","behavior_result"],"synthetic":["candidate","selection_result"]},"candidate_source":"actual_historical_upstream_mechanism_record_envelope;parsed_node_inputs_and_requirement_ids_and_program_outputs_and_required_capabilities_retain_source_tuple_identity","candidate_type_origins":"one_retained_actual_parsed_type_origin_per_upstream_candidate_physical_identity_node_and_argument_path;distinct_even_when_fields_equal;same_origin_used_by_actual_component_provider_registry_descendants","fields":["selection_config","alternative_configs","required_capabilities","aliases"],"fresh_roots":"parsed_candidate_and_assembly_are_fresh_from_original_frozen_payload;assembly_composition_target_is_fresh_and_not_manager_target","kinds":["synthetic","components"],"required_capabilities":"null_without_selection_candidates;otherwise_actual_syntheticCapabilities_constant_host_binding;only_generated_selection_and_provider_candidates_share_this_tuple","result":"actual_historical_pipeline_result_and_record_envelope;finish_reuses_exact_public_result_wrapper_from_result_sequence;historical_views_do_not_grant_fresh_acceptance","selection_config":"actual_requested_host_configuration","sources":["candidate"]},"fixed_registration":{"failure":"published_manager_retained_only_after_exact_completed_rejected_or_opaque_raise_initialization_reply_on_open_channel;fatal_or_uncertain_channel_closes_authority","hook":"source_ordered_actual_fixed_contract_native_producer_ordered_validators_and_introduced_obligations;invoke_current_public_register_once;ignore_return_without_inspection;no_implicit_fallback","native_registration":"only_actual_nested_register_commands_mutate_the_live_manager;producer_wrappers_and_original_native_validator_identity_preserved","publication":"exact_actual_manager_and_authored_target_before_first_input_or_registration;once_per_fixed_initialization;no_manager_replacement","roles":["intent_to_behavior","behavior_to_synthetic","synthetic_to_components"],"staged_components":"existing_actual_public_register_call_only;no_second_register_fixed_hook;unchanged_contract_and_actual_native_validator_enable_host_source_link_capability_independently_of_producer_wrapper"},"fixed_request_tree":"ordered_tree_from_same_authoring_serialization_as_request;exact_canonical_projection_required_before_native_import;retained_order_is_not_acceptance","host_execution":"trusted_host_code_cpu_and_opaque_captures_outside_native_work_and_json_memory_bounds","inspection_order":{"combined_provider_history":"actual_successful_insertion_order;pass_fingerprint_string_or_component_input_tag_and_fingerprint_pair;replacements_preserve_position","fields":["dependencies","passes","component_inputs","provider_history","component_input_history","records","profiles","combined_provider_history","validators"],"mapping_order":"unique_complete_snapshot_key_arrays","provider_fields":["provider_id","object"],"providers":"exact_reachable_snapshot_provider_token_census;stable_bijection_to_actual_retained_callable_identity;no_user_equality_or_hash","scope":"manager_mapping_and_validator_order_only;nested_unobserved_json_order_not_generalized;historical_observation_cannot_grant_acceptance","validator_maps":["passes","component_inputs","provider_history","component_input_history"],"validators":"four_exact_registration_maps_of_unique_complete_validator_key_arrays"},"inspection_references":{"authority":"inspection_only;references_cannot_import_records_or_grant_fresh_acceptance;existing_inspect_ordered_unchanged","definitions":"ordered_complete_record_envelopes_exactly_for_first_compact_publication_of_each_actual_record_incarnation_in_order_records;no_duplicates_unused_definitions_or_rebinding","record_reference_fields":["record_id"],"resolution":"same_channel_earlier_or_current_definitions_only;exact_record_name_and_incarnation_bijection;checked_immutable_full_envelope_expansion_without_get_result_or_acceptance_query","retention":"strong_actual_record_identity_and_definition_publication_census_charged_to_existing_channel_lifetime;publication_marked_only_after_complete_response_assembly","snapshot":"same_complete_historical_state_as_inspect_ordered_with_records_replaced_by_incarnation_references;all_other_fields_and_orders_unchanged"},"iterator_step_fields":["exhausted","object"],"lifecycle":"one_initialization_attempt_per_channel;existing_channel_close_is_top_level_only;no_reconnect_retry_or_state_import","limits":"all_native_framing_application_import_callback_and_publication_work_uses_one_channel_lifetime_ancestor;retention_is_cumulative_no_refund","literal_kinds":["json","tuple","set"],"manager_limits":"initialization_once;null_defaults_or_complete_positive_integer_reductions","native_provider_context":"only_exact_retained_context_from_this_live_manager;no_external_context_import","native_provider_result_kinds":["proposal","decision","invalid"],"native_provider_view":{"alias_fields":["kind","paths","binding"],"alias_kinds":["biocompiler.ir.intent.SourceLocation","biocompiler.semantics.types.TypeSpec","biocompiler.semantics.realization.Observable","biocompiler.semantics.component_contracts.OperatingDomain","biocompiler.semantics.component_contracts.ValueDomain","biocompiler.ir.component_contracts.PinnedIdentity","biocompiler.ir.components.ComponentLock","biocompiler.ir.composition.LifecycleInterval"],"alias_paths":"unique_closed_typed_field_and_nonnegative_array_index_paths_relative_to_complete_value;exact_class_and_shape;slot_overlap_requires_identical_binding","bindings_by_role":{"behavior_to_synthetic.producer":["generator_config","required_capabilities"],"behavior_to_synthetic.validator":[],"intent_to_behavior.producer":[],"intent_to_behavior.validator":[],"synthetic_to_components.producer":["registry","composition","composition_target"],"synthetic_to_components.validator":[]},"fields":["role","tree","bindings","aliases"],"identity":"explicit_actual_host_objects_or_retained_native_constructor_origins;strong_lifetime_retention;never_equal_content_interning;charged_to_channel_limits","invalid":"view_is_null_only_for_invalid_result","lower_context_tuples":"intent_to_behavior_producer_only;BehaviorNode_inputs_and_BehaviorProgram_roots_reuse_exact_actual_owner_context_input_intent_tuples_after_source_node_identity_and_complete_slot_value_checks;no_extra_manager_calls_or_semantic_parser","role_authority":"actual_fixed_native_closure_and_manager_owner;immutable_provider_registration_binding","roles":["intent_to_behavior.producer","intent_to_behavior.validator","behavior_to_synthetic.producer","behavior_to_synthetic.validator","synthetic_to_components.producer","synthetic_to_components.validator"],"scope":"closed_structural_public_views_only;no_semantic_parsers_or_acceptance;fresh_proposal_and_output_roots","tree":"complete_value_ordered_tree;canonical_projection_matches_value"},"object_reference":{"fields":["handle"],"scope":"one_live_trusted_host_broker_physical_identity"},"obligation_objects":"array_of_actual_host_references_matching_canonical_obligation_slots;whole_tuple_sidecar_preserves_add_input_and_admission_collection_identity;run_allocates_a_new_tuple_reusing_elements;sidecars_do_not_grant_acceptance","operations":{"add-input":{"fields":["identity","stage","requirements","obligations","obligation_objects","payload","obligations_object"],"result":"record"},"admit-component-input":{"fields":["contract_id","identity","payload"],"result":"record"},"artifact":{"fields":["name"],"result":"canonical_immutable_build_artifact"},"build-result":{"fields":["kind"],"result":"fixed_build"},"call-native-provider":{"fields":["provider_id","context_id"],"result":"native_provider_result"},"component-profile":{"fields":["preparation_id"],"result":"completion_profile"},"component-registration":{"fields":["preparation_id"],"result":"component_registration"},"finish-components":{"fields":["preparation_id","record_id","result_sequence"],"result":"fixed_build"},"finish-reference-construct":{"fields":["record_id","result_sequence"],"result":"reference_build"},"finish-reference-molecular":{"fields":["preparation_id","record_id","result_sequence","upstream"],"result":"reference_build"},"get":{"fields":["identity"],"result":"record"},"initialize-components":{"fields":["request","request_tree","history","until","config","manager_limits","target_object","request_object","config_object"],"result":"initialization"},"initialize-empty":{"fields":["target","dependencies","completion_profiles","manager_limits","target_object"],"result":"initialization"},"initialize-reference":{"fields":["request","request_tree","registry","registry_tree","manifests","manifests_tree","manager_limits","target_object","request_object","registry_object","construct_manifests_object","molecular_manifests_object","policy_objects"],"result":"initialization"},"initialize-synthetic":{"fields":["request","request_tree","history","until","config","manager_limits","target_object","request_object","config_object"],"result":"initialization"},"inspect":{"fields":[],"result":"historical_observation_only"},"inspect-ordered":{"fields":[],"result":"ordered_historical_observation_only"},"inspect-ordered-references":{"fields":[],"result":"referenced_historical_observation_only"},"leave-reference-molecular-attempt":{"fields":["preparation_id"],"result":"null"},"prepare-components":{"fields":[],"result":"component_preparation"},"prepare-reference-molecular":{"fields":[],"result":"component_preparation"},"prepare-reference-molecular-public":{"fields":["request","request_tree","registry","registry_tree","manifests","manifests_tree","request_object","registry_object","molecular_manifests_object","policy_objects"],"result":"component_preparation"},"reference-admission":{"fields":[],"result":"reference_admission"},"reference-build-result":{"fields":["kind"],"result":"reference_build"},"reference-molecular-profile":{"fields":["preparation_id"],"result":"completion_profile"},"reference-molecular-registration":{"fields":["preparation_id"],"result":"component_registration"},"reference-registration":{"fields":[],"result":"component_registration"},"register":{"fields":["contract","producer","validators","obligation_objects"],"result":"null"},"register-completion-profile":{"fields":["profile"],"result":"null"},"register-component-input":{"fields":["contract","validators","obligation_objects","obligations_object","requirements_object"],"result":"null"},"result":{"fields":["identity","scope"],"result":"pipeline_result"},"run":{"fields":["pass_id","input_id","output_id","configuration"],"result":"record"},"set-dependency":{"fields":["key","identity"],"result":"null"},"target":{"fields":[],"result":"target"}},"ordered_merge":"native_before_and_after_mapping_order_carried_as_complete_duplicate_free_ordered_trees;exact_canonical_projection_required_before_original_host_mapping_unpack;complete_expansion_precharged_to_channel_lifetime;no_host_semantics_or_acceptance_import","ordered_tree":{"array":["array","ordered_trees"],"object":["object","ordered_unique_key_tree_pairs"],"scalar":["scalar","json_scalar"]},"origin_reference":{"authority":"exact_retained_regular_authoring_objects_and_closed_stored_fields;no_dynamic_attribute_or_property_lookup;representation_only","constant_paths":"empty_only","observable_suffix":"optional_dtype_followed_by_zero_or_more_arguments_nonnegative_integer_pairs","request_paths":[["domain","inputs","nonnegative_integer","observable"],["contract","requirements","nonnegative_integer","observable"],["behavior","nodes","nonnegative_integer","source"]],"roots":["request","BOOLEAN","DURATION","LEVEL","defaultLifecycle","syntheticCapabilities"],"synthetic_capabilities":"empty_path_only;exact_unique_tuple_code_constant_of_audited_original_generate_synthetic;closed_structural_reference_only;never_execute_generator"},"profile":"biocompiler.core.pipeline_callback_manager.v1","provider_reference":{"host":["kind","object"],"native":["kind","provider_id"]},"record_bindings":["record_id","payload","dependencies","requirements","obligations","obligation_objects","checks","provenance"],"record_identity":"one_token_per_actual_native_record_physical_identity_including_rejected_and_stored_before_error_records;not_content_hash_or_import","reference_molecular_attempts":{"errors":"logical_failure_preserves_mutations;closed_cleanup_never_replaces_original_exception","notice":"actual_command_entry_scope_preserved_across_nested_callbacks","ownership":"same_actual_manager_and_channel_lifetime","provider_origins":"immutable_preparation_and_actual_provider_identity","retention":"cumulative_no_refund_all_attempts_and_historical_builds","scopes":"explicit_LIFO_prepare_and_leave"},"reference_workflow":{"build":"fresh_closed_candidate_and_check_result_views;exact_historical_public_manager_result;Molecular_construct_is_actual_second_upstream_candidate_read_or_native_default;host_return_root_conveys_no_acceptance","construct_order":["initialize-reference","reference-admission","actual_register-component-input","actual_admit-component-input","actual_get","reference-registration","actual_register","actual_run","actual_result","finish-reference-construct"],"final_source":"after_native_molecular_parse_read_actual_upstream_candidate_for_fresh_independent_check;after_check_read_again_and_retain_actual_opaque_return_root;no_unused_Build_fields_or_identity_requirement","finish":"actual_run_record_and_result_sequence;historical_result_retained;independent_native_final_checks;no_serialized_acceptance_import","host_result":"reference_producers_only;kind_host_with_actual_paired_PassResult_object_reference;no_conversion_or_acceptance","initialization":"ordered_request_registry_and_manifest_documents_with_exact_canonical_projection;actual_authored_target;one_manager_created_publication","limits":"one_shared_channel_lifetime_work_and_cumulative_retention_for_every_phase_callback_origin_and_build;native_semantic_resource_failures_remain_fatal","molecular_authority":"explicit_public_request_registry_and_outer_manifest_snapshot;retained_construct_manager_provenance_is_separate;all_native_limits_and_budget_use_actual_upstream_owner","molecular_order":["prepare-reference-molecular","six_ordered_actual_set-dependency_calls","reference-molecular-profile","actual_register-completion-profile","reference-molecular-registration","actual_register","actual_run","actual_result","finish-reference-molecular"],"owner":"one_actual_native_manager;source_ordered_public_calls;no_hidden_get_or_result","phase_authority":"actual_successful_manager_operation_objects_and_command_sequence;unrelated_generic_calls_do_not_advance;explicit_wrong_phase_or_foreign_capability_is_fatal","provider_view":{"binding":"actual_per_invocation_parsed_host_object;native_output_physical_identity;no_equal_content_or_last_call_interning","construct_origins":["parsed"],"decision_origins":[],"fields":["role","tree","origins"],"molecular_origins":["parsed","request","translation_policy","encoding_policy","evidence_policy"]},"roles":["reference_components.authority","reference_components.linkage","components_to_construct.producer","components_to_construct.layout","construct_to_molecular.producer","construct_to_molecular.sequence","construct_to_molecular.composition"],"scope":"historical_exact_reference_utilities;not_new_product_backends;no_empirical_or_complete_payload_claim","shared_provider":"reference_components.linkage_is_one_actual_closure_for_component_linkage_and_layout_composition","source_argument":"input_is_actual_context_input;argument_and_tree_are_the_complete_fresh_native_parsed_value;host_origin_binds_both_without_python_semantic_parsing","source_callback":"each_original_callpoint_performs_dynamic_host_default_lookup_after_native_parse;verified_default_runs_native_producer;replacement_runs_once_and_remains_opaque_until_deferred_manager_materialization","source_links":"expected_first_sorted_four_field_tuples;duplicates_preserved;actual_host_attribute_order_equality_and_exceptions"},"results":{"component_preparation":["preparation_id","dependencies"],"component_registration":["contract","producer","validators","obligation_objects"],"fixed_build":["kind","identity","result","artifacts","sources","view"],"initialization":["kind","manager","artifacts","target"],"native_provider_result":["kind","value","view"],"ordered_historical_observation_only":["snapshot","order","providers"],"pipeline_result":["value","artifact"],"record":["value","bindings"],"reference_admission":["contract","validators","obligation_objects"],"reference_build":["build_id","kind","candidate","check_result","result","construct"],"reference_source_result":["kind","argument","output"],"reference_upstream_candidate":{"check":["object","value","tree"],"return":["object"]},"referenced_historical_observation_only":["snapshot","order","providers","record_definitions"],"target":["value","binding"]},"schema_version":"biocompiler.pipeline_callback_manager_declaration.v1","source_links_binding":"null_for_native_context_default_or_complete_host_or_native_collection_binding;tuple_identity_and_element_identity_preserved"},"operations":{"package-build":{"fields":["request","run_metadata","runtime"],"result":"package"},"package-check-evaluate":{"fields":["check_id","name","arguments"],"result":"native_report"},"package-check-native":{"fields":["check_id"],"result":"native_report"},"package-collect":{"fields":["reference"],"result":"collection"},"package-export":{"fields":["request","construct","artifact","registry","manifests","line_width"],"result":"export"},"package-import-files":{"fields":["files"],"result":"capability"},"package-import-inputs":{"fields":["request","reference","registry"],"result":"inputs"},"package-inputs":{"fields":["alphabet"],"result":"inputs"},"package-output":{"fields":["capability"],"result":"archive_descriptor"},"package-prepare":{"fields":["inputs","line_width"],"result":"reference_build_request"},"package-reconstruct":{"fields":["archive","expected_request","expected_build_fingerprint","runtime"],"result":"package"},"package-tools-native":{"fields":["versions"],"result":"tool_pins"}},"profile":"biocompiler.core.reference_package_application.v1","reconstruction":"Core reconstruction is distinct from producer-free independently authorized Verify.","rejections":{"cause_utf8_bytes_hex":"lowercase_hex_of_bounded_native_request_member;host_recreates_only_actual_utf8_decode_failure","ordinary":["module","type","message","attributes","attributes_tree"],"request_utf8":["module","type","message","attributes","attributes_tree","cause_utf8_bytes_hex"]},"results":{"archive_descriptor":["bytes","sha256"],"capability":["capability"],"collection":["capability","files"],"completed_sequence":["sequence"],"export":["capability","value"],"export_report_observation":["passed","diagnostics"],"inputs":["capability","request","reference","registry"],"molecular_build_capability":["build_id"],"native_or_host":["kind","value"],"package":["capability","request","manifest","archive","build_fingerprint"],"reference_build_request":"biocompiler.reference_build_request.v0.1"},"retention":"512 MiB lifetime retained ownership; separate unchanged bounded transient checker profiles.","runtime_ownership":"first_build_or_reconstruct_selects_runtime;unchanged_for_entire_owner","runtime_profiles":["python311","python314"],"schema_version":"biocompiler.reference_package_application_declaration.v1"}|application}
type loaded={prepared:Inputs.t}
type pending_check={identity:string;name:string;native:unit->Json.t;mutable invocation:int option;mutable used:bool}
type state={files:Pio.t;mutable owner:B.t option;mutable serial:int;
  mutable loaded:(string*loaded)list;mutable collected:(string*(string*string)list)list;
  mutable exports:(string*Export.checked)list;mutable packages:(string*S.t)list;
  mutable check:pending_check option;mutable runtime:Bioc_artifact.Stored_zip.diagnostic_profile option}
let budget state channel=match Ch.package_budget channel with
  |None->protocol"Package operation requires a negotiated package owner."
  |Some owner->(match state.owner with
    |None->Pio.bind_owner state.files owner;state.owner<-Some owner
    |Some previous->require(previous==owner)"Package operation changed its resource owner.");owner
let runtime state raw=
  let value=match text raw with
    |"python311"->Bioc_artifact.Stored_zip.Python311
    |"python314"->Bioc_artifact.Stored_zip.Python314
    |_->protocol"Unsupported reference package Python runtime profile." in
  (match state.runtime with None->state.runtime<-Some value
   |Some previous->require(previous=value)"Package operation changed its Python runtime profile.");value
let token state budget prefix=
  B.charge budget 1;B.reserve budget 192;
  require(state.serial<max_int)"Package capability counter overflow.";
  let value=prefix^"/"^string_of_int state.serial in state.serial<-state.serial+1;value
let find budget key values=
  let rec loop=function []->protocol"Unknown package lifetime capability."|(name,value)::rest->
    B.charge budget(String.length key+String.length name+1);if name=key then value else loop rest in loop values
let invoke channel budget action arguments=
  B.guard budget;let result=Ch.invoke channel ~action ~arguments in B.guard budget;result
let capability raw=let data=fields["capability"]raw in text(at"capability"data)
let reply_capability identity=Json.Object["capability",str identity]
let package_json budget identity package=
  own_json budget(Json.Object["capability",str identity;"request",D.Request.to_json(S.request package);
    "manifest",D.Manifest.to_json(S.manifest package);"archive",Json.Object[
      "bytes",Json.int(String.length(S.data package));"sha256",str(S.archive_sha256 package)];
    "build_fingerprint",str(S.build_fingerprint package)])
let remember_package state budget package=
  require(S.owner package==budget)"Package result belongs to another resource owner.";
  let rec existing=function
    |[]->None
    |(identity,actual)::rest->B.charge budget 1;if actual==package then Some identity else existing rest in
  let identity=match existing state.packages with
    |Some identity->identity
    |None->let identity=token state budget "package" in state.packages<-(identity,package)::state.packages;identity in
  package_json budget identity package
let callbacks state manager channel budget=
  let run ~request ~registry ~manifests=
    let raw=invoke channel budget "package-run"(Json.Object[
      "request",Reference_construct.Request.to_json request;"registry",Component_registry.to_json registry;
      "manifests",manifests_json manifests]) in
    let data=fields["build_id"]raw in
    CM.molecular_build_capability manager ~channel ~build_id:(text(at"build_id"data)) in
  let construct build=
    let raw=invoke channel budget "package-construct"(Json.Object[
      "artifact",Reference_molecular.Artifact.to_json(V.candidate build)]) in
    Reference_construct.Candidate.of_json ~limits:(codec budget)raw in
  let export ~request ~construct ~artifact ~registry ~manifests ~line_width=
    let raw=invoke channel budget "package-export"(Json.Object[
      "request",Reference_construct.Request.to_json request;"construct",Reference_construct.Candidate.to_json construct;
      "artifact",Reference_molecular.Artifact.to_json artifact;"registry",Component_registry.to_json registry;
      "manifests",manifests_json manifests;"line_width",Json.int line_width]) in
    let data=fields["kind";"value"]raw in match text(at"kind"data) with
    |"native"->find budget(capability(at"value"data))state.exports
    |"host"->
      let claimed=X.of_json budget(at"value"data) in
      let actual=Export.export_checked_owned budget ~request ~construct ~artifact ~registry ~manifests ~line_width() in
      Diagnostic.require(equal budget(codec_json budget claimed)(codec_json budget(Export.checked_bundle actual)))
        "reference_package" "Host sequence export differs from the fresh independent native export.";actual
    |_->protocol"Unknown package export response kind." in
  S.{load=(fun _ _->protocol"Package source load requires its actual prepared capability.");
    collect=(fun _ _->protocol"Package collection requires its actual returned mapping.");
    run=(fun _->run);construct=(fun _->construct);export=(fun _->export);
    package_version=(fun()->text(invoke channel budget "package-version" Json.Null));
    tool_versions=(fun()->let raw=invoke channel budget "package-tools" Json.Null in
      ignore(Codec.measure ~limits:(limits budget)raw);
      List.map(function Json.Array[Json.String key;Json.String value]->key,value|_->protocol"Package tool version shape differs.")(Json.array raw))}
let observe_check state channel budget name arguments native=
  let previous=state.check in
  let pending={identity=token state budget "check";name;native;invocation=None;used=false} in
  state.check<-Some pending;
  let response=Fun.protect ~finally:(fun()->state.check<-previous)(fun()->
    let _,value=Ch.invoke_bound ~on_open:(fun id->pending.invocation<-Some id) channel
      ~action:"package-check" ~arguments:(Json.Object["name",str name;"arguments",arguments;"check_id",str pending.identity]) in value) in
  let data=fields["kind";"value"]response in
  let reference=match text(at"kind"data) with
    |"native"->require(at"value"data=Json.Null)"Native checker request carries a host result.";
      invoke channel budget "package-check-value"(Json.Object["name",str name;"value",native()])
    |"host"->at"value"data|_->protocol"Unknown package checker response kind." in
  own_json budget reference
let hooks state manager channel budget=
  let check name arguments native=
    let reference=observe_check state channel budget name arguments(fun()->S.native_report_document budget(native())) in
    S.observed_report budget
      ~passed:(fun _->Json.boolean(invoke channel budget "package-report-passed" reference))
      ~document:(fun _->invoke channel budget "package-report-document" reference) in
  S.{get=(fun _ build ~identity->
      B.guard budget;let invocation,raw=Ch.invoke_bound channel ~action:"package-get" ~arguments:(Json.Object["identity",str identity]) in
      let data=fields["sequence"]raw in
      CM.get_return_capability manager ~channel ~manager:(V.manager build) ~sequence:(natural(at"sequence"data)) ~invocation ~identity);
    result=(fun _ build ~identity ~scope->
      B.guard budget;let invocation,raw=Ch.invoke_bound channel ~action:"package-result" ~arguments:(Json.Object["identity",str identity;"scope",str scope]) in
      let data=fields["sequence"]raw in
      CM.result_return_capability manager ~channel ~manager:(V.manager build) ~sequence:(natural(at"sequence"data)) ~invocation ~identity ~scope);
    composition=(fun _ ~native ~request ~registry->check "composition"(Json.Object[
      "request",Composition.to_json request;"registry",Component_registry.to_json registry])native);
    construct_check=(fun _ ~native ~request ~construct ~registry ~manifests->check "construct"(Json.Object[
      "request",Reference_construct.Request.to_json request;"construct",Reference_construct.Candidate.to_json construct;
      "registry",Component_registry.to_json registry;"manifests",manifests_json manifests])native);
    molecular_check=(fun _ ~native _build->check "molecular" Json.Null native)}
let dispatch_value state manager channel command=
  if not(List.mem command.Ch.operation operation_names)then None else
  let budget=budget state channel in
  let raw=command.arguments in ignore(Codec.measure ~limits:(limits budget)raw);
  let result=match command.operation with
  |"package-check-native"->
    let data=fields["check_id"]raw in
    let pending=match state.check with Some value->value|None->protocol"No native checker callpoint is active." in
    require(pending.identity=text(at"check_id"data) && not pending.used &&
      pending.invocation=command.parent_invocation && pending.invocation<>None)
      "Native checker capability is stale, repeated or belongs to another invocation.";
    pending.used<-true;pending.native()
  |"package-check-evaluate"->
    let data=fields["check_id";"name";"arguments"]raw in
    let pending=match state.check with Some value->value|None->protocol"No native checker callpoint is active." in
    let name=text(at"name"data) in
    require(pending.identity=text(at"check_id"data) && pending.invocation=command.parent_invocation && pending.invocation<>None &&
      (pending.name=name || (pending.name="export-molecular" && name="molecular")))
      "Native checker evaluation belongs to another callpoint or invocation.";
    let arguments=at"arguments"data in
    let report=match name with
    |"composition"->
      let values=fields["request";"registry"]arguments in
      let request=imported budget (fun raw->Composition.of_json raw)(at"request"values) in
      let registry=imported budget (fun raw->Component_registry.of_json raw)(at"registry"values) in
      Composition_evidence.Result.to_json(Bioc_checker.Composition_check.check ~parent:(B.work budget) ~request ~registry())
    |"construct"->
      let values=fields["request";"construct";"registry";"manifests"]arguments in
      let request=Reference_construct.Request.of_json ~limits:(codec budget)(at"request"values) in
      let candidate=Reference_construct.Candidate.of_json ~limits:(codec budget)(at"construct"values) in
      let registry=imported budget (fun raw->Component_registry.of_json raw)(at"registry"values) in
      let manifests=manifests budget(at"manifests"values) in
      Reference_construct_evidence.Result.to_json(Bioc_checker.Reference_construct_check.check
        ~parent:(B.work budget) ~request ~candidate ~registry ~manifests())
    |"molecular"->
      let values=fields["request";"construct";"candidate";"registry";"manifests"]arguments in
      let request=Reference_construct.Request.of_json ~limits:(codec budget)(at"request"values) in
      let construct=Reference_construct.Candidate.of_json ~limits:(codec budget)(at"construct"values) in
      let candidate=Reference_molecular.Artifact.of_json ~limits:(codec budget)(at"candidate"values) in
      let registry=imported budget (fun raw->Component_registry.of_json raw)(at"registry"values) in
      let manifests=manifests budget(at"manifests"values) in
      Reference_molecular_evidence.Result.to_json(Bioc_checker.Reference_molecular_check.check
        ~parent:(B.work budget) ~request ~construct ~candidate ~registry ~manifests())
    |_->protocol"Native checker evaluation uses an unknown checker name." in
    own_json budget report
  |"package-inputs"->
    let data=fields["alphabet"]raw in let alphabet=alphabet(text(at"alphabet"data)) in
    let read kind path=unhex budget(invoke channel budget "package-read"(Json.Object["kind",str kind;"path",str path])) in
    let snapshot=I.load_snapshot budget ~reader:I.{manifest_first=(fun()->read "manifest-first" "manifest.json");
      retained_first=read "retained-first";manifest_second=(fun()->read "manifest-second" "manifest.json");
      source_second=read "source-second";review_second=read "review-second"} in
    let prepared=Inputs.prepare budget ~alphabet snapshot in
    let identity=token state budget "inputs" in state.loaded<-(identity,{prepared})::state.loaded;
    own_json budget(Json.Object["capability",str identity;"request",Reference_construct.Request.to_json(Inputs.request prepared);
      "reference",Reference_manifest.to_json(Inputs.reference prepared);"registry",Component_registry.to_json(Inputs.registry prepared)])
  |"package-collect"->
    let data=fields["reference"]raw in
    let reference=Reference_manifest.of_json ~limits:(codec budget)(at"reference"data) in
    let read kind path=unhex budget(invoke channel budget "package-read"(Json.Object["kind",str kind;"path",str path])) in
    let snapshot=I.load_snapshot budget ~reader:I.{manifest_first=(fun()->read "manifest-first" "manifest.json");
      retained_first=read "retained-first";manifest_second=(fun()->read "manifest-second" "manifest.json");
      source_second=read "source-second";review_second=read "review-second"} in
    Diagnostic.require(Reference_manifest.fingerprint reference=Reference_manifest.fingerprint(I.manifest snapshot))
      "reference_inputs" "Supplied manifest differs from the current pinned offline reference snapshot.";
    let identity=token state budget "snapshot" in state.collected<-(identity,I.files snapshot)::state.collected;
    own_json budget(Json.Object["capability",str identity;"files",member_json budget(I.files snapshot)])
  |"package-import-inputs"->
    let data=fields["request";"reference";"registry"]raw in
    let request=Reference_construct.Request.of_json ~limits:(codec budget)(at"request"data) in
    let reference=Reference_manifest.of_json ~limits:(codec budget)(at"reference"data) in
    let registry=imported budget (fun raw->Component_registry.of_json raw)(at"registry"data) in
    let prepared=Inputs.supplied budget ~request ~reference ~registry in
    let identity=token state budget "inputs" in state.loaded<-(identity,{prepared})::state.loaded;
    own_json budget(Json.Object["capability",str identity;"request",Reference_construct.Request.to_json request;
      "reference",Reference_manifest.to_json reference;"registry",Component_registry.to_json registry])
  |"package-import-files"->
    let data=fields["files"]raw in
    let entries=Json.array(at"files"data) in
    require(List.length entries<=(B.limits budget).max_entries)"Collected package files exceed their entry bound.";
    B.reserve budget(128*List.length entries+128);
    let total=ref 0 and seen=ref [] in
    let files=List.map(function Json.Array[Json.String path;encoded]->
      B.charge budget(String.length path+List.length !seen+1);
      require(not(List.mem path !seen))"Collected package files repeat a mapping key.";
      seen:=path::!seen;
      let bytes=unhex budget encoded in
      require(String.length bytes<=(B.limits budget).max_archive_bytes- !total)"Collected package files exceed their byte bound.";
      total:= !total+String.length bytes;path,bytes
      |_->protocol"Collected package files require ordered path/hex pairs.")entries in
    let identity=token state budget "files" in state.collected<-(identity,files)::state.collected;
    reply_capability identity
  |"package-tools-native"->
    let data=fields["versions"]raw in
    let versions=List.map(function Json.Array[Json.String id;Json.String version]->id,version
      |_->protocol"Tool versions require ordered string pairs.")(Json.array(at"versions"data)) in
    own_json budget(Json.Array(List.map D.Tool.to_json(S.tool_pins budget versions)))
  |"package-prepare"->
    let data=fields["inputs";"line_width"]raw in let value=find budget(text(at"inputs"data))state.loaded in
    let width=X.line_width_of_json budget(at"line_width"data) in
    D.Request.to_json(D.Request.make budget ~construct:(Inputs.request value.prepared) ~fasta_line_width:width())
  |"package-export"->
    let data=fields["request";"construct";"artifact";"registry";"manifests";"line_width"]raw in
    let request=Reference_construct.Request.of_json ~limits:(codec budget)(at"request"data) in
    let construct=Reference_construct.Candidate.of_json ~limits:(codec budget)(at"construct"data) in
    let artifact=Reference_molecular.Artifact.of_json ~limits:(codec budget)(at"artifact"data) in
    let registry=imported budget (fun raw->Component_registry.of_json raw)(at"registry"data) in
    let manifests=manifests budget(at"manifests"data) in let line_width=X.line_width_of_json budget(at"line_width"data) in
    let observe_check ~native=
      let reference=observe_check state channel budget "export-molecular" raw
        (fun()->own_json budget(Reference_molecular_evidence.Result.to_json(native()))) in
      let observed=fields["passed";"diagnostics"](invoke channel budget "package-report-export" reference) in
      let passed=Json.boolean(at"passed"observed) in
      let codes=List.map text(Json.array(at"diagnostics"observed)) in
      Diagnostic.require passed "reference_sequence_export"
        ("Sequence export requires a currently passing independent molecular check: "^String.concat "; " codes) in
    let value=Export.export_checked_owned ~observe_check budget ~request ~construct ~artifact ~registry ~manifests ~line_width() in
    let identity=token state budget "export" in state.exports<-(identity,value)::state.exports;
    own_json budget(Json.Object["capability",str identity;"value",codec_json budget(Export.checked_bundle value)])
  |"package-build"->
    let data=fields["request";"run_metadata";"runtime"]raw in
    let runtime=runtime state(at"runtime"data) in
    let request=D.Request.of_json budget(at"request"data) in
    let metadata=optional(D.Run_metadata.of_json ~runtime budget)(at"run_metadata"data) in
    let load_prepared owner alphabet=
      let response=invoke channel owner "package-load"(Json.Object["alphabet",str(Reference_manifest.alphabet_name alphabet)]) in
      (find owner(capability response)state.loaded).prepared in
    let collect_files owner reference=
      let response=invoke channel owner "package-collect"(Reference_manifest.to_json reference) in
      find owner(capability response)state.collected in
    let tool_pins owner=List.map(D.Tool.of_json owner)(Json.array(invoke channel owner "package-tools" Json.Null)) in
    let built=S.build budget ~callbacks:(callbacks state manager channel budget) ~hooks:(hooks state manager channel budget)
      ~load_prepared ~collect_files ~tool_pins ~request ?run_metadata:metadata() in remember_package state budget built
  |"package-reconstruct"->
    let data=fields["archive";"expected_request";"expected_build_fingerprint";"runtime"]raw in
    let runtime=runtime state(at"runtime"data) in
    let expected_request=optional(D.Request.of_json budget)(at"expected_request"data) in
    let expected_build_fingerprint=optional text(at"expected_build_fingerprint"data) in
    let descriptor=Pio.descriptor_of_json ~max_bytes:(B.limits budget).max_archive_bytes(at"archive"data) in
    let bytes=Pio.read_archive state.files budget descriptor in
    let built=Rebuild.verify_with_builder ~runtime budget
      ~invalid_utf8:(fun bytes->let encoded=hex budget bytes in B.reserve budget 64;raise(Invalid_request_utf8 encoded))
      ?expected_request ?expected_build_fingerprint bytes
      ~builder:(fun owner ~request ~files ~run_metadata->
        let result=invoke channel owner "package-rebuild"(Json.Object["request",D.Request.to_json request;
          "files",member_json owner files;"run_metadata",(match run_metadata with None->Json.Null|Some value->D.Run_metadata.to_json value)]) in
        find owner(capability result)state.packages) in
    remember_package state budget built
  |"package-output"->
    let data=fields["capability"]raw in let package=find budget(text(at"capability"data))state.packages in
    Pio.descriptor_to_json(Pio.write_archive state.files budget(S.data package))
  |_->assert false in Some(Ch.Success result)
let expected_codes=["reference_package";"reference_package_manifest";"reference_package_container";
  "reference_sequence_export";"reference_inputs";"reference_input_missing";"archive_container";
  "reference_construct";"reference_manifest";"reference_molecular";"component_registry";
  "legacy_artifact_json";"legacy_reference_json"]
let dispatch state manager channel command=
  try dispatch_value state manager channel command with
  |Invalid_request_utf8 encoded->
    let owner=budget state channel in
    Some(Ch.Rejected(own_json owner(Json.Object["module",str"biocompiler.errors";"type",str"SerializationError";
      "message",str"Packaged request must be UTF-8 JSON.";"attributes",Json.Object[];
      "attributes_tree",Json.Array[str"object";Json.Array[]];"cause_utf8_bytes_hex",str encoded])))
  |Diagnostic.Error diagnostic when List.mem diagnostic.code expected_codes->
    let owner=budget state channel in
    Some(Ch.Rejected(own_json owner(Json.Object["module",str"biocompiler.errors";"type",str"SerializationError";
      "message",str diagnostic.message;"attributes",Json.Object[];
      "attributes_tree",Json.Array[str"object";Json.Array[]]])))
let create ~io ~files()=
  let state={files;owner=None;serial=0;loaded=[];collected=[];exports=[];packages=[];check=None;runtime=None} in
  CM.create_package ~io ~application:declaration ~extension:(dispatch state)()

let run ~input ~output=
  set_binary_mode_in stdin true;set_binary_mode_out stdout true;
  Pio.with_fds ~input ~output(fun files->
    let read_header()=
      let buffer=Bytes.create 9 in
      let rec read offset=
        if offset=9 then Some(Bytes.to_string buffer) else
        match Stdlib.input stdin buffer offset(9-offset) with
        |0 when offset=0->None|0->Some(Bytes.sub_string buffer 0 offset)|count->read(offset+count) in
      read 0 in
    let io:Ch.io={read_header;read_body=(fun size->really_input_string stdin size);
      write=(fun frame->output_string stdout frame;flush stdout)} in
    CM.run(create ~io ~files()))
