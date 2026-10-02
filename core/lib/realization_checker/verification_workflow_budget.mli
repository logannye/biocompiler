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
(* Structural workflow work always charges the operation ancestor; the supplied
   evaluator child retains its complete independent 50M allowance. *)
val evaluation_codec : t -> Bioc_checker.Work_budget.t -> Bioc_domain.Verification_exploration.Codec.limits
val evaluation : t -> Bioc_checker.Work_budget.t
val realization_limits : t -> Realization_check.limits
val synthetic_limits : t -> Synthetic_candidate_check.limits
(* Reserve each complete raw incoming artifact exactly once before staged import.
   Transport reads/parsing/hash passes charge [charge] on this same budget. *)
val reserve_request : t -> Bioc_wire.Json.t -> unit
(* Retain/release live inventories; work is never refunded. *)
val retain : t -> int -> unit
val release : t -> int -> unit
(* Incremental caller-owned lifetimes survive final publication transfer.
   Successful reservations charge before mutation; release never refunds work.
   A released scope cannot be retained into or released again. *)
type scope
val create_scope : t -> scope
val retain_in_scope : scope -> int -> unit
val release_scope : scope -> unit
val with_retained : t -> int -> (unit -> 'a) -> 'a
val with_workspace : t -> (unit -> 'a) -> 'a
val history_size : t -> Bioc_domain.Execution_data.Input_frame.t list -> Bioc_domain.Verification_exploration.Codec.size
val equal_json : t -> Bioc_wire.Json.t -> Bioc_wire.Json.t -> bool
(* Final artifact encoding under the same budget, including prospective workspace. *)
val encode_report : t -> Bioc_wire.Json.t -> string
(* Incremental child records transfer into the final report; final validation
   does not charge their publication capacity a second time. *)
val reserve_report_fragment : t -> Bioc_wire.Json.t -> unit
val publish : t -> Bioc_wire.Json.t -> unit
type usage = { work_charged:int; evaluations:int; request_bytes:int; report_bytes:int;
  report_nodes:int; retained_peak:int }
val usage : t -> usage
