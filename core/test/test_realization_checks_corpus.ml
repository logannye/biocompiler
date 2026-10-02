open Bioc_wire
open Bioc_domain
module C = Realization_contract
module E = Realization_evidence
module A = Admission
module P = Bioc_checker.Admission_check
module R = Bioc_realization_checker.Realization_check
module Q = Bioc_realization_checker.Checked_request
let require condition message = if not condition then failwith message
let field key value = Json.field key (Json.object_fields value)
let text key value = Json.string (field key value)
let array key value = Json.array (field key value)
let integer value = Z.to_int (Json.integer value)
let obj value = Json.Object value
let str value = Json.String value
let strings value = Json.Array (List.map str value)
let pin = "8ddc5a929f90e8364e3ffb53c6902ff23bd5dec2524897a8d463f543b887d80a"
let capture_pin = "05d24d0ff4450fc072ba2db4af4a608f6a929aa0f3a6680c2cb9cf29082f046e"
let document_count = 26410
let total_bytes = 201611674
let hash value =
  require (String.length value = 64 && String.for_all (function '0'..'9' | 'a'..'f' -> true | _ -> false) value)
    "Unsafe realization fixture hash"; value
let read path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let bytes = in_channel_length channel in require (bytes <= Limits.max_request_bytes) "Oversized realization fixture";
    let payload = really_input_string channel bytes in let value = Json.parse payload in
    require (Canonical.encode value ^ "\n" = payload) "Noncanonical realization fixture"; value, bytes)
let equal label left right = require (Canonical.encode left = Canonical.encode right) (label ^ ": full record or numeric identity differs")
let props fingerprint = Some (obj ["fingerprint", str fingerprint])
let freshness value = E.Freshness_report.to_json value,
  Some (obj ["fresh", Json.Bool (E.Freshness_report.fresh value); "status", str (E.Freshness_report.status value)])
let assessment value = A.Assessment.to_json value, props (A.Assessment.fingerprint value)
let rec normalize operation value = match operation with
  | "checker_version_mutation" ->
      let api = text "api" value and version = text "checker_version" value in
      require (List.mem api ["realization_dependencies"; "check_realization"]
        && List.mem version ["changed"; "changed.v999"]) "Unreviewed original checker-version mutation";
      let current, _ = normalize api (field "authority" value) in
      let dependencies result = if api = "realization_dependencies" then result else field "dependencies" result in
      let replace key replacement value = obj ((key, replacement) :: List.remove_assoc key (Json.object_fields value)) in
      let with_checker version result =
        let changed = replace "checker" (str version) (dependencies result) in
        if api = "realization_dependencies" then changed else replace "dependencies" changed result in
      require (text "checker" (dependencies current) = R.checker_version && version <> R.checker_version)
        "Current native checker identity differs";
      equal "Full current authority before original version mutation" current
        (with_checker R.checker_version (field "original_result" value));
      let mutated = with_checker version current in
      equal "Full original version mutant" mutated (field "original_result" value);
      require (E.Dependency_snapshot.changed (E.Dependency_snapshot.of_json (dependencies current))
        (E.Dependency_snapshot.of_json (dependencies mutated)) = ["checker"]) "Wrong checker-version invalidation";
      normalize (if api = "realization_dependencies" then "DependencySnapshot" else "CheckResult") mutated
  | "RealizationRequest" ->
      let request = Q.of_json value in
      Q.to_json request, Some (obj ["fingerprint", str (Q.fingerprint request);
        "artifact_fingerprint", str (Q.artifact_fingerprint request);
        "upstream_request_fingerprint", str (Realization_request.upstream_request_fingerprint (Q.request request));
        "target", Build_request.Target.to_json (Q.target request)])
  | "check_realization" | "realization_dependencies" ->
      let behavior = Behavior.of_json (field "behavior" value) in
      let contract = C.Behavior_contract.of_json (field "contract" value) in
      let domain = C.Operating_domain.of_json (field "domain" value) in
      let target = Build_request.Target.of_json (field "target" value) in
      let mechanism = Mechanism.of_json (field "mechanism" value) in
      let observation_map = Observation_map.of_json (field "observation_map" value) in
      let history = array "history" value |> List.map Execution_data.Input_frame.of_json in
      let until = match field "until" value with Json.Null -> None | value -> Some (Runtime_number.of_json value) in
      if operation = "realization_dependencies" then (
        let result = R.dependencies ?until behavior contract domain target mechanism observation_map history in
        E.Dependency_snapshot.to_json result, props (E.Dependency_snapshot.fingerprint result))
      else (
        let result = R.check ?until behavior contract domain target mechanism observation_map history in
        E.Check_result.to_json result, Some (obj ["fingerprint", str (E.Check_result.fingerprint result);
          "passed", Json.Bool (E.Check_result.passed result);
          "exercised_requirement_ids", strings (E.Check_result.exercised_requirement_ids result)]))
  | "Observable" -> let value = C.Observable.of_json value in C.Observable.to_json value, props (C.Observable.fingerprint value)
  | "InputDomain" -> let value = C.Input_domain.of_json value in C.Input_domain.to_json value, props (C.Input_domain.fingerprint value)
  | "OperatingDomain" -> let value = C.Operating_domain.of_json value in C.Operating_domain.to_json value, props (C.Operating_domain.fingerprint value)
  | "ResponseRequirement" -> let value = C.Response.of_json value in C.Response.to_json value, props (C.Response.fingerprint value)
  | "BehaviorContract" -> let value = C.Behavior_contract.of_json value in C.Behavior_contract.to_json value, props (C.Behavior_contract.fingerprint value)
  | "DependencySnapshot" -> let value = E.Dependency_snapshot.of_json value in
      E.Dependency_snapshot.to_json value, props (E.Dependency_snapshot.fingerprint value)
  | "FreshnessReport" -> E.Freshness_report.of_json value |> freshness
  | "CheckDiagnostic" -> E.Check_diagnostic.of_json value |> E.Check_diagnostic.to_json, None
  | "Counterexample" -> E.Counterexample.of_json value |> E.Counterexample.to_json, None
  | "RequirementCoverage" -> E.Requirement_coverage.of_json value |> E.Requirement_coverage.to_json, None
  | "CheckResult" ->
      let value = E.Check_result.of_json value in E.Check_result.to_json value,
      Some (obj ["fingerprint", str (E.Check_result.fingerprint value); "passed", Json.Bool (E.Check_result.passed value);
        "exercised_requirement_ids", strings (E.Check_result.exercised_requirement_ids value)])
  | "AdmissionRequest" -> let value = A.Request.of_json value in A.Request.to_json value, props (A.Request.fingerprint value)
  | "AdmissionAssessment" -> A.Assessment.of_json value |> assessment
  | "InputDomain.contains" | "ResponseRequirement.accepts" ->
      let sample = match text "value_kind" value with
        | "scalar_literal" -> C.sample_of_scalar_json (field "value" value)
        | "json" -> C.sample_of_json (field "value" value)
        | _ -> failwith "Unknown captured membership type" in
      let result = if operation = "InputDomain.contains" then
          C.Input_domain.contains (C.Input_domain.of_json (field "subject" value)) sample
        else C.Response.accepts (C.Response.of_json (field "subject" value)) sample ~active:(Json.boolean (field "active" value)) in
      Json.Bool result, None
  | "DependencySnapshot.changed" -> strings (E.Dependency_snapshot.changed
      (E.Dependency_snapshot.of_json (field "subject" value)) (E.Dependency_snapshot.of_json (field "current" value))), None
  | "CheckResult.freshness" -> E.Check_result.freshness (E.Check_result.of_json (field "subject" value))
      (E.Dependency_snapshot.of_json (field "current" value)) |> freshness
  | "CheckResult.is_fresh" -> Json.Bool (E.Check_result.is_fresh (E.Check_result.of_json (field "subject" value))
      (E.Dependency_snapshot.of_json (field "current" value))), None
  | "AdmissionAssessment.is_current" -> Json.Bool (A.Assessment.is_current (A.Assessment.of_json (field "subject" value))
      (A.Request.of_json (field "current" value))), None
  | "assess_admission" -> A.Request.of_json (field "request" value) |> P.assess |> assessment
  | "verify_admission" -> Json.Bool (P.verify (A.Request.of_json (field "request" value))
      (A.Assessment.of_json (field "assessment" value))), None
  | "admission_for_target" | "require_software_use" ->
      let target = Build_request.Target.of_json (field "target" value) in
      let boundary = A.boundary_of_json (field "boundary" value) in
      let components = array "components" value |> List.map Component.of_json in
      (if operation = "admission_for_target" then P.for_target ~target ~boundary ~components
       else P.require_software_use ~target ~boundary ~components) |> assessment
  | _ -> failwith ("Unimplemented realization corpus operation: " ^ operation)
let run path =
  require (not (Filename.is_relative path)) "Absolute realization corpus path required";
  let index, size = read path in
  require (text "schema_version" index = "biocompiler.realization_checks_conformance.v1") "Wrong realization corpus schema";
  require (text "claim_scope" index = "checked_request_correspondence_and_supplied_finite_history_realization_only_no_generic_component_acceptance_or_biology") "Foundation claim widened";
  require (text "inventory_fingerprint" index = pin && Canonical.fingerprint
    (obj (List.remove_assoc "inventory_fingerprint" (Json.object_fields index))) = pin) "Complete realization corpus identity differs";
  require (text "original_capture_fingerprint" index = capture_pin) "Original complete realization capture differs";
  let docs = Hashtbl.create 20000 and kinds = Hashtbl.create 20000 and used = Hashtbl.create 20000 in
  let total = ref size and directory = Filename.remove_extension path in
  let descriptors = array "documents" index in
  require (List.length descriptors = document_count) "Incomplete realization document inventory";
  List.iter (fun descriptor ->
    Json.exact_fields ["id"; "kind"; "bytes"] (Json.object_fields descriptor);
    let id = hash (text "id" descriptor) in require (not (Hashtbl.mem docs id)) "Duplicate realization document";
    let value, bytes = read (Filename.concat directory (id ^ ".json")) in
    require (bytes = integer (field "bytes" descriptor) && bytes <= 256 * 1024 * 1024 - !total) "Realization storage bound or byte count changed";
    total := !total + bytes; require (Canonical.fingerprint value = id) "Realization document hash differs";
    Hashtbl.add docs id value; Hashtbl.add kinds id (text "kind" descriptor)) descriptors;
  require (!total = total_bytes) "Complete realization byte census changed";
  require ((Array.to_list (Sys.readdir directory) |> List.sort String.compare) =
    (List.map (fun descriptor -> text "id" descriptor ^ ".json") descriptors |> List.sort String.compare)) "Missing or extra realization fixture";
  let use kind id =
    let id = hash id in require (Hashtbl.find_opt kinds id = Some kind) "Wrong realization fixture kind";
    Hashtbl.replace used id (); Hashtbl.find docs id in
  let coverage = field "coverage" index in
  List.iter (fun (key, expected) -> require (integer (field key coverage) = expected) ("Wrong realization census: " ^ key))
    ["original_methods",340; "contexts",348; "api_calls",74803; "subprocess_invocations",2; "unclassified_observations",0];
  let contexts = array "contexts" index and locations = array "source_locations" index in
  require (List.length contexts = 348 && List.length (array "subprocesses" index) = 2) "Missing original contexts or children";
  let call_order = use "call_order" (text "capture_call_order" index) |> Json.array in
  let context_array = Array.of_list contexts and ordered = Hashtbl.create 75000 in
  require (List.length call_order = 74803) "Incomplete original call ordering";
  List.iter (fun value -> match Json.array value with
    | [context; number] ->
        let context = integer context and number = integer number in
        require (context >= 0 && context < Array.length context_array && number >= 0
          && number < integer (field "api_calls" context_array.(context))) "Invalid original ordered call";
        require (not (Hashtbl.mem ordered (context, number))) "Duplicate original ordered call";
        Hashtbl.add ordered (context, number) ()
    | _ -> failwith "Invalid original call order shape") call_order;
  let seen = Hashtbl.create 340 and stages = Hashtbl.create 8 and operations = Hashtbl.create 30 and apis = Hashtbl.create 50 in
  let returned = ref 0 and raised = ref 0 and count = ref 0 and failures = ref [] in
  let increment table key = Hashtbl.replace table key (1 + Option.value (Hashtbl.find_opt table key) ~default:0) in
  let checked label action = try action () with error ->
    let detail = match error with Diagnostic.Error error -> error.code ^ ": " ^ error.message | _ -> Printexc.to_string error in
    let detail = label ^ ": " ^ detail in failures := detail :: !failures; Printf.eprintf "realization corpus failure: %s\n%!" detail in
  List.iter (fun context ->
    let context_id = text "id" context in require (not (Hashtbl.mem seen context_id)) "Duplicate realization context";
    Hashtbl.add seen context_id (); require (text "assertion_status" context = "passed") "Original assertion failed";
    let rows = use "api_ledger" (text "ledger" context) |> array "observations" in
    require (List.length rows = integer (field "api_calls" context)) "Incomplete observation ledger";
    List.iteri (fun number call ->
      incr count; let label = context_id ^ "/api/" ^ string_of_int number in
      (match field "parent" call with Json.Null -> () | value -> require (integer value >= 0 && integer value < number) "Invalid nested call parent");
      let location = integer (field "source" call) in require (location >= 0 && location < List.length locations) "Missing source callsite";
      ignore (use "raw_arguments" (text "input" call) |> Json.string);
      ignore (use "python_types" (text "python_types" call) |> Json.array);
      increment apis (text "api" call);
      let returned_call = text "outcome" call = "returned" in
      require (returned_call || text "outcome" call = "raised") "Unknown captured outcome";
      if returned_call then incr returned else incr raised;
      let expected = if returned_call then Some (use (text "result_format" call) (text "result" call)) else (
        Json.exact_fields ["module"; "type"; "message"] (Json.object_fields (field "error" call)); None) in
      let properties = match List.assoc_opt "properties" (Json.object_fields call) with
        None -> None | Some id -> Some (use "record" (Json.string id)) in
      let native = field "native" call in
      (match List.assoc_opt "serialized_error" (Json.object_fields call) with
      | None -> ()
      | Some error ->
          require (not returned_call && text "source_stage" native = "constructor") "Invalid constructor/import error distinction";
          Json.exact_fields ["module"; "type"; "message"] (Json.object_fields error));
      let operation = text "operation" native and stage = text "native_stage" native in
      increment operations operation; increment stages stage;
      if stage = "deferred_acceptance" then (
        require (List.mem operation ["check_component_behavior"; "check_component_assembly"])
          "Implemented operation silently deferred";
        require (text "obligation" native = "independent_generic_component_acceptance_and_correspondence_remain_unimplemented") "Deferred acceptance obligation lost")
      else (
        let raw = use (text "input_format" native) (text "input" native) |> Json.string in
        let counterpart = List.assoc_opt "counterpart" (Json.object_fields call) in
        let expected = match counterpart with None -> expected | Some value ->
          require (stage = "python_type_boundary" && not returned_call) "Invalid typed counterpart classification";
          if text "outcome" value = "returned" then Some (use "record" (text "result" value)) else None in
        checked label (fun () ->
          let execute () = normalize operation (Json.parse raw) in
          match field "expected_code" native with
          | Json.String code ->
              (match (if stage = "wire" || stage = "python_wire_boundary" then ignore (Json.parse raw) else ignore (execute ())) with
              | () -> failwith "Expected rejection was accepted"
              | exception Diagnostic.Error error -> require (error.code = code)
                  ("Expected " ^ code ^ ", got " ^ error.code ^ ": " ^ error.message))
          | Json.Null ->
              require (List.mem stage ["domain"; "method"; "admission"; "checked_request"; "dependencies"; "realization"; "checker_version_mutation"; "python_type_boundary"]) "Invalid success stage";
              let actual, actual_properties = execute () in
              (match expected with None -> failwith "Missing complete expected result" | Some expected -> equal label actual expected);
              if stage <> "python_type_boundary" then (
                match properties, actual_properties with
                | None, None -> () | Some expected, Some actual -> equal (label ^ "/properties") actual expected
                | _ -> failwith "Missing or extra complete record properties")
          | _ -> failwith "Invalid native diagnostic expectation"))) rows) contexts;
  require (!count = 74803 && !returned = 69580 && !raised = 5223) "Complete original outcome census changed";
  List.iter (fun (key, table) ->
    let expected = Json.object_fields (field key coverage) in require (List.length expected = Hashtbl.length table) "Unexpected native operation family";
    List.iter (fun (key, value) -> require (Hashtbl.find_opt table key = Some (integer value)) ("Incomplete native census: " ^ key)) expected)
    ["native_stages",stages; "native_operations",operations; "api_census",apis];
  require (Hashtbl.length used = Hashtbl.length docs) "Unreachable retained realization fixture";
  require (!failures = []) (Printf.sprintf "%d realization observations failed" (List.length !failures));
  Printf.printf "realization checks: all340methods/348contexts/74803observations retained; checked request correspondence and supplied-history realization checked; generic component acceptance explicitly deferred\n%!"
let () =
  if Array.length Sys.argv <> 2 then failwith "One complete realization foundation corpus path is mandatory";
  run Sys.argv.(1)
