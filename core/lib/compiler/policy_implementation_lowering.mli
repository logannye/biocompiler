(** Deterministic producer for the initial exclusive truth-policy family.
    Selects existing exact primitive configurations from the separately supplied
    authorized library. It neither creates model authority nor imports the
    independent source/graph binding checker or either execution engine.

    The caller retains complete original admitted authority. A proposal is
    untrusted: structural decoding here is not source correspondence,
    preservation, requirement satisfaction, material realization or export.
    Submit it independently to Policy_implementation_binding_check.check.
    Missing supplied configurations and unsupported source families have
    distinct diagnostics. *)
module A = Bioc_checker.Policy_realization_admission
module I = Bioc_domain.Policy_implementation
module B = Bioc_domain.Policy_implementation_binding

type proposal = { implementation : I.t; binding : B.t }
val lower : admitted:A.admitted_inputs -> library:I.library -> proposal

(** Same producer with count-only traversal accounting; failed layouts are charged. *)
val lower_metered : charge:(int -> unit) -> admitted:A.admitted_inputs -> library:I.library -> proposal
