(** Deterministic historical whole-CDS layout proposals. Preparation binds the
    supplied reference selection; neither operation grants checker acceptance. *)
val generator_version : string
type limits = Reference_producer_budget.limits
val make_limits : ?max_work:int -> ?max_input_bytes:int -> ?max_input_nodes:int ->
  ?max_output_bytes:int -> ?max_output_nodes:int -> unit -> limits
val default_limits : limits
val limits_json : limits -> Bioc_wire.Json.t
val prepare : ?limits:limits -> ?parent:Bioc_checker.Work_budget.t ->
  ?molecule_id:string -> ?source_request_fingerprint:string ->
  manifest:Bioc_domain.Reference_manifest.t ->
  selection:Bioc_domain.Reference_components.Selection.t ->
  composition:Bioc_domain.Composition.t -> registry:Bioc_domain.Component_registry.t ->
  unit -> Bioc_domain.Reference_construct.Request.t
val generate : ?limits:limits -> ?parent:Bioc_checker.Work_budget.t ->
  Bioc_domain.Reference_construct.Request.t -> Bioc_domain.Reference_construct.Candidate.t
