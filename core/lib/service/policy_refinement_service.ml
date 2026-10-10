open Bioc_wire
module Material = Policy_component_material_service
module Check = Bioc_realization_checker.Policy_component_material_check
module Evidence = Bioc_realization_checker.Policy_refinement_check
module W = Bioc_checker.Work_budget
module Input = Bioc_domain.Policy_material_request
module Wire = Bioc_domain.Policy_coupled_wire
let str value=Json.String value
let obj fields=Json.Object fields
let get key value=Json.field key(Json.object_fields value)
let operations=["check-policy-refinement";"replay-policy-refinement"]
let schema_version="biocompiler.core.policy_refinement.v1"
let implementation="biocompiler.ocaml.policy_refinement.v0.1"
let validation_scope="policy-named-refinement-v0.1"
let profile=obj ["operations",Json.Array(List.map str operations);
  "schema_version",str schema_version;"implementation",str implementation;
  "validation_scope",str validation_scope;
  "evidence_schema",str "biocompiler.policy_refinement_evidence.v0.1";
  "max_result_bytes",Json.int Material.max_result_bytes;
  "max_result_nodes",Json.int Material.max_result_nodes;
  "artifact",str "none";"empirical",str "unassessed"]
let handle ~operation payload=
  Diagnostic.require(List.mem operation operations) "unsupported_operation"
    "Named refinement service only freshly checks or replays original inputs.";
  let payload=Material.unpack_payload ~assurance:false payload in
  let replay=operation="replay-policy-refinement" in
  let fields=Json.object_fields ~path:"/payload" payload in
  Json.exact_fields ~path:"/payload" (["request";"candidate";"limits"]@(if replay then ["report"] else [])) fields;
  let request=Json.field "request" fields and candidate=Json.field "candidate" fields
  and limits=Json.field "limits" fields in
  let coupled=Material.is_coupled_request request in
  let _,checked=Material.fresh_check ~request ~candidate ~limits in
  let material_report=Check.report checked in
  let evidence=match Check.accepted checked with
    | None -> Json.Null
    | Some value -> Evidence.to_json(Evidence.of_material value) in
  (* The material checker has already charged and bound these exact inputs.
     Only supplementary report hashing is new service work. Its own bounded
     scope cannot alter or borrow the completed material assessment's receipt. *)
  let budget=W.create ~profile:validation_scope ~error_code:"policy_refinement_service_work_limit"
    ~maximum:67108864 () in
  let size=if coupled then Wire.preflight ~charge:(W.charge budget) material_report else
    Input.preflight ~max_bytes:Material.max_result_bytes ~max_nodes:Material.max_result_nodes
      ~max_depth:128 ~charge:(W.charge budget) material_report in
  W.charge budget size;
  let bytes=Canonical.encode_bounded ~max_bytes:Material.max_result_bytes material_report in
  Diagnostic.require(String.length bytes=size) "policy_refinement_service_accounting"
    "Named-evidence report preflight differs from exact canonical bytes.";
  W.charge budget size;
  let material_report_fingerprint=Canonical.sha256 bytes in
  let result=obj ["schema_version",str schema_version;"implementation",str implementation;
    "validation_scope",str validation_scope;
    "request_fingerprint",get "request_fingerprint" material_report;
    "candidate_fingerprint",get "candidate_fingerprint" material_report;
    "invocation_fingerprint",get "invocation_fingerprint" material_report;
    "material_report_fingerprint",str material_report_fingerprint;
    "material_report",material_report;"evidence",evidence] in
  if not coupled then Material.validate_publication result;
  if replay then Diagnostic.require(Material.replay_equal ~coupled result(Json.field "report" fields))
    "policy_refinement_replay" "Saved named evidence differs from complete fresh checking.";
  if coupled then Material.publish_result ~coupled result else result
