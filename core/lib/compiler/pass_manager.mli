(** In-memory checked stage orchestration. Only trusted process-local registrations may
    provide callbacks; serialized records cannot import manager acceptance.
    All calls, including reentrant callback mutations, consume the same caller-
    owned lifetime work ancestor. Limits below bound retained native state and
    recursion independently of historical semantic contracts. Retained JSON
    bytes and items reserve cumulative capacity without refunds. Trusted
    callback closure captures are opaque code-owned state, not imported data. *)
module C = Bioc_domain.Pipeline_contract
module W = Bioc_checker.Work_budget
val implementation_version : string
val resource_profile : string
type limits
val make_limits : ?max_records:int -> ?max_providers:int -> ?max_retained_items:int ->
  ?max_retained_bytes:int -> ?max_call_depth:int -> ?max_ancestor_depth:int -> ?max_document_bytes:int ->
  ?max_document_nodes:int -> unit -> limits
val default_limits : limits
val limits_json : limits -> Bioc_wire.Json.t
(* Process-local host objects are trusted extension capabilities, never wire
   records. Their primitive callbacks preserve host evaluation/exception order;
   manager branches, dependency checks and record storage remain native. *)
type host_class = Pass_result | Source_link | Check_decision | Mapping | String
type host_comparison = Eq | Ne | Is
type host_constant = Json_value of Bioc_wire.Json.t
  | Json_set of Bioc_wire.Json.t list
  | Evidence_kind of C.evidence_kind | Check_outcome of C.outcome
type host_value = {
  attribute : W.t -> string -> host_value;
  attribute_default : W.t -> string -> host_constant -> host_value;
  is_instance : W.t -> host_class -> bool;
  is_none : W.t -> bool;
  truth : W.t -> bool;
  compare : W.t -> host_comparison -> host_constant -> bool;
  (* Is this value a member of the supplied literal container? *)
  contains : W.t -> host_constant -> bool;
  attribute_set_equal : W.t -> host_value list -> attribute:string -> host_constant -> bool;
  source_link_set_equal : W.t -> host_value list -> C.Source_link.t list -> bool;
  lookup : W.t -> (string * Bioc_wire.Json.t) list -> Bioc_wire.Json.t;
  get_item : W.t -> host_constant -> host_value;
  get : W.t -> string -> host_value;
  tuple : W.t -> host_value list;
  iter : W.t -> host_iterator;
  call : W.t -> host_value list -> host_value;
  merge : W.t -> before:Bioc_wire.Json.t -> after:Bioc_wire.Json.t -> host_value;
  document : W.t -> host_value;
  freeze : W.t -> Bioc_wire.Json.t;
  vars : W.t -> host_value;
}
and host_iterator = { next : W.t -> host_value option }
type callback_result = Proposal of C.Pass_result.t | Decision of C.Check_decision.t
  | Invalid_return of Bioc_wire.Json.t | Host_return of host_value
(* The function value is the provider identity: physical equality is intentional.
   A fresh closure is a new provider even when its implementation is identical.
   The same unified provider type allows detecting producer self-certification. *)
type provider = W.t -> C.Pass_context.t -> callback_result
(* Trusted native comparison of prior and replacement validator values; create
   defaults to physical equality. Called
   only when their physical identities differ, in the prior mapping's order.
   It receives the manager's lifetime budget and may reenter the live manager;
   exceptions and mutations are retained. This does not compare producers,
   alter self-certification checks, merge provider identities or import trust. *)
type validator_equivalent = W.t -> provider -> provider -> bool
(* Trusted read-only identity metadata, using the same lifetime budget. One
   execution id relates producer/validator contexts and the stored record.
   Record_stored runs after the real mutation and before final freshness checks.
   The observer must not execute authoring callbacks or change native authority. *)
type origin = Input_origin | Admission_origin of C.Component_input_contract.t
  | Pass_origin of C.Stage_record.t * C.Pass_contract.t
type observation = Context_created of int * origin * C.Pass_context.t
  | Record_stored of int * origin * C.Stage_record.t
type observer = W.t -> observation -> unit
type no_candidate = {pass_id:string; configuration:Bioc_wire.Json.t;
  dependencies:(string * string) list; message:string}
exception No_candidate_found of no_candidate
type t
val create : budget:W.t -> ?limits:limits -> ?validator_equivalent:validator_equivalent -> ?observer:observer ->
  target:Bioc_domain.Build_request.Target.t ->
  dependencies:(string * string) list -> ?completion_profiles:C.Completion_profile.t list -> unit -> t
(* Creates and marks a real trusted host wrapper, retaining its physical identity.
   Native providers consume host-only SourceLink sidecars only after the explicit
   reviewed opt-in below; unmarked providers fail closed before invocation. *)
val bind_host_provider : t -> (W.t -> C.Pass_context.t -> host_value) -> provider
val target : t -> Bioc_domain.Build_request.Target.t
(* Original host SourceLink objects for the active callback only. Nested calls
   restore the previous sidecar; None is the unchanged native-provider path. *)
val callback_source_links : t -> host_value list option
(* Trusted native providers opt in only when they either ignore host links or
   compare them through the exact host set operation below. No wire mutation
   grants this capability. *)
val allow_host_source_links : t -> provider -> unit
val host_source_links_equal : t -> expected:C.Source_link.t list -> bool option
(* Invoke an already retained trusted provider with the retained context's
   original sidecar. The ordinary native callback checks, lifetime budget and
   dynamically scoped restoration apply; no caller data imports acceptance. *)
val invoke_provider : t -> host_links:host_value list option -> provider -> C.Pass_context.t -> callback_result
val register_completion_profile : t -> C.Completion_profile.t -> unit
val set_dependency : t -> string -> string -> unit
(* Host mapping traversals occur only at these requested stages, including two
   distinct snapshots when prior-validator equality is needed. validate checks
   the producer as well for pass registration. All handles remain actual code. *)
type deferred_validators = {
  validate : W.t -> bool;
  keys_match : W.t -> string list -> bool;
  snapshot : W.t -> (string * provider) list;
}
val register_deferred : t -> C.Pass_contract.t -> producer:(W.t -> provider) ->
  self_certifying:(W.t -> bool) -> deferred_validators -> unit
val register_component_input_deferred : t -> C.Component_input_contract.t -> deferred_validators -> unit
val register : t -> C.Pass_contract.t -> producer:provider -> validators:(string * provider) list -> unit
val register_component_input : t -> C.Component_input_contract.t -> validators:(string * provider) list -> unit
(* Deferred entry points run the ordinary native preconditions before invoking
   authored-object conversion or configuration freeze. Host fingerprint lookup
   occurs only after the checked document's default identity is computed. *)
val admit_host_component_input : t -> contract_id:string -> identity:string -> host_value -> C.Stage_record.t
val add_host_input : t -> identity:string -> ?stage:C.stage -> ?requirements:string list ->
  ?obligations:C.Scoped_obligation.t list -> host_value -> C.Stage_record.t
val run_host : t -> pass_id:string -> input_id:string -> output_id:string ->
  ?configuration:host_value -> unit -> C.Stage_record.t
val admit_component_input : t -> contract_id:string -> identity:string -> Bioc_wire.Json.t -> C.Stage_record.t
val add_input : t -> identity:string -> ?stage:C.stage -> ?requirements:string list ->
  ?obligations:C.Scoped_obligation.t list -> Bioc_wire.Json.t -> C.Stage_record.t
(* This entry derives the semantic identity from an actual checked native request;
   it never accepts an externally asserted fingerprint override. *)
val add_build_request : t -> identity:string -> ?requirements:string list ->
  ?obligations:C.Scoped_obligation.t list -> Bioc_domain.Build_request.t -> C.Stage_record.t
val get : t -> string -> C.Stage_record.t
val run : t -> pass_id:string -> input_id:string -> output_id:string ->
  ?configuration:Bioc_wire.Json.t -> unit -> C.Stage_record.t
val result : t -> identity:string -> scope:string -> C.Pipeline_result.t
(* Inspection preserves rejected records and complete registration history but
   grants no acceptance and has no inverse/import operation. Provider labels are
   supplied by trusted diagnostics/test code and never used for identity checks. *)
val inspect : t -> provider_identity:(provider -> string) -> Bioc_wire.Json.t
