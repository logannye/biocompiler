(** Immutable selection authority and complete historical reports. Only fresh
    producer replay checks current constraints, ranking, and admission. *)
val resource_profile : string
(* Bounded UTF-8 canonical byte and key/value-node census. Fixed ceilings are
   32 MiB/250k nodes; imports below use the separate 16 MiB request ceiling. *)
val measure : ?path:string -> ?maximum:int -> Bioc_wire.Json.t -> int * int
module Request : sig
  type t
  val schema_version : string
  val make : implementation_role:string -> target:Build_request.Target.t ->
    required_domain:Component_contract.Operating_domain.t -> ?instance_id:string ->
    ?classification:string -> ?required_guarantees:string list -> ?component_id:string ->
    ?component_version:string -> ?required_identities:Pinned_identity.t list ->
    ?preferred_component_ids:string list -> unit -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val implementation_role : t -> string
  val target : t -> Build_request.Target.t
  val required_domain : t -> Component_contract.Operating_domain.t
  val instance_id : t -> string
  val classification : t -> string option
  val required_guarantees : t -> string list
  val component_id : t -> string option
  val component_version : t -> string option
  val required_identities : t -> Pinned_identity.t list
  val preferred_component_ids : t -> string list
end
module Alternative : sig
  type status = Eligible | Rejected | Unknown
  type t
  val schema_version : string
  val status_name : status -> string
  val make : component_id:string -> version:string -> content_fingerprint:string ->
    status:status -> reasons:string list -> ?preference_rank:Z.t -> unit -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val component_id : t -> string
  val version : t -> string
  val content_fingerprint : t -> string
  val status : t -> status
  val reasons : t -> string list
  val preference_rank : t -> Z.t option
  val compare_rank : t -> t -> int
end
module Result : sig
  type outcome = Pass | Fail | Unknown | Unsupported
  type t
  val schema_version : string
  val make : registry_fingerprint:string -> request_fingerprint:string ->
    selected:Component_registry.Component_lock.t option -> alternatives:Alternative.t list ->
    admission:Admission.Assessment.t -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val registry_fingerprint : t -> string
  val request_fingerprint : t -> string
  val selected : t -> Component_registry.Component_lock.t option
  val alternatives : t -> Alternative.t list
  val admission : t -> Admission.Assessment.t
  val outcome : t -> outcome
  val outcome_name : outcome -> string
end
