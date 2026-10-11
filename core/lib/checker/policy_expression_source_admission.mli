(** Fresh closed static-objective admission only. No construction producer,
    material token, biological evidence or export authority is available here. *)
module E = Bioc_domain.Policy_expression_material
module D = Bioc_domain.Policy_document
module P = Bioc_domain.Pinned_identity
type t
val admit : ?charge:(int -> unit) -> E.t -> t
val request : t -> E.t
val document : t -> D.t
val source_assessment : t -> Bioc_wire.Json.t
val report : t -> Bioc_wire.Json.t
val objective : t -> Bioc_wire.Json.t
val objective_id : t -> string
val objective_path : t -> string
val recipient : t -> Bioc_wire.Json.t
val deployment : t -> Bioc_wire.Json.t
val implementation : t -> Bioc_wire.Json.t
val localization : t -> Bioc_wire.Json.t
val product : t -> P.t
val maximum_rna_nt : t -> int
(** Every fresh generic source obligation plus the explicit new expression
    correspondence obligation, still unresolved by this admission token. The
    independent material checker must give every member a closed disposition. *)
val unresolved_obligations : t -> string list
