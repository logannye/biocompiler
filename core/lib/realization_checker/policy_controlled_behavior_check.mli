(** Independent bounded RC5 checking. Neither candidate decoding, source
    monitoring alone, nor a saved report can recreate the private capability. *)
open Bioc_wire
module R = Bioc_domain.Policy_controlled_behavior_request
module C = Bioc_domain.Policy_controlled_behavior_candidate
module W = Bioc_checker.Work_budget
type result
type checked_controlled_behavior
val schema_version : string
val implementation_version : string
val check : ?parent:W.t -> ?cancelled:(unit -> bool) -> request:R.t -> candidate:C.t -> unit -> result
val replay : ?parent:W.t -> request:R.t -> candidate:C.t -> Json.t -> result
val report : result -> Json.t
val budget : result -> W.t
val accepted : result -> checked_controlled_behavior option
val request_fingerprint : result -> string
val candidate_fingerprint : result -> string
val invocation_fingerprint : result -> string
val request : checked_controlled_behavior -> R.t
val candidate : checked_controlled_behavior -> C.t
val evidence : checked_controlled_behavior -> Json.t
