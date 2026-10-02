(** Producer-only declared editing and translation. Results are untrusted
    proposals, including when no diagnostic is returned. *)
val implementation_version : string
type material = Root of Bioc_domain.Molecule.t | Product of Bioc_domain.Construction_artifact.Value.t
val space : material -> Bioc_domain.Molecule_coordinates.Space.t
val sequence : material -> string
val chemistry : material -> Bioc_domain.Molecule_chemistry.t
val features : material -> Bioc_domain.Molecule.Feature.t list
val sequence_extent : material -> Bioc_domain.Molecule_chemistry.sequence_extent
module Available : sig
  type t
  val of_bindings : (string * material) list -> t
  val find : string -> t -> material option
  val add_products : Bioc_domain.Construction_artifact.Value.t list -> t -> t
end
type budget
val max_work : int
val make_budget : ?parent:Bioc_checker.Work_budget.t -> ?maximum:int -> unit -> budget
(* Internal producer composition: preserve budget exhaustion across legacy
   domain-error recovery and restore its public Diagnostic.Error at entrypoints. *)
val protect : (unit -> 'a) -> 'a
val charge : budget -> int -> unit
val reserve_json : budget -> Bioc_wire.Json.t -> unit
val reserve_output : budget -> Bioc_wire.Json.t -> unit
val reserve_staged : budget -> Bioc_wire.Json.t -> unit
type result = {
  values : Bioc_domain.Construction_artifact.Value.t list;
  used_residues : int;
  diagnostic : string option;
}
val construct_step : ?budget:budget -> step:Bioc_domain.Construction.Transform_step.t ->
  available:Available.t -> remaining_residues:int -> unit -> result
