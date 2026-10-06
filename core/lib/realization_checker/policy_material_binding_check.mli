(** Independent exact case evaluation after fresh source/graph preservation.
    No producer is imported. The candidate's actual molecular content must pass
    fresh PM structure/construction checking, match the full supplied material
    key, and realize the whole supplied kernel under a total ordered bijection.
    Recipient/deployment/resources/input compatibility and export remain
    unassessed. The resulting private leaf cannot authorize final artifacts. *)
open Bioc_wire
module C = Bioc_domain.Policy_material_contract
module K = Bioc_domain.Construction_content
module E = Bioc_domain.Construction_assessment
module P = Policy_preservation_check
module S = Bioc_checker.Policy_mrna_structure_check
type result
type checked_material_binding
val check : ?parent:Bioc_checker.Work_budget.t -> ?maximum:int ->
  contract:C.t -> implementation:P.checked_implementation ->
  proposed:C.proposal -> candidate:K.t -> unit -> result
val outcome : result -> E.outcome
val report : result -> Json.t
val accepted : result -> checked_material_binding option
val contract : checked_material_binding -> C.t
val implementation : checked_material_binding -> P.checked_implementation
val structure : checked_material_binding -> S.checked_structure
val evidence : checked_material_binding -> Json.t
