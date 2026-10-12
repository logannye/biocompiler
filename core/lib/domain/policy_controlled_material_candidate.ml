open Bioc_wire
module K = Construction_content
module Input = Policy_material_request
module M = Molecular_record
let schema_version = "biocompiler.policy_controlled_composition_material_candidate.v0.1"
type t = {
  raw:Json.t; identity:string; work:int;
  request_identity:string; construction_value:K.t;
}
let of_json ?(charge=fun _ -> ()) (raw:Json.t) : t =
  let work = ref 0 in
  let spend amount =
    Diagnostic.require (amount >= 0 && amount <= max_int - !work)
      "controlled_material_candidate_resource" "Candidate work accounting overflow.";
    charge amount; work := !work + amount in
  let bytes = Input.preflight ~charge:spend raw in
  let path = "/payload/candidate" in
  let fields = Json.object_fields ~path raw in
  Json.exact_fields ~path ["schema_version";"request_fingerprint";"construction"] fields;
  Diagnostic.require (Json.field "schema_version" fields = Json.String schema_version)
    "controlled_material_candidate" "Unsupported controlled material-only candidate schema.";
  let request_identity = Json.string (Json.field "request_fingerprint" fields) in
  Diagnostic.require (String.length request_identity = 64 &&
      String.for_all (function '0'..'9'|'a'..'f' -> true | _ -> false) request_identity)
    "controlled_material_candidate" "Request identity must be an exact lowercase SHA-256.";
  let content = Json.field "construction" fields in
  ignore (Input.preflight ~charge:spend content);
  let construction_value = K.of_json ~path:(path ^ "/construction") content in
  spend bytes;
  let encoded = Canonical.encode_bounded ~max_bytes:M.max_json_bytes raw in
  Diagnostic.require (String.length encoded = bytes) "controlled_material_candidate_resource"
    "Candidate canonical byte accounting disagrees.";
  spend bytes;
  let identity = Canonical.sha256 encoded in
  {raw;identity;work= !work;request_identity;construction_value}
let to_json (value:t) = value.raw
let fingerprint (value:t) = value.identity
let decoding_work (value:t) = value.work
let request_fingerprint (value:t) = value.request_identity
let construction (value:t) = value.construction_value
