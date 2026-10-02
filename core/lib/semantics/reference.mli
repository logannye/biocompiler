(** Fresh-session, per-role reference execution of both closed Behavior profiles.
    Supplied observations are authoritative; action requests do not feed back
    into observations. This API establishes no molecular or empirical claim. *)
type budget
val make_budget : ?max_work:int -> ?max_frames:int -> ?max_trace_items:int -> unit -> budget
val default_budget : budget
val budget_json : budget -> Bioc_wire.Json.t
val evaluator_version : string
type usage = { work : int; frames : int; trace_items : int }
(* Consumed work includes preparation, every scheduler/evaluation step and trace
   retention. A failed execution returns neither a partial trace nor usage. *)
val evaluate_with_usage :
  ?role:string -> ?until:Bioc_domain.Runtime_number.t -> ?max_microsteps:int ->
  ?budget:budget -> Bioc_domain.Behavior.t ->
  Bioc_domain.Execution_data.Input_frame.t list ->
  Bioc_domain.Execution_data.Result.t * usage
val evaluate :
  ?role:string -> ?until:Bioc_domain.Runtime_number.t -> ?max_microsteps:int ->
  ?budget:budget -> Bioc_domain.Behavior.t ->
  Bioc_domain.Execution_data.Input_frame.t list ->
  Bioc_domain.Execution_data.Result.t
