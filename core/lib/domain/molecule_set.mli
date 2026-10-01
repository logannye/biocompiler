(** Complete supplied molecule inventories, experimental quantities and archival
    metadata. Importing these declarations grants no construction acceptance. *)
type t
val schema_version : string
val of_json : ?path:string -> Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val make : id:string -> request:Circuit_request.t -> molecules:Molecule.t list -> complexes:Molecule.Complex.t list -> role_instances:Molecule.Role.t list -> form_mappings:Molecule.Form_mapping.t list -> t
val id : t -> string
val request : t -> Circuit_request.t
val molecules : t -> Molecule.t list
val complexes : t -> Molecule.Complex.t list
val role_instances : t -> Molecule.Role.t list
val form_mappings : t -> Molecule.Form_mapping.t list
val subject_nominal_identity : t -> string -> string
val subject_complete : t -> string -> bool
val declared_nominal_complete : t -> bool
val declared_nominal_bundle_identity : t -> string

module Amount : sig
  type quantity = Unknown | Integer of Z.t | Real of float
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> subject_id:string -> subject_fingerprint:string -> preparation_id:string -> role_instance_ids:string list -> quantity:quantity -> unit:string -> provenance:Molecular_record.Provenance.t -> t
  val id : t -> string
  val subject_id : t -> string
  val subject_fingerprint : t -> string
  val preparation_id : t -> string
  val role_instance_ids : t -> string list
  val quantity : t -> quantity
  val unit : t -> string
  val provenance : t -> Molecular_record.Provenance.t
end

module Artifact : sig
  type bundle = t
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : bundle:bundle -> experimental_amounts:Amount.t list -> run_metadata:(string * Bioc_wire.Json.t) list -> t
  val bundle : t -> bundle
  val experimental_amounts : t -> Amount.t list
  val run_metadata : t -> (string * Bioc_wire.Json.t) list
  val nominal_bundle_identity : t -> string
  val experimental_specification_identity : t -> string
  val artifact_fingerprint : t -> string
end
