(** Untrusted construction of the supplied two-member material template. This
    path neither lowers behavior nor creates a checked or admitted token. *)
module R = Bioc_domain.Policy_controlled_composition_request
module C = Bioc_domain.Policy_controlled_material_candidate
val implementation_version : string

(** The optional count-only callback supports an enclosing work/cancellation
    owner. Reduced limits bound proposal generation without granting acceptance. *)
val construct_candidate : ?charge:(int -> unit) -> ?limits:Construction_producer.Limits.t ->
  R.t -> C.t
