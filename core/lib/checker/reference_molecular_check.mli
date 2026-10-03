(** Fresh independent spelling, translation and linked-reference comparisons. *)
type limits
val make_limits : ?max_work:int -> ?max_items:int -> ?max_input_bytes:int ->
  ?max_report_bytes:int -> ?max_report_nodes:int -> unit -> limits
val default_limits : limits
val limits_json : limits -> Bioc_wire.Json.t
val checker_version : string
val implementation_version : string
val dependencies : ?parent:Work_budget.t -> ?limits:limits -> request:Bioc_domain.Reference_construct.Request.t ->
  construct:Bioc_domain.Reference_construct.Candidate.t -> candidate:Bioc_domain.Reference_molecular.Artifact.t ->
  registry:Bioc_domain.Component_registry.t -> manifests:(string * Bioc_domain.Reference_manifest.t) list ->
  unit -> Bioc_domain.Reference_molecular_evidence.Dependencies.t
val check : ?parent:Work_budget.t -> ?limits:limits -> request:Bioc_domain.Reference_construct.Request.t ->
  construct:Bioc_domain.Reference_construct.Candidate.t -> candidate:Bioc_domain.Reference_molecular.Artifact.t ->
  registry:Bioc_domain.Component_registry.t -> manifests:(string * Bioc_domain.Reference_manifest.t) list ->
  unit -> Bioc_domain.Reference_molecular_evidence.Result.t
val freshness : ?parent:Work_budget.t -> ?limits:limits -> request:Bioc_domain.Reference_construct.Request.t ->
  construct:Bioc_domain.Reference_construct.Candidate.t -> candidate:Bioc_domain.Reference_molecular.Artifact.t ->
  registry:Bioc_domain.Component_registry.t -> manifests:(string * Bioc_domain.Reference_manifest.t) list ->
  Bioc_domain.Reference_molecular_evidence.Result.t -> Bioc_domain.Realization_evidence.Freshness_report.t
val replay : ?parent:Work_budget.t -> ?limits:limits -> request:Bioc_domain.Reference_construct.Request.t ->
  construct:Bioc_domain.Reference_construct.Candidate.t -> candidate:Bioc_domain.Reference_molecular.Artifact.t ->
  registry:Bioc_domain.Component_registry.t -> manifests:(string * Bioc_domain.Reference_manifest.t) list ->
  Bioc_domain.Reference_molecular_evidence.Result.t -> bool
