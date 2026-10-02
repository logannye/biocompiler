(** Independent, bounded Boolean-table correspondence against the original full
    source. Diagnostics retain temporal, lifecycle and provider obligations.
    Diagnostic bytes and nodes are cumulatively reserved before retention;
    exhaustion raises an error without a partial list. This helper does not
    verify complete architecture or empirical function. *)
val resource_profile : string
val default_max_work : int
type budget
val make_budget : ?parent:Work_budget.t -> ?max_work:int -> unit -> budget
val check : ?budget:budget -> source:Bioc_domain.Human_request.t ->
  requirements:Bioc_domain.Circuit_request.Requirement.t list ->
  bindings:Bioc_domain.Payload_circuit_binding.t list -> unit -> string list
