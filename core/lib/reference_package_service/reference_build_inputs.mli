(** The closed reviewed component-root constructor. The snapshot must have been
    validated in this exact package lifetime; it cannot carry accepted records. *)
module B = Bioc_artifact.Archive_budget
type t
val prepare : B.t -> alphabet:Bioc_domain.Reference_manifest.alphabet ->
  Bioc_reference_input.Reference_inputs.t -> t
val request : t -> Bioc_domain.Reference_construct.Request.t
val reference : t -> Bioc_domain.Reference_manifest.t
val registry : t -> Bioc_domain.Component_registry.t
