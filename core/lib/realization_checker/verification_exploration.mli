(** Deterministic bounded campaigns under an explicit evaluator. A callback result
    remains a supplied assertion; only the fixed workflow evaluator checks source
    and candidate authority. No callback or serialized executable is imported. *)
type evaluator = parent:Bioc_checker.Work_budget.t -> until:Bioc_domain.Runtime_number.t ->
  Bioc_domain.Execution_data.Input_frame.t list -> Bioc_domain.Realization_evidence.Check_result.t
val explore_in : budget:Verification_workflow_budget.t -> Bioc_domain.Verification_exploration.Bounds.t ->
  evaluate:evaluator -> Bioc_domain.Verification_exploration.Report.t
val explore_with_usage : ?limits:Verification_workflow_budget.limits -> ?parent:Bioc_checker.Work_budget.t ->
  Bioc_domain.Verification_exploration.Bounds.t -> evaluate:evaluator ->
  Bioc_domain.Verification_exploration.Report.t * Verification_workflow_budget.usage
val explore : ?limits:Verification_workflow_budget.limits -> ?parent:Bioc_checker.Work_budget.t ->
  Bioc_domain.Verification_exploration.Bounds.t -> evaluate:evaluator -> Bioc_domain.Verification_exploration.Report.t
val reduce_in : budget:Verification_workflow_budget.t -> history:Bioc_domain.Execution_data.Input_frame.t list ->
  until:Bioc_domain.Runtime_number.t -> signature:Bioc_domain.Verification_exploration.Failure_signature.t ->
  max_evaluations:int -> evaluate:evaluator -> Bioc_domain.Verification_exploration.Reduction.t
val reduce_with_usage : ?limits:Verification_workflow_budget.limits -> ?parent:Bioc_checker.Work_budget.t ->
  history:Bioc_domain.Execution_data.Input_frame.t list -> until:Bioc_domain.Runtime_number.t ->
  signature:Bioc_domain.Verification_exploration.Failure_signature.t -> ?max_evaluations:int ->
  evaluate:evaluator -> unit -> Bioc_domain.Verification_exploration.Reduction.t * Verification_workflow_budget.usage
val reduce : ?limits:Verification_workflow_budget.limits -> ?parent:Bioc_checker.Work_budget.t ->
  history:Bioc_domain.Execution_data.Input_frame.t list -> until:Bioc_domain.Runtime_number.t ->
  signature:Bioc_domain.Verification_exploration.Failure_signature.t -> ?max_evaluations:int ->
  evaluate:evaluator -> unit -> Bioc_domain.Verification_exploration.Reduction.t
val generate_adversarial_histories_in : budget:Verification_workflow_budget.t ->
  Bioc_domain.Verification_exploration.Adversarial_config.t -> Bioc_domain.Verification_exploration.History_case.t list
val generate_adversarial_histories_with_usage : ?limits:Verification_workflow_budget.limits ->
  ?parent:Bioc_checker.Work_budget.t -> Bioc_domain.Verification_exploration.Adversarial_config.t ->
  Bioc_domain.Verification_exploration.History_case.t list * Verification_workflow_budget.usage
val generate_adversarial_histories : ?limits:Verification_workflow_budget.limits ->
  ?parent:Bioc_checker.Work_budget.t -> Bioc_domain.Verification_exploration.Adversarial_config.t ->
  Bioc_domain.Verification_exploration.History_case.t list
