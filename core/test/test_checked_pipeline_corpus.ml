(* Captured results are comparison oracles only: they are never installed as
   records, providers, checker decisions, or manager state. Other original
   cohorts remain in the corpus with explicitly pending callback parity. *)
open Bioc_wire
module C = Bioc_domain.Pipeline_contract
module M = Bioc_compiler.Pass_manager
module W = Bioc_checker.Work_budget
module E = Bioc_domain.Realization_evidence
let require condition message = if not condition then failwith message
let get key value = Json.field key (Json.object_fields value)
let optional key value = List.assoc_opt key (Json.object_fields value)
let text key value = Json.string (get key value)
let obj values = Json.Object values
let str value = Json.String value
let same left right = Canonical.encode left = Canonical.encode right
let equal label expected actual =
  require (same expected actual)
    (label ^ ": full observation differs\nexpected=" ^ Canonical.encode expected ^
     "\nactual=" ^ Canonical.encode actual)
let read_bytes path =
  let channel = open_in_bin path in
  Fun.protect (fun () -> really_input_string channel (in_channel_length channel))
    ~finally:(fun () -> close_in channel)
let parse bytes = Json.parse_bounded ~max_bytes:67_108_864 ~max_nodes:1_000_000 bytes
let digest value = String.length value=64 &&
  String.for_all (function '0'..'9' | 'a'..'f' -> true | _ -> false) value
let object_map f raw = obj (List.map (fun (key,value) -> key,f value) (Json.object_fields raw))
let source_file = "tests/test_pipeline.py"
let source_pin = "cee046bb960cd33f27f886668c5a56d34d14a7305abd1191d13295d41cd30ed7"
let methods = [
  "PipelineTests.test_candidate_cannot_weaken_obligation_or_certify_itself";
  "PipelineTests.test_changed_pass_invalidates_descendants";
  "PipelineTests.test_changed_properties_invalidate_prior_discharges";
  "PipelineTests.test_deeply_frozen_input_output_configuration_and_records";
  "PipelineTests.test_dependency_change_during_check_cannot_be_accepted";
  "PipelineTests.test_failed_unknown_and_unsupported_checks_never_accept";
  "PipelineTests.test_independent_checker_rejects_internally_consistent_wrong_value";
  "PipelineTests.test_missing_check_provider_and_same_function_are_rejected";
  "PipelineTests.test_missing_pass_missing_dependencies_order_and_unsupported_operations";
  "PipelineTests.test_missing_source_and_observation_maps_are_rejected";
  "PipelineTests.test_no_candidate_is_not_infeasibility_and_has_no_accepted_output";
  "PipelineTests.test_provider_changes_require_version_bump";
  "PipelineTests.test_registry_model_and_context_changes_invalidate_evidence";
  "PipelineTests.test_repeated_runs_have_identical_records";
  "PipelineTests.test_root_payload_must_match_request_identity";
  "PipelineTests.test_scope_complete_keeps_unresolved_biological_obligation";
  "PipelineTests.test_scope_requires_final_stage_and_explicit_obligations";
  "PipelineTests.test_skip_stage_and_wrong_target_are_rejected";
  "PipelineTests.test_source_correspondence_does_not_discharge_model_obligation";
  "PipelineTests.test_transitive_invalidation_reaches_multiple_stages";
  "PipelineTests.test_unknown_source_nodes_are_rejected" ]
let context_ids = List.map (fun name -> source_file ^ "::" ^ name) methods

(* Remove only language representation tags, adding exactly the original
   serializer's fixed fields. Unknown tags and classes fail closed. *)
let tagged_mapping raw =
  require (text "$type" raw="mapping") "Expected captured mapping";
  require (List.mem (text "class" raw) ["builtins.dict";"builtins.mappingproxy"])
    "Unreviewed captured mapping class";
  List.map (function Json.Array [key;value] -> key,value
    | _ -> failwith "Malformed captured mapping entry") (Json.array (get "items" raw))
let tagged_field key raw =
  match List.find_opt (fun (name,_) -> name=str key) (tagged_mapping raw) with
  | Some (_,value) -> value | None -> failwith ("Missing captured mapping field " ^ key)
let known_dataclasses = [
  "biocompiler.artifacts.provenance.SourceLink";
  "biocompiler.verification.evidence.Obligation";
  "biocompiler.compiler.pipeline.ScopedObligation";
  "biocompiler.compiler.pipeline.CheckSpec";
  "biocompiler.compiler.pipeline.CheckDecision";
  "biocompiler.compiler.pipeline.PassContract";
  "biocompiler.compiler.pipeline.PassContext";
  "biocompiler.compiler.pipeline.ComponentInputContract";
  "biocompiler.compiler.pipeline.CompletionProfile";
  "biocompiler.compiler.pipeline.StageRecord";
  "biocompiler.compiler.pipeline.PipelineResult";
  "biocompiler.compiler.passes.PassResult";
  "biocompiler.semantics.context.TargetContext" ]
let decorate class_name fields =
  let fixed = match class_name with
    | "biocompiler.compiler.pipeline.StageRecord" -> ["schema_version",str C.Stage_record.schema_version]
    | "biocompiler.semantics.context.TargetContext" -> ["schema_version",str "biocompiler.target.v0.1"]
    | "biocompiler.compiler.pipeline.ComponentInputContract" -> ["stage",str (C.stage_name C.Components)]
    | _ -> [] in
  obj (fixed @ Json.object_fields fields)
let rec unpack raw = match raw with
  | Json.Object fields -> (match List.assoc_opt "$type" fields with
    | None -> object_map unpack raw
    | Some (Json.String "mapping") -> obj (List.map (fun (key,value) -> Json.string key,unpack value) (tagged_mapping raw))
    | Some (Json.String ("tuple" | "list")) -> Json.Array (List.map unpack (Json.array (get "items" raw)))
    | Some (Json.String "enum") ->
      require (List.mem (text "class" raw) [
        "biocompiler.ir.stages.Stage";"biocompiler.semantics.context.PayloadFormat";
        "biocompiler.verification.evidence.CheckOutcome";"biocompiler.verification.evidence.EvidenceKind";
        "biocompiler.compiler.pipeline.ArtifactStatus"]) "Unreviewed captured enum";
      get "value" raw
    | Some (Json.String "dataclass") ->
      let class_name=text "class" raw in
      require (List.mem class_name known_dataclasses) ("Unreviewed captured class " ^ class_name);
      decorate class_name (object_map unpack (get "fields" raw))
    | Some (Json.String ("provider" | "manager")) -> get "id" raw
    | _ -> failwith "Unreviewed captured value tag")
  | Json.Array values -> Json.Array (List.map unpack values)
  | _ -> raw

module type Record = sig
  type t
  val of_json : ?limits:C.Codec.limits -> ?path:string -> Json.t -> t
  val to_json : t -> Json.t
  val fingerprint : t -> string
end
let record_codec = function
  | "SourceLink" -> (module C.Source_link : Record)
  | "Obligation" -> (module C.Producer_obligation : Record)
  | "ScopedObligation" -> (module C.Scoped_obligation : Record)
  | "CheckSpec" -> (module C.Check_spec : Record)
  | "CheckDecision" -> (module C.Check_decision : Record)
  | "PassContract" -> (module C.Pass_contract : Record)
  | "PassContext" -> (module C.Pass_context : Record)
  | "ComponentInputContract" -> (module C.Component_input_contract : Record)
  | "CompletionProfile" -> (module C.Completion_profile : Record)
  | "StageRecord" -> (module C.Stage_record : Record)
  | "PipelineResult" -> (module C.Pipeline_result : Record)
  | "PassResult" -> (module C.Pass_result : Record)
  | name -> failwith ("Unreviewed record API " ^ name)
let class_name = function
  | "PassResult" -> "biocompiler.compiler.passes.PassResult"
  | "SourceLink" -> "biocompiler.artifacts.provenance.SourceLink"
  | "Obligation" -> "biocompiler.verification.evidence.Obligation"
  | name -> "biocompiler.compiler.pipeline." ^ name
let constructor_inputs name raw =
  obj (List.map (fun (key,value) ->
    let key=Json.string key in
    let value=match value with
      | Json.Object fields when List.assoc_opt "$type" fields=Some (str "object") ->
        require (List.mem (name,key) ["PassContext","observation_map";
          "PassResult","observation_map";"CheckDecision","evidence"] &&
          text "class" value="dataclasses._HAS_DEFAULT_FACTORY_CLASS" &&
          get "attributes" value=obj [])
          "Unreviewed Python constructor default factory";
        obj []
      | _ -> unpack value in
    key,value) (tagged_mapping raw))

type corpus = {index:Json.t; document:string -> Json.t; events:Json.t list;
  event_by_id:(string,Json.t) Hashtbl.t; providers:Json.t}
let load path =
  let bytes=read_bytes path in
  let index=parse bytes in
  require (List.mem (text "schema_version" index)
    ["biocompiler.checked_pipeline_original_capture.v1";"biocompiler.checked_pipeline_conformance.v1"])
    "Unknown original checked-pipeline corpus";
  require (text source_file (get "source_files" index)=source_pin) "Original PipelineTests source changed";
  let cache=Hashtbl.create 1024 in
  let document = match get "documents" index with
    | Json.Object fields -> (* The same driver can inspect the bounded pilot. *)
      require (Canonical.sha256 bytes="d7045136c71cf599c90c1646ebd641ee6961b5cc0047585476aee65ad5041fc4")
        "Original bounded pilot oracle changed";
      List.iter (fun (id,raw) -> require (Canonical.fingerprint raw=id) "Pilot document hash differs";
        Hashtbl.add cache id raw) fields;
      (fun id -> Hashtbl.find cache id)
    | Json.Array descriptors ->
      require (text "capture_mode" index="manager_isolation_projection")
        "Native replay requires the reviewed bounded original-manager projection";
      require (text "inventory_fingerprint" index=
        "1c9391db642c9375cc73cd2e28fc49cc6fb5966e0c30d6e430cfe49946e0dcb6")
        "Independently pinned original-manager projection changed";
      let full=get "full_corpus" index in
      Json.exact_fields ["inventory_fingerprint";"original_capture_fingerprint";"contexts";"original_methods"]
        (Json.object_fields full);
      require (get "contexts" full=Json.int 476 && get "original_methods" full=Json.int 467)
        "Full original cohort census changed";
      require (text "inventory_fingerprint" full=
        "1b8ce09b5bb39e9bec43dae64c00291716a5971349eafd14c1f9f7e2a6bb6117" &&
        text "original_capture_fingerprint" full=
        "376fab36d6cd96c9a4cb8d393c76854042b72725c81a12d266eb78fe2cae0e1c")
        "Full original capture authority changed";
      let directory=text "document_directory" index in
      require (directory="checked-pipeline-v1") "Unexpected corpus document directory";
      let entries=Hashtbl.create (List.length descriptors) in
      List.iter (fun descriptor ->
        let id=text "id" descriptor in
        require (digest id && not (Hashtbl.mem entries id)) "Invalid or duplicate document identity";
        Hashtbl.add entries id (Z.to_int (Json.integer (get "bytes" descriptor)))) descriptors;
      (match optional "inventory_fingerprint" index with
       | Some expected -> equal "Complete corpus inventory fingerprint" expected
           (str (Canonical.sha256 (Canonical.encode_bounded ~max_bytes:67_108_864
             (obj (List.remove_assoc "inventory_fingerprint" (Json.object_fields index))))))
       | None -> failwith "Missing complete corpus inventory fingerprint");
      (fun id -> match Hashtbl.find_opt cache id with
       | Some raw -> raw
       | None ->
         require (digest id && Hashtbl.mem entries id) "Uninventoried captured document";
         let bytes=read_bytes (Filename.concat (Filename.concat (Filename.dirname path) directory) (id ^ ".json")) in
         require (String.length bytes=Hashtbl.find entries id) "Captured document byte census differs";
         let raw=parse bytes in
         require (bytes=Canonical.encode raw ^ "\n" && Canonical.fingerprint raw=id)
           "Captured document complete canonical bytes differ";
         Hashtbl.add cache id raw;raw)
    | _ -> failwith "Malformed original document inventory" in
  let events=Json.array (get "events" index) in
  let event_by_id=Hashtbl.create (List.length events) in
  List.iter (fun event -> let id=text "id" event in
    require (not (Hashtbl.mem event_by_id id)) "Duplicate original event identity";
    Hashtbl.add event_by_id id event) events;
  {index;document;events;event_by_id;providers=get "providers" index}
let arguments corpus event = corpus.document (text "arguments" event)
let bound corpus event = tagged_field "bound" (arguments corpus event)
let event_result corpus event = unpack (corpus.document (text "result" event))
let event_id event = text "id" event

(* Full snapshots include rejected records and historical provider identities.
   Native component history is a separate field. The original uses tuple keys;
   this selected cohort has no component admission entries. *)
let snapshot raw =
  let fields=get "fields" raw in
  Json.exact_fields ["_target";"_dependencies";"_passes";"_component_inputs";
    "_provider_history";"_records";"_profiles"] (Json.object_fields fields);
  let registrations raw = obj (List.map (fun (key,value) ->
    match unpack value with
    | Json.Array [contract;producer;validators] -> Json.string key,
      obj ["contract",contract;"producer",producer;"validators",validators]
    | _ -> failwith "Unreviewed registration snapshot") (tagged_mapping raw)) in
  require (tagged_mapping (get "_component_inputs" fields)=[]) "Component admission outside reviewed cohort";
  obj ["target",unpack (get "_target" fields);"dependencies",unpack (get "_dependencies" fields);
    "passes",registrations (get "_passes" fields);"component_inputs",obj [];
    "provider_history",registrations (get "_provider_history" fields);"component_input_history",obj [];
    "records",unpack (get "_records" fields);"profiles",unpack (get "_profiles" fields)]

type replay = {corpus:corpus; managers:(string,M.t) Hashtbl.t;
  mutable provider_values:(string * M.provider) list; mutable callbacks:Json.t list;
  mutable active_manager:string option; mutable active_command:string option;
  mutable records:C.Stage_record.t list; mutable consumed_documents:(string * Json.t) list;
  actual_errors:(string,Json.t) Hashtbl.t;
  mutable callback_count:int; mutable command_count:int; mutable domain_count:int;
  mutable effect_count:int; mutable helper_count:int}
let manager replay id = match Hashtbl.find_opt replay.managers id with
  | Some value -> value | None -> failwith ("Manager was not created by native replay: " ^ id)
let provider_identity replay value =
  match List.find_opt (fun (_,provider) -> provider==value) replay.provider_values with
  | Some (id,_) -> id | None -> failwith "Native manager retained an unknown provider"
let inspect replay id = M.inspect (manager replay id) ~provider_identity:(provider_identity replay)
let check_state replay event key = match get key event with
  | Json.Null -> ()
  | Json.String id ->
    let expected=replay.corpus.document id in
    let manager_id=text "manager" expected in
    if Hashtbl.mem replay.managers manager_id then
      equal (event_id event ^ " " ^ key) (snapshot expected) (inspect replay manager_id)
    else equal (event_id event ^ " not-yet-created state") (obj []) (get "fields" expected)
  | _ -> failwith "Malformed captured state reference"
let error_of_exception = function
  | Diagnostic.Error error ->
    let module_name,type_name = match error.code with
      | "pipeline_error" -> "biocompiler.compiler.pipeline","PipelineError"
      | "pipeline_serialization" | "pipeline_contract" -> "biocompiler.errors","SerializationError"
      | code -> failwith ("Unexpected native diagnostic " ^ code ^ ": " ^ error.message) in
    obj ["module",str module_name;"type",str type_name;"message",str error.message]
  | M.No_candidate_found value -> obj ["module",str "biocompiler.compiler.pipeline";
      "type",str "NoCandidateFound";"message",str value.message;
      "attributes",obj ["pass_id",str value.pass_id;"configuration",value.configuration;
        "dependencies",obj (List.map (fun (key,id) -> key,str id) value.dependencies)]]
  | error -> raise error
let observe replay event action =
  check_state replay event "state_before";
  let actual = try Ok (action ()) with error -> Error (error_of_exception error) in
  check_state replay event "state_after";
  match text "outcome" event,actual with
  | "returned",Ok value -> equal (event_id event ^ " returned") (event_result replay.corpus event) value
  | "raised",Error error ->
    equal (event_id event ^ " raised") (unpack (get "error" event)) error;
    Hashtbl.replace replay.actual_errors (event_id event) error
  | "returned",Error error -> failwith (event_id event ^ ": unexpected rejection " ^ Canonical.encode error)
  | "raised",Ok value -> failwith (event_id event ^ ": expected rejection, got " ^ Canonical.encode value)
  | _ -> failwith "Unknown original event outcome"

let recipes = [
  "PipelineTests.producer.<locals>.produce",118,
    "9437e3af7107969f1d7206f1757a2ef4c4b4c50056aed9e0df411f542bf0f704",
    ["contract";"kind";"links";"mapping";"obligations";"value"];
  "accepted",33,"bae9099280ad1b3890671fa2598ae849d2f04da7d32ab4d0eb93f27c1b124147",[];
  "PipelineTests.test_dependency_change_during_check_cannot_be_accepted.<locals>.changed",333,
    "5a0dd4badd58af357143e7ad0b870f9929f2b3b4385782fbb9dad73ec1e3d0f7",["self"];
  "PipelineTests.test_failed_unknown_and_unsupported_checks_never_accept.<locals>.<lambda>",211,
    "1946d41521a69c55bfeb3692da0dca1f73d3ed94e5b35d375e5ee564064d1114",["outcome"];
  "PipelineTests.test_independent_checker_rejects_internally_consistent_wrong_value.<locals>.verify",219,
    "2b906580ef75553fc535fa489b2cbb40e24b54bbc37fc30b2865b86eaf91e821",[];
  "PipelineTests.test_no_candidate_is_not_infeasibility_and_has_no_accepted_output.<locals>.no_candidate",343,
    "8c6fb2b50fb01df2dc7a615c6d3086900517c7e430dd4d7cde0431ecc3f5112b",[];
  "PipelineTests.test_unknown_source_nodes_are_rejected.<locals>.produce",272,
    "967b3121723010aad373c06508fdfc9c46e69da968cb8542ce9a9856f5898d9d",[] ]
let recipe descriptor =
  let name=text "qualname" descriptor in
  let _,line,hash,freevars = match List.find_opt (fun (other,_,_,_) -> other=name) recipes with
    | Some value -> value | None -> failwith ("Unreviewed native callback recipe " ^ name) in
  require (text "file" descriptor=source_file && get "line" descriptor=Json.int line &&
    Canonical.sha256 (text "source" descriptor)=hash && text "class" descriptor="builtins.function" &&
    get "defaults" descriptor=Json.Null && get "kwdefaults" descriptor=Json.Null)
    ("Original callback source/defaults changed: " ^ name);
  equal "Complete callback free-variable inventory" (Json.Array (List.map str freevars)) (get "freevars" descriptor);
  Json.exact_fields freevars (Json.object_fields (get "closure" descriptor));name,freevars
let document schema value kind = obj ["schema_version",str schema;
  "nodes",Json.Array [obj ["id",str "n";"kind",kind;"value",value]]]
let callback_json = function
  | M.Proposal value -> C.Pass_result.to_json value
  | M.Decision value -> C.Check_decision.to_json value
  | M.Invalid_return value -> value
  | M.Host_return _ -> failwith "Deferred host objects are not native fixture callback recipes"
let dependencies raw = List.map (fun (key,value) -> key,Json.string value) (Json.object_fields raw)
let string_list raw = List.map Json.string (Json.array raw)
let context_parameter locals = match List.assoc_opt "context" (List.map (fun (key,value) -> Json.string key,value) (tagged_mapping locals)) with
  | Some value -> value | None -> tagged_field "_" locals
let consumed_document replay raw =
  let id=match replay.active_command with Some id -> id | None -> failwith "Document outside native command" in
  replay.consumed_documents<-(id,raw)::replay.consumed_documents

let provider replay tagged =
  require (text "$type" tagged="provider") "Expected provider reference";
  let id=text "id" tagged in
  match List.assoc_opt id replay.provider_values with
  | Some value -> value
  | None ->
    let descriptor=get id replay.corpus.providers in
    let name,freevars=recipe descriptor in
    let closure=get "closure" descriptor in
    let value work context =
      let event=match replay.callbacks with
        | event::rest -> replay.callbacks<-rest;event
        | [] -> failwith ("Unexpected actual native callback " ^ id) in
      require (text "provider" event=id) "Actual native callback identity/order differs";
      let manager_id=match replay.active_manager with Some value -> value | None -> failwith "Callback outside native command" in
      require (get "manager" event=str manager_id) "Actual callback manager differs";
      let locals=tagged_field "locals" (arguments replay.corpus event) in
      equal (event_id event ^ " complete context") (unpack (context_parameter locals)) (C.Pass_context.to_json context);
      List.iter (fun key -> equal (event_id event ^ " closure " ^ key)
        (get key closure) (tagged_field key locals)) freevars;
      let result=ref None in
      observe replay event (fun () ->
        let limits=C.Codec.make_limits ~charge:(W.charge work) () in
        let decision outcome detail = M.Decision (C.Check_decision.make ~limits ~outcome ~detail ()) in
        let source_link source target pass_name =
          C.Source_link.make ~limits ~requirement_id:"r" ~source_node_id:source ~target_node_id:target ~pass_name () in
        let proposal ?(obligations=[]) ?(source_links=[]) ?(observation_map=obj []) ?(search_status="candidate") output =
          M.Proposal (C.Pass_result.make ~limits ~output ~obligations ~source_links ~observation_map ~search_status ()) in
        let produced = match name with
          | "PipelineTests.producer.<locals>.produce" ->
            let contract=C.Pass_contract.of_json ~limits (unpack (get "contract" closure)) in
            let source_links=if Json.boolean (get "links" closure) then
              [source_link "n" "n" (C.Pass_contract.id contract)] else [] in
            let mapping=unpack (get "mapping" closure) in
            let observation_map=if mapping=Json.Null then obj ["output",str "n"] else mapping in
            let obligations=List.map (C.Producer_obligation.of_json ~limits)
                (Json.array (unpack (get "obligations" closure))) in
            proposal ~obligations ~source_links ~observation_map
              (Some (document (C.Pass_contract.output_schema contract) (unpack (get "value" closure)) (unpack (get "kind" closure))))
          | "accepted" -> decision E.Pass "Independently matched the expected value."
          | "PipelineTests.test_failed_unknown_and_unsupported_checks_never_accept.<locals>.<lambda>" ->
            let outcome=match unpack (get "outcome" closure) with
              | Json.String "fail" -> E.Fail | Json.String "unknown" -> E.Unknown
              | Json.String "unsupported" -> E.Unsupported | _ -> failwith "Unexpected original loop outcome" in
            decision outcome "Unestablished preservation."
          | "PipelineTests.test_independent_checker_rejects_internally_consistent_wrong_value.<locals>.verify" ->
            let scalar raw=get "value" (List.hd (Json.array (get "nodes" raw))) in
            let output=match C.Pass_context.output context with Some raw -> raw | None -> failwith "Checker missing candidate" in
            decision (if same (scalar output) (scalar (C.Pass_context.input context)) then E.Pass else E.Fail) "Checked input value."
          | "PipelineTests.test_dependency_change_during_check_cannot_be_accepted.<locals>.changed" ->
            let self=get "self" closure in
            require (text "$type" self="object" &&
              String.ends_with ~suffix:".PipelineTests" (text "class" self))
              "Dependency callback lost its original TestCase closure";
            let closed_manager=get "manager" (get "attributes" self) in
            require (text "$type" closed_manager="manager" && text "id" closed_manager=manager_id)
              "Dependency callback must mutate its captured manager";
            let effects=List.filter (fun child -> get "parent" child=str (event_id event) &&
              String.starts_with ~prefix:"PassManager." (text "api" child)) replay.corpus.events in
            (match effects with
             | [mutation] ->
               require (text "api" mutation="PassManager.set_dependency" && get "manager" mutation=str manager_id)
                 "Dependency callback manager/effect differs";
               equal "Original callback dependency arguments"
                 (obj ["key",str "registry";"identity",str (Canonical.fingerprint (str "v2"))])
                 (unpack (bound replay.corpus mutation));
               observe replay mutation (fun () -> M.set_dependency (manager replay manager_id) "registry"
                 (Canonical.fingerprint (str "v2"));Json.Null);
               replay.effect_count<-replay.effect_count+1
             | _ -> failwith "Dependency callback must have exactly its original manager mutation");
            decision E.Pass "Passed before a concurrent change."
          | "PipelineTests.test_no_candidate_is_not_infeasibility_and_has_no_accepted_output.<locals>.no_candidate" ->
            proposal ~search_status:"no_candidate_found" None
          | "PipelineTests.test_unknown_source_nodes_are_rejected.<locals>.produce" ->
            proposal ~source_links:[source_link "wrong" "n" "lower"] (Some (document "behavior.v1" (Json.int 1) (str "constant")))
          | _ -> failwith "Missing source-reviewed callback implementation" in
        (match produced with
         | M.Proposal proposal -> Option.iter (consumed_document replay) (C.Pass_result.output proposal)
         | _ -> ());
        result:=Some produced;callback_json produced);
      replay.callback_count<-replay.callback_count+1;
      match !result with Some value -> value | None -> failwith "Original callback failed unexpectedly" in
    replay.provider_values<-(id,value)::replay.provider_values;value

let domain_observation replay event =
  let api=text "api" event in
  let name,method_name=match String.split_on_char '.' api with [name;method_name] -> name,method_name
    | _ -> failwith ("Unexpected record observation " ^ api) in
  let module R = (val record_codec name : Record) in
  observe replay event (fun () ->
    let raw=if method_name="__init__" then decorate (class_name name) (constructor_inputs name (bound replay.corpus event))
      else unpack (tagged_field "subject" (arguments replay.corpus event)) in
    let parsed=R.of_json raw in
    match method_name with "__init__" | "to_dict" -> R.to_json parsed
      | "fingerprint" -> str (R.fingerprint parsed) | _ -> failwith "Unreviewed record method");
  replay.domain_count<-replay.domain_count+1
let rec root_of corpus event = match get "parent" event with
  | Json.Null -> event_id event
  | Json.String id -> root_of corpus (Hashtbl.find corpus.event_by_id id)
  | _ -> failwith "Malformed original event parent"
let produced_record replay tagged =
  let expected=unpack tagged in
  match List.find_opt (fun record -> same expected (C.Stage_record.to_json record)) replay.records with
  | Some record -> record | None -> failwith "Observed record was not produced by actual native manager"
let command replay event =
  let api=text "api" event in
  let id=event_id event in
  replay.active_command<-Some id;
  replay.callbacks<-List.filter (fun child -> text "api" child="callback.invoke" &&
    root_of replay.corpus child=id) replay.corpus.events;
  replay.active_manager<-(match get "manager" event with Json.String value -> Some value | Json.Null -> None
    | _ -> failwith "Invalid manager identity");
  let remember value=replay.records<-value::replay.records;C.Stage_record.to_json value in
  if String.starts_with ~prefix:"PassManager." api then begin
    observe replay event (fun () ->
      let raw=bound replay.corpus event in
      let arg key=unpack (tagged_field key raw) in
      let string key=Json.string (arg key) in
      let manager_id=text "manager" event in
      if api="PassManager.__init__" then begin
        require (not (Hashtbl.mem replay.managers manager_id)) "Original manager identity reused";
        let work=W.create ~profile:"checked_pipeline_original_replay" ~error_code:"checked_pipeline_replay_budget"
            ~maximum:100_000_000_000 () in
        let value=M.create ~budget:work ~target:(Bioc_domain.Build_request.Target.of_json (arg "target"))
            ~dependencies:(dependencies (arg "dependencies"))
            ~completion_profiles:(List.map (fun raw -> C.Completion_profile.of_json raw)
              (Json.array (arg "completion_profiles"))) () in
        Hashtbl.add replay.managers manager_id value;str manager_id
      end else
        let value=manager replay manager_id in
        match api with
        | "PassManager.add_input" ->
          let payload=arg "payload" in
          consumed_document replay payload;
          remember (M.add_input value ~identity:(string "identity")
            ~stage:(C.stage_of_json (arg "stage")) ~requirements:(string_list (arg "requirements"))
            ~obligations:(List.map (fun raw -> C.Scoped_obligation.of_json raw)
              (Json.array (arg "obligations"))) payload)
        | "PassManager.register" ->
          let producer_value=provider replay (tagged_field "producer" raw) in
          let validators=List.map (fun (key,ref_) -> Json.string key,provider replay ref_)
            (tagged_mapping (tagged_field "validators" raw)) in
          M.register value (C.Pass_contract.of_json (arg "contract")) ~producer:producer_value ~validators;Json.Null
        | "PassManager.run" ->
          let configuration=match arg "configuration" with Json.Null -> None | raw -> Some raw in
          remember (M.run value ~pass_id:(string "pass_id") ~input_id:(string "input_id")
            ~output_id:(string "output_id") ?configuration ())
        | "PassManager.get" -> remember (M.get value (string "identity"))
        | "PassManager.result" -> C.Pipeline_result.to_json (M.result value ~identity:(string "identity") ~scope:(string "scope"))
        | "PassManager.set_dependency" -> M.set_dependency value (string "key") (string "identity");Json.Null
        | "PassManager.register_completion_profile" ->
          M.register_completion_profile value (C.Completion_profile.of_json (arg "profile"));Json.Null
        | "PassManager.target" -> Bioc_domain.Build_request.Target.to_json (M.target value)
        | _ -> failwith ("Unreviewed external manager API " ^ api))
  end else if api="StageRecord.to_dict" || api="StageRecord.fingerprint" then
    observe replay event (fun () ->
      let value=produced_record replay (tagged_field "subject" (arguments replay.corpus event)) in
      if api="StageRecord.to_dict" then C.Stage_record.to_json value else str (C.Stage_record.fingerprint value))
  else domain_observation replay event;
  require (replay.callbacks=[]) (id ^ ": original callbacks were not actually invoked");
  replay.active_manager<-None;replay.active_command<-None;
  replay.command_count<-replay.command_count+1

(* Python's private _document freezes container representation without changing
   canonical content. Bind each such observation to the real native call input
   or produced candidate from that command. NoCandidateFound construction is
   bound to the actual native exception, including all structured attributes.
   Neither observation is used to synthesize a manager result. *)
let helper_observation replay event =
  let root=root_of replay.corpus event in
  require (text "outcome" event="returned") "Unreviewed private-helper rejection";
  (match text "api" event with
   | "_document" ->
     let input=unpack (tagged_field "value" (bound replay.corpus event)) in
     let rec take prefix = function
       | [] -> failwith "Original document was not consumed by this actual native command"
       | (id,raw)::rest when id=root && same input raw ->
         replay.consumed_documents<-List.rev_append prefix rest;raw
       | value::rest -> take (value::prefix) rest in
     let actual=take [] replay.consumed_documents in
     equal (event_id event ^ " complete frozen document") (event_result replay.corpus event) actual
   | "NoCandidateFound.__init__" ->
     let actual=match Hashtbl.find_opt replay.actual_errors root with
       | Some error -> error | None -> failwith "No native no-candidate exception was raised" in
     equal (event_id event ^ " complete native exception") (event_result replay.corpus event) actual;
     equal (event_id event ^ " exception constructor arguments")
       (unpack (bound replay.corpus event)) (get "attributes" actual)
   | _ -> failwith "Unreviewed private-helper observation");
  replay.helper_count<-replay.helper_count+1

let () =
  require (Array.length Sys.argv=2) "Expected complete checked-pipeline corpus index path";
  let corpus=load Sys.argv.(1) in
  let selected=List.filter (fun context -> List.mem (text "id" context) context_ids)
      (Json.array (get "contexts" corpus.index)) in
  equal "All 21 original manager methods" (Json.Array (List.map str (List.sort String.compare context_ids)))
    (Json.Array (List.map str (List.sort String.compare (List.map (text "id") selected))));
  let replay={corpus;managers=Hashtbl.create 32;provider_values=[];callbacks=[];active_manager=None;
    active_command=None;records=[];consumed_documents=[];actual_errors=Hashtbl.create 32;
    callback_count=0;command_count=0;domain_count=0;effect_count=0;helper_count=0} in
  let selected_events=List.filter (fun event -> List.mem (text "context" event) context_ids) corpus.events in
  List.iter (fun context ->
    require (text "assertion_status" context="passed" && text "kind" context="original_method")
      "Original test assertions did not pass";
    let events=List.filter (fun event -> text "context" event=text "id" context) selected_events in
    equal "Complete original context event inventory" (get "events" context)
      (Json.Array (List.map (fun event -> str (event_id event)) events));
    List.iter (command replay) (List.filter (fun event -> get "parent" event=Json.Null) events)) selected;
  (* Independently consume complete nested record-construction/serialization
     observations. Native internal manager call counts need not equal Python
     implementation call counts. *)
  List.iter (fun event -> if get "parent" event<>Json.Null &&
      text "api" event<>"callback.invoke" &&
      not (String.starts_with ~prefix:"PassManager." (text "api" event)) then
    if List.mem (text "api" event) ["_document";"NoCandidateFound.__init__"] then
      helper_observation replay event
    else domain_observation replay event) selected_events;
  require (List.length selected_events=1738 && replay.command_count=374 &&
    replay.callback_count=57 && replay.domain_count=987 && replay.effect_count=1 &&
    replay.helper_count=60 && replay.consumed_documents=[] &&
    Hashtbl.length replay.managers=27) "Original manager replay census changed";
  let full_contexts=match optional "full_corpus" corpus.index with
    | Some full -> Z.to_int (Json.integer (get "contexts" full))
    | None -> List.length (Json.array (get "contexts" corpus.index)) in
  Printf.printf "Checked pipeline: 21 original contexts, 374 external commands, 57 actual callbacks, 987 independent record observations, 60 native-input/exception helper correspondences, one actual reentrant mutation; %d other captured contexts retain pending callback parity\n"
    (full_contexts-List.length selected)
