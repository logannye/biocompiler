(** Fresh complete-catalog checking under one original program and a closed
    material-variant relation. Failed children are never converted into length
    exclusions. Only fresh private material capabilities determine lengths and
    the independently selected winner. No producer is imported. *)
open Bioc_wire
module R = Bioc_domain.Policy_component_selection_request
module V = Bioc_domain.Policy_component_selection_candidate
module P = Policy_preservation_check
module Child = Policy_component_material_check
module W = Bioc_checker.Work_budget
val profile : string
val implementation_version : string
type result
type checked_selection
val check : request:R.t -> candidate:V.t -> limits:P.limits -> result
val report : result -> Json.t
val accepted : result -> checked_selection option
val request : checked_selection -> R.t
val candidate : checked_selection -> V.t
val limits : checked_selection -> P.limits
val selected_id : checked_selection -> string
val selected_material : checked_selection -> Child.checked_material
val evidence : checked_selection -> Json.t

(** A single original-bound owner retains total work, outer work and cumulative
    publication caps. An optional ancestor adds a cap without replacing any
    original cap. No counter, reset, refund or early outer capability escapes. *)
type scope
type pending
val create_scope : ?parent:W.t -> request:R.t -> unit -> scope
val check_in : scope:scope -> candidate:V.t -> limits:P.limits -> pending
val pending_report : scope:scope -> pending -> Json.t
val pending_selected_material : scope:scope -> pending ->
  (string * Child.checked_material) option

(** Preparation methods charge before their corresponding pass. Every failure
    permanently poisons the owner with the first exception. Repeated publication
    reserves again. These methods are unavailable after preparing the guard. *)
val charge_outer : scope -> int -> unit
val equal_json : scope -> Json.t -> Json.t -> bool
val fingerprint : scope -> Json.t -> string
val reserve_publication : scope -> Json.t -> unit
val encode_json : scope -> Json.t -> string
val abort_scope : scope -> exn -> 'a

(** Bind the prepared result and exact protocol identity. The returned one-shot
    guard admits the actual complete response before encoding; it reserves the
    frame with all earlier reports and manifests and precharges encoding work.
    It is mandatory even when the assessment has no accepted selection. *)
val prepare_response : scope:scope -> pending ->
  executable:Protocol.executable -> protocol_request:Protocol.request ->
  result:Json.t -> (Json.t -> unit)
