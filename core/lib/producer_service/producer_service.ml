open Bioc_wire
open Bioc_domain
module Producer = Bioc_compiler.Architecture_producer
module Checker = Bioc_checker.Architecture_check
module Base = Bioc_service.Service
module Assessment_service = Bioc_service.Architecture_service
let str value = Json.String value
let obj value = Json.Object value
let validation_scope = "supplied-architecture-production-v1"
let operations = ["compile-architecture"; "export-architecture"]
let profile = obj [
    "operations", Json.Array (List.map str operations);
    "request_schema", str Architecture_request.schema_version;
    "build_schema", str Architecture_build.schema_version;
    "export_schema", str Architecture_build.Export.schema_version;
    "assessment_schema", str Architecture_assessment.schema_version;
    "implementation", str Producer.implementation_version;
    "resource_profile", str Producer.resource_profile;
    "checker_implementation", str Checker.implementation_version;
    "checker_resource_profile", str Checker.resource_profile;
    "validation_scope", str validation_scope
  ]
let identity_fields schema raw_request request = [
    "schema_version", str schema;
    "implementation", str Producer.implementation_version;
    "resource_profile", str Producer.resource_profile;
    "validation_scope", str validation_scope;
    "supplied_request_fingerprint", str (Canonical.fingerprint raw_request);
    "request_fingerprint", str (Architecture_request.fingerprint request)
  ]
let compile payload =
  let fields = Json.object_fields payload in
  Json.exact_fields ["request"] fields;
  let raw_request = Json.field "request" fields in
  let request = Architecture_request.of_json ~path:"/payload/request" raw_request in
  let build, assessment = Producer.compile_checked request in
  let raw_build = Architecture_build.to_json build in
  let build_json = Canonical.encode raw_build in
  obj (identity_fields "biocompiler.core.architecture_build.v1" raw_request request @ [
      "build_fingerprint", str (Canonical.sha256 build_json);
      "build_json", str build_json;
      "verification", Assessment_service.wrap ~raw_request ~raw_build assessment
    ])
let export payload =
  let fields = Json.object_fields payload in
  Json.exact_fields ["expected_request"; "build"] fields;
  let raw_request = Json.field "expected_request" fields and raw_build = Json.field "build" fields in
  let request = Architecture_request.of_json ~path:"/payload/expected_request" raw_request
  and build = Architecture_build.of_json ~path:"/payload/build" raw_build in
  let artifact, assessment = Producer.export_checked ~expected_request:request build in
  let fasta = Architecture_build.Export.fasta artifact
  and manifest_json = Canonical.encode (Architecture_build.Export.manifest artifact) in
  obj (identity_fields "biocompiler.core.architecture_export.v1" raw_request request @ [
      "supplied_build_fingerprint", str (Canonical.fingerprint raw_build);
      "build_fingerprint", str (Architecture_build.fingerprint build);
      "export_fingerprint", str (Architecture_build.Export.fingerprint artifact);
      "fasta", str fasta;
      "fasta_sha256", str (Canonical.sha256 fasta);
      "manifest_json", str manifest_json;
      "manifest_sha256", str (Canonical.sha256 manifest_json);
      "verification", Assessment_service.wrap ~raw_request ~raw_build assessment
    ])
let capabilities executable request =
  let status, result, diagnostics = Base.handle executable request in
  match status, result, diagnostics with
  | Protocol.Ok, Some original, [] ->
      let changed = Json.object_fields original |> List.map (fun (key, value) -> key,
          match key with
          | "operations" -> Json.Array (Json.array value @ List.map str (operations @ ["compile-policy"; "compile-policy-implementation"; "compile-policy-material"; "compile-policy-component-material"] @ Synthetic_producer_service.operations @ Synthetic_producer_public_service.operations @ Synthetic_inspection_service.operations))
          | "validation_scopes" -> Json.Array (Json.array value @ List.map str (validation_scope :: Synthetic_producer_service.validation_scopes @ Synthetic_producer_public_service.validation_scopes @ Synthetic_inspection_service.validation_scopes))
          | "profiles" -> obj (Json.object_fields value @ ["architecture_producer", profile;
              "policy_operational_producer", Bioc_service.Policy_operational_service.producer_profile;
              "policy_implementation_producer", Bioc_service.Policy_implementation_service.producer_profile;
              "policy_material_producer", Bioc_service.Policy_material_service.producer_profile;
              "policy_component_material_producer", Bioc_service.Policy_component_material_service.producer_profile] @ Synthetic_producer_service.profiles @ Synthetic_producer_public_service.profiles @ Synthetic_inspection_service.profiles)
          | "claim_scope" -> str "Supplied-contract architecture production, independent checking, exact RNA/manifest export and separately scoped finite-history model checks. No search completeness, empirical function or human-use admission is established."
          | _ -> value) in
      Protocol.Ok, Some (obj changed), []
  | _ -> status, result, diagnostics
let handle executable (request : Protocol.request) =
  match executable, request.operation with
  | Protocol.Verify, _ -> Base.handle executable request
  | Protocol.Core, "capabilities" -> capabilities executable request
  | Protocol.Core, "compile-architecture" -> Protocol.Ok, Some (compile request.payload), []
  | Protocol.Core, "compile-policy" -> Protocol.Ok, Some (Policy_operational_producer.compile request.payload), []
  | Protocol.Core, "compile-policy-implementation" -> Protocol.Ok, Some (Policy_implementation_producer.compile request.payload), []
  | Protocol.Core, "compile-policy-material" -> Protocol.Ok, Some (Policy_material_producer.compile request.payload), []
  | Protocol.Core, "compile-policy-component-material" -> Protocol.Ok, Some (Policy_component_material_producer.compile request.payload), []
  | Protocol.Core, "export-architecture" -> Protocol.Ok, Some (export request.payload), []
  | Protocol.Core, operation when List.mem operation Synthetic_producer_service.operations ->
      Protocol.Ok, Some (Synthetic_producer_service.handle ~executable ~request_id:request.request_id
          ~operation request.payload), []
  | Protocol.Core, operation when List.mem operation Synthetic_producer_public_service.operations ->
      Protocol.Ok, Some (Synthetic_producer_public_service.handle ~executable ~request_id:request.request_id
          ~operation request.payload), []
  | Protocol.Core, operation when List.mem operation Synthetic_inspection_service.operations ->
      Protocol.Ok, Some (Synthetic_inspection_service.handle ~executable ~request_id:request.request_id
          ~operation request.payload), []
  | Protocol.Core, _ -> Base.handle executable request
