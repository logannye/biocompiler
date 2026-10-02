(** Supplied behavior-to-material correspondence. Structural validation retains
    infeasible alternatives and unknown execution policies; it does not establish
    behavioral refinement, construction, placement feasibility or admission. *)
type t
val schema_version : string
val of_json : ?path:string -> Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val make : ?connections:Architecture_contract.Connection.t list -> ?controls:Architecture_contract.Control.t list ->
  ?helpers:Architecture_contract.Helper.t list -> ?channels:Architecture_contract.Channel.t list ->
  ?output_contracts:Architecture_contract.Output_binding.t list -> ?match_policy:Architecture_contract.Match_policy.t ->
  ?availability:Architecture_deployment.Availability.t list -> id:string -> version:string -> behavior:Behavior.t ->
  source_bindings:(Identity.Node.t * Identity.Node.t) list -> owned_node_ids:Identity.Node.t list -> components:Component.t list ->
  templates:Payload_template.t list -> bindings:Architecture_contract.Binding.t list -> placements:Architecture_contract.Placement.t list ->
  assumptions:string list -> unit -> t
val id : t -> string
val version : t -> string
val behavior : t -> Behavior.t
val source_bindings : t -> (Identity.Node.t * Identity.Node.t) list
val owned_node_ids : t -> Identity.Node.t list
val components : t -> Component.t list
val templates : t -> Payload_template.t list
val bindings : t -> Architecture_contract.Binding.t list
val placements : t -> Architecture_contract.Placement.t list
val assumptions : t -> string list
val connections : t -> Architecture_contract.Connection.t list
val controls : t -> Architecture_contract.Control.t list
val helpers : t -> Architecture_contract.Helper.t list
val channels : t -> Architecture_contract.Channel.t list
val output_contracts : t -> Architecture_contract.Output_binding.t list
val match_policy : t -> Architecture_contract.Match_policy.t option
val availability : t -> Architecture_deployment.Availability.t list
module Library : sig
  type refinement = t
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : ?assumptions:string list -> id:string -> refinements:refinement list -> unit -> t
  val id : t -> string
  val refinements : t -> refinement list
  val assumptions : t -> string list
end
