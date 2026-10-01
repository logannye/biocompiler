(** Bounded molecular declarations. Provenance is supplied authority metadata,
    not independent evidence or biological acceptance. *)
val max_json_bytes : int
val max_items : int
val max_depth : int
val max_residues : int
val max_text_bytes : int
val bounded_length : ?path:string -> maximum:int -> 'a list -> int
val bounded_tree : ?path:string -> Bioc_wire.Json.t -> unit
val check_resources : ?path:string -> Bioc_wire.Json.t -> unit
val pretty_size : ?indent:int option -> Bioc_wire.Json.t -> int
val text : ?path:string -> ?maximum:int -> Bioc_wire.Json.t -> string
val record : ?path:string -> string -> string list -> Bioc_wire.Json.t -> (string * Bioc_wire.Json.t) list
val array : ?path:string -> maximum:int -> Bioc_wire.Json.t -> Bioc_wire.Json.t list
val index : ?path:string -> ?maximum:int -> Bioc_wire.Json.t -> int
val alphabet_symbols : Molecule_coordinates.alphabet -> string
val valid_sequence : Molecule_coordinates.alphabet -> string -> bool

module Provenance : sig
  type status = Declared | Unknown
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : status:status -> authority:Pinned_identity.t list -> locator:string option -> reason:string -> t
  val status : t -> status
  val authority : t -> Pinned_identity.t list
  val locator : t -> string option
  val reason : t -> string
end
