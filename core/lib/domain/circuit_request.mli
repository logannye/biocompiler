(** Structural circuit authority, not source correspondence, candidate acceptance
    or biological admission. Typed human wrappers retain complete nested source
    authority and all unimplemented assessment/implementation obligations. *)
type unsupported
val unsupported_authority : unsupported -> Bioc_wire.Json.t
val unsupported_reasons : unsupported -> string list
type 'a decoded = Decoded of 'a | Unsupported of unsupported

module Product : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val id : t -> string
  val kind : t -> string
  val observation : t -> Bioc_wire.Json.t
end
module Lifecycle : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val mode : t -> string
  val onset : t -> Bioc_wire.Json.t option
  val cessation : t -> Bioc_wire.Json.t option
  val clearance : t -> Bioc_wire.Json.t option
end
module Provider : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val id : t -> string
  val kind : t -> string
  val compartment : t -> string
end

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
  val source_request : t -> Human_request.t option
  val source_build_request : t -> Build_request.t option
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
  val dependencies : t -> Provider.t list
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
val requested_form : t -> string
val unimplemented_obligations : t -> string list
