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

(* Trusted transport observers preserve actual public call/read cadence. Host
   reports remain untrusted: passed is observed before document, then the whole
   document is checked against the actual memoized fresh native result. *)
type report_view
val observed_report : B.t -> passed:(B.t -> bool) -> document:(B.t -> Bioc_wire.Json.t) -> report_view
val native_report_document : B.t -> report_view -> Bioc_wire.Json.t
(* Native-only view extraction performs no host getter. Replaced host reports
   cannot acquire this capability. *)
type hooks = {
  get : B.t -> V.t -> identity:string -> Bioc_domain.Pipeline_contract.Stage_record.t;
  result : B.t -> V.t -> identity:string -> scope:string -> Bioc_domain.Pipeline_contract.Pipeline_result.t;
  composition : B.t -> native:(unit -> report_view) -> request:Bioc_domain.Composition.t ->
    registry:Bioc_domain.Component_registry.t -> report_view;
  construct_check : B.t -> native:(unit -> report_view) -> request:Bioc_domain.Reference_construct.Request.t ->
    construct:Bioc_domain.Reference_construct.Candidate.t -> registry:Bioc_domain.Component_registry.t ->
    manifests:(string * Bioc_domain.Reference_manifest.t) list -> report_view;
  molecular_check : B.t -> native:(unit -> report_view) -> V.t -> report_view;
}
(* get/result hooks must consume the exact successful façade command capability
   returned by the same channel/owner, not deserialize a record or run another
   native query. The service's closed getters enforce this authority boundary. *)
type t
val build : B.t -> callbacks:callbacks -> ?hooks:hooks ->
  ?load_prepared:(B.t -> Bioc_domain.Reference_manifest.alphabet -> Reference_build_inputs.t) ->
  ?collect_files:(B.t -> Bioc_domain.Reference_manifest.t -> Bioc_artifact.Stored_zip.entry list) ->
  ?tool_pins:(B.t -> D.Tool.t list) -> request:D.Request.t ->
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

val tool_pins : B.t -> (string * string) list -> D.Tool.t list
