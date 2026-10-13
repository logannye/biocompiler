open Bioc_wire
module R = Bioc_domain.Policy_controlled_workflow_request
module C = Bioc_domain.Policy_controlled_workflow_candidate
module Original = Bioc_domain.Policy_controlled_composition_request
module Material = Bioc_checker.Policy_controlled_material_check
module Behavior = Policy_controlled_behavior_check
module W = Bioc_checker.Work_budget
module Input = Bioc_domain.Policy_material_request
let schema_version = "biocompiler.policy_controlled_workflow_assessment.v0.1"
let implementation_version = "biocompiler.ocaml.policy_controlled_workflow_check.v0.1"
let str value = Json.String value
let obj fields = Json.Object fields
let get key raw = Json.field key (Json.object_fields raw)
type checked_controlled_workflow = { original:R.t; proposal:C.t; assessment:Json.t;
  material_value:Material.checked_controlled_material; behavior_value:Behavior.checked_controlled_behavior }
type result = { owner:W.t; assessment:Json.t; checked:checked_controlled_workflow option;
  request_identity:string; candidate_identity:string; invocation_identity:string }
let report (value:result) = value.assessment
let budget (value:result) = value.owner
let accepted (value:result) = value.checked
let request_fingerprint (value:result) = value.request_identity
let candidate_fingerprint (value:result) = value.candidate_identity
let invocation_fingerprint (value:result) = value.invocation_identity
let request (value:checked_controlled_workflow) = value.original
let candidate (value:checked_controlled_workflow) = value.proposal
let evidence (value:checked_controlled_workflow) = value.assessment
let material (value:checked_controlled_workflow) = value.material_value
let behavior (value:checked_controlled_workflow) = value.behavior_value
let measure owner raw = Input.preflight ~max_bytes:8_323_072 ~max_nodes:249_968
  ~max_depth:128 ~charge:(W.charge owner) raw
let encode owner raw =
  let bytes = measure owner raw in W.charge owner bytes;
  let encoded = Canonical.encode_bounded ~max_bytes:8_323_072 raw in
  Diagnostic.require (String.length encoded = bytes) "controlled_workflow_accounting"
    "Joined assessment canonical byte accounting disagrees.";
  encoded
let fingerprint owner raw = let encoded = encode owner raw in
  W.charge owner (String.length encoded); Canonical.sha256 encoded
let check ?parent ?(cancelled=fun () -> false) ~request:original_request ~candidate:proposal () =
  let limits = R.budgets original_request in
  let owner = match parent with
    | None -> W.create ~profile:R.resource_profile ~error_code:"controlled_workflow_work_limit"
        ~maximum:limits.max_work ()
    | Some parent -> W.nested ~parent ~profile:R.resource_profile
        ~error_code:"controlled_workflow_work_limit" ~maximum:limits.max_work () in
  let cancel () = Diagnostic.require (not (cancelled ())) "controlled_workflow_cancelled"
      "Cancelled joining cannot grant a checked workflow capability." in
  let charge amount = cancel (); W.charge owner amount in
  Diagnostic.require (not (W.exhausted owner)) "controlled_workflow_work_limit"
    "Previously exhausted work cannot enter joined checking.";
  charge 1;
  let request = R.of_json ~charge (R.to_json original_request) in
  let candidate = C.of_json ~charge (C.to_json proposal) in
  let request_identity = R.fingerprint request and candidate_identity = C.fingerprint candidate in
  Diagnostic.require (C.request_fingerprint candidate = request_identity)
    "controlled_workflow_request_binding" "Joined proposal belongs to different complete original authority.";
  (* Each child reparses complete originals and its proposal. Both nested scopes
     debit the same live owner; neither serialized child PASS is accepted. *)
  let material_result = Material.check ~parent:owner ~request:(R.original request)
      ~candidate:(C.material candidate) () in
  cancel ();
  let behavior_result = Behavior.check ~parent:owner ~cancelled ~request:(R.behavior request)
      ~candidate:(C.behavior candidate) () in
  let material_report = Material.report material_result and behavior_report = Behavior.report behavior_result in
  let child_outcome value = Json.string (get "outcome" value) in
  let outcomes = [child_outcome material_report;child_outcome behavior_report] in
  let complete = Option.is_some (Material.accepted material_result) && Option.is_some (Behavior.accepted behavior_result) in
  let outcome = if List.mem "fail" outcomes then "fail" else if List.mem "unknown" outcomes then "unknown"
    else if List.mem "unsupported" outcomes then "unsupported" else if complete then "pass" else "fail" in
  let invocation_identity = fingerprint owner (obj ["request_fingerprint",str request_identity;
    "candidate_fingerprint",str candidate_identity]) in
  let original = Original.raw (R.original request) in
  let assessment = obj ["schema_version",str schema_version;"profile",str R.profile;
    "implementation",str implementation_version;"stage",str "joined";
    "status",str (if complete then "controlled_workflow_accepted" else "not_accepted");
    "outcome",str outcome;
    "claim_scope",str "exact_supplied_two_member_rna_and_conditional_behavior_in_complete_finite_domain";
    "request_fingerprint",str request_identity;"candidate_fingerprint",str candidate_identity;
    "invocation_fingerprint",str invocation_identity;"material",material_report;"behavior",behavior_report;
    "project_context",get "project_context" (get "source_authority" original);
    "context",get "context" original;"limits",R.limits request;
    "resources",get "resources" original;"budgets",get "budgets" original;
    "empirical_status",str "unassessed";"human_use",str "unassessed";"therapeutic_export",str "withheld"] in
  ignore (measure owner assessment);
  let output = W.create_output ~profile:R.resource_profile ~error_code:"controlled_workflow_publication_limit"
    ~max_bytes:limits.max_report_bytes ~max_nodes:limits.max_report_nodes () in
  W.reserve_json output assessment;
  cancel ();
  Diagnostic.require (not (W.exhausted owner)) "controlled_workflow_work_limit"
    "Exhausted joining cannot grant a checked workflow capability.";
  let checked = match Material.accepted material_result,Behavior.accepted behavior_result with
    | Some material_value,Some behavior_value -> Some {original=request;proposal=candidate;assessment;
        material_value;behavior_value}
    | _ -> None in
  {owner;assessment;checked;request_identity;candidate_identity;invocation_identity}
let replay ?parent ~request ~candidate saved =
  let fresh = check ?parent ~request ~candidate () in
  let owner = budget fresh in
  let expected = encode owner (report fresh) and actual = encode owner saved in
  W.charge owner (String.length expected + String.length actual);
  Diagnostic.require (expected = actual) "controlled_workflow_assessment_mismatch"
    "Saved joined evidence differs from complete fresh checking under independent originals.";
  Diagnostic.require (not (W.exhausted owner)) "controlled_workflow_work_limit"
    "Exhausted replay cannot grant joined authority.";
  fresh
