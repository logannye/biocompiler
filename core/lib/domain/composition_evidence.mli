(** Historical locked-composition reports. Import and freshness establish only
    structure and identity; fresh independent linking remains a checker task. *)
val checker_version : string
val claim_scope : string
val resource_profile : string
val resource_limits : Bioc_wire.Json.t
type status = Realization_evidence.outcome = Pass | Fail | Unknown | Unsupported
val status_name : status -> string

module Link_diagnostic : sig
  type status = Fail | Unknown | Unsupported
  type t
  val make : status:status -> code:string -> message:string -> ?instance_id:string ->
    ?requirement_ids:string list -> unit -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val status : t -> status
  val status_name : t -> string
  val code : t -> string
  val message : t -> string
  val instance_id : t -> string option
  val requirement_ids : t -> string list
end
module Resolved_dependency : sig
  type provider_kind = Encoded_here | Co_payload | Host | External | Unresolved
  type t
  val make : instance_id:string -> requirement_id:string -> provider_id:string option ->
    provider_kind:provider_kind -> status:status -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val instance_id : t -> string
  val requirement_id : t -> string
  val provider_id : t -> string option
  val provider_kind : t -> provider_kind
  val provider_kind_name : t -> string
  val status : t -> status
end
module Resource_usage : sig
  type t
  val make : pool_id:string -> peak_reservation:Runtime_number.t option ->
    capacity:Runtime_number.t option -> unit:string -> status:status -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val pool_id : t -> string
  val peak_reservation : t -> Runtime_number.t option
  val capacity : t -> Runtime_number.t option
  val unit : t -> string
  val status : t -> status
end
module Dependencies : sig
  type t
  val make : request:string -> registry:string -> registry_lock:string -> target:string ->
    identities:Pinned_identity.t list -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val request : t -> string
  val registry : t -> string
  val registry_lock : t -> string
  val target : t -> string
  val identities : t -> Pinned_identity.t list
  val changed : t -> t -> string list
end
val dependencies : request:Composition.t -> registry:Component_registry.t -> Dependencies.t
module Result : sig
  type t
  val schema_version : string
  val make : outcome:status -> dependencies:Dependencies.t -> checked_requirement_ids:string list ->
    ?diagnostics:Link_diagnostic.t list -> ?resolved_dependencies:Resolved_dependency.t list ->
    ?resource_usage:Resource_usage.t list -> ?claim_scope:string -> unit -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val of_json_text : string -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val outcome : t -> status
  val dependencies : t -> Dependencies.t
  val checked_requirement_ids : t -> string list
  val diagnostics : t -> Link_diagnostic.t list
  val resolved_dependencies : t -> Resolved_dependency.t list
  val resource_usage : t -> Resource_usage.t list
  val passed : t -> bool
  val freshness : t -> request:Composition.t -> registry:Component_registry.t -> Realization_evidence.Freshness_report.t
  val is_fresh : t -> request:Composition.t -> registry:Component_registry.t -> bool
end
