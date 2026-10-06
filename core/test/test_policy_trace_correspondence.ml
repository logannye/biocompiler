open Bioc_wire
module F = Bioc_domain.Policy_operating_domain
module I = Bioc_domain.Policy_implementation
module R = Bioc_domain.Policy_realization_request
module U = Bioc_domain.Policy_implementation_binding
module A = Bioc_checker.Policy_realization_admission
module B = Bioc_checker.Policy_implementation_binding_check
module L = Bioc_compiler.Policy_lowering
module S = Bioc_semantics.Policy_domain_reference
module P = Bioc_candidate_runtime.Policy_primitives
module T = Bioc_realization_checker.Policy_trace_correspondence
let require condition message = if not condition then failwith message
let obj x=Json.Object x
let get name value=Json.field name(Json.object_fields value)
let text name value=Json.string(get name value)
let items name value=Json.array(get name value)
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_bounded ~max_bytes:(4*1024*1024) ~max_nodes:200000 (really_input_string channel(in_channel_length channel)))
let rejects operation=match operation()with
  | _->failwith "Altered observable trace was accepted"
  | exception Diagnostic.Error diagnostic->require(diagnostic.code="policy_trace_correspondence")
      ("Unexpected projection diagnostic: "^diagnostic.code)
let bounds=S.execution_bounds_of_json(obj(List.map(fun(k,v)->k,Json.int v)
  ["max_ticks",20;"max_inputs",100;"max_encounters",4;"max_attempts",20;
   "max_work",1000000;"max_trace_items",10000;"max_microsteps",20]))
let initialize case =
  let request=R.of_json(get "request" case)in
  let behavior=L.lower(Bioc_checker.Policy_admission.admit ~document:(R.document request) ~descriptors:(R.definitions request))in
  let admitted=A.admit ~request ~behavior in
  let implementation=I.of_json ~library:(R.implementation_library request)(get "implementation" case)in
  let bound=B.check ~admitted ~implementation ~proposed:(U.of_json(get "proposed" case))in
  let environment=B.environment bound in
  let runtime=P.initialize ~implementation:(B.implementation bound)
    ~environment:{P.executor=environment.executor;horizon_ticks=environment.horizon_ticks;
      slots=List.map(fun(slot:B.slot)->{P.slot_id=slot.identity;target=slot.target;start_tick=slot.start_tick})environment.slots}
    ~limits:{P.max_work=10000000;max_events=100000;max_attempts=20;max_microsteps=20}in
  S.create ~behavior ~domain:(R.operating_domain request) ~bounds,runtime,T.create bound
let execution (value:S.advanced)=match value.receipt.execution with Some value->value|None->failwith "No source execution"
let quiet (batch:F.input_batch)=batch.feedback=[] && List.for_all(fun(_,action)->action=F.Keep)batch.lifecycle
let observations evidence (batch:F.input_batch)=
  batch.tick<>1 || List.map(fun(row:F.observation_input)->row.slot,row.evidence)batch.observations=evidence
let select source predicate=
  let rec scan sequence=match sequence()with
    |Seq.Nil->failwith "Expected independent source input branch is absent"
    |Seq.Cons(value,rest)->if predicate value then value else scan rest in
  scan(S.choices source)
let execute source runtime correspondence batch =
  let translated=T.input correspondence batch in
  let runtime,frame=P.step runtime translated in
  let advanced=match S.step source batch with S.Advanced value->value
    |S.Stopped value->failwith("Source witness stopped: "^value.diagnostic.code)in
  let correspondence=T.advance correspondence ~batch ~source_frame:advanced.frame
    ~source_attempts:(items "attempts"(execution advanced)) ~source_creations:advanced.creations ~candidate:frame in
  advanced.next,runtime,correspondence,advanced,frame
let reject_mutations correspondence batch (advanced:S.advanced) (frame:P.frame) =
  let check candidate=T.advance correspondence ~batch ~source_frame:advanced.frame
    ~source_attempts:(items "attempts"(execution advanced)) ~source_creations:advanced.creations ~candidate in
  rejects(fun()->check{frame with events=List.tl frame.events});
  rejects(fun()->check{frame with events=frame.events@[List.hd frame.events]});
  rejects(fun()->check{frame with events=List.rev frame.events});
  rejects(fun()->check{frame with actions=List.rev frame.actions});
  rejects(fun()->check{frame with rounds=List.tl frame.rounds});
  rejects(fun()->check{frame with tick=frame.tick+1});
  rejects(fun()->check{frame with creations=[]});
  rejects(fun()->check{frame with attempts=List.rev frame.attempts});
  rejects(fun()->check{frame with evidence=List.rev frame.evidence});
  rejects(fun()->check{frame with slots=List.map(fun(slot:P.slot_snapshot)->{slot with generation=slot.generation+1})frame.slots});
  let first=List.hd frame.attempts in
  List.iter(fun altered->rejects(fun()->check{frame with attempts=altered::List.tl frame.attempts}))
    [{first with subject="wrong-target"};{first with product="wrong-product"};
     {first with causes=[]};{first with deadline_tick=first.deadline_tick+1};
     {first with authorization=I.Unknown};{first with binding={first.binding with slot=Some "e2"}}];
  rejects(fun()->check{frame with creations=List.map(fun(attempt:P.attempt)->{attempt with ordinal=attempt.ordinal+1})frame.creations});
  let created=List.hd frame.creations in
  List.iter(fun altered->rejects(fun()->check{frame with creations=altered::List.tl frame.creations}))
    [{created with product="wrong-creation-product"};{created with guard={created.guard with node_id="wrong-guard"}};
     {created with executor="wrong-executor"};{created with status=P.Completed};{created with authorization=I.Unknown}];
  rejects(fun()->check{frame with attempts=List.map(fun(attempt:P.attempt)->{attempt with ordinal=attempt.ordinal+1})frame.attempts});
  let first=List.hd frame.events in
  rejects(fun()->check{frame with events={first with tick=first.tick+1}::List.tl frame.events});
  rejects(fun()->check{frame with events={first with microstep=first.microstep+1}::List.tl frame.events});
  let state_ports=List.filter(fun(port:P.port_value)->match port.signal with P.Truth _->true|_->false)frame.outputs in
  require(state_ports<>[])"Runtime witness lacks truth outputs";
  rejects(fun()->check{frame with outputs=List.filter(fun(port:P.port_value)->
    match port.signal with P.Truth _->false|_->true)frame.outputs});
  let baseline=T.fingerprint correspondence in
  ignore(check frame);require(T.fingerprint correspondence=baseline)"Comparison mutated a predecessor identity map"
let check_claim correspondence =
  let report=T.report correspondence in
  require(text "claim" report="matched_prefix_only")"Prefix comparison claimed a whole domain";
  List.iter(fun key->require(text key report="unassessed")("Prefix comparison promoted "^key))
    ["requirements";"whole_domain";"material"];
  require(text "export" report="withheld")"Prefix comparison granted export"
let run_case case evidence feedback_mode reset_mode mutations =
  let source,runtime,correspondence=initialize case in
  let rec loop source runtime correspondence =
    if S.finished source then check_claim correspondence else (
      let batch=select source(fun(batch:F.input_batch)->
        observations evidence batch &&
        (if batch.tick=3 && reset_mode then batch.lifecycle=["e1",F.Reset;"e2",F.End]
         else List.for_all(fun(_,action)->action=F.Keep)batch.lifecycle) &&
        (if feedback_mode && (batch.tick=2 || (batch.tick=3 && reset_mode)) then
           List.map(fun(row:F.feedback_input)->row.attempt.source_attempt_id,row.outcome)batch.feedback=
             ["attempt/1",F.Completed;"attempt/2",F.Failed]
         else batch.feedback=[]))in
      let next,runtime,next_correspondence,advanced,frame=execute source runtime correspondence batch in
      if mutations && batch.tick=1 then reject_mutations correspondence batch advanced frame;
      if batch.tick=3 && reset_mode then (
        let rejected=List.filter(fun(action:P.action)->match action.detail with P.Feedback_rejected _->true|_->false)frame.actions in
        require(List.length rejected=2)"Old feedback was dropped or rebound after reset/end");
      loop next runtime next_correspondence)in
  loop source runtime correspondence
let () =
  let fixture=read Sys.argv.(1)in
  List.iter(fun case->
    let both=["e1",F.Known true;"e2",F.Known true]in
    run_case case both false false true;
    run_case case both true true false;
    List.iter(fun evidence->run_case case evidence false false false)
      [[];["e1",F.Known false];["e1",F.Missing];["e1",F.Invalid];["e1",F.Conflicting]];
    let source,runtime,correspondence=initialize case in
    let batch=select source quiet in
    let _,_,matched,_,_=execute source runtime correspondence batch in
    require(T.fingerprint matched<>T.fingerprint correspondence)"Matched prefix did not bind its execution history";
    rejects(fun()->T.input matched batch)) (items "cases" fixture);
  print_endline "policy exact trace correspondence literals and adversarial controls passed"
