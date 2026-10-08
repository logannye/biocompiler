open Bioc_wire
module I = Bioc_domain.Policy_implementation
module P = Bioc_candidate_runtime.Policy_primitives
module S = Bioc_policy_staged_test_support.Literals
let require condition message=if not condition then failwith message
let get key value=Json.field key(Json.object_fields value)
let read path=let channel=open_in_bin path in
  Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
    let length=in_channel_length channel in require(length<=2*1024*1024)"Congruence fixture exceeds its original bound";
    Json.parse_bounded ~max_bytes:(2*1024*1024) ~max_nodes:100000(really_input_string channel length))
let environment:P.environment={executor="cell-1";slots=[
  {slot_id="e1";target="target-1";start_tick=0};
  {slot_id="e2";target="target-2";start_tick=0}];horizon_ticks=6}
let limits:P.limits={max_work=2_000_000;max_events=100_000;max_attempts=32;max_microsteps=100}
let batch ?(observations=[]) ?(feedback=[]) ?(lifecycle=[]) tick:P.input_batch={tick;observations;feedback;lifecycle}
let observation ?(id="sample") ?(input="condition") ?(slot="e1") ?(subject="target-1")
    ?(observer="cell-1") ?(observed=0) evidence:P.observation=
  {observation_id=id;input_id=input;slot_id=slot;observed_tick=observed;observer;subject;evidence}
let equal_result (left_state,left_frame) (right_state,right_frame)=
  require(P.state_fingerprint left_state=P.state_fingerprint right_state)
    "Congruence changed complete successor identity";
  require(Canonical.encode(P.frame_to_json left_frame)=Canonical.encode(P.frame_to_json right_frame))
    "Congruence changed complete ordered frame bytes";
  require(P.usage left_state=P.usage right_state)"Congruence changed original logical resource charges"
let fresh state input=P.step state input
let checked session state input=
  let expected=fresh state input in
  let actual=P.step_with_transition_session session state input in
  equal_result expected actual;actual
let result action=match action()with
  |state,frame->`Value(P.state_fingerprint state,Canonical.encode(P.frame_to_json frame),P.usage state)
  |exception Diagnostic.Error diagnostic->`Failure diagnostic
let same_failure message fresh shared=
  let expected=result fresh and actual=result shared in
  require(expected=actual)message;
  match expected with `Failure _->()|`Value _->failwith(message^": failure was not exercised")
let assert_bounds session=
  let usage=P.transition_usage session in
  require(usage.current_entries<=32 && usage.peak_bytes<=8*1024*1024 && usage.proof_work<=64*1024*1024)
    "Transition witness exceeded its fixed auxiliary bound";
  require(usage.requests=usage.evaluations+usage.reuses)"Transition witness accounting omitted a request"
let converge initial evidence=
  let state,_=fresh initial(batch 0 ~observations:[observation evidence])in
  fresh state(batch 1 ~observations:[observation ~id:"overwrite" ~observed:1 (P.Known false)])
let positive initial=
  let missing,_=converge initial P.Missing_evidence in
  let invalid,_=converge initial P.Invalid_evidence in
  let conflicting,_=converge initial P.Conflicting_evidence in
  require(P.state_fingerprint missing=P.state_fingerprint invalid &&
    P.state_fingerprint missing=P.state_fingerprint conflicting)
    "Independent uncertainty histories did not converge after a strictly newer overwrite";
  let session=P.create_transition_session initial in
  let expected=checked session missing(batch 2)in
  let reused=checked session invalid(batch 2)in
  let reused_again=checked session conflicting(batch 2)in
  equal_result expected reused;equal_result expected reused_again;
  let usage=P.transition_usage session in
  require(usage.requests=3 && usage.evaluations=1 && usage.reuses=2 && usage.current_entries=1)
    "Exact candidate convergence did not avoid two real transition evaluations";
  require(usage.proof_work>0 && usage.peak_bytes>0)"Transition proof work or retained footprint was hidden";
  assert_bounds session;
  let separate=P.create_transition_session initial in
  ignore(checked separate invalid(batch 2));
  require((P.transition_usage separate).reuses=0)"A fresh invocation inherited a prior transition witness";
  Printf.printf "candidate_congruence_positive requests=%d evaluations=%d reuses=%d proof_work=%d peak_bytes=%d\n%!"
    usage.requests usage.evaluations usage.reuses usage.proof_work usage.peak_bytes
let controls implementation initial=
  let rejected=ref 0 in
  let no_hit message session action=
    let before=(P.transition_usage session).reuses in ignore(action());
    require((P.transition_usage session).reuses=before)message;incr rejected in
  let missing,_=converge initial P.Missing_evidence in
  let session=P.create_transition_session initial in
  ignore(checked session missing(batch 2));
  let with_budget ()=
    let expected=P.step ~max_step_work:1_000_000 ~max_step_retained:90_000 missing(batch 2)in
    let actual=P.step_with_transition_session session ~max_step_work:1_000_000 ~max_step_retained:90_000 missing(batch 2)in
    equal_result expected actual in
  no_hit "Changed optional resource guards reused an unrelated witness" session with_budget;
  List.iter(fun(kind,action,shared)->same_failure kind action shared;incr rejected)[
    "A retained transition bypassed a smaller work guard",
      (fun()->P.step ~max_step_work:1 missing(batch 2)),
      (fun()->P.step_with_transition_session session ~max_step_work:1 missing(batch 2));
    "A retained transition bypassed a smaller trace guard",
      (fun()->P.step ~max_step_retained:1 missing(batch 2)),
      (fun()->P.step_with_transition_session session ~max_step_retained:1 missing(batch 2));
    "A retained transition bypassed an invalid guard",
      (fun()->P.step ~max_step_work:0 missing(batch 2)),
      (fun()->P.step_with_transition_session session ~max_step_work:0 missing(batch 2))];
  let foreign=P.initialize ~implementation ~environment ~limits in
  let foreign,_=converge foreign P.Missing_evidence in
  no_hit "Structurally similar foreign plans acquired invocation-owned witnesses" session
    (fun()->checked session foreign(batch 2));
  let other_limits={limits with max_work=2_000_001}in
  let limited=P.initialize ~implementation ~environment ~limits:other_limits in
  let limited,_=converge limited P.Missing_evidence in
  no_hit "Changed original limits acquired another plan's witness" session(fun()->checked session limited(batch 2));
  let altered,_=fresh initial(batch 0 ~observations:[observation ~id:"other-occurrence" P.Missing_evidence])in
  let altered,_=fresh altered(batch 1 ~observations:[observation ~id:"overwrite" ~observed:1 (P.Known false)])in
  no_hit "A different consumed occurrence identity was hidden by final evidence equality" session
    (fun()->checked session altered(batch 2));
  let older,_=fresh initial(batch 0 ~observations:[observation P.Missing_evidence])in
  let older,_=fresh older(batch 1 ~observations:[observation ~id:"overwrite" ~observed:0 (P.Known false)])in
  no_hit "Equal truth with different evidence age or occurrences established congruence" session
    (fun()->checked session older(batch 2));
  let direct=P.create_transition_session initial in
  ignore(checked direct initial(batch 0 ~observations:[observation P.Missing_evidence]));
  no_hit "Missing and invalid input evidence were identified before overwrite" direct
    (fun()->checked direct initial(batch 0 ~observations:[observation P.Invalid_evidence]));
  let a=observation ~id:"a" (P.Known false) and b=observation ~id:"b" ~slot:"e2" ~subject:"target-2" (P.Known false)in
  ignore(checked direct initial(batch 0 ~observations:[a;b]));
  no_hit "Ordered observation batches were treated as sets" direct
    (fun()->checked direct initial(batch 0 ~observations:[b;a]));
  List.iter(fun(message,input)->
    let before=(P.transition_usage direct).current_entries in
    same_failure message (fun()->fresh initial input)(fun()->P.step_with_transition_session direct initial input);
    same_failure message (fun()->fresh initial input)(fun()->P.step_with_transition_session direct initial input);
    require((P.transition_usage direct).current_entries=before)"A failed transition created a retained proof";
    incr rejected)[
      "Foreign recipient was hidden by a partial input key",batch 0 ~observations:[observation ~subject:"wrong" P.Missing_evidence];
      "Foreign observer was hidden by a partial input key",batch 0 ~observations:[observation ~observer:"wrong" P.Missing_evidence];
      "Wrong primitive input was hidden by a partial input key",batch 0 ~observations:[observation ~input:"absent" P.Missing_evidence];
      "Wrong tick was hidden by a partial input key",batch 1;
      "Duplicate occurrence was hidden by a partial input key",batch 0 ~observations:[a;a]];
  let reset=batch 2 ~lifecycle:["e1",P.Reset]in
  no_hit "Lifecycle generation changes were hidden by equal settled truth" session(fun()->checked session missing reset);
  let large=batch 2 ~observations:(List.init 800(fun index->observation
    ~id:(string_of_int index^String.make 240 'x') ~observed:2 P.Missing_evidence))in
  let before=(P.transition_usage session).bypasses in
  same_failure "Auxiliary key preflight changed the ordinary work-limit diagnostic"
    (fun()->P.step ~max_step_work:1 missing large)
    (fun()->P.step_with_transition_session session ~max_step_work:1 missing large);
  require((P.transition_usage session).bypasses>before)"Oversized proof key did not fall back to fresh execution";
  incr rejected;
  let exhausted=P.create_transition_session initial in
  for _index=1 to 64 do
    same_failure "Exhausted auxiliary comparison work changed a fresh primitive failure"
      (fun()->P.step ~max_step_work:1 missing large)
      (fun()->P.step_with_transition_session exhausted ~max_step_work:1 missing large)
  done;
  require((P.transition_usage exhausted).proof_work=64*1024*1024)
    "Auxiliary comparison-work exhaustion was not exercised";
  ignore(checked exhausted missing(batch 2));
  require((P.transition_usage exhausted).reuses=0 && (P.transition_usage exhausted).current_entries=0)
    "Exhausted proof bookkeeping prevented a fresh successful transition";
  incr rejected;
  let full=P.create_transition_session initial in
  for index=0 to 39 do
    ignore(checked full initial(batch 0 ~observations:[observation ~id:("bounded/"^string_of_int index) P.Missing_evidence]))
  done;
  let full_usage=P.transition_usage full in
  require(full_usage.requests=40 && full_usage.evaluations=40 && full_usage.reuses=0 &&
    full_usage.current_entries=32 && full_usage.bypasses=8)
    "A full bounded witness table changed ordinary candidate execution";
  incr rejected;
  List.iter assert_bounds[session;direct;full;exhausted];
  require(!rejected=19)"Incomplete transition congruence negative control census";
  Printf.printf "candidate_congruence_negative_controls=%d\n%!" !rejected
let staged_controls ()=
  let library,graph=S.fixture()in
  let implementation=S.decode library graph in
  let environment:P.environment={executor="cell";slots=[
    {slot_id="e1";target="target1";start_tick=0};{slot_id="e2";target="target2";start_tick=0}];horizon_ticks=8}in
  let limits:P.limits={max_work=8_000_000;max_events=200_000;max_attempts=32;max_microsteps=20}in
  let initial=P.initialize ~implementation ~environment ~limits in
  let observe slot tick value=observation ~id:(slot^"/"^string_of_int tick) ~slot
    ~observer:"cell" ~subject:(if slot="e1"then "target1"else "target2") ~observed:tick(P.Known value)in
  let initial0,_=fresh initial(batch 0 ~observations:[observe "e1" 0 false;observe "e2" 0 false])in
  let first,started=fresh initial0(batch 1 ~observations:[observe "e1" 1 true;observe "e2" 1 true])in
  require(List.map(fun(a:P.attempt)->a.attempt_id,a.machine)started.creations=
    ["primitive/attempt/1",Some "machine";"primitive/attempt/2",Some "machine"])
    "Congruence stage witness omitted real retained attempts and machine ownership";
  let feedback id slot ordinal outcome:P.feedback={feedback_id=id;input_id="first_feedback";
    attempt_id="primitive/attempt/"^string_of_int ordinal;executor="cell";
    subject=(if slot="e1"then "target1"else "target2");slot_id=slot;outcome}in
  let completed=feedback "a1" "e1" 1 P.Complete and failed=feedback "a2" "e2" 2 P.Fail in
  let input=batch 2 ~feedback:[completed;failed]in
  let session=P.create_transition_session initial in
  let next,frame=checked session first input in
  ignore(checked session first input);
  require((P.transition_usage session).reuses=1)"A complete staged transition did not reuse its fresh witness";
  let machine slot (frame:P.frame)=List.find(fun(value:P.machine_snapshot)->value.binding.slot=Some slot)frame.machines in
  let e1=machine "e1" frame and e2=machine "e2" frame in
  require(e1.state="second" && e1.retained_attempts=["primitive/attempt/3"] &&
    e2.state="failed" && e2.retained_attempts=[] && List.length frame.attempts=3)
    "Staged congruence omitted machine state, lineage or historical attempt records";
  let rejected=ref 0 in
  let no_hit message state input=
    let hits=(P.transition_usage session).reuses in
    let result=checked session state input in
    require((P.transition_usage session).reuses=hits)message;incr rejected;result in
  ignore(no_hit "Changed correlated feedback outcomes acquired a retained witness" first
    (batch 2 ~feedback:[{completed with outcome=P.Fail};failed]));
  ignore(no_hit "Changed feedback attempt addresses acquired a retained witness" first
    (batch 2 ~feedback:[{completed with attempt_id="primitive/attempt/99"};failed]));
  ignore(no_hit "Changed feedback input ownership acquired a retained witness" first
    (batch 2 ~feedback:[{completed with input_id="second_feedback"};failed]));
  let other,_=no_hit "Changed feedback occurrence identities acquired a retained witness" first
    (batch 2 ~feedback:[{completed with feedback_id="b1"};failed])in
  ignore(checked session next(batch 3));
  ignore(no_hit "Consumed feedback identities disappeared from complete predecessor equality" other(batch 3));
  let reset,_=fresh first(batch 2 ~lifecycle:["e1",P.Reset] ~observations:[observe "e1" 2 false])in
  ignore(no_hit "Reset machine lineage and generations disappeared from predecessor equality" reset(batch 3));
  assert_bounds session;
  require(!rejected=6)"Incomplete staged transition congruence negative control census";
  Printf.printf "candidate_congruence_staged_negative_controls=%d\n%!" !rejected
let ()=
  require(Array.length Sys.argv=2)"Expected original primitive fixture";
  let fixture=read Sys.argv.(1)in
  let implementation=I.of_json ~library:(I.library_of_json(get "library" fixture))(get "candidate" fixture)in
  let initial=P.initialize ~implementation ~environment ~limits in
  positive initial;controls implementation initial;staged_controls()
