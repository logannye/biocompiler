(** Fresh current use-policy assessment. No human profile is admitted by this
    policy, regardless of stored claims, declared evidence or component labels. *)
val assess : Bioc_domain.Admission.Request.t -> Bioc_domain.Admission.Assessment.t
val verify : Bioc_domain.Admission.Request.t -> Bioc_domain.Admission.Assessment.t -> bool
val for_target : target:Bioc_domain.Build_request.Target.t -> boundary:Bioc_domain.Admission.boundary ->
  components:Bioc_domain.Component.t list -> Bioc_domain.Admission.Assessment.t
val require_software_use : target:Bioc_domain.Build_request.Target.t -> boundary:Bioc_domain.Admission.boundary ->
  components:Bioc_domain.Component.t list -> Bioc_domain.Admission.Assessment.t
