(** Complete frozen composition declarations. Import does not resolve a registry,
    prove linking, execute a model or grant biological/implementation evidence. *)
val resource_profile : string
val resource_limits : Bioc_wire.Json.t

module Lifecycle : sig
  type t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : ?start:Runtime_number.t -> ?end_time:Runtime_number.t -> ?unit:string -> unit -> t
  val start : t -> Runtime_number.t
  val end_time : t -> Runtime_number.t option
  val unit : t -> string
end

module Instance : sig
  type placement = Encoded_here | Co_payload
  type t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> component:Component_registry.Component_lock.t ->
    required_domain:Component_contract.Operating_domain.t -> ?placement:placement ->
    ?lifetime:Lifecycle.t -> ?requirement_ids:string list -> ?source:Behavior.source_location -> unit -> t
  val id : t -> string
  val component : t -> Component_registry.Component_lock.t
  val required_domain : t -> Component_contract.Operating_domain.t
  val placement : t -> placement
  val placement_name : t -> string
  val lifetime : t -> Lifecycle.t
  val requirement_ids : t -> string list
  val source : t -> Behavior.source_location option
end

module Connection : sig
  type t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : producer_instance:string -> producer_port:string -> consumer_instance:string -> consumer_port:string -> t
  val producer_instance : t -> string
  val producer_port : t -> string
  val consumer_instance : t -> string
  val consumer_port : t -> string
end

module Provider : sig
  type kind = Host | External | Unresolved
  type t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> kind:kind -> capabilities:Component.Capability.t list ->
    supported_targets:string list -> ?depends_on:string list -> ?evidence_refs:string list -> unit -> t
  val id : t -> string
  val kind : t -> kind
  val kind_name : t -> string
  val capabilities : t -> Component.Capability.t list
  val supported_targets : t -> string list
  val depends_on : t -> string list
  val evidence_refs : t -> string list
end

module Dependency_binding : sig
  type t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : instance_id:string -> requirement_id:string -> provider_id:string -> t
  val instance_id : t -> string
  val requirement_id : t -> string
  val provider_id : t -> string
end

module Resource_pool : sig
  type t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> resource:string -> unit:string -> capacity:Runtime_number.t option ->
    provider_id:string -> ?dtype:Type_spec.t -> unit -> t
  val id : t -> string
  val resource : t -> string
  val unit : t -> string
  val capacity : t -> Runtime_number.t option
  val provider_id : t -> string
  val dtype : t -> Type_spec.t
end

module Resource_binding : sig
  type t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : instance_id:string -> reservation_id:string -> pool_id:string -> t
  val instance_id : t -> string
  val reservation_id : t -> string
  val pool_id : t -> string
end

type t
val schema_version : string
val of_json : ?path:string -> Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val canonical_size : t -> int
val make : target:Build_request.Target.t -> registry_lock:Component_registry.Lock.t ->
  instances:Instance.t list -> ?connections:Connection.t list -> ?providers:Provider.t list ->
  ?dependency_bindings:Dependency_binding.t list -> ?resource_pools:Resource_pool.t list ->
  ?resource_bindings:Resource_binding.t list -> ?requirement_ids:string list -> unit -> t
val target : t -> Build_request.Target.t
val registry_lock : t -> Component_registry.Lock.t
val instances : t -> Instance.t list
val connections : t -> Connection.t list
val providers : t -> Provider.t list
val dependency_bindings : t -> Dependency_binding.t list
val resource_pools : t -> Resource_pool.t list
val resource_bindings : t -> Resource_binding.t list
val requirement_ids : t -> string list
