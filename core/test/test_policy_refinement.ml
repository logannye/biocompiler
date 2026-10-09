open Bioc_wire
module N = Bioc_domain.Policy_refinement
module R = Bioc_domain.Policy_realization_request
module M = Bioc_domain.Policy_component_material_request
module RA = Bioc_checker.Policy_realization_admission
module B = Bioc_checker.Policy_implementation_binding_check
module P = Bioc_realization_checker.Policy_preservation_check
module A = Bioc_realization_checker.Policy_component_assembly_check
module C = Bioc_realization_checker.Policy_component_context_check
module Check = Bioc_realization_checker.Policy_component_material_check
module E = Bioc_realization_checker.Policy_refinement_check
module Material = Bioc_service.Policy_component_material_service
module Service = Bioc_service.Service
module Producer = Bioc_producer_service.Producer_service

let () = Printexc.register_printer(function
  | Diagnostic.Error d -> Some(Printf.sprintf "Diagnostic.Error(%s, %s)" d.code d.message)
  | _ -> None)
let s value=Json.String value
let o fields=Json.Object fields
let a values=Json.Array values
let get key value=Json.field key(Json.object_fields value)
let rows key value=Json.array(get key value)
let text key value=Json.string(get key value)
let rec at path value=match path with []->value|key::rest->at rest(get key value)
let set key item value=o(List.map(fun(name,value)->name,if name=key then item else value)(Json.object_fields value))
let rec edit path f value=match path with []->f value|key::rest->set key(edit rest f(get key value))value
let require condition message=if not condition then failwith message
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_artifact ~max_bytes:(8*1024*1024) ~max_nodes:400000(really_input_string channel(in_channel_length channel)))
let call handler role operation payload=
  let request:Protocol.request={request_id="refinement-literal";operation;payload}in
  match handler role request with
  |Protocol.Ok,Some result,[]->result
  |_,_,diagnostics->failwith(operation^": "^String.concat "; "(List.map(fun(d:Diagnostic.t)->d.code^": "^d.message)diagnostics))
let controls=ref 0
let rejects label action=match action()with
  |_->failwith("Refinement adversary accepted: "^label)
  |exception Diagnostic.Error _->incr controls
let rejected_service label operation payload=
  let request:Protocol.request={request_id="refinement-mutant";operation;payload}in
  match Service.handle Protocol.Verify request with
  |Protocol.Error,None,(_::_)->incr controls
  |_->failwith("Refinement service adversary accepted: "^label)
  |exception Diagnostic.Error _->incr controls
let accepted label = function Some value->value|None->failwith(label^" withheld its checked capability")
let relation_names evidence=List.map(fun(row:N.claim)->N.relation_name row.relation)(E.claims evidence)
let contains relation evidence=List.exists(fun(row:N.claim)->row.relation=relation)(E.claims evidence)
let decrement value=Json.int(int_of_string(Canonical.encode value)-1)

let () =
  require(Array.length Sys.argv=2)"Expected the independent finite-machine fixture";
  let fixture=read Sys.argv.(1)in
  let row=List.find(fun row->text "id" row="retry_cycle")(rows "cases" fixture)in
  let request=get "request" row and limits=get "limits" fixture in
  let produced=call Producer.handle Protocol.Core "compile-policy-component-material"
    (o["request",request;"limits",limits])in
  let candidate=get "candidate" produced in
  let _,result=Material.fresh_check ~request ~candidate ~limits in
  let checked=accepted "Complete original material" (Check.accepted result)in
  let unchanged=Canonical.encode(Check.evidence checked)in
  let context=Check.context checked in
  let assembly=C.assembly context in
  let preservation=A.implementation assembly in
  let binding=P.binding preservation in
  let admitted=B.admitted_inputs binding in
  let source=E.of_admission admitted and graph=E.of_binding binding
  and bounded=E.of_preservation preservation and material=E.of_assembly assembly
  and contextual=E.of_context context in
  require(relation_names source=["exact_source_occurrence"] &&
    relation_names graph=["source_graph_binding"] &&
    relation_names bounded=["bounded_observable_correspondence";"original_hard_requirements"])
    "Lower factories acquired claims beyond their checker capabilities";
  require((E.scope source).material_request_fingerprint=None &&
    (E.scope graph).limits_fingerprint=None &&
    (E.scope bounded).limits_fingerprint=Some(Canonical.fingerprint limits))
    "Stage-local identities were replaced by a mandatory material root";
  let exact=E.compose source graph in
  require(contains N.Exact_source_graph_correspondence exact &&
    not(contains N.Bounded_observable_correspondence exact))
    "Exact source/graph linkage acquired bounded behavioral claims";
  let behavior=E.compose exact bounded in
  let linked=E.compose behavior(E.conjoin[material;contextual])in
  require(contains N.Conditional_source_material_correspondence linked &&
    (E.scope linked).material_request_fingerprint=Some(Canonical.fingerprint request))
    "Bounded material chain lost its exact supplied material context";
  let evidence=E.of_material checked in
  require(relation_names evidence=[
    "exact_source_occurrence";"source_graph_binding";"bounded_observable_correspondence";
    "original_hard_requirements";"supplied_component_material_correspondence";
    "conditional_deployment_context";"complete_original_obligations";
    "exact_source_graph_correspondence";"bounded_source_observable_correspondence";
    "conditional_source_material_correspondence"])
    "Complete named relation census differs";
  require(List.length(E.premises evidence)=18 &&
    E.fingerprint evidence=Canonical.fingerprint(E.to_json evidence) &&
    Canonical.encode(Check.evidence checked)=unchanged)
    "Evidence changed the legacy report, complete premises or canonical identity";
  let endpoint stage=List.find_map(fun(row:N.claim)->
    if row.source.stage=stage then Some row.source.fingerprint else
    if row.target.stage=stage then Some row.target.fingerprint else None)(E.claims evidence)in
  List.iter(fun(stage,raw)->require(endpoint stage=Some(Canonical.fingerprint raw))
    "A named endpoint no longer binds the complete original/candidate artifact")
    [N.Source_document,at["implementation_request";"document"]request;
      N.Operational_behavior,get "behavior" candidate;N.Implementation_graph,get "implementation" candidate;
      N.Construction_content,get "construction" candidate;N.Deployment_context,get "context" request];
  rejects "reverse chain"(fun()->E.compose graph source);
  rejects "graph-only material promotion"(fun()->E.compose exact material);
  rejects "requirements-only chain"(fun()->E.compose bounded material);
  rejects "stage-compatible but unnamed self chain"(fun()->E.compose source source);
  rejects "empty conjunction"(fun()->E.conjoin[]);
  rejects "zero factory work"(fun()->E.of_material ~maximum:0 checked);
  rejects "zero conjunction work"(fun()->E.conjoin ~maximum:0 [source]);
  rejects "zero composition work"(fun()->E.compose ~maximum:0 source graph);
  rejects "excess input count"(fun()->E.conjoin(List.init(E.max_inputs+1)(fun _->source)));
  let rec cyclic_inputs=source::cyclic_inputs in
  rejects "cyclic native input spine"(fun()->E.conjoin cyclic_inputs);
  rejects "excess derivation depth"(fun()->
    let rec grow remaining value=if remaining=0 then value else grow(remaining-1)(E.conjoin[value])in
    grow E.max_depth source);
  (* Identical document, behavior and graph do not permit replacing the original
     budgets. Admission is sufficient to construct the alternate lower scope. *)
  let original=RA.request admitted in
  let changed_original=R.of_finite_machine_json(edit["budgets";"max_work"]decrement(R.to_json original))in
  let changed=RA.admit ~request:changed_original ~behavior:(RA.behavior admitted)in
  let other_source=E.of_admission changed in
  require((List.hd(E.claims other_source)).source=(List.hd(E.claims source)).source)
    "Budget mutant unexpectedly changed the source endpoint";
  rejects "same endpoint different request budgets"(fun()->E.compose other_source graph);
  rejects "different request conjunction"(fun()->E.conjoin[source;other_source]);
  let changed_domain=R.of_finite_machine_json(edit["operating_domain";"executor";"identity"]
    (fun _->s "cell-other")(R.to_json original))in
  let other_domain=E.of_admission(RA.admit ~request:changed_domain ~behavior:(RA.behavior admitted))in
  rejects "different original domain"(fun()->E.conjoin[source;other_domain]);
  (* Material-request budget changes retain all stage artifacts, but the final
     deployment proof must still belong to one complete original envelope. *)
  let other_request=M.of_json(edit["budgets";"max_work"]decrement request)in
  let other_context=accepted "Alternate context" (C.accepted(C.check ~request:other_request ~assembly ()))in
  rejects "same graph/content different material request"(fun()->E.conjoin[contextual;E.of_context other_context]);
  (* A fresh preservation invocation under different resource limits still
     passes the same semantic domain, but it is not the same scoped evidence. *)
  let other_limits=edit["max_step_work"]decrement limits in
  let other_preservation=P.check ~request:original ~behavior:(RA.behavior admitted)
    ~implementation:(B.implementation binding)
    ~proposed:(Bioc_domain.Policy_implementation_binding.of_json(get "binding" candidate))
    ~limits:(P.limits_of_json other_limits)in
  let other_bounded=E.of_preservation(accepted "Alternate complete limits" (P.accepted other_preservation))in
  rejects "same endpoint different checker limits"(fun()->E.conjoin[bounded;other_bounded]);
  let invocation=o["request",request;"candidate",candidate;"limits",limits]in
  let fresh=call Service.handle Protocol.Verify "check-policy-refinement" invocation in
  require(Json.equal(get "material_report" fresh)(Check.report result) &&
    Json.equal(get "evidence" fresh)(E.to_json evidence) &&
    get "material_report_fingerprint" fresh=s(Canonical.fingerprint(Check.report result)))
    "Service evidence was not derived from the exact fresh material check";
  require(Json.equal fresh(call Service.handle Protocol.Verify "replay-policy-refinement"
    (o["request",request;"candidate",candidate;"limits",limits;"report",fresh])))
    "Complete fresh named-evidence replay differs";
  let forged=edit["evidence";"claims"](fun value->a(List.map(fun claim->
    if text "relation" claim="conditional_source_material_correspondence"
    then edit["target";"fingerprint"](fun _->s(String.make 64 '0'))claim else claim)(Json.array value)))fresh in
  rejected_service "forged saved relation" "replay-policy-refinement"
    (o["request",request;"candidate",candidate;"limits",limits;"report",forged]);
  let incomplete=call Service.handle Protocol.Verify "check-policy-refinement"
    (edit["limits";"max_step_work"](fun _->Json.int 1)invocation)in
  require(get "evidence" incomplete=Json.Null && at["material_report";"status"]incomplete=s "not_accepted")
    "Incomplete original-domain checking produced named accepted evidence";
  incr controls;
  require(!controls>=18)"Named-refinement negative control census incomplete";
  Printf.printf "policy_refinement: ten scoped claims, eighteen retained premises, exact fresh replay, %d rejection controls\n" !controls
