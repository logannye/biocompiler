(** Exactly two complete program strategies, freshly checked before ranking.
    The production entry point always uses the native generator. *)
val selection_version : string
val implementation_version : string
type limits
val make_limits : ?max_work:int -> ?max_monitor_items:int -> ?max_request_bytes:int ->
  ?max_report_bytes:int -> ?max_report_nodes:int -> unit -> limits
val default_limits : limits
val limits_json : limits -> Bioc_wire.Json.t
type usage = { work_charged:int; request_bytes:int; report_bytes:int; retained_peak:int }
module type PROPOSER = sig
  val propose : config:Bioc_domain.Synthetic_authority.Config.t -> limits:Generator.limits ->
    parent:Bioc_checker.Work_budget.t -> Bioc_domain.Realization_request.t ->
    Bioc_domain.Synthetic_authority.Candidate.t
end
module type SELECTOR = sig
  val select_with_usage : ?until:Bioc_domain.Runtime_number.t ->
    ?config:Bioc_domain.Synthetic_authority.Config.t -> ?limits:limits ->
    ?parent:Bioc_checker.Work_budget.t -> Bioc_domain.Realization_request.t ->
    Bioc_domain.Execution_data.Input_frame.t list -> Bioc_domain.Synthetic_selection.Result.t * usage
  val select : ?until:Bioc_domain.Runtime_number.t ->
    ?config:Bioc_domain.Synthetic_authority.Config.t -> ?limits:limits ->
    ?parent:Bioc_checker.Work_budget.t -> Bioc_domain.Realization_request.t ->
    Bioc_domain.Execution_data.Input_frame.t list -> Bioc_domain.Synthetic_selection.Result.t
end
(* Native test seam for independently retained producer corruption cases. Only
   proposals can vary: policy, fresh acceptance, dependencies and ranking remain
   the production implementations. There is no wire callback/check override. *)
module Make (_:PROPOSER) : SELECTOR
include SELECTOR
