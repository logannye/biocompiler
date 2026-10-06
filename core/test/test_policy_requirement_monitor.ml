open Bioc_wire
module D = Bioc_domain.Policy_document
module O = Bioc_domain.Policy_operational
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
module M = Bioc_realization_checker.Policy_requirement_monitor
let require condition message=if not condition then failwith message
let obj fields=Json.Object fields
let str value=Json.String value
let arr values=Json.Array values
let get name value=Json.field name(Json.object_fields value)
let text name value=Json.string(get name value)
let items name value=Json.array(get name value)
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_bounded ~max_bytes:(4*1024*1024) ~max_nodes:200000(really_input_string channel(in_channel_length channel)))
let rec set path replacement value=match path,value with
  |[],_->replacement
  |key::rest,Json.Object fields->require(List.mem_assoc key fields)("Missing mutation field "^key);
      obj(List.map(fun(name,value)->name,if name=key then set rest replacement value else value)fields)
  |index::rest,Json.Array values->arr(List.mapi(fun i value->if i=int_of_string index then set rest replacement value else value)values)
  |_->failwith "Mutation path outside fixture"
let repin case=
  (* Re-inventory only obligation metadata after authoring a distinct source
     requirement. The independent binding checker checks this proposal afresh. *)
  let rec expressions path value=match value with
    |Json.Object fields->(if get "$type" value=str "Expr"then[path]else[])@
        List.concat_map(fun(key,value)->expressions(path^"/"^key)value)fields
    |Json.Array values->List.concat(List.mapi(fun index value->expressions(path^"/"^string_of_int index)value)values)
    |_->[]in
  let paths=List.concat(List.mapi(fun index value->if get "$type" value=str "Requirement"then
    let path="/document/program/declarations/"^string_of_int index in path::expressions path value else [])
      (items "declarations"(get "program"(get "document"(get "request" case)))))in
  let retained=List.filter(fun value->text "role" value<>"requirement")(items "occurrences"(get "implementation" case))in
  let obligations=List.map(fun path->obj["source_path",str path;"role",str "requirement";"disposition",str "obligation";"targets",arr[]])paths in
  let case=set["implementation";"occurrences"](arr(List.sort(fun a b->String.compare(text "source_path" a)(text "source_path" b))(retained@obligations)))case in
  let request=R.of_json(get "request" case)in
  set["implementation";"authority"](obj[
    "source_artifact_digest",str(D.artifact_digest(R.document request));
    "descriptors_digest",str(O.descriptors_digest(R.definitions request));
    "domain_digest",str(F.digest(R.operating_domain request));
    "implementation_catalog_digest",str(Canonical.fingerprint(get "implementations"(D.to_json(R.document request))));
    "library_digest",str(I.library_digest(R.implementation_library request))])case
let declarations case=items "declarations"(get "program"(get "document"(get "request" case)))
let declaration case identity=List.find(fun value->text "id" value=identity)(declarations case)
let edit case identity path replacement=
  let changed=List.map(fun value->if text "id" value=identity then set path replacement value else value)(declarations case)in
  repin(set["request";"document";"program";"declarations"](arr changed)case)
let initialize ?(limits={M.max_work=100000000;max_obligations=1000;max_samples=100000}) case=
  let request=R.of_json(get "request" case)in
  let behavior=L.lower(Bioc_checker.Policy_admission.admit ~document:(R.document request) ~descriptors:(R.definitions request))in
  let admitted=A.admit ~request ~behavior in
  let implementation=I.of_json ~library:(R.implementation_library request)(get "implementation" case)in
  let bound=B.check ~admitted ~implementation ~proposed:(U.of_json(get "proposed" case))in
  let environment=B.environment bound in
  let runtime=P.initialize ~implementation ~environment:{P.executor=environment.executor;horizon_ticks=environment.horizon_ticks;
      slots=List.map(fun(slot:B.slot)->{P.slot_id=slot.identity;target=slot.target;start_tick=slot.start_tick})environment.slots}
    ~limits:{P.max_work=100000000;max_events=1000000;max_attempts=20;max_microsteps=20}in
  bound,runtime,M.create ~binding:bound ~limits
let summary id monitor=List.find(fun(row:M.requirement_summary)->row.id=id)(M.summaries monitor)
let row id monitor=List.find(fun value->text "id" value=id)(items "requirements"(M.report monitor))
let obligation id monitor=List.hd(items "obligations"(row id monitor))
let observe tick slot evidence : P.observation={observation_id="row/"^string_of_int tick^"/"^slot;input_id="condition";
  slot_id=slot;observed_tick=tick;observer="cell-1";subject=(if slot="e1"then "target-1"else "target-2");evidence}
let feedback tick (attempt:P.attempt) outcome : P.feedback={feedback_id="feedback/"^string_of_int tick^"/"^attempt.attempt_id;
  input_id="feedback";attempt_id=attempt.attempt_id;executor=attempt.executor;subject=attempt.subject;
  slot_id=Option.get attempt.binding.slot;outcome}
let batch ?(lifecycle=[]) ?(feedback=[]) tick observations : P.input_batch={tick;lifecycle;observations;feedback}
let apply runtime monitor input=let runtime,frame=P.step runtime input in runtime,M.step monitor frame,frame
let finish runtime monitor start horizon=
  let rec loop runtime monitor tick=if tick>horizon then runtime,monitor else
    let runtime,monitor,_=apply runtime monitor(batch tick [])in loop runtime monitor(tick+1)in
  loop runtime monitor start
let assert_verdict monitor id expected=let actual=(summary id monitor).verdict in
  require(actual=expected)("Unexpected independent verdict for "^id)
let rejects code action=match action()with _->failwith("Expected diagnostic "^code)
  |exception Diagnostic.Error diagnostic->require(diagnostic.code=code)("Unexpected diagnostic "^diagnostic.code)
let assert_claim monitor=
  let report=M.report monitor in require(text "claim" report="candidate_prefix_only")"Monitor claimed a whole domain";
  List.iter(fun key->require(text key report="unassessed")("Monitor promoted "^key))["whole_domain";"global_nonvacuity";"material"];
  require(text "export" report="withheld")"Monitor granted export"
let true_literal case=get "value"(List.hd(items "assignments"(declaration case "respond")))
let observe_expression case=get "when"(declaration case "respond")
let negate value=set["op"](str "not")(set["args"](arr[value])(set["ref"]Json.Null(set["scope"]Json.Null value)))
let phase value name=set["value"](str name)value
let edit_progress case response deadline=
  let case=edit case "initiation_progress" ["response"]response in
  let quantity=get "deadline"(declaration case "initiation_progress")in
  edit case "initiation_progress" ["deadline"](set["amount"](str deadline)quantity)
let start_true case=
  let bound,runtime,monitor=initialize case in
  let runtime,monitor,_=apply runtime monitor(batch 0 [observe 0 "e1"(P.Known false);observe 0 "e2"(P.Known false)])in
  let runtime,monitor,frame=apply runtime monitor(batch 1 [observe 1 "e1"(P.Known true);observe 1 "e2"(P.Known true)])in
  bound,runtime,monitor,frame
let literals first second=
  List.iter(fun(case,safety,horizon)->
    let _,runtime,monitor,_=start_true case in
    require((summary "request_progress" monitor).enabled_triggers=2)"Rising requests were not independently counted";
    require((summary "initiation_progress" monitor).passed_obligations=2)"Same-attempt initiation did not satisfy both requests";
    assert_verdict monitor "request_progress" M.Uncertain;
    let _,monitor=finish runtime monitor 2 horizon in
    assert_verdict monitor "request_progress" M.Passed;assert_verdict monitor "initiation_progress" M.Passed;
    assert_verdict monitor safety M.Passed;
    require((summary safety monitor).samples=2*(horizon+1))"Settled safety omitted a slot or silent tick";
    require((summary safety monitor).false_samples=0)"Settled atomic opposing writes violated exclusion";
    assert_claim monitor)[first,"scoped_memory",4;second,"exclusive_selection",6];
  List.iter(fun(case,safety,horizon,expected)->
    let _,runtime,monitor=initialize case in
    let runtime,monitor,_=apply runtime monitor(batch 0 [])in
    assert_verdict monitor "request_progress" M.Uncertain;
    let _,monitor=finish runtime monitor 1 horizon in
    assert_verdict monitor "request_progress" M.Not_exercised;
    assert_verdict monitor safety expected;
    let compatibility=List.find(fun value->text "id" value="request_progress")(M.source_view monitor)in
    require(text "status" compatibility="unknown")"Compatibility view erased source no-trigger uncertainty";
    require((summary "request_progress" monitor).matched_triggers=0)"Absent input invented a rising event")
    [first,"scoped_memory",4,M.Uncertain;second,"exclusive_selection",6,M.Passed];
  List.iter(fun evidence->
    let _,runtime,monitor=initialize second in
    let runtime,monitor,_=apply runtime monitor(batch 0 [observe 0 "e1" evidence;observe 0 "e2" evidence])in
    let _,monitor=finish runtime monitor 1 6 in
    assert_verdict monitor "exclusive_selection" M.Passed;assert_verdict monitor "request_progress" M.Not_exercised)
    [P.Missing_evidence;P.Invalid_evidence;P.Conflicting_evidence];
  let _,runtime,monitor=initialize first in
  let _,monitor,_=apply runtime monitor(batch 0 [observe 0 "e1"(P.Known true);observe 0 "e2"(P.Known true)])in
  require((summary "request_progress" monitor).matched_triggers=0)"Initial known true was mistaken for a false-to-true transition";
  let state=get "value"(List.hd(items "assignments"(declaration first "respond")))in
  require(get "value" state=Json.Bool true)"Literal source assignment fixture changed";
  let _,runtime,monitor=initialize first in
  let runtime,monitor,frame=apply runtime monitor(batch 0 [observe 0 "e1"(P.Known false);observe 0 "e2"(P.Known false)])in
  let before=M.fingerprint monitor in
  rejects "policy_requirement_monitor_frame"(fun()->M.step monitor frame);
  require(M.fingerprint monitor=before)"Rejected repeated frame mutated predecessor";
  let _,_,next=apply runtime monitor(batch 1 [observe 1 "e1"(P.Known true)])in
  let altered={next with outputs=List.map(fun(port:P.port_value)->
    if port.endpoint.node_id="seen" && port.binding.slot=Some "e1"then {port with signal=P.Truth{value=Some I.False;reasons=[]}}else port)next.outputs}in
  let failed=M.step monitor altered in assert_verdict failed "scoped_memory" M.Failed;
  require(M.fingerprint monitor=before)"Candidate failure corrupted an independent branch"
let progress_controls first=
  let effect_response=get "response"(declaration first "initiation_progress")in
  let completion=edit_progress first(phase effect_response "completed")"2"in
  let _,runtime,monitor,frame=start_true completion in
  let attempts=frame.creations in
  let runtime,monitor,_=apply runtime monitor(batch 2 [] ~feedback:[feedback 2(List.hd attempts)P.Complete])in
  let _,monitor=finish runtime monitor 3 4 in
  assert_verdict monitor "initiation_progress" M.Failed;
  let counts=summary "initiation_progress" monitor in
  require(counts.passed_obligations=1 && counts.failed_obligations=1)"One completion satisfied a different attempt";
  let _,runtime,monitor,frame=start_true completion in
  let runtime,monitor,_=apply runtime monitor(batch 2 [])in
  let runtime,monitor,_=apply runtime monitor(batch 3 [] ~feedback:(List.map(fun attempt->feedback 3 attempt P.Complete)frame.creations))in
  let _,monitor=finish runtime monitor 4 4 in assert_verdict monitor "initiation_progress" M.Passed;
  List.iter(fun lifecycle->
    let _,runtime,monitor,_=start_true completion in
    let runtime,monitor,_=apply runtime monitor(batch 2 [] ~lifecycle:["e1",lifecycle;"e2",lifecycle])in
    let _,monitor=finish runtime monitor 3 4 in assert_verdict monitor "initiation_progress" M.Uncertain;
    let pending=items "obligations"(row "initiation_progress" monitor)in
    require(List.for_all(fun value->text "reason" value=(if lifecycle=P.Reset then "encounter_reset"else "encounter_ended"))pending)
      "Lifecycle did not retain explicit unresolved-obligation reason")[P.Reset;P.End];
  let unknown_literal=set["value"](str "unknown")(true_literal first)in
  let unknown=edit_progress first unknown_literal "1"in
  let _,runtime,monitor,_=start_true unknown in
  let _,monitor=finish runtime monitor 2 4 in assert_verdict monitor "initiation_progress" M.Uncertain;
  require(get "response_unknown"(obligation "initiation_progress" monitor)=Json.Bool true)"Unknown response became definite failure";
  let later=edit_progress first(negate(observe_expression first))"2"in
  let _,runtime,monitor,_=start_true later in
  let runtime,monitor,_=apply runtime monitor(batch 2 [observe 2 "e1" P.Invalid_evidence;observe 2 "e2" P.Invalid_evidence])in
  let runtime,monitor,_=apply runtime monitor(batch 3 [observe 3 "e1"(P.Known false);observe 3 "e2"(P.Known false)])in
  let _,monitor=finish runtime monitor 4 4 in assert_verdict monitor "initiation_progress" M.Passed;
  require(get "response_unknown"(obligation "initiation_progress" monitor)=Json.Bool true)"Later response erased earlier uncertainty";
  let seen=get "args"(get "condition"(declaration first "scoped_memory"))|>Json.array|>List.rev|>List.hd in
  let pre=edit_progress first(negate seen)"1"in
  let pre=edit pre "initiation_progress" ["trigger"](get "trigger"(declaration first "request_progress"))in
  let _,runtime,monitor,_=start_true pre in
  let _,monitor=finish runtime monitor 2 4 in assert_verdict monitor "initiation_progress" M.Passed;
  require(text "phase"(get "response_witness"(obligation "initiation_progress" monitor))="before_activation")
    "Pre-activation true response was lost after atomic state write";
  let guarded=edit pre "initiation_progress" ["condition"]seen in
  let _,runtime,monitor,_=start_true guarded in
  let _,monitor=finish runtime monitor 2 4 in assert_verdict monitor "initiation_progress" M.Not_exercised;
  require((summary "initiation_progress" monitor).disabled_triggers=2)"Enabling guard read post-write state";
  let unsupported=edit_progress first(phase effect_response "ceased")"1"in
  let _,_,monitor=initialize unsupported in assert_verdict monitor "initiation_progress" M.Unsupported_requirement;
  require(text "unsupported_reason"(row "initiation_progress" monitor)="unsupported_effect_phase")"Unsupported phase reason lost";
  let unknown_guard=edit first "initiation_progress" ["condition"]unknown_literal in
  let _,runtime,monitor,_=start_true unknown_guard in
  let _,monitor=finish runtime monitor 2 4 in assert_verdict monitor "initiation_progress" M.Uncertain;
  require((summary "initiation_progress" monitor).unknown_enabling=2)"Unknown enabling became an absent trigger";
  let pending=edit_progress first(phase effect_response "completed")"10"in
  let _,runtime,monitor,_=start_true pending in
  let _,monitor=finish runtime monitor 2 4 in assert_verdict monitor "initiation_progress" M.Uncertain;
  require((summary "initiation_progress" monitor).pending_obligations=2 &&
    get "closed_tick"(obligation "initiation_progress" monitor)=Json.Null)"Partial response window was treated as a completed proof";
  List.iter(fun(name,send_failure)->
    let candidate=edit_progress first(phase effect_response name)"2"in
    let _,runtime,monitor,frame=start_true candidate in
    let feedback=if send_failure then List.map(fun attempt->feedback 2 attempt P.Fail)frame.creations else []in
    let runtime,monitor,_=apply runtime monitor(batch 2 [] ~feedback)in
    let _,monitor=finish runtime monitor 3 4 in assert_verdict monitor "initiation_progress" M.Passed)
    ["failed",true;"timed_out",false];
  let truth_type=get "value_type"(true_literal first)in
  let entity=set["value_type"](set["kind"](str "entity")(set["entity_kind"](str "cell")truth_type))(true_literal first)in
  let entity=set["value"]Json.Null(set["ref"](obj["$type",str "Ref";"kind",str "Subject";"id",str "encounter/target"])
    (set["scope"](obj["$type",str "Ref";"kind",str "Subject";"id",str "encounter/target"])entity))in
  let distinct=set["op"](str "distinct")(set["value"]Json.Null(set["args"](arr[entity;entity])(true_literal first)))in
  let undecodable=edit first "initiation_progress" ["condition"]distinct in
  let _,_,monitor=initialize undecodable in assert_verdict monitor "initiation_progress" M.Unsupported_requirement;
  require(get "condition"(get "source"(row "initiation_progress" monitor))=distinct)"Original unsupported guard operands were erased";
  let scope=get "scope"(declaration first "scoped_memory")in
  let executor_scope=set["subject"](obj["$type",str "Ref";"id",str "executor";"kind",str "Role"])(set["kind"](str "executor")scope)in
  let _,_,monitor=initialize(edit first "scoped_memory" ["scope"]executor_scope)in
  assert_verdict monitor "scoped_memory" M.Unsupported_requirement
let resource_controls first=
  let _,runtime,monitor=initialize ~limits:{M.max_work=100000000;max_obligations=1;max_samples=100000}first in
  let runtime,monitor,_=apply runtime monitor(batch 0 [observe 0 "e1"(P.Known false);observe 0 "e2"(P.Known false)])in
  let _,frame=P.step runtime(batch 1 [observe 1 "e1"(P.Known true);observe 1 "e2"(P.Known true)])in
  let prior=M.fingerprint monitor in rejects "policy_requirement_monitor_obligation_limit"(fun()->M.step monitor frame);
  require(M.fingerprint monitor=prior)"Obligation exhaustion mutated predecessor";
  let _,runtime,monitor=initialize ~limits:{M.max_work=100000000;max_obligations=1000;max_samples=1}first in
  let _,frame=P.step runtime(batch 0 [])in
  rejects "policy_requirement_monitor_sample_limit"(fun()->M.step monitor frame);
  rejects "policy_requirement_monitor_work_limit"(fun()->initialize ~limits:{M.max_work=1;max_obligations=1000;max_samples=100000}first)
let crosscheck case=
  let bound,runtime,monitor=initialize case in
  let admitted=B.admitted_inputs bound in
  let bounds=S.execution_bounds_of_json(obj(List.map(fun(k,v)->k,Json.int v)
    ["max_ticks",20;"max_inputs",100;"max_encounters",4;"max_attempts",20;"max_work",1000000;"max_trace_items",10000;"max_microsteps",20]))in
  let source=S.create ~behavior:(A.behavior admitted) ~domain:(R.operating_domain(A.request admitted)) ~bounds in
  let select source=
    let rec scan sequence=match sequence()with Seq.Nil->failwith "Literal input history absent"|Seq.Cons(batch,rest)->
      if batch.F.feedback=[] && List.for_all(fun(_,action)->action=F.Keep)batch.lifecycle &&
        (batch.tick<>1 || List.map(fun(row:F.observation_input)->row.slot,row.evidence)batch.observations=["e1",F.Known true;"e2",F.Known true])
      then batch else scan rest in scan(S.choices source)in
  let rec loop source runtime correspondence monitor=
    if S.finished source then ()else(
      let batch=select source in
      let runtime,frame=P.step runtime(T.input correspondence batch)in
      let advanced=match S.step source batch with S.Advanced value->value|S.Stopped value->failwith value.diagnostic.code in
      let execution=Option.get advanced.receipt.execution in
      let correspondence=T.advance correspondence ~batch ~source_frame:advanced.frame ~source_attempts:(items "attempts" execution)
        ~source_creations:advanced.creations ~candidate:frame in
      let monitor=M.step monitor frame in
      let identities=T.report correspondence in
      let translate kind value=match value with Json.Null->Json.Null|_->
        get "source"(List.find(fun row->get "candidate" row=value)(items kind identities))in
      let actual=List.map(fun row->set["obligations"](arr(List.map(fun obligation->
        set["trigger"](translate "events"(get "trigger" obligation))
          (set["attempt"](translate "attempts"(get "attempt" obligation))obligation))(items "obligations" row)))row)(M.source_view monitor)in
      require(Json.equal(arr actual)(get "requirements" execution))"Independent candidate requirement view differs from fresh source execution";
      loop advanced.next runtime correspondence monitor)in
  loop source runtime(T.create bound)monitor
let ()=
  let cases=items "cases"(read Sys.argv.(1))in
  let first=List.nth cases 0 and second=List.nth cases 1 in
  literals first second;progress_controls first;resource_controls first;List.iter crosscheck cases;
  print_endline "independent candidate requirement monitor literals and fresh source cross-checks passed"
