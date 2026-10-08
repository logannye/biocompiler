(** Independent deployment, causal-provider and complete record-capacity checks
    for a private checked component assembly. No old kernel/context is created.
    The untouched request and all selected originals are rebound freshly.
    Conditional supplied contracts grant no empirical, human-use or export claim. *)
open Bioc_wire
module R = Bioc_domain.Policy_component_material_request
module X = Bioc_domain.Policy_component_context
module A = Policy_component_assembly_check
module E = Bioc_domain.Construction_assessment
val implementation_version : string
val max_work : int
type discharge = {obligation:string; evidence:Json.t}
type result
type checked_context

(** Minted only after complete fresh prerequisite, deployment, input, resource
    and availability checking. The multi-member profile also checks every
    original member placement and catalog-authorized identity transport.
    Serialized reports cannot construct this value. *)
type checked_prerequisite_closure
val check : ?parent:Bioc_checker.Work_budget.t -> ?maximum:int ->
  request:R.t -> assembly:A.checked_assembly -> unit -> result
val report : result -> Json.t
val outcome : result -> E.outcome
val accepted : result -> checked_context option
val request : checked_context -> R.t
val context : checked_context -> X.t
val assembly : checked_context -> A.checked_assembly
val discharges : checked_context -> discharge list
val evidence : checked_context -> Json.t
val prerequisite_closure : checked_context -> checked_prerequisite_closure option
val prerequisite_evidence : checked_prerequisite_closure -> Json.t
val replay : ?parent:Bioc_checker.Work_budget.t -> ?maximum:int ->
  request:R.t -> assembly:A.checked_assembly -> Json.t -> result
