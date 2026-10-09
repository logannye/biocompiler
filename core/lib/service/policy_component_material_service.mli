(** Fresh full component-policy/material checking and paired exact-artifact export.
    No producer linkage or serialized acceptance reconstruction is available. *)
open Bioc_wire
val operations : string list
val validation_scope : string
val implementation : string
val instance_implementation : string
val instance_validation_scope : string
val instance_profile : Json.t
val instance_producer_profile : Json.t
val prerequisite_implementation : string
val prerequisite_validation_scope : string
val prerequisite_profile : Json.t
val prerequisite_producer_profile : Json.t
val two_observation_implementation : string
val two_observation_validation_scope : string
val multi_member_implementation : string
val multi_member_validation_scope : string
val two_observation_profile : Json.t
val two_observation_producer_profile : Json.t
val multi_member_profile : Json.t
val multi_member_producer_profile : Json.t
val grounded_helper_implementation : string
val grounded_helper_validation_scope : string
val grounded_helper_profile : Json.t
val grounded_helper_producer_profile : Json.t
val finite_machine_implementation : string
val network_implementation : string
val network_validation_scope : string
val network_profile : Bioc_wire.Json.t
val network_producer_profile : Bioc_wire.Json.t
val finite_machine_validation_scope : string
val finite_machine_profile : Json.t
val finite_machine_producer_profile : Json.t
val quantitative_implementation : string
val quantitative_validation_scope : string
val quantitative_profile : Json.t
val quantitative_producer_profile : Json.t
val schema_version : string
val resource_profile : string
val candidate_schema : string
val max_result_bytes : int
val max_result_nodes : int
val profile : Json.t
val producer_profile : Json.t
val validate_publication : Json.t -> unit
(** Decode the complete originals and candidate, then repeat all checking.
    This helper never reconstructs acceptance from serialized evidence. *)
val fresh_check : request:Json.t -> candidate:Json.t -> limits:Json.t ->
  Bioc_domain.Policy_component_material_request.t * Bioc_realization_checker.Policy_component_material_check.result
val check : export:bool -> request:Json.t -> candidate:Json.t -> limits:Json.t -> Json.t
val handle : operation:string -> Json.t -> Json.t
