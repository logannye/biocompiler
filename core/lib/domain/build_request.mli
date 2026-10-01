(** Frozen source authority. Decoding checks structure, target declarations and
    independent parameter resolution. It does not execute source behavior,
    enforce implementation constraints, admit evidence or accept a candidate. *)
type t
type behavior_profile = V1 | V2
type artifact_scope = Abstract_behavior | Synthetic_realization | Exact_cds | Complete_payload
type target_kind = Legacy_target | Human_target
type binding_category = User_selected | Compiler_selected | Measured | Uncertain
type binding_metadata

val schema_version : string
val validation_scope : string
val of_json : Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
(* Semantic serialization omits intent source locations and provenance locations
    and timestamp only. Content identities and captured external inputs remain. *)
val semantic_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val artifact_fingerprint : t -> string
val intent : t -> Intent.t
val behavior_profile : t -> behavior_profile
val artifact_scope : t -> artifact_scope
val target_kind : t -> target_kind option
(* Normalized, structurally checked target declarations; never admission. *)
val target : t -> Bioc_wire.Json.t option
val explicit_overrides : t -> (string * Bioc_wire.Json.t) list
val resolved_defaults : t -> (string * Bioc_wire.Json.t) list
val resolved_bindings : t -> (string * Bioc_wire.Json.t) list
val implementation_constraints : t -> (string * Bioc_wire.Json.t) list
val preferences : t -> (string * Bioc_wire.Json.t) list
val provenance : t -> Bioc_wire.Json.t
val parameter_metadata : t -> (string * binding_metadata) list
val metadata_category : binding_metadata -> binding_category
val metadata_provenance : binding_metadata -> (string * Bioc_wire.Json.t) list
val metadata_allowed_variation : binding_metadata -> Bioc_wire.Json.t option
val runtime_observations : t -> Identity.Node.t list
(* These obligations are not discharged by successful decoding. Downstream
    consumers must account for retained constraints, preferences and assumptions. *)
val unimplemented_obligations : t -> string list
val summary : t -> Bioc_wire.Json.t
