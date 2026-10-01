(** Structural circuit authority, not source correspondence, candidate acceptance
    or biological admission. Unsupported source wrappers retain the complete
    original input and cannot construct a validated circuit or profile. *)
type unsupported
val unsupported_authority : unsupported -> Bioc_wire.Json.t
val unsupported_reasons : unsupported -> string list
type 'a decoded = Decoded of 'a | Unsupported of unsupported

module Recipient : sig
  type t
  val of_json : Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val lineage : t -> string
end
module Experiment : sig
  type t
  val of_json : Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
end
module Profile : sig
  type t
  val of_json : Bioc_wire.Json.t -> t decoded
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val purpose : t -> string
  val mode : t -> string
  val target : t -> Build_request.Target.t option
  val source_request : t -> Build_request.t option
  val unimplemented_obligations : t -> string list
end
module Requirement : sig
  type t
  val of_json : Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val id : t -> string
  val role : t -> Identity.Role.t option
  val source_nodes : t -> Identity.Node.t list
  val executable_behavior : t -> Behavior.t option
  val action_ids : t -> Identity.Node.t list
  val output : t -> Bioc_wire.Json.t
  val input_bindings : t -> (string * Identity.Node.t) list
  val unimplemented_obligations : t -> string list
end
type t
val schema_version : string
val validation_scope : string
val of_json : Bioc_wire.Json.t -> t decoded
val to_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val profile : t -> Profile.t
val requirements : t -> Requirement.t list
val unimplemented_obligations : t -> string list
