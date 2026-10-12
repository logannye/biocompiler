(* Literal originals and independent assertions. Tests are hosted-only. *)
open Bioc_wire
module R = Bioc_domain.Policy_controlled_behavior_request
module C = Bioc_domain.Policy_controlled_behavior_candidate
module P = Bioc_compiler.Policy_controlled_behavior_producer
module Check = Bioc_realization_checker.Policy_controlled_behavior_check
module W = Bioc_checker.Work_budget
let checks = ref 0
let require value message = incr checks; if not value then failwith message
let str s = Json.String s
let obj f = Json.Object f
let arr a = Json.Array a
let get key raw = Json.field key (Json.object_fields raw)
let set key value raw = obj ((key,value)::List.remove_assoc key (Json.object_fields raw))
let rec at path raw = match path with [] -> raw | key::rest ->
  at rest (match raw with Json.Array values -> List.nth values (int_of_string key) | _ -> get key raw)
let rec edit path change raw = match path with [] -> change raw | key::rest ->
  match raw with
  | Json.Array values -> arr (List.mapi (fun index value -> if index = int_of_string key
      then edit rest change value else value) values)
  | _ -> set key (edit rest change (get key raw)) raw
let put path value = edit path (fun _ -> value)
let reject label action = incr checks; match action () with
  | _ -> failwith ("Unexpected behavior acceptance: " ^ label)
  | exception Diagnostic.Error _ -> ()
let read path = let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let size = in_channel_length channel in require (size > 0 && size < 1000000) "Literal bound";
    Json.parse (really_input_string channel size))
let proposal raw = let request = R.of_json raw in
  request,P.construct_candidate ~charge:(fun _ -> ()) request
let check raw = let request,candidate = proposal raw in Check.check ~request ~candidate ()
let repin_model raw =
  let digest = Canonical.fingerprint (at ["original";"mechanism_model";"body"] raw) in
  raw |> put ["original";"mechanism_model";"identity";"content_fingerprint"] (str digest)
    |> put ["original";"catalog_binding";"model_identity";"content_fingerprint"] (str digest)
let delay name value raw = raw
  |> put ["original";"mechanism_model";"body";"delays";name] (Json.int value)
  |> put ["original";"source_authority";"control_contract";"actual_delays";name] (Json.int value)
  |> repin_model
let run path =
  let raw = read path in
  let request,candidate = proposal raw in
  let result = Check.check ~request ~candidate () in
  let report = Check.report result in
  require (Option.is_some (Check.accepted result)) "Complete reversible fixture did not accept";
  require (get "outcome" report = str "pass" && get "stage" report = str "behavior") "Wrong behavior result";
  require (at ["domain";"counters";"histories"] report = Json.int 2 &&
      at ["domain";"assessed_histories"] report = Json.int 2) "An admitted branch disappeared";
  require (List.for_all (fun (_,value) -> value = Json.Bool true)
      (Json.object_fields (get "coverage" report))) "Nonvacuity witness missing";
  require (get "model_correspondence" report = str "pass") "Independent model disagreement";
  require (List.length (Json.array (get "requirements" report)) = 6) "Lost requirement";
  List.iter (fun key -> require (get key report = str "unassessed") "Behavior promoted empirical evidence")
    ["empirical_status";"human_use"];
  require (get "material_status" report = str "not_joined" && get "therapeutic_export" report = str "withheld")
    "Behavior bypassed later material/project gates";
  let replayed = Check.replay ~request ~candidate report in
  require (Json.equal report (Check.report replayed)) "Fresh replay differs";
  reject "forged saved outcome" (fun () -> Check.replay ~request ~candidate (set "outcome" (str "fail") report));
  reject "foreign original" (fun () -> Check.check
    ~request:(R.of_json (put ["original";"source_authority";"project_context";"title"] (str "Foreign") raw)) ~candidate ());
  let foreign = put ["original";"context";"executor_identity"] (str "foreign.executor") raw
    |> put ["original";"operating_domain";"executor";"identity"] (str "foreign.executor") in
  let foreign_request = R.of_json foreign in
  let repinned = C.of_json (set "request_fingerprint" (str (R.fingerprint foreign_request)) (C.to_json candidate)) in
  reject "repinned foreign graph" (fun () -> Check.check ~request:foreign_request ~candidate:repinned ());
  List.iter (fun name ->
    let result = check (delay name 3 raw) in
    require (Check.accepted result = None && get "outcome" (Check.report result) = str "fail")
      ("Source deadline not enforced: " ^ name);
    require (get "model_correspondence" (Check.report result) = str "pass")
      "Source failure was conflated with actual model correspondence";
    require (get "counterexample" (Check.report result) <> Json.Null) "Missing full failing history")
    ["onset_ticks";"cessation_ticks";"reactivation_ticks"];
  let missing = raw |> put ["readout_evidence";"samples";"4";"status"] (str "missing")
    |> put ["readout_evidence";"samples";"4";"observed_tick"] Json.Null in
  let unknown = check missing in
  require (Check.accepted unknown = None && get "outcome" (Check.report unknown) = str "unknown")
    "Unresolved readout evidence granted acceptance";
  require (get "model_correspondence" (Check.report unknown) = str "pass")
    "Missing evidence changed physical execution";
  let missing_branch = raw |> put ["original";"operating_domain";"evidence_factors"]
    (arr [obj ["input",str "controller";"ticks",arr [Json.int 2];
      "statuses",arr [str "missing"];"age_ticks",arr [Json.int 0]]]) in
  let unknown_branch = Check.report (check missing_branch) in
  require (get "outcome" unknown_branch = str "unknown" &&
      at ["domain";"assessed_histories"] unknown_branch = Json.int 4)
    "Unknown branch was pruned or quietly accepted";
  let quiet = edit ["original";"operating_domain";"fixed_inputs"] (fun rows -> arr (List.map
    (put ["physical";"controller"] (str "disabled")) (Json.array rows))) raw in
  let quiet_result = Check.report (check quiet) in
  require (get "outcome" quiet_result = str "fail" && at ["coverage";"active"] quiet_result = Json.Bool false)
    "Always-off domain passed by vacuity";
  List.iter (fun (label,path,value) -> reject label (fun () -> ignore (R.of_json (put path value raw)))) [
    "readout future",["readout_evidence";"samples";"0";"observed_tick"],Json.int 1;
    "readout status",["readout_evidence";"samples";"0";"status"],str "stale";
    "readout missing timestamp",["readout_evidence";"samples";"0";"observed_tick"],Json.Null;
    "readout absent schedule",["readout_evidence";"samples"],arr [];
    "original authority absent",["original"],Json.Null];
  reject "cancellation" (fun () -> Check.check ~cancelled:(fun () -> true) ~request ~candidate ());
  reject "exhausted inherited budget" (fun () ->
    let parent = W.create ~profile:"test" ~error_code:"test_work" ~maximum:1 () in
    Check.check ~parent ~request ~candidate ());
  reject "original publication bound" (fun () -> check (put ["original";"budgets";"max_report_bytes"] (Json.int 1) raw));
  Printf.printf "controlled behavior checker: %d checks\n" !checks
let () = if Array.length Sys.argv <> 2 then failwith "Expected independent behavior request literal"
  else run Sys.argv.(1)
