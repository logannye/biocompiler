(** Bounded external source/domain/model authority. Decoding is not source
    admission, implementation preservation, requirement satisfaction, material
    realization or export permission. No implementation candidate is embedded. *)
open Bioc_wire

val schema_version : string
val profile : string
val prerequisite_schema_version : string
val prerequisite_profile : string
val two_observation_schema_version : string
val two_observation_profile : string
val multi_product_schema_version : string
val multi_product_profile : string
val finite_machine_schema_version : string
val finite_machine_profile : string
val multi_site_schema_version : string
val multi_site_profile : string
val network_schema_version : string
val network_profile : string
val resource_profile : string

type budgets = private {
  max_prefixes : int;
  max_transitions : int;
  max_work : int;
  max_trace_items : int;
}
type catalog_binding = private {
  entry_id : string;
  entry_version : string;
  entry_digest : string;
  operation : Json.t;
  realization : Json.t;
  models : Pinned_identity.t list;
}
type t
val of_multi_site_json : Json.t -> t
val is_multi_site : t -> bool

val of_json : Json.t -> t

(** Separate opt-in constructor for a component-material caller that must close
    every original catalog prerequisite before accepted material or export.
    The legacy [of_json] deliberately rejects this new input profile. *)
val of_prerequisite_json : Json.t -> t
val of_two_observation_json : Json.t -> t
val of_multi_product_json : Json.t -> t
val of_finite_machine_json : Json.t -> t
val of_network_json : Json.t -> t
val requires_prerequisite_closure : t -> bool
val is_two_observation : t -> bool
val is_multi_product : t -> bool
val is_finite_machine : t -> bool
val is_network : t -> bool
val request_profile : t -> string
val to_json : t -> Json.t

(** Exact full-envelope identity, including source maps, bindings and budgets. *)
val fingerprint : t -> string
val document : t -> Policy_document.t
val definitions : t -> Policy_operational.descriptor_bundle
val operating_domain : t -> Policy_operating_domain.t
val implementation_library : t -> Policy_implementation.library
val catalog_bindings : t -> catalog_binding list
val catalog_bindings_digest : t -> string
val budgets : t -> budgets
