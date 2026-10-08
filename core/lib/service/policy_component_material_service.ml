open Bioc_wire
module R=Bioc_domain.Policy_component_material_request
module S=Bioc_domain.Policy_realization_request
module O=Bioc_domain.Policy_operational
module I=Bioc_domain.Policy_implementation
module U=Bioc_domain.Policy_implementation_binding
module C=Bioc_domain.Policy_component_assembly_proposal
module K=Bioc_domain.Construction_content
module P=Bioc_realization_checker.Policy_preservation_check
module Check=Bioc_realization_checker.Policy_component_material_check
module W=Bioc_checker.Work_budget
let str value=Json.String value
let obj fields=Json.Object fields
let arr values=Json.Array values
let get key value=Json.field key(Json.object_fields value)
let operations=["check-policy-component-material";"replay-policy-component-material";"export-policy-component-material"]
let validation_scope="policy-component-mrna-v0.1"
let implementation="biocompiler.ocaml.policy_component_material.v0.1"
let instance_implementation="biocompiler.ocaml.policy_instance_component_material.v0.1"
let instance_validation_scope="policy-instance-component-mrna-v0.1"
let prerequisite_implementation="biocompiler.ocaml.policy_instance_prerequisite_material.v0.1"
let prerequisite_validation_scope="policy-instance-prerequisite-mrna-v0.1"
let two_observation_implementation="biocompiler.ocaml.policy_instance_two_observation_prerequisite_material.v0.1"
let two_observation_validation_scope="policy-instance-two-observation-prerequisite-mrna-v0.1"
let multi_member_implementation="biocompiler.ocaml.policy_multi_member_prerequisite_material.v0.1"
let multi_member_validation_scope="policy-multi-member-prerequisite-mrna-v0.1"
let schema_version="biocompiler.core.policy_component_material.v1"
let resource_profile=R.resource_profile
let candidate_schema="biocompiler.policy_component_material_candidate.v0.1"
let max_result_bytes=Limits.max_response_bytes-6*Limits.max_string_bytes-65536
let max_result_nodes=Limits.max_json_nodes-32
let profile=obj["operations",arr(List.map str operations);"request_schema",str R.schema_version;
  "candidate_schema",str candidate_schema;"schema_version",str schema_version;
  "implementation",str implementation;"resource_profile",str resource_profile;
  "validation_scope",str validation_scope;"max_result_bytes",Json.int max_result_bytes;
  "max_result_nodes",Json.int max_result_nodes;
  "artifact",str "on_fresh_export_only";"empirical",str "unassessed"]
let producer_profile=obj["operations",arr[str "compile-policy-component-material"];
  "implementation",str implementation;"validation_scope",str validation_scope]
let instance_profile=obj (List.map (fun (key,value) -> key,match key with
  | "request_schema" -> str R.instance_schema_version
  | "implementation" -> str instance_implementation
  | "validation_scope" -> str instance_validation_scope
  | _ -> value) (Json.object_fields profile))
let instance_producer_profile=obj["operations",arr[str "compile-policy-component-material"];
  "implementation",str instance_implementation;"validation_scope",str instance_validation_scope]
let prerequisite_profile=obj (List.map (fun (key,value) -> key,match key with
  | "request_schema" -> str R.prerequisite_schema_version
  | "implementation" -> str prerequisite_implementation
  | "validation_scope" -> str prerequisite_validation_scope
  | _ -> value) (Json.object_fields profile))
let prerequisite_producer_profile=obj["operations",arr[str "compile-policy-component-material"];
  "implementation",str prerequisite_implementation;"validation_scope",str prerequisite_validation_scope]
let two_observation_profile=obj (List.map (fun (key,value) -> key,match key with
  | "request_schema" -> str R.two_observation_schema_version
  | "implementation" -> str two_observation_implementation
  | "validation_scope" -> str two_observation_validation_scope
  | _ -> value) (Json.object_fields profile))
let two_observation_producer_profile=obj["operations",arr[str "compile-policy-component-material"];
  "implementation",str two_observation_implementation;"validation_scope",str two_observation_validation_scope]
let multi_member_profile=obj (List.map (fun (key,value) -> key,match key with
  | "request_schema" -> str R.multi_member_schema_version
  | "implementation" -> str multi_member_implementation
  | "validation_scope" -> str multi_member_validation_scope
  | _ -> value) (Json.object_fields profile))
let multi_member_producer_profile=obj["operations",arr[str "compile-policy-component-material"];
  "implementation",str multi_member_implementation;"validation_scope",str multi_member_validation_scope]
let validate_publication raw=
  let framed=obj["result",raw]in
  let output=W.create_output ~profile:validation_scope ~error_code:"policy_component_material_service_publication_limit"
    ~max_bytes:max_result_bytes ~max_nodes:max_result_nodes ()in
  W.reserve_json output framed;
  let encoded=Canonical.encode_bounded ~max_bytes:max_result_bytes framed in
  ignore(Json.parse_artifact ~max_bytes:max_result_bytes ~max_nodes:max_result_nodes encoded)
let export_artifact checked candidate limits=
  let request=Check.request checked and report=Check.evidence checked in
  Diagnostic.require(candidate_schema=Check.candidate_schema &&
    Canonical.fingerprint candidate=Json.string(get "candidate_fingerprint" report) &&
    Json.equal limits(get "limits" report))"policy_component_material_export_identity"
    "Export inputs differ from the freshly checked complete candidate and invocation limits.";
  let rendered=Policy_component_material_format.render checked in
  let members=rendered.members and fasta=rendered.fasta and fasta_sha=rendered.fasta_sha256 in
  let manifest=obj["schema_version",str "biocompiler.policy_component_mrna_manifest.v0.1";
    "profile",str (R.request_profile request);"claim_scope",str "bounded_conditional_policy_via_reusable_components_to_exact_mrna";
    "premise",str "supplied_component_composition_and_provider_contracts";
    "request",R.to_json request;"candidate",candidate;"limits",limits;"assessment",report;
    "bindings",obj["request_fingerprint",str(R.fingerprint request);
      "candidate_fingerprint",get "candidate_fingerprint" report;
      "invocation_fingerprint",get "invocation_fingerprint" report;
      "assessment_fingerprint",str(Canonical.fingerprint report)];
    "members",arr members;"fasta_sha256",str fasta_sha;
    "empirical",str "unassessed";"original_authority",str "retain_original_inputs_separately"]in
  (* Hash the exact canonical bytes published as manifest.json. No self-hash is
     embedded; the enclosing export binds the complete manifest and FASTA pair. *)
  let output=W.create_output ~profile:validation_scope ~error_code:"policy_component_material_service_publication_limit"
    ~max_bytes:max_result_bytes ~max_nodes:max_result_nodes ()in
  W.reserve_json output manifest;
  let manifest_bytes=Canonical.encode_bounded ~max_bytes:max_result_bytes manifest in
  obj["schema_version",str "biocompiler.policy_component_mrna_export.v0.1";
    "fasta",str fasta;"fasta_sha256",str fasta_sha;
    "manifest",manifest;"manifest_sha256",str(Canonical.sha256 manifest_bytes)]
let check ~export ~request:raw_request ~candidate:raw_candidate ~limits:raw_limits=
  let request=R.of_json raw_request in
  let fields=Json.object_fields ~path:"/payload/candidate" raw_candidate in
  Json.exact_fields ~path:"/payload/candidate"
    ["schema_version";"behavior";"implementation";"binding";"assembly_proposal";"construction"]fields;
  Diagnostic.require(Json.field "schema_version" fields=str candidate_schema)
    "policy_component_material_candidate""Unknown complete material candidate schema.";
  let behavior=O.behavior_of_json(Json.field "behavior" fields)
  and actual=I.of_json ~library:(S.implementation_library(R.implementation_request request))(Json.field "implementation" fields)
  and proposed=U.of_json(Json.field "binding" fields)
  and assembly_proposal=C.of_json(Json.field "assembly_proposal" fields)
  and candidate=K.of_json(Json.field "construction" fields)
  and limits=P.limits_of_json raw_limits in
  let checked=Check.check ~request ~behavior ~implementation:actual ~proposed ~assembly_proposal ~candidate ~limits in
  let report=Check.report checked in
  let artifact=if not export then Json.Null else match Check.accepted checked with
    |Some checked->export_artifact checked raw_candidate raw_limits
    |None->Diagnostic.fail "policy_component_material_export_not_accepted"
      "Fresh original-source, implementation, material, context or obligation checking withheld accepted export."in
  let result=obj["schema_version",str schema_version;
    "implementation",str (if R.is_multi_member request then multi_member_implementation
      else if R.is_two_observation request then two_observation_implementation
      else if R.requires_prerequisite_closure request then prerequisite_implementation
      else if R.is_instanced request then instance_implementation else implementation);
    "resource_profile",str resource_profile;
    "validation_scope",str (if R.is_multi_member request then multi_member_validation_scope
      else if R.is_two_observation request then two_observation_validation_scope
      else if R.requires_prerequisite_closure request then prerequisite_validation_scope
      else if R.is_instanced request then instance_validation_scope else validation_scope);
    "request_fingerprint",str(R.fingerprint request);"candidate_fingerprint",str(Canonical.fingerprint raw_candidate);
    "invocation_fingerprint",str(Canonical.fingerprint(obj["request",raw_request;"candidate",raw_candidate;"limits",raw_limits]));
    "report_fingerprint",str(Canonical.fingerprint report);"candidate",raw_candidate;"report",report;"artifact",artifact]in
  validate_publication result;result
let handle ~operation payload=
  Diagnostic.require(List.mem operation operations)"unsupported_operation""Material service only checks, replays or freshly exports supplied candidates.";
  let replay=operation="replay-policy-component-material"in
  let fields=Json.object_fields ~path:"/payload" payload in
  Json.exact_fields ~path:"/payload"(["request";"candidate";"limits"]@(if replay then["report"]else[]))fields;
  let result=check ~export:(operation="export-policy-component-material") ~request:(Json.field "request" fields)
    ~candidate:(Json.field "candidate" fields) ~limits:(Json.field "limits" fields)in
  if replay then Diagnostic.require(Json.equal result(Json.field "report" fields))
    "policy_component_material_replay""Saved full material wrapper differs from complete fresh checking.";
  result
