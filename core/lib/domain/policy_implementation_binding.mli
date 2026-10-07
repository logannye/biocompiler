(** Bounded untrusted source/graph anchors. These names propose locations only;
    they carry no correspondence, execution, material or export authority. *)
open Bioc_wire

val schema_version : string
val profile : string
type observation = { source : string; bank : string; input : string }
type state = { source : string; register : string }
type effect_binding = { source : string; bank : string; feedback : string }
type rule = { source : string; gate : string; arbiter : string; lane : int; commit : string }
type t
val of_json : Json.t -> t
val to_json : t -> Json.t
val fingerprint : t -> string
val catalog_entry : t -> string
val observations : t -> observation list
val states : t -> state list
val effects : t -> effect_binding list
val rules : t -> rule list
