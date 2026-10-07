(** Produces an untrusted behavior/implementation/binding bundle, then invokes
    the same external-authority check as standalone Verify. No material export. *)
val compile : Bioc_wire.Json.t -> Bioc_wire.Json.t
