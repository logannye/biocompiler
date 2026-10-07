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
type phase = Open | Checking | Assessed | Ready | Finalizing | Finalized | Failed
type scope = {
  original_request:R.t; budget:W.t; outer:W.t; output:W.output;
  mutable phase:phase; mutable failure:exn option; mutable charged_work:int;
}
type pending = {
  owner:scope; decoded_request:R.t; decoded_candidate:V.t; checked_limits:P.limits;
  assessment:Json.t; selected:(string * Child.checked_material) option;
}
let scope_require condition message =
  Diagnostic.require condition "policy_component_selection_scope" message
let abort_scope scope error =
  let first = match scope.failure with Some previous -> previous | None -> error in
  scope.failure <- Some first; scope.phase <- Failed; raise first
let budget_guard scope =
  scope_require (not (W.exhausted scope.budget) && not (W.exhausted scope.outer))
    "Selection scope or an ancestor has exhausted its allowance."
let protect scope action =
  match scope.failure with
  | Some error -> raise error
  | None -> (try budget_guard scope; let value=action () in budget_guard scope; value
      with error -> abort_scope scope error)
let work_phase scope =
  scope_require (match scope.phase with Open | Checking | Assessed -> true | _ -> false)
    "Selection scope is no longer open for preparation."
let spend scope budget amount =
  W.charge budget amount;
  scope.charged_work <- scope.charged_work + amount
let charge_outer scope amount = protect scope (fun () ->
  work_phase scope; spend scope scope.outer amount)
let measure_with charge raw = Input.preflight ~max_bytes:R.max_input_bytes
  ~max_nodes:R.max_input_nodes ~max_depth:R.max_input_depth ~charge raw
let measure scope raw = measure_with (charge_outer scope) raw
let encode_json scope raw = protect scope (fun () ->
  work_phase scope;
  let bytes = measure scope raw in
  charge_outer scope bytes;
  let encoded = Canonical.encode_bounded ~max_bytes:R.max_input_bytes raw in
  require (String.length encoded = bytes) "Selection canonical byte accounting differs.";
  encoded)
let fingerprint scope raw = protect scope (fun () ->
  let encoded = encode_json scope raw in
  charge_outer scope (String.length encoded); Canonical.sha256 encoded)
let equal_json scope left right = protect scope (fun () ->
  work_phase scope;
  let a=measure scope left and b=measure scope right in
  charge_outer scope a; charge_outer scope b; Json.equal left right)
let reserve_publication scope raw = protect scope (fun () ->
  work_phase scope;
  let bytes=measure scope raw in
  charge_outer scope bytes; W.reserve_json scope.output raw)
let create_scope ?parent ~request:original_request () =
  let allowances=R.budgets original_request in
  let resources=R.resources original_request in
  let budget=match parent with
    | None -> W.create ~profile:resources
        ~error_code:"policy_component_selection_work_limit" ~maximum:allowances.max_work ()
    | Some parent -> W.nested ~parent ~profile:resources
        ~error_code:"policy_component_selection_work_limit" ~maximum:allowances.max_work () in
  let outer=W.nested ~parent:budget ~profile:resources
    ~error_code:"policy_component_selection_outer_work_limit" ~maximum:1_000_000_000 () in
  let output=W.create_output ~profile:resources
    ~error_code:"policy_component_selection_publication_limit"
    ~max_bytes:allowances.max_report_bytes ~max_nodes:allowances.max_report_nodes () in
  let scope={original_request;budget;outer;output;phase=Open;failure=None;charged_work=0} in
  protect scope (fun () -> scope)
let option_id = function None -> Json.Null | Some value -> str value

let check_in ~scope ~candidate:proposed ~limits = protect scope (fun () ->
  scope_require (scope.phase=Open) "A selection scope can check only one complete candidate.";
  scope.phase <- Checking;
  let starting_work=scope.charged_work in
  let original=scope.original_request in
  let allowances=R.budgets original in
  let budget=scope.budget and outer=scope.outer in
  (* Account for decoding already performed before the declared allowance was
     available. Fresh decoding below has its own additional, charged passes. *)
  charge_outer scope (R.decoding_work original);
  charge_outer scope (V.decoding_work proposed);
  let limits_raw = P.limits_to_json limits in
  let invocation = obj ["request",R.to_json original;"candidate",V.to_json proposed;"limits",limits_raw] in
  ignore (measure scope invocation);
  let request = R.of_json ~charge:(charge_outer scope) (R.to_json original) in
  require (R.fingerprint request = R.fingerprint original &&
    V.request_fingerprint proposed = R.fingerprint request)
    "Decoded candidate and complete original request identities differ.";
  let candidate = V.of_json ~charge:(charge_outer scope) ~request (V.to_json proposed) in
  require (V.fingerprint candidate = V.fingerprint proposed)
    "Complete selection candidate changed since decoding.";
  (* Common's internal charges already debit this same total/outer owner. The
     difference across this one successful call counts only its new work, even
     when an additional ancestor began with a smaller remaining allowance. *)
  let before_common=W.remaining budget in
  Common.check ~budget:outer ~request;
  scope.charged_work <- scope.charged_work + before_common - W.remaining budget;
  let publish=reserve_publication scope in
  let all_inner_accepted = ref true in
  let eligible = ref [] in
  let reserved_children = ref 0 in
  let evaluate (source:R.alternative) (row:V.alternative) =
    require (source.id = row.id) "Original and candidate evaluation censuses differ.";
    let child_allowance = (CR.budgets source.request).max_work in
    (* The child owns its unchanged complete budget. Reserve the entire amount
       conservatively before calling it, without refunding reported usage. *)
    spend scope budget child_allowance;
    reserved_children := !reserved_children + child_allowance;
    let value = row.candidate in
    let checked = Child.check ~request:source.request ~behavior:(C.behavior value)
      ~implementation:(C.implementation value) ~proposed:(C.binding value)
      ~assembly_proposal:(C.assembly_proposal value) ~candidate:(C.construction value) ~limits in
    let child_report = Child.report checked in
    publish child_report;
    let candidate_pin = fingerprint scope (C.to_json value) in
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
          charge_outer scope (1 + nt);
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
    charge_outer scope (1 + String.length left.id + String.length right.id);
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
  let invocation_pin = fingerprint scope invocation in
  let report_base = [
    "schema_version",str "biocompiler.policy_component_selection_assessment.v0.1";
    "profile",str profile;"implementation",str implementation_version;
    "resource_profile",str (R.resources request);"common_authority_profile",str Common.profile;
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
  (* The assessment records this checking pass only. Service import, replay and
     rendering still debit this same owner without changing replay identity. *)
  let charged = scope.charged_work - starting_work in
  require (not (W.exhausted budget) && not (W.exhausted outer))
    "Selection work exhausted before complete publication.";
  let report_value = obj (report_base @ ["usage",usage charged]) in
  let selected = match matches,winner with
    | true,Some winner -> Some (winner.id,winner.material)
    | _ -> None in
  scope.phase <- Assessed;
  {owner=scope;decoded_request=request;decoded_candidate=candidate;checked_limits=limits;
    assessment=report_value;selected})

let pending_guard scope pending =
  scope_require (pending.owner == scope) "Pending selection belongs to another scope.";
  scope_require (scope.phase=Assessed) "Pending selection is unavailable in this scope phase."
let pending_report ~scope pending = protect scope (fun () ->
  pending_guard scope pending; pending.assessment)
let pending_selected_material ~scope pending = protect scope (fun () ->
  pending_guard scope pending; pending.selected)
let seal pending =
  let accepted_value=Option.map (fun (winner_id,material) ->
    {original=pending.decoded_request;proposed=pending.decoded_candidate;
      limits_value=pending.checked_limits;winner_id;material;evidence_value=pending.assessment})
    pending.selected in
  {report_value=pending.assessment;accepted_value}
let check ~request ~candidate ~limits =
  let scope=create_scope ~request () in
  let pending=check_in ~scope ~candidate ~limits in
  protect scope (fun () ->
    pending_guard scope pending;
    let result=seal pending in scope.phase <- Finalized; result)

let prepare_response ~scope pending ~executable ~protocol_request ~result =
  protect scope (fun () ->
    pending_guard scope pending;
    let expected=Protocol.response ~executable ~request:(Some protocol_request)
      ~status:Protocol.Ok ~result:(Some result) [] in
    (* Bind the complete prepared frame while the owner is still open. Actual
       admission below measures and compares the runner's independently built
       value; preparing this closure does not reserve or finalize publication. *)
    ignore (measure scope expected);
    scope.phase <- Ready;
    fun actual -> protect scope (fun () ->
      scope_require (scope.phase=Ready) "Selection response guard is one-shot.";
      scope.phase <- Finalizing;
      let charge amount=spend scope scope.outer amount in
      let a=measure_with charge expected and b=measure_with charge actual in
      charge a; charge b;
      require (Json.equal expected actual) "Actual protocol response differs from the prepared complete selection frame.";
      (* The publication owner counts canonical JSON bytes, including every
         repeated nested report/manifest. The transport LF costs one work unit
         and remains bounded by the runner's strict global response limit. *)
      let bytes=measure_with charge actual in
      charge bytes; W.reserve_json scope.output actual;
      charge bytes; charge 1;
      budget_guard scope;
      scope.phase <- Finalized))
