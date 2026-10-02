(** Emit the selected reference's own nucleotide spelling after a fresh
    independent construct check. The returned artifact remains unchecked. *)
val emitter_version : string
type limits = Reference_producer_budget.limits
val make_limits : ?max_work:int -> ?max_input_bytes:int -> ?max_input_nodes:int ->
  ?max_output_bytes:int -> ?max_output_nodes:int -> unit -> limits
val default_limits : limits
val limits_json : limits -> Bioc_wire.Json.t
val emit : ?limits:limits -> ?parent:Bioc_checker.Work_budget.t ->
  request:Bioc_domain.Reference_construct.Request.t ->
  construct:Bioc_domain.Reference_construct.Candidate.t ->
  registry:Bioc_domain.Component_registry.t ->
  manifests:(string * Bioc_domain.Reference_manifest.t) list -> unit ->
  Bioc_domain.Reference_molecular.Artifact.t
