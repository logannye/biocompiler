(** Producer-linked current reconstruction of a reference package. This is the
    historical package verification operation, not producer-free standalone Verify.
    A caller must supply independent expected authority. Imported reports are data. *)
module B = Bioc_artifact.Archive_budget
module D = Bioc_reference_artifact.Reference_package_manifest
val verify : ?runtime:Bioc_artifact.Stored_zip.diagnostic_profile -> B.t ->
  callbacks:(Bioc_artifact.Stored_zip.entry list -> Reference_package_workflow.callbacks) ->
  ?expected_request:D.Request.t -> ?expected_build_fingerprint:string -> string -> Reference_package_workflow.t
