open Bioc_wire
let ()=Printexc.register_printer(function
  |Diagnostic.Error value->Some(Printf.sprintf "Diagnostic.Error(code=%s, path=%s, message=%s)"
      value.code(Option.value ~default:"<none>" value.path)value.message)
  |_->None)
module R=Bioc_domain.Policy_material_request
module Q=Bioc_domain.Policy_realization_request
module F=Bioc_domain.Policy_operating_domain
module I=Bioc_domain.Policy_implementation
module U=Bioc_domain.Policy_implementation_binding
module C=Bioc_domain.Policy_material_contract
module Context=Bioc_domain.Policy_material_context
module K=Bioc_domain.Construction_content
module A=Bioc_checker.Policy_realization_admission
module B=Bioc_checker.Policy_implementation_binding_check
module S=Bioc_semantics.Policy_domain_reference
module P=Bioc_candidate_runtime.Policy_primitives
module T=Bioc_realization_checker.Policy_trace_correspondence
module V=Bioc_realization_checker.Policy_preservation_check
module L=Bioc_realization_checker.Policy_material_binding_check
module X=Bioc_realization_checker.Policy_material_context_check
module Check=Bioc_realization_checker.Policy_material_check
let checks=ref 0
let require condition message=incr checks;if not condition then failwith message
let get key raw=Json.field key(Json.object_fields raw)
let text key raw=Json.string(get key raw)
let items key raw=Json.array(get key raw)
let integer raw=Z.to_int(Json.integer raw)
let at keys raw=List.fold_left(fun value key->get key value)raw keys
let set key value raw=Json.Object((key,value)::List.remove_assoc key(Json.object_fields raw))
let str value=Json.String value
let arr values=Json.Array values
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_bounded ~max_bytes:8000000 ~max_nodes:400000(really_input_string channel(in_channel_length channel)))
let rejects code run=incr checks;match run()with
  |_->failwith("Compound near-neighbor escaped "^code)
  |exception Diagnostic.Error value->require(value.code=code)("Expected "^code^", received "^value.code)
let lower request=let original=R.implementation_request request in
  Bioc_compiler.Policy_lowering.lower(Bioc_checker.Policy_admission.admit
    ~document:(Q.document original) ~descriptors:(Q.definitions original))
let truth (frame:P.frame) node slot=
  let port=List.find(fun(port:P.port_value)->port.endpoint.node_id=node &&
    port.binding.slot=Some slot && port.binding.generation=0)frame.outputs in
  match port.signal with P.Truth value->value|_->failwith "Literal truth endpoint changed type"
let model_mutation original graph node model_id=
  let library=I.library_to_json(Q.implementation_library original)in
  let model=List.find(fun value->text "id"(get "identity" value)=model_id)(items "models" library)in
  set "nodes"(arr(List.map(fun value->if text "id" value=node then value
    |>set "model"(get "identity" model)|>set "configuration_digest"(get "configuration_digest" model)
    else value)(items "nodes" graph)))graph
let wire_mutation graph node port producer=
  set "wires"(arr(List.map(fun value->if at["consumer";"node"]value=str node &&
      at["consumer";"port"]value=str port then set "producer" producer value else value)(items "wires" graph)))graph
let endpoint node port=Json.Object["node",str node;"port",str port]
let resource_literals evidence=
  let actual=List.map(fun row->let owner=get "owner" row in
    (if text "kind" owner="layout"then"layout"else text "id" owner)^"."^text "unit" row^"."^text "scope" row,
    integer(get "quantity" row))(items "derived_demands" evidence)in
  let expected=["local.selected.truth_cells.per_encounter_slot",1;"local.excluded.truth_cells.per_encounter_slot",1;
    "local.evidence.evidence_records.per_encounter_slot",3;"local.select_edge.edge_history_cells.per_encounter_slot",1;
    "local.exclude_edge.edge_history_cells.per_encounter_slot",1;"layout.generation_counters.per_encounter_slot",1;
    "local.attempt.active_attempt_records.per_encounter_slot",8;"local.attempt.retained_correlation_records.per_executor",2;
    "local.attempt.timer_cells.per_encounter_slot",8;"local.evidence.timer_cells.per_encounter_slot",1;
    "layout.timer_cells.per_executor",1;"layout.control_event_records.per_executor",34;
    "condition.input_rows_per_tick.per_encounter_slot",1;"feedback.input_rows_per_tick.per_executor",2]in
  require(List.sort compare actual=List.sort compare expected)"Literal complete typed resource minima changed"
let undersized_reasons context binding=
  let raw=Context.to_json context in
  let layout=set "ordered_reason_slots"(Json.int 0)(get "record_layout" raw)in
  let providers=items "providers" raw|>List.map(fun provider->
    let body=get "body" provider in
    let capacities=items "capacities" body|>List.map(set "record_layout_digest"(str(Canonical.fingerprint layout)))in
    let body=set "capacities"(arr capacities)body in
    provider|>set "body" body|>set "identity"(set "content_fingerprint"(str(Canonical.fingerprint body))(get "identity" provider)))in
  let changed=raw|>set "record_layout" layout|>set "providers"(arr providers)|>Context.of_json in
  let result=X.check ~context:changed ~binding ()in
  require(X.accepted result=None && List.mem(str "complete_finite_record_layout")(items "diagnostics"(X.report result)))
    "Re-pinned capacity layout silently dropped all ordered uncertainty reasons"
let binding_controls original behavior parts=
  let admitted=A.admit ~request:original ~behavior and graph=get "implementation" parts in
  let check graph=B.check ~admitted ~implementation:(I.of_json ~library:(Q.implementation_library original)graph)
    ~proposed:(U.of_json(get "binding" parts))in
  let reject graph=rejects "policy_implementation_source_binding"(fun()->check graph)in
  reject(model_mutation original graph "guard_select_all" "compound.any2");
  reject(model_mutation original graph "guard_select_any" "compound.all2");
  reject(model_mutation original graph "write_true_all" "compound.any2");
  reject(model_mutation original graph "write_false_any" "compound.all2");
  reject(model_mutation original graph "selected" "exclusion.primitive.register");
  reject(wire_mutation graph "guard_select_any" "in0"(endpoint "true" "out"));
  reject(wire_mutation graph "write_false_all" "in0"(endpoint "true" "out"));
  let swapped=graph|>fun graph->wire_mutation graph "guard_select_all" "in0"(endpoint "guard_select_any" "out")
    |>fun graph->wire_mutation graph "guard_select_all" "in1"(endpoint "evidence" "value")in
  reject swapped;
  ignore(check graph)
type history = Missing | Invalid | Conflicting | Silence | Loss
let choose source history=
  let matching(batch:F.input_batch)=
    let observation=if batch.tick<>2 then true else List.map(fun(row:F.observation_input)->row.slot,row.evidence)batch.observations=
      (match history with Missing->["e1",F.Missing]|Invalid->["e1",F.Invalid]
        |Conflicting->["e1",F.Conflicting]|Silence->[]|Loss->["e1",F.Known false])in
    let feedback=List.map(fun(row:F.feedback_input)->row.attempt.key.creation_ordinal,row.outcome)batch.feedback=
      (if batch.tick=4 && history<>Silence then[1,F.Completed;2,F.Failed]else[])in
    observation && feedback && List.for_all(fun(_,action)->action=F.Keep)batch.lifecycle in
  let rec scan sequence=match sequence()with Seq.Nil->failwith "Literal compound history absent from original grammar"
    |Seq.Cons(value,rest)->if matching value then value else scan rest in
  scan(S.choices source)
let literals width history (frame:P.frame)=
  List.iter(fun slot->
    let selected=if frame.tick=0 then I.Unknown else if history=Loss && frame.tick>=2 && slot="e1"then I.False else I.True
    and excluded=if history=Loss && frame.tick>=2 && slot="e1"then I.True else I.False in
    require(truth frame "selected" slot={P.value=Some selected;reasons=[]} &&
      truth frame "excluded" slot={P.value=Some excluded;reasons=[]})
      "Explicit Unknown/known atomic state differs from literal; Unknown must remain defined";
    require(truth frame "write_true_all" slot={P.value=Some I.True;reasons=[]} &&
      truth frame "write_false_any" slot={P.value=Some I.False;reasons=[]})
      "Nested all/any assignment operands differ from literal values";
    let evidence=if frame.tick=0 then{P.value=Some I.False;reasons=[]}
      else if slot="e1" && frame.tick>=2 then(match history with
        |Missing->{P.value=None;reasons=[P.Missing]}|Invalid->{P.value=None;reasons=[P.Invalid]}
        |Conflicting->{P.value=None;reasons=[P.Conflicting]}
        |Loss->if frame.tick>=4 then{P.value=None;reasons=[P.Stale]}else{P.value=Some I.False;reasons=[]}
        |Silence->if frame.tick>=3 then{P.value=None;reasons=[P.Stale]}else{P.value=Some I.True;reasons=[]})
      else if frame.tick>=3 then{P.value=None;reasons=[P.Stale]}else{P.value=Some I.True;reasons=[]}in
    require(truth frame "evidence" slot=evidence)"Missing evidence lost definedness/value/reason distinction";
    let value=Option.value ~default:I.Unknown evidence.value in
    let reasons=List.concat(List.init width(fun _->evidence.reasons))in
    require(truth frame "guard_select_all" slot={P.value=Some value;reasons})
      "Nested select guard changed truth or ordered reason multiplicity";
    let opposite=match value with I.True->I.False|I.False->I.True|I.Unknown->I.Unknown in
    require(truth frame "guard_exclude_any" slot={P.value=Some opposite;reasons})
      "Nested exclusion guard changed truth or ordered reason multiplicity") ["e1";"e2"];
  let changes=List.filter_map(fun(action:P.action)->match action.detail with
    |P.Authorization_changed(id,value,reasons,response)->
        let owner=List.find(fun(attempt:P.attempt)->attempt.attempt_id=id)frame.attempts in
        Some(owner.ordinal,value,reasons,response,action.microstep)|_->None)frame.actions in
  let reasons reason=List.init width(fun _->reason)in
  let expected=match history,frame.tick with
    |Missing,2->[1,I.Unknown,reasons P.Missing,"defer",0]
    |Invalid,2->[1,I.Unknown,reasons P.Invalid,"defer",0]
    |Conflicting,2->[1,I.Unknown,reasons P.Conflicting,"defer",0]
    |Loss,2->[1,I.False,[],"continue",0]
    |Silence,3->[1,I.Unknown,reasons P.Stale,"defer",0;2,I.Unknown,reasons P.Stale,"defer",0]
    |(Missing|Invalid|Conflicting|Loss),3->[2,I.Unknown,reasons P.Stale,"defer",0]
    |_->[]in
  require(changes=expected)"Retained authorization lost ordered compound reasons";
  require(List.length frame.creations=(if frame.tick=1 then 2 else 0))"Compound guard changed literal effect creation count";
  if frame.tick=2 || frame.tick=3 then require(List.for_all(fun(attempt:P.attempt)->attempt.status=P.Active)frame.attempts)
    "Compound uncertainty/loss stopped an active attempt"
let trace_mutations correspondence batch (advanced:S.advanced) (frame:P.frame)=
  let execution=match advanced.receipt.execution with Some value->value|None->failwith "Missing independent source replay"in
  let check candidate=T.advance correspondence ~batch ~source_frame:advanced.frame
    ~source_attempts:(items "attempts" execution) ~source_creations:advanced.creations ~candidate in
  let reject candidate=rejects "policy_trace_correspondence"(fun()->check candidate)in
  if frame.tick=0 then(
    let altered signal={frame with outputs=List.map(fun(port:P.port_value)->
      if port.endpoint.node_id="selected" && port.binding.slot=Some "e1"then {port with signal=P.Truth signal}else port)frame.outputs}in
    reject(altered{P.value=Some I.False;reasons=[]});
    reject(altered{P.value=None;reasons=[P.Missing]}));
  if frame.tick=1 then(
    let written=List.find(fun(action:P.action)->match action.detail with
      P.State_written write->write.destination="selected"|_->false)frame.actions in
    let changed=match written.detail with P.State_written write->{written with detail=P.State_written{write with value=I.False}}
      |_->assert false in
    reject{frame with actions=List.map(fun action->if action=written then changed else action)frame.actions});
  if frame.tick=2 then(
    match List.find_opt(fun(action:P.action)->match action.detail with P.Authorization_changed(_,_,_::_,_)->true|_->false)frame.actions with
    |None->()
    |Some action->let changed=match action.detail with
        |P.Authorization_changed(id,value,reasons,response)->
            {action with detail=P.Authorization_changed(id,value,List.tl reasons,response)}|_->assert false in
        reject{frame with actions=List.map(fun value->if value=action then changed else value)frame.actions});
  ignore(check frame)
let run_history limits behavior bound width history=
  let original=A.request(B.admitted_inputs bound)and environment=B.environment bound in
  let source=S.create ~behavior ~domain:(Q.operating_domain original) ~bounds:(S.execution_bounds_of_json(get "source" limits))in
  let runtime=P.initialize ~implementation:(B.implementation bound)
    ~environment:{P.executor=environment.executor;horizon_ticks=environment.horizon_ticks;
      slots=List.map(fun(slot:B.slot)->{P.slot_id=slot.identity;target=slot.target;start_tick=slot.start_tick})environment.slots}
    ~limits:{P.max_work=1000000;max_events=100000;max_attempts=32;max_microsteps=32}in
  let rec loop source runtime correspondence=
    if not(S.finished source)then(
      let batch=choose source history in
      let runtime,frame=P.step runtime(T.input correspondence batch)in
      let advanced=match S.step source batch with S.Advanced value->value
        |S.Stopped value->failwith("Source compound literal stopped: "^value.diagnostic.code)in
      literals width history frame;
      trace_mutations correspondence batch advanced frame;
      let execution=match advanced.receipt.execution with Some value->value|None->failwith "Missing source replay"in
      let correspondence=T.advance correspondence ~batch ~source_frame:advanced.frame ~source_attempts:(items "attempts" execution)
        ~source_creations:advanced.creations ~candidate:frame in
      loop advanced.next runtime correspondence)in
  loop source runtime(T.create bound)
let ()=
  require(Array.length Sys.argv=2)"Supply compound material fixture";
  let fixture=read Sys.argv.(1)in
  let cases=items "cases" fixture and limits=get "limits" fixture in
  require(List.map(text "id")cases=["single_reason";"repeated_reasons"])"Compound source family inventory changed";
  let accepted=List.map(fun case->
    let request=R.of_json(get "request" case)and parts=get "candidate_parts" case in
    let original=R.implementation_request request and expected=get "expected" case in
    let behavior=lower request in
    require(R.fingerprint request=text "request_fingerprint" expected)"Compound original root changed";
    let implementation=I.of_json ~library:(Q.implementation_library original)(get "implementation" parts)in
    require(List.length(I.nodes implementation)=23 && List.length(I.wires implementation)=38 &&
      List.length(I.semantic_exports implementation)=29)"Explicit compound graph census changed";
    binding_controls original behavior parts;
    let result=Check.check ~request ~behavior ~implementation ~proposed:(U.of_json(get "binding" parts))
      ~material_binding:(C.proposal_of_json(get "material_binding" parts)) ~candidate:(K.of_json(get "construction" parts))
      ~limits:(V.limits_of_json limits)in
    let report=Check.report result in
    let accepted=match Check.accepted result with Some value->value|None->
      failwith("Compound full material case failed: "^text "id" case^": "^Canonical.encode report)in
    require(text "status" report="checked_material" && get "all_original_obligations_discharged" report=Json.Bool true)
      "Compound acceptance dropped an original obligation";
    List.iter(fun(key,value)->require(at["preservation";"coverage";key]report=Json.int value)("Compound domain census changed: "^key))
      ["histories",54;"transitions",176;"prefixes_started",177];
    let requirements=items "requirements"(get "preservation" report)in
    require(List.sort String.compare(List.map(text "id")requirements)=["exclusive_selection";"initiation_progress";"request_progress"] &&
      List.for_all(fun row->text "status" row="pass")requirements)"Compound witness weakened or omitted original hard properties";
    let context=Check.context accepted in
    let evidence=X.evidence context in
    let width=integer(get "ordered_reason_width" case)in
    resource_literals evidence;
    require(List.length(items "derived_demands" evidence)=14 && at["record_layout";"ordered_reason_slots"]evidence=Json.int width &&
      at["record_layout";"ordered_cause_slots"]evidence=Json.int 238 && at["record_layout";"maximum_tick"]evidence=Json.int 11 &&
      at["record_layout";"identifier_bytes"]evidence=Json.int 384)"Complete compound record capacity derivation changed";
    undersized_reasons(X.context context)(X.binding context);
    let material=L.implementation(X.binding context)in
    List.iter(run_history limits behavior(V.binding material)width)[Missing;Invalid;Conflicting;Silence;Loss];
    let content=Bioc_checker.Policy_mrna_structure_check.content(L.structure(X.binding context))in
    let molecules=get "molecules"(get "inventory"(K.to_json content))in
    require(Json.equal molecules(get "molecules"(get "inventory"(get "construction" parts))) &&
      text "sequence"(List.hd(Json.array molecules))="CCAUGGCUUAAGGAAAA")"Compound material changed literal exact RNA";
    require(text "claim_scope" report="bounded_conditional_policy_to_exact_mrna" && text "empirical" report="unassessed" &&
      text "artifact" report="withheld" && text "export" report="withheld")"Compound leaf widened its claim";
    case,request,material)cases in
  List.iteri(fun index(case,_,implementation)->
    let other,other_request,_=List.nth accepted(1-index)in
    let contract=C.of_json ~library:(Q.implementation_library(R.implementation_request other_request))
      (get "material_contract"(get "request" other))in
    let parts=get "candidate_parts" case and other_parts=get "candidate_parts" other in
    require(Json.equal(get "construction" parts)(get "construction" other_parts))"Cross-case RNA no longer identical";
    let result=L.check ~contract ~implementation ~proposed:(C.proposal_of_json(get "material_binding" other_parts))
      ~candidate:(K.of_json(get "construction" parts))()in
    require(L.accepted result=None && text "outcome"(L.report result)="fail" &&
      List.mem(str "complete_ordered_wiring")(items "diagnostics"(L.report result)))
      "A different compound whole-graph case was accepted merely because its RNA matched")accepted;
  Printf.printf "policy material compound literals and near-neighbor controls passed (%d checks)\n" !checks
