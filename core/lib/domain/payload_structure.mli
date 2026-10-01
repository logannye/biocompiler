(** Supplied required-region authority. Structural decoding establishes neither
    feature geometry, regulatory function, evidence review nor admission. *)
val max_contracts : int
val max_regions : int
val profile : string
val claim : string
type form = Delivered_rna | Delivered_dna
val form_name : form -> string
val alphabet : form -> Molecule_coordinates.alphabet

module Region : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : feature_id:string -> kind:string -> t
  val feature_id : t -> string
  val kind : t -> string
end

type t
val schema_version : string
val of_json : ?path:string -> Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val make : member_id:string -> form:form -> topology:Molecule_coordinates.topology ->
  regions:Region.t list -> provenance:Molecular_record.Provenance.t -> t
val member_id : t -> string
val form : t -> form
val topology : t -> Molecule_coordinates.topology
val regions : t -> Region.t list
val provenance : t -> Molecular_record.Provenance.t
