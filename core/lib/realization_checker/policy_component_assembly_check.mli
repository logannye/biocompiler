(** Independent exact graph and material correspondence under supplied original
    component/rule authority. Actual implementation is available only through a
    fresh preservation capability. This checker grants no catalog-to-component
    authorization, context/resource satisfaction, source-obligation discharge,
    empirical claim or export authority. No report decoder can grant a token. *)
open Bioc_wire
module R = Bioc_domain.Policy_realization_request
module L = Bioc_domain.Policy_component_library
module A = Bioc_domain.Policy_component_assembly_rule
module Q = Bioc_domain.Policy_component_assembly_proposal
module P = Policy_preservation_check
module K = Bioc_domain.Construction_content
module E = Bioc_domain.Construction_assessment
module S = Bioc_checker.Policy_mrna_structure_check
val implementation_version : string

(** Version used only for the separately versioned named-instance profile.
    Legacy two-slot reports retain [implementation_version]. *)
val instance_implementation_version : string
val max_work : int
type result
type checked_assembly
val check : ?parent:Bioc_checker.Work_budget.t -> ?maximum:int ->
  original:R.t -> components:L.t -> rule:A.t -> implementation:P.checked_implementation ->
  proposed:Q.t -> candidate:K.t -> unit -> result
val outcome : result -> E.outcome
val report : result -> Json.t
val accepted : result -> checked_assembly option
val original : checked_assembly -> R.t
val components : checked_assembly -> L.t
val rule : checked_assembly -> A.t
val implementation : checked_assembly -> P.checked_implementation
val structure : checked_assembly -> S.checked_structure
val evidence : checked_assembly -> Json.t
