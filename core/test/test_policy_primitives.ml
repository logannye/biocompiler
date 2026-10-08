open Bioc_wire
module I = Bioc_domain.Policy_implementation
module P = Bioc_candidate_runtime.Policy_primitives
let require condition message=if not condition then failwith message
let str value=Json.String value
let obj value=Json.Object value
let arr value=Json.Array value
let get key value=Json.field key(Json.object_fields value)
let items key value=Json.array(get key value)
let text key value=Json.string(get key value)
let replace key item value=obj(List.map(fun(name,value)->name,(if name=key then item else value))(Json.object_fields value))
let endpoint node port=obj["node",str node;"port",str port]
let rewire node port producer candidate=replace "wires"(arr(List.map(fun wire->
  if get "consumer" wire=endpoint node port then replace "producer" producer wire else wire)(items "wires" candidate)))candidate
let rehash model=
  let body=get "body" model in
  model |> replace "configuration_digest"(str(Canonical.fingerprint(get "configuration" body)))
    |> replace "identity"(replace "content_fingerprint"(str(Canonical.fingerprint body))(get "identity" model))
let repin library candidate=replace "authority"(replace "library_digest"(str(Canonical.fingerprint library))(get "authority" candidate))candidate
let decode library candidate=I.of_json ~library:(I.library_of_json library)(repin library candidate)
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  let length=in_channel_length channel in require(length<=2*1024*1024)"Primitive fixture too large";
  Json.parse_bounded ~max_bytes:(2*1024*1024) ~max_nodes:100000(really_input_string channel length))
let rejected=ref 0
let rejects code action=match action()with
  |_->failwith("Primitive mutant accepted: "^code)
  |exception Diagnostic.Error diagnostic->require(diagnostic.code="policy_primitives_"^code)
      ("Wrong primitive rejection: "^diagnostic.code^" expected "^code);incr rejected
let environment:P.environment={executor="cell-1";slots=[
  {slot_id="e1";target="target-1";start_tick=0};{slot_id="e2";target="target-2";start_tick=0}];horizon_ticks=6}
let limits:P.limits={max_work=1_000_000;max_events=100_000;max_attempts=32;max_microsteps=100}
let initial ?(limits=limits) implementation=P.initialize ~implementation ~environment ~limits
let batch ?(observations=[]) ?(feedback=[]) ?(lifecycle=[]) tick:P.input_batch={tick;observations;feedback;lifecycle}
let observation ?(input_id="condition") ?observed ?(suffix="") slot tick evidence:P.observation={
  observation_id=slot^"/"^input_id^"/"^string_of_int tick^suffix;input_id;slot_id=slot;
  observed_tick=Option.value observed ~default:tick;observer="cell-1";
  subject=(if slot="e1"then "target-1"else "target-2");evidence}
let feedback ?(slot="e1") ?(suffix="") ordinal outcome:P.feedback={feedback_id="feedback/"^string_of_int ordinal^suffix;
  input_id="feedback";attempt_id="primitive/attempt/"^string_of_int ordinal;executor="cell-1";
  subject=(if slot="e1"then "target-1"else "target-2");slot_id=slot;outcome}
let bootstrap state=P.step state(batch 0 ~observations:[observation "e1" 0(P.Known false);observation "e2" 0(P.Known false)])
let port (frame:P.frame) node port slot=List.find(fun(value:P.port_value)->value.endpoint.node_id=node && value.endpoint.port_id=port && value.binding.slot=Some slot)frame.outputs
let truth frame node port_name slot=match(port frame node port_name slot).signal with P.Truth value->value|_->failwith "Expected truth output"
let assert_truth frame node port_name slot value reasons=
  let actual=truth frame node port_name slot in require(actual.value=value && actual.reasons=reasons)("Truth/definedness/reasons differ for "^node^"/"^slot)
let attempt (frame:P.frame) ordinal=List.find(fun(value:P.attempt)->value.ordinal=ordinal)frame.attempts
let action_kinds (frame:P.frame)=List.map(fun(value:P.action)->match value.detail with
  |P.Observation_batch _->"observation"|P.State_written _->"write"|P.Effect_requested _->"request"
  |P.Machine_transition _->"machine"
  |P.Authorization_changed _->"authorization"|P.Feedback_accepted _->"feedback"
  |P.Feedback_rejected _->"rejected"|P.Deferred _->"deferred"|P.Undefined_commit _->"undefined"|P.Suppressed _->"suppressed")frame.actions
let reconfigure library candidate node_id transform=
  let selected=List.find(fun n->text "id" n=node_id)(items "nodes" candidate)in
  let original=get "model" selected in
  let changed=List.find(fun m->get "identity" m=original)(items "models" library)
    |>fun m->rehash(replace "body"(transform(get "body" m))m)in
  let library=replace "models"(arr(List.map(fun m->if get "identity" m=original then changed else m)(items "models" library)))library in
  let candidate=replace "nodes"(arr(List.map(fun n->if get "model" n=original then
    n |>replace "model"(get "identity" changed)|>replace "configuration_digest"(get "configuration_digest" changed)else n)(items "nodes" candidate)))candidate in
  library,repin library candidate
let refresh_exports library candidate=
  let models=I.models(I.library_of_json library)in
  let exports=List.concat_map(fun node->
    let model=List.find(fun(model:I.model)->Bioc_domain.Pinned_identity.to_json model.identity=get "model" node)models in
    List.filter_map(fun(port:I.port)->if port.direction=I.Output then Some(endpoint(text "id" node)port.port_id)else None)(I.ports model.primitive))
    (items "nodes" candidate)in
  replace "semantic_exports"(arr exports)candidate

let basic fixture=
  let library=get "library" fixture and candidate=get "candidate" fixture in
  let implementation=decode library candidate in
  let root=initial implementation in
  let root_id=P.state_fingerprint root in
  let root_usage=P.usage root in
  let s0,f0=bootstrap root in
  require(P.state_fingerprint root=root_id && P.next_tick root=0)"Initial branch was mutated";
  require(P.usage root=root_usage && (P.usage s0).work>root_usage.work && (P.usage s0).retained>root_usage.retained)
    "Usage counters changed a predecessor or omitted charged successor work";
  assert_truth f0 "seen" "value" "e1"(Some I.False)[];
  let s1,f1=P.step s0(batch 1 ~observations:[observation "e1" 1(P.Known true)])in
  require(List.length f1.creations=1)"Literal rising edge did not create exactly one attempt";
  let created=List.hd f1.creations in
  require(created.bank="attempt" && created.gate="gate" && created.guard={I.node_id="evidence";port_id="value"} &&
    created.binding={P.slot=Some "e1";generation=0} && created.subject="target-1" && created.product="fixture.product.alpha" &&
    created.started_tick=1 && created.deadline_tick=3 && List.length created.causes=1)"Creation lost actual graph identity or correlation";
  require(action_kinds f1=["observation";"write";"request"])"Neutral actions changed literal phase order";
  require(List.map(fun(a:P.action)->a.microstep)f1.actions=[0;1;1])"Neutral actions lost actual microsteps";
  require(List.exists(fun(e:P.event)->e.kind=P.Primitive_event I.Rising && List.mem e.event_id created.causes)f1.events)
    "Request cause does not identify the actual rising event";
  require(List.length f1.rounds=2)"Requested/initiated events did not enter the next microstep";
  require(List.filter_map(fun(e:P.event)->match e.kind with
    |P.Primitive_event I.Requested->Some "requested"|P.Primitive_event I.Initiated->Some "initiated"|_->None)f1.events=["requested";"initiated"])
    "Effect initiation was emitted before its request";
  assert_truth f1 "seen" "value" "e1"(Some I.True)[];
  assert_truth f1 "seen" "value" "e2"(Some I.False)[];
  let s2,f2=P.step s1(batch 2 ~observations:[observation "e2" 2(P.Known true)])in
  require(List.length f2.creations=1 && (List.hd f2.creations).binding.slot=Some "e2")"Equal evidence mixed target identities";
  let s3,f3=P.step s2(batch 3 ~feedback:[feedback 1 P.Complete;feedback ~slot:"e2" 2 P.Fail])in
  require((attempt f3 1).status=P.Completed && (attempt f3 2).status=P.Failed)"Feedback lost completion/failure distinction";
  require(not(List.exists(fun(e:P.event)->e.kind=P.Primitive_event I.Timed_out)f3.events))"Timeout preceded equal-deadline feedback";
  let _,f4=P.step s3(batch 4)in
  assert_truth f4 "evidence" "value" "e1" None[P.Stale];
  assert_truth f4 "evidence" "value" "e2" None[P.Stale];
  assert_truth f4 "seen" "value" "e1"(Some I.True)[];
  let before_branch=P.state_fingerprint s1 in
  rejects "work_limit"(fun()->P.step ~max_step_work:1 s1(batch 2));
  rejects "trace_limit"(fun()->P.step ~max_step_retained:1 s1(batch 2));
  rejects "limit"(fun()->P.step ~max_step_work:0 s1(batch 2));
  let bounded,_=P.step ~max_step_work:limits.max_work ~max_step_retained:limits.max_events s1(batch 2)
  and unbounded,_=P.step s1(batch 2)in
  require(P.state_fingerprint bounded=P.state_fingerprint unbounded)"Per-call resource guards changed semantic state identity";
  let r2,reset=P.step s1(batch 2 ~lifecycle:["e1",P.Reset] ~observations:[observation "e1" 2(P.Known false)])in
  require(P.state_fingerprint s1=before_branch)"Reset mutated sibling prefix";
  require((attempt reset 1).status=P.Reset_invalidated)"Reset failed to invalidate an active old attempt";
  assert_truth reset "seen" "value" "e1"(Some I.False)[];
  let _,r3=P.step r2(batch 3 ~observations:[observation "e1" 3(P.Known true)] ~feedback:[feedback 1 P.Complete])in
  require(List.length r3.creations=1 && (List.hd r3.creations).binding.generation=1 && (attempt r3 2).status=P.Active)
    "New generation reused old attempt identity or lost its edge bootstrap";
  require(List.exists(fun(a:P.action)->match a.detail with P.Feedback_rejected(_,_,"stale_attempt")->true|_->false)r3.actions)
    "Late prior-generation feedback was not retained/rejected";
  let ended,end_frame=P.step s1(batch 2 ~lifecycle:["e1",P.End])in
  require((attempt end_frame 1).status=P.End_invalidated)"End failed to invalidate attempts";
  let _,late=P.step ended(batch 3 ~feedback:[feedback 1 P.Complete])in
  require((attempt late 1).status=P.End_invalidated)"Late feedback resurrected an ended encounter";
  let _,quiet2=P.step s1(batch 2)in
  require((attempt quiet2 1).status=P.Active)"Quiet time advanced deadline early";
  let quiet_state,_=P.step s1(batch 2)in
  let _,quiet3=P.step quiet_state(batch 3)in
  require((attempt quiet3 1).status=P.Timed_out)"Quiet timeout required a new observation";
  let _,older=P.step s1(batch 2 ~observations:[observation ~observed:0 "e1" 2(P.Known false)])in
  assert_truth older "evidence" "value" "e1"(Some I.True)[];
  require(older.creations=[] && List.exists(fun(e:P.event)->e.kind=P.Primitive_event I.Updated)older.events)
    "Older arrival overwrote retained evidence or lost its update event";
  let _,conflict=P.step s0(batch 1 ~observations:[observation ~suffix:"a" "e1" 1(P.Known true);observation ~suffix:"b" "e1" 1(P.Known false)])in
  assert_truth conflict "evidence" "value" "e1" None[P.Conflicting];require(conflict.creations=[])"Conflicting evidence created an effect";
  List.iter(fun evidence->let _,unknown=P.step root(batch 0 ~observations:[observation "e1" 0 evidence])in
    require(unknown.creations=[])"Unavailable first observation fabricated a rising edge")
    [P.Missing_evidence;P.Invalid_evidence;P.Conflicting_evidence];
  let _,unbootstrapped=P.step root(batch 0 ~observations:[observation "e1" 0(P.Known true)])in
  require(unbootstrapped.creations=[])"Unknown-to-true was incorrectly treated as observed rising";
  rejects "time"(fun()->P.step s1(batch 3));
  rejects "identity"(fun()->P.step r2(batch 3 ~observations:[observation ~observed:1 "e1" 3(P.Known true)]));
  rejects "feedback"(fun()->P.step s2(batch 3 ~feedback:[feedback 1 P.Complete;feedback ~suffix:"conflict" 1 P.Fail]));
  rejects "feedback"(fun()->P.step s2(batch 3 ~feedback:[feedback 1 P.Complete;
    {(feedback ~suffix:"wrong-address" 1 P.Fail)with subject="target-2"}]));
  rejects "identity"(fun()->P.step s1(batch 2 ~feedback:[{(feedback 1 P.Complete)with feedback_id="e1/condition/1"}]));
  rejects "identity"(fun()->P.step root(batch 0 ~lifecycle:["e1",P.Reset]));
  let _,wrong=P.step s1(batch 2 ~feedback:[{(feedback 1 P.Complete)with subject="target-2"}])in
  require((attempt wrong 1).status=P.Active && List.mem "rejected"(action_kinds wrong))"Wrong feedback identity changed an attempt";
  rejects "unsupported"(fun()->initial(decode library(rewire "attempt" "authorization"(endpoint "true" "out")candidate)));
  rejects "unsupported"(fun()->initial(decode library(rewire "edge" "in"(endpoint "seen" "value")candidate)));
  let low_limits={limits with max_work=1}in
  rejects "work_limit"(fun()->bootstrap(initial ~limits:low_limits implementation));
  let one_round=initial ~limits:{limits with max_microsteps=1} implementation in
  let one0,_=bootstrap one_round in
  rejects "settling_limit"(fun()->P.step one0(batch 1 ~observations:[observation "e1" 1(P.Known true)]));
  require(P.state_fingerprint s1=before_branch)"Rejected or successful sibling steps changed a prior state";
  let altered_limits=initial ~limits:{limits with max_attempts=31} implementation in
  require(P.state_fingerprint altered_limits<>root_id)"Fingerprint omitted future allocation bound";
  require(P.state_fingerprint(P.initialize ~implementation ~environment:{environment with executor="different"} ~limits)<>root_id)
    "Fingerprint omitted executor identity";
  ignore(Canonical.encode(P.frame_to_json f1));
  let capacity_library,capacity_candidate=reconfigure library candidate "attempt"(fun body->replace "configuration"
    ((get "configuration" body)|>replace "capacity"(Json.int 1)|>replace "timeout_ticks"(Json.int 4))body)in
  let capacity_graph=decode capacity_library capacity_candidate in
  let cap0,_=bootstrap(initial capacity_graph)in
  let cap1,cap_frame=P.step cap0(batch 1 ~observations:[observation "e1" 1(P.Known true);observation "e2" 1(P.Known true)])in
  require(List.length cap_frame.creations=2)"Per-slot capacity collapsed two distinct encounter banks";
  let cap2,_=P.step cap1(batch 2 ~observations:[observation "e1" 2(P.Known false)])in
  let cap_id=P.state_fingerprint cap2 in
  rejects "capacity"(fun()->P.step cap2(batch 3 ~observations:[observation "e1" 3(P.Known true)]));
  require(P.state_fingerprint cap2=cap_id)"Capacity failure partially committed its batch";
  let _,freed=P.step cap2(batch 3 ~observations:[observation "e1" 3(P.Known true)] ~feedback:[feedback 1 P.Complete])in
  require(List.length freed.creations=1 && (List.hd freed.creations).ordinal=3)"Completed attempt failed to release active capacity or identity was reused";
  library,candidate

let extend_operand library candidate use_not=
  let original=List.find(fun model->text "primitive"(get "body" model)="evidence_bank")(items "models" library)in
  let not_model=original|>replace "identity"(replace "id"(str "fixture.runtime.not")(get "identity" original))
    |>(fun model->replace "body"((get "body" model)|>replace "primitive"(str "truth_not")|>replace "configuration"(obj []))model)|>rehash in
  let library=replace "models"(arr(items "models" library@[not_model]))library in
  let node id model=obj["id",str id;"model",get "identity" model;"configuration_digest",get "configuration_digest" model]in
  let candidate=candidate
    |>replace "nodes"(arr(items "nodes" candidate@[node "other" original;node "other_not" not_model]))
    |>replace "wires"(arr(items "wires" candidate@[obj["producer",endpoint "other" "value";"consumer",endpoint "other_not" "in"]]))
    |>replace "inputs"(arr(items "inputs" candidate@[obj["id",str "other_input";"kind",str "evidence";"consumer",endpoint "other" "samples"]]))
    |>replace "semantic_exports"(arr(items "semantic_exports" candidate@[endpoint "other" "value";endpoint "other" "updated";endpoint "other_not" "out"]))
    |>replace "occurrences"(arr(items "occurrences" candidate@List.map(fun(id,port)->obj["source_path",str("/runtime/"^id);
      "role",str "predicate";"disposition",str "executable";"targets",arr[endpoint id port]])["other","value";"other_not","out"]))
    |>rewire "commit" "value0"(if use_not then endpoint "other_not" "out"else endpoint "other" "value")in
  decode library candidate
let definedness library candidate=
  let raw=extend_operand library candidate false and negated=extend_operand library candidate true in
  let raw0,_=bootstrap(initial raw)and not0,_=bootstrap(initial negated)in
  let _,undefined=P.step raw0(batch 1 ~observations:[observation "e1" 1(P.Known true)])
  and _,defined=P.step not0(batch 1 ~observations:[observation "e1" 1(P.Known true)])in
  assert_truth undefined "other" "value" "e1" None[P.Missing];
  assert_truth undefined "other_not" "out" "e1"(Some I.Unknown)[P.Missing];
  require(undefined.creations=[] && List.mem "undefined"(action_kinds undefined))"Undefined assignment partially executed the atomic effect";
  assert_truth undefined "seen" "value" "e1"(Some I.False)[];
  require(List.length defined.creations=1)"Defined Unknown was treated as an undefined assignment";
  assert_truth defined "seen" "value" "e1"(Some I.Unknown)[]

let truth_graph original_library original_candidate specs links external_inputs=
  let template=List.hd(items "models" original_library)in
  let models=List.map(fun(id,tag,configuration)->
    let replication=if tag="truth_constant"then obj["kind",str "executor"]else get "replication"(get "body" template)in
    template|>replace "identity"(replace "id"(str("fixture.truth."^id))(get "identity" template))
      |>replace "body"((get "body" template)|>replace "primitive"(str tag)|>replace "configuration" configuration|>replace "replication" replication)
      |>rehash)specs in
  let library=replace "models"(arr models)original_library in
  let nodes=List.map2(fun(id,_,_)model->obj["id",str id;"model",get "identity" model;"configuration_digest",get "configuration_digest" model])specs models in
  let candidate=original_candidate|>replace "nodes"(arr nodes)
    |>replace "wires"(arr(List.map(fun(a,b,c,d)->obj["producer",endpoint a b;"consumer",endpoint c d])links))
    |>replace "inputs"(arr(List.map(fun(id,node)->obj["id",str id;"kind",str "evidence";"consumer",endpoint node "samples"])external_inputs))
    |>replace "atomic_groups"(arr [])
    |>replace "occurrences"(arr(List.map(fun(id,tag,_)->obj["source_path",str("/runtime/truth/"^id);"role",str "predicate";
      "disposition",str "executable";"targets",arr[endpoint id(if tag="evidence_bank"then "value"else "out")]])specs))
    |>refresh_exports library in
  decode library candidate
let truth_profiles library candidate=
  let graph=truth_graph library candidate[
    "a","evidence_bank",obj["freshness_ticks",Json.int 1];"b","evidence_bank",obj["freshness_ticks",Json.int 1];
    "false","truth_constant",obj["value",str "false"];"true","truth_constant",obj["value",str "true"];
    "all","truth_all",obj["arity",Json.int 2];"any","truth_any",obj["arity",Json.int 2];
    "equal","truth_equal",obj[];"not","truth_not",obj[]][
    "a","value","all","in0";"false","out","all","in1";
    "a","value","any","in0";"true","out","any","in1";
    "all","out","equal","left";"false","out","equal","right";"b","value","not","in"]
    ["condition","a";"other","b"]in
  let state,frame=P.step(initial graph)(batch 0 ~observations:[observation "e1" 0 P.Invalid_evidence])in
  assert_truth frame "all" "out" "e1"(Some I.False)[P.Invalid];
  assert_truth frame "any" "out" "e1"(Some I.True)[P.Invalid];
  assert_truth frame "equal" "out" "e1"(Some I.True)[];
  assert_truth frame "not" "out" "e1"(Some I.Unknown)[P.Missing];
  let _,quiet=P.step state(batch 1)in
  assert_truth quiet "a" "value" "e1" None[P.Invalid];
  let amplify=truth_graph library candidate[
    "a","evidence_bank",obj["freshness_ticks",Json.int 1];
    "fan1","truth_all",obj["arity",Json.int 64];"fan2","truth_all",obj["arity",Json.int 64];
    "copy","truth_not",obj[]]
    (List.init 64(fun i->"a","value","fan1","in"^string_of_int i)@
      List.init 64(fun i->"fan1","out","fan2","in"^string_of_int i)@["fan2","out","copy","in"])
    ["condition","a"]in
  rejects "trace_limit"(fun()->P.step(initial ~limits:{limits with max_events=10000;max_work=100_000_000}amplify)(batch 0))

let exclusion fixture=
  let library=get "library" fixture and candidate=get "candidate" fixture in
  let graph=decode library candidate in
  let zero,initial_frame=bootstrap(initial graph)in
  List.iter(fun slot->assert_truth initial_frame "selected" "value" slot(Some I.False)[];
    assert_truth initial_frame "excluded" "value" slot(Some I.False)[])["e1";"e2"];
  let one,f1=P.step zero(batch 1 ~observations:[observation "e1" 1(P.Known true)])in
  assert_truth f1 "selected" "value" "e1"(Some I.True)[];assert_truth f1 "excluded" "value" "e1"(Some I.False)[];
  let two,f2=P.step one(batch 2 ~observations:[observation "e1" 2(P.Known false);observation "e2" 2(P.Known true)])in
  assert_truth f2 "selected" "value" "e1"(Some I.False)[];assert_truth f2 "excluded" "value" "e1"(Some I.True)[];
  assert_truth f2 "selected" "value" "e2"(Some I.True)[];assert_truth f2 "excluded" "value" "e2"(Some I.False)[];
  require((attempt f2 1).status=P.Active && (attempt f2 1).authorization=I.False)"Negative branch silently cancelled a continuing attempt";
  let _,quiet=P.step two(batch 3)in
  require((attempt quiet 1).status=P.Active)"Quiet tick inferred unsupported cancellation";
  let prestate=decode library(rewire "select_commit" "value1"(endpoint "selected" "value")candidate)in
  let pre0,_=bootstrap(initial prestate)in
  let _,pre1=P.step pre0(batch 1 ~observations:[observation "e1" 1(P.Known true)])in
  assert_truth pre1 "selected" "value" "e1"(Some I.True)[];
  assert_truth pre1 "excluded" "value" "e1"(Some I.False)[];
  let simultaneous=candidate|>rewire "exclude_gate" "on"(endpoint "positive_edge" "events")
    |>rewire "exclude_gate" "guard"(endpoint "true" "out")in
  let both0,_=bootstrap(initial(decode library simultaneous))in
  rejects "exclusive"(fun()->P.step both0(batch 1 ~observations:[observation "e1" 1(P.Known true)]));
  let priority_library,priority_candidate=reconfigure library simultaneous "arbiter"(fun body->body
    |>replace "primitive"(str "priority_arbiter")|>replace "configuration"(obj["order",arr[Json.int 1;Json.int 0]]))in
  let priority0,_=bootstrap(initial(decode priority_library priority_candidate))in
  let _,priority1=P.step priority0(batch 1 ~observations:[observation "e1" 1(P.Known true)])in
  require(priority1.creations=[] && List.mem "suppressed"(action_kinds priority1))"Priority failed to suppress the losing request";
  assert_truth priority1 "selected" "value" "e1"(Some I.False)[];
  assert_truth priority1 "excluded" "value" "e1"(Some I.True)[];
  (* A third lane distinguishes priority-order suppression from candidate order. *)
  let third_library,third_candidate=reconfigure priority_library priority_candidate "arbiter"(fun body->
    replace "configuration"(obj["order",arr[Json.int 2;Json.int 1;Json.int 0]])body)in
  let third_library,third_candidate=reconfigure third_library third_candidate "selected"(fun body->
    replace "configuration"((get "configuration" body)|>replace "writers"(Json.int 3))body)in
  let copy_node old id=List.find(fun node->text "id" node=old)(items "nodes" third_candidate)|>replace "id"(str id)in
  let new_wires=List.map(fun(a,b,c,d)->obj["producer",endpoint a b;"consumer",endpoint c d])[
    "positive_edge","events","third_gate","on";"true","out","third_gate","guard";
    "third_gate","candidate","arbiter","in2";"arbiter","out2","third_commit","grant";
    "true","out","third_commit","value0";"false","out","third_commit","value1";
    "third_commit","write0","selected","write2";"third_commit","write1","excluded","write2"]in
  let third_candidate=third_candidate
    |>replace "nodes"(arr(items "nodes" third_candidate@[copy_node "select_gate" "third_gate";copy_node "exclude_commit" "third_commit"]))
    |>replace "wires"(arr(items "wires" third_candidate@new_wires))
    |>replace "atomic_groups"(arr[obj["id",str "exclusive";"arbiter",str "arbiter";
      "commits",arr(List.map str["select_commit";"exclude_commit";"third_commit"])]])
    |>replace "occurrences"(arr(items "occurrences" third_candidate@List.map(fun(node,port)->obj[
      "source_path",str("/runtime/"^node);"role",str "predicate";"disposition",str "executable";
      "targets",arr[endpoint node port]])["third_gate","candidate";"third_commit","write0"]))
    |>refresh_exports third_library in
  let third0,_=bootstrap(initial(decode third_library third_candidate))in
  let _,third1=P.step third0(batch 1 ~observations:[observation "e1" 1(P.Known true)])in
  let suppression=List.filter_map(fun(action:P.action)->match action.detail with P.Suppressed(a,selected)->
    require(selected="third_gate")"Wrong three-lane winner";Some a.gate|_->None)third1.actions in
  require(suppression=["exclude_gate";"select_gate"])"Suppressed activations lost explicit priority order";
  require(third1.creations=[])"Suppressed lower-priority lane still requested an effect"

let ()=
  require(Array.length Sys.argv=3)"Supply original and exclusion primitive graph fixtures";
  let library,candidate=basic(read Sys.argv.(1))in
  definedness library candidate;truth_profiles library candidate;exclusion(read Sys.argv.(2));
  Printf.printf "Independent actual-graph primitive literals passed with %d rejection controls; source preservation and material acceptance unassessed\n" !rejected
