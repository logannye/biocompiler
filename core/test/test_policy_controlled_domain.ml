open Bioc_wire
module F = Bioc_domain.Policy_controlled_domain

let require condition message = if not condition then failwith message
let str value = Json.String value
let arr values = Json.Array values
let obj fields = Json.Object fields
let get name raw = Json.field name(Json.object_fields raw)
let items name raw = Json.array(get name raw)
let replace key value raw = obj(List.map(fun(name,old)->name,if name=key then value else old)(Json.object_fields raw))
let read path = let channel=open_in_bin path in
  Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
    Json.parse_bounded ~max_bytes:1048576 ~max_nodes:100000(really_input_string channel(in_channel_length channel)))
let rejects code action = match action()with
  |_->failwith("Expected rejection: "^code)
  |exception Diagnostic.Error diagnostic->require(diagnostic.code=code)("Wrong rejection: "^diagnostic.code^" expected "^code)
let rejects_any action = match action()with
  |_->failwith "Malformed domain was accepted"
  |exception Diagnostic.Error _->()
let bindings : F.bindings = {
  clock="clock";executor_role="tcell";executor_identity="fixture.executor";slot="fixture.encounter";
  encounter_declaration="contact";encounter_subject="target";antigen_observation="antigen";
  controller_observation="controller";antigen_freshness_ticks=1;controller_freshness_ticks=1;
  member_a="rna-a";member_b="rna-b";product_a="product-a";product_b="product-b";
}
let deadlines : F.deadlines = {onset_ticks=2;controller_off_ticks=2;antigen_off_ticks=2;
  component_off_ticks=2;reactivation_ticks=2}
(* Complete literal expected source clock, deliberately not copied out of the
   domain under test. These are software fixture units, not biological timing. *)
let resolution = obj["$type",str "Quantity";"amount",str "1";
  "unit",obj["$type",str "Unit";"id",str "second";"dimension",str "time";
    "quantity_kind",str "duration";"scale",str "1";"reference",Json.Null]]
let validate ?(expected=bindings) ?(bounds=deadlines) ?(horizon=10) raw =
  F.validate_for ~bindings:expected ~resolution ~deadlines:bounds ~horizon_ticks:horizon(F.of_json raw)
let batches domain cursor = List.of_seq(F.choices domain cursor)
let only = function [value]->value|_->failwith "Expected one literal input choice"
let step domain cursor = F.advance domain cursor(only(batches domain cursor))
let rec until domain tick cursor = if F.cursor_tick cursor=tick then cursor else until domain tick(step domain cursor)
let complete domain = match F.enumerate domain with F.Complete usage->usage
  |F.Exhausted _->failwith "Unexpected exhaustion"|F.Cancelled _->failwith "Unexpected cancellation"
let change_frame tick f raw = replace "fixed_inputs"(arr(List.map(fun row->
  if get "tick" row=Json.int tick then f row else row)(items "fixed_inputs" raw)))raw
let change_evidence input f row = replace "evidence"(replace input(f(get input(get "evidence" row)))(get "evidence" row))row
let change_physical input value row = replace "physical"(replace input(str value)(get "physical" row))row
let change_input input f raw = replace "inputs"(arr(List.map(fun row->
  if get "key" row=str input then f row else row)(items "inputs" raw)))raw
let factor input = obj["input",str input;"ticks",arr[Json.int 1];"values",arr[str "absent";str "present"]]
let cartesian raw = raw
  |>replace "physical_factors"(arr[factor "rna_a";factor "rna_b"])
  |>replace "evidence_factors"(arr[obj["input",str "controller";"ticks",arr[Json.int 2];
      "statuses",arr[str "valid";str "missing"];"age_ticks",arr[Json.int 0]]])
let limit key value raw = replace "limits"(replace key(Json.int value)(get "limits" raw))raw

let run raw =
  let decoded=F.of_json raw in
  require(Json.equal(F.to_json decoded)raw)"Domain round-trip changed original authority";
  require(F.fingerprint decoded=Canonical.fingerprint raw)"Domain fingerprint omitted original authority";
  let counted=ref 0 in
  let charged=F.of_json ~charge:(fun n->counted:= !counted+n) raw in
  require(F.decoding_work charged= !counted && !counted>0)"Decode work did not reach enclosing budget";
  let meta=F.metadata decoded in
  require(meta.fixed_input_count=3 && meta.physical_factor_count=0 && meta.evidence_factor_count=0 &&
    meta.lifecycle_factor_count=0 && meta.domain_fingerprint=F.fingerprint decoded)
    "Receipt metadata changed fixed demonstration into factor coverage";
  let domain=validate raw in
  let history=ref [] in
  let usage=match F.enumerate ~on_history:(fun rows->history:=rows) domain with
    |F.Complete usage->usage|_->failwith "Literal bounded domain did not complete"in
  require(usage.histories=1 && usage.transitions=11 && usage.prefixes=12)"Literal complete-prefix census changed";
  require(List.map(fun(batch:F.input_batch)->batch.tick)!history=List.init 11 Fun.id)"Tick-zero or suffix frames were omitted";
  let frame tick=List.nth !history tick in
  require((frame 0).event=F.Start && (frame 0).generation=1 && (frame 0).live)"Explicit initial start was lost";
  require((frame 2).physical.controller && not(frame 3).physical.controller && (frame 6).physical.controller)
    "Literal enable/disable/restore physical history changed";
  require(F.effective_evidence domain(frame 2)F.Controller=F.Stale && (frame 2).physical.controller)
    "Stale controller evidence rewrote enabled physical input";
  require(F.effective_evidence domain(frame 10)F.Antigen=F.Stale && (frame 10).physical.antigen)
    "Suffix stale antigen was dropped or turned physically absent";
  require(List.for_all(fun(batch:F.input_batch)->batch.tick<=6 || batch.physical=(frame 6).physical)!history)
    "Hold suffix changed physical state";
  let cross=validate(cartesian raw)in
  let seen=ref [] in
  let cross_usage=match F.enumerate ~on_history:(fun history->
    let (one:F.input_batch)=List.nth history 1 and (two:F.input_batch)=List.nth history 2 in
    seen:=(one.physical.rna_a,one.physical.rna_b,List.assoc F.Controller two.evidence):: !seen)cross with
    |F.Complete usage->usage|_->failwith "Cartesian domain did not complete"in
  (* Independent literal census: four RNA pairs at t1, three distinct evidence
     records at t2; 1 + 4 + 12 + 8*12 transitions, plus the initial prefix. *)
  require(cross_usage.histories=12 && cross_usage.transitions=113 && cross_usage.prefixes=114)
    "Cartesian domain omitted a cross-combination or collapsed converging prefixes";
  require(List.length(List.sort_uniq compare !seen)=12)"Cartesian evidence/physical combinations were duplicated or absent";
  let cross_meta=F.metadata(F.specification cross)in
  require(cross_meta.physical_factor_count=2 && cross_meta.evidence_factor_count=1 && cross_meta.fixed_input_count=3)
    "Factor census omitted mixed physical/evidence choices";
  let debited=ref 0 in
  let charged_usage=match F.enumerate ~charge:(fun n->debited:= !debited+n)cross with
    |F.Complete usage->usage|_->failwith "Charged Cartesian traversal did not complete"in
  require(charged_usage.work= !debited && !debited>cross_usage.transitions)
    "Enumeration hid traversal or fingerprint work from enclosing budget";
  let exception Outer_budget in
  (match F.enumerate ~charge:(fun _->raise Outer_budget)domain with
   |_->failwith "Enclosing work exception became a receipt"|exception Outer_budget->());
  (match F.of_json ~charge:(fun _->raise Outer_budget)raw with
   |_->failwith "Decode swallowed enclosing budget exception"|exception Outer_budget->());
  (match F.validate_for ~charge:(fun _->raise Outer_budget) ~bindings ~resolution ~deadlines ~horizon_ticks:10 decoded with
   |_->failwith "Validation swallowed enclosing budget exception"|exception Outer_budget->());
  let exception History_failure in
  (match F.enumerate ~on_history:(fun _->raise History_failure)domain with
   |_->failwith "History callback failure became complete"|exception History_failure->());
  List.iter(fun bound->match F.enumerate(validate(limit bound 1(cartesian raw)))with
    |F.Exhausted _->()|_->failwith("Exhaustion became complete: "^bound))
    ["max_prefixes";"max_transitions";"max_histories";"max_work"];
  (match F.enumerate ~cancelled:(fun()->true)domain with
   |F.Cancelled usage->require(usage.histories=0 && usage.work=0)"Cancelled domain performed work"
   |_->failwith "Cancellation became a completed domain");
  let checks=ref 0 in
  (match F.enumerate ~cancelled:(fun()->incr checks; !checks>100)domain with
   |F.Cancelled usage->require(usage.histories=0 && usage.work>0)"Mid-history cancellation did not retain partial accounting"
   |_->failwith "Mid-history cancellation became complete");
  let reset_raw=raw
    |>change_frame 3(fun row->row|>replace "event"(str "reset")|>change_physical "antigen" "absent")
    |>change_frame 6(change_evidence "antigen"(replace "generation"(Json.int 2)))in
  let reset=validate reset_raw in
  let reset_cursor=until reset 3(F.initial reset)in
  let reset_batch=only(batches reset reset_cursor)in
  require(reset_batch.live && reset_batch.generation=2 && not reset_batch.physical.antigen &&
    reset_batch.physical.rna_a && reset_batch.physical.protein_a)"Reset lost persistent executor availability";
  require(F.effective_evidence reset reset_batch F.Antigen=F.Stale &&
    F.effective_evidence reset reset_batch F.Controller=F.Fresh F.Valid)
    "Reset did not distinguish old antigen generation from fresh executor evidence";
  ignore(complete reset);
  let restart_raw=raw
    |>change_frame 3(fun row->row|>replace "event"(str "end")|>change_physical "antigen" "absent")
    |>change_frame 6(fun row->row|>replace "event"(str "start")|>change_evidence "antigen"(replace "generation"(Json.int 2)))in
  let restart=validate restart_raw in
  let restarted=only(batches restart(until restart 6(F.initial restart)))in
  require(restarted.live && restarted.generation=2 && restarted.physical.controller && restarted.physical.protein_b)
    "End/start did not reuse the slot with persistent executor state";
  ignore(complete restart);
  let boundary_error raw = rejects "policy_controlled_domain_contradiction"(fun()->complete(validate raw))in
  boundary_error(change_frame 3(replace "event"(str "start"))raw);
  boundary_error(change_frame 0(fun row->row|>replace "event"(str "end")|>change_physical "antigen" "absent")raw);
  boundary_error(change_frame 3(replace "event"(str "reset"))raw);
  boundary_error(change_frame 0(change_evidence "antigen"(replace "generation"(Json.int 2)))raw);
  boundary_error(change_frame 0(replace "event"(str "none"))raw);
  (* One optional end branch conflicts with the later fixed antigen-present
     frame. The valid none branch must not conceal that original contradiction. *)
  boundary_error(replace "lifecycle_factors"(arr[obj["ticks",arr[Json.int 2];"actions",arr[str "end"]]])raw);
  rejects "policy_controlled_domain_generation_bound"(fun()->complete(validate(limit "max_generations" 1 restart_raw)));
  let append_frame row raw=replace "fixed_inputs"(arr(items "fixed_inputs" raw@[row]))raw in
  let last=List.nth(items "fixed_inputs" raw)2 in
  let suffix=last|>replace "tick"(Json.int 8)|>change_physical "controller" "disabled"in
  boundary_error(append_frame suffix raw);
  let refresh=replace "evidence_factors"(arr[obj["input",str "controller";"ticks",arr[Json.int 8];
    "statuses",arr[str "valid"];"age_ticks",arr[Json.int 0]]])raw in
  require((complete(validate refresh)).histories=2)"Explicit suffix evidence refresh was omitted";
  let unknown=change_frame 0(change_evidence "protein_a"(fun _->obj["status",str "missing";
    "observed_tick",Json.Null;"generation",Json.Null]))raw in
  let unknown_domain=validate unknown in let unknown_frame=only(batches unknown_domain(F.initial unknown_domain))in
  require(unknown_frame.physical.protein_a && F.effective_evidence unknown_domain unknown_frame F.Protein_a=F.Fresh F.Missing)
    "Missing availability evidence removed the physical protein";
  List.iter(fun(expected:F.bindings)->rejects "policy_controlled_domain_binding"(fun()->validate ~expected raw))
    [{bindings with member_a="foreign-rna"};{bindings with product_b="foreign-product"};
     {bindings with executor_identity="foreign-executor"};{bindings with slot="foreign-slot"};
     {bindings with antigen_freshness_ticks=2};{bindings with controller_freshness_ticks=2}];
  rejects "policy_controlled_domain_binding"(fun()->F.validate_for ~bindings ~resolution:(replace "amount"(str "2")resolution)
    ~deadlines ~horizon_ticks:10 decoded);
  rejects "policy_controlled_domain_binding"(fun()->validate ~bounds:{deadlines with component_off_ticks=3}raw);
  rejects "policy_controlled_domain_binding"(fun()->validate ~horizon:11 raw);
  let unequal=replace "source_deadlines"(replace "component_off_ticks"(Json.int 3)(get "source_deadlines" raw))raw in
  rejects "policy_controlled_domain"(fun()->F.of_json unequal);
  let unequal=replace "horizon_tick"(Json.int 11)unequal in
  require((complete(validate ~bounds:{deadlines with component_off_ticks=3} ~horizon:11 unequal)).transitions=12)
    "Suffix ignored the independently larger component deadline";
  List.iter(fun value->rejects_any(fun()->F.of_json(replace "horizon_tick" value raw)))
    [Json.Float 10.;Json.Bool true;str "10";Json.int 65;Json.int(-1)];
  List.iter(fun mutation->rejects_any(fun()->F.of_json(mutation raw)))
    [change_input "controller"(replace "scope"(str "encounter"));
     change_input "rna_a"(fun row->replace "reference"(replace "kind"(str "Observation")(get "reference" row))row);
     change_input "controller"(replace "freshness_ticks"(Json.int 65));
     change_frame 0(change_evidence "antigen"(replace "observed_tick"(Json.int 1)));
     change_frame 0(change_evidence "controller"(replace "generation"(Json.int 1)));
     change_frame 0(change_evidence "controller"(replace "status"(str "stale")));
     change_frame 0(change_physical "protein_a" "unknown");
     replace "physical_factors"(arr[factor "rna_a";factor "rna_a"]);
     replace "physical_factors"(arr[replace "ticks"(arr[Json.int 0])(factor "rna_a")]);
     replace "physical_factors"(arr[replace "ticks"(arr[Json.int 7])(factor "rna_a")]);
     replace "lifecycle_factors"(arr[obj["ticks",arr[Json.int 1];"actions",arr[str "reset"]];obj["ticks",arr[Json.int 1];"actions",arr[str "end"]]]);
     replace "evidence_factors"(arr[obj["input",str "controller";"ticks",arr[Json.int 1];"statuses",arr[str "valid"];
       "age_ticks",arr[Json.int 2]]]);
     limit "max_work" 16000001;
     (fun raw->obj(("extra",Json.Null)::Json.object_fields raw));
     (fun raw->replace "inputs"(arr(List.rev(items "inputs" raw)))raw)];
  (* Private batches bind the whole prefix, including histories whose physical
     state converges again at the fixed t3 frame. *)
  let one=step cross(F.initial cross)in
  let alternatives=batches cross one in
  let first=F.advance cross one(List.hd alternatives)and second=F.advance cross one(List.nth alternatives 1)in
  let first_two=List.hd(batches cross first)in
  rejects "policy_controlled_domain_cursor"(fun()->F.advance cross second first_two);
  let third_a=F.advance cross first first_two in
  let third_b=F.advance cross second(List.hd(batches cross second))in
  let fourth_a=step cross third_a and fourth_b=step cross third_b in
  let fourth_batch=only(batches cross fourth_a)in
  rejects "policy_controlled_domain_cursor"(fun()->F.advance cross fourth_b fourth_batch);
  let foreign=validate(limit "max_work" 999999 raw)in
  let original_zero=only(batches domain(F.initial domain))in
  rejects "policy_controlled_domain_cursor"(fun()->F.advance foreign(F.initial foreign)original_zero);
  rejects "policy_controlled_domain_cursor"(fun()->F.effective_evidence foreign original_zero F.Controller);
  Printf.printf "Controlled-domain literal and Cartesian censuses: 1 and 12 histories; input coverage only, no activity or requirement acceptance\n"

let () =
  require(Array.length Sys.argv=2)"Expected original controlled-domain fixture";
  run(read Sys.argv.(1))
