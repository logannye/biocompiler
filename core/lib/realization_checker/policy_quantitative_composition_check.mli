(** Exact partitioned private-state and actual edge-signal checking under the supplied atomic coordination premise. *)
open Bioc_wire
module R = Bioc_domain.Policy_component_material_request
module C = Policy_component_context_check
module E = Bioc_domain.Construction_assessment
val schema_version : string
val profile : string
val implementation_version : string
val max_work : int
type result
type checked_composition
val check : ?parent:Bioc_checker.Work_budget.t -> ?maximum:int ->
  request:R.t -> context:C.checked_context -> unit -> result
val report : result -> Json.t
val outcome : result -> E.outcome
val accepted : result -> checked_composition option
val request : checked_composition -> R.t
val evidence : checked_composition -> Json.t
