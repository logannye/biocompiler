open Bioc_wire
module Behavior = Policy_controlled_behavior_request
module Original = Policy_controlled_composition_request
let schema_version = "biocompiler.policy_controlled_workflow_request.v0.1"
let limits_schema = "biocompiler.policy_controlled_workflow_limits.v0.1"
let profile = Original.profile
let resource_profile = Original.resource_profile
type t = { body:Json.t; behavior_value:Behavior.t; identity:string; work:int; limits_value:Json.t }
let get key raw = Json.field key (Json.object_fields raw)
let project_limits (behavior:Behavior.t) =
  let original = Original.raw (Behavior.original behavior) in
  let domain = get "operating_domain" original in
  Json.Object ["schema_version",Json.String limits_schema;
    "budgets",get "budgets" original;"domain_limits",get "limits" domain;
    "horizon_tick",get "horizon_tick" domain;
    "intervention_cutoff_tick",get "intervention_cutoff_tick" domain;
    "resources",get "resources" original]
let of_json ?(charge=fun _ -> ()) body =
  let work = ref 0 in
  let spend amount =
    Diagnostic.require (amount >= 0 && amount <= max_int - !work)
      "controlled_workflow_request" "Workflow decoding work overflow.";
    charge amount; work := !work + amount in
  let measure value = Policy_material_request.preflight ~charge:spend value in
  let encode value =
    let bytes = measure value in spend bytes;
    let encoded = Canonical.encode_bounded ~max_bytes:Molecular_record.max_json_bytes value in
    Diagnostic.require (String.length encoded = bytes) "controlled_workflow_request"
      "Workflow canonical byte accounting disagrees.";
    encoded in
  ignore (measure body);
  Json.exact_fields ["schema_version";"behavior_request";"limits"] (Json.object_fields body);
  Diagnostic.require (get "schema_version" body = Json.String schema_version)
    "controlled_workflow_request" "Unsupported joined workflow request schema.";
  let behavior_value = Behavior.of_json ~charge:spend (get "behavior_request" body) in
  let limits_value = get "limits" body in
  Json.exact_fields ["schema_version";"budgets";"domain_limits";"horizon_tick";
    "intervention_cutoff_tick";"resources"] (Json.object_fields limits_value);
  let expected = encode (project_limits behavior_value) and actual = encode limits_value in
  spend (String.length expected + String.length actual);
  Diagnostic.require (expected = actual) "controlled_workflow_limits_binding"
    "Every workflow limit must exactly equal its complete native original authority.";
  let encoded = encode body in spend (String.length encoded);
  Diagnostic.require (!work <= (Behavior.budgets behavior_value).max_work)
    "controlled_workflow_request" "Joined request decoding exceeds the original work ceiling.";
  {body;behavior_value;identity=Canonical.sha256 encoded;work= !work;limits_value}
let raw (value:t) = value.body
let to_json = raw
let behavior (value:t) = value.behavior_value
let original (value:t) = Behavior.original value.behavior_value
let limits (value:t) = value.limits_value
let budgets (value:t) = Behavior.budgets value.behavior_value
let fingerprint (value:t) = value.identity
let decoding_work (value:t) = value.work
