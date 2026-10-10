(** Fresh module elaboration and linked material checks. The existing material
    path remains independently required; serialized linkage grants no capability. *)
open Bioc_wire
val operations : string list
val linking_operations : string list
val material_operations : string list
val schema_version : string
val implementation : string
val validation_scope : string
val material_schema_version : string
val material_implementation : string
val material_validation_scope : string
val max_result_bytes : int
val max_result_nodes : int
val profile : Json.t
val material_profile : Json.t
val producer_profile : Json.t
val validate_input : Json.t -> unit
val check_linkage : modules:Json.t -> request:Json.t ->
  Bioc_checker.Policy_module_linking_check.checked_linkage
val check : export:bool -> modules:Json.t -> request:Json.t -> candidate:Json.t ->
  limits:Json.t -> Json.t
val handle : operation:string -> Json.t -> Json.t
