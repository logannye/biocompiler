(* Execute source-pinned original comparison bodies against a live manager.
   Captured records, decisions and states are comparison data, never inputs to
   registration or acceptance. Provider labels identify distinct native closures. *)
open Bioc_wire
module C = Bioc_domain.Pipeline_contract
module M = Bioc_compiler.Pass_manager
module W = Bioc_checker.Work_budget
let require condition message = if not condition then failwith message
let get key raw = Json.field key (Json.object_fields raw)
let text key raw = Json.string (get key raw)
let obj fields = Json.Object fields
let str value = Json.String value
let canonical = Canonical.encode_bounded ~max_bytes:16_777_216
let equal label expected actual =
  require (canonical expected=canonical actual)
    (label ^ ": original observation differs\nexpected=" ^ canonical expected ^ "\nactual=" ^ canonical actual)
let read path =
  let channel=open_in_bin path in
  Fun.protect (fun () -> really_input_string channel (in_channel_length channel))
    ~finally:(fun () -> close_in channel)
let budget maximum = W.create ~profile:"provider_comparison.original"
    ~error_code:"provider_comparison_work" ~maximum ()
let maximum_work = 1_000_000_000
exception Comparison_error of string
let error = function
  | Comparison_error message -> obj ["module",str "builtins";"type",str "ValueError";"message",str message]
  | Diagnostic.Error value ->
    let owner,kind=match value.code with
      | "pipeline_error" -> "biocompiler.compiler.pipeline","PipelineError"
      | "pipeline_serialization" | "pipeline_contract" -> "biocompiler.errors","SerializationError"
      | _ -> raise (Diagnostic.Error value) in
    obj ["module",str owner;"type",str kind;"message",str value.message]
  | value -> raise value
let provider label : M.provider =
  let identity=ref label in
  fun _ _ -> failwith ("Comparison-only fixture unexpectedly invoked provider " ^ !identity)
let providers case = List.map (fun (label,_) -> label,provider label)
    (Json.object_fields (get "providers" case))
let label values callback = match List.find_opt (fun (_,other) -> callback==other) values with
  | Some (label,_) -> label | None -> failwith "Native manager retained an uninventoried provider"
let keys raw = Json.Array (List.map (fun (key,_) -> str key) (Json.object_fields raw))
let snapshot manager values =
  let state=M.inspect manager ~provider_identity:(label values) in
  let pass_history=get "provider_history" state and admission_history=get "component_input_history" state in
  (* This original cohort has either pass or admission registrations. A mixed
     history requires its own interleaving observation and is not synthesized. *)
  require (Json.object_fields pass_history=[] || Json.object_fields admission_history=[])
    "Unreviewed mixed comparison history";
  let combined=List.map (fun (key,_) -> str key) (Json.object_fields pass_history) @
    List.map (fun (key,_) -> Json.Array [str "component_input";str key]) (Json.object_fields admission_history) in
  let validator_order=obj (List.map (fun field -> field,
    obj (List.map (fun (key,value) -> key,keys (get "validators" value))
      (Json.object_fields (get field state))))
    ["passes";"component_inputs";"provider_history";"component_input_history"]) in
  let order=obj (List.filter_map (fun (key,value) ->
    if key="target" then None else Some (key,keys value)) (Json.object_fields state) @
    ["combined_provider_history",Json.Array combined;"validators",validator_order]) in
  obj ["state",state;"order",order]
let create ?limits ?validator_equivalent work setup =
  let dependencies=get "dependencies" setup in
  let dependencies=List.map (fun key -> key,text key dependencies) ["request";"registry"] in
  let manager=M.create ~budget:work ?limits ?validator_equivalent
    ~target:(Bioc_domain.Build_request.Target.of_json (get "target" setup)) ~dependencies
    ~completion_profiles:(List.map (fun raw -> C.Completion_profile.of_json raw)
      (Json.array (get "profiles" setup))) () in
  (match get "input" setup with
   | Json.Null -> ()
   | raw -> ignore (M.add_input manager ~identity:(text "input_id" setup)
       ~requirements:(List.map Json.string (Json.array (get "requirements" setup)))
       ~obligations:(List.map (fun raw -> C.Scoped_obligation.of_json raw)
         (Json.array (get "obligations" setup))) raw));
  manager
let execute manager setup values recipe =
  let lookup id=List.assoc id values in
  let validators ()=List.map (function Json.Array [key;value] -> Json.string key,lookup (Json.string value)
    | _ -> failwith "Invalid original validator registration") (Json.array (get "validators" recipe)) in
  let contract ()=get (text "contract" recipe) (get "contracts" setup) in
  match text "operation" recipe with
  | "register" -> M.register manager (C.Pass_contract.of_json (contract ()))
      ~producer:(lookup (text "producer" recipe)) ~validators:(validators ());Json.Null
  | "register_component_input" ->
    M.register_component_input manager (C.Component_input_contract.of_json (contract ()))
      ~validators:(validators ());Json.Null
  | "set_dependency" -> M.set_dependency manager (text "key" recipe) (text "identity" recipe);Json.Null
  | "target" -> Bioc_domain.Build_request.Target.to_json (M.target manager)
  | "get" -> C.Stage_record.to_json (M.get manager (text "identity" recipe))
  | _ -> failwith "Unreviewed original comparison effect"
let replay ?(maximum=maximum_work) case =
  let work=budget maximum and values=providers case and setup=get "setup" case in
  let current=ref None and next=ref 0 and stack=ref [] in
  let events=Array.of_list (Json.array (get "events" case)) in
  let manager ()=match !current with Some value -> value | None -> failwith "Comparison before manager creation" in
  let observe kind recipe action =
    require (!next<Array.length events) "Uncaptured native comparison/manager action";
    let event=events.(!next) in
    let id=Json.int !next in incr next;
    equal "Original event identity" (get "id" event) id;
    equal "Original callback nesting" (get "parent" event)
      (match !stack with [] -> Json.Null | parent::_ -> parent);
    equal "Original action kind" (get "kind" event) (str kind);
    equal "Original action recipe" (get "recipe" event) recipe;
    equal "Complete state before action" (get "before" event) (snapshot (manager ()) values);
    stack:=id:: !stack;
    Fun.protect (fun () ->
      let outcome=try Ok (action ()) with
        | Diagnostic.Error diagnostic when W.is_exhaustion work diagnostic -> raise (Diagnostic.Error diagnostic)
        | (Diagnostic.Error _ | Comparison_error _) as cause -> Error cause in
      equal "Complete state after action" (get "after" event) (snapshot (manager ()) values);
      match outcome with
      | Ok result ->
        require (text "outcome" event="returned") "Native comparator accepted an original rejection";
        equal "Complete original action result" (get "result" event) result;result
      | Error cause ->
        require (text "outcome" event="raised") "Unexpected native comparator rejection";
        equal "Complete original action exception" (get "error" event) (error cause);raise cause)
      ~finally:(fun () -> match !stack with _::rest -> stack:=rest | [] -> assert false) in
  let descriptors=get "providers" case in
  let descriptor id=get id descriptors in
  let rec operation recipe = observe "manager" recipe (fun () -> execute (manager ()) setup values recipe)
  and comparison left right =
    let details=descriptor left in
    match text "kind" details with
    | "comparable" | "comparable_subclass" ->
      let result=observe "comparison" (obj ["left",str left;"right",str right]) (fun () ->
        List.iter (fun action -> ignore (operation action)) (Json.array (get "actions" details));
        match text "equality" details with
        | "true" -> Json.Bool true | "false" -> Json.Bool false
        | "not_implemented" -> obj ["python_singleton",str "NotImplemented"]
        | "raise" -> raise (Comparison_error ("Original comparator rejected " ^ left))
        | _ -> failwith "Unreviewed comparator body") in
      (match result with Json.Bool value -> Some value | _ -> None)
    | "bound_method" ->
      let other=descriptor right in
      if text "kind" other="bound_method" then
        Some (text "owner" details=text "owner" other && text "method" details=text "method" other)
      else None
    | "producer" | "identity_only" -> None
    | _ -> failwith "Unreviewed callable equality type"
  in
  let equivalent received left right =
    require (received==work) "Comparator received a fresh work ancestor";
    W.charge received 7;
    let left=label values left and right=label values right in
    (* Source-pinned ComparableSubclass has Python's right-subtype precedence;
       NotImplemented tries the other operand without inventing equivalence. *)
    let reflected=text "kind" (descriptor left)="comparable" &&
      text "kind" (descriptor right)="comparable_subclass" in
    let first,second=if reflected then right,left else left,right in
    match comparison first second with
    | Some value -> value
    | None -> (match comparison second first with Some value -> value | None -> false) in
  let native=create ~validator_equivalent:equivalent work setup in
  current:=Some native;
  equal "Complete initial manager" (get "initial_state" case) (snapshot native values);
  List.iter (fun action ->
    try ignore (operation action) with
    | Diagnostic.Error diagnostic when W.is_exhaustion work diagnostic -> raise (Diagnostic.Error diagnostic)
    | Diagnostic.Error _ | Comparison_error _ -> ()) (Json.array (get "actions" case));
  require (!next=Array.length events && !stack=[]) "Original comparator events were omitted";
  equal "Complete final manager" (get "final_state" case) (snapshot native values);
  maximum-W.remaining work
let rejected code action = match action () with
  | _ -> failwith ("Expected native rejection " ^ code)
  | exception Diagnostic.Error diagnostic -> require (diagnostic.code=code) ("Wrong rejection " ^ diagnostic.code)
let extra_controls case =
  let setup=get "setup" case and values=providers case in
  let actions=Json.array (get "actions" case) in
  require (List.length actions=2) "Unexpected equivalent-provider fixture";
  let first=List.hd actions and second=List.nth actions 1 in
  let native=create (budget maximum_work) setup in
  ignore (execute native setup values first);
  rejected "pipeline_error" (fun () -> execute native setup values second);
  let work=budget maximum_work in
  let native=create ~limits:(M.make_limits ~max_providers:2 ())
      ~validator_equivalent:(fun received _ _ -> require (received==work) "Changed comparator budget";true)
      work setup in
  ignore (execute native setup values first);
  rejected "pipeline_provider_limit" (fun () -> execute native setup values second);
  let original=Comparison_error "Keep the exact exception value." in
  let native=create ~validator_equivalent:(fun _ _ _ -> raise original) (budget maximum_work) setup in
  ignore (execute native setup values first);
  (match execute native setup values second with
   | _ -> failwith "Comparator exception was swallowed"
   | exception cause -> require (cause==original) "Comparator exception identity changed");
  let active=ref None in
  let native=create ~limits:(M.make_limits ~max_call_depth:3 ())
      ~validator_equivalent:(fun _ _ _ ->
        ignore (execute (Option.get !active) setup values second);true) (budget maximum_work) setup in
  active:=Some native;ignore (execute native setup values first);
  rejected "pipeline_recursion_limit" (fun () -> execute native setup values second);
  let used=replay case in
  require (used>0 && used<maximum_work) "Meaningless comparator lifetime measurement";
  require (replay ~maximum:used case=used) "Exact shared comparator budget changed";
  rejected "provider_comparison_work" (fun () -> replay ~maximum:(used-1) case)
let () =
  require (Array.length Sys.argv=2) "Expected independently captured provider-comparison fixture";
  let bytes=read Sys.argv.(1) in
  let fixture=Json.parse_bounded ~max_bytes:16_777_216 ~max_nodes:1_000_000 bytes in
  require (bytes=canonical fixture ^ "\n") "Original comparator fixture bytes changed";
  require (text "schema_version" fixture="biocompiler.pipeline_callback_semantics.v1") "Unexpected comparator fixture schema";
  let pin=text "inventory_fingerprint" fixture in
  require (pin="81462d7732ba6205791831030b21ebcbaa3f8d4c58837deb38d072b3e1025d45" &&
    pin=Canonical.sha256 (canonical (obj (List.remove_assoc "inventory_fingerprint" (Json.object_fields fixture)))))
    "Pinned original comparator inventory changed";
  equal "Original comparison census" (obj ["cases",Json.int 34;"comparison_events",Json.int 28;
    "manager_events",Json.int 78;"raised_events",Json.int 18]) (get "coverage" fixture);
  let cases=Json.array (get "cases" fixture) in
  require (List.length cases=34) "Original comparator cases were omitted";
  List.iter (fun case -> ignore (replay case)) cases;
  extra_controls (List.find (fun case -> text "id" case="pass:equal") cases);
  print_endline "Provider comparison: all 34 original cases and 106 nested events match complete states/results/errors; physical identity, reentrancy, retention and exact lifetime bounds checked."
