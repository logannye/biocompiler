(** Exact-reference Construct -> Molecular continuation on the actual upstream
    manager. Independent checks establish only the declared exact-CDS software
    scope. Payload completeness and molecular behavior remain unresolved. *)
val implementation_version : string
val pipeline_version : string
val resource_profile : string
val resource_limits : Bioc_wire.Json.t
type t
type authority = {
  request : Bioc_domain.Reference_construct.Request.t;
  registry : Bioc_domain.Component_registry.t;
  manifests : (string * Bioc_domain.Reference_manifest.t) list;
}
(* Caller-authored molecular authority is independent of the returned Construct
   build's manager provenance. Both remain bounded, untrusted checker inputs. *)
type final_source_bridge = {
  check_construct : Bioc_checker.Work_budget.t -> Bioc_domain.Reference_construct.Candidate.t;
  return_construct : Bioc_checker.Work_budget.t -> Bioc_compiler.Pass_manager.host_value;
}
(* Two distinct original candidate reads: the first follows artifact parsing
   and supplies untrusted typed input to the independent check. The second
   follows that check and remains an opaque Build.construct value; it may differ.
   Callbacks retain their original exceptions. The host owns their captures and
   handle reservations; this bridge cannot grant acceptance. *)
type prepared
type profiled
type registration
type provider_role = Emit | Sequence_identity | Encoding_composition
type provider_observer = Bioc_checker.Work_budget.t ->
  Bioc_compiler.Pass_manager.t -> Bioc_compiler.Pass_manager.provider ->
  provider_role -> unit
(* Trusted read-only identity publication, once for each actual closure. The
   observer must not run authoring code, replace providers, or mutate manager
   authority. It consumes the supplied lifetime budget. *)

(* A trusted source-authoring seam, called at each original emitter lookup.
   A host output stays opaque until ordinary deferred manager conversion. The
   paired builder constructs only the original PassResult container after the
   native source links have been derived. Neither part decides acceptance. *)
type emitted = Native_artifact of Bioc_domain.Reference_molecular.Artifact.t
  | Host_artifact of Bioc_compiler.Pass_manager.host_value
(* [input] retains the actual context document separately from the complete
   freshly parsed Construct value, including any parser-supplied defaults. *)
type emitter = Bioc_checker.Work_budget.t -> input:Bioc_wire.Json.t ->
  request:Bioc_domain.Reference_construct.Request.t ->
  construct:Bioc_domain.Reference_construct.Candidate.t ->
  registry:Bioc_domain.Component_registry.t ->
  manifests:(string * Bioc_domain.Reference_manifest.t) list ->
  emitted
type emitter_bridge = {
  emit : emitter;
  host_proposal : Bioc_checker.Work_budget.t ->
    output:Bioc_compiler.Pass_manager.host_value ->
    source_links:Bioc_domain.Pipeline_contract.Source_link.t list ->
    Bioc_compiler.Pass_manager.host_value;
}
type host_links_equal = Bioc_checker.Work_budget.t ->
  actual:Bioc_compiler.Pass_manager.host_value list ->
  expected:Bioc_domain.Pipeline_contract.Source_link.t list -> bool
(* The optional comparator must perform the original sorted four-field tuple
   comparison on actual host objects, retaining duplicate multiplicity. It is
   not a set comparison or an imported equality assertion. *)

(* Preparation captures no replacement state and performs no manager queries.
   Preserve the original sequence: prepare, six dependency writes,
   prepare_profile, profile registration, prepare_registration, registration,
   run, result, finish. Every phase requires the upstream lifetime budget. *)
val prepare : budget:Bioc_checker.Work_budget.t -> ?authority:authority ->
  Reference_construct_pipeline.t -> prepared
val prepared_authority : prepared -> authority
val dependencies : prepared -> (string * string) list
val prepare_profile : budget:Bioc_checker.Work_budget.t -> prepared -> profiled
val completion_profile : profiled -> Bioc_domain.Pipeline_contract.Completion_profile.t
val prepare_registration : budget:Bioc_checker.Work_budget.t ->
  ?provider_observer:provider_observer -> ?emitter_bridge:emitter_bridge ->
  ?host_links_equal:host_links_equal -> profiled -> registration
val contract : registration -> Bioc_domain.Pipeline_contract.Pass_contract.t
val producer : registration -> Bioc_compiler.Pass_manager.provider
val validators : registration -> (string * Bioc_compiler.Pass_manager.provider) list
(* Call only after the actual registration. The provenance validator opts in
   only when its exact host comparator was supplied; otherwise it fails closed.
   The linkage validator ignores source links and may safely consume a context
   retaining them. No proposal receives acceptance from this capability. *)
val allow_host_source_links : registration -> unit

(* The trusted caller supplies the actual returned run/result capabilities.
   No serialized acceptance import, new get, or new result query is performed.
   The default final source is the retained upstream candidate; the optional
   bridge preserves the two external source reads without fresh manager queries. *)
val finish : budget:Bioc_checker.Work_budget.t -> ?final_source_bridge:final_source_bridge -> registration ->
  record:Bioc_domain.Pipeline_contract.Stage_record.t ->
  result:Bioc_domain.Pipeline_contract.Pipeline_result.t -> t

type failure = {error:exn;manager:Bioc_compiler.Pass_manager.t}
type attempt = Completed of t | Failed of failure
val attempt : budget:Bioc_checker.Work_budget.t -> ?authority:authority ->
  ?provider_observer:provider_observer -> ?emitter_bridge:emitter_bridge ->
  ?host_links_equal:host_links_equal ->
  ?register_fixed:Synthetic_pipeline.registration_hook -> ?final_source_bridge:final_source_bridge ->
  Reference_construct_pipeline.t -> attempt
val run : budget:Bioc_checker.Work_budget.t -> ?authority:authority ->
  ?provider_observer:provider_observer -> ?emitter_bridge:emitter_bridge ->
  ?host_links_equal:host_links_equal ->
  ?register_fixed:Synthetic_pipeline.registration_hook -> ?final_source_bridge:final_source_bridge ->
  Reference_construct_pipeline.t -> t
val upstream : t -> Reference_construct_pipeline.t
(* Native upstream authority, not the optional opaque public return override. *)
val construct : t -> Bioc_domain.Reference_construct.Candidate.t
val returned_construct : t -> Bioc_compiler.Pass_manager.host_value option
val build_authority : t -> authority
val candidate : t -> Bioc_domain.Reference_molecular.Artifact.t
val check_result : t -> Bioc_domain.Reference_molecular_evidence.Result.t
val result : t -> Bioc_domain.Pipeline_contract.Pipeline_result.t
val record : t -> Bioc_domain.Pipeline_contract.Stage_record.t
val manager : t -> Bioc_compiler.Pass_manager.t
