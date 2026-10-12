(** Source-only obligations over completed physical activity observations.
    Source deadlines are never used as implementation delays. Evidence gaps
    are sticky and do not alter the physical input or activity history. *)
open Bioc_wire
module Source = Policy_controlled_source
module Domain = Bioc_domain.Policy_controlled_domain
module Sample = Bioc_domain.Policy_controlled_activity_sample
type t
val create : charge:(int -> unit) -> source:Source.t -> domain:Domain.validated -> t
val step : charge:(int -> unit) -> t -> input:Domain.input_batch -> activity:Sample.t ->
  readout:Domain.effective_evidence -> t
val finish : charge:(int -> unit) -> t -> Json.t
val satisfied : t -> bool
val failed : t -> bool
val unknown : t -> bool
val pending : t -> bool
val coverage : t -> (string * bool) list
