(** Supplied expression windows and deployment requirements. These are structural
    declarations, not delivery predictions, fresh assessments or acceptance. *)
val max_seconds : int
val clock : string

module Time : sig
  type t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val zero : t
  val maximum : t
  val compare : t -> t -> int
  (* Exact decimal seconds, matching Fraction(str(value)). This deliberately
     differs from the binary64 arithmetic of the reference evaluator. *)
  val compare_sum : t -> t -> t -> int
  val ratio : t -> Z.t * Z.t
end

module Availability : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> placement_id:string -> onset_min:Time.t -> onset_max:Time.t ->
    duration_min:Time.t -> duration_max:Time.t -> assumptions:string list -> t
  val id : t -> string
  val placement_id : t -> string
  val onset_min : t -> Time.t
  val onset_max : t -> Time.t
  val duration_min : t -> Time.t
  val duration_max : t -> Time.t
  val assumptions : t -> string list
end

module Requirement : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val make : id:string -> delivery_group_id:string -> recipient_role:string ->
    compartment:string -> required_from:Time.t -> required_until:Time.t ->
    unavailable_after:Time.t option -> require_same_recipient:bool -> assumptions:string list -> t
  val id : t -> string
  val delivery_group_id : t -> string
  val recipient_role : t -> string
  val compartment : t -> string
  val required_from : t -> Time.t
  val required_until : t -> Time.t
  val unavailable_after : t -> Time.t option
  val require_same_recipient : t -> bool
  val assumptions : t -> string list
end
