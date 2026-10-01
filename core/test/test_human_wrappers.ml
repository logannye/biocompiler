open Bioc_wire
module M = Bioc_domain.Measurement_contract
module H = Bioc_domain.Human_contract
module W = Bioc_domain.Human_request
module B = Bioc_domain.Build_request
module C = Bioc_domain.Circuit_request
let require condition message = if not condition then failwith message
let field = M.field
let str value = Json.String value
let replace key replacement value = Json.Object (M.replace key replacement (Json.object_fields value))
let rejected label code operation = match operation () with
  | () -> failwith (label ^ ": intended rejection accepted")
  | exception Diagnostic.Error diagnostic -> require (diagnostic.code = code)
      (label ^ ": expected " ^ code ^ ", got " ^ diagnostic.code ^ ": " ^ diagnostic.message)
let decoded = function C.Decoded value -> value | C.Unsupported _ -> failwith "Complete typed source was treated as opaque authority"
let claim = Json.parse {|{"schema_version":"biocompiler.target_claim.v0.1","description":"Artificial declaration.","basis":"assumed","evidence_ids":[],"limitations":"No empirical validation."}|}
let duration value = Json.Object ["kind", str "scalar"; "value", value; "canonical_value", value; "unit", str "s"; "type", Bioc_domain.Type_spec.to_json M.duration_type]
let literals () =
  let parsed = B.Target_claim.of_json claim in
  require (Json.equal claim (B.Target_claim.to_json parsed) && B.Target_claim.evidence_ids parsed = []) "Target claim authority changed";
  rejected "claim evidence" "invalid_target_claim" (fun () -> ignore (B.Target_claim.of_json (replace "basis" (str "cited") claim)));
  let positive = M.Scalar.duration ~positive:true (duration (Json.int 1)) in
  require (Json.equal (M.Scalar.to_json positive) (duration (Json.int 1))) "Duration numeric representation changed";
  let negative_zero = M.Scalar.duration (duration (Json.Float (-0.))) in
  require (Json.equal (M.Scalar.to_json negative_zero) (duration (Json.Float (-0.)))) "Negative zero duration was relabelled";
  rejected "strict duration positivity" "invalid_measurement_contract" (fun () -> ignore (M.Scalar.duration ~positive:true (duration (Json.int 0))));
  rejected "Boolean duration" "invalid_type" (fun () -> ignore (M.Scalar.duration (duration (Json.Bool true))));
  rejected "raw nonfinite" "nonfinite_number" (fun () -> M.preflight (Json.Array [Json.Float infinity]));
  rejected "raw duplicate" "duplicate_key" (fun () -> M.preflight (Json.Object ["x", Json.Null; "x", Json.Null]));
  let rec value_cycle = Json.Array [value_cycle] in
  let rec array_spine = Json.Null :: array_spine in
  let rec object_spine = ("x", Json.Null) :: object_spine in
  rejected "native value cycle" "human_record_cycle" (fun () -> M.preflight value_cycle);
  rejected "native array spine" "human_record_limit" (fun () -> M.preflight (Json.Array array_spine));
  rejected "native object spine" "human_record_limit" (fun () -> M.preflight (Json.Object object_spine));
  rejected "native constructor list" "human_record_limit" (fun () -> ignore (M.bounded_list array_spine));
  let rec nested depth = if depth = 0 then Json.Null else Json.Array [nested (depth - 1)] in
  M.preflight (nested Limits.max_depth);
  rejected "native nesting" "human_record_limit" (fun () -> M.preflight (nested (Limits.max_depth + 1)));
  M.preflight (Json.Array (List.init (Limits.max_json_nodes - 1) (fun _ -> Json.Null)));
  rejected "native value census" "human_record_limit" (fun () -> M.preflight (Json.Array (List.init Limits.max_json_nodes (fun _ -> Json.Null))));
  let repeated = Json.String (String.make Limits.max_string_bytes 'x') in
  rejected "aggregate byte expansion" "human_record_limit" (fun () -> M.preflight (Json.Array [repeated; repeated; repeated; repeated]));
  rejected "strict fixed Boolean" "invalid_human_contract" (fun () -> ignore (H.External_shutdown.of_json (Json.Object [
      "schema_version", str H.External_shutdown.schema_version; "id", str "stop"; "request_definition", str "Recorded request";
      "observation_method", str "Artificial log"; "response_delay", duration (Json.int 0); "observability", claim; "controllability", claim;
      "request_access", str "external_evaluator"; "persistence", str "latched_for_remaining_horizon"; "requirement", str "background_after_deadline";
      "overrides_source_guard", Json.int 0; "actuator_support", str "unimplemented"])));
  print_endline "human wrappers: independent typed numeric, fixed policy, provenance and native resource literals passed"

let source_kind = function "build" | "behavior_request" | "deployment_request" | "acceptance_request" -> true | _ -> false
let inspect kind raw =
  if source_kind kind then let value = W.of_json raw in W.to_json value, W.fingerprint value
  else let json = match kind with
  | "target_claim" -> B.Target_claim.of_json raw |> B.Target_claim.to_json
  | "observable" -> M.Observable.of_json raw |> M.Observable.to_json
  | "response" -> M.Response.of_json raw |> M.Response.to_json
  | "measurement" -> H.Measurement.of_json raw |> H.Measurement.to_json
  | "predicate" -> H.Predicate.of_json raw |> H.Predicate.to_json
  | "conditional_secretion" -> H.Conditional_secretion.of_json raw |> H.Conditional_secretion.to_json
  | "platform" -> H.Platform.of_json raw |> H.Platform.to_json
  | "exposure" -> H.Exposure.of_json raw |> H.Exposure.to_json
  | "timing" -> H.Expression_timing.of_json raw |> H.Expression_timing.to_json
  | "co_payload" -> H.Co_payload.of_json raw |> H.Co_payload.to_json
  | "deployment" -> H.Deployment.of_json raw |> H.Deployment.to_json
  | "input_availability" -> H.Input_availability.of_json raw |> H.Input_availability.to_json
  | "shutdown" -> H.External_shutdown.of_json raw |> H.External_shutdown.to_json
  | "acceptance" -> H.Acceptance.of_json raw |> H.Acceptance.to_json
  | "profile" -> C.Profile.of_json raw |> decoded |> C.Profile.to_json
  | "circuit" -> C.of_json raw |> decoded |> C.to_json
  | _ -> failwith ("Unknown human fixture kind " ^ kind)
  in json, Canonical.fingerprint json
let validate_children kind raw = match kind with
  | "behavior_request" -> ignore (B.of_json (field "build_request" raw)); ignore (H.Conditional_secretion.of_json (field "contract" raw))
  | "deployment_request" -> ignore (W.Behavior_request.of_json (field "behavior_request" raw)); ignore (H.Deployment.of_json (field "deployment" raw))
  | "acceptance_request" -> ignore (W.Deployment_request.of_json (field "deployment_request" raw)); ignore (H.Acceptance.of_json (field "acceptance" raw))
  | "circuit" -> ignore (C.Profile.of_json (field "profile" raw) |> decoded);
      List.iter (fun raw -> ignore (C.Requirement.of_json raw)) (Json.array (field "requirements" raw))
  | _ -> failwith "Fixture claims a wrapper stage for an ordinary record"
let read_json path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
      let size = in_channel_length channel in require (size <= Limits.max_request_bytes) "Human corpus exceeds read budget";
      Json.parse (really_input_string channel size))
let retained path =
  let corpus = read_json path in
  require (field "schema_version" corpus = str "biocompiler.human_wrappers_conformance.v1") "Unknown human corpus schema";
  let records = Json.array (field "records" corpus) and rejections = Json.array (field "rejections" corpus)
  and literals = Json.array (field "literal_expectations" corpus) in
  require (List.length records >= 40 && List.length rejections >= 244 && List.length literals = 4) "Missing human wrapper corpus cases";
  let coverage = field "coverage" corpus in
  require (field "positive_count" coverage = Json.int (List.length records) && field "rejection_count" coverage = Json.int (List.length rejections)
      && field "independent_literal_count" coverage = Json.int (List.length literals)) "Incorrect human corpus census";
  let expected_kinds = ["acceptance"; "acceptance_request"; "behavior_request"; "build"; "circuit"; "co_payload";
    "conditional_secretion"; "deployment"; "deployment_request"; "exposure"; "input_availability"; "measurement";
    "observable"; "platform"; "predicate"; "profile"; "response"; "shutdown"; "target_claim"; "timing"] in
  let kinds = List.map (fun item -> Json.string (field "kind" item)) records |> List.sort_uniq String.compare in
  require (kinds = expected_kinds && field "kinds" coverage = Json.Array (List.map str expected_kinds)) "Human corpus omits a structural record family";
  let ids = List.map (fun item -> Json.string (field "id" item)) (records @ rejections) in
  require (List.length ids = List.length (List.sort_uniq String.compare ids)) "Duplicate human fixture identity";
  let inventory = Json.Array (List.map str (List.sort String.compare ids)) in
  require (Canonical.fingerprint inventory = "328ae5ce04ba46dc940e215b0533f211fa21e3abdcb2f2165d941468b1ee441a") "Changed or missing retained human case inventory";
  let failure_inventory = List.sort (fun left right -> String.compare (Json.string (field "id" left)) (Json.string (field "id" right))) rejections
    |> List.map (fun item -> Json.Array (List.map (fun key -> field key item) ["id"; "kind"; "expected_stage"; "expected_code"])) |> fun values -> Json.Array values in
  require (Canonical.fingerprint failure_inventory = "874807705594153a7ab0da6e26743f0e1465e6cab4506861defe4916a0e13b29") "Changed human rejection stage or diagnostic inventory";
  List.iter (fun item ->
      let id = Json.string (field "id" item) and kind = Json.string (field "kind" item) in
      let normalized, semantic = inspect kind (field "input" item) in
      require (Json.equal normalized (field "normalized" item)) (id ^ ": full normalized authority changed");
      require (str semantic = field "fingerprint" item && str (Canonical.fingerprint normalized) = field "artifact_fingerprint" item) (id ^ ": authority identity changed");
      let again, again_id = inspect kind normalized in
      require (Json.equal normalized again && semantic = again_id) (id ^ ": repeated import changed authority");
      if source_kind kind then (
        let value = W.of_json normalized in
        require (Json.Array (List.map str (W.unresolved_evidence value)) = field "unresolved_evidence" item) (id ^ ": evidence obligation paths changed");
        require (List.mem "candidate_acceptance" (W.unimplemented_obligations value)) "Structural wrapper import granted candidate acceptance";
        if kind = "acceptance_request" then require (List.mem "human_shutdown_actuator" (W.unimplemented_obligations value)) "Shutdown actuator silently implemented");
      if kind = "profile" then (
        let value = C.Profile.of_json normalized |> decoded in
        match C.Profile.source_request value with
        | None -> failwith "Human profile lost complete original source"
        | Some original -> require (Json.equal (W.to_json original) (field "source_request" normalized)) "Human profile unwrapped original authority");
      if kind = "circuit" then (
        let value = C.of_json normalized |> decoded in
        require (C.requested_form value = Json.string (field "requested_form" normalized)) "Circuit form accessor changed authority")) records;
  List.iter (fun item ->
      let id = Json.string (field "id" item) and kind = Json.string (field "kind" item) and raw = field "input" item in
      (match Json.string (field "expected_stage" item) with
       | "record" -> () | "wrapper" | "circuit" -> validate_children kind raw
       | _ -> failwith "Unknown human rejection stage");
      rejected id (Json.string (field "expected_code" item)) (fun () -> ignore (inspect kind raw))) rejections;
  List.iter (fun literal ->
      let id = field "id" literal in
      let item = List.find (fun item -> field "id" item = id) records in
      let normalized, _ = inspect (Json.string (field "kind" item)) (field "input" item) in
      require (Json.equal normalized (field "normalized" literal)) "Independent complete record literal changed") literals;
  let by_id id = List.find (fun item -> field "id" item = str id) records in
  let original = by_id "base/behavior_request" and moved = by_id "behavior/source_only_relocation" in
  require (field "fingerprint" original = field "fingerprint" moved && field "artifact_fingerprint" original <> field "artifact_fingerprint" moved)
    "Diagnostic relocation lost semantic/full-identity distinction";
  Printf.printf "human wrappers: %d exact records, %d intended staged failures and %d independent literals passed\n" (List.length records) (List.length rejections) (List.length literals)
let () = match Array.to_list Sys.argv with
  | [_] -> literals ()
  | [_; path] -> literals (); retained path
  | _ -> failwith "Usage: test_human_wrappers.exe [required-human-wrappers-v1.json]"
