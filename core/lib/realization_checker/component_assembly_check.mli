(** Fresh source correspondence for an actual component assembly, including
    synthetic acceptance over the exact supplied history, independently derived
    declarations, generic linking and independently reconstructed behavior.
    Neither imported claims nor matching hashes alone grant acceptance. *)
val implementation_version : string
type limits
val make_limits : ?max_work:int -> ?max_monitor_items:int -> ?max_request_bytes:int ->
  ?max_report_bytes:int -> ?max_report_nodes:int -> unit -> limits
val default_limits : limits
val limits_json : limits -> Bioc_wire.Json.t
type usage = { work_charged : int; reconstruction_work : int; authority_work : int;
  request_bytes : int; report_bytes : int; retained_peak : int }
val check_with_usage : ?until:Bioc_domain.Runtime_number.t -> ?limits:limits ->
  ?parent:Bioc_checker.Work_budget.t -> Bioc_domain.Realization_request.t ->
  Bioc_domain.Synthetic_authority.Candidate.t -> Bioc_domain.Component_assembly.t ->
  Bioc_domain.Execution_data.Input_frame.t list -> Bioc_domain.Composition_evidence.Result.t * usage
val check : ?until:Bioc_domain.Runtime_number.t -> ?limits:limits ->
  ?parent:Bioc_checker.Work_budget.t -> Bioc_domain.Realization_request.t ->
  Bioc_domain.Synthetic_authority.Candidate.t -> Bioc_domain.Component_assembly.t ->
  Bioc_domain.Execution_data.Input_frame.t list -> Bioc_domain.Composition_evidence.Result.t
