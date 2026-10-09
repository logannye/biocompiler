(** Supplied local fragment/material declarations. Decoding establishes bounded
    shape, exact model membership and local consistency only. It does not check
    translation, composition, source preservation, context, resource sufficiency
    or export eligibility. Full root identity is stronger than peptide equality. *)
open Bioc_wire
module F = Policy_component_fragment
module MC = Policy_material_contract
val schema_version : string
val profile : string
val quantitative_schema_version : string
val quantitative_profile : string
val max_carriers : int
val max_provider_requirements : int

type target = Primitive of string | Configuration of string | Replication of string
  | Local_wire of int | External_slot of string | Boundary_port of string
  | Atomic_group of string | Semantic_export of int | Slot_layout
type site = private { root_id:string; feature_id:string; path:Molecule_coordinates.Path.t }
type carrier = private { target:target; sites:site list }
type product = private {
  node_id:string; symbol:string; root_id:string; cds_feature:string;
  expected:Policy_mrna_structure.product;
}
type owner = Node of string | External_slot_owner of string
type provider_requirement = private
  | Input of { id:string; external_slot:string }
  | Capacity of { id:string; owner:owner; unit:MC.resource_unit;
                  scope:MC.resource_scope; minimum:int }
type t

(** Existing molecular pretty-size+newline, node and depth limits precede the
    explicit no-Float walk and all nested decoding. The embedded fragment keeps
    its independent stricter bounds. No receipt or acceptance is returned. *)
val of_json : library:Policy_implementation.library -> Json.t -> t
val to_json : t -> Json.t
val fingerprint : t -> string
val identity : t -> Pinned_identity.t
val model_library_digest : t -> string
val fragment : t -> F.t
val root : t -> Construction.Root_source.t
val carriers : t -> carrier list
val products : t -> product list

(** Concrete providers, global layout demands and larger original-domain
    demands remain external. Input types/replication come from the exact fragment
    slot/model; minima are not proof of memory sufficiency or runtime behavior. *)
val provider_requirements : t -> provider_requirement list
val quantitative_contracts : t -> Policy_quantitative_contract.local_contract list
val target_inventory : F.t -> target list
val target_to_json : target -> Json.t
