(** Producer-side exact graph embeddings. Matching proposes correspondence and
    retains exhausted-search results as explicitly incomplete. Independent
    architecture verification never imports this module. *)
val implementation_version : string
val resource_profile : string
val max_work : int
type result
val instances : result -> Bioc_domain.Architecture_contract.Instance.t list
val states_examined : result -> int
val exhausted : result -> bool
val diagnostics : result -> string list
val instance_id : Bioc_domain.Architecture_refinement.t ->
  (Bioc_domain.Identity.Node.t * Bioc_domain.Identity.Node.t) list -> string
val instantiate : Bioc_domain.Architecture_refinement.t -> Bioc_domain.Architecture_contract.Instance.t -> Bioc_domain.Architecture_refinement.t
val match_refinement : ?budget:Bioc_checker.Work_budget.t -> ?circuit:Bioc_domain.Circuit_request.t ->
  ?max_states:int -> ?max_instances:int -> Bioc_domain.Architecture_refinement.t -> Bioc_domain.Behavior.t -> result
