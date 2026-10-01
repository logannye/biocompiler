(** Frozen human source authority. Successful import checks declarations and
    source correspondence; it establishes no observation outcome or admission. *)
module Behavior_request : sig
  type t
  val schema_version : string
  val make : build_request:Build_request.t -> contract:Human_contract.Conditional_secretion.t -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val artifact_fingerprint : t -> string
  val build_request : t -> Build_request.t
  val target : t -> Build_request.Target.t
  val contract : t -> Human_contract.Conditional_secretion.t
end
module Deployment_request : sig
  type t
  val schema_version : string
  val make : behavior_request:Behavior_request.t -> deployment:Human_contract.Deployment.t -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val artifact_fingerprint : t -> string
  val behavior_request : t -> Behavior_request.t
  val build_request : t -> Build_request.t
  val target : t -> Build_request.Target.t
  val deployment : t -> Human_contract.Deployment.t
end
module Acceptance_request : sig
  type t
  val schema_version : string
  val make : deployment_request:Deployment_request.t -> acceptance:Human_contract.Acceptance.t -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val artifact_fingerprint : t -> string
  val deployment_request : t -> Deployment_request.t
  val behavior_request : t -> Behavior_request.t
  val build_request : t -> Build_request.t
  val target : t -> Build_request.Target.t
  val acceptance : t -> Human_contract.Acceptance.t
end
type kind = Build | Behavior | Deployment | Acceptance
type t
val validation_scope : string
val of_json : Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val artifact_fingerprint : t -> string
val kind : t -> kind
(* Traversal projection only: never replace full source authority with this. *)
val build_request : t -> Build_request.t
val target : t -> Build_request.Target.t option
val deployment : t -> Human_contract.Deployment.t option
val unimplemented_obligations : t -> string list
val unresolved_evidence : t -> string list
