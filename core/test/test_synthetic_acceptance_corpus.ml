open Bioc_wire
open Bioc_domain
module S = Synthetic_authority
module C = Realization_contract
module E = Realization_evidence
module R = Bioc_realization_checker.Realization_check
module B = Bioc_realization_checker.Component_behavior_check
module Y = Bioc_realization_checker.Synthetic_candidate_check
module A = Bioc_realization_checker.Component_assembly_check
let require condition message = if not condition then failwith message
let field key value = Json.field key (Json.object_fields value)
let text key value = Json.string (field key value)
let array key value = Json.array (field key value)
let integer value = Z.to_int (Json.integer value)
let obj value = Json.Object value
let str value = Json.String value
let pin = "d32009a03f0af00de4da60f0244c210ba15b9ff89e828ea56c82b5f9e4a73331"
let capture_pin = "9b17701d25eb2dfe1ecef87eccc46dc506475ae34d90fcce8bcda88b6e058f29"
let document_count = 4910
let total_bytes = 109400531
let hash value =
  require (String.length value = 64 && String.for_all (function '0'..'9' | 'a'..'f' -> true | _ -> false) value)
    "Unsafe synthetic acceptance fixture hash"; value
let read path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let bytes = in_channel_length channel in require (bytes <= Limits.max_request_bytes) "Oversized synthetic acceptance fixture";
    let payload = really_input_string channel bytes in let value = Json.parse payload in
    require (Canonical.encode value ^ "\n" = payload) "Noncanonical synthetic acceptance fixture"; value, bytes)
let equal label left right = require (Canonical.encode left = Canonical.encode right) (label ^ ": full record or numeric identity differs")
let props fingerprint = Some (obj ["fingerprint", str fingerprint])
let horizon value = match field "until" value with Json.Null -> None | value -> Some (Runtime_number.of_json value)
let history value = array "history" value |> List.map Execution_data.Input_frame.of_json
let rec normalize operation value = match operation with
  | "checker_version_mutation" ->
      let api = text "api" value and version = text "checker_version" value in
      require (List.mem api ["realization_dependencies"; "check_realization"; "check_synthetic_candidate"]
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
      mutated, None
  | "check_realization" | "realization_dependencies" ->
      let behavior = Behavior.of_json (field "behavior" value) in
      let contract = C.Behavior_contract.of_json (field "contract" value) in
      let domain = C.Operating_domain.of_json (field "domain" value) in
      let target = Build_request.Target.of_json (field "target" value) in
      let mechanism = Mechanism.of_json (field "mechanism" value) in
      let observation_map = Observation_map.of_json (field "observation_map" value) in
      let history = history value and until = horizon value in
      if operation = "realization_dependencies" then
        R.dependencies ?until behavior contract domain target mechanism observation_map history
        |> E.Dependency_snapshot.to_json, None
      else R.check ?until behavior contract domain target mechanism observation_map history |> E.Check_result.to_json, None
  | "check_synthetic_candidate" | "check_component_assembly" | "check_component_behavior" ->
      let request = Realization_request.of_json (field "request" value) in
      let history = history value and until = horizon value in
      if operation = "check_component_behavior" then
        B.check ?until request (Component_assembly.of_json (field "assembly" value)) history |> E.Check_result.to_json, None
      else let candidate = S.Candidate.of_json (field "candidate" value) in
        if operation = "check_synthetic_candidate" then Y.check ?until request candidate history |> E.Check_result.to_json, None
        else A.check ?until request candidate (Component_assembly.of_json (field "assembly" value)) history
          |> Composition_evidence.Result.to_json, None
  | "SyntheticComponent" -> let value = S.Component.of_json value in
      S.Component.to_json value, props (S.Component.fingerprint value)
  | "SyntheticCatalog" -> let value = S.Catalog.of_json value in
      S.Catalog.to_json value, props (S.Catalog.fingerprint value)
  | "SyntheticGeneratorConfig" -> let value = S.Config.of_json value in
      S.Config.to_json value, props (S.Config.fingerprint value)
  | "SyntheticCandidate" -> let value = S.Candidate.of_json value in
      S.Candidate.to_json value, props (S.Candidate.fingerprint value)
  | "catalog_for_profile" -> let value = S.catalog_for_profile (text "profile" value) in
      S.Catalog.to_json value, props (S.Catalog.fingerprint value)
  | "SyntheticCatalog.for_operation" ->
      let catalog = S.Catalog.of_json (field "subject" value) in
      (match S.Catalog.for_operation catalog (text "operation" value) with
      | Some value -> S.Component.to_json value, props (S.Component.fingerprint value)
      | None -> Diagnostic.fail "synthetic_catalog_operation" "Synthetic catalog operation unavailable.")
  | "SyntheticCatalog.lock" ->
      let catalog = S.Catalog.of_json (field "subject" value) in
      let mechanism = Mechanism.of_json (field "mechanism" value) in
      Json.Array (S.Catalog.lock catalog mechanism |> List.map Component_registry.Component_lock.to_json), None
  | _ -> failwith ("Unimplemented synthetic acceptance corpus operation: " ^ operation)
let run path =
  require (not (Filename.is_relative path)) "Absolute synthetic acceptance corpus path required";
  let index, size = read path in
  require (text "schema_version" index = "biocompiler.synthetic_acceptance_conformance.v1") "Wrong synthetic acceptance corpus schema";
  require (text "claim_scope" index = "independent_synthetic_and_assembly_acceptance_with_complete_source_authority_no_producer_or_biology") "Synthetic acceptance claim widened";
  require (text "inventory_fingerprint" index = pin && Canonical.fingerprint
    (obj (List.remove_assoc "inventory_fingerprint" (Json.object_fields index))) = pin) "Complete synthetic acceptance corpus identity differs";
  require (text "original_capture_fingerprint" index = capture_pin) "Original complete synthetic acceptance capture differs";
  let docs = Hashtbl.create 6000 and kinds = Hashtbl.create 6000 and used = Hashtbl.create 6000 in
  let total = ref size and directory = Filename.remove_extension path in
  let descriptors = array "documents" index in
  require (List.length descriptors = document_count) "Incomplete synthetic acceptance document inventory";
  List.iter (fun descriptor ->
    Json.exact_fields ["id"; "kind"; "bytes"] (Json.object_fields descriptor);
    let id = hash (text "id" descriptor) in require (not (Hashtbl.mem docs id)) "Duplicate synthetic acceptance document";
    let value, bytes = read (Filename.concat directory (id ^ ".json")) in
    require (bytes = integer (field "bytes" descriptor) && bytes <= 256 * 1024 * 1024 - !total) "Synthetic acceptance storage bound or byte count changed";
    total := !total + bytes; require (Canonical.fingerprint value = id) "Synthetic acceptance document hash differs";
    Hashtbl.add docs id value; Hashtbl.add kinds id (text "kind" descriptor)) descriptors;
  require (!total = total_bytes) "Complete synthetic acceptance byte census changed";
  require ((Array.to_list (Sys.readdir directory) |> List.sort String.compare) =
    (List.map (fun descriptor -> text "id" descriptor ^ ".json") descriptors |> List.sort String.compare)) "Missing or extra synthetic acceptance fixture";
  let use kind id =
    let id = hash id in require (Hashtbl.find_opt kinds id = Some kind) "Wrong synthetic acceptance fixture kind";
    Hashtbl.replace used id (); Hashtbl.find docs id in
  let coverage = field "coverage" index in
  List.iter (fun (key, expected) -> require (integer (field key coverage) = expected) ("Wrong synthetic acceptance census: " ^ key))
    ["original_methods",373; "contexts",381; "api_calls",47758; "subprocess_invocations",2; "unclassified_observations",0];
  let contexts = array "contexts" index and locations = array "source_locations" index in
  require (List.length contexts = 381 && List.length (array "subprocesses" index) = 2) "Missing original contexts or children";
  let call_order = use "call_order" (text "capture_call_order" index) |> Json.array in
  let context_array = Array.of_list contexts and ordered = Hashtbl.create 5000 in
  require (List.length call_order = 47758) "Incomplete original call ordering";
  List.iter (fun value -> match Json.array value with
    | [context; number] ->
        let context = integer context and number = integer number in
        require (context >= 0 && context < Array.length context_array && number >= 0
          && number < integer (field "api_calls" context_array.(context))) "Invalid original ordered call";
        require (not (Hashtbl.mem ordered (context, number))) "Duplicate original ordered call";
        Hashtbl.add ordered (context, number) ()
    | _ -> failwith "Invalid original call order shape") call_order;
  let seen = Hashtbl.create 381 and stages = Hashtbl.create 8 and operations = Hashtbl.create 30 and apis = Hashtbl.create 50 in
  let returned = ref 0 and raised = ref 0 and count = ref 0 and failures = ref [] in
  let increment table key = Hashtbl.replace table key (1 + Option.value (Hashtbl.find_opt table key) ~default:0) in
  let checked label action = try action () with error ->
    let detail = match error with Diagnostic.Error error -> error.code ^ ": " ^ error.message | _ -> Printexc.to_string error in
    let detail = label ^ ": " ^ detail in failures := detail :: !failures; Printf.eprintf "synthetic acceptance corpus failure: %s\n%!" detail in
  List.iter (fun context ->
    let context_id = text "id" context in require (not (Hashtbl.mem seen context_id)) "Duplicate synthetic acceptance context";
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
        require (List.mem operation ["generate_synthetic"; "_generate_synthetic"; "select_synthetic"; "adapt_synthetic_components"])
          "Implemented operation silently deferred";
        require (text "obligation" native = "full_original_producer_observation_retained_no_native_generation_adaptation_or_selection_claim") "Deferred acceptance obligation lost")
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
              require (List.mem stage ["domain"; "catalog"; "python_type_boundary"; "synthetic_acceptance"; "assembly_acceptance"; "component_behavior"; "realization"; "dependencies"; "checker_version_mutation"]) "Invalid success stage";
              let actual, actual_properties = execute () in
              (match expected with None -> failwith "Missing complete expected result" | Some expected -> equal label actual expected);
              if stage <> "python_type_boundary" then (
                match properties, actual_properties with
                | None, None -> () | Some expected, Some actual -> equal (label ^ "/properties") actual expected
                | _ -> failwith "Missing or extra complete record properties")
          | _ -> failwith "Invalid native diagnostic expectation"))) rows) contexts;
  require (!count = 47758 && !returned = 47673 && !raised = 85) "Complete original outcome census changed";
  List.iter (fun (key, table) ->
    let expected = Json.object_fields (field key coverage) in require (List.length expected = Hashtbl.length table) "Unexpected native operation family";
    List.iter (fun (key, value) -> require (Hashtbl.find_opt table key = Some (integer value)) ("Incomplete native census: " ^ key)) expected)
    ["native_stages",stages; "native_operations",operations; "api_census",apis];
  require (Hashtbl.length used = Hashtbl.length docs) "Unreachable retained synthetic acceptance fixture";
  require (!failures = []) (Printf.sprintf "%d synthetic acceptance observations failed" (List.length !failures));
  Printf.printf "synthetic acceptance: all 373 methods / 381 contexts / 47,758 observations retained; full synthetic and assembly acceptance checked; generation, adaptation and selection explicitly deferred\n%!"
let () =
  if Array.length Sys.argv <> 2 then failwith "One complete synthetic acceptance corpus path is mandatory";
  run Sys.argv.(1)
