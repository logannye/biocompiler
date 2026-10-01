open Bioc_wire

let require condition message = if not condition then failwith message
let str value = Json.String value
let obj fields = Json.Object fields
let arr values = Json.Array values
let node ?(kind = "unknown-extension") ?(inputs = []) ?(attributes = []) ?(dtype = Json.Null) ?(role = Json.Null) id =
  obj ["id", str id; "kind", str kind; "inputs", arr (List.map str inputs);
       "attributes", obj attributes; "data_type", dtype; "role", role]
let program ?(roots = []) nodes =
  obj ["schema_version", str "biocompiler.intent.v0.1"; "name", str "checked";
       "nodes", arr nodes; "roots", arr (List.map str roots)]
let fields = Json.object_fields
let set key value source = obj ((key, value) :: List.remove_assoc key (fields source))
let scalar_type = Json.parse {|{"kind":"scalar","name":"Duration","dimensions":{"time":1},"arguments":[]}|}
let scalar ?(unit_name = "s") value canonical =
  obj ["kind", str "scalar"; "value", value; "canonical_value", canonical;
       "unit", str unit_name; "type", scalar_type]
let literal binding = node ~kind:"literal" ~dtype:scalar_type ~attributes:["value", binding] "number"
let accepted value = ignore (Bioc_domain.Intent.of_json value)
let rejected value code =
  match Bioc_domain.Intent.of_json value with
  | _ -> failwith ("Accepted invalid intent; expected " ^ code)
  | exception Diagnostic.Error diagnostic ->
      require (diagnostic.code = code) ("Wrong intent rejection: " ^ diagnostic.code ^ ", expected " ^ code)

let () =
  let role = node ~kind:"role" "cell" in
  let signal = node ~role:(str "cell") "signal" in
  let source = program ~roots:["signal"] [role; signal] in
  accepted source;
  let without_source = Bioc_domain.Intent.of_json source in
  let location = obj ["file", str "examples/intent.py"; "line", Json.int 12; "function", str "main"] in
  let with_source = Bioc_domain.Intent.of_json (program ~roots:["signal"] [set "source" location role; set "source" location signal]) in
  require (Bioc_domain.Intent.fingerprint without_source = Bioc_domain.Intent.fingerprint with_source) "Source location changed structural identity";
  let restored = Bioc_domain.Intent.of_json (Bioc_domain.Intent.to_json without_source) in
  require (Bioc_domain.Intent.fingerprint restored = Bioc_domain.Intent.fingerprint without_source) "Intent roundtrip changed identity";
  accepted (program []);
  accepted (program [literal (scalar ~unit_name:"ms" (Json.int 1000) (Json.Float 1.))]);
  accepted (program [literal (scalar (Json.int 9007199254740993) (Json.parse "9007199254740993"))]);
  rejected (program [role; role]) "duplicate_node";
  rejected (program ~roots:["cell"; "cell"] [role]) "duplicate_root";
  rejected (program ~roots:["absent"] [role]) "dangling_root";
  rejected (program [signal]) "invalid_role";
  rejected (program [node ~inputs:["missing"] "a"]) "dangling_reference";
  rejected (program [node ~inputs:["b"] "a"; node ~inputs:["a"] "b"]) "cyclic_graph";
  rejected (program [set "source" (set "line" (Json.Bool true) location) role]) "invalid_type";
  rejected (program [node "\194\160"]) "invalid_name";
  rejected (program [literal (scalar ~unit_name:"ms" (Json.int 1000) (Json.Float 2.))]) "canonical_value_mismatch";
  rejected (program [literal (scalar (Json.Bool true) (Json.int 1))]) "invalid_type";
  rejected (program [literal (scalar ~unit_name:"weeks" (Json.int 1) (Json.int 1))]) "unsupported_unit";
  let parameter id = node ~kind:"parameter" ~dtype:scalar_type ~attributes:["name", str "duration"; "bound", Json.Bool false] id in
  accepted (program [parameter "a"]);
  rejected (program [parameter "a"; parameter "b"]) "duplicate_parameter";
  rejected (program [node ~kind:"parameter" ~dtype:scalar_type ~attributes:["name", str "duration"; "bound", Json.Bool true] "a"]) "invalid_parameter";
  rejected (program [node ~kind:"literal" "a"]) "missing_type";
  let report = Bioc_checker.Intent_check.check source |> fields in
  require (Json.string (Json.field "validation_scope" report) = "intent-structure-types-bindings-v1") "Missing bounded validation scope";
  require (List.length (Json.array (Json.field "unimplemented_obligations" report)) = 5) "Lost unimplemented obligations";
  print_endline "intent: graph, types, units, bindings, source identity and claim-scope checks passed"
