(** Independently reconstruct complete RNA under an exact admitted controlled
    nominal-translation premise. This capability is distinct from the ordinary
    CDS checker. N1-methylpseudouridine at declared canonical U positions is a
    nominal parent-base projection only; physical translation is unassessed. *)
open Bioc_wire
module Request = Bioc_domain.Policy_controlled_composition_request
module Admission = Policy_controlled_composition_admission
module A = Bioc_domain.Policy_mrna_structure
module K = Bioc_domain.Construction_content
module E = Bioc_domain.Construction_assessment
val implementation_version : string
val profile : string
val translation_definition : unit -> Json.t
val requests_nominal_translation : charge:(int -> unit) -> admitted:Admission.t -> request:Request.t -> bool
type result
type checked_structure
val check : ?parent:Work_budget.t -> ?maximum:int -> admitted:Admission.t -> request:Request.t -> candidate:K.t -> unit -> result
val report : result -> Json.t
val outcome : result -> E.outcome
val checked_structure : result -> checked_structure option
val authority : checked_structure -> A.t
val content : checked_structure -> K.t
val evidence : checked_structure -> Json.t
