(** Typed observation declarations and bounded import helpers. These records do
    not execute observations, evaluate a candidate or establish evidence. *)
val preflight : ?path:string -> Bioc_wire.Json.t -> unit
val bounded_list : ?path:string -> 'a list -> 'a list
val record : ?path:string -> string -> string list -> Bioc_wire.Json.t -> (string * Bioc_wire.Json.t) list
val finish : Bioc_wire.Json.t -> Bioc_wire.Json.t
val field : string -> Bioc_wire.Json.t -> Bioc_wire.Json.t
val replace : string -> 'a -> (string * 'a) list -> (string * 'a) list
val type_equal : Type_spec.t -> Type_spec.t -> bool
val duration_type : Type_spec.t
val production_rate_type : Type_spec.t
module Scalar : sig
  type t
  val of_json : ?path:string -> ?expected:Type_spec.t -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val dtype : t -> Type_spec.t
  val canonical : t -> Runtime_number.t
  val duration : ?path:string -> ?positive:bool -> Bioc_wire.Json.t -> t
end
module Interval : sig
  type t
  val of_json : ?path:string -> ?expected:Type_spec.t -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val dtype : t -> Type_spec.t
  val lower : t -> Runtime_number.t
  val upper : t -> Runtime_number.t
  val lower_scalar : t -> Scalar.t
  val upper_scalar : t -> Scalar.t
end
module Observable : sig
  type scope = Cell | Contact
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val id : t -> string
  val dtype : t -> Type_spec.t
  val role : t -> string
  val scope : t -> scope
  val compartment : t -> string
end
module Response : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val observable : t -> Observable.t
  val active : t -> Interval.t
  val inactive : t -> Interval.t
  val activation : t -> Scalar.t
  val deactivation : t -> Scalar.t
  val rule_id : t -> string
  val specification_id : t -> string
end
