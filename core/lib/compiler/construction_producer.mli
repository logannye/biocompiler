(** Deterministic untrusted proposals from complete supplied construction
    authority. No private checker reconstruction is reused. *)
val implementation_version : string
module Limits : sig
  type t
  (* Optional reductions support explicitly bounded producer runs. No ceiling
     can exceed the legacy residue limits or the native fixed work limit. *)
  val make : ?produced_residues:int -> ?final_residues:int -> ?work:int -> unit -> t
end
val construct : ?parent:Bioc_checker.Work_budget.t -> ?limits:Limits.t -> Bioc_domain.Construction.Request.t -> Bioc_domain.Construction_artifact.t
