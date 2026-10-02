(** Fixed checked Intent -> Behavior -> Mechanism -> Components compilation.
    Every producer, independent checker, structural conversion and manager call
    consumes the supplied lifetime work ancestor. There is no provider hook or
    receipt import route. The returned reports are historical observations;
    only a fresh query of the retained live manager establishes current scoped
    completion. Declared contracts and finite histories confer no empirical or
    human-use acceptance. *)
val implementation_version : string
val resource_profile : string
val resource_limits : Bioc_wire.Json.t
type t
type failure = {error:exn;manager:Bioc_compiler.Pass_manager.t option}
type attempt = Completed of t | Failed of failure

(* Expected failure retains the actual upstream/partial component manager and
    the original exception value. Fatal/unexpected exceptions escape. No
    serialized record or caller-provided state is installed by this API. *)
val attempt : budget:Bioc_checker.Work_budget.t ->
  ?manager_limits:Bioc_compiler.Pass_manager.limits ->
  ?validator_equivalent:Bioc_compiler.Pass_manager.validator_equivalent ->
  ?observer:Bioc_compiler.Pass_manager.observer ->
  ?provider_observer:Synthetic_pipeline.provider_observer ->
  ?until:Bioc_domain.Runtime_number.t ->
  ?config:Bioc_domain.Synthetic_authority.Config.t ->
  Bioc_domain.Realization_request.t ->
  Bioc_domain.Execution_data.Input_frame.t list -> attempt
val run : budget:Bioc_checker.Work_budget.t ->
  ?manager_limits:Bioc_compiler.Pass_manager.limits ->
  ?validator_equivalent:Bioc_compiler.Pass_manager.validator_equivalent ->
  ?observer:Bioc_compiler.Pass_manager.observer ->
  ?provider_observer:Synthetic_pipeline.provider_observer ->
  ?until:Bioc_domain.Runtime_number.t ->
  ?config:Bioc_domain.Synthetic_authority.Config.t ->
  Bioc_domain.Realization_request.t ->
  Bioc_domain.Execution_data.Input_frame.t list -> t
val candidate : t -> Bioc_domain.Synthetic_authority.Candidate.t
val assembly : t -> Bioc_domain.Component_assembly.t
val link_result : t -> Bioc_domain.Composition_evidence.Result.t
val result : t -> Bioc_domain.Pipeline_contract.Pipeline_result.t
val manager : t -> Bioc_compiler.Pass_manager.t
val behavior_result : t -> Bioc_domain.Realization_evidence.Check_result.t
val selection_result : t -> Bioc_domain.Synthetic_selection.Result.t option
