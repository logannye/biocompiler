open Bioc_wire
module R=Bioc_domain.Policy_component_material_request
module S=Bioc_domain.Policy_realization_request
module O=Bioc_domain.Policy_operational
module I=Bioc_domain.Policy_implementation
module U=Bioc_domain.Policy_implementation_binding
module C=Bioc_domain.Policy_component_assembly_proposal
module K=Bioc_domain.Construction_content
module N=Bioc_domain.Molecule
module P=Bioc_realization_checker.Policy_preservation_check
module Check=Bioc_realization_checker.Policy_component_material_check
module X=Bioc_realization_checker.Policy_component_context_check
module L=Bioc_realization_checker.Policy_component_assembly_check
module Structure=Bioc_checker.Policy_mrna_structure_check
module W=Bioc_checker.Work_budget
let str value=Json.String value
let obj fields=Json.Object fields
let arr values=Json.Array values
let get key value=Json.field key(Json.object_fields value)
let operations=["check-policy-component-material";"replay-policy-component-material";"export-policy-component-material"]
let validation_scope="policy-component-mrna-v0.1"
let implementation="biocompiler.ocaml.policy_component_material.v0.1"
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
  let structure=L.structure(X.assembly(Check.context checked))in
  let content=Structure.content structure in
  let molecules=match K.inventory content with
    |Some value->K.Inventory.molecules value
    |None->Diagnostic.fail "policy_component_material_export_incomplete" "Checked material has no exact molecular inventory."in
  Diagnostic.require(List.map N.id molecules=K.member_order content && molecules<>[])
    "policy_component_material_export_incomplete""Exact delivered member order is absent from checked material.";
  let fasta=Buffer.create 1024 in
  let members=List.mapi(fun index molecule->
    let id=Printf.sprintf "rna_%04d"(index+1)in
    Buffer.add_string fasta(">"^id^" alphabet=RNA\n");
    let sequence=N.sequence molecule in
    let rec lines offset=if offset<String.length sequence then(
      let count=min 80(String.length sequence-offset)in
      Buffer.add_substring fasta sequence offset count;Buffer.add_char fasta '\n';lines(offset+count))in
    lines 0;
    obj["fasta_id",str id;"member_id",str(N.id molecule);"molecule",N.to_json molecule;
      "sequence_sha256",str(Canonical.sha256 sequence)])molecules in
  let fasta=Buffer.contents fasta in
  let fasta_sha=Canonical.sha256 fasta in
  let manifest=obj["schema_version",str "biocompiler.policy_component_mrna_manifest.v0.1";
    "profile",str R.profile;"claim_scope",str "bounded_conditional_policy_via_reusable_components_to_exact_mrna";
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
  let result=obj["schema_version",str schema_version;"implementation",str implementation;
    "resource_profile",str resource_profile;"validation_scope",str validation_scope;
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
