open Bioc_wire
open Bioc_domain
module S = Bioc_candidate_runtime.Synthetic
module D = Model_execution_data
let require value message = if not value then failwith message
let field key value = Json.field key (Json.object_fields value)
let text key value = Json.string (field key value)
let integer value = Json.integer value |> Z.to_int
let array key value = Json.array (field key value)
let pin = "e29da7150c3a80621967d332f8bb03065b07ebcb30b58b30fc8029e296393599"
let hash value =
  require (String.length value = 64 && String.for_all (function '0'..'9' | 'a'..'f' -> true | _ -> false) value)
    "Unsafe candidate-runtime fixture identity"; value
let read path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let bytes = in_channel_length channel in
    require (bytes <= Limits.max_request_bytes) "Candidate-runtime fixture exceeds individual wire bound";
    let payload = really_input_string channel bytes in
    let value = Json.parse payload in
    require (Canonical.encode value ^ "\n" = payload) "Noncanonical retained fixture bytes";
    value, bytes)
let equal label actual expected =
  require (Canonical.encode actual = Canonical.encode expected) (label ^ ": complete record or numeric representation differs")
let reject label code ?message operation =
  match operation () with
  | _ -> failwith (label ^ ": expected explicit rejection was accepted")
  | exception Diagnostic.Error diagnostic ->
      require (diagnostic.code = code) (label ^ ": expected " ^ code ^ ", got " ^ diagnostic.code ^ ": " ^ diagnostic.message);
      (match message with None -> () | Some expected -> require (diagnostic.message = expected) (label ^ ": legacy diagnostic text differs: " ^ diagnostic.message))
let normalize operation value = match operation with
  | "node" -> Mechanism.Node.of_json value |> Mechanism.Node.to_json
  | "program" -> Mechanism.of_json value |> Mechanism.to_json
  | "input_frame" -> D.Input_frame.of_json value |> D.Input_frame.to_json
  | "frame" -> D.Frame.of_json value |> D.Frame.to_json
  | "trace" -> D.Trace.of_json value |> D.Trace.to_json
  | _ -> failwith "Unknown domain observation operation"
let run path =
  require (not (Filename.is_relative path)) "Candidate-runtime corpus path must be absolute";
  let index, index_bytes = read path in
  require (text "schema_version" index = "biocompiler.candidate_runtime_conformance.v1") "Wrong candidate-runtime corpus schema";
  require (text "claim_scope" index = "independent_synthetic_candidate_execution_only_no_biological_evidence") "Candidate scope drift";
  let inventory = Json.Object (List.remove_assoc "inventory_fingerprint" (Json.object_fields index)) in
  require (text "inventory_fingerprint" index = pin && Canonical.fingerprint inventory = pin) "Complete candidate-runtime inventory differs";
  let documents = Hashtbl.create 4096 and kinds = Hashtbl.create 4096 and used = Hashtbl.create 4096 in
  let total = ref index_bytes and directory = Filename.remove_extension path in
  let descriptors = array "documents" index in
  require (List.length descriptors = 3955) "Candidate document census changed";
  List.iter (fun descriptor ->
      Json.exact_fields ["id"; "kind"; "bytes"] (Json.object_fields descriptor);
      let id = hash (text "id" descriptor) in
      require (not (Hashtbl.mem documents id)) "Duplicate candidate document";
      let raw, bytes = read (Filename.concat directory (id ^ ".json")) in
      require (bytes = integer (field "bytes" descriptor) && bytes <= 32 * 1024 * 1024 - !total) "Candidate stored size differs or exceeds complete bound";
      total := !total + bytes;
      require (Canonical.fingerprint raw = id) "Candidate document identity differs";
      Hashtbl.add documents id raw; Hashtbl.add kinds id (text "kind" descriptor)) descriptors;
  require (!total = 16098793) "Candidate complete stored byte census changed";
  let expected_files = List.map (fun descriptor -> text "id" descriptor ^ ".json") descriptors |> List.sort String.compare in
  require ((Array.to_list (Sys.readdir directory) |> List.sort String.compare) = expected_files) "Missing or extra candidate fixture document";
  let use kind id =
    let id = hash id in
    require (Hashtbl.find_opt kinds id = Some kind) "Missing or wrong-kind candidate fixture document";
    Hashtbl.replace used id (); Hashtbl.find documents id in
  let coverage = field "coverage" index in
  List.iter (fun (key, expected) -> require (integer (field key coverage) = expected) ("Wrong complete census: " ^ key))
    ["original_methods",155; "contexts",158; "api_calls",12487; "run_calls",549; "domain_observations",11938;
     "original_primary_methods",50; "original_primary_api_calls",727; "original_primary_runs",55; "unclassified_observations",0];
  let runtime_cases = Hashtbl.create 550 and runtime_seen = Hashtbl.create 550 in
  let runs = array "runs" index in
  require (List.length runs = 549) "Missing original candidate-runtime call";
  List.iter (fun case -> let id = text "api_call" case in
      require (not (Hashtbl.mem runtime_cases id)) "Duplicate runtime API linkage";
      Hashtbl.add runtime_cases id case) runs;
  let calls = Hashtbl.create 12500 and context_ids = Hashtbl.create 160 in
  let domain_passed = ref 0 and domain_failed = ref 0 and wire_failed = ref 0 in
  let operations = Hashtbl.create 8 in
  let contexts = array "contexts" index in
  require (List.length contexts = 158) "Missing original candidate context";
  List.iter (fun context ->
      let context_id = text "id" context in
      require (not (Hashtbl.mem context_ids context_id)) "Duplicate candidate context";
      Hashtbl.add context_ids context_id ();
      require (text "assertion_status" context = "passed") "Original Python assertion did not pass";
      let ledger = use "api_ledger" (text "ledger" context) |> Json.array in
      require (List.length ledger = integer (field "api_calls" context)) "Incomplete candidate API ledger";
      List.iteri (fun number call ->
          let id = text "id" call in
          require (id = context_id ^ "/api/" ^ string_of_int number && text "source_test" call = context_id)
            "Missing/reordered/misattributed API observation";
          require (not (Hashtbl.mem calls id)) "Duplicate candidate API observation";
          (match field "parent_call" call with
           | Json.Null -> ()
           | value -> require (Hashtbl.mem calls (Json.string value)) "Unobserved API parent");
          Hashtbl.add calls id call;
          ignore (use "raw_arguments" (text "input" call) |> Json.string);
          let native = field "native" call in
          let operation = text "operation" native in
          Hashtbl.replace operations operation (1 + Option.value (Hashtbl.find_opt operations operation) ~default:0);
          let returned = text "outcome" call = "returned" in
          let expected = if returned then Some (use "record" (text "result" call)) else None in
          if operation = "run_model" then begin
            require (text "runtime_case" native = id && Hashtbl.mem runtime_cases id) "Runtime API observation lacks complete case";
            let case = Hashtbl.find runtime_cases id in
            require (text "source_test" case = context_id && text "outcome" case = text "outcome" call) "Runtime observation linkage changed";
            (match expected with
             | Some _ -> require (text "expected" case = text "result" call) "Runtime/API full trace identities differ"
             | None -> equal id (field "error" call) (field "error" case));
            Hashtbl.add runtime_seen id ()
          end else begin
            let input = use "json_text" (text "input" native) |> Json.string in
            let execute () = Json.parse input |> normalize operation in
            match expected with
            | Some expected ->
                require (field "expected_code" native = Json.Null && text "native_stage" native = "domain") "Successful import stage/code drift";
                equal id (execute ()) expected; incr domain_passed
            | None ->
                let code = text "expected_code" native in
                if text "native_stage" native = "wire" then begin
                  reject id code (fun () -> Json.parse input); incr wire_failed
                end else begin
                  ignore (Json.parse input);
                  reject id code execute
                end;
                incr domain_failed
          end) ledger) contexts;
  require (Hashtbl.length calls = 12487 && Hashtbl.length runtime_seen = 549 && !domain_passed = 11809 && !domain_failed = 129 && !wire_failed = 5)
    "Candidate observed outcome census differs";
  List.iter (fun (kind,count) -> require (Hashtbl.find_opt operations kind = Some count) ("Missing complete operation family: " ^ kind))
    ["node",7855; "program",815; "input_frame",2705; "frame",12; "trace",551; "run_model",549];
  let passed = ref 0 and failed = ref 0 and witnessed = Hashtbl.create 14 and program_ids = Hashtbl.create 74 in
  List.iter (fun case ->
      let id = text "id" case in
      let program_id = text "program" case in
      let raw = use "record" program_id in
      let program = Mechanism.of_json raw in
      equal (id ^ "/program") (Mechanism.to_json program) raw;
      require (Mechanism.fingerprint program = program_id) "Native mechanism changed complete authority identity";
      Hashtbl.replace program_ids program_id ();
      let input = use "runtime_input" (text "input" case) in
      Json.exact_fields ["history"; "until"; "until_supplied"] (Json.object_fields input);
      let history = array "history" input |> List.map D.Input_frame.of_json in
      let supplied = Json.boolean (field "until_supplied" input) in
      require (supplied || field "until" input = Json.Null) "Omitted horizon unexpectedly has a value";
      let until = match field "until" input with Json.Null -> None | raw -> Some (Runtime_number.of_json raw) in
      let execute () = S.run ?until program history |> D.Trace.to_json in
      match field "expected" case with
      | Json.Null ->
          reject id (text "expected_code" case) ~message:(text "message" (field "error" case)) execute;
          incr failed
      | value ->
          let expected = use "record" (Json.string value) in
          equal (id ^ "/trace_import") (D.Trace.of_json expected |> D.Trace.to_json) expected;
          equal id (execute ()) expected;
          List.iter (fun node -> Hashtbl.replace witnessed (Mechanism.Node.kind node) ()) (Mechanism.nodes program);
          incr passed) runs;
  require (!passed = 537 && !failed = 12 && Hashtbl.length program_ids = 73) "Complete runtime outcome/program census differs";
  let witnessed = Hashtbl.fold (fun kind () values -> kind :: values) witnessed [] |> List.sort String.compare in
  require (witnessed = List.sort String.compare Mechanism.supported_kinds && List.length witnessed = 14) "Missing successful full-operation witness";
  require (Hashtbl.length used = Hashtbl.length documents) "Unreachable retained candidate observation document";
  Printf.printf "candidate runtime corpus: 155 original methods, 2 subprocesses, 549 complete runs (537 returned, 12 rejected), 11938 domain observations (11809 returned, 129 rejected), all 14 operations, 3955 exact documents passed\n"
let () =
  try
    require (Array.length Sys.argv = 2) "The complete candidate-runtime corpus is mandatory";
    run Sys.argv.(1)
  with Diagnostic.Error diagnostic -> failwith (diagnostic.code ^ ": " ^ diagnostic.message)
