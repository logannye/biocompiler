open Bioc_wire
module R = Bioc_domain.Policy_expression_material
module A = Bioc_domain.Policy_mrna_structure
module Producer = Bioc_compiler.Construction_producer
module Service = Bioc_service.Policy_expression_material_service
module W = Bioc_checker.Work_budget
let compile payload =
  let fields = Json.object_fields ~path:"/payload" payload in
  Json.exact_fields ~path:"/payload" ["request"] fields;
  let raw = Json.field "request" fields in
  let request = R.of_json raw in
  let budget = W.create ~profile:R.resource_profile ~error_code:"policy_expression_producer_work_limit"
    ~maximum:(R.budgets request).max_work () in
  W.charge budget (R.decoding_work request);
  ignore (Bioc_checker.Policy_expression_source_admission.admit ~charge:(W.charge budget) request);
  let authority = R.structure_authority request in
  (* An untrusted proposal: independent service checking below starts afresh
     from the original source and reconstructs all original material roots. *)
  let content = Producer.construct_template ~parent:budget
    ~member_order:(A.member_order authority) (A.template authority) in
  let candidate = Json.Object ["schema_version",Json.String Service.candidate_schema;
    "construction",Producer.content_json ~charge:(W.charge budget) content] in
  Service.check ~export:false ~request:raw ~candidate
