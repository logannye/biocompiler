(** Direct equations for the original global supplied activity model. This
    reference imports neither candidate execution nor source requirement bounds. *)
module R = Bioc_domain.Policy_controlled_composition_request
module Domain = Bioc_domain.Policy_controlled_domain
module Sample = Bioc_domain.Policy_controlled_activity_sample
type t
val initialize : charge:(int -> unit) -> original:R.t -> domain:Domain.validated -> t
val step : charge:(int -> unit) -> t -> Domain.input_batch -> t * Sample.t
val pending : t -> bool
