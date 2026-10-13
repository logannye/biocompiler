(** Fresh structural and bounded-behavior checking under one cumulative owner.
    This module imports no producer and grants a token only when both checks pass. *)
open Bioc_wire
module R = Bioc_domain.Policy_controlled_workflow_request
module C = Bioc_domain.Policy_controlled_workflow_candidate
module Material = Bioc_checker.Policy_controlled_material_check
module Behavior = Policy_controlled_behavior_check
module W = Bioc_checker.Work_budget
type result
type checked_controlled_workflow
val schema_version : string
val implementation_version : string
val check : ?parent:W.t -> ?cancelled:(unit -> bool) -> request:R.t -> candidate:C.t -> unit -> result
val replay : ?parent:W.t -> request:R.t -> candidate:C.t -> Json.t -> result
val report : result -> Json.t
val budget : result -> W.t
val accepted : result -> checked_controlled_workflow option
val request_fingerprint : result -> string
val candidate_fingerprint : result -> string
val invocation_fingerprint : result -> string
val request : checked_controlled_workflow -> R.t
val candidate : checked_controlled_workflow -> C.t
val evidence : checked_controlled_workflow -> Json.t
val material : checked_controlled_workflow -> Material.checked_controlled_material
val behavior : checked_controlled_workflow -> Behavior.checked_controlled_behavior
