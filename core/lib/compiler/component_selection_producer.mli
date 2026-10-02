(** Deterministic offline selection under full supplied registry/request authority.
    Fresh replay recomputes all alternatives and admission; archived results do
    not grant eligibility. No empirical or human-use admission is established. *)
val implementation_version : string
val resource_profile : string
type limits
val make_limits : ?max_work:int -> ?max_components:int -> ?max_input_bytes:int ->
  ?max_output_bytes:int -> ?max_output_nodes:int -> unit -> limits
val default_limits : limits
val limits_json : limits -> Bioc_wire.Json.t
type usage = { work : int; components : int; input_bytes : int; output_bytes : int }
val select_with_usage : ?limits:limits -> ?parent:Bioc_checker.Work_budget.t ->
  registry:Bioc_domain.Component_registry.t -> request:Bioc_domain.Component_selection.Request.t ->
  unit -> Bioc_domain.Component_selection.Result.t * usage
val select : ?limits:limits -> ?parent:Bioc_checker.Work_budget.t ->
  registry:Bioc_domain.Component_registry.t -> request:Bioc_domain.Component_selection.Request.t ->
  unit -> Bioc_domain.Component_selection.Result.t
val verify_selection_with_usage : ?limits:limits -> ?parent:Bioc_checker.Work_budget.t ->
  registry:Bioc_domain.Component_registry.t -> request:Bioc_domain.Component_selection.Request.t ->
  Bioc_domain.Component_selection.Result.t -> bool * usage
val verify_selection : ?limits:limits -> ?parent:Bioc_checker.Work_budget.t ->
  registry:Bioc_domain.Component_registry.t -> request:Bioc_domain.Component_selection.Request.t ->
  Bioc_domain.Component_selection.Result.t -> bool
