(** Compatibility of independently supplied finite measurement intervals with
    explicit criteria for freshly selected parameters. This capability never
    establishes authenticity, statistical coverage or biological realization. *)
open Bioc_wire
module Contract = Bioc_domain.Policy_realization_evidence_contract
module Material = Policy_component_material_check
type status = Supported | Incompatible | Unassessed
val status_name : status -> string
val schema_version : string
val profile : string
val implementation_version : string
val max_work : int
type result
type checked_evidence
val applicability : Material.checked_material -> Json.t
val check : ?parent:Bioc_checker.Work_budget.t -> ?maximum:int ->
  material:Material.checked_material -> contract:Contract.t -> unit -> result
val report : result -> Json.t
val status : result -> status
val accepted : result -> checked_evidence option

(** Only the explicit compatibility flag gates export. Formal acceptance and
    the original material report remain independent for every evidence status. *)
val export_permitted : result -> bool
val material : checked_evidence -> Material.checked_material
val contract : checked_evidence -> Contract.t
val evidence : checked_evidence -> Json.t
