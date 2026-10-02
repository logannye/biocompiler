(** Experimental standalone checking. No producer or source evaluator is linked.
    Successful protocol execution can return a failing or unresolved assessment. *)
val validation_scope : string
val profile : Bioc_wire.Json.t
val verify : replay:bool -> Bioc_wire.Json.t -> Bioc_wire.Json.t
val wrap : raw_request:Bioc_wire.Json.t -> raw_build:Bioc_wire.Json.t ->
  Bioc_domain.Architecture_assessment.t -> Bioc_wire.Json.t
