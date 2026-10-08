(** Fresh full component-policy/material checking and paired exact-artifact export.
    No producer linkage or serialized acceptance reconstruction is available. *)
open Bioc_wire
val operations : string list
val validation_scope : string
val implementation : string
val schema_version : string
val resource_profile : string
val candidate_schema : string
val max_result_bytes : int
val max_result_nodes : int
val profile : Json.t
val producer_profile : Json.t
val validate_publication : Json.t -> unit
val check : export:bool -> request:Json.t -> candidate:Json.t -> limits:Json.t -> Json.t
val handle : operation:string -> Json.t -> Json.t
