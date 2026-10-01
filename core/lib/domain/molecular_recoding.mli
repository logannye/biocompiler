(** Declared exact edits and codon policies. These leaves neither translate a
    sequence nor bind source positions, biochemical effects or assumptions. *)
val max_recodings : int
val standard_genetic_code : string
val standard_rna_codon_table : (string * char) list
module Canonical_edit : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : position:int -> expected:char -> replacement:char -> t
  val position : t -> int
  val expected : t -> char
  val replacement : t -> char
end
module Chemical_edit : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : position:int -> parent:char -> before:Molecule_chemistry.Chemical_identity.t option -> after:Molecule_chemistry.Chemical_identity.t option -> t
  val position : t -> int
  val parent : t -> char
  val before : t -> Molecule_chemistry.Chemical_identity.t option
  val after : t -> Molecule_chemistry.Chemical_identity.t option
end
module Codon_recoding : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : codon_index:int -> expected_triplet:string -> amino_acid:char -> condition:string -> t
  val codon_index : t -> int
  val expected_triplet : t -> string
  val amino_acid : t -> char
  val condition : t -> string
end
module Translation_policy : sig
  type profile = Ordinary_cds | Conditional_cds
  type t
  val schema_version : string
  val profile_name : profile -> string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : ?genetic_code:string -> ?recodings:Codon_recoding.t list -> profile:profile -> unit -> t
  val profile : t -> profile
  val genetic_code : t -> string
  val recodings : t -> Codon_recoding.t list
end
