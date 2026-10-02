(** Structural frozen request envelope only. A value may have no target or have
    inconsistent source, Behavior, contract or role correspondence. Use the
    checker-owned Checked_request for freshly checked source authority. *)
type t
val schema_version : string
val validation_scope : string
val resource_profile : string
val of_json : ?path:string -> Bioc_wire.Json.t -> t
val make : build_request:Build_request.t -> behavior:Behavior.t ->
  contract:Realization_contract.Behavior_contract.t ->
  domain:Realization_contract.Operating_domain.t -> t
val to_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val artifact_fingerprint : t -> string
val canonical_size : t -> int
val build_request : t -> Build_request.t
val behavior : t -> Behavior.t
val contract : t -> Realization_contract.Behavior_contract.t
val domain : t -> Realization_contract.Operating_domain.t
val target : t -> Build_request.Target.t option
val upstream_request_fingerprint : t -> string
