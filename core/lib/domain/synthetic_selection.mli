(** Complete historical bounded-search records. Imported checks are historical
    evidence; this module never grants fresh acceptance. Canonical identities use
    UTF-8, including nested evidence whose own identities use its ASCII profile. *)
val resource_profile : string
val selection_version : string
val cost_version : string
val strategies : string list
val valid_horizon : Runtime_number.t option -> bool
module Alternative : sig
  type t
  val schema_version : string
  val make : strategy:string -> ?candidate:Synthetic_authority.Candidate.t ->
    ?constraint_violations:string list -> ?check:Realization_evidence.Check_result.t ->
    ?generation_error:string -> unit -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val strategy : t -> string
  val candidate : t -> Synthetic_authority.Candidate.t option
  val constraint_violations : t -> string list
  val check : t -> Realization_evidence.Check_result.t option
  val generation_error : t -> string option
  val gate_count : t -> int option
  val status : t -> string
end
module Result : sig
  type t
  val schema_version : string
  val make : request_fingerprint:string -> history_fingerprint:string ->
    ?until:Runtime_number.t -> config:Synthetic_authority.Config.t ->
    minimize:string -> Alternative.t list -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val request_fingerprint : t -> string
  val history_fingerprint : t -> string
  val until : t -> Runtime_number.t option
  val config : t -> Synthetic_authority.Config.t
  val minimize : t -> string
  val alternatives : t -> Alternative.t list
  val selected_strategy : t -> string option
  val candidate : t -> Synthetic_authority.Candidate.t option
  val outcome : t -> string
  val checked_candidates : t -> int
  val rejected_candidates : t -> int
end
