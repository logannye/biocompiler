(* The framed engine receives original authority only. Historical expected
   records below are comparison data, never commands that install acceptance. *)
open Bioc_wire
module S = Bioc_pipeline_service.Session
let require condition message = if not condition then failwith message
let obj fields = Json.Object fields
let str value = Json.String value
let get key raw = Json.field key (Json.object_fields raw)
let text key raw = Json.string (get key raw)
let integer key raw = Z.to_int (Json.integer (get key raw))
let set key value raw = obj ((key,value)::List.remove_assoc key (Json.object_fields raw))
let canonical raw = Canonical.encode_bounded ~max_bytes:67_108_864 raw
let equal label left right = require (canonical left=canonical right) label
let read path =
  let channel=open_in_bin path in
  Fun.protect (fun () -> really_input_string channel (in_channel_length channel))
    ~finally:(fun () -> close_in channel)
let parse raw = Json.parse_artifact ~max_bytes:67_108_864 ~max_nodes:1_000_000 raw
let session_id = "01234567-89ab-cdef-0123-456789abcdef"
let limits = get "limits" S.declaration
let manager_limits = get "manager_limits" S.declaration
let hello limits manager_limits = obj ["profile",str S.profile;"limits",limits;"manager_limits",manager_limits]
let request ?(identity=session_id) sequence operation payload =
  obj ["protocol",str S.protocol;"session_id",str identity;"sequence",Json.int sequence;
    "operation",str operation;"payload",payload]
let raw_exchange state raw =
  try S.reserve_frame state (String.length raw);S.handle_frame state raw
  with Diagnostic.Error _ -> S.abort ~unbound:true state
let exchange ?identity state sequence operation payload =
  let raw=canonical (request ?identity sequence operation payload) in
  let response=raw_exchange state raw in
  let value=parse response.bytes in
  equal "Response protocol differs" (get "protocol" value) (str S.protocol);
  equal "Response profile differs" (get "profile" value) (str S.profile);
  require (response.closed=Json.boolean (get "closed" value) && response.closed=S.is_closed state)
    "Response closure differs from actual native session";
  if get "sequence" value<>Json.Null then (
    equal "Response sequence differs" (get "sequence" value) (Json.int sequence);
    equal "Response operation differs" (get "operation" value) (str operation);
    equal "Response exact request bytes are unbound" (get "request_sha256" value) (str (Canonical.sha256 raw)));
  value
let successful response =
  require (text "status" response="ok") ("Unexpected session rejection: " ^ canonical response);
  require (get "diagnostics" response=Json.Array [] && get "exception" response=Json.Null)
    "Successful session response carried an exception";
  get "result" response
let alive_error response =
  require (text "status" response="error" && not (Json.boolean (get "closed" response)))
    "Expected logical error must preserve actual manager"
let fatal response =
  require (text "status" response="error" && Json.boolean (get "closed" response))
    "Expected terminal session failure";
  require (String.length (canonical response)+9<=8192) "Terminal response exceeded prepaid bytes";
  require (get "result" response=Json.Null) "Fatal session supplied a successful artifact"
let start ?(controls=Json.Null) ?(manager=Json.Null) () =
  let state=S.create () in
  let response=exchange state 0 "hello" (hello controls manager) in
  let value=successful response in
  equal "Hello did not bind complete declaration" (get "profile" value) S.declaration;
  equal "Effective session limits differ" (get "limits" value) (if controls=Json.Null then limits else controls);
  equal "Effective manager limits differ" (get "manager_limits" value) (if manager=Json.Null then manager_limits else manager);
  state,response
let body raw = obj ["schema_version",str "session.literal.v1";"target",raw;"value",Json.int 7]
let empty target document = obj ["target",target;
  "dependencies",Json.Array [Json.Array [str "request";str (Canonical.sha256 (canonical document))]];
  "completion_profiles",Json.Array []]
let add document identity = obj ["identity",str identity;"stage",str (Bioc_domain.Pipeline_contract.stage_name Bioc_domain.Pipeline_contract.Intent);
  "requirements",Json.Array [];"obligations",Json.Array [];"document",document]
let load_cases path =
  let corpus=parse (read path) in
  equal "Session test lost original fixed corpus pin" (get "inventory_fingerprint" corpus)
    (str "ce976b30aa5e0a8f6477cc027d7bec4a780a31a567f19cfb0993b10839d58f6d");
  equal "Session original corpus content differs" (get "inventory_fingerprint" corpus)
    (str (Canonical.sha256 (canonical (obj (List.remove_assoc "inventory_fingerprint" (Json.object_fields corpus))))));
  let directory=Filename.concat (Filename.dirname path) (text "document_directory" corpus) in
  let document id =
    require (String.length id=64 && String.for_all (function '0'..'9'|'a'..'f' -> true | _ -> false) id)
      "Invalid original document reference";
    let descriptor=List.find (fun raw -> text "id" raw=id) (Json.array (get "documents" corpus)) in
    let bytes=read (Filename.concat directory (id ^ ".json")) in
    let raw=parse bytes in
    require (String.length bytes=integer "bytes" descriptor && bytes=canonical raw ^ "\n" &&
      Canonical.sha256 (canonical raw)=id) "Original authority or comparison document changed";
    raw in
  let eligible raw = text "kind" raw="actual_original_function" &&
    get "changed_bindings" raw=Json.Array [] && get "python_only_inputs" raw=Json.Array [] in
  List.filter eligible (Json.array (get "cases" corpus)),document
let find_case cases api outcome partial =
  List.find (fun raw -> text "api" raw=api && text "outcome" raw=outcome &&
    (not partial || get "manager_state" raw<>Json.Null)) cases
let () =
  require (Array.length Sys.argv=3) "Expected session declaration and original fixed corpus paths";
  equal "Native session declaration differs from external contract" S.declaration (parse (read Sys.argv.(1)));
  let cases,document=load_cases Sys.argv.(2) in
  let synthetic=find_case cases "run_synthetic_pipeline" "returned" false in
  let component=find_case cases "run_component_pipeline" "returned" false in
  let rejected=find_case cases "run_synthetic_pipeline" "raised" true in
  let authority case=document (text "authority" case) in
  let target=get "target" (get "build_request" (get "request" (authority synthetic))) in
  let input=body target in
  let state,first=start () in
  let second=exchange state 1 "initialize-empty" (empty target input) in
  ignore (successful second);
  let added=successful (exchange state 2 "add-input" (add input "root")) in
  equal "Root payload changed" (get "payload" added) input;
  equal "Live root retrieval changed" (successful (exchange state 3 "get" (obj ["identity",str "root"]))) added;
  let missing=exchange state 4 "get" (obj ["identity",str "absent"]) in
  alive_error missing;
  equal "Logical failure class differs" (get "type" (get "exception" missing)) (str "PipelineError");
  equal "Logical error destroyed manager" (successful (exchange state 5 "target" (obj []))) target;
  ignore (successful (exchange state 6 "set-dependency" (obj ["key",str "request";
    "identity",str (Canonical.sha256 "changed")])));
  let stale=exchange state 7 "get" (obj ["identity",str "root"]) in
  alive_error stale;
  let inspect=successful (exchange state 8 "inspect" (obj [])) in
  equal "Failed freshness check erased historical record" (get "root" (get "records" inspect)) added;
  let closed=exchange state 9 "close" (obj []) in
  ignore (successful closed);require (Json.boolean (get "closed" closed)) "Close retained live authority";
  require (integer "work_charged" (get "usage" second)>integer "work_charged" (get "usage" first) &&
    integer "work_remaining" (get "usage" closed)<integer "work_remaining" (get "usage" second))
    "Session command reset its lifetime work allowance";
  (* Native fixed providers and independent validators actually run; changing a
     dependency invalidates fresh access while immutable emitted artifacts stay
     available as historical data. *)
  let run_fixed case operation controls =
    let state,_=start ~controls () in
    let initialized=exchange state 1 operation (authority case) in
    state,initialized in
  let state,initialized=run_fixed synthetic "initialize-synthetic" Json.Null in
  ignore (successful initialized);
  let snapshot=successful (exchange state 2 "inspect" (obj [])) in
  let expected=document (text "complete_records" synthetic) in
  equal "Actual fixed records differ" (get "records" snapshot) (get "stages" expected);
  let candidate=successful (exchange state 3 "artifact" (obj ["name",str "candidate"])) in
  equal "Actual fixed artifact differs" candidate (get "candidate" expected);
  let current=successful (exchange state 4 "result" (obj ["identity",str "mechanism";"scope",str "synthetic_realization"])) in
  equal "Emitted result differs from fresh manager result" current
    (successful (exchange state 5 "artifact" (obj ["name",str "pipeline_result"])));
  let sequence=ref 6 in
  List.iter (fun pass ->
    let registration=get pass (get "passes" snapshot) in
    require (String.starts_with ~prefix:"provider/" (text "producer" registration))
      "Provider diagnostics lost process-local labels") ["intent_to_behavior";"behavior_to_synthetic"];
  let request operation payload = let reply=exchange state !sequence operation payload in incr sequence;reply in
  equal "Repeated inspection changed physical provider labels" snapshot (successful (request "inspect" (obj [])));
  ignore (successful (request "set-dependency" (obj ["key",str "model";"identity",str (Canonical.sha256 "changed-model")])));
  alive_error (request "result" (obj ["identity",str "mechanism";"scope",str "synthetic_realization"]));
  equal "Immutable artifact was relabeled as fresh or lost" candidate
    (successful (request "artifact" (obj ["name",str "candidate"])));
  ignore (successful (request "close" (obj [])));
  (* Partial failure is actual retained state, including rejected records. *)
  let state,rejection=run_fixed rejected "initialize-synthetic" Json.Null in
  alive_error rejection;
  equal "Original partial failure message changed" (get "message" (get "exception" rejection))
    (get "message" (get "error" rejected));
  let partial=successful (exchange state 2 "inspect" (obj [])) in
  require (List.mem_assoc "mechanism" (Json.object_fields (get "records" partial)))
    "Rejected candidate was rolled back from the real manager";
  require (not (Json.boolean (get "accepted" (get "mechanism" (get "records" partial)))))
    "Rejected candidate was promoted by session transport";
  alive_error (exchange state 3 "get" (obj ["identity",str "mechanism"]));
  equal "Failure lost root target" target (successful (exchange state 4 "target" (obj [])));
  let duplicate=exchange state 5 "initialize-synthetic" (authority synthetic) in alive_error duplicate;
  equal "Second initialization replaced partial manager" partial (successful (exchange state 6 "inspect" (obj [])));
  ignore (successful (exchange state 7 "close" (obj [])));
  (* Data cannot register checkers or import historical accepted state. The
     unsupported command consumes its sequence but keeps the actual manager. *)
  let state,_=start () in
  ignore (successful (exchange state 1 "initialize-empty" (empty target input)));
  let before=successful (exchange state 2 "inspect" (obj [])) in
  let denied=exchange state 3 "register" (obj ["accepted",Json.Bool true;"records",get "records" snapshot]) in
  require (text "status" denied="unsupported" && not (Json.boolean (get "closed" denied)))
    "Wire data installed unsupported provider authority";
  equal "Unsupported registration mutated manager" before (successful (exchange state 4 "inspect" (obj [])));
  ignore (successful (exchange state 5 "close" (obj [])));
  (* Transport's declared million key/value nodes are distinct from the
     manager's smaller per-document profile. A large rejected proposal is still
     completely parsed under the transport budget; it grants no authority. *)
  let state,_=start () in
  let rejected=exchange state 1 "unknown-operation" (Json.Array (List.init 250_001 (fun _ -> Json.Null))) in
  require (text "status" rejected="unsupported" && not (Json.boolean (get "closed" rejected)))
    "Session silently inherited the one-shot 250000-node ceiling";
  ignore (successful (exchange state 2 "close" (obj [])));
  let state,_=start ~controls:(set "max_json_nodes" (Json.int 4096) limits) () in
  let excessive=obj (List.init 2048 (fun index -> string_of_int index,Json.Null)) in
  fatal (exchange state 1 "unknown-operation" excessive);
  (* Retained byte accounting includes derived component closure authority even
     before success, and does not use the manager's separate record allowance. *)
  let state,built=run_fixed component "initialize-components" Json.Null in
  ignore (successful built);
  let retained=integer "retained_bytes" (get "usage" built) in
  require (retained>=33_554_432) "Adapted closure capture escaped session retention";
  ignore (successful (exchange state 2 "close" (obj [])));
  let state,exact=run_fixed component "initialize-components" (set "max_retained_bytes" (Json.int retained) limits) in
  ignore (successful exact);
  require (integer "retained_bytes" (get "usage" exact)=retained) "Exact retention allowance changed accounting";
  ignore (successful (exchange state 2 "close" (obj [])));
  let _,short=run_fixed component "initialize-components" (set "max_retained_bytes" (Json.int (retained-1)) limits) in fatal short;
  (* A genuine component assembly exceeds a reduced leaf serialization cap
     even though the identical upstream synthetic build fits. The failure must
     terminate the session, not be presented as a recoverable semantic error. *)
  let expected_component=document (text "complete_records" component) in
  let assembly_limit=String.length (canonical (get "assembly" expected_component))-1 in
  let reduced_manager=set "max_document_bytes" (Json.int assembly_limit) manager_limits in
  let state,_=start ~manager:reduced_manager () in
  ignore (successful (exchange state 1 "initialize-synthetic" (authority component)));
  ignore (successful (exchange state 2 "close" (obj [])));
  let state,_=start ~manager:reduced_manager () in
  fatal (exchange state 1 "initialize-components" (authority component));
  (* Domain graph capacity is stricter than this small transport document. This
     reaches Intent.of_json's native intent_node_limit before malformed element
     decoding, and exercises fatal handling of a nested domain resource code. *)
  let too_many_nodes=Json.Array (List.init 50_001 (fun _ -> Json.Null)) in
  let original=authority synthetic in
  let realization=get "request" original in
  let build=get "build_request" realization in
  let oversized_intent=set "nodes" too_many_nodes (get "intent" build) in
  let invalid=set "request" (set "build_request" (set "intent" oversized_intent build) realization) original in
  let state,_=start () in
  fatal (exchange state 1 "initialize-synthetic" invalid);
  (* Replay, sequence gaps, identity changes and duplicate hello are fatal. *)
  List.iter (fun (sequence,identity,operation,payload) ->
    let state,_=start () in fatal (exchange ~identity state sequence operation payload))
    [0,session_id,"target",obj [];2,session_id,"target",obj [];
     1,"abcdef01-2345-6789-abcd-ef0123456789","target",obj [];
     1,session_id,"hello",hello Json.Null Json.Null];
  let state=S.create () in fatal (exchange state 0 "target" (obj []));
  List.iter (fun raw -> let state=S.create () in fatal (parse (raw_exchange state raw).bytes))
    ["{";"{}";"{\"protocol\":null,\"protocol\":null}";"[]"];
  let state=S.create () in S.reserve_frame state 1;
  fatal (parse (S.handle_frame state "{}").bytes);
  List.iter (fun size ->
    let state=S.create () in
    (match S.reserve_frame state size with
     | () -> failwith "Invalid frame size was reserved"
     | exception Diagnostic.Error _ -> ());
    fatal (parse (S.abort ~unbound:true state).bytes)) [0;S.maximum_frame_bytes+1];
  (* Complete positive reductions only, with hello prefix and prepaid terminal
     work/bytes charged before negotiated limits can be installed. *)
  List.iter (fun controls -> let state=S.create () in
    fatal (exchange state 0 "hello" (hello controls Json.Null)))
    [obj [];set "max_work" (Json.int 1) limits;set "max_work" (Json.int 0) limits;
     set "max_frame_bytes" (Json.int 1) limits;set "max_json_nodes" (Json.int 1) limits;
     set "max_total_bytes" (Json.int 8192) limits];
  let state,_=start ~controls:(set "max_commands" (Json.int 2) limits) () in
  ignore (successful (exchange state 1 "initialize-empty" (empty target input)));
  fatal (exchange state 2 "target" (obj []));
  let state,_=start ~manager:(set "max_records" (Json.int 1) manager_limits) () in
  ignore (successful (exchange state 1 "initialize-empty" (empty target input)));
  ignore (successful (exchange state 2 "add-input" (add input "first")));
  fatal (exchange state 3 "add-input" (add input "second"));
  (* Determine the exact work boundary from real metered execution. Updating
     only the declared integer may lower its encoding charge; iterate until the
     complete five-command transcript consumes its entire allowance. *)
  let work_trial maximum =
    let state=S.create () in
    let commands=["hello",hello (set "max_work" (Json.int maximum) limits) Json.Null;
      "initialize-empty",empty target input;"get",obj ["identity",str "missing"];
      "target",obj [];"close",obj []] in
    let rec run index = function
      | [] -> failwith "Missing closing command"
      | (operation,payload)::rest ->
        let reply=exchange state index operation payload in
        if Json.boolean (get "closed" reply) && operation<>"close" then None
        else if rest=[] then
          if text "status" reply="ok" then Some (integer "work_charged" (get "usage" reply)) else None
        else run (index+1) rest in
    run 0 commands in
  let rec exact_work count maximum =
    require (count<16) "Exact session work boundary did not converge";
    match work_trial maximum with
    | None -> failwith "Measured complete session work became insufficient"
    | Some used when used=maximum -> maximum
    | Some used -> require (used<maximum) "Session overran its lifetime budget";exact_work (count+1) used in
  let exact=exact_work 0 (integer "max_work" limits) in
  require (work_trial exact=Some exact) "Exact lifetime budget was rejected";
  require (work_trial (exact-1)=None) "One-short lifetime budget was accepted";
  print_endline "Native persistent session identity, live fixed authority, partial errors, freshness, retention and lifetime limits passed."
