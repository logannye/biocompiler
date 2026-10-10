(** Producer-independent field/occurrence correspondence against complete
    external source and operational definitions. *)
val check : ?charge:(int -> unit) -> expected_document:Bioc_domain.Policy_document.t ->
  descriptors:Bioc_domain.Policy_operational.descriptor_bundle ->
  Bioc_domain.Policy_operational.behavior -> Bioc_wire.Json.t

(** Invocation-local result produced only after fresh source admission and all
    independent behavior comparisons. Its assessment is data, not an admitted
    source capability; no serialized result can construct this value. *)
type fresh
val check_fresh : ?charge:(int -> unit) -> expected_document:Bioc_domain.Policy_document.t ->
  descriptors:Bioc_domain.Policy_operational.descriptor_bundle ->
  Bioc_domain.Policy_operational.behavior -> fresh
val source_assessment : fresh -> Bioc_wire.Json.t
val report : fresh -> Bioc_wire.Json.t
