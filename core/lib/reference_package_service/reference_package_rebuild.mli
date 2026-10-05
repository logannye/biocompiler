(** Producer-linked current reconstruction of a reference package. This is the
    historical package verification operation, not producer-free standalone Verify.
    A caller must supply independent expected authority. Imported reports are data. *)
module B = Bioc_artifact.Archive_budget
module D = Bioc_reference_artifact.Reference_package_manifest
val verify : ?runtime:Bioc_artifact.Stored_zip.diagnostic_profile -> B.t ->
  callbacks:(Bioc_artifact.Stored_zip.entry list -> Reference_package_workflow.callbacks) ->
  ?expected_request:D.Request.t -> ?expected_build_fingerprint:string -> string -> Reference_package_workflow.t

(* Trusted live embedding: invoke the current public build callpoint and return
   its actual same-owner capability. No serialized package can satisfy this. *)
val verify_with_builder : ?runtime:Bioc_artifact.Stored_zip.diagnostic_profile ->
  ?invalid_utf8:(string -> unit) -> B.t -> builder:(B.t -> request:Bioc_reference_artifact.Reference_package_manifest.Request.t ->
    files:Bioc_artifact.Stored_zip.entry list ->
    run_metadata:Bioc_reference_artifact.Reference_package_manifest.Run_metadata.t option ->
    Reference_package_workflow.t) ->
  ?expected_request:Bioc_reference_artifact.Reference_package_manifest.Request.t ->
  ?expected_build_fingerprint:string -> string -> Reference_package_workflow.t
