(** Fresh source authority validation for CLI input-order compatibility.
    The returned request is not an acceptance token or a workflow assessment.
    A subsequent workflow operation must decode and check its original bytes
    again under its own complete operation budget. *)
val implementation_version : string
val profile_version : string
val profile : Bioc_wire.Json.t
val profiles : (string * Bioc_wire.Json.t) list
val operations : string list
val validation_scopes : string list
val limits_of_payload : Bioc_wire.Json.t -> Bioc_realization_checker.Verification_workflow_budget.limits
type result = Verification_workflow_service.result = { artifact : string; result : Bioc_wire.Json.t }
(* Transport charges raw byte read/hash/parse on [budget]; this service reserves
   the sole complete raw authority exactly once. No retained record or lazy
   retained-record reader is accepted, and no workflow evaluator is invoked. *)
val handle_in : budget:Bioc_realization_checker.Verification_workflow_budget.t ->
  executable:Bioc_wire.Protocol.executable -> request_id:string -> operation:string ->
  payload:Bioc_wire.Json.t -> authority:Bioc_wire.Json.t -> unit -> result
