(** Deterministic software-model production. A proposal grants neither finite
    history acceptance nor biological applicability. *)
val resource_profile : string
type error = { message : string; node_id : string option;
  source : Bioc_domain.Behavior.source_location option }
exception Unsupported of error
val format_error : error -> string
type policy
val policy_for_request : budget:Bioc_realization_checker.Realization_budget.t ->
  Bioc_realization_checker.Checked_request.t -> profile:string -> policy
val violations : budget:Bioc_realization_checker.Realization_budget.t -> policy ->
  Bioc_domain.Mechanism.t -> string list
val minimize : policy -> string
type limits
val make_limits : ?max_work:int -> ?max_monitor_items:int -> ?max_request_bytes:int ->
  ?max_report_bytes:int -> ?max_report_nodes:int -> unit -> limits
val default_limits : limits
val limits_json : limits -> Bioc_wire.Json.t
type usage = { work_charged : int; request_bytes : int; report_bytes : int; retained_peak : int }
(* Propose preserves a complete generated graph even when hard policy rejects
   it. Generate additionally checks that policy against the actual proposal. *)
val propose_with_usage : ?config:Bioc_domain.Synthetic_authority.Config.t -> ?limits:limits ->
  ?parent:Bioc_checker.Work_budget.t -> Bioc_domain.Realization_request.t ->
  Bioc_domain.Synthetic_authority.Candidate.t * usage
val propose : ?config:Bioc_domain.Synthetic_authority.Config.t -> ?limits:limits ->
  ?parent:Bioc_checker.Work_budget.t -> Bioc_domain.Realization_request.t ->
  Bioc_domain.Synthetic_authority.Candidate.t
val generate_with_usage : ?config:Bioc_domain.Synthetic_authority.Config.t -> ?limits:limits ->
  ?parent:Bioc_checker.Work_budget.t -> Bioc_domain.Realization_request.t ->
  Bioc_domain.Synthetic_authority.Candidate.t * usage
val generate : ?config:Bioc_domain.Synthetic_authority.Config.t -> ?limits:limits ->
  ?parent:Bioc_checker.Work_budget.t -> Bioc_domain.Realization_request.t ->
  Bioc_domain.Synthetic_authority.Candidate.t
