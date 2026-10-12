(* The candidate runtime is tested from independent literal input/output rows.
   This executable links no source/model interpreter, checker or compiler. *)
open Bioc_wire
module D = Bioc_domain.Policy_controlled_domain
module I = Bioc_domain.Policy_controlled_activity_implementation
module C = Bioc_domain.Policy_controlled_behavior_candidate
module S = Bioc_domain.Policy_controlled_activity_sample
module Runtime = Bioc_candidate_runtime.Policy_controlled_activity
let checks = ref 0
let require value message = incr checks; if not value then failwith message
let str value = Json.String value
let arr value = Json.Array value
let get key raw = Json.field key (Json.object_fields raw)
let set key value raw = Json.Object ((key,value)::List.remove_assoc key (Json.object_fields raw))
let rec edit path change raw = match path with [] -> change raw | key::rest ->
  match raw with
  | Json.Array rows -> arr (List.mapi (fun i row -> if i = int_of_string key then edit rest change row else row) rows)
  | _ -> set key (edit rest change (get key raw)) raw
let put path value = edit path (fun _ -> value)
let read path = let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    Json.parse_bounded ~max_bytes:200000 ~max_nodes:100000
      (really_input_string channel (in_channel_length channel)))
let reject code action = incr checks; match action () with
  | _ -> failwith ("Expected runtime rejection: " ^ code)
  | exception Diagnostic.Error diagnostic ->
      if diagnostic.code <> code then failwith ("Expected " ^ code ^ "; got " ^ diagnostic.code)
let bindings : D.bindings = {
  clock="clock";executor_role="tcell";executor_identity="fixture.executor";
  slot="fixture.encounter";encounter_declaration="contact";encounter_subject="target";
  antigen_observation="antigen";controller_observation="controller";
  antigen_freshness_ticks=1;controller_freshness_ticks=1;
  member_a="rna-a";member_b="rna-b";product_a="product-a";product_b="product-b"}
let deadlines : D.deadlines = {onset_ticks=2;controller_off_ticks=2;
  antigen_off_ticks=2;component_off_ticks=2;reactivation_ticks=2}
let resolution = Json.Object ["$type",str "Quantity";"amount",str "1";
  "unit",Json.Object ["$type",str "Unit";"id",str "second";"dimension",str "time";
    "quantity_kind",str "duration";"scale",str "1";"reference",Json.Null]]
let validate raw = D.validate_for ~bindings ~resolution ~deadlines ~horizon_ticks:10 (D.of_json raw)
let noop _ = ()
let only = function [value] -> value | _ -> failwith "Expected one literal choice"
let choices domain cursor = List.of_seq (D.choices domain cursor)
let frame tick change raw =
  let rows = Json.array (get "fixed_inputs" raw) in
  let old = match List.find_opt (fun row -> get "tick" row = Json.int tick) rows with
    | Some row -> row
    | None -> List.hd rows |> set "tick" (Json.int tick) |> set "event" (str "none") in
  let rows = change old::List.filter (fun row -> get "tick" row <> Json.int tick) rows in
  let rows = List.sort (fun left right -> Z.compare (Json.integer (get "tick" left)) (Json.integer (get "tick" right))) rows in
  set "fixed_inputs" (arr rows) raw
let physical key value = edit ["physical"] (set key (str value))
let controller value = physical "controller" value
let event value = set "event" (str value)
let params (implementation:I.t) onset off restart =
  I.of_json (I.to_json implementation
    |> put ["primitives";"6";"onset_ticks"] (Json.int onset)
    |> put ["primitives";"6";"cessation_ticks"] (Json.int off)
    |> put ["primitives";"6";"reactivation_ticks"] (Json.int restart))
let all_rows change raw = set "fixed_inputs" (arr (List.map change (Json.array (get "fixed_inputs" raw)))) raw
let trace raw implementation =
  let domain = validate raw in
  let histories = ref [] in
  (match D.enumerate ~on_history:(fun rows -> histories := rows:: !histories) domain with
   | D.Complete usage -> require (usage.histories = 1 && usage.transitions = 11) "Literal full-horizon domain census changed"
   | _ -> failwith "Literal input enumeration did not complete");
  let input = only !histories in
  let charged = ref 0 in let charge n = charged := !charged + n in
  let state = Runtime.initialize ~charge ~implementation ~domain in
  let final,samples = List.fold_left (fun (state,samples) row ->
    let next,sample = Runtime.step ~charge state row in next,sample::samples) (state,[]) input in
  require (!charged > List.length input * 8) "Domain/primitive work was not charged to enclosing owner";
  final,List.rev samples
let assert_trace label expected expected_generation (final,samples) =
  require (List.map (fun (sample:S.t) -> sample.tick) samples = List.init 11 Fun.id) (label ^ ": missing tick");
  require (List.map (fun (sample:S.t) -> sample.band = S.Active) samples = expected) (label ^ ": wrong physical bands");
  require (List.map (fun (sample:S.t) -> sample.activation_generation) samples = expected_generation)
    (label ^ ": wrong activation generation");
  require (not (Runtime.pending final)) (label ^ ": unresolved final timer")
let generations values = List.map (fun value -> if value then Some 1 else None) values
let run domain_path fixture_path =
  let raw = read domain_path and literal = read fixture_path in
  let candidate = C.of_json (get "literal_candidate" literal) in
  let supplied = C.implementation candidate in
  let implementation = params supplied 2 2 2 in
  let normal = [false;false;true;true;true;false;false;false;true;true;true] in
  assert_trace "on/off/on" normal (generations normal) (trace raw implementation);
  let early = [false;true;true;true;false;false;false;true;true;true;true] in
  assert_trace "candidate actual delays differ from source deadlines" early (generations early) (trace raw supplied);
  let always = raw |> frame 3 (controller "enabled") in
  let continuous = [false;false;true;true;true;true;true;true;true;true;true] in
  assert_trace "gate remains enabled" continuous (generations continuous) (trace always implementation);
  let absent = all_rows (physical "antigen" "absent") always in
  assert_trace "controller cannot substitute for antigen" (List.init 11 (fun _ -> false))
    (List.init 11 (fun _ -> None)) (trace absent implementation);
  let maturity = raw |> frame 2 (controller "disabled") |> frame 3 (controller "enabled") in
  let cancelled = [false;false;false;false;false;true;true;true;true;true;true] in
  assert_trace "disable at onset maturity cancels activation" cancelled (generations cancelled) (trace maturity implementation);
  let restore = raw |> frame 4 (controller "enabled") in
  let noncancelable = [false;false;true;true;true;false;false;true;true;true;true] in
  assert_trace "restoration cannot cancel stopping" noncancelable (generations noncancelable) (trace restore implementation);
  let repeated_loss = restore |> frame 5 (controller "disabled") in
  assert_trace "later loss cannot postpone cessation" normal (generations normal) (trace repeated_loss implementation);
  let reset = raw |> frame 3 (fun row -> row |> event "reset" |> physical "antigen" "absent" |> controller "enabled")
      |> frame 4 (fun row -> row |> controller "enabled" |> physical "antigen" "present") in
  let reset_generations = [None;None;Some 1;Some 1;Some 1;None;None;Some 2;Some 2;Some 2;Some 2] in
  assert_trace "reset retains residual activity and executor timer" noncancelable reset_generations (trace reset implementation);
  let reset_stopping = raw |> frame 4 (fun row -> row |> event "reset" |> physical "antigen" "absent" |> controller "enabled")
      |> frame 5 (physical "antigen" "present") in
  assert_trace "reset cannot postpone existing stop" noncancelable reset_generations (trace reset_stopping implementation);
  let onset_reset = always |> frame 1 (fun row -> row |> event "reset" |> physical "antigen" "absent")
      |> frame 2 (physical "antigen" "present") in
  let restart_onset = [false;false;false;false;true;true;true;true;true;true;true] in
  assert_trace "reset cancels pending first onset" restart_onset
    (List.map (fun active -> if active then Some 2 else None) restart_onset) (trace onset_reset implementation);
  let ended = raw |> frame 3 (fun row -> row |> event "end" |> physical "antigen" "absent")
      |> frame 6 (event "start") in
  assert_trace "end/start reuses one slot and preserves executor state" normal
    [None;None;Some 1;Some 1;Some 1;None;None;None;Some 2;Some 2;Some 2] (trace ended implementation);
  List.iter (fun key ->
    let unavailable = always |> frame 3 (physical key "absent") |> frame 6 (physical key "present") in
    assert_trace (key ^ " loss/recovery") normal (generations normal) (trace unavailable implementation))
    ["protein_a";"protein_b";"antigen"];
  List.iter (fun key ->
    let rna_loss = always |> frame 3 (physical key "absent") in
    assert_trace (key ^ " loss preserves persisting protein activity") continuous (generations continuous) (trace rna_loss implementation))
    ["rna_a";"rna_b"];
  let missing = all_rows (edit ["evidence"] (fun evidence -> Json.Object (List.map (fun (key,_) ->
    key,Json.Object ["status",str "missing";"observed_tick",Json.Null;"generation",Json.Null]) (Json.object_fields evidence)))) raw in
  assert_trace "missing evidence cannot become physical OFF" normal (generations normal) (trace missing implementation);
  let invalid = all_rows (edit ["evidence"] (fun evidence -> Json.Object (List.map (fun (key,value) ->
    key,set "status" (str (if key="protein_a" then "conflicting" else "invalid")) value) (Json.object_fields evidence)))) raw in
  assert_trace "invalid/conflicting evidence cannot change physical timing" normal (generations normal) (trace invalid implementation);
  (* A longer but well-formed candidate delay is executable as an untrusted
     proposal. Its source failure belongs to the independent monitor. *)
  let unequal = [false;true;true;true;true;true;false;false;true;true;true] in
  assert_trace "separate onset/cessation/reactivation parameters" unequal (generations unequal) (trace raw (params supplied 1 3 2));
  let unfinished,_ = trace always (params supplied 64 2 2) in
  require (Runtime.pending unfinished) "An activation beyond the finite horizon was hidden";
  let domain = validate raw in let initial = D.initial domain in
  let first = only (choices domain initial) in
  let state = Runtime.initialize ~charge:noop ~implementation ~domain in
  require (not (Runtime.pending state)) "Initial state invented a timer";
  let after,sample = Runtime.step ~charge:noop state first in
  require (Runtime.pending after && sample.band = S.Background) "First enablement failed to start bounded onset";
  reject "policy_controlled_domain_cursor" (fun () -> Runtime.step ~charge:noop after first);
  let cursor1 = D.advance domain initial first in
  let second = only (choices domain cursor1) in
  reject "policy_controlled_domain_cursor" (fun () -> Runtime.step ~charge:noop state second);
  let other = validate (put ["limits";"max_work"] (Json.int 999999) raw) in
  reject "policy_controlled_domain_cursor" (fun () -> Runtime.step ~charge:noop state (only (choices other (D.initial other))));
  let divergent = raw |> set "physical_factors" (arr [Json.Object ["input",str "controller";
    "ticks",arr [Json.int 1];"values",arr [str "disabled"]]]) in
  let branch = validate divergent in let start = D.initial branch in
  let zero = only (choices branch start) in
  let common = D.advance branch start zero in
  let alternatives = choices branch common in
  require (List.length alternatives = 2) "Hold/disabled branch inventory changed";
  let left = List.nth alternatives 0 and right = List.nth alternatives 1 in
  let start_state = Runtime.initialize ~charge:noop ~implementation ~domain:branch in
  let common_state,_ = Runtime.step ~charge:noop start_state zero in
  let left_state,_ = Runtime.step ~charge:noop common_state left in
  let right_next = only (choices branch (D.advance branch common right)) in
  reject "policy_controlled_domain_cursor" (fun () -> Runtime.step ~charge:noop left_state right_next);
  let cancelled_initialize = try ignore (Runtime.initialize ~charge:(fun _ -> raise Exit) ~implementation ~domain); false with Exit -> true in
  require cancelled_initialize "Initialize swallowed cancellation";
  let cancelled_step = try ignore (Runtime.step ~charge:(fun _ -> raise Exit) state first); false with Exit -> true in
  require cancelled_step "Step swallowed cancellation";
  reject "outer_work" (fun () -> Runtime.step ~charge:(fun _ -> Diagnostic.fail "outer_work" "Original budget exhausted") state first);
  let unchanged,again = Runtime.step ~charge:noop state first in
  require (Runtime.pending unchanged && S.to_json again = S.to_json sample) "Failed or branched step mutated original state";
  Printf.printf "controlled candidate activity: %d literal timing, scope and resource checks\n" !checks
let () =
  if Array.length Sys.argv <> 3 then failwith "Expected original domain and independent behavior candidate fixtures";
  try run Sys.argv.(1) Sys.argv.(2) with Diagnostic.Error diagnostic ->
    Printf.eprintf "controlled candidate activity unexpected diagnostic after %d checks: %s\n%!" !checks diagnostic.code;
    raise (Diagnostic.Error diagnostic)
