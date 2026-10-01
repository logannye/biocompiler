module type S = sig
  type t
  val of_string : string -> t
  val to_string : t -> string
  val compare : t -> t -> int
end
module Node : S
module Requirement : S
module Role : S
module Observation : S
module Product : S
module Component : S
module Molecule : S
