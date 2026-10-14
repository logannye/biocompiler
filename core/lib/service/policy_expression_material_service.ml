open Bioc_wire
module R=Bioc_domain.Policy_expression_material
module K=Bioc_domain.Construction_content
module N=Bioc_domain.Molecule
module Check=Bioc_checker.Policy_expression_material_check
module Structure=Bioc_checker.Policy_expression_structure_check
module W=Bioc_checker.Work_budget
let str value=Json.String value
let obj fields=Json.Object fields
let arr values=Json.Array values
let get key value=Json.field key(Json.object_fields value)
let operations=["check-policy-expression-material";"replay-policy-expression-material";"export-policy-expression-material"]
let validation_scope="policy-single-expression-mrna-v0.1"
let implementation="biocompiler.ocaml.policy_expression_material.v0.2"
let schema_version="biocompiler.core.policy_expression_material.v1"
let resource_profile=R.resource_profile
let candidate_schema="biocompiler.policy_expression_material_candidate.v0.1"
let max_result_bytes=Limits.max_response_bytes-6*Limits.max_string_bytes-65536
let max_result_nodes=Limits.max_json_nodes-32
let profile=obj["operations",arr(List.map str operations);"request_schema",str R.schema_version;
  "candidate_schema",str candidate_schema;"schema_version",str schema_version;
  "implementation",str implementation;"resource_profile",str resource_profile;
  "validation_scope",str validation_scope;"max_result_bytes",Json.int max_result_bytes;
  "max_result_nodes",Json.int max_result_nodes;
  "artifact",str "on_fresh_export_only";"empirical",str "unassessed"]
let producer_profile=obj["operations",arr[str "compile-policy-expression-material"];
  "implementation",str implementation;"validation_scope",str validation_scope]
let measure budget raw=Bioc_domain.Policy_material_request.preflight
  ~max_bytes:max_result_bytes ~max_nodes:max_result_nodes ~max_depth:64 ~charge:(W.charge budget) raw
let fingerprint budget raw=
  let bytes=measure budget raw in W.charge budget bytes;
  let encoded=Canonical.encode_bounded ~max_bytes:max_result_bytes raw in
  Diagnostic.require(String.length encoded=bytes) "policy_expression_accounting" "Service canonical byte accounting changed.";
  W.charge budget bytes;Canonical.sha256 encoded
let validate_publication raw=
  let framed=obj["result",raw]in
  let output=W.create_output ~profile:validation_scope ~error_code:"policy_expression_service_publication_limit"
    ~max_bytes:max_result_bytes ~max_nodes:max_result_nodes ()in
  W.reserve_json output framed;
  let encoded=Canonical.encode_bounded ~max_bytes:max_result_bytes framed in
  ignore(Json.parse_artifact ~max_bytes:max_result_bytes ~max_nodes:max_result_nodes encoded)
let export_artifact budget ~report_fingerprint checked candidate=
  let request=Check.request checked and report=Check.evidence checked in
  Diagnostic.require(candidate_schema=Check.candidate_schema &&
    fingerprint budget candidate=Json.string(get "candidate_fingerprint" report))"policy_expression_export_identity"
    "Export inputs differ from the freshly checked complete candidate and original invocation.";
  let structure=Check.structure checked in
  let content=Structure.content structure in
  let molecules=match K.inventory content with
    |Some value->K.Inventory.molecules value
    |None->Diagnostic.fail "policy_expression_export_incomplete" "Checked material has no exact molecular inventory."in
  Diagnostic.require(List.map N.id molecules=K.member_order content && molecules<>[])
    "policy_expression_export_incomplete""Exact delivered member order is absent from checked material.";
  let expected_fasta_bytes=List.fold_left(fun total molecule->
    let length=String.length(N.sequence molecule)in
    total+String.length ">rna_0001 alphabet=RNA\n"+length+(length+79)/80)0 molecules in
  W.charge budget(expected_fasta_bytes+List.length molecules);
  let fasta=Buffer.create expected_fasta_bytes in
  let members=List.mapi(fun index molecule->
    let id=Printf.sprintf "rna_%04d"(index+1)in
    Buffer.add_string fasta(">"^id^" alphabet=RNA\n");
    let sequence=N.sequence molecule in
    let rec lines offset=if offset<String.length sequence then(
      let count=min 80(String.length sequence-offset)in
      Buffer.add_substring fasta sequence offset count;Buffer.add_char fasta '\n';lines(offset+count))in
    lines 0;
    obj["fasta_id",str id;"member_id",str(N.id molecule);"molecule",N.to_json molecule;
      "sequence_sha256",str(W.charge budget(String.length sequence);Canonical.sha256 sequence)])molecules in
  let fasta=Buffer.contents fasta in
  W.charge budget(String.length fasta);
  let fasta_sha=Canonical.sha256 fasta in
  let manifest=obj["schema_version",str "biocompiler.policy_expression_mrna_manifest.v0.1";
    "profile",str R.profile;"claim_scope",str "conditional_encoding_and_localization";
    "premise",str "supplied_expression_localization_recipient_and_nominal_translation_contracts";
    "request",R.to_json request;"candidate",candidate;"assessment",report;
    "bindings",obj["request_fingerprint",str(R.fingerprint request);
      "candidate_fingerprint",get "candidate_fingerprint" report;
      "invocation_fingerprint",get "invocation_fingerprint" report;
      "assessment_fingerprint",str report_fingerprint];
    "members",arr members;"fasta_sha256",str fasta_sha;
    "empirical",str "unassessed";"human_use",str "unassessed";"original_authority",str "retain_original_inputs_separately"]in
  (* Hash the exact canonical bytes published as manifest.json. No self-hash is
     embedded; the enclosing export binds the complete manifest and FASTA pair. *)
  let output=W.create_output ~profile:validation_scope ~error_code:"policy_expression_service_publication_limit"
    ~max_bytes:max_result_bytes ~max_nodes:max_result_nodes ()in
  let manifest_size=measure budget manifest in
  W.charge budget manifest_size;W.reserve_json output manifest;
  W.charge budget manifest_size;
  let manifest_bytes=Canonical.encode_bounded ~max_bytes:max_result_bytes manifest in
  W.charge budget manifest_size;
  obj["schema_version",str "biocompiler.policy_expression_mrna_export.v0.1";
    "fasta",str fasta;"fasta_sha256",str fasta_sha;
    "manifest",manifest;"manifest_sha256",str(Canonical.sha256 manifest_bytes)]
let check ~export ~request:raw_request ~candidate:raw_candidate=
  let request=R.of_json raw_request in
  let fields=Json.object_fields ~path:"/payload/candidate" raw_candidate in
  Json.exact_fields ~path:"/payload/candidate" ["schema_version";"construction"] fields;
  Diagnostic.require(Json.field "schema_version" fields=str candidate_schema)
    "policy_expression_candidate" "Unknown complete expression material candidate schema.";
  let candidate=K.of_json(Json.field "construction" fields)in
  let checked=Check.check ~request ~candidate in
  let report=Check.report checked in
  let budget=Check.budget checked in
  let report_fingerprint=fingerprint budget report in
  let artifact=if not export then Json.Null else match Check.accepted checked with
    |Some checked->export_artifact budget ~report_fingerprint checked raw_candidate
    |None->Diagnostic.fail "policy_expression_export_not_accepted"
      "Fresh source, conditional contract, length or exact material checking withheld export."in
  let fields=["schema_version",str schema_version;"implementation",str implementation;
    "resource_profile",str resource_profile;"validation_scope",str validation_scope;
    "request_fingerprint",str(R.fingerprint request);"candidate_fingerprint",get "candidate_fingerprint" report;
    "invocation_fingerprint",get "invocation_fingerprint" report;
    "report_fingerprint",str report_fingerprint;"candidate",raw_candidate;"report",report;"artifact",artifact]in
  let maximum=(R.budgets request).max_work in
  let usage total=obj["unit",str "logical_data_visits_and_child_semantic_work";
    "total_charged_work",Json.int total;"checker_charged_work",get "charged_work"(get "usage" report)]in
  let reserved=obj(fields@["usage",usage maximum])in
  let publication_bytes=measure budget(obj["result",reserved])in
  (* Reserve serialization, parser readback and final framed protocol encoding
     before any of those passes. The upper-bound counter has at least as many
     digits as the final value; fields and nodes remain identical. *)
  W.charge budget(3*publication_bytes);
  validate_publication reserved;
  obj(fields@["usage",usage(maximum-W.remaining budget)])
let handle ~operation payload=
  Diagnostic.require(List.mem operation operations)"unsupported_operation"
    "Expression service only checks, replays or freshly exports supplied candidates.";
  let replay=operation="replay-policy-expression-material"in
  let fields=Json.object_fields ~path:"/payload" payload in
  Json.exact_fields ~path:"/payload"(["request";"candidate"]@(if replay then["report"]else[]))fields;
  let result=check ~export:(operation="export-policy-expression-material") ~request:(Json.field "request" fields)
    ~candidate:(Json.field "candidate" fields)in
  if replay then Diagnostic.require(Json.equal result(Json.field "report" fields))
    "policy_expression_replay""Saved full wrapper differs from complete fresh expression checking.";
  result
