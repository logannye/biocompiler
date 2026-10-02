(** Produce complete software component declarations from a freshly accepted
    actual candidate. The result preserves its bounded history acceptance;
    adaptation does not establish linking or biological validity. *)
val adapter_version : string
type t
val registry : t -> Bioc_domain.Component_registry.t
val composition : t -> Bioc_domain.Composition.t
val acceptance : t -> Bioc_domain.Realization_evidence.Check_result.t
val to_json : t -> Bioc_wire.Json.t
type limits
val make_limits : ?max_work:int -> ?max_monitor_items:int -> ?max_request_bytes:int ->
  ?max_report_bytes:int -> ?max_report_nodes:int -> unit -> limits
val default_limits : limits
val limits_json : limits -> Bioc_wire.Json.t
type usage = { work_charged : int; request_bytes : int; report_bytes : int; retained_peak : int }
val adapt_with_usage : ?until:Bioc_domain.Runtime_number.t -> ?limits:limits ->
  ?parent:Bioc_checker.Work_budget.t -> Bioc_domain.Realization_request.t ->
  Bioc_domain.Synthetic_authority.Candidate.t -> Bioc_domain.Execution_data.Input_frame.t list -> t * usage
val adapt : ?until:Bioc_domain.Runtime_number.t -> ?limits:limits ->
  ?parent:Bioc_checker.Work_budget.t -> Bioc_domain.Realization_request.t ->
  Bioc_domain.Synthetic_authority.Candidate.t -> Bioc_domain.Execution_data.Input_frame.t list -> t
