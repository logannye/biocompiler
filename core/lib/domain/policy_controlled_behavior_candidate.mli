(** Untrusted behavior-only candidate. No material or behavioral capability is
    produced by this neutral codec. *)
open Bioc_wire
module I = Policy_controlled_activity_implementation
type t
val schema_version : string
val of_json : ?charge:(int -> unit) -> Json.t -> t
val to_json : t -> Json.t
val fingerprint : t -> string
val decoding_work : t -> int
val request_fingerprint : t -> string
val implementation : t -> I.t
