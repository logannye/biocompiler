(** Candidate-only lowering of the original two-stage encounter machine and
    separately opted-in bounded finite-machine source family. Legacy staged
    dimensions remain exact; the finite family derives state, writer, lane and
    retained-attempt inventories from original admitted source. Exact finite
    inputs consume the checker's retained typed program and resolved symbols;
    raw expression views serve metadata restrictions, exact sharing keys and
    original occurrence identity only. They are not decoded for execution.
    Other profiles retain their existing lowering and metering paths. Supplied
    finite primitive models remain original authority; no preservation, material
    or export receipt is constructed here. *)
val lower_metered : charge:(int -> unit) ->
  admitted:Bioc_checker.Policy_realization_admission.admitted_inputs ->
  library:Bioc_domain.Policy_implementation.library ->
  Bioc_domain.Policy_implementation.t * Bioc_domain.Policy_implementation_binding.t
