(** Original, bounded, closed authority for one conditional expression-material
    objective. Decoding grants neither source admission nor material acceptance. *)
open Bioc_wire
module D = Policy_document
module P = Pinned_identity
module A = Policy_mrna_structure
val schema_version : string
val profile : string
val contract_schema : string
val resource_profile : string
val max_work : int
val parameter_ids : string list

(** Complete normative descriptors; exact body equality is required at admission.
    These constructors contain no biological or localization evidence. *)
val objective_definition : unit -> Json.t
val operation_definition : unit -> Json.t
val translation_definition : unit -> Json.t
type definition_ref = private { id:string; version:string; digest:string }
val definition_ref_of_json : Json.t -> definition_ref
val definition_ref_to_json : definition_ref -> Json.t
val definition_ref : Json.t -> definition_ref

type selection = private {
  objective:string; recipient:string; implementation:P.t; member:string; cds:string;
}
type material = private { structure_sha256:string; member:string; cds:string }
type translation = private {
  terminal_stop_codons:int; model:definition_ref;
}
type expression_contract = private {
  identity:P.t; body:Json.t; operation:definition_ref; realization:definition_ref;
  product:P.t; recipient:Json.t; deployment:Json.t; localization:Json.t;
  material:material; translation:translation;
  dependencies:definition_ref list; evidence:definition_ref list;
}
type budgets = private { max_work:int; max_report_bytes:int; max_report_nodes:int }
type t
val of_json : ?charge:(int -> unit) -> Json.t -> t
val to_json : t -> Json.t
val fingerprint : t -> string
val decoding_work : t -> int
val document : t -> D.t
(** Complete inert original project metadata; no source-byte, publication,
    reuse-rights or empirical qualification is granted by this accessor. *)
val project_context : t -> Json.t
val selection : t -> selection
val expression_contract : t -> expression_contract
val structure_authority : t -> A.t
val structure_fingerprint : t -> string
val budgets : t -> budgets
