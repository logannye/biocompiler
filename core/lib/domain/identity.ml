module type S = sig
  type t
  val of_string : string -> t
  val to_string : t -> string
  val compare : t -> t -> int
end

module Make () : S = struct
  type t = string
  let of_string value = Bioc_wire.Json.name (Bioc_wire.Json.String value)
  let to_string value = value
  let compare = String.compare
end

module Node = Make ()
module Requirement = Make ()
module Role = Make ()
module Observation = Make ()
module Product = Make ()
module Component = Make ()
module Molecule = Make ()
