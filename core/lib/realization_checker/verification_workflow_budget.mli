(** Aggregate workflow accounting, separate from semantic history/evaluation caps.
    Every evaluator and all domain publication work share the same ancestor. *)
type limits
val resource_profile : string
val make_limits : ?max_work:int -> ?max_monitor_items:int -> ?max_request_bytes:int ->
  ?max_report_bytes:int -> ?max_report_nodes:int -> unit -> limits
val default_limits : limits
val limits_json : limits -> Bioc_wire.Json.t
type t
val create : ?limits:limits -> ?parent:Bioc_checker.Work_budget.t -> unit -> t
val limits : t -> limits
val work : t -> Bioc_checker.Work_budget.t
val charge : t -> int -> unit
val input_codec : t -> Bioc_domain.Verification_exploration.Codec.limits
val report_codec : t -> Bioc_domain.Verification_exploration.Codec.limits
val evaluation_codec : t -> Bioc_checker.Work_budget.t -> Bioc_domain.Verification_exploration.Codec.limits
val evaluation : t -> Bioc_checker.Work_budget.t
val realization_limits : t -> Realization_check.limits
val synthetic_limits : t -> Synthetic_candidate_check.limits
val reserve_request : t -> Bioc_wire.Json.t -> unit
(* Retain/release live inventories; work is never refunded. *)
val retain : t -> int -> unit
val release : t -> int -> unit
(* Incremental child records transfer into the final report; final validation
   does not charge their publication capacity a second time. *)
val reserve_report_fragment : t -> Bioc_wire.Json.t -> unit
val publish : t -> Bioc_wire.Json.t -> unit
type usage = { work_charged:int; evaluations:int; request_bytes:int; report_bytes:int;
  report_nodes:int; retained_peak:int }
val usage : t -> usage
