(** A joined proposal retains both complete untrusted children. No saved report
    or candidate-local digest grants material, behavioral or joined acceptance. *)
open Bioc_wire
module Material = Policy_controlled_material_candidate
module Behavior = Policy_controlled_behavior_candidate
type t
val schema_version : string
val of_json : ?charge:(int -> unit) -> Json.t -> t
val to_json : t -> Json.t
val fingerprint : t -> string
val decoding_work : t -> int
val request_fingerprint : t -> string
val material : t -> Material.t
val behavior : t -> Behavior.t
