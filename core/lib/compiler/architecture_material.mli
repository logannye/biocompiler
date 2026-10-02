(** Producer-only material namespace and plan derivation. These transformations
    create candidates; they are never independent checking authority. *)
val namespace_template : Bioc_domain.Payload_template.t -> string -> Bioc_domain.Payload_template.t
val construction_request : Bioc_domain.Architecture_refinement.t list -> Bioc_domain.Architecture_request.t -> Bioc_domain.Construction.Request.t
val plan : Bioc_domain.Architecture_refinement.t list -> Bioc_domain.Source_execution_manifest.t ->
  Bioc_domain.Architecture_request.t -> Bioc_domain.Architecture_contract.Instance.t list -> Bioc_domain.Architecture_build.Plan.t
val delivered : Bioc_domain.Construction_build.t -> Bioc_domain.Molecule.t list
