open Bioc_wire
module O = Bioc_domain.Observation_map
let count = ref 0
let check condition message = incr count; if not condition then failwith message
let reject code run =
  incr count;
  match run () with
  | _ -> failwith ("Expected observation rejection " ^ code)
  | exception Diagnostic.Error diagnostic -> if diagnostic.code <> code then
      failwith ("Expected " ^ code ^ ", received " ^ diagnostic.code ^ ": " ^ diagnostic.message)
let str value = Json.String value
let set key replacement value = Json.Object ((key,replacement) :: List.remove_assoc key (Json.object_fields value))
let input field = O.Input_binding.make ~signal_id:"α\n" ~field ~mechanism_input_id:"sensor"
let output = O.Output_binding.make ~requirement_id:"r" ~mechanism_output_id:"out"
let literals () =
  let binding = input O.Present in
  let map = O.make ~inputs:[binding;binding] ~outputs:[output] in
  let expected = Json.parse {|{"inputs":[{"field":"present","mechanism_input_id":"sensor","signal_id":"α\n"},{"field":"present","mechanism_input_id":"sensor","signal_id":"α\n"}],"outputs":[{"mechanism_output_id":"out","requirement_id":"r"}],"schema_version":"biocompiler.observation_map.v0.1"}|} in
  check (Json.equal (O.to_json map) expected) "Independent complete observation literal differs";
  check (O.fingerprint map = "fb4f3a6ca1a65d81ea0823a6d5f6f41b96ed8c3fd2c8ffb008c7b52a24a12884" && O.canonical_size map = 265)
    "Observation Unicode/escaping identity differs";
  check (List.length (O.inputs map) = 2 && List.length (O.outputs map) = 1) "Structural duplicate input was removed";
  check (O.Input_binding.signal_id binding = "α\n" && O.Input_binding.mechanism_input_id binding = "sensor" &&
         O.Input_binding.field binding = O.Present && O.Input_binding.field_name binding = "present") "Input getters differ";
  check (O.Output_binding.requirement_id output = "r" && O.Output_binding.mechanism_output_id output = "out") "Output getters differ";
  let all = [O.Value;O.Present;O.High;O.Low] in
  let ordered = O.make ~inputs:(List.map input all) ~outputs:[output;output] in
  check (List.map O.Input_binding.field_name (O.inputs ordered) = ["value";"present";"high";"low"] &&
         List.length (O.outputs ordered) = 2) "Observation order/contextual duplicates changed";
  check (List.map O.field_name all = ["value";"present";"high";"low"]) "Field variant encoding differs";
  check (O.fingerprint ordered <> O.fingerprint (O.make ~inputs:(List.rev (O.inputs ordered)) ~outputs:(O.outputs ordered)))
    "Observation tuple order stopped participating in identity";
  check (Json.equal (O.to_json (O.of_json (O.to_json ordered))) (O.to_json ordered)) "Observation roundtrip differs";
  let empty = O.make ~inputs:[] ~outputs:[] in
  check (O.inputs empty = [] && O.outputs empty = []) "Empty structural observation map was rejected";
  let raw = O.Input_binding.to_json binding in
  reject "invalid_observation_map" (fun () -> O.Input_binding.of_json (set "field" (str "future") raw));
  reject "invalid_type" (fun () -> O.Input_binding.of_json (set "field" (Json.Bool true) raw));
  reject "invalid_name" (fun () -> O.Input_binding.make ~signal_id:" " ~field:O.Value ~mechanism_input_id:"input");
  reject "invalid_name" (fun () -> O.Output_binding.make ~requirement_id:"r" ~mechanism_output_id:"");
  reject "missing_field" (fun () -> O.Input_binding.of_json (Json.Object (List.remove_assoc "field" (Json.object_fields raw))));
  reject "unknown_field" (fun () -> O.Output_binding.of_json (set "accepted" (Json.Bool true) (O.Output_binding.to_json output)));
  reject "unsupported_schema" (fun () -> O.of_json (set "schema_version" (str "old") (O.to_json map)));
  reject "invalid_type" (fun () -> O.of_json (set "inputs" Json.Null (O.to_json map)))
let boundaries () =
  let raw = O.Input_binding.to_json (input O.Value) in
  reject "duplicate_key" (fun () -> O.Input_binding.of_json (Json.Object (("field",str "low") :: Json.object_fields raw)));
  reject "invalid_utf8" (fun () -> O.Input_binding.of_json (set "signal_id" (str "\255") raw));
  reject "nonfinite_number" (fun () -> O.Input_binding.of_json (set "field" (Json.Float infinity) raw));
  let rec cycle = Json.Array [cycle] in
  reject "observation_map_cycle" (fun () -> O.of_json cycle);
  let rec spine = Json.Null :: spine in
  reject "observation_map_limit" (fun () -> O.of_json (Json.Array spine));
  let rec fields = ("same",Json.Null) :: fields in
  reject "observation_map_limit" (fun () -> O.of_json (Json.Object fields));
  let binding = input O.Value in
  let rec inputs = binding :: inputs in
  reject "observation_map_limit" (fun () -> O.make ~inputs ~outputs:[]);
  let rec outputs = output :: outputs in
  reject "observation_map_limit" (fun () -> O.make ~inputs:[] ~outputs);
  let long = O.Input_binding.make ~signal_id:(String.make Limits.max_string_bytes 'x') ~field:O.Value ~mechanism_input_id:"input" in
  ignore (O.make ~inputs:[long] ~outputs:[]);
  reject "observation_map_limit" (fun () -> O.Input_binding.make ~signal_id:(String.make (Limits.max_string_bytes + 1) 'x') ~field:O.Value ~mechanism_input_id:"input");
  reject "observation_map_limit" (fun () -> O.make ~inputs:[long;long;long;long] ~outputs:[]);
  let deep = List.fold_left (fun value _ -> Json.Array [value]) Json.Null (List.init (Limits.max_depth + 1) Fun.id) in
  reject "observation_map_limit" (fun () -> O.of_json deep)
let () = literals (); boundaries (); Printf.printf "observation map: %d literal checks passed\n" !count
