(** Fresh complete construction correspondence against independent authority.
    No expected candidate is exported. Resource exhaustion raises Diagnostic.Error
    without an assessment; structural success never establishes biological use. *)
(* Native receipts bind this implementation separately from legacy policy fields. *)
val implementation_version : string
val resource_profile : string
val max_work : int
val check : ?parent:Work_budget.t -> ?maximum:int -> expected_request:Bioc_domain.Construction.Request.t -> Bioc_domain.Construction_artifact.t -> Bioc_domain.Construction_assessment.t
val replay : ?parent:Work_budget.t -> ?maximum:int -> expected_request:Bioc_domain.Construction.Request.t -> candidate:Bioc_domain.Construction_artifact.t ->
  Bioc_domain.Construction_assessment.t -> Bioc_domain.Construction_assessment.t

(** Fresh source-neutral exact-content correspondence only. Original provider,
    recipient, implementation and required-region/complete-payload eligibility
    are deliberately unassessed. The abstract result has no public constructor. *)
type content_assessment
val content_implementation_version : string
val content_outcome : content_assessment -> Bioc_domain.Construction_assessment.outcome
val content_diagnostics : content_assessment -> string list
val content_report : content_assessment -> Bioc_wire.Json.t
val checked_content : content_assessment -> Bioc_domain.Construction_content.t option
val check_template : ?parent:Work_budget.t -> ?maximum:int ->
  expected_template:Bioc_domain.Payload_template.t -> expected_member_order:string list ->
  Bioc_domain.Construction_content.t -> content_assessment
val replay_template : ?parent:Work_budget.t -> ?maximum:int ->
  expected_template:Bioc_domain.Payload_template.t -> expected_member_order:string list ->
  candidate:Bioc_domain.Construction_content.t -> Bioc_wire.Json.t -> content_assessment
