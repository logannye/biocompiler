(** Independent execution of decoded candidate primitives. Only original domain
    physical inputs enter the transition; evidence cannot alter physical bands.
    State is immutable and its domain cursor binds each input to its prefix. *)
module I = Bioc_domain.Policy_controlled_activity_implementation
module D = Bioc_domain.Policy_controlled_domain
module Sample = Bioc_domain.Policy_controlled_activity_sample
type state
val initialize : charge:(int -> unit) -> implementation:I.t -> domain:D.validated -> state
val step : charge:(int -> unit) -> state -> D.input_batch -> state * Sample.t
val pending : state -> bool
