(** Neutral completed activity observation. No source verdict, evidence status,
    candidate authority or model phase is embedded in this shared value. *)
open Bioc_wire
type band = Background | Active
type t = { tick : int; band : band; activation_generation : int option }
val to_json : t -> Json.t
