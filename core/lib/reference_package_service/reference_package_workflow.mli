(** Live reference package construction. Only actual native manager capabilities
    supply the stage snapshot. Retained archive members or reported PASS values
    cannot initialize this workflow. Transport and publication remain external. *)
module B = Bioc_artifact.Archive_budget
module D = Bioc_reference_artifact.Reference_package_manifest
module I = Bioc_reference_input.Reference_inputs
module U = Bioc_pipeline.Reference_construct_pipeline
module V = Bioc_pipeline.Reference_molecular_pipeline
module X = Bioc_reference_export.Reference_sequence_codec
val build_version : string
val default_tool_versions : unit -> (string * string) list

type callbacks = {
  load : B.t -> Bioc_domain.Reference_manifest.alphabet -> I.t;
  collect : B.t -> Bioc_domain.Reference_manifest.t -> I.t;
  run : B.t -> request:Bioc_domain.Reference_construct.Request.t ->
    registry:Bioc_domain.Component_registry.t ->
    manifests:(string * Bioc_domain.Reference_manifest.t) list -> V.t;
  construct : B.t -> V.t -> Bioc_domain.Reference_construct.Candidate.t;
  export : B.t -> request:Bioc_domain.Reference_construct.Request.t ->
    construct:Bioc_domain.Reference_construct.Candidate.t ->
    artifact:Bioc_domain.Reference_molecular.Artifact.t ->
    registry:Bioc_domain.Component_registry.t ->
    manifests:(string * Bioc_domain.Reference_manifest.t) list -> line_width:int ->
    Bioc_reference_export.Reference_sequence_export.checked;
  package_version : unit -> string;
  tool_versions : unit -> (string * string) list;
}
(* These trusted adapters preserve the original module lookup and filesystem
   call points. Returned declarations remain untrusted independent-check inputs.
   The run callback must return a build on this exact Work_budget owner. The
   two construct reads remain separate. Exceptions are not replaced or swallowed. *)
val native_callbacks : load:(B.t -> Bioc_domain.Reference_manifest.alphabet -> I.t) ->
  collect:(B.t -> Bioc_domain.Reference_manifest.t -> I.t) ->
  package_version:(unit -> string) -> callbacks

type t
val build : B.t -> callbacks:callbacks -> request:D.Request.t ->
  ?run_metadata:D.Run_metadata.t -> unit -> t
val request : t -> D.Request.t
val manifest : t -> D.Manifest.t
val data : t -> string
val archive_sha256 : t -> string
val build_fingerprint : t -> string
val owner : t -> B.t
val molecular_build : t -> V.t
val records : t -> Bioc_domain.Pipeline_contract.Stage_record.t list
val completion : t -> Bioc_domain.Pipeline_contract.Pipeline_result.t
val files : t -> Bioc_artifact.Stored_zip.entry list
