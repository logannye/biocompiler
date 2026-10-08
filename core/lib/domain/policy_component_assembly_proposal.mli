(** Untrusted ordered component-to-actual-node correspondence. This record
    supplies no component, source, material or execution authority. *)
open Bioc_wire
module A = Policy_component_assembly_rule
val schema_version : string
val profile : string
type node_binding = private { slot:A.slot; node_id:string; actual_id:string }
type t
val of_json : Json.t -> t
val to_json : t -> Json.t
val fingerprint : t -> string
val rule : t -> Pinned_identity.t
val nodes : t -> node_binding list
