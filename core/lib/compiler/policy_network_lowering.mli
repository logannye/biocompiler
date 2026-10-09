(** Candidate-only lowering of explicitly bounded networks. Original complete
    priority policies define arbitration groups; each store has one writer
    machine and observation streams retain independent evidence identities.
    Source/graph preservation and material/export authority require independent
    downstream checking. Legacy staged lowering is not changed. *)
val lower_metered : charge:(int -> unit) ->
  admitted:Bioc_checker.Policy_realization_admission.admitted_inputs ->
  library:Bioc_domain.Policy_implementation.library ->
  Bioc_domain.Policy_implementation.t * Bioc_domain.Policy_implementation_binding.t
