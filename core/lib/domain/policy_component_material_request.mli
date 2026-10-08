(** Closed original authority for one bounded component/one-member composition.
    The entire realization request remains untouched. Static catalog, provider
    and reference closure is not source admission or compilation acceptance. *)
open Bioc_wire
module R = Policy_realization_request
module L = Policy_component_library
module A = Policy_component_assembly_rule
module X = Policy_component_context
module C = Policy_material_contract
val schema_version : string
val profile : string
val instance_schema_version : string
val instance_profile : string
val prerequisite_schema_version : string
val prerequisite_profile : string
val two_observation_schema_version : string
val two_observation_profile : string
val resource_profile : string
type component_binding = private { slot:A.slot; component:Pinned_identity.t }
type catalog_binding = private {
  entry_id:string; entry_version:string; entry_digest:string;
  operation:C.provider_ref; realization:C.provider_ref;
  components:component_binding list; rule:Pinned_identity.t;
}
type input_binding = private {
  input_id:string; source:string; provider:C.provider_ref; channel:string;
}
type resource_owner = Node of {slot:A.slot; node_id:string} | Input of string | Layout
type resource_key = {owner:resource_owner; unit:C.resource_unit; scope:C.resource_scope}
type resource_binding = private {key:resource_key; provider:C.provider_ref; capacity_id:string}

(** Capacity keys retain decision then driver prerequisite order for the legacy
    profile, or declared named-instance order for the versioned instance profile,
    followed by layout generation counters, executor timer and executor control-event queue.
    Their quantities still require independent original-domain derivation. *)
val resource_keys : A.t -> resource_key list
val resource_owner_to_json : resource_owner -> Json.t
type budgets = private {max_work:int; max_report_bytes:int; max_report_nodes:int}
type t
val of_json : ?charge:(int -> unit) -> Json.t -> t
val is_instanced : t -> bool
val requires_prerequisite_closure : t -> bool
val is_two_observation : t -> bool
val request_profile : t -> string
val to_json : t -> Json.t
val fingerprint : t -> string
val decoding_work : t -> int
val implementation_request : t -> R.t
val component_library : t -> L.t
val composition_rule : t -> A.t
val catalog_binding : t -> catalog_binding
val input_bindings : t -> input_binding list
val resource_bindings : t -> resource_binding list
val context : t -> X.t
val budgets : t -> budgets
