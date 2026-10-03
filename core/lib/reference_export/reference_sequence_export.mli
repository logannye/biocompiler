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
