(** Immutable use declarations and historical decisions. Decoding and identity
    freshness never grant admission; Admission_check recomputes current policy. *)
type use = Software_test | Human_therapeutic
type boundary = Planning | Selection | Verification | Export
type decision = Software_only | Not_admitted
val policy_version : string
val resource_profile : string
val use_name : use -> string
val boundary_name : boundary -> string
val decision_name : decision -> string
val use_of_json : ?path:string -> Bioc_wire.Json.t -> use
val boundary_of_json : ?path:string -> Bioc_wire.Json.t -> boundary
val decision_of_json : ?path:string -> Bioc_wire.Json.t -> decision
module Request : sig
  type t
  val schema_version : string
  val make : target:Build_request.Target.t -> intended_use:use -> boundary:boundary -> components:Component.t list -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val target : t -> Build_request.Target.t
  val intended_use : t -> use
  val boundary : t -> boundary
  val components : t -> Component.t list
end
module Assessment : sig
  type t
  val schema_version : string
  val make : request_fingerprint:string -> target_fingerprint:string -> intended_use:use -> boundary:boundary ->
    decision:decision -> diagnostics:string list -> component_fingerprints:string list -> evidence:Build_request.Target_evidence.t list -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val request_fingerprint : t -> string
  val target_fingerprint : t -> string
  val intended_use : t -> use
  val boundary : t -> boundary
  val decision : t -> decision
  val diagnostics : t -> string list
  val component_fingerprints : t -> string list
  val evidence : t -> Build_request.Target_evidence.t list
  val is_current : t -> Request.t -> bool
end
