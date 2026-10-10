(** Fresh bounded relational checking over complete original laws and a checked
    exact material capability. Imported error reports never mint this token. *)
open Bioc_wire
module Contract = Bioc_domain.Policy_approximation_contract
module E = Bioc_domain.Construction_assessment
val schema_version : string
val profile : string
val implementation_version : string
val max_work : int
type result
type checked_approximation
val check : ?parent:Bioc_checker.Work_budget.t -> ?maximum:int ->
  material:Policy_component_material_check.checked_material -> contract:Contract.t -> unit -> result
val report : result -> Json.t
val outcome : result -> E.outcome
val accepted : result -> checked_approximation option
val evidence : checked_approximation -> Json.t
val contract : checked_approximation -> Contract.t
val material : checked_approximation -> Policy_component_material_check.checked_material
