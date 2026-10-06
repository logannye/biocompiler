(** Fresh exact-content reconstruction plus independent mRNA geometry,
    ordinary-CDS translation and chemistry checks. This leaf grants no policy,
    recipient, component-to-material or complete export authority. *)
open Bioc_wire
module A = Bioc_domain.Policy_mrna_structure
module K = Bioc_domain.Construction_content
module E = Bioc_domain.Construction_assessment
val implementation_version : string
val max_work : int
type result
type checked_structure

(** Work exhaustion raises a resource diagnostic without an assessment. Input
    and output are additionally bounded by Molecular_record's byte/node limits.
    Unknown authority and unsupported profile cases never yield checked content. *)
val check : ?parent:Work_budget.t -> ?maximum:int -> authority:A.t -> candidate:K.t -> unit -> result
val report : result -> Json.t
val outcome : result -> E.outcome

(** Present only when fresh complete original-root reconstruction and every
    supported structural obligation both pass. Wider claims remain unassessed. *)
val checked_structure : result -> checked_structure option
val authority : checked_structure -> A.t
val content : checked_structure -> K.t
val evidence : checked_structure -> Json.t
val replay : ?parent:Work_budget.t -> ?maximum:int -> authority:A.t -> candidate:K.t -> Json.t -> result
