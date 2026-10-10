open Bioc_wire
module I = Bioc_domain.Policy_implementation
module Map = Map.Make(String)
module Set = Set.Make(String)

let profile = "biocompiler.policy_primitive_execution.v0.1"
let staged_execution_profile = "biocompiler.policy_staged_primitive_execution.v0.1"
let multi_site_execution_profile = "biocompiler.policy_multi_site_primitive_execution.v0.1"
let execution_profile implementation =
  if I.implementation_profile implementation=I.multi_site_profile then multi_site_execution_profile
  else if I.implementation_profile implementation=I.staged_profile then staged_execution_profile else profile
type reason = Missing | Stale | Invalid | Conflicting
type truth_signal = { value : I.truth option; reasons : reason list }
type binding = { slot : string option; generation : int }
type concrete_slot = { slot_id : string; target : string; start_tick : int }
type environment = { executor : string; slots : concrete_slot list; horizon_ticks : int }
type limits = { max_work : int; max_events : int; max_attempts : int; max_microsteps : int }
type evidence = Known of bool | Missing_evidence | Invalid_evidence | Conflicting_evidence
type observation = { observation_id : string; input_id : string; slot_id : string;
  observed_tick : int; observer : string; subject : string; evidence : evidence }
type outcome = Complete | Fail
type feedback = { feedback_id : string; input_id : string; attempt_id : string;
  executor : string; subject : string; slot_id : string; outcome : outcome }
type lifecycle = Reset | End
type input_batch = { tick : int; lifecycle : (string * lifecycle) list;
  observations : observation list; feedback : feedback list }
type event_kind = Primitive_event of I.event_kind | Encounter_started
  | Encounter_reset | Encounter_ended | Attempt_reset | Attempt_ended
type event = { event_id : string; origin : I.endpoint option; kind : event_kind;
  binding : binding; attempt_id : string option; tick : int; microstep : int }
type activation = { gate : string; guard : I.endpoint; binding : binding; causes : string list }
type attempt_status = Active | Completed | Failed | Timed_out | Reset_invalidated | End_invalidated
type attempt = { attempt_id : string; ordinal : int; bank : string; binding : binding;
  executor : string; subject : string; gate : string; guard : I.endpoint;
  causes : string list; product : string; started_tick : int; deadline_tick : int;
  ended_tick : int option; status : attempt_status; authorization : I.truth; machine : string option }
type truth_write = { commit : string; destination : string; binding : binding; value : I.truth }
type request = { commit : string; bank : string; activation : activation; product : string }
type machine_snapshot = { bank : string; binding : binding; state : string; retained_attempts : string list }
type machine_write = { commit : string; destination : string; binding : binding; state : string }
type machine_transition = { bank : string; gate : string; commit : string; binding : binding;
  destination : string; retained_attempts : string list }
type signal = Truth of truth_signal | Product of string | Events of event list
  | Activations of activation list | Writes of truth_write list
  | Requests of request list | Attempts of attempt list
  | Machine of machine_snapshot | Machine_writes of machine_write list
type port_value = { endpoint : I.endpoint; binding : binding; signal : signal }
type evidence_snapshot = { bank : string; binding : binding; signal : truth_signal;
  observed_tick : int option; available_tick : int option; occurrences : string list }
type action_kind = Deferred of activation * reason list
  | Undefined_commit of activation | Suppressed of activation * string
  | Authorization_changed of string * I.truth * reason list * string
  | Feedback_accepted of string * string | Feedback_rejected of string * string * string
  | Observation_batch of { bank : string; binding : binding; input_ids : string list;
      retained_ids : string list; evidence : evidence; observed_tick : int }
  | State_written of truth_write | Effect_requested of attempt | Machine_transition of machine_transition
type action = { microstep : int; detail : action_kind }
type round = { microstep : int; ports : port_value list }
type slot_snapshot = { slot_id : string; generation : int; active : bool }
type frame = { tick : int; rounds : round list; outputs : port_value list;
  events : event list; actions : action list; creations : attempt list;
  attempts : attempt list; evidence : evidence_snapshot list; slots : slot_snapshot list;
  machines : machine_snapshot list; execution_profile : string }
type slot_state = { description : concrete_slot; generation : int; active : bool; generation_start : int }
type retained_evidence = { observed : int; available : int; evidence : evidence; occurrences : string list }
type control = { arbiter : string; lane : int; commit : string; gate : string }
type plan = { implementation : I.t; environment : environment; limits : limits;
  nodes : I.node list; node_index : I.node Map.t; incoming : I.endpoint Map.t;
  destinations : I.endpoint Map.t; controls : control list; input_index : I.external_input Map.t }
type state = { plan : plan; next : int; slots : slot_state list;
  registers : I.truth Map.t; evidence : retained_evidence Map.t; rising : I.truth Map.t;
  machines : machine_snapshot Map.t;
  attempts : attempt list; sequence : int; allocated : int; work : int; retained : int;
  observation_ids : Set.t; feedback_ids : Set.t }
type usage = { work : int; retained : int; allocations : int }
type worker = { mutable current : state; now : int; mutable microstep : int;
  mutable events_rev : event list; mutable actions_rev : action list; mutable creations_rev : attempt list;
  mutable frame_cost : int; work_ceiling : int; retained_ceiling : int }
let fail code message = Diagnostic.fail ("policy_primitives_" ^ code) message
let require condition code message = if not condition then fail code message
let endpoint node_id port_id : I.endpoint = { node_id; port_id }
let key (e:I.endpoint) = Canonical.encode (Json.Array [Json.String e.node_id; Json.String e.port_id])
let cell node (b:binding) = Canonical.encode (Json.Array [Json.String node;
  (match b.slot with None -> Json.Null | Some slot -> Json.String slot); Json.int b.generation])
let executor_binding = { slot=None; generation=0 }
let binding (s:slot_state) = {slot=Some s.description.slot_id;generation=s.generation}
let name value = require (String.length value>0 && String.length value<=256) "input" "Runtime identity exceeds its closed bound.";
  ignore(Json.name(Json.String value))
let bounded_list maximum values =
  let rec scan count = function []->()|_::rest->require(count<maximum) "limit" "Runtime list exceeds its declared bound.";scan(count+1)rest in
  scan 0 values
let unique ?(validate=true) label values =
  ignore(List.fold_left(fun seen id->if validate then name id;require(not(Set.mem id seen)) "identity" ("Duplicate "^label^" identity.");Set.add id seen)Set.empty values)
let node (p:plan) id = match Map.find_opt id p.node_index with Some value->value|None->fail "graph" "Absent runtime node."
let input (p:plan) id port = match Map.find_opt(key(endpoint id port))p.incoming with
  |Some value->value|None->fail "graph" "Runtime input lacks a graph producer."
let destination (p:plan) id port = match Map.find_opt(key(endpoint id port))p.destinations with
  |Some value->value|None->fail "graph" "Atomic output lacks a unique bank destination."
let context (p:plan) (e:I.endpoint) (b:binding) = match (node p e.node_id).model.replication with
  |I.Executor->executor_binding|I.Encounter_slots _->b
let live_bindings (s:state) (n:I.node) = match n.model.replication with
  |I.Executor->[executor_binding]|I.Encounter_slots _->List.filter_map(fun(slot:slot_state)->if slot.active then Some(binding slot)else None)s.slots
let find_slot (s:state) id = match List.find_opt(fun slot->slot.description.slot_id=id)s.slots with
  |Some value->value|None->fail "identity" "Input names an absent concrete slot."
let charge w amount =
  let s=w.current in require(amount>=0 && amount<=min s.plan.limits.max_work w.work_ceiling-s.work) "work_limit" "Cumulative or per-step primitive execution work exhausted.";
  w.current<-{s with work=s.work+amount}
let retain w = charge w 1;let s=w.current in
  require(s.retained<min s.plan.limits.max_events w.retained_ceiling) "trace_limit" "Complete primitive event/action/port inventory exceeds its bound.";
  w.current<-{s with retained=s.retained+1}
let retain_payload w count = charge w count;let s=w.current in
  require(count<=min s.plan.limits.max_events w.retained_ceiling-s.retained) "trace_limit" "Expanded semantic payload inventory exceeds its bound.";
  w.current<-{s with retained=s.retained+count}
let reserve_output w cost =
  require(cost>=0 && cost<=8*1024*1024-w.frame_cost) "trace_limit" "Expanded tick frame exceeds its 8 MiB conservative output bound.";
  charge w cost;w.frame_cost<-w.frame_cost+cost
let text_cost value=8+6*String.length value
let texts_cost values=List.fold_left(fun count value->count+text_cost value)0 values
let binding_cost (value:binding)=80+(match value.slot with None->0|Some slot->text_cost slot)
let endpoint_cost (value:I.endpoint)=80+text_cost value.node_id+text_cost value.port_id
let activation_cost (value:activation)=160+text_cost value.gate+endpoint_cost value.guard+binding_cost value.binding+texts_cost value.causes
let attempt_cost (value:attempt)=1000+texts_cost[value.attempt_id;value.bank;value.executor;value.subject;value.gate;value.product]+
  endpoint_cost value.guard+binding_cost value.binding+texts_cost value.causes+
  (match value.machine with None->0|Some bank->text_cost bank)
let machine_cost (value:machine_snapshot)=200+text_cost value.bank+binding_cost value.binding+
  text_cost value.state+texts_cost value.retained_attempts
let action w detail =
  let count,cost=match detail with
    |Deferred(a,reasons)->List.length a.causes+List.length reasons,activation_cost a+24*List.length reasons
    |Undefined_commit a|Suppressed(a,_)->List.length a.causes,activation_cost a
    |Authorization_changed(id,_,reasons,_)->List.length reasons,text_cost id+24*List.length reasons
    |Observation_batch{bank;binding;input_ids;retained_ids;_}->List.length input_ids+List.length retained_ids,
        text_cost bank+binding_cost binding+texts_cost input_ids+texts_cost retained_ids
    |State_written value->0,text_cost value.commit+text_cost value.destination+binding_cost value.binding
    |Effect_requested value->List.length value.causes,attempt_cost value
    |Machine_transition value->List.length value.retained_attempts,300+text_cost value.bank+
        text_cost value.gate+text_cost value.commit+binding_cost value.binding+text_cost value.destination+texts_cost value.retained_attempts
    |Feedback_accepted(id,attempt)->0,text_cost id+text_cost attempt
    |Feedback_rejected(id,attempt,reason)->0,text_cost id+text_cost attempt+text_cost reason in
  retain w;retain_payload w count;reserve_output w(500+cost);w.actions_rev<-{microstep=w.microstep;detail}::w.actions_rev
let emit w ?origin ?attempt_id kind binding =
  retain w;let s=w.current in let sequence=s.sequence+1 in w.current<-{s with sequence};
  let value={event_id="primitive/event/"^string_of_int sequence;origin;kind;binding;attempt_id;
    tick=w.now;microstep=w.microstep}in
  reserve_output w(500+text_cost value.event_id+binding_cost binding+(match origin with None->0|Some e->endpoint_cost e));
  w.events_rev<-value::w.events_rev;value
let known value = {value=Some value;reasons=[]}
let truth (signal:truth_signal) = Option.value signal.value ~default:I.Unknown
let inverse = function I.True->I.False|I.False->I.True|I.Unknown->I.Unknown
let conjunction a b = match a,b with I.False,_|_,I.False->I.False|I.True,I.True->I.True|_->I.Unknown
let disjunction a b = match a,b with I.True,_|_,I.True->I.True|I.False,I.False->I.False|_->I.Unknown
let reason = function Known _->None|Missing_evidence->Some Missing|Invalid_evidence->Some Invalid|Conflicting_evidence->Some Conflicting
let evidence_signal now freshness = function
  |None->{value=None;reasons=[Missing]}
  |Some(retained:retained_evidence)->(match reason retained.evidence with Some reason->{value=None;reasons=[reason]}|None->
      if now-retained.observed>=freshness then {value=None;reasons=[Stale]}else
      match retained.evidence with Known value->known(if value then I.True else I.False)|_->assert false)

let initialize ~implementation ~(environment:environment) ~(limits:limits) =
  bounded_list 16 environment.slots;name environment.executor;
  require(environment.horizon_ticks>=0 && environment.horizon_ticks<=10000) "limit" "Runtime horizon exceeds finite ticks.";
  require(environment.slots<>[] && List.length environment.slots=(I.slot_layout implementation).slots) "scope" "Concrete ordered slot layout differs from the graph.";
  unique "slot"(List.map(fun(s:concrete_slot)->s.slot_id)environment.slots);
  List.iter(fun(s:concrete_slot)->name s.target;require(s.start_tick>=0 && s.start_tick<=environment.horizon_ticks) "input" "Slot start is outside the supplied horizon.")environment.slots;
  List.iter(fun(value,maximum)->require(value>0 && value<=maximum) "limit" "Runtime limits require explicit positive bounded values.")
    [limits.max_work,100_000_000;limits.max_events,1_000_000;limits.max_attempts,10000;limits.max_microsteps,1000];
  let nodes=I.nodes implementation in
  let node_index=List.fold_left(fun map(n:I.node)->Map.add n.node_id n map)Map.empty nodes
  and incoming=List.fold_left(fun map(w:I.wire)->Map.add(key w.consumer)w.producer map)Map.empty(I.wires implementation)
  and destinations=List.fold_left(fun map(w:I.wire)->Map.add(key w.producer)w.consumer map)Map.empty(I.wires implementation)
  and input_index=List.fold_left(fun map(i:I.external_input)->Map.add i.input_id i map)Map.empty(I.inputs implementation)in
  let base={implementation;environment;limits;nodes;node_index;incoming;destinations;controls=[];input_index}in
  let controls=List.concat_map(fun(g:I.atomic_group)->List.mapi(fun lane commit->
    let producer=input base g.arbiter("in"^string_of_int lane)in
    require(producer.port_id="candidate" && (match(node base producer.node_id).model.primitive with
      |I.Activation_gate|I.Transition_gate _->true|_->false))
      "unsupported" "Initial runtime requires direct activation-gate to arbiter to commit control.";
    {arbiter=g.arbiter;lane;commit;gate=producer.node_id})g.commits)(I.atomic_groups implementation)in
  unique "initiating gate control"(List.map(fun(c:control)->c.gate)controls);
  List.iter(fun(n:I.node)->match n.model.primitive with
    |I.Activation_gate|I.Transition_gate _->
        let owner=match List.find_opt(fun(c:control)->c.gate=n.node_id)controls with
          |Some owner->owner|None->fail "unsupported" "Every gate needs exactly one direct atomic control path."in
        (match n.model.primitive,(node base owner.commit).model.primitive with
         |I.Activation_gate,I.Atomic_commit _->()
         |I.Transition_gate{source;correlation},I.Transition_commit{destination=target;_}->
             let snapshot=input base n.node_id "machine"and writer=destination base owner.commit "machine_write"in
             require(snapshot.port_id="snapshot" && snapshot.node_id=writer.node_id) "unsupported"
               "Transition reads and writes different machine banks.";
             (match(node base snapshot.node_id).model.primitive with
              |I.Machine_bank{states;_}->require(List.mem source states && List.mem target states) "unsupported"
                  "Transition state is absent from its actual machine alphabet."
              |_->fail "unsupported" "Transition snapshot does not come from a machine bank.");
             (match correlation with I.Unbound->()|I.Retained_attempt->
               let selected=input base n.node_id "on"in
               require(selected.port_id="selected" && (match(node base selected.node_id).model.primitive with
                 |I.Event_select(I.Completed|I.Failed|I.Timed_out)->true|_->false)) "unsupported"
                 "Retained transition requires an explicit completion/failure/timeout selector.";
               let origin=input base selected.node_id "events"in
               require(origin.port_id="events" && (match(node base origin.node_id).model.primitive with
                 |I.Attempt_bank _|I.Attempt_bank_sites _->true|_->false)) "unsupported" "Retained transition selector lacks an actual attempt bank.")
         |_->fail "unsupported" "Legacy and machine controls cannot interchange their commit semantics.")
    |I.Attempt_bank _->let producer=input base n.node_id "request"in
        let owner=match List.find_opt(fun(c:control)->c.commit=producer.node_id)controls with Some c->c|None->fail "unsupported" "Attempt requests need one actual initiating gate."in
        require(input base n.node_id "authorization"=input base owner.gate "guard") "unsupported" "Attempt authorization differs from the retained initiating guard endpoint."
    |I.Attempt_bank_sites{sites;_}->
        let owners=List.init sites(fun index->
          let suffix=string_of_int index in
          let producer=input base n.node_id("request"^suffix)in
          let owner=match List.find_opt(fun(c:control)->c.commit=producer.node_id)controls with
            |Some c->c|None->fail "unsupported" "Every request site needs an actual initiating transition."in
          require(producer.port_id="request0" &&
            (match(node base owner.commit).model.primitive with I.Transition_commit{requests=1;_}->true|_->false))
            "unsupported" "Multi-site attempts require one request per original transition commit.";
          require(input base n.node_id("authorization"^suffix)=input base owner.gate "guard")
            "unsupported" "Request-site authorization differs from its initiating guard endpoint.";owner)in
        unique "request-site gate"(List.map(fun(c:control)->c.gate)owners);
        let arbiters=List.sort_uniq String.compare(List.map(fun(c:control)->c.arbiter)owners)in
        require(List.length arbiters=1 && (match(node base(List.hd arbiters)).model.primitive with
          |I.Exclusive_arbiter _->true|_->false)) "unsupported"
          "Shared attempt sites require one exclusive arbiter with rejected conflicts.";
        let machines=List.sort_uniq String.compare(List.map(fun(c:control)->
          (destination base c.commit "machine_write").node_id)owners)in
        require(List.length machines=1) "unsupported" "Shared effect request sites must retain one actual machine owner."
    |_->())nodes;
  let ancestry=Hashtbl.create 32 in
  let rec observed depth (e:I.endpoint)=
    require(depth<=256) "unsupported" "Observed-edge ancestry exceeds the acyclic profile.";
    match Hashtbl.find_opt ancestry(key e)with Some value->value|None->
    let value=match(node base e.node_id).model.primitive with
    |I.Evidence_bank _->true|I.Truth_constant _->false
    |I.Truth_not->observed(depth+1)(input base e.node_id "in")
    |I.Truth_all count|I.Truth_any count->List.fold_left(fun found index->observed(depth+1)(input base e.node_id("in"^string_of_int index))||found)false(List.init count Fun.id)
    |I.Truth_equal->let left=observed(depth+1)(input base e.node_id "left")and right=observed(depth+1)(input base e.node_id "right")in left||right
    |_->fail "unsupported" "Observed rising accepts evidence and pure truth logic, without state feedback."in
    Hashtbl.add ancestry(key e)value;value in
  List.iter(fun(n:I.node)->match n.model.primitive with I.Observed_rising->
    require(observed 0(input base n.node_id "in")) "unsupported" "Observed rising requires at least one evidence bank."|_->())nodes;
  {plan={base with controls};next=0;slots=List.map(fun description->{description;generation=0;active=false;generation_start=description.start_tick})environment.slots;
   registers=Map.empty;evidence=Map.empty;rising=Map.empty;machines=Map.empty;attempts=[];sequence=0;allocated=0;work=0;retained=0;
   observation_ids=Set.empty;feedback_ids=Set.empty}
let next_tick (s:state)=s.next
let usage (s:state):usage={work=s.work;retained=s.retained;allocations=s.allocated}
let machine (snapshot:state) bank binding = match Map.find_opt(cell bank binding)snapshot.machines with
  |Some value->value|None->fail "scope" "Live machine has no independent slot storage."

let evaluator w (snapshot:state) =
  let memo=Hashtbl.create 32 in
  let rec evaluate (e:I.endpoint) b =
    let b=context snapshot.plan e b in let cache=key e^cell "" b in
    match Hashtbl.find_opt memo cache with Some result->result|None->
      charge w 1;
      let n=node snapshot.plan e.node_id in
      let argument port=evaluate(input snapshot.plan n.node_id port)b in
      let result=match n.model.primitive with
      |I.Truth_constant value->known value
      |I.Evidence_bank{freshness_ticks}->evidence_signal w.now freshness_ticks(Map.find_opt(cell n.node_id b)snapshot.evidence)
      |I.Truth_register _->(match Map.find_opt(cell n.node_id b)snapshot.registers with Some value->known value|None->fail "scope" "Live register has no independent slot storage.")
      |I.Truth_not->let value=argument "in"in {value=Some(inverse(truth value));reasons=value.reasons}
      |I.Truth_all count|I.Truth_any count->
          let operands=List.init count(fun index->argument("in"^string_of_int index))in
          let operation,initial=match n.model.primitive with I.Truth_all _->conjunction,I.True|_->disjunction,I.False in
          let reason_count=List.fold_left(fun count(v:truth_signal)->count+List.length v.reasons)0 operands in
          require(reason_count<=4096) "trace_limit" "Ordered uncertainty reasons exceed the finite signal bound.";charge w reason_count;
          {value=Some(List.fold_left(fun value operand->operation value(truth operand))initial operands);
           reasons=List.concat_map(fun(v:truth_signal)->v.reasons)operands}
      |I.Truth_equal->let left=argument "left"and right=argument "right"in
          if truth left=I.Unknown || truth right=I.Unknown then (
            require(List.length left.reasons+List.length right.reasons<=4096) "trace_limit" "Ordered uncertainty reasons exceed the finite signal bound.";
            charge w(List.length left.reasons+List.length right.reasons);{value=Some I.Unknown;reasons=left.reasons@right.reasons})
          else known(if left.value=right.value then I.True else I.False)
      |_->fail "graph" "Truth wire reaches a non-truth primitive."in
      Hashtbl.add memo cache result;result in evaluate
let product (p:plan) (e:I.endpoint) = match(node p e.node_id).model.primitive with
  |I.Product_constant value->value|_->fail "unsupported" "Product requests require supplied constant symbols."
let event_evaluator w (snapshot:state) (events:event list) =
  let memo=Hashtbl.create 32 in
  let rec evaluate (e:I.endpoint) b =
    let b=context snapshot.plan e b in let cache=key e^cell "" b in
    match Hashtbl.find_opt memo cache with Some value->value|None->
      charge w (1+List.length events);
      let result=match(node snapshot.plan e.node_id).model.primitive with
      |I.Event_select kind->List.filter(fun(event:event)->event.kind=Primitive_event kind)(evaluate(input snapshot.plan e.node_id "events")b)
      |I.Evidence_bank _|I.Observed_rising|I.Attempt_bank _|I.Attempt_bank_sites _->List.filter(fun(event:event)->event.origin=Some e && event.binding=b)events
      |_->fail "graph" "Event wire reaches a non-event primitive."in
      Hashtbl.add memo cache result;result in evaluate
let initialize_slot w (slot:slot_state) =
  let b=binding slot in
  List.iter(fun(n:I.node)->charge w 1;match n.model.primitive with
    |I.Truth_register{initial;_}->let s=w.current in w.current<-{s with registers=Map.add(cell n.node_id b)initial s.registers}
    |I.Machine_bank{initial;_}->let s=w.current in
        let value:machine_snapshot={bank=n.node_id;binding=b;state=initial;retained_attempts=[]}in
        w.current<-{s with machines=Map.add(cell n.node_id b)value s.machines}
    |_->())w.current.plan.nodes
let discard_slot w (slot:slot_state) reset =
  let b=binding slot in
  List.iter(fun(n:I.node)->charge w 1;let k=cell n.node_id b in let s=w.current in
    w.current<-{s with registers=Map.remove k s.registers;evidence=Map.remove k s.evidence;rising=Map.remove k s.rising;
      machines=Map.remove k s.machines})w.current.plan.nodes;
  let attempts=List.map(fun(a:attempt)->charge w 1;if a.binding=b && a.status=Active then (
    ignore(emit w ~origin:(endpoint a.bank "events") ~attempt_id:a.attempt_id (if reset then Attempt_reset else Attempt_ended)b);
    {a with status=(if reset then Reset_invalidated else End_invalidated);ended_tick=Some w.now})else a)w.current.attempts in
  w.current<-{w.current with attempts}
let apply_lifecycle w (batch:input_batch) =
  unique "lifecycle slot"(List.map fst batch.lifecycle);
  List.iter(fun(id,_)->let slot=find_slot w.current id in require(slot.active && w.now>slot.description.start_tick) "identity" "Lifecycle input must lie strictly inside an active slot lifetime.")batch.lifecycle;
  let slots=List.map(fun(slot:slot_state)->charge w 1;
    let slot=if slot.description.start_tick=w.now then (
      let started={slot with active=true}in initialize_slot w started;
      ignore(emit w Encounter_started(binding started));started)else slot in
    match List.assoc_opt slot.description.slot_id batch.lifecycle with
    |None->slot
    |Some Reset->discard_slot w slot true;
        let next={slot with generation=slot.generation+1;generation_start=w.now}in
        initialize_slot w next;ignore(emit w Encounter_reset(binding next));next
    |Some End->discard_slot w slot false;ignore(emit w Encounter_ended(binding slot));{slot with active=false})w.current.slots in
  w.current<-{w.current with slots}
let merge_evidence previous (rows:observation list) now =
  let newest=List.fold_left(fun value(row:observation)->max value row.observed_tick)(match previous with None->(-1)|Some e->e.observed)rows in
  let selected=List.filter(fun(row:observation)->row.observed_tick=newest)rows in
  let members=(match previous with Some e when e.observed=newest->[e.evidence,e.occurrences,e.available]|_->[])@
    List.map(fun(row:observation)->row.evidence,[row.observation_id],now)selected in
  match members with
  |[]->Option.get previous
  |(first,_,_)::_->let same=List.for_all(fun(value,_,_)->value=first)members in
      {observed=newest;available=List.fold_left(fun value(_,_,tick)->max value tick)0 members;
       evidence=(if same then first else Conflicting_evidence);occurrences=List.concat_map(fun(_,ids,_)->ids)members}
let external_endpoint (p:plan) id kind = name id;
  match Map.find_opt id p.input_index with Some input when input.input_kind=kind->input.consumer
  |_->fail "input" "External input identity/kind does not match an actual graph port."
let apply_observations w (batch:input_batch) =
  let groups=ref []in
  List.iter(fun(row:observation)->charge w 1;name row.observation_id;name row.observer;name row.subject;
    require(not(Set.mem row.observation_id w.current.observation_ids || Set.mem row.observation_id w.current.feedback_ids)) "identity" "Observation occurrence identity was reused.";
    let target=external_endpoint w.current.plan row.input_id I.Evidence_input in
    let slot=find_slot w.current row.slot_id in
    require(slot.active && row.observer=w.current.plan.environment.executor && row.subject=slot.description.target)
      "identity" "Observation recipient, observer or slot lifetime differs.";
    require(row.observed_tick>=slot.generation_start && row.observed_tick<=w.now) "identity" "Observation age predates this generation or lies in the future.";
    let s=w.current in w.current<-{s with observation_ids=Set.add row.observation_id s.observation_ids};
    let group=target.node_id,binding slot in
    let previous=Option.value(List.assoc_opt group !groups)~default:[]in
    groups:=List.remove_assoc group !groups@[group,previous@[row]])batch.observations;
  List.map(fun((bank,b),rows)->charge w(List.length rows);
    let s=w.current and k=cell bank b in
    let retained=merge_evidence(Map.find_opt k s.evidence)rows w.now in
    w.current<-{s with evidence=Map.add k retained s.evidence};
    action w(Observation_batch{bank;binding=b;input_ids=List.map(fun(row:observation)->row.observation_id)rows;
      retained_ids=retained.occurrences;evidence=retained.evidence;observed_tick=retained.observed});
    emit w ~origin:(endpoint bank "updated") (Primitive_event I.Updated)b) !groups
let apply_feedback w (batch:input_batch) =
  (* Conflicting simultaneous outcomes are invalid before any effect mutation. *)
  let addresses=ref []in
  List.iter(fun(row:feedback)->charge w 1;name row.feedback_id;name row.attempt_id;name row.executor;name row.subject;name row.slot_id;
    require(not(Set.mem row.feedback_id w.current.feedback_ids || Set.mem row.feedback_id w.current.observation_ids)) "identity" "Feedback occurrence identity was reused.";
    ignore(external_endpoint w.current.plan row.input_id I.Feedback_input);
    let address=row.attempt_id in
    (match List.assoc_opt address !addresses with Some previous->require(previous=row.outcome) "feedback" "One simultaneous feedback address has conflicting outcomes."|None->());
    addresses:=(address,row.outcome):: !addresses;
    let s=w.current in w.current<-{s with feedback_ids=Set.add row.feedback_id s.feedback_ids})batch.feedback;
  List.filter_map(fun(row:feedback)->charge w(1+List.length w.current.attempts);
    let target=external_endpoint w.current.plan row.input_id I.Feedback_input in
    let rejected why=action w(Feedback_rejected(row.feedback_id,row.attempt_id,why));None in
    match List.find_opt(fun(a:attempt)->a.attempt_id=row.attempt_id)w.current.attempts with
    |None->rejected "unknown_attempt"
    |Some a when a.bank<>target.node_id || a.executor<>row.executor || a.subject<>row.subject || a.binding.slot<>Some row.slot_id->rejected "identity_mismatch"
    |Some a when a.status<>Active->rejected "stale_attempt"
    |Some a->let slot=find_slot w.current row.slot_id in
        if not slot.active || slot.generation<>a.binding.generation then rejected "stale_attempt"else (
          let changed={a with status=(match row.outcome with Complete->Completed|Fail->Failed);ended_tick=Some w.now}in
          w.current<-{w.current with attempts=List.map(fun(current:attempt)->if current.attempt_id=a.attempt_id then changed else current)w.current.attempts};
          action w(Feedback_accepted(row.feedback_id,a.attempt_id));
          Some(emit w ~origin:(endpoint a.bank "events") ~attempt_id:a.attempt_id
            (Primitive_event(match row.outcome with Complete->I.Completed|Fail->I.Failed))a.binding)))batch.feedback
let apply_timeouts w =
  let events=ref []in
  let attempts=List.map(fun(a:attempt)->charge w 1;
    if a.status=Active && a.deadline_tick=w.now then (
      events:= !events@[emit w ~origin:(endpoint a.bank "events") ~attempt_id:a.attempt_id (Primitive_event I.Timed_out)a.binding];
      {a with status=Timed_out;ended_tick=Some w.now})else a)w.current.attempts in
  w.current<-{w.current with attempts};!events
let refresh_authorization w =
  let snapshot=w.current in let evaluate=evaluator w snapshot in
  let attempts=List.map(fun(a:attempt)->charge w 1;
    match(node snapshot.plan a.bank).model.primitive with
    |(I.Attempt_bank{authorization=I.Continuous;on_unknown;_}
      |I.Attempt_bank_sites{authorization=I.Continuous;on_unknown;_})when a.status=Active->
        let signal=evaluate a.guard a.binding in let value=truth signal in
        if value=a.authorization then a else (
          let response=if value=I.Unknown then(match on_unknown with I.Continue->"continue"|I.Defer->"defer")else if value=I.False then "continue"else "authorized"in
          action w(Authorization_changed(a.attempt_id,value,signal.reasons,response));{a with authorization=value})
    |_->a)snapshot.attempts in
  w.current<-{w.current with attempts}
let update_rising w =
  let snapshot=w.current in let evaluate=evaluator w snapshot in
  List.concat_map(fun(n:I.node)->match n.model.primitive with
    |I.Observed_rising->List.filter_map(fun b->
        let k=cell n.node_id b in let before=Option.value(Map.find_opt k w.current.rising)~default:I.Unknown in
        let after=truth(evaluate(input snapshot.plan n.node_id "in")b)in
        w.current<-{w.current with rising=Map.add k after w.current.rising};
        if before=I.False && after=I.True then Some(emit w ~origin:(endpoint n.node_id "events") (Primitive_event I.Rising)b)else None)
        (live_bindings snapshot n)
    |_->[])snapshot.plan.nodes

type prepared = { writes : (int * truth_write) list; requests : (int * request) list;
  machine_write : machine_write option; activation : activation }
let control (p:plan) gate = match List.find_opt(fun(c:control)->c.gate=gate)p.controls with
  |Some value->value|None->fail "graph" "Gate lacks its direct atomic path."
let candidates w (snapshot:state) (evaluate:I.endpoint -> binding -> truth_signal) events =
  let evaluate_events=event_evaluator w snapshot events in
  List.concat_map(fun(n:I.node)->match n.model.primitive with
    |I.Activation_gate|I.Transition_gate _->List.filter_map(fun b->
        let selected=match n.model.primitive with
          |I.Transition_gate{source;_}->
              let bank=input snapshot.plan n.node_id "machine"in
              (machine snapshot bank.node_id b).state=source
          |_->true in
        let causes=if not selected then []else evaluate_events(input snapshot.plan n.node_id "on")b in
        let causes=match n.model.primitive with
          |I.Transition_gate{correlation=I.Retained_attempt;_}->
              let bank=input snapshot.plan n.node_id "machine"in
              let retained=(machine snapshot bank.node_id b).retained_attempts in
              List.filter(fun(e:event)->charge w(1+List.length retained);
                match e.attempt_id with Some id->List.mem id retained|None->false)causes
          |_->causes in
        if causes=[] then None else (
          let guard=input snapshot.plan n.node_id "guard"in
          let a={gate=n.node_id;guard;binding=b;causes=List.map(fun(e:event)->e.event_id)causes}in
          let signal=evaluate guard b in
          match truth signal with I.True->Some a|I.False->None|I.Unknown->
            (match n.model.primitive with I.Activation_gate->action w(Deferred(a,signal.reasons))|_->());None))
        (live_bindings snapshot n)
    |_->[])snapshot.plan.nodes
let arbitrate w (values:activation list) =
  let p=w.current.plan in
  let groups=List.fold_left(fun groups(a:activation)->
    let owner=control p a.gate in let key=owner.arbiter,a.binding in
    let previous=Option.value(List.assoc_opt key groups)~default:[]in
    List.remove_assoc key groups@[key,previous@[a]])[]values in
  List.concat_map(fun((arbiter,_),members)->charge w(List.length members);
    match members with []->[]|[_]->members|_->
      match(node p arbiter).model.primitive with
      |I.Exclusive_arbiter _->fail "exclusive" "Simultaneous gate activations violate supplied exclusive arbitration."
      |I.Priority_arbiter order->
          let rank (a:activation)=let lane=(control p a.gate).lane in
            let rec find index=function []->fail "graph" "Priority lane is absent."|x::rest->if x=lane then index else find(index+1)rest in find 0 order in
          let sorted=List.stable_sort(fun a b->compare(rank a)(rank b))members in
          let selected=List.hd sorted in
          List.iter(fun(a:activation)->action w(Suppressed(a,selected.gate)))(List.tl sorted);[selected]
      |_->fail "graph" "Activation group lacks an arbiter.")groups
let prepare w (snapshot:state) (evaluate:I.endpoint -> binding -> truth_signal) (selected:activation list) =
  List.filter_map(fun(a:activation)->charge w 1;
    let owner=control snapshot.plan a.gate in
    let writes,requests=match(node snapshot.plan owner.commit).model.primitive with
      |I.Atomic_commit{writes;requests}|I.Transition_commit{writes;requests;_}->writes,requests
      |_->fail "graph" "Control does not terminate at an atomic commit."in
    let operands=List.init writes(fun index->index,evaluate(input snapshot.plan owner.commit("value"^string_of_int index))a.binding)in
    if List.exists(fun(_,(value:truth_signal))->value.value=None)operands then (action w(Undefined_commit a);None)else
    let writes=List.map(fun(index,(value:truth_signal))->
      let target=destination snapshot.plan owner.commit("write"^string_of_int index)in
      index,{commit=owner.commit;destination=target.node_id;binding=a.binding;value=Option.get value.value})operands in
    let requests=List.init requests(fun index->
      let target=destination snapshot.plan owner.commit("request"^string_of_int index)in
      let product=product snapshot.plan(input snapshot.plan owner.commit("product"^string_of_int index))in
      index,{commit=owner.commit;bank=target.node_id;activation=a;product})in
    let machine_write=match(node snapshot.plan owner.commit).model.primitive with
      |I.Transition_commit{destination=state;_}->
          let bank=destination snapshot.plan owner.commit "machine_write"in
          Some{commit=owner.commit;destination=bank.node_id;binding=a.binding;state}
      |_->None in
    Some{writes;requests;machine_write;activation=a})selected
let commit w (prepared:prepared list) =
  let writes=List.concat_map(fun(p:prepared)->List.map snd p.writes)prepared
  and requests=List.concat_map(fun(p:prepared)->List.map snd p.requests)prepared in
  unique ~validate:false "simultaneous state write"(List.map(fun(write:truth_write)->cell write.destination write.binding)writes);
  require(List.length requests<=w.current.plan.limits.max_attempts-w.current.allocated) "attempt_limit" "Cumulative attempt allocation bound exhausted before atomic commit.";
  let counts=ref Map.empty in
  List.iter(fun(request:request)->charge w(1+List.length w.current.attempts);
    let key=cell request.bank request.activation.binding in
    let old=match Map.find_opt key !counts with Some count->count|None->
      List.fold_left(fun count(a:attempt)->if a.bank=request.bank && a.binding=request.activation.binding && a.status=Active then count+1 else count)0 w.current.attempts in
    let capacity=match(node w.current.plan request.bank).model.primitive with I.Attempt_bank{capacity;_}|I.Attempt_bank_sites{capacity;_}->capacity|_->fail "graph" "Request does not reach an attempt bank."in
    require(old<capacity) "capacity" "Per-bank/per-slot active attempt capacity exhausted before atomic commit.";
    counts:=Map.add key(old+1)!counts)requests;
  let machine_writes=List.filter_map(fun(p:prepared)->p.machine_write)prepared in
  unique ~validate:false "simultaneous machine write"
    (List.map(fun(write:machine_write)->cell write.destination write.binding)machine_writes);
  List.iter(fun(p:prepared)->match p.machine_write with None->()|Some write->
    charge w 1;
    let previous=machine w.current write.destination write.binding in
    let terminal,capacity=match(node w.current.plan write.destination).model.primitive with
      |I.Machine_bank{terminal;retained_capacity;_}->terminal,retained_capacity
      |_->fail "graph" "Machine write does not reach an actual machine bank."in
    let retained=if List.mem write.state terminal then 0 else
      if p.requests=[]then List.length previous.retained_attempts else List.length p.requests in
    require(retained<=capacity) "capacity" "Machine retained-attempt capacity exhausted before atomic commit.")prepared;
  List.iter(fun(write:truth_write)->charge w 1;let s=w.current in
    w.current<-{s with registers=Map.add(cell write.destination write.binding)write.value s.registers};
    action w(State_written write))writes;
  List.concat_map(fun(p:prepared)->
    let started=List.map(fun(_, (request:request))->
    let s=w.current in
    let timeout=match(node s.plan request.bank).model.primitive with I.Attempt_bank{timeout_ticks;_}|I.Attempt_bank_sites{timeout_ticks;_}->timeout_ticks|_->assert false in
    let b=request.activation.binding in
    let slot=match b.slot with Some id->find_slot s id|None->fail "scope" "Attempt cannot collapse an encounter to executor scope."in
    let ordinal=s.allocated+1 in
    let attempt={attempt_id="primitive/attempt/"^string_of_int ordinal;ordinal;bank=request.bank;binding=b;
      executor=s.plan.environment.executor;subject=slot.description.target;gate=request.activation.gate;guard=request.activation.guard;
      causes=request.activation.causes;product=request.product;started_tick=w.now;deadline_tick=w.now+timeout;
      ended_tick=None;status=Active;authorization=I.True;
      machine=Option.map(fun(write:machine_write)->write.destination)p.machine_write}in
    retain w;charge w(List.length s.attempts);
    (* [s] predates the debit; preserve the current work/retention counters. *)
    w.current<-{w.current with allocated=ordinal;attempts=s.attempts@[attempt]};
    w.creations_rev<-attempt::w.creations_rev;
    action w(Effect_requested attempt);
    let requested=emit w ~origin:(endpoint request.bank "events") ~attempt_id:attempt.attempt_id (Primitive_event I.Requested)b in
    let initiated=emit w ~origin:(endpoint request.bank "events") ~attempt_id:attempt.attempt_id (Primitive_event I.Initiated)b in
    attempt,[requested;initiated])p.requests in
    (match p.machine_write with None->()|Some write->
      let old=machine w.current write.destination write.binding in
      let terminal=match(node w.current.plan write.destination).model.primitive with
        |I.Machine_bank{terminal;_}->terminal|_->assert false in
      let retained_attempts=if List.mem write.state terminal then []else
        if started=[]then old.retained_attempts else List.map(fun((attempt:attempt),_)->attempt.attempt_id)started in
      let value:machine_snapshot={bank=write.destination;binding=write.binding;state=write.state;retained_attempts}in
      w.current<-{w.current with machines=Map.add(cell write.destination write.binding)value w.current.machines};
      action w(Machine_transition{bank=write.destination;gate=p.activation.gate;commit=write.commit;
        binding=write.binding;destination=write.state;retained_attempts}));
    List.concat_map snd started)prepared
let signal_cost=function
  |Truth value->List.length value.reasons,100+24*List.length value.reasons
  |Product value->0,100+text_cost value
  |Events values->List.length values,List.fold_left(fun total(event:event)->total+500+text_cost event.event_id+
      binding_cost event.binding+(match event.origin with None->0|Some e->endpoint_cost e))0 values
  |Activations values->List.fold_left(fun total(a:activation)->total+1+List.length a.causes)0 values,
      List.fold_left(fun total a->total+activation_cost a)0 values
  |Writes values->List.length values,List.fold_left(fun total(write:truth_write)->total+300+
      text_cost write.commit+text_cost write.destination+binding_cost write.binding)0 values
  |Requests values->List.fold_left(fun total(request:request)->total+1+List.length request.activation.causes)0 values,
      List.fold_left(fun total(request:request)->total+200+text_cost request.commit+text_cost request.bank+
        activation_cost request.activation+text_cost request.product)0 values
  |Attempts values->List.fold_left(fun total(a:attempt)->total+1+List.length a.causes)0 values,
      List.fold_left(fun total a->total+attempt_cost a)0 values
  |Machine value->List.length value.retained_attempts,machine_cost value
  |Machine_writes values->List.length values,List.fold_left(fun total(write:machine_write)->
      total+200+text_cost write.commit+text_cost write.destination+binding_cost write.binding+text_cost write.state)0 values
let port_inventory w snapshot evaluate events (candidates:activation list) (selected:activation list) (prepared:prepared list) =
  let evaluate_events=event_evaluator w snapshot events in
  List.concat_map(fun(n:I.node)->
    List.concat_map(fun(p:I.port)->if p.direction=I.Input then []else
      List.map(fun b->retain w;
        let e=endpoint n.node_id p.port_id in
        let signal=match p.signal_type with
        |I.Truth_value->Truth(evaluate e b)
        |I.Product_symbol->Product(product snapshot.plan e)
        |I.Event_batch->Events(evaluate_events e b)
        |I.Activation_batch->
            let found=match n.model.primitive with
              |I.Activation_gate|I.Transition_gate _->List.filter(fun(a:activation)->a.gate=n.node_id && a.binding=b)candidates
              |I.Exclusive_arbiter _|I.Priority_arbiter _->List.filter(fun(a:activation)->let c=control snapshot.plan a.gate in
                  c.arbiter=n.node_id && p.port_id="out"^string_of_int c.lane && a.binding=b)selected
              |_->fail "graph" "Activation output has no runtime meaning."in Activations found
        |I.Truth_write->Writes(List.concat_map(fun(prepared:prepared)->List.filter_map(fun(index,(write:truth_write))->
            if write.commit=n.node_id && p.port_id="write"^string_of_int index && write.binding=b then Some write else None)prepared.writes)prepared)
        |I.Effect_request->Requests(List.concat_map(fun(prepared:prepared)->List.filter_map(fun(index,(request:request))->
            if request.commit=n.node_id && p.port_id="request"^string_of_int index && request.activation.binding=b then Some request else None)prepared.requests)prepared)
        |I.Attempt_snapshot->Attempts(List.filter(fun(a:attempt)->a.bank=n.node_id && a.binding=b)snapshot.attempts)
        |I.Machine_snapshot->Machine(machine snapshot n.node_id b)
        |I.Machine_write->Machine_writes(List.filter_map(fun(prepared:prepared)->match prepared.machine_write with
            |Some write when write.commit=n.node_id && write.binding=b->Some write|_->None)prepared)
        |I.Evidence_batch|I.Feedback_batch->fail "graph" "External input cannot appear in semantic output inventory."in
        let count,cost=signal_cost signal in retain_payload w count;reserve_output w(300+endpoint_cost e+binding_cost b+cost);
        {endpoint=e;binding=b;signal})(live_bindings snapshot n)) (I.ports n.model.primitive))snapshot.plan.nodes
let evidence_inventory w (snapshot:state) =
  List.concat_map(fun(n:I.node)->match n.model.primitive with
    |I.Evidence_bank{freshness_ticks}->List.map(fun b->retain w;
        let retained=Map.find_opt(cell n.node_id b)snapshot.evidence in
        let occurrences=match retained with None->[]|Some e->e.occurrences in
        retain_payload w(List.length occurrences);reserve_output w(500+text_cost n.node_id+binding_cost b+texts_cost occurrences);
        {bank=n.node_id;binding=b;signal=evidence_signal w.now freshness_ticks retained;
         observed_tick=Option.map(fun e->e.observed)retained;available_tick=Option.map(fun e->e.available)retained;
         occurrences})(live_bindings snapshot n)
    |_->[])snapshot.plan.nodes
let step ?max_step_work ?max_step_retained (before:state) (batch:input_batch) =
  require(batch.tick=before.next && batch.tick<=before.plan.environment.horizon_ticks) "time" "Runtime requires the next consecutive inclusive clock tick.";
  bounded_list 16 batch.lifecycle;bounded_list 4096 batch.observations;bounded_list 4096 batch.feedback;
  let ceiling requested current maximum=match requested with
    |None->maximum
    |Some delta->require(delta>0 && delta<=maximum) "limit" "Per-step resource deltas must be positive and within the original resource ceiling.";
        current+min delta(maximum-current)in
  let work_ceiling=ceiling max_step_work before.work before.plan.limits.max_work
  and retained_ceiling=ceiling max_step_retained before.retained before.plan.limits.max_events in
  let w={current=before;now=batch.tick;microstep=0;events_rev=[];actions_rev=[];creations_rev=[];
    frame_cost=0;work_ceiling;retained_ceiling}in
  charge w(1+List.length before.plan.nodes+List.length before.slots);
  apply_lifecycle w batch;
  let updates=apply_observations w batch in
  let feedback=apply_feedback w batch in
  let timeouts=apply_timeouts w in
  refresh_authorization w;
  let rising=update_rising w in
  let events=ref(updates@feedback@timeouts@rising)and rounds=ref []and continue=ref true in
  while !continue do
    require(w.microstep<before.plan.limits.max_microsteps) "settling_limit" "Same-tick settling exceeds its explicit finite bound.";
    w.microstep<-w.microstep+1;
    let snapshot=w.current in let evaluate=evaluator w snapshot in
    let values=candidates w snapshot evaluate !events in
    let selected=arbitrate w values in
    let prepared=prepare w snapshot evaluate selected in
    let ports=port_inventory w snapshot evaluate !events values selected prepared in
    retain w;reserve_output w 100;
    rounds:={microstep=w.microstep;ports}:: !rounds;
    let next=commit w prepared in
    refresh_authorization w;events:=next;continue:=next<>[]
  done;
  let snapshot=w.current in let evaluate=evaluator w snapshot in
  let events=List.rev w.events_rev in
  let outputs=port_inventory w snapshot evaluate events [] [] []in
  let evidence=evidence_inventory w snapshot in
  let machines=Map.bindings snapshot.machines|>List.map(fun(_, (value:machine_snapshot))->
    retain w;retain_payload w(List.length value.retained_attempts);reserve_output w(machine_cost value);value)in
  let slots=List.map(fun(s:slot_state)->retain w;reserve_output w(200+text_cost s.description.slot_id);
    {slot_id=s.description.slot_id;generation=s.generation;active=s.active})snapshot.slots in
  List.iter(fun(a:attempt)->retain_payload w(1+List.length a.causes);reserve_output w(attempt_cost a))
    (snapshot.attempts@w.creations_rev);
  reserve_output w 500;
  let result={tick=batch.tick;rounds=List.rev !rounds;outputs;events;actions=List.rev w.actions_rev;
    creations=List.rev w.creations_rev;attempts=snapshot.attempts;evidence;slots;machines;
    execution_profile=execution_profile before.plan.implementation}in
  {w.current with next=before.next+1},result
let creations (value:frame)=value.creations

let str value=Json.String value
let arr values=Json.Array values
let obj values=Json.Object values
let optional encode=function None->Json.Null|Some value->encode value
let truth_name=function I.True->"true"|I.False->"false"|I.Unknown->"unknown"
let reason_name=function Missing->"missing"|Stale->"stale"|Invalid->"invalid"|Conflicting->"conflicting"
let binding_json (value:binding)=obj["slot",optional str value.slot;"generation",Json.int value.generation]
let endpoint_json (value:I.endpoint)=obj["node",str value.node_id;"port",str value.port_id]
let truth_json (value:truth_signal)=obj["value",optional(fun value->str(truth_name value))value.value;
  "reasons",arr(List.map(fun value->str(reason_name value))value.reasons)]
let activation_json (value:activation)=obj["gate",str value.gate;"guard",endpoint_json value.guard;
  "binding",binding_json value.binding;"causes",arr(List.map str value.causes)]
let status_name=function Active->"active"|Completed->"completed"|Failed->"failed"|Timed_out->"timed_out"
  |Reset_invalidated->"encounter_reset"|End_invalidated->"encounter_ended"
let primitive_event_name=function I.Updated->"updated"|I.Rising->"rising"|I.Requested->"requested"
  |I.Initiated->"initiated"|I.Completed->"completed"|I.Failed->"failed"|I.Timed_out->"timed_out"
let event_json (value:event)=obj["id",str value.event_id;"origin",optional endpoint_json value.origin;
  "kind",str(match value.kind with Primitive_event kind->primitive_event_name kind|Encounter_started->"encounter_started"
    |Encounter_reset->"encounter_reset"|Encounter_ended->"encounter_ended"|Attempt_reset->"attempt_reset"|Attempt_ended->"attempt_ended");
  "binding",binding_json value.binding;"attempt",optional str value.attempt_id;"tick",Json.int value.tick;"microstep",Json.int value.microstep]
let attempt_json (value:attempt)=obj(["id",str value.attempt_id;"ordinal",Json.int value.ordinal;"bank",str value.bank;
  "binding",binding_json value.binding;"executor",str value.executor;"subject",str value.subject;
  "gate",str value.gate;"guard",endpoint_json value.guard;"causes",arr(List.map str value.causes);"product",str value.product;
  "started_tick",Json.int value.started_tick;"deadline_tick",Json.int value.deadline_tick;
  "ended_tick",optional Json.int value.ended_tick;"status",str(status_name value.status);"authorization",str(truth_name value.authorization)]@
  (match value.machine with None->[]|Some bank->["machine",str bank]))
let write_json (value:truth_write)=obj["commit",str value.commit;"destination",str value.destination;
  "binding",binding_json value.binding;"value",str(truth_name value.value)]
let request_json (value:request)=obj["commit",str value.commit;"bank",str value.bank;
  "activation",activation_json value.activation;"product",str value.product]
let machine_json (value:machine_snapshot)=obj["bank",str value.bank;"binding",binding_json value.binding;
  "state",str value.state;"retained_attempts",arr(List.map str value.retained_attempts)]
let machine_write_json (value:machine_write)=obj["commit",str value.commit;"destination",str value.destination;
  "binding",binding_json value.binding;"state",str value.state]
let signal_json=function
  |Truth value->obj["kind",str "truth";"data",truth_json value]
  |Product value->obj["kind",str "product";"data",str value]
  |Events values->obj["kind",str "events";"data",arr(List.map event_json values)]
  |Activations values->obj["kind",str "activations";"data",arr(List.map activation_json values)]
  |Writes values->obj["kind",str "writes";"data",arr(List.map write_json values)]
  |Requests values->obj["kind",str "requests";"data",arr(List.map request_json values)]
  |Attempts values->obj["kind",str "attempts";"data",arr(List.map attempt_json values)]
  |Machine value->obj["kind",str "machine";"data",machine_json value]
  |Machine_writes values->obj["kind",str "machine_writes";"data",arr(List.map machine_write_json values)]
let port_json (value:port_value)=obj["endpoint",endpoint_json value.endpoint;"binding",binding_json value.binding;"signal",signal_json value.signal]
let evidence_json (value:evidence_snapshot)=obj["bank",str value.bank;"binding",binding_json value.binding;
  "signal",truth_json value.signal;"observed_tick",optional Json.int value.observed_tick;
  "available_tick",optional Json.int value.available_tick;"occurrences",arr(List.map str value.occurrences)]
let action_kind_json=function
  |Deferred(a,reasons)->obj["kind",str "activation_deferred";"activation",activation_json a;"reasons",arr(List.map(fun reason->str(reason_name reason))reasons)]
  |Undefined_commit a->obj["kind",str "undefined_commit";"activation",activation_json a]
  |Suppressed(a,selected)->obj["kind",str "arbitration_suppressed";"activation",activation_json a;"selected",str selected]
  |Authorization_changed(id,value,reasons,response)->obj["kind",str "authorization_changed";"attempt",str id;
      "authorization",str(truth_name value);"reasons",arr(List.map(fun reason->str(reason_name reason))reasons);"response",str response]
  |Feedback_accepted(id,attempt)->obj["kind",str "feedback_accepted";"id",str id;"attempt",str attempt]
  |Feedback_rejected(id,attempt,reason)->obj["kind",str "feedback_rejected";"id",str id;"attempt",str attempt;"reason",str reason]
  |Observation_batch{bank;binding;input_ids;retained_ids;evidence;observed_tick}->obj[
      "kind",str "observation_batch";"bank",str bank;"binding",binding_json binding;
      "input_ids",arr(List.map str input_ids);"retained_ids",arr(List.map str retained_ids);
      "status",str(match evidence with Known _->"valid"|Missing_evidence->"missing"|Invalid_evidence->"invalid"|Conflicting_evidence->"conflicting");
      "observed_tick",Json.int observed_tick]
  |State_written value->obj["kind",str "state_written";"write",write_json value]
  |Effect_requested value->obj["kind",str "effect_requested";"attempt",attempt_json value]
  |Machine_transition value->obj["kind",str "machine_transition";"bank",str value.bank;
      "gate",str value.gate;"commit",str value.commit;"binding",binding_json value.binding;
      "destination",str value.destination;"retained_attempts",arr(List.map str value.retained_attempts)]
let action_json (value:action)=obj["microstep",Json.int value.microstep;"detail",action_kind_json value.detail]
let frame_to_json (value:frame)=obj(["profile",str value.execution_profile;"claim",str "actual_primitive_graph_only";"tick",Json.int value.tick;
  "rounds",arr(List.map(fun(round:round)->obj["microstep",Json.int round.microstep;"ports",arr(List.map port_json round.ports)])value.rounds);
  "outputs",arr(List.map port_json value.outputs);"events",arr(List.map event_json value.events);
  "actions",arr(List.map action_json value.actions);"creations",arr(List.map attempt_json value.creations);
  "attempts",arr(List.map attempt_json value.attempts);"evidence",arr(List.map evidence_json value.evidence);
  "slots",arr(List.map(fun(slot:slot_snapshot)->obj["id",str slot.slot_id;"generation",Json.int slot.generation;"active",Json.Bool slot.active])value.slots)]@
  (if value.execution_profile=staged_execution_profile then ["machines",arr(List.map machine_json value.machines)]else []))
let retained_json (value:retained_evidence)=obj["observed",Json.int value.observed;"available",Json.int value.available;
  "evidence",(match value.evidence with Known value->Json.Bool value|Missing_evidence->str "missing"|Invalid_evidence->str "invalid"|Conflicting_evidence->str "conflicting");
  "occurrences",arr(List.map str value.occurrences)]
let state_fingerprint (value:state)=
  let environment=value.plan.environment and limits=value.plan.limits in
  let map encode values=obj(List.map(fun(key,value)->key,encode value)(Map.bindings values))in
  let raw=obj(["profile",str(execution_profile value.plan.implementation);"graph_digest",str(I.fingerprint value.plan.implementation);
    "environment",obj["executor",str environment.executor;"horizon_ticks",Json.int environment.horizon_ticks;
      "slots",arr(List.map(fun(slot:concrete_slot)->obj["id",str slot.slot_id;"target",str slot.target;"start_tick",Json.int slot.start_tick])environment.slots)];
    "limits",obj["max_work",Json.int limits.max_work;"max_events",Json.int limits.max_events;
      "max_attempts",Json.int limits.max_attempts;"max_microsteps",Json.int limits.max_microsteps];
    "next",Json.int value.next;"sequence",Json.int value.sequence;"allocated",Json.int value.allocated;
    "work",Json.int value.work;"retained",Json.int value.retained;
    "slots",arr(List.map(fun(slot:slot_state)->obj["id",str slot.description.slot_id;"generation",Json.int slot.generation;
      "active",Json.Bool slot.active;"generation_start",Json.int slot.generation_start])value.slots);
    "registers",map(fun value->str(truth_name value))value.registers;"evidence",map retained_json value.evidence;
    "rising",map(fun value->str(truth_name value))value.rising;"attempts",arr(List.map attempt_json value.attempts);
    "observation_ids",arr(List.map str(Set.elements value.observation_ids));"feedback_ids",arr(List.map str(Set.elements value.feedback_ids))]@
    (if List.mem(I.implementation_profile value.plan.implementation)[I.staged_profile;I.multi_site_profile] then
      ["machines",map machine_json value.machines]else []))in
  Canonical.sha256(Canonical.encode_bounded ~max_bytes:(8*1024*1024)raw)

(* Successful deterministic transitions are private witnesses, not acceptance.
   Keep this closed record destructuring exhaustive: a new future-read field
   must invalidate the equality/preflight audit at compilation (warning 9). *)
type transition_witness = { predecessor : string; successor : state;
  observed : frame }
type transition_session = { owner : plan; mutable witnesses : transition_witness list;
  mutable requests : int; mutable evaluations : int; mutable reuses : int;
  mutable bypasses : int; mutable proof_work : int; mutable resident_bytes : int;
  mutable peak_bytes : int }
type transition_usage = { requests : int; evaluations : int; reuses : int;
  bypasses : int; proof_work : int; peak_bytes : int; current_entries : int }
let transition_entry_limit = 32
let transition_byte_limit = 8 * 1024 * 1024
let transition_work_limit = 64 * 1024 * 1024
let transition_key_limit = 1024 * 1024
exception Transition_proof_bound
let create_transition_session (initial:state) =
  {owner=initial.plan;witnesses=[];requests=0;evaluations=0;reuses=0;
   bypasses=0;proof_work=0;resident_bytes=0;peak_bytes=0}
let transition_usage (session:transition_session) : transition_usage =
  {requests=session.requests;evaluations=session.evaluations;reuses=session.reuses;
   bypasses=session.bypasses;proof_work=session.proof_work;peak_bytes=session.peak_bytes;
   current_entries=List.length session.witnesses}
let proof_spend (session:transition_session) amount =
  if amount<0 || amount>transition_work_limit-session.proof_work then (
    session.proof_work<-transition_work_limit;raise Transition_proof_bound);
  session.proof_work<-session.proof_work+amount
let proof_option f = function None->()|Some value->f value
let proof_iter (session:transition_session) f values = List.iter(fun value->proof_spend session 8;f value)values
let proof_text (session:transition_session) value = proof_spend session (8+6*String.length value)
let proof_binding (session:transition_session) ({slot;generation}:binding) =
  proof_spend session 128;proof_option(proof_text session)slot;ignore generation
let proof_endpoint (session:transition_session) ({node_id;port_id}:I.endpoint) =
  proof_spend session 128;proof_text session node_id;proof_text session port_id
let proof_machine (session:transition_session) ({bank;binding;state;retained_attempts}:machine_snapshot) =
  proof_spend session 256;proof_text session bank;proof_binding session binding;
  proof_text session state;proof_iter session (proof_text session) retained_attempts
let proof_attempt (session:transition_session) ({attempt_id;ordinal;bank;binding;executor;subject;gate;guard;
    causes;product;started_tick;deadline_tick;ended_tick;status;authorization;machine}:attempt) =
  proof_spend session 1024;
  List.iter(proof_text session)[attempt_id;bank;executor;subject;gate;product];
  proof_binding session binding;proof_endpoint session guard;
  proof_iter session (proof_text session) causes;proof_option(proof_text session)machine;
  ignore(ordinal,started_tick,deadline_tick,ended_tick,status,authorization)
let proof_state (session:transition_session) (value:state) =
  let {plan;next;slots;registers;evidence;rising;machines;attempts;sequence;allocated;
    work;retained;observation_ids;feedback_ids}=value in
  proof_spend session 1024;ignore(plan,next,sequence,allocated,work,retained);
  proof_iter session (fun ({description;generation;active;generation_start}:slot_state)->
    let {slot_id;target;start_tick}=description in
    proof_spend session 512;proof_text session slot_id;proof_text session target;
    ignore(start_tick,generation,active,generation_start))slots;
  let map f values=Map.iter(fun key value->proof_spend session 8;proof_text session key;f value)values in
  map(fun value->proof_spend session 32;ignore value)registers;
  map(fun ({observed;available;evidence;occurrences}:retained_evidence)->
    proof_spend session 256;ignore(observed,available,evidence);
    proof_iter session(proof_text session)occurrences)evidence;
  map(fun value->proof_spend session 32;ignore value)rising;
  map(proof_machine session)machines;
  proof_iter session(proof_attempt session)attempts;
  Set.iter(fun value->proof_spend session 8;proof_text session value)observation_ids;
  Set.iter(fun value->proof_spend session 8;proof_text session value)feedback_ids
let proof_batch (session:transition_session) ({tick;lifecycle;observations;feedback}:input_batch) =
  proof_spend session 256;ignore tick;
  proof_iter session(fun(slot,action)->proof_text session slot;proof_spend session 32;ignore action)lifecycle;
  proof_iter session(fun({observation_id;input_id;slot_id;observed_tick;observer;subject;evidence}:observation)->
    proof_spend session 512;List.iter(proof_text session)[observation_id;input_id;slot_id;observer;subject];
    ignore(observed_tick,evidence))observations;
  proof_iter session(fun({feedback_id;input_id;attempt_id;executor;subject;slot_id;outcome}:feedback)->
    proof_spend session 512;List.iter(proof_text session)[feedback_id;input_id;attempt_id;executor;subject;slot_id];
    ignore outcome)feedback
let transition_state_json (value:state) =
  let {plan;next;slots;registers;evidence;rising;machines;attempts;sequence;allocated;
    work;retained;observation_ids;feedback_ids}=value in
  (* Plan equality is physical ownership, not a graph digest. Include machines
     even in an unstaged state; no profile-conditioned field may hide data. *)
  ignore plan;
  let map encode values=obj(List.map(fun(key,value)->key,encode value)(Map.bindings values))in
  obj["next",Json.int next;"sequence",Json.int sequence;"allocated",Json.int allocated;
    "work",Json.int work;"retained",Json.int retained;
    "slots",arr(List.map(fun({description;generation;active;generation_start}:slot_state)->
      let {slot_id;target;start_tick}=description in
      obj["id",str slot_id;"target",str target;"start",Json.int start_tick;
        "generation",Json.int generation;"active",Json.Bool active;"generation_start",Json.int generation_start])slots);
    "registers",map(fun value->str(truth_name value))registers;"evidence",map retained_json evidence;
    "rising",map(fun value->str(truth_name value))rising;"machines",map machine_json machines;
    "attempts",arr(List.map attempt_json attempts);
    "observation_ids",arr(List.map str(Set.elements observation_ids));
    "feedback_ids",arr(List.map str(Set.elements feedback_ids))]
let transition_batch_json ({tick;lifecycle;observations;feedback}:input_batch) =
  let evidence_json = function Known value->obj["known",Json.Bool value]
    |Missing_evidence->str "missing"|Invalid_evidence->str "invalid"|Conflicting_evidence->str "conflicting"in
  obj["tick",Json.int tick;
    "lifecycle",arr(List.map(fun(slot,action)->arr[str slot;str(match action with Reset->"reset"|End->"end")])lifecycle);
    "observations",arr(List.map(fun({observation_id;input_id;slot_id;observed_tick;observer;subject;evidence}:observation)->
      obj["id",str observation_id;"input",str input_id;"slot",str slot_id;"observed",Json.int observed_tick;
        "observer",str observer;"subject",str subject;"evidence",evidence_json evidence])observations);
    "feedback",arr(List.map(fun({feedback_id;input_id;attempt_id;executor;subject;slot_id;outcome}:feedback)->
      obj["id",str feedback_id;"input",str input_id;"attempt",str attempt_id;"executor",str executor;
        "subject",str subject;"slot",str slot_id;"outcome",str(match outcome with Complete->"complete"|Fail->"fail")])feedback)]
let proof_encode (session:transition_session) maximum value =
  let remaining=transition_work_limit-session.proof_work in
  if remaining<=0 || maximum<=0 then raise Transition_proof_bound;
  let ceiling=min maximum remaining in
  match Canonical.encode_bounded ~max_bytes:ceiling value with
  | bytes->proof_spend session(String.length bytes);bytes
  | exception Diagnostic.Error _->proof_spend session ceiling;raise Transition_proof_bound
let proof_key (session:transition_session) max_step_work max_step_retained state batch =
  let start=session.proof_work in
  proof_state session state;proof_batch session batch;proof_spend session 256;
  if session.proof_work-start>transition_key_limit then raise Transition_proof_bound;
  proof_encode session transition_key_limit
    (obj["state",transition_state_json state;"batch",transition_batch_json batch;
      "max_step_work",optional Json.int max_step_work;"max_step_retained",optional Json.int max_step_retained])
let step_with_transition_session (session:transition_session) ?max_step_work ?max_step_retained before batch =
  session.requests<-session.requests+1;
  let fresh ()=session.evaluations<-session.evaluations+1;
    step ?max_step_work ?max_step_retained before batch in
  let bypass ()=session.bypasses<-session.bypasses+1;fresh()in
  if before.plan != session.owner || session.proof_work>=transition_work_limit then bypass()else
  let key=try Some(proof_key session max_step_work max_step_retained before batch)
    with Transition_proof_bound->None in
  match key with None->bypass()|Some key->
    let found=try
      Some(List.find_opt(fun witness->
        proof_spend session(max(String.length key)(String.length witness.predecessor));
        String.equal key witness.predecessor)session.witnesses)
      with Transition_proof_bound->None in
    match found with None->bypass()|Some(Some witness)->
      session.reuses<-session.reuses+1;witness.successor,witness.observed
    |Some None->
      let after,frame=fresh()in
      if List.length session.witnesses>=transition_entry_limit then session.bypasses<-session.bypasses+1
      else (try
        (* P.step's conservative output charge bounds construction of the
           frame JSON before encoding. State construction has its own typed
           structural/string preflight, independent of any claimed digest. *)
        let start=session.proof_work in proof_state session after;
        if session.proof_work-start>transition_key_limit then raise Transition_proof_bound;
        let successor=proof_encode session transition_key_limit(transition_state_json after)in
        proof_spend session(after.work-before.work);
        let observation=proof_encode session transition_byte_limit(frame_to_json frame)in
        let footprint=256+String.length key+String.length successor+String.length observation in
        if footprint>transition_byte_limit-session.resident_bytes then raise Transition_proof_bound;
        session.witnesses<-session.witnesses@[{predecessor=key;successor=after;observed=frame}];
        session.resident_bytes<-session.resident_bytes+footprint;
        session.peak_bytes<-max session.peak_bytes session.resident_bytes
      with Transition_proof_bound->session.bypasses<-session.bypasses+1);
      after,frame
