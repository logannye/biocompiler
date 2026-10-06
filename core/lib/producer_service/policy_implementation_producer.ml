open Bioc_wire
module R = Bioc_domain.Policy_realization_request
module O = Bioc_domain.Policy_operational
module I = Bioc_domain.Policy_implementation
module U = Bioc_domain.Policy_implementation_binding
module S = Bioc_service.Policy_implementation_service
let compile payload=
  let fields=Json.object_fields ~path:"/payload" payload in
  Json.exact_fields ~path:"/payload"["request";"limits"]fields;
  let raw_request=Json.field "request" fields in
  let request=R.of_json raw_request in
  let source=Bioc_checker.Policy_admission.admit ~document:(R.document request) ~descriptors:(R.definitions request)in
  let behavior=Bioc_compiler.Policy_lowering.lower source in
  let admitted=Bioc_checker.Policy_realization_admission.admit ~request ~behavior in
  let proposal=Bioc_compiler.Policy_implementation_lowering.lower ~admitted ~library:(R.implementation_library request)in
  let candidate=Json.Object["schema_version",Json.String S.candidate_schema;
    "behavior",O.behavior_to_json behavior;"implementation",I.to_json proposal.implementation;
    "binding",U.to_json proposal.binding]in
  S.check ~request:raw_request ~candidate ~limits:(Json.field "limits" fields)
