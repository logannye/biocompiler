(** Native source-contract analysis only. It neither executes a policy nor grants
    lowering, target suitability, realization or artifact-release authority. *)
val checker_version : string
val check : ?charge:(int -> unit) -> Bioc_domain.Policy_document.t -> Bioc_wire.Json.t

(** A fresh source check scoped to one callback. The abstract handle cannot be
    decoded from data; all access and charging reject after normal or exceptional
    callback exit. Its exact immutable document uses canonical /document paths.
    It grants no operational, behavior-correspondence or export authority. *)
type assessed_source
val with_assessment : charge:(int -> unit) -> document:Bioc_domain.Policy_document.t ->
  (assessed_source -> 'a) -> 'a
val assessed_document : assessed_source -> Bioc_domain.Policy_document.t
val assessed_report : assessed_source -> Bioc_wire.Json.t
val charge_assessed : assessed_source -> int -> unit
