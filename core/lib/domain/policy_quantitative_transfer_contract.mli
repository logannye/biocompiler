(** Exact bounded reversible transfer between two explicitly named compartments.
    Decoding does not establish source, component, material or empirical claims. *)
open Bioc_wire
val schema_version : string
val profile : string
type quantity = private {raw:Json.t;amount:Q.t;unit:Json.t}
type reservoir = private {compartment:string;capacity:quantity;initial:quantity;levels:int}
type mechanism = private {
  raw:Json.t;substance:string;unit:Json.t;quantum:quantity;
  source:reservoir;destination:reservoir;forward:quantity;reverse:quantity;
  threshold:quantity;sample_period:quantity;levels:int;
}
type state_value = private {state:string;source:quantity;destination:quantity}
type output_site = private {source_state:string;input:bool;boundary:string;model:Pinned_identity.t}
type local_contract = private {
  raw:Json.t;id:string;mechanism:mechanism;
  state_node:string;state_model:Pinned_identity.t;values:state_value list;
  input_node:string;input_model:Pinned_identity.t;value_port:string;updated_port:string;
  outputs:output_site list;
}
type selection = private {
  raw:Json.t;mechanism:mechanism;instance:string;component:Pinned_identity.t;
  contract:string;machine:string;observation:string;effect_value:string;
}
val of_json : ?charge:(int -> unit) -> Json.t -> mechanism
val local_of_json : ?charge:(int -> unit) -> Json.t -> local_contract
val selection_of_json : ?charge:(int -> unit) -> Json.t -> selection
val to_json : mechanism -> Json.t
val local_to_json : local_contract -> Json.t
val selection_to_json : selection -> Json.t
