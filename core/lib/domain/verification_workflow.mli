(** Complete historical workflow authority and records. Request import is
    structural; the native engine independently validates source lowering. *)
type operation = Check | Explore | Reduce
type mode = Candidate | Model
val workflow_version : string
val claim_scope : string
module Request : sig
  type t
  val schema_version : string
  val make : ?limits:Verification_exploration.Codec.limits -> realization:Realization_request.t ->
    candidate:Synthetic_authority.Candidate.t -> operation:operation -> ?mode:mode ->
    ?history:Execution_data.Input_frame.t list -> ?until:Runtime_number.t ->
    ?bounds:Verification_exploration.Bounds.t -> ?signature:Verification_exploration.Failure_signature.t ->
    ?max_evaluations:int -> unit -> t
  val of_json : ?limits:Verification_exploration.Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val decode_with_realization : ?limits:Verification_exploration.Codec.limits -> ?path:string ->
    decode_realization:(path:string -> Bioc_wire.Json.t -> Realization_request.t) -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val realization : t -> Realization_request.t
  val candidate : t -> Synthetic_authority.Candidate.t
  val operation : t -> operation
  val mode : t -> mode
  val history : t -> Execution_data.Input_frame.t list
  val until : t -> Runtime_number.t option
  val bounds : t -> Verification_exploration.Bounds.t option
  val signature : t -> Verification_exploration.Failure_signature.t option
  val max_evaluations : t -> int option
end
type result = Checked of Realization_evidence.Check_result.t
  | Explored of Verification_exploration.Report.t | Reduced of Verification_exploration.Reduction.t
val result_of_json : ?limits:Verification_exploration.Codec.limits -> ?path:string -> Bioc_wire.Json.t -> result
val result_to_json : result -> Bioc_wire.Json.t
module Record : sig
  type t
  val schema_version : string
  val make : ?limits:Verification_exploration.Codec.limits -> request:Request.t -> result:result ->
    ?workflow_version:string -> ?claim_scope:string -> unit -> t
  val of_json : ?limits:Verification_exploration.Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val decode_with_request : ?limits:Verification_exploration.Codec.limits -> ?path:string ->
    decode_request:(path:string -> Bioc_wire.Json.t -> Request.t) -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val request : t -> Request.t
  val result : t -> result
  val workflow_version : t -> string
  val claim_scope : t -> string
end
