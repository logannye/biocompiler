open Bioc_wire
module K = Bioc_producer_service.Synthetic_inspection_service
module W = Bioc_checker.Work_budget
let require condition message = if not condition then failwith message
let get key raw = Json.field key (Json.object_fields raw)
let set key value raw = Json.Object ((key,value)::List.remove_assoc key (Json.object_fields raw))
let same left right = Canonical.encode left=Canonical.encode right
let string value = Json.String value
let read path = let channel = open_in_bin path in
  let bytes = really_input_string channel (in_channel_length channel) in close_in channel; Json.parse bytes
let run ?parent operation payload =
  K.handle ?parent ~executable:Protocol.Core ~request_id:"inspection-test" ~operation payload
let rejected action = match action () with
  | _ -> failwith "Malformed or exhausted inspection accepted"
  | exception Diagnostic.Error _ -> ()
let expected fixture =
  let payload=get "payload" fixture and value=get "expected_value" fixture in
  let operation=get "operation" fixture in
  let fields=List.filter (fun (key,_) -> key<>"profile" && key<>"limits") (Json.object_fields payload) in
  Json.Object ["schema_version",get "result_schema" K.profile;"profile",get "profile" K.profile;
    "service_implementation",get "implementation" K.profile;"operation",operation;
    "resources",get "resources" K.profile;"validation_scope",get "validation_scope" K.profile;
    "claim_scope",get "claim_scope" K.profile;
    "supplied_authority_fingerprint",string (Canonical.fingerprint payload);
    "input_fingerprints",Json.Object (List.map (fun (key,value)->key,string (Canonical.fingerprint value)) fields);
    "value",value;"value_fingerprint",string (Canonical.fingerprint value)]
let literals fixtures =
  let seen=Hashtbl.create 8 in
  List.iter (fun fixture ->
    let operation=Json.string (get "operation" fixture) and payload=get "payload" fixture in
    Hashtbl.replace seen operation ();
    let id=Json.string (get "id" fixture) in
    match get "error" fixture with
    | Json.Null -> require (same (run operation payload) (expected fixture)) (id^": full original helper result differs")
    | error -> (match run operation payload with
        | _ -> failwith (id^": original rejection accepted")
        | exception Diagnostic.Error actual ->
          let path=match actual.path with None->Json.Null | Some value->string value in
          require (same (Json.Object ["code",string actual.code;"message",string actual.message;"path",path]) error)
            (id^": original error code/message/path differs: "^actual.message))) fixtures;
  require (List.for_all (Hashtbl.mem seen) K.operations) "An inspection operation has no complete original fixture";
  List.iter (fun operation ->
    match K.handle ~executable:Protocol.Verify ~request_id:"inspection-test" ~operation Json.Null with
    | _ -> failwith "Verifier performed producer-only helper"
    | exception Diagnostic.Error error -> require (error.code="unsupported_operation") "Wrong verifier role rejection") K.operations
let limits fixtures =
  let fixture=List.find (fun f->get "operation" f=string "inspect-synthetic-mechanism") fixtures in
  let operation=Json.string (get "operation" fixture) and payload=get "payload" fixture in
  let defaults=get "default_limits" K.profile in
  let _,usage=K.handle_with_usage ~executable:Protocol.Core ~request_id:"inspection-test" ~operation payload in
  let parent maximum=W.create ~profile:"inspection.parent" ~error_code:"inspection_parent_exhausted" ~maximum () in
  let exact=parent usage.work_charged in
  require (same (run ~parent:exact operation payload) (expected fixture) && W.remaining exact=0)
    "Inspection framing/import/helper/hash/final response escaped its ancestor";
  let short=parent (usage.work_charged-1) in
  (match run ~parent:short operation payload with
   | _ -> failwith "Inspection exceeded ancestor budget"
   | exception Diagnostic.Error error -> require (W.is_exhaustion short error && error.code="inspection_parent_exhausted")
       "Inspection obscured ancestor exhaustion");
  List.iter (fun key ->
    let ceiling=Z.to_int (Json.integer (get key defaults)) in
    let with_limit value=set "limits" (set key (Json.int value) defaults) payload in
    let accepts value=match run operation (with_limit value) with _->true | exception Diagnostic.Error _->false in
    require (not (accepts 1) && accepts ceiling) (key^": resource ceiling not applied");
    let rec find low high=if high-low<=1 then high else let mid=(low+high)/2 in
      if accepts mid then find low mid else find mid high in
    let boundary=find 1 ceiling in
    require (boundary<ceiling && accepts boundary && not (accepts (boundary-1)))
      (key^": positive reduced success and adjacent exhaustion absent");
    let value=run operation (with_limit boundary) in
    require (get key (get "protocol" (get "resources" value))=Json.int boundary)
      (key^": selected resource profile was not published"))
    ["max_work";"max_monitor_items";"max_request_bytes";"max_report_bytes";"max_report_nodes"];
  List.iter (fun invalid -> rejected (fun ()->run operation (set "limits" invalid payload)))
    [Json.Bool true;Json.Array [];Json.Object [];set "max_work" (Json.Float 50000000.) defaults;
     set "max_work" (Json.int 0) defaults;set "max_report_nodes" (Json.int 250001) defaults];
  rejected (fun ()->run operation (set "profile" (string "future") payload));
  rejected (fun ()->run operation (set "unexpected" Json.Null payload));
  rejected (fun ()->run operation (Json.Object (("profile",get "profile" payload)::Json.object_fields payload)));
  let changed=set "mechanism" (set "name" (string "different supplied name") (get "mechanism" payload)) payload in
  let a=run operation payload and b=run operation changed in
  require (same (get "value" a) (get "value" b) && get "supplied_authority_fingerprint" a<>get "supplied_authority_fingerprint" b &&
    get "input_fingerprints" a<>get "input_fingerprints" b) "Unchanged helper value erased changed supplied authority";
  let rec cyclic=Json.Array [cyclic] in rejected (fun ()->run operation (set "mechanism" cyclic payload));
  let rec spine=Json.Null::spine in rejected (fun ()->run operation (set "mechanism" (Json.Array spine) payload));
  rejected (fun ()->run operation (set "mechanism" (string "\255") payload));
  rejected (fun ()->run "unknown-inspection" payload)
let () =
  require (Array.length Sys.argv=3) "Expected supplemental fixture and protocol declaration paths";
  let corpus=read Sys.argv.(1) and declaration=read Sys.argv.(2) in
  require (same declaration K.profile) "Embedded inspection capability declaration differs from immutable protocol";
  let fixtures=Json.array (get "cases" corpus) in
  require (List.length fixtures=28) "Complete supplemental fixture census changed";
  literals fixtures;limits fixtures;
  print_endline "Synthetic inspection protocol: complete literal helpers, role separation, identity and five bounded controls passed"
