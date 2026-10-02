(** Fresh finite-history checking under supplied complete Behavior authority.
    This direct API does not establish lowering from a BuildRequest, composition
    acceptance, human admission or empirical biological behavior. *)
val checker_version : string
val implementation_version : string
val reference_evaluator_version : string
val settings : Bioc_wire.Json.t
type limits
val make_limits : ?max_work:int -> ?max_monitor_items:int -> ?max_request_bytes:int ->
  ?max_report_bytes:int -> ?max_report_nodes:int -> unit -> limits
val default_limits : limits
val limits_json : limits -> Bioc_wire.Json.t
type usage = { work_charged : int; reserved_failure_work : int; monitor_peak : int;
  request_bytes : int; report_bytes : int }
(* Failure reservations are conservative charges, never exact failed-engine
   usage. Source/candidate trace-item units are deliberately not combined.
   Translated candidate history has its own fixed cumulative 16 MiB/250k-node
   ceiling; its complete UTF-8 bytes/key-value nodes charge the same work scope
   before typed import without changing original request bytes or identity. *)
val dependencies_with_usage : ?until:Bioc_domain.Runtime_number.t -> ?limits:limits ->
  ?parent:Bioc_checker.Work_budget.t -> Bioc_domain.Behavior.t ->
  Bioc_domain.Realization_contract.Behavior_contract.t -> Bioc_domain.Realization_contract.Operating_domain.t ->
  Bioc_domain.Build_request.Target.t -> Bioc_domain.Mechanism.t -> Bioc_domain.Observation_map.t ->
  Bioc_domain.Execution_data.Input_frame.t list -> Bioc_domain.Realization_evidence.Dependency_snapshot.t * usage
val dependencies : ?until:Bioc_domain.Runtime_number.t -> ?limits:limits ->
  ?parent:Bioc_checker.Work_budget.t -> Bioc_domain.Behavior.t ->
  Bioc_domain.Realization_contract.Behavior_contract.t -> Bioc_domain.Realization_contract.Operating_domain.t ->
  Bioc_domain.Build_request.Target.t -> Bioc_domain.Mechanism.t -> Bioc_domain.Observation_map.t ->
  Bioc_domain.Execution_data.Input_frame.t list -> Bioc_domain.Realization_evidence.Dependency_snapshot.t
val check_with_usage : ?until:Bioc_domain.Runtime_number.t -> ?limits:limits ->
  ?parent:Bioc_checker.Work_budget.t -> Bioc_domain.Behavior.t ->
  Bioc_domain.Realization_contract.Behavior_contract.t -> Bioc_domain.Realization_contract.Operating_domain.t ->
  Bioc_domain.Build_request.Target.t -> Bioc_domain.Mechanism.t -> Bioc_domain.Observation_map.t ->
  Bioc_domain.Execution_data.Input_frame.t list -> Bioc_domain.Realization_evidence.Check_result.t * usage
val check : ?until:Bioc_domain.Runtime_number.t -> ?limits:limits ->
  ?parent:Bioc_checker.Work_budget.t -> Bioc_domain.Behavior.t ->
  Bioc_domain.Realization_contract.Behavior_contract.t -> Bioc_domain.Realization_contract.Operating_domain.t ->
  Bioc_domain.Build_request.Target.t -> Bioc_domain.Mechanism.t -> Bioc_domain.Observation_map.t ->
  Bioc_domain.Execution_data.Input_frame.t list -> Bioc_domain.Realization_evidence.Check_result.t
