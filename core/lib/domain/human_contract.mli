(** Structural human declarations. Cited support, complete records and imported
    requirements never establish evidence, delivery, actuators or admission. *)
module Claim = Build_request.Target_claim
module Measurement : sig
  type access = Cell | External_evaluator
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val observable : t -> Measurement_contract.Observable.t
  val access : t -> access
  val support : t -> Claim.t
end
module Predicate : sig
  type operator = Greater | Greater_equal | Less | Less_equal
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val id : t -> string
  val operator : t -> operator
  val threshold : t -> Measurement_contract.Scalar.t
  val support : t -> Claim.t
  val accepts : t -> Measurement_contract.Scalar.t -> bool
end
module Conditional_secretion : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val input : t -> Measurement.t
  val output : t -> Measurement.t
  val predicate : t -> Predicate.t
  val response : t -> Measurement_contract.Response.t
  val horizon : t -> Measurement_contract.Scalar.t
  val goal_id : t -> string
  val product : t -> string
  val input_signal_id : t -> string
  val claims : t -> (string * Claim.t) list
end
module Platform : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val payload_format : t -> string
  val claims : t -> (string * Claim.t) list
end
module Exposure : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val id : t -> string
  val observable : t -> string
  val compartment : t -> string
  val support : t -> Claim.t
end
module Expression_timing : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val support : t -> Claim.t
end
module Co_payload : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val id : t -> string
  val destination : t -> string
  val support : t -> Claim.t
end
module Deployment : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val target_fingerprint : t -> string
  val recipient_role : t -> string
  val platform : t -> Platform.t
  val exposures : t -> Exposure.t list
  val co_payloads : t -> Co_payload.t list
  val destination : t -> string
  val intended_population : t -> Claim.t
  val excluded_population : t -> Claim.t
  val claims : t -> (string * Claim.t) list
end
module Input_availability : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val delay : t -> Measurement_contract.Scalar.t
  val claims : t -> (string * Claim.t) list
end
module External_shutdown : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val delay : t -> Measurement_contract.Scalar.t
  val claims : t -> (string * Claim.t) list
end
module Acceptance : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val behavior_fingerprint : t -> string
  val healthy_measurement : t -> Measurement.t
  val background : t -> Measurement_contract.Scalar.t
  val peak : t -> Measurement_contract.Scalar.t
  val input_availability : t -> Input_availability.t
  val shutdown : t -> External_shutdown.t
  val claims : t -> (string * Claim.t) list
end
