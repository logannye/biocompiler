(** Producer-independent field/occurrence correspondence against complete
    external source and operational definitions. *)
val check : expected_document:Bioc_domain.Policy_document.t ->
  descriptors:Bioc_domain.Policy_operational.descriptor_bundle ->
  Bioc_domain.Policy_operational.behavior -> Bioc_wire.Json.t
