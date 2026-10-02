open Bioc_wire
open Bioc_domain
module S = Synthetic_authority
let require condition message = if not condition then failwith message
let field key value = Json.field key (Json.object_fields value)
let text key value = Json.string (field key value)
let array key value = Json.array (field key value)
let integer value = Z.to_int (Json.integer value)
let obj value = Json.Object value
let str value = Json.String value
let pin = "caf19f88640281b28b4ea4a39d131a5e2ecf8c696465af1c5a020a265aa161fa"
let capture_pin = "9b17701d25eb2dfe1ecef87eccc46dc506475ae34d90fcce8bcda88b6e058f29"
let document_count = 3759
let total_bytes = 75488401
let hash value =
  require (String.length value = 64 && String.for_all (function '0'..'9' | 'a'..'f' -> true | _ -> false) value)
    "Unsafe synthetic authority fixture hash"; value
let read path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let bytes = in_channel_length channel in require (bytes <= Limits.max_request_bytes) "Oversized synthetic authority fixture";
    let payload = really_input_string channel bytes in let value = Json.parse payload in
    require (Canonical.encode value ^ "\n" = payload) "Noncanonical synthetic authority fixture"; value, bytes)
let equal label left right = require (Canonical.encode left = Canonical.encode right) (label ^ ": full record or numeric identity differs")
let props fingerprint = Some (obj ["fingerprint", str fingerprint])
let normalize operation value = match operation with
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
  | _ -> failwith ("Unimplemented synthetic authority corpus operation: " ^ operation)
let run path =
  require (not (Filename.is_relative path)) "Absolute synthetic authority corpus path required";
  let index, size = read path in
  require (text "schema_version" index = "biocompiler.synthetic_authority_conformance.v1") "Wrong synthetic authority corpus schema";
  require (text "claim_scope" index = "synthetic_catalog_configuration_and_candidate_authority_only_no_generation_source_correspondence_or_biology") "Synthetic authority claim widened";
  require (text "inventory_fingerprint" index = pin && Canonical.fingerprint
    (obj (List.remove_assoc "inventory_fingerprint" (Json.object_fields index))) = pin) "Complete synthetic authority corpus identity differs";
  require (text "original_capture_fingerprint" index = capture_pin) "Original complete synthetic authority capture differs";
  let docs = Hashtbl.create 6000 and kinds = Hashtbl.create 6000 and used = Hashtbl.create 6000 in
  let total = ref size and directory = Filename.remove_extension path in
  let descriptors = array "documents" index in
  require (List.length descriptors = document_count) "Incomplete synthetic authority document inventory";
  List.iter (fun descriptor ->
    Json.exact_fields ["id"; "kind"; "bytes"] (Json.object_fields descriptor);
    let id = hash (text "id" descriptor) in require (not (Hashtbl.mem docs id)) "Duplicate synthetic authority document";
    let value, bytes = read (Filename.concat directory (id ^ ".json")) in
    require (bytes = integer (field "bytes" descriptor) && bytes <= 256 * 1024 * 1024 - !total) "Synthetic authority storage bound or byte count changed";
    total := !total + bytes; require (Canonical.fingerprint value = id) "Synthetic authority document hash differs";
    Hashtbl.add docs id value; Hashtbl.add kinds id (text "kind" descriptor)) descriptors;
  require (!total = total_bytes) "Complete synthetic authority byte census changed";
  require ((Array.to_list (Sys.readdir directory) |> List.sort String.compare) =
    (List.map (fun descriptor -> text "id" descriptor ^ ".json") descriptors |> List.sort String.compare)) "Missing or extra synthetic authority fixture";
  let use kind id =
    let id = hash id in require (Hashtbl.find_opt kinds id = Some kind) "Wrong synthetic authority fixture kind";
    Hashtbl.replace used id (); Hashtbl.find docs id in
  let coverage = field "coverage" index in
  List.iter (fun (key, expected) -> require (integer (field key coverage) = expected) ("Wrong synthetic authority census: " ^ key))
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
    let detail = label ^ ": " ^ detail in failures := detail :: !failures; Printf.eprintf "synthetic authority corpus failure: %s\n%!" detail in
  List.iter (fun context ->
    let context_id = text "id" context in require (not (Hashtbl.mem seen context_id)) "Duplicate synthetic authority context";
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
        require (List.mem operation ["generate_synthetic"; "_generate_synthetic"; "select_synthetic"; "check_synthetic_candidate"; "adapt_synthetic_components"; "check_component_assembly"; "check_component_behavior"; "check_realization"; "realization_dependencies"])
          "Implemented operation silently deferred";
        require (text "obligation" native = "full_original_observation_retained_not_a_domain_acceptance_or_generation_claim") "Deferred acceptance obligation lost")
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
              require (List.mem stage ["domain"; "catalog"; "python_type_boundary"]) "Invalid success stage";
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
  require (Hashtbl.length used = Hashtbl.length docs) "Unreachable retained synthetic authority fixture";
  require (!failures = []) (Printf.sprintf "%d synthetic authority observations failed" (List.length !failures));
  Printf.printf "synthetic authority: all 373 methods / 381 contexts / 47,758 observations retained; catalog/configuration/candidate domain checked; generation and acceptance explicitly deferred\n%!"
let () =
  if Array.length Sys.argv <> 2 then failwith "One complete synthetic authority corpus path is mandatory";
  run Sys.argv.(1)
