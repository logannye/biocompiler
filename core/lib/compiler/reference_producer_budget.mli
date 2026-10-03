(** Bounded work and complete input/output inventories for exact-reference
    producers. A resource reservation grants no acceptance authority. *)
val resource_profile : string
type limits
val make_limits : ?max_work:int -> ?max_input_bytes:int -> ?max_input_nodes:int ->
  ?max_output_bytes:int -> ?max_output_nodes:int -> unit -> limits
val default_limits : limits
val limits_json : limits -> Bioc_wire.Json.t
(* Clamp the independent checker to the producer's applicable reductions.
   Producer input nodes remain an aggregate reservation before checker entry;
   the checker additionally retains its own fixed input-node ceiling. *)
val checker_limits : limits -> Bioc_checker.Reference_construct_check.limits
type t
val create : ?parent:Bioc_checker.Work_budget.t -> limits -> t
val work : t -> Bioc_checker.Work_budget.t
val codec : t -> Bioc_domain.Verification_exploration.Codec.limits
val charge : t -> int -> unit
val charge_product : t -> int -> int -> unit
val input : t -> Bioc_wire.Json.t -> unit
val output : t -> Bioc_wire.Json.t -> unit
