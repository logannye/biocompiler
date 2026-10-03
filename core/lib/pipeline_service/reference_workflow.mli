(** Channel-owned capabilities for the historical reference workflow. This layer
    performs native declaration preparation and final checks, but never invents
    manager calls, imports records, hydrates host objects or parses a protocol. *)
module M = Bioc_compiler.Pass_manager
module C = Bioc_domain.Pipeline_contract
module W = Bioc_checker.Work_budget
module Construct = Bioc_pipeline.Reference_construct_pipeline
module Molecular = Bioc_pipeline.Reference_molecular_pipeline

type phase = Fresh | Initializing | Construct_created | Admission_available
  | Admission_registered | Admission_returned | Admission_checked
  | Construct_registration_available | Construct_registered | Construct_ran
  | Construct_result | Construct_finished | Molecular_dependencies
  | Molecular_profile_available | Molecular_profile_registered
  | Molecular_registration_available | Molecular_registered | Molecular_ran
  | Molecular_result | Molecular_finished | Interrupted | Closed

type t
type molecular_attempt
(* [retain_bytes] is the owning channel's cumulative, no-refund reservation.
   It must reserve before returning and propagate resource failures unchanged. *)
val create : budget:W.t -> retain_bytes:(int -> unit) ->
  ?manager_limits:M.limits -> unit -> t
val owner : t -> M.t option
val phase : t -> phase
val close : t -> unit
val initialize_construct : t -> budget:W.t ->
  ?validator_equivalent:M.validator_equivalent -> ?observer:M.observer ->
  ?manager_created:Construct.manager_created ->
  request:Bioc_domain.Reference_construct.Request.t ->
  registry:Bioc_domain.Component_registry.t ->
  manifests:(string * Bioc_domain.Reference_manifest.t) list -> unit -> M.t
val prepare_admission : t -> budget:W.t ->
  ?provider_observer:Construct.provider_observer -> unit -> Construct.admission
val prepare_construct_registration : t -> budget:W.t ->
  ?provider_observer:Construct.provider_observer ->
  ?generator_bridge:Construct.generator_bridge ->
  ?host_links_equal:Construct.host_links_equal -> unit -> Construct.registration

(* The application calls [notice] exactly once AFTER each successful real
   manager operation. These are trusted actual objects from that call, never
   decoded acceptance or independently reconstructed provider snapshots. A
   producer may be a registered host wrapper. The exact native validators alone
   receive their reviewed host-sidecar opt-in after actual registration.

   Unrelated generic operations keep their ordinary manager behavior. Only a matching successful operation advances the current phase; extra,
   repeated or out-of-order generic operations leave it unchanged. Command
   sequence replay and foreign manager ownership are adapter errors. *)
type operation =
  | Input_registered of C.Component_input_contract.t * (string * M.provider) list
  | Admitted of {contract_id:string; identity:string; record:C.Stage_record.t}
  | Got of {identity:string; record:C.Stage_record.t}
  | Pass_registered of C.Pass_contract.t * M.provider * (string * M.provider) list
  | Ran of {pass_id:string; input_id:string; output_id:string;
      default_configuration:bool; record:C.Stage_record.t}
  | Result_returned of {identity:string; scope:string; result:C.Pipeline_result.t}
  | Dependency_set of string * string
  | Profile_registered of C.Completion_profile.t
val notice : t -> budget:W.t -> owner:M.t -> sequence:int -> operation -> unit

(* Both capabilities must name the exact previously observed run/result pair.
   Finishing is single-use, retains the original historical result, and never
   calls manager get/result. Failed final checks leave the real manager intact. *)
val finish_construct : t -> budget:W.t -> record:C.Stage_record.t ->
  result_sequence:int -> Construct.t
val prepare_molecular : ?authority:Molecular.authority -> t -> budget:W.t -> unit -> Molecular.prepared
val prepare_molecular_profile : t -> budget:W.t -> unit -> Molecular.profiled
val prepare_molecular_registration : t -> budget:W.t ->
  ?provider_observer:Molecular.provider_observer ->
  ?emitter_bridge:Molecular.emitter_bridge ->
  ?host_links_equal:Molecular.host_links_equal -> unit -> Molecular.registration
val finish_molecular : ?final_source_bridge:Molecular.final_source_bridge -> t -> budget:W.t -> record:C.Stage_record.t ->
  result_sequence:int -> Molecular.t
val construct_build : t -> Construct.t option
(* Kind-only lookup names the last successfully finished attempt, in completion
   order. A later created or failed attempt never replaces that capability.
   Each public invocation still returns its own exact finished Build. *)
val molecular_build : t -> Molecular.t option
val construct_result_sequence : t -> int option
val molecular_result_sequence : t -> int option

(* Attempt scopes are explicit LIFO capabilities. They share one actual manager
   and lifetime allowance; leaving drops only execution scope, never old roots,
   providers, records, results or completed builds. The caller must leave in a
   finally block unless the channel is already closed. *)
val active_molecular : t -> molecular_attempt option
val molecular_attempt_phase : molecular_attempt -> phase
val molecular_prepared : molecular_attempt -> Molecular.prepared
val leave_molecular : t -> budget:W.t -> molecular_attempt -> unit
val notice_for : t -> budget:W.t -> owner:M.t -> sequence:int ->
  molecular:molecular_attempt option -> operation -> unit
val molecular_build_of : t -> budget:W.t -> molecular_attempt -> Molecular.t option
