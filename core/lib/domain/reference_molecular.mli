(** Historical reference declarations. All parseable unsupported layouts remain
    representable; importing a candidate never establishes acceptance. *)
module Codec = Verification_exploration.Codec
val default_limits : Codec.limits
val bounded_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> unit
type feature_status = Known | Unknown | Inapplicable
val feature_status_name : feature_status -> string
type feature_scope = Cds_record | Delivered_molecule
val feature_scope_name : feature_scope -> string
type profile = Dna_cds | Rna_cds
val profile_name : profile -> string
val canonical_sequence_sha256 : ?limits:Codec.limits -> string -> Reference_manifest.alphabet -> string
module Feature_status : sig
  type t
  val schema_version : string
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val of_json_text : ?limits:Codec.limits -> ?path:string -> string -> t
  val make : ?limits:Codec.limits -> feature:string -> status:feature_status -> scope:feature_scope -> reason:string -> value:string option -> unit -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val feature : t -> string
  val status : t -> feature_status
  val scope : t -> feature_scope
  val reason : t -> string
  val value : t -> string option
end
module Translation_policy : sig
  type t
  val schema_version : string
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val of_json_text : ?limits:Codec.limits -> ?path:string -> string -> t
  val make : ?limits:Codec.limits -> genetic_code:Z.t -> start_codon:string -> stop_convention:string -> protein_length_includes_stop:bool -> unit -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val genetic_code : t -> Z.t
  val start_codon : t -> string
  val stop_convention : t -> string
  val protein_length_includes_stop : t -> bool
  val default : ?limits:Codec.limits -> unit -> t
end
module Encoding_policy : sig
  type t
  val schema_version : string
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val of_json_text : ?limits:Codec.limits -> ?path:string -> string -> t
  val make : ?limits:Codec.limits -> mode:string -> optimization:string -> transformations:string list -> unit -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val mode : t -> string
  val optimization : t -> string
  val transformations : t -> string list
  val default : ?limits:Codec.limits -> unit -> t
end
module Evidence_policy : sig
  type t
  val schema_version : string
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val of_json_text : ?limits:Codec.limits -> ?path:string -> string -> t
  val make : ?limits:Codec.limits -> semantic_properties:string list -> invalidated_analyses:string list -> unit -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val semantic_properties : t -> string list
  val invalidated_analyses : t -> string list
  val default : ?limits:Codec.limits -> unit -> t
end
module Change : sig
  type t
  val schema_version : string
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val of_json_text : ?limits:Codec.limits -> ?path:string -> string -> t
  val make : ?limits:Codec.limits -> id:string -> record_id:string -> before_sequence_sha256:string -> after_sequence_sha256:string -> changed_properties:string list -> reason:string -> preservation_claims:string list -> unit -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val id : t -> string
  val record_id : t -> string
  val before_sequence_sha256 : t -> string
  val after_sequence_sha256 : t -> string
  val changed_properties : t -> string list
  val reason : t -> string
  val preservation_claims : t -> string list
end
module Record : sig
  type t
  val schema_version : string
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val of_json_text : ?limits:Codec.limits -> ?path:string -> string -> t
  val make : ?limits:Codec.limits -> id:string -> instance_id:string -> molecule_id:string -> alphabet:Reference_manifest.alphabet -> artifact_class:string -> sequence:string -> sequence_sha256:string -> component:Component_registry.Component_lock.t -> reference_selection:Reference_components.Selection.t -> source_range:Reference_construct.Sequence_range.t -> molecule_range:Reference_construct.Sequence_range.t -> features:Reference_construct.Feature.t list -> feature_statuses:Feature_status.t list -> orientation:Reference_construct.orientation -> reading_frame:int option -> translation_policy:Translation_policy.t -> completeness:string -> unknown_features:string list -> evidence_relationships:string list -> requirement_ids:string list -> source:Behavior.source_location option -> unit -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val id : t -> string
  val instance_id : t -> string
  val molecule_id : t -> string
  val alphabet : t -> Reference_manifest.alphabet
  val artifact_class : t -> string
  val sequence : t -> string
  val sequence_sha256 : t -> string
  val component : t -> Component_registry.Component_lock.t
  val reference_selection : t -> Reference_components.Selection.t
  val source_range : t -> Reference_construct.Sequence_range.t
  val molecule_range : t -> Reference_construct.Sequence_range.t
  val features : t -> Reference_construct.Feature.t list
  val feature_statuses : t -> Feature_status.t list
  val orientation : t -> Reference_construct.orientation
  val reading_frame : t -> int option
  val translation_policy : t -> Translation_policy.t
  val completeness : t -> string
  val unknown_features : t -> string list
  val evidence_relationships : t -> string list
  val requirement_ids : t -> string list
  val source : t -> Behavior.source_location option
  val length : t -> int
  val reference : t -> Pinned_identity.t
end
module Artifact : sig
  type t
  val schema_version : string
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val of_json_text : ?limits:Codec.limits -> ?path:string -> string -> t
  val make : ?limits:Codec.limits -> request_fingerprint:string -> construct_fingerprint:string -> layout_fingerprint:string -> registry_lock:Component_registry.Lock.t -> profile:profile -> records:Record.t list -> encoding_policy:Encoding_policy.t -> evidence_policy:Evidence_policy.t -> changes:Change.t list -> source_request_fingerprint:string option -> artifact_scope:string -> unit -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val request_fingerprint : t -> string
  val construct_fingerprint : t -> string
  val layout_fingerprint : t -> string
  val registry_lock : t -> Component_registry.Lock.t
  val profile : t -> profile
  val records : t -> Record.t list
  val encoding_policy : t -> Encoding_policy.t
  val evidence_policy : t -> Evidence_policy.t
  val changes : t -> Change.t list
  val source_request_fingerprint : t -> string option
  val artifact_scope : t -> string
end
val reference_feature_statuses : ?limits:Codec.limits -> Reference_manifest.Record.t -> Feature_status.t list
