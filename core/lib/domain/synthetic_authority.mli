(** Complete historical software-fixture declarations and pinned generation
    authority. These codecs establish neither source provenance nor acceptance.
    In particular, a candidate's source labels and locks remain untrusted claims
    until independently checked against the original request and catalog. *)
val resource_profile : string
val combinational_profile : string
val temporal_profile : string
val catalog_version : string
val generator_version : string
val model_runner_version : string
val checker_version : string
(* UTF-8 canonical bytes and key/value nodes, with cycle and spine checks.
    Both imports and constructors have the 16 MiB / 250,000 node ceiling. *)
val measure : ?path:string -> ?maximum:int -> Bioc_wire.Json.t -> int * int
module Component : sig
  type t
  val schema_version : string
  val make : id:string -> version:string -> operation:string -> interface:string ->
    model_version:string -> assumptions:string list -> guarantees:string list ->
    supported_profile:string -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val id : t -> string
  val version : t -> string
  val operation : t -> string
  val interface : t -> string
  val model_version : t -> string
  val assumptions : t -> string list
  val guarantees : t -> string list
  val supported_profile : t -> string
end
module Catalog : sig
  type t
  val schema_version : string
  val make : ?version:string -> Component.t list -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val version : t -> string
  val components : t -> Component.t list
  val for_operation : t -> string -> Component.t option
  (* Sorted by mechanism node ID. Missing providers reject with
      [synthetic_catalog_operation], the wire equivalent of Python KeyError. *)
  val lock : t -> Mechanism.t -> Component_registry.Component_lock.t list
end
val combinational_catalog : Catalog.t
val temporal_catalog : Catalog.t
val catalog_for_profile : string -> Catalog.t
module Config : sig
  type t
  val schema_version : string
  val make : ?profile_version:string -> ?generator_version:string ->
    ?catalog_fingerprint:string -> ?witness_selection:string ->
    ?conjunction_strategy:string -> unit -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val profile_version : t -> string
  val generator_version : t -> string
  val catalog_fingerprint : t -> string
  val witness_selection : t -> string
  val conjunction_strategy : t -> string
end
module Candidate : sig
  type t
  val schema_version : string
  val make : request_fingerprint:string -> mechanism:Mechanism.t ->
    observation_map:Observation_map.t -> source_map:(string * string list) list ->
    behavior_requirement_ids:(string * string list) list ->
    component_locks:Component_registry.Component_lock.t list ->
    generator_config:Config.t -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val request_fingerprint : t -> string
  val mechanism : t -> Mechanism.t
  val observation_map : t -> Observation_map.t
  val source_map : t -> (string * string list) list
  val behavior_requirement_ids : t -> (string * string list) list
  val component_locks : t -> Component_registry.Component_lock.t list
  val generator_config : t -> Config.t
end
