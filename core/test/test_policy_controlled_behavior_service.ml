open Bioc_wire
module Base = Bioc_service.Service
module Producer = Bioc_producer_service.Producer_service
module S = Bioc_service.Policy_controlled_behavior_service
let require condition message = if not condition then failwith message
let obj fields = Json.Object fields
let str value = Json.String value
let get key value = Json.field key (Json.object_fields value)
let text key value = Json.string (get key value)
let set key replacement value = obj ((key,replacement)::List.remove_assoc key (Json.object_fields value))
let update key f value = set key (f (get key value)) value
let read path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    Json.parse_bounded ~max_bytes:4_000_000 ~max_nodes:100_000
      (really_input_string channel (in_channel_length channel)))
let rejects label action = match action () with
  | _ -> failwith (label ^ ": accepted forbidden operation")
  | exception Diagnostic.Error _ -> ()
let rejects_code label code action = match action () with
  | _ -> failwith (label ^ ": accepted forbidden operation")
  | exception Diagnostic.Error diagnostic ->
      require (diagnostic.code=code) (label ^ ": rejected at a different boundary: " ^ diagnostic.code)
let request operation payload : Protocol.request = {request_id="rc5-original";operation;payload}
let prepare executable request = match Producer.scoped_handle executable request with
  | Some (reply:Base.scoped_reply) ->
      require (reply.status=Protocol.Ok && reply.diagnostics=[]) "Behavior did not prepare success";
      let result=match reply.result with Some value->value | None->failwith "Absent prepared result" in
      let frame=Protocol.response ~executable ~request:(Some request) ~status:reply.status
        ~result:reply.result reply.diagnostics in
      result,frame,reply.before_encode
  | None -> failwith "Behavior is missing scoped dispatch"
let complete executable invocation =
  let result,frame,guard=prepare executable invocation in guard frame;result
let () =
  require (Array.length Sys.argv=2) "Supply complete original behavior authority fixture";
  let original=read Sys.argv.(1) in
  let constructed=complete Protocol.Core (request S.producer_operation (obj ["request",original])) in
  let candidate=get "candidate" constructed in
  let invoke operation=request operation (obj ["request",original;"candidate",candidate]) in
  let core=complete Protocol.Core (invoke "check-policy-controlled-behavior") in
  let verify=complete Protocol.Verify (invoke "check-policy-controlled-behavior") in
  require (Json.equal core verify) "Core and independent Verify checking differ";
  require (Json.equal (get "report" core) (get "report" constructed)) "Construction history changed behavioral verdict";
  let report=get "report" verify in
  require (text "status" report="checked_controlled_behavior" && text "outcome" report="pass")
    "Original finite two-history fixture did not pass";
  require (text "material_status" report="not_joined" && text "human_use" report="unassessed" &&
    text "empirical_status" report="unassessed" && text "therapeutic_export" report="withheld" &&
    get "artifact" verify=Json.Null) "Behavior checking upgraded material or empirical scope";
  List.iter (fun executable ->
    let replay=complete executable (request "replay-policy-controlled-behavior"
      (obj ["request",original;"candidate",candidate;"report",report])) in
    require (Json.equal (get "report" replay) report && get "artifact" replay=Json.Null)
      "Replay changed exact fresh assessment") [Protocol.Core;Protocol.Verify];
  require (Json.equal (get "max_work" (get "budgets" (get "original" original))) (Json.int 20_000_000))
    "The independent RC5 fixture must explicitly supply work for full counterexample publication";
  let missing=update "readout_evidence" (update "samples" (fun values ->
    Json.Array (List.mapi (fun tick value -> if tick=3 then
      value |> set "status" (str "missing") |> set "observed_tick" Json.Null else value)
      (Json.array values)))) original in
  let late=update "original" (fun value ->
    let model=update "body" (update "delays" (set "onset_ticks" (Json.int 3)))
      (get "mechanism_model" value) in
    let identity=set "content_fingerprint" (str (Canonical.fingerprint (get "body" model)))
      (get "identity" model) in
    value |> set "mechanism_model" (set "identity" identity model)
      |> update "catalog_binding" (set "model_identity" identity)
      |> update "source_authority" (update "control_contract"
        (update "actual_delays" (set "onset_ticks" (Json.int 3))))) original in
  List.iter (fun (label,altered,outcome) ->
    (* Complete the original final-frame guard for nonaccepted semantic results,
       including their full counterexample, on every supported public route. *)
    let built=complete Protocol.Core (request S.producer_operation (obj ["request",altered])) in
    let proposal=get "candidate" built and assessment=get "report" built in
    require (text "status" assessment="not_accepted" && text "outcome" assessment=outcome &&
      text "model_correspondence" assessment="pass" && get "artifact" built=Json.Null)
      (label ^ ": construction lost the intended semantic result");
    let witness=get "counterexample" assessment in
    require (List.length (Json.array (get "trace" witness))=11 &&
      List.length (Json.array (get "history" (get "source_monitor" witness)))=11)
      (label ^ ": complete original counterexample suffix was omitted");
    if label="missing readout" then
      require (text "evidence_status" assessment="unknown") "Missing readout became a physical OFF value"
    else (
      let onset=List.find (fun row -> text "id" row="onset") (Json.array (get "requirements" assessment)) in
      require (Z.sign (Json.integer (get "fail" onset))>0 && text "evidence_status" assessment="resolved")
        "Late model lost its original source deadline failure");
    let exercise operation extra = List.map (fun executable ->
      let result=complete executable (request operation
        (obj (["request",altered;"candidate",proposal] @ extra))) in
      require (Json.equal (get "report" result) assessment && get "artifact" result=Json.Null)
        (label ^ ": fresh checking/replay changed the complete original assessment");
      result) [Protocol.Core;Protocol.Verify] in
    List.iter (fun results -> match results with
      | [core;verify] -> require (Json.equal core verify) (label ^ ": Core/Verify publication differs")
      | _ -> failwith "Altered service test lost an executable role")
      [exercise "check-policy-controlled-behavior" [];
       exercise "replay-policy-controlled-behavior" ["report",assessment]])
    ["missing readout",missing,"unknown";"late model",late,"fail"];
  (* The prior artificial10M allowance reaches a prepared unknown report but
     cannot publish its full frame. Keep the original budget and exact failure
     instead of treating preparation as permission or dropping the witness. *)
  let missing_limited=update "original" (update "budgets" (set "max_work" (Json.int 10_000_000))) missing in
  let unknown_result,unknown_frame,unknown_guard=prepare Protocol.Core
    (request S.producer_operation (obj ["request",missing_limited])) in
  require (text "outcome" (get "report" unknown_result)="unknown" && get "artifact" unknown_result=Json.Null)
    "The prior work allowance must reach preparation before its final publication regression";
  rejects_code "original unknown final frame work exhaustion" "controlled_behavior_service_work_limit"
    (fun () -> unknown_guard unknown_frame);
  rejects_code "exhausted unknown frame reuse" "controlled_behavior_service_publication_guard"
    (fun () -> unknown_guard unknown_frame);
  let forged label transform =
    let _,frame,guard=prepare Protocol.Verify (invoke "check-policy-controlled-behavior") in
    rejects label (fun () -> guard (transform frame));
    rejects (label ^ " reuse") (fun () -> guard frame) in
  forged "foreign outer id" (set "request_id" (str "foreign"));
  forged "foreign operation" (set "operation" (str S.producer_operation));
  forged "foreign executable" (update "core" (set "executable" (str "core")));
  forged "locally rehashed scope upgrade" (update "result" (fun result ->
    let changed=set "material_status" (str "joined") (get "report" result) in
    result |> set "report" changed |> set "report_fingerprint" (str (Canonical.fingerprint changed))));
  let _,frame,guard=prepare Protocol.Verify (invoke "check-policy-controlled-behavior") in
  guard frame; rejects "one-shot guard reuse" (fun () -> guard frame);
  rejects "unscoped bypass" (fun () -> Base.handle Protocol.Core (invoke "check-policy-controlled-behavior"));
  require (Producer.scoped_handle Protocol.Verify
    (request S.producer_operation (obj ["request",original]))=None) "Verify gained construction";
  rejects "Verify generated service bypass" (fun () -> S.prepare_generated ~executable:Protocol.Verify
    ~request:(request S.producer_operation (obj ["request",original]))
    ~produce:(fun ~charge:_ _ -> failwith "Verify invoked a producer"));
  rejects "forged replay" (fun () -> prepare Protocol.Verify (request "replay-policy-controlled-behavior"
    (obj ["request",original;"candidate",candidate;"report",set "material_status" (str "joined") report])));
  let limited key amount=update "original" (update "budgets" (set key (Json.int amount))) original in
  rejects "original work exhaustion" (fun () -> prepare Protocol.Core
    (request S.producer_operation (obj ["request",limited "max_work" 1])));
  List.iter (fun key ->
    let small=limited key 1 in
    let repinned=set "request_fingerprint" (str (Canonical.fingerprint small)) candidate in
    rejects ("original " ^ key ^ " exhaustion") (fun () -> prepare Protocol.Verify
      (request "check-policy-controlled-behavior" (obj ["request",small;"candidate",repinned]))))
    ["max_report_bytes";"max_report_nodes"];
  let prepared=Z.to_int (Json.integer (get "preparation_charged_work" (get "usage" core))) in
  let small=limited "max_work" (prepared+2048) in
  let repinned=set "request_fingerprint" (str (Canonical.fingerprint small)) candidate in
  let _,frame,guard=prepare Protocol.Verify (request "check-policy-controlled-behavior"
    (obj ["request",small;"candidate",repinned])) in
  rejects "final original frame work exhaustion" (fun () -> guard frame);
  rejects "exhausted frame reuse" (fun () -> guard frame);
  List.iter (fun executable ->
    match Producer.handle executable (request "capabilities" (obj [])) with
    | Protocol.Ok,Some result,[] ->
        require (Json.equal (get "policy_controlled_composition_behavior" (get "profiles" result))
          (if executable=Protocol.Core then S.producer_profile else S.profile))
          "Behavior capability differs from actual supported operations"
    | _ -> failwith "Capabilities failed") [Protocol.Core;Protocol.Verify];
  print_endline "controlled behavior service: fresh construction/check/replay, finite conditional scope and original one-shot publication passed"
