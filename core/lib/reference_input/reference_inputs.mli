(** Reviewed immutable byte snapshots only. No path is opened, URL fetched,
    directory freshness inferred, or candidate acceptance imported. The adapter
    must supply separate snapshots at the original load/collect call points. *)
module B = Bioc_artifact.Archive_budget
val inputs_version : string
val manifest_pin : Bioc_domain.Pinned_identity.t
val reference_pin : B.t -> Bioc_domain.Reference_manifest.alphabet -> Bioc_domain.Pinned_identity.t
type t
val validate_snapshot : B.t -> files:(string * string) list -> t
val collect_snapshot : B.t -> reference:Bioc_domain.Reference_manifest.t -> files:(string * string) list -> t
val require_owner : B.t -> t -> unit
val manifest : t -> Bioc_domain.Reference_manifest.t
val files : t -> (string * string) list
val manifest_bytes : B.t -> Bioc_domain.Reference_manifest.t -> string
