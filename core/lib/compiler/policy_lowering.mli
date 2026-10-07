(** Producer for the dedicated bounded policy behavior IR. *)
val lower : ?charge:(int -> unit) -> Bioc_checker.Policy_admission.t -> Bioc_domain.Policy_operational.behavior
