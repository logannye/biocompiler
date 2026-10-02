(** Structural, historical source-execution declarations. Original wrapped
    source, ordering and arbitrary retained JSON inventories are preserved.
    [complete] is a stored-shape property, never fresh semantic acceptance.
    Native imports additionally enforce bounded UTF-8 JSON (32 MiB compact,
    250,000 nodes including keys, depth 128); see [boundary_version]. *)
val schema_version : string
val claim_scope : string
val boundary_version : string
val max_source_nodes : int
(* Aggregate reservation for independently reconstructed inventories. Exhaustion
    raises [source_manifest_limit] and yields no partial semantic report. *)
type resource_budget
val create_resource_budget : unit -> resource_budget
val reserve_json : resource_budget -> Bioc_wire.Json.t -> unit
module Diagnostic_record : sig
  type category = Unsupported_semantics | Missing_refinement | Contradiction
  type t
  val make : code:string -> category:category -> source_node_ids:string list -> message:string -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val category_name : category -> string
  val code : t -> string
  val category : t -> category
  val source_node_ids : t -> string list
  val message : t -> string
end
module Output : sig
  type trigger = Condition | Event
  type activation = Level | Event_activation | Onset | Explicit_duration
  type t
  val make : id:string -> rule_id:string -> action_id:string -> guard_id:string -> role_id:string ->
    action_kind:string -> lineage:string list -> trigger:trigger -> activation:activation ->
    product:string option -> semantics:Bioc_wire.Json.t -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val trigger_name : trigger -> string
  val activation_name : activation -> string
  val id : t -> string
  val rule_id : t -> string
  val action_id : t -> string
  val guard_id : t -> string
  val role_id : t -> string
  val action_kind : t -> string
  val lineage : t -> string list
  val trigger : t -> trigger
  val activation : t -> activation
  val product : t -> string option
  val semantics : t -> Bioc_wire.Json.t
end
type t
val make : source:Human_request.t -> behavior:Behavior.t option -> roles:string list ->
  outputs:Output.t list -> ledger:Bioc_wire.Json.t list -> role_nodes:Bioc_wire.Json.t ->
  states:Bioc_wire.Json.t list -> channels:Bioc_wire.Json.t list -> diagnostics:Diagnostic_record.t list -> t
val of_json : ?path:string -> Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val source : t -> Human_request.t
val behavior : t -> Behavior.t option
val roles : t -> string list
val outputs : t -> Output.t list
val ledger : t -> Bioc_wire.Json.t list
val role_nodes : t -> Bioc_wire.Json.t
val states : t -> Bioc_wire.Json.t list
val channels : t -> Bioc_wire.Json.t list
val diagnostics : t -> Diagnostic_record.t list
val build_request : t -> Build_request.t
val source_fingerprint : t -> string
val complete : t -> bool
