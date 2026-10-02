(** Independent declared chemistry and feature correspondence over reconstructed
    inputs. No producer or stored acceptance result supplies expected authority. *)
module Input : sig
  type t
  val of_molecule : Bioc_domain.Molecule.t -> t
  val of_value : Bioc_domain.Construction_artifact.Value.t -> t
  val space : t -> Bioc_domain.Molecule_coordinates.Space.t
  val sequence : t -> string
  val chemistry : t -> Bioc_domain.Molecule_chemistry.t
  val features : t -> Bioc_domain.Molecule.Feature.t list
  val sequence_extent : t -> Bioc_domain.Molecule_chemistry.sequence_extent
end
val resource_profile : string
val default_max_work : int
val max_projected_residues : int
val max_derivation_segments : int
type budget
val make_budget : ?max_work:int -> unit -> budget
type result
val chemistry : result -> Bioc_domain.Molecule_chemistry.t option
val features : result -> Bioc_domain.Molecule.Feature.t list
val diagnostics : result -> string list
val unsupported : result -> string list
val to_json : result -> Bioc_wire.Json.t
val resolve : ?budget:budget -> Bioc_domain.Molecular_transition.Chemistry.t ->
  Bioc_domain.Molecular_transition.Feature.t -> inputs:(string * Input.t) list ->
  output_sequence:string -> output_space:Bioc_domain.Molecule_coordinates.Space.t ->
  derivation:Bioc_domain.Construction_artifact.Derived_segment.t list ->
  sequence_extent:Bioc_domain.Molecule_chemistry.sequence_extent -> result
