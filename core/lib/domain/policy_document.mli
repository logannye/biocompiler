(** Closed, bounded data-only policy documents. Representation validity grants
    no execution, semantic-preservation, biological or release acceptance. *)
open Bioc_wire

type kind = Program | Request | Submission

type declaration_kind =
  | Role | Subject | Encounter | Spatial_scope | Clock | Observation
  | State_store | Effect | Rule | Machine | Transition | Channel | Message
  | Requirement | Parameter

type declaration = {
  kind : declaration_kind;
  id : string;
  path : string;
  value : Json.t;
}

type t
val profile : string
val of_json : ?path:string -> Json.t -> t
val to_json : t -> Json.t
val kind : t -> kind
val program : t -> Json.t
val request : t -> Json.t option
val declarations : t -> declaration list
(** The request document identity, or program identity for an unbound program. *)
val fingerprint : t -> string
(** Identity of every field in the submitted artifact, including source maps. *)
val artifact_digest : t -> string
(** Canonical Python-compatible JSON hash, excluding precisely fields named
    [source_map] and [provenance] recursively. This function enforces budgets
    but does not on its own validate a document's record shapes or meaning. *)
val document_digest : Json.t -> string
(** Bounded finite decimal syntax, evaluated exactly without binary64 coercion. *)
val exact_decimal : ?path:string -> string -> Q.t
