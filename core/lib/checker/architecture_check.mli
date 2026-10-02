(** Fresh architecture correspondence against full separately supplied authority.
    Search completeness, empirical component function and admission are outside
    this receipt. Resource exhaustion raises an error without a partial report. *)
val implementation_version : string
val resource_profile : string
val max_work : int
val make_budget : ?parent:Work_budget.t -> ?maximum:int -> unit -> Work_budget.t
val check : ?budget:Work_budget.t -> expected_request:Bioc_domain.Architecture_request.t ->
  Bioc_domain.Architecture_build.t -> Bioc_domain.Architecture_assessment.t
val replay : ?budget:Work_budget.t -> expected_request:Bioc_domain.Architecture_request.t ->
  build:Bioc_domain.Architecture_build.t -> Bioc_domain.Architecture_assessment.t -> Bioc_domain.Architecture_assessment.t
