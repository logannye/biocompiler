(** Fresh complete construction correspondence against independent authority.
    No expected candidate is exported. Resource exhaustion raises Diagnostic.Error
    without an assessment; structural success never establishes biological use. *)
(* Native receipts bind this implementation separately from legacy policy fields. *)
val implementation_version : string
val check : expected_request:Bioc_domain.Construction.Request.t -> Bioc_domain.Construction_artifact.t -> Bioc_domain.Construction_assessment.t
val replay : expected_request:Bioc_domain.Construction.Request.t -> candidate:Bioc_domain.Construction_artifact.t ->
  Bioc_domain.Construction_assessment.t -> Bioc_domain.Construction_assessment.t
