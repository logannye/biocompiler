(** Exact supplied helper material authority. Shape and pin checking do not
    establish translation, capacity, initialization, behavior or export. *)
open Bioc_wire
val schema_version : string
val profile : string
type t
val of_json : Json.t -> t
val to_json : t -> Json.t
val fingerprint : t -> string
val identity : t -> Pinned_identity.t
val root : t -> Construction.Root_source.t
val regions : t -> Policy_mrna_structure.regions
val product : t -> Policy_mrna_structure.product

(** Original root-frame chemistry; final member projection is checked later. *)
val chemistry : t -> Molecule_chemistry.t
val capability : t -> Policy_material_contract.provider_ref
val prerequisites : t -> Policy_material_contract.provider_ref list
