(** Immutable checked-pipeline contracts and historical records. Structural
    decoding never registers a provider, runs a validator, imports acceptance,
    establishes freshness, or completes a scope. Only a live manager may do so.
    Records with no original Python serializer use a complete field observation
    object without inventing an artifact schema. Original to_dict fields remain
    byte-identical under canonical UTF-8 serialization. *)
type json = Bioc_wire.Json.t
type stage = Intent | Behavior | Mechanism | Components | Construct | Molecular
type artifact_status = Partial | Complete
type outcome = Realization_evidence.outcome
type evidence_kind = Realization_evidence.evidence_kind
val stage_name : stage -> string
val stage_of_json : ?path:string -> json -> stage
val stage_index : stage -> int
val status_name : artifact_status -> string
val outcome_name : outcome -> string
val evidence_kind_name : evidence_kind -> string
val resource_profile : string
module Codec : module type of Verification_exploration.Codec
val resource_limits : json
module Source_link : sig
  type t
  val make : ?limits:Codec.limits ->
    requirement_id:string ->
    source_node_id:string ->
    target_node_id:string ->
    pass_name:string -> unit -> t
  val of_json : ?limits:Codec.limits -> ?path:string -> json -> t
  val to_json : t -> json
  val fingerprint : t -> string
  val canonical_size : t -> int
  val requirement_id : t -> string
  val source_node_id : t -> string
  val target_node_id : t -> string
  val pass_name : t -> string
end
module Producer_obligation : sig
  type t
  val make : ?limits:Codec.limits ->
    requirement_id:string ->
    description:string ->
    ?evidence_kind:evidence_kind ->
    ?evidence_refs:string list -> unit -> t
  val of_json : ?limits:Codec.limits -> ?path:string -> json -> t
  val to_json : t -> json
  val fingerprint : t -> string
  val canonical_size : t -> int
  val requirement_id : t -> string
  val description : t -> string
  val evidence_kind : t -> evidence_kind
  val evidence_refs : t -> string list
end
module Scoped_obligation : sig
  type t
  val make : ?limits:Codec.limits ->
    id:string ->
    scope:string ->
    evidence_kind:evidence_kind ->
    description:string -> unit -> t
  val of_json : ?limits:Codec.limits -> ?path:string -> json -> t
  val to_json : t -> json
  val fingerprint : t -> string
  val canonical_size : t -> int
  val id : t -> string
  val scope : t -> string
  val evidence_kind : t -> evidence_kind
  val description : t -> string
end
module Check_spec : sig
  type t
  val make : ?limits:Codec.limits ->
    id:string ->
    evidence_kind:evidence_kind ->
    ?discharges:string list -> unit -> t
  val of_json : ?limits:Codec.limits -> ?path:string -> json -> t
  val to_json : t -> json
  val fingerprint : t -> string
  val canonical_size : t -> int
  val id : t -> string
  val evidence_kind : t -> evidence_kind
  val discharges : t -> string list
end
module Check_decision : sig
  type t
  val make : ?limits:Codec.limits ->
    outcome:outcome ->
    detail:string ->
    ?evidence:json -> unit -> t
  val of_json : ?limits:Codec.limits -> ?path:string -> json -> t
  val to_json : t -> json
  val fingerprint : t -> string
  val canonical_size : t -> int
  val outcome : t -> outcome
  val detail : t -> string
  val evidence : t -> json
end
module Pass_contract : sig
  type t
  val make : ?limits:Codec.limits ->
    id:string ->
    version:string ->
    input_stage:stage ->
    output_stage:stage ->
    input_schema:string ->
    output_schema:string ->
    profile:string ->
    profile_version:string ->
    supported_operations:string list ->
    checks:Check_spec.t list ->
    ?dependency_keys:string list ->
    ?targets:string list ->
    ?required_capabilities:string list ->
    ?consumes_requirements:string list ->
    ?assumptions:string list ->
    ?introduces:Scoped_obligation.t list ->
    ?requires_source_map:bool ->
    ?requires_observation_map:bool ->
    ?changed_properties:string list ->
    ?invalidated_analyses:string list ->
    ?operation_path:string list -> unit -> t
  val of_json : ?limits:Codec.limits -> ?path:string -> json -> t
  val to_json : t -> json
  val fingerprint : t -> string
  val canonical_size : t -> int
  val id : t -> string
  val version : t -> string
  val input_stage : t -> stage
  val output_stage : t -> stage
  val input_schema : t -> string
  val output_schema : t -> string
  val profile : t -> string
  val profile_version : t -> string
  val supported_operations : t -> string list
  val checks : t -> Check_spec.t list
  val dependency_keys : t -> string list
  val targets : t -> string list
  val required_capabilities : t -> string list
  val consumes_requirements : t -> string list
  val assumptions : t -> string list
  val introduces : t -> Scoped_obligation.t list
  val requires_source_map : t -> bool
  val requires_observation_map : t -> bool
  val changed_properties : t -> string list
  val invalidated_analyses : t -> string list
  val operation_path : t -> string list
end
module Pass_context : sig
  type t
  val make : ?limits:Codec.limits ->
    input:json ->
    output:json option ->
    target:Build_request.Target.t ->
    configuration:json ->
    dependencies:(string * string) list ->
    requirements:string list ->
    ?source_links:Source_link.t list ->
    ?observation_map:json -> unit -> t
  val of_json : ?limits:Codec.limits -> ?path:string -> json -> t
  val to_json : t -> json
  val fingerprint : t -> string
  val canonical_size : t -> int
  val input : t -> json
  val output : t -> json option
  val target : t -> Build_request.Target.t
  val configuration : t -> json
  val dependencies : t -> (string * string) list
  val requirements : t -> string list
  val source_links : t -> Source_link.t list
  val observation_map : t -> json
end
module Component_input_contract : sig
  type t
  val make : ?limits:Codec.limits ->
    id:string ->
    version:string ->
    schema:string ->
    checks:Check_spec.t list ->
    requirements:string list ->
    obligations:Scoped_obligation.t list ->
    ?dependency_keys:string list ->
    ?operation_path:string list -> unit -> t
  val of_json : ?limits:Codec.limits -> ?path:string -> json -> t
  val to_json : t -> json
  val fingerprint : t -> string
  val canonical_size : t -> int
  val id : t -> string
  val version : t -> string
  val schema : t -> string
  val checks : t -> Check_spec.t list
  val requirements : t -> string list
  val obligations : t -> Scoped_obligation.t list
  val dependency_keys : t -> string list
  val operation_path : t -> string list
end
module Completion_profile : sig
  type t
  val make : ?limits:Codec.limits ->
    scope:string ->
    stage:stage ->
    schema:string ->
    obligations:string list -> unit -> t
  val of_json : ?limits:Codec.limits -> ?path:string -> json -> t
  val to_json : t -> json
  val fingerprint : t -> string
  val canonical_size : t -> int
  val scope : t -> string
  val stage : t -> stage
  val schema : t -> string
  val obligations : t -> string list
end
module Stage_record : sig
  type t
  val schema_version : string
  val make : ?limits:Codec.limits ->
    id:string ->
    stage:stage ->
    payload:json ->
    requirements:string list ->
    obligations:Scoped_obligation.t list ->
    discharged:string list ->
    dependencies:(string * string) list ->
    parent:string option ->
    pass_id:string option ->
    pass_identity:string option ->
    checks:json ->
    provenance:json ->
    accepted:bool -> unit -> t
  val of_json : ?limits:Codec.limits -> ?path:string -> json -> t
  val to_json : t -> json
  val fingerprint : t -> string
  val canonical_size : t -> int
  val id : t -> string
  val stage : t -> stage
  val payload : t -> json
  val requirements : t -> string list
  val obligations : t -> Scoped_obligation.t list
  val discharged : t -> string list
  val dependencies : t -> (string * string) list
  val parent : t -> string option
  val pass_id : t -> string option
  val pass_identity : t -> string option
  val checks : t -> json
  val provenance : t -> json
  val accepted : t -> bool
end
module Pipeline_result : sig
  type t
  val make : ?limits:Codec.limits ->
    status:artifact_status ->
    artifact:Stage_record.t ->
    scope:string ->
    unresolved:Scoped_obligation.t list -> unit -> t
  val of_json : ?limits:Codec.limits -> ?path:string -> json -> t
  val to_json : t -> json
  val fingerprint : t -> string
  val canonical_size : t -> int
  val status : t -> artifact_status
  val artifact : t -> Stage_record.t
  val scope : t -> string
  val unresolved : t -> Scoped_obligation.t list
end
module Pass_result : sig
  type t
  val make : ?limits:Codec.limits ->
    output:json option ->
    obligations:Producer_obligation.t list ->
    source_links:Source_link.t list ->
    ?observation_map:json ->
    ?search_status:string -> unit -> t
  val of_json : ?limits:Codec.limits -> ?path:string -> json -> t
  val to_json : t -> json
  val fingerprint : t -> string
  val canonical_size : t -> int
  val output : t -> json option
  val obligations : t -> Producer_obligation.t list
  val source_links : t -> Source_link.t list
  val observation_map : t -> json
  val search_status : t -> string
end
