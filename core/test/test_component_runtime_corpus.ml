open Bioc_wire
open Bioc_domain
module R = Component_registry
module C = Composition
module A = Component_assembly
module D = Model_execution_data
module E = Bioc_candidate_runtime.Components
module S = Bioc_candidate_runtime.Synthetic
let require value message = if not value then failwith message
let field key value = Json.field key (Json.object_fields value)
let text key value = Json.string (field key value)
let integer value = Json.integer value |> Z.to_int
let array key value = Json.array (field key value)
let pin = "aea8309d6efa172777f550d4a91cd3ebb7b40c301234fc7e90636fb4f466fcbf"
let hash value =
  require (String.length value = 64 && String.for_all (function '0'..'9' | 'a'..'f' -> true | _ -> false) value)
    "Unsafe component-runtime document identity"; value
let read path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
      let bytes = in_channel_length channel in
      require (bytes <= Limits.max_request_bytes) "Component-runtime document exceeds wire bound";
      let payload = really_input_string channel bytes in
      let value = Json.parse payload in
      require (Canonical.encode value ^ "\n" = payload) "Noncanonical component-runtime fixture";
      value, bytes)
let equal label actual expected =
  require (Canonical.encode actual = Canonical.encode expected) (label ^ ": complete record or numeric representation differs")
let reject label code ?message execute =
  match execute () with
  | _ -> failwith (label ^ ": expected rejection was accepted")
  | exception Diagnostic.Error diagnostic ->
      require (diagnostic.code = code) (label ^ ": expected " ^ code ^ ", got " ^ diagnostic.code ^ ": " ^ diagnostic.message);
      (match message with None -> () | Some expected ->
         require (diagnostic.message = expected) (label ^ ": original diagnostic message differs: " ^ diagnostic.message))
let runtime operation value =
  let history = array "history" value |> List.map D.Input_frame.of_json in
  let supplied = Json.boolean (field "until_supplied" value) in
  require (supplied || field "until" value = Json.Null) "Omitted horizon gained a value";
  let until = match field "until" value with Json.Null -> None | raw -> Some (Runtime_number.of_json raw) in
  let subject = field "subject" value in
  if operation = "run_component_model" then E.run ?until (A.of_json subject) history |> D.Trace.to_json
  else S.run ?until (Mechanism.of_json subject) history |> D.Trace.to_json
let normalize operation value = match operation with
  | "ComponentLock" -> R.Component_lock.of_json value |> R.Component_lock.to_json
  | "RegistryLock" -> R.Lock.of_json value |> R.Lock.to_json
  | "ComponentRegistry" -> R.of_json value |> R.to_json
  | "LifecycleInterval" -> C.Lifecycle.of_json value |> C.Lifecycle.to_json
  | "CompositionInstance" -> C.Instance.of_json value |> C.Instance.to_json
  | "Connection" -> C.Connection.of_json value |> C.Connection.to_json
  | "Provider" -> C.Provider.of_json value |> C.Provider.to_json
  | "DependencyBinding" -> C.Dependency_binding.of_json value |> C.Dependency_binding.to_json
  | "ResourcePool" -> C.Resource_pool.of_json value |> C.Resource_pool.to_json
  | "ResourceBinding" -> C.Resource_binding.of_json value |> C.Resource_binding.to_json
  | "CompositionRequest" -> C.of_json value |> C.to_json
  | "InputBinding" -> Observation_map.Input_binding.of_json value |> Observation_map.Input_binding.to_json
  | "OutputBinding" -> Observation_map.Output_binding.of_json value |> Observation_map.Output_binding.to_json
  | "ObservationMap" -> Observation_map.of_json value |> Observation_map.to_json
  | "ComponentAssembly" -> A.of_json value |> A.to_json
  | "registry_lock" ->
      let registry = R.of_json (field "registry" value) in
      let selections = Json.object_fields (field "selections" value)
                       |> List.map (fun (id, raw) -> id, Component.of_json raw) in
      R.lock registry selections |> R.Lock.to_json
  | "registry_resolve" ->
      let registry = R.of_json (field "registry" value) in
      let lock = R.Lock.of_json (field "lock" value) in
      Json.Object (R.resolve registry lock |> List.map (fun (id, record) -> id, Component.to_json record))
  | "reconstruct" -> A.of_json value |> E.reconstruct |> Mechanism.to_json
  | "run_component_model" | "run_locked_mechanism" -> runtime operation value
  | _ -> failwith ("Unknown component-runtime operation: " ^ operation)
let run path =
  require (not (Filename.is_relative path)) "Complete component-runtime corpus path must be absolute";
  let index, index_bytes = read path in
  require (text "schema_version" index = "biocompiler.component_runtime_conformance.v1") "Wrong component-runtime schema";
  require (text "claim_scope" index = "locked_component_identity_reconstruction_and_digital_execution_only_no_acceptance_or_biology") "Component scope changed";
  let inventory = Json.Object (List.remove_assoc "inventory_fingerprint" (Json.object_fields index)) in
  require (text "inventory_fingerprint" index = pin && Canonical.fingerprint inventory = pin) "Complete component-runtime inventory differs";
  require (text "original_capture_fingerprint" index = "de5a18829b1d624262dddc12488e52c7b1898d1191ce09df53de13aa6d3c6114") "Original observation identity changed";
  let documents = Hashtbl.create 5000 and kinds = Hashtbl.create 5000 and used = Hashtbl.create 5000 in
  let total = ref index_bytes and directory = Filename.remove_extension path in
  let descriptors = array "documents" index in
  require (List.length descriptors = 4934) "Complete component document census changed";
  List.iter (fun descriptor ->
      Json.exact_fields ["id"; "kind"; "bytes"] (Json.object_fields descriptor);
      let id = hash (text "id" descriptor) in
      require (not (Hashtbl.mem documents id)) "Duplicate component document";
      let raw, bytes = read (Filename.concat directory (id ^ ".json")) in
      require (bytes = integer (field "bytes" descriptor) && bytes <= 64 * 1024 * 1024 - !total) "Component byte census or total bound differs";
      total := !total + bytes;
      require (Canonical.fingerprint raw = id) "Retained component document identity differs";
      Hashtbl.add documents id raw; Hashtbl.add kinds id (text "kind" descriptor)) descriptors;
  require (!total = 64530645) "Complete component stored byte census changed";
  let expected_files = List.map (fun descriptor -> text "id" descriptor ^ ".json") descriptors |> List.sort String.compare in
  require ((Array.to_list (Sys.readdir directory) |> List.sort String.compare) = expected_files) "Missing or extra component document";
  let use kind id =
    let id = hash id in require (Hashtbl.find_opt kinds id = Some kind) "Missing or wrong-kind component document";
    Hashtbl.replace used id (); Hashtbl.find documents id in
  let input native =
    let format = text "input_format" native in
    let raw = use format (text "input" native) in
    match format with "record" -> raw | "json_text" -> Json.parse (Json.string raw) | _ -> failwith "Unknown component input representation" in
  let coverage = field "coverage" index in
  List.iter (fun (key, expected) -> require (integer (field key coverage) = expected) ("Incomplete component census: " ^ key))
    ["original_methods",163; "contexts",167; "api_calls",52476; "subprocess_invocations",0;
     "supplemental_successes",1; "supplemental_rejections",1; "unclassified_observations",0];
  let contexts = array "contexts" index and locations = array "source_locations" index in
  require (List.length contexts = 167 && List.length locations = 330) "Missing component context or source location";
  let calls = Hashtbl.create 52500 and context_ids = Hashtbl.create 170 in
  let operations = Hashtbl.create 20 and stages = Hashtbl.create 5 and witnessed = Hashtbl.create 13 and executed_kinds = Hashtbl.create 13 in
  let returned = ref 0 and raised = ref 0 in
  let failures = ref [] in
  let check_case label execute =
    try execute () with error ->
      let detail = match error with
        | Diagnostic.Error diagnostic -> diagnostic.code ^ ": " ^ diagnostic.message
        | Failure message -> message
        | _ -> Printexc.to_string error in
      let message = label ^ ": " ^ detail in
      failures := message :: !failures;
      Printf.eprintf "component corpus failure: %s\n%!" message in
  let count table key = Hashtbl.replace table key (1 + Option.value (Hashtbl.find_opt table key) ~default:0) in
  let witness value =
    let mechanism = Mechanism.of_json value in
    equal "reconstructed mechanism codec" (Mechanism.to_json mechanism) value;
    List.iter (fun node -> Hashtbl.replace witnessed (Mechanism.Node.kind node) ()) (Mechanism.nodes mechanism) in
  List.iter (fun context ->
      let context_id = text "id" context in
      require (not (Hashtbl.mem context_ids context_id)) "Duplicate component context";
      Hashtbl.add context_ids context_id ();
      require (text "assertion_status" context = "passed") "Original component assertion failed";
      let ledger = use "api_ledger" (text "ledger" context) |> array "observations" in
      require (List.length ledger = integer (field "api_calls" context)) "Incomplete component call ledger";
      List.iteri (fun number call ->
          let id = context_id ^ "/api/" ^ string_of_int number in
          require (not (Hashtbl.mem calls id)) "Duplicate component call";
          (match field "parent" call with Json.Null -> () | raw ->
             let parent = integer raw in require (parent >= 0 && parent < number) "Unobserved component call parent");
          let source = integer (field "source" call) in
          require (source >= 0 && source < List.length locations) "Missing original component callsite";
          ignore (use "raw_arguments" (text "input" call) |> Json.string);
          ignore (use "python_types" (text "python_types" call) |> Json.array);
          let native = field "native" call in
          let operation = text "operation" native and stage = text "native_stage" native in
          count operations operation; count stages stage;
          Hashtbl.add calls id call;
          let execute () = input native |> normalize operation in
          let succeeded = text "outcome" call = "returned" in
          require (succeeded || text "outcome" call = "raised") "Unknown original component outcome";
          if succeeded then incr returned else incr raised;
          check_case id (fun () -> if succeeded then begin
            require (field "expected_code" native = Json.Null && stage <> "wire") "Successful component case has a rejection code/stage";
            let expected = use "record" (text "result" call) in
            equal id (execute ()) expected;
            if operation = "reconstruct" then witness expected;
            if operation = "run_component_model" || operation = "run_locked_mechanism" then
              equal (id ^ "/trace_codec") (D.Trace.of_json expected |> D.Trace.to_json) expected;
            if operation = "run_locked_mechanism" then begin
              let linked_id = text "reconstruction_call" call in
              require (Hashtbl.mem calls linked_id) "Locked execution lost its actual reconstruction";
              let linked = Hashtbl.find calls linked_id in
              require (text "api" linked = "reconstruct_component_mechanism" && text "outcome" linked = "returned") "Invalid reconstruction provenance";
              let program = field "subject" (input native) in
              require (Canonical.fingerprint program = text "result" linked && text "program_fingerprint" expected = text "result" linked) "Execution graph differs from actual locked reconstruction";
              List.iter (fun node -> Hashtbl.replace executed_kinds (text "kind" node) ()) (array "nodes" program)
            end
          end else begin
            let code = text "expected_code" native in
            if stage = "wire" then reject id code (fun () -> input native)
            else begin
              ignore (input native);
              let message = if operation = "registry_resolve" || operation = "reconstruct" then Some (text "message" (field "error" call)) else None in
              reject id code ?message execute
            end
          end)) ledger) contexts;
  require (Hashtbl.length calls = 52476 && !returned = 51495 && !raised = 981) "Complete original component outcome census differs";
  List.iter (fun (key, value) -> require (Hashtbl.find_opt operations key = Some (integer value)) ("Component operation census changed: " ^ key))
    (Json.object_fields (field "native_operations" coverage));
  require (Hashtbl.length operations = 20) "Unexpected component operation family";
  List.iter (fun (key, expected) -> require (Hashtbl.find_opt stages key = Some expected) ("Component stage census changed: " ^ key))
    ["domain",50597; "registry",1650; "reconstruction",134; "runtime",93; "wire",2];
  check_case "original operation witnesses" (fun () ->
      require (Hashtbl.length witnessed = 12 && not (Hashtbl.mem witnessed "compare") && not (Hashtbl.mem witnessed "delay")) "Original component witness scope changed";
      require (Hashtbl.length executed_kinds = 12 && Hashtbl.fold (fun kind () valid -> valid && Hashtbl.mem witnessed kind) executed_kinds true)
        "Reconstruction-only observations cannot substitute for original full runtime witnesses");
  let supplements = array "supplemental" index in
  require (List.length supplements = 1) "Missing supplemental comparison witness";
  List.iter (fun case -> check_case (text "id" case) (fun () ->
      require (text "origin" case = "explicit_new_literal_not_original_assertion") "New literal misclassified as original assertion";
      let assembly = use "record" (text "assembly" case) |> A.of_json in
      let mechanism = use "record" (text "mechanism" case) in
      equal "comparison mechanism" (E.reconstruct assembly |> Mechanism.to_json) mechanism; witness mechanism;
      let request = use "record" (text "runtime_input" case) in
      let history = array "history" request |> List.map D.Input_frame.of_json in
      let until = Runtime_number.of_json (field "until" request) in
      let expected = use "record" (text "trace" case) in
      equal "comparison full trace" (E.run ~until assembly history |> D.Trace.to_json) expected)) supplements;
  let rejections = array "supplemental_rejections" index in
  require (List.length rejections = 1) "Missing explicit excluded-delay case";
  List.iter (fun case -> check_case (text "id" case) (fun () ->
      let raw = use "record" (text "input" case) in
      require (text "operation" raw = "delay") "Excluded operation changed";
      reject (text "id" case) (text "expected_code" case) (fun () -> Component.Synthetic_operator.of_json raw))) rejections;
  let actual_kinds = Hashtbl.fold (fun kind () result -> kind :: result) witnessed [] |> List.sort String.compare in
  let expected_kinds = ["input";"constant";"and";"or";"not";"compare";"select";"any_contact";"output";"held_for";"onset";"pulse";"memory"] |> List.sort String.compare in
  check_case "complete operation witnesses" (fun () -> require (actual_kinds = expected_kinds) "Missing successful complete component-operation witness");
  check_case "complete document reachability" (fun () -> require (Hashtbl.length used = Hashtbl.length documents) "Unreachable retained component document");
  require (!failures = []) (Printf.sprintf "%d component-runtime conformance failures; every original and supplementary case was attempted (diagnostics above)" (List.length !failures));
  Printf.printf "component runtime corpus: 163 original methods, 52476 complete observations (51495 returned, 981 rejected), 134 reconstructions, 93 runtime calls, 4934 documents, all 13 component operations and excluded delay passed\n"
let () =
  try
    require (Array.length Sys.argv = 2) "The complete component-runtime corpus is mandatory";
    run Sys.argv.(1)
  with Diagnostic.Error diagnostic -> failwith (diagnostic.code ^ ": " ^ diagnostic.message)
