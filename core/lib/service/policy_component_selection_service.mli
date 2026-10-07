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
