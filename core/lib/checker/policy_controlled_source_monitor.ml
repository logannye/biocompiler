open Bioc_wire
module Source = Policy_controlled_source
module Domain = Bioc_domain.Policy_controlled_domain
module Sample = Bioc_domain.Policy_controlled_activity_sample

type obligation_state = {
  original : Source.obligation; exercised : bool; violated : bool;
  uncertain : bool; events : Json.t list;
}
type demand = { kind : Source.obligation_kind; trigger : int; deadline : int; generation : int }
type t = {
  source : Source.source; domain : Domain.validated; cursor : Domain.cursor;
  obligations : obligation_state list; demands : demand list;
  previous : Sample.band; ever_active : bool; last_generation : int option;
  has_failure : bool; has_unknown : bool;
  saw_active : bool; saw_background : bool; saw_antigen_absent : bool;
  saw_controller_disabled : bool; cycle : int;
  evidence_gaps : Json.t list; history : Json.t list;
}

let pending (state:t) = state.demands<>[]
let failed (state:t) = state.has_failure
let unknown (state:t) = state.has_unknown || not (Domain.finished state.domain state.cursor) || pending state
let satisfied (state:t) = not (failed state) && not (unknown state)
let coverage (state:t) = ["active",state.saw_active;"background",state.saw_background;
  "antigen_absent_controller_enabled",state.saw_antigen_absent;
  "controller_disabled_antigen_present",state.saw_controller_disabled;
  "reversible_cycle",state.cycle=4]

module Make (Charge:sig val charge:int -> unit end) = struct
module Meter = Policy_generation_meter.Make(Charge)
module List = Meter.List
module Json = Meter.Json
let charge = Charge.charge
let str value = Json.String value
let obj fields = Json.Object fields
let arr values = Json.Array values
let get key value = Json.field key (Json.object_fields value)
let check condition message = Diagnostic.require condition "policy_controlled_source_monitor" message
let optional_int = function None -> Json.Null | Some value -> Json.int value
let quality = function
  | Domain.Stale -> "stale"
  | Domain.Fresh Domain.Valid -> "valid"
  | Domain.Fresh Domain.Missing -> "missing"
  | Domain.Fresh Domain.Invalid -> "invalid"
  | Domain.Fresh Domain.Conflicting -> "conflicting"
let source_bounds (source:Source.source) = obj [
  "onset_ticks",Json.int source.deadlines.onset_ticks;
  "controller_off_ticks",Json.int source.deadlines.controller_off_ticks;
  "antigen_off_ticks",Json.int source.deadlines.antigen_off_ticks;
  "component_off_ticks",Json.int source.deadlines.component_off_ticks;
  "reactivation_ticks",Json.int source.deadlines.reactivation_ticks]

let create ~source:admitted ~domain =
  charge 1;
  let source : Source.source = Source.typed admitted in
  let raw = Domain.to_json (Domain.specification domain) in
  (* This checks correspondence to the admitted SOURCE. It does not consult the
     mechanism model or copy its actual transition delays. *)
  check (Json.equal (get "horizon_tick" raw) (Json.int source.horizon_ticks) &&
    Json.equal (get "source_deadlines" raw) (source_bounds source))
    "The operating domain must retain the original source horizon and five independent deadlines.";
  let clock=get "clock" raw in
  check (Json.equal (get "id" clock) (str source.clock.id) && Json.equal (get "resolution" clock) source.resolution)
    "The source monitor requires the original exact clock.";
  check (Json.equal (get "role" (get "executor" raw)) (str source.executor.id) &&
    Json.equal (get "declaration" (get "encounter" raw)) (str source.encounter.id) &&
    Json.equal (get "subject" (get "encounter" raw)) (str source.target.id))
    "The source monitor requires the original executor and encounter bindings.";
  let inputs=Json.array (get "inputs" raw) in
  let bound_input key identity freshness =
    let row=List.find (fun row -> Json.equal (get "key" row) (str key)) inputs in
    check (Json.equal (get "id" (get "reference" row)) (str identity)) "A source input identity was changed.";
    match freshness with None -> () | Some ticks ->
      check (Json.equal (get "freshness_ticks" row) (Json.int ticks)) "Source freshness was changed." in
  bound_input "antigen" source.antigen.symbol.id (Some source.antigen.freshness_ticks);
  bound_input "controller" source.controller.symbol.id (Some source.controller.freshness_ticks);
  let (a:Source.product),(b:Source.product)=source.products in
  bound_input "protein_a" a.symbol.id None;bound_input "protein_b" b.symbol.id None;
  let obligations=List.map (fun (original:Source.obligation) ->
    {original;exercised=false;violated=false;uncertain=false;events=[]}) source.obligations in
  {source;domain;cursor=Domain.initial ~charge domain;obligations;demands=[];
   previous=Sample.Background;ever_active=false;last_generation=None;
   has_failure=false;has_unknown=false;saw_active=false;saw_background=false;
   saw_antigen_absent=false;saw_controller_disabled=false;cycle=0;evidence_gaps=[];history=[]}

let event tick action (demand:demand) = obj ["tick",Json.int tick;"action",str action;
  "trigger_tick",Json.int demand.trigger;"deadline_tick",Json.int demand.deadline;
  "generation",Json.int demand.generation]

let step (state:t) ~(input:Domain.input_batch) ~(activity:Sample.t) ~readout =
  charge 1;
  let cursor=Domain.advance ~charge state.domain state.cursor input in
  check (activity.tick=input.tick) "Activity and original-domain tick differ.";
  check ((activity.band=Sample.Background && activity.activation_generation=None) ||
    (activity.band=Sample.Active && match activity.activation_generation with
      | Some generation -> generation>0 && generation<=input.generation | None -> false))
    "The neutral activity sample has an invalid generation annotation.";
  let active=activity.band=Sample.Active in
  let was_active=state.previous=Sample.Active in
  let gate=input.live && input.event<>Domain.End && input.event<>Domain.Reset &&
    input.physical.antigen && input.physical.controller && input.physical.protein_a && input.physical.protein_b in
  let obligations=ref state.obligations in
  let demands=ref state.demands in
  let mark kind f = obligations:=List.map (fun (value:obligation_state) ->
    if value.original.kind=kind then f value else value) !obligations in
  let add_event kind value = mark kind (fun row -> {row with exercised=true;events=value::row.events}) in
  let violation kind reason = mark kind (fun row -> {row with exercised=true;violated=true;
    events=obj["tick",Json.int input.tick;"action",str "violation";"reason",str reason]::row.events}) in
  let find kind = List.find_opt (fun (demand:demand) -> demand.kind=kind) !demands in
  let trigger kind =
    if find kind=None then begin
      let row=List.find (fun (row:obligation_state) -> row.original.kind=kind) !obligations in
      let delay=match row.original.deadline_ticks with Some ticks -> ticks | None ->
        Diagnostic.fail "policy_controlled_source_monitor" "A response obligation lost its original deadline." in
      let demand={kind;trigger=input.tick;deadline=input.tick+delay;generation=input.generation} in
      demands:=demand::!demands;add_event kind (event input.tick "triggered" demand)
    end in
  let response kind = kind=Source.Initial_activation || kind=Source.Reactivation in
  (* Cancel only encounter-owned response obligations. Cessation obligations
     survive every restoration, repeat, reset and encounter end. *)
  demands:=List.filter (fun (demand:demand) ->
    if response demand.kind && (not gate || demand.generation<>input.generation) then
      (add_event demand.kind (event input.tick "cancelled" demand);false) else true) !demands;
  if (not was_active || not active) && gate then
    trigger (if state.ever_active then Source.Reactivation else Source.Initial_activation);
  mark Source.No_unauthorized_activation (fun row -> {row with exercised=true});
  if active && not was_active then begin
    let kind=if state.ever_active then Source.Reactivation else Source.Initial_activation in
    let authorized=gate && (match find kind with
      | Some demand -> demand.generation=input.generation && demand.trigger<=input.tick
      | None -> false) && activity.activation_generation=Some input.generation in
    if not authorized then violation Source.No_unauthorized_activation "activation_without_uninterrupted_qualified_response"
  end;
  if active && was_active && activity.activation_generation<>state.last_generation then
    violation Source.No_unauthorized_activation "active_episode_changed_generation_without_background";
  if active || was_active then begin
    if not input.physical.controller then trigger Source.Controller_cessation;
    if not input.live || not input.physical.antigen || input.event=Domain.End || input.event=Domain.Reset then
      trigger Source.Antigen_cessation;
    if not input.physical.protein_a || not input.physical.protein_b then trigger Source.Component_cessation
  end;
  let required_inputs=active || was_active || gate || state.demands<>[] || !demands<>[] in
  let evidence=ref ["activity",readout] in
  if required_inputs then List.iter (fun (name,key) ->
    evidence:=(name,Domain.effective_evidence state.domain input key)::!evidence)
    ["antigen",Domain.Antigen;"controller",Domain.Controller;"protein_a",Domain.Protein_a;"protein_b",Domain.Protein_b];
  let gaps=List.filter_map (fun (channel,status) ->
    if status=Domain.Fresh Domain.Valid then None else
      Some (obj["tick",Json.int input.tick;"channel",str channel;"status",str(quality status)])) !evidence in
  (* The closed conservative evidence policy treats each required unresolved
     frame as unknown for this six-obligation source assessment, even if later
     evidence recovers. The physical frame is retained unchanged below. *)
  if gaps<>[] then obligations:=List.map (fun (row:obligation_state) -> {row with uncertain=true}) !obligations;
  demands:=List.filter (fun (demand:demand) ->
    let discharged=if response demand.kind then active else not active in
    if discharged then (add_event demand.kind (event input.tick "discharged" demand);false)
    else begin
      if input.tick=demand.deadline then begin
        add_event demand.kind (event input.tick "deadline_missed" demand);
        mark demand.kind (fun row -> {row with violated=true})
      end;
      true
    end) !demands;
  let cycle=match state.cycle,activity.band with
    | 0,Sample.Background -> 1 | 1,Sample.Active -> 2 | 2,Sample.Background -> 3
    | 3,Sample.Active -> 4 | value,_ -> value in
  charge (1 + String.length input.origin + String.length input.origin_domain);
  let batch=Domain.batch_to_json input in
  Meter.preflight batch;
  let frame=obj["input",batch;"activity",Sample.to_json activity;"readout_evidence",str(quality readout);
    "qualified_gate",Json.Bool gate;"inputs_required",Json.Bool required_inputs] in
  {state with cursor;obligations= !obligations;demands= !demands;previous=activity.band;
   ever_active=state.ever_active || active;last_generation=activity.activation_generation;
   has_failure=state.has_failure || List.exists (fun (row:obligation_state) -> row.violated) !obligations;
   has_unknown=state.has_unknown || gaps<>[];
   saw_active=state.saw_active || active;saw_background=state.saw_background || not active;
   saw_antigen_absent=state.saw_antigen_absent || (not input.physical.antigen && input.physical.controller);
   saw_controller_disabled=state.saw_controller_disabled || (input.physical.antigen && not input.physical.controller);
   cycle;evidence_gaps=List.rev_append gaps state.evidence_gaps;history=frame::state.history}

let finish (state:t) =
  charge 1;
  let complete=Domain.finished state.domain state.cursor in
  let rows=List.map (fun (row:obligation_state) ->
    let original:Source.obligation=row.original in
    let has_pending=List.exists (fun (demand:demand) -> demand.kind=original.kind) state.demands in
    let status=if row.violated then "fail" else if row.uncertain || has_pending || not complete then "unknown"
      else if row.exercised then "pass" else "not_exercised" in
    Meter.preflight original.symbol.original;
    Meter.preflight original.contract.reference;Meter.preflight original.contract.body;
    obj["id",str original.symbol.id;"source_path",str original.symbol.path;
      "kind",str(Source.obligation_tag original.kind);"status",str status;
      "deadline_ticks",optional_int original.deadline_ticks;
      "source_declaration",original.symbol.original;
      "contract",obj["identity",str original.contract.identity;"path",str original.contract.path;
        "reference",original.contract.reference;"body",original.contract.body];
      "events",arr(List.rev row.events)]) state.obligations in
  let report=obj[
    "schema_version",str "biocompiler.policy_controlled_source_monitor.v0.1";
    "profile",str "biocompiler.policy_controlled_composition_mrna.v0.1";
    "complete",Json.Bool complete;"outcome",str(if failed state then "fail" else if unknown state then "unknown" else "pass");
    "horizon_ticks",Json.int state.source.horizon_ticks;"last_tick",Json.int(Domain.cursor_tick state.cursor-1);
    "pending",Json.Bool(pending state);"evidence_policy",str "biocompiler.controlled_evidence.conservative.v0.1";
    "requirements",arr rows;"coverage",obj(List.map (fun (key,value) -> key,Json.Bool value) (coverage state));
    "evidence_gaps",arr(List.rev state.evidence_gaps);"history",arr(List.rev state.history)] in
  Meter.preflight report;report
end

let create ~charge ~source ~domain = let module M=Make(struct let charge=charge end) in M.create ~source ~domain
let step ~charge state ~input ~activity ~readout = let module M=Make(struct let charge=charge end) in M.step state ~input ~activity ~readout
let finish ~charge state = let module M=Make(struct let charge=charge end) in M.finish state
