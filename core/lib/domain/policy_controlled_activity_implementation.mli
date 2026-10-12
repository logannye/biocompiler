(** Neutral representation of the closed controlled activity primitive graph.
    Retained authority bodies are inert data; decoding does not establish their
    correspondence to an independently supplied original. *)
open Bioc_wire
type t
type delays = private {
  onset_ticks : int; cessation_ticks : int; reactivation_ticks : int;
}
val schema_version : string
val of_json : ?charge:(int -> unit) -> Json.t -> t
val to_json : t -> Json.t
val fingerprint : t -> string
val decoding_work : t -> int
val delays : t -> delays
