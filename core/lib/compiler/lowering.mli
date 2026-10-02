(** Authoritative frozen-request lowering. Every returned Behavior has passed
    both domain validation and independent Lowering_check against the original
    request. No evaluator, molecular selection or biological admission runs. *)
val producer_version : string
val lower : Bioc_domain.Build_request.t -> Bioc_domain.Behavior.t
val resource_profile : string
(** Same lowering and independent acceptance, with producer transformations,
    document materialization and the independent checker sharing [parent].
    The caller bounds aggregate work; the checker's existing nested allowance
    and every structural/lineage/publication limit remain in force. *)
val lower_with_budget : parent:Bioc_checker.Work_budget.t ->
  Bioc_domain.Build_request.t -> Bioc_domain.Behavior.t
