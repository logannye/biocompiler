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
module K=Bioc_domain.Construction_content
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
let at keys raw=List.fold_left(fun value key->get key value)raw keys
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_bounded ~max_bytes:8000000 ~max_nodes:400000(really_input_string channel(in_channel_length channel)))
let rejects run=incr checks;match run()with
  |_->failwith "Near-neighbor lifecycle trace was accepted"
  |exception Diagnostic.Error value->require(value.code="policy_trace_correspondence")
      ("Unexpected lifecycle diagnostic: "^value.code)
let lower request=let original=R.implementation_request request in
  Bioc_compiler.Policy_lowering.lower(Bioc_checker.Policy_admission.admit
    ~document:(Q.document original) ~descriptors:(Q.definitions original))
let attempt (frame:P.frame) ordinal=List.find(fun(value:P.attempt)->value.ordinal=ordinal)frame.attempts
let authorization_actions (frame:P.frame)=List.filter_map(fun(action:P.action)->match action.detail with
  |P.Authorization_changed(id,value,reasons,response)->
      let owner=List.find(fun(value:P.attempt)->value.attempt_id=id)frame.attempts in
      Some(owner.ordinal,value,reasons,response,action.microstep)
  |_->None)frame.actions
type history = Missing_then_feedback | Invalid_then_feedback | Conflicting_then_feedback
  | Silence_then_timeout | Loss_then_feedback
let select source history=
  let matches(batch:F.input_batch)=
    let observation=if batch.tick<>2 then true else
      List.map(fun(row:F.observation_input)->row.slot,row.evidence)batch.observations=
        (match history with Missing_then_feedback->["e1",F.Missing]
          |Invalid_then_feedback->["e1",F.Invalid]|Conflicting_then_feedback->["e1",F.Conflicting]
          |Silence_then_timeout->[]|Loss_then_feedback->["e1",F.Known false])in
    let feedback=List.map(fun(row:F.feedback_input)->row.attempt.key.creation_ordinal,row.outcome)batch.feedback=
      (if batch.tick=4 && history<>Silence_then_timeout then[1,F.Completed;2,F.Failed]else[])in
    observation && feedback && List.for_all(fun(_,action)->action=F.Keep)batch.lifecycle in
  let rec scan sequence=match sequence()with
    |Seq.Nil->failwith "Literal lifecycle history is absent from original causal grammar"
    |Seq.Cons(value,rest)->if matches value then value else scan rest in
  scan(S.choices source)
let literals case history (frame:P.frame)=
  let continuous=text "authorization" case="continuous" and response=text "on_unknown" case in
  let tick=frame.tick in
  require(List.length frame.creations=(if tick=1 then 2 else 0))"Lifecycle unexpectedly created another attempt";
  require(List.length frame.attempts=(if tick=0 then 0 else 2))"Lifecycle lost retained attempt identity";
  let expected_actions=if not continuous then[]else match history,tick with
    |Missing_then_feedback,2->[1,I.Unknown,[P.Missing],response,0]
    |Invalid_then_feedback,2->[1,I.Unknown,[P.Invalid],response,0]
    |Conflicting_then_feedback,2->[1,I.Unknown,[P.Conflicting],response,0]
    |(Missing_then_feedback|Invalid_then_feedback|Conflicting_then_feedback),3->[2,I.Unknown,[P.Stale],response,0]
    |Silence_then_timeout,3->[1,I.Unknown,[P.Stale],response,0;2,I.Unknown,[P.Stale],response,0]
    |Loss_then_feedback,2->[1,I.False,[],"continue",0]
    |Loss_then_feedback,3->[2,I.Unknown,[P.Stale],response,0]
    |_->[]in
  require(authorization_actions frame=expected_actions)"Literal authorization phase/value/reason/response differs";
  List.iter(fun(value:P.attempt)->
    let expected_status=if history=Silence_then_timeout then(if tick=6 then P.Timed_out else P.Active)
      else if tick>=4 then(if value.ordinal=1 then P.Completed else P.Failed)else P.Active in
    let expected_authorization=if not continuous || tick<2 then I.True else match history with
      |Missing_then_feedback|Invalid_then_feedback|Conflicting_then_feedback->if value.ordinal=1 || tick>=3 then I.Unknown else I.True
      |Silence_then_timeout->if tick>=3 then I.Unknown else I.True
      |Loss_then_feedback->if value.ordinal=1 then I.False else if tick>=3 then I.Unknown else I.True in
    require(value.status=expected_status && value.authorization=expected_authorization)
      "Authorization uncertainty/loss changed activity or retained authorization incorrectly";
    require(value.started_tick=1 && value.deadline_tick=6 && value.binding.generation=0 &&
      value.binding.slot=Some(if value.ordinal=1 then "e1"else"e2") && value.executor="cell-1" &&
      value.subject=(if value.ordinal=1 then "target-1"else"target-2"))"Attempt timing or correlation changed";
    require(value.ended_tick=(if expected_status=P.Active then None else Some(if history=Silence_then_timeout then 6 else 4)))
      "Attempt acquired an unrequested stop/cancellation time")frame.attempts;
  let lifecycle_events=List.filter_map(fun(event:P.event)->match event.kind with
    |P.Primitive_event(I.Requested|I.Initiated|I.Completed|I.Failed|I.Timed_out as kind)->Some kind
    |_->None)frame.events in
  require(lifecycle_events=(if tick=1 then[I.Requested;I.Initiated;I.Requested;I.Initiated]
    else if tick=4 && history<>Silence_then_timeout then[I.Completed;I.Failed]
    else if tick=6 && history=Silence_then_timeout then[I.Timed_out;I.Timed_out]else[]))
    "Effect lifecycle emitted an early terminal event or changed exact event order";
  if tick=2 || tick=3 then require(List.for_all(fun(value:P.attempt)->value.status=P.Active)frame.attempts)
    "Uncertainty/false evidence stopped an effect before feedback/deadline"
let mutations correspondence batch (advanced:S.advanced) (frame:P.frame)=
  let execution=match advanced.receipt.execution with Some value->value|None->failwith "Missing source replay"in
  let compare candidate=T.advance correspondence ~batch ~source_frame:advanced.frame
    ~source_attempts:(items "attempts" execution) ~source_creations:advanced.creations ~candidate in
  let original=attempt frame 1 in
  let change_attempt changed={frame with attempts=List.map(fun(value:P.attempt)->
    if value.ordinal=1 then changed else value)frame.attempts}in
  rejects(fun()->compare(change_attempt{original with status=P.Completed;ended_tick=Some frame.tick}));
  rejects(fun()->compare(change_attempt{original with authorization=(if original.authorization=I.False then I.Unknown else I.False)}));
  let auth=List.find_opt(fun(action:P.action)->match action.detail with P.Authorization_changed _->true|_->false)frame.actions in
  (match auth with
   |Some changed->
      rejects(fun()->compare{frame with actions=List.filter((<>)changed)frame.actions});
      let replacement=match changed.detail with
        |P.Authorization_changed(id,value,reasons,response)->
            {changed with detail=P.Authorization_changed(id,value,reasons,if response="continue"then"defer"else"continue")}
        |_->assert false in
      rejects(fun()->compare{frame with actions=List.map(fun action->if action=changed then replacement else action)frame.actions});
      let replacement=match changed.detail with
        |P.Authorization_changed(id,value,reasons,response)->
            {changed with detail=P.Authorization_changed(id,value,(if reasons=[P.Missing]then[P.Invalid]else[P.Missing]),response)}
        |_->assert false in
      rejects(fun()->compare{frame with actions=List.map(fun action->if action=changed then replacement else action)frame.actions})
   |None->
      let invented:P.action={microstep=0;detail=P.Authorization_changed(original.attempt_id,I.Unknown,[P.Invalid],"defer")}in
      rejects(fun()->compare{frame with actions=invented::frame.actions}));
  ignore(compare frame)
let run_history case limits behavior bound history=
  let original=Q.of_json(get "implementation_request"(get "request" case))in
  let environment=B.environment bound in
  let runtime=P.initialize ~implementation:(B.implementation bound)
    ~environment:{P.executor=environment.executor;horizon_ticks=environment.horizon_ticks;
      slots=List.map(fun(slot:B.slot)->{P.slot_id=slot.identity;target=slot.target;start_tick=slot.start_tick})environment.slots}
    ~limits:{P.max_work=1000000;max_events=100000;max_attempts=32;max_microsteps=32}in
  let source=S.create ~behavior ~domain:(Q.operating_domain original)
    ~bounds:(S.execution_bounds_of_json(get "source" limits))in
  let rec loop source runtime correspondence=
    if not(S.finished source)then(
      let batch=select source history in
      let runtime,frame=P.step runtime(T.input correspondence batch)in
      let advanced=match S.step source batch with S.Advanced value->value
        |S.Stopped value->failwith("Literal source stopped: "^value.diagnostic.code)in
      literals case history frame;
      if frame.tick=2 then mutations correspondence batch advanced frame;
      let execution=match advanced.receipt.execution with Some value->value|None->failwith "No source replay"in
      let correspondence=T.advance correspondence ~batch ~source_frame:advanced.frame
        ~source_attempts:(items "attempts" execution) ~source_creations:advanced.creations ~candidate:frame in
      loop advanced.next runtime correspondence)in
  loop source runtime(T.create bound)
let ()=
  require(Array.length Sys.argv=2)"Supply lifecycle material literal fixture";
  let fixture=read Sys.argv.(1)in
  let cases=items "cases" fixture and limits=get "limits" fixture in
  require(List.map(text "id")cases=["initiation_continue";"initiation_defer";"continuous_continue";"continuous_defer"])
    "Lifecycle inventory no longer covers each admitted authorization/unknown-response pair";
  let census=get "census_derivation" fixture in
  let prefixes=List.map(fun value->Z.to_int(Json.integer value))(items "tick_prefix_counts" census)in
  require(prefixes=[1;1;6;6;54;54;54] && List.fold_left(+)0 prefixes=176 && 6*3*3=54)
    "Independent literal environment census changed";
  let accepted=List.map(fun case->
    let request=R.of_json(get "request" case)and parts=get "candidate_parts" case in
    let original=R.implementation_request request and expected=get "expected" case in
    let behavior=lower request in
    let implementation=I.of_json ~library:(Q.implementation_library original)(get "implementation" parts)in
    require(R.fingerprint request=text "request_fingerprint" expected)"Lifecycle original authority changed";
    let result=Check.check ~request ~behavior ~implementation ~proposed:(U.of_json(get "binding" parts))
      ~material_binding:(C.proposal_of_json(get "material_binding" parts)) ~candidate:(K.of_json(get "construction" parts))
      ~limits:(V.limits_of_json limits)in
    let report=Check.report result in
    let accepted=match Check.accepted result with Some value->value|None->
      failwith("Complete lifecycle material case failed: "^text "id" case^": "^Canonical.encode report)in
    require(text "status" report="checked_material" && get "all_original_obligations_discharged" report=Json.Bool true)
      "Lifecycle material acceptance omitted an original obligation";
    List.iter(fun key->require(at["preservation";"coverage";key]report=get key expected)("Lifecycle census differs: "^key))
      ["histories";"transitions";"prefixes_started"];
    let requirements=items "requirements"(get "preservation" report)in
    require(List.sort String.compare(List.map(text "id")requirements)=List.map Json.string(items "requirements" expected) &&
      List.for_all(fun row->text "status" row="pass")requirements)"Lifecycle witness weakened/dropped a hard requirement";
    require(text "claim_scope" report="bounded_conditional_policy_to_exact_mrna" && text "empirical" report="unassessed" &&
      text "artifact" report="withheld" && text "export" report="withheld")"Lifecycle leaf widened its authority";
    let material=L.implementation(X.binding(Check.context accepted))in
    let bound=V.binding material in
    List.iter(run_history case limits behavior bound)
      [Missing_then_feedback;Invalid_then_feedback;Conflicting_then_feedback;Silence_then_timeout;Loss_then_feedback];
    let content=Bioc_checker.Policy_mrna_structure_check.content(L.structure(X.binding(Check.context accepted)))in
    require(Json.equal(get "molecules"(get "inventory"(K.to_json content)))(get "molecules"(get "inventory"(get "construction" parts))))
      "Lifecycle acceptance changed exact full molecules";
    require(text "sequence"(List.hd(items "molecules"(get "inventory"(K.to_json content))))="CCAUGGCUUAAGGAAAA")
      "Literal lifecycle RNA spelling changed";
    case,request,material)cases in
  (* Equal sequence is not an interchangeable behavioral contract. Decode each
     other complete supplied authority independently, then compare it against
     the already freshly checked actual graph, with its own correct proposal. *)
  List.iteri(fun index (case,_,material)->
    let other,other_request,_=List.nth accepted((index+1)mod List.length accepted)in
    let other_contract=C.of_json ~library:(Q.implementation_library(R.implementation_request other_request))
      (get "material_contract"(get "request" other))in
    let parts=get "candidate_parts" case and other_parts=get "candidate_parts" other in
    require(get "construction" parts=get "construction" other_parts)"Cross-case control no longer has identical material";
    let changed=L.check ~contract:other_contract ~implementation:material
      ~proposed:(C.proposal_of_json(get "material_binding" other_parts)) ~candidate:(K.of_json(get "construction" parts))()in
    require(L.accepted changed=None && text "outcome"(L.report changed)="fail" &&
      List.mem(Json.String "complete_primitive_configuration_replication:local.attempt")(items "diagnostics"(L.report changed)))
      "Different supplied lifecycle case gained acceptance through identical RNA" )accepted;
  Printf.printf "policy material lifecycle literals and near-neighbor controls passed (%d checks)\n" !checks
