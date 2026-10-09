(** Independent exact one-step law/source/local-model correspondence. Complete
    source-domain preservation, original context and atomic resource reservation
    are preconditions supplied by a fresh checked context. No physical rates,
    calibration, continuous-time evolution or empirical claim is inferred.
    Separate transfer-pair and reserved-network requests dispatch to their
    independent checkers; the generic capability wraps only fresh acceptance. *)
open Bioc_wire
module R = Bioc_domain.Policy_component_material_request
module C = Policy_component_context_check
module E = Bioc_domain.Construction_assessment
val schema_version : string
val profile : string
val implementation_version : string
val step_schema_version : string
val step_implementation_version : string
val max_work : int
type result
type checked_quantitative
val check : ?parent:Bioc_checker.Work_budget.t -> ?maximum:int ->
  request:R.t -> context:C.checked_context -> unit -> result
val report : result -> Json.t
val outcome : result -> E.outcome
val accepted : result -> checked_quantitative option
val request : checked_quantitative -> R.t
val evidence : checked_quantitative -> Json.t
