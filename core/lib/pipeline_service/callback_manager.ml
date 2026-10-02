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
let declaration=Json.parse {declaration|{"acceptance":"native_manager_checks_and_freshness_only;inspection_and_host_sidecars_cannot_import_accepted_records","actions":{"hydrate-context":{"fields":["context_id","document","bindings"],"result":"object_reference"},"native-provider":{"fields":["provider_id","role"],"result":"object_reference"},"ordered-json":{"fields":["object"],"result":"ordered_tree"},"origin-reference":{"fields":["root","path"],"result":"object_reference"},"provider-reference":{"fields":["object"],"result":"host_or_native_provider_reference"},"set-equal":{"fields":["object","values"],"result":"boolean"},"source-link-set-equal":{"fields":["objects","expected"],"result":"boolean"}},"argument":"--pipeline-callback-session-v1","authoring_boundary":"canonical_typed_contract_target_profile_fields;opaque_payload_configuration_provider_and_validator_objects_are_read_at_native_requested_points","bindings":{"host":["kind","object"],"native":["kind","identity","tree"]},"broker_actions":{"attr":{"fields":["object","name"],"result":"object_reference"},"attr-default":{"fields":["object","name","default"],"result":"object_reference"},"bind-provider":{"fields":["provider_id","object"],"result":"null"},"call":{"fields":["callable","args","kwargs"],"result":"object_reference"},"call-provider":{"fields":["provider_id","context"],"result":"object_reference"},"callable":{"fields":["object"],"result":"boolean"},"compare":{"fields":["left","right","operator"],"result":"boolean"},"contains":{"fields":["container","item"],"result":"boolean"},"dict":{"fields":["object"],"result":"object_reference"},"document":{"fields":["object"],"result":"object_reference"},"enum":{"fields":["type","value"],"result":"object_reference"},"freeze-json":{"fields":["object"],"result":"object_reference"},"get-item":{"fields":["object","key"],"result":"object_reference"},"is-instance":{"fields":["object","type"],"result":"boolean"},"is-none":{"fields":["object"],"result":"boolean"},"iter":{"fields":["object"],"result":"object_reference"},"json":{"fields":["object"],"result":"json"},"len":{"fields":["object"],"result":"integer"},"list":{"fields":["object"],"result":"object_reference"},"literal":{"fields":["kind","value"],"result":"object_reference"},"lookup":{"fields":["object","entries"],"result":"object_reference"},"mapping-items":{"fields":["object"],"result":"object_reference"},"mapping-keys":{"fields":["object"],"result":"object_reference"},"mapping-values":{"fields":["object"],"result":"object_reference"},"merge":{"fields":["object","before","after"],"result":"object_reference"},"next":{"fields":["object"],"result":"iterator_step"},"release":{"fields":["handles"],"result":"null"},"set-attribute-equal":{"fields":["objects","name","values"],"result":"boolean"},"truth":{"fields":["object"],"result":"boolean"},"tuple":{"fields":["object"],"result":"object_reference"},"vars":{"fields":["object"],"result":"object_reference"}},"channel":"biocompiler.pipeline_callback_channel.v1","claim_scope":"software_contract_conditional_translation_and_scoped_completion;no_empirical_or_human_use_acceptance","comparison_operators":["eq","ne","is","is-not"],"compatibility_pending":["complete_original_installed_replay","fixed_public_registration_interception","arbitrary_authoring_subclass_and_scalar_operator_semantics","default_cutover"],"context_bindings":["input","output","target","configuration","dependencies","requirements","source_links","observation_map"],"context_identity":"actual_native_context_physical_identity;distinct_producer_and_validation_contexts;one_validation_context_shared_by_its_validators","dependencies_encoding":"ordered_unique_string_identity_pairs","enum_types":["EvidenceKind","CheckOutcome","Stage","ArtifactStatus","PayloadFormat"],"executable":"core","expected_rejection_attributes":"fresh_ordered_tree_with_exact_canonical_attributes_projection;no_cached_binding_or_context_container_reuse;NoCandidateFound_retains_pass_configuration_and_dependency_order","expected_rejection_fields":["module","type","message","attributes","attributes_tree"],"failure":"expected_logical_rejection_and_opaque_host_exception_preserve_actual_partial_manager;malformed_resource_internal_or_uncertain_io_failure_closes_authority","fixed_request_tree":"ordered_tree_from_same_authoring_serialization_as_request;exact_canonical_projection_required_before_native_import;retained_order_is_not_acceptance","host_execution":"trusted_host_code_cpu_and_opaque_captures_outside_native_work_and_json_memory_bounds","inspection_order":{"combined_provider_history":"actual_successful_insertion_order;pass_fingerprint_string_or_component_input_tag_and_fingerprint_pair;replacements_preserve_position","fields":["dependencies","passes","component_inputs","provider_history","component_input_history","records","profiles","combined_provider_history","validators"],"mapping_order":"unique_complete_snapshot_key_arrays","provider_fields":["provider_id","object"],"providers":"exact_reachable_snapshot_provider_token_census;stable_bijection_to_actual_retained_callable_identity;no_user_equality_or_hash","scope":"manager_mapping_and_validator_order_only;nested_unobserved_json_order_not_generalized;historical_observation_cannot_grant_acceptance","validator_maps":["passes","component_inputs","provider_history","component_input_history"],"validators":"four_exact_registration_maps_of_unique_complete_validator_key_arrays"},"iterator_step_fields":["exhausted","object"],"lifecycle":"one_initialization_attempt_per_channel;existing_channel_close_is_top_level_only;no_reconnect_retry_or_state_import","limits":"all_native_framing_application_import_callback_and_publication_work_uses_one_channel_lifetime_ancestor;retention_is_cumulative_no_refund","literal_kinds":["json","tuple","set"],"manager_limits":"initialization_once;null_defaults_or_complete_positive_integer_reductions","native_provider_context":"only_exact_retained_context_from_this_live_manager;no_external_context_import","native_provider_result_kinds":["proposal","decision","invalid"],"native_provider_view":{"alias_fields":["kind","paths","binding"],"alias_kinds":["biocompiler.ir.intent.SourceLocation","biocompiler.semantics.types.TypeSpec","biocompiler.semantics.realization.Observable","biocompiler.semantics.component_contracts.OperatingDomain","biocompiler.semantics.component_contracts.ValueDomain","biocompiler.ir.component_contracts.PinnedIdentity","biocompiler.ir.components.ComponentLock","biocompiler.ir.composition.LifecycleInterval"],"alias_paths":"unique_closed_typed_field_and_nonnegative_array_index_paths_relative_to_complete_value;exact_class_and_shape;slot_overlap_requires_identical_binding","bindings_by_role":{"behavior_to_synthetic.producer":["generator_config"],"behavior_to_synthetic.validator":[],"intent_to_behavior.producer":[],"intent_to_behavior.validator":[],"synthetic_to_components.producer":["registry","composition","composition_target"],"synthetic_to_components.validator":[]},"fields":["role","tree","bindings","aliases"],"identity":"explicit_actual_host_objects_or_retained_native_constructor_origins;strong_lifetime_retention;never_equal_content_interning;charged_to_channel_limits","invalid":"view_is_null_only_for_invalid_result","role_authority":"actual_fixed_native_closure_and_manager_owner;immutable_provider_registration_binding","roles":["intent_to_behavior.producer","intent_to_behavior.validator","behavior_to_synthetic.producer","behavior_to_synthetic.validator","synthetic_to_components.producer","synthetic_to_components.validator"],"scope":"closed_structural_public_views_only;no_semantic_parsers_or_acceptance;fresh_proposal_and_output_roots","tree":"complete_value_ordered_tree;canonical_projection_matches_value"},"object_reference":{"fields":["handle"],"scope":"one_live_trusted_host_broker_physical_identity"},"obligation_objects":"array_of_actual_host_references_matching_canonical_obligation_slots;whole_tuple_sidecar_preserves_add_input_and_admission_collection_identity;run_allocates_a_new_tuple_reusing_elements;sidecars_do_not_grant_acceptance","operations":{"add-input":{"fields":["identity","stage","requirements","obligations","obligation_objects","payload","obligations_object"],"result":"record"},"admit-component-input":{"fields":["contract_id","identity","payload"],"result":"record"},"artifact":{"fields":["name"],"result":"canonical_immutable_build_artifact"},"call-native-provider":{"fields":["provider_id","context_id"],"result":"native_provider_result"},"get":{"fields":["identity"],"result":"record"},"initialize-components":{"fields":["request","request_tree","history","until","config","manager_limits","target_object","request_object","config_object"],"result":"initialization"},"initialize-empty":{"fields":["target","dependencies","completion_profiles","manager_limits","target_object"],"result":"initialization"},"initialize-synthetic":{"fields":["request","request_tree","history","until","config","manager_limits","target_object","request_object","config_object"],"result":"initialization"},"inspect":{"fields":[],"result":"historical_observation_only"},"inspect-ordered":{"fields":[],"result":"ordered_historical_observation_only"},"register":{"fields":["contract","producer","validators","obligation_objects"],"result":"null"},"register-completion-profile":{"fields":["profile"],"result":"null"},"register-component-input":{"fields":["contract","validators","obligation_objects","obligations_object","requirements_object"],"result":"null"},"result":{"fields":["identity","scope"],"result":"pipeline_result"},"run":{"fields":["pass_id","input_id","output_id","configuration"],"result":"record"},"set-dependency":{"fields":["key","identity"],"result":"null"},"target":{"fields":[],"result":"target"}},"ordered_tree":{"array":["array","ordered_trees"],"object":["object","ordered_unique_key_tree_pairs"],"scalar":["scalar","json_scalar"]},"origin_reference":{"authority":"exact_retained_regular_authoring_objects_and_closed_stored_fields;no_dynamic_attribute_or_property_lookup;representation_only","constant_paths":"empty_only","observable_suffix":"optional_dtype_followed_by_zero_or_more_arguments_nonnegative_integer_pairs","request_paths":[["domain","inputs","nonnegative_integer","observable"],["contract","requirements","nonnegative_integer","observable"],["behavior","nodes","nonnegative_integer","source"]],"roots":["request","BOOLEAN","DURATION","LEVEL","defaultLifecycle"]},"profile":"biocompiler.core.pipeline_callback_manager.v1","provider_reference":{"host":["kind","object"],"native":["kind","provider_id"]},"record_bindings":["record_id","payload","dependencies","requirements","obligations","obligation_objects","checks","provenance"],"record_identity":"one_token_per_actual_native_record_physical_identity_including_rejected_and_stored_before_error_records;not_content_hash_or_import","results":{"initialization":["kind","manager","artifacts","target"],"native_provider_result":["kind","value","view"],"ordered_historical_observation_only":["snapshot","order","providers"],"pipeline_result":["value","artifact"],"record":["value","bindings"],"target":["value","binding"]},"schema_version":"biocompiler.pipeline_callback_manager_declaration.v1","source_links_binding":"null_for_native_context_default_or_complete_host_or_native_collection_binding;tuple_identity_and_element_identity_preserved"}|declaration}
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
type provider_view={provider:M.provider;provider_id:string;host:Json.t option;
  mutable proxy:Json.t option;mutable fixed:fixed_provider option}
type t={mutable channel:Ch.t option;mutable bridge:H.t option;mutable initialized:bool;
  mutable live:M.t option;mutable manager_limits:M.limits;mutable manager_json:Json.t;
  mutable target_binding:Json.t option;mutable artifacts:(string*Json.t) list;
  mutable requested_config:(Json.t*Json.t) option;
  mutable fixed_request:Json.t option;mutable origins:(string*Json.t) list;
  mutable providers:provider_view list;mutable contexts:context_view list;
  mutable records:record_view list;mutable bindings:(Json.t*Json.t) list;
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
      let value={provider;provider_id=identity state "provider";host=None;proxy=None;fixed=None} in
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
  require(entry.host=None && entry.fixed=None && entry.proxy=None) "Fixed provider metadata was rebound.";
  let candidate=match role with S.Synthetic_to_components_producer value->
    let size=Synthetic_authority.Candidate.canonical_size value.candidate in
    W.charge(work state)(128*(size+1));Ch.retain_bytes(channel state)(8*size+256);
    Some(Synthetic_authority.Candidate.to_json value.candidate)
    | _->None in
  entry.fixed<-Some {owner;role;candidate;view_bindings=[]}
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
        obj["generator_config",actual]
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
  | None,None->let role=role_name(fixed_provider entry).role in
      let value=invoke state "native-provider" (obj["provider_id",str entry.provider_id;"role",str role]) in
      ignore(host state value);retain state value;entry.proxy<-Some value;value
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
           let entry={provider;provider_id;host=Some raw;proxy=None;fixed=None} in
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
    map state(fun value->retain state(Execution_data.Input_frame.to_json value)) frames |> ignore;
    retain_fixed state(kind="components") request config until;
    let artifact name raw=retain state raw;state.artifacts<-state.artifacts@[name,raw] in
    let selection=function None->Json.Null | Some value->Synthetic_selection.Result.to_json value in
    if kind="synthetic" then match S.attempt ~budget ~manager_limits:state.manager_limits
      ~observer ~provider_observer ~validator_equivalent ?until ?config request frames with
      | S.Failed failure->state.live<-failure.manager;raise failure.error
      | S.Completed value->state.live<-Some(S.manager value);
          artifact "candidate"(Synthetic_authority.Candidate.to_json(S.candidate value));
          artifact "pipeline_result"(C.Pipeline_result.to_json(S.result value));
          artifact "selection_result"(selection(S.selection_result value))
    else match P.attempt ~budget ~manager_limits:state.manager_limits
      ~observer ~provider_observer ~validator_equivalent ?until ?config request frames with
      | P.Failed failure->state.live<-failure.manager;raise failure.error
      | P.Completed value->state.live<-Some(P.manager value);
          artifact "candidate"(Synthetic_authority.Candidate.to_json(P.candidate value));
          artifact "pipeline_result"(C.Pipeline_result.to_json(P.result value));
          artifact "selection_result"(selection(P.selection_result value));
          artifact "assembly"(Component_assembly.to_json(P.assembly value));
          artifact "link_result"(Composition_evidence.Result.to_json(P.link_result value));
          artifact "behavior_result"(Realization_evidence.Check_result.to_json(P.behavior_result value)));
  obj["kind",str kind;"manager",Json.Bool true;"artifacts",strings(List.map fst state.artifacts);
    "target",target_envelope state]
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
let dispatch_value (state:t) operation payload=
  let declared=try get operation(get "operations" declaration) with Diagnostic.Error _->fail "Unknown manager operation." in
  Json.exact_fields(List.map Json.string(Json.array(get "fields" declared)))(Json.object_fields payload);
  let field key=get key payload and name key=text key payload in
  match operation with
  | "initialize-empty"->initialize state "empty" payload
  | "initialize-synthetic"->initialize state "synthetic" payload
  | "initialize-components"->initialize state "components" payload
  | "target"->target_envelope state
  | "inspect"->inspect state
  | "inspect-ordered"->inspect_ordered state
  | "get"->record_envelope state(M.get(live state)(name "identity"))
  | "result"->let manager=live state in
      let value=M.result manager ~identity:(name "identity") ~scope:(name "scope") in
      obj["value",C.Pipeline_result.to_json value;
        "artifact",record_envelope state(M.get manager(name "identity"))]
  | "set-dependency"->M.set_dependency(live state)(name "key")(name "identity");Json.Null
  | "register-completion-profile"->let manager=live state in
      let profile=C.Completion_profile.of_json ~limits:(manager_codec state)(field "profile") in
      M.register_completion_profile manager profile;Json.Null
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
  | "admit-component-input"->record_envelope state(M.admit_host_component_input(live state)
      ~contract_id:(name "contract_id") ~identity:(name "identity")(host state(field "payload")))
  | "run"->let configuration=match field "configuration" with Json.Null->None | raw->Some(host state raw) in
      record_envelope state(M.run_host(live state) ~pass_id:(name "pass_id") ~input_id:(name "input_id")
        ~output_id:(name "output_id") ?configuration ())
  | "register"->let manager=live state in
      let contract=C.Pass_contract.of_json ~limits:(manager_codec state)(field "contract") in
      let sidecar=authored_sidecar state(C.Pass_contract.introduces contract) payload ~whole:false ~requirements:false in
      let producer=field "producer" and validators=field "validators" in
      let deferred=deferred_validators state ~producer validators in
      M.register_deferred manager contract ~producer:(fun _->intern_provider state producer)
        ~self_certifying:(self_certifying state producer validators) deferred;
      retain state(field "contract");state.pass_sidecars<-(contract,sidecar)::state.pass_sidecars;Json.Null
  | "register-component-input"->let manager=live state in
      let contract=C.Component_input_contract.of_json ~limits:(manager_codec state)(field "contract") in
      let sidecar=authored_sidecar state(C.Component_input_contract.obligations contract) payload ~whole:true ~requirements:true in
      M.register_component_input_deferred manager contract(deferred_validators state(field "validators"));
      retain state(field "contract");state.admission_sidecars<-(contract,sidecar)::state.admission_sidecars;Json.Null
  | "artifact"->(match List.assoc_opt(name "name") state.artifacts with
      | Some value->value | None->fail "No such completed build artifact.")
  | "call-native-provider"->
      let provider=match find state(fun value->value.provider_id=name "provider_id" && value.host=None) state.providers with
        | Some value->value | None->fail "Unknown native provider capability." in
      require((fixed_provider provider).owner==live state) "Fixed provider belongs to another manager incarnation.";
      let context=match find state(fun value->value.context_id=name "context_id") state.contexts with
        | Some value->value | None->fail "Unknown native context capability." in
      let kind,value=match M.invoke_provider(live state) ~host_links:context.host_links provider.provider context.context with
        | M.Proposal value->"proposal",C.Pass_result.to_json value
        | M.Decision value->"decision",C.Check_decision.to_json value
        | M.Invalid_return value->"invalid",value
        | M.Host_return _->fail "Native provider returned a foreign host result." in
      let view=if kind="invalid" then Json.Null else provider_view state provider kind value in
      obj["kind",str kind;"value",value;"view",view]
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
  | M.No_candidate_found value->
      let dependencies=exception_dependencies state value.dependencies in
      Some(exception_json state "biocompiler.compiler.pipeline" "NoCandidateFound" value.message
        (obj["pass_id",str value.pass_id;"configuration",value.configuration;"dependencies",dependencies]))
  | G.Unsupported value->Some(exception_json state "biocompiler.errors" "UnsupportedBehaviorError"(G.format_error value)(obj[]))
  | _->None
let dispatch (state:t) _ (command:Ch.command)=
  try Ch.Success(dispatch_value state command.operation command.arguments)
  with cause->match reject state cause with Some value->Ch.Rejected value | None->raise cause
let create ~io ()=
  let state={channel=None;bridge=None;initialized=false;live=None;manager_limits=M.default_limits;
    manager_json=defaults;target_binding=None;requested_config=None;fixed_request=None;origins=[];artifacts=[];providers=[];contexts=[];records=[];
    bindings=[];frozen=[];executions=[];pass_sidecars=[];admission_sidecars=[];
    input_sidecar=None;next_identity=0} in
  let value=Ch.create ~io ~application:declaration ~dispatch:(dispatch state) () in
  state.channel<-Some value;state
let release (state:t)=
  Option.iter H.close state.bridge;state.bridge<-None;state.live<-None;state.target_binding<-None;state.requested_config<-None;state.fixed_request<-None;state.origins<-[];
  state.artifacts<-[];state.providers<-[];state.contexts<-[];state.records<-[];state.bindings<-[];
  state.frozen<-[];state.executions<-[];state.pass_sidecars<-[];state.admission_sidecars<-[];state.input_sidecar<-None
let run (state:t)=Fun.protect ~finally:(fun()->release state)(fun()->Ch.run(channel state))
let is_closed (state:t)=Ch.is_closed(channel state)
