(** Contextual operational admission repeats native source checking and binds
    every executable semantic use to an exact external descriptor. Operational
    occurrence paths use the canonical /document root independently of ingress
    diagnostic locations; complete authored source bytes remain unchanged. *)
module O = Bioc_domain.Policy_operational
type t

(** Count-only invocation meter; failures propagate unchanged before further
    work. The legacy entry below uses the no-op meter and unchanged local caps. *)
val admit_metered : charge:(int -> unit) -> document:Bioc_domain.Policy_document.t -> descriptors:O.descriptor_bundle -> t
val admit : document:Bioc_domain.Policy_document.t -> descriptors:O.descriptor_bundle -> t
val document : t -> Bioc_domain.Policy_document.t
val descriptors : t -> O.descriptor_bundle
val source_assessment : t -> Bioc_wire.Json.t
val report : t -> Bioc_wire.Json.t
