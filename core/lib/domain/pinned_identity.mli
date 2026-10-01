(** An immutable identity declaration bound to exact external content. Parsing a
    pin does not establish that the named content exists or supports a claim. *)
type kind = Model | Reference | Registry | Source | Evidence
type t
val schema_version : string
val make : kind:kind -> id:string -> version:string -> content_fingerprint:string -> t
val of_json : ?path:string -> Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val kind : t -> kind
val kind_name : t -> string
val id : t -> string
val version : t -> string
val content_fingerprint : t -> string
