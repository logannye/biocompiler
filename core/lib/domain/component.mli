(** Complete component declarations and contextual synthetic interface checks.
    These constructors do not establish registry resolution, model behavior,
    molecular implementation, composition acceptance or biological support. *)
module Pinned_identity = Pinned_identity
type scope = Component_contract.Port.scope = Cell | Contact

module Synthetic_operator : sig
  type t
  val schema_version : string
  val transition_policy : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : operation:Component_contract.synthetic_operation -> attributes:Bioc_wire.Json.t -> input_ports:string list -> output_port:string -> t
  val operation : t -> Component_contract.synthetic_operation
  val attributes : t -> Bioc_wire.Json.t
  val input_ports : t -> string list
  val output_port : t -> string
  val policy : t -> string
  (* A standalone declaration checks attribute inventory, not output-dependent
     literal types. Component construction calls this contextual validator. *)
  val validate_ports : t -> ports:Component_contract.Port.t list -> supported_domain:Component_contract.Operating_domain.t -> unit
  val domain_checks : t -> ports:Component_contract.Port.t list -> supported_domain:Component_contract.Operating_domain.t -> Component_contract.assessment list
end

module Parameter : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> value:Component_contract.Value_domain.t -> source:Pinned_identity.t -> method_name:string -> t
  val id : t -> string
  val value : t -> Component_contract.Value_domain.t
  val source : t -> Pinned_identity.t
  val method_name : t -> string
end

module Dependency : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> capability:string -> role:string -> scope:scope -> compartment:string -> required:bool -> t
  val id : t -> string
  val capability : t -> string
  val role : t -> string
  val scope : t -> scope
  val compartment : t -> string
  val required : t -> bool
end

module Capability : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> role:string -> scope:scope -> compartment:string -> t
  val id : t -> string
  val role : t -> string
  val scope : t -> scope
  val compartment : t -> string
end

module Resource : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> resource:string -> amount:Runtime_number.t option -> unit:string -> dtype:Type_spec.t -> reusable:bool -> role:string -> scope:scope -> compartment:string -> t
  val id : t -> string
  val resource : t -> string
  val amount : t -> Runtime_number.t option
  val unit : t -> string
  val dtype : t -> Type_spec.t
  val reusable : t -> bool
  val role : t -> string
  val scope : t -> scope
  val compartment : t -> string
end

module Sequence_reference : sig
  type artifact_class = Coding_dna | Coding_rna | Protein
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : artifact_class:artifact_class -> sequence_length:Z.t -> unknown_features:string list -> t
  val artifact_class : t -> artifact_class
  val sequence_length : t -> Z.t
  val unknown_features : t -> string list
  val completeness : t -> string
end

type classification = Synthetic_model | Sequence_reference | Modeled_component
type t
val schema_version : string
val of_json : ?path:string -> Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val make : id:string -> version:string -> classification:classification -> implementation_role:string -> supported_targets:string list ->
  ports:Component_contract.Port.t list -> supported_domain:Component_contract.Operating_domain.t -> identities:Pinned_identity.t list ->
  assumptions:string list -> guarantees:string list -> evidence:Pinned_identity.t list -> parameters:Parameter.t list ->
  dependencies:Dependency.t list -> capabilities:Capability.t list -> resources:Resource.t list ->
  reference_metadata:Sequence_reference.t option -> synthetic_model:Synthetic_operator.t option -> t
val id : t -> string
val version : t -> string
val classification : t -> classification
val implementation_role : t -> string
val supported_targets : t -> string list
val ports : t -> Component_contract.Port.t list
val port : t -> string -> Component_contract.Port.t option
val supported_domain : t -> Component_contract.Operating_domain.t
val identities : t -> Pinned_identity.t list
val assumptions : t -> string list
val guarantees : t -> string list
val evidence : t -> Pinned_identity.t list
val parameters : t -> Parameter.t list
val dependencies : t -> Dependency.t list
val capabilities : t -> Capability.t list
val resources : t -> Resource.t list
val reference_metadata : t -> Sequence_reference.t option
val synthetic_model : t -> Synthetic_operator.t option
