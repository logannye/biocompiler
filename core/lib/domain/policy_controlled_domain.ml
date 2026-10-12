open Bioc_wire

let schema_version = "biocompiler.policy_controlled_composition_domain.v0.1"
let profile = "biocompiler.policy_controlled_composition_mrna.v0.1"
type input_key = Antigen | Controller | Rna_a | Rna_b | Protein_a | Protein_b
type physical = { antigen:bool; controller:bool; rna_a:bool; rna_b:bool; protein_a:bool; protein_b:bool }
type evidence_quality = Valid | Missing | Invalid | Conflicting
type evidence = { status:evidence_quality; observed_tick:int option; generation:int option }
type effective_evidence = Fresh of evidence_quality | Stale
type lifecycle = None_event | Start | End | Reset
type bindings = {
  clock:string; executor_role:string; executor_identity:string; slot:string;
  encounter_declaration:string; encounter_subject:string; antigen_observation:string;
  controller_observation:string; antigen_freshness_ticks:int; controller_freshness_ticks:int;
  member_a:string; member_b:string; product_a:string; product_b:string;
}
type deadlines = { onset_ticks:int; controller_off_ticks:int; antigen_off_ticks:int;
  component_off_ticks:int; reactivation_ticks:int }
type physical_factor = { p_input:input_key; p_ticks:int list; p_values:bool list }
type evidence_factor = { e_input:input_key; e_ticks:int list;
  e_statuses:evidence_quality list; e_ages:int list }
type lifecycle_factor = { l_ticks:int list; l_actions:lifecycle list }
type fixed_input = { f_tick:int; f_event:lifecycle; f_physical:physical;
  f_evidence:(input_key * evidence) list }
type limits = { max_generations:int; max_prefixes:int; max_transitions:int;
  max_histories:int; max_work:int }
type t = { raw:Json.t; identity:string; decoded_work:int; bindings:bindings;
  resolution:Json.t; deadlines:deadlines; cutoff:int; horizon:int;
  freshness:(input_key * int) list; initial_physical:physical;
  initial_evidence:(input_key * evidence) list; physical_factors:physical_factor list;
  evidence_factors:evidence_factor list; lifecycle_factors:lifecycle_factor list;
  fixed_inputs:fixed_input list; limits:limits }
type validated = Validated of t
type metadata = { domain_fingerprint:string; fixed_input_count:int;
  physical_factor_count:int; evidence_factor_count:int; lifecycle_factor_count:int }
type input_batch = { tick:int; event:lifecycle; live:bool; generation:int;
  generation_started_tick:int; physical:physical; evidence:(input_key * evidence) list; origin:string; origin_domain:string }
type cursor = { domain:string; lineage:string; next_tick:int; c_live:bool; c_generation:int;
  c_generation_started_tick:int; c_physical:physical; c_evidence:(input_key * evidence) list }
type usage = { prefixes:int; transitions:int; histories:int; work:int }
type enumeration = Complete of usage | Exhausted of usage | Cancelled of usage

let keys = [Antigen;Controller;Rna_a;Rna_b;Protein_a;Protein_b]
let key_name = function Antigen->"antigen"|Controller->"controller"|Rna_a->"rna_a"
  |Rna_b->"rna_b"|Protein_a->"protein_a"|Protein_b->"protein_b"
let key_names = List.map key_name keys
let str value = Json.String value
let obj fields = Json.Object fields
let get key raw = Json.field key(Json.object_fields raw)
let exact fields raw = Json.exact_fields fields(Json.object_fields raw)
let require condition message = Diagnostic.require condition "policy_controlled_domain" message
let contradiction condition message = Diagnostic.require condition "policy_controlled_domain_contradiction" message
let noop _ = ()
let bounded maximum raw =
  let value=Json.integer raw in
  require(Z.sign value>=0 && Z.compare value(Z.of_int maximum)<=0)"Controlled-domain integer exceeds its explicit profile bound.";
  Z.to_int value
let positive maximum raw = let value=bounded maximum raw in require(value>0)"Controlled-domain limit/deadline must be positive.";value
let name raw = let value=Json.name raw in require(String.length value<=256)"Controlled-domain name exceeds 256 bytes.";value
let unique values = List.length(List.sort_uniq compare values)=List.length values
let nonempty_unique values = require(values<>[] && unique values)"Controlled-domain choice lists must be nonempty and unique.";values
let ascending values = require(values<>[] && List.sort_uniq Int.compare values=values)"Controlled-domain tick/age lists must be nonempty, ascending and unique.";values
let key raw = let value=Json.string raw in
  match List.find_opt(fun item->key_name item=value)keys with Some item->item
  |None->Diagnostic.fail "policy_controlled_domain" "Unknown controlled-domain input key."
let physical_value input raw = match input,Json.string raw with
  |Controller,"disabled"->false|Controller,"enabled"->true
  |(Antigen|Rna_a|Rna_b|Protein_a|Protein_b),"absent"->false
  |(Antigen|Rna_a|Rna_b|Protein_a|Protein_b),"present"->true
  |_->Diagnostic.fail "policy_controlled_domain" "Physical values must use the exact input alphabet."
let value_at physical = function Antigen->physical.antigen|Controller->physical.controller
  |Rna_a->physical.rna_a|Rna_b->physical.rna_b|Protein_a->physical.protein_a|Protein_b->physical.protein_b
let with_value physical input value = match input with
  |Antigen->{physical with antigen=value}|Controller->{physical with controller=value}
  |Rna_a->{physical with rna_a=value}|Rna_b->{physical with rna_b=value}
  |Protein_a->{physical with protein_a=value}|Protein_b->{physical with protein_b=value}
let physical_json physical = obj(List.map(fun input->key_name input,
  str(match input,value_at physical input with Controller,true->"enabled"|Controller,false->"disabled"
    |_,true->"present"|_,false->"absent"))keys)
let physical raw = exact key_names raw;
  let read input=physical_value input(get(key_name input)raw)in
  {antigen=read Antigen;controller=read Controller;rna_a=read Rna_a;rna_b=read Rna_b;
   protein_a=read Protein_a;protein_b=read Protein_b}
let quality raw = match Json.string raw with "valid"->Valid|"missing"->Missing
  |"invalid"->Invalid|"conflicting"->Conflicting
  |_->Diagnostic.fail "policy_controlled_domain" "Unknown authored evidence status; stale is derived, not authored."
let quality_name = function Valid->"valid"|Missing->"missing"|Invalid->"invalid"|Conflicting->"conflicting"
let lifecycle raw = match Json.string raw with "none"->None_event|"start"->Start|"end"->End|"reset"->Reset
  |_->Diagnostic.fail "policy_controlled_domain" "Unknown controlled-domain lifecycle event."
let lifecycle_name = function None_event->"none"|Start->"start"|End->"end"|Reset->"reset"
let missing = {status=Missing;observed_tick=None;generation=None}
let optional_int maximum = function Json.Null->None|value->Some(bounded maximum value)
let option_json = function None->Json.Null|Some value->Json.int value
let evidence_json value = obj["status",str(quality_name value.status);
  "observed_tick",option_json value.observed_tick;"generation",option_json value.generation]
let evidence_map_json values = obj(List.map(fun(input,value)->key_name input,evidence_json value)values)
let evidence input ~tick raw =
  exact["status";"observed_tick";"generation"]raw;
  let status=quality(get "status" raw)and observed_tick=optional_int 64(get "observed_tick" raw)
  and generation=optional_int 16(get "generation" raw)in
  (match status,observed_tick,generation,input with
  |Missing,None,None,_->()
  |(Valid|Invalid|Conflicting),Some observed,Some _,Antigen->
      require(observed<=tick)"Evidence cannot be future dated."
  |(Valid|Invalid|Conflicting),Some observed,None,(Controller|Rna_a|Rna_b|Protein_a|Protein_b)->
      require(observed<=tick)"Evidence cannot be future dated."
  |_->Diagnostic.fail "policy_controlled_domain" "Evidence timestamp/generation contradicts its status or owner.");
  {status;observed_tick;generation}
let evidence_map ~tick raw = exact key_names raw;
  List.map(fun input->input,evidence input ~tick(get(key_name input)raw))keys
let decimal raw = let text=Json.string raw in require(String.length text<=256)"Clock decimal exceeds its bound.";
  Policy_document.exact_decimal text
let clock_resolution raw =
  exact["$type";"amount";"unit"]raw;
  require(get "$type" raw=str "Quantity")"Clock resolution requires a complete Quantity record.";
  let unit=get "unit" raw in exact["$type";"id";"dimension";"quantity_kind";"scale";"reference"]unit;
  ignore(name(get "id" unit));
  require(get "$type" unit=str "Unit" && get "dimension" unit=str "time" &&
    get "quantity_kind" unit=str "duration" && get "reference" unit=Json.Null)
    "Clock resolution requires an exact time/duration Unit with null reference.";
  require(Q.sign(decimal(get "amount" raw))>0 && Q.sign(decimal(get "scale" unit))>0)
    "Clock resolution amount and scale must be positive.";raw
let deadlines raw =
  exact["onset_ticks";"controller_off_ticks";"antigen_off_ticks";"component_off_ticks";"reactivation_ticks"]raw;
  {onset_ticks=positive 64(get "onset_ticks" raw);controller_off_ticks=positive 64(get "controller_off_ticks" raw);
   antigen_off_ticks=positive 64(get "antigen_off_ticks" raw);component_off_ticks=positive 64(get "component_off_ticks" raw);
   reactivation_ticks=positive 64(get "reactivation_ticks" raw)}
let ticks maximum raw = ascending(List.map(bounded maximum)(Json.array raw))
let rows maximum raw = let values=Json.array raw in
  require(List.length values<=maximum)"Controlled-domain factor/frame inventory exceeds its closed bound.";values
let charged_fingerprint charge raw =
  let bytes=Policy_material_request.preflight ~max_bytes:1048576 ~max_nodes:100000 ~max_depth:32 ~charge raw in
  charge bytes;
  let encoded=Canonical.encode_bounded ~max_bytes:1048576 raw in
  require(String.length encoded=bytes)"Domain canonical accounting differs from its preflight.";
  charge bytes;Canonical.sha256 encoded
let of_json ?(charge=noop) raw =
  let decoding=ref 0 in
  let debit amount=charge amount;decoding:= !decoding+amount in
  ignore(Policy_material_request.preflight ~max_bytes:1048576 ~max_nodes:100000 ~max_depth:32 ~charge:debit raw);
  exact["schema_version";"profile";"clock";"executor";"encounter";"inputs";"source_deadlines";
    "intervention_cutoff_tick";"horizon_tick";"suffix_policy";"initial";"physical_factors";
    "evidence_factors";"lifecycle_factors";"fixed_inputs";"limits"]raw;
  require(get "schema_version" raw=str schema_version && get "profile" raw=str profile)"Unknown controlled-domain schema/profile.";
  let clock=get "clock" raw and executor=get "executor" raw and encounter=get "encounter" raw in
  exact["id";"resolution"]clock;exact["role";"identity"]executor;exact["slot";"declaration";"subject"]encounter;
  let resolution=clock_resolution(get "resolution" clock)in
  let inputs=Json.array(get "inputs" raw)in require(List.length inputs=6)"All six ordered controlled inputs are required.";
  let references=List.map2(fun expected row->
    exact["key";"reference";"scope";"freshness_ticks"]row;
    require(key(get "key" row)=expected)"Controlled input inventory/order differs from the closed profile.";
    require(get "scope" row=str(if expected=Antigen then "encounter" else "executor"))"Controlled input has a foreign owner scope.";
    let reference=get "reference" row in exact["$type";"id";"kind"]reference;
    let kind=match expected with Antigen|Controller->"Observation"|Rna_a|Rna_b->"MaterialMember"|Protein_a|Protein_b->"Parameter"in
    require(get "$type" reference=str "Ref" && get "kind" reference=str kind)"Controlled input requires the original typed reference.";
    expected,name(get "id" reference),bounded 64(get "freshness_ticks" row))keys inputs in
  let reference input=let _,id,_=List.find(fun(item,_,_)->item=input)references in id in
  let freshness input=let _,_,value=List.find(fun(item,_,_)->item=input)references in value in
  require(reference Antigen<>reference Controller && reference Rna_a<>reference Rna_b && reference Protein_a<>reference Protein_b)
    "Each same-kind controlled input requires a distinct original identity.";
  let bindings={clock=name(get "id" clock);executor_role=name(get "role" executor);executor_identity=name(get "identity" executor);
    slot=name(get "slot" encounter);encounter_declaration=name(get "declaration" encounter);encounter_subject=name(get "subject" encounter);
    antigen_observation=reference Antigen;controller_observation=reference Controller;member_a=reference Rna_a;member_b=reference Rna_b;
    product_a=reference Protein_a;product_b=reference Protein_b;
    antigen_freshness_ticks=freshness Antigen;controller_freshness_ticks=freshness Controller}in
  let deadlines=deadlines(get "source_deadlines" raw)in
  let cutoff=bounded 32(get "intervention_cutoff_tick" raw)and horizon=positive 64(get "horizon_tick" raw)in
  let suffix=max deadlines.controller_off_ticks(max deadlines.antigen_off_ticks deadlines.component_off_ticks)+
    max deadlines.onset_ticks deadlines.reactivation_ticks in
  require(cutoff<horizon && horizon-cutoff>=suffix)"Hold suffix cannot cover every original source deadline.";
  require(get "suffix_policy" raw=str "hold_last_physical_inputs_no_encounter_events")"Unknown controlled-domain suffix policy.";
  let initial=get "initial" raw in exact["physical";"evidence"]initial;
  let initial_physical=physical(get "physical" initial)and initial_evidence=evidence_map ~tick:0(get "evidence" initial)in
  require(not initial_physical.antigen && List.for_all(fun(_,value)->value=missing)initial_evidence)
    "Initial idle slot requires absent antigen and explicitly missing evidence.";
  let physical_factors=List.map(fun row->debit 1;exact["input";"ticks";"values"]row;
    let p_input=key(get "input" row)in
    {p_input;p_ticks=ticks cutoff(get "ticks" row);p_values=nonempty_unique(List.map(physical_value p_input)(Json.array(get "values" row)))})
    (rows 6(get "physical_factors" raw))in
  require(unique(List.map(fun row->row.p_input)physical_factors))"Physical factors repeat an input.";
  let evidence_factors=List.map(fun row->debit 1;exact["input";"ticks";"statuses";"age_ticks"]row;
    let e_input=key(get "input" row)and e_ticks=ticks horizon(get "ticks" row)
    and e_statuses=nonempty_unique(List.map quality(Json.array(get "statuses" row)))and e_ages=ticks 64(get "age_ticks" row)in
    require(List.for_all(fun age->List.for_all(fun tick->age<=tick)e_ticks)e_ages)"Evidence factor would produce a future observation.";
    {e_input;e_ticks;e_statuses;e_ages})(rows 6(get "evidence_factors" raw))in
  require(unique(List.map(fun row->row.e_input)evidence_factors))"Evidence factors repeat an input.";
  let lifecycle_factors=List.map(fun row->debit 1;exact["ticks";"actions"]row;
    let l_ticks=ticks cutoff(get "ticks" row)and l_actions=nonempty_unique(List.map lifecycle(Json.array(get "actions" row)))in
    require(not(List.mem None_event l_actions))"Lifecycle none is implicit, not an authored factor action.";
    {l_ticks;l_actions})(rows 33(get "lifecycle_factors" raw))in
  require(unique(List.concat_map(fun row->row.l_ticks)lifecycle_factors))"Lifecycle factor ticks overlap.";
  let factor_ticks=List.concat_map(fun row->row.p_ticks)physical_factors@
    List.concat_map(fun row->row.e_ticks)evidence_factors@List.concat_map(fun row->row.l_ticks)lifecycle_factors in
  let fixed_inputs=List.map(fun row->debit 1;exact["tick";"event";"physical";"evidence"]row;
    let f_tick=bounded horizon(get "tick" row)in
    require(not(List.mem f_tick factor_ticks))"Fixed inputs overlap a factor tick.";
    let f_event=lifecycle(get "event" row)in require(f_tick<=cutoff || f_event=None_event)"Suffix cannot contain a lifecycle event.";
    {f_tick;f_event;f_physical=physical(get "physical" row);f_evidence=evidence_map ~tick:f_tick(get "evidence" row)})
    (rows 65(get "fixed_inputs" raw))in
  let fixed_ticks=List.map(fun row->row.f_tick)fixed_inputs in
  require(List.sort_uniq Int.compare fixed_ticks=fixed_ticks)"Fixed input ticks must be ascending and unique.";
  let limits=get "limits" raw in exact["max_generations";"max_prefixes";"max_transitions";"max_histories";"max_work"]limits;
  let limits={max_generations=positive 16(get "max_generations" limits);max_prefixes=positive 1000000(get "max_prefixes" limits);
    max_transitions=positive 1000000(get "max_transitions" limits);max_histories=positive 65536(get "max_histories" limits);
    max_work=positive 16000000(get "max_work" limits)}in
  debit 1;
  let identity=charged_fingerprint debit raw in
  {raw;identity;decoded_work= !decoding;bindings;resolution;deadlines;cutoff;horizon;
   freshness=List.map(fun(input,_,value)->input,value)references;initial_physical;initial_evidence;
   physical_factors;evidence_factors;lifecycle_factors;fixed_inputs;limits}
let to_json domain = domain.raw
let fingerprint domain = domain.identity
let decoding_work domain = domain.decoded_work
let metadata domain = {domain_fingerprint=domain.identity;fixed_input_count=List.length domain.fixed_inputs;
  physical_factor_count=List.length domain.physical_factors;evidence_factor_count=List.length domain.evidence_factors;
  lifecycle_factor_count=List.length domain.lifecycle_factors}
let validate_for ?(charge=noop) ~bindings ~resolution ~deadlines ~horizon_ticks domain =
  charge 1;
  Diagnostic.require(domain.bindings=bindings && Json.equal domain.resolution resolution &&
    domain.deadlines=deadlines && domain.horizon=horizon_ticks)"policy_controlled_domain_binding"
    "Controlled domain differs from the independently admitted source/context bindings, clock or five deadline bounds.";
  Validated domain
let specification(Validated domain) = domain
let initial ?(charge=noop) (Validated domain) = charge 1;
  {domain=domain.identity;lineage=domain.identity;next_tick=0;c_live=false;c_generation=0;c_generation_started_tick=0;
   c_physical=domain.initial_physical;c_evidence=domain.initial_evidence}
let cursor_tick cursor = cursor.next_tick
let check_cursor domain cursor = Diagnostic.require(cursor.domain=domain.identity)"policy_controlled_domain_cursor" "Foreign controlled-domain cursor."
let finished (Validated domain) cursor = check_cursor domain cursor;cursor.next_tick>domain.horizon
(* The immutable cursor lineage commits to the complete domain and every prior
   complete input frame, even when different histories converge physically. *)
let cursor_identity cursor = cursor.lineage
let batch_to_json batch = obj["tick",Json.int batch.tick;"event",str(lifecycle_name batch.event);"live",Json.Bool batch.live;
  "generation",Json.int batch.generation;"generation_started_tick",Json.int batch.generation_started_tick;
  "physical",physical_json batch.physical;"evidence",evidence_map_json batch.evidence]
let eligible cursor = function None_event->true|Start->not cursor.c_live|End|Reset->cursor.c_live
let event_state domain cursor event =
  contradiction(eligible cursor event)"Fixed lifecycle event is invalid for a reachable prefix.";
  let generation=match event with Start|Reset->cursor.c_generation+1|None_event|End->cursor.c_generation in
  Diagnostic.require(generation<=domain.limits.max_generations)"policy_controlled_domain_generation_bound"
    "A declared lifecycle history exceeds its generation bound; it cannot be pruned.";
  let live=match event with Start|Reset->true|End->false|None_event->cursor.c_live in
  let started=match event with Start|Reset->cursor.next_tick|None_event|End->cursor.c_generation_started_tick in
  let physical=match event with End|Reset->{cursor.c_physical with antigen=false}|None_event|Start->cursor.c_physical in
  live,generation,started,physical
let check_batch domain cursor batch =
  contradiction((batch.live || not batch.physical.antigen) &&
    ((batch.event<>End && batch.event<>Reset)||not batch.physical.antigen))
    "Physical antigen contradicts an idle or end/reset boundary on a reachable prefix.";
  contradiction(cursor.next_tick<=domain.cutoff || (batch.event=None_event && batch.physical=cursor.c_physical))
    "A fixed suffix frame changes a held physical input.";
  List.iter(fun(input,value)->match input,value.generation with
    |Antigen,Some generation->contradiction(generation<=batch.generation)"Antigen evidence refers to a future generation."
    |_->())batch.evidence
let effective_evidence (Validated domain) batch input =
  Diagnostic.require(batch.origin_domain=domain.identity)"policy_controlled_domain_cursor" "Foreign controlled-domain evidence batch.";
  let value=List.assoc input batch.evidence in
  match value.status,value.observed_tick with Missing,_->Fresh Missing
  |_,Some observed when batch.tick-observed>List.assoc input domain.freshness->Stale
  |_,Some observed when input=Antigen && (not batch.live || value.generation<>Some batch.generation || observed<batch.generation_started_tick)->Stale
  |_,_->Fresh value.status
let dedup values = List.fold_left(fun kept value->if List.mem value kept then kept else kept@[value])[]values
let rec flat_map f sequence () = match sequence()with
  |Seq.Nil->Seq.Nil|Seq.Cons(value,rest)->Seq.append(f value)(flat_map f rest)()
let rec product charge options = function
  |[]->Seq.return []
  |input::rest->flat_map(fun value->
      let tail=product charge options rest in
      Seq.map(fun rows->charge 1;(input,value)::rows)tail)(List.to_seq(options input))
let choices ?(charge=noop) (Validated domain) cursor =
  check_cursor domain cursor;
  if cursor.next_tick>domain.horizon then Seq.empty else
  let tick=cursor.next_tick in
  (* Delay preparation until the caller forces the sequence, so enumeration's
     work/cancellation guard precedes the actual Cartesian traversal. *)
  let start () =
    charge 1;
    let origin=cursor_identity cursor in
    match List.find_opt(fun row->row.f_tick=tick)domain.fixed_inputs with
    |Some fixed->
        let live,generation,generation_started_tick,_=event_state domain cursor fixed.f_event in
        let batch={tick;event=fixed.f_event;live;generation;generation_started_tick;
          physical=fixed.f_physical;evidence=fixed.f_evidence;origin;origin_domain=domain.identity}in
        check_batch domain cursor batch;Seq.Cons(batch,Seq.empty)
    |None->
        let actions=match List.find_opt(fun row->List.mem tick row.l_ticks)domain.lifecycle_factors with
          |None->[None_event]|Some row->None_event::List.filter(eligible cursor)row.l_actions in
        let sequence=flat_map(fun event->
          charge 1;
          let live,generation,generation_started_tick,base=event_state domain cursor event in
          let physical_options input=charge 1;
            let held=value_at base input in
            match List.find_opt(fun row->row.p_input=input && List.mem tick row.p_ticks)domain.physical_factors with
            |None->[held]|Some row->dedup(held::row.p_values)in
          flat_map(fun rows->
            charge 1;
            let physical=List.fold_left(fun state(input,value)->with_value state input value)base rows in
            let evidence_options input=charge 1;
              let held=List.assoc input cursor.c_evidence in
              match List.find_opt(fun row->row.e_input=input && List.mem tick row.e_ticks)domain.evidence_factors with
              |None->[held]
              |Some row->dedup(held::List.concat_map(fun status->if status=Missing then [missing]else
                List.map(fun age->{status;observed_tick=Some(tick-age);
                  generation=(if input=Antigen then Some generation else None)})row.e_ages)row.e_statuses)in
            Seq.map(fun evidence->charge 1;
              let batch={tick;event;live;generation;generation_started_tick;physical;evidence;origin;origin_domain=domain.identity}in
              check_batch domain cursor batch;batch)(product charge evidence_options keys))
            (product charge physical_options keys)) (List.to_seq actions)in
        sequence()
  in start
let advance ?(charge=noop) (Validated domain) cursor batch =
  charge 1;check_cursor domain cursor;
  Diagnostic.require(cursor.next_tick<=domain.horizon && batch.tick=cursor.next_tick && batch.origin=cursor_identity cursor)
    "policy_controlled_domain_cursor" "Input batch belongs to a different domain or prefix.";
  {domain=domain.identity;lineage=charged_fingerprint charge(obj["prefix",str batch.origin;"batch",batch_to_json batch]);
   next_tick=cursor.next_tick+1;c_live=batch.live;c_generation=batch.generation;
   c_generation_started_tick=batch.generation_started_tick;c_physical=batch.physical;c_evidence=batch.evidence}
let enumerate ?(charge=noop) ?(cancelled=fun()->false) ?(on_history=fun _->()) ((Validated domain)as validated) =
  let exception Local_exhausted in let exception Local_cancelled in
  let usage=ref{prefixes=0;transitions=0;histories=0;work=0}in
  let debit amount=
    if cancelled()then raise Local_cancelled;
    if amount>domain.limits.max_work-(!usage).work then raise Local_exhausted;
    charge amount;usage:={!usage with work=(!usage).work+amount}in
  let rec visit cursor history =
    debit 1;
    if (!usage).prefixes>=domain.limits.max_prefixes then raise Local_exhausted;
    usage:={!usage with prefixes=(!usage).prefixes+1};
    if finished validated cursor then begin
      if (!usage).histories>=domain.limits.max_histories then raise Local_exhausted;
      usage:={!usage with histories=(!usage).histories+1};on_history(List.rev history)
    end else Seq.iter(fun batch->
      debit 1;
      if (!usage).transitions>=domain.limits.max_transitions then raise Local_exhausted;
      usage:={!usage with transitions=(!usage).transitions+1};
      visit(advance ~charge:debit validated cursor batch)(batch::history))
      (choices ~charge:debit validated cursor)
  in
  try visit(initial ~charge:debit validated)[];Complete !usage with
  |Local_exhausted->Exhausted !usage|Local_cancelled->Cancelled !usage
