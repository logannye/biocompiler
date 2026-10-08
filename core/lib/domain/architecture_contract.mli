(** Architecture declarations and source-side constraints. Construction establishes
    only local record invariants, never material feasibility, correspondence,
    candidate execution or acceptance. Contextual obligations remain explicit. *)
val max_records : int
val max_nodes : int
val max_match_states : int
type control_kind = Activation | Production_adjustment | Activity_control | Memory_reset
  | Shutdown | Physical_separation | Dependency_disjointness
val control_kind_name : control_kind -> string

module Binding : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> behavior_node_ids:Identity.Node.t list -> component_ids:Identity.Component.t list -> template_ids:string list -> placement_ids:string list -> t
  val id : t -> string
  val behavior_node_ids : t -> Identity.Node.t list
  val component_ids : t -> Identity.Component.t list
  val template_ids : t -> string list
  val placement_ids : t -> string list
end

module Connection : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> producer_component_id:Identity.Component.t -> producer_port_id:string -> consumer_component_id:Identity.Component.t -> consumer_port_id:string -> t
  val id : t -> string
  val producer_component_id : t -> Identity.Component.t
  val producer_port_id : t -> string
  val consumer_component_id : t -> Identity.Component.t
  val consumer_port_id : t -> string
end

module Placement : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> template_id:string -> member_id:string -> recipient_role:Identity.Role.t -> compartment:string -> delivery_group:string -> t
  val id : t -> string
  val template_id : t -> string
  val member_id : t -> string
  val recipient_role : t -> Identity.Role.t
  val compartment : t -> string
  val delivery_group : t -> string
end

module Control : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> kind:control_kind -> behavior_node_ids:Identity.Node.t list -> controlling_node_ids:Identity.Node.t list -> component_ids:Identity.Component.t list -> domain_id:string -> assumptions:string list -> t
  val id : t -> string
  val kind : t -> control_kind
  val behavior_node_ids : t -> Identity.Node.t list
  val controlling_node_ids : t -> Identity.Node.t list
  val component_ids : t -> Identity.Component.t list
  val domain_id : t -> string
  val assumptions : t -> string list
end

module Control_requirement : sig
  type relation = Shared | Independent
  val relation_name : relation -> string
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> kind:control_kind -> behavior_node_ids:Identity.Node.t list -> relation:relation -> forbidden_shared_dependencies:string list -> t
  val id : t -> string
  val kind : t -> control_kind
  val behavior_node_ids : t -> Identity.Node.t list
  val relation : t -> relation
  val forbidden_shared_dependencies : t -> string list
end

module Helper : sig
  (* Capacity, prerequisite cycles and provider feasibility are contextual checks.
     This record retains infeasible alternatives for later explanation. *)
  type availability = Same_rna | Other_rna | Host | External
  type initialization = Available_at_start | After_expression | After_trigger
  type sharing = Exclusive | Shared
  val availability_name : availability -> string
  val initialization_name : initialization -> string
  val sharing_name : sharing -> string
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t

  (** Opt-in grounded policy helper syntax allows an empty assumption list.
      Contextual initialization and capacity checks remain separate. *)
  val of_grounded_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> capability:string -> consumer_component_ids:Identity.Component.t list -> recipient_role:Identity.Role.t -> compartment:string -> availability:availability -> initialization:initialization -> sharing:sharing -> capacity:int -> assumptions:string list -> placement_id:string option -> provider_component_id:Identity.Component.t option -> depends_on:string list -> t
  val id : t -> string
  val capability : t -> string
  val consumer_component_ids : t -> Identity.Component.t list
  val recipient_role : t -> Identity.Role.t
  val compartment : t -> string
  val availability : t -> availability
  val initialization : t -> initialization
  val sharing : t -> sharing
  val capacity : t -> int
  val assumptions : t -> string list
  val placement_id : t -> string option
  val provider_component_id : t -> Identity.Component.t option
  val depends_on : t -> string list
end

module Channel : sig
  (* Initial values remain complete bounded JSON declarations. Source channel
     typing and executable transport policy are separate contextual checks. *)
  type failure_mode = Retain_last | Clear | Unknown
  type aggregation = Single_sender | Sum | Max
  val failure_mode_name : failure_mode -> string
  val aggregation_name : aggregation -> string
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> source_channel_id:Identity.Node.t -> sender_role:Identity.Role.t -> receiver_role:Identity.Role.t -> sender_node_id:Identity.Node.t -> receiver_node_id:Identity.Node.t -> latency_seconds:Architecture_deployment.Time.t -> persistence_seconds:Architecture_deployment.Time.t option -> failure_mode:failure_mode -> aggregation:aggregation -> initial_value:Bioc_wire.Json.t -> assumptions:string list -> t
  val id : t -> string
  val source_channel_id : t -> Identity.Node.t
  val sender_role : t -> Identity.Role.t
  val receiver_role : t -> Identity.Role.t
  val sender_node_id : t -> Identity.Node.t
  val receiver_node_id : t -> Identity.Node.t
  val latency_seconds : t -> Architecture_deployment.Time.t
  val persistence_seconds : t -> Architecture_deployment.Time.t option
  val failure_mode : t -> failure_mode
  val aggregation : t -> aggregation
  val initial_value : t -> Bioc_wire.Json.t
  val assumptions : t -> string list
end

module Output_binding : sig
  (* Product and lifecycle are independently checked source declarations. Their
     correspondence to the named actions remains a checker responsibility. *)
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> requirement_id:Identity.Requirement.t -> action_ids:Identity.Node.t list -> product:Circuit_request.Product.t -> lifecycle:Circuit_request.Lifecycle.t -> t
  val id : t -> string
  val requirement_id : t -> Identity.Requirement.t
  val action_ids : t -> Identity.Node.t list
  val product : t -> Circuit_request.Product.t
  val lifecycle : t -> Circuit_request.Lifecycle.t
end

module Delivery_group : sig
  type mode = Co_delivered | Independent
  val mode_name : mode -> string
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> recipient_roles:Identity.Role.t list -> mode:mode -> same_recipient:bool -> assumptions:string list -> exact_count:int option -> max_count:int option -> max_total_bases:int option -> t
  val id : t -> string
  val recipient_roles : t -> Identity.Role.t list
  val mode : t -> mode
  val same_recipient : t -> bool
  val assumptions : t -> string list
  val exact_count : t -> int option
  val max_count : t -> int option
  val max_total_bases : t -> int option
end

module Constraints : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : exact_count:int option -> max_count:int option -> max_member_bases:int option -> max_total_bases:int option -> delivery_groups:Delivery_group.t list -> control_requirements:Control_requirement.t list -> preferred_refinement_ids:string list -> max_combinations:int -> require_complete:bool -> max_match_states:int -> max_match_instances:int -> deployment_requirements:Architecture_deployment.Requirement.t list -> t
  val exact_count : t -> int option
  val max_count : t -> int option
  val max_member_bases : t -> int option
  val max_total_bases : t -> int option
  val delivery_groups : t -> Delivery_group.t list
  val control_requirements : t -> Control_requirement.t list
  val preferred_refinement_ids : t -> string list
  val max_combinations : t -> int
  val require_complete : t -> bool
  val max_match_states : t -> int
  val max_match_instances : t -> int
  val deployment_requirements : t -> Architecture_deployment.Requirement.t list
end

module Match_policy : sig
  type mode = Exact_semantic_subgraph
  val mode_name : mode -> string
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : mode:mode -> t
  val mode : t -> mode
end

module Instance : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> refinement_id:string -> source_bindings:((Identity.Node.t * Identity.Node.t) list) -> t
  val id : t -> string
  val refinement_id : t -> string
  val source_bindings : t -> (Identity.Node.t * Identity.Node.t) list
end
