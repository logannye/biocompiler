open Bioc_wire
module D = Bioc_domain.Policy_document
module O = Bioc_domain.Policy_operational
module F = Bioc_domain.Policy_operating_domain
module A = Bioc_checker.Policy_admission
module L = Bioc_compiler.Policy_lowering
module C = Bioc_checker.Policy_correspondence

let require condition message = if not condition then failwith message
let str value = Json.String value
let arr values = Json.Array values
let obj fields = Json.Object fields
let get name value = Json.field name(Json.object_fields value)
let items name value = Json.array(get name value)
let replace key replacement value = obj(List.map(fun(name,item)->name,if name=key then replacement else item)(Json.object_fields value))
let replace_first key transform raw = match items key raw with
  | first::rest->replace key(arr(transform first::rest))raw
  | []->failwith "Literal factor is absent"
let read path = let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_bounded ~max_bytes:(2*1024*1024) ~max_nodes:100000(really_input_string channel(in_channel_length channel)))
let rejects code action = match action()with
  | _->failwith("Expected domain rejection: "^code)
  | exception Diagnostic.Error diagnostic->require(diagnostic.code=code)("Wrong rejection: "^diagnostic.code^" expected "^code)
let compiled fixture =
  let document=D.of_json(get "document" fixture) and descriptors=O.descriptors_of_json(get "definitions" fixture) in
  let behavior=L.lower(A.admit ~document ~descriptors) in
  ignore(C.check ~expected_document:document ~descriptors behavior);behavior
let batches domain cursor = List.of_seq(F.choices domain cursor)
let only values = match values with [value]->value | _->failwith "Expected one deterministic input batch"
let choose predicate values = List.find predicate values
let no_observations (batch:F.input_batch) = batch.observations=[]
let keep (batch:F.input_batch) = List.for_all(fun(_,action)->action=F.Keep)batch.lifecycle
let no_feedback (batch:F.input_batch) = batch.feedback=[]
let advance domain cursor batch = F.advance domain cursor batch ~source_creations:[]
let creation slot ordinal tick : F.source_creation = {
  key={context=F.Encounter_slot slot;generation=0;effect_id="response";creation_ordinal=ordinal};
  source_attempt_id="source/"^string_of_int ordinal;created_tick=tick;
}
let at_one domain = let zero=F.initial domain in advance domain zero(only(batches domain zero))
let at_three_without_attempts domain =
  let one=at_one domain in
  let two=advance domain one(choose(fun batch->keep batch && no_observations batch)(batches domain one)) in
  advance domain two(only(batches domain two))

let run raw fixture =
  let behavior=compiled fixture in
  let specification=F.of_json raw in
  let domain=F.validate_for ~behavior specification in
  require(Json.equal(F.to_json specification)raw)"Domain decoder lost original authority";
  require(F.digest specification=Canonical.fingerprint raw)"Domain identity differs from complete canonical authority";
  require(F.digest specification="74408eecc735967f39c283fdc1ad7c688d3beb567222f5bd0033a0d17b013e1d")
    "Canonical domain identity differs from the independently frozen JSON SHA-256";
  require(F.digest(F.of_json(obj(List.rev(Json.object_fields raw))))=F.digest specification)"JSON field order changed canonical domain identity";
  require(F.digest(F.of_json(replace "horizon_ticks"(Json.int 5)raw))<>F.digest specification)"Changed time domain retained an old identity";
  require(Q.equal(F.resolution domain)Q.one)"Domain discarded exact source clock quantum";
  let validate raw=F.validate_for ~behavior(F.of_json raw) in
  rejects "policy_domain_representation"(fun()->F.of_json(obj(("exploration_budget",obj[])::Json.object_fields raw)));
  rejects "policy_domain_duplicate"(fun()->F.of_json(replace "encounters"(arr[List.hd(items "encounters" raw);List.hd(items "encounters" raw)])raw));
  rejects "policy_domain_overlap"(fun()->F.of_json(replace "observation_factors"(arr(items "observation_factors" raw@items "observation_factors" raw))raw));
  rejects "policy_domain_overlap"(fun()->F.of_json(replace "fixed_observations"(arr(items "fixed_observations" raw@[List.hd(items "fixed_observations" raw)]))raw));
  rejects "policy_domain_reference"(fun()->F.of_json(replace_first "observation_factors"(replace "slots"(arr[str "absent"]))raw));
  rejects "policy_domain_reference"(fun()->validate(replace_first "observation_factors"(replace "observation"(str "absent"))raw));
  rejects "policy_domain_source"(fun()->validate(replace "clock"(str "another_clock")raw));
  rejects "policy_domain_representation"(fun()->F.of_json(replace_first "observation_factors"(replace "ticks"(arr[Json.int 1;Json.int 1]))raw));
  rejects "policy_domain_unsupported"(fun()->F.of_json(replace_first "feedback_factors"(replace "routes"(arr[str "correlated";str "wrong_target"]))raw));
  rejects "policy_domain_unsupported"(fun()->F.of_json(replace_first "feedback_factors"(replace "attempt_selector"(str "active_only"))raw));
  rejects "policy_domain_unsupported"(fun()->F.of_json(replace "foreign_feedback_factors"(arr[obj[]])raw));
  rejects "policy_domain_continuation"(fun()->F.of_json(replace_first "lifecycle_factors"(replace "actions"(arr[str "reset";str "end"]))raw));
  rejects "policy_domain_causality"(fun()->F.of_json(replace_first "fixed_observations"(replace "observed_tick"(Json.int 1))raw));
  List.iter(fun change->rejects "policy_domain_evidence"(fun()->F.of_json(replace_first "fixed_observations" change raw)))
    [replace "status"(str "stale");replace "value"(str "unknown");replace "status"(str "invalid")];
  let original=get "document" fixture in
  let narrow=replace "declarations"(arr(List.map(fun declaration->if get "id" declaration=str "seen" then replace "capacity"(Json.int 1)declaration else declaration)(items "declarations" original)))original in
  let narrow_behavior=compiled(replace "document" narrow fixture) in
  rejects "policy_domain_source_capacity"(fun()->F.validate_for ~behavior:narrow_behavior specification);
  let zero=F.initial domain in
  let initial_batch=only(batches domain zero) in
  require(List.length initial_batch.observations=2 && List.for_all(fun(o:F.observation_input)->o.evidence=F.Known false && o.observed_tick=0)initial_batch.observations)
    "Initial evidence differs from the independent known-false literal";
  rejects "policy_domain_causality"(fun()->F.advance domain zero initial_batch ~source_creations:[creation "e1" 1 1]);
  let one=advance domain zero initial_batch in
  let choices=batches domain one in
  require(List.length choices=36)"Two independent five-row alphabets plus silence did not produce 36 batches";
  require(List.for_all no_feedback choices)"Feedback was invented before any source creation";
  let alphabet=List.sort_uniq compare(List.filter_map(fun(batch:F.input_batch)->
    match List.filter(fun(o:F.observation_input)->o.slot="e1")batch.observations with []->Some None | [row]->Some(Some row.evidence) | _->None)choices) in
  require(alphabet=List.sort compare[None;Some(F.Known false);Some(F.Known true);Some F.Missing;Some F.Invalid;Some F.Conflicting])
    "Finite factor omitted an evidence class or confused truth Unknown with missing evidence";
  let both_true=choose(fun(batch:F.input_batch)->List.length batch.observations=2 && List.for_all(fun(o:F.observation_input)->o.evidence=F.Known true)batch.observations)choices in
  rejects "policy_domain_causality"(fun()->F.advance domain one both_true ~source_creations:[creation "e1" 2 1]);
  let executor_creation={ (creation "e1" 1 1) with key={context=F.Executor;generation=0;effect_id="response";creation_ordinal=1} } in
  rejects "policy_domain_causality"(fun()->F.advance domain one both_true ~source_creations:[executor_creation]);
  let creations=[creation "e1" 1 1;creation "e2" 2 1] in
  let two=F.advance domain one both_true ~source_creations:creations in
  require(List.length(batches domain two)=9)"Prior attempts did not independently permit absent, completed and failed feedback";
  let completed=choose(fun(batch:F.input_batch)->List.length batch.feedback=2 && List.for_all(fun(f:F.feedback_input)->f.outcome=F.Completed)batch.feedback)(batches domain two) in
  let three=advance domain two completed in
  let next=batches domain three in
  require(List.length next=81)"Completed attempts were filtered out, or reset/end factors lost their independent choices";
  let reset_feedback=choose(fun(batch:F.input_batch)->List.assoc "e1" batch.lifecycle=F.Reset && List.length batch.feedback=2)next in
  require(List.for_all(fun(f:F.feedback_input)->f.attempt.key.generation=0)reset_feedback.feedback)"Same-tick reset rewrote old feedback into a new generation";
  rejects "policy_domain_cursor"(fun()->advance domain three initial_batch);
  rejects "policy_domain_source_bound"(fun()->F.advance domain three reset_feedback ~source_creations:[creation "e1" 3 3]);
  let tighter=validate(replace "logical_limits"(replace "max_source_attempts"(Json.int 1)(get "logical_limits" raw))raw) in
  let tighter_one=at_one tighter in
  let tighter_choices=batches tighter tighter_one in
  require(List.length tighter_choices=36)"Source-output bound pruned environmental input choices";
  let tighter_true=choose(fun(batch:F.input_batch)->List.length batch.observations=2 && List.for_all(fun(o:F.observation_input)->o.evidence=F.Known true)batch.observations)tighter_choices in
  rejects "policy_domain_source_bound"(fun()->F.advance tighter tighter_one tighter_true ~source_creations:creations);
  let one_true=choose(fun(batch:F.input_batch)->match batch.observations with [row]->row.slot="e1" && row.evidence=F.Known true | _->false)choices in
  let single_two=F.advance domain one one_true ~source_creations:[creation "e1" 1 1] in
  let single_two_batch=choose no_feedback(batches domain single_two) in
  let duplicate={ (creation "e1" 2 2) with source_attempt_id="source/1" } in
  rejects "policy_domain_causality"(fun()->F.advance domain single_two single_two_batch ~source_creations:[duplicate]);
  let single_three=advance domain single_two single_two_batch in
  let ended=choose(fun(batch:F.input_batch)->List.assoc "e1" batch.lifecycle=F.End && no_feedback batch)(batches domain single_three) in
  rejects "policy_domain_causality"(fun()->F.advance domain single_three ended ~source_creations:[creation "e1" 2 3]);
  let reset=choose(fun(batch:F.input_batch)->List.assoc "e1" batch.lifecycle=F.Reset && no_feedback batch)(batches domain single_three) in
  rejects "policy_domain_causality"(fun()->F.advance domain single_three reset ~source_creations:[creation "e1" 2 3]);
  let next_generation={ (creation "e1" 2 3) with key={context=F.Encounter_slot "e1";generation=1;effect_id="response";creation_ordinal=2} } in
  let four=F.advance domain single_three reset ~source_creations:[next_generation] in
  require(F.cursor_tick four=4 && List.length(batches domain four)=1)"Idle tick or fresh reset generation was lost";
  let done_cursor=advance domain four(only(batches domain four)) in
  require(F.finished domain done_cursor && batches domain done_cursor=[])"Enumeration continued beyond its exact inclusive horizon";
  rejects "policy_domain_cursor"(fun()->F.choices tighter one);
  let multiplicity=validate(replace_first "observation_factors"(replace "max_rows_per_slot_tick"(Json.int 2))raw) in
  let expanded=batches multiplicity(at_one multiplicity) in
  require(List.length expanded=961)"Ordered input multiplicities were reduced or not exhaustively generated";
  let has_pair values=List.exists(fun(batch:F.input_batch)->List.filter_map(fun(o:F.observation_input)->if o.slot="e1"then Some o.evidence else None)batch.observations=values)expanded in
  require(has_pair[F.Known false;F.Known true] && has_pair[F.Known true;F.Known false])"Opposing simultaneous occurrence orders disappeared";
  let limited=validate(replace "logical_limits"(replace "max_generations_per_slot"(Json.int 1)(get "logical_limits" raw))raw) in
  require(List.length(batches limited(at_three_without_attempts limited))=4)"Generation bound did not leave keep/end continuations";
  let age_factor=List.hd(items "observation_factors" raw)|>replace "ticks"(arr[Json.int 3])|>replace "age_ticks"(arr[Json.int 0;Json.int 1;Json.int 2]) in
  let aged=validate(raw|>replace "observation_factors"(arr[age_factor])|>replace "lifecycle_factors"(arr[])) in
  let aged_three=at_three_without_attempts aged in
  let aged_choices=batches aged aged_three in
  require(List.length aged_choices=256)"Finite ages and evidence classes were not combined exhaustively";
  require(List.exists(fun(batch:F.input_batch)->List.exists(fun(o:F.observation_input)->o.evidence=F.Known true && o.observed_tick=1 && o.available_tick=3)batch.observations)aged_choices)
    "Old valid evidence lost the timestamps needed for source-derived staleness";
  let early_end=List.hd(items "lifecycle_factors" raw)|>replace "ticks"(arr[Json.int 1]) in
  let contradictory=validate(replace "lifecycle_factors"(arr[early_end])raw) in
  let contradictory_one=at_one contradictory in
  let ending=choose(fun(batch:F.input_batch)->List.assoc "e1" batch.lifecycle=F.End)(batches contradictory contradictory_one) in
  let contradictory_two=advance contradictory contradictory_one ending in
  rejects "policy_domain_contradiction"(fun()->batches contradictory contradictory_two);
  let old_fixed=List.map(fun input->if get "slot" input=str "e1" && get "available_tick" input=Json.int 2
    then replace "observed_tick"(Json.int 0)input else input)(items "fixed_observations" raw) in
  let reset_contradiction=validate(raw|>replace "fixed_observations"(arr old_fixed)|>replace "lifecycle_factors"(arr[early_end])) in
  let before_reset=at_one reset_contradiction in
  let resetting=choose(fun(batch:F.input_batch)->List.assoc "e1" batch.lifecycle=F.Reset)(batches reset_contradiction before_reset) in
  let after_reset=advance reset_contradiction before_reset resetting in
  rejects "policy_domain_contradiction"(fun()->batches reset_contradiction after_reset);
  (* This is a literal creation callback for an environment census, not a source
     evaluator or evidence that a policy/implementation satisfies requirements. *)
  let prefixes=ref 0 and terminals=ref 0 in
  let rec visit cursor =
    incr prefixes;
    if F.finished domain cursor then incr terminals else
      Seq.iter(fun(batch:F.input_batch)->
        let creations=if batch.tick<>1 then[]else
          List.filter_map(fun slot->if List.exists(fun(o:F.observation_input)->o.slot=slot && o.evidence=F.Known true)batch.observations then Some slot else None)["e1";"e2"]
          |>List.mapi(fun index slot->creation slot(index+1)1) in
        visit(F.advance domain cursor batch ~source_creations:creations))(F.choices domain cursor) in
  visit(F.initial domain);
  require(!terminals=1764 && !prefixes=3630)"Complete independent factor census changed (expected 1764 histories / 3630 prefixes)";
  Printf.printf "Finite policy environment: %d literal histories, %d prefixes; no preservation or requirement acceptance claimed\n" !terminals !prefixes

let () =
  require(Array.length Sys.argv=3)"Expected operating-domain and original operational-source fixtures";
  run(read Sys.argv.(1))(read Sys.argv.(2))
