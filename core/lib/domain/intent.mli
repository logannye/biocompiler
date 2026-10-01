(** Validated intent structure and typed literals. This type makes no claim
    about operation semantics, lowering, realization or biological function. *)
type t
val schema_version : string
val validation_scope : string
val of_json : Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val summary : t -> Bioc_wire.Json.t
