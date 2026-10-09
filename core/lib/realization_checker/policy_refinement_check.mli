(** Named summaries of fresh opaque checker capabilities, with a closed
    directional composition algebra. Serialized evidence is never an acceptance
    input. These claims remain conditional on complete supplied authorities and
    the original finite operating domain; they grant no empirical, universal,
    clinical or export authority. Legacy reports are read, never rewritten. *)
open Bioc_wire
module N = Bioc_domain.Policy_refinement
type t
val resource_profile : string
val max_work : int
val max_claims : int
val max_premises : int
val max_inputs : int
val max_depth : int
val max_evidence_bytes : int
val max_evidence_nodes : int

(** Every factory/conjunction/chain owns a bounded work allowance. Complete
    input preflight, canonical encoding and hashing are charged separately
    from legacy checking. The coupled material factory may reuse a fully paid
    hash of the identical immutable input within that single invocation; its
    bounded index lookups are charged and publication remains fully charged.
    Derived summaries have bounded inventories, depth and publication size.
    Exhaustion returns no evidence. *)
val of_admission : ?maximum:int -> Bioc_checker.Policy_realization_admission.admitted_inputs -> t
val of_binding : ?maximum:int -> Bioc_checker.Policy_implementation_binding_check.checked_binding -> t
val of_preservation : ?maximum:int -> Policy_preservation_check.checked_implementation -> t
val of_assembly : ?maximum:int -> Policy_component_assembly_check.checked_assembly -> t
val of_context : ?maximum:int -> Policy_component_context_check.checked_context -> t
val of_material : ?maximum:int -> Policy_component_material_check.checked_material -> t

(** A conjunction retains every claim and premise and unifies only compatible
    scope identities. A chain additionally applies exactly one named rule:
    source occurrence + graph binding; source occurrence + bounded preservation;
    bounded source correspondence + supplied component material correspondence.
    All repeated stage artifacts and premise identities must match exactly.
    Missing local scope fields may be supplied by a later checked stage; a
    conflicting nonempty identity is never erased, widened or replaced. *)
val conjoin : ?maximum:int -> t list -> t
val compose : ?maximum:int -> t -> t -> t
val claims : t -> N.claim list
val premises : t -> N.premise list
val scope : t -> N.scope
val to_json : t -> Json.t
val fingerprint : t -> string
