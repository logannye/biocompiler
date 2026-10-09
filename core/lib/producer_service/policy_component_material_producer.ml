open Bioc_wire
module R = Bioc_domain.Policy_component_material_request
module S = Bioc_domain.Policy_realization_request
module O = Bioc_domain.Policy_operational
module I = Bioc_domain.Policy_implementation
module U = Bioc_domain.Policy_implementation_binding
module A = Bioc_domain.Policy_component_assembly_rule
module Q = Bioc_domain.Policy_component_assembly_proposal
module PM = Bioc_domain.Policy_mrna_structure
module Service = Bioc_service.Policy_component_material_service
module Input = Bioc_domain.Policy_material_request
let construct_candidate ?charge request =
  let metered=Option.is_some charge in
  let charge=Option.value charge ~default:Bioc_checker.Policy_generation_meter.no_charge in
  charge 1;
  let original = R.implementation_request request in
  let source = Bioc_checker.Policy_admission.admit_metered ~charge
    ~document:(S.document original) ~descriptors:(S.definitions original) in
  let behavior = Bioc_compiler.Policy_lowering.lower ~charge source in
  let admitted = Bioc_checker.Policy_realization_admission.admit_metered ~charge ~request:original ~behavior in
  let library = S.implementation_library original in
  let lowered = Bioc_compiler.Policy_implementation_lowering.lower_metered ~charge ~admitted ~library in
  let rule = R.composition_rule request in
  let source_inputs = if R.is_network request || R.is_finite_machine request || R.is_two_observation request || R.is_multi_member request then Some (List.map (fun (value:R.input_binding) ->
      charge (1+String.length value.source+String.length value.input_id); value.source,value.input_id)
      (R.input_bindings request)) else None in
  let arranged = Bioc_compiler.Policy_component_lowering.arrange ~charge ?source_inputs ~library ~rule lowered in
  let authority = A.material_authority rule in
  let content = Bioc_compiler.Construction_producer.construct_template ~charge
    ~member_order:(PM.member_order authority) (PM.template authority) in
  (* Cached behavioral/graph JSON is immutable; assembly serialization allocates
     one record per binding and must be paid before that pass. *)
  List.iter (fun (row:Q.node_binding) ->
    charge (16 + String.length row.node_id + String.length row.actual_id)) (Q.nodes arranged.assembly);
  charge 256;
  let candidate = Json.Object ["schema_version",Json.String Service.candidate_schema;
    "behavior",O.behavior_to_json behavior;"implementation",I.to_json arranged.implementation;
    "binding",U.to_json arranged.binding;"assembly_proposal",Q.to_json arranged.assembly;
    "construction",Bioc_compiler.Construction_producer.content_json ~charge content] in
  if metered then (
    let bytes=Input.preflight ~max_bytes:8388608 ~max_nodes:250000 ~max_depth:128 ~charge candidate in
    charge bytes;
    ignore (Canonical.encode_bounded ~max_bytes:8388608 candidate));
  candidate

let compile payload =
  let payload = Service.unpack_payload ~assurance:false payload in
  let fields = Json.object_fields ~path:"/payload" payload in
  Json.exact_fields ~path:"/payload" ["request";"limits"] fields;
  let raw = Json.field "request" fields in
  let request = R.of_json raw in
  let candidate = construct_candidate request in
  let result=Service.check ~export:false ~request:raw ~candidate ~limits:(Json.field "limits" fields)in
  if R.is_quantitative_composition request then Service.publish_result ~coupled:true result else result
