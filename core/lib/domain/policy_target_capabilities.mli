(** Installed planner vocabulary and profile identities. This descriptive
    catalog is not source admission, a promise that arbitrary combinations of
    features lower, a checked realization, or biological target acceptance.
    Fresh bounded planning must inspect the complete supplied authority. *)
open Bioc_wire

val schema_version : string
val catalog : Json.t
val catalog_fingerprint : string
val target_ids : string list

(** Unknown target identities fail closed with [policy_target_unknown]. *)
val target : string -> Json.t
val is_material : string -> bool
val request_schema : string -> string
val request_profile : string -> string
val realization_schema : string -> string
val realization_profile : string -> string
