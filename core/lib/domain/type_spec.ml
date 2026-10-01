open Bioc_wire

type kind = Scalar | Condition | Event | Interval | Curve
type t = { kind : kind; name : string; dimensions : (string * Z.t) list; arguments : t list }

let kind value = value.kind
let path_child path name = path ^ "/" ^ name
let require = Diagnostic.require
let fail = Diagnostic.fail

let kind_name = function
  | Scalar -> "scalar" | Condition -> "condition" | Event -> "event"
  | Interval -> "interval" | Curve -> "curve"

let rec of_json ?(path = "") value =
  let fields = Json.object_fields ~path value in
  Json.allowed_fields ~path ~required:["kind"; "name"] ~optional:["dimensions"; "arguments"] fields;
  let kind = match Json.string ~path (Json.field ~path "kind" fields) with
    | "scalar" -> Scalar | "condition" -> Condition | "event" -> Event
    | "interval" -> Interval | "curve" -> Curve
    | _ -> fail ~path "invalid_type_spec" "Unknown semantic type kind."
  in
  let name = Json.string ~path (Json.field ~path "name" fields) in
  require ~path (name <> "") "invalid_type_spec" "A semantic type requires a nonempty name.";
  let dimensions = match List.assoc_opt "dimensions" fields with
    | None -> []
    | Some value ->
        Json.object_fields ~path value
        |> List.map (fun (key, value) ->
            require ~path (key <> "") "invalid_type_spec" "A dimension requires a nonempty name.";
            key, Json.integer ~path value)
        |> List.filter (fun (_, exponent) -> not (Z.equal exponent Z.zero))
        |> List.sort (fun (a, _) (b, _) -> String.compare a b)
  in
  let arguments = match List.assoc_opt "arguments" fields with
    | None -> []
    | Some value -> Json.array ~path value |> List.mapi (fun index -> of_json ~path:(path_child path (string_of_int index)))
  in
  (match kind with
   | Scalar -> require ~path (arguments = []) "invalid_type_spec" "Scalar types cannot have type arguments."
   | Condition | Event ->
       require ~path (dimensions = [] && arguments = []) "invalid_type_spec" "Conditions and events have no dimensions or arguments."
   | Interval | Curve ->
       let count = if kind = Interval then 1 else 2 in
       require ~path (dimensions = [] && List.length arguments = count && List.for_all (fun item -> item.kind = Scalar) arguments)
         "invalid_type_spec" "Intervals and curves require scalar type arguments.");
  { kind; name; dimensions; arguments }

let rec to_json value = Json.Object [
    "kind", Json.String (kind_name value.kind);
    "name", Json.String value.name;
    "dimensions", Json.Object (List.map (fun (key, value) -> key, Json.Int value) value.dimensions);
    "arguments", Json.Array (List.map to_json value.arguments)
  ]

let rec compatible left right =
  left.kind = right.kind && left.dimensions = right.dimensions
  && List.length left.arguments = List.length right.arguments
  && List.for_all2 compatible left.arguments right.arguments

let registered_units value =
  let dimension key exponent = [key, Z.of_int exponent] in
  if value.kind <> Scalar || value.arguments <> [] then None
  else match value.name, value.dimensions with
  | "Level", [] -> Some ["1", Json.int 1; "dimensionless", Json.int 1]
  | "Duration", dims when dims = dimension "time" 1 ->
      Some ["s", Json.int 1; "sec", Json.int 1; "second", Json.int 1; "seconds", Json.int 1;
            "ms", Json.Float 0.001; "min", Json.int 60; "minute", Json.int 60; "minutes", Json.int 60;
            "h", Json.int 3600; "hour", Json.int 3600; "hours", Json.int 3600;
            "d", Json.int 86400; "day", Json.int 86400; "days", Json.int 86400]
  | "Concentration", [("amount", one); ("length", minus_three)]
      when Z.equal one Z.one && Z.equal minus_three (Z.of_int (-3)) ->
      Some ["mol/m^3", Json.int 1; "mol/L", Json.int 1000; "M", Json.int 1000;
            "mM", Json.int 1; "uM", Json.Float 1e-3; "µM", Json.Float 1e-3;
            "nM", Json.Float 1e-6; "pM", Json.Float 1e-9]
  | "SurfaceDensity", [("amount", one); ("length", minus_two)]
      when Z.equal one Z.one && Z.equal minus_two (Z.of_int (-2)) ->
      Some ["mol/m^2", Json.int 1; "molecules/um^2", Json.Float (1e12 /. 6.02214076e23);
            "molecules/µm^2", Json.Float (1e12 /. 6.02214076e23)]
  | "ProductionRate", [("amount", one); ("time", minus_one)]
      when Z.equal one Z.one && Z.equal minus_one Z.minus_one ->
      Some ["mol/s", Json.int 1; "mol/min", Json.Float (1. /. 60.);
            "molecules/s", Json.Float (1. /. 6.02214076e23);
            "molecules/min", Json.Float (1. /. (60. *. 6.02214076e23))]
  | _ -> None

let multiply left right = match left, right with
  | Json.Int left, Json.Int right -> Json.Int (Z.mul left right)
  | _ -> Json.Float (Json.number_to_float left *. Json.number_to_float right)

let finite_number ~path value =
  let number = Json.number ~path value in
  ignore (Json.number_to_float ~path number);
  number

let rec validate_binding ?(path = "") ~expected value =
  let fields = Json.object_fields ~path value in
  let expected_fields = match expected.kind with
    | Scalar -> ["kind"; "value"; "unit"; "canonical_value"; "type"]
    | Interval -> ["kind"; "lower"; "upper"; "type"]
    | Curve -> ["kind"; "points"; "interpolation"; "extrapolation"; "type"]
    | Condition | Event -> fail ~path "invalid_binding" "Conditions and events do not accept literal bindings."
  in
  Json.exact_fields ~path expected_fields fields;
  require ~path (Json.string ~path (Json.field "kind" fields) = kind_name expected.kind)
    "invalid_binding" "Binding kind disagrees with its declared type.";
  let actual = of_json ~path:(path_child path "type") (Json.field "type" fields) in
  require ~path (compatible actual expected) "type_mismatch" "Binding type disagrees with its declaration.";
  match actual.kind with
  | Scalar ->
      let value = finite_number ~path (Json.field "value" fields) in
      let canonical = finite_number ~path (Json.field "canonical_value" fields) in
      let unit = Json.name ~path (Json.field "unit" fields) in
      (match registered_units actual with
       | None -> ()
       | Some units ->
           let factor = match List.assoc_opt unit units with
             | None -> fail ~path "unsupported_unit" "Unsupported unit for the registered scalar type."
             | Some factor -> factor
           in
           let normalized = finite_number ~path (multiply value factor) in
           require ~path (Json.number_compare canonical normalized = 0)
             "canonical_value_mismatch" "Canonical value disagrees with its value and registered unit.")
  | Interval ->
      let item = List.hd actual.arguments in
      let lower = Json.field "lower" fields and upper = Json.field "upper" fields in
      validate_binding ~path:(path_child path "lower") ~expected:item lower;
      validate_binding ~path:(path_child path "upper") ~expected:item upper;
      let canonical value = Json.field "canonical_value" (Json.object_fields value) in
      require ~path (Json.number_compare (canonical lower) (canonical upper) <= 0)
        "invalid_interval" "Interval lower bound exceeds upper bound."
  | Curve ->
      let input_type, output_type = match actual.arguments with
        | [input; output] -> input, output
        | _ -> assert false
      in
      let points = Json.array ~path (Json.field "points" fields) in
      require ~path (List.length points >= 2) "invalid_curve" "A curve requires at least two points.";
      let previous = ref None in
      List.iteri (fun index point ->
        let point_path = path_child path ("points/" ^ string_of_int index) in
        let x, y = match Json.array ~path:point_path point with
          | [x; y] -> x, y
          | _ -> fail ~path:point_path "invalid_curve" "Curve points require input/output pairs."
        in
        validate_binding ~path:point_path ~expected:input_type x;
        validate_binding ~path:point_path ~expected:output_type y;
        let canonical = Json.field "canonical_value" (Json.object_fields x) in
        (match !previous with
         | Some value -> require ~path:point_path (Json.number_compare value canonical < 0)
             "invalid_curve" "Curve inputs must be strictly increasing."
         | None -> ());
        previous := Some canonical) points;
      let interpolation = Json.string ~path (Json.field "interpolation" fields)
      and extrapolation = Json.string ~path (Json.field "extrapolation" fields) in
      require ~path (List.mem interpolation ["linear"; "step"]) "invalid_curve" "Unsupported curve interpolation.";
      require ~path (List.mem extrapolation ["clamp"; "error"]) "invalid_curve" "Unsupported curve extrapolation."
  | Condition | Event -> assert false
