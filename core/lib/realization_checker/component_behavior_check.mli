(** Fresh behavior checking of the actual locked assembly. This independently
    reconstructs and executes its records, checks generic linking, and retains
    the complete conditional finite-history result. It does not prove source
    correspondence to a synthetic generator or empirical biological behavior. *)
val implementation_version : string
type limits
(* Every reduction is propagated to execution and generic composition linking;
   both phases and actual reconstruction consume the same ancestor work. *)
val make_limits : ?max_work:int -> ?max_monitor_items:int -> ?max_request_bytes:int ->
  ?max_report_bytes:int -> ?max_report_nodes:int -> unit -> limits
val default_limits : limits
val limits_json : limits -> Bioc_wire.Json.t
type usage = { work_charged : int; reconstruction_work : int }
val check_with_usage : ?until:Bioc_domain.Runtime_number.t -> ?limits:limits ->
  ?parent:Bioc_checker.Work_budget.t -> Bioc_domain.Realization_request.t ->
  Bioc_domain.Component_assembly.t -> Bioc_domain.Execution_data.Input_frame.t list ->
  Bioc_domain.Realization_evidence.Check_result.t * usage
val check : ?until:Bioc_domain.Runtime_number.t -> ?limits:limits ->
  ?parent:Bioc_checker.Work_budget.t -> Bioc_domain.Realization_request.t ->
  Bioc_domain.Component_assembly.t -> Bioc_domain.Execution_data.Input_frame.t list ->
  Bioc_domain.Realization_evidence.Check_result.t
