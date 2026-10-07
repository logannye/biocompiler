(** Conditional deployment/resource checking after private fresh implementation
    and material/structure acceptance. No source receipt is rewritten. No
    empirical, human-use or export authority is conferred by this leaf. *)
open Bioc_wire
module C = Bioc_domain.Policy_material_context
module E = Bioc_domain.Construction_assessment
module B = Policy_material_binding_check
val implementation_version : string
val max_work : int
type discharge = { obligation:string; evidence:Json.t }
type result
type checked_context
val check : ?parent:Bioc_checker.Work_budget.t -> ?maximum:int ->
  context:C.t -> binding:B.checked_material_binding -> unit -> result
val report : result -> Json.t
val outcome : result -> E.outcome
val accepted : result -> checked_context option
val context : checked_context -> C.t
val binding : checked_context -> B.checked_material_binding
val discharges : checked_context -> discharge list
val evidence : checked_context -> Json.t
val replay : ?parent:Bioc_checker.Work_budget.t -> ?maximum:int ->
  context:C.t -> binding:B.checked_material_binding -> Json.t -> result
