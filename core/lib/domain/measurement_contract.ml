open Bioc_wire
module N = Runtime_number
let require ?path condition message = Diagnostic.require ?path condition "invalid_measurement_contract" message
let str value = Json.String value
let field key value = Json.field key (Json.object_fields value)
let replace key value fields = (key, value) :: List.remove_assoc key fields
let bounded_list ?(path = "") values =
  let rec count remaining = function
    | [] -> ()
    | _ :: rest -> Diagnostic.require ~path (remaining > 0) "human_record_limit" "Human record collection exceeds its native bound."; count (remaining - 1) rest
  in count Limits.max_json_nodes values; values

type visit = Enter of Json.t * int | Leave of Json.t
(* Bound native values before sorting, recursive decoding or canonical encoding.
   Wire nodes are values; keys consume encoded bytes but are not value nodes. *)
let preflight ?(path = "") value =
  let limit condition = Diagnostic.require ~path condition "human_record_limit" "Human record exceeds the native request budget." in
  let bytes = ref 0 and nodes = ref 0 and queued = ref 1 in
  let add amount = limit (amount <= Limits.max_request_bytes - !bytes); bytes := !bytes + amount in
  let quoted value =
    limit (String.length value <= Limits.max_string_bytes); add (String.length value + 2);
    String.iter (function '"' | '\\' | '\b' | '\012' | '\n' | '\r' | '\t' -> add 1
      | value when Char.code value < 32 -> add 5 | _ -> ()) value;
    Json.validate_utf8 value in
  let length maximum values =
    let rec loop count = function
      | [] -> count
      | _ :: rest -> limit (count < maximum); loop (count + 1) rest in
    loop 0 values in
  let pending = ref [Enter (value, 0)] and active = ref [] in
  while !pending <> [] do
    let next = List.hd !pending in pending := List.tl !pending;
    match next with
    | Leave value -> active := List.filter (fun item -> item != value) !active
    | Enter (value, depth) ->
        decr queued; incr nodes; limit (!nodes <= Limits.max_json_nodes && depth <= Limits.max_depth);
        let enter children count =
          Diagnostic.require ~path (not (List.exists (fun item -> item == value) !active)) "human_record_cycle" "Cyclic human record.";
          active := value :: !active; pending := Leave value :: !pending;
          List.iter (fun child -> pending := Enter (child, depth + 1) :: !pending) children;
          queued := !queued + count in
        (match value with
        | Json.Null -> add 4
        | Json.Bool value -> add (if value then 4 else 5)
        | Json.Int value ->
            limit (Z.numbits value <= 4 * Limits.max_number_chars);
            let text = Z.to_string value in limit (String.length text <= Limits.max_number_chars); add (String.length text)
        | Json.Float value ->
            Diagnostic.require ~path (Float.is_finite value) "nonfinite_number" "Human records require finite JSON numbers.";
            add (String.length (Canonical.float_string value))
        | Json.String value -> quoted value
        | Json.Array values ->
            let count = length (Limits.max_json_nodes - !nodes - !queued) values in
            add (2 + max 0 (count - 1)); enter values count
        | Json.Object fields ->
            let count = length (Limits.max_json_nodes - !nodes - !queued) fields in
            add (2 + count + max 0 (count - 1));
            let seen = Hashtbl.create 16 in
            List.iter (fun (key, _) -> quoted key;
                Diagnostic.require ~path (not (Hashtbl.mem seen key)) "duplicate_key" "Duplicate human record field.";
                Hashtbl.add seen key ()) fields;
            enter (List.map snd fields) count)
  done
let record ?(path = "") version keys value =
  preflight ~path value;
  let fields = Json.object_fields ~path value in
  Json.exact_fields ~path ("schema_version" :: keys) fields;
  Diagnostic.require ~path (Json.string (Json.field "schema_version" fields) = version) "unsupported_schema" "Unsupported human record schema.";
  fields
let finish value = preflight value; value
let type_equal left right = Json.equal (Type_spec.to_json left) (Type_spec.to_json right)
let duration_type = Type_spec.of_json (Json.parse {|{"kind":"scalar","name":"Duration","dimensions":{"time":1},"arguments":[]}|})
let production_rate_type = Type_spec.of_json (Json.parse {|{"kind":"scalar","name":"ProductionRate","dimensions":{"amount":1,"time":-1},"arguments":[]}|})
let interval_type dtype = Type_spec.of_json (Json.Object ["kind", str "interval"; "name", str "Interval";
    "dimensions", Json.Object []; "arguments", Json.Array [Type_spec.to_json dtype]])

module Scalar = struct
  type t = { json : Json.t; dtype : Type_spec.t; canonical : N.t }
  let of_json ?(path = "") ?expected value =
    preflight ~path value;
    let dtype = Type_spec.of_json ~path:(path ^ "/type") (field "type" value) in
    require ~path (Type_spec.kind dtype = Type_spec.Scalar) "Expected a typed scalar measurement.";
    let expected = Option.value expected ~default:dtype in
    let json = Type_spec.normalize_binding ~path ~expected value |> finish in
    {json; dtype; canonical = N.of_json ~path:(path ^ "/canonical_value") (field "canonical_value" json)}
  let to_json value = value.json
  let dtype value = value.dtype
  let canonical value = value.canonical
  let duration ?(path = "") ?(positive = false) value =
    let value = of_json ~path ~expected:duration_type value in
    require ~path (if positive then N.compare value.canonical N.zero > 0 else N.compare value.canonical N.zero >= 0)
      "Duration must be nonnegative, or positive where required."; value
end
module Interval = struct
  type t = { json : Json.t; dtype : Type_spec.t; lower : Scalar.t; upper : Scalar.t }
  let of_json ?(path = "") ?expected value =
    preflight ~path value;
    let dtype = Type_spec.of_json ~path:(path ^ "/type") (field "type" value) in
    require ~path (Type_spec.kind dtype = Type_spec.Interval) "Expected a typed interval measurement.";
    let expected = match expected with None -> dtype | Some value -> interval_type value in
    let json = Type_spec.normalize_binding ~path ~expected value |> finish in
    {json; dtype; lower = Scalar.of_json ~path:(path ^ "/lower") (field "lower" json);
     upper = Scalar.of_json ~path:(path ^ "/upper") (field "upper" json)}
  let to_json value = value.json
  let dtype value = value.dtype
  let lower value = Scalar.canonical value.lower
  let upper value = Scalar.canonical value.upper
  let lower_scalar value = value.lower
  let upper_scalar value = value.upper
end
module Observable = struct
  type scope = Cell | Contact
  type t = { json : Json.t; id : string; dtype : Type_spec.t; role : string; scope : scope; compartment : string }
  let schema_version = "biocompiler.observable.v0.1"
  let of_json ?(path = "") value =
    let fields = record ~path schema_version ["id"; "dtype"; "role"; "scope"; "compartment"] value in
    let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
    let name key = Json.name ~path:(path ^ "/" ^ key) (get key) in
    let dtype = Type_spec.of_json ~path:(path ^ "/dtype") (get "dtype") in
    require ~path (List.mem (Type_spec.kind dtype) [Type_spec.Scalar; Type_spec.Condition]) "Observable requires a scalar or condition type.";
    let scope = match Json.string (get "scope") with "cell" -> Cell | "contact" -> Contact
      | _ -> Diagnostic.fail ~path "invalid_measurement_contract" "Unknown observable scope." in
    {json = finish (Json.Object (replace "dtype" (Type_spec.to_json dtype) fields));
     id = name "id"; dtype; role = name "role"; scope; compartment = name "compartment"}
  let to_json value = value.json
  let fingerprint value = Canonical.fingerprint value.json
  let id value = value.id
  let dtype value = value.dtype
  let role value = value.role
  let scope value = value.scope
  let compartment value = value.compartment
end
module Response = struct
  type t = { json : Json.t; observable : Observable.t; active : Interval.t; inactive : Interval.t;
             activation : Scalar.t; deactivation : Scalar.t; rule : string; specification : string }
  let schema_version = "biocompiler.response_requirement.v0.1"
  let of_json ?(path = "") value =
    let fields = record ~path schema_version ["id"; "rule_id"; "specification_id"; "observable";
        "active_range"; "inactive_range"; "max_activation_delay"; "max_deactivation_delay"] value in
    let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
    ignore (Json.name ~path (get "id"));
    let rule = Json.name ~path (get "rule_id") and specification = Json.name ~path (get "specification_id") in
    let observable = Observable.of_json ~path:(path ^ "/observable") (get "observable") in
    let dtype = Observable.dtype observable in
    require ~path (Type_spec.kind dtype = Type_spec.Scalar) "Response requires a scalar observable.";
    let active = Interval.of_json ~path:(path ^ "/active_range") ~expected:dtype (get "active_range")
    and inactive = Interval.of_json ~path:(path ^ "/inactive_range") ~expected:dtype (get "inactive_range") in
    require ~path (N.compare (Interval.upper active) (Interval.lower inactive) < 0 || N.compare (Interval.upper inactive) (Interval.lower active) < 0)
      "Closed active and inactive response ranges must be disjoint.";
    let activation = Scalar.duration ~path:(path ^ "/max_activation_delay") (get "max_activation_delay")
    and deactivation = Scalar.duration ~path:(path ^ "/max_deactivation_delay") (get "max_deactivation_delay") in
    let json = Json.Object (fields |> replace "observable" (Observable.to_json observable)
        |> replace "active_range" (Interval.to_json active) |> replace "inactive_range" (Interval.to_json inactive)
        |> replace "max_activation_delay" (Scalar.to_json activation) |> replace "max_deactivation_delay" (Scalar.to_json deactivation)) |> finish in
    {json; observable; active; inactive; activation; deactivation; rule; specification}
  let to_json value = value.json
  let fingerprint value = Canonical.fingerprint value.json
  let observable value = value.observable
  let active value = value.active
  let inactive value = value.inactive
  let activation value = value.activation
  let deactivation value = value.deactivation
  let rule_id value = value.rule
  let specification_id value = value.specification
end
