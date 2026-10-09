(** Fresh bounded implementation checking and complete-wrapper replay.
    No material, target or export authority is created by this service. *)
val operations : string list
val validation_scope : string
val candidate_schema : string
val profile : Bioc_wire.Json.t
val producer_profile : Bioc_wire.Json.t
val multi_site_implementation : string
val multi_site_validation_scope : string
val multi_site_profile : Bioc_wire.Json.t
val multi_site_producer_profile : Bioc_wire.Json.t
val network_implementation : string
val network_validation_scope : string
val network_profile : Bioc_wire.Json.t
val network_producer_profile : Bioc_wire.Json.t
val finite_machine_validation_scope : string
val finite_machine_profile : Bioc_wire.Json.t
val finite_machine_producer_profile : Bioc_wire.Json.t
val request_of_json : Bioc_wire.Json.t -> Bioc_domain.Policy_realization_request.t

(** Checks the complete publication, including conservative protocol-envelope
    allowance. This is a resource check only and confers no semantic authority. *)
val validate_publication : Bioc_wire.Json.t -> unit

(** The original realization request is external to the untrusted candidate. *)
val check : request:Bioc_wire.Json.t -> candidate:Bioc_wire.Json.t ->
  limits:Bioc_wire.Json.t -> Bioc_wire.Json.t

(** Replay payload.report is the entire saved service wrapper, not its inner
    report. Every field must equal a complete fresh independently checked result. *)
val handle : operation:string -> Bioc_wire.Json.t -> Bioc_wire.Json.t
