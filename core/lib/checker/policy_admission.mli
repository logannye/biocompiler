(** Contextual operational admission repeats native source checking and binds
    every executable semantic use to an exact external descriptor. *)
module O = Bioc_domain.Policy_operational
type t
val admit : document:Bioc_domain.Policy_document.t -> descriptors:O.descriptor_bundle -> t
val document : t -> Bioc_domain.Policy_document.t
val descriptors : t -> O.descriptor_bundle
val source_assessment : t -> Bioc_wire.Json.t
val report : t -> Bioc_wire.Json.t
