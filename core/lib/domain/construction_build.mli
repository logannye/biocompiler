(** Historical request, candidate and assessment with mutually consistent
    identities. Importing the record does not freshly verify its contents. *)
type t
val schema_version : string
val of_json : ?path:string -> Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val make : request:Construction.Request.t -> candidate:Construction_artifact.t -> assessment:Construction_assessment.t -> t
val request : t -> Construction.Request.t
val candidate : t -> Construction_artifact.t
val assessment : t -> Construction_assessment.t
