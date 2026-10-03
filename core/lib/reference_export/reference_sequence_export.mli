(** Fresh software-use admission and independent molecular checking precede
    serialization. Caller supplies one existing512MiB package scope/ancestor;
    insufficient existing scopes fail rather than gaining fresh resources. *)
module B = Bioc_artifact.Archive_budget
val checker_limits_json : unit -> Bioc_wire.Json.t
val checker_reservation_bytes : unit -> int
val export : B.t -> request:Bioc_domain.Reference_construct.Request.t ->
  construct:Bioc_domain.Reference_construct.Candidate.t ->
  artifact:Bioc_domain.Reference_molecular.Artifact.t ->
  registry:Bioc_domain.Component_registry.t ->
  manifests:(string * Bioc_domain.Reference_manifest.t) list ->
  line_width:int -> unit -> Reference_sequence_codec.t

(* The explicit package-owned path keeps identical checker limits and charges
   the returned, locally bounded report before persistent ownership transfer.
   Existing standalone export retains its conservative ceiling reservations. *)
val export_owned : B.t -> request:Bioc_domain.Reference_construct.Request.t ->
  construct:Bioc_domain.Reference_construct.Candidate.t ->
  artifact:Bioc_domain.Reference_molecular.Artifact.t ->
  registry:Bioc_domain.Component_registry.t ->
  manifests:(string * Bioc_domain.Reference_manifest.t) list ->
  line_width:int -> unit -> Reference_sequence_codec.t

(* Only the actual fresh owned exporter can mint this abstract capability.
   Identity comparisons below bind immutable authority; they do not import PASS. *)
type checked
val export_checked_owned : B.t -> request:Bioc_domain.Reference_construct.Request.t ->
  construct:Bioc_domain.Reference_construct.Candidate.t ->
  artifact:Bioc_domain.Reference_molecular.Artifact.t ->
  registry:Bioc_domain.Component_registry.t ->
  manifests:(string * Bioc_domain.Reference_manifest.t) list ->
  line_width:int -> unit -> checked
val require_checked : B.t -> checked -> request:Bioc_domain.Reference_construct.Request.t ->
  construct:Bioc_domain.Reference_construct.Candidate.t ->
  artifact:Bioc_domain.Reference_molecular.Artifact.t ->
  registry:Bioc_domain.Component_registry.t ->
  manifests:(string * Bioc_domain.Reference_manifest.t) list -> line_width:int -> unit
val checked_bundle : checked -> Reference_sequence_codec.t
val checked_report : checked -> Bioc_domain.Reference_molecular_evidence.Result.t
