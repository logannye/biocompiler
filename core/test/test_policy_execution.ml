open Bioc_wire
module O = Bioc_domain.Policy_operational
module D = Bioc_domain.Policy_document
module A = Bioc_checker.Policy_admission
module C = Bioc_checker.Policy_correspondence
module L = Bioc_compiler.Policy_lowering
module E = Bioc_semantics.Policy_execution
let require condition message = if not condition then failwith message
let str x = Json.String x
let arr x = Json.Array x
let obj x = Json.Object x
let field key value = Json.field key (Json.object_fields value)
let text key value = Json.string(field key value)
let items key value = Json.array(field key value)
let replace key replacement value = obj(List.map(fun(k,v)->k,if k=key then replacement else v)(Json.object_fields value))
let named id xs = List.find(fun x->text "id" x=id)xs
let declaration id document = named id (items "declarations" document)
let change id key replacement document = replace "declarations" (arr(List.map(fun x->if text "id" x=id then replace key replacement x else x)(items "declarations" document))) document
let add xs document = replace "declarations" (arr(items "declarations" document@xs)) document
let reference kind id = obj["$type",str "Ref";"kind",str kind;"id",str id]
let read path = let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_bounded ~max_bytes:(2*1024*1024) ~max_nodes:100000(really_input_string channel(in_channel_length channel)))
let compiled document definitions =
  let document=D.of_json document and descriptors=O.descriptors_of_json definitions in
  let behavior=L.lower(A.admit ~document ~descriptors)in
  ignore(C.check ~expected_document:document ~descriptors behavior);behavior
let rejects code f = match f()with
  | _->failwith("Expected rejection: "^code)
  | exception Diagnostic.Error diagnostic->require(diagnostic.code=code)("Wrong diagnostic: "^diagnostic.code^" expected "^code)
let frame time report = List.find(fun frame->text "time" frame=time)(items "frames" report)
let attempt id report = named id(items "attempts" report)
let requirement id report = named id(items "requirements" report)
let actions kind report = List.concat_map(fun frame->List.filter(fun action->text "kind" action=kind)(items "actions" frame))(items "frames" report)
let state id encounter frame = List.find(fun state->text "state" state=id && field "encounter" (field "binding" state)=encounter)(items "states" frame)
let evidence encounter frame = List.find(fun e->field "encounter"(field "binding"e)=str encounter)(items "evidence" frame)
let single timeline = timeline
  |>replace "encounters" (arr[List.hd(items "encounters" timeline)])
  |>replace "observations" (arr(List.filter(fun x->field "encounter"x=str "e1")(items "observations"timeline)))
  |>replace "feedback" (arr[])
let observation base id at value = base |>replace "id"(str id)|>replace "available_at"(str at)|>replace "observed_at"(str at)|>replace "value"value
let feedback base id at attempt outcome = base |>replace "id"(str id)|>replace "available_at"(str at)|>replace "attempt"(str attempt)|>replace "outcome"(str outcome)
let boolean_literal base value = base |>replace "op"(str "literal")|>replace "args"(arr[])|>replace "value"(Json.Bool value)|>replace "ref"Json.Null|>replace "scope"Json.Null
let run fixture =
  let document=field "document"fixture and definitions=field "definitions"fixture and timeline=field "timeline"fixture in
  let behavior=compiled document definitions in
  let execute=E.execute behavior in
  let base=execute timeline in
  require(text "schema_version"base="biocompiler.policy_execution.v0.1")"Wrong execution schema";
  require(text "claim"base="bounded_supplied_timeline_only")"Execution claim widened";
  require(text "timeline_digest"base=Canonical.fingerprint timeline)"Timeline identity omitted";
  require(List.length(items "frames"base)=5)"Silent ticks disappeared";
  List.iter(fun expected->let actual=attempt(text "id"expected)base in
    List.iter(fun key->require(field key actual=field key expected)("Literal attempt differs: "^key))["id";"subject";"status"];
    require(field "encounter"(field "binding"actual)=field "encounter"expected)"Literal concrete encounter differs") (items "expected_attempts"fixture);
  require(text "ended_at"(attempt "attempt/2"base)="3")"Silent timeout did not fire exactly";
  require(text "status"(requirement "completion"base)="fail")"Missing correlated completion escaped bounded progress";
  require(text "status"(requirement "scoped_memory"base)="pass")"Settled scoped-state safety failed";
  List.iter(fun target->
    require(field "value"(state "seen"(str target)(frame "0"base))=Json.Bool false)"Encounter state not initialized";
    require(field "value"(state "seen"(str target)(frame "1"base))=Json.Bool true)"Atomic scoped assignment lost";
    require(text "status"(evidence target(frame "3"base))="stale")"Freshness equality is not stale") ["e1";"e2"];
  require(items "active_attempts"(frame "2"base)=[str "attempt/2"])"Completion mixed distinct target attempts";
  let one=single timeline in
  let initial=List.hd(items "observations"one) and external_feedback=List.hd(items "feedback"timeline) in
  let without_initial=one |>replace "observations"(arr[observation initial "initial-true" "1"(Json.Bool true)])in
  let no_edge=execute without_initial in
  require(items "attempts"no_edge=[])"Unknown-to-true invented a rising edge";
  require(text "status"(requirement "completion"no_edge)="unknown")"Vacuous progress incorrectly passed";
  let missing=execute(replace "observations"(arr[])one)in
  require(text "status"(evidence "e1"(frame "0"missing))="missing")"Missing evidence collapsed";
  List.iter(fun status->let input=observation initial ("uncertain-"^status) "0" Json.Null |>replace "status"(str status)in
    let result=execute(replace "observations"(arr[input])one)in
    require(text "status"(evidence "e1"(frame "0"result))=status)("Evidence reason lost: "^status);
    require(items "attempts"result=[])"Uncertain evidence initiated an effect") ["missing";"invalid";"conflicting"];
  let conflict=one |>replace "observations"(arr[initial;observation initial "true" "1"(Json.Bool true);observation initial "false" "1"(Json.Bool false)])in
  let conflicting=execute conflict in
  require(text "status"(evidence "e1"(frame "1"conflicting))="conflicting")"Simultaneous conflicting evidence was ordered away";
  require(items "attempts"conflicting=[])"Conflicting evidence authorized an attempt";
  let delayed=observation initial "late-true" "1"(Json.Bool true)|>replace "available_at"(str "3")in
  let stale=execute(replace "observations"(arr[initial;delayed])one)in
  require(items "attempts"stale=[])"Stale-at-arrival evidence generated a rising edge";
  require(text "status"(evidence "e1"(frame "3"stale))="stale")"Observed/availability time distinction lost";
  let target_mix=replace "observations"(arr[replace "subject"(str "target-2")initial])one in
  rejects "policy_execution_identity"(fun()->execute target_mix);
  rejects "policy_execution_occurrence"(fun()->execute(replace "observations"(arr[initial;initial])one));
  rejects "policy_execution_evidence"(fun()->execute(replace "observations"(arr[replace "value"Json.Null initial])one));
  rejects "policy_execution_evidence"(fun()->execute(replace "observations"(arr[replace "value"(str "unknown")initial])one));
  rejects "policy_operational_value"(fun()->execute(replace "observations"(arr[replace "value"(str "true")initial])one));
  rejects "policy_execution_time"(fun()->execute(replace "horizon"(str "4.5")one));
  let fail_bound name value code = let bounds=field "bounds"timeline|>replace name(Json.int value)in rejects code(fun()->execute(replace "bounds"bounds timeline))in
  fail_bound "max_ticks" 4 "policy_execution_tick_limit";
  fail_bound "max_attempts" 1 "policy_execution_attempt_limit";
  fail_bound "max_work" 1 "policy_execution_work_limit";
  fail_bound "max_inputs" 1 "policy_execution_input_limit";
  fail_bound "max_encounters" 1 "policy_execution_encounter_limit";
  fail_bound "max_trace_items" 1 "policy_execution_trace_limit";
  fail_bound "max_microsteps" 1 "policy_execution_settling_limit";
  let wrong=feedback external_feedback "wrong" "2" "attempt/1" "completed" |>replace "subject"(str "target-2")in
  let wrong_report=execute(replace "feedback"(arr[wrong])one)in
  require(text "status"(attempt "attempt/1"wrong_report)="timed_out")"Wrong-target feedback completed an attempt";
  require(List.map(fun action->text "reason"(field "detail"action))(actions "feedback_rejected"wrong_report)=["identity_mismatch"])"Wrong feedback reason omitted";
  let at_deadline=feedback external_feedback "at-deadline" "3" "attempt/1" "completed"in
  let deadline_report=execute(replace "feedback"(arr[at_deadline])one)in
  require(text "status"(attempt "attempt/1"deadline_report)="completed")"Inclusive deadline lost correlated completion";
  require(text "status"(requirement "completion"deadline_report)="pass")"Nonvacuous timely progress did not pass";
  let failure=feedback external_feedback "failure" "2" "attempt/1" "failed"in
  let failed=execute(replace "feedback"(arr[failure])one)in
  require(text "status"(attempt "attempt/1"failed)="failed")"Failure feedback changed meaning";
  require(text "status"(requirement "completion"failed)="fail")"Failed attempt counted as completion";
  let first=feedback external_feedback "first" "2" "attempt/1" "completed"in
  let stale_feedback=feedback external_feedback "duplicate" "3" "attempt/1" "completed"in
  let duplicate=execute(replace "feedback"(arr[first;stale_feedback])one)in
  require(List.map(fun action->text "reason"(field "detail"action))(actions "feedback_rejected"duplicate)=["stale_attempt"])"Repeated completed feedback was not rejected";
  rejects "policy_execution_feedback_conflict"(fun()->execute(replace "feedback"(arr[first;failure])one));
  let second_false=observation initial "false-2" "2"(Json.Bool false)and second_true=observation initial "true-3" "3"(Json.Bool true)in
  let repeated=one |>replace "observations"(arr(items "observations"one@[second_false;second_true]))
    |>replace "feedback"(arr[first;feedback external_feedback "second" "4" "attempt/2" "completed"])in
  let repeated_report=execute repeated in
  require(List.map(fun x->text "id"x,text "status"x)(items "attempts"repeated_report)=["attempt/1","completed";"attempt/2","completed"])"Repeated attempts merged their occurrence identities";
  let reset_encounter=List.hd(items "encounters"one)|>replace "resets"(arr[str "2"])in
  let reset_timeline=repeated |>replace "encounters"(arr[reset_encounter])
    |>replace "feedback"(arr[stale_feedback;feedback external_feedback "second" "4" "attempt/2" "completed"])in
  let reset_report=execute reset_timeline in
  require(text "status"(attempt "attempt/1"reset_report)="encounter_reset")"Reset retained old attempt activity";
  require(field "value"(state "seen"(str "e1")(frame "2"reset_report))=Json.Bool false)"Reset leaked old encounter state";
  require(field "generation"(field "binding"(attempt "attempt/2"reset_report))=Json.int 1)"Reset generation not retained";
  require(text "status"(requirement "completion"reset_report)="unknown")"Reset erased unresolved source progress";
  let old_observation=observation initial "old-generation" "1"(Json.Bool true)|>replace "available_at"(str "2")in
  rejects "policy_execution_identity"(fun()->execute(reset_timeline |>replace "observations"(arr[initial;old_observation])));
  let ended=execute(one |>replace "encounters"(arr[List.hd(items "encounters"one)|>replace "end"(str "2")]))in
  require(text "status"(attempt "attempt/1"ended)="encounter_ended")"End-of-encounter retained active attempt";
  require(items "states"(frame "2"ended)=[])"End-of-encounter did not release scoped storage";
  let long_lifecycle=field "lifecycle"(declaration "response"document)|>replace "timeout"Json.Null in
  let indefinite=compiled(change "response" "lifecycle" long_lifecycle document)definitions in
  let continuing=E.execute indefinite one in
  require(text "status"(attempt "attempt/1"continuing)="active")"unknown=defer stopped existing activity";
  require(text "authorization"(attempt "attempt/1"continuing)="unknown")"Continuous guard/binding not retained";
  require(List.exists(fun action->text "lifecycle_response"(field "detail"action)="defer")(actions "authorization_changed"continuing))"Stale continuous authorization not recorded";
  let capacity=compiled(change "seen" "capacity"(Json.int 1)document)definitions in
  rejects "policy_execution_state_capacity"(fun()->E.execute capacity timeline);
  let rule=declaration "respond"document in
  let true_literal=boolean_literal(field "when"rule)true in
  let resetting=compiled(change "seen" "reset"true_literal document)definitions in
  let reset_state=E.execute resetting one in
  require(field "value"(state "seen"(str "e1")(frame "1"reset_state))=Json.Bool true)"Pre-activation reset prevented same-tick assignment";
  require(field "value"(state "seen"(str "e1")(frame "2"reset_state))=Json.Bool false)"Truth reset did not execute once at the silent tick";
  let unknown_literal=replace "value"(str "unknown")true_literal in
  let unknown_assignment=List.hd(items "assignments"rule)|>replace "value"unknown_literal in
  let unknown_state=compiled(change "respond" "assignments"(arr[unknown_assignment])document)definitions in
  let unknown_state_report=E.execute unknown_state one in
  require(field "value"(state "seen"(str "e1")(frame "1"unknown_state_report))=str "unknown")"Explicit third truth value was deferred instead of stored";
  require(List.length(items "attempts"unknown_state_report)=1)"Truth unknown assignment incorrectly canceled atomic effect";
  let unknown_response=compiled(change "completion" "response"unknown_literal document)definitions in
  let unknown_response_report=E.execute unknown_response one in
  require(text "status"(requirement "completion"unknown_response_report)="unknown")"Unknown response was mislabeled a proven progress failure";
  let integer_type=obj["$type",str "TypeSpec";"kind",str "integer";"unit",Json.Null;"entity_kind",Json.Null]in
  let integer text=replace "value_type"integer_type true_literal|>replace "value"(Json.Int(Z.of_string text))in
  let exact_comparison=true_literal|>replace "op"(str "gt")|>replace "value"Json.Null
    |>replace "args"(arr[integer "9007199254740993";integer "9007199254740992"])in
  let exact_behavior=compiled(change "respond" "when"exact_comparison document)definitions in
  require(List.length(items "attempts"(E.execute exact_behavior one))=1)"Exact comparison was rounded through binary64";
  let denied=compiled(change "respond" "when"(replace "op"(str "lt")exact_comparison)document)definitions in
  require(items "attempts"(E.execute denied one)=[])"Exact comparison reversed ordering";
  let duplicate_rule=rule|>replace "id"(str "respond-second")in
  let exclusive=compiled(add[duplicate_rule]document)definitions in
  rejects "policy_execution_exclusive"(fun()->E.execute exclusive one);
  let priority=field "arbitration"rule|>replace "mode"(str "priority")|>replace "order"(arr[str "respond-second";str "respond"])in
  let selected=duplicate_rule|>replace "arbitration"priority in
  let priority_behavior=compiled(add[selected](change "respond" "arbitration"priority document))definitions in
  let priority_report=E.execute priority_behavior one in
  require(text "initiator"(attempt "attempt/1"priority_report)="respond-second")"Declared priority did not override source declaration order";
  require(List.length(actions "arbitration_suppressed"priority_report)=1)"Priority suppression omitted";
  let machine=obj["$type",str "Machine";"id",str "cycle";"executor",reference "Role""executor";
    "scope",obj["$type",str "Scope";"kind",str "encounter";"subject",reference "Encounter""encounter"];
    "states",arr[str "idle";str "active"];"initial",str "idle";"terminal",arr[];"lifetime",str "encounter";
    "arbitration",field "arbitration"rule]in
  let transition id source destination on effects assignments=obj[
    "$type",str "Transition";"id",str id;"machine",reference "Machine""cycle";
    "source",str source;"destination",str destination;"on",on;"when",true_literal;"unknown",str "defer";
    "effects",arr effects;"assignments",arr assignments;"unknown_target",Json.Null;"emissions",arr[]]in
  let completed=field "response"(declaration "completion"document)in
  let begin_transition=transition "begin" "idle" "active"(field "on"rule)[reference "Effect""response"](items "assignments"rule)in
  let finish_transition=transition "finish" "active" "idle"completed[][]in
  let timeout_transition=transition "timeout" "active" "idle"(replace "value"(str "timed_out")completed)[][]in
  let machine_document=replace "declarations"(arr(List.filter(fun d->text "id"d<>"respond")(items "declarations"document)))document
    |>replace "source_map"(arr(List.filter(fun span->text "declaration_id"span<>"respond")(items "source_map"document)))
    |>add[machine;begin_transition;finish_transition;timeout_transition]in
  let machine_behavior=compiled machine_document definitions in
  let machine_timeline=repeated|>replace "horizon"(str "5")|>replace "feedback"(arr[
    first;feedback external_feedback "stale-machine-attempt" "4" "attempt/1" "completed";
    feedback external_feedback "complete-second-machine" "5" "attempt/2" "completed"])in
  let machine_report=E.execute machine_behavior machine_timeline in
  let machine_state time=let row=List.hd(items "machines"(frame time machine_report))in text "state"row,items "attempts"row in
  require(machine_state "1"=("active",[str "attempt/1"]))"Machine did not retain the attempt it started";
  require(machine_state "2"=("idle",[str "attempt/1"]))"Machine completion transition did not retain explicit attempt lineage";
  require(machine_state "3"=("active",[str "attempt/2"]))"Machine reused an earlier attempt binding";
  require(machine_state "4"=("active",[str "attempt/2"]))"Old feedback advanced a newer machine attempt";
  require(fst(machine_state "5")="idle")"Correct second-attempt feedback did not advance machine";
  let timeout_machine=E.execute machine_behavior one in
  require(text "state"(List.hd(items "machines"(frame "3"timeout_machine)))="idle")"Machine timeout did not occur at a silent tick";
  let unsupported_scope=change "scoped_memory" "scope"
    (obj["$type",str "Scope";"kind",str "executor";"subject",reference "Role""executor"])document in
  let unsupported_scope_report=E.execute(compiled unsupported_scope definitions)one in
  require(text "status"(requirement "scoped_memory"unsupported_scope_report)="unsupported")"Mismatched requirement scope was evaluated as if bound";
  let executor_scope=obj["$type",str "Scope";"kind",str "executor";"subject",reference "Role" "executor"]in
  let executor_state=declaration "seen"document|>replace "scope"executor_scope|>replace "lifetime"(str "executor")in
  let source=replace "declarations"(arr(List.map(fun d->if text "id"d="seen"then executor_state else d)(items "declarations"document)))document in
  let safety=declaration "scoped_memory"source in
  let condition=field "condition"safety in
  let condition=replace "args"(arr(List.map(fun x->if field "op"x=str "state"then replace "scope"(reference "Role""executor")x else x)(items "args"condition)))condition in
  let shared_state=compiled(change "scoped_memory" "condition"condition source)definitions in
  rejects "policy_execution_write_conflict"(fun()->E.execute shared_state timeline);
  let identical=field "arbitration"rule|>replace "write_conflict"(str "identical_only")in
  let shared_identical=compiled(change "respond" "arbitration"identical(change "scoped_memory" "condition"condition source))definitions in
  require(field "value"(state "seen"Json.Null(frame "1"(E.execute shared_identical timeline)))=Json.Bool true)"Identical atomic assignments failed";
  let unsupported=change "completion" "kind"(str "objective")document in
  let unsupported_report=E.execute(compiled unsupported definitions)one in
  require(text "status"(requirement "completion"unsupported_report)="unsupported")"Unsupported requirement was proved";
  require(List.map(fun r->text "id"r)(items "requirements"unsupported_report)=["completion";"scoped_memory"])"Requirement ledger was reordered or dropped";
  print_endline "bounded operational execution: independent literal timelines and negative controls passed"
let () =
  require(Array.length Sys.argv=2)"Expected frozen operational fixture path";
  run(read Sys.argv.(1))
