(** Deferred Python object capabilities for a trusted callback channel. This
    adapter executes no acceptance rules and imports no manager records. The
    invoker must bind each action to the live channel's outstanding invocation.
    One bridge retains physical host identities and shares the manager budget.
    Arbitrary host code and closure captures are outside JSON resource bounds. *)
module M = Bioc_compiler.Pass_manager
module W = Bioc_checker.Work_budget
type t
val create : budget:W.t ->
  ?max_handles:int -> ?max_actions:int -> ?max_retained_bytes:int ->
  invoke:(action:string -> arguments:Bioc_wire.Json.t -> Bioc_wire.Json.t) -> unit -> t
val close : t -> unit
val of_reference : t -> Bioc_wire.Json.t -> M.host_value
val reference : t -> M.host_value -> Bioc_wire.Json.t
val literal : t -> M.host_constant -> M.host_value
val counts : t -> Bioc_wire.Json.t

(** The exact host tuple retained by a successful tuple materialization. This
    read-only identity sidecar cannot authorize a stage or change native checks. *)
val tuple_origin : t -> M.host_value list -> M.host_value option
