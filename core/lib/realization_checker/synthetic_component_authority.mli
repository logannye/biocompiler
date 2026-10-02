(** Checker-private declaration reconstruction. The caller must first freshly
    accept this actual candidate for the same request/history. No producer or
    supplied component declaration contributes expected authority. *)
val adapter_version : string
type t
val derive : budget:Realization_budget.t -> Checked_request.t ->
  Bioc_domain.Synthetic_authority.Candidate.t -> t
val registry : t -> Bioc_domain.Component_registry.t
val composition : t -> Bioc_domain.Composition.t
