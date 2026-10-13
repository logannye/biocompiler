open Bioc_wire
module R = Bioc_domain.Policy_controlled_workflow_request
module C = Bioc_domain.Policy_controlled_workflow_candidate
let implementation_version = "biocompiler.ocaml.policy_controlled_workflow_producer.v0.1"
let construct_candidate ~charge (request:R.t) : C.t =
  charge 1;
  let material = Policy_controlled_material_producer.construct_candidate ~charge (R.original request) in
  let behavior = Policy_controlled_behavior_producer.construct_candidate ~charge (R.behavior request) in
  C.of_json ~charge (Json.Object ["schema_version",Json.String C.schema_version;
    "request_fingerprint",Json.String (R.fingerprint request);
    "material_candidate",Bioc_domain.Policy_controlled_material_candidate.to_json material;
    "behavior_candidate",Bioc_domain.Policy_controlled_behavior_candidate.to_json behavior])
