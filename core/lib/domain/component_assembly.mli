(** A complete locked candidate and its supplied lineage. Import validates exact
    registry contents and inventories; it does not accept behavior or biology. *)
type t
val schema_version : string
val resource_profile : string
val of_json : ?path:string -> Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val make : registry:Component_registry.t -> composition:Composition.t ->
  request_fingerprint:string -> candidate_fingerprint:string ->
  behavior_sources:(string * string list) list -> observation_map:Observation_map.t -> t
val fingerprint : t -> string
val canonical_size : t -> int
val registry : t -> Component_registry.t
val composition : t -> Composition.t
val request_fingerprint : t -> string
val candidate_fingerprint : t -> string
val behavior_sources : t -> (string * string list) list
val observation_map : t -> Observation_map.t
