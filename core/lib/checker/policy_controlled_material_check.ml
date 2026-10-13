open Bioc_wire
module R = Bioc_domain.Policy_controlled_composition_request
module C = Bioc_domain.Policy_controlled_material_candidate
module K = Bioc_domain.Construction_content
module E = Bioc_domain.Construction_assessment
module M = Bioc_domain.Policy_mrna_structure
module N = Bioc_domain.Molecule
module Input = Bioc_domain.Policy_material_request
module A = Policy_controlled_composition_admission
module S = Policy_mrna_structure_check
module Nominal = Policy_controlled_structure_check
module W = Work_budget
let schema_version = "biocompiler.policy_controlled_composition_material_assessment.v0.1"
let implementation_version = "biocompiler.ocaml.policy_controlled_material_check.v0.1"
let str value = Json.String value
let obj fields = Json.Object fields
let arr values = Json.Array values
let get key raw = Json.field key (Json.object_fields raw)
let strings values = arr (List.map str values)
type checked_structure = Ordinary of S.checked_structure | Nominal of Nominal.checked_structure
type checked_controlled_material = {
  original:R.t; proposal:C.t; admitted:A.t; structural:checked_structure; assessment:Json.t;
}
type result = {
  owner:W.t; assessment:Json.t; outcome_value:E.outcome;
  checked:checked_controlled_material option;
  request_identity:string; candidate_identity:string; invocation_identity:string;
}
let budget (value:result) = value.owner
let report (value:result) = value.assessment
let outcome (value:result) = value.outcome_value
let accepted (value:result) = value.checked
let request_fingerprint (value:result) = value.request_identity
let candidate_fingerprint (value:result) = value.candidate_identity
let invocation_fingerprint (value:result) = value.invocation_identity
let request (value:checked_controlled_material) = value.original
let candidate (value:checked_controlled_material) = value.proposal
let admission (value:checked_controlled_material) = value.admitted
let structure (value:checked_controlled_material) = value.structural
let structure_evidence = function Ordinary value -> S.evidence value | Nominal value -> Nominal.evidence value
let content (value:checked_controlled_material) = match value.structural with
  | Ordinary value -> S.content value | Nominal value -> Nominal.content value
let evidence (value:checked_controlled_material) = value.assessment
let measure owner raw = Input.preflight ~max_bytes:8_323_072 ~max_nodes:249_968
  ~max_depth:128 ~charge:(W.charge owner) raw
let fingerprint owner raw =
  let bytes = measure owner raw in
  W.charge owner bytes;
  let encoded = Canonical.encode_bounded ~max_bytes:8_323_072 raw in
  Diagnostic.require (bytes = String.length encoded) "controlled_material_accounting"
    "Controlled material canonical byte accounting disagrees.";
  W.charge owner bytes;
  Canonical.sha256 encoded
let check ?parent ~request:original ~candidate:proposed () =
  let limits:R.budgets = R.budgets original in
  let owner = match parent with
    | None -> W.create ~profile:R.resource_profile ~error_code:"controlled_material_work_limit"
        ~maximum:limits.max_work ()
    | Some parent -> W.nested ~parent ~profile:R.resource_profile
        ~error_code:"controlled_material_work_limit" ~maximum:limits.max_work () in
  Diagnostic.require (not (W.exhausted owner)) "controlled_material_work_limit"
    "Previously exhausted work cannot enter controlled material checking.";
  (* The neutral codecs return immutable original JSON. Reparse both complete
     originals under this live owner; no candidate-local PASS is consumed. *)
  let request = R.of_json ~charge:(W.charge owner) (R.to_json original) in
  let candidate = C.of_json ~charge:(W.charge owner) (C.to_json proposed) in
  let request_identity = R.fingerprint request and candidate_identity = C.fingerprint candidate in
  Diagnostic.require (C.request_fingerprint candidate = request_identity)
    "controlled_material_request_binding"
    "Material candidate is not bound to the complete independently supplied original request.";
  let admitted = A.admit ~charge:(W.charge owner) request in
  let structural_report,structural_outcome,structural_checked =
    if Nominal.requests_nominal_translation ~charge:(W.charge owner) ~admitted ~request then (
      let result = Nominal.check ~parent:owner ~admitted ~request
        ~candidate:(C.construction candidate) () in
      Nominal.report result,Nominal.outcome result,
        Option.map (fun value -> Nominal value) (Nominal.checked_structure result))
    else (
      let result = S.check ~parent:owner ~authority:(R.material request)
        ~candidate:(C.construction candidate) () in
      S.report result,S.outcome result,
        Option.map (fun value -> Ordinary value) (S.checked_structure result)) in
  (* The leaf already performs private independent reconstruction. Repeating
     reconstruction here would neither add an oracle nor strengthen a claim. *)
  let raw = R.raw request in
  let resources = get "resources" raw in
  let maximum_member = Z.to_int (Json.integer (get "max_member_rna_nt" resources))
  and maximum_total = Z.to_int (Json.integer (get "max_total_rna_nt" resources)) in
  let members = match K.inventory (C.construction candidate) with
    | None -> [] | Some inventory -> K.Inventory.molecules inventory in
  let expected_order = M.member_order (R.material request) in
  W.charge owner (1 + List.length members + List.length expected_order);
  let total = ref 0 in
  let actual_lengths = List.map (fun (member:N.t) ->
    let length = String.length (N.sequence member) in
    W.charge owner (1 + length);
    Diagnostic.require (length <= max_int - !total) "controlled_material_work_limit"
      "Complete material length accounting overflow.";
    total := !total + length;
    obj ["member_id",str (N.id member); "rna_nt",Json.int length;
      "within_limit",Json.Bool (length <= maximum_member)]) members in
  let member_order = List.map N.id members in
  let limits_pass = List.length members = 2 && member_order = expected_order &&
    List.for_all (fun (member:N.t) -> String.length (N.sequence member) <= maximum_member) members &&
    !total <= maximum_total in
  let outcome_value = if limits_pass then structural_outcome else E.Fail in
  let material_limits = obj ["member_order",strings member_order;
    "expected_member_order",strings expected_order; "members",arr actual_lengths;
    "max_member_rna_nt",Json.int maximum_member; "total_rna_nt",Json.int !total;
    "max_total_rna_nt",Json.int maximum_total;
    "outcome",str (if limits_pass then "pass" else "fail")] in
  let invocation_identity = fingerprint owner (obj [
    "request_fingerprint",str request_identity; "candidate_fingerprint",str candidate_identity]) in
  let complete = outcome_value = E.Pass && Option.is_some structural_checked in
  let assessment = obj ["schema_version",str schema_version; "profile",str R.profile;
    "implementation",str implementation_version; "stage",str "material";
    "status",str (if complete then "checked_controlled_material" else "not_accepted");
    "outcome",str (E.outcome_name outcome_value);
    "claim_scope",str "exact_supplied_two_member_rna_structure_only";
    "request_fingerprint",str request_identity; "candidate_fingerprint",str candidate_identity;
    "invocation_fingerprint",str invocation_identity;
    "admission",A.report admitted; "structure",structural_report;
    "material_limits",material_limits;
    "bindings",get "product_bindings" (get "assembly" raw);
    "context",get "context" raw; "resources",resources; "budgets",get "budgets" raw;
    "behavior_status",str "not_performed"; "empirical_status",str "unassessed";
    "human_use",str "unassessed"; "therapeutic_export",str "withheld"] in
  (* The complete retained report consumes both work and the supplied report
     ceiling before any material capability is returned. Outer frame accounting
     remains the responsibility of the same live service invocation. *)
  ignore (measure owner assessment);
  let output = W.create_output ~profile:R.resource_profile ~error_code:"controlled_material_publication_limit"
    ~max_bytes:limits.max_report_bytes ~max_nodes:limits.max_report_nodes () in
  W.reserve_json output assessment;
  Diagnostic.require (not (W.exhausted owner)) "controlled_material_work_limit"
    "Exhausted work cannot produce a material capability.";
  let checked = match complete,structural_checked with
    | true,Some structural -> Some {original=request; proposal=candidate; admitted;
        structural; assessment}
    | _ -> None in
  {owner; assessment; outcome_value; checked; request_identity; candidate_identity; invocation_identity}
let replay ?parent ~request ~candidate saved =
  let fresh = check ?parent ~request ~candidate () in
  let owner = budget fresh in
  let encode raw =
    let bytes = measure owner raw in
    W.charge owner bytes;
    Canonical.encode_bounded ~max_bytes:8_323_072 raw in
  let expected = encode (report fresh) and observed = encode saved in
  W.charge owner (String.length expected + String.length observed);
  Diagnostic.require (expected = observed) "controlled_material_assessment_mismatch"
    "Saved material evidence differs from fresh checking against complete original authority.";
  Diagnostic.require (not (W.exhausted owner)) "controlled_material_work_limit"
    "Exhausted replay cannot return material authority.";
  fresh
