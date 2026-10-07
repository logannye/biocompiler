(** Count-only generation instrumentation. No owner, mutable global callback,
    new validation limit or producer dependency is introduced. Each instance
    belongs to one enclosing invocation. Opaque codec passes are preceded by
    complete data/byte preflights; caller-owned repeated searches are charged
    separately through the collection and comparison wrappers. *)
val no_charge : int -> unit
module Make (_ : sig val charge : int -> unit end) : sig
  val preflight : Bioc_wire.Json.t -> unit
  val serialization : Bioc_wire.Json.t -> unit
  val append_string : string -> string -> string
  module List : module type of Stdlib.List
  module String : module type of Stdlib.String
  module Json : module type of struct include Bioc_wire.Json end
  module Canonical : module type of struct include Bioc_wire.Canonical end
  module Document : module type of struct include Bioc_domain.Policy_document end
  module Operational : module type of struct include Bioc_domain.Policy_operational end
  module Names : Map.S with type key = string
  module Seen : Set.S with type elt = string
end
