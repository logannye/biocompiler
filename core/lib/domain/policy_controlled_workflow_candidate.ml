open Bioc_wire
module Material = Policy_controlled_material_candidate
module Behavior = Policy_controlled_behavior_candidate
let schema_version = "biocompiler.policy_controlled_workflow_candidate.v0.1"
type t = { body:Json.t; identity:string; work:int; request_identity:string;
  material_value:Material.t; behavior_value:Behavior.t }
let of_json ?(charge=fun _ -> ()) body =
  let work = ref 0 in
  let spend amount =
    Diagnostic.require (amount >= 0 && amount <= max_int - !work)
      "controlled_workflow_candidate" "Joined candidate work overflow.";
    charge amount; work := !work + amount in
  let bytes = Policy_material_request.preflight ~charge:spend body in
  let fields = Json.object_fields body in
  Json.exact_fields ["schema_version";"request_fingerprint";"material_candidate";"behavior_candidate"] fields;
  Diagnostic.require (Json.field "schema_version" fields = Json.String schema_version)
    "controlled_workflow_candidate" "Unsupported joined candidate schema.";
  let request_identity = Json.string (Json.field "request_fingerprint" fields) in
  Diagnostic.require (String.length request_identity = 64 &&
    String.for_all (function '0'..'9'|'a'..'f' -> true | _ -> false) request_identity)
    "controlled_workflow_candidate" "Request identity must be an exact lowercase SHA-256.";
  let material_value = Material.of_json ~charge:spend (Json.field "material_candidate" fields) in
  let behavior_value = Behavior.of_json ~charge:spend (Json.field "behavior_candidate" fields) in
  spend bytes;
  let encoded = Canonical.encode_bounded ~max_bytes:Molecular_record.max_json_bytes body in
  Diagnostic.require (String.length encoded = bytes) "controlled_workflow_candidate"
    "Joined candidate canonical byte accounting disagrees.";
  spend bytes;
  {body;identity=Canonical.sha256 encoded;work= !work;request_identity;material_value;behavior_value}
let to_json (value:t) = value.body
let fingerprint (value:t) = value.identity
let decoding_work (value:t) = value.work
let request_fingerprint (value:t) = value.request_identity
let material (value:t) = value.material_value
let behavior (value:t) = value.behavior_value
