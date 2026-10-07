(** Fresh complete-catalog checking under one original program and a closed
    material-variant relation. Failed children are never converted into length
    exclusions. Only fresh private material capabilities determine lengths and
    the independently selected winner. No producer is imported. *)
open Bioc_wire
module R = Bioc_domain.Policy_component_selection_request
module V = Bioc_domain.Policy_component_selection_candidate
module P = Policy_preservation_check
module Child = Policy_component_material_check
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
