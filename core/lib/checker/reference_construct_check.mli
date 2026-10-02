(** Independent reference-layout acceptance from supplied authority. No producer
    is imported and no historical report grants acceptance. *)
type limits
val make_limits : ?max_work:int -> ?max_items:int -> ?max_input_bytes:int ->
  ?max_report_bytes:int -> ?max_report_nodes:int -> unit -> limits
val default_limits : limits
val limits_json : limits -> Bioc_wire.Json.t
val checker_version : string
val implementation_version : string
val dependencies : ?parent:Work_budget.t -> ?limits:limits -> request:Bioc_domain.Reference_construct.Request.t ->
  candidate:Bioc_domain.Reference_construct.Candidate.t -> registry:Bioc_domain.Component_registry.t ->
  manifests:(string * Bioc_domain.Reference_manifest.t) list -> unit -> Bioc_domain.Reference_construct_evidence.Dependencies.t
val check_request : ?parent:Work_budget.t -> ?limits:limits -> request:Bioc_domain.Reference_construct.Request.t ->
  registry:Bioc_domain.Component_registry.t -> manifests:(string * Bioc_domain.Reference_manifest.t) list ->
  unit -> Bioc_domain.Reference_construct_evidence.Diagnostic.t list
val check : ?parent:Work_budget.t -> ?limits:limits -> request:Bioc_domain.Reference_construct.Request.t ->
  candidate:Bioc_domain.Reference_construct.Candidate.t -> registry:Bioc_domain.Component_registry.t ->
  manifests:(string * Bioc_domain.Reference_manifest.t) list -> unit -> Bioc_domain.Reference_construct_evidence.Result.t
val freshness : ?parent:Work_budget.t -> ?limits:limits -> request:Bioc_domain.Reference_construct.Request.t ->
  candidate:Bioc_domain.Reference_construct.Candidate.t -> registry:Bioc_domain.Component_registry.t ->
  manifests:(string * Bioc_domain.Reference_manifest.t) list -> Bioc_domain.Reference_construct_evidence.Result.t ->
  Bioc_domain.Realization_evidence.Freshness_report.t
val replay : ?parent:Work_budget.t -> ?limits:limits -> request:Bioc_domain.Reference_construct.Request.t ->
  candidate:Bioc_domain.Reference_construct.Candidate.t -> registry:Bioc_domain.Component_registry.t ->
  manifests:(string * Bioc_domain.Reference_manifest.t) list -> Bioc_domain.Reference_construct_evidence.Result.t -> bool
