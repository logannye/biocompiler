(** Fixed checked Intent -> Behavior -> Mechanism -> Components compilation.
    Every producer, independent checker, structural conversion and manager call
    consumes the supplied lifetime work ancestor. Optional trusted registration
    hooks act on the live manager; there is no receipt import route. The returned
    reports are historical observations;
    only a fresh query of the retained live manager establishes current scoped
    completion. Declared contracts and finite histories confer no empirical or
    human-use acceptance. *)
val implementation_version : string
val resource_profile : string
val resource_limits : Bioc_wire.Json.t
type t
type failure = {error:exn;manager:Bioc_compiler.Pass_manager.t option}
type attempt = Completed of t | Failed of failure

(* Shared phases for the fixed pipeline and its live-manager facade. Preparing
   declarations does not register them or change dependency roots. Callers keep
   the original order: prepare, eight dependency updates, prepare_profile,
   register the profile, prepare_registration, register/run/result, finish.
   Every phase is tied to the same actual upstream build and lifetime budget. *)
type prepared
type profiled
type registration
val prepare : budget:Bioc_checker.Work_budget.t ->
  ?manager_limits:Bioc_compiler.Pass_manager.limits ->
  ?until:Bioc_domain.Runtime_number.t -> Bioc_domain.Realization_request.t ->
  Bioc_domain.Execution_data.Input_frame.t list -> Synthetic_pipeline.t -> prepared
val dependencies : prepared -> (string * string) list
val prepare_profile : budget:Bioc_checker.Work_budget.t -> prepared -> profiled
val completion_profile : profiled -> Bioc_domain.Pipeline_contract.Completion_profile.t
val prepare_registration : budget:Bioc_checker.Work_budget.t ->
  ?provider_observer:Synthetic_pipeline.provider_observer -> profiled -> registration
val contract : registration -> Bioc_domain.Pipeline_contract.Pass_contract.t
val producer : registration -> Bioc_compiler.Pass_manager.provider
val validators : registration -> (string * Bioc_compiler.Pass_manager.provider) list
(* Enable the original fixed validator's explicit host source-link view only
   after its actual successful registration. This does not grant acceptance. *)
val allow_host_source_links : registration -> unit
(* Trusted result capabilities must be the actual run/result returns from this
   registration and upstream manager. The wire service resolves private retained
   capabilities and never supplies imported stage records or result snapshots.
   This phase parses the final artifact and performs the native link/behavior
   checks, without making a fresh manager get/result query. *)
val finish : budget:Bioc_checker.Work_budget.t -> registration ->
  record:Bioc_domain.Pipeline_contract.Stage_record.t ->
  result:Bioc_domain.Pipeline_contract.Pipeline_result.t -> t

(* Expected failure retains the actual upstream/partial component manager and
    the original exception value. Fatal/unexpected exceptions escape. No
    serialized record or caller-provided state is installed by this API. *)
val attempt : budget:Bioc_checker.Work_budget.t ->
  ?manager_limits:Bioc_compiler.Pass_manager.limits ->
  ?validator_equivalent:Bioc_compiler.Pass_manager.validator_equivalent ->
  ?observer:Bioc_compiler.Pass_manager.observer ->
  ?provider_observer:Synthetic_pipeline.provider_observer ->
  ?manager_created:Synthetic_pipeline.manager_created ->
  ?register_fixed:Synthetic_pipeline.registration_hook ->
  ?until:Bioc_domain.Runtime_number.t ->
  ?config:Bioc_domain.Synthetic_authority.Config.t ->
  Bioc_domain.Realization_request.t ->
  Bioc_domain.Execution_data.Input_frame.t list -> attempt
val run : budget:Bioc_checker.Work_budget.t ->
  ?manager_limits:Bioc_compiler.Pass_manager.limits ->
  ?validator_equivalent:Bioc_compiler.Pass_manager.validator_equivalent ->
  ?observer:Bioc_compiler.Pass_manager.observer ->
  ?provider_observer:Synthetic_pipeline.provider_observer ->
  ?manager_created:Synthetic_pipeline.manager_created ->
  ?register_fixed:Synthetic_pipeline.registration_hook ->
  ?until:Bioc_domain.Runtime_number.t ->
  ?config:Bioc_domain.Synthetic_authority.Config.t ->
  Bioc_domain.Realization_request.t ->
  Bioc_domain.Execution_data.Input_frame.t list -> t
val candidate : t -> Bioc_domain.Synthetic_authority.Candidate.t
(* Exact earlier synthetic build on the same manager, including its historical
   result and original mechanism record; this accessor performs no recheck. *)
val upstream : t -> Synthetic_pipeline.t
val assembly : t -> Bioc_domain.Component_assembly.t
val link_result : t -> Bioc_domain.Composition_evidence.Result.t
val result : t -> Bioc_domain.Pipeline_contract.Pipeline_result.t
(* Actual record returned by the initialized manager. This historical object
   remains observable even when a later manager mutation makes it stale. *)
val record : t -> Bioc_domain.Pipeline_contract.Stage_record.t
val manager : t -> Bioc_compiler.Pass_manager.t
val behavior_result : t -> Bioc_domain.Realization_evidence.Check_result.t
val selection_result : t -> Bioc_domain.Synthetic_selection.Result.t option
