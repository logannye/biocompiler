open Bioc_wire
module I = Policy_controlled_activity_implementation
module Input = Policy_material_request
let schema_version = "biocompiler.policy_controlled_behavior_candidate.v0.1"
type t = { raw:Json.t; identity:string; work:int;
  request_identity:string; implementation_value:I.t }
let of_json ?(charge=fun _ -> ()) (raw:Json.t) : t =
  let work = ref 0 in
  let spend amount =
    Diagnostic.require (amount >= 0 && amount <= max_int - !work)
      "controlled_behavior_candidate_resource" "Candidate work accounting overflow.";
    charge amount; work := !work + amount in
  let bytes = Input.preflight ~charge:spend raw in
  let fields = Json.object_fields raw in
  Json.exact_fields ["schema_version";"request_fingerprint";"implementation"] fields;
  Diagnostic.require (Json.field "schema_version" fields = Json.String schema_version)
    "controlled_behavior_candidate" "Unsupported behavior-only candidate schema.";
  let request_identity = Json.string (Json.field "request_fingerprint" fields) in
  Diagnostic.require (String.length request_identity = 64 &&
      String.for_all (function '0'..'9'|'a'..'f' -> true | _ -> false) request_identity)
    "controlled_behavior_candidate" "Request identity must be an exact lowercase SHA-256.";
  let implementation_value = I.of_json ~charge:spend (Json.field "implementation" fields) in
  spend bytes;
  let encoded = Canonical.encode_bounded ~max_bytes:Molecular_record.max_json_bytes raw in
  Diagnostic.require (String.length encoded = bytes) "controlled_behavior_candidate_resource"
    "Candidate canonical byte accounting disagrees.";
  spend bytes;
  {raw;identity=Canonical.sha256 encoded;work= !work;request_identity;implementation_value}
let to_json (value:t) = value.raw
let fingerprint (value:t) = value.identity
let decoding_work (value:t) = value.work
let request_fingerprint (value:t) = value.request_identity
let implementation (value:t) = value.implementation_value
