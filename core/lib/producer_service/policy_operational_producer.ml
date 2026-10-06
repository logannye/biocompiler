open Bioc_wire
module Document = Bioc_domain.Policy_document
module O = Bioc_domain.Policy_operational
module Service = Bioc_service.Policy_operational_service

let compile payload =
  let fields = Json.object_fields ~path:"/payload" payload in
  Json.exact_fields ~path:"/payload" ["document"; "definitions"] fields;
  let document = Document.of_json ~path:"/document" (Json.field "document" fields) in
  let definitions = O.descriptors_of_json (Json.field "definitions" fields) in
  let admitted = Bioc_checker.Policy_admission.admit ~document ~descriptors:definitions in
  let candidate = Bioc_compiler.Policy_lowering.lower admitted in
  let correspondence = Bioc_checker.Policy_correspondence.check
      ~expected_document:document ~descriptors:definitions candidate in
  let report = Service.lowering_report ~document ~correspondence in
  Service.wrap ~payload ~candidate:(O.behavior_to_json candidate) ~report
