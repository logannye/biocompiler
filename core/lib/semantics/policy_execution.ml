open Bioc_wire
module O = Bioc_domain.Policy_operational
module D = Bioc_domain.Policy_document

let schema_version = "biocompiler.policy_execution.v0.1"
let timeline_profile = "biocompiler.policy_timeline.v0.1"
let require = Diagnostic.require
let fail = Diagnostic.fail
let str x = Json.String x
let arr x = Json.Array x
let obj x = Json.Object x
let nullable f = function None -> Json.Null | Some x -> f x
let field key value = Json.field key (Json.object_fields value)
let text key value = Json.string (field key value)
let items key value = Json.array (field key value)
let fields names value = Json.exact_fields names (Json.object_fields value)
let optional_text = function Json.Null -> None | x -> Some (Json.name x)
let name key value = Json.name (field key value)
let exact value = D.exact_decimal (Json.string value)
let time_json q =
  (* Times originate in finite decimal source/input fields and only receive
     integer multiplication/addition; this path never rounds through floats. *)
  let numerator = Q.num q and denominator = Q.den q in
  let rec digits n d acc remaining =
    if Z.equal n Z.zero then acc else (
      require (remaining > 0) "policy_execution_time" "Time has no bounded finite decimal representation.";
      let digit, rest = Z.ediv_rem (Z.mul n (Z.of_int 10)) d in
      digits rest d (acc ^ Z.to_string digit) (remaining - 1)) in
  let whole, rest = Z.ediv_rem numerator denominator in
  str (Z.to_string whole ^ if Z.equal rest Z.zero then "" else "." ^ digits rest denominator "" 256)
let unique code ids =
  let seen = Hashtbl.create 16 in
  List.iter (fun identity -> require (not (Hashtbl.mem seen identity)) code ("Duplicate identity: " ^ identity); Hashtbl.add seen identity ()) ids

type bounds = { max_ticks:int; max_inputs:int; max_encounters:int; max_attempts:int;
                max_work:int; max_trace_items:int; max_microsteps:int }
let bound key upper raw =
  let n = Json.integer (field key raw) in
  require (Z.sign n > 0 && Z.leq n (Z.of_int upper)) "policy_execution_bound" ("Invalid explicit execution bound: " ^ key);
  Z.to_int n
let bounds raw =
  fields ["max_ticks";"max_inputs";"max_encounters";"max_attempts";"max_work";"max_trace_items";"max_microsteps"] raw;
  {max_ticks=bound "max_ticks" 10000 raw;max_inputs=bound "max_inputs" 10000 raw;
   max_encounters=bound "max_encounters" 1000 raw;max_attempts=bound "max_attempts" 10000 raw;
   max_work=bound "max_work" 10000000 raw;max_trace_items=bound "max_trace_items" 100000 raw;
   max_microsteps=bound "max_microsteps" 1000 raw}
type binding = { encounter:string option; generation:int }
type concrete_encounter = { identity:string; declaration:string; target:string;
  start:int; finish:int option; resets:int list; mutable generation:int; mutable active:bool }
type observation_input = { input_id:string; available:int; observed:int; observer:string;
  subject:string; binding_id:string option; observation:string; status:string; value:O.value option }
type feedback = { feedback_id:string; feedback_at:int; feedback_executor:string; feedback_subject:string;
  feedback_encounter:string option; feedback_effect:string; feedback_attempt:string; outcome:string }
type evidence = { observed:int; available:int; status:string; value:O.value option; occurrences:string list }
type evaluated = { value:O.value option; reasons:string list }
type event = { event_id:string; kind:string; declaration:string; binding:binding; attempt:string option }
type attempt = { attempt_id:string; effect_spec:O.effect_spec; binding:binding; subject:string;
  initiator:string; guard:O.expression; causes:string list; parameters:(string * O.value) list;
  started:int; deadline:int option; mutable ended:int option; mutable status:string;
  mutable authorization:O.truth; machine:string option }
type pending = { requirement:O.requirement; binding:binding; trigger_id:string; attempt:string option;
  opened:int; deadline:int; mutable status:string; mutable closed:int option; mutable response_unknown:bool }
type requirement_state = { requirement:O.requirement; mutable samples:int; mutable true_samples:int;
  mutable false_samples:int; mutable unknown_samples:int; mutable triggers:int; mutable supported:bool;
  mutable active_samples:int; mutable inactive_samples:int }
type session = { behavior:O.behavior; executor:string; resolution:Q.t; horizon:int; bounds:bounds;
  encounters:concrete_encounter list; observations:observation_input list; feedback:feedback list;
  evidence:((string * binding),evidence) Hashtbl.t; states:((string * binding),O.value) Hashtbl.t;
  machines:((string * binding),string) Hashtbl.t;
  machine_attempts:((string * binding),string list) Hashtbl.t;
  rising:((string * binding),O.truth) Hashtbl.t;
  requirements:requirement_state list; mutable pending:pending list; mutable attempts:attempt list;
  mutable work:int; mutable trace_items:int; mutable sequence:int; mutable attempt_sequence:int;
  mutable now:int; mutable microstep:int; mutable events:event list;
  mutable tick_events:Json.t list; mutable tick_actions:Json.t list }
let charge (s:session) n = require (n >= 0 && n <= s.bounds.max_work - s.work) "policy_execution_work_limit" "Cumulative policy execution work budget exhausted."; s.work <- s.work+n
let retain (s:session) = charge s 1; require (s.trace_items < s.bounds.max_trace_items) "policy_execution_trace_limit" "Complete policy trace exceeds its explicit bound."; s.trace_items <- s.trace_items+1
let charge_json (s:session) value = charge s (String.length(Canonical.encode value))
let tick (s:session) n = Q.mul s.resolution (Q.of_int n)
let aligned resolution q =
  require (Q.sign q >= 0) "policy_execution_time" "Policy times must be nonnegative.";
  let ticks = Q.div q resolution in
  require (Z.equal (Q.den ticks) Z.one && Z.fits_int (Q.num ticks)) "policy_execution_time" "Policy time is not an integer number of clock ticks.";
  Z.to_int (Q.num ticks)
let deadline (s:session) duration =
  let duration=aligned s.resolution duration in
  require(duration<=max_int-s.now) "policy_execution_time" "Deadline exceeds the bounded exact scheduler integer domain.";
  s.now+duration
let binding_json (b:binding) = obj ["encounter",nullable str b.encounter;"generation",Json.int b.generation]
let executor_binding = {encounter=None;generation=0}
let find code id get xs = match List.find_opt (fun x -> get x=id) xs with Some x -> x | None -> fail code ("Unknown declaration or identity: " ^ id)
let lookup (s:session) code id get xs = charge s (List.length xs+1); find code id get xs
let encounter (s:session) id = lookup s "policy_execution_identity" id (fun (x:concrete_encounter) -> x.identity) s.encounters
let concrete_binding (e:concrete_encounter) = {encounter=Some e.identity;generation=e.generation}
let binding_live (s:session) (b:binding) = match b.encounter with None -> true | Some identity -> let e=encounter s identity in e.active && e.generation=b.generation
let scope_binding (s:session) scope (b:binding) = match scope with
  | O.Executor role -> require (List.exists (fun (r:O.role) -> r.role_id=role) s.behavior.roles) "policy_execution_scope" "State executor scope differs."; executor_binding
  | O.Encounter declaration -> (match b.encounter with
      | Some identity when (encounter s identity).declaration=declaration -> b
      | _ -> fail "policy_execution_scope" "Encounter declaration and concrete state binding differ.")
let subject_binding (s:session) subject (b:binding) =
  let role = (List.hd s.behavior.roles).role_id in
  if subject=role then executor_binding else
    let declaration = lookup s "policy_execution_subject" subject (fun (x:O.subject) -> x.subject_id) s.behavior.subjects in
    match declaration.encounter,b.encounter with
    | Some expected,Some identity when (encounter s identity).declaration=expected -> b
    | None,None when declaration.executor=Some role -> executor_binding
    | _ -> fail "policy_execution_subject" "Subject is not bound to this concrete encounter/executor."
let concrete_subject (s:session) subject (b:binding) = match (subject_binding s subject b).encounter with None -> s.executor | Some identity -> (encounter s identity).target
let value_equal (a:O.value) (b:O.value) = match a,b with
  | O.Truth x,O.Truth y -> x=y | O.Integer x,O.Integer y -> Z.equal x y | O.Text x,O.Text y -> x=y
  | O.Quantity(x,_),O.Quantity(y,_) -> Q.equal x y | _ -> false
let truth (value:evaluated) = match value.value with Some(O.Truth x) -> x | None -> O.Unknown | _ -> fail "policy_execution_type" "Boolean expression did not evaluate to truth."
let truth_json = function O.True -> str "true" | O.False -> str "false" | O.Unknown -> str "unknown"
let truth_value x : evaluated = {value=Some(O.Truth x);reasons=[]}
let inverse = function O.True -> O.False | O.False -> O.True | O.Unknown -> O.Unknown
let and_truth a b = match a,b with O.False,_|_,O.False -> O.False | O.True,O.True -> O.True | _ -> O.Unknown
let or_truth a b = match a,b with O.True,_|_,O.True -> O.True | O.False,O.False -> O.False | _ -> O.Unknown
let evidence_value (s:session) observation (b:binding) : evaluated =
  let d = lookup s "policy_execution_observation" observation (fun (x:O.observation) -> x.observation_id) s.behavior.observations in
  let b=subject_binding s d.subject b in
  match Hashtbl.find_opt s.evidence (observation,b) with
  | None -> {value=None;reasons=["missing"]}
  | Some evidence ->
      if evidence.status<>"valid" then {value=None;reasons=[evidence.status]}
      else if s.now-evidence.observed >= aligned s.resolution d.freshness then {value=None;reasons=["stale"]}
      else {value=evidence.value;reasons=[]}
let reference (expression:O.expression) = match expression.O.reference with Some x -> x | None -> fail "policy_execution_expression" "Expression lacks a required reference."
let rec eval (s:session) (b:binding) (expression:O.expression) : evaluated =
  charge s 1;
  let args () = List.map (eval s b) expression.O.args in
  let one () = match args () with [x] -> x | _ -> fail "policy_execution_expression" "Unary expression has wrong arity." in
  let two () = match args () with [a;c] -> a,c | _ -> fail "policy_execution_expression" "Binary expression has wrong arity." in
  match expression.O.op with
  | "literal" -> {value=expression.value;reasons=[]}
  | "observe" -> evidence_value s (reference expression) b
  | "state" -> let store=lookup s "policy_execution_state" (reference expression) (fun (x:O.state_store)->x.state_id) s.behavior.stores in
      {value=Hashtbl.find_opt s.states (store.state_id,scope_binding s store.scope b);reasons=[]}
  | "parameter" -> let parameter=lookup s "policy_execution_parameter" (reference expression) (fun (x:O.parameter)->x.parameter_id) s.behavior.parameters in {value=Some parameter.value;reasons=[]}
  | "not" -> let x=one () in {value=Some(O.Truth(inverse(truth x)));reasons=x.reasons}
  | "all" | "any" -> let xs=args () in
      let operation,initial=if expression.op="all" then and_truth,O.True else or_truth,O.False in
      {value=Some(O.Truth(List.fold_left (fun t x -> operation t (truth x)) initial xs));reasons=List.concat_map (fun x->x.reasons) xs}
  | "eq" | "ne" | "lt" | "le" | "gt" | "ge" ->
      let a,c=two () in (match a.value,c.value with
      | Some(O.Truth O.Unknown),_ | _,Some(O.Truth O.Unknown) | None,_ | _,None -> {value=Some(O.Truth O.Unknown);reasons=a.reasons@c.reasons}
      | Some x,Some y -> let comparison=match x,y with
          | O.Integer x,O.Integer y -> Z.compare x y | O.Quantity(x,_),O.Quantity(y,_) -> Q.compare x y
          | O.Text x,O.Text y -> String.compare x y | O.Truth x,O.Truth y -> compare x y
          | _ -> fail "policy_execution_type" "Exact comparison operands have incompatible types." in
          let answer=match expression.op with "eq"->comparison=0|"ne"->comparison<>0|"lt"->comparison<0|"le"->comparison<=0|"gt"->comparison>0|_->comparison>=0 in
          truth_value (if answer then O.True else O.False))
  | "add" | "subtract" | "multiply" | "divide" ->
      let a,c=two () in (match a.value,c.value with
      | None,_|_,None -> {value=None;reasons=a.reasons@c.reasons}
      | Some(O.Integer x),Some(O.Integer y) ->
          let n=match expression.op with "add"->Z.add x y|"subtract"->Z.sub x y|"multiply"->Z.mul x y|_->
            require (not(Z.equal y Z.zero) && Z.equal(Z.rem x y) Z.zero) "policy_execution_arithmetic" "Integer division must be exact and nonzero.";Z.div x y in
          require (Z.numbits n <= 4096) "policy_execution_numeric_limit" "Exact arithmetic exceeds the numeric bound.";
          {value=Some(O.Integer n);reasons=[]}
      | Some(O.Quantity(x,u)),Some(O.Quantity(y,_)) ->
          let n=match expression.op with "add"->Q.add x y|"subtract"->Q.sub x y|"multiply"->Q.mul x y|_->require(Q.sign y<>0) "policy_execution_arithmetic" "Division by zero.";Q.div x y in
          require (Z.numbits(Q.num n)<=4096 && Z.numbits(Q.den n)<=4096) "policy_execution_numeric_limit" "Exact arithmetic exceeds the numeric bound.";
          {value=Some(O.Quantity(n,u));reasons=[]}
      | _ -> fail "policy_execution_type" "Arithmetic operands have incompatible types.")
  | _ -> fail "policy_execution_expression" ("Unsupported value operation: " ^ expression.op)
let emit (s:session) ?attempt kind declaration (b:binding) : event =
  retain s;s.sequence<-s.sequence+1;
  let event={event_id="event/"^string_of_int s.sequence;kind;declaration;binding=b;attempt} in
  let row=obj["id",str event.event_id;"kind",str kind;"declaration",str declaration;
      "binding",binding_json b;"attempt",nullable str attempt;"microstep",Json.int s.microstep]in
  charge_json s row;charge s(List.length s.tick_events);s.tick_events<-s.tick_events@[row];
  event
let action (s:session) kind detail = retain s;let row=obj["kind",str kind;"microstep",Json.int s.microstep;"detail",detail]in
  charge_json s row;charge s(List.length s.tick_actions);s.tick_actions<-s.tick_actions@[row]
let expression_key (expression:O.expression) = Canonical.encode (obj["op",str expression.O.op;"reference",nullable str expression.reference;
  "value",nullable O.value_to_json expression.value;"scope",nullable str expression.scope;
  "phase",nullable str expression.phase])
let rec full_expression_key (expression:O.expression) = expression_key expression ^ "(" ^ String.concat "," (List.map full_expression_key expression.O.args) ^ ")"
let event_matches (s:session) (b:binding) ?machine (expression:O.expression) =
  charge s (1+List.length s.events);
  match expression.O.op with
  | "updated" ->
      let observation=lookup s "policy_execution_observation" (reference expression) (fun (x:O.observation)->x.observation_id) s.behavior.observations in
      let expected=subject_binding s observation.subject b in
      List.filter(fun (e:event)->e.kind="updated" && e.declaration=observation.observation_id && e.binding=expected) s.events
  | "effect_event" ->
      let effect_spec=lookup s "policy_execution_effect" (reference expression) (fun (x:O.effect_spec)->x.effect_id) s.behavior.effects in
      let expected=subject_binding s effect_spec.subject b in
      let matches=List.filter(fun (e:event)->e.kind=Option.value expression.phase ~default:"" && e.declaration=effect_spec.effect_id && e.binding=expected) s.events in
      (match machine with None->matches | Some identity ->
        let retained=Option.value(Hashtbl.find_opt s.machine_attempts(identity,b)) ~default:[] in
        List.filter(fun (e:event)->match e.attempt with Some id->List.mem id retained|None->false) matches)
  | "rising" ->
      List.filter(fun (e:event)->e.kind="rising" && e.declaration=full_expression_key expression && e.binding=b) s.events
  | _ -> fail "policy_execution_event" ("Unsupported event expression: " ^ expression.op)
let contexts (s:session) = executor_binding :: List.filter_map(fun (e:concrete_encounter)->if e.active then Some(concrete_binding e) else None) s.encounters
let rec required_encounters (s:session) (expression:O.expression) =
  charge s (1+List.length s.behavior.subjects);
  let current=match expression.O.op,expression.reference with
    | ("observe"|"updated"),Some id -> let o=lookup s "policy_execution_observation" id (fun(x:O.observation)->x.observation_id) s.behavior.observations in
        (match List.find_opt(fun(x:O.subject)->x.subject_id=o.subject) s.behavior.subjects with Some x->Option.to_list x.encounter|None->[])
    | "effect_event",Some id -> let e=lookup s "policy_execution_effect" id (fun(x:O.effect_spec)->x.effect_id) s.behavior.effects in
        (match List.find_opt(fun(x:O.subject)->x.subject_id=e.subject) s.behavior.subjects with Some x->Option.to_list x.encounter|None->[])
    | "state",Some id -> let st=lookup s "policy_execution_state" id (fun(x:O.state_store)->x.state_id) s.behavior.stores in
        (match st.scope with O.Encounter id->[id]|_->[])
    | _ -> [] in
  List.sort_uniq String.compare (current @ List.concat_map(required_encounters s) expression.args)
let expression_contexts (s:session) (expressions:O.expression list) =
  let required=List.sort_uniq String.compare (List.concat_map(required_encounters s) expressions) in
  match required with []->[executor_binding] | [declaration]->List.filter_map(fun (e:concrete_encounter)->if e.active && e.declaration=declaration then Some(concrete_binding e) else None) s.encounters
  | _ -> fail "policy_execution_scope" "One activation cannot mix multiple encounter declarations."
let scope_contexts (s:session) = function None->contexts s | Some(O.Executor _)->[executor_binding]
  | Some(O.Encounter declaration)->List.filter_map(fun (e:concrete_encounter)->if e.active && e.declaration=declaration then Some(concrete_binding e) else None) s.encounters

let initialize_scope (s:session) (b:binding) =
  List.iter(fun (store:O.state_store)->
    let applies=match store.scope,b.encounter with O.Executor _,None->true|O.Encounter id,Some concrete->(encounter s concrete).declaration=id|_->false in
    if applies then (
      let allocated=Hashtbl.fold(fun(id,_)_ count->if id=store.state_id then count+1 else count)s.states 0 in
      require(allocated<store.capacity) "policy_execution_state_capacity" "Concrete scoped state keys exceed the declaration's finite capacity.";
      Hashtbl.replace s.states(store.state_id,b) store.initial)) s.behavior.stores;
  List.iter(fun (machine:O.machine)->
    let applies=match machine.scope,b.encounter with O.Executor _,None->true|O.Encounter id,Some concrete->(encounter s concrete).declaration=id|_->false in
    if applies then (Hashtbl.replace s.machines(machine.machine_id,b) machine.initial;
                     Hashtbl.replace s.machine_attempts(machine.machine_id,b) [])) s.behavior.machines
let discard_scope (s:session) (b:binding) reason =
  let remove table =
    let keys=Hashtbl.fold(fun ((_,binding) as key) _ acc -> if binding=b then key::acc else acc) table [] in
    List.iter(Hashtbl.remove table) keys in
  remove s.states;remove s.machines;remove s.machine_attempts;remove s.evidence;remove s.rising;
  List.iter(fun (a:attempt)->if a.binding=b && a.status="active" then (
    a.status<-reason;a.ended<-Some s.now;ignore(emit s ~attempt:a.attempt_id reason a.effect_spec.effect_id b))) s.attempts;
  List.iter(fun (p:pending)->if p.binding=b && p.status="pending" then (p.status<-"unknown";p.closed<-Some s.now)) s.pending
let apply_encounters (s:session) =
  List.iter(fun (e:concrete_encounter)->charge s 1;
    if e.active && e.finish=Some s.now then (
      let b=concrete_binding e in discard_scope s b "encounter_ended";e.active<-false;
      ignore(emit s "encounter_ended" e.declaration b));
    if e.start=s.now then (e.active<-true;let b=concrete_binding e in initialize_scope s b;ignore(emit s "encounter_started" e.declaration b));
    if e.active && List.mem s.now e.resets then (
      let old=concrete_binding e in discard_scope s old "encounter_reset";
      e.generation<-e.generation+1;let b=concrete_binding e in initialize_scope s b;ignore(emit s "encounter_reset" e.declaration b))) s.encounters
let merge_evidence (previous:evidence option) (inputs:observation_input list) : evidence =
  let newest=List.fold_left(fun n (input:observation_input)->max n input.observed) (match previous with None->(-1)|Some e->e.observed) inputs in
  let fresh=List.filter(fun (input:observation_input)->input.observed=newest) inputs in
  let old=match previous with Some e when e.observed=newest->Some e|_->None in
  let members=(match old with None->[]|Some e->[e.status,e.value,e.occurrences,e.available]) @
    List.map(fun (x:observation_input)->x.status,x.value,[x.input_id],x.available) fresh in
  match members with
  | [] -> Option.get previous
  | (status,value,_,_)::_ ->
      let same (other,other_value,_,_)=status=other && (match value,other_value with None,None->true|Some x,Some y->value_equal x y|_->false) in
      let conflict=not(List.for_all same members) in
      {observed=newest;available=List.fold_left(fun n (_,_,_,t)->max n t) 0 members;
       status=(if conflict then "conflicting" else status);value=(if conflict then None else value);
       occurrences=List.concat_map(fun(_,_,ids,_)->ids) members}
let apply_observations (s:session) =
  let groups=ref [] in
  List.iter(fun (input:observation_input)->charge s 1;if input.available=s.now then (
    let b=match input.binding_id with None->executor_binding|Some identity->let e=encounter s identity in require e.active "policy_execution_identity" "Observation supplied outside its encounter lifetime.";concrete_binding e in
    let declaration=lookup s "policy_execution_observation" input.observation (fun(x:O.observation)->x.observation_id) s.behavior.observations in
    let expected=subject_binding s declaration.subject b in
    require (expected=b && input.observer=s.executor && input.subject=concrete_subject s declaration.subject b)
      "policy_execution_identity" "Observation executor, subject or encounter identity differs.";
    (match b.encounter with None->()|Some identity->
      let encounter=encounter s identity in
      let generation_start=List.fold_left(fun start reset->if reset<=s.now then reset else start)encounter.start encounter.resets in
      require(input.observed>=generation_start) "policy_execution_identity" "Observation predates the current encounter generation.");
    let key=input.observation,b in
    let existing=Option.value(List.assoc_opt key !groups) ~default:[] in
    groups:=List.remove_assoc key !groups @ [key,existing@[input]])) s.observations;
  List.map(fun ((id,b),inputs)->
    charge s (List.length inputs);
    let previous=Hashtbl.find_opt s.evidence(id,b) in
    let next=merge_evidence previous inputs in
    Hashtbl.replace s.evidence(id,b) next;
    action s "observation_batch" (obj["observation",str id;"binding",binding_json b;
      "occurrences",arr(List.map(fun(x:observation_input)->str x.input_id) inputs);
      "retained_occurrences",arr(List.map str next.occurrences);"status",str next.status;
      "observed_at",time_json(tick s next.observed)]);
    emit s "updated" id b) !groups
let apply_feedback (s:session) =
  List.filter_map(fun (input:feedback)->charge s (1+List.length s.attempts);if input.feedback_at<>s.now then None else
    let reject reason = action s "feedback_rejected" (obj["id",str input.feedback_id;"attempt",str input.feedback_attempt;"reason",str reason]);None in
    match List.find_opt(fun(a:attempt)->a.attempt_id=input.feedback_attempt) s.attempts with
    | None -> reject "unknown_attempt"
    | Some a when input.feedback_executor<>s.executor || input.feedback_subject<>a.subject ||
        input.feedback_encounter<>a.binding.encounter || input.feedback_effect<>a.effect_spec.effect_id -> reject "identity_mismatch"
    | Some a when a.status<>"active" || not(binding_live s a.binding) -> reject "stale_attempt"
    | Some a -> a.status<-input.outcome;a.ended<-Some s.now;
        action s "feedback_accepted" (obj["id",str input.feedback_id;"attempt",str a.attempt_id]);
        Some(emit s ~attempt:a.attempt_id input.outcome a.effect_spec.effect_id a.binding)) s.feedback
let apply_timeouts (s:session) =
  List.filter_map(fun (a:attempt)->charge s 1;
    if a.status="active" && a.deadline=Some s.now then (
      a.status<-"timed_out";a.ended<-Some s.now;Some(emit s ~attempt:a.attempt_id "timed_out" a.effect_spec.effect_id a.binding)) else None) s.attempts
let refresh_authorizations (s:session) =
  List.iter(fun (a:attempt)->charge s 1;if a.status="active" && a.effect_spec.lifecycle.authorization="continuous" then (
    let evaluated=eval s a.binding a.guard in
    let current=truth evaluated in
    if current<>a.authorization then (
      a.authorization<-current;
      action s "authorization_changed" (obj["attempt",str a.attempt_id;"authorization",truth_json current;
        "reasons",arr(List.map str evaluated.reasons);
        "lifecycle_response",str(if current=O.Unknown then a.effect_spec.lifecycle.on_unknown else if current=O.False then a.effect_spec.lifecycle.on_loss else "authorized")])))) s.attempts
let rising_expressions (s:session) =
  let all=List.concat_map(fun(r:O.rule)->[r.on]) s.behavior.rules @
    List.concat_map(fun(t:O.transition)->[t.on]) s.behavior.transitions @
    List.filter_map(fun(st:O.state_store)->st.reset) s.behavior.stores @
    List.concat_map(fun (ledger:requirement_state)->if ledger.supported then Option.to_list ledger.requirement.trigger @ Option.to_list ledger.requirement.response else []) s.requirements in
  List.fold_left(fun acc x->if x.O.op="rising" && not(List.exists(fun y->full_expression_key x=full_expression_key y) acc) then acc@[x] else acc) [] all
let update_rising (s:session) =
  List.concat_map(fun expression->
    let predicate=match expression.O.args with [x]->x|_->fail "policy_execution_event" "Rising must have one predicate." in
    List.filter_map(fun b->let key=full_expression_key expression,b in
      let before=Option.value(Hashtbl.find_opt s.rising key) ~default:O.Unknown in
      let after=truth(eval s b predicate) in Hashtbl.replace s.rising key after;
      if before=O.False && after=O.True then Some(emit s "rising" (fst key) b) else None)
      (expression_contexts s [predicate])) (rising_expressions s)

type activation = { identity:string; binding:binding; guard:O.expression; causes:event list;
  effects:string list; assignments:O.assignment list; arbitration:O.arbitration;
  machine:O.machine option; destination:string option }
let candidate_activations (s:session) =
  let rules=List.concat_map(fun(r:O.rule)->
    let expressions=r.on::r.guard::List.map(fun(a:O.assignment)->a.value) r.assignments in
    (* Effect-only subject binding is also part of an activation's environment. *)
    let effect_context=List.concat_map(fun id->let e=lookup s "policy_execution_effect" id (fun(x:O.effect_spec)->x.effect_id) s.behavior.effects in
      match List.find_opt(fun(x:O.subject)->x.subject_id=e.subject) s.behavior.subjects with Some x->Option.to_list x.encounter|None->[]) r.effects in
    let contexts=match List.sort_uniq String.compare effect_context with
      | []->expression_contexts s expressions
      | [declaration]->let expression_scopes=List.concat_map(required_encounters s) expressions in
          require(List.for_all((=)declaration) expression_scopes) "policy_execution_scope" "Rule effects and source expressions bind different encounters.";
          scope_contexts s (Some(O.Encounter declaration))
      | _->fail "policy_execution_scope" "Rule effect batch mixes encounter declarations." in
    List.filter_map(fun b->let causes=event_matches s b r.on in
      if causes=[] then None else let guard=eval s b r.guard in
      if truth guard=O.True then Some{identity=r.rule_id;binding=b;guard=r.guard;causes;effects=r.effects;
          assignments=r.assignments;arbitration=r.arbitration;machine=None;destination=None}
      else (if truth guard=O.Unknown then action s "activation_deferred" (obj["declaration",str r.rule_id;"binding",binding_json b;"reasons",arr(List.map str guard.reasons)]);None)) contexts) s.behavior.rules in
  let transitions=List.concat_map(fun(t:O.transition)->
    let machine=lookup s "policy_execution_machine" t.machine (fun(m:O.machine)->m.machine_id) s.behavior.machines in
    List.filter_map(fun b->if Hashtbl.find_opt s.machines(machine.machine_id,b)<>Some t.source then None else
      let causes=event_matches s b ~machine:machine.machine_id t.on in
      if causes=[] || truth(eval s b t.guard)<>O.True then None else
      Some{identity=t.transition_id;binding=b;guard=t.guard;causes;effects=t.effects;assignments=t.assignments;
           arbitration=machine.arbitration;machine=Some machine;destination=Some t.destination})
      (scope_contexts s (Some machine.scope))) s.behavior.transitions in
  rules@transitions
let arbitration_key (a:activation) =
  let policy=a.arbitration in
  Canonical.encode(obj["mode",str policy.mode;"tie",str policy.tie;"write_conflict",str policy.write_conflict;
    "order",arr(List.map str policy.order);"binding",binding_json a.binding])
let arbitrate (s:session) (activations:activation list) =
  let groups=List.fold_left(fun groups a->let key=arbitration_key a in
    let existing=Option.value(List.assoc_opt key groups) ~default:[] in List.remove_assoc key groups@[key,existing@[a]]) [] activations in
  List.concat_map(fun(_,group)->charge s (List.length group);match group with []->[]|first::_->
    if first.arbitration.mode="priority" then List.iter(fun (a:activation)->require(List.mem a.identity a.arbitration.order) "policy_execution_arbitration" "Activation missing from explicit arbitration order.") group;
    match first.arbitration.mode,group with
    | _,[_]->group
    | "exclusive",_->fail "policy_execution_exclusive" "Simultaneous activations violate declared exclusive arbitration."
    | "priority",_->
        let rank (a:activation)=let rec loop index=function []->max_int|id::rest->if id=a.identity then index else loop(index+1)rest in loop 0 a.arbitration.order in
        let sorted=List.stable_sort(fun a b->compare(rank a)(rank b)) group in
        let selected=List.hd sorted in
        require(not(List.exists(fun a->rank a=rank selected)(List.tl sorted))) "policy_execution_tie" "Multiple activations have equal explicit priority.";
        List.iter(fun (a:activation)->action s "arbitration_suppressed" (obj["declaration",str a.identity;"selected",str selected.identity;"binding",binding_json a.binding])) (List.tl sorted);
        [selected]
    | _->fail "policy_execution_arbitration" "Unsupported arbitration mode.") groups
let apply_resets (s:session) =
  (* All reset predicates read the same pre-reset state. Commit their initial
     values together once per tick, before activation guards and assignments. *)
  let resets=List.concat_map(fun(st:O.state_store)->match st.reset with None->[]|Some predicate->
    List.filter_map(fun b->if truth(eval s b predicate)=O.True then Some(st,b)else None)
      (scope_contexts s (Some st.scope))) s.behavior.stores in
  List.iter(fun((st:O.state_store),b)->Hashtbl.replace s.states(st.state_id,b)st.initial;
    action s "state_reset" (obj["state",str st.state_id;"binding",binding_json b]))resets
let execute_activations (s:session) (activations:activation list) =
  let writes=ref [] and prepared=ref [] in
  List.iter(fun(a:activation)->
    let assigned=List.map(fun(assignment:O.assignment)->
      let store=lookup s "policy_execution_state" assignment.state (fun(st:O.state_store)->st.state_id) s.behavior.stores in
      let binding=scope_binding s store.scope a.binding in
      (store.state_id,binding),eval s a.binding assignment.value) a.assignments in
    let effects=List.map(fun id->let effect_spec=lookup s "policy_execution_effect" id (fun(e:O.effect_spec)->e.effect_id) s.behavior.effects in
      let parameters=List.map(fun(name,expression)->name,eval s a.binding expression) effect_spec.parameters in
      effect_spec,parameters) a.effects in
    if List.exists(fun(_,(value:evaluated))->value.value=None) assigned ||
       List.exists(fun(_,parameters)->List.exists(fun(_,(value:evaluated))->value.value=None) parameters) effects
    then action s "activation_deferred" (obj["declaration",str a.identity;"binding",binding_json a.binding;"reasons",arr[str "unknown_assignment_or_parameter"]])
    else (
      List.iter(fun(key,(value:evaluated))->let value=Option.get value.value in
        (match List.find_opt(fun(k,_,_)->k=key) !writes with
        | None->writes:= !writes@[key,value,a.arbitration.write_conflict]
        | Some(_,previous,policy)->require(a.arbitration.write_conflict="identical_only" && policy="identical_only" && value_equal previous value)
            "policy_execution_write_conflict" "Atomic activations conflict on a concrete state key.");
        ()) assigned;
      prepared:= !prepared@[a,List.map(fun(e,parameters)->e,List.map(fun(name,(v:evaluated))->name,Option.get v.value) parameters) effects])) activations;
  let requested=List.fold_left(fun count(_,effects)->count+List.length effects)0 !prepared in
  require(requested<=s.bounds.max_attempts-s.attempt_sequence) "policy_execution_attempt_limit" "Effect attempt bound exhausted before atomic batch.";
  List.iter(fun((state,b),value,_)->Hashtbl.replace s.states(state,b) value;
    action s "state_written" (obj["state",str state;"binding",binding_json b;"value",O.value_to_json value])) !writes;
  List.concat_map(fun((a:activation),effects)->
    let started=List.map(fun((effect_spec:O.effect_spec),parameters)->
      s.attempt_sequence<-s.attempt_sequence+1;
      let id="attempt/"^string_of_int s.attempt_sequence in
      let binding=subject_binding s effect_spec.subject a.binding in
      (* The retained activation binding is wider than an executor-targeted
         effect when the initiating guard depended on an encounter. Keep it. *)
      require(binding=a.binding) "policy_execution_scope" "Effect subject and retained activation binding must coincide.";
      let attempt={attempt_id=id;effect_spec;binding=a.binding;subject=concrete_subject s effect_spec.subject a.binding;
        initiator=a.identity;guard=a.guard;causes=List.map(fun(e:event)->e.event_id)a.causes;parameters;
        started=s.now;deadline=Option.map(deadline s) effect_spec.lifecycle.timeout;
        ended=None;status="active";authorization=O.True;machine=Option.map(fun(m:O.machine)->m.machine_id)a.machine} in
      charge s(List.length s.attempts);s.attempts<-s.attempts@[attempt];
      action s "effect_requested" (obj["attempt",str id;"effect",str effect_spec.effect_id;"initiator",str a.identity;
        "binding",binding_json a.binding;"subject",str attempt.subject;"causes",arr(List.map str attempt.causes);
        "parameters",obj(List.map(fun(name,value)->name,O.value_to_json value) parameters)]);
      attempt,[emit s ~attempt:id "requested" effect_spec.effect_id a.binding;emit s ~attempt:id "initiated" effect_spec.effect_id a.binding]) effects in
    (match a.machine,a.destination with
    | Some machine,Some destination->Hashtbl.replace s.machines(machine.machine_id,a.binding)destination;
        let retained=Option.value(Hashtbl.find_opt s.machine_attempts(machine.machine_id,a.binding))~default:[] in
        let retained=if List.mem destination machine.terminal then []
          else if started=[] then retained else List.map(fun(a,_)->a.attempt_id)started in
        Hashtbl.replace s.machine_attempts(machine.machine_id,a.binding)retained;
        action s "machine_transition" (obj["machine",str machine.machine_id;"transition",str a.identity;"destination",str destination;
          "binding",binding_json a.binding;"retained_attempts",arr(List.map str retained)])
    | None,None->()|_->fail "policy_execution_machine" "Incomplete machine activation.");
    List.concat_map snd started) !prepared

let value_ops = ["literal";"observe";"state";"parameter";"all";"any";"not";"eq";"ne";"lt";"le";"gt";"ge"]
let rec supported_value (expression:O.expression) = expression.O.value_type<>None && List.mem expression.op value_ops && List.for_all supported_value expression.args
let rec observed_predicate (expression:O.expression) = expression.O.op<>"state" && supported_value expression && List.for_all observed_predicate expression.args
let rec contains_observation (expression:O.expression) = expression.O.op="observe" || List.exists contains_observation expression.args
let supported_event (expression:O.expression) = expression.O.value_type=None &&
  (match expression.op with
   | "updated"->expression.args=[]
   | "effect_event"->expression.args=[] && (match expression.phase with
       | Some phase->List.mem phase ["requested";"initiated";"completed";"failed";"timed_out"]
       | None->false)
   | "rising"->(match expression.args with [x]->observed_predicate x && contains_observation x|_->false)
   | _->false)
let supported_response_correlation (trigger:O.expression) (response:O.expression) =
  (* An effect trigger retains its attempt identity. Cross-effect and
     effect-to-observation event correlation needs a separate interpretation. *)
  trigger.op<>"effect_event" || response.value_type<>None ||
    (response.op="effect_event" && trigger.reference=response.reference)
let supported_requirement (r:O.requirement) =
  let absent key = match List.assoc_opt key (Json.object_fields r.source) with None|Some Json.Null->true|Some(Json.Array [])->true|_->false in
  let no_extra=List.for_all absent ["lower";"upper";"applies_to";"contract"] in
  let finite_horizon=match List.assoc_opt "horizon"(Json.object_fields r.source)with Some(Json.String _)->false|_->true in
  (* The domain retains unsupported expressions in [source], even when they
     cannot decode into operational expressions. Never treat that as absence. *)
  let decoded=List.for_all(fun(key,expression)->field key r.source=Json.Null || Option.is_some expression)
    ["condition",r.condition;"trigger",r.trigger;"response",r.response] in
  no_extra && finite_horizon && decoded && r.scope<>None && match r.kind with
  | "safety" -> r.trigger=None && r.response=None && r.deadline=None && (match r.condition with Some x->supported_value x && x.value_type=Some O.Truth_type|None->false)
  | "progress" -> (match r.trigger,r.response,r.deadline with Some trigger,Some response,Some deadline->
      supported_event trigger && (supported_event response || (supported_value response && response.value_type=Some O.Truth_type)) && Q.sign deadline>0
      && supported_response_correlation trigger response
      && (match r.condition with None->true|Some x->supported_value x && x.value_type=Some O.Truth_type)|_->false)
  | _ -> false
let requirement_in_horizon (s:session) (r:O.requirement) = match r.horizon with None->true|Some horizon->Q.compare(tick s s.now)horizon<=0
let satisfy_progress (s:session) =
  List.iter(fun (p:pending)->charge s 1;if p.status="pending" && binding_live s p.binding && requirement_in_horizon s p.requirement then
    let response=Option.get p.requirement.response in
    let satisfied=if response.O.value_type=None then
      List.exists(fun(e:event)->match p.attempt with None->true|Some attempt->e.attempt=Some attempt)(event_matches s p.binding response)
      else let response=truth(eval s p.binding response) in
        if response=O.Unknown then p.response_unknown<-true;
        response=O.True in
    if satisfied then (p.status<-"pass";p.closed<-Some s.now;
      action s "requirement_response" (obj["requirement",str p.requirement.requirement_id;"trigger",str p.trigger_id;"binding",binding_json p.binding]))) s.pending
let progress_events (s:session) =
  List.iter(fun (ledger:requirement_state)->let r=ledger.requirement in
    if ledger.supported && r.kind="progress" && requirement_in_horizon s r then
      List.iter(fun b->
        let matched=event_matches s b (Option.get r.trigger) in
        List.iter(fun (event:event)->
          charge s 1;
          let condition=match r.condition with None->O.True|Some x->truth(eval s b x) in
          if condition<>O.False then (
            ledger.triggers<-ledger.triggers+1;
            let pending={requirement=r;binding=b;trigger_id=event.event_id;attempt=event.attempt;opened=s.now;
              deadline=deadline s (Option.get r.deadline);
              status=(if condition=O.Unknown then "unknown" else "pending");closed=(if condition=O.Unknown then Some s.now else None);response_unknown=false} in
            retain s;charge s(List.length s.pending);s.pending<-s.pending@[pending])) matched)
        (scope_contexts s r.scope)) s.requirements;
  satisfy_progress s
let close_requirements (s:session) =
  List.iter(fun (ledger:requirement_state)->let r=ledger.requirement in
    if ledger.supported && r.kind="safety" && requirement_in_horizon s r then
      List.iter(fun b->charge s 1;ledger.samples<-ledger.samples+1;
        (match truth(eval s b (Option.get r.condition)) with O.True->ledger.true_samples<-ledger.true_samples+1
         | O.False->ledger.false_samples<-ledger.false_samples+1|O.Unknown->ledger.unknown_samples<-ledger.unknown_samples+1);
        if List.exists(fun(a:attempt)->a.binding=b && a.status="active")s.attempts then ledger.active_samples<-ledger.active_samples+1
        else ledger.inactive_samples<-ledger.inactive_samples+1) (scope_contexts s r.scope)) s.requirements;
  List.iter(fun(p:pending)->charge s 1;if p.status="pending" && p.deadline<=s.now && requirement_in_horizon s p.requirement then (
    p.status<-(if p.response_unknown then "unknown"else "fail");p.closed<-Some s.now;
    action s "requirement_deadline" (obj["requirement",str p.requirement.requirement_id;"trigger",str p.trigger_id;"binding",binding_json p.binding]))) s.pending
let snapshot (s:session) =
  let states=Hashtbl.fold(fun(state,binding)value acc -> (state,binding,value)::acc)s.states[]
      |>List.sort(fun(a,b,_)(c,d,_)->compare(a,b)(c,d))
      |>List.map(fun(state,binding,value)->retain s;obj["state",str state;"binding",binding_json binding;"value",O.value_to_json value]) in
  let machines=Hashtbl.fold(fun(machine,binding)state acc -> (machine,binding,state)::acc)s.machines[]
      |>List.sort(fun(a,b,_)(c,d,_)->compare(a,b)(c,d))
      |>List.map(fun(machine,binding,state)->retain s;obj["machine",str machine;"binding",binding_json binding;"state",str state;
        "attempts",arr(List.map str(Option.value(Hashtbl.find_opt s.machine_attempts(machine,binding))~default:[]))]) in
  let evidence=List.concat_map(fun(o:O.observation)->
    let contexts=if o.subject=(List.hd s.behavior.roles).role_id then [executor_binding] else
      let subject=lookup s "policy_execution_subject" o.subject(fun(x:O.subject)->x.subject_id)s.behavior.subjects in
      match subject.encounter with None->[executor_binding]|Some declaration->scope_contexts s (Some(O.Encounter declaration)) in
    List.map(fun b->retain s;let value=evidence_value s o.observation_id b in
      let retained=Hashtbl.find_opt s.evidence(o.observation_id,b) in
      obj["observation",str o.observation_id;"binding",binding_json b;
        "status",str(match value.reasons with []->"valid"|reason::_->reason);
        "value",nullable O.value_to_json value.value;
        "observed_at",nullable(fun(e:evidence)->time_json(tick s e.observed))retained;
        "available_at",nullable(fun(e:evidence)->time_json(tick s e.available))retained;
        "occurrences",arr(List.map str(match retained with None->[]|Some e->e.occurrences))]) contexts) s.behavior.observations in
  retain s;let result=obj["time",time_json(tick s s.now);"microsteps",Json.int s.microstep;
    "events",arr s.tick_events;"actions",arr s.tick_actions;"states",arr states;"machines",arr machines;
    "evidence",arr evidence;"active_attempts",arr(List.filter_map(fun(a:attempt)->if a.status="active" then Some(str a.attempt_id)else None)s.attempts)]in
  charge_json s result;result
let attempt_json (s:session) (a:attempt) = obj[
  "id",str a.attempt_id;"effect",str a.effect_spec.effect_id;"executor",str s.executor;"subject",str a.subject;
  "binding",binding_json a.binding;"initiator",str a.initiator;"causes",arr(List.map str a.causes);
  "parameters",obj(List.map(fun(k,v)->k,O.value_to_json v)a.parameters);
  "started_at",time_json(tick s a.started);"deadline",nullable(fun t->time_json(tick s t))a.deadline;
  "ended_at",nullable(fun t->time_json(tick s t))a.ended;"status",str a.status;
  "authorization",truth_json a.authorization;"machine",nullable str a.machine]
let requirement_json (s:session) (ledger:requirement_state) =
  let r=ledger.requirement in
  let obligations=List.filter(fun(p:pending)->p.requirement.requirement_id=r.requirement_id)s.pending in
  let horizon_complete=match r.horizon with None->true|Some horizon->Q.compare(tick s s.horizon)horizon>=0 in
  let status=if not ledger.supported then "unsupported" else if r.kind="safety" then
    if ledger.false_samples>0 then "fail" else if ledger.samples=0 || ledger.unknown_samples>0 || not horizon_complete then "unknown" else "pass"
    else if List.exists(fun(p:pending)->p.status="fail")obligations then "fail"
    else if ledger.triggers=0 || not horizon_complete || List.exists(fun(p:pending)->p.status<>"pass")obligations then "unknown" else "pass" in
  obj["id",str r.requirement_id;"kind",str r.kind;"status",str status;"source",r.source;
    "assumptions",arr(List.map str r.assumptions);"conditional",Json.Bool(r.assumptions<>[] || s.behavior.assumptions<>[]);
    "coverage",obj["samples",Json.int ledger.samples;"true",Json.int ledger.true_samples;"false",Json.int ledger.false_samples;
      "unknown",Json.int ledger.unknown_samples;"triggers",Json.int ledger.triggers;"active",Json.int ledger.active_samples;
      "inactive",Json.int ledger.inactive_samples;"horizon_complete",Json.Bool horizon_complete];
    "obligations",arr(List.map(fun(p:pending)->obj["trigger",str p.trigger_id;"binding",binding_json p.binding;
      "attempt",nullable str p.attempt;"opened_at",time_json(tick s p.opened);"deadline",time_json(tick s p.deadline);
      "status",str(if p.status="pending" then "unknown"else p.status);"closed_at",nullable(fun t->time_json(tick s t))p.closed;
      "response_unknown",Json.Bool p.response_unknown])obligations)]

let execute (behavior:O.behavior) timeline =
  ignore(D.document_digest timeline);
  fields["profile";"executor";"horizon";"encounters";"observations";"feedback";"bounds"]timeline;
  require(text "profile" timeline=timeline_profile) "policy_execution_profile" "Unsupported timeline profile.";
  require(List.length behavior.O.roles=1 && List.length behavior.clocks=1) "policy_execution_profile" "Execution requires exactly one executor role and clock.";
  let resolution=(List.hd behavior.clocks).resolution in
  require(Q.sign resolution>0) "policy_execution_time" "Clock resolution must be positive.";
  let bounds=bounds(field "bounds" timeline) in
  let time value=aligned resolution(exact value) in
  let horizon=time(field "horizon" timeline) in
  require(horizon<bounds.max_ticks) "policy_execution_tick_limit" "Inclusive horizon exceeds explicit tick bound.";
  let within value=let t=time value in require(t<=horizon) "policy_execution_time" "Input time exceeds declared horizon.";t in
  let executor=name "executor" timeline in
  let encounter_values=items "encounters" timeline and observation_values=items "observations" timeline and feedback_values=items "feedback" timeline in
  require(List.length encounter_values<=bounds.max_encounters) "policy_execution_encounter_limit" "Concrete encounter count exceeds bound.";
  require(List.length observation_values+List.length feedback_values<=bounds.max_inputs) "policy_execution_input_limit" "Timeline input count exceeds bound.";
  let ingress_work=String.length(Canonical.encode timeline)+
    (1+List.length behavior.nodes+List.length encounter_values)*(1+List.length observation_values+List.length feedback_values+List.length encounter_values)in
  require(ingress_work<=bounds.max_work) "policy_execution_work_limit" "Timeline ingress exceeds cumulative work bound.";
  let encounters=List.map(fun value->fields["id";"declaration";"target";"start";"end";"resets"]value;
    let identity=name "id" value and declaration=name "declaration" value and target=name "target" value in
    ignore(find "policy_execution_identity" declaration(fun(e:O.encounter)->e.encounter_id)behavior.encounters);
    let start=within(field "start" value) and finish=match field "end" value with Json.Null->None|v->Some(within v) in
    require(match finish with None->true|Some t->t>start) "policy_execution_time" "Encounter end must follow its start.";
    let resets=List.map within(items "resets" value) in
    require(List.sort_uniq compare resets=resets && List.for_all(fun t->t>start && (match finish with None->true|Some ending->t<ending))resets)
      "policy_execution_time" "Encounter resets must be unique, sorted and strictly inside the lifetime.";
    {identity;declaration;target;start;finish;resets;generation=0;active=false})encounter_values in
  unique "policy_execution_identity" (List.map(fun (e:concrete_encounter)->e.identity)encounters);
  let check_encounter=function None->()|Some id->ignore(find "policy_execution_identity" id(fun(e:concrete_encounter)->e.identity)encounters) in
  let observations=List.map(fun value->fields["id";"available_at";"observed_at";"observer";"subject";"encounter";"observation";"status";"value"]value;
    let observation=name "observation" value in
    let declaration=find "policy_execution_observation" observation(fun(o:O.observation)->o.observation_id)behavior.observations in
    let available=within(field "available_at" value) and observed=within(field "observed_at" value) in
    require(observed<=available) "policy_execution_time" "Observation cannot be available before it was observed.";
    let binding_id=optional_text(field "encounter" value) in check_encounter binding_id;
    let status=text "status" value in
    require(List.mem status["valid";"missing";"invalid";"conflicting"]) "policy_execution_evidence" "Unknown evidence status.";
    let raw=field "value" value in
    let evidence_value=if status="valid" then (
      require(raw<>Json.Null) "policy_execution_evidence" "Valid evidence must supply a known typed value.";
      let typed=O.value_of_json declaration.value_type raw in
      require(typed<>O.Truth O.Unknown) "policy_execution_evidence" "Valid evidence must carry known truth; uncertainty requires an explicit evidence status.";
      Some typed)
      else (require(raw=Json.Null) "policy_execution_evidence" "Unknown evidence must not carry an asserted value.";None) in
    {input_id=name "id" value;available;observed;observer=name "observer" value;subject=name "subject" value;binding_id;observation;status;value=evidence_value})observation_values in
  let feedback=List.map(fun value->fields["id";"available_at";"executor";"subject";"encounter";"effect";"attempt";"outcome"]value;
    let outcome=text "outcome" value in require(List.mem outcome["completed";"failed"]) "policy_execution_feedback" "Unsupported external effect outcome.";
    {feedback_id=name "id" value;feedback_at=within(field "available_at" value);feedback_executor=name "executor" value;
     feedback_subject=name "subject" value;feedback_encounter=optional_text(field "encounter" value);
     feedback_effect=name "effect" value;feedback_attempt=name "attempt" value;outcome})feedback_values in
  unique "policy_execution_occurrence" (List.map(fun(o:observation_input)->o.input_id)observations @ List.map(fun (f:feedback)->f.feedback_id)feedback);
  let feedback_outcomes=Hashtbl.create 16 in
  List.iter(fun (input:feedback)->let key=input.feedback_at,input.feedback_attempt in
    (match Hashtbl.find_opt feedback_outcomes key with None->Hashtbl.add feedback_outcomes key input.outcome
    | Some outcome->require(outcome=input.outcome) "policy_execution_feedback_conflict" "One attempt has contradictory simultaneous feedback outcomes."))feedback;
  List.iter(fun(o:O.observation)->require(aligned resolution o.freshness>0) "policy_execution_time" "Freshness must span at least one tick.")behavior.observations;
  List.iter(fun(e:O.effect_spec)->
    require(List.mem e.lifecycle.authorization["initiation";"continuous"] && e.lifecycle.on_loss="continue" && List.mem e.lifecycle.on_unknown["continue";"defer"])
      "policy_execution_lifecycle" "Lifecycle stop or cancellation is not implemented in this profile.";
    Option.iter(fun d->require(aligned resolution d>0) "policy_execution_time" "Timeout must span at least one tick.")e.lifecycle.timeout)behavior.effects;
  let requirements=List.map(fun requirement->{requirement;samples=0;true_samples=0;false_samples=0;unknown_samples=0;triggers=0;
    supported=supported_requirement requirement;active_samples=0;inactive_samples=0})behavior.requirements in
  let s={behavior;executor;resolution;horizon;bounds;encounters;observations;feedback;
    evidence=Hashtbl.create 16;states=Hashtbl.create 16;machines=Hashtbl.create 16;machine_attempts=Hashtbl.create 16;
    rising=Hashtbl.create 16;requirements;pending=[];attempts=[];work=ingress_work;trace_items=0;sequence=0;attempt_sequence=0;
    now=0;microstep=0;events=[];tick_events=[];tick_actions=[]} in
  List.iter(fun (ledger:requirement_state)->if ledger.supported then (
    let r=ledger.requirement in
    let encountered=List.sort_uniq String.compare(List.concat_map(required_encounters s)
      (Option.to_list r.condition @ Option.to_list r.trigger @ Option.to_list r.response)) in
    let compatible=match r.scope with Some(O.Executor _)->encountered=[]
      | Some(O.Encounter identity)->List.for_all((=)identity)encountered|None->false in
    ledger.supported<-compatible))requirements;
  (* Ingress and linear indexed scans are charged conservatively before work.
     No runtime cache or previous report supplies acceptance. *)
  initialize_scope s executor_binding;
  let frames=ref [] in
  for now=0 to horizon do
    s.now<-now;s.microstep<-0;s.tick_events<-[];s.tick_actions<-[];
    charge s (1+List.length observations+List.length feedback+
      (1+List.length behavior.nodes)*(1+List.length encounters));
    apply_encounters s;
    let updates=apply_observations s in
    let feedback_events=apply_feedback s in
    let timeout_events=apply_timeouts s in
    apply_resets s;
    refresh_authorizations s;
    let edges=update_rising s in
    s.events<-updates@feedback_events@timeout_events@edges;
    let continue=ref true in
    while !continue do
      require(s.microstep<bounds.max_microsteps) "policy_execution_settling_limit" "Same-time settling exceeds explicit microstep bound.";
      s.microstep<-s.microstep+1;
      charge s (1+(1+List.length behavior.nodes)*(1+List.length encounters));
      progress_events s;
      let candidates=candidate_activations s in
      let selected=arbitrate s candidates in
      let next=execute_activations s selected in
      satisfy_progress s;
      refresh_authorizations s;
      s.events<-next;
      continue:=next<>[]
    done;
    close_requirements s;
    frames:=snapshot s :: !frames
  done;
  List.iter(fun _->retain s)s.attempts;
  List.iter(fun _->retain s)s.requirements;
  let attempts=List.map(fun a->let row=attempt_json s a in charge_json s row;row)s.attempts in
  let requirements=List.map(fun (ledger:requirement_state)->charge s(List.length s.pending);let row=requirement_json s ledger in charge_json s row;row)s.requirements in
  obj["schema_version",str schema_version;"profile",str O.profile;
    "behavior_digest",str(Canonical.fingerprint(O.behavior_to_json behavior));
    "timeline_digest",str(Canonical.fingerprint timeline);"horizon",field "horizon" timeline;
    "executor",str executor;"status",str "complete";"frames",arr(List.rev !frames);
    "attempts",arr attempts;"requirements",arr requirements;
    "usage",obj["ticks",Json.int(horizon+1);"work",Json.int s.work;"trace_items",Json.int s.trace_items;"attempts",Json.int s.attempt_sequence];
    "claim",str "bounded_supplied_timeline_only"]
