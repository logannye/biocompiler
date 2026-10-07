(** Core-only complete-census generation under a caller-owned count-only meter.
    Returns an untrusted candidate; never checks, exports or skips a loser. *)
val produce : charge:(int -> unit) -> Bioc_domain.Policy_component_selection_request.t -> Bioc_wire.Json.t
