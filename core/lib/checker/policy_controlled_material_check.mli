(** RC4 independently joins fresh complete controlled authority admission with
    exact two-member RNA reconstruction. This private capability certifies only
    supplied material structure; it does not execute activity or requirements. *)
open Bioc_wire
module R = Bioc_domain.Policy_controlled_composition_request
module C = Bioc_domain.Policy_controlled_material_candidate
module K = Bioc_domain.Construction_content
module E = Bioc_domain.Construction_assessment
module A = Policy_controlled_composition_admission
module S = Policy_mrna_structure_check
val schema_version : string
val implementation_version : string
type result
type checked_controlled_material

(** The optional live parent owns earlier decoding/production and subsequent
    publication. Every fresh check also enforces the original request ceiling;
    exhaustion or caller cancellation propagates without a material token. *)
val check : ?parent:Work_budget.t -> request:R.t -> candidate:C.t -> unit -> result
val budget : result -> Work_budget.t
val report : result -> Json.t
val outcome : result -> E.outcome
val accepted : result -> checked_controlled_material option
val request_fingerprint : result -> string
val candidate_fingerprint : result -> string
val invocation_fingerprint : result -> string
val request : checked_controlled_material -> R.t
val candidate : checked_controlled_material -> C.t
val admission : checked_controlled_material -> A.t
val structure : checked_controlled_material -> S.checked_structure
val content : checked_controlled_material -> K.t
val evidence : checked_controlled_material -> Json.t

(** Saved evidence is compared with a complete fresh check; decoding a report
    can never recreate the abstract material capability. *)
val replay : ?parent:Work_budget.t -> request:R.t -> candidate:C.t -> Json.t -> result
