(** Complete finite-history declarations. Contracts retain supplied meaning;
    decoding or range membership never grants realization or empirical evidence. *)
val resource_profile : string
val resource_limits : Bioc_wire.Json.t
type sample = Boolean of bool | Number of Runtime_number.t |
  Scalar of Measurement_contract.Scalar.t | Other
(* Raw JSON objects are Other, not typed Scalar literals. This distinguishes the
   original API's supplied ScalarLiteral from a plain dictionary. *)
val sample_of_json : Bioc_wire.Json.t -> sample
(* Explicitly tagged ScalarLiteral import: invalid scalar meaning becomes Other;
   malformed wire values and resource/cycle failures remain diagnostics. *)
val sample_of_scalar_json : ?path:string -> Bioc_wire.Json.t -> sample

module Observable : sig
  type scope = Measurement_contract.Observable.scope = Cell | Contact
  type t = Measurement_contract.Observable.t
  val schema_version : string
  val make : id:string -> dtype:Type_spec.t -> role:string -> ?scope:scope -> ?compartment:string -> unit -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val id : t -> string
  val dtype : t -> Type_spec.t
  val role : t -> string
  val scope : t -> scope
  val compartment : t -> string
end

module Response : sig
  include module type of Measurement_contract.Response
    with type t = Measurement_contract.Response.t
  val canonical_size : t -> int
  val accepts : t -> sample -> active:bool -> bool
end

module Input_domain : sig
  type field = Observation_map.field = Value | Present | High | Low
  type allowed = Booleans of bool list | Range of Measurement_contract.Interval.t
  type t
  val schema_version : string
  val make : signal_id:string -> field:field -> observable:Observable.t -> allowed:allowed -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val signal_id : t -> string
  val field : t -> field
  val field_name : t -> string
  val observable : t -> Observable.t
  val allowed : t -> allowed
  val scope : t -> Observable.scope
  val role : t -> string
  val contains : t -> sample -> bool
end

module Operating_domain : sig
  type t
  val schema_version : string
  val make : id:string -> version:string -> role:string -> inputs:Input_domain.t list ->
    minimum_horizon:Measurement_contract.Scalar.t -> ?max_contacts:Z.t ->
    ?required_capabilities:string list -> unit -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val id : t -> string
  val version : t -> string
  val role : t -> string
  val inputs : t -> Input_domain.t list
  val minimum_horizon : t -> Measurement_contract.Scalar.t
  val max_contacts : t -> Z.t option
  val required_capabilities : t -> string list
end

module Behavior_contract : sig
  type t
  val schema_version : string
  val make : id:string -> behavior_fingerprint:string -> requirements:Response.t list -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val id : t -> string
  val behavior_fingerprint : t -> string
  val requirements : t -> Response.t list
  val role : t -> string
end
