(** Frozen construction authority. Typed recipes retain every input, product,
    disposition and assumption; they do not perform a molecular transform. *)
module type Record = sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
end
val profile_version : string
val capability_profile_version : string
val transcription_mapping_profile : string
val max_sources : int
val max_steps : int
val max_selections : int
val max_products : int
val max_processing_products : int
val max_translation_products : int
val max_translation_branches : int
val max_output_members : int
val max_complex_members : int
val max_amount_declarations : int
val max_member_requirements : int
val max_role_declarations : int
val max_assumptions : int
val max_total_source_residues : int
val max_cumulative_produced_residues : int

module Root_source : sig
  include Record
  val make : id:string -> molecule:Molecule.t -> provenance:Molecular_record.Provenance.t -> t
  val id : t -> string
  val molecule : t -> Molecule.t
  val provenance : t -> Molecular_record.Provenance.t
end
module Value_ref : sig
  type kind = Root | Product
  include Record
  val kind_name : kind -> string
  val make : kind:kind -> id:string -> t
  val kind : t -> kind
  val id : t -> string
  val equal : t -> t -> bool
end
module Selection : sig
  include Record
  val make : ?path:Molecule_coordinates.Path.t -> Value_ref.t -> t
  val value : t -> Value_ref.t
  val path : t -> Molecule_coordinates.Path.t option
  val equal : t -> t -> bool
end
module Output_member : sig
  include Record
  val make : id:string -> value:Value_ref.t -> space_id:string -> form:Molecule.form -> sequence_extent:Molecule_chemistry.sequence_extent -> coding_status:Molecule.coding_status -> provenance:Molecular_record.Provenance.t -> t
  val id : t -> string
  val value : t -> Value_ref.t
  val space_id : t -> string
  val form : t -> Molecule.form
  val sequence_extent : t -> Molecule_chemistry.sequence_extent
  val coding_status : t -> Molecule.coding_status
  val provenance : t -> Molecular_record.Provenance.t
end
module Role : sig
  include Record
  val make : id:string -> role:string -> purpose:Molecule.Role.purpose -> compartment:string -> t
  val id : t -> string
  val role : t -> string
  val purpose : t -> Molecule.Role.purpose
  val compartment : t -> string
end
module Member_requirement : sig
  type category = Payload | Delivered_helper | Encoded_product | Host_provider | Experimental_input | Control | Assay_reference
  type subject = Materialized of string | External of {id : string; fingerprint : string}
  include Record
  val category_name : category -> string
  val category_purpose : category -> Molecule.Role.purpose
  val make : id:string -> category:category -> subject:subject -> roles:Role.t list -> t
  val id : t -> string
  val category : t -> category
  val subject : t -> subject
  val member_id : t -> string option
  val roles : t -> Role.t list
end
module Complex_constituent : sig
  include Record
  val make : member_id:string -> stoichiometry:int option -> provenance:Molecular_record.Provenance.t -> t
  val member_id : t -> string
  val stoichiometry : t -> int option
  val provenance : t -> Molecular_record.Provenance.t
end
module Complex_member : sig
  include Record
  val make : id:string -> kind:Molecule.Complex.kind -> constituents:Complex_constituent.t list -> provenance:Molecular_record.Provenance.t -> t
  val id : t -> string
  val kind : t -> Molecule.Complex.kind
  val constituents : t -> Complex_constituent.t list
  val provenance : t -> Molecular_record.Provenance.t
end
module Amount_declaration : sig
  type quantity = Unknown | Integer of Z.t | Real of float
  include Record
  val make : id:string -> subject_id:string -> preparation_id:string -> role_instance_ids:string list -> quantity:quantity -> unit:string -> provenance:Molecular_record.Provenance.t -> t
  val id : t -> string
  val subject_id : t -> string
  val preparation_id : t -> string
  val role_instance_ids : t -> string list
  val quantity : t -> quantity
  val unit : t -> string
  val provenance : t -> Molecular_record.Provenance.t
end
module Product_port : sig
  include Record
  val make : id:string -> space_id:string -> alphabet:Molecule_coordinates.alphabet -> topology:Molecule_coordinates.topology -> chemistry_transition:Molecular_transition.Chemistry.t -> feature_transition:Molecular_transition.Feature.t -> t
  val id : t -> string
  val space_id : t -> string
  val alphabet : t -> Molecule_coordinates.alphabet
  val topology : t -> Molecule_coordinates.topology
  val chemistry_transition : t -> Molecular_transition.Chemistry.t
  val feature_transition : t -> Molecular_transition.Feature.t
end
module Processing_product : sig
  include Record
  val make : port_id:string -> path:Molecule_coordinates.Path.t -> t
  val port_id : t -> string
  val path : t -> Molecule_coordinates.Path.t
end
module Translation_product : sig
  include Record
  val make : port_id:string -> input:Selection.t -> policy:Molecular_recoding.Translation_policy.t -> t
  val port_id : t -> string
  val input : t -> Selection.t
  val policy : t -> Molecular_recoding.Translation_policy.t
end
module Translation_branch : sig
  include Record
  val make : id:string -> condition:string -> input:Selection.t -> policy:Molecular_recoding.Translation_policy.t option -> port_id:string option -> t
  val id : t -> string
  val condition : t -> string
  val input : t -> Selection.t
  val policy : t -> Molecular_recoding.Translation_policy.t option
  val port_id : t -> string option
end
module Peptide_product : sig
  include Record
  val make : port_id:string -> residues:Molecule_coordinates.Span.t -> t
  val port_id : t -> string
  val residues : t -> Molecule_coordinates.Span.t
end
module Operation : sig
  type orientation = Reverse | Reverse_complement
  type specification =
    | Slice of Selection.t
    | Concatenate of Selection.t list
    | Orientation of {input : Selection.t; action : orientation}
    | Transcription of Selection.t
    | Rna_cleavage of {input : Selection.t; products : Processing_product.t list}
    | Rna_splicing of {input : Selection.t; products : Processing_product.t list}
    | Protein_cleavage of {input : Selection.t; products : Processing_product.t list}
    | Protein_splicing of {input : Selection.t; products : Processing_product.t list}
    | Circularization of {input : Selection.t; origin : int}
    | Base_editing of {input : Selection.t; canonical_edits : Molecular_recoding.Canonical_edit.t list; chemical_edits : Molecular_recoding.Chemical_edit.t list}
    | Translation of {input : Selection.t; policy : Molecular_recoding.Translation_policy.t}
    | Multi_orf_translation of Translation_product.t list
    | Conditional_translation of Translation_branch.t list
    | Ribosomal_skipping of {input : Selection.t; policy : Molecular_recoding.Translation_policy.t; products : Peptide_product.t list; event_id : string}
  type t
  val name : t -> string
  val schema_version : t -> string
  val schema_versions : string list
  val make : specification -> t
  val specification : t -> specification
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val selections : t -> Selection.t list
  val conditions : t -> string list
  val product_ids : t -> string list option
  val processing_products : t -> (Selection.t * Processing_product.t list) option
end
val operation_selections : Operation.t -> Selection.t list
module Transform_step : sig
  include Record
  val make : id:string -> operation:Operation.t -> ports:Product_port.t list -> assumptions:string list -> provenance:Molecular_record.Provenance.t -> t
  val id : t -> string
  val operation : t -> Operation.t
  val ports : t -> Product_port.t list
  val assumptions : t -> string list
  val provenance : t -> Molecular_record.Provenance.t
end
module Request : sig
  type mode = Strict | Diagnostic
  include Record
  val mode_name : mode -> string
  val make : ?complex_members:Complex_member.t list -> ?amounts:Amount_declaration.t list -> ?payload_structures:Payload_structure.t list ->
    id:string -> circuit:Circuit_request.t -> sources:Root_source.t list -> steps:Transform_step.t list -> output_members:Output_member.t list ->
    requirements:Member_requirement.t list -> mode:mode -> unit -> t
  val id : t -> string
  val circuit : t -> Circuit_request.t
  val sources : t -> Root_source.t list
  val steps : t -> Transform_step.t list
  val output_members : t -> Output_member.t list
  val requirements : t -> Member_requirement.t list
  val mode : t -> mode
  val complex_members : t -> Complex_member.t list
  val amounts : t -> Amount_declaration.t list
  val payload_structures : t -> Payload_structure.t list
end
