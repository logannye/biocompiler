(** Independent relation between complete original component requests.
    Success establishes only the closed decision-leader material-variant
    relation. Every child still needs fresh material checking; no selection,
    material or export capability is created here. *)
module S = Bioc_domain.Policy_component_selection_request
module W = Bioc_checker.Work_budget

val profile : string

(** Check the complete census in ASCII-ID order, including the anchor itself.
    The caller supplies its bounded outer-work owner. All reconstruction,
    complete comparisons and canonical identities are charged to that owner;
    exhaustion propagates without being classified as child ineligibility. *)
val check : budget:W.t -> request:S.t -> unit
