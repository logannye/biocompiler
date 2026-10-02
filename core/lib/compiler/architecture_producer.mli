(** Bounded search over supplied implementations. Source, component models,
    material authority, every retained alternative and exact search exhaustion
    remain explicit. Public independent checkers accept completed candidates. *)
val implementation_version : string
val resource_profile : string
val max_work : int
val compile : ?budget:Bioc_checker.Work_budget.t -> Bioc_domain.Architecture_request.t -> Bioc_domain.Architecture_build.t
val export : ?budget:Bioc_checker.Work_budget.t -> expected_request:Bioc_domain.Architecture_request.t ->
  Bioc_domain.Architecture_build.t -> Bioc_domain.Architecture_build.Export.t

(* Return the exact assessment computed before artifact publication. These
   variants do not replay or grant authority to a historical supplied report. *)
val compile_checked : ?budget:Bioc_checker.Work_budget.t -> Bioc_domain.Architecture_request.t ->
  Bioc_domain.Architecture_build.t * Bioc_domain.Architecture_assessment.t
val export_checked : ?budget:Bioc_checker.Work_budget.t -> expected_request:Bioc_domain.Architecture_request.t ->
  Bioc_domain.Architecture_build.t -> Bioc_domain.Architecture_build.Export.t * Bioc_domain.Architecture_assessment.t
