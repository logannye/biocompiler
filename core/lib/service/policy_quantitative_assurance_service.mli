(** Fresh conjunction of unchanged exact material checking, optional bounded
    approximation and separately reported supplied experimental compatibility.
    Replay never imports evidence as authority. Coupled export responses alone
    use the separately advertised paired wire bounds; every original child
    limit and report/manifest identity remains unchanged. *)
open Bioc_wire
val operations : string list
val schema_version : string
val implementation : string
val validation_scope : string
val profile : Json.t
val producer_profile : Json.t
val check : export:bool -> request:Json.t -> candidate:Json.t -> limits:Json.t -> Json.t
val handle : operation:string -> Json.t -> Json.t
