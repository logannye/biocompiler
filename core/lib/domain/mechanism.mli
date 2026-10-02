(** Checked single-role digital mechanism declarations. These synthetic models
    do not establish molecular behavior or biological applicability. *)
type literal = Boolean of bool | Scalar of Measurement_contract.Scalar.t
type comparison = Lt | Le | Gt | Ge | Eq | Ne
type operation =
  | Input | Constant of literal | And | Or | Not | Compare of comparison | Select
  | Delay of { duration : Measurement_contract.Scalar.t; initial : literal }
  | Held_for of Measurement_contract.Scalar.t | Onset
  | Pulse of Measurement_contract.Scalar.t | Memory of Measurement_contract.Scalar.t option
  | Output | Any_contact

val schema_version : string
val resource_profile : string
val supported_kinds : string list
val literal_to_json : literal -> Bioc_wire.Json.t
val operation_kind : operation -> string

module Node : sig
  type t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val make : id:string -> operation:operation -> output:Measurement_contract.Observable.t ->
    ?inputs:string list -> ?requirement_ids:string list -> unit -> t
  val to_json : t -> Bioc_wire.Json.t
  val id : t -> string
  val kind : t -> string
  val operation : t -> operation
  val output : t -> Measurement_contract.Observable.t
  val inputs : t -> string list
  val requirement_ids : t -> string list
  val dtype : t -> Type_spec.t
  val role : t -> string
  val scope : t -> Measurement_contract.Observable.scope
  val compartment : t -> string
end

type t
val of_json : ?path:string -> Bioc_wire.Json.t -> t
val make : name:string -> nodes:Node.t list -> outputs:string list ->
  ?required_capabilities:string list -> unit -> t
val to_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val canonical_size : t -> int
val name : t -> string
val nodes : t -> Node.t list
(* Sorted ready layers, distinct from supplied declaration order. *)
val topological_nodes : t -> Node.t list
val outputs : t -> string list
val required_capabilities : t -> string list
val role : t -> string
val get : t -> string -> Node.t option
