(* Real fixed producers/checkers execute from complete original authority.
   Expected records are comparison data only. Provider IDs are translated only
   for diagnostic snapshots, never registered or used as acceptance authority. *)
open Bioc_wire
open Bioc_domain
module C = Pipeline_contract
module M = Bioc_compiler.Pass_manager
module W = Bioc_checker.Work_budget
module S = Bioc_pipeline.Synthetic_pipeline
module P = Bioc_pipeline.Component_pipeline
module G = Bioc_synthetic_producer.Generator
let require condition message = if not condition then failwith message
let get key raw = Json.field key (Json.object_fields raw)
let text key raw = Json.string (get key raw)
let obj fields = Json.Object fields
let str value = Json.String value
let canonical raw = Canonical.encode_bounded ~max_bytes:67_108_864 raw
let fingerprint raw = Canonical.sha256 (canonical raw)
let same left right = canonical left=canonical right
let equal label expected actual =
  require (same expected actual)
    (label ^ ": complete original observation differs\nexpected=" ^ canonical expected ^
     "\nactual=" ^ canonical actual)
let read path =
  let input=open_in_bin path in
  Fun.protect (fun () -> really_input_string input (in_channel_length input))
    ~finally:(fun () -> close_in input)
let parse raw = Json.parse_bounded ~max_bytes:67_108_864 ~max_nodes:1_000_000 raw
let is_hash value = String.length value=64 &&
  String.for_all (function 'a'..'f' | '0'..'9' -> true | _ -> false) value
let map_object f raw = obj (List.map (fun (key,value) -> key,f value) (Json.object_fields raw))
let tagged_mapping raw =
  require (text "$type" raw="mapping") "Expected original mapping";
  require (List.mem (text "class" raw) ["builtins.dict";"builtins.mappingproxy"])
    "Unreviewed original mapping class";
  List.map (function Json.Array [key;value] -> key,value
    | _ -> failwith "Malformed original mapping entry") (Json.array (get "items" raw))
let tagged_field key raw =
  match List.find_opt (fun (name,_) -> name=str key) (tagged_mapping raw) with
  | Some (_,value) -> value | None -> failwith ("Missing original mapping key " ^ key)
let decorate name fields =
  let additions=match name with
    | "biocompiler.compiler.pipeline.StageRecord" -> ["schema_version",str C.Stage_record.schema_version]
    | "biocompiler.semantics.context.TargetContext" -> ["schema_version",str "biocompiler.target.v0.1"]
    | "biocompiler.compiler.pipeline.ComponentInputContract" -> ["stage",str (C.stage_name C.Components)]
    | "biocompiler.artifacts.provenance.SourceLink"
    | "biocompiler.compiler.pipeline.ScopedObligation"
    | "biocompiler.compiler.pipeline.CheckSpec"
    | "biocompiler.compiler.pipeline.CheckDecision"
    | "biocompiler.compiler.pipeline.PassContract"
    | "biocompiler.compiler.pipeline.PassContext"
    | "biocompiler.compiler.pipeline.CompletionProfile"
    | "biocompiler.compiler.pipeline.PipelineResult" -> []
    | _ -> failwith ("Unreviewed original record observation " ^ name) in
  obj (additions @ Json.object_fields fields)
let rec unpack raw = match raw with
  | Json.Object fields -> (match List.assoc_opt "$type" fields with
    | None -> map_object unpack raw
    | Some (Json.String "mapping") -> obj (List.map (fun (key,value) -> Json.string key,unpack value) (tagged_mapping raw))
    | Some (Json.String ("list" | "tuple")) -> Json.Array (List.map unpack (Json.array (get "items" raw)))
    | Some (Json.String "enum") -> get "value" raw
    | Some (Json.String ("manager" | "provider")) -> get "id" raw
    | Some (Json.String "dataclass") -> decorate (text "class" raw) (map_object unpack (get "fields" raw))
    | _ -> failwith "Unreviewed original observation tag")
  | Json.Array values -> Json.Array (List.map unpack values)
  | _ -> raw
type documents = {index:Json.t; document:string -> Json.t}
let load ~schema ~pin ~directory path =
  let index=parse (read path) in
  require (text "schema_version" index=schema) "Unexpected fixed pipeline corpus schema";
  require (text "inventory_fingerprint" index=pin) "Pinned original corpus inventory changed";
  equal "Fixed corpus inventory" (get "inventory_fingerprint" index)
    (str (fingerprint (obj (List.remove_assoc "inventory_fingerprint" (Json.object_fields index)))));
  require (text "document_directory" index=directory) "Unexpected fixed pipeline document directory";
  let descriptors=Hashtbl.create 2048 and cache=Hashtbl.create 2048 in
  List.iter (fun raw ->
    let id=text "id" raw in
    require (is_hash id && not (Hashtbl.mem descriptors id)) "Invalid original document identity";
    Hashtbl.add descriptors id (Z.to_int (Json.integer (get "bytes" raw))))
    (Json.array (get "documents" index));
  let document id = match Hashtbl.find_opt cache id with
    | Some value -> value
    | None ->
      require (is_hash id && Hashtbl.mem descriptors id) "Uninventoried original document";
      let bytes=read (Filename.concat (Filename.concat (Filename.dirname path) directory) (id ^ ".json")) in
      require (String.length bytes=Hashtbl.find descriptors id) "Original document byte count changed";
      let value=parse bytes in
      require (bytes=canonical value ^ "\n" && fingerprint value=id) "Complete original document bytes changed";
      (* Keep read caching bounded independently of the full original inventory. *)
      if Hashtbl.length cache>=8 then Hashtbl.clear cache;
      Hashtbl.add cache id value;value in
  {index;document}
let doc corpus key raw = corpus.document (text key raw)
let error = function
  | Diagnostic.Error value ->
    let owner,kind=match value.code with
      | "pipeline_error" -> "biocompiler.compiler.pipeline","PipelineError"
      | "pipeline_serialization" | "pipeline_contract" -> "biocompiler.errors","SerializationError"
      | code -> failwith ("Unreviewed fixed pipeline diagnostic " ^ code ^ ": " ^ value.message) in
    obj ["module",str owner;"type",str kind;"message",str value.message]
  | G.Unsupported value ->
    obj ["module",str "biocompiler.errors";"type",str "UnsupportedBehaviorError";
      "message",str (G.format_error value)]
  | M.No_candidate_found value ->
    obj ["module",str "biocompiler.compiler.pipeline";"type",str "NoCandidateFound";"message",str value.message;
      "attributes",obj ["pass_id",str value.pass_id;"configuration",value.configuration;
        "dependencies",obj (List.map (fun (key,value) -> key,str value) value.dependencies)]]
  | value -> raise value
let expected_snapshot raw =
  let fields=get "fields" raw in
  Json.exact_fields ["_target";"_dependencies";"_passes";"_component_inputs";
    "_provider_history";"_records";"_profiles"] (Json.object_fields fields);
  let registrations raw = obj (List.map (fun (key,value) ->
    match unpack value with
    | Json.Array [contract;producer;validators] -> Json.string key,
      obj ["contract",contract;"producer",producer;"validators",validators]
    | _ -> failwith "Unexpected original registration snapshot") (tagged_mapping raw)) in
  require (tagged_mapping (get "_component_inputs" fields)=[]) "Unexpected fixed component-input registration";
  obj ["target",unpack (get "_target" fields);"dependencies",unpack (get "_dependencies" fields);
    "passes",registrations (get "_passes" fields);"component_inputs",obj [];
    "provider_history",registrations (get "_provider_history" fields);"component_input_history",obj [];
    "records",unpack (get "_records" fields);"profiles",unpack (get "_profiles" fields)]
type labels = {mutable values:(M.provider * string) list}
let raw_snapshot labels manager =
  M.inspect manager ~provider_identity:(fun provider ->
    match List.find_opt (fun (other,_) -> other==provider) labels.values with
    | Some (_,name) -> name
    | None ->
      let name="native/" ^ string_of_int (List.length labels.values) in
      labels.values<-labels.values @ [provider,name];name)
let allowed_provider_slots = [
  "intent_to_behavior","producer","biocompiler/compiler/synthetic.py","run_synthetic_pipeline.<locals>.lower";
  "intent_to_behavior","preservation","biocompiler/compiler/synthetic.py","run_synthetic_pipeline.<locals>.verify";
  "behavior_to_synthetic","producer","biocompiler/compiler/synthetic.py","run_synthetic_pipeline.<locals>.generate";
  "behavior_to_synthetic","finite_history","biocompiler/compiler/synthetic.py","run_synthetic_pipeline.<locals>.check";
  "synthetic_to_components","producer","biocompiler/compiler/components.py","run_component_pipeline.<locals>.generate";
  "synthetic_to_components","composition","biocompiler/compiler/components.py","run_component_pipeline.<locals>.verify"]
let validate_provider providers contract slot id =
  let descriptor=get id providers in
  let _,_,file,name=match List.find_opt (fun (key,role,_,_) -> key=contract && role=slot) allowed_provider_slots with
    | Some value -> value | None -> failwith "Unexpected fixed callback registration" in
  require (text "file" descriptor="src/" ^ file && text "qualname" descriptor=name &&
    text "class" descriptor="builtins.function") "Original fixed callback identity changed"
type alignment = {forward:(string,string) Hashtbl.t;reverse:(string,string) Hashtbl.t}
let alignment () = {forward=Hashtbl.create 8;reverse=Hashtbl.create 8}
let align_snapshot aliases providers expected actual =
  let bind contract slot expected actual =
    let expected=Json.string expected and actual=Json.string actual in
    validate_provider providers contract slot expected;
    (match Hashtbl.find_opt aliases.forward actual with
      | None -> Hashtbl.add aliases.forward actual expected
      | Some previous -> require (previous=expected) "Native callback physical identity differs");
    (match Hashtbl.find_opt aliases.reverse expected with
      | None -> Hashtbl.add aliases.reverse expected actual
      | Some previous -> require (previous=actual) "Distinct native callbacks alias one original provider") in
  List.iter (fun field ->
    List.iter (fun (key,registration) ->
      let counterpart=get key (get field actual) in
      equal ("Actual fixed contract " ^ key) (get "contract" registration) (get "contract" counterpart);
      let id=text "id" (get "contract" registration) in
      bind id "producer" (get "producer" registration) (get "producer" counterpart);
      List.iter (fun (key,value) -> bind id key value (get key (get "validators" counterpart)))
        (Json.object_fields (get "validators" registration))) (Json.object_fields (get field expected)))
    ["passes";"provider_history"];
  let provider raw=match Hashtbl.find_opt aliases.forward (Json.string raw) with
    | Some id -> str id | None -> failwith "Native manager contains an unbound fixed provider" in
  let registration raw=obj ["contract",get "contract" raw;"producer",provider (get "producer" raw);
      "validators",map_object provider (get "validators" raw)] in
  obj (List.map (fun (key,value) -> key,
    if key="passes" || key="provider_history" then map_object registration value else value)
    (Json.object_fields actual))
let check_snapshot aliases providers labels manager expected =
  let expected=expected_snapshot expected in
  let actual=align_snapshot aliases providers expected (raw_snapshot labels manager) in
  equal "Complete actual fixed manager state" expected actual
let stage_records labels manager = get "records" (raw_snapshot labels manager)
let selection_json = function None -> Json.Null | Some value -> Synthetic_selection.Result.to_json value
type completed = {manager:M.t;records:Json.t;result:C.Pipeline_result.t}
type execution = Completed of completed | Failed of exn * M.t option
let execute authority api =
  let budget=W.create ~profile:"fixed_pipeline_original_corpus" ~error_code:"fixed_pipeline_corpus_budget"
      ~maximum:1_000_000_000_000 () in
  let request=Realization_request.of_json (get "request" authority) in
  let frames=List.map (fun raw -> Execution_data.Input_frame.of_json raw) (Json.array (get "history" authority)) in
  let config=match get "config" authority with Json.Null -> None | value -> Some (Synthetic_authority.Config.of_json value) in
  let until=match get "until" authority with Json.Null -> None | value -> Some (Runtime_number.of_json value) in
  let labels={values=[]} in
  match api with
  | "run_synthetic_pipeline" -> (match S.attempt ~budget ?until ?config request frames with
    | S.Failed failure -> Failed (failure.error,failure.manager)
    | S.Completed value ->
      let manager=S.manager value in
      Completed {manager;result=S.result value;records=obj [
        "candidate",Synthetic_authority.Candidate.to_json (S.candidate value);
        "selection_result",selection_json (S.selection_result value);
        "stages",stage_records labels manager]})
  | "run_component_pipeline" -> (match P.attempt ~budget ?until ?config request frames with
    | P.Failed failure -> Failed (failure.error,failure.manager)
    | P.Completed value ->
      let manager=P.manager value in
      Completed {manager;result=P.result value;records=obj [
        "candidate",Synthetic_authority.Candidate.to_json (P.candidate value);
        "assembly",Component_assembly.to_json (P.assembly value);
        "link_result",Composition_evidence.Result.to_json (P.link_result value);
        "behavior_result",Realization_evidence.Check_result.to_json (P.behavior_result value);
        "selection_result",selection_json (P.selection_result value);
        "stages",stage_records labels manager]})
  | _ -> failwith "Unreviewed fixed pipeline operation"
let original_result corpus case =
  let returned=doc corpus "result" case in
  require (text "$type" returned="dataclass") "Original build result lost its typed record";
  let expected_class=match text "api" case with
    | "run_synthetic_pipeline" -> "biocompiler.compiler.synthetic.SyntheticBuild"
    | "run_component_pipeline" -> "biocompiler.compiler.components.ComponentBuild"
    | _ -> failwith "Unexpected original pipeline operation" in
  require (text "class" returned=expected_class) "Original fixed build class differs";
  unpack (get "result" (get "fields" returned))
let eligible case =
  text "kind" case="actual_original_function" &&
  get "changed_bindings" case=Json.Array [] && get "python_only_inputs" case=Json.Array []
let run_case corpus cases case =
  let actual=execute (doc corpus "authority" case) (text "api" case) in
  let providers=get "providers" corpus.index and labels={values=[]} and aliases=alignment () in
  let retained=match actual with Completed value -> Some value.manager | Failed (_,manager) -> manager in
  (match get "manager_state" case,retained with
   | Json.Null,None -> ()
   | Json.String id,Some manager ->
     check_snapshot aliases providers labels manager (corpus.document id)
   | Json.Null,Some manager when text "api" case="run_component_pipeline" && text "outcome" case="raised" ->
     (* The outer Python frame never acquired a manager; the actual nested
        failing synthetic frame did. Bind the diagnostic extension to that
        complete original child observation, preserving the outer null. *)
     let children=List.filter (fun child -> get "parent" child=str (text "id" case)) cases in
     (match children with
      | [child] when text "api" child="run_synthetic_pipeline" && text "outcome" child="raised" ->
        equal "Original nested failure" (get "error" case) (get "error" child);
        check_snapshot aliases providers labels manager (doc corpus "manager_state" child)
      | _ -> failwith "No unique original nested synthetic failure state")
   | _ -> failwith (text "id" case ^ ": actual partial manager presence differs"));
  (match text "outcome" case,actual with
   | "returned",Completed value ->
     equal (text "id" case ^ " complete emitted records") (doc corpus "complete_records" case) value.records;
     equal (text "id" case ^ " complete pipeline result") (original_result corpus case)
       (C.Pipeline_result.to_json value.result)
   | "raised",Failed (cause,_) ->
     equal (text "id" case ^ " complete native exception") (unpack (get "error" case)) (error cause)
   | "returned",Failed (cause,_) ->
     failwith (text "id" case ^ ": unexpected native failure " ^ canonical (error cause))
   | "raised",Completed _ -> failwith (text "id" case ^ ": native pipeline accepted original rejection")
   | _ -> failwith "Unknown original fixed-pipeline outcome");
  retained,labels
let supported_api = function
  | "PassManager.get" | "PassManager.result" | "PassManager.set_dependency" | "PassManager.target" -> true
  | _ -> false
let invoke manager api bound = match api with
  | "PassManager.get" -> C.Stage_record.to_json (M.get manager (text "identity" bound))
  | "PassManager.result" -> C.Pipeline_result.to_json
      (M.result manager ~identity:(text "identity" bound) ~scope:(text "scope" bound))
  | "PassManager.set_dependency" ->
    M.set_dependency manager (text "key" bound) (text "identity" bound);Json.Null
  | "PassManager.target" -> Build_request.Target.to_json (M.target manager)
  | _ -> failwith "Callback-dependent continuation reached the supported prefix"
let continuation_observation corpus aliases labels manager expected_manager event =
  require (get "parent" event=Json.Null && text "manager" event=expected_manager)
    "Original continuation is not a top-level action on this live manager";
  let arguments=doc corpus "arguments" event in
  equal "Original continuation manager argument" (str expected_manager)
    (unpack (tagged_field "subject" arguments));
  let providers=get "providers" corpus.index in
  check_snapshot aliases providers labels manager (doc corpus "state_before" event);
  let actual=try Ok (invoke manager (text "api" event) (unpack (tagged_field "bound" arguments)))
    with Diagnostic.Error _ as cause -> Error (error cause) in
  (match text "outcome" event,actual with
   | "returned",Ok value -> equal (text "id" event ^ " full return") (unpack (doc corpus "result" event)) value
   | "raised",Error value -> equal (text "id" event ^ " full error") (get "error" event) value
   | "returned",Error value -> failwith (text "id" event ^ ": unexpected continuation error " ^ canonical value)
   | "raised",Ok _ -> failwith (text "id" event ^ ": original continuation rejection was accepted")
   | _ -> failwith "Unexpected original continuation outcome");
  check_snapshot aliases providers labels manager (doc corpus "state_after" event)
let continuations corpus case labels manager entry =
  equal "Continuation original case" (get "id" case) (get "case" entry);
  equal "Continuation operation" (get "api" case) (get "operation" entry);
  List.iter (fun key -> equal ("Continuation classification " ^ key) (get key case) (get key entry))
    ["kind";"changed_bindings";"python_only_inputs"];
  let events=Json.array (get "events" entry) in
  if get "boundary" entry=Json.Null then (
    require (text "outcome" case="raised" && events=[]) "Unexpected absent original return boundary";
    0,0)
  else (
    require (text "status" entry="complete_original_continuation" && text "outcome" case="returned")
      "Unexpected original continuation status";
    let manager=match manager with Some value -> value | None -> failwith "Completed pipeline lost its live manager" in
    let aliases=alignment () in
    let boundary=get "boundary" entry in
    (* Re-evaluate the actual scoped result that ended the original function.
       This additionally proves the returned live manager matches the old ledger. *)
    continuation_observation corpus aliases labels manager (text "manager" entry) boundary;
    let prefix=Json.array (get "supported_prefix_events" entry) in
    let suffix=Json.array (get "pending_callback_dependent_suffix" entry) in
    equal "Complete original continuation ordering" (Json.Array (List.map (get "id") events))
      (Json.Array (prefix @ suffix));
    let rec replay ids remaining = match ids,remaining with
      | [],rest -> rest
      | id::ids,event::rest ->
        equal "Original supported prefix identity" id (get "id" event);
        require (supported_api (text "api" event)) "Unsupported action advertised in native prefix";
        continuation_observation corpus aliases labels manager (text "manager" entry) event;
        replay ids rest
      | _ -> failwith "Incomplete original supported prefix" in
    let remaining=replay prefix events in
    (match remaining with [] -> () | event::_ ->
      require (not (supported_api (text "api" event))) "Supported action was silently withheld from native prefix");
    List.length prefix,List.length suffix)
let assert_count index key expected =
  equal ("Original census " ^ key) (Json.int expected) (get key (get "coverage" index))
let count items predicate = List.length (List.filter predicate items)
let assert_sources index =
  let sources=get "source_files" index in
  equal "Original synthetic pipeline source" (str "9ecf345ff5ea4da687b6344342862c68cd116296e01308f8d4c76d05dc091ff2")
    (get "src/biocompiler/compiler/synthetic.py" sources);
  equal "Original component pipeline source" (str "dc9edc3cb5fee5aef128a5a096ff6c20bfbf2af97f1077b74851a505d4b5d034")
    (get "src/biocompiler/compiler/components.py" sources)
let () =
  require (Array.length Sys.argv=3) "Expected fixed pipeline and continuation native corpus paths";
  let corpus=load ~schema:"biocompiler.fixed_pipeline_literals.v1"
    ~pin:"ce976b30aa5e0a8f6477cc027d7bec4a780a31a567f19cfb0993b10839d58f6d"
    ~directory:"fixed-pipeline-literals-v1" Sys.argv.(1) in
  let later=load ~schema:"biocompiler.fixed_pipeline_continuations.v1"
    ~pin:"45c78ef53692cb71fe644ea98331c9ce8caa1bda3b1eab67a93061f30557a9eb"
    ~directory:"checked-pipeline-v1" Sys.argv.(2) in
  equal "Complete original fixed ancestor" (str "28d8befb9fad240a80edf341ad64f822517f6e65f43c611966c9d0b7ff43d652")
    (get "inventory_fingerprint" (get "full_corpus" corpus.index));
  equal "Complete original continuation ancestor" (str "6b364ddf4b06140d788466fa7af5236ebfd3361854809d92d0ca99e0cac898f1")
    (get "inventory_fingerprint" (get "full_corpus" later.index));
  equal "Continuation binds full fixed corpus" (get "inventory_fingerprint" (get "full_corpus" corpus.index))
    (get "fixed_inventory_fingerprint" later.index);
  equal "Original manager ledger ancestor" (str "1b8ce09b5bb39e9bec43dae64c00291716a5971349eafd14c1f9f7e2a6bb6117")
    (get "prior_inventory_fingerprint" later.index);
  assert_sources corpus.index;assert_sources later.index;
  List.iter (fun (key,value) -> assert_count corpus.index key value)
    ["original_methods",467;"contexts",471;"cases",136;"documents",445;
     "document_bytes",104594191;"providers",458;"original_manager_constructors",309];
  List.iter (fun (key,value) -> assert_count later.index key value)
    ["cases",136;"returned_cases",124;"top_level_observations",850;
     "supported_prefix_observations",587;"pending_suffix_observations",263;
     "documents",1349;"document_bytes",78675553;"providers",430];
  let cases=Json.array (get "cases" corpus.index) in
  require (List.length cases=136 && List.length (Json.array (get "original_methods" corpus.index))=467)
    "Complete original method or call inventory changed";
  List.iter (fun (api,returned,raised) ->
    require (count cases (fun case -> eligible case && text "api" case=api && text "outcome" case="returned")=returned &&
      count cases (fun case -> eligible case && text "api" case=api && text "outcome" case="raised")=raised)
      "Actual original eligible call/outcome census changed")
    ["run_synthetic_pipeline",82,4;"run_component_pipeline",39,1];
  let pending_cases=List.filter (fun case -> not (eligible case)) cases in
  require (List.length pending_cases=10 &&
    count pending_cases (fun case -> get "changed_bindings" case=Json.Array [str "PassManager.register"])=6 &&
    count pending_cases (fun case -> get "python_only_inputs" case=Json.Array [str "config_python_type"])=3 &&
    count pending_cases (fun case -> text "kind" case="mocked_boundary")=1)
    "Original pending cases or exact reasons changed";
  let entries=Json.array (get "entries" later.index) in
  equal "Every original case has one complete continuation inventory"
    (Json.Array (List.map (get "id") cases)) (Json.Array (List.map (get "case") entries));
  let executed=ref 0 and prefix=ref 0 and suffix=ref 0 and withheld_prefix=ref 0 and withheld_suffix=ref 0 in
  List.iter2 (fun case entry ->
    if eligible case then (
      let manager,labels=run_case corpus cases case in
      incr executed;
      let done_count,pending_count=continuations later case labels manager entry in
      prefix:= !prefix+done_count;suffix:= !suffix+pending_count)
    else if get "boundary" entry<>Json.Null then (
      withheld_prefix:= !withheld_prefix+List.length (Json.array (get "supported_prefix_events" entry));
      withheld_suffix:= !withheld_suffix+List.length (Json.array (get "pending_callback_dependent_suffix" entry)))) cases entries;
  require (!executed=126 && !prefix=563 && !suffix=254 && !withheld_prefix=24 && !withheld_suffix=9)
    "Actual replay or explicitly pending continuation census changed";
  Printf.printf "Fixed pipelines: 126 real native runs (121 returned, 5 rejected), complete records/state/errors; 121 return-boundary rechecks and 563 continuation commands. Preserved pending: 6 patched-register, 3 Python-type, 1 mocked call; 254 callback-dependent suffix commands plus 24 prefix/9 suffix commands tied to patched calls. All 136 calls/850 continuations across 467 original methods retained.\n"
