(** Independent fresh-session execution of the complete 14-operation synthetic
    mechanism profile. This digital trace is neither source-reference execution
    nor evidence of molecular or empirical function. *)
val implementation_version : string
val runner_version : string
val resource_profile : string

type limits
val make_limits : ?max_work:int -> ?max_frames:int -> ?max_trace_items:int ->
  ?max_trace_bytes:int -> ?max_state_items:int -> unit -> limits
val default_limits : limits
val limits_json : limits -> Bioc_wire.Json.t

type usage = { work : int; frames : int; trace_items : int; trace_bytes : int }
(* Caller limits can only reduce the fixed native resource profile. Work covers
   complete supplied history/graph preparation, settlement, scheduling and trace
   retention. Trace items count JSON values and object keys. Retained temporal
   stores and the current settlement share the state-item ceiling. Failure
   returns neither a partial trace nor a successful usage receipt. *)
val run_with_usage : ?until:Bioc_domain.Runtime_number.t -> ?limits:limits ->
  Bioc_domain.Mechanism.t -> Bioc_domain.Model_execution_data.Input_frame.t list ->
  Bioc_domain.Model_execution_data.Trace.t * usage
val run : ?until:Bioc_domain.Runtime_number.t -> ?limits:limits ->
  Bioc_domain.Mechanism.t -> Bioc_domain.Model_execution_data.Input_frame.t list ->
  Bioc_domain.Model_execution_data.Trace.t
