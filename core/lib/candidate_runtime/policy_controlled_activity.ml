module I = Bioc_domain.Policy_controlled_activity_implementation
module D = Bioc_domain.Policy_controlled_domain
module Sample = Bioc_domain.Policy_controlled_activity_sample
(* An executable fixed graph has one all-input gate and one stateful delayed
   primitive. Its parameters come from the candidate, never from a source
   evaluator, original-model interpreter or requirement monitor. *)
type phase = Quiet | Arming of int * int | Emitting of int | Draining of int * int
type state = {
  parameters:I.delays; domain:D.validated; cursor:D.cursor;
  phase:phase; has_activated:bool;
}
let initialize ~charge ~implementation ~domain : state =
  charge 1;
  {parameters=I.delays implementation;domain;cursor=D.initial ~charge domain;
    phase=Quiet;has_activated=false}
let step ~charge (state:state) (input:D.input_batch) : state * Sample.t =
  (* The original domain enforces the integral clock, finite horizon, lifecycle,
     suffix and exact batch/prefix lineage before any state transition. *)
  charge 8;
  let cursor = D.advance ~charge state.domain state.cursor input in
  let available = input.physical in
  let live = input.live && (match input.event with D.End | D.Reset -> false | _ -> true) in
  let enabled = live && available.antigen && available.controller &&
    available.protein_a && available.protein_b in
  let start () =
    let delay = if state.has_activated then state.parameters.reactivation_ticks
      else state.parameters.onset_ticks in
    Arming (input.tick + delay,input.generation) in
  let phase,has_activated = match state.phase with
    | Quiet -> (if enabled then start () else Quiet),state.has_activated
    | Arming (due,generation) ->
        if not enabled then Quiet,state.has_activated
        else if input.tick >= due then Emitting generation,true
        else state.phase,state.has_activated
    | Emitting generation ->
        (if enabled then state.phase else Draining (input.tick + state.parameters.cessation_ticks,generation)),true
    | Draining (due,_) ->
        if input.tick >= due then (if enabled then start () else Quiet),true
        else state.phase,true in
  let band,activation_generation = match phase with
    | Quiet | Arming _ -> Sample.Background,None
    | Emitting generation | Draining (_,generation) -> Sample.Active,Some generation in
  {state with cursor;phase;has_activated},
    {Sample.tick=input.tick;band;activation_generation}
let pending (state:state) = match state.phase with Arming _ | Draining _ -> true | _ -> false
