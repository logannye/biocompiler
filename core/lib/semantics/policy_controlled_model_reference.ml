open Bioc_wire
module R = Bioc_domain.Policy_controlled_composition_request
module Domain = Bioc_domain.Policy_controlled_domain
module Sample = Bioc_domain.Policy_controlled_activity_sample

type phase = Quiet | Waiting of int * int | Engaged of int | Releasing of int * int
type t = {
  domain : Domain.validated; cursor : Domain.cursor;
  onset : int; cessation : int; reactivation : int;
  phase : phase; ever_active : bool;
}

let field charge name value =
  let rec find = function
    | [] -> Diagnostic.fail "policy_controlled_reference" "Original model field is absent."
    | (key,value)::rest -> charge (1 + String.length key);
        if key=name then value else find rest in
  charge 1; find (Json.object_fields value)

let initialize ~charge ~original ~domain =
  charge 1;
  Diagnostic.require (Domain.fingerprint (Domain.specification domain)=Domain.fingerprint (R.domain original))
    "policy_controlled_reference" "The model reference requires the original complete operating domain.";
  let model = field charge "mechanism_model" (R.raw original) in
  let body = field charge "body" model in
  let delays = field charge "delays" body in
  let delay name =
    let value = Json.integer (field charge name delays) in
    Diagnostic.require (Z.sign value>0 && Z.leq value (Z.of_int 10000))
      "policy_controlled_reference" "Original model delays must be positive bounded integral ticks.";
    Z.to_int value in
  Diagnostic.require (Json.string (field charge "initial_activity" body)="background")
    "policy_controlled_reference" "Only the declared background initial model state is supported.";
  let onset=delay "onset_ticks" in
  let cessation=delay "cessation_ticks" in
  let reactivation=delay "reactivation_ticks" in
  {domain;cursor=Domain.initial ~charge domain;onset;cessation;reactivation;phase=Quiet;ever_active=false}

let pending (state:t) = match state.phase with Waiting _ | Releasing _ -> true | Quiet | Engaged _ -> false

let step ~charge (state:t) (input:Domain.input_batch) =
  charge 1;
  let cursor = Domain.advance ~charge state.domain state.cursor input in
  let gate = input.live && input.event<>Domain.End && input.event<>Domain.Reset &&
    input.physical.antigen && input.physical.controller && input.physical.protein_a && input.physical.protein_b in
  let initiate ever_active = Waiting (input.tick + (if ever_active then state.reactivation else state.onset),input.generation) in
  let phase,ever_active = match state.phase with
    | Quiet -> (if gate then initiate state.ever_active else Quiet),state.ever_active
    | Waiting (due,generation) ->
        if not gate || generation<>input.generation then Quiet,state.ever_active
        else if input.tick>=due then Engaged generation,true
        else state.phase,state.ever_active
    | Engaged generation ->
        (if gate then state.phase else Releasing (input.tick+state.cessation,generation)),state.ever_active
    | Releasing (due,_) when input.tick>=due ->
        (if gate then initiate true else Quiet),true
    | Releasing _ -> state.phase,state.ever_active in
  let band,activation_generation = match phase with
    | Quiet | Waiting _ -> Sample.Background,None
    | Engaged generation | Releasing (_,generation) -> Sample.Active,Some generation in
  let sample : Sample.t = {tick=input.tick;band;activation_generation} in
  {state with cursor;phase;ever_active},sample
