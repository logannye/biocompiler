open Bioc_wire
module R=Bioc_domain.Policy_quantitative_assurance_request
module M=Bioc_domain.Policy_component_material_request
let compile payload=
  let fields=Json.object_fields ~path:"/payload" payload in
  Json.exact_fields ~path:"/payload" ["request";"limits"] fields;
  let raw=Json.field "request" fields in
  let request=R.of_json raw in
  let material=M.of_json(R.material_request request) in
  let candidate=Policy_component_material_producer.construct_candidate material in
  Bioc_service.Policy_quantitative_assurance_service.check ~export:false ~request:raw
    ~candidate ~limits:(Json.field "limits" fields)
