open Bioc_wire
module Input = Policy_material_request
let schema_version = "biocompiler.policy_quantitative_assurance_request.v0.1"
let profile = "biocompiler.policy_quantitative_assurance.v0.1"
let maximum_work = 134217728
type t = {raw:Json.t;material:Json.t;approx:Policy_approximation_contract.t option;
  evidence:Policy_realization_evidence_contract.t option;work:int}
let of_json ?(charge=fun _->()) raw =
  ignore(Input.preflight ~max_bytes:8388608 ~max_nodes:250000 ~max_depth:128 ~charge raw);
  let fields=Json.object_fields ~path:"/request" raw in
  Json.exact_fields ~path:"/request" ["schema_version";"profile";"material_request";
    "approximation";"realization_evidence";"max_work"] fields;
  let get key=Json.field key fields in
  Diagnostic.require(get "schema_version"=Json.String schema_version && get "profile"=Json.String profile)
    "policy_quantitative_assurance_request" "Unknown quantitative assurance schema or profile.";
  let work=Json.integer ~path:"/request/max_work" (get "max_work") in
  Diagnostic.require(Z.sign work>0 && Z.leq work(Z.of_int maximum_work))
    "policy_quantitative_assurance_request" "Assurance work must lower the fixed positive ceiling.";
  let material=get "material_request" in
  ignore(Json.object_fields ~path:"/request/material_request" material);
  let approx=match get "approximation" with Json.Null->None|value->Some(Policy_approximation_contract.of_json ~charge value)
  and evidence=match get "realization_evidence" with Json.Null->None|value->Some(Policy_realization_evidence_contract.of_json ~charge value) in
  {raw;material;approx;evidence;work=Z.to_int work}
let to_json value=value.raw
let material_request value=value.material
let approximation value=value.approx
let realization_evidence value=value.evidence
let max_work value=value.work
