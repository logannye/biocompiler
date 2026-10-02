open Bioc_wire
module M = Bioc_domain.Mechanism
module O = Bioc_domain.Measurement_contract.Observable
module S = Bioc_domain.Measurement_contract.Scalar
module T = Bioc_domain.Type_spec
module N = Bioc_domain.Runtime_number
let checks = ref 0
let check value message = incr checks; if not value then failwith message
let reject code run =
  incr checks;
  match run () with
  | _ -> failwith ("Accepted invalid mechanism; expected " ^ code)
  | exception Diagnostic.Error error -> if error.code <> code then
      failwith ("Expected " ^ code ^ ", got " ^ error.code ^ ": " ^ error.message)
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let get key value = Json.field key (Json.object_fields value)
let set key replacement value = obj ((key, replacement) :: List.remove_assoc key (Json.object_fields value))
let boolean = T.of_json (Json.parse {|{"kind":"condition","name":"Condition","dimensions":{},"arguments":[]}|})
let level = T.of_json (Json.parse {|{"kind":"scalar","name":"Level","dimensions":{},"arguments":[]}|})
let duration_type = Bioc_domain.Measurement_contract.duration_type
let observable ?(dtype = boolean) ?(scope = "cell") ?(role = "role") ?(compartment = "abstract") id =
  O.of_json (obj ["schema_version", str O.schema_version; "id", str ("meaning:" ^ id);
                 "dtype", T.to_json dtype; "scope", str scope; "role", str role; "compartment", str compartment])
let scalar ?(dtype = level) ?(unit = "1") value canonical =
  S.of_json (obj ["kind", str "scalar"; "type", T.to_json dtype; "value", value;
                 "unit", str unit; "canonical_value", canonical])
let seconds value = scalar ~dtype:duration_type ~unit:"s" (Json.int value) (Json.int value)
let node ?(dtype = boolean) ?(scope = "cell") ?(inputs = []) id operation =
  M.Node.make ~id ~operation ~output:(observable ~dtype ~scope id) ~inputs ()
let program nodes outputs = M.make ~name:"literal" ~nodes ~outputs ()
let ids nodes = List.map M.Node.id nodes

let complete_variants () =
  let input = node "input" M.Input and reset = node "reset" M.Input in
  let contact = node ~scope:"contact" "contact" M.Input in
  let reduce = node ~inputs:["contact"] "reduce" M.Any_contact in
  let constant = node ~dtype:level "constant" (M.Constant (M.Scalar (scalar (Json.int 2) (Json.int 2)))) in
  let other = node ~dtype:level "other" (M.Constant (M.Scalar (scalar (Json.int 3) (Json.int 3)))) in
  let and_node = node ~inputs:["input"; "reduce"] "and" M.And in
  let or_node = node ~inputs:["input"; "reduce"] "or" M.Or in
  let not_node = node ~inputs:["input"] "not" M.Not in
  let compare = node ~inputs:["constant"; "other"] "compare" (M.Compare M.Lt) in
  let select = node ~dtype:level ~inputs:["compare"; "constant"; "other"] "select" M.Select in
  let delay = node ~dtype:level ~inputs:["select"] "delay"
      (M.Delay {duration = seconds 2; initial = M.Scalar (scalar (Json.int 0) (Json.int 0))}) in
  let held = node ~inputs:["input"] "held" (M.Held_for (seconds 2)) in
  let onset = node ~inputs:["input"] "onset" M.Onset in
  let pulse = node ~inputs:["onset"] "pulse" (M.Pulse (seconds 2)) in
  let memory = node ~inputs:["onset"; "reset"] "memory" (M.Memory None) in
  let output = node ~dtype:level ~inputs:["delay"] "output" M.Output in
  let declared = [output; memory; pulse; onset; held; delay; select; compare; not_node; or_node;
                  and_node; other; constant; reduce; contact; reset; input] in
  let value = program declared ["output"] in
  check (List.sort_uniq String.compare (List.map M.Node.kind (M.nodes value)) = M.supported_kinds)
    "Full fourteen-operation ADT did not roundtrip";
  check (ids (M.nodes value) = ids declared) "Declaration order was replaced by execution order";
  check (Json.equal (M.to_json value) (M.to_json (M.of_json (M.to_json value)))) "Complete mechanism roundtrip changed";
  check (M.fingerprint value = Canonical.fingerprint (M.to_json value)
         && M.canonical_size value = String.length (Canonical.encode (M.to_json value))) "Cached exact identity changed";
  check (M.role value = "role" && M.name value = "literal") "Program identity getters changed";
  List.iter (fun operator ->
      let changed = M.Node.make ~id:"comparison" ~operation:(M.Compare operator)
          ~output:(observable "comparison") ~inputs:["constant"; "other"] () in
      ignore (program (changed :: declared) ["output"])) [M.Lt; M.Le; M.Gt; M.Ge; M.Eq; M.Ne];
  let memory_timed = node ~inputs:["onset"; "reset"] "timed_memory" (M.Memory (Some (seconds 1))) in
  ignore (program (memory_timed :: declared) ["output"]);
  check (M.get value "absent" = None) "Absent lookup invented a node"

let order_and_identity () =
  let a = node "a" M.Input and z = node "z" M.Input in
  let b = node ~inputs:["a"] "b" M.Not in
  let output = node ~inputs:["b"] "output" M.Output in
  let unlisted = node ~inputs:["z"] "uout" M.Output in
  let value = program [output; unlisted; b; z; a] ["output"] in
  check (ids (M.topological_nodes value) = ["a"; "z"; "b"; "uout"; "output"])
    "Topological scheduler must emit complete sorted ready layers";
  check (M.outputs value = ["output"] && List.length (M.nodes value) = 5)
    "A valid selected output subset or unlisted input/output declaration disappeared";
  let duplicate_edges = node ~inputs:["a"; "a"] "both" M.And in
  ignore (program [a; duplicate_edges; node ~inputs:["both"] "output" M.Output] ["output"]);
  let reordered = program [a; z; b; output; unlisted] ["output"] in
  check (M.fingerprint reordered <> M.fingerprint value
         && ids (M.topological_nodes reordered) = ids (M.topological_nodes value))
    "Declaration identity and execution order were conflated";
  let raw = M.Node.to_json (node ~dtype:level "c" (M.Constant (M.Scalar (scalar (Json.int 1) (Json.int 1)))))
      |> set "attributes" (obj ["value", Json.Float (-0.)]) in
  let normalized = M.Node.of_json raw |> M.Node.to_json in
  check (Canonical.encode (get "canonical_value" (get "value" (get "attributes" normalized))) = "-0.0")
    "Dimensionless scalar shorthand erased signed zero";
  let custom = T.of_json (Json.parse {|{"kind":"scalar","name":"CustomLevel"}|}) in
  let raw_custom = raw |> set "output" (O.to_json (observable ~dtype:custom "c")) in
  let normalized_custom = M.Node.of_json raw_custom |> M.Node.to_json in
  check (Json.equal (get "type" (get "value" (get "attributes" normalized_custom))) (T.to_json custom))
    "Compatible actual custom type was renamed";
  let quantity = scalar ~dtype:duration_type ~unit:"ms" (Json.int 2) (Json.Float 0.002) in
  check (N.equal (S.canonical quantity) (N.Real 0.002)) "Registered unit normalization changed";
  let requirements = M.Node.make ~id:"a" ~operation:M.Input ~output:(observable "a")
      ~requirement_ids:["second"; "first"] () in
  check (M.Node.requirement_ids requirements = ["second"; "first"]) "Requirement order was sorted";
  reject "invalid_mechanism" (fun () -> M.Node.make ~id:"a" ~operation:M.Input ~output:(observable "a")
      ~requirement_ids:["same"; "same"] ())

let invalid_graphs () =
  let input = node "input" M.Input in
  let output = node ~inputs:["input"] "output" M.Output in
  let base = program [input; output] ["output"] |> M.to_json in
  reject "unsupported_schema" (fun () -> M.of_json (set "schema_version" (str "biocompiler.mechanism.synthetic.v0.1") base));
  reject "unknown_field" (fun () -> M.of_json (set "extra" Json.Null base));
  reject "missing_field" (fun () -> M.of_json (obj (List.remove_assoc "name" (Json.object_fields base))));
  reject "invalid_mechanism" (fun () -> program [input; input; output] ["output"]);
  reject "invalid_mechanism" (fun () -> program [input; output] []);
  reject "invalid_mechanism" (fun () -> program [input; output] ["input"]);
  reject "invalid_mechanism" (fun () -> program [input; output] ["output"; "output"]);
  reject "invalid_mechanism" (fun () -> program [output] ["output"]);
  reject "invalid_mechanism" (fun () -> program [node ~inputs:["output"] "input" M.Not; output] ["output"]);
  reject "invalid_mechanism" (fun () -> program [node ~inputs:["output"] "input" M.Input; output] ["output"]);
  reject "invalid_mechanism" (fun () -> program [input; node "output" M.Output] ["output"]);
  reject "invalid_mechanism" (fun () -> program [input; node ~inputs:["input"] "logical" M.And; output] ["output"]);
  reject "invalid_mechanism" (fun () -> program [input; node ~inputs:["input"; "input"] "logical" M.Not; output] ["output"]);
  let scalar_input = node ~dtype:level "scalar" M.Input in
  reject "invalid_mechanism" (fun () -> program [scalar_input; node ~inputs:["scalar"] "output" M.Output] ["output"]);
  reject "invalid_mechanism" (fun () -> program [input; node ~inputs:["input"; "input"] "cmp" (M.Compare M.Eq); output] ["output"]);
  reject "invalid_mechanism" (fun () -> program [input; scalar_input;
      node ~inputs:["scalar"; "input"; "input"] "select" M.Select; output] ["output"]);
  let other_role = M.Node.make ~id:"output" ~operation:M.Output ~inputs:["input"]
      ~output:(observable ~role:"other" "output") () in
  reject "invalid_mechanism" (fun () -> program [input; other_role] ["output"]);
  let other_compartment = M.Node.make ~id:"output" ~operation:M.Output ~inputs:["input"]
      ~output:(observable ~compartment:"other" "output") () in
  reject "invalid_mechanism" (fun () -> program [input; other_compartment] ["output"]);
  reject "invalid_mechanism" (fun () -> program [node ~scope:"contact" "input" M.Input; output] ["output"]);
  reject "invalid_mechanism" (fun () -> program [input; node ~inputs:["input"] "output" M.Any_contact] ["output"]);
  let onset = node ~inputs:["input"] "onset" M.Onset in
  reject "invalid_mechanism" (fun () -> program [input; onset; node ~inputs:["onset"] "output" M.Output] ["output"]);
  reject "invalid_mechanism" (fun () -> program [input; node ~inputs:["input"] "pulse" (M.Pulse (seconds 2)); output] ["output"]);
  reject "invalid_mechanism" (fun () -> program [input; onset;
      node ~scope:"contact" ~inputs:["onset"; "input"] "memory" (M.Memory None); output] ["output"]);
  reject "invalid_mechanism" (fun () -> program [input; onset;
      node ~inputs:["onset"; "onset"] "memory" (M.Memory None); output] ["output"]);
  let node_json = M.Node.to_json input in
  reject "invalid_mechanism_node" (fun () -> M.Node.of_json (set "kind" (str "future") node_json));
  reject "unknown_field" (fun () -> M.Node.of_json (set "attributes" (obj ["hidden", Json.Null]) node_json));
  let duration_json = M.Node.to_json (node ~inputs:["input"] "held" (M.Held_for (seconds 1))) in
  reject "invalid_measurement_contract" (fun () -> M.Node.of_json (set "attributes" (obj ["duration", S.to_json (seconds 0)]) duration_json));
  reject "invalid_type" (fun () -> M.Node.of_json (set "attributes" (obj ["duration", Json.Null]) duration_json))

let resource_boundaries () =
  let rec cycle = Json.Object ["loop", cycle] in
  reject "mechanism_json_cycle" (fun () -> M.of_json cycle);
  let rec spine = Json.Null :: spine in
  reject "mechanism_limit" (fun () -> M.of_json (Json.Array spine));
  let rec fields = ("x", Json.Null) :: fields in
  reject "mechanism_limit" (fun () -> M.of_json (Json.Object fields));
  let input = node "input" M.Input in
  let rec nodes = input :: nodes in
  reject "mechanism_limit" (fun () -> M.make ~name:"cycle" ~nodes ~outputs:["input"] ());
  reject "duplicate_key" (fun () -> M.Node.of_json (obj (("id", str "duplicate") :: Json.object_fields (M.Node.to_json input))));
  reject "nonfinite_number" (fun () -> M.Node.of_json (set "attributes" (obj ["ignored", Json.Float nan]) (M.Node.to_json input)));
  reject "invalid_utf8" (fun () -> M.Node.of_json (set "id" (str "\255") (M.Node.to_json input)));
  let deep = List.fold_left (fun value _ -> arr [value]) Json.Null (List.init (Limits.max_depth + 1) Fun.id) in
  reject "mechanism_limit" (fun () -> M.of_json deep);
  let chain_length = 1500 in
  let chain = List.init chain_length (fun index ->
      if index = 0 then node "n0" M.Input else
        node ~inputs:["n" ^ string_of_int (index - 1)] ("n" ^ string_of_int index) M.Not) in
  let output = node ~inputs:["n" ^ string_of_int (chain_length - 1)] "output" M.Output in
  let value = program (output :: List.rev chain) ["output"] in
  check (List.length (M.topological_nodes value) = chain_length + 1) "Deep flat graph lost nodes or required native recursion"

let () =
  if Array.length Sys.argv <> 1 then failwith "test_mechanism accepts no arguments; corpus replay is a separate mandatory suite";
  complete_variants (); order_and_identity (); invalid_graphs (); resource_boundaries ();
  Printf.printf "Mechanism independent domain checks: %d passed\n" !checks
