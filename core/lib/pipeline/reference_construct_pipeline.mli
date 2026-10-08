(** Historical reference Components -> Construct workflow on one live manager.
    Contracts and result views never import acceptance. All native leaves and
    reentrant hooks consume the supplied lifetime work ancestor. *)
val pipeline_version : string
val implementation_version : string
val resource_profile : string
val resource_limits : Bioc_wire.Json.t
module M = Bioc_compiler.Pass_manager
module C = Bioc_domain.Pipeline_contract
module W = Bioc_checker.Work_budget
module R = Bioc_domain.Reference_construct

type provider_role = Authority_validator | Linkage_validator | Construct_producer | Layout_validator
type provider_observer = W.t -> M.t -> M.provider -> provider_role -> unit
type manager_created = W.t -> M.t -> unit
type input_registration_hook = W.t -> M.t -> C.Component_input_contract.t ->
  validators:(string * M.provider) list -> unit
type registration_hook = W.t -> M.t -> C.Pass_contract.t -> producer:M.provider ->
  validators:(string * M.provider) list -> unit
(* A host-generated candidate is retained as its actual object until ordinary
   deferred output materialization. The trusted adapter constructs only the
   original PassResult container after native source links have been derived;
   this capability cannot grant candidate or manager acceptance. *)
type generated = Native_candidate of R.Candidate.t | Host_candidate of M.host_value
(* [input] is the exact context document; the typed request is the freshly
   parsed representation, which may contain supplied parser defaults. *)
type generator = W.t -> input:Bioc_wire.Json.t -> R.Request.t -> generated
type generator_bridge = {
  generate : generator;
  host_proposal : W.t -> output:M.host_value -> source_links:C.Source_link.t list -> M.host_value;
}
(* Trusted host operand semantics for the original sorted four-field SourceLink
   tuples. Multiplicity and host exceptions must be preserved. The pipeline
   makes the actual provenance/observation acceptance decision. *)
type host_links_equal = W.t -> actual:M.host_value list -> expected:C.Source_link.t list -> bool

type prepared
type initialized
type admission
type registration
type t
type failure = { error:exn; manager:M.t option }
type attempt = Completed of t | Failed of failure
val prepare : budget:W.t -> ?manager_limits:M.limits ->
  request:R.Request.t -> registry:Bioc_domain.Component_registry.t ->
  manifests:(string * Bioc_domain.Reference_manifest.t) list -> unit -> prepared
val dependencies : prepared -> (string * string) list
val obligations : prepared -> C.Scoped_obligation.t list
val completion_profile : prepared -> C.Completion_profile.t
val create : budget:W.t -> ?validator_equivalent:M.validator_equivalent ->
  ?observer:M.observer -> ?manager_created:manager_created -> prepared -> initialized
val initialized_manager : initialized -> M.t
val prepare_admission : budget:W.t -> ?provider_observer:provider_observer -> initialized -> admission
val admission_contract : admission -> C.Component_input_contract.t
val admission_validators : admission -> (string * M.provider) list
val allow_admission_host_source_links : admission -> unit
(* The caller performs the original register-input, admit and fresh get calls
   before this phase. The record is the actual get return, retained by trusted
   application code, never reconstructed from a wire snapshot. *)
val prepare_registration : budget:W.t -> ?provider_observer:provider_observer ->
  ?generator_bridge:generator_bridge -> ?host_links_equal:host_links_equal -> admission ->
  admitted:C.Stage_record.t -> registration
val contract : registration -> C.Pass_contract.t
val producer : registration -> M.provider
val validators : registration -> (string * M.provider) list
(* Opt in only after the real successful registration. Without a configured
   exact host comparison capability, host-only layout links remain fail-closed. *)
val allow_host_source_links : registration -> unit
(* Finish consumes actual run/result capabilities, imports the returned payload
   structurally, and performs the original independent final check. It does not
   repeat a manager get/result query or confer fresh export acceptance. *)
val finish : budget:W.t -> registration -> record:C.Stage_record.t ->
  result:C.Pipeline_result.t -> t
val attempt : budget:W.t -> ?manager_limits:M.limits ->
  ?validator_equivalent:M.validator_equivalent -> ?observer:M.observer ->
  ?provider_observer:provider_observer -> ?manager_created:manager_created ->
  ?register_input:input_registration_hook -> ?register_fixed:registration_hook ->
  ?generator_bridge:generator_bridge -> ?host_links_equal:host_links_equal -> request:R.Request.t ->
  registry:Bioc_domain.Component_registry.t -> manifests:(string * Bioc_domain.Reference_manifest.t) list -> unit -> attempt
val run : budget:W.t -> ?manager_limits:M.limits ->
  ?validator_equivalent:M.validator_equivalent -> ?observer:M.observer ->
  ?provider_observer:provider_observer -> ?manager_created:manager_created ->
  ?register_input:input_registration_hook -> ?register_fixed:registration_hook ->
  ?generator_bridge:generator_bridge -> ?host_links_equal:host_links_equal -> request:R.Request.t ->
  registry:Bioc_domain.Component_registry.t -> manifests:(string * Bioc_domain.Reference_manifest.t) list -> unit -> t
val manager : t -> M.t
val candidate : t -> R.Candidate.t
val check_result : t -> Bioc_domain.Reference_construct_evidence.Result.t
val result : t -> C.Pipeline_result.t
val record : t -> C.Stage_record.t
val request : t -> R.Request.t
val registry : t -> Bioc_domain.Component_registry.t
val manifests : t -> (string * Bioc_domain.Reference_manifest.t) list
val budget : t -> W.t
val manager_limits : t -> M.limits
