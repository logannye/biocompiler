(** Fresh source-to-Behavior authority. Construction never executes authoring,
    a lowering producer, reference/candidate execution or admission. This type
    cannot be obtained by importing a claimed report; it grants no realization
    or empirical acceptance. *)
type t
val implementation_version : string
val resource_profile : string
val check : ?parent:Bioc_checker.Work_budget.t -> Bioc_domain.Realization_request.t -> t
val of_json : ?parent:Bioc_checker.Work_budget.t -> Bioc_wire.Json.t -> t
val make : ?parent:Bioc_checker.Work_budget.t -> build_request:Bioc_domain.Build_request.t ->
  behavior:Bioc_domain.Behavior.t -> contract:Bioc_domain.Realization_contract.Behavior_contract.t ->
  domain:Bioc_domain.Realization_contract.Operating_domain.t -> unit -> t
val request : t -> Bioc_domain.Realization_request.t
val target : t -> Bioc_domain.Build_request.Target.t
val lowering_report : t -> Bioc_checker.Lowering_check.report
val fingerprint : t -> string
val artifact_fingerprint : t -> string
val to_json : t -> Bioc_wire.Json.t
