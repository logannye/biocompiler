(** Authoritative frozen-request lowering. Every returned Behavior has passed
    both domain validation and independent Lowering_check against the original
    request. No evaluator, molecular selection or biological admission runs. *)
val producer_version : string
val lower : Bioc_domain.Build_request.t -> Bioc_domain.Behavior.t
