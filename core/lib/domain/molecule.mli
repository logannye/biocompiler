(** Exact supplied covalent molecules and separately declared associations.
    These domains establish structural consistency, never transformation,
    empirical function or human-use acceptance. *)
type form = Deposited_template_record | Dna_expression_template | Delivered_dna
  | Primary_rna | Delivered_rna | Processed_rna | Edited_rna
  | Protein_precursor | Mature_protein
type coding_status = Coding | Noncoding | Unknown | Inapplicable
val form_name : form -> string
val coding_status_name : coding_status -> string
val max_molecules : int
val max_features : int
val max_origins : int
val max_roles : int
val max_mappings : int

module Assembly_origin : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> destination:Molecule_coordinates.Path.t -> source_space:Molecule_coordinates.Space.t -> source_path:Molecule_coordinates.Path.t -> provenance:Molecular_record.Provenance.t -> t
  val id : t -> string
  val destination : t -> Molecule_coordinates.Path.t
  val source_space : t -> Molecule_coordinates.Space.t
  val source_path : t -> Molecule_coordinates.Path.t
  val provenance : t -> Molecular_record.Provenance.t
end

module Feature : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : ?reading_frame:int -> id:string -> kind:string -> path:Molecule_coordinates.Path.t option -> provenance:Molecular_record.Provenance.t -> unit -> t
  val id : t -> string
  val kind : t -> string
  val path : t -> Molecule_coordinates.Path.t option
  val reading_frame : t -> int option
  val provenance : t -> Molecular_record.Provenance.t
end

type t
val schema_version : string
val of_json : ?path:string -> Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val make : id:string -> form:form -> space:Molecule_coordinates.Space.t -> sequence:string -> sequence_extent:Molecule_chemistry.sequence_extent -> coding_status:coding_status -> assembly:Assembly_origin.t list -> features:Feature.t list -> chemistry:Molecule_chemistry.t -> provenance:Molecular_record.Provenance.t -> t
val id : t -> string
val form : t -> form
val space : t -> Molecule_coordinates.Space.t
val sequence : t -> string
val sequence_extent : t -> Molecule_chemistry.sequence_extent
val coding_status : t -> coding_status
val assembly : t -> Assembly_origin.t list
val features : t -> Feature.t list
val chemistry : t -> Molecule_chemistry.t
val provenance : t -> Molecular_record.Provenance.t
val spelling_identity : t -> string
val nominal_json : t -> Bioc_wire.Json.t
val declared_nominal_identity : t -> string
val declared_nominal_complete : t -> bool
val complete_nominal_identity : t -> string option
val base_rotation_identity : t -> string option

module Constituent : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : molecule_id:string -> molecule_fingerprint:string -> stoichiometry:int option -> provenance:Molecular_record.Provenance.t -> t
  val molecule_id : t -> string
  val molecule_fingerprint : t -> string
  val stoichiometry : t -> int option
  val provenance : t -> Molecular_record.Provenance.t
end

module Complex : sig
  type kind = Protein_complex | Dna_duplex | Rna_complex
  type t
  val schema_version : string
  val kind_name : kind -> string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> kind:kind -> constituents:Constituent.t list -> provenance:Molecular_record.Provenance.t -> t
  val id : t -> string
  val kind : t -> kind
  val constituents : t -> Constituent.t list
  val provenance : t -> Molecular_record.Provenance.t
end

module Role : sig
  type purpose = Requested_payload | Helper | Host_provider | Assay_control | External_input
  type t
  val schema_version : string
  val purpose_name : purpose -> string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> subject_id:string -> subject_fingerprint:string -> role:string -> purpose:purpose -> compartment:string -> t
  val id : t -> string
  val subject_id : t -> string
  val subject_fingerprint : t -> string
  val role : t -> string
  val purpose : t -> purpose
  val compartment : t -> string
end

module Form_mapping : sig
  type relation = Declared_correspondence | Slice | Orientation | Transcription
    | Rna_processing | Base_editing | Translation | Protein_cleavage
    | Protein_splicing | Circularization | Ribosomal_skipping
  type t
  val schema_version : string
  val relation_name : relation -> string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> source_molecule_id:string -> source_molecule_fingerprint:string -> destination_molecule_id:string -> destination_molecule_fingerprint:string -> source_path:Molecule_coordinates.Path.t -> destination_path:Molecule_coordinates.Path.t -> relation:relation -> provenance:Molecular_record.Provenance.t -> t
  val id : t -> string
  val source_molecule_id : t -> string
  val source_molecule_fingerprint : t -> string
  val destination_molecule_id : t -> string
  val destination_molecule_fingerprint : t -> string
  val source_path : t -> Molecule_coordinates.Path.t
  val destination_path : t -> Molecule_coordinates.Path.t
  val relation : t -> relation
  val provenance : t -> Molecular_record.Provenance.t
end
