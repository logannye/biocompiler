open Bioc_wire
module O = Policy_operational

let schema_version = "biocompiler.policy_operating_domain.v0.1"
let profile = "biocompiler.policy_truth_domain.v0.1"
let require = Diagnostic.require
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let get key value = Json.field key (Json.object_fields value)
let name key value = Json.name (get key value)
let items key value = Json.array (get key value)
let exact keys value =
  let actual=List.map fst(Json.object_fields value) in
  require(List.sort String.compare actual=List.sort String.compare keys)
    "policy_domain_representation" "Operating-domain fields differ from the closed schema."
let integer lower upper value =
  let number=Json.integer value in
  require(Z.geq number(Z.of_int lower) && Z.leq number(Z.of_int upper))
    "policy_domain_limit" "Operating-domain integer exceeds its explicit representation bounds.";
  Z.to_int number
let unique code values =
  require(List.length(List.sort_uniq compare values)=List.length values) code "Operating-domain identities or factor values repeat."
let names key value =
  let values=List.map Json.name(items key value) in
  require(values<>[]) "policy_domain_representation" "A finite factor must have a nonempty alphabet.";
  unique "policy_domain_duplicate" values;values
let ticks horizon key value =
  let values=List.map(integer 0 horizon)(items key value) in
  require(values<>[] && List.sort_uniq compare values=values) "policy_domain_representation" "Tick/age sets must be nonempty, sorted and unique.";
  values
let find code identity get values = match List.find_opt(fun value->get value=identity)values with
  | Some value->value | None->Diagnostic.fail code("Unknown operating-domain reference: "^identity)

type evidence = Known of bool | Missing | Invalid | Conflicting
type outcome = Completed | Failed
type lifecycle_action = Keep | Reset | End
type context = Executor | Encounter_slot of string
type encounter = { identity:string; declaration:string; target:string; start_tick:int }
type observation_input = { slot:string; observation:string; available_tick:int; observed_tick:int; evidence:evidence }
type observation_factor = { slots:string list; observation:string; ticks:int list; age_ticks:int list; max_rows_per_slot_tick:int }
type lifecycle_factor = { slots:string list; ticks:int list; actions:lifecycle_action list }
type feedback_factor = { effect_id:string; ticks:int list; outcomes:outcome list; max_rows_per_attempt_tick:int }
type logical_limits = { max_live_encounters:int; max_generations_per_slot:int; max_source_attempts:int }
type t = {
  raw:Json.t; clock:string; executor_role:string; executor_identity:string; horizon_ticks:int;
  encounters:encounter list; fixed_observations:observation_input list;
  observation_factors:observation_factor list; lifecycle_factors:lifecycle_factor list;
  feedback_factors:feedback_factor list; logical_limits:logical_limits;
}
type validated = { domain:t; behavior:O.behavior; resolution:Q.t; validation_id:string }

let evidence_of_json value = match name "status" value,get "value" value with
  | "valid",Json.Bool value->Known value
  | "missing",Json.Null->Missing | "invalid",Json.Null->Invalid | "conflicting",Json.Null->Conflicting
  | _->Diagnostic.fail "policy_domain_evidence" "Evidence requires known Boolean valid values or null missing/invalid/conflicting values; stale is derived from age."
let lifecycle_of_string = function
  | "keep"->Keep | "reset"->Reset | "end"->End
  | _->Diagnostic.fail "policy_domain_unsupported" "Unsupported environment lifecycle action."
let outcome_of_string = function
  | "completed"->Completed | "failed"->Failed
  | _->Diagnostic.fail "policy_domain_unsupported" "Unsupported feedback outcome."
let lifecycle_name = function Keep->"keep" | Reset->"reset" | End->"end"
let outcome_name = function Completed->"completed" | Failed->"failed"
let to_json (domain:t) = domain.raw
let digest (domain:t) = Canonical.fingerprint domain.raw
let specification (validated:validated) = validated.domain
let resolution (validated:validated) = validated.resolution

let of_json raw =
  ignore(Policy_document.document_digest raw);
  exact["schema_version";"profile";"clock";"executor";"horizon_ticks";"encounters";"fixed_observations";
    "observation_factors";"lifecycle_factors";"feedback_factors";"foreign_feedback_factors";"logical_limits"]raw;
  require(name "schema_version" raw=schema_version && name "profile" raw=profile)
    "policy_domain_unsupported" "Unknown operating-domain schema/profile.";
  require(items "foreign_feedback_factors" raw=[]) "policy_domain_unsupported" "Foreign-attempt feedback factors are not implemented in this profile.";
  let horizon_ticks=integer 0 16(get "horizon_ticks" raw) in
  let executor=get "executor" raw in exact["role";"identity"]executor;
  let limits=get "logical_limits" raw in exact["max_live_encounters";"max_generations_per_slot";"max_source_attempts"]limits;
  let logical_limits={max_live_encounters=integer 1 4(get "max_live_encounters" limits);
    max_generations_per_slot=integer 1 4(get "max_generations_per_slot" limits);
    max_source_attempts=integer 1 16(get "max_source_attempts" limits)} in
  let encounter_values=items "encounters" raw in
  require(encounter_values<>[] && List.length encounter_values<=logical_limits.max_live_encounters)
    "policy_domain_limit" "Initial encounter slots exceed the declared live-encounter bound.";
  let encounters=List.map(fun value->exact["identity";"declaration";"target";"start_tick"]value;
    let start_tick=integer 0 horizon_ticks(get "start_tick" value) in
    require(start_tick=0) "policy_domain_unsupported" "This profile creates fixed encounter slots at tick zero.";
    {identity=name "identity" value;declaration=name "declaration" value;target=name "target" value;start_tick})encounter_values in
  unique "policy_domain_duplicate"(List.map(fun(e:encounter)->e.identity)encounters);
  let slot identity=ignore(find "policy_domain_reference" identity(fun(e:encounter)->e.identity)encounters) in
  List.iter(fun key->require(List.length(items key raw)<=128) "policy_domain_limit" "Too many finite operating-domain factors.")
    ["fixed_observations";"observation_factors";"lifecycle_factors";"feedback_factors"];
  let fixed_observations=List.map(fun value->exact["slot";"observation";"available_tick";"observed_tick";"status";"value"]value;
    let identity=name "slot" value in slot identity;
    let available_tick=integer 0 horizon_ticks(get "available_tick" value) and observed_tick=integer 0 horizon_ticks(get "observed_tick" value) in
    require(observed_tick<=available_tick) "policy_domain_causality" "An observation cannot precede its observed timestamp.";
    {slot=identity;observation=name "observation" value;available_tick;observed_tick;evidence=evidence_of_json value})(items "fixed_observations" raw) in
  let factor_slots value=let values=names "slots" value in List.iter slot values;values in
  let observation_factors=List.map(fun value->exact["slots";"observation";"ticks";"alphabet";"age_ticks";"max_rows_per_slot_tick"]value;
    require(name "alphabet" value="known_truth_and_evidence_status.v1") "policy_domain_unsupported" "Unknown finite evidence alphabet.";
    {slots=factor_slots value;observation=name "observation" value;ticks=ticks horizon_ticks "ticks" value;
     age_ticks=ticks horizon_ticks "age_ticks" value;max_rows_per_slot_tick=integer 0 2(get "max_rows_per_slot_tick" value)})(items "observation_factors" raw) in
  let lifecycle_factors=List.map(fun value->exact["slots";"ticks";"actions"]value;
    let actions=List.map lifecycle_of_string(names "actions" value) and selected_ticks=ticks horizon_ticks "ticks" value in
    require(List.mem Keep actions) "policy_domain_continuation" "Lifecycle factors must retain keep as a permitted continuation.";
    require(not(List.mem 0 selected_ticks) || actions=[Keep]) "policy_domain_causality" "Reset/end cannot coincide with the initial encounter birth.";
    {slots=factor_slots value;ticks=selected_ticks;actions})(items "lifecycle_factors" raw) in
  let feedback_factors=List.map(fun value->exact["effect";"ticks";"attempt_selector";"outcomes";"routes";"max_rows_per_attempt_tick"]value;
    require(name "attempt_selector" value="all_previously_created") "policy_domain_unsupported" "Feedback must range over all prior creations, not active or successful attempts.";
    require(names "routes" value=["correlated"]) "policy_domain_unsupported" "Wrong-address feedback routes are not implemented in this profile.";
    {effect_id=name "effect" value;ticks=ticks horizon_ticks "ticks" value;
     outcomes=List.map outcome_of_string(names "outcomes" value);
     max_rows_per_attempt_tick=integer 0 1(get "max_rows_per_attempt_tick" value)})(items "feedback_factors" raw) in
  let observation_coordinates=List.map(fun(o:observation_input)->o.slot,o.observation,o.available_tick)fixed_observations @
    List.concat_map(fun(f:observation_factor)->List.concat_map(fun slot->List.map(fun tick->slot,f.observation,tick)f.ticks)f.slots)observation_factors in
  unique "policy_domain_overlap" observation_coordinates;
  unique "policy_domain_overlap"(List.concat_map(fun(f:lifecycle_factor)->List.concat_map(fun slot->List.map(fun tick->slot,tick)f.ticks)f.slots)lifecycle_factors);
  unique "policy_domain_overlap"(List.concat_map(fun(f:feedback_factor)->List.map(fun tick->f.effect_id,tick)f.ticks)feedback_factors);
  {raw;clock=name "clock" raw;executor_role=name "role" executor;executor_identity=name "identity" executor;
   horizon_ticks;encounters;fixed_observations;observation_factors;lifecycle_factors;feedback_factors;logical_limits}

let validate_for ?charge ~(behavior:O.behavior) (domain:t) =
  (* Domain remains producer/checker independent. The callback counts only the
     compatibility and identity passes; exploration is deliberately untouched. *)
  let metered = Option.is_some charge in
  let charge = Option.value ~default:(fun _ -> ()) charge in
  let rec preflight value = if metered then (
    charge 1;
    match value with
    | Json.String value -> charge (String.length value)
    | Json.Int value -> charge (1 + Z.numbits value)
    | Json.Float _ -> charge 64
    | Json.Array values -> List.iter (fun value -> charge 1; preflight value) values
    | Json.Object fields -> List.iter (fun (key,value) -> charge (1 + String.length key); preflight value) fields
    | Json.Null | Json.Bool _ -> ()) in
  let module List = struct
    include Stdlib.List
    let length values = Stdlib.List.iter (fun _ -> charge 1) values; Stdlib.List.length values
    let iter f values = Stdlib.List.iter (fun value -> charge 1; f value) values
    let filter f values = Stdlib.List.iter (fun _ -> charge 1) values;
      Stdlib.List.filter (fun value -> charge 1; f value) values
    let find_opt f values = Stdlib.List.find_opt (fun value -> charge 1; f value) values
  end in
  let find code identity get values =
    match List.find_opt (fun value -> let candidate=get value in
      charge (String.length candidate); charge (String.length identity); candidate=identity) values with
    | Some value -> value | None -> Diagnostic.fail code ("Unknown operating-domain reference: "^identity) in
  let fingerprint value =
    preflight value; preflight value; Canonical.fingerprint value in
  preflight domain.raw; preflight (O.behavior_to_json behavior);
  let compatible condition message=require condition "policy_domain_source" message in
  compatible(List.length behavior.roles=1 && (List.hd behavior.roles).role_id=domain.executor_role) "Domain executor declaration differs from supplied behavior.";
  compatible(List.length behavior.clocks=1 && (List.hd behavior.clocks).clock_id=domain.clock) "Domain clock differs from supplied behavior.";
  let resolution=(List.hd behavior.clocks).resolution in
  compatible(Q.sign resolution>0) "Source clock resolution must be positive.";
  List.iter(fun(e:encounter)->let source=find "policy_domain_reference" e.declaration(fun(x:O.encounter)->x.encounter_id)behavior.encounters in
    compatible(source.executor=domain.executor_role) "Encounter belongs to another executor.")domain.encounters;
  List.iter(fun(o:O.observation)->require(o.value_type=O.Truth_type) "policy_domain_unsupported" "The finite domain supports truth-valued dynamic observations only.")behavior.observations;
  let check_observation slot identity =
    let instance=find "policy_domain_reference" slot(fun(e:encounter)->e.identity)domain.encounters in
    let observation=find "policy_domain_reference" identity(fun(o:O.observation)->o.observation_id)behavior.observations in
    let subject=find "policy_domain_reference" observation.subject(fun(s:O.subject)->s.subject_id)behavior.subjects in
    compatible(observation.observer=domain.executor_role && observation.clock=domain.clock && subject.encounter=Some instance.declaration)
      "Observation input does not belong to its supplied executor, clock and encounter slot." in
  List.iter(fun(o:observation_input)->check_observation o.slot o.observation)domain.fixed_observations;
  List.iter(fun(f:observation_factor)->List.iter(fun slot->check_observation slot f.observation)f.slots)domain.observation_factors;
  List.iter(fun(f:feedback_factor)->let effect_spec=find "policy_domain_reference" f.effect_id(fun(e:O.effect_spec)->e.effect_id)behavior.effects in
    compatible(effect_spec.executor=domain.executor_role) "Feedback effect belongs to another executor.")domain.feedback_factors;
  List.iter(fun(store:O.state_store)->
    require(store.value_type=O.Truth_type) "policy_domain_unsupported" "Dynamic state in this profile is three-valued truth; fixed text product parameters remain unchanged.";
    let initial_keys=match store.scope with O.Executor _->1 | O.Encounter identity->List.length(List.filter(fun(e:encounter)->e.declaration=identity)domain.encounters) in
    require(initial_keys<=store.capacity) "policy_domain_source_capacity" "Initial live encounter keys exceed source storage capacity; this input domain cannot be pruned to hide the violation.")behavior.stores;
  let validation_id=fingerprint(obj["domain",str(fingerprint domain.raw);"behavior",str(fingerprint(O.behavior_to_json behavior))]) in
  {domain;behavior;resolution;validation_id}

type attempt_key = { context:context; generation:int; effect_id:string; creation_ordinal:int }
type source_creation = { key:attempt_key; source_attempt_id:string; created_tick:int }
type feedback_input = { attempt:source_creation; outcome:outcome }
type input_batch = { tick:int; lifecycle:(string*lifecycle_action)list;
  observations:observation_input list; feedback:feedback_input list; origin:string }
type slot_state = { slot_id:string; active:bool; generation:int; generation_start:int }
type cursor = { validation_id:string; now:int; slots:slot_state list; attempts:source_creation list; prefix_id:string }

let context_json = function Executor->obj["kind",str "executor"] | Encounter_slot identity->obj["kind",str "encounter";"slot",str identity]
let creation_json (creation:source_creation) = obj[
  "context",context_json creation.key.context;"generation",Json.int creation.key.generation;
  "effect",str creation.key.effect_id;"creation_ordinal",Json.int creation.key.creation_ordinal;
  "source_attempt_id",str creation.source_attempt_id;"created_tick",Json.int creation.created_tick]
let observation_json (input:observation_input) =
  let status,value=match input.evidence with Known value->"valid",Json.Bool value | Missing->"missing",Json.Null | Invalid->"invalid",Json.Null | Conflicting->"conflicting",Json.Null in
  obj["slot",str input.slot;"observation",str input.observation;"available_tick",Json.int input.available_tick;
    "observed_tick",Json.int input.observed_tick;"status",str status;"value",value]
let batch_to_json (batch:input_batch) = obj["tick",Json.int batch.tick;"origin",str batch.origin;
  "lifecycle",arr(List.map(fun(slot,action)->obj["slot",str slot;"action",str(lifecycle_name action)])batch.lifecycle);
  "observations",arr(List.map observation_json batch.observations);
  "feedback",arr(List.map(fun(input:feedback_input)->obj["attempt",creation_json input.attempt;"outcome",str(outcome_name input.outcome)])batch.feedback)]
let cursor_digest (cursor:cursor) = cursor.prefix_id
let cursor_tick (cursor:cursor) = cursor.now
let check_cursor (validated:validated) (cursor:cursor) =
  require(validated.validation_id=cursor.validation_id) "policy_domain_cursor" "Cursor belongs to another domain/source compatibility context."
let finished (validated:validated) (cursor:cursor) = check_cursor validated cursor;cursor.now>validated.domain.horizon_ticks
let initial (validated:validated) =
  {validation_id=validated.validation_id;now=0;slots=List.map(fun(e:encounter)->
     {slot_id=e.identity;active=true;generation=0;generation_start=0})validated.domain.encounters;
   attempts=[];prefix_id=Canonical.fingerprint(obj["initial",str validated.validation_id])}
let slot_state (slots:slot_state list) identity = find "policy_domain_reference" identity(fun(s:slot_state)->s.slot_id)slots
let apply_lifecycle now slots actions = List.map(fun(state:slot_state)->
  match List.assoc state.slot_id actions with
  | Keep->state | End->{state with active=false}
  | Reset->{state with generation=state.generation+1;generation_start=now})slots
let singleton value () = Seq.Cons(value,Seq.empty)
let rec concat_map f values () = match values() with
  | Seq.Nil->Seq.Nil | Seq.Cons(value,rest)->Seq.append(f value)(concat_map f rest)()
let rec products = function
  | []->singleton []
  | factor::rest->concat_map(fun value->Seq.map(fun tail->value::tail)(products rest))factor
let rec rows alphabet length = if length=0 then singleton [] else
  concat_map(fun value->Seq.map(fun tail->value::tail)(rows alphabet(length-1)))(List.to_seq alphabet)
let bounded_rows alphabet maximum = concat_map(rows alphabet)(List.to_seq(List.init(maximum+1)Fun.id))

let choices (validated:validated) (cursor:cursor) =
  check_cursor validated cursor;
  if finished validated cursor then Seq.empty else
  let domain=validated.domain in
  let lifecycle_options=List.map(fun(state:slot_state)->
    let factor=List.find_opt(fun(f:lifecycle_factor)->List.mem state.slot_id f.slots && List.mem cursor.now f.ticks)domain.lifecycle_factors in
    let actions=match factor with None->[Keep] | Some factor when state.active->List.filter(function
      | Keep->true | End->cursor.now>0 | Reset->cursor.now>0 && state.generation+1<domain.logical_limits.max_generations_per_slot)factor.actions
      | Some _->[Keep] in
    List.to_seq(List.map(fun action->state.slot_id,action)actions))cursor.slots in
  concat_map(fun lifecycle->
    let next_slots=apply_lifecycle cursor.now cursor.slots lifecycle in
    let fixed=List.filter(fun(o:observation_input)->o.available_tick=cursor.now)domain.fixed_observations in
    List.iter(fun(o:observation_input)->let state=slot_state next_slots o.slot in
      require(state.active && o.observed_tick>=state.generation_start) "policy_domain_contradiction"
        "A fixed observation conflicts with a permitted encounter end/reset prefix; the branch cannot be discarded.")fixed;
    let observation_options=List.concat_map(fun(f:observation_factor)->if not(List.mem cursor.now f.ticks)then[]else
      List.map(fun slot->let state=slot_state next_slots slot in
        let alphabet=if not state.active then[]else List.concat_map(fun age->
          if age>cursor.now-state.generation_start then[]else
          List.map(fun evidence->{slot;observation=f.observation;available_tick=cursor.now;observed_tick=cursor.now-age;evidence})
            [Known false;Known true;Missing;Invalid;Conflicting])f.age_ticks in
        bounded_rows alphabet f.max_rows_per_slot_tick)f.slots)domain.observation_factors in
    let feedback_options=List.map(fun(attempt:source_creation)->
      let factor=List.find_opt(fun(f:feedback_factor)->f.effect_id=attempt.key.effect_id && List.mem cursor.now f.ticks)domain.feedback_factors in
      match factor with None->singleton[] | Some factor->
        bounded_rows(List.map(fun outcome->{attempt;outcome})factor.outcomes)factor.max_rows_per_attempt_tick)cursor.attempts in
    concat_map(fun observations->Seq.map(fun feedback->{tick=cursor.now;lifecycle;
      observations=fixed@List.concat observations;feedback=List.concat feedback;origin=cursor.prefix_id})(products feedback_options))
      (products observation_options))(products lifecycle_options)

let advance (validated:validated) (cursor:cursor) (batch:input_batch) ~source_creations =
  check_cursor validated cursor;
  require(not(finished validated cursor) && batch.origin=cursor.prefix_id && batch.tick=cursor.now)
    "policy_domain_cursor" "Input batch belongs to another causal prefix or a finished domain.";
  require(List.length source_creations<=validated.domain.logical_limits.max_source_attempts-List.length cursor.attempts)
    "policy_domain_source_bound" "Source attempt creations exceed the declared logical bound; retaining only a smaller input domain is forbidden.";
  let next_slots=apply_lifecycle cursor.now cursor.slots batch.lifecycle in
  let all=cursor.attempts@source_creations in
  unique "policy_domain_causality"(List.map(fun(c:source_creation)->c.source_attempt_id)all);
  unique "policy_domain_causality"(List.map(fun(c:source_creation)->c.key)all);
  List.iteri(fun index (creation:source_creation)->
    ignore(Json.name(str creation.source_attempt_id));
    require(creation.created_tick=cursor.now && creation.key.creation_ordinal=List.length cursor.attempts+index+1)
      "policy_domain_causality" "Source creations must have this tick and the next global creation ordinal.";
    let effect_spec=find "policy_domain_reference" creation.key.effect_id(fun(e:O.effect_spec)->e.effect_id)validated.behavior.effects in
    let subject_encounter=if effect_spec.subject=validated.domain.executor_role then None else
      let subject=find "policy_domain_reference" effect_spec.subject(fun(s:O.subject)->s.subject_id)validated.behavior.subjects in
      subject.encounter in
    let correct_scope=match creation.key.context with
      | Executor->creation.key.generation=0 && subject_encounter=None
      | Encounter_slot identity->let state=slot_state next_slots identity in
          let instance=find "policy_domain_reference" identity(fun(e:encounter)->e.identity)validated.domain.encounters in
          state.active && state.generation=creation.key.generation && subject_encounter=Some instance.declaration in
    require(effect_spec.executor=validated.domain.executor_role && correct_scope)
      "policy_domain_causality" "Source creation crosses its effect subject, live encounter or generation." )source_creations;
  let prefix_id=Canonical.fingerprint(obj["previous",str cursor.prefix_id;"inputs",batch_to_json batch;
    "source_creations",arr(List.map creation_json source_creations)]) in
  {cursor with now=cursor.now+1;slots=next_slots;attempts=all;prefix_id}
