(** Read-only original-authority admission. This service cannot create a
    candidate, checked material capability, behavioral verdict or artifact. *)
open Bioc_wire
val operations : string list
val validation_scope : string
val implementation : string
val schema_version : string
val resource_profile : string
val max_result_bytes : int
val max_result_nodes : int
val profile : Json.t
(** Prepared results cannot be published until their one-shot guard accepts the
    exact full protocol frame under the same original work/publication owner. *)
val prepare : executable:Protocol.executable -> request:Protocol.request ->
  Json.t * (Json.t -> unit)
