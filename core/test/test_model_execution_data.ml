open Bioc_wire
module D = Bioc_domain.Model_execution_data
module N = Bioc_domain.Runtime_number
let checks = ref 0
let check value message = incr checks; if not value then failwith message
let reject code run =
  incr checks;
  match run () with
  | _ -> failwith ("Accepted invalid candidate data; expected " ^ code)
  | exception Diagnostic.Error error -> if error.code <> code then
      failwith ("Expected " ^ code ^ ", got " ^ error.code ^ ": " ^ error.message)
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let integer value = N.Integer (Z.of_int value)
let get key value = Json.field key (Json.object_fields value)
let set key replacement value = obj ((key, replacement) :: List.remove_assoc key (Json.object_fields value))
let hash = String.make 64 'a'
let frame time values = D.Frame.make ~time:(integer time) ~values ()

let snapshot_literals () =
  let empty = D.Input_frame.make ~time:N.zero () in
  check (Json.equal (D.Input_frame.to_json empty)
      (Json.parse {|{"time":0,"values":{},"contacts":{}}|})) "Empty full snapshot shape changed";
  let value = D.Input_frame.make ~time:(N.Real (-0.))
      ~values:["bool", D.Boolean false; "int", D.Number (integer 0); "float", D.Number (N.Real 0.);
               "large", D.Number (N.Integer (Z.of_string "9007199254740993"))]
      ~contacts:["z", ["input", D.Boolean true]; "a", ["input", D.Boolean false]] () in
  let json = D.Input_frame.to_json value in
  check (Canonical.encode (get "time" json) = "-0.0") "Signed zero time changed";
  check (List.map fst (D.Input_frame.values value) = ["bool"; "int"; "float"; "large"]
         && List.map fst (D.Input_frame.contacts value) = ["z"; "a"]) "Snapshot insertion order was sorted";
  check (Json.equal json (Json.parse {|{"time":-0.0,"values":{"bool":false,"int":0,"float":0.0,"large":9007199254740993},"contacts":{"z":{"input":true},"a":{"input":false}}}|}))
    "Full independent snapshot literal changed";
  check (D.Input_frame.canonical_size value = String.length (Canonical.encode json)) "Input size cache differs from exact UTF-8 bytes";
  check (Json.equal json (D.Input_frame.to_json (D.Input_frame.of_json json))) "Input serialization replay changed";
  let public = D.Frame.of_json json in
  check (D.Frame.canonical_size public = D.Input_frame.canonical_size value
         && D.Frame.values public = D.Input_frame.values value
         && D.Frame.contacts public = D.Input_frame.contacts value) "Frame and input snapshot shapes diverged";
  check (D.value_of_json (Json.Bool false) = D.Boolean false
         && D.value_of_json (Json.int 0) = D.Number N.zero
         && D.value_of_json (Json.Float 0.) = D.Number (N.Real 0.)) "Boolean/integer/float distinctions disappeared";
  let escaped = D.Input_frame.make ~time:N.zero ~values:["é\n\"", D.Boolean true] () in
  check (D.Input_frame.canonical_size escaped = String.length (Canonical.encode (D.Input_frame.to_json escaped)))
    "Escaped and multibyte name sizes were counted as character lengths"

let input_rejections () =
  let base = D.Input_frame.to_json (D.Input_frame.make ~time:N.zero ()) in
  reject "model_time" (fun () -> D.Input_frame.make ~time:(integer (-1)) ());
  reject "model_numeric_type" (fun () -> D.Input_frame.of_json (set "time" (Json.Bool false) base));
  reject "model_numeric_type" (fun () -> D.Input_frame.of_json (set "values" (obj ["x", Json.Null]) base));
  reject "model_nonfinite" (fun () -> D.Input_frame.make ~time:(N.Real infinity) ());
  reject "model_nonfinite" (fun () -> D.Input_frame.make ~time:N.zero ~values:["x", D.Number (N.Real nan)] ());
  reject "model_nonfinite" (fun () -> D.Input_frame.of_json (set "values" (obj ["x", Json.Int (Z.pow (Z.of_int 10) 400)]) base));
  reject "nonfinite_number" (fun () -> D.Input_frame.of_json (set "values" (obj ["x", Json.Float nan]) base));
  reject "unknown_field" (fun () -> D.Input_frame.of_json (set "signals" (obj []) base));
  reject "missing_field" (fun () -> D.Input_frame.of_json (obj (List.remove_assoc "contacts" (Json.object_fields base))));
  reject "invalid_type" (fun () -> D.Input_frame.of_json (set "contacts" (arr []) base));
  reject "invalid_type" (fun () -> D.Input_frame.of_json (set "contacts" (obj ["c", arr []]) base));
  reject "invalid_name" (fun () -> D.Input_frame.make ~time:N.zero ~values:["\194\160", D.Boolean true] ());
  reject "invalid_name" (fun () -> D.Input_frame.make ~time:N.zero ~contacts:["", []] ());
  reject "duplicate_key" (fun () -> D.Input_frame.make ~time:N.zero ~values:["x", D.Boolean true; "x", D.Boolean false] ());
  reject "duplicate_key" (fun () -> D.Input_frame.make ~time:N.zero ~contacts:["c", []; "c", []] ());
  reject "duplicate_key" (fun () -> D.Input_frame.of_json (obj (("time", Json.int 1) :: Json.object_fields base)));
  reject "invalid_utf8" (fun () -> D.Input_frame.make ~time:N.zero ~values:["\255", D.Boolean true] ())

let trace_literals () =
  let frames = [frame 0 ["output", D.Boolean false]; frame 2 ["output", D.Boolean true]] in
  let value = D.Trace.make ~frames ~horizon:(integer 2) ~program_fingerprint:hash () in
  let expected = Json.parse {|{"schema_version":"biocompiler.synthetic.trace.v0.1","frames":[{"time":0,"values":{"output":false},"contacts":{}},{"time":2,"values":{"output":true},"contacts":{}}],"horizon":2,"program_fingerprint":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","model_version":"biocompiler.synthetic.runner.v0.2"}|} in
  check (Json.equal (D.Trace.to_json value) expected) "Complete literal historical trace changed";
  check (D.Trace.fingerprint value = Canonical.fingerprint expected) "Trace identity does not bind complete literal record";
  check (List.map D.Frame.time (D.Trace.frames value) = [integer 0; integer 2]
         && D.Trace.horizon value = integer 2 && D.Trace.program_fingerprint value = hash) "Trace getter lost authority";
  check (Json.equal (D.Trace.to_json (D.Trace.of_json expected)) expected) "Trace full roundtrip changed";
  let floating = D.Trace.make ~frames:[D.Frame.make ~time:(N.Real 0.) ()] ~horizon:N.zero ~program_fingerprint:hash () in
  check (Canonical.encode (get "time" (List.hd (Json.array (get "frames" (D.Trace.to_json floating))))) = "0.0")
    "Numeric endpoint equality normalized away float identity";
  let larger = D.Trace.make ~frames:[frame 0 []; D.Frame.make ~time:(N.Integer (Z.of_string "9007199254740993")) ()]
      ~horizon:(N.Integer (Z.of_string "9007199254740993")) ~program_fingerprint:hash () in
  check (D.Trace.horizon larger = N.Integer (Z.of_string "9007199254740993")) "Trace time rounded an exact finite integer";
  reject "invalid_model_trace" (fun () -> D.Trace.make ~frames:[] ~horizon:N.zero ~program_fingerprint:hash ());
  reject "invalid_model_trace" (fun () -> D.Trace.make ~frames:[frame 1 []] ~horizon:(integer 1) ~program_fingerprint:hash ());
  reject "invalid_model_trace" (fun () -> D.Trace.make ~frames ~horizon:(integer 3) ~program_fingerprint:hash ());
  reject "invalid_model_trace" (fun () -> D.Trace.make ~frames:[frame 0 []; D.Frame.make ~time:(N.Real 0.) ()]
      ~horizon:N.zero ~program_fingerprint:hash ());
  reject "invalid_model_trace" (fun () -> D.Trace.make ~frames:[frame 0 []; frame 2 []; frame 1 []]
      ~horizon:(integer 1) ~program_fingerprint:hash ());
  reject "invalid_model_trace" (fun () -> D.Trace.make ~frames ~horizon:(integer 2) ~program_fingerprint:(String.make 64 'A') ());
  reject "invalid_model_trace" (fun () -> D.Trace.make ~frames ~horizon:(integer 2) ~program_fingerprint:hash
      ~model_version:"biocompiler.synthetic.runner.v0.1" ());
  reject "unsupported_schema" (fun () -> D.Trace.of_json (set "schema_version" (str "old") expected));
  reject "model_time" (fun () -> D.Trace.of_json (set "horizon" (Json.int (-1)) expected));
  reject "model_numeric_type" (fun () -> D.Trace.of_json (set "horizon" (Json.Bool true) expected));
  reject "unknown_field" (fun () -> D.Trace.of_json (set "accepted" (Json.Bool true) expected))

let resource_literals () =
  let rec cycle = Json.Object ["loop", cycle] in
  reject "model_data_cycle" (fun () -> D.Input_frame.of_json cycle);
  let rec spine = Json.Null :: spine in
  reject "model_data_limit" (fun () -> D.Input_frame.of_json (arr spine));
  let rec fields = ("x", Json.Null) :: fields in
  reject "model_data_limit" (fun () -> D.Input_frame.of_json (obj fields));
  let rec values = ("x", D.Boolean true) :: values in
  reject "model_data_limit" (fun () -> D.Input_frame.make ~time:N.zero ~values ());
  let rec contacts = ("x", []) :: contacts in
  reject "model_data_limit" (fun () -> D.Input_frame.make ~time:N.zero ~contacts ());
  let frame = frame 0 [] in
  let rec frames = frame :: frames in
  reject "model_data_limit" (fun () -> D.Trace.make ~frames ~horizon:N.zero ~program_fingerprint:hash ());
  let deep = List.fold_left (fun value _ -> arr [value]) Json.Null (List.init (Limits.max_depth + 1) Fun.id) in
  reject "model_data_limit" (fun () -> D.Input_frame.of_json deep);
  reject "model_data_limit" (fun () -> D.Input_frame.of_json (Json.Int (Z.pow (Z.of_int 10) Limits.max_number_chars)));
  let large_name = String.make Limits.max_string_bytes 'x' in
  let one = D.Frame.make ~time:N.zero ~values:[large_name, D.Boolean true] () in
  check (D.Frame.canonical_size one > Limits.max_string_bytes) "Exact permitted string boundary rejected";
  reject "model_data_limit" (fun () -> D.Frame.make ~time:N.zero ~values:[large_name ^ "x", D.Boolean true] ());
  (* Cached child JSON may be shared. Every occurrence must still consume the
     whole publication budget before trace validation or expanded serialization. *)
  reject "model_data_limit" (fun () -> D.Trace.make ~frames:(List.init 9 (fun _ -> one))
      ~horizon:N.zero ~program_fingerprint:hash ());
  let shared_values = [large_name, D.Boolean true] in
  reject "model_data_limit" (fun () -> D.Input_frame.make ~time:N.zero
      ~contacts:(List.init 5 (fun index -> string_of_int index, shared_values)) ())

let () =
  if Array.length Sys.argv <> 1 then failwith "test_model_execution_data accepts no arguments; corpus replay is a separate mandatory suite";
  snapshot_literals (); input_rejections (); trace_literals (); resource_literals ();
  Printf.printf "Candidate execution data independent checks: %d passed\n" !checks
