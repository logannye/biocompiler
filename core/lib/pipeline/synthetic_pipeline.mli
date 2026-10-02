(** Fixed checked BuildRequest -> Behavior -> synthetic candidate compilation.
    The supplied request is freshly checked; accepted records cannot be
    imported. Trusted process-local registration hooks operate on the actual
    manager, whose validation and freshness checks remain authoritative. Every
    operation consumes the same caller-owned lifetime work ancestor. Results are historical records;
    the retained live manager must be queried again before reusing completion.
    Finite-history completion leaves empirical molecular behavior unresolved. *)
val implementation_version : string
val resource_profile : string
val resource_limits : Bioc_wire.Json.t
type t
type config_origin = Requested | Selected
type provider_role =
  | Intent_to_behavior_producer
  | Intent_to_behavior_validator
  | Behavior_to_synthetic_producer of {
      requested_config:Bioc_domain.Synthetic_authority.Config.t;
      selected_config:Bioc_domain.Synthetic_authority.Config.t;
      config_origin:config_origin}
  | Behavior_to_synthetic_validator
  | Synthetic_to_components_producer of {
      registry:Bioc_domain.Component_registry.t;composition:Bioc_domain.Composition.t;
      candidate:Bioc_domain.Synthetic_authority.Candidate.t}
  | Synthetic_to_components_validator
type provider_observer = Bioc_checker.Work_budget.t -> Bioc_compiler.Pass_manager.t ->
  Bioc_compiler.Pass_manager.provider -> provider_role -> unit
(* Trusted read-only metadata for actual fixed closures, emitted once before
   registration. Captured object/origin identity is authoritative for views;
   equal serialized documents do not confer identity or a provider role. The
   observer uses the supplied lifetime budget and must not execute host code,
   register providers, alter the manager, or import acceptance. Omission keeps
   the ordinary fixed pipeline's metadata allocation and behavior unchanged. *)
type manager_created = Bioc_checker.Work_budget.t -> Bioc_compiler.Pass_manager.t -> unit
type registration_hook = Bioc_checker.Work_budget.t -> Bioc_compiler.Pass_manager.t ->
  Bioc_domain.Pipeline_contract.Pass_contract.t -> producer:Bioc_compiler.Pass_manager.provider ->
  validators:(string * Bioc_compiler.Pass_manager.provider) list -> unit
(* Optional fixed-authoring control seams. Publish the actual manager after its
   constructor and before add-input. A registration hook replaces exactly one
   real register call; it may invoke the live manager, and its return is ignored.
   Neither hook supplies a replacement owner or imports acceptance. Omitted
   hooks retain the ordinary native path and its resource behavior. *)
type failure = {error:exn;manager:Bioc_compiler.Pass_manager.t option}
type attempt = Completed of t | Failed of failure

(* Retains only the actual live manager if construction reached that point.
    Expected diagnostics, unsupported generation and no-candidate exceptions
    retain their original exception values. Fatal/unexpected exceptions escape.
    This diagnostic result neither imports records nor grants acceptance. *)
val attempt : budget:Bioc_checker.Work_budget.t ->
  ?manager_limits:Bioc_compiler.Pass_manager.limits ->
  ?validator_equivalent:Bioc_compiler.Pass_manager.validator_equivalent ->
  ?observer:Bioc_compiler.Pass_manager.observer ->
  ?provider_observer:provider_observer ->
  ?manager_created:manager_created -> ?register_fixed:registration_hook ->
  ?until:Bioc_domain.Runtime_number.t ->
  ?config:Bioc_domain.Synthetic_authority.Config.t ->
  Bioc_domain.Realization_request.t ->
  Bioc_domain.Execution_data.Input_frame.t list -> attempt
val run : budget:Bioc_checker.Work_budget.t ->
  ?manager_limits:Bioc_compiler.Pass_manager.limits ->
  ?validator_equivalent:Bioc_compiler.Pass_manager.validator_equivalent ->
  ?observer:Bioc_compiler.Pass_manager.observer ->
  ?provider_observer:provider_observer ->
  ?manager_created:manager_created -> ?register_fixed:registration_hook ->
  ?until:Bioc_domain.Runtime_number.t ->
  ?config:Bioc_domain.Synthetic_authority.Config.t ->
  Bioc_domain.Realization_request.t ->
  Bioc_domain.Execution_data.Input_frame.t list -> t
val candidate : t -> Bioc_domain.Synthetic_authority.Candidate.t
val result : t -> Bioc_domain.Pipeline_contract.Pipeline_result.t
(* Actual record returned by the initialized manager, retained without a fresh
   query or a clone through the historical result codec. *)
val record : t -> Bioc_domain.Pipeline_contract.Stage_record.t
val manager : t -> Bioc_compiler.Pass_manager.t
val selection_result : t -> Bioc_domain.Synthetic_selection.Result.t option
