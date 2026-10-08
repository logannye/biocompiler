(** Original composition deployment and capacity declarations. No old material
    kernel or context is synthesized. Shape and pin consistency grant no resource,
    timing, recipient, preservation, material or export acceptance. *)
open Bioc_wire
module X = Policy_material_context
module A = Policy_component_assembly_rule
val schema_version : string
val multi_member_schema_version : string
val multi_member_profile : string
val profile : string
val instance_profile : string
val instance_staged_profile : string
val prerequisite_profile : string
val two_observation_profile : string
val instance_union_profile : string
val staged_profile : string
val staged_record_profile : string
val staged_record_shapes : Json.t
val record_profile : string
val union_profile : string

(** Canonical ordered union of original component records, with structured local
    identities. This is neither a candidate implementation nor source authority. *)
val ordered_union_json : A.t -> Json.t
val ordered_union_digest : A.t -> string
type record_layout = {
  staged:bool; rule:Pinned_identity.t; union_digest:string; domain_digest:string;
  slots:int; generations:int; attempts:int; horizon:int; maximum_tick:int;
  ordered_reasons:int; ordered_causes:int; identifier_bytes:int;
}
val record_layout_of_json : Json.t -> record_layout
val record_layout_to_json : record_layout -> Json.t
val record_layout_fingerprint : record_layout -> string
type t
val of_json : Json.t -> t
val is_instanced : t -> bool
val requires_prerequisite_closure : t -> bool
val is_two_observation : t -> bool
val is_multi_member : t -> bool
val context_profile : t -> string
val to_json : t -> Json.t
val fingerprint : t -> string
val clock : t -> X.clock
val recipient : t -> X.recipient
val record_layout : t -> record_layout

(** Legacy singleton accessor; rejects the multi-member context family. *)
val placement : t -> Architecture_contract.Placement.t
val placements : t -> Architecture_contract.Placement.t list
val delivery_group : t -> X.delivery_group
val providers : t -> X.provider list
