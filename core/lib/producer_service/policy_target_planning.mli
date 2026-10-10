(** Bounded producer-side diagnostic planning. Plans are inert and never consumed
    by admission, execution, preservation, material checking or export. *)
open Bioc_wire
val implementation : string
val validation_scope : string
val resource_profile : string
val operations : string list
val profile : Json.t
val handle : operation:string -> Json.t -> Json.t
