(** Fixed checked BuildRequest -> Behavior -> synthetic candidate compilation.
    The supplied request is freshly checked; no imported accepted record or
    caller-supplied provider can authorize a stage. Every operation consumes the
    same caller-owned lifetime work ancestor. Results are historical records;
    the retained live manager must be queried again before reusing completion.
    Finite-history completion leaves empirical molecular behavior unresolved. *)
val implementation_version : string
val resource_profile : string
val resource_limits : Bioc_wire.Json.t
type t
type failure = {error:exn;manager:Bioc_compiler.Pass_manager.t option}
type attempt = Completed of t | Failed of failure

(* Retains only the actual live manager if construction reached that point.
    Expected diagnostics, unsupported generation and no-candidate exceptions
    retain their original exception values. Fatal/unexpected exceptions escape.
    This diagnostic result neither imports records nor grants acceptance. *)
val attempt : budget:Bioc_checker.Work_budget.t ->
  ?manager_limits:Bioc_compiler.Pass_manager.limits ->
  ?validator_equivalent:Bioc_compiler.Pass_manager.validator_equivalent ->
  ?until:Bioc_domain.Runtime_number.t ->
  ?config:Bioc_domain.Synthetic_authority.Config.t ->
  Bioc_domain.Realization_request.t ->
  Bioc_domain.Execution_data.Input_frame.t list -> attempt
val run : budget:Bioc_checker.Work_budget.t ->
  ?manager_limits:Bioc_compiler.Pass_manager.limits ->
  ?validator_equivalent:Bioc_compiler.Pass_manager.validator_equivalent ->
  ?until:Bioc_domain.Runtime_number.t ->
  ?config:Bioc_domain.Synthetic_authority.Config.t ->
  Bioc_domain.Realization_request.t ->
  Bioc_domain.Execution_data.Input_frame.t list -> t
val candidate : t -> Bioc_domain.Synthetic_authority.Candidate.t
val result : t -> Bioc_domain.Pipeline_contract.Pipeline_result.t
val manager : t -> Bioc_compiler.Pass_manager.t
val selection_result : t -> Bioc_domain.Synthetic_selection.Result.t option
