(** Immutable historical reference authority. Parsing checks original declaration
    invariants and exact identities; it does not fetch sources or grant empirical
    evidence. Metadata stays complete and bounded. *)
module Codec = Verification_exploration.Codec
val default_limits : Codec.limits
val schema_version : string
val normalization_version : string
type alphabet = DNA | RNA | Protein
val alphabet_name : alphabet -> string
type status = Candidate | Blocked | Accepted
val status_name : status -> string
val normalize_sequence : ?limits:Codec.limits -> string -> alphabet -> string * Bioc_wire.Json.t
val translate_cds : ?limits:Codec.limits -> string -> alphabet -> string
val normalize_sequence_json : ?limits:Codec.limits -> raw_text:Bioc_wire.Json.t -> alphabet:Bioc_wire.Json.t -> unit -> string * Bioc_wire.Json.t
val translate_cds_json : ?limits:Codec.limits -> sequence:Bioc_wire.Json.t -> alphabet:Bioc_wire.Json.t -> unit -> string
module Record : sig
  type t
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val of_json_text : ?limits:Codec.limits -> ?path:string -> string -> t
  val make : ?limits:Codec.limits -> reference_id:string -> variant_id:string -> version:string -> alphabet:alphabet -> artifact_class:string -> orientation:string -> source_id:string -> source_locator:string -> raw_sequence_text:string -> raw_text_sha256:string -> sequence:string -> sequence_sha256:string -> length:int -> normalization:Bioc_wire.Json.t -> linked_reference_ids:string list -> completeness:string -> unknown_features:string list -> evidence_relationships:string list -> unit -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val reference_id : t -> string
  val variant_id : t -> string
  val version : t -> string
  val alphabet : t -> alphabet
  val artifact_class : t -> string
  val orientation : t -> string
  val source_id : t -> string
  val source_locator : t -> string
  val raw_sequence_text : t -> string
  val raw_text_sha256 : t -> string
  val sequence : t -> string
  val sequence_sha256 : t -> string
  val length : t -> int
  val normalization : t -> Bioc_wire.Json.t
  val linked_reference_ids : t -> string list
  val completeness : t -> string
  val unknown_features : t -> string list
  val evidence_relationships : t -> string list
end
module Manifest : sig
  type t
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val of_json_text : ?limits:Codec.limits -> ?path:string -> string -> t
  val make : ?limits:Codec.limits -> reference_set_id:string -> version:string -> sources:Bioc_wire.Json.t list -> records:Record.t list -> translation:Bioc_wire.Json.t -> reviews:Bioc_wire.Json.t list -> status:status -> unresolved_discrepancies:string list -> redistribution:Bioc_wire.Json.t -> unit -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val reference_set_id : t -> string
  val version : t -> string
  val sources : t -> Bioc_wire.Json.t list
  val records : t -> Record.t list
  val translation : t -> Bioc_wire.Json.t
  val reviews : t -> Bioc_wire.Json.t list
  val status : t -> status
  val unresolved_discrepancies : t -> string list
  val redistribution : t -> Bioc_wire.Json.t
  val discrepancies : ?limits:Codec.limits -> t -> string list
  val record : ?require_accepted:bool -> t -> string -> Record.t
end
include module type of Manifest with type t = Manifest.t
