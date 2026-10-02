(** Independent correspondence against the complete caller-supplied frozen
    request. No producer, evaluator, matcher or molecular acceptance is invoked.
    Unsupported source semantics and correspondence discrepancies have distinct
    Diagnostic.Error codes. A report exists only after every check passes. *)
type preservation_check
val property : preservation_check -> string
val detail : preservation_check -> string
type report
val schema_version : string
val checker_version : string
val resource_profile : string
val validation_scope : string
val claim_scope : string
val check : expected_request:Bioc_domain.Build_request.t -> behavior:Bioc_domain.Behavior.t -> report
(* The terminal unit makes optional parent erasure explicit; the original
   labeled check entry point remains source-compatible and uses the same bound. *)
val check_with_budget : ?parent:Work_budget.t -> expected_request:Bioc_domain.Build_request.t ->
  behavior:Bioc_domain.Behavior.t -> unit -> report
val to_json : report -> Bioc_wire.Json.t
val passed : report -> bool
val checks : report -> preservation_check list
val unimplemented_obligations : report -> string list
