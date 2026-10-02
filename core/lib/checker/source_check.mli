(** Independent reconstruction from complete original source authority. No
    source producer or evaluator is linked. Results concern declared semantics
    and retained inventories, never candidate implementation or admission.
    Native lowering discrepancies use [source_behavior:<native diagnostic code>]
    under this checker version; other scoped keys preserve the Python profile.
    Resource exhaustion raises an error and never returns a partial report. *)
val checker_version : string
val claim_scope : string
type result = { failures : string list; unresolved : string list }
val check : expected_source:Bioc_domain.Human_request.t -> manifest:Bioc_domain.Source_execution_manifest.t -> result
val check_json : expected_source:Bioc_wire.Json.t -> manifest:Bioc_wire.Json.t -> result
