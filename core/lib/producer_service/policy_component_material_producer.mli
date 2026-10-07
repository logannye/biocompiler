(** Untrusted component selection/arrangement and construction, followed by fresh
    complete checking through the same producer-independent service. *)
open Bioc_wire
val compile : Json.t -> Json.t

(** Candidate production only: no child checker, publication or accepted state.
    A count-only owner can meter all lowering and construction work. *)
val construct_candidate : ?charge:(int -> unit) ->
  Bioc_domain.Policy_component_material_request.t -> Json.t
