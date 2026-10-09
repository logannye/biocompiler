(** Fresh named evidence, derived only after complete material checking.
    This supplementary service grants no export authority and leaves existing
    material reports unchanged. *)
open Bioc_wire
val operations : string list
val schema_version : string
val implementation : string
val validation_scope : string
val profile : Json.t
val handle : operation:string -> Json.t -> Json.t
