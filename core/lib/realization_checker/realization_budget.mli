(** Explicit native resource accounting; no semantic or acceptance authority. *)
val resource_profile : string
type limits
val make_limits : ?max_work:int -> ?max_monitor_items:int -> ?max_request_bytes:int ->
  ?max_report_bytes:int -> ?max_report_nodes:int -> unit -> limits
val default_limits : limits
val limits_json : limits -> Bioc_wire.Json.t
type t
val create : ?parent:Bioc_checker.Work_budget.t -> ?limits:limits -> unit -> t
val work : t -> Bioc_checker.Work_budget.t
val charge : t -> int -> unit
val remaining : t -> int
val is_resource_error : t -> Bioc_wire.Diagnostic.t -> bool
val bounded_list : t -> 'a list -> 'a list
val reserve_request : t -> Bioc_wire.Json.t -> unit
(* Publication traversal consumes the same shared work allowance. *)
val reserve_report : t -> Bioc_wire.Json.t -> unit
val validate_report : t -> Bioc_domain.Realization_evidence.Check_result.t -> unit
(* Hold this much available work outside an engine allocation, for bounded
   ordinary-failure diagnostic creation and complete UNKNOWN publication. It is
   capacity only: unused work is not charged, refunded, or reported consumed. *)
val failure_finish_allowance : t -> int
val retain_monitor : t -> int -> unit
val release_monitor : t -> int -> unit
val burn_failure : t -> int -> unit
type usage = { work_charged : int; reserved_failure_work : int; monitor_peak : int;
  request_bytes : int; report_bytes : int }
val usage : t -> usage
