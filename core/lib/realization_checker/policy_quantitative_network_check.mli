(** Independent complete finite network-law/source/component correspondence.
    Declared-order reservations use only prestate stock and receiver room under
    one atomic owner. Conservation excludes reset, which restores the vector.
    No distributed atomicity or physical transport is established. *)
open Bioc_wire
module R = Bioc_domain.Policy_component_material_request
module C = Policy_component_context_check
module E = Bioc_domain.Construction_assessment
val schema_version : string
val profile : string
val implementation_version : string
val max_work : int
type result
type checked_network
val check : ?parent:Bioc_checker.Work_budget.t -> ?maximum:int ->
  request:R.t -> context:C.checked_context -> unit -> result
val report : result -> Json.t
val outcome : result -> E.outcome
val accepted : result -> checked_network option
val request : checked_network -> R.t
val evidence : checked_network -> Json.t
