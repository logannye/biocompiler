(** Fresh complete-source, conditional contract and independently reconstructed
    exact RNA conjunction. No saved assessment can recreate this private token. *)
open Bioc_wire
module R = Bioc_domain.Policy_expression_material
module K = Bioc_domain.Construction_content
module S = Policy_expression_structure_check
module A = Policy_expression_source_admission
val candidate_schema : string
val implementation_version : string
type result
type checked_expression_material
val check : request:R.t -> candidate:K.t -> result

(** Same live invocation owner for final service publication; budget access
    grants no semantic or export authority. *)
val budget : result -> Work_budget.t
val report : result -> Json.t
val accepted : result -> checked_expression_material option
val request : checked_expression_material -> R.t
val source : checked_expression_material -> A.t
val structure : checked_expression_material -> S.checked_structure
val evidence : checked_expression_material -> Json.t
