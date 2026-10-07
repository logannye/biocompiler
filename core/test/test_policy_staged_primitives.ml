open Bioc_wire
open Bioc_policy_staged_test_support.Literals
module I = Bioc_domain.Policy_implementation
module P = Bioc_candidate_runtime.Policy_primitives
let rejected=ref 0
let rejects code action=match action()with
  |_->failwith("Staged runtime mutant accepted: "^code)
  |exception Diagnostic.Error diagnostic->
      require(diagnostic.code=code)("Wrong staged diagnostic: "^diagnostic.code^" expected "^code);incr rejected

let environment:P.environment={executor="cell";slots=[{slot_id="e1";target="target1";start_tick=0};
  {slot_id="e2";target="target2";start_tick=0}];horizon_ticks=8}
let limits:P.limits={max_work=8_000_000;max_events=200_000;max_attempts=32;max_microsteps=20}
let initial ?(limits=limits) implementation=P.initialize ~implementation ~environment ~limits
let batch ?(observations=[]) ?(feedback=[]) ?(lifecycle=[]) tick:P.input_batch={tick;observations;feedback;lifecycle}
let observation slot tick evidence:P.observation={observation_id=slot^"/"^string_of_int tick;
  input_id="condition";slot_id=slot;observed_tick=tick;observer="cell";
  subject=(if slot="e1"then "target1"else "target2");evidence}
let feedback ?(slot="e1") ?(suffix="") bank ordinal outcome:P.feedback={feedback_id=bank^"/"^string_of_int ordinal^suffix;
  input_id=bank^"_feedback";attempt_id="primitive/attempt/"^string_of_int ordinal;executor="cell";
  subject=(if slot="e1"then "target1"else "target2");slot_id=slot;outcome}
let bootstrap implementation=P.step(initial implementation)(batch 0 ~observations:
  [observation "e1" 0(P.Known false);observation "e2" 0(P.Known false)])
let machine(frame:P.frame)slot=List.find(fun(value:P.machine_snapshot)->value.bank="machine" && value.binding.slot=Some slot)frame.machines
let expect_machine frame slot state attempts=
  let actual=machine frame slot in require(actual.state=state && actual.retained_attempts=List.map(fun n->"primitive/attempt/"^string_of_int n)attempts)
    ("Incorrect stage/lineage for "^slot^"; expected "^state)
let attempt(frame:P.frame)ordinal=List.find(fun(value:P.attempt)->value.ordinal=ordinal)frame.attempts
let positive implementation=
  let s0,f0=bootstrap implementation in expect_machine f0 "e1" "ready"[];expect_machine f0 "e2" "ready"[];
  let s1,f1=P.step s0(batch 1 ~observations:[observation "e1" 1(P.Known true);observation "e2" 1(P.Known true)])in
  expect_machine f1 "e1" "first"[1];expect_machine f1 "e2" "first"[2];
  require(List.map(fun(a:P.attempt)->a.machine)f1.creations=[Some "machine";Some "machine"])
    "Stage requests omitted their actual machine owner";
  let kinds=List.filter_map(fun(action:P.action)->match action.detail with
    |P.Effect_requested attempt->Some("request",attempt.binding.slot)
    |P.Machine_transition transition->Some("machine",transition.binding.slot)|_->None)f1.actions in
  require(kinds=["request",Some "e1";"machine",Some "e1";"request",Some "e2";"machine",Some "e2"])
    "Machine commits lost per-activation source ordering";
  let s2,f2=P.step s1(batch 2 ~feedback:[feedback "first" 1 P.Complete;feedback ~slot:"e2" "first" 2 P.Fail])in
  expect_machine f2 "e1" "second"[3];expect_machine f2 "e2" "failed"[];
  require((attempt f2 1).status=P.Completed && (attempt f2 2).status=P.Failed && (attempt f2 3).bank="second")
    "Stage handoff changed effect identity or discarded historical attempts";
  require((attempt f2 3).guard={I.node_id="true";port_id="out"} && (attempt f2 3).authorization=I.True)
    "Machine-state predicate leaked into retained continuous authorization";
  let s3,f3=P.step s2(batch 3 ~feedback:[feedback "second" 3 P.Complete;feedback ~suffix:"/stale" "first" 1 P.Complete])in
  expect_machine f3 "e1" "completed"[];
  let s4,_=P.step s3(batch 4 ~observations:[observation "e1" 4(P.Known false)])in
  let _,f5=P.step s4(batch 5 ~observations:[observation "e1" 5(P.Known true)])in
  expect_machine f5 "e1" "completed"[];require(f5.creations=[])"Terminal machine re-entered the regimen";
  require(text "profile"(P.frame_to_json f2)=P.staged_execution_profile && List.length(rows "machines"(P.frame_to_json f2))=2)
    "Staged profile or complete machine snapshots absent from serialized frame";
  s0,s1
let lifecycle_and_feedback implementation s1=
  let before=P.state_fingerprint s1 in
  let _,wrong=P.step s1(batch 2 ~feedback:[feedback "second" 1 P.Complete])in
  expect_machine wrong "e1" "first"[1];require((attempt wrong 1).status=P.Active)"Wrong driver input completed a stage";
  let _,wrong_scope=P.step s1(batch 2 ~feedback:[feedback ~slot:"e2" "first" 1 P.Complete])in
  expect_machine wrong_scope "e1" "first"[1];
  let quiet2,_=P.step s1(batch 2)in let _,quiet3=P.step quiet2(batch 3)in
  expect_machine quiet3 "e1" "failed"[];require((attempt quiet3 1).status=P.Timed_out)"Silent timeout failed to advance machine";
  let _,deadline=P.step quiet2(batch 3 ~feedback:[feedback "first" 1 P.Complete])in
  expect_machine deadline "e1" "second"[3];require((attempt deadline 1).status=P.Completed)"Deadline timeout preceded completion feedback";
  let next,reset=P.step s1(batch 2 ~lifecycle:["e1",P.Reset] ~observations:[observation "e1" 2(P.Known false)])in
  expect_machine reset "e1" "ready"[];expect_machine reset "e2" "first"[2];
  require((machine reset "e1").binding.generation=1 && (attempt reset 1).status=P.Reset_invalidated)"Reset lost generation or attempt history";
  let _,again=P.step next(batch 3 ~observations:[observation "e1" 3(P.Known true)] ~feedback:[feedback "first" 1 P.Complete])in
  expect_machine again "e1" "first"[3];require((attempt again 3).binding.generation=1)"Fresh attempt reused a prior-generation binding";
  let _,ended=P.step s1(batch 2 ~lifecycle:["e1",P.End])in
  require(not(List.exists(fun(value:P.machine_snapshot)->value.binding.slot=Some "e1")ended.machines))"Ended machine remained live";
  rejects "policy_primitives_work_limit"(fun()->P.step ~max_step_work:1 s1(batch 2));
  rejects "policy_primitives_trace_limit"(fun()->P.step ~max_step_retained:1 s1(batch 2));
  require(P.state_fingerprint s1=before)"Sibling success/failure mutated a predecessor";
  let low=initial ~limits:{limits with max_attempts=1}implementation in
  let low0,_=P.step low(batch 0 ~observations:[observation "e1" 0(P.Known false);observation "e2" 0(P.Known false)])in
  let lowid=P.state_fingerprint low0 in
  rejects "policy_primitives_attempt_limit"(fun()->P.step low0(batch 1 ~observations:
    [observation "e1" 1(P.Known true);observation "e2" 1(P.Known true)]));
  require(P.state_fingerprint low0=lowid)"Attempt ceiling partially changed machine state"
let independent_controls library graph=
  let guarded=graph|>rewire "handoff_gate" "guard"(endpoint "evidence" "value")
    |>rewire "second" "authorization"(endpoint "evidence" "value")in
  let start,_=bootstrap(decode library guarded)in
  let first,_=P.step start(batch 1 ~observations:[observation "e1" 1(P.Known true)])in
  let waiting,unknown=P.step first(batch 2 ~observations:[observation "e1" 2 P.Missing_evidence]
    ~feedback:[feedback "first" 1 P.Complete])in
  expect_machine unknown "e1" "first"[1];require(unknown.creations=[])"Unknown handoff guard created stage two";
  require(not(List.exists(fun(action:P.action)->match action.detail with P.Deferred _->true|_->false)unknown.actions))
    "Unknown transition guard emitted a legacy rule-deferred action";
  let _,later=P.step waiting(batch 3 ~observations:[observation "e1" 3(P.Known true)])in
  expect_machine later "e1" "first"[1];require(later.creations=[])"Recovered guard invented a queued completion event";
  let foreign_library,foreign_graph=fixture ~foreign:true ()in
  let foreign0,_=bootstrap(decode foreign_library foreign_graph)in
  let foreign1,_=P.step foreign0(batch 1 ~observations:[observation "e1" 1(P.Known true)])in
  let _,foreign2=P.step foreign1(batch 2 ~feedback:[feedback "foreign" 2 P.Complete])in
  expect_machine foreign2 "e1" "first"[1];require(foreign2.creations=[] && (attempt foreign2 2).status=P.Completed)
    "Valid feedback for another controller bypassed retained-attempt membership";
  let unbound_library,unbound_graph=reconfigure foreign_library foreign_graph "handoff_gate"
    (o["source",s "first";"correlation",s "unbound"])in
  let unbound0,_=bootstrap(decode unbound_library unbound_graph)in
  let unbound1,_=P.step unbound0(batch 1 ~observations:[observation "e1" 1(P.Known true)])in
  let _,unbound2=P.step unbound1(batch 2 ~feedback:[feedback "foreign" 2 P.Complete])in
  expect_machine unbound2 "e1" "second"[3];
  let small_library,small_graph=fixture ~wide:true ()in
  let small0,_=bootstrap(decode small_library small_graph)in let original=P.state_fingerprint small0 in
  rejects "policy_primitives_capacity"(fun()->P.step small0(batch 1 ~observations:[observation "e1" 1(P.Known true)]));
  require(P.state_fingerprint small0=original)"Machine lineage capacity partially committed requests";
  let wide_library,wide_graph=fixture ~wide:true ~retained_capacity:2 ()in
  let wide0,_=bootstrap(decode wide_library wide_graph)in
  let wide_state,wide1=P.step wide0(batch 1 ~observations:[observation "e1" 1(P.Known true)])in
  expect_machine wide1 "e1" "first"[1;2];
  let _,wide2=P.step wide_state(batch 2 ~feedback:[feedback "first" 1 P.Complete])in
  expect_machine wide2 "e1" "second"[1;2];require(wide2.creations=[])
    "A state-only nonterminal transition replaced the existing machine lineage"

(* Independently count the public retained-inventory contract, including each
   allocation record and its visible copies. No usage counter supplies the
   expected value. *)
let retained_inventory (frame:P.frame)=
  let sum f values=List.fold_left(fun total value->total+f value)0 values in
  let signal=function
    |P.Truth value->List.length value.reasons|P.Product _->0
    |P.Events values->List.length values
    |P.Activations values->sum(fun(value:P.activation)->1+List.length value.causes)values
    |P.Writes values->List.length values
    |P.Requests values->sum(fun(value:P.request)->1+List.length value.activation.causes)values
    |P.Attempts values->sum(fun(value:P.attempt)->1+List.length value.causes)values
    |P.Machine value->List.length value.retained_attempts
    |P.Machine_writes values->List.length values in
  let port(value:P.port_value)=1+signal value.signal in
  let action(value:P.action)=1+(match value.detail with
    |P.Deferred(value,reasons)->List.length value.causes+List.length reasons
    |P.Undefined_commit value|P.Suppressed(value,_)->List.length value.causes
    |P.Authorization_changed(_,_,reasons,_)->List.length reasons
    |P.Observation_batch{input_ids;retained_ids;_}->List.length input_ids+List.length retained_ids
    |P.State_written _|P.Feedback_accepted _|P.Feedback_rejected _->0
    |P.Effect_requested value->List.length value.causes
    |P.Machine_transition value->List.length value.retained_attempts)in
  List.length frame.events+sum action frame.actions+
  sum(fun(round:P.round)->1+sum port round.ports)frame.rounds+sum port frame.outputs+
  sum(fun(value:P.evidence_snapshot)->1+List.length value.occurrences)frame.evidence+
  List.length frame.slots+sum(fun(value:P.machine_snapshot)->1+List.length value.retained_attempts)frame.machines+
  sum(fun(value:P.attempt)->1+List.length value.causes)(frame.attempts@frame.creations)+List.length frame.creations
let allocation_accounting implementation=
  let check before input=
    let original=P.state_fingerprint before in
    let after,frame=P.step before input in
    let expected=retained_inventory frame in
    require((P.usage after).retained-(P.usage before).retained=expected)
      "Runtime erased charged allocation records or omitted an expanded retained item";
    require((P.usage after).allocations=(P.usage before).allocations+List.length frame.creations)
      "Cumulative allocation count does not preserve every attempt";
    let exact,_=P.step ~max_step_retained:expected before input in
    require(P.state_fingerprint exact=P.state_fingerprint after)"Exact retained budget changed the successor";
    rejects "policy_primitives_trace_limit"(fun()->P.step ~max_step_retained:(expected-1)before input);
    require(P.state_fingerprint before=original)"Allocation budget failure mutated its predecessor";
    after,frame in
  let start,_=check(initial implementation)(batch 0 ~observations:
    [observation "e1" 0(P.Known false);observation "e2" 0(P.Known false)])in
  let first,frame=check start(batch 1 ~observations:
    [observation "e1" 1(P.Known true);observation "e2" 1(P.Known true)])in
  require(List.length frame.creations=2 && (P.usage first).allocations=2)"First allocation batch is vacuous";
  let reset,_=check first(batch 2 ~lifecycle:["e1",P.Reset;"e2",P.Reset] ~observations:
    [observation "e1" 2(P.Known false);observation "e2" 2(P.Known false)])in
  let again,frame=check reset(batch 3 ~observations:
    [observation "e1" 3(P.Known true);observation "e2" 3(P.Known true)])in
  require(List.length frame.creations=2 && (P.usage again).allocations=4 && List.length frame.attempts=4)
    "Reset reclaimed cumulative allocation identities or old correlation records"
let read path=
  let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
    let length=in_channel_length channel in require(length<=2*1024*1024)"Fixture exceeds its bound";
    Json.parse_bounded ~max_bytes:(2*1024*1024) ~max_nodes:100000(really_input_string channel length))
let ()=
  require(Array.length Sys.argv=2)"Expected existing literal legacy implementation fixture";
  let library,graph=fixture ()in
  let implementation=decode library graph in
  require(I.library_profile(I.library_of_json library)=I.staged_profile && I.implementation_profile implementation=I.staged_profile &&
    I.implementation_observable_profile implementation=I.staged_observable_profile)"Staged profile accessor changed identity";
  List.iter2(fun(model:I.model)raw->require(Json.equal(I.model_body_to_json model)(get "body" raw))
    "Primitive model body failed exact roundtrip")(I.models(I.library_of_json library))(rows "models" library);
  rejects "policy_implementation_contract"(fun()->I.library_of_json(replace "profile"(s I.profile)library));
  rejects "policy_implementation_contract"(fun()->decode library(graph|>replace "profile"(s I.profile)|>replace "observable_profile"(s I.observable_profile)));
  let machine_model=List.find(fun value->text "primitive"(get "body" value)="machine_bank")(rows "models" library)in
  let configuration=get "configuration"(get "body" machine_model)in
  List.iter(fun(key,value)->let l,g=reconfigure library graph "machine"(replace key value configuration)in
    rejects "policy_implementation_contract"(fun()->decode l g))
    ["states",a[s "ready";s "ready"];"initial",s "absent";"terminal",a[s "absent"];
     "writers",Json.int 0;"retained_capacity",Json.int 0];
  let bad_library,bad_graph=reconfigure library graph "handoff_gate"(o["source",s "absent";"correlation",s "retained_attempt"])in
  rejects "policy_primitives_unsupported"(fun()->initial(decode bad_library bad_graph));
  rejects "policy_primitives_unsupported"(fun()->initial(decode library(rewire "second" "authorization"(endpoint "evidence" "value")graph)));
  let _,s1=positive implementation in lifecycle_and_feedback implementation s1;
  independent_controls library graph;
  allocation_accounting implementation;
  let legacy=read Sys.argv.(1)in
  let legacy_implementation=decode(get "library" legacy)(get "candidate" legacy)in
  allocation_accounting legacy_implementation;
  let _,legacy_frame=bootstrap legacy_implementation in
  let legacy_json=P.frame_to_json legacy_frame in
  require(text "profile" legacy_json=P.profile && not(List.mem_assoc "machines"(Json.object_fields legacy_json)) &&
    legacy_frame.machines=[])"Legacy observable profile silently acquired staged fields";
  Printf.printf "Staged primitive controls passed; %d explicit rejection controls.\n" !rejected
