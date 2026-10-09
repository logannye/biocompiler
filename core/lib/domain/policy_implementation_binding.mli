(** Bounded untrusted source/graph anchors. These names propose locations only;
    they carry no correspondence, execution, material or export authority. *)
open Bioc_wire

val schema_version : string
val profile : string
val staged_schema_version : string
val staged_profile : string
val two_observation_schema_version : string
val two_observation_profile : string
val multi_product_schema_version : string
val multi_product_profile : string
val finite_machine_schema_version : string
val finite_machine_profile : string
type observation = { source : string; bank : string; input : string }
type state = { source : string; register : string }
type effect_binding = { source : string; bank : string; feedback : string }
type rule = { source : string; gate : string; arbiter : string; lane : int; commit : string }
type machine = { source : string; bank : string }
type transition = rule
type t
val of_json : Json.t -> t
val to_json : t -> Json.t
val fingerprint : t -> string
val catalog_entry : t -> string
val observations : t -> observation list
val states : t -> state list
val effects : t -> effect_binding list
val rules : t -> rule list
val machines : t -> machine list
val transitions : t -> transition list
val is_staged : t -> bool
val is_two_observation : t -> bool

val is_multi_product : t -> bool

val is_finite_machine : t -> bool
