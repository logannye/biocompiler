open Bioc_wire
module M = Molecular_record
let max_seconds = 31_536_000
let clock = "declared_exposure_start"
let check ?path condition message = Diagnostic.require ?path condition "invalid_deployment" message
let string value = Json.String value
let child path key = path ^ "/" ^ key

module Time = struct
  type t = { json : Json.t; decimal : Q.t }
  let of_json ?path json =
    Diagnostic.require ?path
      (match json with
       | Json.Int value -> Z.sign value >= 0 && Z.compare value (Z.of_int max_seconds) <= 0
       | Json.Float value -> Float.is_finite value && value >= 0. && value <= float_of_int max_seconds
       | _ -> false)
      "invalid_deployment_time" "Deployment time requires bounded finite nonnegative numeric seconds.";
    let decimal = match json with
      | Json.Int value -> Q.of_bigint value
      | Json.Float value ->
          (* Use the pinned Python-compatible shortest spelling, never Q.of_float:
             decimal interval boundaries must not acquire binary rounding gaps. *)
          let text = Canonical.float_string value in
          let mantissa, exponent = match String.split_on_char 'e' text with
            | [mantissa] -> mantissa, 0
            | [mantissa; exponent] -> mantissa, int_of_string exponent
            | _ -> Diagnostic.fail "internal_decimal" "Unexpected finite decimal spelling." in
          let digits, scale = match String.split_on_char '.' mantissa with
            | [whole] -> whole, 0
            | [whole; fraction] -> whole ^ fraction, String.length fraction
            | _ -> Diagnostic.fail "internal_decimal" "Unexpected finite decimal mantissa." in
          let numerator = Z.of_string digits and power = exponent - scale in
          if power >= 0 then Q.of_bigint (Z.mul numerator (Z.pow (Z.of_int 10) power))
          else Q.make numerator (Z.pow (Z.of_int 10) (-power))
      | _ -> assert false in
    { json; decimal }
  let to_json value = value.json
  let zero = of_json (Json.int 0)
  let maximum = of_json (Json.int max_seconds)
  let compare left right = Q.compare left.decimal right.decimal
  let compare_sum left right bound = Q.compare (Q.add left.decimal right.decimal) bound.decimal
  let ratio value = Q.num value.decimal, Q.den value.decimal
end

let assumptions ~path value =
  let items = M.array ~path ~maximum:64 value |> List.map (M.text ~path) in
  check ~path (items <> []) "Deployment timing requires explicit supplied assumptions.";
  let sorted = List.sort_uniq String.compare items in
  check ~path (List.length sorted = List.length items) "Duplicate deployment assumptions.";
  sorted
let assumptions_json values =
  ignore (M.bounded_length ~maximum:64 values);
  Json.Array (List.map string values)
let check_clock ~path fields =
  check ~path (Json.string ~path (Json.field "clock" fields) = clock) "Unsupported deployment clock."
let finish ~path json result = M.check_resources ~path json; result

module Availability = struct
  type t = { id : string; placement : string; onset_min : Time.t; onset_max : Time.t;
             duration_min : Time.t; duration_max : Time.t; assumptions : string list }
  let schema_version = "biocompiler.rna_availability_contract.v0.1"
  let to_json value = Json.Object ["schema_version", string schema_version;
      "id", string value.id; "placement_id", string value.placement;
      "onset_min_seconds", Time.to_json value.onset_min; "onset_max_seconds", Time.to_json value.onset_max;
      "duration_min_seconds", Time.to_json value.duration_min; "duration_max_seconds", Time.to_json value.duration_max;
      "assumptions", assumptions_json value.assumptions; "clock", string clock]
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["id"; "placement_id"; "onset_min_seconds"; "onset_max_seconds";
        "duration_min_seconds"; "duration_max_seconds"; "assumptions"; "clock"] value in
    let get key = Json.field ~path:(child path key) key fields in
    let time key = Time.of_json ~path:(child path key) (get key) in
    let result = { id = M.text ~path:(child path "id") (get "id");
      placement = M.text ~path:(child path "placement_id") (get "placement_id");
      onset_min = time "onset_min_seconds"; onset_max = time "onset_max_seconds";
      duration_min = time "duration_min_seconds"; duration_max = time "duration_max_seconds";
      assumptions = assumptions ~path:(child path "assumptions") (get "assumptions") } in
    check_clock ~path:(child path "clock") fields;
    check ~path (Time.compare result.onset_min result.onset_max <= 0) "Availability onset bounds are reversed.";
    check ~path (Time.compare result.duration_min Time.zero > 0 && Time.compare result.duration_min result.duration_max <= 0)
      "Availability duration requires positive ordered bounds.";
    check ~path (Time.compare_sum result.onset_max result.duration_max Time.maximum <= 0)
      "Availability exceeds the deployment time bound.";
    finish ~path (to_json result) result
  let make ~id ~placement_id ~onset_min ~onset_max ~duration_min ~duration_max ~assumptions =
    of_json (to_json { id; placement = placement_id; onset_min; onset_max; duration_min; duration_max; assumptions })
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id value = value.id
  let placement_id value = value.placement
  let onset_min value = value.onset_min
  let onset_max value = value.onset_max
  let duration_min value = value.duration_min
  let duration_max value = value.duration_max
  let assumptions value = value.assumptions
end

module Requirement = struct
  type t = { id : string; group : string; role : string; compartment : string;
             required_from : Time.t; required_until : Time.t; unavailable_after : Time.t option;
             same_recipient : bool; assumptions : string list }
  let schema_version = "biocompiler.rna_deployment_requirement.v0.1"
  let to_json value = Json.Object ["schema_version", string schema_version;
      "id", string value.id; "delivery_group_id", string value.group; "recipient_role", string value.role;
      "compartment", string value.compartment; "required_from_seconds", Time.to_json value.required_from;
      "required_until_seconds", Time.to_json value.required_until;
      "unavailable_after_seconds", (match value.unavailable_after with None -> Json.Null | Some time -> Time.to_json time);
      "require_same_recipient", Json.Bool value.same_recipient;
      "assumptions", assumptions_json value.assumptions; "clock", string clock]
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["id"; "delivery_group_id"; "recipient_role"; "compartment";
        "required_from_seconds"; "required_until_seconds"; "unavailable_after_seconds";
        "require_same_recipient"; "assumptions"; "clock"] value in
    let get key = Json.field ~path:(child path key) key fields in
    let text key = M.text ~path:(child path key) (get key)
    and time key = Time.of_json ~path:(child path key) (get key) in
    let result = { id = text "id"; group = text "delivery_group_id"; role = text "recipient_role";
      compartment = text "compartment"; required_from = time "required_from_seconds";
      required_until = time "required_until_seconds";
      unavailable_after = (match get "unavailable_after_seconds" with Json.Null -> None
        | value -> Some (Time.of_json ~path:(child path "unavailable_after_seconds") value));
      same_recipient = Json.boolean ~path:(child path "require_same_recipient") (get "require_same_recipient");
      assumptions = assumptions ~path:(child path "assumptions") (get "assumptions") } in
    check_clock ~path:(child path "clock") fields;
    (* Ordered bounds in the legacy declarations compare the original numbers.
       For nonnegative finite binary64/integer values within this bound, decimal
       spelling preserves that order; only sums require exact decimal arithmetic. *)
    check ~path (Time.compare result.required_from result.required_until < 0)
      "Deployment requires a nonempty execution window.";
    Option.iter (fun bound -> check ~path (Time.compare bound result.required_until >= 0)
        "Unavailability precedes the required window.") result.unavailable_after;
    finish ~path (to_json result) result
  let make ~id ~delivery_group_id ~recipient_role ~compartment ~required_from ~required_until
      ~unavailable_after ~require_same_recipient ~assumptions =
    of_json (to_json { id; group = delivery_group_id; role = recipient_role; compartment; required_from; required_until;
                      unavailable_after; same_recipient = require_same_recipient; assumptions })
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id value = value.id
  let delivery_group_id value = value.group
  let recipient_role value = value.role
  let compartment value = value.compartment
  let required_from value = value.required_from
  let required_until value = value.required_until
  let unavailable_after value = value.unavailable_after
  let require_same_recipient value = value.same_recipient
  let assumptions value = value.assumptions
end
