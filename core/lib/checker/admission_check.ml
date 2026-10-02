open Bioc_wire
open Bioc_domain
module A = Admission
module R = A.Request
module S = A.Assessment
module T = Build_request.Target
module E = Build_request.Target_evidence
let category_reason = function
  | E.Human_in_vivo -> "human_in_vivo_evidence_requires_independent_review"
  | E.Primary_human_cells -> "primary_human_cell_evidence_does_not_establish_in_vivo_applicability"
  | E.Human_cell_line -> "human_cell_line_evidence_does_not_establish_primary_or_in_vivo_applicability"
  | E.Nonhuman_in_vivo -> "nonhuman_in_vivo_evidence_does_not_establish_human_applicability"
  | E.Nonhuman_cells -> "nonhuman_cell_evidence_does_not_establish_human_applicability"
  | E.Cell_free -> "cell_free_evidence_does_not_establish_recipient_applicability"
  | E.Software_fixture -> "software_fixture_is_not_biological_evidence"
let component_reason = function
  | Component.Synthetic_model -> "synthetic_model_not_human_implementation"
  | Component.Sequence_reference -> "sequence_reference_not_human_implementation"
  | Component.Modeled_component -> "modeled_component_not_independently_admitted_for_human_use"
let assess request =
  let request = R.of_json (R.to_json request) in
  let target = R.target request in
  let human = T.kind target = Build_request.Human_target in
  let evidence = T.evidence target in
  let reasons = ref [] in
  let reason value = reasons := value :: !reasons in
  let decision = if R.intended_use request = A.Software_test && not human then begin
      reason "software_testing_only_no_human_therapeutic_admission"; A.Software_only
    end else begin
      reason "human_profile_unavailable";
      if not human then reason "human_target_contract_missing"
      else if R.intended_use request = A.Software_test then reason "human_target_cannot_be_downgraded_to_software";
      if human then reason "human_applicability_not_independently_validated";
      let categories = List.map E.system evidence |> List.sort_uniq Stdlib.compare in
      if not (List.mem E.Human_in_vivo categories) then reason "human_in_vivo_evidence_not_declared";
      List.iter (fun category -> reason (category_reason category)) categories;
      List.iter (fun component ->
          reason (component_reason (Component.classification component));
          if List.exists (fun pin -> Pinned_identity.id pin = "wo2022081694a1.murine-fapcar.cds") (Component.identities component)
          then reason "murine_fap_reference_not_human_implementation") (R.components request);
      A.Not_admitted
    end in
  S.make ~request_fingerprint:(R.fingerprint request) ~target_fingerprint:(T.fingerprint target)
    ~intended_use:(R.intended_use request) ~boundary:(R.boundary request) ~decision
    ~diagnostics:(List.sort_uniq String.compare !reasons)
    ~component_fingerprints:(List.map Component.fingerprint (R.components request)) ~evidence
let verify request assessment =
  let expected = assess request in
  let supplied = S.of_json (S.to_json assessment) in
  Json.equal (S.to_json expected) (S.to_json supplied)
let for_target ~target ~boundary ~components =
  let target = T.of_json (T.to_json target) in
  let intended_use = match T.kind target with Build_request.Legacy_target -> A.Software_test | Build_request.Human_target -> A.Human_therapeutic in
  assess (R.make ~target ~intended_use ~boundary ~components)
let require_software_use ~target ~boundary ~components =
  let assessment = for_target ~target ~boundary ~components in
  Diagnostic.require (S.decision assessment = A.Software_only) "admission_not_admitted"
    ("Human therapeutic use is not admitted: " ^ String.concat "; " (S.diagnostics assessment));
  assessment
