(** Fresh structural compatibility under complete locked composition authority.
    No producer, source interpreter, sequence emitter or candidate runtime is
    invoked. A successful report remains conditional on declared contracts. *)
val checker_version : string
val implementation_version : string
val resource_profile : string
val diagnostic_order_profile : string
type limits
val make_limits : ?max_work:int -> ?max_items:int -> ?max_input_bytes:int ->
  ?max_report_bytes:int -> ?max_report_nodes:int -> ?max_rational_bits:int -> unit -> limits
val default_limits : limits
val limits_json : limits -> Bioc_wire.Json.t
type usage = { work : int; retained_items : int }
val dependencies : ?parent:Work_budget.t -> ?limits:limits ->
  request:Bioc_domain.Composition.t -> registry:Bioc_domain.Component_registry.t -> unit ->
  Bioc_domain.Composition_evidence.Dependencies.t
val check_with_usage : ?parent:Work_budget.t -> ?limits:limits ->
  request:Bioc_domain.Composition.t -> registry:Bioc_domain.Component_registry.t -> unit ->
  Bioc_domain.Composition_evidence.Result.t * usage
val check : ?parent:Work_budget.t -> ?limits:limits ->
  request:Bioc_domain.Composition.t -> registry:Bioc_domain.Component_registry.t -> unit ->
  Bioc_domain.Composition_evidence.Result.t
(* Replay checks the complete supplied report against a new calculation. *)
val replay : ?parent:Work_budget.t -> ?limits:limits ->
  expected_request:Bioc_domain.Composition.t -> registry:Bioc_domain.Component_registry.t ->
  Bioc_domain.Composition_evidence.Result.t -> unit -> bool
