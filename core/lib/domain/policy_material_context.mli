(** Original supplied deployment and finite-record capacity authority. Decoding
    is bounded shape checking only; it grants no recipient, timing, resource,
    implementation, material, biological or export acceptance. *)
open Bioc_wire
module C = Policy_material_contract
val schema_version : string
val profile : string
val provider_schema : string
val transport_provider_schema : string
val helper_provider_schema : string
val helper_capacity_profile : string
val helper_bootstrap_profile : string
val transport_profile : string
val transport_phase_profile : string
val record_profile : string
val delivery_group_schema : string

type time = private { spelling:string; seconds:Q.t }
type interval = { earliest:time; latest:time }
type availability = { onset_min:time; onset_max:time; duration_min:time; duration_max:time }
type recipient = { role:string; identity:string; compartment:string }
type clock = { original_clock:Json.t; period:time; origin:time; deployment_clock:string }
type record_layout = {
  kernel_digest:string; domain_digest:string; slots:int; generations:int;
  attempts:int; horizon:int; maximum_tick:int; ordered_reasons:int;
  ordered_causes:int; identifier_bytes:int;
}
val record_layout_to_json : record_layout -> Json.t
val record_layout_fingerprint : record_layout -> string
type capacity = {
  capacity_id:string; pool_id:string; unit:C.resource_unit; scope:C.resource_scope;
  quantity:int; slots:string list; record_layout_digest:string; available:availability;
}
type channel_kind = Observation | Feedback
type channel = {
  channel_id:string; kind:channel_kind; source:string; observer:string;
  subject:string; available:availability;
}
type helper_bootstrap = { completion:interval; prerequisites:C.provider_ref list }
val helper_bootstrap_to_json : helper_bootstrap -> Json.t
type body = Chassis of Json.t | Environment of Policy_operating_domain.t
  | Interface of { environment:C.provider_ref; channels:channel list }
  | Delivery of { arrival:interval; expression:interval; activation:interval }
  | Transport of { environment:C.provider_ref; original_clock:Json.t }
  | Helper of { material:Pinned_identity.t; environment:C.provider_ref;
                delivery:C.provider_ref; bootstrap:helper_bootstrap }
type provider = private {
  identity:Pinned_identity.t; definition:C.provider_ref; recipient:recipient;
  available:availability; capacities:capacity list; body:body;
}
val provider_body_to_json : provider -> Json.t
val provider_to_json : provider -> Json.t
val availability_to_json : availability -> Json.t
val recipient_to_json : recipient -> Json.t

(* Separate from legacy architecture delivery groups: an empty assumption
   inventory is representable. The context checker rejects nonempty assumptions
   rather than treating them as established premises. *)
type delivery_mode = Co_delivered | Independent
type delivery_group = {
  group_id:string; recipient_roles:string list; mode:delivery_mode;
  same_recipient:bool; assumptions:string list; exact_count:int option;
  max_count:int option; max_total_bases:int option;
}

type t
val of_json : Json.t -> t
val to_json : t -> Json.t
val fingerprint : t -> string
val clock : t -> clock
val recipient : t -> recipient
val record_layout : t -> record_layout
val placement : t -> Architecture_contract.Placement.t
val delivery_group : t -> delivery_group
val helpers : t -> Architecture_contract.Helper.t list
val providers : t -> provider list

(** Bounded syntax leaves shared with independently versioned context records.
    These do not confer original-context, capacity or deployment acceptance. *)
val clock_of_json : Json.t -> clock
val clock_to_json : clock -> Json.t
val recipient_of_json : Json.t -> recipient
val provider_of_json : Json.t -> provider

(** Opt-in provider syntax: legacy v0.1 bodies or the fixed v0.2 transport
    premise. No source authorization, endpoint or availability acceptance. *)
val provider_with_transport_of_json : Json.t -> provider

(** Additional opt-in helper premise; accepts the preceding provider families
    and the fixed v0.3 helper syntax without establishing its causal validity. *)
val provider_with_helper_of_json : Json.t -> provider
val delivery_group_of_json : Json.t -> delivery_group
val delivery_group_to_json : delivery_group -> Json.t
val record_shapes : Json.t
