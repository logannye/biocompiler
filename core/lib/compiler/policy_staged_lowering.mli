(** Candidate-only lowering of the bounded two-stage encounter machine. Supplied
    finite primitive models remain original authority; no preservation, material
    or export receipt is constructed here. *)
val lower_metered : charge:(int -> unit) ->
  admitted:Bioc_checker.Policy_realization_admission.admitted_inputs ->
  library:Bioc_domain.Policy_implementation.library ->
  Bioc_domain.Policy_implementation.t * Bioc_domain.Policy_implementation_binding.t
