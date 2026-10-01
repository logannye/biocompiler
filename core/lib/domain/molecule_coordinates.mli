(** Declared molecular frames and ordered, zero-based, half-open paths.
    Validation establishes coordinate consistency only, never a processing
    mechanism, symbol transformation, or empirical biological behavior. *)
type alphabet = Dna | Rna | Protein
type topology = Linear | Circular
type axis = Five_prime_to_three_prime | N_to_c
type strand = Forward | Reverse

module Space_id : sig
  type t
  val to_string : t -> string
  val equal : t -> t -> bool
end

module Space : sig
  type t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val id : t -> Space_id.t
  val alphabet : t -> alphabet
  val length : t -> int
  val topology : t -> topology
  val axis : t -> axis
end

module Span : sig
  type t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val start : t -> int
  val stop : t -> int
  val length : t -> int
end

module Path : sig
  type t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val space_id : t -> Space_id.t
  val spans : t -> Span.t list
  val strand : t -> strand
  val length : t -> int
  val validate_for : t -> Space.t -> unit
  (** [positions] bounds work before enumerating indices. Reverse traversal
      reverses each span while retaining the supplied span order. *)
  val positions : ?limit:int -> t -> Space.t -> int list
end
