open Bioc_wire
module R = Bioc_domain.Policy_component_material_request
module S = Bioc_domain.Policy_realization_request
module O = Bioc_domain.Policy_operational
module I = Bioc_domain.Policy_implementation
module U = Bioc_domain.Policy_implementation_binding
module A = Bioc_domain.Policy_component_assembly_rule
module Q = Bioc_domain.Policy_component_assembly_proposal
module PM = Bioc_domain.Policy_mrna_structure
module K = Bioc_domain.Construction_content
module Service = Bioc_service.Policy_component_material_service
let compile payload =
  let fields = Json.object_fields ~path:"/payload" payload in
  Json.exact_fields ~path:"/payload" ["request";"limits"] fields;
  let raw = Json.field "request" fields in
  let request = R.of_json raw in
  let original = R.implementation_request request in
  let source = Bioc_checker.Policy_admission.admit
    ~document:(S.document original) ~descriptors:(S.definitions original) in
  let behavior = Bioc_compiler.Policy_lowering.lower source in
  let admitted = Bioc_checker.Policy_realization_admission.admit ~request:original ~behavior in
  let library = S.implementation_library original in
  let lowered = Bioc_compiler.Policy_implementation_lowering.lower ~admitted ~library in
  let rule = R.composition_rule request in
  let arranged = Bioc_compiler.Policy_component_lowering.arrange ~library ~rule lowered in
  let authority = A.material_authority rule in
  let content = Bioc_compiler.Construction_producer.construct_template
    ~member_order:(PM.member_order authority) (PM.template authority) in
  let candidate = Json.Object ["schema_version",Json.String Service.candidate_schema;
    "behavior",O.behavior_to_json behavior;"implementation",I.to_json arranged.implementation;
    "binding",U.to_json arranged.binding;"assembly_proposal",Q.to_json arranged.assembly;
    "construction",K.to_json content] in
  Service.check ~export:false ~request:raw ~candidate ~limits:(Json.field "limits" fields)
