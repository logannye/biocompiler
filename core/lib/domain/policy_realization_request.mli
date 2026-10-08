(** Bounded external source/domain/model authority. Decoding is not source
    admission, implementation preservation, requirement satisfaction, material
    realization or export permission. No implementation candidate is embedded. *)
open Bioc_wire

val schema_version : string
val profile : string
val prerequisite_schema_version : string
val prerequisite_profile : string
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

val of_json : Json.t -> t

(** Separate opt-in constructor for a component-material caller that must close
    every original catalog prerequisite before accepted material or export.
    The legacy [of_json] deliberately rejects this new input profile. *)
val of_prerequisite_json : Json.t -> t
val requires_prerequisite_closure : t -> bool
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
