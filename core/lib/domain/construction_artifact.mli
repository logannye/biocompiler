(** Unchecked candidate values. Parsing never supplies independent expected
    authority or grants construction acceptance. *)
module Derived_segment : sig
  type rule = Copy | Complement | Transcription | Rna_editing | Translation_codon
  val rule_name : rule -> string
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : destination:Molecule_coordinates.Span.t -> source_id:string -> source_path:Molecule_coordinates.Path.t -> rule:rule -> t
  val destination : t -> Molecule_coordinates.Span.t
  val source_id : t -> string
  val source_path : t -> Molecule_coordinates.Path.t
  val rule : t -> rule
end
module Consumed_segment : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : source_id:string -> source_path:Molecule_coordinates.Path.t -> t
  val source_id : t -> string
  val source_path : t -> Molecule_coordinates.Path.t
end
module Value : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> space:Molecule_coordinates.Space.t -> sequence:string -> chemistry:Molecule_chemistry.t ->
    features:Molecule.Feature.t list -> segments:Derived_segment.t list -> step_id:string ->
    sequence_extent:Molecule_chemistry.sequence_extent -> consumed:Consumed_segment.t list -> t
  val id : t -> string
  val space : t -> Molecule_coordinates.Space.t
  val sequence : t -> string
  val chemistry : t -> Molecule_chemistry.t
  val features : t -> Molecule.Feature.t list
  val segments : t -> Derived_segment.t list
  val step_id : t -> string
  val sequence_extent : t -> Molecule_chemistry.sequence_extent
  val consumed : t -> Consumed_segment.t list
end
type t
val schema_version : string
val of_json : ?path:string -> Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val make : request_fingerprint:string -> values:Value.t list -> bundle:Molecule_set.t option ->
  missing_members:string list -> diagnostics:string list -> experimental_amounts:Molecule_set.Amount.t list -> t
val request_fingerprint : t -> string
val values : t -> Value.t list
val bundle : t -> Molecule_set.t option
val missing_members : t -> string list
val diagnostics : t -> string list
val experimental_amounts : t -> Molecule_set.Amount.t list
