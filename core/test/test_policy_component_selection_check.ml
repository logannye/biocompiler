open Bioc_wire
open Bioc_policy_component_test_support.Literals
module Originals = Bioc_policy_component_test_support.Selection_requests
module R = Bioc_domain.Policy_component_selection_request
module V = Bioc_domain.Policy_component_selection_candidate
module CR = Bioc_domain.Policy_component_material_request
module CV = Bioc_domain.Policy_component_material_candidate
module K = Bioc_domain.Construction_content
module P = Bioc_realization_checker.Policy_preservation_check
module Check = Bioc_realization_checker.Policy_component_selection_check
module Child = Bioc_realization_checker.Policy_component_material_check
module Context = Bioc_realization_checker.Policy_component_context_check
module Assembly = Bioc_realization_checker.Policy_component_assembly_check
module Structure = Bioc_checker.Policy_mrna_structure_check
module Producer = Bioc_producer_service.Policy_component_material_producer

(* The existing producer supplies only SUBJECT candidates. Original same-A
   requests, both RNA strings, complete-domain counts and winner expectations
   are independent literals. No producer report supplies an expected result. *)
let short_rna="CCAUGGCUUAAGGAAAA"
let long_rna="CGCAUGGCUUAAGGAAAA"
let child id raw=List.find (fun row -> get "id" row=str id) (items "alternatives" raw)
let change_row id transform=edit ["alternatives"] (fun rows -> arr (List.map (fun row ->
  if get "id" row=str id then transform row else row) (Json.array rows)))
let change_request id transform=change_row id (edit ["request"] transform)
let change_candidate id transform=change_row id (edit ["candidate"] transform)
let every_request transform=edit ["alternatives"] (fun rows -> arr (List.map
  (edit ["request"] transform) (Json.array rows)))
let reverse=edit ["alternatives"] (fun rows -> arr (List.rev (Json.array rows)))
let candidate_raw original limits=
  obj ["schema_version",str "biocompiler.policy_component_selection_candidate.v0.1";
    "alternatives",arr (List.map (fun row ->
      let compiled=Producer.compile (obj ["request",get "request" row;"limits",limits]) in
      obj ["id",get "id" row;"candidate",get "candidate" compiled]) (items "alternatives" original));
    "selected_id",str "short"]
let decode original proposed limits=
  let request=R.of_json original in
  request,V.of_json ~request proposed,P.limits_of_json limits
let check original proposed limits=
  let request,candidate,limits=decode original proposed limits in
  Check.check ~request ~candidate ~limits
let no_token status result=
  let report=Check.report result in
  require (Option.is_none (Check.accepted result) && get "status" report=str status)
    ("Failed/empty selection granted a token or wrong status: "^Canonical.encode report);
  require (get "artifact" report=str "withheld" && get "export" report=str "withheld" &&
    get "empirical" report=str "unassessed") "Selection failure changed artifact or empirical scope";
  report
let token_sequence accepted=
  let material=Check.selected_material accepted in
  let content=Structure.content (Assembly.structure (Context.assembly (Child.context material))) in
  match K.inventory content with
  | Some inventory -> (match K.Inventory.molecules inventory with
      | [molecule] -> require (K.member_order content=["payload"] && N.id molecule="payload")
          "Selected token lost the exact single-RNA member identity"; N.sequence molecule
      | _ -> failwith "Selected token has a different molecular census")
  | None -> failwith "Selected token has no checked inventory"
let complete_inner fixture row sequence eligible=
  let report=get "inner" row in
  require (get "status" report=str "checked_component_material" &&
    get "all_original_obligations_discharged" report=Json.Bool true)
    "An eligible or losing original skipped complete inner material acceptance";
  require (get "total_nt" row=Json.int (String.length sequence) &&
    get "sequence_sha256" row=str (Canonical.sha256 sequence) && get "eligible" row=Json.Bool eligible)
    "Outer eligibility differs from the independently declared exact RNA";
  require (List.map (get "obligation") (items "obligations" report)=items "obligations" (get "expected" fixture) &&
    List.length (items "obligations" report)=23 &&
    List.for_all (fun item -> get "status" item=str "discharged") (items "obligations" report))
    "Selection dropped original obligations from a losing or winning child";
  let preservation=get "preservation" report in
  List.iter (fun (key,value) -> require (at ["coverage";key] preservation=Json.int value)
    ("Selection child lost complete original domain "^key))
    ["histories",9;"transitions",47;"prefixes_started",48;"matched_prefixes",48];
  require (at ["coverage";"complete"] preservation=Json.Bool true &&
    List.map (get "id") (items "requirements" preservation)=
      List.map str ["request_progress";"initiation_progress";"exclusive_selection"] &&
    List.for_all (fun item -> get "status" item=str "pass" && at ["histories";"pass"] item=Json.int 9)
      (items "requirements" preservation)) "Selection weakened original hard requirements or exercise coverage"
let accepted original proposed limits winner sequence result=
  let token=match Check.accepted result with Some value -> value
    | None -> failwith ("Expected a fresh checked selection: "^Canonical.encode (Check.report result)) in
  let report=Check.report result in
  require (get "status" report=str "checked_selection" && get "census_complete" report=Json.Bool true &&
    get "all_inner_accepted" report=Json.Bool true && get "winner_matches" report=Json.Bool true &&
    get "selected_id" report=str winner && Check.selected_id token=winner && token_sequence token=sequence)
    "Fresh selection differs from literal hard-constraint/rank/ASCII winner and RNA";
  require (R.fingerprint (Check.request token)=Canonical.fingerprint original &&
    V.fingerprint (Check.candidate token)=Canonical.fingerprint proposed &&
    Json.equal (P.limits_to_json (Check.limits token)) limits && Json.equal (Check.evidence token) report)
    "Private selection capability lost complete original/candidate/limits/evidence binding";
  require (CR.fingerprint (Child.request (Check.selected_material token))=
    Canonical.fingerprint (get "request" (child winner original)))
    "Selection capability material belongs to a different original alternative";
  require (get "request_fingerprint" report=str (Canonical.fingerprint original) &&
    get "candidate_fingerprint" report=str (Canonical.fingerprint proposed) &&
    get "invocation_fingerprint" report=str (Canonical.fingerprint
      (obj ["request",original;"candidate",proposed;"limits",limits])))
    "Complete selection invocation identity was replaced by a selected-child identity";
  require (get "claim_scope" report=str "bounded_complete_supplied_catalog_selection" &&
    get "premise" report=str "supplied_component_composition_and_provider_contracts" &&
    get "empirical" report=str "unassessed" && get "artifact" report=str "withheld" &&
    get "export" report=str "withheld") "Checked supplied contracts became exported or biological evidence";
  report

let positives fixture original proposed limits=
  require (String.length short_rna=17 && String.length long_rna=18) "Literal base counts changed";
  let first=accepted original proposed limits "short" short_rna (check original proposed limits) in
  require (List.map (get "id") (items "alternatives" first)=[str "long";str "short"])
    "Complete child checking must use ASCII ID order";
  complete_inner fixture (child "long" first) long_rna false;
  complete_inner fixture (child "short" first) short_rna true;
  require (at ["usage";"reserved_child_work"] first=Json.int 1000000000 &&
    Z.gt (Json.integer (at ["usage";"charged_work"] first)) (Z.of_int 1000000000) &&
    Z.leq (Json.integer (at ["usage";"charged_work"] first)) (Z.of_int 17000000000))
    "Both complete child allowances plus outer work must be conservatively charged";
  let eighteen=put ["predicate";"max_total_nt"] (Json.int 18) original in
  let long=replace "selected_id" (str "long") proposed in
  let report=accepted eighteen long limits "long" long_rna (check eighteen long limits) in
  complete_inner fixture (child "long" report) long_rna true;
  complete_inner fixture (child "short" report) short_rna true;
  require (get "request_fingerprint" report<>get "request_fingerprint" first &&
    get "invocation_fingerprint" report<>get "invocation_fingerprint" first)
    "Changed outer predicate reused the old selection authority";
  let sixteen=put ["predicate";"max_total_nt"] (Json.int 16) original in
  let none=replace "selected_id" Json.Null proposed in
  let report=no_token "no_eligible_alternative" (check sixteen none limits) in
  require (get "census_complete" report=Json.Bool true && get "all_inner_accepted" report=Json.Bool true &&
    get "selected_id" report=Json.Null && get "winner_matches" report=Json.Bool true)
    "Complete no-selection was confused with child failure or incomplete search";
  complete_inner fixture (child "long" report) long_rna false;
  complete_inner fixture (child "short" report) short_rna false;
  let ranked=eighteen |> change_row "short" (replace "rank" (Json.int 0))
    |> change_row "long" (replace "rank" (Json.int 1)) in
  ignore (accepted ranked proposed limits "short" short_rna (check ranked proposed limits));
  let tied=eighteen |> change_row "short" (replace "rank" (Json.int 0)) in
  ignore (accepted tied long limits "long" long_rna (check tied long limits));
  (* Distinct IDs may retain identical child originals: the declared ASCII tie
     must not depend on request order, candidate order or material equality. *)
  let shared=get "request" (child "short" original) and material=get "candidate" (child "short" proposed) in
  let identical=replace "alternatives" (arr (List.map (fun id -> obj ["id",str id;"rank",Json.int 0;"request",shared]) ["z";"A"])) original in
  let identical_candidate=obj ["schema_version",get "schema_version" proposed;
    "alternatives",arr (List.map (fun id -> obj ["id",str id;"candidate",material]) ["z";"A"]);"selected_id",str "A"] in
  ignore (accepted identical identical_candidate limits "A" short_rna (check identical identical_candidate limits));
  List.iter (fun (source,candidate) ->
    let report=accepted source candidate limits "short" short_rna (check source candidate limits) in
    require (get "invocation_fingerprint" report<>get "invocation_fingerprint" first &&
      List.map (get "id") (items "alternatives" report)=[str "long";str "short"])
      "Permutation lost its original identity or changed checking order")
    [reverse original,proposed;original,reverse proposed;reverse original,reverse proposed];
  List.iter (fun winner ->
    let report=no_token "proposed_winner_mismatch" (check original (replace "selected_id" winner proposed) limits) in
    require (get "selected_id" report=str "short" && get "winner_matches" report=Json.Bool false &&
      get "all_inner_accepted" report=Json.Bool true)
      "Wrong or null proposal overrode the independently computed winner") [str "long";Json.Null]

let controls original proposed limits=
  (* A corrupt losing molecule retains its structural subject pin, so failure
     must come from fresh correspondence instead of decoder shape rejection. *)
  let changed_material candidate=
    let molecule=at ["construction";"inventory";"molecules";"0"] candidate
      |> replace "sequence" (str "AGCAUGGCUUAAGGAAAA") in
    candidate |> put ["construction";"inventory";"molecules";"0"] molecule
      |> put ["construction";"inventory";"role_instances";"0";"subject_fingerprint"]
        (str (Canonical.fingerprint molecule)) in
  let bad=change_candidate "long" changed_material proposed in
  let request,candidate,decoded_limits=decode original bad limits in
  let report=no_token "inner_not_accepted" (Check.check ~request ~candidate ~limits:decoded_limits) in
  require (List.map (get "id") (items "alternatives" report)=[str "long";str "short"] &&
    at ["inner";"status"] (child "long" report)=str "not_accepted" &&
    at ["inner";"status"] (child "short" report)=str "checked_component_material" &&
    get "eligible" (child "long" report)=Json.Null && get "eligible" (child "short" report)=Json.Bool true &&
    get "selected_id" report=Json.Null && get "winner_matches" report=Json.Null)
    "Failed losing child was excluded by length or prevented visiting the returned succeeding child";
  let reject code label source candidate limits=
    let request,candidate,limits=decode source candidate limits in
    rejected code label (fun () -> Check.check ~request ~candidate ~limits) in
  reject "policy_implementation_source_binding" "Wrong feedback on an ineligible loser cannot authorize another winner"
    original (change_candidate "long" (put ["binding";"effects";"0";"feedback"] (str "wrong_feedback")) proposed) limits;
  reject "policy_component_selection_common" "A weaker losing source assurance is not a material alternative"
    (change_request "long" (put ["implementation_request";"document";"assurance";"horizon";"amount"] (str "5")) original)
    proposed limits;
  let incomplete=put ["monitor";"max_work"] (Json.int 1) limits in
  let report=no_token "inner_not_accepted" (check original proposed incomplete) in
  require (List.length (items "alternatives" report)=2 && get "census_complete" report=Json.Bool true &&
    get "all_inner_accepted" report=Json.Bool false &&
    List.for_all (fun row -> at ["inner";"preservation";"status"] row=str "incomplete" &&
      get "total_nt" row=Json.Null && get "eligible" row=Json.Null) (items "alternatives" report))
    "Exhausted child exploration became eligibility or silently skipped another child";
  reject "policy_component_selection_work_limit" "Initial selection decoding cannot ignore its declared work"
    (put ["budgets";"max_work"] (Json.int 1) original) proposed limits;
  reject "policy_component_selection_work_limit" "Two full child allowances need outer overhead and cannot refund unused work"
    (put ["budgets";"max_work"] (Json.int 1000000000) original) proposed limits;
  reject "policy_component_material_work_limit" "Insufficient complete child work cannot mint a selection token"
    (every_request (put ["budgets";"max_work"] (Json.int 1)) original) proposed limits;
  List.iter (fun field ->
    reject "policy_component_selection_publication_limit" ("Outer full publication bound: "^field)
      (put ["budgets";field] (Json.int 1) original) proposed limits;
    reject "policy_component_material_publication_limit" ("Child full publication bound: "^field)
      (every_request (put ["budgets";field] (Json.int 1)) original) proposed limits)
    ["max_report_bytes";"max_report_nodes"];
  let reordered=change_candidate "long" (edit ["construction";"inventory";"molecules";"0";"features"]
    (fun raw -> arr (List.rev (Json.array raw)))) proposed in
  let request,normalized,decoded_limits=decode original reordered limits in
  let original_candidate=V.of_json ~request proposed in
  let content value=List.find (fun (row:V.alternative) -> row.id="long") (V.alternatives value)
    |> fun row -> CV.construction row.candidate |> K.to_json in
  require (V.fingerprint normalized<>V.fingerprint original_candidate &&
    Json.equal (content normalized) (content original_candidate))
    "Raw/typed identity control must retain a distinct raw spelling of the same neutral construction";
  rejected "policy_component_selection_identity" "A differently normalized raw child cannot acquire a token for another fingerprint"
    (fun () -> Check.check ~request ~candidate:normalized ~limits:decoded_limits);
  let request,candidate,decoded_limits=decode original proposed limits in
  let changed=R.of_json (put ["predicate";"max_total_nt"] (Json.int 18) original) in
  require (R.fingerprint request<>R.fingerprint changed) "Changed-original token binding control is vacuous";
  rejected "policy_component_selection_identity" "Previously decoded candidate cannot transfer to another complete original"
    (fun () -> Check.check ~request:changed ~candidate ~limits:decoded_limits)

let ()=
  try
    require (Array.length Sys.argv=2) "Supply the independent A original fixture";
    let fixture=read Sys.argv.(1) in
    let original=Originals.selection_literal fixture and limits=get "limits" fixture in
    let proposed=candidate_raw original limits in
    positives fixture original proposed limits;controls original proposed limits;
    Printf.printf "component selection check: %d independent winner/material/failure controls passed\n" !checks
  with Diagnostic.Error value ->
    Printf.eprintf "Diagnostic.Error(code=%s,path=%s,message=%s)\n" value.code
      (Option.value ~default:"<none>" value.path) value.message;exit 1
