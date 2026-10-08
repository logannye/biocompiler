open Bioc_wire
module D = Bioc_domain.Policy_document
module O = Bioc_domain.Policy_operational
module A = Bioc_checker.Policy_admission
module C = Bioc_checker.Policy_correspondence
module L = Bioc_compiler.Policy_lowering
module E = Bioc_semantics.Policy_execution

let require condition message = if not condition then failwith message
let field key value = Json.field key (Json.object_fields value)
let text key value = Json.string (field key value)
let items key value = Json.array (field key value)
let project names value = Json.Object (List.map (fun key -> key,field key value) names)
let without key value = Json.Object (List.filter (fun (name,_) -> name<>key) (Json.object_fields value))
let replace key replacement value = Json.Object (List.map (fun (name,v) -> name,if name=key then replacement else v) (Json.object_fields value))
let change id key replacement document = replace "declarations" (Json.Array (List.map (fun row ->
  if text "id" row=id then replace key replacement row else row) (items "declarations" document))) document
let read path = let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel) (fun()->
  Json.parse_bounded ~max_bytes:(2*1024*1024) ~max_nodes:100000 (really_input_string channel (in_channel_length channel)))
let rejects code action = match action () with
  | _ -> failwith ("Expected rejection: "^code)
  | exception Diagnostic.Error diagnostic -> require (diagnostic.code=code) ("Wrong rejection: "^diagnostic.code)

let check_case behavior row =
  let name=text "id" row and expected=field "expected" row in
  let report=E.execute behavior (field "timeline" row) in
  let same label left right = require (Json.equal left right) (name^": "^label) in
  require (text "claim" report="bounded_supplied_timeline_only") "Source claim widened";
  same "all bounded machine snapshots differ" (Json.Array (List.map (project ["time";"machines";"active_attempts"]) (items "frames" report))) (field "frames" expected);
  same "complete attempt identity/status differs" (Json.Array (List.map (without "causes") (items "attempts" report))) (field "attempts" expected);
  let rejected=List.concat_map (fun frame -> List.filter_map (fun action ->
    if text "kind" action="feedback_rejected" then Some (project ["id";"reason"] (field "detail" action)) else None) (items "actions" frame)) (items "frames" report) in
  same "feedback rejection differs" (Json.Array rejected) (field "feedback_rejected" expected);
  List.iter (fun frame -> require (items "states" frame=[]) "Unexpected source state store") (items "frames" report);
  let events=List.concat_map (items "events") (items "frames" report) in
  List.iteri (fun index event -> require (text "id" event="event/"^string_of_int (index+1)) "Event census is reordered or incomplete") events;
  List.iter (fun attempt ->
    let id=field "id" attempt in
    let creation=List.filter (fun event -> field "attempt" event=id && List.mem (text "kind" event) ["requested";"initiated"]) events in
    require (List.map (text "kind") creation=["requested";"initiated"]) "Request/initiation order or multiplicity differs";
    List.iter (fun event -> same "creation binding" (field "binding" event) (field "binding" attempt);
      same "creation effect" (field "declaration" event) (field "effect" attempt)) creation;
    let causes=items "causes" attempt in
    require (List.length causes=1) "Staged attempt lost its unique causal event";
    let cause=List.find (fun event -> field "id" event=List.hd causes) events in
    same "causal encounter generation" (field "binding" cause) (field "binding" attempt);
    if text "effect" attempt="stage_one" then require (text "kind" cause="rising") "First stage lost rising cause"
    else (
      require (text "kind" cause="completed" && text "declaration" cause="stage_one") "Handoff lost first-stage completion cause";
      let first=List.find (fun candidate -> field "id" candidate=field "attempt" cause) (items "attempts" report) in
      same "handoff retained attempt binding" (field "binding" first) (field "binding" attempt))) (items "attempts" report);
  same "serialized behavior replay differs" report (E.execute (O.behavior_of_json (O.behavior_to_json behavior)) (field "timeline" row))

let () =
  require (Array.length Sys.argv=2) "Expected independent source fixture";
  let fixture=read Sys.argv.(1) in
  require (text "fixture_version" fixture="biocompiler.policy_staged_regimen_source_literals.v0.1") "Wrong source fixture";
  require (List.map (text "id") (items "cases" fixture)=
    ["both_complete";"first_failure_and_timeout";"second_timeouts";"false_handoff_no_retry";"unknown_handoff_no_retry";
     "wrong_feedback";"reset_generation";"end_scope";"terminal_no_reentry"]) "Incomplete literal source case census";
  let original=field "document" fixture in
  let document=D.of_json original and descriptors=O.descriptors_of_json (field "definitions" fixture) in
  let behavior=L.lower (A.admit ~document ~descriptors) in
  ignore (C.check ~expected_document:document ~descriptors behavior);
  require (List.length behavior.O.machines=1 && List.length behavior.O.transitions=7 && List.length behavior.O.effects=2) "Staged source shape differs";
  List.iter (check_case behavior) (items "cases" fixture);
  let stale=change "regimen/stages" "initial" (Json.String "first") original in
  rejects "policy_correspondence" (fun () -> C.check ~expected_document:(D.of_json stale) ~descriptors behavior);
  let wrong_lifetime=change "regimen/stages" "lifetime" (Json.String "executor") original in
  rejects "policy_operational_unsupported" (fun () -> A.admit ~document:(D.of_json wrong_lifetime) ~descriptors)
