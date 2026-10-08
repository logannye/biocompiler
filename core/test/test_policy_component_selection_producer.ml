open Bioc_wire
open Bioc_policy_component_test_support.Literals
module Originals=Bioc_policy_component_test_support.Selection_requests
module R=Bioc_domain.Policy_component_selection_request
module CR=Bioc_domain.Policy_component_material_request
module C=Bioc_domain.Policy_component_material_candidate
module I=Bioc_domain.Policy_realization_request
module K=Bioc_domain.Construction_content
module N=Bioc_domain.Molecule
module S=Bioc_service.Policy_component_selection_service
module Dispatch=Bioc_producer_service.Producer_service
module Child=Bioc_producer_service.Policy_component_material_producer
module Producer=Bioc_producer_service.Policy_component_selection_producer

let protocol operation payload:Protocol.request={request_id="literal.generated.selection";operation;payload}
let input original limits=obj ["request",original;"limits",limits]
let check_input original candidate limits=obj ["request",original;"candidate",candidate;"limits",limits]
let frame executable request result=Protocol.response ~executable ~request:(Some request)
  ~status:Protocol.Ok ~result:(Some result) []
let call role operation payload=
  let request=protocol operation payload in
  match Dispatch.scoped_handle role request with
  |None->failwith "Expected mandatory scoped operation"
  |Some reply->
      let result=Option.get reply.result in
      require (reply.status=Protocol.Ok && reply.diagnostics=[]) "Invalid generated reply";
      reply.before_encode (frame role request result);result
let compile original limits=call Protocol.Core S.producer_operation (input original limits)
let verify original candidate limits=call Protocol.Verify "check-policy-component-selection" (check_input original candidate limits)
let original fixture maximum=Originals.selection_literal ~max_total_nt:maximum fixture
  |> put ["budgets";"profile"] (str "biocompiler.policy_component_selection_resources.v0.2")
  |> put ["budgets";"max_report_nodes"] (Json.int 1000000)
let sequence original row=
  let id=get "id" row in
  let source=List.find (fun value->get "id" value=id) (items "alternatives" original) in
  let request=CR.of_json (get "request" source) in
  let candidate=C.of_json ~library:(I.implementation_library (CR.implementation_request request)) (get "candidate" row) in
  match K.inventory (C.construction candidate) with
  |Some value->(match K.Inventory.molecules value with [molecule]->N.sequence molecule|_->failwith "Expected one RNA")
  |None->failwith "Expected complete candidate inventory"
let generation_controls fixture limits=
  List.iter (fun (maximum,winner) ->
    let original=original fixture maximum in
    let generated=compile original limits in
    let candidate=get "candidate" generated in
    require (get "artifact" generated=Json.Null) "Compile must not export";
    require (get "selected_id" candidate=winner && at ["report";"selected_id"] generated=winner)
      "Generation did not propose the independently expected length/rank winner";
    require (List.map (get "id") (items "alternatives" candidate)=[str "long";str "short"])
      "Generation omitted a loser or failed ASCII ordering";
    List.iter (fun row ->
      let expected=if get "id" row=str "short" then "CCAUGGCUUAAGGAAAA" else "CGCAUGGCUUAAGGAAAA" in
      require (sequence original row=expected) "Generated RNA differs from independent literal") (items "alternatives" candidate);
    require (Json.equal generated (verify original candidate limits))
      "Generation result differs from fresh independent Verify result") [17,str "short";18,str "long";1,Json.Null];
  let original=original fixture 17 in
  let generated=compile original limits in
  let reversed=edit ["alternatives"] (fun values->arr (List.rev (Json.array values))) original in
  let reordered=compile reversed limits in
  require (Json.equal (get "candidate" generated) (get "candidate" reordered) &&
    get "request_fingerprint" generated<>get "request_fingerprint" reordered)
    "Permutation must retain deterministic generated candidates and distinct original identity";
  rejected "policy_component_selection_replay" "Changed original order cannot reuse a generated wrapper"
    (fun ()->call Protocol.Verify "replay-policy-component-selection"
      (add "report" generated (check_input reversed (get "candidate" reordered) limits)));
  let typed=R.of_json original in
  let total=ref 0 and calls=ref 0 in
  let produced=Producer.produce ~charge:(fun n->incr calls;total:= !total+n) typed in
  require (!calls>0 && !total>0 && Json.equal produced (get "candidate" generated))
    "Generation meter changes the candidate or does not observe work";
  List.iter (fun cutoff ->
    let spent=ref 0 in
    rejected "literal_generation_exhaustion" "Early and late generation failures are terminal"
      (fun ()->Producer.produce ~charge:(fun n->
        if n>cutoff- !spent then Diagnostic.fail "literal_generation_exhaustion" "Original outer meter exhausted";
        spent:= !spent+n) typed)) [0; !total/2; !total-1];
  List.iter (fun (row:R.alternative) ->
    let metered=Child.construct_candidate ~charge:(fun _->()) row.request in
    let legacy=Child.compile (input (CR.to_json row.request) limits) in
    require (Json.equal metered (Child.construct_candidate row.request) && Json.equal metered (get "candidate" legacy))
      "Candidate-only factoring changes legacy child bytes") (R.alternatives typed);
  original,get "candidate" generated

let scope_controls original candidate limits=
  let request=protocol S.producer_operation (input original limits) in
  let callback_calls=ref 0 in
  rejected "unsupported_operation" "Verify cannot invoke a generated callback"
    (fun ()->S.prepare_generated ~executable:Protocol.Verify ~request
      ~produce:(fun ~charge:_ _->incr callback_calls;candidate));
  require (!callback_calls=0) "Verify called a producer";
  rejected "policy_component_selection_outer_work_limit" "Caught generation exhaustion poisons later checking"
    (fun ()->S.prepare_generated ~executable:Protocol.Core ~request
      ~produce:(fun ~charge _->(try charge 1000000001 with Diagnostic.Error _->());candidate));
  let small=put ["budgets";"max_work"] (Json.int 10000) original in
  rejected "policy_component_selection_work_limit" "Original smaller total bounds generation and checking"
    (fun ()->compile small limits);
  let prepared,guard=S.prepare_generated ~executable:Protocol.Core ~request ~produce:Producer.produce in
  guard (frame Protocol.Core request prepared);
  rejected "policy_component_selection_scope" "Generated actual-frame guard is one shot"
    (fun ()->guard (frame Protocol.Core request prepared));
  let called=ref false in
  let malformed=protocol S.producer_operation (add "candidate" candidate (input original limits)) in
  (match S.prepare_generated ~executable:Protocol.Core ~request:malformed
      ~produce:(fun ~charge:_ _->called:=true;candidate) with
   |_->failwith "Compile accepted a supplied candidate field"
   |exception Diagnostic.Error _->());
  require (not !called) "Malformed compile envelope reached generation"

let capabilities ()=
  List.iter (fun role ->
    let _,result,_=Dispatch.handle role (protocol "capabilities" (obj [])) in
    let result=Option.get result in
    require (List.mem (str S.producer_operation) (items "operations" result)=(role=Protocol.Core))
      "Producer capability escaped Core or was withheld from Core";
    require (Json.equal (at ["profiles";"policy_component_selection"] result) S.profile)
      "Producer capability changes the independent verifier profile";
    let status,_,_=Dispatch.handle role (protocol S.producer_operation (obj [])) in
    require (status=Protocol.Unsupported) "Unguarded dispatch bypassed actual-frame admission") [Protocol.Core;Protocol.Verify]

let ()=
  try
    require (Array.length Sys.argv=2) "Supply independent original fixture";
    let fixture=read Sys.argv.(1) in
    let limits=get "limits" fixture in
    capabilities ();
    let original,candidate=generation_controls fixture limits in
    scope_controls original candidate limits;
    Printf.printf "selection producer: %d candidate/preservation/generation/owner controls passed\n" !checks
  with Diagnostic.Error value ->
    Printf.eprintf "Diagnostic.Error(%s): %s\n" value.code value.message;exit 1
