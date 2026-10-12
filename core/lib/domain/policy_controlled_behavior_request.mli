(** Complete RC5 authority, including an independently supplied executor-owned
    readout evidence schedule. Decoding confers no behavioral capability. *)
open Bioc_wire
module Original = Policy_controlled_composition_request
module Domain = Policy_controlled_domain
type t
val schema_version : string
val profile : string
val resource_profile : string
val of_json : ?charge:(int -> unit) -> Json.t -> t
val raw : t -> Json.t
val to_json : t -> Json.t
val original : t -> Original.t
val fingerprint : t -> string
val decoding_work : t -> int
val budgets : t -> Original.budgets
val readout : t -> int -> Domain.effective_evidence
