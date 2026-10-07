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
  val of_bindings : ?charge:(int -> unit) -> (string * material) list -> t
  val find : ?charge:(int -> unit) -> string -> t -> material option
  val add_products : ?charge:(int -> unit) -> Bioc_domain.Construction_artifact.Value.t list -> t -> t
end
type budget
val max_work : int
val make_budget : ?parent:Bioc_checker.Work_budget.t -> ?charge:(int -> unit) -> ?maximum:int -> unit -> budget
(* Internal producer composition: preserve budget exhaustion across legacy
   domain-error recovery and restore its public Diagnostic.Error at entrypoints. *)
val protect : (unit -> 'a) -> 'a
val charge : budget -> int -> unit

(** Extra traversals debit only the supplied outer callback. *)
val outer_charge : budget -> int -> unit
val outer_meter : budget -> int -> unit
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

module Serialization : sig
  val template : (int -> unit) -> Bioc_domain.Payload_template.t -> unit
  val step : (int -> unit) -> Bioc_domain.Construction.Transform_step.t -> unit
  val path : (int -> unit) -> Bioc_domain.Molecule_coordinates.Path.t -> unit
  val chemistry : (int -> unit) -> Bioc_domain.Molecule_chemistry.t -> unit
  val feature : (int -> unit) -> Bioc_domain.Molecule.Feature.t -> unit
  val value : (int -> unit) -> Bioc_domain.Construction_artifact.Value.t -> unit
  val molecule : (int -> unit) -> Bioc_domain.Molecule.t -> unit
  val complex : (int -> unit) -> Bioc_domain.Molecule.Complex.t -> unit
  val role : (int -> unit) -> Bioc_domain.Molecule.Role.t -> unit
  val mapping : (int -> unit) -> Bioc_domain.Molecule.Form_mapping.t -> unit
  val amount : (int -> unit) -> Bioc_domain.Molecule_set.Amount.t -> unit
end
val value_json : budget -> Bioc_domain.Construction_artifact.Value.t -> Bioc_wire.Json.t
val molecule_json : budget -> Bioc_domain.Molecule.t -> Bioc_wire.Json.t
val chemistry_json : budget -> Bioc_domain.Molecule_chemistry.t -> Bioc_wire.Json.t
val feature_json : budget -> Bioc_domain.Molecule.Feature.t -> Bioc_wire.Json.t
val complex_json : budget -> Bioc_domain.Molecule.Complex.t -> Bioc_wire.Json.t
val amount_json : budget -> Bioc_domain.Molecule_set.Amount.t -> Bioc_wire.Json.t

val step_json : budget -> Bioc_domain.Construction.Transform_step.t -> Bioc_wire.Json.t
val port_json : budget -> Bioc_domain.Construction.Product_port.t -> Bioc_wire.Json.t
