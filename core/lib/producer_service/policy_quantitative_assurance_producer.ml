open Bioc_wire
module R=Bioc_domain.Policy_quantitative_assurance_request
module M=Bioc_domain.Policy_component_material_request
module Material=Bioc_service.Policy_component_material_service
let compile payload=
  let payload=Material.unpack_payload ~assurance:true payload in
  let fields=Json.object_fields ~path:"/payload" payload in
  Json.exact_fields ~path:"/payload" ["request";"limits"] fields;
  let raw=Json.field "request" fields in
  let request=R.of_json raw in
  let material=M.of_json(R.material_request request) in
  let candidate=Policy_component_material_producer.construct_candidate material in
  let result=Bioc_service.Policy_quantitative_assurance_service.check ~export:false ~request:raw
    ~candidate ~limits:(Json.field "limits" fields)in
  if M.is_quantitative_composition material then Material.publish_result ~coupled:true result else result
