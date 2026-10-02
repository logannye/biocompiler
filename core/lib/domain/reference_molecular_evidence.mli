(** Historical molecular comparisons and scoped reports. A parsed report is
    evidence to compare with a fresh calculation, never acceptance authority. *)
module Codec = Verification_exploration.Codec
type status = Realization_evidence.outcome = Pass | Fail | Unknown | Unsupported
val checker_version : string
val claim_scope : string
module Diagnostic : sig
  type t
  val make : ?limits:Codec.limits -> status:status -> code:string -> message:string ->
    ?record_id:string -> ?instance_id:string -> ?molecule_id:string ->
    ?requirement_ids:string list -> ?source:Behavior.source_location -> unit -> t
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val canonical_size : t -> int
  val status : t -> status
  val record_id : t -> string option
end
module Comparison : sig
  type t
  val make : ?limits:Codec.limits -> record_id:string -> check:string -> outcome:status ->
    expected_fingerprint:string option -> actual_fingerprint:string option -> message:string -> unit -> t
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val canonical_size : t -> int
  val record_id : t -> string
  val check : t -> string
  val outcome : t -> status
end
module Dependencies : sig
  type t
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val changed : ?limits:Codec.limits -> t -> t -> string list
end
module Result : sig
  type t
  val schema_version : string
  val make : ?limits:Codec.limits -> outcome:status -> dependencies:Dependencies.t ->
    checked_requirement_ids:string list -> ?diagnostics:Diagnostic.t list ->
    ?checks:Comparison.t list -> ?claim_scope:string -> unit -> t
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val of_json_text : ?limits:Codec.limits -> ?path:string -> string -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val outcome : t -> status
  val passed : t -> bool
  val dependencies : t -> Dependencies.t
  val diagnostics : t -> Diagnostic.t list
  val checks : t -> Comparison.t list
  val checked_requirement_ids : t -> string list
  val freshness : ?limits:Codec.limits -> t -> Dependencies.t -> Realization_evidence.Freshness_report.t
end
