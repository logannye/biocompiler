(** Neutral, bounded codec for an untrusted RC4 material-only proposal. Decoding
    grants no admission, structural, behavioral, recipient or export authority. *)
open Bioc_wire
module K = Construction_content
val schema_version : string
type t
val of_json : ?charge:(int -> unit) -> Json.t -> t
val to_json : t -> Json.t
val fingerprint : t -> string
val decoding_work : t -> int
val request_fingerprint : t -> string
val construction : t -> K.t
