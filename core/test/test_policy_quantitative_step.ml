open Bioc_wire
module R = Bioc_domain.Policy_realization_request
module M = Bioc_domain.Policy_component_material_request
module O = Bioc_domain.Policy_operational
module I = Bioc_domain.Policy_implementation
module F = Bioc_domain.Policy_operating_domain
module Q = Bioc_domain.Policy_quantitative_contract
module K = Bioc_domain.Construction_content
module U = Bioc_domain.Policy_component_assembly_proposal
module Library = Bioc_domain.Policy_component_library
module Rule = Bioc_domain.Policy_component_assembly_rule
module Context = Bioc_domain.Policy_component_context
module RA = Bioc_checker.Policy_realization_admission
module B = Bioc_checker.Policy_implementation_binding_check
module Binding = Bioc_domain.Policy_implementation_binding
module S = Bioc_semantics.Policy_domain_reference
module Runtime = Bioc_candidate_runtime.Policy_primitives
module T = Bioc_realization_checker.Policy_trace_correspondence
module P = Bioc_realization_checker.Policy_preservation_check
module A = Bioc_realization_checker.Policy_component_assembly_check
module C = Bioc_realization_checker.Policy_component_context_check
module Check = Bioc_realization_checker.Policy_component_material_check
module Quant = Bioc_realization_checker.Policy_quantitative_check
module Outcome = Bioc_domain.Construction_assessment
module Material = Bioc_service.Policy_component_material_service
module Service = Bioc_service.Service
module Producer = Bioc_producer_service.Producer_service

let ()=Printexc.register_printer(function
  |Diagnostic.Error d->Some(Printf.sprintf "Diagnostic.Error(%s, %s)" d.code d.message)
  |_->None)
let s value=Json.String value
let o fields=Json.Object fields
let a values=Json.Array values
let get key value=Json.field key(Json.object_fields value)
let rows key value=Json.array(get key value)
let text key value=Json.string(get key value)
let rec at path value=match path with []->value|key::rest->at rest(get key value)
let set key item value=o(List.map(fun(name,value)->name,if name=key then item else value)(Json.object_fields value))
let remove key value=o(List.filter(fun(name,_)->name<>key)(Json.object_fields value))
let rec edit path f value=match path with []->f value|key::rest->set key(edit rest f(get key value))value
let require condition message=if not condition then failwith message
let accepted label=function Some value->value|None->failwith(label^" withheld its checked capability")
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_artifact ~max_bytes:(8*1024*1024) ~max_nodes:400000(really_input_string channel(in_channel_length channel)))
let call handler role operation payload=
  let request:Protocol.request={request_id="quantitative-literal";operation;payload}in
  match handler role request with
  |Protocol.Ok,Some result,[]->result
  |_,_,diagnostics->failwith(operation^": "^String.concat "; "(List.map(fun(d:Diagnostic.t)->d.code^": "^d.message)diagnostics))
let controls=ref 0
let rejects label action=match action()with
  |_->failwith("Quantitative adversary accepted: "^label)
  |exception Diagnostic.Error _->incr controls
let rejected_service label operation payload=
  let request:Protocol.request={request_id="quantitative-mutant";operation;payload}in
  match Service.handle Protocol.Verify request with
  |Protocol.Error,None,(_::_)->incr controls
  |_->failwith("Quantitative service adversary accepted: "^label)
  |exception Diagnostic.Error _->incr controls
let table_row source input destination request=o[
  "source",s source;"input",s input;"destination",s destination;"request",Json.Bool request]

(* Independent sampled-step oracle and complete source/component/material checks.
   This suite intentionally does not invoke a quantitative authoring evaluator. *)
let source_bounds=S.execution_bounds_of_json(o(List.map(fun(k,v)->k,Json.int v)
  ["max_ticks",32;"max_inputs",1000;"max_encounters",4;"max_attempts",32;
   "max_work",8_000_000;"max_trace_items",100000;"max_microsteps",30]))
let initialize bound=
  let admitted=B.admitted_inputs bound and environment=B.environment bound in
  S.create ~behavior:(RA.behavior admitted) ~domain:(R.operating_domain(RA.request admitted)) ~bounds:source_bounds,
  Runtime.initialize ~implementation:(B.implementation bound)
    ~environment:{Runtime.executor=environment.executor;horizon_ticks=environment.horizon_ticks;
      slots=List.map(fun(slot:B.slot)->{Runtime.slot_id=slot.identity;target=slot.target;start_tick=slot.start_tick})environment.slots}
    ~limits:{Runtime.max_work=20_000_000;max_events=200000;max_attempts=32;max_microsteps=30},T.create bound
let select source reset=
  let rec scan count sequence=
    require(count<100)"Quantitative literal selection exceeded its independent search bound";
    match sequence()with
    |Seq.Nil->failwith "Original finite domain lacks the handwritten quantitative witness"
    |Seq.Cons(value,rest)->
      if List.for_all(fun(_,action)->action=(if reset && value.F.tick=12 then F.Reset else F.Keep))value.lifecycle
      then value else scan(count+1)rest in
  scan 0(S.choices source)
let expected_state reset tick=
  "q" ^ string_of_int(List.nth (if reset then
    [0;2;4;4;3;2;2;1;3;4;4;3;0;2;4;3;3]
    else [0;2;4;4;3;2;2;1;3;4;4;3;2;4;4;3;3]) tick)
let selected_trace bound reset=
  let source,runtime,correspondence=initialize bound in
  let created=ref 0 in
  let rec loop source runtime correspondence=
    if S.finished source then correspondence else
    let batch=select source reset in
    let runtime,frame=Runtime.step runtime(T.input correspondence batch)in
    let advanced=match S.step source batch with S.Advanced value->value
      |S.Stopped stopped->failwith("Quantitative literal source stopped: "^stopped.diagnostic.code)in
    let matched=T.advance correspondence ~batch ~source_frame:advanced.frame
      ~source_attempts:(rows "attempts"(Option.get advanced.receipt.execution))
      ~source_creations:advanced.creations ~candidate:frame in
    let expected=expected_state reset frame.tick in
    List.iter(fun slot->
      let machine=List.find(fun(value:Runtime.machine_snapshot)->value.binding.slot=Some slot)frame.machines in
      require(machine.state=expected && machine.binding.generation=(if reset && frame.tick>=12 then 1 else 0))
        ("Literal quantitative candidate state/generation differs at "^string_of_int frame.tick);
      let source_machine=List.find(fun row->at["binding";"encounter"]row=s slot)(rows "machines" advanced.frame)in
      require(get "state" source_machine=s expected)
        "Literal quantitative source state differs from the independent amount trajectory")["e1";"e2"];
    let new_requests=if frame.tick=2 || frame.tick=8 || frame.tick=(if reset then 14 else 13) then 2 else 0 in
    require(List.length frame.creations=new_requests && List.length advanced.creations=new_requests)
      "Threshold crossing created missing or extra abstract effect attempts";
    created:= !created+List.length frame.creations;
    let expected_initiator=if frame.tick=8 then "up1" else "up2"in
    List.iter(fun(attempt:Runtime.attempt)->
      let transition=List.find(fun(value:B.transition)->value.gate=attempt.gate)(B.transitions bound)in
      require(transition.source=expected_initiator)
        "Shared effect bank lost the actual initiating transition identity")frame.creations;
    if frame.tick=3 then (
      require(frame.creations=[] && List.length(List.filter(fun(value:Runtime.attempt)->
        value.status=Runtime.Active && value.authorization=I.Unknown)frame.attempts)=2)
        "Unknown sample cancelled old active attempts or created a new request";
      require(List.length(List.filter(fun(event:Runtime.event)->event.kind=Runtime.Primitive_event I.Updated)frame.events)=2)
        "Unknown sample lost its update event");
    if frame.tick=6 then require(not(List.exists(fun(event:Runtime.event)->
      event.kind=Runtime.Primitive_event I.Updated)frame.events) && frame.creations=[])
        "No-update interval produced a quantitative sample step";
    loop advanced.next runtime matched in
  let matched=loop source runtime correspondence in
  require(!created=6 && text "claim"(T.report matched)="matched_prefix_only")
    "Selected quantitative trace changed request count or broadened its prefix scope"

(* Repin the complete independently supplied local contract and every direct
   selected-component/rule reference. These mutants are not stale-hash tests. *)
let refresh_context request=
  let layout=Canonical.fingerprint(at["context";"record_layout"]request)in
  edit["context";"providers"](fun providers->a(List.map(fun provider->
    let body=get "body" provider in
    let body=if text "kind" body="environment" then
      set "grammar"(at["implementation_request";"operating_domain"]request)body else body in
    let body=edit["capacities"](fun capacities->a(List.map(fun capacity->
      set "record_layout_digest"(s layout)capacity)(Json.array capacities)))body in
    provider|>set "body" body|>edit["identity";"content_fingerprint"](fun _->s(Canonical.fingerprint body)))
    (Json.array providers)))request
let change_contract request change=
  let selected=at["quantitative";"selection";"component"]request in
  let components=rows "components"(get "component_library" request)in
  let component=List.find(fun value->Json.equal(get "identity" value)selected)components in
  let body=edit["quantitative_contracts"](fun values->a(List.map change(Json.array values)))(get "body" component)in
  let identity=set "content_fingerprint"(s(Canonical.fingerprint body))(get "identity" component)in
  let component=component|>set "body" body|>set "identity" identity in
  let selected_rows values=a(List.map(fun value->
    if Json.equal(get "component" value)selected then set "component" identity value else value)(Json.array values))in
  let rule=get "composition_rule" request|>edit["body";"components"]selected_rows in
  let rule=set "identity"(set "content_fingerprint"(s(Canonical.fingerprint(get "body" rule)))(get "identity" rule))rule in
  let request=request|>edit["component_library";"components"](fun _->a(List.map(fun value->
      if Json.equal(get "identity" value)selected then component else value)components))
    |>set "composition_rule" rule
    |>edit["catalog_binding";"components"]selected_rows
    |>edit["catalog_binding";"rule"](fun _->get "identity" rule)
    |>edit["quantitative";"selection";"component"](fun _->identity)
    |>edit["context";"record_layout";"rule"](fun _->get "identity" rule)in
  (* Complete capacity records pin the whole record layout, which in turn pins
     the original rule. Provider references are unchanged DefinitionRefs; each
     changed supplied provider Model identity must nevertheless be refreshed. *)
  refresh_context request
let candidate_for request candidate=
  edit["assembly_proposal";"rule"](fun _->at["composition_rule";"identity"]request)candidate
let quant_check preservation request candidate=
  let request=M.of_json request in
  let assembly=A.check ~original:(M.implementation_request request) ~components:(M.component_library request)
    ~rule:(M.composition_rule request) ~implementation:preservation
    ~proposed:(U.of_json(get "assembly_proposal" candidate))
    ~candidate:(K.of_json(get "construction" candidate))() in
  let assembly=accepted "Fresh repinned assembly"(A.accepted assembly)in
  let context=C.check ~request ~assembly () in
  let context=accepted "Fresh repinned context"(C.accepted context)in
  Quant.check ~request ~context ()
let quantitative_failure preservation label request candidate=
  let result=quant_check preservation request(candidate_for request candidate)in
  require(Quant.accepted result=None && Quant.outcome result=Outcome.Fail &&
    get "table"(Quant.report result)=a[])
    ("Quantitative semantic mutant did not fail at the quantitative checker: "^label);
  incr controls

(* Grid spacing one, rise two, fall one, threshold three. These literal rows
   exercise both distinct crossing sites and both saturation boundaries. *)
let expected_table=a[
  table_row "q0" "true" "q2" false;table_row "q0" "false" "q0" false;table_row "q0" "unknown" "q0" false;
  table_row "q1" "true" "q3" true;table_row "q1" "false" "q0" false;table_row "q1" "unknown" "q1" false;
  table_row "q2" "true" "q4" true;table_row "q2" "false" "q1" false;table_row "q2" "unknown" "q2" false;
  table_row "q3" "true" "q4" false;table_row "q3" "false" "q2" false;table_row "q3" "unknown" "q3" false;
  table_row "q4" "true" "q4" false;table_row "q4" "false" "q3" false;table_row "q4" "unknown" "q4" false]

let ()=
  require(Array.length Sys.argv=2)"Expected independent sampled-step originals";
  let fixture=read Sys.argv.(1)in
  require(text "schema_version" fixture="biocompiler.policy_quantitative_step_literals.v0.1")
    "Wrong sampled-step fixture schema";
  require(Json.equal(at["expected";"table"]fixture)expected_table)
    "Sampled-step fixture disagrees with the handwritten complete table";
  let request=get "request" fixture and limits=get "limits" fixture in
  let original=M.of_json request in
  require(M.is_multi_site original && M.is_finite_machine original && M.is_quantitative original)
    "Sampled-step profile lost its explicit multi-site quantitative family";
  let produced=call Producer.handle Protocol.Core "compile-policy-component-material"
    (o["request",request;"limits",limits])in
  let candidate=get "candidate" produced in
  let _,result=Material.fresh_check ~request ~candidate ~limits in
  let checked=accepted "Complete sampled-step material"(Check.accepted result)in
  let report=Check.report result and contextual=Check.context checked in
  let preservation=A.implementation(C.assembly contextual)in
  let bound=P.binding preservation in
  let quantitative=Quant.check ~request:original ~context:contextual ()in
  let summary=Quant.report quantitative in
  require(Quant.outcome quantitative=Outcome.Pass && Option.is_some(Quant.accepted quantitative) &&
    Json.equal summary(get "quantitative" report) && Json.equal(get "table" summary)expected_table &&
    get "schema_version" summary=s "biocompiler.policy_quantitative_assessment.v0.2" &&
    get "profile" summary=s "biocompiler.policy_sampled_saturating_step_reservoir.v0.1" &&
    get "empirical" summary=s "unassessed")"Fresh sampled-step evidence changed its exact law or claim boundary";
  let sites=rows "crossing_sites"(get "bindings" summary)in
  require(List.map(text "transition")sites=["up1";"up2"] &&
    List.map(text "source_state")sites=["q1";"q2"] &&
    List.map(text "attempt_port")sites=["request0";"request1"] &&
    List.for_all(fun row->get "input" row=Json.Bool true && at["request_endpoint";"port"]row=s "request0")sites)
    "Sampled-step evidence omitted, reordered or misbound a crossing request site";
  let effect_value=List.hd(B.effects bound)in
  require(List.length(B.effects bound)=1 && List.map(fun(value:B.effect_site)->value.initiating_rule)effect_value.request_sites=["up1";"up2"] &&
    at["bindings";"attempt_bank"]summary=s effect_value.bank)
    "Repeated crossings were split into independent effects or attempt banks";
  selected_trace bound false;
  selected_trace bound true;
  let bound_graph=get "implementation" candidate in
  let check_graph raw=B.check ~admitted:(B.admitted_inputs bound)
    ~implementation:(I.of_json ~library:(R.implementation_library(M.implementation_request original))raw)
    ~proposed:(Binding.of_json(get "binding" candidate))in
  let bank_port name endpoint=text "node" endpoint=effect_value.bank && text "port" endpoint=name in
  rejects "crossing commits swapped between actual request ports"(fun()->check_graph
    (edit["wires"](fun wires->a(List.map(fun wire->let consumer=get "consumer" wire in
      if bank_port "request0" consumer then set "consumer"(set "port"(s "request1")consumer)wire
      else if bank_port "request1" consumer then set "consumer"(set "port"(s "request0")consumer)wire else wire)
      (Json.array wires)))bound_graph));
  rejects "omitted second request site wire"(fun()->check_graph
    (edit["wires"](fun wires->a(List.filter(fun wire->not(bank_port "request1"(get "consumer" wire)))
      (Json.array wires)))bound_graph));
  let downward=List.find(fun(value:B.transition)->value.source="down1")(B.transitions bound)in
  let negative_guard=List.find(fun(wire:I.wire)->wire.consumer.node_id=downward.gate && wire.consumer.port_id="guard")
    (I.wires(B.implementation bound))in
  let wrong_guard=o["node",s negative_guard.producer.node_id;"port",s negative_guard.producer.port_id]in
  rejects "request site authorization detached from initiating guard"(fun()->check_graph
    (edit["wires"](fun wires->a(List.map(fun wire->if bank_port "authorization1"(get "consumer" wire)
      then set "producer" wrong_guard wire else wire)(Json.array wires)))bound_graph));
  let law=at["quantitative";"mechanism"]request in
  List.iter(fun(label,path,value)->rejects label(fun()->Q.of_json(edit path(fun _->value)law)))
    ["zero rise",["rise";"amount"],s "0";"negative fall",["fall";"amount"],s "-1";
     "off-grid rise",["rise";"amount"],s "1.5";"rise above capacity",["rise";"amount"],s "5";
     "binary float rise",["rise";"amount"],Json.Float 2.;
     "nominal fall unit mutation",["fall";"unit";"id"],s "other"];
  let component=List.find(fun row->Json.equal(get "identity" row)(at["quantitative";"selection";"component"]request))
    (rows "components"(get "component_library" request))in
  let local=List.hd(rows "quantitative_contracts"(get "body" component))in
  rejects "empty output inventory"(fun()->Q.local_of_json(set "outputs"(a[])local));
  rejects "duplicate output source"(fun()->Q.local_of_json(edit["outputs"](fun values->
    let first=List.hd(Json.array values)in a[first;first])local));
  rejects "legacy local output spelling"(fun()->Q.local_of_json(local|>remove "outputs"|>set "output"
    (o["boundary",s "crossing";"model",at["state";"model"]local])));
  rejects "legacy material route consumes step contracts"(fun()->M.of_json(request
    |>set "schema_version"(s M.quantitative_schema_version)|>set "profile"(s M.quantitative_profile)));
  rejects "zero quantitative work"(fun()->Quant.check ~maximum:0 ~request:original ~context:contextual ());
  let change_outputs f=change_contract request(edit["outputs"](fun rows->a(f(Json.array rows))))in
  quantitative_failure preservation "omitted second crossing"(change_outputs(fun values->[List.hd values]))candidate;
  quantitative_failure preservation "reordered crossing rows"(change_outputs List.rev)candidate;
  quantitative_failure preservation "wrong crossing polarity"(change_outputs(fun values->
    List.mapi(fun index row->if index=0 then set "input"(Json.Bool false)row else row)values))candidate;
  quantitative_failure preservation "wrong crossing commit model"(change_outputs(fun values->
    List.mapi(fun index row->if index=0 then set "model"(at["state";"model"]local)row else row)values))candidate;
  quantitative_failure preservation "swapped real crossing boundaries"(change_outputs(function
    |[first;second]->[set "boundary"(get "boundary" second)first;set "boundary"(get "boundary" first)second]
    |_->failwith "Expected two independently supplied crossing boundaries"))candidate;
  let wrong_law=edit["quantitative";"mechanism";"rise";"amount"](fun _->s "1")request in
  quantitative_failure preservation "original/component law mismatch" wrong_law candidate;
  let both_laws=change_contract wrong_law(edit["mechanism";"rise";"amount"](fun _->s "1"))in
  quantitative_failure preservation "repinned coherent law changes actual source table" both_laws candidate;
  let _,bad=Material.fresh_check ~request:both_laws ~candidate:(candidate_for both_laws candidate) ~limits in
  require(Check.accepted bad=None && at["quantitative";"outcome"](Check.report bad)=s "fail" &&
    get "all_original_obligations_discharged"(Check.report bad)=Json.Bool false)
    "Quantitative contradiction acquired a complete material capability";
  incr controls;
  let invocation=o["request",request;"candidate",candidate;"limits",limits]in
  let replayed=call Service.handle Protocol.Verify "replay-policy-component-material"
    (o["request",request;"candidate",candidate;"limits",limits;"report",produced])in
  require(Json.equal replayed produced)"Fresh sampled-step replay changed the full wrapper";
  let exported=call Service.handle Protocol.Verify "export-policy-component-material" invocation in
  let artifact=get "artifact" exported and expected=get "expected" fixture in
  require(at["construction";"inventory";"molecules"]candidate=a[get "molecule" expected] &&
    get "fasta" artifact=s(">rna_0001 alphabet=RNA\n"^text "sequence" expected^"\n"))
    "Sampled-step source/effect correspondence lost exact declared RNA identity";
  let manifest=get "manifest" artifact in
  require(Json.equal(get "request" manifest)request && Json.equal(get "candidate" manifest)candidate &&
    Json.equal(get "assessment" manifest)report &&
    get "manifest_sha256" artifact=s(Canonical.sha256(Canonical.encode manifest)))
    "Sampled-step export omitted exact authority or complete quantitative checking";
  let named=call Service.handle Protocol.Verify "check-policy-refinement" invocation in
  require(Json.equal(at["material_report";"quantitative"]named)summary)
    "Named refinement erased the complete multiple-crossing law evidence";
  rejected_service "saved PASS cannot substitute fresh work" "replay-policy-component-material"
    (o["request",request;"candidate",candidate;"limits",edit["max_step_work"](fun _->Json.int 1)limits;"report",produced]);
  let tampered=edit["report";"quantitative";"bindings";"crossing_sites"](fun values->a(List.rev(Json.array values)))produced in
  rejected_service "saved crossing order mutation" "replay-policy-component-material"
    (o["request",request;"candidate",candidate;"limits",limits;"report",tampered]);
  require(!controls=24)"Sampled-step rejection census is incomplete";
  Printf.printf "policy_quantitative_step: exact 15-row law, two distinct retained request sites, reset and RNA export, %d rejection controls\n" !controls
