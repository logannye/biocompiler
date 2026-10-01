(** Finite numeric operations for the existing Python reference-execution model.
    This shared numeric trusted base contains no scheduler or evaluation logic. *)
type t = Behavior.number = Integer of Z.t | Real of float

val zero : t
val of_int : int -> t
val check_finite : ?path:string -> t -> t
val of_behavior : t -> t
val of_json : ?path:string -> Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val to_float : t -> float
val add : t -> t -> t
val sub : t -> t -> t
val mul : t -> t -> t
val div : t -> t -> t
val neg : t -> t
val compare : t -> t -> int
val equal : t -> t -> bool
val min : t -> t -> t
val max : t -> t -> t
(* Accurate binary64 summation after Python-compatible operand conversion.
   Intermediate overflow is rejected even if a later term would cancel it. *)
val fsum : t list -> t
(* Positive duration must produce a finite, strictly later representable time. *)
val advance : t -> t -> t
