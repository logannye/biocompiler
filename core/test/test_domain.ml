open Bioc_wire
open Bioc_domain

let require condition message = if not condition then failwith message
let parse = Json.parse
let binding_type value = Type_spec.of_json (Json.field "type" (Json.object_fields value))

(* Json.equal deliberately ignores object order. Public provider views expose
   Python mapping iteration, so check each original literal serializer's order
   separately, including scalar children of interval and curve bindings. *)
let rec check_binding_order label value =
  let fields = Json.object_fields value in
  let field key = Json.field key fields in
  let expected, children = match Json.string (field "kind") with
    | "scalar" -> ["kind"; "value"; "unit"; "canonical_value"; "type"], []
    | "interval" -> ["kind"; "lower"; "upper"; "type"], [field "lower"; field "upper"]
    | "curve" -> ["kind"; "type"; "points"; "interpolation"; "extrapolation"],
        List.concat_map Json.array (Json.array (field "points"))
    | _ -> failwith (label ^ ": unexpected literal kind") in
  require (List.map fst fields = expected) (label ^ ": public literal mapping order differs");
  List.iter (check_binding_order label) children

let rec reverse_object_order = function
  | Json.Object fields -> Json.Object
      (List.rev_map (fun (key, value) -> key, reverse_object_order value) fields)
  | Json.Array values -> Json.Array (List.map reverse_object_order values)
  | value -> value

let check label source expected =
  let source = parse source and expected = parse expected in
  let actual = Type_spec.normalize_binding ~expected:(binding_type source) source in
  require (Json.equal actual expected)
    (label ^ ": normalized value differs: " ^ Canonical.encode actual);
  check_binding_order label actual;
  let repeated = Type_spec.normalize_binding ~expected:(binding_type actual) actual in
  require (Json.equal repeated actual) (label ^ ": normalization is not idempotent");
  check_binding_order (label ^ " repeated") repeated;
  let reordered = Type_spec.normalize_binding ~expected:(binding_type source)
      (reverse_object_order source) in
  require (Json.equal reordered actual) (label ^ ": input order changed normalized meaning");
  check_binding_order (label ^ " reordered input") reordered

let rejected label expected source code =
  let source = parse source in
  let check operation =
    match operation () with
    | () -> failwith (label ^ ": invalid binding accepted")
    | exception Diagnostic.Error diagnostic ->
        require (diagnostic.code = code) (label ^ ": wrong diagnostic: " ^ diagnostic.code);
        require (diagnostic.path = Some "/binding") (label ^ ": lost diagnostic path")
  in
  check (fun () -> Type_spec.validate_binding ~path:"/binding" ~expected source);
  check (fun () -> ignore (Type_spec.normalize_binding ~path:"/binding" ~expected source))

let () =
  (* Expected JSON is literal Python decode_binding(...).to_dict() output;
     equality distinguishes integer/float forms and the sign of zero. *)
  check "registered integer product"
    {|{"kind":"scalar","value":1,"unit":"min","canonical_value":60.0,"type":{"kind":"scalar","name":"Duration","dimensions":{"time":1,"unused":0}}}|}
    {|{"kind":"scalar","value":1,"unit":"min","canonical_value":60,"type":{"kind":"scalar","name":"Duration","dimensions":{"time":1},"arguments":[]}}|};
  check "registered floating product"
    {|{"kind":"scalar","value":1000,"unit":"ms","canonical_value":1,"type":{"kind":"scalar","name":"Duration","dimensions":{"time":1}}}|}
    {|{"kind":"scalar","value":1000,"unit":"ms","canonical_value":1.0,"type":{"kind":"scalar","name":"Duration","dimensions":{"time":1},"arguments":[]}}|};
  check "registered negative zero"
    {|{"kind":"scalar","value":-0.0,"unit":"s","canonical_value":0,"type":{"kind":"scalar","name":"Duration","dimensions":{"time":1}}}|}
    {|{"kind":"scalar","value":-0.0,"unit":"s","canonical_value":-0.0,"type":{"kind":"scalar","name":"Duration","dimensions":{"time":1},"arguments":[]}}|};
  check "registered positive zero"
    {|{"kind":"scalar","value":0.0,"unit":"s","canonical_value":-0.0,"type":{"kind":"scalar","name":"Duration","dimensions":{"time":1}}}|}
    {|{"kind":"scalar","value":0.0,"unit":"s","canonical_value":0.0,"type":{"kind":"scalar","name":"Duration","dimensions":{"time":1},"arguments":[]}}|};
  check "large integer remains exact"
    {|{"kind":"scalar","value":9007199254740993,"unit":"s","canonical_value":9007199254740993,"type":{"kind":"scalar","name":"Duration","dimensions":{"time":1}}}|}
    {|{"kind":"scalar","value":9007199254740993,"unit":"s","canonical_value":9007199254740993,"type":{"kind":"scalar","name":"Duration","dimensions":{"time":1},"arguments":[]}}|};
  check "custom conversion retained"
    {|{"kind":"scalar","value":2,"unit":"arbitrary-unit","canonical_value":-0.0,"type":{"kind":"scalar","name":"CustomDuration","dimensions":{"time":1,"zero":0}}}|}
    {|{"kind":"scalar","value":2,"unit":"arbitrary-unit","canonical_value":-0.0,"type":{"kind":"scalar","name":"CustomDuration","dimensions":{"time":1},"arguments":[]}}|};
  check "interval recursively normalized"
    {|{"kind":"interval","type":{"kind":"interval","name":"CustomInterval","arguments":[{"kind":"scalar","name":"Duration","dimensions":{"time":1}}]},"lower":{"kind":"scalar","value":0,"unit":"ms","canonical_value":0,"type":{"kind":"scalar","name":"Duration","dimensions":{"time":1}}},"upper":{"kind":"scalar","value":1,"unit":"min","canonical_value":60.0,"type":{"kind":"scalar","name":"Duration","dimensions":{"time":1}}}}|}
    {|{"kind":"interval","type":{"kind":"interval","name":"CustomInterval","dimensions":{},"arguments":[{"kind":"scalar","name":"Duration","dimensions":{"time":1},"arguments":[]}]},"lower":{"kind":"scalar","value":0,"unit":"ms","canonical_value":0.0,"type":{"kind":"scalar","name":"Duration","dimensions":{"time":1},"arguments":[]}},"upper":{"kind":"scalar","value":1,"unit":"min","canonical_value":60,"type":{"kind":"scalar","name":"Duration","dimensions":{"time":1},"arguments":[]}}}|};
  check "curve recursively normalized"
    {|{"kind":"curve","type":{"kind":"curve","name":"CustomCurve","arguments":[{"kind":"scalar","name":"Level"},{"kind":"scalar","name":"Duration","dimensions":{"time":1}}]},"points":[[{"kind":"scalar","value":0,"unit":"1","canonical_value":0.0,"type":{"kind":"scalar","name":"Level"}},{"kind":"scalar","value":1000,"unit":"ms","canonical_value":1,"type":{"kind":"scalar","name":"Duration","dimensions":{"time":1}}}],[{"kind":"scalar","value":1,"unit":"1","canonical_value":1.0,"type":{"kind":"scalar","name":"Level"}},{"kind":"scalar","value":2,"unit":"s","canonical_value":2.0,"type":{"kind":"scalar","name":"Duration","dimensions":{"time":1}}}]],"interpolation":"step","extrapolation":"error"}|}
    {|{"kind":"curve","type":{"kind":"curve","name":"CustomCurve","dimensions":{},"arguments":[{"kind":"scalar","name":"Level","dimensions":{},"arguments":[]},{"kind":"scalar","name":"Duration","dimensions":{"time":1},"arguments":[]}]},"points":[[{"kind":"scalar","value":0,"unit":"1","canonical_value":0,"type":{"kind":"scalar","name":"Level","dimensions":{},"arguments":[]}},{"kind":"scalar","value":1000,"unit":"ms","canonical_value":1.0,"type":{"kind":"scalar","name":"Duration","dimensions":{"time":1},"arguments":[]}}],[{"kind":"scalar","value":1,"unit":"1","canonical_value":1,"type":{"kind":"scalar","name":"Level","dimensions":{},"arguments":[]}},{"kind":"scalar","value":2,"unit":"s","canonical_value":2,"type":{"kind":"scalar","name":"Duration","dimensions":{"time":1},"arguments":[]}}]],"interpolation":"step","extrapolation":"error"}|};
  let duration = Type_spec.of_json (parse {|{"kind":"scalar","name":"Duration","dimensions":{"time":1}}|}) in
  let custom = parse {|{"kind":"scalar","value":2,"unit":"custom","canonical_value":7.0,"type":{"kind":"scalar","name":"CustomDuration","dimensions":{"time":1}}}|} in
  let normalized = Type_spec.normalize_binding ~expected:duration custom in
  require (Json.string (Json.field "name" (Json.object_fields (Json.field "type" (Json.object_fields normalized)))) = "CustomDuration")
    "Normalization substituted the compatible expected type's name";
  require (Json.equal (Json.field "canonical_value" (Json.object_fields normalized)) (Json.Float 7.))
    "Normalization invented a conversion for a compatible custom type";
  rejected "bad canonical is not repaired" duration
    {|{"kind":"scalar","value":1000,"unit":"ms","canonical_value":2,"type":{"kind":"scalar","name":"Duration","dimensions":{"time":1}}}|}
    "canonical_value_mismatch";
  rejected "Boolean is not a number" duration
    {|{"kind":"scalar","value":true,"unit":"s","canonical_value":1,"type":{"kind":"scalar","name":"Duration","dimensions":{"time":1}}}|}
    "invalid_type";
  rejected "unknown unit is not normalized" duration
    {|{"kind":"scalar","value":1,"unit":"week","canonical_value":1,"type":{"kind":"scalar","name":"Duration","dimensions":{"time":1}}}|}
    "unsupported_unit";
  rejected "incompatible type is not coerced" duration
    {|{"kind":"scalar","value":1,"unit":"1","canonical_value":1,"type":{"kind":"scalar","name":"Level"}}|}
    "type_mismatch";
  print_endline "domain: exact typed-binding reconstruction and validation preservation checked"
