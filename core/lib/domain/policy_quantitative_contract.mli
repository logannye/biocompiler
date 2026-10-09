(** Bounded independently supplied sampled laws. Decoding gives no behavioral,
    component, material or empirical acceptance. All quantities retain complete
    nominal units; this profile performs no unit conversion. *)
open Bioc_wire
val schema_version : string
val profile : string
val step_schema_version : string
val step_profile : string
type quantity = private { raw:Json.t; amount:Q.t; unit:Json.t }
type mechanism = private {
  raw:Json.t; unit:Json.t; substance:string; compartment:string;
  quantum:quantity; capacity:quantity; threshold:quantity; initial:quantity;
  sample_period:quantity; rise:quantity; fall:quantity; multi_site:bool; levels:int;
}
type state_value = private { state:string; quantity:quantity }
type output_site = private { source_state:string; input:bool; boundary:string; model:Pinned_identity.t }
type local_contract = private {
  raw:Json.t; id:string; mechanism:mechanism;
  state_node:string; state_model:Pinned_identity.t; values:state_value list;
  input_node:string; input_model:Pinned_identity.t; value_port:string; updated_port:string;
  output_boundary:string; output_model:Pinned_identity.t; outputs:output_site list;
}
type selection = private {
  raw:Json.t; mechanism:mechanism; instance:string; component:Pinned_identity.t;
  contract:string; machine:string; observation:string; effect_value:string;
}
val of_json : ?charge:(int -> unit) -> Json.t -> mechanism
val local_of_json : ?charge:(int -> unit) -> Json.t -> local_contract
val selection_of_json : ?charge:(int -> unit) -> Json.t -> selection
val to_json : mechanism -> Json.t
val local_to_json : local_contract -> Json.t
val selection_to_json : selection -> Json.t
