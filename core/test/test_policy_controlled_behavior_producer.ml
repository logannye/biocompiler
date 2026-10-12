(* Exact expected graph is an independent literal, never a checker/producer result. *)
open Bioc_wire
module R = Bioc_domain.Policy_controlled_behavior_request
module C = Bioc_domain.Policy_controlled_behavior_candidate
module I = Bioc_domain.Policy_controlled_activity_implementation
module P = Bioc_compiler.Policy_controlled_behavior_producer
let checks = ref 0
let require value message = incr checks; if not value then failwith message
let str value = Json.String value
let get key raw = Json.field key (Json.object_fields raw)
let set key value raw = Json.Object ((key,value)::List.remove_assoc key (Json.object_fields raw))
let rec edit path change raw = match path with [] -> change raw | key::rest ->
  match raw with
  | Json.Array rows -> Json.Array (List.mapi (fun i row -> if i = int_of_string key then edit rest change row else row) rows)
  | _ -> set key (edit rest change (get key raw)) raw
let put path value = edit path (fun _ -> value)
let read path = let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    Json.parse_bounded ~max_bytes:1000000 ~max_nodes:100000
      (really_input_string channel (in_channel_length channel)))
let run request_path fixture_path =
  let raw = read request_path and fixture = read fixture_path in
  let request = R.of_json raw in
  require (str (R.fingerprint request) = get "request_sha256" fixture) "Independent request changed";
  let charged = ref 0 in
  let charge n = charged := !charged + n;
    Diagnostic.require (!charged <= (R.budgets request).max_work) "test_work_limit" "Original work budget exhausted." in
  let candidate = P.construct_candidate ~charge request in
  require (Json.equal (C.to_json candidate) (get "literal_candidate" fixture)) "Proposal differs from independent literal graph";
  require (str (C.fingerprint candidate) = get "candidate_sha256" fixture) "Complete candidate digest differs";
  let implementation = C.implementation candidate in
  require (str (I.fingerprint implementation) = get "implementation_sha256" fixture) "Implementation digest differs";
  require (!charged > C.decoding_work candidate && !charged < (R.budgets request).max_work)
    "Producer escaped construction charges or original work ceiling";
  require (Json.equal raw (R.to_json request)) "Proposal changed caller authority";
  let second = P.construct_candidate ~charge request in
  require (C.fingerprint second = C.fingerprint candidate) "Identical original produced a different graph";
  let implementation_raw = I.to_json implementation in
  let model = get "mechanism_model" (get "original" raw) in
  require (Json.equal (get "mechanism_model" implementation_raw) model)
    "Full model/component/port bodies were reduced to IDs";
  let original_definitions = get "semantics" (get "program" (get "document" (get "source_authority" (get "original" raw)))) in
  require (Json.equal (get "semantics" implementation_raw) original_definitions)
    "Complete original semantic dependency bodies were omitted";
  let delays = I.delays implementation in
  require (delays.onset_ticks = 1 && delays.cessation_ticks = 1 && delays.reactivation_ticks = 1)
    "Actual model delays were replaced with source deadlines";
  List.iter (fun (label,changed) ->
    let next_request = R.of_json changed in
    let next = P.construct_candidate ~charge next_request in
    require (C.request_fingerprint next = R.fingerprint next_request && C.fingerprint next <> C.fingerprint candidate)
      (label ^ " is missing from candidate original identity");
    require (I.fingerprint (C.implementation next) = I.fingerprint implementation)
      (label ^ " changed an unchanged primitive implementation")) [
    "project title",put ["original";"source_authority";"project_context";"title"] (str "Other artificial original") raw;
    "report bound",put ["original";"budgets";"max_report_bytes"] (Json.int 999999) raw;
    "readout evidence",raw |> put ["readout_evidence";"samples";"0";"status"] (str "missing")
      |> put ["readout_evidence";"samples";"0";"observed_tick"] Json.Null
  ];
  let changed = raw |> put ["original";"mechanism_model";"body";"delays";"onset_ticks"] (Json.int 2)
      |> put ["original";"source_authority";"control_contract";"actual_delays";"onset_ticks"] (Json.int 2) in
  let body = get "body" (get "mechanism_model" (get "original" changed)) in
  let digest = str (Canonical.fingerprint body) in
  let changed = changed |> put ["original";"mechanism_model";"identity";"content_fingerprint"] digest
      |> put ["original";"catalog_binding";"model_identity";"content_fingerprint"] digest in
  let next = P.construct_candidate ~charge (R.of_json changed) in
  require ((I.delays (C.implementation next)).onset_ticks = 2 &&
    I.fingerprint (C.implementation next) <> I.fingerprint implementation)
    "Proposal ignored a changed independent model with valid full identity";
  let cancelled = try ignore (P.construct_candidate ~charge:(fun _ -> raise Exit) request); false with Exit -> true in
  require cancelled "Caller cancellation was swallowed";
  let calls = ref 0 in
  let stopped = try ignore (P.construct_candidate ~charge:(fun _ -> incr calls;
      if !calls = 2 then Diagnostic.fail "outer_work" "Original owner stopped construction") request); false
    with Diagnostic.Error diagnostic -> diagnostic.code = "outer_work" in
  require (stopped && !calls = 2) "Original enclosing work failure was swallowed";
  Printf.printf "controlled behavior producer: %d checks; cumulative work %d\n" !checks !charged
let () =
  if Array.length Sys.argv <> 3 then failwith "Expected behavior request and independent candidate literal fixtures";
  run Sys.argv.(1) Sys.argv.(2)
