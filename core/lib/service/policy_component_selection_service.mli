(** Producer-independent complete-catalog check/replay/fresh export.
    The result is preparation data until its one-shot callback admits the actual
    complete Protocol.response under the same original work/publication owner. *)
open Bioc_wire
val operations : string list
val validation_scope : string
val implementation : string
val schema_version : string
val resource_profiles : string list
val candidate_schema : string
val manifest_schema : string
val export_schema : string
val publication_profile : string
val max_result_bytes : int
val max_result_nodes : int
val profile : Json.t
val prepare : executable:Protocol.executable -> request:Protocol.request ->
  Json.t * (Json.t -> unit)

val producer_operation : string
val producer_profile : Json.t
(** Core-only generation callback returns an untrusted complete candidate.
    Generation and mandatory fresh checking share the original owner through
    final-frame admission. Compile does not export or confer producer authority. *)
val prepare_generated : executable:Protocol.executable -> request:Protocol.request ->
  produce:(charge:(int -> unit) -> Bioc_domain.Policy_component_selection_request.t -> Json.t) -> Json.t * (Json.t -> unit)
