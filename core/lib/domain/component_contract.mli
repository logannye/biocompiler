(** Closed component contract records and exact local domain algebra.
    Structural imports retain declarations; only the algebra constructs a fresh
    assessment. Neither establishes empirical behavior or architecture acceptance. *)
type status = Pass | Fail | Unknown
type assessment
val status : assessment -> status
val reasons : assessment -> string list
val passed : assessment -> bool
val assessment_to_json : assessment -> Bioc_wire.Json.t
(* Assessment reason text uses this explicit Unicode profile. *)
val diagnostic_profile : string

module Value_domain : sig
  type kind = Boolean | Scalar_interval | Unknown_domain
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val boolean : ?values:bool list -> unit -> t
  val interval : lower:Runtime_number.t -> upper:Runtime_number.t -> dtype:Type_spec.t -> unit:string -> t
  val unknown : dtype:Type_spec.t -> unit:string -> reason:string -> t
  val kind : t -> kind
  val dtype : t -> Type_spec.t
  val unit : t -> string
  val values : t -> bool list
  val lower : t -> Runtime_number.t option
  val upper : t -> Runtime_number.t option
  val reason : t -> string option
end

module Domain_check : sig
  (** An imported status is an archived claim, not an [assessment]. *)
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val claimed_status : t -> status
  val claimed_reasons : t -> string list
  val of_assessment : assessment -> t
end

module Operating_domain : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : (string * Value_domain.t) list -> t
  val constraints : t -> (string * Value_domain.t) list
end

module Port : sig
  type direction = Input | Output
  type scope = Cell | Contact
  type timing = Stateless | Temporal_level | Temporal_event | Unknown_timing
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> direction:direction -> meaning:string -> dtype:Type_spec.t ->
    unit:string -> role:string -> scope:scope -> compartment:string -> timing:timing ->
    initialization:Value_domain.t -> domain:Value_domain.t -> t
  val id : t -> string
  val direction : t -> direction
  val meaning : t -> string
  val dtype : t -> Type_spec.t
  val unit : t -> string
  val role : t -> string
  val scope : t -> scope
  val compartment : t -> string
  val timing : t -> timing
  val initialization : t -> Value_domain.t
  val domain : t -> Value_domain.t
end

val contract_type : Type_spec.t -> Type_spec.t
val canonical_synthetic_unit : Type_spec.t -> string
val domain_subset : required:Value_domain.t -> supported:Value_domain.t -> assessment
val operating_domain_subset : required:Operating_domain.t -> supported:Operating_domain.t -> assessment
val ports_compatible : producer:Port.t -> consumer:Port.t -> assessment

type synthetic_operation =
  | Input | Constant | And | Or | Not | Compare | Select | Any_contact | Output
  | Held_for | Onset | Pulse | Memory
val synthetic_operation_of_string : string -> synthetic_operation
val synthetic_operation_name : synthetic_operation -> string
(* Local abstraction over checked domains. Full executable model port/attribute
    admissibility belongs to Component; this does not create an executable model.
    None means external Input supplies an assumption and has no inferred domain. *)
val synthetic_output_domain : operation:synthetic_operation -> attributes:Bioc_wire.Json.t ->
  inputs:Value_domain.t list -> dtype:Type_spec.t -> ?initialization:bool ->
  ?max_contacts:Runtime_number.t -> unit -> Value_domain.t option
