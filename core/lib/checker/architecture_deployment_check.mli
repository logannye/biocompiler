(** Exact decimal interval checks against full original architecture authority.
    These prove declared interval containment only, never delivery predictions
    or fresh architecture acceptance. Cached derived intervals are ignored. *)
val checker_version : string
type budget
val max_work : int
val make_budget : ?parent:Work_budget.t -> ?maximum:int -> unit -> budget
module Inventory : sig
  type t
  val make : placements:Bioc_wire.Json.t list -> availability:Bioc_wire.Json.t list -> t
  val of_json : Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
end
type result = { failures : string list; witnesses : Bioc_wire.Json.t list }
val check : ?budget:budget -> request:Bioc_domain.Architecture_request.t -> inventory:Inventory.t -> unit -> result
val check_json : ?budget:budget -> request:Bioc_wire.Json.t -> inventory:Bioc_wire.Json.t -> unit -> result
