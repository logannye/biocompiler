(** Native source assessment only. It grants no executable, molecular or use acceptance. *)
val operations : string list
val validation_scope : string
val profile : Bioc_wire.Json.t
val handle : operation:string -> Bioc_wire.Json.t -> Bioc_wire.Json.t
