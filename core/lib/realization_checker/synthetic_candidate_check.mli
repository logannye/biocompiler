(** Fresh synthetic source provenance and finite-history acceptance. Candidate
    execution remains independent of source derivation; source labels, saved
    results and exact catalog identities alone never establish behavior. *)
val checker_version : string
val implementation_version : string
type limits
val make_limits : ?max_work:int -> ?max_monitor_items:int -> ?max_request_bytes:int ->
  ?max_report_bytes:int -> ?max_report_nodes:int -> unit -> limits
val default_limits : limits
val limits_json : limits -> Bioc_wire.Json.t
type usage = { work_charged : int }
val check_with_usage : ?until:Bioc_domain.Runtime_number.t -> ?limits:limits ->
  ?parent:Bioc_checker.Work_budget.t -> Bioc_domain.Realization_request.t ->
  Bioc_domain.Synthetic_authority.Candidate.t -> Bioc_domain.Execution_data.Input_frame.t list ->
  Bioc_domain.Realization_evidence.Check_result.t * usage
val check : ?until:Bioc_domain.Runtime_number.t -> ?limits:limits ->
  ?parent:Bioc_checker.Work_budget.t -> Bioc_domain.Realization_request.t ->
  Bioc_domain.Synthetic_authority.Candidate.t -> Bioc_domain.Execution_data.Input_frame.t list ->
  Bioc_domain.Realization_evidence.Check_result.t
