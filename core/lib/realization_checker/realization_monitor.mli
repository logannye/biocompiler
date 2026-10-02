val check : budget:Realization_budget.t -> behavior:Bioc_domain.Behavior.t ->
  contract:Bioc_domain.Realization_contract.Behavior_contract.t ->
  domain:Bioc_domain.Realization_contract.Operating_domain.t ->
  observation_map:Bioc_domain.Observation_map.t ->
  history:Bioc_domain.Execution_data.Input_frame.t list ->
  desired:Bioc_domain.Execution_data.Result.t -> actual:Bioc_domain.Model_execution_data.Trace.t ->
  dependencies:Bioc_domain.Realization_evidence.Dependency_snapshot.t ->
  horizon:Bioc_domain.Runtime_number.t -> Bioc_domain.Realization_evidence.Check_result.t
