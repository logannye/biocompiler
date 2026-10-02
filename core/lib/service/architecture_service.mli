(** Experimental standalone checking. No producer or source evaluator is linked.
    Successful protocol execution can return a failing or unresolved assessment. *)
val validation_scope : string
val profile : Bioc_wire.Json.t
val verify : replay:bool -> Bioc_wire.Json.t -> Bioc_wire.Json.t
