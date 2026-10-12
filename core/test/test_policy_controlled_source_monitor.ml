open Bioc_wire
module D = Bioc_domain.Policy_document
module F = Bioc_domain.Policy_controlled_domain
module S = Bioc_checker.Policy_controlled_source
module M = Bioc_checker.Policy_controlled_source_monitor
module A = Bioc_domain.Policy_controlled_activity_sample
let count=ref 0
let require label condition = incr count;if not condition then failwith label
let charge _ = ()
let obj fields=Json.Object fields
let str value=Json.String value
let arr values=Json.Array values
let get key value=Json.field key (Json.object_fields value)
let text key value=Json.string(get key value)
let set key replacement value=obj(List.map(fun(name,value)->name,if name=key then replacement else value)(Json.object_fields value))
let update key f value=set key (f(get key value))value
let declaration identity f=update "program" (update "declarations" (fun values ->
  arr(List.map(fun value->if text "id" value=identity then f value else value)(Json.array values))))
let deadline identity ticks=declaration identity(update "deadline"(set "amount"(str(string_of_int ticks))))
let source original=S.admit ~charge ~document:(D.of_controlled_json(get "document"(get "source_authority" original)))
let evidence ?(status="valid") ?(observed=None) tick generation = obj[
  "status",str status;"observed_tick",(if status="missing" then Json.Null else Json.int(Option.value observed ~default:tick));
  "generation",(if status="missing" then Json.Null else match generation with None->Json.Null|Some value->Json.int value)]
let row ?(event="none") ?(generation=1) ?(antigen=true) ?(controller=true)
    ?(rna_a=true) ?(rna_b=true) ?(protein_a=true) ?(protein_b=true) tick =
  let presence value=str(if value then "present" else "absent")in
  obj["tick",Json.int tick;"event",str event;
    "physical",obj["antigen",presence antigen;"controller",str(if controller then "enabled" else "disabled");
      "rna_a",presence rna_a;"rna_b",presence rna_b;"protein_a",presence protein_a;"protein_b",presence protein_b];
    "evidence",obj(List.map(fun key->key,evidence tick(if key="antigen" then Some generation else None))
      ["antigen";"controller";"rna_a";"rna_b";"protein_a";"protein_b"])]
let rows f=List.init 11(fun tick->f tick)
let ordinary f=rows(fun tick->f tick(row ~event:(if tick=0 then "start" else "none") tick))
let physical key value=update "physical"(set key(str value))
let domain original admitted ?(cutoff=6) fixed =
  let typed:S.source=S.typed admitted in
  let bounds:F.deadlines={onset_ticks=typed.deadlines.onset_ticks;controller_off_ticks=typed.deadlines.controller_off_ticks;
    antigen_off_ticks=typed.deadlines.antigen_off_ticks;component_off_ticks=typed.deadlines.component_off_ticks;
    reactivation_ticks=typed.deadlines.reactivation_ticks}in
  let bindings:F.bindings={clock="clock";executor_role="tcell";executor_identity="fixture.executor";slot="fixture.encounter";
    encounter_declaration="contact";encounter_subject="target";antigen_observation="antigen";controller_observation="controller";
    antigen_freshness_ticks=typed.antigen.freshness_ticks;controller_freshness_ticks=typed.controller.freshness_ticks;
    member_a="rna-a";member_b="rna-b";product_a="product-a";product_b="product-b"}in
  let raw=get "operating_domain" original |> set "physical_factors"(arr[]) |> set "evidence_factors"(arr[])
    |> set "lifecycle_factors"(arr[]) |> set "fixed_inputs"(arr fixed) |> set "intervention_cutoff_tick"(Json.int cutoff)
    |> set "source_deadlines"(obj["onset_ticks",Json.int bounds.onset_ticks;"controller_off_ticks",Json.int bounds.controller_off_ticks;
      "antigen_off_ticks",Json.int bounds.antigen_off_ticks;"component_off_ticks",Json.int bounds.component_off_ticks;
      "reactivation_ticks",Json.int bounds.reactivation_ticks])in
  F.validate_for ~bindings ~resolution:typed.resolution ~deadlines:bounds ~horizon_ticks:typed.horizon_ticks(F.of_json raw)
let history domain=
  let histories=ref[]in
  (match F.enumerate ~on_history:(fun rows->histories:=rows::!histories)domain with
   |F.Complete _->()|_->failwith "single literal history was not completely enumerated");
  match !histories with [rows]->rows|_->failwith "test requires one original history"
let sample ?(generation=1) tick active : A.t =
  {tick;band=(if active then A.Active else A.Background);activation_generation=(if active then Some generation else None)}
let run ?(readout=fun _->F.Fresh F.Valid) admitted domain samples =
  let inputs=history domain in
  List.fold_left2(fun monitor (input:F.input_batch) (activity:A.t)->
    M.step ~charge monitor ~input ~activity ~readout:(readout input.tick))
    (M.create ~charge ~source:admitted ~domain) inputs samples
let bands values=List.mapi(fun tick active->sample tick active)values
let report state=M.finish ~charge state
let requirement state id=List.find(fun value->text "id" value=id)(Json.array(get "requirements"(report state)))
let status state id=text "status"(requirement state id)
let events state id=Json.array(get "events"(requirement state id))
let has_action state id action=List.exists(fun value->text "action" value=action)(events state id)
let all_background=bands(List.init 11(fun _->false))
let on_off_on=bands[false;false;true;true;true;false;false;false;true;true;true]
let controller_trace=ordinary(fun tick value->if tick>=3 && tick<6 then physical "controller" "disabled" value else value)

let source_controls original =
  let admitted=source original in
  let controlled=domain original admitted controller_trace in
  let accepted=run admitted controlled on_off_on in
  require "reversible_on_off_on"(M.satisfied accepted && not(M.pending accepted));
  require "six original requirements retained"(List.length(Json.array(get "requirements"(report accepted)))=6);
  require "source IDs, paths, complete clauses retained"(List.for_all(fun row->
    String.starts_with ~prefix:"/document/program/declarations/"(text "source_path" row) &&
    Json.equal(get "id"(get "source_declaration" row))(get "id" row) &&
    Json.array(get "clauses"(get "body"(get "contract" row)))<>[])(Json.array(get "requirements"(report accepted))));
  require "reversible coverage"(List.assoc "reversible_cycle"(M.coverage accepted));
  let early=bands[false;true;true;true;false;false;false;true;true;true;true]in
  require "response_before_deadline"(M.satisfied(run admitted controlled early));
  let forever=run admitted controlled all_background in
  require "forever_off"(M.failed forever && status forever "onset"="fail");
  let constant=run admitted controlled(bands(List.init 11(fun _->true)))in
  require "constant_on fails cessation"(M.failed constant && status constant "controller-off"="fail");
  let irreversible=run admitted controlled(bands[false;false;true;true;true;false;false;false;false;false;false])in
  require "irreversible_stop"(M.failed irreversible && status irreversible "reactivation"="fail");
  let late_onset=run admitted controlled(bands[false;false;false;false;false;false;false;false;true;true;true])in
  require "late_onset"(status late_onset "onset"="fail");
  let late_stop=run admitted controlled(bands[false;false;true;true;true;true;false;false;true;true;true])in
  require "late_cessation"(status late_stop "controller-off"="fail");
  let late_restart=run admitted controlled(bands[false;false;true;true;true;false;false;false;false;true;true])in
  require "late_reactivation"(status late_restart "reactivation"="fail");
  List.iter(fun(label,change)->
    let quiet=domain original admitted(ordinary(fun _ value->change value))in
    let state=run admitted quiet all_background in
    require label(M.satisfied state && status state "onset"="not_exercised" && not(List.assoc "active"(M.coverage state))))
    ["antigen_absent_quiet",physical "antigen" "absent";"controller_disabled_quiet",physical "controller" "disabled";
     "both_inputs_disabled_quiet",(fun value->value |> physical "antigen" "absent" |> physical "controller" "disabled")];
  let absent=domain original admitted(ordinary(fun _ value->physical "antigen" "absent" value))in
  let unauthorized=run admitted absent(bands(List.init 11(fun tick->tick>=1)))in
  require "antigen_absent_activation"(status unauthorized "safety"="fail");
  let tight_doc=get "document"(get "source_authority" original)|>deadline "onset" 1 in
  let tight=S.admit ~charge ~document:(D.of_controlled_json tight_doc)in
  require "tighter_source_deadline"(status(run tight(domain original tight controller_trace)on_off_on)"onset"="fail");
  let pending_state=List.fold_left2(fun monitor input activity->M.step ~charge monitor ~input ~activity ~readout:(F.Fresh F.Valid))
    (M.create ~charge ~source:admitted ~domain:controlled)
    (List.filter(fun (input:F.input_batch)->input.tick<2)(history controlled))
    (bands[false;false])in
  require "pending incomplete horizon is not accepted"(M.pending pending_state && not(M.satisfied pending_state) && M.unknown pending_state);
  let horizon_pending=run admitted controlled(bands[false;false;true;true;true;true;true;true;true;false;false])in
  require "pending obligation at complete horizon cannot pass"(M.pending horizon_pending && not(M.satisfied horizon_pending));
  require "full bounded failing history retained"(List.length(Json.array(get "history"(report horizon_pending)))=11);
  let changed=List.nth(history controlled)1 in
  (match M.step ~charge(M.create ~charge ~source:admitted ~domain:controlled)~input:changed ~activity:(sample 1 false)~readout:(F.Fresh F.Valid)with
   |_->failwith "Skipped original-domain prefix accepted"|exception Diagnostic.Error diagnostic->require "domain cursor rejects skipped ticks"(diagnostic.code="policy_controlled_domain_cursor"));
  (match M.create ~charge:(fun _->Diagnostic.fail "fixture_budget" "Meter stopped.")~source:admitted ~domain:controlled with
   |_->failwith "Meter interruption accepted"|exception Diagnostic.Error diagnostic->require "source monitor preserves enclosing meter failure"(diagnostic.code="fixture_budget"));
  let zero=List.hd(history controlled)in
  (match M.step ~charge:(fun _->Diagnostic.fail "fixture_budget" "Meter stopped.")
      (M.create ~charge ~source:admitted ~domain:controlled)~input:zero ~activity:(sample 0 false)~readout:(F.Fresh F.Valid)with
   |_->failwith "Step meter interruption accepted"|exception Diagnostic.Error diagnostic->require "monitor step meter propagates"(diagnostic.code="fixture_budget"));
  (match M.finish ~charge:(fun _->Diagnostic.fail "fixture_budget" "Meter stopped.")accepted with
   |_->failwith "Report meter interruption accepted"|exception Diagnostic.Error diagnostic->require "monitor report meter propagates"(diagnostic.code="fixture_budget"));
  (match M.step ~charge(M.create ~charge ~source:admitted ~domain:controlled)~input:zero ~activity:(sample 1 false)~readout:(F.Fresh F.Valid)with
   |_->failwith "Mismatched readout tick accepted"|exception Diagnostic.Error diagnostic->require "sample tick bound to original input"(diagnostic.code="policy_controlled_source_monitor"));
  (match M.create ~charge ~source:admitted ~domain:(domain original tight controller_trace)with
   |_->failwith "Foreign source deadlines accepted"|exception Diagnostic.Error diagnostic->require "monitor source/domain correspondence"(diagnostic.code="policy_controlled_source_monitor"))

let causal_controls original =
  let admitted=source original in
  let run_rows fixed samples=run admitted(domain original admitted fixed)samples in
  let antigen=ordinary(fun tick value->if tick>=3 && tick<6 then physical "antigen" "absent" value else value)in
  require "antigen_loss_and_recovery"(M.satisfied(run_rows antigen on_off_on));
  let protein=ordinary(fun tick value->if tick>=3 && tick<6 then physical "protein_a" "absent" value else value)in
  require "protein_loss_and_recovery"(M.satisfied(run_rows protein on_off_on));
  let rna=ordinary(fun tick value->if tick>=3 then value |>physical "rna_a" "absent" |>physical "rna_b" "absent" else value)in
  let persistent=run_rows rna(bands[false;false;true;true;true;true;true;true;true;true;true])in
  require "rna_loss_protein_persistence"(M.satisfied persistent && status persistent "component-off"="not_exercised");
  let repeated=ordinary(fun tick value->if tick=3 || tick=5 then physical "controller" "disabled" value else value)in
  let stopped=run_rows repeated on_off_on in
  require "repeated_loss_does_not_postpone_stop"(M.satisfied stopped);
  let triggers=List.filter(fun value->text "action" value="triggered")(events stopped "controller-off")in
  require "repeated loss retains one original trigger and deadline"(List.length triggers=1 &&
    Json.equal(get "trigger_tick"(List.hd triggers))(Json.int 3) && Json.equal(get "deadline_tick"(List.hd triggers))(Json.int 5));
  let restored=ordinary(fun tick value->if tick=3 then physical "controller" "disabled" value else value)in
  let state=run_rows restored(bands[false;false;true;true;true;false;false;true;true;true;true])in
  require "restoration_during_cessation"(M.satisfied state);
  let reactivation=List.find(fun value->text "action" value="triggered")(events state "reactivation")in
  require "reactivation clock begins on observed background"(Json.equal(get "trigger_tick" reactivation)(Json.int 5));
  let premature=ordinary(fun tick value->if tick>=2 then physical "controller" "disabled" value else value)in
  let state=run_rows premature all_background in
  require "disable_at_onset_maturity cancels response"(M.satisfied state && has_action state "onset" "cancelled");
  let pulse=run_rows premature(bands[false;false;true;true;false;false;false;false;false;false;false])in
  require "disable_at_onset_maturity forbids pulse"(status pulse "safety"="fail");
  let document=get "document"(get "source_authority" original)|>deadline "controller-off" 3|>deadline "antigen-off" 1|>deadline "component-off" 4 in
  let unequal=S.admit ~charge ~document:(D.of_controlled_json document)in
  let losses=ordinary(fun tick value->if tick=3 then value|>physical "antigen" "absent"|>physical "controller" "disabled"|>physical "protein_b" "absent" else value)in
  let state=run unequal(domain original unequal ~cutoff:4 losses)(bands[false;false;true;true;true;false;false;true;true;true;true])in
  require "unequal independent cessation deadlines"(status state "controller-off"="pass" && status state "antigen-off"="fail" && status state "component-off"="pass");
  require "simultaneous causes each retain original requirement"(List.for_all(fun id->has_action state id "triggered" && has_action state id "discharged")
    ["controller-off";"antigen-off";"component-off"])

let evidence_controls original =
  let admitted=source original in
  let active_bands=bands[false;false;true;true;true;true;true;true;true;true;true]in
  List.iter(fun(label,key,status,observed)->
    let fixed=ordinary(fun tick value->if tick=2 then update "evidence"(set key(evidence ~status ~observed tick(if key="antigen" then Some 1 else None)))value else value)in
    let state=run admitted(domain original admitted fixed)active_bands in
    require label(M.unknown state && not(M.satisfied state) && not(M.failed state));
    require (label^" remains sticky after recovery")(text "outcome"(report state)="unknown" && List.length(Json.array(get "history"(report state)))=11))
    ["antigen_missing_evidence","antigen","missing",None;
     "controller_missing_evidence","controller","missing",None;
     "protein_missing_evidence","protein_a","missing",None;
     "controller_stale_evidence","controller","valid",Some 0;
     "controller_invalid_evidence","controller","invalid",None;
     "controller_conflicting_evidence","controller","conflicting",None];
  let controlled=domain original admitted controller_trace in
  let readout=run ~readout:(fun tick->if tick=2 then F.Fresh F.Missing else F.Fresh F.Valid)admitted controlled on_off_on in
  require "activity_missing_evidence"(M.unknown readout && not(M.satisfied readout));
  let fail_unknown=run ~readout:(fun tick->if tick=1 then F.Stale else F.Fresh F.Valid)admitted controlled all_background in
  require "physical failure retained alongside evidence unknown"(M.failed fail_unknown && M.unknown fail_unknown && text "outcome"(report fail_unknown)="fail");
  let no_rna_evidence=ordinary(fun tick value->update "evidence"(set "rna_a"(evidence ~status:"missing" tick None))value)in
  require "RNA evidence is not a physical activity gate"(M.satisfied(run admitted(domain original admitted no_rna_evidence)active_bands));
  let quiet=ordinary(fun tick value->value|>physical "antigen" "absent"|>update "evidence"(set "controller"(evidence ~status:"missing" tick None)))in
  require "quiet input evidence not demanded without activity or pending response"(M.satisfied(run admitted(domain original admitted quiet)all_background));
  let pending_missing=ordinary(fun tick value->if tick=1 then update "evidence"(set "protein_b"(evidence ~status:"missing" tick None))value else value)in
  require "pending response requires protein evidence"(M.unknown(run admitted(domain original admitted pending_missing)active_bands))

let lifecycle_controls original =
  let admitted=source original in
  let reset=rows(fun tick->row ~event:(if tick=0 then "start" else if tick=3 then "reset" else "none")
    ~generation:(if tick<3 then 1 else 2) ~antigen:(tick<>3) tick)in
  let samples=List.mapi(fun tick active->sample ~generation:(if tick<7 then 1 else 2)tick active)
    [false;false;true;true;true;false;false;true;true;true;true]in
  let state=run admitted(domain original admitted reset)samples in
  require "encounter_reset_recovery preserves old residual generation"(not(M.failed state) && has_action state "antigen-off" "discharged" && List.assoc "reversible_cycle"(M.coverage state));
  require "fresh new-generation absence resolves reset boundary"(M.satisfied state && not(M.unknown state));
  let inherited_reset=List.mapi(fun tick value->if tick=3 then
    update "evidence"(set "antigen"(evidence ~observed:(Some 2) tick(Some 1)))value else value)reset in
  let inherited=run admitted(domain original admitted inherited_reset)samples in
  require "reset invalidates inherited antigen evidence without rewriting activity"
    (M.unknown inherited && not(M.failed inherited) &&
      List.exists(fun gap->Json.equal(get "tick" gap)(Json.int 3) && text "channel" gap="antigen" && text "status" gap="stale")
        (Json.array(get "evidence_gaps"(report inherited))) &&
      List.map(get "activity")(Json.array(get "history"(report inherited)))=
        List.map(get "activity")(Json.array(get "history"(report state))));
  let onset_reset=rows(fun tick->row ~event:(if tick=0 then "start" else if tick=1 then "reset" else "none")
    ~generation:(if tick<1 then 1 else 2) ~antigen:(tick<>1) tick)in
  let state=run admitted(domain original admitted onset_reset)
    (List.mapi(fun tick active->sample ~generation:2 tick active)[false;false;false;false;true;true;true;true;true;true;true])in
  require "reset_during_onset cancels old response interval"(not(M.failed state) && has_action state "onset" "cancelled");
  let ending=rows(fun tick->row ~event:(if tick=0 || tick=6 then "start" else if tick=3 then "end" else "none")
    ~generation:(if tick<6 then 1 else 2) ~antigen:(tick<3 || tick>=6) tick)in
  let samples=List.mapi(fun tick active->sample ~generation:(if tick<8 then 1 else 2)tick active)
    [false;false;true;true;true;false;false;false;true;true;true]in
  let state=run admitted(domain original admitted ending)samples in
  require "encounter_end_and_restart keeps executor controller enabled"(not(M.failed state) && has_action state "reactivation" "discharged");
  let scope_bug=run admitted(domain original admitted reset)
    (bands[false;false;true;true;true;false;false;false;false;false;false])in
  require "wrong_scope_controller_reset misses independently demanded reactivation"(status scope_bug "reactivation"="fail");
  let reset_stopping=rows(fun tick->row ~event:(if tick=0 then "start" else if tick=4 then "reset" else "none")
    ~generation:(if tick<4 then 1 else 2) ~antigen:(tick<>4) ~controller:(tick<>3) tick)in
  let state=run admitted(domain original admitted reset_stopping)
    (List.mapi(fun tick active->sample ~generation:(if tick<7 then 1 else 2)tick active)
      [false;false;true;true;true;false;false;true;true;true;true])in
  require "reset while stopping does not postpone original controller deadline"(status state "controller-off"<>"fail" &&
    List.exists(fun event->text "action" event="discharged" && Json.equal(get "deadline_tick" event)(Json.int 5))(events state "controller-off"))

let () =
  require "expected RC5 complete original fixture"(Array.length Sys.argv=2);
  let channel=open_in_bin Sys.argv.(1)in
  let raw=Fun.protect ~finally:(fun()->close_in channel)(fun()->really_input_string channel(in_channel_length channel))in
  let original=get "original"(Json.parse raw)in
  source_controls original;causal_controls original;evidence_controls original;lifecycle_controls original;
  Printf.printf "controlled source monitor: %d independent literal source, evidence, lifecycle and deadline assertions passed\n" !count
