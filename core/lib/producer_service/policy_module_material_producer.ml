open Bioc_wire
module Service = Bioc_service.Policy_module_linking_service
module Link = Bioc_checker.Policy_module_linking_check
module Request = Bioc_domain.Policy_component_material_request
let compile payload=
  Service.validate_input payload;
  let fields=Json.object_fields ~path:"/payload" payload in
  Json.exact_fields ~path:"/payload" ["modules";"request";"limits"]fields;
  let modules=Json.field "modules" fields and request=Json.field "request" fields
  and limits=Json.field "limits" fields in
  let linked=Service.check_linkage ~modules ~request in
  let candidate=try Policy_component_material_producer.construct_candidate(Request.of_json request)with
    |Diagnostic.Error diagnostic->raise(Diagnostic.Error(Link.remap_diagnostic linked diagnostic))in
  Service.check ~export:false ~modules ~request ~candidate ~limits
