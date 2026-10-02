(** Public production is followed by fresh independent construction checking.
    Replay and handoff never call the producer. Handoff is scoped structural
    correspondence, not biological or human-use admission. *)
val build : ?parent:Bioc_checker.Work_budget.t -> Bioc_domain.Construction.Request.t -> Bioc_domain.Construction_build.t
val verify : ?parent:Bioc_checker.Work_budget.t -> expected_request:Bioc_domain.Construction.Request.t ->
  Bioc_domain.Construction_build.t -> Bioc_domain.Construction_assessment.t
val verified_molecules : ?parent:Bioc_checker.Work_budget.t -> expected_request:Bioc_domain.Construction.Request.t ->
  Bioc_domain.Construction_build.t -> Bioc_domain.Molecule_set.Artifact.t
