(** Propose both children under the caller's one cumulative work owner.
    Construction does not create any checked capability. *)
module R = Bioc_domain.Policy_controlled_workflow_request
module C = Bioc_domain.Policy_controlled_workflow_candidate
val implementation_version : string
val construct_candidate : charge:(int -> unit) -> R.t -> C.t
