(** Exact offline registry declarations and complete dependency locks.
    Resolution establishes identity only, never selection or admission. *)
val resource_profile : string
module Component_lock : sig
  type t
  val schema_version : string
  val make : node_id:string -> component_id:string -> version:string -> content_fingerprint:string -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val node_id : t -> string
  val component_id : t -> string
  val version : t -> string
  val content_fingerprint : t -> string
end
module Lock : sig
  type t
  val schema_version : string
  val make : registry_id:string -> registry_version:string -> registry_fingerprint:string -> components:Component_lock.t list -> identities:Pinned_identity.t list -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val registry_id : t -> string
  val registry_version : t -> string
  val registry_fingerprint : t -> string
  val components : t -> Component_lock.t list
  val identities : t -> Pinned_identity.t list
end
type t
val schema_version : string
val make : id:string -> version:string -> components:Component.t list -> t
val of_json : ?path:string -> Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val canonical_size : t -> int
val id : t -> string
val version : t -> string
val components : t -> Component.t list
val lock : t -> (string * Component.t) list -> Lock.t
val resolve : t -> Lock.t -> (string * Component.t) list
