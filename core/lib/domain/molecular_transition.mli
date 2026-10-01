(** Complete declared chemistry and annotation fate. Import does not prove a
    transition, geometry correspondence or biochemical effect. *)
val max_dispositions : int
val max_component_destinations : int
val max_feature_outputs : int
module Component : sig
  type t = private Cap | Start_end | Finish_end | Terminal_tail | Modification_inventory | Modification of string
  val of_string : ?path:string -> string -> t
  val to_string : t -> string
end
module Chemistry_disposition : sig
  type decision = Mapped_copy | Declared_replacement | Not_carried | Unknown
  type t
  val schema_version : string
  val decision_name : decision -> string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : source_id:string -> component:Component.t -> decision:decision -> destination_components:Component.t list -> provenance:Molecular_record.Provenance.t -> t
  val source_id : t -> string
  val component : t -> Component.t
  val decision : t -> decision
  val destination_components : t -> Component.t list
  val provenance : t -> Molecular_record.Provenance.t
end
module Chemistry : sig
  type mode = Exact_inheritance | Explicit_output
  type t
  val schema_version : string
  val mode_name : mode -> string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : mode:mode -> output:Molecule_chemistry.t option -> dispositions:Chemistry_disposition.t list -> provenance:Molecular_record.Provenance.t -> t
  val mode : t -> mode
  val output : t -> Molecule_chemistry.t option
  val dispositions : t -> Chemistry_disposition.t list
  val provenance : t -> Molecular_record.Provenance.t
end
module Feature_disposition : sig
  type decision = Exact | Partial | Split | Not_carried | Outside_selection | Unknown
  type t
  val schema_version : string
  val decision_name : decision -> string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : source_id:string -> feature_id:string -> decision:decision -> outputs:Molecule.Feature.t list -> provenance:Molecular_record.Provenance.t -> t
  val source_id : t -> string
  val feature_id : t -> string
  val decision : t -> decision
  val outputs : t -> Molecule.Feature.t list
  val provenance : t -> Molecular_record.Provenance.t
end
module Feature : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : dispositions:Feature_disposition.t list -> added:Molecule.Feature.t list -> provenance:Molecular_record.Provenance.t -> t
  val dispositions : t -> Feature_disposition.t list
  val added : t -> Molecule.Feature.t list
  val provenance : t -> Molecular_record.Provenance.t
end
