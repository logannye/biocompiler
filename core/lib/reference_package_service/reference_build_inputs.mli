(** The closed reviewed component-root constructor. The snapshot must have been
    validated in this exact package lifetime; it cannot carry accepted records. *)
module B = Bioc_artifact.Archive_budget
type t
val prepare : B.t -> alphabet:Bioc_domain.Reference_manifest.alphabet ->
  Bioc_reference_input.Reference_inputs.t -> t
val request : t -> Bioc_domain.Reference_construct.Request.t
val reference : t -> Bioc_domain.Reference_manifest.t
val registry : t -> Bioc_domain.Component_registry.t

(** A typed host declaration, never an accepted build. The original public
    loader may be replaced; independent downstream checks retain authority. *)
val supplied : B.t -> request:Bioc_domain.Reference_construct.Request.t ->
  reference:Bioc_domain.Reference_manifest.t -> registry:Bioc_domain.Component_registry.t -> t
val require_owner : B.t -> t -> unit
