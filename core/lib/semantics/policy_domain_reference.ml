open Bioc_wire
module F = Bioc_domain.Policy_operating_domain
module O = Bioc_domain.Policy_operational
module D = Bioc_domain.Policy_document
module E = Policy_execution

let profile = "biocompiler.policy_domain_reference.v0.1"
let str value = Json.String value
let arr values = Json.Array values
let obj fields = Json.Object fields
let get name value = Json.field name (Json.object_fields value)
let items name value = Json.array (get name value)
let require = Diagnostic.require
let replace key replacement value = obj (List.map (fun (name, item) ->
  name, if name = key then replacement else item) (Json.object_fields value))

type execution_bounds = {
  raw : Json.t; max_ticks : int; max_encounters : int;
  max_attempts : int; max_work : int;
}
let execution_bounds_of_json raw =
  ignore (D.document_digest raw);
  let limits = ["max_ticks",10000; "max_inputs",10000;
    "max_encounters",1000; "max_attempts",10000; "max_work",10000000;
    "max_trace_items",100000; "max_microsteps",1000] in
  Json.exact_fields (List.map fst limits) (Json.object_fields raw);
  let values = List.map (fun (name, maximum) ->
    let value = Json.integer (get name raw) in
    require (Z.sign value > 0 && Z.leq value (Z.of_int maximum))
      "policy_domain_reference_bound" ("Invalid explicit adapter bound: " ^ name);
    name, Z.to_int value) limits in
  {raw; max_ticks=List.assoc "max_ticks" values;
   max_encounters=List.assoc "max_encounters" values;
   max_attempts=List.assoc "max_attempts" values; max_work=List.assoc "max_work" values}
let execution_bounds_to_json (bounds:execution_bounds) = bounds.raw

type accounting = {
  replay_calls : Z.t; reserved_work : Z.t; charged_work : Z.t; reported_work : Z.t;
  reported_trace_items : Z.t; unreported_calls : Z.t; timeline_bytes : Z.t;
}
let zero = {replay_calls=Z.zero; reserved_work=Z.zero; charged_work=Z.zero; reported_work=Z.zero;
  reported_trace_items=Z.zero; unreported_calls=Z.zero; timeline_bytes=Z.zero}
let add (a:accounting) (b:accounting) = {
  replay_calls=Z.add a.replay_calls b.replay_calls;
  reserved_work=Z.add a.reserved_work b.reserved_work;
  charged_work=Z.add a.charged_work b.charged_work;
  reported_work=Z.add a.reported_work b.reported_work;
  reported_trace_items=Z.add a.reported_trace_items b.reported_trace_items;
  unreported_calls=Z.add a.unreported_calls b.unreported_calls;
  timeline_bytes=Z.add a.timeline_bytes b.timeline_bytes;
}
type t = {
  behavior : O.behavior; domain : F.validated; bounds : execution_bounds;
  cursor : F.cursor; encounters : Json.t list; observations : Json.t list;
  feedback : Json.t list; frames : Json.t list; attempts : Json.t list;
  cost : accounting;
}
type receipt = {
  timeline : Json.t; execution : Json.t option;
  delta : accounting; cumulative : accounting;
}
type failure_kind = Source_bound | Exhausted | Source_error
type failure = {kind:failure_kind; diagnostic:Diagnostic.t; receipt:receipt}
type advanced = {
  next : t; receipt : receipt; frame : Json.t;
  creations : F.source_creation list;
}
type outcome = Advanced of advanced | Stopped of failure

let create ~(behavior:O.behavior) ~(domain:F.t) ~(bounds:execution_bounds) =
  let validated = F.validate_for ~behavior domain in
  require (bounds.max_ticks > domain.horizon_ticks &&
    bounds.max_encounters >= List.length domain.encounters)
    "policy_domain_reference_bound" "Execution bounds do not cover the declared inclusive horizon and encounter slots.";
  require (bounds.max_attempts > domain.logical_limits.max_source_attempts)
    "policy_domain_reference_bound" "Executor attempt ceiling must exceed the logical source-attempt bound; it cannot hide a source-bound violation.";
  let encounters = List.map (fun (slot:F.encounter) ->
    obj ["id",str slot.identity; "declaration",str slot.declaration;
      "target",str slot.target;
      "start",E.time_json (Q.mul (F.resolution validated) (Q.of_int slot.start_tick));
      "end",Json.Null; "resets",arr []]) domain.encounters in
  {behavior; domain=validated; bounds; cursor=F.initial validated;
   encounters; observations=[]; feedback=[]; frames=[]; attempts=[]; cost=zero}
let choices (state:t) = F.choices state.domain state.cursor
let finished (state:t) = F.finished state.domain state.cursor
let cursor_digest (state:t) = F.cursor_digest state.cursor
let accounting (state:t) = state.cost
let next_work_reservation (state:t) = Z.of_int state.bounds.max_work
let time (state:t) tick = E.time_json (Q.mul (F.resolution state.domain) (Q.of_int tick))
let slot (state:t) identity =
  match List.find_opt (fun (slot:F.encounter) -> slot.identity=identity)
    (F.specification state.domain).encounters with
  | Some value -> value
  | None -> Diagnostic.fail "policy_domain_reference_identity" "Causal input refers to an absent encounter slot."
let occurrence kind tick index = str ("domain/" ^ kind ^ "/" ^ string_of_int tick ^ "/" ^ string_of_int index)
let observation_json (state:t) index (input:F.observation_input) =
  let target = (slot state input.slot).target in
  let status,value = match input.evidence with
    | F.Known value -> "valid",Json.Bool value
    | F.Missing -> "missing",Json.Null | F.Invalid -> "invalid",Json.Null
    | F.Conflicting -> "conflicting",Json.Null in
  obj ["id",occurrence "observation" input.available_tick index;
    "available_at",time state input.available_tick;
    "observed_at",time state input.observed_tick;
    "observer",str (F.specification state.domain).executor_identity;
    "subject",str target; "encounter",str input.slot;
    "observation",str input.observation; "status",str status; "value",value]
let feedback_json (state:t) tick index (input:F.feedback_input) =
  let executor = (F.specification state.domain).executor_identity in
  let context,subject = match input.attempt.key.context with
    | F.Executor -> Json.Null,executor
    | F.Encounter_slot identity -> str identity,(slot state identity).target in
  obj ["id",occurrence "feedback" tick index; "available_at",time state tick;
    "executor",str executor; "subject",str subject; "encounter",context;
    "effect",str input.attempt.key.effect_id;
    "attempt",str input.attempt.source_attempt_id;
    "outcome",str (match input.outcome with F.Completed -> "completed" | F.Failed -> "failed")]
let encounters_at (state:t) (batch:F.input_batch) =
  List.map (fun row ->
    let identity = Json.string (get "id" row) in
    match List.assoc identity batch.lifecycle with
    | F.Keep -> row
    | F.End -> replace "end" (time state batch.tick) row
    | F.Reset -> replace "resets" (arr (items "resets" row @ [time state batch.tick])) row
  ) state.encounters

let invariant condition message = require condition "policy_domain_reference_prefix" message
let rec split count values =
  if count=0 then [],values else match values with
  | [] -> Diagnostic.fail "policy_domain_reference_prefix" "Replay removed previously emitted source records."
  | first::rest -> let prefix,suffix=split (count-1) rest in first::prefix,suffix
let immutable_attempt row =
  obj (List.map (fun key -> key,get key row)
    ["id";"effect";"executor";"subject";"binding";"initiator";"causes";
     "parameters";"started_at";"deadline";"machine"])
let creations (state:t) (batch:F.input_batch) attempts =
  let prior,new_attempts = split (List.length state.attempts) attempts in
  invariant (List.for_all2 (fun a b -> Json.equal (immutable_attempt a) (immutable_attempt b))
    state.attempts prior) "Replay altered prior immutable source attempt metadata.";
  List.mapi (fun index row ->
    invariant (Json.equal (get "started_at" row) (time state batch.tick))
      "New source creation does not belong to the current causal tick.";
    let binding = get "binding" row in
    let context = match get "encounter" binding with
      | Json.Null -> F.Executor | value -> F.Encounter_slot (Json.name value) in
    let generation = Json.integer (get "generation" binding) in
    invariant (Z.sign generation >= 0 && Z.fits_int generation) "Source generation is not a finite nonnegative integer.";
    {F.key={context; generation=Z.to_int generation;
      effect_id=Json.name (get "effect" row);
      creation_ordinal=List.length state.attempts+index+1};
     source_attempt_id=Json.name (get "id" row); created_tick=batch.tick}
  ) new_attempts
let failure_kind (diagnostic:Diagnostic.t) = match diagnostic.code with
  | "policy_domain_source_bound" | "policy_execution_attempt_limit" -> Source_bound
  | "policy_execution_tick_limit" | "policy_execution_input_limit"
  | "policy_execution_encounter_limit" | "policy_execution_work_limit"
  | "policy_execution_trace_limit" | "policy_execution_settling_limit" -> Exhausted
  | _ -> Source_error
let receipt (state:t) timeline execution =
  let reported_work,reported_trace_items,unreported_calls = match execution with
    | None -> Z.zero,Z.zero,Z.one
    | Some report -> let usage=get "usage" report in
        Json.integer (get "work" usage),Json.integer (get "trace_items" usage),Z.zero in
  let delta = {replay_calls=Z.one; reserved_work=next_work_reservation state;
    charged_work=(if execution=None then next_work_reservation state else reported_work);
    reported_work; reported_trace_items; unreported_calls;
    timeline_bytes=Z.of_int (String.length (Canonical.encode timeline))} in
  {timeline; execution; delta; cumulative=add state.cost delta}

let step (state:t) (batch:F.input_batch) =
  require (not (finished state) && batch.tick=F.cursor_tick state.cursor &&
    batch.origin=F.cursor_digest state.cursor) "policy_domain_cursor"
    "Input batch belongs to another causal source prefix or a finished domain.";
  let encounters = encounters_at state batch in
  let observations = state.observations @ List.mapi (observation_json state) batch.observations in
  let feedback = state.feedback @ List.mapi (feedback_json state batch.tick) batch.feedback in
  let timeline = obj ["profile",str E.timeline_profile;
    "executor",str (F.specification state.domain).executor_identity;
    "horizon",time state batch.tick; "encounters",arr encounters;
    "observations",arr observations; "feedback",arr feedback; "bounds",state.bounds.raw] in
  match E.execute state.behavior timeline with
  | exception Diagnostic.Error diagnostic ->
      Stopped {kind=failure_kind diagnostic; diagnostic; receipt=receipt state timeline None}
  | execution ->
      let receipt = receipt state timeline (Some execution) in
      let frames = items "frames" execution and attempts = items "attempts" execution in
      let previous,current = split (List.length state.frames) frames in
      invariant (List.for_all2 Json.equal state.frames previous)
        "A later closed prefix altered an earlier source frame or source event identity.";
      let frame = match current with [frame] -> frame
        | _ -> Diagnostic.fail "policy_domain_reference_prefix" "Replay must append exactly one inclusive tick frame." in
      invariant (Json.equal (get "time" frame) (time state batch.tick)) "Replay appended a different tick.";
      let creations = creations state batch attempts in
      match F.advance state.domain state.cursor batch ~source_creations:creations with
      | exception Diagnostic.Error diagnostic -> Stopped {kind=failure_kind diagnostic; diagnostic; receipt}
      | cursor ->
          let next = {state with cursor; encounters; observations; feedback;
            frames; attempts; cost=receipt.cumulative} in
          Advanced {next; receipt; frame; creations}
