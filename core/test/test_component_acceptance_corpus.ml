open Bioc_wire
open Bioc_domain
module E = Realization_evidence
module L = Composition_evidence
module S = Component_selection
module K = Bioc_checker.Composition_check
module P = Bioc_compiler.Component_selection_producer
module B = Bioc_realization_checker.Component_behavior_check
let require condition message = if not condition then failwith message
let field key value = Json.field key (Json.object_fields value)
let text key value = Json.string (field key value)
let array key value = Json.array (field key value)
let integer value = Z.to_int (Json.integer value)
let obj value = Json.Object value
let str value = Json.String value
let pin = "9eb76b8f697b00be207e6bb2e1cccdfd46ee974b09a3525d21eb4f32634ee116"
let capture_pin = "592dce033ac74ca643b2a53bd590e0033674b42fa95b526e8632db1496dc81fe"
let document_count = 5394
let total_bytes = 30453450
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
let link value = L.Result.to_json value, Some (obj ["fingerprint", str (L.Result.fingerprint value);
  "passed", Json.Bool (L.Result.passed value)])
let selection value = S.Result.to_json value, Some (obj ["fingerprint", str (S.Result.fingerprint value);
  "outcome", str (S.Result.outcome_name (S.Result.outcome value))])
let normalize operation value = match operation with
  | "admission_policy_mutation" ->
      let authority = field "authority" value in
      let api = text "api" value in
      require (List.mem api ["composition_dependencies"; "CompositionResult.freshness"; "CompositionResult.is_fresh"]
        && text "policy_version" value = "future") "Unrecognized original policy mutation";
      let request = Composition.of_json (field "request" authority) in
      let registry = Component_registry.of_json (field "registry" authority) in
      let current = K.dependencies ~request ~registry () |> L.Dependencies.to_json in
      require (text "admission_policy" current = Admission.policy_version) "Current policy version differs";
      let original = field "original_dependencies" value in
      let replace_policy version raw = obj (("admission_policy", str version) :: List.remove_assoc "admission_policy" (Json.object_fields raw)) in
      equal "Complete current dependencies for original policy mutation" current
        (replace_policy Admission.policy_version original);
      let mutated = replace_policy "future" current in
      equal "Complete original policy mutant" mutated original;
      if api = "composition_dependencies" then mutated, None else (
        let previous = field "dependencies" (field "subject" authority) in
        let changed = Json.object_fields mutated |> List.filter_map (fun (key, entry) ->
          if Json.equal entry (field key previous) then None else Some key) |> List.sort String.compare in
        require (changed = ["admission_policy"]) "Wrong policy freshness invalidation";
        if api = "CompositionResult.is_fresh" then Json.Bool false, None
        else E.Freshness_report.make changed |> E.Freshness_report.to_json, None)
  | "ComponentRegistry" -> let value = Component_registry.of_json value in
      Component_registry.to_json value, props (Component_registry.fingerprint value)
  | "SelectionRequest" -> let value = S.Request.of_json value in S.Request.to_json value, props (S.Request.fingerprint value)
  | "SelectionAlternative" -> let value = S.Alternative.of_json value in S.Alternative.to_json value, props (S.Alternative.fingerprint value)
  | "SelectionResult" -> S.Result.of_json value |> selection
  | "LinkDiagnostic" -> let value = L.Link_diagnostic.of_json value in L.Link_diagnostic.to_json value, props (L.Link_diagnostic.fingerprint value)
  | "ResolvedDependency" -> let value = L.Resolved_dependency.of_json value in L.Resolved_dependency.to_json value, props (L.Resolved_dependency.fingerprint value)
  | "ResourceUsage" -> let value = L.Resource_usage.of_json value in L.Resource_usage.to_json value, props (L.Resource_usage.fingerprint value)
  | "CompositionResult" -> L.Result.of_json value |> link
  | "composition_dependencies" | "check_composition" ->
      let request = Composition.of_json (field "request" value) in
      let registry = Component_registry.of_json (field "registry" value) in
      if operation = "composition_dependencies" then K.dependencies ~request ~registry () |> L.Dependencies.to_json, None
      else K.check ~request ~registry () |> link
  | "ComponentRegistry.select" | "ComponentRegistry.verify_selection" ->
      let registry = Component_registry.of_json (field "subject" value) in
      let request = S.Request.of_json (field "request" value) in
      if operation = "ComponentRegistry.select" then P.select ~registry ~request () |> selection
      else Json.Bool (P.verify_selection ~registry ~request (S.Result.of_json (field "result" value))), None
  | "CompositionResult.freshness" | "CompositionResult.is_fresh" ->
      let result = L.Result.of_json (field "subject" value) in
      let request = Composition.of_json (field "request" value) in
      let registry = Component_registry.of_json (field "registry" value) in
      if operation = "CompositionResult.freshness" then L.Result.freshness result ~request ~registry |> E.Freshness_report.to_json, None
      else Json.Bool (L.Result.is_fresh result ~request ~registry), None
  | "check_component_behavior" ->
      let request = Realization_request.of_json (field "request" value) in
      let assembly = Component_assembly.of_json (field "assembly" value) in
      let history = array "history" value |> List.map Execution_data.Input_frame.of_json in
      let until = match field "until" value with Json.Null -> None | raw -> Some (Runtime_number.of_json raw) in
      B.check ?until request assembly history |> E.Check_result.to_json, None
  | _ -> failwith ("Unimplemented component acceptance corpus operation: " ^ operation)
let run path =
  require (not (Filename.is_relative path)) "Absolute realization corpus path required";
  let index, size = read path in
  require (text "schema_version" index = "biocompiler.component_acceptance_conformance.v1") "Wrong realization corpus schema";
  require (text "claim_scope" index = "generic_composition_selection_and_actual_component_behavior_only_no_source_correspondence_or_biology") "Foundation claim widened";
  require (text "inventory_fingerprint" index = pin && Canonical.fingerprint
    (obj (List.remove_assoc "inventory_fingerprint" (Json.object_fields index))) = pin) "Complete realization corpus identity differs";
  require (text "original_capture_fingerprint" index = capture_pin) "Original complete realization capture differs";
  let docs = Hashtbl.create 6000 and kinds = Hashtbl.create 6000 and used = Hashtbl.create 6000 in
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
    ["original_methods",373; "contexts",380; "api_calls",4539; "subprocess_invocations",2; "unclassified_observations",0];
  let contexts = array "contexts" index and locations = array "source_locations" index in
  require (List.length contexts = 380 && List.length (array "subprocesses" index) = 2) "Missing original contexts or children";
  let call_order = use "call_order" (text "capture_call_order" index) |> Json.array in
  let context_array = Array.of_list contexts and ordered = Hashtbl.create 5000 in
  require (List.length call_order = 4539) "Incomplete original call ordering";
  List.iter (fun value -> match Json.array value with
    | [context; number] ->
        let context = integer context and number = integer number in
        require (context >= 0 && context < Array.length context_array && number >= 0
          && number < integer (field "api_calls" context_array.(context))) "Invalid original ordered call";
        require (not (Hashtbl.mem ordered (context, number))) "Duplicate original ordered call";
        Hashtbl.add ordered (context, number) ()
    | _ -> failwith "Invalid original call order shape") call_order;
  let seen = Hashtbl.create 380 and stages = Hashtbl.create 8 and operations = Hashtbl.create 30 and apis = Hashtbl.create 50 in
  let returned = ref 0 and raised = ref 0 and count = ref 0 and failures = ref [] in
  let increment table key = Hashtbl.replace table key (1 + Option.value (Hashtbl.find_opt table key) ~default:0) in
  let checked label action = try action () with error ->
    let detail = match error with Diagnostic.Error error -> error.code ^ ": " ^ error.message | _ -> Printexc.to_string error in
    let detail = label ^ ": " ^ detail in failures := detail :: !failures; Printf.eprintf "component acceptance corpus failure: %s\n%!" detail in
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
        require (List.mem operation ["check_component_assembly"])
          "Implemented operation silently deferred";
        require (text "obligation" native = "independent_source_to_component_correspondence_remains_unimplemented") "Deferred acceptance obligation lost")
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
              require (List.mem stage ["domain"; "method"; "dependencies"; "composition"; "selection"; "selection_replay"; "component_behavior"; "admission_policy_mutation"]) "Invalid success stage";
              let actual, actual_properties = execute () in
              (match expected with None -> failwith "Missing complete expected result" | Some expected -> equal label actual expected);
              if stage <> "python_type_boundary" then (
                match properties, actual_properties with
                | None, None -> () | Some expected, Some actual -> equal (label ^ "/properties") actual expected
                | _ -> failwith "Missing or extra complete record properties")
          | _ -> failwith "Invalid native diagnostic expectation"))) rows) contexts;
  require (!count = 4539 && !returned = 2930 && !raised = 1609) "Complete original outcome census changed";
  List.iter (fun (key, table) ->
    let expected = Json.object_fields (field key coverage) in require (List.length expected = Hashtbl.length table) "Unexpected native operation family";
    List.iter (fun (key, value) -> require (Hashtbl.find_opt table key = Some (integer value)) ("Incomplete native census: " ^ key)) expected)
    ["native_stages",stages; "native_operations",operations; "api_census",apis];
  require (Hashtbl.length used = Hashtbl.length docs) "Unreachable retained realization fixture";
  require (!failures = []) (Printf.sprintf "%d realization observations failed" (List.length !failures));
  Printf.printf "component acceptance: all373methods/380contexts/4539observations retained; composition/selection/actual-component behavior checked; source correspondence explicitly deferred\n%!"
let () =
  if Array.length Sys.argv <> 2 then failwith "One complete realization foundation corpus path is mandatory";
  run Sys.argv.(1)
