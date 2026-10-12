(** Fresh construction checking and atomic-pair structural publication. Every
    response retains one original work owner through the full protocol frame. *)
open Bioc_wire
val operations : string list
val producer_operation : string
val validation_scope : string
val implementation : string
val schema_version : string
val resource_profile : string
val max_result_bytes : int
val max_result_nodes : int
val profile : Json.t
val producer_profile : Json.t
val prepare : executable:Protocol.executable -> request:Protocol.request ->
  Json.t * (Json.t -> unit)
val prepare_generated : executable:Protocol.executable -> request:Protocol.request ->
  produce:(charge:(int -> unit) -> Bioc_domain.Policy_controlled_composition_request.t ->
    Bioc_domain.Policy_controlled_material_candidate.t) -> Json.t * (Json.t -> unit)
