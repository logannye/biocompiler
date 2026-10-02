(** Historical architecture verification claims. Decoding does not establish
    their correspondence with current external request and candidate authority. *)
type outcome = Construction_assessment.outcome = Pass | Fail | Unknown | Unsupported
type t
val schema_version : string
val checker_version : string
val claim_scope : string
val of_json : ?path:string -> Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val make : request_fingerprint:string -> build_fingerprint:string -> outcome:outcome ->
  translation_complete:bool -> construction_complete:bool -> diagnostics:Architecture_build.Gap.t list ->
  unresolved:string list -> assumptions:string list -> t
val request_fingerprint : t -> string
val build_fingerprint : t -> string
val outcome : t -> outcome
val passed : t -> bool
val translation_complete : t -> bool
val construction_complete : t -> bool
val diagnostics : t -> Architecture_build.Gap.t list
val unresolved : t -> string list
val assumptions : t -> string list
