(** Exact nominal chemistry declarations, separate from canonical spelling,
    transformation correctness, provenance completeness and empirical claims. *)
type status = Declared | Unknown | Inapplicable | Absent
type sequence_extent = Complete | Exact_core
val status_name : status -> string
module Chemical_identity : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val nominal_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : namespace:string -> accession:string -> version:string -> t
  val namespace : t -> string
  val accession : t -> string
  val version : t -> string
  val declared_nominal_complete : t -> bool
end
module Claim : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val nominal_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : status:status -> identity:Chemical_identity.t option -> provenance:Molecular_record.Provenance.t -> t
  val status : t -> status
  val identity : t -> Chemical_identity.t option
  val provenance : t -> Molecular_record.Provenance.t
  val declared_nominal_complete : t -> bool
end
module Modification : sig
  type scope = Positions | All_matching_bases
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val nominal_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> identity:Chemical_identity.t -> canonical_base:char -> scope:scope -> positions:int list -> provenance:Molecular_record.Provenance.t -> t
  val id : t -> string
  val identity : t -> Chemical_identity.t
  val canonical_base : t -> char
  val scope : t -> scope
  val positions : t -> int list
  val provenance : t -> Molecular_record.Provenance.t
end
module Tail_length : sig
  type mode = Exact of int | Bounded of int * int | Unknown_length
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val nominal_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : mode -> t
  val mode : t -> mode
end
module Tail : sig
  type placement = Represented_terminal | Appended_terminal | Absent_tail
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val nominal_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : status:status -> placement:placement option -> length:Tail_length.t option -> path:Molecule_coordinates.Path.t option -> provenance:Molecular_record.Provenance.t -> t
  val status : t -> status
  val placement : t -> placement option
  val length : t -> Tail_length.t option
  val path : t -> Molecule_coordinates.Path.t option
  val provenance : t -> Molecular_record.Provenance.t
  val declared_nominal_complete : t -> bool
end
type t
val schema_version : string
val of_json : ?path:string -> Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val nominal_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val make : cap:Claim.t -> start_end:Claim.t -> finish_end:Claim.t -> modifications:Modification.t list -> modification_inventory_status:status -> modification_inventory_provenance:Molecular_record.Provenance.t -> terminal_tail:Tail.t -> t
val cap : t -> Claim.t
val start_end : t -> Claim.t
val finish_end : t -> Claim.t
val modifications : t -> Modification.t list
val modification_inventory_status : t -> status
val modification_inventory_provenance : t -> Molecular_record.Provenance.t
val terminal_tail : t -> Tail.t
val declared_nominal_complete : t -> bool
val validate_for : t -> Molecule_coordinates.Space.t -> sequence:string -> sequence_extent:sequence_extent -> unit
