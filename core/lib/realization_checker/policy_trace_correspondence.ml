open Bioc_wire
module F = Bioc_domain.Policy_operating_domain
module O = Bioc_domain.Policy_operational
module I = Bioc_domain.Policy_implementation
module P = Bioc_candidate_runtime.Policy_primitives
module B = Bioc_checker.Policy_implementation_binding_check
module A = Bioc_checker.Policy_realization_admission

let profile = "biocompiler.policy_exact_trace_correspondence.v0.1"
let str x = Json.String x
let arr x = Json.Array x
let obj x = Json.Object x
let get name value = Json.field name (Json.object_fields value)
let text name value = Json.string (get name value)
let items name value = Json.array (get name value)
let optional encode = function None -> Json.Null | Some x -> encode x
let require condition message = Diagnostic.require condition "policy_trace_correspondence" message
let same name expected actual = require (Json.equal expected actual) ("Observable mismatch: " ^ name)
let find name predicate values = match List.find_opt predicate values with
  | Some value -> value
  | None -> Diagnostic.fail "policy_trace_correspondence" ("Unmapped observable " ^ name)
let truth = function I.True -> "true" | I.False -> "false" | I.Unknown -> "unknown"
let truth_value = function I.True -> Json.Bool true | I.False -> Json.Bool false | I.Unknown -> str "unknown"
let reason = function P.Missing -> "missing" | P.Stale -> "stale" | P.Invalid -> "invalid" | P.Conflicting -> "conflicting"
let binding (value:P.binding) = obj ["encounter",optional str value.slot; "generation",Json.int value.generation]
let status = function P.Active -> "active" | P.Completed -> "completed" | P.Failed -> "failed"
  | P.Timed_out -> "timed_out" | P.Reset_invalidated -> "encounter_reset" | P.End_invalidated -> "encounter_ended"
let rec expression_key (value:O.expression) =
  Canonical.encode (obj ["op",str value.op; "reference",optional str value.reference;
    "value",optional O.value_to_json value.value; "scope",optional str value.scope;
    "phase",optional str value.phase]) ^ "(" ^ String.concat "," (List.map expression_key value.args) ^ ")"
type t = { checked:B.checked_binding; domain:F.validated; cursor:F.cursor; next:int;
  attempts:(string * string) list; events:(string * string) list;
  slots:P.slot_snapshot list; history_digest:string }
let create checked =
  let domain=A.operating_domain (B.admitted_inputs checked) in
  {checked; domain; cursor=F.initial domain;
  next=0; attempts=[]; events=[];
  slots=List.map(fun(slot:B.slot)->{P.slot_id=slot.identity;generation=0;active=false})(B.environment checked).slots;
  history_digest=Canonical.fingerprint(obj["profile",str profile;"binding",B.report checked])}
let original state = F.specification state.domain
let time state tick = Bioc_semantics.Policy_execution.time_json
  (Q.mul (F.resolution state.domain) (Q.of_int tick))
let lookup name pairs key = match List.assoc_opt key pairs with
  | Some value -> value
  | None -> Diagnostic.fail "policy_trace_correspondence" ("No prior " ^ name ^ " identity correspondence: " ^ key)
let source_attempt state = lookup "attempt" state.attempts
let source_event state = lookup "event" state.events
let candidate_attempt state source = lookup "feedback attempt" (List.map (fun (a,b)->b,a) state.attempts) source
let observation_by_source state id = find "source observation" (fun (x:B.observation)->x.source=id) (B.observations state.checked)
let observation_by_bank state id = find "observation bank" (fun (x:B.observation)->x.bank=id) (B.observations state.checked)
let effect_by_source state id = find "source effect" (fun (x:B.effect_binding)->x.source=id) (B.effects state.checked)
let effect_by_bank state id = find "effect bank" (fun (x:B.effect_binding)->x.bank=id) (B.effects state.checked)
let rule_by_gate state id = find "activation gate" (fun (x:B.rule)->x.gate=id) (B.rules state.checked)
let store_by_register state id = find "truth register" (fun (x:B.state)->x.register=id) (B.states state.checked)
let slot state id = find "encounter slot" (fun (x:F.encounter)->x.identity=id) (original state).encounters
let occurrence kind tick index = "domain/" ^ kind ^ "/" ^ string_of_int tick ^ "/" ^ string_of_int index
let input state (batch:F.input_batch) : P.input_batch =
  require (batch.tick=state.next && batch.tick<=(original state).horizon_ticks &&
    batch.origin=F.cursor_digest state.cursor) "Input is not from this exact causal domain prefix.";
  let observations = List.mapi (fun index (row:F.observation_input) ->
    let mapped=observation_by_source state row.observation in
    {P.observation_id=occurrence "observation" batch.tick index; input_id=mapped.input;
     slot_id=row.slot; observed_tick=row.observed_tick; observer=(original state).executor_identity;
     subject=(slot state row.slot).target; evidence=(match row.evidence with
       | F.Known value -> P.Known value | F.Missing -> P.Missing_evidence
       | F.Invalid -> P.Invalid_evidence | F.Conflicting -> P.Conflicting_evidence)}) batch.observations in
  let feedback = List.mapi (fun index (row:F.feedback_input) ->
    let mapped=effect_by_source state row.attempt.key.effect_id in
    let id=match row.attempt.key.context with F.Encounter_slot id->id
      | F.Executor -> Diagnostic.fail "policy_trace_correspondence" "Executor feedback is outside the bound encounter profile." in
    {P.feedback_id=occurrence "feedback" batch.tick index; input_id=mapped.feedback;
     attempt_id=candidate_attempt state row.attempt.source_attempt_id;
     executor=(original state).executor_identity; subject=(slot state id).target; slot_id=id;
     outcome=(match row.outcome with F.Completed -> P.Complete | F.Failed -> P.Fail)}) batch.feedback in
  {P.tick=batch.tick; lifecycle=List.filter_map (fun (id,action)->match action with
    | F.Keep->None | F.Reset->Some(id,P.Reset) | F.End->Some(id,P.End)) batch.lifecycle;
   observations; feedback}
let extend name pairs additions =
  List.fold_left (fun values (candidate,source)->
    require (not (List.mem_assoc candidate values) && not (List.exists (fun (_,id)->id=source) values))
      ("Reused or collapsed " ^ name ^ " identity."); values@[candidate,source]) pairs additions
let zip name first second =
  require (List.length first=List.length second) ("Observable multiplicity differs: " ^ name);
  List.combine first second
let event_kind = function
  | P.Primitive_event I.Updated -> "updated" | P.Primitive_event I.Rising -> "rising"
  | P.Primitive_event I.Requested -> "requested" | P.Primitive_event I.Initiated -> "initiated"
  | P.Primitive_event I.Completed -> "completed" | P.Primitive_event I.Failed -> "failed"
  | P.Primitive_event I.Timed_out -> "timed_out" | P.Encounter_started -> "encounter_started"
  | P.Encounter_reset | P.Attempt_reset -> "encounter_reset"
  | P.Encounter_ended | P.Attempt_ended -> "encounter_ended"
let event_declaration state (event:P.event) =
  let endpoint () = match event.origin with Some endpoint -> endpoint
    | None -> Diagnostic.fail "policy_trace_correspondence" "Primitive event lacks its actual origin." in
  match event.kind with
  | P.Encounter_started | P.Encounter_reset | P.Encounter_ended ->
      require (event.origin=None && event.attempt_id=None) "Encounter event has a primitive/attempt origin.";
      (I.slot_layout (B.implementation state.checked)).encounter_id
  | P.Primitive_event I.Updated -> let origin=endpoint () in
      require (origin.port_id="updated" && event.attempt_id=None) "Observation event endpoint or attempt differs.";
      (observation_by_bank state origin.node_id).source
  | P.Primitive_event I.Rising -> let origin=endpoint () in
      require (event.attempt_id=None) "Rising event gained an attempt identity.";
      let rule=find "rising edge" (fun (rule:B.rule)->rule.trigger=origin) (B.rules state.checked) in
      expression_key rule.source_trigger
  | P.Primitive_event _ | P.Attempt_reset | P.Attempt_ended -> let origin=endpoint () in
      require (origin.port_id="events" && Option.is_some event.attempt_id) "Effect event endpoint or attempt differs.";
      (effect_by_bank state origin.node_id).source
let event_json state tick (event:P.event) =
  require (event.tick=tick) "Event timestamp differs from its frame.";
  obj ["id",str (source_event state event.event_id); "kind",str (event_kind event.kind);
    "declaration",str (event_declaration state event); "binding",binding event.binding;
    "attempt",optional (fun id->str(source_attempt state id)) event.attempt_id; "microstep",Json.int event.microstep]
let attempt_json state (attempt:P.attempt) =
  let effect_binding=effect_by_bank state attempt.bank and rule=rule_by_gate state attempt.gate in
  require (attempt.gate=effect_binding.gate && attempt.guard=effect_binding.guard && rule.source=effect_binding.initiating_rule)
    "Attempt guard/initiator differs from checked source binding.";
  obj ["id",str (source_attempt state attempt.attempt_id); "effect",str effect_binding.source;
    "executor",str attempt.executor; "subject",str attempt.subject; "binding",binding attempt.binding;
    "initiator",str rule.source; "causes",arr(List.map(fun id->str(source_event state id))attempt.causes);
    "parameters",obj[effect_binding.product_parameter,str attempt.product]; "started_at",time state attempt.started_tick;
    "deadline",time state attempt.deadline_tick; "ended_at",optional (time state) attempt.ended_tick;
    "status",str(status attempt.status); "authorization",str(truth attempt.authorization); "machine",Json.Null]
let action_json state (action:P.action) =
  let kind,detail=match action.detail with
  | P.Deferred (activation,reasons) -> "activation_deferred",obj[
      "declaration",str ((rule_by_gate state activation.gate).source); "binding",binding activation.binding;
      "reasons",arr(List.map(fun value->str(reason value))reasons)]
  | P.Undefined_commit activation -> "activation_deferred",obj[
      "declaration",str ((rule_by_gate state activation.gate).source); "binding",binding activation.binding;
      "reasons",arr[str "unknown_assignment_or_parameter"]]
  | P.Suppressed (activation,selected) -> "arbitration_suppressed",obj[
      "declaration",str ((rule_by_gate state activation.gate).source); "selected",str ((rule_by_gate state selected).source);
      "binding",binding activation.binding]
  | P.Authorization_changed (id,value,reasons,response) -> "authorization_changed",obj[
      "attempt",str(source_attempt state id); "authorization",str(truth value);
      "reasons",arr(List.map(fun value->str(reason value))reasons); "lifecycle_response",str response]
  | P.Feedback_accepted (id,attempt) -> "feedback_accepted",obj[
      "id",str id; "attempt",str(source_attempt state attempt)]
  | P.Feedback_rejected (id,attempt,reason) -> "feedback_rejected",obj[
      "id",str id; "attempt",str(source_attempt state attempt); "reason",str reason]
  | P.Observation_batch batch -> "observation_batch",obj[
      "observation",str ((observation_by_bank state batch.bank).source); "binding",binding batch.binding;
      "occurrences",arr(List.map str batch.input_ids); "retained_occurrences",arr(List.map str batch.retained_ids);
      "status",str(match batch.evidence with P.Known _->"valid"|P.Missing_evidence->"missing"
        |P.Invalid_evidence->"invalid"|P.Conflicting_evidence->"conflicting"); "observed_at",time state batch.observed_tick]
  | P.State_written write -> "state_written",obj[
      "state",str ((store_by_register state write.destination).source); "binding",binding write.binding;
      "value",truth_value write.value]
  | P.Effect_requested attempt -> let projected=attempt_json state attempt in
      "effect_requested",obj(List.map(fun key->key,get key projected)
        ["effect";"initiator";"binding";"subject";"causes";"parameters"] @ ["attempt",get "id" projected]) in
  obj["kind",str kind; "microstep",Json.int action.microstep; "detail",detail]
let source_actions frame =
  List.filter(fun row -> match text "kind" row with
    | "requirement_response" | "requirement_deadline" -> false
    | "observation_batch" | "feedback_accepted" | "feedback_rejected" | "authorization_changed"
    | "activation_deferred" | "arbitration_suppressed" | "state_written" | "effect_requested" -> true
    | other -> Diagnostic.fail "policy_trace_correspondence" ("Source action outside fixed observable profile: " ^ other))
    (items "actions" frame)
let evidence_json state (value:P.evidence_snapshot) =
  obj["observation",str ((observation_by_bank state value.bank).source); "binding",binding value.binding;
    "status",str(match value.signal.reasons with []->"valid"|first::_->reason first);
    "value",optional truth_value value.signal.value; "observed_at",optional(time state)value.observed_tick;
    "available_at",optional(time state)value.available_tick; "occurrences",arr(List.map str value.occurrences)]
let state_rows state (candidate:P.frame) =
  List.concat_map(fun(store:B.state)->List.filter_map(fun(port:P.port_value)->
    if port.endpoint.node_id<>store.register || port.endpoint.port_id<>"value" then None else
    let value=match port.signal with P.Truth {value=Some value;reasons=[]}->value
      | _->Diagnostic.fail "policy_trace_correspondence" "Settled truth register is undefined or carries evidence reasons." in
    Some(store.source,port.binding,obj["state",str store.source;"binding",binding port.binding;"value",truth_value value]))candidate.outputs)
    (B.states state.checked)
  |> List.sort(fun(a,b,_)(c,d,_)->compare(a,b)(c,d)) |> List.map(fun(_,_,row)->row)
let advance state ~(batch:F.input_batch) ~source_frame ~source_attempts ~source_creations ~(candidate:P.frame) =
  require (candidate.tick=state.next && batch.tick=state.next && batch.tick<=(original state).horizon_ticks &&
    batch.origin=F.cursor_digest state.cursor) "Executions do not share this exact causal domain prefix.";
  Json.exact_fields ["time";"microsteps";"events";"actions";"states";"machines";"evidence";"active_attempts"]
    (Json.object_fields source_frame);
  same "timestamp" (time state candidate.tick) (get "time" source_frame);
  same "unsupported machines" (arr []) (get "machines" source_frame);
  List.iteri(fun index(round:P.round)->require(round.microstep=index+1) "Candidate rounds are not consecutive.")candidate.rounds;
  same "settling steps" (Json.int(List.length candidate.rounds)) (get "microsteps" source_frame);
  let expected_slots=List.map(fun(previous:P.slot_snapshot)->
    let description=slot state previous.slot_id in
    let active=previous.active || description.start_tick=batch.tick in
    match List.assoc previous.slot_id batch.lifecycle with
    | F.Keep->{previous with active}
    | F.Reset->{previous with active;generation=previous.generation+1}
    | F.End->{previous with active=false})state.slots in
  require(candidate.slots=expected_slots) "Concrete encounter activity/generation differs.";
  let added=List.mapi(fun index ((created:F.source_creation),(actual:P.attempt))->
    let context=match created.key.context with F.Executor->None|F.Encounter_slot id->Some id in
    require (created.created_tick=candidate.tick && actual.started_tick=candidate.tick &&
      actual.ordinal=created.key.creation_ordinal && created.key.creation_ordinal=List.length state.attempts+index+1 &&
      actual.binding.slot=context && actual.binding.generation=created.key.generation &&
      (effect_by_bank state actual.bank).source=created.key.effect_id) "Creation identity/order/scope/time differs.";
    actual.attempt_id,created.source_attempt_id) (zip "creations" source_creations candidate.creations) in
  let state={state with attempts=extend "attempt" state.attempts added} in
  require (List.length source_attempts=List.length state.attempts && List.length candidate.attempts=List.length state.attempts)
    "A retained attempt was lost, duplicated or introduced without a matched creation.";
  List.iteri(fun index(attempt:P.attempt)->require(attempt.ordinal=index+1)
    "Retained attempt creation order changed.")candidate.attempts;
  let immutable(attempt:P.attempt)={attempt with status=P.Active;authorization=I.True;ended_tick=None} in
  List.iter(fun(created:P.attempt)->
    let retained=find "created attempt ledger row" (fun(attempt:P.attempt)->attempt.attempt_id=created.attempt_id)candidate.attempts in
    require(created.status=P.Active && created.authorization=I.True && created.ended_tick=None &&
      immutable created=immutable retained) "Creation metadata disagrees with its retained attempt ledger.")candidate.creations;
  let event_pairs=zip "events" (items "events" source_frame) candidate.events in
  let state={state with events=extend "event" state.events (List.map(fun(source,(actual:P.event))->actual.event_id,text "id" source)event_pairs)} in
  List.iter(fun(source,actual)->same "event" source (event_json state candidate.tick actual))event_pairs;
  List.iter(fun(source,actual)->same "attempt" source (attempt_json state actual)) (zip "attempt ledger" source_attempts candidate.attempts);
  same "ordered actions" (arr(source_actions source_frame)) (arr(List.map(action_json state)candidate.actions));
  same "settled scoped state" (get "states" source_frame) (arr(state_rows state candidate));
  same "settled evidence" (get "evidence" source_frame) (arr(List.map(evidence_json state)candidate.evidence));
  same "active attempts" (get "active_attempts" source_frame) (arr(List.filter_map(fun(actual:P.attempt)->
    if actual.status=P.Active then Some(str(source_attempt state actual.attempt_id))else None)candidate.attempts));
  let history_digest=Canonical.fingerprint(obj["previous",str state.history_digest;
    "input",F.batch_to_json batch; "source_frame",source_frame; "source_attempts",arr source_attempts;
    "candidate_frame",P.frame_to_json candidate]) in
  let cursor=F.advance state.domain state.cursor batch ~source_creations in
  {state with next=state.next+1;slots=expected_slots;history_digest;cursor}
let report state = obj["profile",str profile; "claim",str "matched_prefix_only";
  "binding",B.report state.checked; "next_tick",Json.int state.next; "history_digest",str state.history_digest;
  "domain_cursor",str(F.cursor_digest state.cursor);
  "attempts",arr(List.map(fun(candidate,source)->obj["candidate",str candidate;"source",str source])state.attempts);
  "events",arr(List.map(fun(candidate,source)->obj["candidate",str candidate;"source",str source])state.events);
  "requirements",str "unassessed"; "whole_domain",str "unassessed"; "material",str "unassessed"; "export",str "withheld"]
let candidate_event_to_source = source_event
let candidate_attempt_to_source = source_attempt
let identity state = obj["profile",str profile;"history_digest",str state.history_digest;
  "domain_cursor",str(F.cursor_digest state.cursor);"next_tick",Json.int state.next;
  "attempts",arr(List.map(fun(candidate,source)->arr[str candidate;str source])state.attempts);
  "events",arr(List.map(fun(candidate,source)->arr[str candidate;str source])state.events)]
let fingerprint state = Canonical.fingerprint(identity state)
