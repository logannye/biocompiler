(** Complete immutable joined authority. Limits are an exact original projection,
    never a second source of policy or an override. Decoding grants no capability. *)
open Bioc_wire
module Behavior = Policy_controlled_behavior_request
module Original = Policy_controlled_composition_request
type t
val schema_version : string
val limits_schema : string
val profile : string
val resource_profile : string
val project_limits : Behavior.t -> Json.t
val of_json : ?charge:(int -> unit) -> Json.t -> t
val raw : t -> Json.t
val to_json : t -> Json.t
val behavior : t -> Behavior.t
val original : t -> Original.t
val limits : t -> Json.t
val budgets : t -> Original.budgets
val fingerprint : t -> string
val decoding_work : t -> int
