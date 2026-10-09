open Bioc_wire
module R = Bioc_domain.Policy_quantitative_assurance_request
module Input = Bioc_domain.Policy_material_request
module Material = Policy_component_material_service
module M = Bioc_realization_checker.Policy_component_material_check
module Exact = Bioc_realization_checker.Policy_refinement_check
module Approx = Bioc_realization_checker.Policy_approximation_check
module Evidence = Bioc_realization_checker.Policy_realization_evidence_check
module W = Bioc_checker.Work_budget
let str value=Json.String value
let obj fields=Json.Object fields
let get key value=Json.field key(Json.object_fields value)
let schema_version="biocompiler.core.policy_quantitative_assurance.v1"
let implementation="biocompiler.ocaml.policy_quantitative_assurance.v0.1"
let validation_scope="policy-quantitative-assurance-v0.1"
let operations=["check-policy-quantitative-assurance";"replay-policy-quantitative-assurance";
  "export-policy-quantitative-assurance"]
let make_profile operations=obj["operations",Json.Array(List.map str operations);
  "schema_version",str schema_version;"request_schema",str R.schema_version;
  "implementation",str implementation;"validation_scope",str validation_scope;
  "max_result_bytes",Json.int Material.max_result_bytes;"max_result_nodes",Json.int Material.max_result_nodes;
  "artifact",str "fresh_exact_mrna_with_separate_assurance";"empirical",str "unassessed"]
let profile=make_profile operations
let producer_profile=make_profile ["compile-policy-quantitative-assurance"]
let budget maximum=W.create ~profile:validation_scope ~error_code:"policy_quantitative_assurance_work_limit" ~maximum ()
let preflight work raw=Input.preflight ~max_bytes:Material.max_result_bytes
  ~max_nodes:Material.max_result_nodes ~max_depth:128 ~charge:(W.charge work) raw
let hash work raw=
  let size=preflight work raw in
  W.charge work size;
  let bytes=Canonical.encode_bounded ~max_bytes:Material.max_result_bytes raw in
  Diagnostic.require(String.length bytes=size)"policy_quantitative_assurance_accounting"
    "Assurance preflight differs from the exact canonical bytes.";
  W.charge work size;Canonical.sha256 bytes
let check ~export ~request:raw ~candidate ~limits=
  (* A fixed bounded preflight precedes decoding. The caller's lower allowance
     is then charged for the complete decoding input before any child checks. *)
  let decoding=budget R.maximum_work in
  let before=W.remaining decoding in
  let request=R.of_json ~charge:(W.charge decoding) raw in
  let work=budget(R.max_work request) in
  W.charge work (before-W.remaining decoding);
  let invocation=obj["request",raw;"candidate",candidate;"limits",limits] in
  ignore(preflight work invocation);
  let _,material_result=Material.fresh_check ~request:(R.material_request request) ~candidate ~limits in
  let material_report=M.report material_result in
  let checked=M.accepted material_result in
  let exact,approximation,evidence,allowed=match checked with
    | None->Json.Null,Json.Null,Json.Null,false
    | Some material->
      let exact=Exact.to_json(Exact.of_material material) in
      let approximation,approximate=match R.approximation request with
        | None->Json.Null,true
        | Some contract->let result=Approx.check ~parent:work ~material ~contract () in
          Approx.report result,Option.is_some(Approx.accepted result) in
      let evidence,compatible=match R.realization_evidence request with
        | None->Json.Null,true
        | Some contract->let result=Evidence.check ~parent:work ~material ~contract () in
          Evidence.report result,Evidence.export_permitted result in
      exact,approximation,evidence,approximate && compatible in
  let request_pin=hash work raw and candidate_pin=hash work candidate
  and invocation_pin=hash work invocation in
  let report=obj["schema_version",str "biocompiler.policy_quantitative_assurance_assessment.v0.1";
    "request_fingerprint",str request_pin;"candidate_fingerprint",str candidate_pin;
    "invocation_fingerprint",str invocation_pin;"material",material_report;
    "exact_refinement",exact;"approximation",approximation;"realization_evidence",evidence;
    "export_permitted",Json.Bool allowed;"empirical_function",str "unassessed"] in
  let report_pin=hash work report in
  let artifact=if not export then Json.Null else (
    Diagnostic.require allowed "policy_quantitative_assurance_export_not_accepted"
      "Fresh material or requested approximation/evidence acceptance withheld export.";
    let material=match checked with Some value->value|None->assert false in
    let original=Material.export_artifact material candidate limits in
    let manifest=obj["schema_version",str "biocompiler.policy_quantitative_assurance_manifest.v0.1";
      "request",raw;"limits",limits;"assessment",report;"assessment_fingerprint",str report_pin;
      "material_manifest",get "manifest" original;"material_manifest_sha256",get "manifest_sha256" original;
      "fasta_sha256",get "fasta_sha256" original;
      "claim_scope",str "exact_material_and_scoped_mathematical_assurance_with_separate_supplied_evidence";
      "empirical_function",str "unassessed";"original_authority",str "retain_original_inputs_separately"] in
    let manifest_pin=hash work manifest in
    obj["schema_version",str "biocompiler.policy_quantitative_assurance_export.v0.1";
      "fasta",get "fasta" original;"fasta_sha256",get "fasta_sha256" original;
      "manifest",manifest;"manifest_sha256",str manifest_pin]) in
  let result=obj["schema_version",str schema_version;"implementation",str implementation;
    "validation_scope",str validation_scope;"request_fingerprint",str request_pin;
    "candidate_fingerprint",str candidate_pin;"invocation_fingerprint",str invocation_pin;
    "report_fingerprint",str report_pin;"candidate",candidate;"report",report;"artifact",artifact] in
  ignore(preflight work result);
  Diagnostic.require(not(W.exhausted work))"policy_quantitative_assurance_work_limit"
    "Assurance work was exhausted before publication.";
  Material.validate_publication result;result
let handle ~operation payload=
  Diagnostic.require(List.mem operation operations)"unsupported_operation"
    "Quantitative assurance verifier cannot produce a candidate.";
  let replay=operation="replay-policy-quantitative-assurance" in
  let fields=Json.object_fields ~path:"/payload" payload in
  Json.exact_fields ~path:"/payload" (["request";"candidate";"limits"]@(if replay then ["report"] else [])) fields;
  let result=check ~export:(operation="export-policy-quantitative-assurance")
    ~request:(Json.field "request" fields) ~candidate:(Json.field "candidate" fields) ~limits:(Json.field "limits" fields) in
  if replay then Diagnostic.require(Json.equal result(Json.field "report" fields))
    "policy_quantitative_assurance_replay" "Saved assurance differs from complete fresh original-authority checking.";
  result
