open Bioc_wire
module R = Bioc_domain.Policy_component_selection_request
module V = Bioc_domain.Policy_component_selection_candidate
module CR = Bioc_domain.Policy_component_material_request
module CV = Bioc_domain.Policy_component_material_candidate
module Input = Bioc_domain.Policy_material_request
module P = Bioc_realization_checker.Policy_preservation_check
module Check = Bioc_realization_checker.Policy_component_selection_check
module Child = Bioc_realization_checker.Policy_component_material_check
module Format = Policy_component_material_format

let operations = ["check-policy-component-selection";"replay-policy-component-selection";
  "export-policy-component-selection"]
let validation_scope = "policy-component-selection-mrna-v0.1"
let implementation = "biocompiler.ocaml.policy_component_selection.v0.1"
let schema_version = "biocompiler.core.policy_component_selection.v1"
let resource_profiles = R.resource_profiles
let candidate_schema = V.schema_version
let manifest_schema = "biocompiler.policy_component_selection_mrna_manifest.v0.1"
let export_schema = "biocompiler.policy_component_selection_mrna_export.v0.1"
let publication_profile = "biocompiler.policy_component_selection_publication.v0.1"
let max_result_bytes = Limits.max_response_bytes - 6 * Limits.max_string_bytes - 65536
let max_result_nodes = Limits.max_json_nodes - 32
let str value = Json.String value
let obj fields = Json.Object fields
let arr values = Json.Array values
let get key raw = Json.field key (Json.object_fields raw)
let profile = obj ["operations",arr (List.map str operations);
  "request_schema",str R.schema_version;"candidate_schema",str candidate_schema;
  "schema_version",str schema_version;"implementation",str implementation;
  "resource_profiles",arr (List.map str resource_profiles);
  "publication_limits",arr [
    obj ["profile",str R.resource_profile;"max_report_bytes",Json.int max_result_bytes;
      "max_report_nodes",Json.int max_result_nodes];
    obj ["profile",str R.publication_resource_profile;"max_report_bytes",Json.int max_result_bytes;
      "max_report_nodes",Json.int R.max_publication_nodes]];
  "publication_profile",str publication_profile;
  "validation_scope",str validation_scope;"max_input_bytes",Json.int R.max_input_bytes;
  "max_result_bytes",Json.int max_result_bytes;"max_result_nodes",Json.int max_result_nodes;
  "artifact",str "on_fresh_export_only";"empirical",str "unassessed"]

let require condition message =
  Diagnostic.require condition "policy_component_selection_export_identity" message

let export_artifact scope pending request candidate limits report =
  let id,material = match Check.pending_selected_material ~scope pending with
    | Some value -> value
    | None -> Diagnostic.fail "policy_component_selection_export_not_accepted"
        "Fresh complete-catalog checking did not establish a matching accepted winner." in
  let find label id_of rows =
    let found=List.filter (fun row ->
      let actual=id_of row in Check.charge_outer scope (1+String.length actual+String.length id);
      actual=id) rows in
    match found with [value] -> value
    | _ -> Diagnostic.fail "policy_component_selection_export_identity"
        ("Fresh selection lacks one exact "^label^" for its winner.") in
  let original=find "original alternative" (fun (row:R.alternative) -> row.id) (R.alternatives request) in
  let proposed=find "candidate alternative" (fun (row:V.alternative) -> row.id) (V.alternatives candidate) in
  let child_report=Child.evidence material in
  let retained=find "complete child report" (fun row -> Json.string (get "id" row))
    (Json.array (get "alternatives" report)) in
  Check.charge_outer scope 512;
  require (CR.fingerprint (Child.request material)=CR.fingerprint original.request &&
    get "request_fingerprint" child_report=str (CR.fingerprint original.request) &&
    get "candidate_fingerprint" child_report=str (CV.fingerprint proposed.candidate) &&
    get "selected_id" report=str id && get "status" report=str "checked_selection")
    "Winning material does not bind the original alternative, candidate and complete selection.";
  require (Check.equal_json scope child_report (get "inner" retained) &&
    Check.equal_json scope limits (get "limits" child_report))
    "Winning material report differs from the retained complete child evidence or invocation limits.";
  let rendered=Format.render ~charge:(Check.charge_outer scope) material in
  require (List.length rendered.members=1) "Selection export requires the exact checked single RNA member.";
  let selected=obj ["id",str id;"request_fingerprint",str (CR.fingerprint original.request);
    "candidate_fingerprint",str (CV.fingerprint proposed.candidate);
    "assessment_fingerprint",str (Check.fingerprint scope child_report)] in
  let manifest=obj ["schema_version",str manifest_schema;"profile",str R.profile;
    "claim_scope",str "bounded_complete_supplied_catalog_selection_to_exact_mrna";
    "premise",str "supplied_component_composition_and_provider_contracts";
    "request",R.to_json request;"candidate",V.to_json candidate;"limits",limits;"assessment",report;
    "bindings",obj ["request_fingerprint",str (R.fingerprint request);
      "candidate_fingerprint",str (V.fingerprint candidate);
      "invocation_fingerprint",get "invocation_fingerprint" report;
      "assessment_fingerprint",str (Check.fingerprint scope report)];
    "selected",selected;"members",arr rendered.members;
    "fasta_sha256",str rendered.fasta_sha256;"empirical",str "unassessed";
    "original_authority",str "retain_original_inputs_separately"] in
  (* The standalone manifest and its repeated occurrence in the later actual
     wire frame are distinct publication events on this same original owner. *)
  Check.reserve_publication scope manifest;
  let bytes=Check.encode_json scope manifest in
  Check.charge_outer scope (String.length bytes);
  obj ["schema_version",str export_schema;"fasta",str rendered.fasta;
    "fasta_sha256",str rendered.fasta_sha256;"manifest",manifest;
    "manifest_sha256",str (Canonical.sha256 bytes)]

let prepare ~executable ~(request:Protocol.request) =
  Diagnostic.require (List.mem request.operation operations) "unsupported_operation"
    "Selection service accepts complete supplied candidates for check, replay or fresh export only.";
  (* Bound the complete service payload, including a retained replay wrapper,
     before any field/list traversal. Its count is paid before fresh checking;
     the checker records only its own phase delta so replay remains exact. *)
  let startup=ref 0 in
  let charge amount =
    Diagnostic.require (amount>=0 && amount<=max_int - !startup)
      "policy_component_selection_work_limit" "Selection service import counter overflow.";
    startup := !startup+amount in
  ignore (Input.preflight ~max_bytes:R.max_input_bytes ~max_nodes:R.max_input_nodes
    ~max_depth:R.max_input_depth ~charge request.payload);
  let replay=request.operation="replay-policy-component-selection" in
  let fields=Json.object_fields ~path:"/payload" request.payload in
  Json.exact_fields ~path:"/payload" (["request";"candidate";"limits"]@(if replay then ["report"] else [])) fields;
  let original=R.of_json (Json.field "request" fields) in
  let scope=Check.create_scope ~request:original () in
  try
    Check.charge_outer scope !startup;
    let candidate=V.of_json ~request:original (Json.field "candidate" fields) in
    let limits_raw=Json.field "limits" fields in
    let limits=P.limits_of_json limits_raw in
    let pending=Check.check_in ~scope ~candidate ~limits in
    let report=Check.pending_report ~scope pending in
    let artifact=if request.operation="export-policy-component-selection"
      then export_artifact scope pending original candidate limits_raw report else Json.Null in
    let result=obj ["schema_version",str schema_version;"implementation",str implementation;
      "resource_profile",str (R.resources original);"validation_scope",str validation_scope;
      "request_fingerprint",str (R.fingerprint original);
      "candidate_fingerprint",str (V.fingerprint candidate);
      "invocation_fingerprint",get "invocation_fingerprint" report;
      "report_fingerprint",str (Check.fingerprint scope report);
      "candidate",V.to_json candidate;"report",report;"artifact",artifact] in
    if replay then Diagnostic.require (Check.equal_json scope result (Json.field "report" fields))
      "policy_component_selection_replay"
      "Saved complete selection wrapper differs from fresh checking of every original and candidate.";
    (* This advertised result envelope has its own smaller bound. It is a
       checked preparation pass, not an extra publication event. The actual
       protocol frame is still separately measured and reserved by the guard. *)
    ignore (Input.preflight ~max_bytes:max_result_bytes ~max_nodes:max_result_nodes
      ~max_depth:R.max_input_depth ~charge:(Check.charge_outer scope) (obj ["result",result]));
    let before_encode=Check.prepare_response ~scope pending ~executable ~protocol_request:request ~result in
    result,before_encode
  with error -> Check.abort_scope scope error
