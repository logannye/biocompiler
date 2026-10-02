(** In-memory checked stage orchestration. Only trusted native registrations may
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
type callback_result = Proposal of C.Pass_result.t | Decision of C.Check_decision.t
  | Invalid_return of Bioc_wire.Json.t
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
type no_candidate = {pass_id:string; configuration:Bioc_wire.Json.t;
  dependencies:(string * string) list; message:string}
exception No_candidate_found of no_candidate
type t
val create : budget:W.t -> ?limits:limits -> ?validator_equivalent:validator_equivalent ->
  target:Bioc_domain.Build_request.Target.t ->
  dependencies:(string * string) list -> ?completion_profiles:C.Completion_profile.t list -> unit -> t
val target : t -> Bioc_domain.Build_request.Target.t
val register_completion_profile : t -> C.Completion_profile.t -> unit
val set_dependency : t -> string -> string -> unit
val register : t -> C.Pass_contract.t -> producer:provider -> validators:(string * provider) list -> unit
val register_component_input : t -> C.Component_input_contract.t -> validators:(string * provider) list -> unit
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
