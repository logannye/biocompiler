(** Original versioned component composition declarations. Decoding checks bounded
    shape, exact component membership, signal/order consistency and the supplied
    construction premise. It grants no source preservation, execution, material
    reconstruction, translation, context or export acceptance. No candidate
    renaming or source-bearing implementation authority is constructed here. *)
open Bioc_wire
module I = Policy_implementation
module C = Policy_component_material
module L = Policy_component_library
val schema_version : string
val profile : string
val staged_profile : string
val instance_schema_version : string
val instance_profile : string
val multi_member_schema_version : string
val multi_member_profile : string
val max_instances : int
val transport_profile : string

type slot = Decision | Driver | Instance of string
type component_selection = private { slot:slot; identity:Pinned_identity.t }
type node_ref = private { slot:slot; node_id:string }
type endpoint_ref = private { node:node_ref; port_id:string }
type boundary_ref = private { slot:slot; boundary_id:string }
type link_kind = Product | Request | Authorization
  | Stage_product of int | Stage_request of int | Stage_authorization of int
  | Stage_event of int * I.event_kind
  | Named_link of string
type scope_relation = Same_encounter_slot | Immutable_executor_broadcast
type link = private {
  kind:link_kind; producer:boundary_ref; consumer:boundary_ref;
  signal_type:I.signal_type; scope:scope_relation;
}
type wire_ref = Local_wire of {slot:slot; index:int} | Cross_link of link_kind
type input_ref = private { slot:slot; external_slot:string; input_id:string }
type group_ref = private { slot:slot; group_id:string }
type root_binding = private { slot:slot; source_id:string }
type member_binding = private { slot:slot; source_id:string; member_id:string }
type transport = private {
  definition:Policy_material_contract.provider_ref; provider:Pinned_identity.t;
  producer_member:string; consumer_member:string;
}
type join = private {
  join_id:string; step_id:string; port_id:string; left:slot; right:slot; offset:int;
}
type link_carrier = private {
  kind:link_kind; producer_site:int; consumer_site:int; join_id:string; join_path:string list; transport:transport option;
}
type t

(** Molecular resource preflight and no-float checks precede nested decoding.
    Complete typed roundtrip equality preserves supplied order and rejects leaf
    normalization. Inputs are original component records, never a proposal. *)
val of_json : components:L.t -> Json.t -> t
val to_json : t -> Json.t
val fingerprint : t -> string
val identity : t -> Pinned_identity.t
val component_library_digest : t -> string
val model_library_digest : t -> string
val components : t -> component_selection list
val slots : t -> slot list
val slot_name : slot -> string
val slot_of_json : ?instanced:bool -> Json.t -> slot
val assembly_profile : t -> string
val component : t -> slot -> C.t
val layout : t -> Policy_component_fragment.slot_layout
val links : t -> link list
val node_order : t -> node_ref list
val wire_order : t -> wire_ref list
val input_order : t -> input_ref list
val group_order : t -> group_ref list
val export_order : t -> endpoint_ref list
val root_bindings : t -> root_binding list
val join : t -> join
val joins : t -> join list
val offset : t -> slot -> int
val projected_feature_id : t -> slot -> string -> string
val link_carriers : t -> link_carrier list
val carrier_joins : link_carrier -> string list
val material_authority : t -> Policy_mrna_structure.t

val is_staged : t -> bool
val is_instanced : t -> bool
val link_name : link_kind -> string

(** Separately versioned direct-root, two-member material ownership and explicit
    noncovalent transport references. These references do not establish the
    provider contract, recipient or availability; the context checker does. *)
val is_multi_member : t -> bool
val member_bindings : t -> member_binding list
val member_for_slot : t -> slot -> member_binding
val carrier_transport : link_carrier -> transport option
val transport_to_json : transport -> Json.t
