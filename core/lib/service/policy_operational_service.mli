(** Checked bounded reference execution. No target, realization or RNA authority. *)
val operations : string list
val validation_scope : string
val profile : Bioc_wire.Json.t
val producer_profile : Bioc_wire.Json.t
val wrap : payload:Bioc_wire.Json.t -> candidate:Bioc_wire.Json.t ->
  report:Bioc_wire.Json.t -> Bioc_wire.Json.t
val lowering_report : document:Bioc_domain.Policy_document.t ->
  correspondence:Bioc_wire.Json.t -> Bioc_wire.Json.t
val handle : operation:string -> Bioc_wire.Json.t -> Bioc_wire.Json.t
