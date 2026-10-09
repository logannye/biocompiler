(** Closed bounded approximation and finite quantum-aligned uncertainty originals.
    Decoding never establishes an error bound, material acceptance or empirical fact. *)
open Bioc_wire
module Network = Policy_quantitative_network_contract
val schema_version : string
val profile : string
type rational = private {raw:Json.t;value:Q.t;unit:Json.t}
type endpoint = private {raw:Json.t;mechanism:Network.mechanism;observation:string list}
type parameter = Initial | Transfer_amount
type interval = private {parameter:parameter;id:string;lower:int;upper:int}
type link = private {
  raw:Json.t;id:string;source:endpoint;target:endpoint;
  uncertainty:interval list;maximum_error:rational;
}
type t = private {
  raw:Json.t;horizon_steps:int;coordinates:string list;unit:Json.t;
  maximum_error:rational;links:link list;
}
val of_json : ?charge:(int -> unit) -> Json.t -> t
val to_json : t -> Json.t
val parameter_name : parameter -> string
val rational_to_json : unit:Json.t -> Q.t -> Json.t

(** Complete deterministic Cartesian enumeration; intervals are not sampled.
    Every generated mechanism is decoded independently against the exact law. *)
val cases : ?charge:(int -> unit) -> link -> Network.mechanism list
