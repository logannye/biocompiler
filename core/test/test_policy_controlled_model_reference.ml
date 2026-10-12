(* Direct original-model equations are tested against hand-authored observations,
   without importing a candidate, producer, or candidate activity runtime. *)
open Bioc_wire
module R = Bioc_domain.Policy_controlled_composition_request
module F = Bioc_domain.Policy_controlled_domain
module A = Bioc_domain.Policy_controlled_activity_sample
module Admit = Bioc_checker.Policy_controlled_composition_admission
module Reference = Bioc_semantics.Policy_controlled_model_reference
let checks=ref 0
let require label condition=incr checks;if not condition then failwith label
let charge _ = ()
let obj fields=Json.Object fields
let str value=Json.String value
let arr values=Json.Array values
let get key value=Json.field key(Json.object_fields value)
let set key replacement value=obj(List.map(fun(name,value)->name,if name=key then replacement else value)(Json.object_fields value))
let update key f value=set key(f(get key value))value
let physical key value=update "physical"(set key(str value))
let frame ?(event="none") ?(generation=1) tick = obj[
  "tick",Json.int tick;"event",str event;
  "physical",obj["antigen",str "present";"controller",str "enabled";"rna_a",str "present";
    "rna_b",str "present";"protein_a",str "present";"protein_b",str "present"];
  "evidence",obj(List.map(fun key->key,obj["status",str "valid";"observed_tick",Json.int tick;
    "generation",(if key="antigen" then Json.int generation else Json.Null)])
    ["antigen";"controller";"rna_a";"rna_b";"protein_a";"protein_b"])]
let fixed f=List.init 11(fun tick->f tick(frame ~event:(if tick=0 then "start" else "none") tick))
let with_domain rows original=update "operating_domain"(fun domain->domain
  |>set "fixed_inputs"(arr rows)|>set "physical_factors"(arr[])|>set "evidence_factors"(arr[])|>set "lifecycle_factors"(arr[]))original
let with_delays onset cessation reactivation original=
  let delays=obj["onset_ticks",Json.int onset;"cessation_ticks",Json.int cessation;"reactivation_ticks",Json.int reactivation]in
  let model=get "mechanism_model" original in
  let body=set "delays" delays(get "body" model)in
  let identity=set "content_fingerprint"(str(Canonical.fingerprint body))(get "identity" model)in
  original |>set "mechanism_model"(model|>set "body" body|>set "identity" identity)
    |>update "catalog_binding"(set "model_identity" identity)
    |>update "source_authority"(update "control_contract"(set "actual_delays" delays))
let prepare raw=
  let original=R.of_json raw in
  let admission=Admit.admit ~charge original in
  original,Admit.domain admission
let histories domain=
  let found=ref[]in
  (match F.enumerate ~on_history:(fun values->found:=values::!found)domain with
   |F.Complete _->()|_->failwith "Original finite domain did not complete");List.rev !found
let execute original domain inputs=
  let state=Reference.initialize ~charge ~original ~domain in
  let final,samples=List.fold_left(fun(state,values)input->let next,value=Reference.step ~charge state input in next,value::values)(state,[])inputs in
  final,List.rev samples
let trace raw=
  let original,domain=prepare raw in
  match histories domain with [inputs]->execute original domain inputs|_->failwith "Expected one literal original history"
let assert_trace label expected generations (state,samples)=
  require(label^": complete original ticks")(List.map(fun(sample:A.t)->sample.tick)samples=List.init 11 Fun.id);
  require(label^": literal bands")(List.map(fun(sample:A.t)->sample.band=A.Active)samples=expected);
  require(label^": literal activation generations")(List.map(fun(sample:A.t)->sample.activation_generation)samples=generations);
  require(label^": no unresolved model timer")(not(Reference.pending state))
let generations bands=List.map(fun active->if active then Some 1 else None)bands
let reject code f=match f()with
  |_->failwith("Expected "^code)|exception Diagnostic.Error diagnostic->require("exact rejection "^code)(diagnostic.code=code)
let run raw=
  let original,domain=prepare raw in
  let traces=List.map(execute original domain)(histories domain)in
  require "original Cartesian two-history fixture retained"(List.length traces=2);
  let literal_a=[false;true;true;false;true;true;false;true;true;true;true]in
  let literal_b=[false;true;true;true;true;true;false;true;true;true;true]in
  let actual=List.map(fun(_,samples)->List.map(fun(sample:A.t)->sample.band=A.Active)samples)traces in
  require "reference original two-history literal oracle"(List.sort compare actual=List.sort compare[literal_a;literal_b]);
  let normal=[false;false;true;true;true;false;false;false;true;true;true]in
  let rows=fixed(fun tick value->if tick>=3 && tick<6 then physical "controller" "disabled" value else value)in
  let baseline=raw|>with_domain rows|>with_delays 2 2 2 in
  assert_trace "actual delay two" normal(generations normal)(trace baseline);
  let fast=[false;true;true;true;false;false;false;true;true;true;true]in
  assert_trace "actual model delays independent of source maximum two" fast(generations fast)(trace(with_delays 1 1 1 baseline));
  let tightened=baseline
    |>update "source_authority"(fun authority->authority
      |>update "document"(update "program"(update "declarations"(fun values->arr(List.map(fun value->
        if get "id" value=str "onset" then update "deadline"(set "amount"(str "1"))value else value)(Json.array values)))))
      |>update "control_contract"(update "requested_deadlines"(set "onset_ticks"(Json.int 1))))
    |>update "operating_domain"(update "source_deadlines"(set "onset_ticks"(Json.int 1)))in
  assert_trace "tighter source does not rewrite actual original equations"normal(generations normal)(trace tightened);
  let unequal=[false;true;true;true;true;true;false;false;true;true;true]in
  assert_trace "separate original onset, cessation and reactivation" unequal(generations unequal)(trace(with_delays 1 3 2 baseline));
  let uninterrupted=[false;false;true;true;true;true;true;true;true;true;true]in
  let continuous=with_domain(fixed(fun _ value->value))baseline in
  assert_trace "continuous qualified gate" uninterrupted(generations uninterrupted)(trace continuous);
  List.iter(fun key->
    let changed=with_domain(fixed(fun tick value->if tick>=3 then physical key "absent" value else value))baseline in
    assert_trace(key^" does not remove persisting protein")uninterrupted(generations uninterrupted)(trace changed)) ["rna_a";"rna_b"];
  List.iter(fun key->
    let changed=with_domain(fixed(fun tick value->if tick>=3 && tick<6 then physical key "absent" value else value))baseline in
    assert_trace(key^" loss and recovery")normal(generations normal)(trace changed))["antigen";"protein_a";"protein_b"];
  let absent=with_domain(fixed(fun _ value->physical "antigen" "absent" value))baseline in
  assert_trace "controller without antigen stays background"(List.init 11(fun _->false))(List.init 11(fun _->None))(trace absent);
  let cancelled=[false;false;false;false;false;true;true;true;true;true;true]in
  let maturity=with_domain(fixed(fun tick value->if tick=2 then physical "controller" "disabled" value else value))baseline in
  assert_trace "disabling precedes activation maturity"cancelled(generations cancelled)(trace maturity);
  let restored=[false;false;true;true;true;false;false;true;true;true;true]in
  let restoration=with_domain(fixed(fun tick value->if tick=3 then physical "controller" "disabled" value else value))baseline in
  assert_trace "restoration cannot cancel committed cessation"restored(generations restored)(trace restoration);
  let repeat=with_domain(fixed(fun tick value->if tick=3 || tick=5 then physical "controller" "disabled" value else value))baseline in
  assert_trace "repeat on original due tick does not postpone stop"normal(generations normal)(trace repeat);
  let reset_rows=List.init 11(fun tick->frame ~event:(if tick=0 then "start" else if tick=3 then "reset" else "none")
    ~generation:(if tick<3 then 1 else 2)tick|>fun value->if tick=3 then physical "antigen" "absent" value else value)in
  let reset_generations=[None;None;Some 1;Some 1;Some 1;None;None;Some 2;Some 2;Some 2;Some 2]in
  assert_trace "reset preserves residual executor activity"restored reset_generations(trace(with_domain reset_rows baseline));
  let reset_stopping=List.init 11(fun tick->frame ~event:(if tick=0 then "start" else if tick=4 then "reset" else "none")
    ~generation:(if tick<4 then 1 else 2)tick|>fun value->if tick=3 then physical "controller" "disabled" value
      else if tick=4 then physical "antigen" "absent" value else value)in
  assert_trace "reset while stopping retains committed deadline"restored reset_generations(trace(with_domain reset_stopping baseline));
  let pending_reset=List.init 11(fun tick->frame ~event:(if tick=0 then "start" else if tick=1 then "reset" else "none")
    ~generation:(if tick<1 then 1 else 2)tick|>fun value->if tick=1 then physical "antigen" "absent" value else value)in
  let rearmed=[false;false;false;false;true;true;true;true;true;true;true]in
  assert_trace "reset cancels initial onset"rearmed(List.map(fun active->if active then Some 2 else None)rearmed)
    (trace(with_domain pending_reset baseline));
  let end_rows=List.init 11(fun tick->frame ~event:(if tick=0 || tick=6 then "start" else if tick=3 then "end" else "none")
    ~generation:(if tick<6 then 1 else 2)tick|>fun value->if tick>=3 && tick<6 then physical "antigen" "absent" value else value)in
  assert_trace "end/start preserves executor controller"normal
    [None;None;Some 1;Some 1;Some 1;None;None;None;Some 2;Some 2;Some 2](trace(with_domain end_rows baseline));
  let missing=List.map(update "evidence"(fun value->obj(List.map(fun(key,_)->key,obj["status",str "missing";
    "observed_tick",Json.Null;"generation",Json.Null])(Json.object_fields value))))rows in
  assert_trace "model equations do not turn missing evidence into OFF"normal(generations normal)(trace(with_domain missing baseline));
  let pending,_=trace(with_delays 64 2 2 continuous)in
  require "unresolved actual model delay retained at horizon"(Reference.pending pending);
  let original,domain=prepare baseline in
  let inputs=List.hd(histories domain)in
  let state=Reference.initialize ~charge ~original ~domain in
  let next,_=Reference.step ~charge state(List.hd inputs)in
  reject "policy_controlled_domain_cursor"(fun()->Reference.step ~charge next(List.hd inputs));
  reject "policy_controlled_domain_cursor"(fun()->Reference.step ~charge state(List.nth inputs 1));
  let _,foreign=prepare continuous in
  reject "policy_controlled_reference"(fun()->Reference.initialize ~charge ~original ~domain:foreign);
  reject "fixture_budget"(fun()->Reference.initialize ~charge:(fun _->Diagnostic.fail "fixture_budget" "No work remains.")~original ~domain);
  reject "fixture_budget"(fun()->Reference.step ~charge:(fun _->Diagnostic.fail "fixture_budget" "No work remains.")state(List.hd inputs))
let () =
  require "expected complete RC5 original fixture"(Array.length Sys.argv=2);
  let channel=open_in_bin Sys.argv.(1)in
  let bytes=Fun.protect ~finally:(fun()->close_in channel)(fun()->really_input_string channel(in_channel_length channel))in
  run(get "original"(Json.parse bytes));
  Printf.printf "controlled original model reference: %d independent literal timeline and authority assertions passed\n" !checks
