open Bioc_wire
module Data = Bioc_domain.Execution_data
module Behavior = Bioc_domain.Behavior

let checks = ref 0
let check condition message = incr checks; if not condition then failwith message
let reject code run =
  incr checks;
  match run () with
  | _ -> failwith ("Accepted execution data; expected " ^ code)
  | exception Diagnostic.Error diagnostic ->
      if diagnostic.code <> code then failwith ("Expected " ^ code ^ ", received " ^ diagnostic.code)
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let integer value = Behavior.Integer (Z.of_int value)
let get key value = Json.field key (Json.object_fields value)
let set key replacement value = obj ((key, replacement) :: List.remove_assoc key (Json.object_fields value))
let hash = String.make 64 'a'
let source = { Behavior.file = "fixture.py"; line = Z.of_int 7; function_name = "literal" }
let source_json = obj ["file", str "fixture.py"; "line", Json.int 7; "function", str "literal"]

let sample_tests () =
  let empty = Data.Sample.make () in
  check (Json.equal (Data.Sample.to_json empty) (Json.parse {|{"value":null,"present":null,"high":null,"low":null}|}))
    "Missing sample channels must remain null, not false or zero";
  let value = Data.Sample.make ~value:(integer 3) ~present:false ~high:true ~low:false () in
  check (Data.Sample.value value = Some (integer 3) && Data.Sample.present value = Some false
    && Data.Sample.high value = Some true && Data.Sample.low value = Some false) "Independent sample channels changed";
  let negative_zero = Data.Sample.make ~value:(Behavior.Real (-0.)) () in
  check (Canonical.encode (Data.Sample.to_json negative_zero) = "{\"high\":null,\"low\":null,\"present\":null,\"value\":-0.0}") "Signed zero was erased";
  let float = Data.Sample.make ~value:(Behavior.Real 3.) () in
  check (Canonical.encode (Data.Sample.to_json float) <> Canonical.encode (Data.Sample.to_json (Data.Sample.make ~value:(integer 3) ())))
    "Float identity became integer identity";
  let json = Data.Sample.to_json value in
  check (Json.equal json (Data.Sample.to_json (Data.Sample.of_json json))) "Sample replay changed";
  reject "unknown_field" (fun () -> Data.Sample.of_json (set "inferred" (Json.Bool true) json));
  reject "missing_field" (fun () -> Data.Sample.of_json (obj (List.remove_assoc "low" (Json.object_fields json))));
  reject "invalid_type" (fun () -> Data.Sample.of_json (set "present" (Json.int 1) json));
  reject "evaluation_numeric_type" (fun () -> Data.Sample.of_json (set "value" (Json.Bool true) json));
  reject "evaluation_nonfinite" (fun () -> Data.Sample.of_json (set "value" (Json.Int (Z.pow (Z.of_int 10) 400)) json));
  reject "nonfinite_number" (fun () -> Data.Sample.of_json (set "value" (Json.Float nan) json));
  reject "duplicate_key" (fun () -> Data.Sample.of_json (obj (("value", Json.int 2) :: Json.object_fields json)))

let input_tests () =
  let sample = Data.Sample.make ~present:true () in
  let input = Data.Input_frame.make ~time:(Behavior.Real 0.) ~signals:["z", sample; "a", sample]
      ~contacts:["second", ["b", sample]; "first", ["a", sample]] () in
  check (Data.Input_frame.time input = Behavior.Real 0.) "Input time lost floating kind";
  check (List.map fst (Data.Input_frame.signals input) = ["z"; "a"]
    && List.map fst (Data.Input_frame.contacts input) = ["second"; "first"]) "Input association order was sorted";
  let json = Data.Input_frame.to_json input in
  check (Json.equal json (Data.Input_frame.to_json (Data.Input_frame.of_json json))) "Input replay changed";
  let short = obj ["time", Json.int 0; "signals", obj ["a", Json.int 7]; "contacts", obj []] in
  let normalized = Data.Input_frame.to_json (Data.Input_frame.of_json short) in
  check (Json.equal (get "value" (get "a" (get "signals" normalized))) (Json.int 7)) "Numeric sample shorthand failed";
  reject "execution_data_time" (fun () -> Data.Input_frame.make ~time:(integer (-1)) ());
  reject "duplicate_key" (fun () -> Data.Input_frame.make ~time:(integer 0) ~signals:["s", sample; "s", sample] ());
  reject "duplicate_key" (fun () -> Data.Input_frame.make ~time:(integer 0) ~contacts:["c", []; "c", []] ());
  reject "invalid_name" (fun () -> Data.Input_frame.make ~time:(integer 0) ~signals:["\194\160", sample] ());
  reject "invalid_type" (fun () -> Data.Input_frame.of_json (set "signals" (obj ["s", Json.Bool true]) short));
  let spaced = Data.Input_frame.make ~time:(integer 0) ~signals:[" s ", sample] () in
  check (List.map fst (Data.Input_frame.signals spaced) = [" s "]) "Identifier was normalized without authority"

let action ?specification_id ?specification_source ?started_at ?expires_at () =
  Data.Action.make ~action_id:"action" ~rule_id:"rule" ~kind:"action.secrete" ~contact_id:"contact"
    ~attributes:(obj ["ongoing", Json.Bool true; "product", str "declared"])
    ~values:(obj ["rate", Json.Float 2.]) ~requirement_ids:["req-b"; "req-a"] ~source ~rule_source:source
    ?specification_id ?specification_source ?started_at ?expires_at ()

let trace_tests () =
  let request = action ~started_at:(integer 0) ~expires_at:(Behavior.Real 2.) () in
  let expected = obj ["action_id", str "action"; "rule_id", str "rule"; "kind", str "action.secrete";
    "contact_id", str "contact"; "attributes", obj ["ongoing", Json.Bool true; "product", str "declared"];
    "values", obj ["rate", Json.Float 2.]; "requirement_ids", arr [str "req-b"; str "req-a"];
    "source", source_json; "rule_source", source_json; "started_at", Json.int 0; "expires_at", Json.Float 2.;
    "specification_id", str "action"; "specification_source", source_json] in
  check (Json.equal expected (Data.Action.to_json request)) "Full literal action trace differs";
  check (Data.Action.specification_id request = "action" && Data.Action.specification_source request = Some source)
    "Default specification did not preserve primitive authority";
  let explicit = action ~specification_id:"pulse" () in
  check (Data.Action.specification_id explicit = "pulse" && Data.Action.specification_source explicit = None)
    "Explicit specification incorrectly inherited primitive source";
  let fallback = Data.Action.of_json (expected |> set "specification_id" Json.Null |> set "specification_source" Json.Null) in
  check (Json.equal expected (Data.Action.to_json fallback)) "Null specification fallback changed Python shape";
  reject "invalid_type" (fun () -> Data.Action.of_json (set "specification_source" (Json.int 1) (set "specification_id" Json.Null expected)));
  reject "invalid_type" (fun () -> Data.Action.of_json (set "values" (arr []) expected));
  reject "invalid_source" (fun () -> Data.Action.of_json (set "source" (set "line" (Json.int 0) source_json) expected));
  reject "execution_data_time" (fun () -> action ~started_at:(integer (-1)) ());
  let event = Data.Event.make ~node_id:"onset" ~contact_id:"contact" ~requirement_ids:["req-b"; "req-a"] ~source () in
  check (Json.equal (Data.Event.to_json event) (obj ["node_id", str "onset"; "contact_id", str "contact";
      "requirement_ids", arr [str "req-b"; str "req-a"]; "source", source_json])) "Event lineage changed";
  let state = ["bool", Behavior.Boolean false; "int", Behavior.State_integer Z.zero;
      "float", Behavior.State_real (-0.); "text", Behavior.Text ""] in
  let frame = Data.Frame.make ~time:(integer 0) ~actions:[request; explicit] ~reactions:[explicit]
      ~events:[event] ~states:state ~memories:["latch", true] ~microsteps:3 in
  check (List.map Data.Action.specification_id (Data.Frame.actions frame) = ["action"; "pulse"])
    "Action order was not retained";
  check (Data.Frame.microsteps frame = 3 && List.length (Data.Frame.reactions frame) = 1
    && List.length (Data.Frame.events frame) = 1 && Data.Frame.memories frame = ["latch", true]) "Frame fields disappeared";
  let frame_json = Data.Frame.to_json frame in
  check (Canonical.encode (get "states" frame_json) = "{\"bool\":false,\"float\":-0.0,\"int\":0,\"text\":\"\"}") "Typed state identity changed";
  check (Json.equal frame_json (Data.Frame.to_json (Data.Frame.of_json frame_json))) "Frame replay changed";
  let large_state = Z.pow (Z.of_int 10) 400 in
  let large_frame = Data.Frame.make ~time:(integer 0) ~actions:[] ~reactions:[] ~events:[]
      ~states:["state", Behavior.State_integer large_state] ~memories:[] ~microsteps:1 in
  check (Data.Frame.states large_frame = ["state", Behavior.State_integer large_state])
    "Arbitrary-precision nominal state was subjected to numeric observation conversion";
  reject "execution_data_state" (fun () -> Data.Frame.of_json (set "states" (obj ["state", Json.Null]) frame_json));
  reject "invalid_type" (fun () -> Data.Frame.of_json (set "memories" (obj ["m", Json.int 1]) frame_json));
  reject "execution_data_microsteps" (fun () -> Data.Frame.of_json (set "microsteps" (Json.int 0) frame_json));
  reject "invalid_type" (fun () -> Data.Frame.of_json (set "microsteps" (Json.Float 1.) frame_json));
  reject "duplicate_key" (fun () -> Data.Frame.make ~time:(integer 0) ~actions:[] ~reactions:[] ~events:[]
      ~states:["s", Behavior.Text "a"; "s", Behavior.Text "b"] ~memories:[] ~microsteps:1);
  let result = Data.Result.make ~frames:[frame] ~role:"role" ~horizon:(Behavior.Real 2.)
      ~behavior_fingerprint:hash ~source_fingerprint:(String.make 64 'b') ~execution_profile:"abstract_single_cell.v0.1" in
  let result_json = Data.Result.to_json result in
  let expected_result = obj ["frames", arr [frame_json]; "role", str "role"; "horizon", Json.Float 2.;
      "behavior_fingerprint", str hash; "source_fingerprint", str (String.make 64 'b');
      "execution_profile", str "abstract_single_cell.v0.1"] in
  check (Json.equal result_json expected_result) "Literal full result serialization differs";
  check (Json.equal result_json (Data.Result.to_json (Data.Result.of_json result_json))) "Result replay changed";
  reject "execution_data_fingerprint" (fun () -> Data.Result.of_json (set "behavior_fingerprint" (str (String.make 64 'A')) result_json));
  reject "unknown_field" (fun () -> Data.Result.of_json (set "passed" (Json.Bool true) result_json));
  (* A record is not a verified execution token: the scheduler owns temporal
     completeness, graph identity, membership and history consistency. *)
  let structural = Data.Result.make ~frames:[] ~role:"unresolved-role" ~horizon:(integer 0)
      ~behavior_fingerprint:hash ~source_fingerprint:hash ~execution_profile:"declared-profile" in
  check (Data.Result.frames structural = []) "Data constructor pretended to perform reference execution"

let resource_tests () =
  let minimal = Data.Action.to_json (action ()) in
  let with_payload value = set "attributes" (obj ["payload", value]) minimal in
  reject "duplicate_key" (fun () -> Data.Action.of_json (with_payload (obj ["x", Json.int 1; "x", Json.int 2])));
  reject "nonfinite_number" (fun () -> Data.Action.of_json (with_payload (Json.Float infinity)));
  reject "invalid_utf8" (fun () -> Data.Action.of_json (with_payload (str "\255")));
  reject "execution_data_limit" (fun () -> Data.Action.of_json (with_payload (str (String.make (Limits.max_string_bytes + 1) 'x'))));
  let repeated = str (String.make Limits.max_string_bytes 'x') in
  reject "execution_data_limit" (fun () -> Data.Action.of_json (with_payload (arr (List.init 9 (fun _ -> repeated)))));
  let deep = List.fold_left (fun value _ -> arr [value]) Json.Null (List.init (Limits.max_depth + 1) Fun.id) in
  reject "execution_data_limit" (fun () -> Data.Action.of_json (with_payload deep));
  reject "execution_data_limit" (fun () -> Data.Action.of_json (with_payload (arr (List.init Limits.max_json_nodes (fun _ -> Json.Null)))));
  reject "execution_data_limit" (fun () -> Data.Action.of_json (with_payload (Json.Int (Z.shift_left Z.one (4 * Limits.max_number_chars + 1)))));
  reject "execution_data_limit" (fun () -> Data.Action.make ~action_id:"a" ~rule_id:"r" ~kind:"action.report"
    ~attributes:(obj ["large", arr (List.init 9 (fun _ -> repeated))]) ~values:(obj []) ~requirement_ids:[] ())

let read_json path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
      let length = in_channel_length channel in
      if length > Limits.max_request_bytes then failwith "Execution corpus exceeds wire input byte bound";
      Json.parse (really_input_string channel length))

let corpus path =
  let document = read_json path in
  check (get "schema_version" document = str "biocompiler.reference_execution_conformance.v1") "Wrong execution corpus schema";
  let coverage = get "coverage" document in
  let programs = Json.array (get "programs" document)
  and cases = Json.array (get "cases" document)
  and rejections = Json.array (get "rejections" document)
  and parser_rejections = Json.array (get "parser_rejections" document) in
  let census name minimum records =
    check (List.length records >= minimum) ("Truncated corpus inventory: " ^ name);
    check (get name coverage = Json.int (List.length records)) ("Incorrect corpus census: " ^ name)
  in
  census "program_count" 66 programs;
  census "positive_count" 86 cases;
  census "evaluation_rejection_count" 23 rejections;
  census "parser_rejection_count" 16 parser_rejections;
  check (get "profiles" coverage = arr [str "biocompiler.behavior.v0.1"; str "biocompiler.behavior.v0.2"])
    "Missing execution profiles";
  check (get "uncovered_kinds" coverage = arr []
    && List.length (Json.array (get "supported_kinds" coverage)) = 38
    && List.length (Json.array (get "extension_kinds" coverage)) = 4
    && List.length (Json.array (get "reachable_kinds" coverage)) = 42) "Incomplete declared operation census";
  let program_ids = Hashtbl.create 67 in
  List.iter (fun item -> let id = Json.string (get "id" item) in
      check (not (Hashtbl.mem program_ids id)) "Duplicate retained program";
      Hashtbl.add program_ids id ()) programs;
  let seen = Hashtbl.create 127 in
  let identity item =
    let id = Json.name (get "id" item) in
    check (not (Hashtbl.mem seen id)) ("Duplicate retained case: " ^ id);
    Hashtbl.add seen id (); id
  in
  let inputs = ref 0 in
  let history id item =
    check (Hashtbl.mem program_ids (Json.string (get "program_id" item))) ("Unknown program for " ^ id);
    List.iter (fun input ->
        let restored = Data.Input_frame.to_json (Data.Input_frame.of_json input) in
        check (Canonical.encode input = Canonical.encode restored) ("Input identity changed: " ^ id);
        incr inputs) (Json.array (get "history" item))
  in
  let case_b_count = ref 0 in
  List.iter (fun item ->
      let id = identity item in
      if String.starts_with ~prefix:"case_b/" id then incr case_b_count;
      history id item;
      let expected = get "expected_trace" item in
      let restored = Data.Result.to_json (Data.Result.of_json expected) in
      check (Canonical.encode expected = Canonical.encode restored) ("Full result identity changed: " ^ id);
      check (str (Canonical.fingerprint restored) = get "trace_fingerprint" item) ("Trace pin changed: " ^ id)) cases;
  check (!case_b_count = 24 && get "case_b_count" coverage = Json.int 24) "Missing case B variant/timeline pairs";
  List.iter (fun item -> let id = identity item in history id item) rejections;
  List.iter (fun item ->
      let id = identity item in
      let kind = Json.string (get "record_kind" item) in
      let expected_code = Json.string (get "expected_code" item)
      and expected_stage = Json.string (get "expected_stage" item) in
      let raw = Json.string (get "input_json" item) in
      let stage = ref "json" in
      incr checks;
      match (let value = Json.parse raw in stage := "decode";
          match kind with
          | "sample" -> ignore (Data.Sample.of_json value)
          | "input_frame" -> ignore (Data.Input_frame.of_json value)
          | _ -> failwith ("Unknown parser record kind: " ^ kind)) with
      | () -> failwith ("Accepted malformed retained input: " ^ id)
      | exception Diagnostic.Error diagnostic ->
          if diagnostic.code <> expected_code || !stage <> expected_stage then
            failwith ("Wrong retained input rejection for " ^ id ^ ": " ^ !stage ^ "/" ^ diagnostic.code ^
              "; expected " ^ expected_stage ^ "/" ^ expected_code)) parser_rejections;
  Printf.printf "Execution data corpus: %d input frames, %d complete traces, %d parser rejections round-tripped/checked.\n"
    !inputs (List.length cases) (List.length parser_rejections)

let () =
  match Array.length Sys.argv with
  | 1 ->
      sample_tests (); input_tests (); trace_tests (); resource_tests ();
      Printf.printf "Execution data: %d literal and malformed-record checks passed.\n" !checks
  | 2 -> corpus Sys.argv.(1)
  | _ -> failwith "Usage: test_execution_data.exe [reference-execution-v1.json]"
