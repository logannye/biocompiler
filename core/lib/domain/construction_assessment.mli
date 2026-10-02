(** Historical construction report codec. A parsed report grants no acceptance;
    replay requires the independent checker and complete current authority. *)
type outcome = Pass | Fail | Unknown | Unsupported
type t
val schema_version : string
val checker_version : string
val capability_version : string
val construction_profile : string
val admission_policy : string
val claim_scope : string
val max_diagnostics : int
val max_diagnostic_bytes : int
val max_retained_diagnostic_bytes : int
val outcome_name : outcome -> string
val of_json : ?path:string -> Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val make : request_fingerprint:string -> candidate_fingerprint:string -> reconstructed_fingerprint:string ->
  outcome:outcome -> complete:bool -> diagnostics:string list -> t
val request_fingerprint : t -> string
val candidate_fingerprint : t -> string
val reconstructed_fingerprint : t -> string
val outcome : t -> outcome
val complete : t -> bool
val passed : t -> bool
val diagnostics : t -> string list

(* Untrusted diagnostic text with fixed retention bounds. The builder neither
   decides outcomes nor establishes candidate correspondence or acceptance. *)
module Inventory : sig
  type t
  val create : unit -> t
  val add : t -> string -> unit
  val elements : t -> string list
end
