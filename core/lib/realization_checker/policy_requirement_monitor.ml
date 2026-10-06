open Bioc_wire
module B = Bioc_checker.Policy_implementation_binding_check
module A = Bioc_checker.Policy_realization_admission
module F = Bioc_domain.Policy_operating_domain
module O = Bioc_domain.Policy_operational
module I = Bioc_domain.Policy_implementation
module P = Bioc_candidate_runtime.Policy_primitives

let profile = "biocompiler.policy_candidate_requirements.v0.1"
let str value=Json.String value
let arr values=Json.Array values
let obj fields=Json.Object fields
let get name value=Json.field name(Json.object_fields value)
let optional encode=function None->Json.Null|Some value->encode value
let fail code message=Diagnostic.fail("policy_requirement_monitor_"^code)message
let require condition code message=if not condition then fail code message
type limits={max_work:int;max_obligations:int;max_samples:int}
type usage={steps:int;work:int;obligations:int;samples:int}
type kind=Truth_kind|Text_kind
type value=Truth of I.truth|Text of string
type expression=Literal of I.truth|Read of I.endpoint list*kind
  |Not of expression|All of expression list|Any of expression list|Equal of expression*expression
type event_match={origin:I.endpoint;phase:I.event_kind}
type response=Value of expression|Event of event_match
type compiled={scope:O.scope;horizon:Z.t;condition:expression option;
  trigger:event_match option;response:response option;deadline:Z.t option}
type coverage={samples:int;true_samples:int;false_samples:int;unknown_samples:int;
  active:int;inactive:int;matched:int;enabled:int;disabled:int;unknown_enabling:int;
  first_failure:Json.t option;first_unknown:Json.t option}
type ledger={source:O.requirement;meaning:compiled option;unsupported:string option;coverage:coverage}
type status=Pending|Pass|Fail|Unknown
type obligation={requirement_index:int;binding:P.binding;trigger_id:string;attempt_id:string option;
  opened:int;opened_round:int;deadline:Z.t;status:status;closed:int option;
  reason:string option;uncertainty:string list;response_unknown:bool;witness:Json.t option}
type t={binding:B.checked_binding;binding_digest:string;limits:limits;resolution:Q.t;horizon:int;
  rows:ledger list;pending:obligation list;slots:P.slot_snapshot list;next:int;
  consumed:usage;history:string}
type worker={base:t;now:int;mutable rows:ledger array;mutable pending:obligation list;mutable consumed:usage}
exception Unsupported of string
let unsupported message=raise(Unsupported message)
let support condition message=if not condition then unsupported message
let charge (usage:usage ref) (limits:limits) amount=
  require(amount>=0 && amount<=limits.max_work-(!usage).work) "work_limit" "Requirement evaluation work exhausted.";
  usage:={!usage with work=(!usage).work+amount}
let spend (w:worker) amount=let used=ref w.consumed in charge used w.base.limits amount;w.consumed<- !used
let sample (w:worker)=spend w 1;
  require(w.consumed.samples<w.base.limits.max_samples) "sample_limit" "Requirement sample bound exhausted.";
  w.consumed<-{w.consumed with samples=w.consumed.samples+1}
let endpoint node_id port_id : I.endpoint={node_id;port_id}
let binding_json(value:P.binding)=obj["slot",optional str value.slot;"generation",Json.int value.generation]
let reason_name=function P.Missing->"missing"|P.Stale->"stale"|P.Invalid->"invalid"|P.Conflicting->"conflicting"
let truth_of_source=function O.True->I.True|O.False->I.False|O.Unknown->I.Unknown
let reference(expression:O.expression)=match expression.reference with Some value->value|None->unsupported "missing_reference"
let find_supported label predicate values=match List.find_opt predicate values with Some value->value|None->unsupported label
let ticks resolution amount=
  let value=Q.div amount resolution in
  support(Z.equal(Q.den value)Z.one && Z.sign(Q.num value)>=0) "unaligned_requirement_time";Q.num value
let empty_coverage={samples=0;true_samples=0;false_samples=0;unknown_samples=0;active=0;inactive=0;
  matched=0;enabled=0;disabled=0;unknown_enabling=0;first_failure=None;first_unknown=None}

let compile (binding:B.checked_binding) resolution (used:usage ref) (limits:limits) (requirement:O.requirement)=
  let behavior=A.behavior(B.admitted_inputs binding) in
  let domain=F.specification(A.operating_domain(B.admitted_inputs binding)) in
  let nodes=I.nodes(B.implementation binding) in
  let lookup_cost=1+List.length behavior.stores+List.length behavior.parameters+List.length behavior.effects+
    List.length(B.observations binding)+List.length(B.states binding)+List.length(B.effects binding)+
    List.length(B.rules binding)+List.length(B.expressions binding)in
  let scope=match requirement.scope with Some value->value|None->unsupported "unsupported_scope" in
  (match scope with
   |O.Executor role->support(role=domain.executor_role) "wrong_executor_scope"
   |O.Encounter declaration->support(List.for_all(fun(slot:F.encounter)->slot.declaration=declaration)domain.encounters) "wrong_encounter_scope");
  let read endpoints kind=
    support(endpoints<>[]) "no_actual_parameter_port";
    List.iter(fun(e:I.endpoint)->charge used limits(List.length nodes+1);
      let node=find_supported "unmapped_port" (fun(n:I.node)->n.node_id=e.node_id) nodes in
      match scope,node.model.replication with
      |O.Executor _,I.Encounter_slots _->unsupported "scope_requires_encounter"
      |_->())endpoints;
    Read(endpoints,kind),kind in
  let rec value(expression:O.expression)=
    charge used limits lookup_cost;
    let expect_truth (result,kind)=support(kind=Truth_kind) "nontruth_operand";result in
    match expression.op,expression.args with
    |"literal",[]->(match expression.value,expression.value_type with
        |Some(O.Truth truth),Some O.Truth_type->Literal(truth_of_source truth),Truth_kind
        |_->unsupported "unsupported_literal_type")
    |"observe",[]->
        let source=reference expression in
        let observation=find_supported "unmapped_observation" (fun(o:B.observation)->o.source=source)(B.observations binding) in
        support(expression.scope=Some observation.subject && expression.value_type=Some O.Truth_type) "observation_scope_or_type";
        read [endpoint observation.bank "value"] Truth_kind
    |"state",[]->
        let source=reference expression in
        let store=find_supported "unmapped_state" (fun(s:B.state)->s.source=source)(B.states binding) in
        let declaration=find_supported "absent_state_declaration" (fun(s:O.state_store)->s.state_id=source)behavior.stores in
        let expected=match declaration.scope with O.Encounter id|O.Executor id->id in
        support(expression.scope=Some expected && expression.value_type=Some O.Truth_type) "state_scope_or_type";
        read [endpoint store.register "value"] Truth_kind
    |"parameter",[]->
        let source=reference expression in
        let parameter=find_supported "absent_parameter" (fun(p:O.parameter)->p.parameter_id=source)behavior.parameters in
        let kind=match parameter.value,expression.value_type with
          |O.Truth _,Some O.Truth_type->Truth_kind|O.Text _,Some O.Text_type->Text_kind
          |_->unsupported "unsupported_parameter_type" in
        let endpoints=List.filter_map(fun(e:B.expression)->
          let raw=e.source_expression in
          if get "op" raw=str "parameter" && O.ref_id(get "ref" raw)=source then Some e.endpoint else None)
          (B.expressions binding) |> List.sort_uniq compare in
        read endpoints kind
    |"not",[operand]->support(expression.value_type=Some O.Truth_type) "nontruth_result";
        Not(expect_truth(value operand)),Truth_kind
    |("all"|"any"),operands->support(expression.value_type=Some O.Truth_type) "nontruth_result";
        let values=List.map(fun operand->expect_truth(value operand))operands in
        (if expression.op="all"then All values else Any values),Truth_kind
    |"eq",[left;right]->support(expression.value_type=Some O.Truth_type) "nontruth_result";
        let left,left_kind=value left and right,right_kind=value right in
        support(left_kind=right_kind) "incompatible_equality_types";Equal(left,right),Truth_kind
    |_->unsupported "unsupported_value_operation" in
  let predicate expression=let value,kind=value expression in support(kind=Truth_kind) "nontruth_predicate";value in
  let event(expression:O.expression)=
    charge used limits lookup_cost;support(expression.value_type=None) "nonevent_trigger";
    match expression.op,expression.args with
    |"updated",[]->let observation=find_supported "unmapped_observation_event"
        (fun(o:B.observation)->o.source=reference expression)(B.observations binding) in
        support(expression.scope=Some observation.subject) "observation_event_scope";
        ignore(read[endpoint observation.bank "value"]Truth_kind);
        {origin=endpoint observation.bank "updated";phase=I.Updated}
    |"rising",[_]->let rule=find_supported "unmapped_rising_event"
        (fun(r:B.rule)->r.source_trigger=expression)(B.rules binding) in
        support(match scope with O.Encounter _->true|_->false) "rising_requires_encounter";
        {origin=rule.trigger;phase=I.Rising}
    |"effect_event",[]->let effect_binding=find_supported "unmapped_effect_event"
        (fun(e:B.effect_binding)->e.source=reference expression)(B.effects binding) in
        let source=find_supported "absent_effect" (fun(e:O.effect_spec)->e.effect_id=effect_binding.source)behavior.effects in
        support(expression.scope=Some source.subject && (match scope with O.Encounter _->true|_->false)) "effect_event_scope";
        let phase=match expression.phase with Some "requested"->I.Requested|Some "initiated"->I.Initiated
          |Some "completed"->I.Completed|Some "failed"->I.Failed|Some "timed_out"->I.Timed_out
          |_->unsupported "unsupported_effect_phase" in {origin=endpoint effect_binding.bank "events";phase}
    |_->unsupported "unsupported_event_operation" in
  let absent key=match get key requirement.source with Json.Null|Json.Array []->true|_->false in
  support(List.for_all absent["lower";"upper";"applies_to";"contract"]) "unsupported_requirement_fields";
  support(requirement.assumptions=[] && behavior.assumptions=[]) "uninterpreted_assumptions";
  List.iter(fun(key,decoded)->support(get key requirement.source=Json.Null || Option.is_some decoded)
    "undecodable_original_expression")["condition",requirement.condition;"trigger",requirement.trigger;"response",requirement.response];
  let horizon=match requirement.horizon with Some duration->ticks resolution duration|None->unsupported "missing_finite_horizon" in
  match requirement.kind with
  |"safety"->support(requirement.trigger=None && requirement.response=None && requirement.deadline=None) "unsupported_safety_fields";
      let condition=match requirement.condition with Some value->predicate value|None->unsupported "missing_safety_condition" in
      {scope;horizon;condition=Some condition;trigger=None;response=None;deadline=None}
  |"progress"->
      let original_trigger=match requirement.trigger with Some value->value|None->unsupported "missing_trigger" in
      let original_response=match requirement.response with Some value->value|None->unsupported "missing_response" in
      let trigger=event original_trigger in
      let response=if original_response.value_type=None then Event(event original_response)else Value(predicate original_response) in
      support(original_trigger.op<>"effect_event" || (match response with Value _->true|Event _->
        original_response.op="effect_event" && original_trigger.reference=original_response.reference)) "unsupported_event_correlation";
      let deadline=match requirement.deadline with Some duration->ticks resolution duration|None->unsupported "missing_deadline" in
      support(Z.sign deadline>0) "nonpositive_deadline";
      {scope;horizon;condition=Option.map predicate requirement.condition;trigger=Some trigger;response=Some response;deadline=Some deadline}
  |_->unsupported "unsupported_requirement_kind"

let create ~binding ~(limits:limits)=
  List.iter(fun(value,maximum)->require(value>0 && value<=maximum) "limits" "Monitor bounds must be explicit positive bounded integers.")
    [limits.max_work,100000000;limits.max_obligations,10000;limits.max_samples,1000000];
  let domain=A.operating_domain(B.admitted_inputs binding) in
  let resolution=F.resolution domain in
  let used=ref{steps=0;work=0;obligations=0;samples=0} in
  let requirements=(A.behavior(B.admitted_inputs binding)).requirements in
  require(List.length requirements<=1024) "limits" "Monitor requirement inventory exceeds the profile bound.";
  let rows=List.map(fun source->charge used limits 1;
    let meaning,unsupported=try Some(compile binding resolution used limits source),None
      with Unsupported reason->None,Some reason in
    {source;meaning;unsupported;coverage=empty_coverage})requirements in
  let binding_bytes=Canonical.encode_bounded ~max_bytes:(8*1024*1024)(B.report binding)in
  charge used limits(String.length binding_bytes);
  let binding_digest=Canonical.sha256 binding_bytes in
  {binding;binding_digest;limits;resolution;horizon=(F.specification domain).horizon_ticks;rows;pending=[];
   slots=List.map(fun(slot:B.slot)->{P.slot_id=slot.identity;generation=0;active=false})(B.environment binding).slots;
   next=0;consumed= !used;history=Canonical.fingerprint(obj["profile",str profile;"binding_digest",str binding_digest])}
let usage(state:t)=state.consumed
type evaluated={value:value option;reasons:string list}
let truth(value:evaluated)=match value.value with Some(Truth truth)->truth|None->I.Unknown
  |Some(Text _)->fail "frame" "Candidate supplied text to an admitted truth predicate."
let negate=function I.True->I.False|I.False->I.True|I.Unknown->I.Unknown
let and_truth a b=match a,b with I.False,_|_,I.False->I.False|I.True,I.True->I.True|_->I.Unknown
let or_truth a b=match a,b with I.True,_|_,I.True->I.True|I.False,I.False->I.False|_->I.Unknown
let evaluate (w:worker) (ports:P.port_value list) (scope:P.binding) expression=
  let rec eval=function
    |Literal truth->spend w 1;{value=Some(Truth truth);reasons=[]}
    |Read(endpoints,kind)->
        let values=List.map(fun(e:I.endpoint)->
          let nodes=I.nodes(B.implementation w.base.binding) in spend w(List.length nodes+List.length ports+1);
          let node=List.find(fun(n:I.node)->n.node_id=e.node_id)nodes in
          let binding=match node.model.replication with I.Executor->{P.slot=None;generation=0}|I.Encounter_slots _->scope in
          let found=List.filter(fun(p:P.port_value)->p.endpoint=e && p.binding=binding)ports in
          match found with
          |[{P.signal=P.Truth signal;_}] when kind=Truth_kind->
              spend w(List.length signal.reasons);{value=Option.map(fun value->Truth value)signal.value;reasons=List.map reason_name signal.reasons}
          |[{P.signal=P.Product value;_}] when kind=Text_kind->{value=Some(Text value);reasons=[]}
          |_->fail "frame" "Required actual candidate port is missing, duplicated or mistyped.")endpoints in
        let first=List.hd values in
        require(List.for_all((=)first)values) "frame" "One source parameter has inconsistent actual candidate port values.";first
    |Not operand->spend w 1;let value=eval operand in {value=Some(Truth(negate(truth value)));reasons=value.reasons}
    |(All operands|Any operands) as expression->spend w 1;
        let values=List.map eval operands in
        let operation,initial=match expression with All _->and_truth,I.True|_->or_truth,I.False in
        let reasons=List.concat_map(fun(value:evaluated)->spend w(List.length value.reasons);value.reasons)values in
        {value=Some(Truth(List.fold_left(fun prior value->operation prior(truth value))initial values));
         reasons=List.sort_uniq String.compare reasons}
    |Equal(left,right)->spend w 1;let left=eval left and right=eval right in
        (match left.value,right.value with
         |None,_|_,None|Some(Truth I.Unknown),_|_,Some(Truth I.Unknown)->
             {value=Some(Truth I.Unknown);reasons=left.reasons@right.reasons}
         |Some a,Some b->{value=Some(Truth(if a=b then I.True else I.False));reasons=[]}) in
  sample w;eval expression
let scopes (frame:P.frame)=function O.Executor _->[{P.slot=None;generation=0}]
  |O.Encounter _->List.filter_map(fun(slot:P.slot_snapshot)->if slot.active then Some{P.slot=Some slot.slot_id;generation=slot.generation}else None)frame.slots
let live (frame:P.frame) (binding:P.binding)=match binding.slot with None->true|Some id->
  List.exists(fun(slot:P.slot_snapshot)->slot.slot_id=id && slot.generation=binding.generation && slot.active)frame.slots
let events (w:worker) values (binding:P.binding) (selector:event_match)=
  spend w(List.length values+1);
  List.filter(fun(event:P.event)->event.binding=binding && event.origin=Some selector.origin &&
    event.kind=P.Primitive_event selector.phase)values
let uncertainty (value:evaluated)=if value.reasons=[]then["truth_unknown"]else value.reasons
let update_coverage (w:worker) index update=let row=w.rows.(index)in w.rows.(index)<-{row with coverage=update row.coverage}
let within (w:worker) (meaning:compiled)=Z.leq(Z.of_int w.now)meaning.horizon
let satisfy (w:worker) (frame:P.frame) ports ingress round phase=
  w.pending<-List.map(fun(pending:obligation)->spend w 1;
    let meaning=Option.get w.rows.(pending.requirement_index).meaning in
    if pending.status<>Pending || not(live frame pending.binding) || not(within w meaning)then pending else
    let matched,unknown,reasons=match Option.get meaning.response with
      |Event selector->
          let found=List.find_opt(fun(event:P.event)->match pending.attempt_id with None->true|Some id->event.attempt_id=Some id)
            (events w ingress pending.binding selector) in
          Option.map(fun(event:P.event)->obj["event",str event.event_id;"tick",Json.int w.now;"round",Json.int round;"phase",str phase])found,false,[]
      |Value expression->let value=evaluate w ports pending.binding expression in
          (if truth value=I.True then Some(obj["truth",str "true";"tick",Json.int w.now;"round",Json.int round;"phase",str phase])else None),
          truth value=I.Unknown,uncertainty value in
    match matched with
    |Some witness->{pending with status=Pass;closed=Some w.now;reason=Some "response";witness=Some witness}
    |None->{pending with response_unknown=pending.response_unknown || unknown;
        uncertainty=(if unknown then List.sort_uniq String.compare(pending.uncertainty@reasons)else pending.uncertainty)})w.pending
let open_triggers (w:worker) (frame:P.frame) ports ingress round=
  spend w(Array.length w.rows*(1+List.length frame.slots));
  Array.iteri(fun index (row:ledger)->match row.meaning with
    |Some meaning when row.source.kind="progress" && within w meaning->
        List.iter(fun binding->List.iter(fun(event:P.event)->
          let value=match meaning.condition with None->sample w;{value=Some(Truth I.True);reasons=[]}
            |Some expression->evaluate w ports binding expression in
          let condition=truth value in
          update_coverage w index(fun coverage->{coverage with matched=coverage.matched+1;
            enabled=coverage.enabled+(if condition=I.True then 1 else 0);
            disabled=coverage.disabled+(if condition=I.False then 1 else 0);
            unknown_enabling=coverage.unknown_enabling+(if condition=I.Unknown then 1 else 0)});
          if condition<>I.False then(
            require(w.consumed.obligations<w.base.limits.max_obligations) "obligation_limit" "Complete requirement obligation ledger exceeds its bound.";
            spend w(List.length w.pending+1);w.consumed<-{w.consumed with obligations=w.consumed.obligations+1};
            let pending={requirement_index=index;binding;trigger_id=event.event_id;attempt_id=event.attempt_id;
              opened=w.now;opened_round=round;deadline=Z.add(Z.of_int w.now)(Option.get meaning.deadline);
              status=(if condition=I.Unknown then Unknown else Pending);closed=(if condition=I.Unknown then Some w.now else None);
              reason=(if condition=I.Unknown then Some "unknown_condition" else None);
              uncertainty=(if condition=I.Unknown then uncertainty value else []);response_unknown=false;witness=None} in
            w.pending<-w.pending@[pending]))(events w ingress binding(Option.get meaning.trigger)))(scopes frame meaning.scope)
    |_->())w.rows
let lifecycle (w:worker) (frame:P.frame)=
  require(List.map(fun(s:P.slot_snapshot)->s.slot_id)frame.slots=List.map(fun(s:P.slot_snapshot)->s.slot_id)w.base.slots)
    "frame" "Candidate slot inventory changed.";
  let changed=List.filter_map(fun(previous:P.slot_snapshot)->
    let current=List.find(fun(s:P.slot_snapshot)->s.slot_id=previous.slot_id)frame.slots in
    require(current.generation>=previous.generation && current.generation<=previous.generation+1) "frame" "Candidate generation is not a single causal reset.";
    if previous.active && (not current.active || current.generation<>previous.generation)then
      Some({P.slot=Some previous.slot_id;generation=previous.generation},if current.active then "encounter_reset"else "encounter_ended")else None)w.base.slots in
  w.pending<-List.map(fun(pending:obligation)->spend w 1;match List.assoc_opt pending.binding changed with
    |Some reason when pending.status=Pending->{pending with status=Unknown;closed=Some w.now;reason=Some reason}
    |_->pending)w.pending
let close_tick (w:worker) (frame:P.frame)=
  Array.iteri(fun index(row:ledger)->match row.meaning with
    |Some meaning when row.source.kind="safety" && within w meaning->
        List.iter(fun binding->let value=evaluate w frame.outputs binding(Option.get meaning.condition)in
          let result=truth value in spend w(List.length frame.attempts+1);
          let active=List.exists(fun(a:P.attempt)->a.binding=binding && a.status=P.Active)frame.attempts in
          let witness=obj["tick",Json.int w.now;"binding",binding_json binding;"reasons",arr(List.map str(uncertainty value))]in
          update_coverage w index(fun coverage->{coverage with samples=coverage.samples+1;
            true_samples=coverage.true_samples+(if result=I.True then 1 else 0);
            false_samples=coverage.false_samples+(if result=I.False then 1 else 0);
            unknown_samples=coverage.unknown_samples+(if result=I.Unknown then 1 else 0);
            active=coverage.active+(if active then 1 else 0);inactive=coverage.inactive+(if active then 0 else 1);
            first_failure=(if result=I.False && coverage.first_failure=None then Some witness else coverage.first_failure);
            first_unknown=(if result=I.Unknown && coverage.first_unknown=None then Some witness else coverage.first_unknown)}))(scopes frame meaning.scope)
    |_->())w.rows;
  w.pending<-List.map(fun(pending:obligation)->spend w 1;
    let meaning=Option.get w.rows.(pending.requirement_index).meaning in
    if pending.status=Pending && Z.leq pending.deadline(Z.of_int w.now) && within w meaning then
      {pending with status=(if pending.response_unknown then Unknown else Fail);closed=Some w.now;
        reason=Some(if pending.response_unknown then "unknown_response"else "deadline_without_response")}
    else pending)w.pending
let step (state:t) (frame:P.frame)=
  require(frame.tick=state.next && frame.tick<=state.horizon) "frame" "Candidate frame is not the next inclusive domain tick.";
  require(frame.rounds<>[] && List.length frame.rounds<=1000) "frame" "Candidate settling rounds are missing or exceed profile limits.";
  List.iteri(fun index(round:P.round)->require(round.microstep=index+1) "frame" "Candidate rounds are not consecutive.")frame.rounds;
  let w={base=state;now=frame.tick;rows=Array.of_list state.rows;pending=state.pending;consumed=state.consumed}in
  spend w(List.length frame.events+List.length frame.slots+List.length state.rows+1);
  lifecycle w frame;
  let rec rounds=function []->()|(round:P.round)::rest->
    spend w(List.length frame.events+1);
    let ingress=List.filter(fun(event:P.event)->event.microstep=round.microstep-1)frame.events in
    open_triggers w frame round.ports ingress round.microstep;
    satisfy w frame round.ports ingress round.microstep "before_activation";
    let post=match rest with (next:P.round)::_->next.ports|[]->frame.outputs in
    satisfy w frame post ingress round.microstep "after_atomic_writes";
    rounds rest in
  rounds frame.rounds;close_tick w frame;
  let serialized=Canonical.encode_bounded ~max_bytes:(8*1024*1024)
    (obj["previous",str state.history;"candidate_frame",P.frame_to_json frame])in
  spend w(String.length serialized);
  {state with rows=Array.to_list w.rows;pending=w.pending;slots=frame.slots;next=state.next+1;
    consumed={w.consumed with steps=w.consumed.steps+1};
    history=Canonical.sha256 serialized}
let status_name=function Pending|Unknown->"unknown"|Pass->"pass"|Fail->"fail"
type verdict=Passed|Failed|Uncertain|Not_exercised|Unsupported_requirement
type requirement_summary={id:string;kind:string;verdict:verdict;horizon_complete:bool;
  samples:int;true_samples:int;false_samples:int;unknown_samples:int;active:int;inactive:int;
  matched_triggers:int;enabled_triggers:int;disabled_triggers:int;unknown_enabling:int;
  passed_obligations:int;failed_obligations:int;unknown_obligations:int;pending_obligations:int}
let complete (state:t) (row:ledger)=match row.source.horizon with None->true|Some horizon->
  Q.compare(Q.mul state.resolution(Q.of_int(state.next-1)))horizon>=0
let row_obligations (state:t) index=List.filter(fun(p:obligation)->p.requirement_index=index)state.pending
let verdict (row:ledger) complete (obligations:obligation list)=
  let coverage=row.coverage in match row.meaning with None->Unsupported_requirement|Some _->
  if coverage.false_samples>0 || List.exists(fun(p:obligation)->p.status=Fail)obligations then Failed
  else if not complete || coverage.unknown_samples>0 || coverage.unknown_enabling>0 ||
    List.exists(fun(p:obligation)->p.status<>Pass)obligations then Uncertain
  else if (if row.source.kind="safety"then coverage.samples=0 else coverage.enabled=0)then Not_exercised else Passed
let verdict_name=function Passed->"pass"|Failed->"fail"|Uncertain->"unknown"
  |Not_exercised->"not_exercised"|Unsupported_requirement->"unsupported"
let summaries (state:t)=List.mapi(fun index(row:ledger)->
  let obligations=row_obligations state index and c=row.coverage in
  let count status=List.length(List.filter(fun(p:obligation)->p.status=status)obligations)in
  {id=row.source.requirement_id;kind=row.source.kind;verdict=verdict row(complete state row)obligations;
   horizon_complete=complete state row;samples=c.samples;true_samples=c.true_samples;false_samples=c.false_samples;
   unknown_samples=c.unknown_samples;active=c.active;inactive=c.inactive;matched_triggers=c.matched;
   enabled_triggers=c.enabled;disabled_triggers=c.disabled;unknown_enabling=c.unknown_enabling;
   passed_obligations=count Pass;failed_obligations=count Fail;unknown_obligations=count Unknown;pending_obligations=count Pending})state.rows
let exact_time (state:t) tick=
  let time=Q.mul state.resolution(Q.of_bigint tick)in
  let whole,remainder=Z.ediv_rem(Q.num time)(Q.den time)in
  let buffer=Buffer.create 32 in Buffer.add_string buffer(Z.to_string whole);
  if not(Z.equal remainder Z.zero)then(
    Buffer.add_char buffer '.';
    let rec decimal remaining budget=if not(Z.equal remaining Z.zero)then(
      require(budget>0) "time" "Exact requirement time is not a bounded decimal.";
      let digit,rest=Z.ediv_rem(Z.mul remaining(Z.of_int 10))(Q.den time)in
      Buffer.add_string buffer(Z.to_string digit);decimal rest(budget-1))in
    decimal remainder 256);
  str(Buffer.contents buffer)
let source_view (state:t)=
  let behavior=A.behavior(B.admitted_inputs state.binding)in
  List.mapi(fun index(row:ledger)->
    let obligations=row_obligations state index and c=row.coverage in
    let status=match verdict row(complete state row)obligations with Not_exercised->"unknown"|value->verdict_name value in
    obj["id",str row.source.requirement_id;"kind",str row.source.kind;"status",str status;"source",row.source.source;
      "assumptions",arr(List.map str row.source.assumptions);"conditional",Json.Bool(row.source.assumptions<>[] || behavior.assumptions<>[]);
      "coverage",obj["samples",Json.int c.samples;"true",Json.int c.true_samples;"false",Json.int c.false_samples;
        "unknown",Json.int c.unknown_samples;"triggers",Json.int(c.enabled+c.unknown_enabling);"active",Json.int c.active;
        "inactive",Json.int c.inactive;"horizon_complete",Json.Bool(complete state row)];
      "obligations",arr(List.map(fun(p:obligation)->obj[
        "trigger",str p.trigger_id;"binding",obj["encounter",optional str p.binding.slot;"generation",Json.int p.binding.generation];
        "attempt",optional str p.attempt_id;"opened_at",exact_time state(Z.of_int p.opened);"deadline",exact_time state p.deadline;
        "status",str(status_name p.status);"closed_at",optional(fun tick->exact_time state(Z.of_int tick))p.closed;
        "response_unknown",Json.Bool p.response_unknown])obligations)])state.rows
let rows_json ~include_source (state:t)=
  List.mapi(fun index(row:ledger)->
    let obligations=row_obligations state index in
    let complete=complete state row in
    let coverage=row.coverage in
    let status=verdict_name(verdict row complete obligations)in
    obj((if include_source then ["source",row.source.source]else[])@[
      "id",str row.source.requirement_id;"kind",str row.source.kind;"status",str status;
      "unsupported_reason",optional str row.unsupported;
      "coverage",obj["horizon_complete",Json.Bool complete;"samples",Json.int coverage.samples;
        "true",Json.int coverage.true_samples;"false",Json.int coverage.false_samples;"unknown",Json.int coverage.unknown_samples;
        "active",Json.int coverage.active;"inactive",Json.int coverage.inactive;"matched_triggers",Json.int coverage.matched;
        "enabled_triggers",Json.int coverage.enabled;"disabled_triggers",Json.int coverage.disabled;"unknown_enabling",Json.int coverage.unknown_enabling];
      "first_failure",optional Fun.id coverage.first_failure;"first_unknown",optional Fun.id coverage.first_unknown;
      "obligations",arr(List.map(fun(p:obligation)->obj["trigger",str p.trigger_id;"binding",binding_json p.binding;
        "attempt",optional str p.attempt_id;"opened_tick",Json.int p.opened;"opened_round",Json.int p.opened_round;
        "deadline_tick",str(Z.to_string p.deadline);"status",str(status_name p.status);"closed_tick",optional Json.int p.closed;
        "reason",optional str(if p.status=Pending then Some "pending_horizon"else p.reason);
        "response_unknown",Json.Bool p.response_unknown;"uncertainty",arr(List.map str p.uncertainty);
        "response_witness",optional Fun.id p.witness])obligations)]))state.rows
let usage_json (used:usage)=obj["steps",Json.int used.steps;"work",Json.int used.work;
  "obligations",Json.int used.obligations;"samples",Json.int used.samples]
let identity (state:t)=obj["profile",str profile;"binding_digest",str state.binding_digest;
  "limits",obj["max_work",Json.int state.limits.max_work;"max_obligations",Json.int state.limits.max_obligations;"max_samples",Json.int state.limits.max_samples];
  "next_tick",Json.int state.next;"domain_horizon_ticks",Json.int state.horizon;"history_digest",str state.history;
  "slots",arr(List.map(fun(slot:P.slot_snapshot)->obj["slot",str slot.slot_id;"generation",Json.int slot.generation;"active",Json.Bool slot.active])state.slots);
  "usage",usage_json state.consumed;"requirements",arr(rows_json ~include_source:false state)]
let report(state:t)=
  let value=obj["profile",str profile;"claim",str "candidate_prefix_only";"binding",B.report state.binding;
    "next_tick",Json.int state.next;"domain_horizon_ticks",Json.int state.horizon;"history_digest",str state.history;
    "usage",usage_json state.consumed;
    "requirements",arr(rows_json ~include_source:true state);"whole_domain",str "unassessed";"global_nonvacuity",str "unassessed";
    "material",str "unassessed";"export",str "withheld"]in
  ignore(Canonical.encode_bounded ~max_bytes:(8*1024*1024)value);value
let fingerprint state=Canonical.fingerprint(identity state)
