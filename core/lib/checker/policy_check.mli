(** Native source-contract analysis only. It neither executes a policy nor grants
    lowering, target suitability, realization or artifact-release authority. *)
val checker_version : string
val check : Bioc_domain.Policy_document.t -> Bioc_wire.Json.t
