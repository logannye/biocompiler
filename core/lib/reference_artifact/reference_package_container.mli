(** Typed reference-only archive integrity. These functions never invoke a
    producer, import acceptance, or authorize export/publication. *)
module B = Bioc_artifact.Archive_budget
module M = Reference_package_manifest
type t
val assemble : B.t -> M.Manifest.t -> Bioc_artifact.Stored_zip.entry list ->
  ?run_metadata:M.Run_metadata.t -> unit -> string
val read : ?runtime:Bioc_artifact.Stored_zip.diagnostic_profile -> B.t -> string -> t
val manifest : t -> M.Manifest.t
val files : t -> Bioc_artifact.Stored_zip.entry list
val run_metadata : t -> M.Run_metadata.t option
