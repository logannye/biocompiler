open Bioc_wire
module R = Bioc_domain.Policy_component_selection_request
module V = Bioc_domain.Policy_component_selection_candidate
module C = Bioc_domain.Policy_component_material_candidate
module CR = Bioc_domain.Policy_component_material_request
module Input = Bioc_domain.Policy_material_request
module K = Bioc_domain.Construction_content
module N = Bioc_domain.Molecule
module W = Bioc_checker.Work_budget
module Structure = Bioc_checker.Policy_mrna_structure_check
module P = Policy_preservation_check
module Child = Policy_component_material_check
module Common = Policy_component_selection_common
module Context = Policy_component_context_check
module Assembly = Policy_component_assembly_check

let profile = R.profile
let implementation_version = "biocompiler.ocaml.policy_component_selection_check.v0.1"
let str value = Json.String value
let obj fields = Json.Object fields
let arr values = Json.Array values
let get key raw = Json.field key (Json.object_fields raw)
let require condition message =
  Diagnostic.require condition "policy_component_selection_identity" message
type checked_selection = {
  original:R.t; proposed:V.t; limits_value:P.limits;
  winner_id:string; material:Child.checked_material; evidence_value:Json.t;
}
type result = {report_value:Json.t; accepted_value:checked_selection option}
type eligible = {id:string; rank:int; material:Child.checked_material}
let report value = value.report_value
let accepted value = value.accepted_value
let request value = value.original
let candidate value = value.proposed
let limits value = value.limits_value
let selected_id value = value.winner_id
let selected_material (value:checked_selection) = value.material
let evidence value = value.evidence_value
let measure budget raw = Input.preflight ~max_bytes:R.max_input_bytes
  ~max_nodes:R.max_input_nodes ~max_depth:R.max_input_depth ~charge:(W.charge budget) raw
let fingerprint budget raw =
  let bytes = measure budget raw in
  W.charge budget bytes;
  let encoded = Canonical.encode_bounded ~max_bytes:R.max_input_bytes raw in
  require (String.length encoded = bytes) "Selection canonical byte accounting differs.";
  W.charge budget bytes; Canonical.sha256 encoded
let option_id = function None -> Json.Null | Some value -> str value

let check ~request:original ~candidate:proposed ~limits =
  let allowances = R.budgets original in
  let budget = W.create ~profile:R.resource_profile
    ~error_code:"policy_component_selection_work_limit" ~maximum:allowances.max_work () in
  let outer = W.nested ~parent:budget ~profile:R.resource_profile
    ~error_code:"policy_component_selection_outer_work_limit" ~maximum:1_000_000_000 () in
  (* Account for decoding already performed before the declared allowance was
     available. Fresh decoding below has its own additional, charged passes. *)
  W.charge outer (R.decoding_work original);
  W.charge outer (V.decoding_work proposed);
  let limits_raw = P.limits_to_json limits in
  let invocation = obj ["request",R.to_json original;"candidate",V.to_json proposed;"limits",limits_raw] in
  ignore (measure outer invocation);
  let request = R.of_json ~charge:(W.charge outer) (R.to_json original) in
  require (R.fingerprint request = R.fingerprint original &&
    V.request_fingerprint proposed = R.fingerprint request)
    "Decoded candidate and complete original request identities differ.";
  let candidate = V.of_json ~charge:(W.charge outer) ~request (V.to_json proposed) in
  require (V.fingerprint candidate = V.fingerprint proposed)
    "Complete selection candidate changed since decoding.";
  Common.check ~budget:outer ~request;
  let output = W.create_output ~profile:R.resource_profile
    ~error_code:"policy_component_selection_publication_limit"
    ~max_bytes:allowances.max_report_bytes ~max_nodes:allowances.max_report_nodes () in
  let publish raw =
    let bytes = measure outer raw in
    W.charge outer bytes; W.reserve_json output raw in
  let all_inner_accepted = ref true in
  let eligible = ref [] in
  let reserved_children = ref 0 in
  let evaluate (source:R.alternative) (row:V.alternative) =
    require (source.id = row.id) "Original and candidate evaluation censuses differ.";
    let child_allowance = (CR.budgets source.request).max_work in
    (* The child owns its unchanged complete budget. Reserve the entire amount
       conservatively before calling it, without refunding reported usage. *)
    W.charge budget child_allowance;
    reserved_children := !reserved_children + child_allowance;
    let value = row.candidate in
    let checked = Child.check ~request:source.request ~behavior:(C.behavior value)
      ~implementation:(C.implementation value) ~proposed:(C.binding value)
      ~assembly_proposal:(C.assembly_proposal value) ~candidate:(C.construction value) ~limits in
    let child_report = Child.report checked in
    publish child_report;
    let candidate_pin = fingerprint outer (C.to_json value) in
    let length, sequence_pin, passes = match Child.accepted checked with
      | None -> all_inner_accepted := false; Json.Null,Json.Null,Json.Null
      | Some material ->
          require (CR.fingerprint (Child.request material) = CR.fingerprint source.request &&
            get "candidate_fingerprint" (Child.evidence material) = str candidate_pin &&
            Json.equal (get "limits" (Child.evidence material)) limits_raw)
            "Fresh child capability does not bind the complete original candidate and limits.";
          let content = Structure.content (Assembly.structure (Context.assembly (Child.context material))) in
          let molecule = match K.inventory content with
            | Some inventory -> (match K.Inventory.molecules inventory with
                | [value] when K.member_order content = [N.id value] -> value
                | _ -> Diagnostic.fail "policy_component_selection_material_scope"
                    "Selection requires the exact checked single-RNA member inventory.")
            | None -> Diagnostic.fail "policy_component_selection_material_scope"
                "Fresh child capability has no exact checked molecular inventory." in
          let sequence = N.sequence molecule in
          let nt = String.length sequence in
          W.charge outer (1 + nt);
          let passes = nt <= (R.predicate request).max_total_nt in
          if passes then eligible := {id=source.id;rank=source.rank;material} :: !eligible;
          Json.int nt,str (Canonical.sha256 sequence),Json.Bool passes in
    obj ["id",str source.id;"rank",Json.int source.rank;
      "request_fingerprint",str (CR.fingerprint source.request);
      "candidate_fingerprint",str candidate_pin;"inner",child_report;
      "total_nt",length;"sequence_sha256",sequence_pin;"eligible",passes] in
  let original_rows = R.evaluation_order request and candidate_rows = V.evaluation_order candidate in
  require (List.length original_rows = List.length candidate_rows)
    "Complete original and candidate cardinalities differ.";
  let rows = List.map2 evaluate original_rows candidate_rows in
  let choose left right =
    W.charge outer (1 + String.length left.id + String.length right.id);
    if left.rank < right.rank || (left.rank = right.rank && String.compare left.id right.id < 0)
    then left else right in
  let winner = if not !all_inner_accepted then None else
    List.fold_left (fun best value -> Some (match best with None -> value | Some old -> choose old value)) None !eligible in
  let winner_id = Option.map (fun value -> value.id) winner in
  let matches = !all_inner_accepted && V.selected_id candidate = winner_id in
  let status = if not !all_inner_accepted then "inner_not_accepted"
    else if not matches then "proposed_winner_mismatch"
    else if Option.is_none winner then "no_eligible_alternative"
    else "checked_selection" in
  let invocation_pin = fingerprint outer invocation in
  let report_base = [
    "schema_version",str "biocompiler.policy_component_selection_assessment.v0.1";
    "profile",str profile;"implementation",str implementation_version;
    "resource_profile",str R.resource_profile;"common_authority_profile",str Common.profile;
    "request_fingerprint",str (R.fingerprint request);"candidate_fingerprint",str (V.fingerprint candidate);
    "invocation_fingerprint",str invocation_pin;"status",str status;
    "claim_scope",str "bounded_complete_supplied_catalog_selection";
    "premise",str "supplied_component_composition_and_provider_contracts";
    "census_complete",Json.Bool true;"all_inner_accepted",Json.Bool !all_inner_accepted;
    "alternatives",arr rows;"predicate",get "predicate" (R.to_json request);
    "proposed_selected_id",option_id (V.selected_id candidate);
    "selected_id",option_id winner_id;
    "winner_matches",(if !all_inner_accepted then Json.Bool matches else Json.Null);
    "limits",limits_raw;"budgets",get "budgets" (R.to_json request);
    "empirical",str "unassessed";"artifact",str "withheld";"export",str "withheld"] in
  let usage charged = obj ["unit",str "logical_data_visits_and_reserved_child_allowances";
    "charged_work",Json.int charged;"reserved_child_work",Json.int !reserved_children;
    "original_decoding_work",Json.int (R.decoding_work original);
    "candidate_decoding_work",Json.int (V.decoding_work proposed)] in
  (* The reservation counts every child report above and each repeated report
     occurrence in this enclosing publication. The maximal usage spelling is
     conservative; no partial/truncated report can authorize a winner. *)
  publish (obj (report_base @ ["usage",usage allowances.max_work]));
  let charged = allowances.max_work - W.remaining budget in
  require (not (W.exhausted budget) && not (W.exhausted outer))
    "Selection work exhausted before complete publication.";
  let report_value = obj (report_base @ ["usage",usage charged]) in
  let accepted_value = match matches,winner with
    | true,Some winner -> Some {original=request;proposed=candidate;limits_value=limits;
        winner_id=winner.id;material=winner.material;evidence_value=report_value}
    | _ -> None in
  {report_value;accepted_value}
