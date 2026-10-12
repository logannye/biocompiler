(** An untrusted fixed primitive proposal from the complete original model.
    Empty component model bodies remain declared realization dependencies.
    This function creates neither material nor a behavioral acceptance token. *)
module R = Bioc_domain.Policy_controlled_behavior_request
module C = Bioc_domain.Policy_controlled_behavior_candidate
val implementation_version : string
val construct_candidate : charge:(int -> unit) -> R.t -> C.t
