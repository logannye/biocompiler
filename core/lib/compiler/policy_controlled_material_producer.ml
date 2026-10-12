open Bioc_wire
module R = Bioc_domain.Policy_controlled_composition_request
module C = Bioc_domain.Policy_controlled_material_candidate
module M = Bioc_domain.Policy_mrna_structure
module P = Construction_producer
module W = Bioc_checker.Work_budget
let implementation_version = "biocompiler.ocaml.policy_controlled_material_producer.v0.1"
let construct_candidate ?charge ?limits (request:R.t) : C.t =
  let budget = W.create ~profile:R.resource_profile ~error_code:"controlled_material_producer_resource"
      ~maximum:(R.budgets request).max_work () in
  let spend amount =
    W.charge budget amount;
    Option.iter (fun callback -> callback amount) charge in
  spend 1;
  let authority = R.material request in
  let content = P.construct_template ~charge:spend ?limits
      ~member_order:(M.member_order authority) (M.template authority) in
  spend (128 + String.length C.schema_version + String.length (R.fingerprint request));
  let raw = Json.Object ["schema_version",Json.String C.schema_version;
    "request_fingerprint",Json.String (R.fingerprint request);
    "construction",P.content_json ~charge:spend content] in
  C.of_json ~charge:spend raw
