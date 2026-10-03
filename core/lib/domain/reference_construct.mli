(** Historical reference declarations. All parseable unsupported layouts remain
    representable; importing a candidate never establishes acceptance. *)
module Codec = Verification_exploration.Codec
val default_limits : Codec.limits
val bounded_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> unit
type orientation = Forward | Reverse
val orientation_name : orientation -> string
type topology = Linear | Circular | Unspecified
val topology_name : topology -> string
type junction_kind = Direct | Overlap | Gap
val junction_kind_name : junction_kind -> string
type dependency_kind = Same_cell | Co_payload | Regulatory | Resource
val dependency_kind_name : dependency_kind -> string
val source_of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> Behavior.source_location option
val source_to_json : Behavior.source_location option -> Bioc_wire.Json.t
module Sequence_range : sig
  type t
  val schema_version : string
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val of_json_text : ?limits:Codec.limits -> ?path:string -> string -> t
  val make : ?limits:Codec.limits -> start:Z.t -> end_:Z.t -> unit -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val start : t -> Z.t
  val end_ : t -> Z.t
  val length : t -> Z.t
end
module Reference : sig
  type t
  val schema_version : string
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val of_json_text : ?limits:Codec.limits -> ?path:string -> string -> t
  val make : ?limits:Codec.limits -> instance_id:string -> selection:Reference_components.Selection.t -> unit -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val instance_id : t -> string
  val selection : t -> Reference_components.Selection.t
end
module Molecule : sig
  type t
  val schema_version : string
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val of_json_text : ?limits:Codec.limits -> ?path:string -> string -> t
  val make : ?limits:Codec.limits -> id:string -> alphabet:Reference_manifest.alphabet -> artifact_class:string -> length:Z.t -> component_order:string list -> topology:topology -> completeness:string -> unknown_features:string list -> compartment:string -> unit -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val id : t -> string
  val alphabet : t -> Reference_manifest.alphabet
  val artifact_class : t -> string
  val length : t -> Z.t
  val component_order : t -> string list
  val topology : t -> topology
  val completeness : t -> string
  val unknown_features : t -> string list
  val compartment : t -> string
end
module Placement : sig
  type t
  val schema_version : string
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val of_json_text : ?limits:Codec.limits -> ?path:string -> string -> t
  val make : ?limits:Codec.limits -> instance_id:string -> molecule_id:string -> component:Component_registry.Component_lock.t -> reference:Pinned_identity.t -> source_range:Sequence_range.t -> molecule_range:Sequence_range.t -> orientation:orientation -> reading_frame:int option -> requirement_ids:string list -> source:Behavior.source_location option -> unit -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val instance_id : t -> string
  val molecule_id : t -> string
  val component : t -> Component_registry.Component_lock.t
  val reference : t -> Pinned_identity.t
  val source_range : t -> Sequence_range.t
  val molecule_range : t -> Sequence_range.t
  val orientation : t -> orientation
  val reading_frame : t -> int option
  val requirement_ids : t -> string list
  val source : t -> Behavior.source_location option
end
module Feature : sig
  type t
  val schema_version : string
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val of_json_text : ?limits:Codec.limits -> ?path:string -> string -> t
  val make : ?limits:Codec.limits -> id:string -> molecule_id:string -> kind:string -> range:Sequence_range.t -> source_reference:Pinned_identity.t -> source_range:Sequence_range.t -> source_locator:string -> provenance:Pinned_identity.t list -> orientation:orientation -> unit -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val id : t -> string
  val molecule_id : t -> string
  val kind : t -> string
  val range : t -> Sequence_range.t
  val source_reference : t -> Pinned_identity.t
  val source_range : t -> Sequence_range.t
  val source_locator : t -> string
  val provenance : t -> Pinned_identity.t list
  val orientation : t -> orientation
end
module Junction : sig
  type t
  val schema_version : string
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val of_json_text : ?limits:Codec.limits -> ?path:string -> string -> t
  val make : ?limits:Codec.limits -> id:string -> molecule_id:string -> left_instance:string -> right_instance:string -> kind:junction_kind -> range:Sequence_range.t -> choice:string -> provenance:Pinned_identity.t list -> unit -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val id : t -> string
  val molecule_id : t -> string
  val left_instance : t -> string
  val right_instance : t -> string
  val kind : t -> junction_kind
  val range : t -> Sequence_range.t
  val choice : t -> string
  val provenance : t -> Pinned_identity.t list
end
module Regulatory_relationship : sig
  type t
  val schema_version : string
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val of_json_text : ?limits:Codec.limits -> ?path:string -> string -> t
  val make : ?limits:Codec.limits -> id:string -> kind:string -> regulator_instance:string -> target_instance:string -> provenance:Pinned_identity.t list -> assumptions:string list -> unit -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val id : t -> string
  val kind : t -> string
  val regulator_instance : t -> string
  val target_instance : t -> string
  val provenance : t -> Pinned_identity.t list
  val assumptions : t -> string list
end
module Dependency : sig
  type t
  val schema_version : string
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val of_json_text : ?limits:Codec.limits -> ?path:string -> string -> t
  val make : ?limits:Codec.limits -> id:string -> consumer_molecule:string -> provider_molecule:string -> kind:dependency_kind -> assumption:string -> requirement_ids:string list -> unit -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val id : t -> string
  val consumer_molecule : t -> string
  val provider_molecule : t -> string
  val kind : t -> dependency_kind
  val assumption : t -> string
  val requirement_ids : t -> string list
end
module Evidence_policy : sig
  type t
  val schema_version : string
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val of_json_text : ?limits:Codec.limits -> ?path:string -> string -> t
  val make : ?limits:Codec.limits -> semantic_properties:string list -> invalidated_analyses:string list -> unit -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val semantic_properties : t -> string list
  val invalidated_analyses : t -> string list
  val default : ?limits:Codec.limits -> unit -> t
end
module Request : sig
  type t
  val schema_version : string
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val of_json_text : ?limits:Codec.limits -> ?path:string -> string -> t
  val make : ?limits:Codec.limits -> composition:Composition.t -> references:Reference.t list -> molecules:Molecule.t list -> placements:Placement.t list -> features:Feature.t list -> junctions:Junction.t list -> regulatory_relations:Regulatory_relationship.t list -> dependencies:Dependency.t list -> assumptions:string list -> source_request_fingerprint:string option -> evidence_policy:Evidence_policy.t -> unit -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val composition : t -> Composition.t
  val references : t -> Reference.t list
  val molecules : t -> Molecule.t list
  val placements : t -> Placement.t list
  val features : t -> Feature.t list
  val junctions : t -> Junction.t list
  val regulatory_relations : t -> Regulatory_relationship.t list
  val dependencies : t -> Dependency.t list
  val assumptions : t -> string list
  val source_request_fingerprint : t -> string option
  val evidence_policy : t -> Evidence_policy.t
  val layout_json : t -> Bioc_wire.Json.t
  val layout_fingerprint : t -> string
  val target : t -> Build_request.Target.t
  val registry_lock : t -> Component_registry.Lock.t
end
module Candidate : sig
  type t
  val schema_version : string
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val of_json_text : ?limits:Codec.limits -> ?path:string -> string -> t
  val make : ?limits:Codec.limits -> request_fingerprint:string -> composition_fingerprint:string -> registry_lock:Component_registry.Lock.t -> molecules:Molecule.t list -> placements:Placement.t list -> features:Feature.t list -> junctions:Junction.t list -> regulatory_relations:Regulatory_relationship.t list -> dependencies:Dependency.t list -> assumptions:string list -> evidence_policy:Evidence_policy.t -> unit -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val request_fingerprint : t -> string
  val composition_fingerprint : t -> string
  val registry_lock : t -> Component_registry.Lock.t
  val molecules : t -> Molecule.t list
  val placements : t -> Placement.t list
  val features : t -> Feature.t list
  val junctions : t -> Junction.t list
  val regulatory_relations : t -> Regulatory_relationship.t list
  val dependencies : t -> Dependency.t list
  val assumptions : t -> string list
  val evidence_policy : t -> Evidence_policy.t
  val layout_json : t -> Bioc_wire.Json.t
  val layout_fingerprint : t -> string
end
