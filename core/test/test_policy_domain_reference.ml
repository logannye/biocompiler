open Bioc_wire
module D = Bioc_domain.Policy_document
module O = Bioc_domain.Policy_operational
module F = Bioc_domain.Policy_operating_domain
module A = Bioc_checker.Policy_admission
module L = Bioc_compiler.Policy_lowering
module C = Bioc_checker.Policy_correspondence
module E = Bioc_semantics.Policy_execution
module R = Bioc_semantics.Policy_domain_reference

let require condition message = if not condition then failwith message
let str value = Json.String value
let arr values = Json.Array values
let obj fields = Json.Object fields
let get name value = Json.field name (Json.object_fields value)
let items name value = Json.array (get name value)
let text name value = Json.string (get name value)
let replace key replacement value = obj (List.map (fun (name,item) ->
  name,if name=key then replacement else item) (Json.object_fields value))
let read path = let channel=open_in_bin path in
  Fun.protect ~finally:(fun()->close_in_noerr channel) (fun()->
    Json.parse_bounded ~max_bytes:(2*1024*1024) ~max_nodes:100000
      (really_input_string channel (in_channel_length channel)))
let compiled fixture =
  let document=D.of_json (get "document" fixture)
  and descriptors=O.descriptors_of_json (get "definitions" fixture) in
  let behavior=L.lower (A.admit ~document ~descriptors) in
  ignore (C.check ~expected_document:document ~descriptors behavior); behavior
let rejects code action = match action () with
  | _ -> failwith ("Expected diagnostic: " ^ code)
  | exception Diagnostic.Error diagnostic ->
      require (diagnostic.code=code) ("Wrong diagnostic: " ^ diagnostic.code)
let only = function [value] -> value | _ -> failwith "Expected one input choice"
let batches state = List.of_seq (R.choices state)
let keep (batch:F.input_batch) = List.for_all (fun (_,action)->action=F.Keep) batch.lifecycle
let quiet_feedback (batch:F.input_batch) = batch.feedback=[]
let choose predicate state = List.find predicate (batches state)
let advanced = function R.Advanced value -> value
  | R.Stopped stopped -> failwith ("Unexpected stopped reference: " ^ stopped.diagnostic.code)
let step state batch = advanced (R.step state batch)
let report (value:R.advanced) = Option.get value.receipt.execution
let at_one state = step state (only (batches state))
let both_true (batch:F.input_batch) = List.length batch.observations=2 &&
  List.for_all (fun (row:F.observation_input)->row.evidence=F.Known true) batch.observations
let one_feedback identity outcome (batch:F.input_batch) = match batch.feedback with
  | [input] -> input.attempt.source_attempt_id=identity && input.outcome=outcome
  | _ -> false
let state_row slot rows = List.find (fun row -> get "encounter" (get "binding" row)=str slot) rows
let attempt identity value = List.find (fun row->text "id" row=identity) (items "attempts" value)
let event_ids frame = List.map (text "id") (items "events" frame)
let rejection_reason frame reason = List.exists (fun row ->
  text "kind" row="feedback_rejected" && text "reason" (get "detail" row)=reason) (items "actions" frame)
let stopped kind code = function
  | R.Advanced _ -> failwith "Expected a retained stopped branch"
  | R.Stopped value -> require (value.kind=kind && value.diagnostic.code=code)
      ("Wrong stopped outcome: " ^ value.diagnostic.code); value

let run raw fixture =
  let behavior=compiled fixture in
  let original_bounds=get "bounds" (get "timeline" fixture) in
  let bounds=R.execution_bounds_of_json original_bounds in
  require (Json.equal (R.execution_bounds_to_json bounds) original_bounds) "Bounds authority changed";
  let create raw = R.create ~behavior ~domain:(F.of_json raw) ~bounds in
  let initial=create raw in
  let zero=at_one initial in
  require (event_ids zero.frame=["event/1";"event/2";"event/3";"event/4"])
    "Initial source event identities/order differ from the literal";
  let one=step zero.next (choose both_true zero.next) in
  require (List.map (fun (c:F.source_creation)->c.source_attempt_id,c.key.context,c.key.generation,c.key.creation_ordinal,c.created_tick) one.creations =
    ["attempt/1",F.Encounter_slot "e1",0,1,1; "attempt/2",F.Encounter_slot "e2",0,2,1])
    "Fresh creation extraction changed source IDs, binding, generation or global order";
  require (event_ids one.frame=["event/5";"event/6";"event/7";"event/8";
    "event/9";"event/10";"event/11";"event/12"])
    "Source observation/edge/request/initiation event identities changed";
  require (List.map (text "kind") (items "events" one.frame)=
    ["updated";"updated";"rising";"rising";"requested";"initiated";"requested";"initiated"])
    "Source event kinds lost explicit requested-before-initiated order";
  let two=step one.next (choose (one_feedback "attempt/1" F.Completed) one.next) in
  let three=step two.next (choose (fun batch->keep batch && quiet_feedback batch) two.next) in
  let four=step three.next (only (batches three.next)) in
  require (R.finished four.next && batches four.next=[]) "Inclusive horizon did not terminate the cursor";
  require (text "status" (attempt "attempt/1" (report four))="completed" &&
    text "status" (attempt "attempt/2" (report four))="timed_out")
    "Missing feedback no longer reaches the source timeout";
  require (items "events" four.frame=[]) "Quiet expiry tick invented events";
  require (List.for_all (fun row->text "status" row="stale") (items "evidence" four.frame))
    "A silent tick failed to expire retained evidence";
  require (Json.equal (E.execute behavior four.receipt.timeline) (report four))
    "Final prefix report differs from a fresh complete source execution";
  let literal_observation identity tick target value = obj [
    "id",str identity;"available_at",str tick;"observed_at",str tick;
    "observer",str "cell-1";"subject",str ("target-" ^ target);
    "encounter",str ("e" ^ target);"observation",str "condition";
    "status",str "valid";"value",Json.Bool value] in
  let literal_encounter target = obj ["id",str ("e" ^ target);"declaration",str "encounter";
    "target",str ("target-" ^ target);"start",str "0";"end",Json.Null;"resets",arr []] in
  let expected_timeline=obj ["profile",str "biocompiler.policy_timeline.v0.1";
    "executor",str "cell-1";"horizon",str "4";"bounds",original_bounds;
    "encounters",arr [literal_encounter "1";literal_encounter "2"];
    "observations",arr [literal_observation "domain/observation/0/0" "0" "1" false;
      literal_observation "domain/observation/0/1" "0" "2" false;
      literal_observation "domain/observation/1/0" "1" "1" true;
      literal_observation "domain/observation/1/1" "1" "2" true;
      literal_observation "domain/observation/2/0" "2" "1" false;
      literal_observation "domain/observation/2/1" "2" "2" false];
    "feedback",arr [obj ["id",str "domain/feedback/2/0";"available_at",str "2";
      "executor",str "cell-1";"subject",str "target-1";"encounter",str "e1";
      "effect",str "response";"attempt",str "attempt/1";"outcome",str "completed"]]] in
  require (Json.equal four.receipt.timeline expected_timeline) "Complete transport differs from independent timeline literal";
  let receipts=[zero;one;two;three;four] in
  let reported=List.fold_left (fun total (value:R.advanced)->
    Z.add total (Json.integer (get "work" (get "usage" (report value))))) Z.zero receipts in
  let cost=R.accounting four.next in
  require (Z.equal cost.replay_calls (Z.of_int 5) && Z.equal cost.reserved_work (Z.of_int 5000000) &&
    Z.equal cost.reported_work reported && Z.equal cost.charged_work reported && Z.equal cost.unreported_calls Z.zero)
    "Prefix replay work was lost or full successful reservations were charged as consumed work";
  require (Z.equal (R.accounting initial).replay_calls Z.zero) "Stepping mutated an earlier immutable prefix";
  let other=step zero.next (choose (fun (b:F.input_batch)->b.observations=[]) zero.next) in
  rejects "policy_domain_cursor" (fun()->R.step other.next (List.hd (batches one.next)));
  rejects "policy_domain_cursor" (fun()->R.step four.next (List.hd (batches three.next)));
  let changed_domain=create (replace "logical_limits"
    (replace "max_source_attempts" (Json.int 3) (get "logical_limits" raw)) raw) in
  rejects "policy_domain_cursor" (fun()->R.step changed_domain (only (batches initial)));
  let repeated=step two.next (choose (fun b->keep b && one_feedback "attempt/1" F.Failed b) two.next) in
  require (rejection_reason repeated.frame "stale_attempt" &&
    text "status" (attempt "attempt/1" (report repeated))="completed")
    "Repeated old feedback overwrote completion or was filtered before the source saw it";
  let pending=step one.next (choose quiet_feedback one.next) in
  let deadline=step pending.next (choose (fun b->keep b && one_feedback "attempt/1" F.Completed b) pending.next) in
  require (text "status" (attempt "attempt/1" (report deadline))="completed" &&
    text "ended_at" (attempt "attempt/1" (report deadline))="3")
    "Correlated feedback at its deadline lost source-defined precedence";
  let reset=step pending.next (choose (fun (b:F.input_batch)->List.assoc "e1" b.lifecycle=F.Reset &&
    List.assoc "e2" b.lifecycle=F.Keep && one_feedback "attempt/1" F.Completed b) pending.next) in
  require (rejection_reason reset.frame "stale_attempt" &&
    text "status" (attempt "attempt/1" (report reset))="encounter_reset")
    "Reset feedback was rebound to the new generation or accepted before reset";
  let reset_state=state_row "e1" (items "states" reset.frame) in
  require (get "generation" (get "binding" reset_state)=Json.int 1 && get "value" reset_state=Json.Bool false)
    "Source-owned reset generation/initial state was changed";
  let ended=step pending.next (choose (fun (b:F.input_batch)->List.assoc "e1" b.lifecycle=F.End &&
    List.assoc "e2" b.lifecycle=F.Keep && one_feedback "attempt/1" F.Completed b) pending.next) in
  require (rejection_reason ended.frame "stale_attempt" &&
    text "status" (attempt "attempt/1" (report ended))="encounter_ended")
    "Ended-attempt feedback disappeared or completed a dead encounter";
  List.iter (fun (evidence,expected_status,expected_value) ->
    let value=step zero.next (choose (fun (batch:F.input_batch)->match batch.observations with
      | [row] -> row.slot="e1" && row.evidence=evidence | _ -> false) zero.next) in
    let retained=state_row "e1" (items "evidence" value.frame) in
    require (text "status" retained=expected_status && get "value" retained=expected_value)
      "An explicit evidence class was changed in transport or source execution")
    [F.Known false,"valid",Json.Bool false; F.Known true,"valid",Json.Bool true;
     F.Missing,"missing",Json.Null; F.Invalid,"invalid",Json.Null;
     F.Conflicting,"conflicting",Json.Null];
  let factor=List.hd (items "observation_factors" raw) in
  let multiple=create (replace "observation_factors"
    (arr [replace "max_rows_per_slot_tick" (Json.int 2) factor]) raw) in
  let multiple_zero=at_one multiple in
  List.iter (fun pair ->
    let value=step multiple_zero.next (choose (fun (batch:F.input_batch)->
      List.map (fun (row:F.observation_input)->row.slot,row.evidence) batch.observations=
        List.map (fun truth->"e1",F.Known truth) pair) multiple_zero.next) in
    let transported=List.filter (fun row->get "available_at" row=str "1")
      (items "observations" value.receipt.timeline) in
    require (List.map (get "value") transported=List.map (fun truth->Json.Bool truth) pair &&
      List.map (text "id") transported=["domain/observation/1/0";"domain/observation/1/1"])
      "Simultaneous input ordering or multiplicity was normalized away";
    let retained=state_row "e1" (items "evidence" value.frame) in
    require (text "status" retained="conflicting" && value.creations=[])
      "Contradictory simultaneous observations became an asserted truth") [[false;true];[true;false]];
  let aged_raw=raw |> replace "lifecycle_factors" (arr [])
    |> replace "fixed_observations" (arr (List.filter (fun row->get "available_tick" row=Json.int 0)
      (items "fixed_observations" raw)))
    |> replace "observation_factors" (arr [factor |> replace "ticks" (arr [Json.int 3])
      |> replace "age_ticks" (arr [Json.int 2])]) in
  let aged_zero=at_one (create aged_raw) in
  let aged_one=step aged_zero.next (only (batches aged_zero.next)) in
  let aged_two=step aged_one.next (only (batches aged_one.next)) in
  let aged_three=step aged_two.next (choose (fun (batch:F.input_batch)->match batch.observations with
    | [row] -> row.slot="e1" && row.evidence=F.Known true | _ -> false) aged_two.next) in
  let stale=state_row "e1" (items "evidence" aged_three.frame) in
  require (get "observed_at" stale=str "1" && get "available_at" stale=str "3" &&
    text "status" stale="stale" && aged_three.creations=[])
    "Sample age was rewritten into availability time or stale evidence created an attempt";
  let tight_raw=replace "logical_limits" (replace "max_source_attempts" (Json.int 1) (get "logical_limits" raw)) raw in
  let tight_zero=at_one (create tight_raw) in
  require (List.length (batches tight_zero.next)=36) "Logical output bound pruned source input choices";
  let too_many=stopped R.Source_bound "policy_domain_source_bound"
    (R.step tight_zero.next (choose both_true tight_zero.next)) in
  require (Option.is_some too_many.receipt.execution && List.length (items "attempts" (Option.get too_many.receipt.execution))=2 &&
    Z.equal too_many.receipt.delta.unreported_calls Z.zero)
    "Logical source-bound violation lost the complete violating execution";
  let constrained key number = R.create ~behavior ~domain:(F.of_json raw)
    ~bounds:(R.execution_bounds_of_json (replace key (Json.int number) original_bounds)) in
  rejects "policy_domain_reference_bound" (fun()->constrained "max_attempts" 2);
  rejects "policy_domain_reference_bound" (fun()->constrained "max_ticks" 4);
  rejects "policy_domain_reference_bound" (fun()->constrained "max_encounters" 1);
  rejects "policy_domain_reference_bound" (fun()->R.execution_bounds_of_json (replace "max_work" (Json.int 0) original_bounds));
  List.iter (fun (key,number,code) ->
    let state=constrained key number in
    let result=stopped R.Exhausted code (R.step state (only (batches state))) in
    require (result.receipt.execution=None && Z.equal result.receipt.delta.unreported_calls Z.one &&
      Z.equal result.receipt.delta.charged_work result.receipt.delta.reserved_work)
      "Failed replay was presented as a complete report or charged as zero work")
    ["max_work",1,"policy_execution_work_limit";
     "max_trace_items",1,"policy_execution_trace_limit";
     "max_inputs",1,"policy_execution_input_limit"];
  let document=get "document" fixture in
  let rule=List.find (fun declaration->get "id" declaration=str "respond") (items "declarations" document) in
  let exclusive_document=replace "declarations"
    (arr (items "declarations" document @ [replace "id" (str "respond_again") rule])) document in
  let exclusive_behavior=compiled (replace "document" exclusive_document fixture) in
  let exclusive=R.create ~behavior:exclusive_behavior ~domain:(F.of_json raw) ~bounds in
  let exclusive_zero=at_one exclusive in
  let source_error=stopped R.Source_error "policy_execution_exclusive"
    (R.step exclusive_zero.next (choose both_true exclusive_zero.next)) in
  require (source_error.receipt.execution=None &&
    List.length (items "observations" source_error.receipt.timeline)=4)
    "Source arbitration error lost its permitted causal input or gained a partial report";
  let effect_spec=List.find (fun declaration->get "id" declaration=str "response") (items "declarations" document) in
  let doubled_rule=replace "effects" (arr (items "effects" rule @
    [obj ["$type",str "Ref";"kind",str "Effect";"id",str "response_again"]])) rule in
  let doubled_document=replace "declarations" (arr
    (List.map (fun declaration->if get "id" declaration=str "respond" then doubled_rule else declaration)
      (items "declarations" document) @ [replace "id" (str "response_again") effect_spec])) document in
  let doubled_behavior=compiled (replace "document" doubled_document fixture) in
  let doubled=R.create ~behavior:doubled_behavior ~domain:(F.of_json raw)
    ~bounds:(R.execution_bounds_of_json (replace "max_attempts" (Json.int 3) original_bounds)) in
  let doubled_zero=at_one doubled in
  let ceiling=stopped R.Source_bound "policy_execution_attempt_limit"
    (R.step doubled_zero.next (choose both_true doubled_zero.next)) in
  require (ceiling.receipt.execution=None && Z.equal ceiling.receipt.delta.unreported_calls Z.one)
    "Executor ceiling above the logical attempt limit became an ordinary incomplete input prune";
  let resolution_source=replace "declarations" (arr (List.map (fun declaration ->
    if get "id" declaration=str "clock" then replace "resolution"
      (replace "amount" (str "0.1") (get "resolution" declaration)) declaration else declaration)
    (items "declarations" document))) document in
  let fractional_behavior=compiled (replace "document" resolution_source fixture) in
  let fractional=R.create ~behavior:fractional_behavior ~domain:(F.of_json raw) ~bounds in
  let fractional_zero=at_one fractional in
  let fractional_one=step fractional_zero.next (choose both_true fractional_zero.next) in
  require (get "horizon" fractional_one.receipt.timeline=str "0.1" &&
    get "started_at" (attempt "attempt/1" (report fractional_one))=str "0.1")
    "Tick conversion rounded or failed to use exact source clock resolution";
  rejects "policy_domain_cursor" (fun()->R.step fractional (only (batches initial)));
  (* Small actual-reference census. This tests transport and causal enumeration;
     no candidate is executed and failing/unknown requirements are not pruned. *)
  let prefixes=ref 1 and terminals=ref 0 and charged=ref Z.zero in
  let rec visit state =
    if R.finished state then incr terminals else
      Seq.iter (fun batch -> let value=step state batch in
        incr prefixes; charged:=Z.add !charged value.receipt.delta.charged_work; visit value.next) (R.choices state) in
  visit initial;
  require (!prefixes=3630 && !terminals=1764 && Z.sign !charged>0)
    "Actual source prefix census differs from the independent 1764-history / 3630-prefix literal";
  Printf.printf "Source domain transport: %d histories, %d prefixes; no preservation acceptance\n" !terminals !prefixes

let () =
  require (Array.length Sys.argv=3) "Expected finite-domain and operational-source fixtures";
  run (read Sys.argv.(1)) (read Sys.argv.(2))
